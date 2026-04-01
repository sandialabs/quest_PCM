import os
import pandas as pd
from pyomo.environ import *
from datetime import datetime
from egret.data.model_data import ModelData
from egret.common.log import logger as egret_logger
from pcm.market_manager.egret_decorators import apply_egret_decorators
import pcm.market_manager.market_utils as MarketUtils

class MarketSimulator:
    """
    MarketSimulator manages the creation and execution of Day-Ahead (DA) and Real-Time (RT) market simulations.

    This class is responsible for:
        - Creating Egret ModelData objects for DA and RT markets.
        - Running unit commitment (UC) and economic dispatch (ED) solvers for DA and RT models.
        - Managing the simulation loop over the specified time horizon.
        - Storing and organizing simulation results for further analysis.

    Attributes:
        data_obj (DataManager): DataManager instance containing all input data and configuration.
        utils (MarketUtils): Stores helper methods for market simulation tasks.
        DA_result_dict (dict): Dictionary storing DA simulation results by day.
        RT_result_dict (dict): Dictionary storing RT simulation results by day and time.
    """

    def __init__(self, data_obj):
        """
        Initialize the MarketSimulator.

        Args:
            data_obj (DataManager): DataManager instance with input data and configuration.
        """
        self.data_obj = data_obj
        self.utils = MarketUtils
        self.DA_result_dict = {}
        self.RT_result_dict = {}
        self.PTDF_holder = {}
        self.egret_uc_model_generator, self.egret_uc_solver, self.egret_uc_result_exporter = apply_egret_decorators()
        
    def create_DA_RT_models(self):
        """
        Create Egret 'ModelData' objects for Day-Ahead and Real-Time markets.
        """
        json_folder = self.data_obj.json_file_directory
        self.DA_model = ModelData.read(os.path.join(json_folder, 'DA_data.json'))
        self.RT_model = ModelData.read(os.path.join(json_folder, 'RT_data.json'))
    
    def uc_solver(self, egret_md, model_relaxed=False, return_pyomo_result=False, tee=False):
        """
        Solve the unit commitment (UC) problem using Egret.

        Args:
            egret_md: Egret ModelData object.
            model_relaxed (bool): Whether to relax integer variables.
            return_pyomo_result (bool): If True, return both Pyomo and Egret solutions.
            tee (bool): If True, display solver output.

        Returns:
            Egret solution or (Pyomo solution, Egret solution) if return_pyomo_result is True.
        """
        if self.PTDF_holder:
            pyomo_md = self.egret_uc_model_generator(egret_md, PTDF_matrix_dict = self.PTDF_holder, relaxed=model_relaxed)
        else:
            pyomo_md = self.egret_uc_model_generator(egret_md, relaxed=model_relaxed)

        if model_relaxed:
            pyomo_md.dual = Suffix(direction=Suffix.IMPORT)
        pyomo_sol, _, _ = self.egret_uc_solver(
            pyomo_md,
            solver=self.data_obj.config["solver"],
            mipgap=self.data_obj.config.get("mipgap", 0.001),
            timelimit=None,
            solver_tee=tee,
            symbolic_solver_labels=False,
            solver_options=None,
            solve_method_options=None,
            relaxed=model_relaxed
        )
        egret_sol = self.egret_uc_result_exporter(pyomo_sol, relaxed=model_relaxed)
        if return_pyomo_result:
            return pyomo_sol, egret_sol
        else:
            return egret_sol    
        
    def simulate_market(self):
        """
        Coordinates the Day-Ahead and Real-Time market simulations for each day.
        
        Returns:
            None. Results are stored in self.DA_result_dict and self.RT_result_dict.
        """
        input_data = self.data_obj
        total_days = (input_data.end_date - input_data.start_date).days + 1 - bool(input_data.DA_lookahead_periods)
        DA_timekeys_set, RT_timekeys_set = self.utils.build_time_sets(
            total_days, input_data.DA_lookahead_periods, input_data.RT_resolution, input_data.RT_lookahead_periods
        )
        final_RT_sol = None  # To hold the final RT solution for initializing the next day's DA model

        for day in range(total_days):
            current_day = (input_data.start_date + pd.Timedelta(days=day)).date()
            DA_timekeys = DA_timekeys_set[day]
            RT_timekeys = RT_timekeys_set[day]

            # Simulate Day-Ahead market for the current day
            md_DA_truncated, md_DA_full, pyomo_DA_sol = self._simulate_day_ahead(
                current_day, DA_timekeys, day, final_RT_sol
            )
            self.DA_result_dict[current_day] = md_DA_truncated
            # Simulate Real-Time market for the current day
            self.RT_result_dict[current_day], final_RT_sol = self._simulate_real_time(
                current_day, RT_timekeys, day, pyomo_DA_sol, md_DA_full, RT_timekeys_set, final_RT_sol, self.data_obj.config.get("run_RTSCED_as")
            )

        # Evaluate degradation for any BESS in the system
        self.utils.evaluate_degradation(self.RT_model, self.RT_result_dict)
        pass
    
    def _simulate_day_ahead(self, current_day, DA_timekeys, day, initializer_model):
        """
        Runs the Day-Ahead simulation for a single day.

        Args:
            current_day (date): The current simulation day.
            DA_timekeys (list): List of DA time keys for the day.
            day (int): Day index in the simulation loop.
            initializer_model: Model to initialize DA status (from previous RT).

        Returns:
            tuple: (price_DA_truncated, pyomo_DA_sol, md_DA_sol)
        """
        md_DA = self.DA_model.clone_at_time_keys(list(map(str, DA_timekeys)))
        md_DA.data["current_market"] = "DA"

        # Initialize DA model with previous day's RT status if not the first day
        if day > 0 and initializer_model is not None:
            self.utils.populate_initial_status(initializer_model, md_DA, self.data_obj.RT_resolution)
        self.utils.fix_penalties_egret(md_DA, md_DA.data["system"], 1000)
        pyomo_DA_sol, md_DA_sol = self.uc_solver(md_DA, return_pyomo_result=True, tee = False)

        if day == 0:
            self.PTDF_holder = pyomo_DA_sol._PTDFs
        # Pricing and cost evaluation
        pricing_model = md_DA_sol.clone()
        self.utils.fix_all_binaries(md_DA_sol, pricing_model, 60, pricing_problem='LMP')
        self.utils.fix_penalties_egret(pricing_model, pricing_model.data["system"], 1)

        price_DA_sol = self.uc_solver(
            pricing_model, model_relaxed=True, tee=False
        )
        md_DA_truncated = price_DA_sol.clone_at_time_indices(list(range(24)))

        c_fixed, c_variable = self.utils.evaluate_system_costs_revenue(md_DA_truncated, md_DA_sol)
        print(f'SCUC Solved for {current_day} ! Commitment cost = {c_fixed:.2f}, Predicted Production cost = {c_variable:.2f}')

        return md_DA_truncated, price_DA_sol, pyomo_DA_sol

    def _simulate_real_time(self, current_day, RT_timekeys, day, pyomo_DA_sol, md_DA_sol, RT_timekeys_set, initializer_model, mode):
        """
        Unified Real-Time simulation routine that supports both LP (relaxed) and MILP workflows.

        Args:
            current_day (date): Current simulation date.
            RT_timekeys (list): Time keys for the RT model clone.
            day (int): Day index in the simulation loop.
            pyomo_DA_sol: Pyomo solution from the DA run (used to set SoC/resets).
            md_DA_sol: (optional) DA model solution used by MILP path for binary fixes.
            RT_timekeys_set: all RT timekey groups for the entire simulation horizon.
            initializer_model: model to initialize RT initial state from previous RT.
            mode (str): 'LP' for the relaxed SCED flow, 'MILP' for integer unit-level RT flow.

        Returns:
            tuple: (rt_results_dict, last_truncated_model_for_next_day)
        """
        input_data = self.data_obj
        RT_model_length = input_data.RT_lookahead_periods + 1

        # Base RT model (cloned to the day's full RT horizon)
        md_RT = self.RT_model.clone_at_time_keys(list(map(str, RT_timekeys)))
        md_RT.data["current_market"] = "RT"

        # ensure RT model has SoC/other resolution adjustments from DA pyomo solution
        self.utils.evaluate_RT_resolution_SoC(pyomo_DA_sol, md_RT)

        # mode-specific global preparations
        if mode == "LP":
            # relaxed/LP flow tends to use light penalties and full binary-fixing from DA solve
            self.utils.fix_penalties_egret(md_RT, md_RT.data["system"], 1)
            if md_DA_sol is not None:
                self.utils.fix_all_binaries(md_DA_sol, md_RT, input_data.RT_resolution)
        else:  # MILP
            # MILP flow uses DA commitment to set slow-unit behavior and stronger penalties during solve
            if md_DA_sol is not None:
                self.utils.fix_slow_units(md_DA_sol, md_RT, input_data.RT_resolution)

        rt_results = {}
        last_truncated = None

        # iterate RT periods (sliding-window/rolling horizon)
        for rt_time_idx, rt_period in enumerate(input_data.RT_periods):
            # clock for logging
            current_time = f"{((rt_period-1)*5)//60:02d}:{((rt_period-1)*5)%60:02d}"

            end_idx = min(rt_time_idx + RT_model_length, len(RT_timekeys_set[day]))
            current_RT_timekeys = RT_timekeys_set[day][rt_time_idx:end_idx]
            md_RT_current = md_RT.clone_at_time_keys(list(map(str, current_RT_timekeys)))
            md_RT_current.data["system"]["timestamp"] = [current_time]

            # initialize state-of-charge and status from prior RT model if available
            if current_RT_timekeys[0] > 1 and initializer_model is not None:
                self.utils.populate_initial_status(initializer_model, md_RT_current, input_data.RT_resolution)

            if mode == "LP":
                # relaxed SCED solve (try then fallback relaxing PHS binaries if solver fails)
                try:
                    md_RT_sol = self.uc_solver(md_RT_current, model_relaxed=True)
                except Exception:
                    # fallback: relax PHS binaries and retry
                    print(f"SCED failed for {current_day} at {current_time}. Relaxing PHS binary variables.")
                    self.utils.relax_PHS_binaries(md_RT_current)
                    md_RT_sol = self.uc_solver(md_RT_current, model_relaxed=True)

                # truncated (first-period) solution returned for downstream use
                last_truncated = md_RT_sol.clone_at_time_indices([0])

            else:  # MILP path
                # stronger penalties for integer solve
                self.utils.fix_penalties_egret(md_RT_current, md_RT_current.data["system"], 1000)

                # solve MILP to get integer commitment and dispatch (return both pyomo and egret results)
                pyomo_RT_sol, md_RT_sol = self.uc_solver(md_RT_current, return_pyomo_result=True)

                # build pricing problem: fix binaries from integer solve, relax, and resolve for prices
                price_RT_model = md_RT_current.clone()
                self.utils.fix_all_binaries(md_RT_sol, price_RT_model, 60)
                self.utils.fix_penalties_egret(price_RT_model, price_RT_model.data["system"], 1)
                price_RT_sol = self.uc_solver(price_RT_model, model_relaxed=True, tee=False)

                last_truncated = price_RT_sol.clone_at_time_indices([0])

            # evaluate costs vs DA schedule (md_DA_sol is expected)
            _, c_variable = self.utils.evaluate_system_costs_revenue(last_truncated, md_DA_sol, evaluate_revenue = True)
            print(f"SCED Solved for {current_day} at {current_time}! Production cost = {c_variable:.2f}. Objective = {last_truncated.data['system'].get('total_cost', 0.0):.2f}")
            rt_results[current_time] = last_truncated

            # pass truncated model forward to initialize next sliding window / next day
            initializer_model = last_truncated

        return rt_results, initializer_model