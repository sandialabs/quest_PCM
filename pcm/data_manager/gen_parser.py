# -------------------------------------------------------------------------
# Generator Parser Module
# -------------------------------------------------------------------------

import pandas as pd
import copy as copy
import pcm.data_manager.input_utils as input_utils
import warnings 

class GenParser:
    """
    GenParser is responsible for parsing generator-related data, including thermal and renewable generators,
    from the provided configuration and dataframes.

    Attributes:
        config (dict): Configuration dictionary loaded from YAML.
        data_df (dict): Dictionary mapping file keys to pandas DataFrames.
        utils: Utility module for helper functions.
        thermal_gen_dict (dict): Parsed thermal generator attributes keyed by GEN UID.
        renewable_DA_dict (dict): Parsed DA time series for renewable generators.
        renewable_RT_dict (dict): Parsed RT time series for renewable generators.
    """

    def __init__(self, config, data_df):
        """
        Initialize the GenParser.

        Args:
            config (dict): Configuration dictionary loaded from YAML.
            data_df (dict): Dictionary mapping file keys to pandas DataFrames.
        """
        self.config = config
        self.data_df = data_df
        self.utils = input_utils
        self.thermal_gen_dict = {}
        self.renewable_DA_dict = {}
        self.renewable_RT_dict = {}

    def parse_thermal_generators(self, bus_dict):
        """
        Parse thermal generator data from 'gen.csv' and initial status from 'gen_initial_status.csv'.

        Populates the thermal_gen_dict with attributes for each thermal generator,
        including ramp rates, startup/shutdown costs, fuel curves, initial status, and ancillary service eligibility.

        Args:
            bus_dict (dict): Dictionary of bus attributes keyed by bus ID.

        Raises:
            ValueError: If 'gen.csv' or 'gen_initial_status.csv' is missing.
        """
        generator_dict = self.thermal_gen_dict
        df_gendata = self.data_df.get("gen")
        if df_gendata is None:
            raise ValueError("gen.csv file must be present in the data folder.")
        
        for _, row in df_gendata.iterrows():
            if row["Type"] != "Thermal":
                continue

            gen_id = str(row.get("GEN UID", row.get("Gen Name")))
            pmax = float(row.get("PMax MW", row.get("Max Cap")))
            pmin = float(row.get("PMin MW", row.get("Min Cap")))
            
            generator_dict[gen_id] = {
                "generator_type": "thermal",
                "bus": str(row.get("Bus ID", row.get("Bus No."))),
                "area": bus_dict[str(row.get("Bus ID", row.get("Bus No.")))]["area"],
                "zone": bus_dict[str(row.get("Bus ID", row.get("Bus No.")))]["zone"],
                "fuel": str(row.get("Fuel")),
                "category": str(row.get("Category")),
                "in_service": bool(row.get("In Service",True)),
                "p_min": pmin,
                "p_max": pmax,
                "ramp_up_60min": float(row.get("Ramp Rate MW/Min")) * 60,
                "ramp_down_60min": float(row.get("Ramp Rate MW/Min")) * 60,
                "startup_capacity": float(row.get("Startup Capacity", pmin)),
                "shutdown_capacity": float(row.get("Shutdown Capacity", pmin)),
                "min_up_time": float(row.get("Min Up Time Hr")),
                "min_down_time": float(row.get("Min Down Time Hr")),
                "initial_status": float(row.get("Initial Time Hr")),  
                "initial_p_output": float(row.get("Initial Power MW")), 
                "non_fuel_startup_cost": float(row.get("Non Fuel Start Cost $",0.0)),
                "shutdown_cost": float(row.get("Shutdown Cost $",0.0)),
                "fuel_cost": float(row.get("Fuel Price $/MMBTU")),
                "agc_capable" : bool(row.get("AGC capable", True)),
                "agc_marginal_cost" : float(row.get("Reg offer $/MW/hr", 0.0)),
                "p_max_agc" : float(row.get("Pmax AGC MW", pmax)),
                "p_min_agc" : float(row.get("Pmin AGC MW", pmin)),
                "ramp_agc" : row.get("Ramp Rate MW/Min"),
                "fast_start" : bool(row.get("Fast start", True)), 
                "spinning_capacity": float(row.get("Spin offer MW", pmax)),
                "spinning_cost" : float(row.get("Spin offer $/MW/hr", 0.0)),
                "non_spinning_capacity" : float(row.get("NonSpin offer MW", pmax)),   
                "non_spinning_cost" : float(row.get("NonSpin offer $/MW/hr", 0.0)),
                "supplemental_start": bool(row.get("Fast start", True)),
                "supplemental_spinning_capacity": float(row.get("CR offer MW", pmax)),
                "supplemental_non_spinning_capacity": float(row.get("CR offer MW", pmax)),
                "supplemental_cost": float(row.get("Supp offer $/MW/hr", 0.0))
            }

            # Parse startup fuel data if available
            startup_fuel_data = []
            startup_fuel_columns = [
                ("Start Time Hot Hr", "Start Heat Hot MBTU"),
                ("Start Time Warm Hr", "Start Heat Warm MBTU"),
                ("Start Time Cold Hr", "Start Heat Cold MBTU")
            ]
            for time_col, heat_col in startup_fuel_columns:
                time_val = row.get(time_col)
                heat_val = row.get(heat_col)

                if (
                    pd.notna(time_val) and
                    pd.notna(heat_val) and
                    float(time_val) != 0     # <-- exclude zero start times
                ):
                    startup_fuel_data.append([int(time_val), float(heat_val)])
            if startup_fuel_data:
               
                # Sort by time-lag (just in case)
                startup_fuel_data.sort(key=lambda x: x[0])

                first_lag = startup_fuel_data[0][0]
                min_down = float(row.get("Min Down Time Hr"))
                cold_heat = float(row.get("Start Heat Cold MBTU"))

                if first_lag != min_down:
                    # print(
                    #     f"DATA Warning: The first startup lag for thermal generator={gen_id} "
                    #     f"(Lag = {first_lag} hr does not equal the minimum down time {min_down} hr). "
                    #     f"Setting startup_fuel to [[{min_down}, {cold_heat}]]."
                    # )
                    # DATA ERROR condition triggered
                    # Use Cold start heat (most conservative)
                    cold_heat = float(row.get("Start Heat Cold MBTU"))

                    startup_fuel_data = [[min_down, cold_heat]]
            
            generator_dict[gen_id]["startup_fuel"] = startup_fuel_data
            
            # Parse production fuel curve
            production_fuel_columns = [
                ("Output_pct_0", "HR_avg_0"),
                ("Output_pct_1", "HR_incr_1"),
                ("Output_pct_2", "HR_incr_2"),
                ("Output_pct_3", "HR_incr_3")
            ]
            def evaluate_piecewise_costs(production_fuel_columns, current_gen_df):
                """
                Helper to evaluate piecewise fuel costs for generator.
                """
                production_fuel = []
                pmax = float(row.get("PMax MW", row.get("Max Cap")))
                for idx, (power_col, heat_col) in enumerate(production_fuel_columns):
                    if power_col == "Output_pct_0":
                        power_component = current_gen_df[power_col] * pmax
                        fuel_component = current_gen_df[heat_col] / 1e3 * power_component
                    else:
                        power_component = current_gen_df[power_col] * pmax
                        fuel_component = production_fuel[idx-1][1] + current_gen_df[heat_col] / 1e3  * (power_component-production_fuel[idx-1][0])
                    production_fuel.append([float(power_component), float(fuel_component)])
                return production_fuel

            generator_dict[gen_id]["p_fuel"] = {
                "data_type": "fuel_curve",
                "values": evaluate_piecewise_costs(production_fuel_columns, row)
            }
 
    # -------------------------------------------------------------------------

    def parse_renewable_generators(self, bus_dict, time_settings):
        """
        Parse renewable generator data and time series from DA and RT renewable timeseries CSVs.

        Populates the renewable_DA_dict and renewable_RT_dict with time series for each renewable generator,
        including p_max and p_min (for non-dispatchable types).

        Args:
            time_settings (dict): Dictionary containing time filtering and period information.

        Raises:
            ValueError: If DA or RT renewable time series data is missing.
        """
        simulate_DA_only = self.config.get("simulate_DA_only", False)
        df_da = self.data_df.get("renewable_timeseries_DA")
        
        if df_da is None:
            warnings.warn(
                "DA renewable_timeseries CSV not found. Using each renewable generator's 'PMax MW' as a constant p_max profile.",
                UserWarning,
            )

        if not simulate_DA_only:
            df_rt = self.data_df.get("renewable_timeseries_RT", None)
            if df_rt is None:
                warnings.warn(
                    "RT renewable_timeseries CSV not found. Using each renewable generator's 'PMax MW' as a constant p_max profile.",
                    UserWarning,
                )
            df_da, df_rt = self.utils.filter_data_timesteps(time_settings, df_da, df_rt)
        else:
            df_da, df_rt = self.utils.filter_data_timesteps(time_settings, df_da, None)
            
        DA_dict = self.renewable_DA_dict
        RT_dict = self.renewable_RT_dict
        gen_data = self.data_df.get("gen")

        for _, row in gen_data.iterrows():
            if row["Type"] != "Renewable" and row["Type"] != "Fixed Renewable":
                continue

            gid = str(row.get("GEN UID", row.get("Gen Name")))
            bus = str(row.get("Bus ID", row.get("Bus No.")))
            area = bus_dict[str(row.get("Bus ID", row.get("Bus No.")))]["area"]
            zone = bus_dict[str(row.get("Bus ID", row.get("Bus No.")))]["zone"]
            category = str(row.get("Category"))
            base_pmax = float(row.get("PMax MW",  row.get("Max Cap")))
            in_srv = bool(row.get("In Service", True))
            fuel = str(row.get("Fuel"))
            is_nd = row["Type"] == "Fixed Renewable"

            # Always do DA
            ts_pairs = [(DA_dict, df_da, False)]
            # Add RT only if available
            if not simulate_DA_only:
                ts_pairs.append((RT_dict, df_rt, True))
            for ts_dict, df, is_rt in ts_pairs:
                if df is not None and gid in df.columns:
                    pmax_values = df[gid].tolist()
                else:
                    pmax_values = [base_pmax] * (
                            len(time_settings["RT_timekeys"]) if is_rt else len(time_settings["DA_timekeys"]))
                    
                ts_dict[gid] = {
                    "bus": bus,
                    "area": area,
                    "zone": zone,
                    "in_service": in_srv,
                    "fuel": fuel,
                    "category": category,
                    "generator_type": "renewable",
                    "p_max": {"data_type": "time_series", "values": pmax_values}
                }
                ts_dict[gid]["p_min"] = (
                    copy.copy(ts_dict[gid]["p_max"]) if is_nd else {
                        "data_type": "time_series",
                        "values": [0.0] * len(pmax_values)
                    }
                )
# -------------------------------------------------------------------------

