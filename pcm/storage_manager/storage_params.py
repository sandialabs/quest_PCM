from pyomo.environ import *
from egret.model_library.unit_commitment.status_vars import _is_relaxed
from egret.model_library.unit_commitment.uc_utils import uc_time_helper

class StorageParams():
    """
    StorageParams defines and initializes all Pyomo parameters related to storage operation
    for GESS, BESS, and PHS units.

    Attributes:
        opt_model: The Pyomo model to which parameters are added.
        baseMVA_val (float): System baseMVA value for normalization.
        TimeMapper: Helper for mapping time series data to model time periods.
        storage_attrs (dict): Storage attributes from model data.
        storage_common_attrs (dict): Common ancillary service parameters from model data.
    """

    def __init__(self, pyomo_model):
        """
        Initialize the StorageParams object.

        Args:
            model: The Pyomo model object to operate on.
        """
        self.opt_model = pyomo_model
        self.baseMVA_val = pyomo_model.model_data.data['system']['baseMVA']
        self.TimeMapper = uc_time_helper(pyomo_model.TimePeriods)

        self.storage_attrs = pyomo_model.model_data.attributes(element_type='storage')
        self.storage_common_attrs = pyomo_model.model_data.data.get("system")

        # Identify storage units by type
        BESS_list = [s for s in self.storage_attrs['names'] if self.storage_attrs['storage_type'][s] == 'BESS']
        PHS_list = [s for s in self.storage_attrs['names'] if self.storage_attrs['storage_type'][s] == 'PHS']
        GESS_list = [s for s in self.storage_attrs['names'] if self.storage_attrs['storage_type'][s] == 'Generic']
        
        # Define sets for each storage type in the model
        self.opt_model.GESS_Storage = Set(initialize=GESS_list)
        self.opt_model.BESS_Storage = Set(initialize=BESS_list)
        self.opt_model.PHS_Storage = Set(initialize=PHS_list)
        self.opt_model.GESS_present = Param(initialize=bool(GESS_list))
        self.opt_model.BESS_present = Param(initialize=bool(BESS_list))
        self.opt_model.PHS_present = Param(initialize=bool(PHS_list))
        
        # Define a dictionary mapping each PHS storage to its units
        PHS_units_mapping = {
            s: range(self.storage_attrs['num_units'][s]) 
            for s in PHS_list if s in self.storage_attrs['num_units']
        }
        # Create a set of (PHS storage, unit number) pairs
        PHS_units_set = [(s, u) for s, units in PHS_units_mapping.items() for u in units]
        self.opt_model.PHS_units = Set(dimen=2, initialize=PHS_units_set)
        
        # Set for all BESS and PHS units (for AS participation)
        self.opt_model.BESS_PHS_set = self.opt_model.BESS_Storage.union(self.opt_model.PHS_Storage)

    ##################################
    # Common Storage Parameters
    ##################################
    def initialize_storage_common_params(self):
        """
        Define and initialize parameters that are common to all storage types.

        - Initial state of charge, regulation efficiencies, AS stacking, and market-specific parameters.
        - Ancillary service selectors for RT market.
        - Fixed variables for relaxed (LP) formulations.
        - Maximum SoC for BESS and PHS units.
        """
        model = self.opt_model
        
        model.storage_AS_stacking = Param(within=Integers, initialize = (self.storage_common_attrs).get('storage_AS_stacking_level', 0))
        model.current_market =  Param(initialize = model.model_data.data["current_market"], within = Any)
        
        if value(model.current_market) == "RT":
            model.RT_SoC_requirement = Param(model.Storage, model.TimePeriods, within = PercentFraction, initialize = self.TimeMapper(self.storage_attrs.get('RT_SoC_requirement')))
        # Market-specific AS SoC time requirement
        if value(model.current_market) == "DA":
            model.AS_SoC_time_requirement = Param(within = NonNegativeReals, initialize=(self.storage_common_attrs or {}).get('AS_time_DA', 1))
        if value(model.current_market) == "RT":
            model.AS_SoC_time_requirement = Param(within = NonNegativeReals, initialize=(self.storage_common_attrs or {}).get('AS_time_RT', 0.5))
        
        
        model.RT_SOC_deviation_penalty = Param(within=NonNegativeReals, initialize=model.LoadMismatchPenalty/10)

        # Ancillary service selectors (for RT market)
        model.RegUP_efficiency = Param(
            model.TimePeriods, 
            within=PercentFraction,                    
            default=0.08,
            initialize = dict() if value(model.current_market) == "DA" else self.TimeMapper(self.storage_common_attrs.get('regulation_up_deployed'))
        )
        model.RegDOWN_efficiency = Param(
            model.TimePeriods, 
            within=PercentFraction,
            default=0.17,
            initialize = dict() if value(model.current_market) == "DA" else self.TimeMapper(self.storage_common_attrs.get('regulation_down_deployed'))
        )
        model.SP_selector = Param(
            model.TimePeriods, 
            within=PercentFraction, 
            initialize = dict() if value(model.current_market) == "DA" else self.TimeMapper(self.storage_common_attrs.get('spinning_reserve_deployed')), 
            default= 0
        )
        model.NSP_selector = Param(
            model.TimePeriods, 
            within=PercentFraction, 
            initialize = dict() if value(model.current_market) == "DA" else self.TimeMapper(self.storage_common_attrs.get('nonspinning_reserve_deployed')), 
            default= 0
        )
        model.SUPP_selector = Param(
            model.TimePeriods, 
            within=PercentFraction, 
            initialize = dict() if value(model.current_market) == "DA" else self.TimeMapper(self.storage_common_attrs.get('supplemental_reserve_deployed')), 
            default= 0
        )

        # Fixed variables for relaxed (LP) formulations
        if _is_relaxed(model):
            model.FixedStorageInput = Param(model.Storage, model.TimePeriods, within = Any, initialize = self.TimeMapper(self.storage_attrs.get('ESSFixedInput')))
            model.FixedStorageOutput = Param(model.Storage, model.TimePeriods, within = Any, initialize = self.TimeMapper(self.storage_attrs.get('ESSFixedOutput')))
            model.FixedStorageReg = Param(model.BESS_PHS_set, model.TimePeriods, within = Any, initialize = self.TimeMapper(self.storage_attrs.get('ESSFixedReg')))
            model.FixedStorageSP = Param(model.BESS_PHS_set, model.TimePeriods, within = Any, initialize = self.TimeMapper(self.storage_attrs.get('ESSFixedSP')))
            model.FixedStorageNSP = Param(model.BESS_PHS_set, model.TimePeriods, within = Any, initialize = self.TimeMapper(self.storage_attrs.get('ESSFixedNSP')))
            model.FixedStorageSUPP = Param(model.BESS_PHS_set, model.TimePeriods, within = Any, initialize = self.TimeMapper(self.storage_attrs.get('ESSFixedSUPP')))

        # Maximum SoC for BESS and PHS units
        model.MaximumSocStorage = Param(model.BESS_PHS_set, within=PercentFraction,
                                        default=1.0,
                                        initialize=self.storage_attrs.get('maximum_state_of_charge'))

    ##################################
    # BESS Parameters
    ##################################
    def initialize_BESS_params(self):
        """
        Define and initialize parameters specific to Battery Energy Storage Systems (BESS).

        - Power rating and conversion efficiency for each BESS unit.
        """
        model = self.opt_model
        
        model.storage_power = Param(model.BESS_Storage, within=NonNegativeReals, default=0.0,
                                   initialize={k: v / self.baseMVA_val for k, v in self.storage_attrs.get('power_rating', {}).items()})
        model.ConversionEfficiency = Param(model.BESS_Storage, within=PercentFraction,
                                           default=0.85,
                                           initialize=self.storage_attrs.get('conversion_efficiency'))

    ##################################
    # PHS Parameters
    ##################################   
    def initialize_PHS_params(self):
        """
        Define and initialize parameters specific to Pumped Hydro Storage (PHS) units.

        - Number of units, conversion coefficients, efficiencies, reservoir levels, power ratings, and startup costs.
        - Initial generation and pump modes for each unit.
        - Fixed variables for relaxed (LP) formulations.
        """
        model = self.opt_model

        def flatten_dict(d):
            """
            Helper to flatten a nested dictionary for unit-level parameters.
            """
            items = []
            for outer_key, inner_dict in d.items():
                if isinstance(inner_dict, dict):
                    items.extend(inner_dict.items())
            return dict(items)

        model.PHS_num_units = Param(model.PHS_Storage, within=NonNegativeIntegers,
                                    default=0,
                                    initialize=self.storage_attrs.get('num_units', dict()))
        
        model.PHS_conversion_coefficient = Param(model.PHS_Storage, within=PercentFraction,
                                    default=1e-10,
                                    initialize={k: v / self.baseMVA_val for k, v in self.storage_attrs.get('conversion_coefficient', {}).items()})
        
        model.PHS_PumpEfficiency = Param(model.PHS_Storage, within=PercentFraction,
                                    default=0.85,
                                    initialize=self.storage_attrs.get('pump_efficiency', dict()))
        
        model.PHS_GeneratorEfficiency = Param(model.PHS_Storage, within=PercentFraction,
                                    default=0.85,
                                    initialize=self.storage_attrs.get('generator_efficiency', dict()))
        
        model.PHS_UpperReservoirMaxLevel = Param(model.PHS_Storage, within=NonNegativeReals,
                                    default=1e-10,
                                    initialize=self.storage_attrs.get('max_upper_reservoir_level', dict()))
        
        model.PHS_UpperReservoirMinLevel = Param(model.PHS_Storage, within=NonNegativeReals,
                                    default=0.0,
                                    initialize=self.storage_attrs.get('min_upper_reservoir_level', dict()))
        
        model.PHS_MaxWaterDischargeLevel = Param(model.PHS_Storage, within=NonNegativeReals,
                                    default=0.0,
                                    initialize=self.storage_attrs.get('max_water_discharge_level', dict()))
        
        model.PHS_MinWaterDischargeLevel = Param(model.PHS_Storage, within=NonNegativeReals,
                                    default=0.0,
                                    initialize=self.storage_attrs.get('min_water_discharge_level', dict()))
        
        model.PHS_MaxWaterPumpLevel = Param(model.PHS_Storage, within=NonNegativeReals,
                                    default=0.0,
                                    initialize=self.storage_attrs.get('max_water_pump_level', dict()))
        
        model.PHS_Gen_max_rating = Param(model.PHS_Storage, within=NonNegativeReals,
                                    default=0.0,
                                    initialize={k: v / self.baseMVA_val for k, v in self.storage_attrs.get('generator_max_power', {}).items()})
        
        model.PHS_Gen_min_rating = Param(model.PHS_Storage, within=NonNegativeReals,
                                    default=0.0,
                                    initialize={k: v / self.baseMVA_val for k, v in self.storage_attrs.get('generator_min_power', {}).items()})
        
        model.PHS_Pump_rating = Param(model.PHS_Storage, within=NonNegativeReals,
                                    default=0.0,
                                    initialize={k: v / self.baseMVA_val for k, v in self.storage_attrs.get('pump_rating', {}).items()})
        
        model.PHS_gen_startup_cost = Param(model.PHS_Storage, within=NonNegativeReals,
                                    default=0.0,
                                    initialize=self.storage_attrs.get('gen_startup_cost', dict()))
        
        model.PHS_pump_startup_cost = Param(model.PHS_Storage, within=NonNegativeReals,
                                    default=0.0,
                                    initialize=self.storage_attrs.get('pump_startup_cost', dict()))
        
        model.PHS_hsc_mode = Param(model.PHS_Storage, within=Boolean,
                                    default=True,
                                    initialize=self.storage_attrs.get('hsc_mode', dict()))
        
        model.PHS_Initial_GenMode = Param(model.PHS_units, within=Binary,
                                    default=0,
                                    initialize=flatten_dict(self.storage_attrs.get('initial_gen_mode', dict())))
        
        model.PHS_Initial_PumpMode = Param(model.PHS_units, within=Binary,
                                    default=0,
                                    initialize=flatten_dict(self.storage_attrs.get('initial_pump_mode', dict())))
        
        model.relax_PHS_vars = Param(model.PHS_Storage, within= Boolean,
                                    default = False,
                                    initialize = self.storage_attrs.get('relax_PHS_vars', dict()))
        # Fixed variables for relaxed (LP) formulations
        if _is_relaxed(model):
            model.FixedPHSgenmode = Param(model.PHS_units, model.TimePeriods, within = NonNegativeReals, initialize = self.TimeMapper(flatten_dict(self.storage_attrs.get('PHSFixedGenMode'))))
            model.FixedPHSpumpmode = Param(model.PHS_units, model.TimePeriods, within = NonNegativeReals, initialize = self.TimeMapper(flatten_dict(self.storage_attrs.get('PHSFixedPumpMode'))))
            model.FixedPHSgenstart = Param(model.PHS_units, model.TimePeriods, within = NonNegativeReals, initialize = self.TimeMapper(flatten_dict(self.storage_attrs.get('PHSFixedGenStart')))) 
            model.FixedPHSpumpstart = Param(model.PHS_units, model.TimePeriods, within = NonNegativeReals, initialize = self.TimeMapper(flatten_dict(self.storage_attrs.get('PHSFixedPumpStart'))))
            model.FixedConventionalmode = Param(model.PHS_Storage, model.TimePeriods, within = NonNegativeReals, initialize = self.TimeMapper(self.storage_attrs.get('PHSFixedConventionalMode')))

