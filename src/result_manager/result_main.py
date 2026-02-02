import numpy as np
from functools import reduce
import pandas as pd
import copy
import os
import datetime
from .result_exporter import ResultExporter
from .result_plotter import ResultPlotter
from collections import defaultdict

class ResultManager():
    """
    Class for exporting and plotting simulation results.

    ResultManager accepts a market simulation object and provides methods
    to:

    construct output directories,
    merge DA and RT outputs into combined structures,
    write JSON and Excel summaries, and
    produce standard visualizations.
    Attributes

    DA_output_data (dict): Raw day-ahead result objects keyed by date.
    RT_output_data (dict): Raw real-time result objects keyed by date.
    all_config (dict): Full simulation configuration.
    input_data_ref (dict): Reference input structure used to trim outputs.
    RT_resolution (int): Real-time step size in minutes.
    start_date, end_date (date-like): Simulation horizon boundaries.
    base_result_directory (str): Top-level results folder created by the manager.
    """
    def __init__(self, market_obj):
        """
        Initialize the ResultManager.

        Parameters

        market_obj: Object returned by the market simulation which must expose:
        DA_result_dict and RT_result_dict (raw outputs),
        data_obj (with config, start_date, end_date, folder_path),
        DA_model (used to obtain input_data_ref).
        The constructor extracts commonly used metadata, resolution and plotting
        flags, and creates a base results directory via set_base_output_directory.
        """
        # Raw outputs provided by the market simulator
        self.DA_output_data = market_obj.DA_result_dict
        self.RT_output_data = market_obj.RT_result_dict

        # Reference data for exporters and metadata
        self.all_config = market_obj.data_obj.config
        self.input_data_ref = market_obj.DA_model.data
        self.RT_resolution = market_obj.data_obj.config["RT_resolution"]
        self.start_date = market_obj.data_obj.start_date
        self.end_date = market_obj.data_obj.end_date
        self.system_name = market_obj.data_obj.folder_path
        self.result_interval = market_obj.data_obj.config["output_interval"]
        self.plotly_enabled = market_obj.data_obj.config["plotly_plots"]
        self.set_base_output_directory()
        
    def set_base_output_directory(self):
        """
        Create and assign a unique base results directory.

        The method builds Results/<input_name>_<timestamp> where <input_name>
        is derived from the simulation input folder and <timestamp> is the
        current datetime. The directory is created on disk and stored in
        self.base_result_directory for later use.
        """
        # Extract the input folder base name (strip any trailing slash)
        input_name = os.path.basename(os.path.normpath(self.system_name))

        # Create a timestamp for uniqueness and traceability
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")

        # Construct the results path and ensure it exists
        results_dir = os.path.join("Results", f"{input_name}_{timestamp}")
        os.makedirs(results_dir, exist_ok=True)

        self.base_result_directory = results_dir

    def merge_dicts(self, DA_output_data, RT_output_data):
        """
        Merge DA and RT outputs into JSON-serializable per-day dictionaries
        and a single aggregated RT dictionary for plotting and summaries.

        Parameters

        DA_output_data (dict): Day-ahead outputs keyed by date.
        RT_output_data (dict): Real-time outputs keyed by date (may contain
        grouped model runs per day).

        Returns

        DA_output_json (dict): DA outputs converted to JSON-ready mapping
        keyed by ISO date strings.
        RT_output_json (dict): Per-day merged RT outputs keyed by ISO date strings.
        merged_res_dict (dict): Cumulative merged RT data suitable for
        plotting and summary routines.

        Note: The method uses a nested helper deep_merge_inplace(d1, d2)
        to recursively merge dictionaries and lists; identical keys that
        contain dicts are merged recursively while lists are extended.
        """
        def deep_merge_inplace(d1, d2):
            """
            Recursively merge d2 into d1 in place.

            Behavior:

            If a key exists in both and values are dicts: merge recursively.
            If a key exists in both and values are lists: extend the first list.
            Otherwise: overwrite the value in d1 with that from d2.
            Returns the modified d1.
            """
            for k, v in d2.items():
                if k in d1:
                    if isinstance(d1[k], dict) and isinstance(v, dict):
                        deep_merge_inplace(d1[k], v)
                    elif isinstance(d1[k], list) and isinstance(v, list):
                        d1[k].extend(v)
                    else:
                        d1[k] = v
                else:
                    d1[k] = v
            return d1
        # Work on copies to keep original outputs intact
        DA_res_dict = copy.deepcopy(DA_output_data)
        RT_res_dict = copy.deepcopy(RT_output_data)
        merged_res_dict_DA = {}
        merged_res_dict_RT = {}
        DA_output_json = {}
        RT_output_json = {}
        # Iterate over simulation days present in DA results
        for sim_day in DA_res_dict.keys():
            current_day_RT_merged = {}
            # Each sim_day in RT_res_dict contains model groups (e.g., different RT models)
            # Merge the .data dict for each group into a single per-day dict
            for model_group in RT_res_dict[sim_day].values():
                deep_merge_inplace(current_day_RT_merged, model_group.data)
            # Use ISO date string as the JSON key
            current_key = sim_day.isoformat()
            RT_output_json[current_key] = copy.deepcopy(current_day_RT_merged)
            DA_output_json[current_key] = DA_res_dict[sim_day].data
            # Merge into cumulative dict used for plotting and summaries
            deep_merge_inplace(merged_res_dict_RT, current_day_RT_merged)
            deep_merge_inplace(merged_res_dict_DA, DA_res_dict[sim_day].data)
        return DA_output_json, RT_output_json, merged_res_dict_RT, merged_res_dict_DA

    def set_subfolders(self, name):
        """
        Create a named subfolder under the base results directory and prepare
        plot subdirectories.

        Parameters

        name (str): Subfolder name (e.g., a date or group label). If empty,
        an unnamed (root) results folder is used.
        
        Creates <base_result_directory>/<name> and ensures
        png_plots exist. If Plotly is enabled, also creates plotly_plots.
        Returns the full path to the created subfolder.
        """
        results_dir = os.path.join(self.base_result_directory, f"{name}")
        os.makedirs(results_dir, exist_ok=True)
        os.makedirs(os.path.join(results_dir, "png_plots"))
        if self.plotly_enabled:
            os.makedirs(os.path.join(results_dir, "plotly_plots"))
        return results_dir
    
    def export_results(self):
        """
        Exports results and generates plots.

        - Builds an Excel summary for the entire run by merging all DA/RT days.
        - Groups simulation days according to self.result_interval ("daily", "weekly", 
          "monthly", "at_once").
        - For each group:
            - prepares a subfolder, 
            - exports JSON outputs trimmed by the input reference data,
            - instantiates ResultPlotter and generates the standard set of plots.

        This method writes files to disk (JSON, Excel, PNG, HTML) and prints
        status messages indicating where results were saved.
        """
        start_date = self.start_date
        end_date = self.end_date 
        output_mode = self.result_interval

        result_exporter = ResultExporter()
        _, full_RT_data, _, _ = self.merge_dicts(self.DA_output_data, self.RT_output_data)
        result_exporter.export_excel_file(full_RT_data, self.all_config, self.base_result_directory)
        print("Excel summary file saved to:", self.base_result_directory)
        
        # Convert keys of dicts into DatetimeIndex
        orig_keys = sorted(self.DA_output_data.keys()) 
        all_keys = pd.to_datetime(orig_keys)  # -> Timestamps
        groups = defaultdict(list)

        if output_mode == "daily":
            grouper = all_keys.to_period("D")
        elif output_mode == "weekly":
            grouper = all_keys.to_period("W-SUN")   # weeks end on Sunday
        elif output_mode == "monthly":
            grouper = all_keys.to_period("M")
        elif output_mode == "at_once":
            # everything in one group
            groups["all_data"] = list(orig_keys)
        else:
            raise ValueError(f"Unknown mode: {output_mode}")
        
        # Build groups unless mode == once
        if output_mode != "at_once":
            for dt, grp in zip(all_keys, grouper):
                groups[grp].append(dt.date())
        # Loop over each group (day/week/month)
        for grp_label, time_keys in groups.items():
            current_start_date = time_keys[0]

            # Extract subset from dicts
            DA_data = {k: self.DA_output_data[k] for k in time_keys}
            RT_data = {k: self.RT_output_data[k] for k in time_keys}

            # Merge DA + RT dicts
            DA_json_data, RT_json_data, merged_RT_data, merged_DA_data = self.merge_dicts(DA_data, RT_data)

            # Make subfolder (like "2020-01-Week1" or "2020-01-01")
            if output_mode == "at_once":
                current_directory = self.set_subfolders("")
            else:
                folder_name = str(grp_label).replace("/", "_")  # replace / with 
                current_directory = self.set_subfolders(folder_name)

            # Export JSON outputs
            result_exporter.export_json_outputs(self.input_data_ref, current_directory, DA_json_data, RT_json_data)
            
            # Plots
            plotter_DA = ResultPlotter(merged_DA_data, current_directory, current_start_date, 60, self.plotly_enabled, "DA")
            plotter_DA.plot_dispatch_stackgraphs()
            plotter_DA.plot_lmp()
            plotter_DA.plot_reserves()

            plotter = ResultPlotter(merged_RT_data, current_directory, current_start_date, self.RT_resolution, self.plotly_enabled, "RT")
            plotter.plot_dispatch_stackgraphs()
            plotter.plot_costs()
            plotter.plot_lmp()
            plotter.plot_reserves()
            plotter.plot_storage_data()

            print("Results saved to:", current_directory)


