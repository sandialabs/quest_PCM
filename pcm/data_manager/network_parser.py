# -------------------------------------------------------------------------
# Network Parser Module
# -------------------------------------------------------------------------

from egret.model_library.transmission.tx_calc import construct_connection_graph, get_N_minus_1_branches
import pcm.data_manager.input_utils as input_utils

class NetworkParser:
    """
    NetworkParser is responsible for parsing network-related data, including buses, branches, contingencies,
    and load time series from the provided configuration and dataframes.

    Attributes:
        config (dict): Configuration dictionary loaded from YAML.
        data_df (dict): Dictionary mapping file keys to pandas DataFrames.
        utils: Utility module for helper functions.
        bus_dict (dict): Parsed bus attributes keyed by bus ID.
        branch_dict (dict): Parsed branch attributes keyed by branch name.
        contingency_dict (dict): Parsed branch contingency data.
        DA_load_dict (dict): Scaled DA load time series for each bus.
        RT_load_dict (dict): Scaled RT load time series for each bus.
    """

    def __init__(self, config, data_df):
        """
        Initialize the NetworkParser.

        Args:
            config (dict): Configuration dictionary loaded from YAML.
            data_df (dict): Dictionary mapping file keys to pandas DataFrames.
        """
        self.config = config
        self.data_df = data_df
        self.utils = input_utils
        self.bus_dict = {}
        self.branch_dict = {}
        self.contingency_dict = {}
        self.DA_load_dict = {}
        self.RT_load_dict = {}

    def parse_buses(self):
        """
        Parses bus data from 'bus.csv' and populates the bus_dict attribute.

        Raises:
            ValueError: If 'bus.csv' is not found in the data folder.

        Populates:
            self.bus_dict: Dictionary of bus attributes keyed by bus ID.
        """
        bus_df = self.data_df.get("bus")
        if bus_df is None:
            raise ValueError("bus.csv file must be present in the data folder.")

        for idx, row in bus_df.iterrows():
            bus_type = str(row.get("Bus Type"))
            bus_name = str(row.get("Bus Name"))
            bus_id = str(row.get("Bus ID"))
            base_kv = float(row.get("BaseKV", 100))
            area = str(row.get("Area"))
            zone = str(row.get("Zone"))
            mw_load = float(row.get("MW Load"))
            if bus_id:
                self.bus_dict[bus_id] = {
                    "matpower_bustype": bus_type,
                    "bus_name": bus_name,
                    "base_kv": base_kv,
                    "area": area,
                    "zone": zone,
                    "mw_load": mw_load
                }
                
    # -------------------------------------------------------------------------

    def parse_branches(self, bus_data=None):
        """
        Parses branch data from 'branch.csv' and populates the branch_dict attribute.
        Identifies branch type (line or transformer) and sets transformer attributes if applicable.
        Optionally constructs contingency data if branch contingencies are enabled in the config.

        Args:
            bus_data (dict, optional): Dictionary of bus data. If not provided, uses self.bus_dict.

        Raises:
            ValueError: If 'branch.csv' is not found in the data folder.
            ValueError: If bus data is required for contingencies but not available.

        Populates:
            self.branch_dict: Dictionary of branch attributes keyed by branch name.
            self.contingency_dict: Dictionary of branch contingencies (if enabled).
        """
        branch_df = self.data_df.get("branch")
        if branch_df is None:
            raise ValueError("branch.csv file must be present in the data folder.")
        
        for idx, row in branch_df.iterrows():
            from_bus = str(row.get("From Bus"))
            to_bus = str(row.get("To Bus"))
            resistance = float(row.get("R", 0.0))
            reactance = float(row.get("X", 0.0))
            susceptance = float(row.get("B", 0.0))
            rating_long_term = float(row.get("Cont Rating", 0.0))
            rating_short_term = float(row.get("LTE Rating", 0.0))
            rating_emergency = float(row.get("STE Rating", 0.0))
            in_service = bool(row.get("In Service", 1))
            name = str(row.get("Line ID"))

            self.branch_dict[name] = {
                "from_bus": from_bus,
                "to_bus": to_bus,
                "resistance": resistance,
                "reactance": reactance,
                "charging_susceptance": susceptance,
                "rating_long_term": rating_long_term,
                "rating_short_term": rating_short_term,
                "rating_emergency": rating_emergency,
                "in_service": in_service,
                "angle_diff_min": -180.0,
                "angle_diff_max": 180.0
            }

            tr_ratio_any = float(row.get("Tr Ratio"))
            if tr_ratio_any != 0:
                self.branch_dict[name]["branch_type"] = "transformer"
                self.branch_dict[name]["transformer_tap_ratio"] = tr_ratio_any
                self.branch_dict[name]["transformer_phase_shift"] = 0.0
            else:
                self.branch_dict[name]["branch_type"] = "line"

        # Handle branch contingencies if enabled in config
        if self.config.get("branch_contingency", True):
            bus_data = bus_data or self.bus_dict
            if not bus_data:
                raise ValueError("For contingencies, bus data must be parsed first")
        
            key = []
            for bn, b in self.branch_dict.items():
                if 'planned_outage' in b:
                    if isinstance(b['planned_outage'], dict):
                        if any(b['planned_outage']['values']):
                            key.append(b)
                    elif b['planned_outage']:
                        key.append(b)

            key = tuple(key)
            if key not in self.contingency_dict:
                mapping_bus_to_idx = {k: i for i, k in enumerate(bus_data.keys())}
                graph = construct_connection_graph(self.branch_dict, mapping_bus_to_idx)
                contingency_list = get_N_minus_1_branches(graph, self.branch_dict, mapping_bus_to_idx)
                contingency_dict = {cn: {'branch_contingency': cn} for cn in contingency_list}
                self.contingency_dict = contingency_dict

    # -------------------------------------------------------------------------

    def parse_load(self, time_setup):
        """
        Parses and scales load time series data for each bus from DA and RT load timeseries CSVs.
        Aggregates and scales load based on the configured aggregation level ('node', 'area', or 'zone').
        Populates DA and RT load time series in the respective dictionaries.

        Args:
            time_setup (dict): Dictionary containing time filtering and period information.

        Raises:
            ValueError: If DA or RT load timeseries data is missing.
            ValueError: If bus data is not available.
            KeyError: If a required region is not found in the load timeseries data.

        Populates:
            self.DA_load_dict: Scaled DA load time series for each bus.
            self.RT_load_dict: Scaled RT load time series for each bus.
        """
        df_da = self.data_df.get("load_timeseries_DA")
        df_rt = self.data_df.get("load_timeseries_RT")
        df_da, df_rt = self.utils.filter_data_timesteps(time_setup, df_da, df_rt)

        if df_da is None or df_rt is None:
            raise ValueError("Missing DA or RT load timeseries data.")
        if self.bus_dict is None:
            raise ValueError("Bus data must be parsed first")
        
        buses = self.bus_dict
        agg_level = self.config["load_timeseries_aggregation_level"]

        for bus_id, bus in buses.items():
            base_load = bus["mw_load"]
            if base_load <= 0:
                continue

            # Determine aggregation region and total load
            if agg_level == "node":
                region = bus_id
                total_load = base_load
            elif agg_level == "area":
                region = bus["area"]
                total_load = sum(b["mw_load"] for b in buses.values() if b["area"] == region)
            elif agg_level == "zone":
                region = bus["zone"]
                total_load = sum(b["mw_load"] for b in buses.values() if b["zone"] == region)
            else:
                raise ValueError("Invalid load aggregation level. Choose 'node', 'area', or 'zone'.")

            if region not in df_da.columns or region not in df_rt.columns:
                raise KeyError(f"Region '{region}' not found in DA or RT load timeseries data.")

            scale = base_load / total_load

            self.DA_load_dict[bus_id] = {
                "bus": bus_id,
                "area": bus["area"],
                "p_load": {
                    "data_type": "time_series",
                    "values": [v * scale for v in df_da[region]]
                }
            }
            self.RT_load_dict[bus_id] = {
                "bus": bus_id,
                "area": bus["area"],
                "p_load": {
                    "data_type": "time_series",
                    "values": [v * scale for v in df_rt[region]]
                }
            }