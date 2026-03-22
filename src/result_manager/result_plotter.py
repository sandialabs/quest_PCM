import os
import pandas as pd
import numpy as np
import datetime
import src.result_manager.result_utils as utils

class ResultPlotter:
    """
    High-level plotter for Market results.

    The class accepts market results dictionary 
    to generate system-level and per-asset plots (dispatch, costs, LMP,
    reserves, storage dispatch/revenue/SOC/cost). Plot generation is
    delegated to the plotting helpers in src.result_manager.result_utils.

    Attributes

    RT_res_dict (dict): Full runtime results dictionary.
    result_directory (str): Output directory for plot files.
    start_date (str|datetime): Start timestamp for the x axis.
    RT_resolution (int): Time-step resolution in minutes.
    enable_plotly (bool): Enable Plotly outputs where supported.
    plotter_x_axis (DatetimeIndex): Generated time index for plots.
    plot_colors (dict): Mapping of technology/series names to colors.
    """
    def __init__(self, rt_result_dict, output_directory, start_date, time_resolution, enable_plotly, current_market):
        """
        Initialize a ResultPlotter.

        Parameters

        rt_result_dict (dict): Results returned by the market
        simulation. Expected keys include "elements" and "system".
        output_directory (str): Directory where plot outputs will be written.
        start_date (str|datetime): Timestamp or parseable date string for
        the plotting x-axis start.
        time_resolution (int): Resolution in minutes for time steps.
        enable_plotly (bool): If True, enable Plotly output paths where
        supported by the plotting utilities.
        """
        self.RT_res_dict = rt_result_dict
        self.result_directory = output_directory
        self.start_date = start_date
        self.RT_resolution = time_resolution
        self.enable_plotly = enable_plotly
        self.current_market = current_market

        self.gen_dat = self.RT_res_dict["elements"]["generator"]
        self.storage_dat = self.RT_res_dict["elements"]["storage"]
        self.load_dat = self.RT_res_dict["elements"]["load"]
        self.bus_dat = self.RT_res_dict["elements"]["bus"]
        self.system_dat = self.RT_res_dict["system"]

        self.utils = utils
        self.plotter_x_axis = pd.date_range(start=self.start_date, periods=len(self.system_dat["time_keys"]), freq=f'{self.RT_resolution}min')
        self.tech_plot_colors()

    def tech_plot_colors(self):
        """
        Initialize the default color mapping for technology labels.

        Sets self.plot_colors to a consistent mapping used across plots so
        color assignments remain stable between figures.
        """
        self.plot_colors = {
            # Fossil Fuels
            'Coal': "#343232",          # Dark Gray
            'Oil': "#5B5858",           # Medium Gray
            'Oil CT': "#837D7D",        # Light Gray
            'Oil ST': '#C0C0C0',        # Very Light Gray
            'NG': "#D48F28",            # Muted Blue (Gas blend)
            'Gas CC': "#784D0D",        # Lighter Blue
            'Gas CT': "#AD7521",        # Mid Blue
            'thermal': '#9CB446',         # Burnt Orange (thermal gen)    
            # Nuclear
            'Nuclear': "#36031F",       # Deep Red
            # Hydro
            'Hydro': "#1F77B4",         # Rich Blue
            'PHS': "#6BAED6",           # Slate Blue
            # Renewables
            'Wind': '#228B22',          # Forest Green
            'Solar': '#FFD700',         # Gold
            'Solar PV': "#DF9B1C",      # Orange
            'CSP': '#FF8C00',           # Dark Orange
            'Solar RTPV': '#F0E68C',    # Khaki
            'RTPV': '#EEE8AA',          # Pale Goldenrod
            'Geothermal': '#A0522D',    # Sienna Brown
            # Storage
            'BESS': "#D75DE2",          # Sky Blue
            'Storage': "#CAADE6",       # Light Blue
            'Generic': "#BB64ED",       # Cornflower Blue
            'CAES': "#D21EB4",          # Chocolate
            'Hydrogen': "#DA70A2",      # Orchid
            'Storage Charge': "#F9C8F8",# Hot Pink
            'Storage Discharge': "#9E29C5", # Deep Pink
            # Curtailment / Overgeneration
            'Curtailment': "#F46074",   
            "Overgeneration": "#5F262E" ,
            #Costs
            "Thermal Fixed Cost": "lightblue",
            "Thermal Variable Cost": "orange",
            "Storage Cost": "lightgreen",
            #storage variables 
            'P_discharge': "#FF8800",   # Orange-Red
            'P_RegUP':     "#CF9952",   # Bright Yellow
            'P_SP':        "#AFDA14",   # Strong Blue
            'P_NSP':       "#A1F3C3",   # Pink/Magenta
            'P_SUPP':      "#A6E8F8",   # Green
            'P_charge':    "#722585",   # Sky Blue
            'P_RegDOWN':   "#E9A2D7",   # Deep Teal
            'Energy revenue': "#FF8800", 
            'RegUp revenue': "#CF9952",   
            'RegDown revenue': "#AFDA14",
            'SP revenue': "#A6E8F8",
            'NSP revenue': "#722585",
            'SUPP revenue': "#E9A2D7",
            'Operational Cost': "#1F77B4"
        }

    def extract_records(self, data, type_field, value_field):
        """
        Extract labeled time-series records from a nested result mapping.

        Parameters

        data (dict): Mapping of item keys to their result dicts (e.g., gens,
        storage, buses).
        type_field (str): Key in each item used to produce the series label
        (e.g., 'category' or 'fuel').
        value_field (str): Key or nested key name where the numeric series
        (list of values) are stored.

        Returns

        list of dict: Each element has keys 'type' (label) and 'values'
        (list of numeric values) suitable for constructing DataFrames.
        """
        records = []
        for k, v in data.items():
            if not isinstance(v, dict):
                continue
            type_value = v.get(type_field, type_field)
            # Try direct key, else look nested
            if k == value_field:
                values_list = v.get("values",[])
            else:
                values_list = v.get(value_field, {}).get("values",[])
            if values_list:
                records.append({"type": type_value, "values": values_list})
        return records
        
    def populate_plot_dict(self, plt_color_dict, ylabel_name, plt_units, ref_val_name, plt_title, plt_type):
        """
        Build and return a plotting-metadata dictionary for the utilities.

        Parameters

        plt_color_dict (dict|None): Mapping of series names to color hexes.
        ylabel_name (str): Y-axis label text.
        plt_units (str): Unit string for legend/labels (e.g., 'MW', '$').
        ref_val_name (str|None): Optional reference series name (e.g., 'Demand').
        plt_title (str): Title used for the plot.
        plt_type (str): Plot type hint used by plotting helpers ('fill',
        'bar', 'step', 'linear', etc.).

        Returns

        dict: Contains axis, labels, color mapping, title and width metadata.
        """
        return {"time_resolution": self.RT_resolution,
                "start_date": self.start_date,
                "result_directory": self.result_directory,
                "plotter_x_axis": self.plotter_x_axis,
                "color_dict": plt_color_dict,
                "ylabel" : ylabel_name,
                "unit" : plt_units,
                "reference_val_name" : ref_val_name,
                "title": plt_title,
                "plot_type": plt_type,
                "width_days": pd.Timedelta(minutes=self.RT_resolution).total_seconds() / 86400.0 * 0.9}
    
    def plot_dispatch_stackgraphs(self):
        """
        Aggregate generator, storage and curtailment time-series and plot a
        system dispatch stacked area chart.

        The method buckets dispatch by technology, constructs the demand
        reference series and delegates drawing to utils.plot_stackgraphs.
        """
        # Plot the dispatch stackgraph
        gen_dispatch = self.extract_records(self.gen_dat, 'category', 'pg')
        storage_discharge = self.extract_records(self.storage_dat, 'fuel', 'p_discharge')
        storage_charge = self.extract_records(self.storage_dat, 'fuel', 'p_charge')
        curtailment = self.extract_records(self.bus_dat, 'Curtailment', 'p_balance_violation')
        storage_charge = [{k: [-x for x in v] if isinstance(v, list) else v for k, v in d.items()} for d in storage_charge]
        for d in storage_discharge:
            d["type"] = "Storage Discharge" 
        for d in storage_charge:
            d["type"] = "Storage Charge"
        df = pd.DataFrame(gen_dispatch + storage_discharge + storage_charge + curtailment)

        # Step 2: Create pivot table (e.g., sum of 'value' grouped by 'a')
        result = df.groupby('type')['values'].agg(lambda x: np.sum(x.tolist(), axis=0).tolist())
        result = pd.DataFrame(result.tolist(), index=result.index).T
        #desired_order = ["Nuclear", "Coal", "Oil", "NG", "Hydro", "Solar", "Wind", "Storage Discharge", "Storage Charge", "Curtailment"]
        desired_order = ["Nuclear", "Coal", "Oil CT", "Oil ST", "Gas CC", "Gas CT", "Hydro", "Geothermal", "CSP", "Solar PV", "Solar RTPV", "Wind", 
                         "Storage Discharge", "Storage Charge", "Curtailment","Overgeneration"]
        result = result[[col for col in desired_order if col in result.columns]]
        
        # Total Demand for Plotting
        overall_demand = self.extract_records(self.load_dat, 'load', 'p_load')
        df_demand = pd.DataFrame(overall_demand)
        overall_demand =  df_demand.groupby('type')['values'].agg(lambda x: np.sum(x.tolist(), axis=0).tolist())
        overall_demand = pd.DataFrame(overall_demand.tolist(), index=overall_demand.index).T

        plt_color_dict = {c: self.plot_colors[c] for c in result.columns}
        plt_dict = self.populate_plot_dict(plt_color_dict, "Power (MW)", "MW", "Demand", "Overall Dispatch", "fill")
        
        self.utils.plot_stackgraphs(result, overall_demand, plt_dict, f"dispatch_{self.current_market}", self.enable_plotly)

    def plot_costs(self):
        """
        Aggregate and plot system cost components (thermal fixed and
        variable costs) as a stacked figure.

        Delegates rendering to utils.plot_stackgraphs.
        """
        # Plot stackgraph for costs
        gen_fixed_cost = self.extract_records(self.gen_dat, 'Thermal Fixed Cost', 'commitment_cost')
        gen_fixed_cost = [g for g in gen_fixed_cost if g.get('values') != []]
        gen_var_cost = self.extract_records(self.gen_dat, 'Thermal Variable Cost', 'production_cost')
        gen_var_cost = [g for g in gen_var_cost if g.get('values') != []]
       
        df_cost = pd.DataFrame(gen_fixed_cost + gen_var_cost)
        df_cost = df_cost.groupby('type')['values'].agg(lambda x: np.sum(x.tolist(), axis=0).tolist())
        df_cost = pd.DataFrame(df_cost.tolist(), index=df_cost.index).T
        if self.storage_dat:
            df_cost = df_cost[['Thermal Fixed Cost', 'Thermal Variable Cost']]
        else:
            df_cost = df_cost[['Thermal Fixed Cost', 'Thermal Variable Cost']]
        # Plot the data
        plt_color_dict = {c: self.plot_colors[c] for c in df_cost.columns}
        plt_dict = self.populate_plot_dict(plt_color_dict, "Cost ($)", "$", None, "Overall Costs", "bar")
        self.utils.plot_stackgraphs(df_cost, pd.Series(dtype= float), plt_dict, "cost",self.enable_plotly)

    def plot_lmp(self):
        """
        Plot locational marginal prices (LMP) for all buses.

        For small numbers of buses, static PNG output is enabled; for large
        numbers, PNG generation may be disabled to avoid very wide images.
        """
        bus_name = []
        bus_lmp = []
        for bus_idx in self.bus_dat:
            bus_name.append(self.bus_dat[bus_idx]["bus_name"])
            bus_lmp.append(self.bus_dat[bus_idx]["lmp"]["values"])

        df_lmp = pd.DataFrame(bus_lmp).T  # transpose so that rows=time steps
        df_lmp.columns = bus_name
        plt_dict = self.populate_plot_dict(None, "LMP ($/MWh)", "$", None, "Bus Locational Marginal Prices", "step")

        if len(df_lmp.columns) < 10:
            self.utils.plot_lines(df_lmp, plt_dict, f"bus_LMP_{self.current_market}", self.enable_plotly)
        else:
            self.utils.plot_lines(df_lmp, plt_dict, f"bus_LMP_{self.current_market}", plotly_enabled = True, png_enabled = False)

    def plot_reserves(self):
        """
        Plot system- and area-level reserve supply stacks and clearing prices.

        Iterates present reserve products, builds stacked supply plots and
        time-series of clearing prices for both system-level and per-area
        markets, and delegates plotting to the shared utilities.
        """
        product_key_map = {
            "spinning_reserve_requirement": "spinning_reserve_supplied",
            "non_spinning_reserve_requirement": "non_spinning_reserve_supplied",
            "regulation_up_requirement": "regulation_up_supplied",
            "regulation_down_requirement": "regulation_down_supplied",
            "flexible_ramp_up_requirement": "flexible_ramp_up_supplied",
            "flexible_ramp_down_requirement": "flexible_ramp_down_supplied",
            "supplemental_reserve_requirement": "supplemental_reserve_supplied"
        }
        system_clearing_prices = {}
        for reserve_type, supply_key in product_key_map.items():
            if reserve_type in self.system_dat:
                # Plot the reserve stackgraph
                gen_reserve = self.extract_records(self.gen_dat, 'category', supply_key)
                storage_reserve = self.extract_records(self.storage_dat, 'fuel', supply_key)
                df = pd.DataFrame(gen_reserve + storage_reserve)
                # Step 2: Create pivot table (e.g., sum of 'value' grouped by 'a')
                result = df.groupby('type')['values'].agg(lambda x: np.sum(x.tolist(), axis=0).tolist())
                result = pd.DataFrame(result.tolist(), index=result.index).T
                desired_order = ["Nuclear", "Coal", "Oil CT", "Oil ST", "Gas CC", "Gas CT", "Storage"]
                result = result[[col for col in desired_order if col in result.columns]]
        
                # Total Reserve Requirement for Plotting
                reserve_req = self.system_dat[reserve_type].get('values', [0]*len(result))
                reserve_req = pd.DataFrame({reserve_type: reserve_req})

                plt_color_dict = {c: self.plot_colors[c] for c in result.columns}
                plt_dict = self.populate_plot_dict(plt_color_dict, "Power (MW)", "MW", "requirement", f"{reserve_type.replace('_requirement', '').replace('_', ' ').title()}", "fill")
                plt_name = f"{reserve_type.replace('_requirement', '')}"
                self.utils.plot_stackgraphs(result, reserve_req, plt_dict, f"system_{plt_name}_{self.current_market}", self.enable_plotly, subdir_name=f"Ancillary_Services_{self.current_market}")

                system_clearing_prices[f"system_{plt_name}"] = self.system_dat[f"{plt_name}_price"]["values"]
        if system_clearing_prices:
            df_system_prices = pd.DataFrame(system_clearing_prices)
            plt_dict = self.populate_plot_dict(None, "Clearing price ($/MW)", "$", None, "System Ancillary Service Clearing Prices", "step")
            self.utils.plot_lines(df_system_prices, plt_dict, f"system_AS_clearing_prices_{self.current_market}", self.enable_plotly, subdir_name=f"Ancillary_Services_{self.current_market}")

        area_clearing_prices = {}       
        for area in self.RT_res_dict["elements"].get("area", {}):
            area_dat = self.RT_res_dict["elements"]["area"][area]
            for reserve_type, supply_key in product_key_map.items():
                if reserve_type in area_dat:
                    # Plot the reserve stackgraph
                    current_area_gens = {k: v for k, v in self.gen_dat.items() if v.get("area") == area}
                    gen_reserve = self.extract_records(current_area_gens, 'category', supply_key)
                    current_area_storage = {k: v for k, v in self.storage_dat.items() if v.get("area") == area}
                    storage_reserve = self.extract_records(current_area_storage, 'fuel', supply_key)
                    df = pd.DataFrame(gen_reserve + storage_reserve)
                    # Step 2: Create pivot table (e.g., sum of 'value' grouped by 'a')
                    result = df.groupby('type')['values'].agg(lambda x: np.sum(x.tolist(), axis=0).tolist())
                    result = pd.DataFrame(result.tolist(), index=result.index).T
                    desired_order = ["Nuclear", "Coal", "Oil CT", "Oil ST", "Gas CC", "Gas CT", "Storage"]
                    result = result[[col for col in desired_order if col in result.columns]]
        
                    # Total Reserve Requirement for Plotting
                    reserve_req = area_dat[reserve_type].get('values', [0]*len(result))
                    reserve_req = pd.DataFrame({reserve_type: reserve_req})

                    plt_color_dict = {c: self.plot_colors[c] for c in result.columns}
                    plt_dict = self.populate_plot_dict(plt_color_dict, "Power (MW)", "MW", "requirement", f"Area {area} {reserve_type.replace('_requirement', '').replace('_', ' ').title()}", "fill")
                    plt_name = f"{reserve_type.replace('_requirement', '')}"
                    self.utils.plot_stackgraphs(result, reserve_req, plt_dict, f"area_{area}_{plt_name}_{self.current_market}", self.enable_plotly, subdir_name=f"Ancillary Services_{self.current_market}")

                    area_clearing_prices[f"area_{area}_{plt_name}"] = area_dat[f"{plt_name}_price"]["values"]
        if area_clearing_prices:
            df_area_prices = pd.DataFrame(area_clearing_prices)
            plt_dict = self.populate_plot_dict(None, "Clearing price ($/MW)", "$", None, "Area Ancillary Service Clearing Prices", "step")
            self.utils.plot_lines(df_area_prices, plt_dict, f"area_AS_clearing_prices_{self.current_market}", self.enable_plotly, subdir_name=f"Ancillary Services_{self.current_market}")

    def storage_dispatch_plotter(self, storage_name, input_dict, plt_name, subdirectory_name=""):
        """
        Create and plot dispatch stacks for a single storage asset.

        Parameters

        storage_name (str): Display name for the storage asset.
        input_dict (dict): Storage-specific result dictionary containing
        dispatch and ancillary service series.
        plt_name (str): Plot base name used by the utilities.
        subdirectory_name (str): Optional results subdirectory for this storage.
        """
        storage_discharge_power = self.extract_records(input_dict, 'P_discharge', 'p_discharge_only')
        storage_charge_power = self.extract_records(input_dict, 'P_charge', 'p_charge_only')
        storage_charge_power = [{k: [-x for x in v] if isinstance(v, list) else v for k, v in d.items()} for d in storage_charge_power]

        storage_regup = self.extract_records(input_dict, 'P_RegUP', 'regulation_up_supplied')
        storage_regdown = self.extract_records(input_dict, 'P_RegDOWN', 'regulation_down_supplied')
        storage_regdown = [{k: [-x for x in v] if isinstance(v, list) and None not in v else v for k, v in d.items()} for d in storage_regdown]
        storage_sp = self.extract_records(input_dict, 'P_SP', 'spinning_reserve_supplied')
        storage_nsp = self.extract_records(input_dict, 'P_NSP', 'non_spinning_reserve_supplied')
        storage_supp = self.extract_records(input_dict, 'P_SUPP', 'supplemental_reserve_supplied')

        storage_dispatch = pd.DataFrame(storage_discharge_power + storage_charge_power + 
                                        storage_regup + storage_regdown + storage_sp + 
                                        storage_nsp + storage_supp)
        
        storage_dispatch = storage_dispatch[storage_dispatch['values'].apply(lambda x: None not in x)]
        storage_dispatch = storage_dispatch.groupby('type')['values'].agg(lambda x: np.sum(x.tolist(), axis=0).tolist())
        storage_dispatch = pd.DataFrame(storage_dispatch.tolist(), index=storage_dispatch.index).T
        
        desired_order = ['P_discharge', 'P_RegUP', 'P_SP', 'P_NSP', 'P_SUPP', 'P_charge', 'P_RegDOWN']
        storage_dispatch = storage_dispatch[[col for col in desired_order if col in storage_dispatch.columns]]
        
        plt_color_dict = {c: self.plot_colors[c] for c in storage_dispatch.columns}
        plt_dict = self.populate_plot_dict(plt_color_dict, "Power (MW)", "MW", None, f"{storage_name} Dispatch", "bar")
        
        self.utils.plot_stackgraphs(storage_dispatch, pd.Series(dtype= float), plt_dict, plt_name, self.enable_plotly, subdir_name = subdirectory_name)

    def storage_revenue_plotter(self, storage_name, input_dict, plt_name, subdirectory_name=""):
        """
        Aggregate and plot revenue streams for a storage asset.

        Builds energy and ancillary-service revenue series and delegates the
        plot to utils.plot_stackgraphs.

        Parameters are the same as storage_dispatch_plotter.
        """
        storage_energy_revenue = self.extract_records(input_dict, 'Energy revenue', 'energy_revenue')
        storage_regup_revenue = self.extract_records(input_dict, 'RegUp revenue', 'regulation_up_revenue')
        storage_regdown_revenue = self.extract_records(input_dict, 'RegDown revenue', 'regulation_down_revenue')
        storage_sp_revenue = self.extract_records(input_dict, 'SP revenue', 'spinning_reserve_revenue')
        storage_nsp_revenue = self.extract_records(input_dict, 'NSP revenue', 'non_spinning_reserve_revenue')
        storage_supp_revenue = self.extract_records(input_dict, 'SUPP revenue', 'supplemental_reserve_revenue')
        
        storage_revenue = pd.DataFrame(storage_energy_revenue + storage_regup_revenue + storage_regdown_revenue + storage_sp_revenue + 
                                        storage_nsp_revenue + storage_supp_revenue)
        
        storage_revenue = storage_revenue[storage_revenue['values'].apply(lambda x: None not in x)]
        storage_revenue = storage_revenue.groupby('type')['values'].agg(lambda x: np.sum(x.tolist(), axis=0).tolist())
        storage_revenue = pd.DataFrame(storage_revenue.tolist(), index=storage_revenue.index).T
        
        desired_order = ['Energy revenue', 'RegUp revenue', 'RegDown revenue', 'SP revenue', 'NSP revenue', 'SUPP revenue']
        storage_revenue = storage_revenue[[col for col in desired_order if col in storage_revenue.columns]]
        
        plt_color_dict = {c: self.plot_colors[c] for c in storage_revenue.columns}
        plt_dict = self.populate_plot_dict(plt_color_dict, "Revenue ($)", "$", None, f"{storage_name} Revenue", "bar")
        
        self.utils.plot_stackgraphs(storage_revenue, pd.Series(dtype= float), plt_dict, plt_name, self.enable_plotly, subdir_name = subdirectory_name)

    def storage_soc_plotter(self, storage_name, input_dict, plt_name, subdirectory_name=""):
        """
        Plot the state-of-charge (SoC) time-series for a storage asset.

        Converts the SOC list into a single-column DataFrame and calls the
        line-plot helper.

        Parameters are the same as storage_dispatch_plotter.
        """
        storage_soc = self.extract_records(input_dict, 'State of Charge', 'state_of_charge')
        storage_soc = storage_soc[0]['values']
        
        storage_DA_soc = self.extract_records(input_dict, 'DA State of Charge Requirement', 'RT_SoC_requirement')
        storage_DA_soc = storage_DA_soc[0]['values'] 

        df_soc = pd.DataFrame({
            f"{storage_name} RT SoC": storage_soc,
            f"{storage_name} DA SoC": storage_DA_soc
        })

        plt_dict = self.populate_plot_dict(None, "State of Charge", "", None, f"{storage_name} State of Charge", "linear")
        self.utils.plot_lines(df_soc, plt_dict, plt_name, self.enable_plotly, subdir_name = subdirectory_name)

    def storage_cost_plotter(self, storage_name, input_dict, plt_name, subdirectory_name=""):
        """
        Plot operational costs for a storage asset.

        Extracts the operational cost time-series and sends it to the stack
        plot routine.

        Parameters are the same as storage_dispatch_plotter.
        """
        storage_cost = self.extract_records(input_dict, 'Operational Cost', 'operational_cost')
        storage_cost = storage_cost[0]['values']
        
        df_cost = pd.DataFrame(storage_cost)  # transpose so that rows=time steps
        df_cost.columns = [storage_name]

        color_dict = {storage_name: self.plot_colors['Operational Cost']}
        plt_dict = self.populate_plot_dict(color_dict, "Operational Cost", "", None, f"{storage_name} Operational Cost", "bar")
        self.utils.plot_stackgraphs(df_cost, pd.Series(dtype= float), plt_dict, plt_name, self.enable_plotly, subdir_name = subdirectory_name)

    def plot_storage_degradation(self, storage_name, input_dict, plt_name, subdirectory_name=""):
        """
        Plot battery capacity degradation for a storage asset.

        Extracts the per-chemistry capacity degradation time-series and
        delegates plotting to the line-plot helper.

        Parameters are the same as storage_dispatch_plotter.
        """
        degradation_data = {}
        for chemistry in ["LMO", "LFP", "NMC", "NCA"]:
            deg_record = self.extract_records(input_dict, f'{chemistry}', f'capacity_after_degradation_{chemistry}')
            if deg_record:
                degradation_data[chemistry] = deg_record[0]['values']
        
        df_deg = pd.DataFrame(degradation_data)  # transpose so that rows=time steps

        plt_dict = self.populate_plot_dict(None, "Capacity (MWh)", "MWh", None, f"{storage_name} Potential Cyclic Degradation", "linear")
        self.utils.plot_lines(df_deg, plt_dict, plt_name, self.enable_plotly, subdir_name = subdirectory_name)

    def plot_PHS_unit_schedule(self, storage_name, input_dict, plt_name, subdirectory_name=""):
        pass
        unit_schedules = {}
        plt_color_dict = {}
        genmode_dict = input_dict['Unit_GenMode']
        pumpmode_dict = input_dict['Unit_PumpMode']
        for u in range(input_dict["num_units"]):
            genmode_list = genmode_dict[(storage_name,u)]['values']
            pumpmode_list = pumpmode_dict[(storage_name,u)]['values']
            
            unit_schedules[f"{storage_name} Unit {u} Schedule"] = np.array(genmode_list) - np.array(pumpmode_list)
            current_schedule = {}
            current_schedule["Gen Mode"] = np.array(genmode_list)
            current_schedule["Pump Mode"] = -1*np.array(pumpmode_list)

            df_schedule = pd.DataFrame(current_schedule)  # transpose so that rows=time steps
            plt_color_dict[f"{storage_name} Unit {u} Schedule"] = "#1F77B4"
    
            plt_dict = self.populate_plot_dict(None, "Unit Status", "Status", None, f"Unit {u} Status", "bar")
            plt_name = f"{storage_name}_Unit_{u}_Schedule"
            self.utils.plot_lines(df_schedule, plt_dict, plt_name, plotly_enabled = False, subdir_name = subdirectory_name)
        
        plotly_plot_dict = self.populate_plot_dict(plt_color_dict, "Unit Status", "", None, f"{storage_name} Unit Schedules (+1 for generation mode, -1 for pumping mode, 0 for idle)", "bar")
        plotly_plot_name = f"{storage_name}_Unit_Schedules"
        self.utils.plot_lines(pd.DataFrame(unit_schedules), plotly_plot_dict, plotly_plot_name, plotly_enabled = self.enable_plotly, png_enabled = False, subdir_name = subdirectory_name)

    def plot_storage_data(self):
        """
        Create all storage-related plots for the system.

        If no storage is present, the method returns immediately. Otherwise it
        produces aggregated and per-asset dispatch, revenue, SOC and cost plots,
        organizing per-asset outputs into optional subdirectories.
        """
        #Plot overall dispatch of storage in energy and ancillary service markets
        if not self.storage_dat:
            return
        self.storage_dispatch_plotter("Aggregated Storage", self.storage_dat, "Aggregated_Storage_Dispatch")
        for s_name, s_dict in self.storage_dat.items():

            self.storage_dispatch_plotter(s_name, s_dict, s_name + "_Dispatch", subdirectory_name = s_name)
            self.storage_revenue_plotter(s_name, s_dict,  s_name + "_Revenue", subdirectory_name = s_name)
            self.storage_soc_plotter(s_name, s_dict, s_name + "_SoC", subdirectory_name = s_name)
            self.storage_cost_plotter(s_name, s_dict, s_name + "_Cost", subdirectory_name = s_name)
            if s_dict["storage_type"] == "BESS":
                self.plot_storage_degradation(s_name, s_dict, s_name + "_Degradation", subdirectory_name = s_name)
            if s_dict["storage_type"] == "PHS":
                self.plot_PHS_unit_schedule(s_name, s_dict, s_name + "_Degradation", subdirectory_name = s_name)