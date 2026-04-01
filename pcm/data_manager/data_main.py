import os
import pandas as pd
import json
import yaml
import re
from .network_parser import NetworkParser
from .gen_parser import GenParser
from .reserve_parser import ReserveParser
from .storage_parser import StorageParser
import pcm.data_manager.input_utils as input_utils

class DataManager:
    """
    DataManager is responsible for loading, parsing, and managing all input data required for market simulations.

    This class handles:
        - Loading CSV and YAML configuration files from the specified data directory.
        - Parsing and organizing system elements such as buses, branches, loads, generators, reserves, and storage.
        - Managing time series data for Day-Ahead (DA) and Real-Time (RT) market models.
        - Filtering and aligning data to the simulation time horizon and resolution.
        - Exporting processed data to JSON files compatible with downstream simulation tools.

    Attributes:
        folder_path (str): Path to the data directory containing input files.
        yaml_path (str): Path to the YAML configuration file.
        csv_data (dict): Dictionary mapping relative file paths to pandas DataFrames.
        constant_data_dict (dict): Static system data (elements and system-wide parameters).
        DA_timeseries (dict): Time series data for the Day-Ahead market.
        RT_timeseries (dict): Time series data for the Real-Time market.
        config (dict): Parsed YAML configuration.
        utils: Utility module for helper functions.
        networkparser (NetworkParser): Parser for network data (buses, branches, loads).
        genparser (GenParser): Parser for generator data.
        reserveparser (ReserveParser): Parser for reserve data.
        storageparser (StorageParser): Parser for storage data.
        time_settings (dict): Dictionary of time-related simulation settings.
        json_file_directory (str): Directory where JSON files are exported.
    """

    def __init__(self, folder_path, yaml_path):
        """
        Initialize the DataManager object.

        Loads the YAML configuration file and all CSV files from the specified data directory.
        Initializes the main data structures for system constants and time series.
        Instantiates parser objects for each data domain.

        Args:
            folder_path (str): Path to the data directory containing input files.
            yaml_path (str): Path to the YAML configuration file.
        """
        self.folder_path = folder_path
        self.yaml_path = yaml_path
        self.csv_data = {}
        self.utils = input_utils

        # Initialize main data structures for system constants and time series
        self.constant_data_dict = {"elements": {}, "system": {}}
        self.DA_timeseries = {"elements": {}, "system": {}}
        self.RT_timeseries = {"elements": {}, "system": {}}

        # Load configuration and all CSV files
        self._load_yaml_file()
        self._load_all_csv_files()

        # Instantiate data parsers for each domain
        self.networkparser = NetworkParser(self.config, self.csv_data)
        self.genparser = GenParser(self.config, self.csv_data)
        self.reserveparser = ReserveParser(self.config, self.csv_data)
        self.storageparser = StorageParser(self.config, self.csv_data)

    # -------------------------------------------------------------------------

    def _load_yaml_file(self):
        """
        Load the YAML configuration file into self.config.

        Raises:
            FileNotFoundError: If the YAML file does not exist.
            yaml.YAMLError: If the YAML file cannot be parsed.
        """
        with open(self.yaml_path, 'r') as file:
            self.config = yaml.safe_load(file)

    # -------------------------------------------------------------------------

    def _load_all_csv_files(self):
        """
        Load all CSV files from the data directory into pandas DataFrames.

        Populates:
            self.csv_data (dict): Dictionary mapping file base names (without extension) to DataFrames.

        Prints:
            Completion message and any errors encountered while reading files.
        """
        for root, _, files in os.walk(self.folder_path):
            for file_name in files:
                if file_name.endswith(".csv"):
                    full_path = os.path.join(root, file_name)
                    try:
                        df = pd.read_csv(full_path)
                        relative_path = os.path.relpath(full_path, self.folder_path)
                        filename = os.path.basename(relative_path)
                        param_name, _ = os.path.splitext(filename)
                        self.csv_data[param_name] = df
                    except Exception as e:
                        print(f"Error reading {file_name}: {e}")

        print('Completed reading csv files!')

    # -------------------------------------------------------------------------

    def _populate_system_params(self):
        """
        Populate time parameters for DA and RT models based on the YAML configuration.

        Sets up periods, time keys, and system parameters for simulation, including:
            - Simulation start and end dates
            - DA and RT lookahead and resolution
            - DA and RT periods and time keys
            - System baseMVA and ancillary service parameters

        Stores a dictionary of time settings for use by helper classes.
        """
        # Parse simulation start and end dates
        self.start_date = pd.to_datetime(self.config["start_date"], format="%m/%d/%Y")
        self.end_date = pd.to_datetime(self.config["end_date"], format="%m/%d/%Y")

        # Extract lookahead and resolution parameters
        self.DA_lookahead_periods = self.config["DA_lookahead_periods"]
        self.RT_lookahead_periods = self.config["RT_lookahead_periods"]
        self.RT_resolution = self.config["RT_resolution"]

        # Extend end date by one day if DA lookahead is used
        if self.DA_lookahead_periods > 0:
            self.end_date += pd.Timedelta(days=1)

        # Calculate number of simulation days
        num_days = (self.end_date - self.start_date).days + 1

        # Define DA periods (hourly)
        self.DA_periods = list(range(1, 25))  # 1 to 24 inclusive

        # Define RT periods (sub-hourly, e.g., every 5 minutes)
        base_RT_periods = 5  # base period in minutes
        periods_per_day = int(24 * 60 / base_RT_periods) 
        step = self.RT_resolution // base_RT_periods
        self.RT_periods = list(range(1, periods_per_day + 1, step))

        # Generate time keys for DA and RT timeseries
        time_keys_DA = list(range(1, len(self.DA_periods) * num_days + 1))
        time_keys_RT = list(range(1, len(self.RT_periods) * num_days + 1))
        self.DA_timeseries["system"]["time_keys"] = list(map(str, time_keys_DA))
        self.RT_timeseries["system"]["time_keys"] = list(map(str, time_keys_RT))

        # Set time period lengths (in minutes)
        self.DA_timeseries["system"]["time_period_length_minutes"] = 60
        self.RT_timeseries["system"]["time_period_length_minutes"] = self.RT_resolution

        # Set system baseMVA and ancillary service parameters
        self.constant_data_dict["system"]["baseMVA"] = self.config.get("baseMVA", 100.0)

        # Store a dict to pass on to helper classes
        self.time_settings = {
            'start_date': self.start_date,
            'end_date': self.end_date,
            'DA_periods': self.DA_periods,
            'RT_periods': self.RT_periods,
            'DA_timekeys': time_keys_DA,
            'RT_timekeys': time_keys_RT
        }

    # -------------------------------------------------------------------------

    def sequential_data_parser(self):
        """
        Parse and organize data sequentially using helper functions from other modules.

        This method calls all parsing functions in the correct order to populate
        the system constants and time series dictionaries for buses, branches, loads,
        generators, reserves, and storage.

        Populates:
            self.constant_data_dict, self.DA_timeseries, self.RT_timeseries
        """
        # Parse all system elements and time series data
        self._populate_system_params()

        # Network (buses, branches, contingencies, loads)
        self.networkparser.parse_buses()
        self.constant_data_dict["elements"]["bus"] = self.networkparser.bus_dict
        self.networkparser.parse_branches()
        self.constant_data_dict["elements"]["branch"] = self.networkparser.branch_dict
        self.constant_data_dict["elements"]["contingency"] = self.networkparser.contingency_dict
        self.networkparser.parse_load(self.time_settings)
        self.DA_timeseries["elements"]["load"] = self.networkparser.DA_load_dict
        self.RT_timeseries["elements"]["load"] = self.networkparser.RT_load_dict

        # Generators (thermal and renewable)
        genparser = GenParser(self.config, self.csv_data)
        genparser.parse_thermal_generators(self.networkparser.bus_dict)
        self.constant_data_dict["elements"]["generator"] = genparser.thermal_gen_dict
        genparser.parse_renewable_generators(self.networkparser.bus_dict, self.time_settings)
        self.DA_timeseries["elements"]["generator"] = genparser.renewable_DA_dict
        self.RT_timeseries["elements"]["generator"] = genparser.renewable_RT_dict

        # Reserves (system and area)
        self.reserveparser.parse_reserves(
            self.networkparser.bus_dict,
            self.networkparser.DA_load_dict,
            self.networkparser.RT_load_dict,
            self.time_settings
        )
        self.DA_timeseries["system"].update(self.reserveparser.DA_system_reserve)
        self.RT_timeseries["system"].update(self.reserveparser.RT_system_reserve)
        self.DA_timeseries["elements"].setdefault("area", {}).update(self.reserveparser.DA_area_reserve)
        self.RT_timeseries["elements"].setdefault("area", {}).update(self.reserveparser.RT_area_reserve)
        self.RT_timeseries["system"].update(self.reserveparser.reserve_deployment)

        # Storage
        self.storageparser.parse_storage(self.networkparser.bus_dict)
        self.constant_data_dict["elements"]["storage"] = self.storageparser.storage_dict
        self.constant_data_dict["system"].update(self.storageparser.static_storage_dict)

        #Store penalties
        penalty_key_map = {
            "Curtailment_penalty": "Load Curtailment",
            "DA_reserve_shortfall_penalty": "DA Reserve Shortfall",
            "Reg_shortfall_penalty": "Regulation shortfall",
            "Spin_shortfall_penalty": "Spinning reserve shortfall",
            "Nonspin_shortfall_penalty": "Nonspinning reserve shortfall",
            "Supplemental_reserve_shortfall_penalty": "Supplemental reserve shortfall",
            "Flexramp_shortfall_penalty": "Flexramp shortfall",
            "Contingency_flow_violation_penalty": "Contingency flow violation"
        }
        penalty_df = self.csv_data["penalties"]
        for dict_key, dict_value in penalty_key_map.items():
            self.constant_data_dict["system"][dict_key] = float(penalty_df.loc[penalty_df["Name"] == dict_value, "Cost $/MWh"].values[0])
            
    # -------------------------------------------------------------------------

    def export_input_json(self):
        """
        Export the processed input data as EGRET-compatible JSON files.

        This method:
            - Calls sequential_data_parser() to ensure all data is parsed and organized.
            - Merges constant and time series dictionaries for DA and RT.
            - Writes the merged data to JSON files in the 'json_dumps' directory.
            - Ensures lists are formatted compactly for EGRET compatibility.

        Side Effects:
            Creates 'json_dumps' directory in the data folder if it does not exist.
            Writes 'DA_data.json' and 'RT_data.json' files to the directory.
            Sets self.json_file_directory to the output directory path.
        """
        # Parse and organize all data before exporting
        self.sequential_data_parser()

        # Merge constant and timeseries dictionaries for DA and RT
        final_DA_dict = self.utils.deep_merge(self.constant_data_dict, self.DA_timeseries)
        final_RT_dict = self.utils.deep_merge(self.constant_data_dict, self.RT_timeseries)

        # Prepare output directory
        json_folder = os.path.join(self.folder_path, "json_dumps")
        os.makedirs(json_folder, exist_ok=True)
        self.json_file_directory = json_folder

        # Write DA JSON
        output_path_DA = os.path.join(json_folder, "DA_data.json")
        with open(output_path_DA, "w") as f:
            dumper = json.dumps(final_DA_dict, indent=2, separators=(",", ": "))
            # Collapse lists (any [...] across lines -> one line)
            dumper = re.sub(r"\[\s+([^]]*?)\s+\]",
                            lambda m: "[" + " ".join(m.group(1).split()) + "]",
                            dumper, flags=re.DOTALL)
            f.write(dumper)

        # Write RT JSON
        output_path_RT = os.path.join(json_folder, "RT_data.json")
        with open(output_path_RT, "w") as f:
            dumper = json.dumps(final_RT_dict, indent=2, separators=(",", ": "))
            # Collapse lists (any [...] across lines -> one line)
            dumper = re.sub(r"\[\s+([^]]*?)\s+\]",
                            lambda m: "[" + " ".join(m.group(1).split()) + "]",
                            dumper, flags=re.DOTALL)
            f.write(dumper)

        print(f'EGRET-compatible input JSON files created!\n')


