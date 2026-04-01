from pyomo.environ import *
from egret.model_library.unit_commitment.status_vars import _is_relaxed

class StorageVars():
    """
    StorageVars defines and initializes all Pyomo variables and expressions related to storage operation
    for GESS, BESS, and PHS units.

    Attributes:
        opt_model: The Pyomo model to which variables and expressions are added.
    """

    def __init__(self, pyomo_model):
        """
        Initialize the StorageVars object.

        Args:
            model: The Pyomo model object to operate on.
        """
        self.opt_model = pyomo_model

    ##################################
    # Common Storage Variables
    ##################################
    def define_storage_common_vars(self):
        """
        Define variables for storage operation that are common to all storage types (GESS, BESS, PHS).

        - Binary or relaxed variables to control charging and discharging modes.
        - State of charge (SoC) and SoC slack variables.
        - Ancillary service (AS) participation binaries for BESS and PHS.
        - Fixes variables for BESS and PHS as required by EGRET.
        """
        model = self.opt_model

        # Storage decision variables: charging/discharging mode
        if _is_relaxed(model):
            model.InputStorage = Var(model.Storage, model.TimePeriods, within=Any)
            model.OutputStorage = Var(model.Storage, model.TimePeriods, within=Any)
            # Fix variables to provided values in relaxed case
            for s in model.GESS_Storage:
                for t in model.TimePeriods:
                    model.InputStorage[s, t].fix(value(model.FixedStorageInput[s, t]))
                    model.OutputStorage[s, t].fix(value(model.FixedStorageOutput[s, t]))
        else:
            model.InputStorage = Var(model.Storage, model.TimePeriods, within=Binary)
            model.OutputStorage = Var(model.Storage, model.TimePeriods, within=Binary)

        # State of charge and slack variables
        model.SocStorage = Var(model.Storage, model.TimePeriods, within=PercentFraction)
        model.soc_slack = Var(model.Storage, model.TimePeriods, within=PercentFraction)

        # For BESS and PHS, fix binaries as required by EGRET
        for s in model.BESS_PHS_set:
            for t in model.TimePeriods:
                model.InputStorage[s, t].fix(1)
                model.OutputStorage[s, t].fix(1)

        # Ancillary service participation binaries for BESS and PHS
        if _is_relaxed(model):
            model.BinStorage_reg = Var(model.BESS_PHS_set, model.TimePeriods, within=Any)
            model.BinStorage_SP = Var(model.BESS_PHS_set, model.TimePeriods, within=Any)
            model.BinStorage_NSP = Var(model.BESS_PHS_set, model.TimePeriods, within=Any)
            model.BinStorage_SUPP = Var(model.BESS_PHS_set, model.TimePeriods, within=Any)
            # Fix variables to provided values in relaxed case
            for s in model.BESS_PHS_set:
                for t in model.TimePeriods:
                    model.BinStorage_reg[s, t].fix(value(model.FixedStorageReg[s, t]))
                    model.BinStorage_SP[s, t].fix(value(model.FixedStorageSP[s, t]))
                    model.BinStorage_NSP[s, t].fix(value(model.FixedStorageNSP[s, t]))
                    model.BinStorage_SUPP[s, t].fix(value(model.FixedStorageSUPP[s, t]))
        else:
            model.BinStorage_reg = Var(model.BESS_PHS_set, model.TimePeriods, within=Binary)
            model.BinStorage_SP = Var(model.BESS_PHS_set, model.TimePeriods, within=Binary)
            model.BinStorage_NSP = Var(model.BESS_PHS_set, model.TimePeriods, within=Binary)
            model.BinStorage_SUPP = Var(model.BESS_PHS_set, model.TimePeriods, within=Binary)

    ##################################
    # BESS Variables
    ##################################
    def define_BESS_vars(self):
        """
        Define variables and expressions specific to Battery Energy Storage Systems (BESS).

        - Power charge/discharge variables and bounds.
        - Ancillary service (AS) provision variables for regulation, spinning, non-spinning, and supplemental reserves.
        - Expressions for total input and output, including AS participation.
        """
        model = self.opt_model

        def power_output_storage_bounds_rule(m, s, t):
            return (0, m.storage_power[s])

        # Power charge/discharge variables
        model.PowerChargeBESS = Var(model.BESS_Storage, model.TimePeriods, within=NonNegativeReals, bounds=power_output_storage_bounds_rule)
        model.PowerDischargeBESS = Var(model.BESS_Storage, model.TimePeriods, within=NonNegativeReals, bounds=power_output_storage_bounds_rule)

        # Ancillary service provision variables
        model.BESS_RegUP = Var(model.BESS_Storage, model.TimePeriods, within=NonNegativeReals, bounds=power_output_storage_bounds_rule)
        model.BESS_RegDOWN = Var(model.BESS_Storage, model.TimePeriods, within=NonNegativeReals, bounds=power_output_storage_bounds_rule)
        model.BESS_SP = Var(model.BESS_Storage, model.TimePeriods, within=NonNegativeReals, bounds=power_output_storage_bounds_rule)
        model.BESS_NSP = Var(model.BESS_Storage, model.TimePeriods, within=NonNegativeReals, bounds=power_output_storage_bounds_rule)
        model.BESS_SUPP = Var(model.BESS_Storage, model.TimePeriods, within=NonNegativeReals, bounds=power_output_storage_bounds_rule)

        # Expressions for total input/output including AS
        def BESS_total_input(model, s, t):
            return model.PowerChargeBESS[s, t] + model.BESS_RegDOWN[s, t] * model.RegDOWN_efficiency[t]
        model.BESS_TotalInput = Expression(model.BESS_Storage, model.TimePeriods, rule=BESS_total_input)

        def BESS_total_output(model, s, t):
            return model.PowerDischargeBESS[s, t] + model.BESS_RegUP[s, t] * model.RegUP_efficiency[t]
        model.BESS_TotalOutput = Expression(model.BESS_Storage, model.TimePeriods, rule=BESS_total_output)

    ##################################
    # PHS Variables
    ##################################
    def define_PHS_vars(self):
        """
        Define variables and expressions specific to Pumped Hydro Storage (PHS) units.

        - Unit-level discharge flow, pump, and generator variables.
        - Ancillary service (AS) provision variables for each unit.
        - Mode and startup variables for generation and pumping.
        - Expressions for conventional mode and unit-level participation.
        - Handles both relaxed and integer (binary) formulations.
        """
        model = self.opt_model

        # Discharge flow variable for each unit
        def PHS_unit_gen_flow_rule(m, s, u, t):
            return (0, m.PHS_MaxWaterDischargeLevel[s])
        model.PHS_unit_Discharge_Flow_abovemin = Var(model.PHS_units, model.TimePeriods, within=NonNegativeReals, bounds=PHS_unit_gen_flow_rule)

        # Pump and generator bounds
        def PHS_pump_bounds_rule(m, s, u, t):
            return (0, m.PHS_Pump_rating[s])
        def PHS_gen_bounds_rule(m, s, u, t):
            return (0, m.PHS_Gen_max_rating[s])

        # Ancillary service provision variables for each unit
        model.PHS_unit_RegUP = Var(model.PHS_units, model.TimePeriods, within=NonNegativeReals, bounds=PHS_gen_bounds_rule)
        model.PHS_unit_RegDOWN = Var(model.PHS_units, model.TimePeriods, within=NonNegativeReals, bounds=PHS_gen_bounds_rule)
        model.PHS_unit_SP = Var(model.PHS_units, model.TimePeriods, within=NonNegativeReals, bounds=PHS_gen_bounds_rule)
        model.PHS_unit_NSP = Var(model.PHS_units, model.TimePeriods, within=NonNegativeReals, bounds=PHS_gen_bounds_rule)
        model.PHS_unit_SUPP_ON = Var(model.PHS_units, model.TimePeriods, within=NonNegativeReals, bounds=PHS_gen_bounds_rule)
        model.PHS_unit_SUPP_OFF = Var(model.PHS_units, model.TimePeriods, within=NonNegativeReals, bounds=PHS_gen_bounds_rule)

        # Mode and startup variables (relaxed or binary)
        if _is_relaxed(model):
            model.PHS_unit_genmode = Var(model.PHS_units, model.TimePeriods, within=NonNegativeReals)
            model.PHS_unit_pumpmode = Var(model.PHS_units, model.TimePeriods, within=NonNegativeReals)
            model.PHS_unit_genstart = Var(model.PHS_units, model.TimePeriods, within=NonNegativeReals)
            model.PHS_unit_pumpstart = Var(model.PHS_units, model.TimePeriods, within=NonNegativeReals)
            model.PHS_conv_var = Var(model.PHS_Storage, model.TimePeriods, within=NonNegativeReals)
            # Fix variables to provided values in relaxed case
            for s, u in model.PHS_units:
                for t in model.TimePeriods:
                    model.PHS_conv_var[s, t].fix(value(model.FixedConventionalmode[s, t]))
                    if not model.relax_PHS_vars[s]:
                        model.PHS_unit_genmode[s, u, t].fix(value(model.FixedPHSgenmode[s, u, t]))
                        model.PHS_unit_pumpmode[s, u, t].fix(value(model.FixedPHSpumpmode[s, u, t]))
                    model.PHS_unit_genstart[s, u, t].fix(value(model.FixedPHSgenstart[s, u, t]))
                    model.PHS_unit_pumpstart[s, u, t].fix(value(model.FixedPHSpumpstart[s, u, t]))
        else:
            model.PHS_unit_genmode = Var(model.PHS_units, model.TimePeriods, within=Binary)
            model.PHS_unit_pumpmode = Var(model.PHS_units, model.TimePeriods, within=Binary)
            model.PHS_unit_genstart = Var(model.PHS_units, model.TimePeriods, within=Binary)
            model.PHS_unit_pumpstart = Var(model.PHS_units, model.TimePeriods, within=Binary)
            model.PHS_conv_var = Var(model.PHS_Storage, model.TimePeriods, within=Binary)

