# -------------------------------------------------------------------------
# Storage Parser Module
# -------------------------------------------------------------------------

class StorageParser:
    """
    StorageParser is responsible for parsing storage unit data from the provided configuration and dataframes.
    It supports parsing of Generic Energy Storage Systems (GESS), Battery Energy Storage Systems (BESS),
    and Pumped Hydro Storage (PHS), and organizes their technical and operational parameters.

    Attributes:
        config (dict): Configuration dictionary loaded from YAML.
        data_df (dict): Dictionary mapping file keys to pandas DataFrames.
        storage_dict (dict): Parsed storage attributes keyed by Storage ID.
        static_storage_dict (dict): Dictionary for static storage system parameters (e.g., AS stacking level).
    """

    def __init__(self, config, data_df):
        """
        Initialize the StorageParser.

        Args:
            config (dict): Configuration dictionary loaded from YAML.
            data_df (dict): Dictionary mapping file keys to pandas DataFrames.
        """
        self.config = config
        self.data_df = data_df
        self.storage_dict = {}
        self.static_storage_dict = {}

    def parse_storage(self, bus_dict):
        """
        Parse storage data from generic, battery, and pumped hydro storage CSVs.

        Populates the storage_dict with attributes for each storage unit,
        including technical parameters, efficiencies, costs, and initial states.

        Handles three storage types:
            - Generic Storage (GESS)
            - Battery Energy Storage Systems (BESS)
            - Pumped Hydro Storage (PHS)

        Args:
            bus_dict (dict): Dictionary of bus attributes keyed by bus ID.

        Raises:
            ValueError: If required storage CSV files are missing.

        Populates:
            self.storage_dict: Dictionary of storage attributes keyed by Storage ID.
            self.static_storage_dict["AS_stacking_level"]: Ancillary service stacking level from config.
        """
        # ---------------------------------------------------------
        # Parse Generic Storage (GESS)
        # ---------------------------------------------------------
        df_GESS = self.data_df.get("generic_storage")
        if df_GESS is not None:
            for _, row in df_GESS.iterrows():
                storage_id = str(row.get("Storage ID"))
                self.storage_dict[storage_id] = {
                    "storage_type": "Generic",
                    "bus": str(row.get("Bus ID")),
                    "fuel": "Storage",
                    "category": "GESS",
                    "area": bus_dict[str(row.get("Bus ID"))]["area"],
                    "zone": bus_dict[str(row.get("Bus ID"))]["zone"],
                    "in_service": bool(row.get("In Service", True)),
                    "max_charge_rate": float(row.get("Charge Rating MW")),
                    "min_charge_rate": float(row.get("Min Charge Rating MW")),
                    "max_discharge_rate": float(row.get("Discharge Rating MW")),
                    "min_discharge_rate": float(row.get("Min Discharge Rating MW")),
                    "energy_capacity": float(row.get("Rated Capacity MWh")),
                    "charge_efficiency": float(row.get("Charging Efficiency")),
                    "discharge_efficiency": float(row.get("Discharging Efficiency")),
                    "initial_state_of_charge": float(row.get("Initial SoC")),
                    "minimum_state_of_charge": float(row.get("Minimum SoC")),
                    "end_state_of_charge": float(row.get("End of day SoC", 0.5)),
                    "ramp_up_input_60min": float(row.get("Charging RampUP MW/min")) * 60,
                    "ramp_down_input_60min": float(row.get("Charging RampDOWN MW/min")) * 60,
                    "ramp_up_output_60min": float(row.get("Discharging RampUP MW/min")) * 60,
                    "ramp_down_output_60min": float(row.get("Discharging RampDOWN MW/min")) * 60,
                    "discharge_cost": float(row.get("Discharging Cost $/MWh")),
                    "charge_cost": float(row.get("Charging Cost $/MWh"))
                }
        # ---------------------------------------------------------
        # Parse Battery Energy Storage Systems (BESS)
        # ---------------------------------------------------------
        df_BESS = self.data_df.get("battery_storage")
        if df_BESS is not None:
            for _, row in df_BESS.iterrows():
                storage_id = str(row.get("Storage ID"))
                self.storage_dict[storage_id] = {
                    "storage_type": "BESS",
                    "bus": str(row.get("Bus ID")),
                    "fuel": "Storage",
                    "category": "BESS",
                    "area": bus_dict[str(row.get("Bus ID"))]["area"],
                    "zone": bus_dict[str(row.get("Bus ID"))]["zone"],
                    "in_service": bool(row.get("In Service", True)),
                    "power_rating": float(row.get("Rated Power MW")),
                    "energy_capacity": float(row.get("Rated Capacity MWh")),
                    "retention_rate_60min": float(row.get("Capacity Retention Rate")),
                    "conversion_efficiency": float(row.get("Conversion Efficiency")),
                    "discharge_cost": float(row.get("Battery Discharging Cost $/MWh")),
                    "initial_state_of_charge": float(row.get("Initial SoC")),
                    "minimum_state_of_charge": float(row.get("Minimum SoC")),
                    "maximum_state_of_charge": float(row.get("Maximum SoC")),
                    "end_state_of_charge": float(row.get("End of day SoC", 0.5)),
                    "ramp_up_input_60min": 1e20,
                    "ramp_down_input_60min": 1e20,
                    "ramp_up_output_60min": 1e20,
                    "ramp_down_output_60min": 1e20,
                }
        # ---------------------------------------------------------
        # Parse Pumped Hydro Storage (PHS)
        # ---------------------------------------------------------
        df_PHS = self.data_df.get("pumped_hydro_storage")
        if df_PHS is not None:
            for _, row in df_PHS.iterrows():
                storage_id = str(row.get("Storage ID"))
                self.storage_dict[storage_id] = {
                    "storage_type": "PHS",
                    "bus": str(row.get("Bus ID")),
                    "fuel": "Storage",
                    "category": "PHS",
                    "area": bus_dict[str(row.get("Bus ID"))]["area"],
                    "zone": bus_dict[str(row.get("Bus ID"))]["zone"],
                    "in_service": bool(row.get("In Service", True)),
                    "hsc_mode": bool(row.get("Supports HSC")),
                    "num_units": int(row.get("Units")),
                    "generator_max_power": float(row.get("Pmax Generator MW")),
                    "generator_min_power": float(row.get("Pmin Generator MW")),
                    "pump_rating": float(row.get("Prated Pump MW")),
                    "generator_efficiency": float(row.get("Generator Efficiency")),
                    "pump_efficiency": float(row.get("Pump Efficiency")),
                    "max_upper_reservoir_level": float(row.get("Max Upper Reservoir Volume m^3")),
                    "max_water_discharge_level": float(row.get("Max Gen Discharge Flow-Rate m^3/s")),
                    "min_water_discharge_level": float(row.get("Min Gen Discharge Flow-Rate m^3/s")),
                    "max_water_pump_level": float(row.get("Max Pumping Flow-Rate m^3/s")),
                    "conversion_coefficient": float(row.get("Power-Flow Conversion Coefficient MW/m^3")),
                    "gen_startup_cost": float(row.get("Generator Startup Cost $")),
                    "pump_startup_cost": float(row.get("Pump Startup Cost $")),
                    "initial_state_of_charge": float(row.get("Initial SoC")),
                    "minimum_state_of_charge": float(row.get("Minimum SoC")),
                    "maximum_state_of_charge": float(row.get("Maximum SoC")),
                    "end_state_of_charge": float(row.get("End of day SoC", 0.5)),
                    "ramp_up_input_60min": 1e20,
                    "ramp_down_input_60min": 1e20,
                    "ramp_up_output_60min": 1e20,
                    "ramp_down_output_60min": 1e20,
                }
        # Store ancillary service stacking level from config
        target_params = [
            "Regulation Up",
            "Regulation Down",
            "Spinning Reserve",
            "NonSpinning Reserve",
            "Contingency Reserve"
        ]
        # check if all of those are None
        all_none = all(
            (self.config.get(param) is None or str(self.config.get(param)).lower() == "none")
            for param in target_params
        )
        if not all_none:
            self.static_storage_dict["storage_AS_stacking_level"] = self.config["storage_AS_participation_level"]
        else:
            self.static_storage_dict["storage_AS_stacking_level"] = 0