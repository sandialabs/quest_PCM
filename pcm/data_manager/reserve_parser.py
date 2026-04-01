# -------------------------------------------------------------------------
# Reserve Parser Module
# -------------------------------------------------------------------------

import pcm.data_manager.input_utils as input_utils

class ReserveParser:
    """
    ReserveParser is responsible for parsing reserve requirement data for both system-wide and area-specific reserves,
    supporting fixed, percentage-based, and time series input modes.

    Attributes:
        config (dict): Configuration dictionary loaded from YAML.
        data_df (dict): Dictionary mapping file keys to pandas DataFrames.
        utils: Utility module for helper functions.
        DA_system_reserve (dict): Parsed DA system-wide reserve time series.
        DA_area_reserve (dict): Parsed DA area-specific reserve time series.
        RT_system_reserve (dict): Parsed RT system-wide reserve time series.
        RT_area_reserve (dict): Parsed RT area-specific reserve time series.
    """

    def __init__(self, config, data_df):
        """
        Initialize the ReserveParser.

        Args:
            config (dict): Configuration dictionary loaded from YAML.
            data_df (dict): Dictionary mapping file keys to pandas DataFrames.
        """
        self.config = config
        self.data_df = data_df
        self.utils = input_utils
        self.DA_system_reserve = {}
        self.DA_area_reserve = {}
        self.RT_system_reserve = {}
        self.RT_area_reserve = {}
        self.reserve_deployment = {}

    def parse_reserves(self, bus_dict, DA_load_dict, RT_load_dict, time_settings):
        """
        Parse DA and RT reserves separately for system and areas.
        """
        self.product_key_map = {
            "System Reserve": "reserve_requirement",
            "Spinning Reserve": "spinning_reserve_requirement",
            "NonSpinning Reserve": "non_spinning_reserve_requirement",
            "Regulation Up": "regulation_up_requirement",
            "Regulation Down": "regulation_down_requirement",
            "Flexible Ramp Up": "flexible_ramp_up_requirement",
            "Flexible Ramp Down": "flexible_ramp_down_requirement",
            "Supplemental Reserve": "supplemental_reserve_requirement"
        }

        df_DA = self.data_df.get("DA_reserves_fixed_percentage")
        df_RT = self.data_df.get("RT_reserves_fixed_percentage")
        df_deploy = self.data_df.get("reserve_deployment")

        if df_DA is None or df_RT is None:
            raise ValueError("DA_reserves_fixed_percentage.csv and RT_reserve_fixed_percentage.csv files must be present in the data\\reserves folder.")

        system_areas = {bus.get("area") for bus in bus_dict.values() if bus.get("area")}

        # Helper to sum demand
        def total_demand(load_dict, area=None):
            loads = [b['p_load']['values'] for b in load_dict.values() if area is None or b.get("area") == area]
            return [sum(x) for x in zip(*loads)]

        # DA reserves
        self._parse_reserves(df_DA, total_demand, DA_load_dict, self.DA_system_reserve, self.DA_area_reserve, system_areas, time_settings, "DA")

        # RT reserves
        self._parse_reserves(df_RT, total_demand, RT_load_dict, self.RT_system_reserve, self.RT_area_reserve, system_areas, time_settings, "RT")

        df_res_deployed = self.data_df.get("reserve_deployment")
        self._parse_reserve_deployment(df_res_deployed, time_settings)

    def _parse_reserves(self, df, total_demand, load_dict, system_reserve_dict, area_reserve_dict, system_areas, time_settings, timeframe):
        
        """Populate system and area reserves for a single timeframe (DA or RT)"""
        for _, row in df.iterrows():
            reserve_type = str(row.get("Reserve Type"))
            key = self.product_key_map.get(reserve_type)
            eligible_areas = [str(c) for c in str(row.get("Eligible Areas")) if c.isdigit()]
            reserve_mode = self.config.get(reserve_type)
            period_len = len(time_settings[f"{timeframe}_timekeys"])
            # -------------------------
            # System reserves
            # -------------------------
            if reserve_mode == "fixed":
                val = float(row.get("System Fixed Requirement MW", 0))
                if val > 0:
                    system_reserve_dict[key] = {"data_type": "time_series", "values": [val]*period_len}
            elif reserve_mode == "percentage":
                perc = float(row.get("System Percentage Requirement", 0))
                if perc > 0:
                    system_reserve_dict[key] = {"data_type": "time_series", "values": [perc/100 * x for x in total_demand(load_dict)]}
            elif reserve_mode == "timeseries":
                df_ts = self.data_df.get(f"{reserve_type}_timeseries_{timeframe}")
                if timeframe == "DA":
                    df_ts, _ = self.utils.filter_data_timesteps(time_settings, df_ts, None)
                else:
                    _, df_ts = self.utils.filter_data_timesteps(time_settings, None, df_ts)
                if df_ts is not None and "System" in df_ts and df_ts["System"].sum()>1e-5:
                    system_reserve_dict[key] = {"data_type": "time_series", "values": df_ts["System"].tolist()}
            # -------------------------
            # Area reserves
            # -------------------------
            for area in system_areas:
                if area not in eligible_areas:
                    continue
                area_dict = area_reserve_dict.setdefault(area, {})

                if reserve_mode == "fixed":
                    val = float(row.get("Area Fixed Requirement MW", 0))
                    if val > 0:
                        area_dict[key] = {"data_type": "time_series", "values": [val]*period_len}
                elif reserve_mode == "percentage":
                    perc = float(row.get("Area Percentage Requirement", 0))
                    if perc > 0:
                        area_dict[key] = {"data_type": "time_series", "values": [perc/100 * x for x in total_demand(load_dict, area)]}
                elif reserve_mode == "timeseries":
                    df_ts = self.data_df.get(f"{reserve_type}_timeseries_{timeframe}")
                    if timeframe == "DA":
                        df_ts, _ = self.utils.filter_data_timesteps(time_settings, df_ts, None)
                    else:
                        _, df_ts = self.utils.filter_data_timesteps(time_settings, None, df_ts)
                    col_name = f"Area {area}"
                    if df_ts is not None and col_name in df_ts and df_ts[col_name].sum()>1e-5:
                        area_dict[key] = {"data_type": "time_series", "values": df_ts[col_name].tolist()}

    # -------------------------
    # Reserve deployments
    # -------------------------
    def _parse_reserve_deployment(self, df_ts, time_settings):
        """
        Parsing of reserve deployment data.
        """
        mapper = {"regulation_up_deployed": "RegUp usage (fraction)",
                  "regulation_down_deployed": "RegDown usage (fraction)",
                  "spinning_reserve_deployed": "Spin usage (minutes)",
                  "nonspinning_reserve_deployed": "NonSpin usage (minutes)",
                  "supplemental_reserve_deployed": "SR usage (minutes)"}
        
        cumsum_columns = ["Spin usage (minutes)", "NonSpin usage (minutes)", "SR usage (minutes)"]
        _, filtered_dat = self.utils.filter_data_timesteps(time_settings, None, df_ts, cumsum_cols = cumsum_columns)
        filtered_dat[cumsum_columns] = filtered_dat[cumsum_columns]/self.config["RT_resolution"]
        for reserve_type, usage_col in mapper.items():       
            self.reserve_deployment[reserve_type] = {"data_type": "time_series", "values": filtered_dat[usage_col].tolist()}
            