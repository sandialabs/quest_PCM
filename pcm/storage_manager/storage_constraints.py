from pyomo.environ import *
from egret.model_library.unit_commitment.status_vars import _is_relaxed

class StorageConstraints():
    """
    StorageConstraints defines and enforces all Pyomo constraints and expressions
    related to storage operation for GESS, BESS, and PHS units.

    Attributes:
        opt_model: The Pyomo model to which constraints and expressions are added.
    """
    def __init__(self, pyomo_model):
        """
        Initialize the StorageConstraints object.

        Args:
            pyomo_model: The Pyomo model object to operate on.
        """
        self.opt_model = pyomo_model

    def enforce_common_storage_constraints(self):
        """
        Enforce constraints that are common to all storage types (GESS, BESS, PHS).

        - Enforces exclusive reserve stacking (limits the number of ancillary services a storage unit can provide simultaneously).
        - Enforces storage end-point state-of-charge (SoC) constraints for DA and RT markets.
        """
        model = self.opt_model
        def enforce_exclusive_reserve_rule(model, s, t):
            return (model.BinStorage_reg[s, t] + model.BinStorage_SP[s, t] + 
                model.BinStorage_NSP[s, t] + model.BinStorage_SUPP[s, t] <= model.storage_AS_stacking)
            
        model.ExclusiveReserve = Constraint(model.BESS_PHS_set, model.TimePeriods, rule=enforce_exclusive_reserve_rule)

        # storage end-point constraints  
        def storage_end_point_soc_rule(m, s, t):
            # storage s, last time period
            if m.model_data.data["current_market"] == "DA":
                m.soc_slack[s, t].fix(0.0)
                if t == 24:
                    return m.SocStorage[s, t] >= m.EndPointSocStorage[s]  # Enforce SoC[24] ≥ SoC[0]
                elif t == value(m.NumTimePeriods):  # Assuming this is 36
                    return m.SocStorage[s, t] >= m.EndPointSocStorage[s]  # m.SocStorage[s, 24]      # Enforce SoC[36] ≥ SoC[24]
                else:
                    return Constraint.Skip
            else:
                if t == value(m.NumTimePeriods):
                    return m.SocStorage[s, t] + m.soc_slack[s, t] >= m.RT_SoC_requirement[s,t]
                else:
                    m.soc_slack[s, t].fix(0.0)
                    return Constraint.Skip
        model.EnforceEndPointSocStorage = Constraint(model.Storage, model.TimePeriods, rule=storage_end_point_soc_rule)
        
    ##################################
    # GESS Constraints  #
    ##################################
    def enforce_GESS_storage_constraints(self):
        """
        Enforce constraints and define variables/expressions specific to Generic Energy Storage Systems (GESS).

        - Input/output complementarity (cannot charge and discharge simultaneously)
        - Power input/output bounds and variables
        - SoC minimum constraint
        - Input/output power limits
        - Ramping constraints for input/output
        - Energy conservation constraint
        - Storage cost expression
        """
        model = self.opt_model
        def input_output_complementarity_rule(m,s,t):
            return m.InputStorage[s,t] + m.OutputStorage[s,t] <= 1
        model.InputOutputComplementarity = Constraint(model.GESS_Storage, model.TimePeriods, rule=input_output_complementarity_rule)

        # amount of output power of each storage unit, at each time period, on the grid side
        def power_output_storage_bounds_rule(m, s, t):
            return (0, m.MaximumPowerOutputStorage[s])
        model.PowerDischargeGESS = Var(model.GESS_Storage, model.TimePeriods, within=NonNegativeReals, bounds=power_output_storage_bounds_rule)

        # amount of input power of each storage unit, at each time period, on the grid side
        def power_input_storage_bounds_rule(m, s, t):
            return (0, m.MaximumPowerInputStorage[s])
        model.PowerChargeGESS = Var(model.GESS_Storage, model.TimePeriods, within=NonNegativeReals, bounds=power_input_storage_bounds_rule)

        def min_soc_rule(model, m, t):
            return model.SocStorage[m,t] >= model.MinimumSocStorage[m]
        model.SocMinimum = Constraint(model.GESS_Storage, model.TimePeriods, rule=min_soc_rule)

        def enforce_storage_input_limits_rule_part_a(m, s, t):
            return m.MinimumPowerInputStorage[s] * (m.InputStorage[s, t]) <= m.PowerChargeGESS[s,t]
        model.EnforceStorageInputLimitsPartA = Constraint(model.GESS_Storage, model.TimePeriods, rule=enforce_storage_input_limits_rule_part_a)

        def enforce_storage_input_limits_rule_part_b(m, s, t):
            return m.PowerChargeGESS[s,t] <= m.MaximumPowerInputStorage[s] * (m.InputStorage[s, t])
        model.EnforceStorageInputLimitsPartB = Constraint(model.GESS_Storage, model.TimePeriods, rule=enforce_storage_input_limits_rule_part_b)

        def enforce_storage_output_limits_rule_part_a(m, s, t):
            return m.MinimumPowerOutputStorage[s] * m.OutputStorage[s, t] <= m.PowerDischargeGESS[s,t]
        model.EnforceStorageOutputLimitsPartA = Constraint(model.GESS_Storage, model.TimePeriods, rule=enforce_storage_output_limits_rule_part_a)

        def enforce_storage_output_limits_rule_part_b(m, s, t):
            return m.PowerDischargeGESS[s,t] <= m.MaximumPowerOutputStorage[s] * m.OutputStorage[s, t]
        model.EnforceStorageOutputLimitsPartB = Constraint(model.GESS_Storage, model.TimePeriods, rule=enforce_storage_output_limits_rule_part_b)

        #####################################
        # energy storage ramping contraints #
        #####################################

        def enforce_ramp_up_rates_power_output_storage_rule(m, s, t):
            if value(m.ScaledNominalRampUpLimitStorageOutput[s]) >= \
                    value(m.MaximumPowerOutputStorage[s]-m.MinimumPowerOutputStorage[s]):
                return Constraint.Skip
            if t == m.InitialTime:
                return m.PowerDischargeGESS[s, t] <= m.StoragePowerOutputOnT0[s] + m.ScaledNominalRampUpLimitStorageOutput[s]
            else:
                return m.PowerDischargeGESS[s, t] <= m.PowerDischargeGESS[s, t-1] + m.ScaledNominalRampUpLimitStorageOutput[s]

        model.EnforceStorageOutputRampUpRates = Constraint(model.GESS_Storage, model.TimePeriods, rule=enforce_ramp_up_rates_power_output_storage_rule)

        def enforce_ramp_down_rates_power_output_storage_rule(m, s, t):
            if value(m.ScaledNominalRampDownLimitStorageOutput[s]) >= \
                    value(m.MaximumPowerOutputStorage[s]-m.MinimumPowerOutputStorage[s]):
                return Constraint.Skip
            if t == m.InitialTime:
                return m.PowerDischargeGESS[s, t] >= m.StoragePowerOutputOnT0[s] - m.ScaledNominalRampDownLimitStorageOutput[s]
            else:
                return m.PowerDischargeGESS[s, t] >= m.PowerDischargeGESS[s, t-1] - m.ScaledNominalRampDownLimitStorageOutput[s]
        model.EnforceStorageOutputRampDownRates = Constraint(model.GESS_Storage, model.TimePeriods, rule=enforce_ramp_down_rates_power_output_storage_rule)

        def enforce_ramp_up_rates_power_input_storage_rule(m, s, t):
            if value(m.ScaledNominalRampUpLimitStorageInput[s]) >= \
                    value(m.MaximumPowerInputStorage[s]-m.MinimumPowerInputStorage[s]):
                return Constraint.Skip
            if t == m.InitialTime:
                return m.PowerChargeGESS[s, t] <= m.StoragePowerInputOnT0[s] + m.ScaledNominalRampUpLimitStorageInput[s]
            else:
                return m.PowerChargeGESS[s, t] <= m.PowerChargeGESS[s, t-1] + m.ScaledNominalRampUpLimitStorageInput[s]
        model.EnforceStorageInputRampUpRates = Constraint(model.GESS_Storage, model.TimePeriods, rule=enforce_ramp_up_rates_power_input_storage_rule)

        def enforce_ramp_down_rates_power_input_storage_rule(m, s, t):
            if value(m.ScaledNominalRampDownLimitStorageInput[s]) >= \
                    value(m.MaximumPowerInputStorage[s]-m.MinimumPowerInputStorage[s]):
                return Constraint.Skip
            if t == m.InitialTime:
                return m.PowerChargeGESS[s, t] >= m.StoragePowerInputOnT0[s] - m.ScaledNominalRampDownLimitStorageInput[s]
            else:
                return m.PowerChargeGESS[s, t] >= m.PowerChargeGESS[s, t-1] - m.ScaledNominalRampDownLimitStorageInput[s]
        model.EnforceStorageInputRampDownRates = Constraint(model.GESS_Storage, model.TimePeriods, rule=enforce_ramp_down_rates_power_input_storage_rule)

        def energy_conservation_rule(m, s, t):
            # storage s, time t
            if t == m.InitialTime:
                return m.SocStorage[s, t] == m.StorageSocOnT0[s]  + \
                    (-m.PowerDischargeGESS[s, t]/m.OutputEfficiencyEnergy[s] + m.PowerChargeGESS[s,t]*m.InputEfficiencyEnergy[s])*m.TimePeriodLengthHours/m.MaximumEnergyStorage[s]
            else:
                return m.SocStorage[s, t] == m.SocStorage[s, t-1]*m.ScaledRetentionRate[s]  + \
                    (-m.PowerDischargeGESS[s, t]/m.OutputEfficiencyEnergy[s] + m.PowerChargeGESS[s,t]*m.InputEfficiencyEnergy[s])*m.TimePeriodLengthHours/m.MaximumEnergyStorage[s]
        model.EnergyConservation = Constraint(model.GESS_Storage, model.TimePeriods, rule=energy_conservation_rule)
        
        def GESS_storage_cost_rule(m, s, t):
            return m.ChargeCost[s]*m.PowerChargeGESS[s,t]*m.TimePeriodLengthHours + \
                    m.DischargeCost[s]*m.PowerDischargeGESS[s,t]*m.TimePeriodLengthHours
        model.GESS_cost = Expression(model.GESS_Storage, model.TimePeriods, rule=GESS_storage_cost_rule)

    ##################################
    # BESS constraints  #
    ##################################
    def enforce_BESS_constraints(self):
        """
        Enforce constraints and define expressions specific to Battery Energy Storage Systems (BESS).

        - Ancillary service (AS) constraints for regulation, spinning, non-spinning, and supplemental reserves.
        - Power and SoC constraints, including minimum/maximum SoC and energy conservation.
        - Storage cost expression for BESS.
        """
        model = self.opt_model
        def create_AS_constraints(model, bin_var, output_var, suffix):
            model.add_component(f"EnforceBESS{suffix}PartB", Constraint(
                model.BESS_Storage, model.TimePeriods,
                rule=lambda m, s, t: output_var[s, t] <= model.storage_power[s] * bin_var[s, t]
            ))
            
        create_AS_constraints(model, model.BinStorage_reg, model.BESS_RegUP, "RegUP")
        create_AS_constraints(model, model.BinStorage_reg, model.BESS_RegDOWN, "RegDOWN")
        create_AS_constraints(model, model.BinStorage_SP, model.BESS_SP, "SP")
        create_AS_constraints(model, model.BinStorage_NSP, model.BESS_NSP, "NSP")
        create_AS_constraints(model, model.BinStorage_SUPP, model.BESS_SUPP, "SUPP")
        
        def max_overall_power_rule(model, s, t):
            return model.PowerDischargeBESS[s,t] + model.BESS_RegUP[s,t] + model.BESS_SP[s,t] + \
                    model.BESS_NSP[s,t] + model.BESS_SUPP[s,t] + model.PowerChargeBESS[s,t] + \
                    model.BESS_RegDOWN[s,t] <= model.storage_power[s]
        model.StoragePowerCons = Constraint(model.BESS_Storage, model.TimePeriods, rule=max_overall_power_rule)
        
        def BESS_min_soc_rule(model, s, t):
            return model.SocStorage[s,t] >= model.MinimumSocStorage[s] + (model.BESS_SP[s,t] + \
                                        model.BESS_NSP[s,t]+ model.BESS_SUPP[s,t] + \
                                        model.BESS_RegUP[s,t])*model.AS_SoC_time_requirement/model.MaximumEnergyStorage[s]
        model.BESSSocMinimum = Constraint(model.BESS_Storage, model.TimePeriods, rule=BESS_min_soc_rule)
        
        def BESS_max_soc_rule(model, s, t):
            return model.SocStorage[s,t] <= model.MaximumSocStorage[s] - model.BESS_RegDOWN[s,t] * model.AS_SoC_time_requirement/model.MaximumEnergyStorage[s]
        model.BESSSocMaximum = Constraint(model.BESS_Storage, model.TimePeriods, rule=BESS_max_soc_rule)
        
        def BESS_cycle_rule(m, s): #Not active right now
            if model.current_market == "DA":
                return sum(m.PowerDischargeBESS[s, t] for t in m.TimePeriods) <= m.CycleLimit[s] * (model.MaximumSocStorage[s] - model.MinimumSocStorage[s]) * model.MaximumEnergyStorage[s]

        def BESS_energy_conservation_rule(m, s, t):
            # storage s, time t
            if t == m.InitialTime:
                return  (m.SocStorage[s, t] == m.StorageSocOnT0[s] + 
                        (-m.PowerDischargeBESS[s, t] + m.PowerChargeBESS[s,t]*m.ConversionEfficiency[s] + 
                        m.RegDOWN_efficiency[t]*m.ConversionEfficiency[s]*m.BESS_RegDOWN[s,t] - 
                        m.RegUP_efficiency[t]*m.BESS_RegUP[s,t] - 
                        m.SP_selector[t]*m.BESS_SP[s,t]    - 
                        m.NSP_selector[t]*m.BESS_NSP[s,t]  -
                        m.SUPP_selector[t]*m.BESS_SUPP[s,t])*m.TimePeriodLengthHours/m.MaximumEnergyStorage[s])
            else:
                return  (m.SocStorage[s, t] == m.SocStorage[s, t-1]*m.ScaledRetentionRate[s]  + 
                        (-m.PowerDischargeBESS[s, t] + m.PowerChargeBESS[s,t]*m.ConversionEfficiency[s] + 
                        m.RegDOWN_efficiency[t]*m.ConversionEfficiency[s]*m.BESS_RegDOWN[s,t] - 
                        m.RegUP_efficiency[t]*m.BESS_RegUP[s,t] - 
                        m.SP_selector[t]*m.BESS_SP[s,t]    - 
                        m.NSP_selector[t]*m.BESS_NSP[s,t]  -
                        m.SUPP_selector[t]*m.BESS_SUPP[s,t])*m.TimePeriodLengthHours/m.MaximumEnergyStorage[s])
        model.BESSEnergyConservation = Constraint(model.BESS_Storage, model.TimePeriods, rule=BESS_energy_conservation_rule)
        
        def BESS_cost_rule(m, s, t):
            return (m.DischargeCost[s]*(m.PowerDischargeBESS[s,t] +
                        m.RegUP_efficiency[t]*m.BESS_RegUP[s,t] +
                        m.SP_selector[t]*m.BESS_SP[s,t] + 
                        m.NSP_selector[t]*m.BESS_NSP[s,t]  +
                        m.SUPP_selector[t]*m.BESS_SUPP[s,t])*m.TimePeriodLengthHours)
        model.BESS_cost = Expression(model.BESS_Storage, model.TimePeriods, rule=BESS_cost_rule)
    ##################################
    # PHS constraints  #
    ##################################
    def enforce_PHS_unit_constraints(self):
        """
        Enforce constraints and define expressions for Pumped Hydro Storage (PHS) units at the unit level.

        - Defines unit-level output/input, flow, and mode constraints.
        - Enforces complementarity between generation and pumping modes.
        - Startup constraints for generator and pump units.
        - Aggregates unit-level variables to storage-level expressions.
        """
        model = self.opt_model
        
        def PHS_unit_discharge_power_expr(m, s, u ,t):
            return m.PHS_unit_genmode[s,u,t]*m.PHS_Gen_min_rating[s] + m.PHS_unit_Discharge_Flow_abovemin[s,u,t] * m.PHS_conversion_coefficient[s]
        model.PHS_unit_Output = Expression(model.PHS_units, model.TimePeriods, rule=PHS_unit_discharge_power_expr)
        
        def flow_limit_cons(m, s, u, t):
            return m.PHS_unit_Discharge_Flow_abovemin[s,u,t]  <= m.PHS_unit_genmode[s,u,t]*(m.PHS_MaxWaterDischargeLevel[s]-m.PHS_MinWaterDischargeLevel[s])
        model.PHS_discharge_flow_limit = Constraint(model.PHS_units, model.TimePeriods, rule = flow_limit_cons)
        
        def PHS_unit_discharge_flow_expr(m, s, u ,t):
            return m.PHS_unit_genmode[s,u,t]*m.PHS_MinWaterDischargeLevel[s] + model.PHS_unit_Discharge_Flow_abovemin[s,u,t]
        model.PHS_unit_Discharge_Flow = Expression(model.PHS_units, model.TimePeriods, rule=PHS_unit_discharge_flow_expr)
        
        def pump_power_expr(m, s ,u, t):
            return m.PHS_unit_pumpmode[s,u,t]*m.PHS_Pump_rating[s]
        model.PHS_unit_Input = Expression(model.PHS_units, model.TimePeriods, rule=pump_power_expr)
        
        def PHS_unit_charge_flow_expr(m, s, u ,t):
            return m.PHS_unit_pumpmode[s,u,t]*m.PHS_MaxWaterPumpLevel[s]
        model.PHS_unit_Charge_Flow = Expression(model.PHS_units, model.TimePeriods, rule=PHS_unit_charge_flow_expr)
        
        #If generator is on it must deliver minimum amount of power, independent of reserves
        def min_output_power_cons(m, s ,u, t):
            return m.PHS_unit_Output[s,u,t] - m.PHS_unit_RegDOWN[s,u,t] >=  m.PHS_unit_genmode[s,u,t]*m.PHS_Gen_min_rating[s]
        
        model.PHS_min_output_cons = Constraint(model.PHS_units, model.TimePeriods, rule=min_output_power_cons)
        
        #Ensure generation and online AS services only when unit is in generation mode
        def PHS_upward_power_cons_online(m, s ,u, t):
            return m.PHS_unit_Output[s,u,t] + m.PHS_unit_RegUP[s,u,t] + m.PHS_unit_SP[s,u,t] + m.PHS_unit_SUPP_ON[s,u,t] <=  m.PHS_unit_genmode[s,u,t]*m.PHS_Gen_max_rating[s]
        
        model.PHS_upward_cons_online = Constraint(model.PHS_units, model.TimePeriods, rule=PHS_upward_power_cons_online)
        
        def PHS_upward_power_cons_offline(m, s ,u, t):
            return m.PHS_unit_NSP[s,u,t] + m.PHS_unit_SUPP_OFF[s,u,t] <=  (1-m.PHS_unit_genmode[s,u,t])*m.PHS_Gen_max_rating[s]
        
        model.PHS_upward_cons_offline = Constraint(model.PHS_units, model.TimePeriods, rule=PHS_upward_power_cons_offline)
        
        def gen_pump_complementarity_rule(m, s, u, t):
            return m.PHS_unit_genmode[s,u,t] + m.PHS_unit_pumpmode[s,u,t] <= 1
        model.PHS_unit_GenPumpComplementarity = Constraint(model.PHS_units, model.TimePeriods, rule=gen_pump_complementarity_rule)

        if not _is_relaxed(model):
            
            #Startup constraints for generator and pumps
            def PHS_gen_startup_cons(m,s,u,t):
                if t == m.InitialTime:
                    return m.PHS_unit_genstart[s,u,t] >= m.PHS_unit_genmode[s,u,t] - m.PHS_Initial_GenMode[s,u] 
                else:
                    return m.PHS_unit_genstart[s,u,t] >= m.PHS_unit_genmode[s,u,t] - m.PHS_unit_genmode[s,u,t-1]
            model.PHS_units_gen_startup_cons = Constraint(model.PHS_units, model.TimePeriods, rule=PHS_gen_startup_cons)
            
            def PHS_pump_startup_cons(m,s,u,t):
                if t == m.InitialTime:
                    return m.PHS_unit_pumpstart[s,u,t] >= m.PHS_unit_pumpmode[s,u,t]  - m.PHS_Initial_PumpMode[s,u]
                else:
                    return m.PHS_unit_pumpstart[s,u,t] >= m.PHS_unit_pumpmode[s,u,t] - m.PHS_unit_pumpmode[s,u,t-1]
            model.PHS_units_pump_startup_cons = Constraint(model.PHS_units, model.TimePeriods, rule=PHS_pump_startup_cons)
            
            #Only pump or generator can be started at a time
            def PHS_gen_pump_startup_complimentary(m,s,u,t):
                return m.PHS_unit_genstart[s,u,t] + m.PHS_unit_pumpstart[s,u,t] <= 1
            model.PHS_units_gen_pump_complimentary_cons = Constraint(model.PHS_units, model.TimePeriods, rule=PHS_gen_pump_startup_complimentary)
            
            # If PHS is in conventional mode, all units must be in pump/idle mode or generation/idle mode at a time step
            def PHS_conv_cons1(m,s,u,t):
                if not model.PHS_hsc_mode[s]:
                    return m.PHS_conv_var[s,t] >= m.PHS_unit_pumpmode[s,u,t] 
                else:
                    m.PHS_conv_var[s,t].fix(1)
                    return Constraint.Skip
            model.PHS_conventional_mode_cons1 = Constraint(model.PHS_units, model.TimePeriods, rule=PHS_conv_cons1)
            
            def PHS_conv_cons2(m,s,u,t):
                if not model.PHS_hsc_mode[s]:
                    return 1 - m.PHS_conv_var[s,t] >= m.PHS_unit_genmode[s,u,t] 
                else:
                    m.PHS_conv_var[s,t].fix(1)
                    return Constraint.Skip
            model.PHS_conventional_mode_cons2 = Constraint(model.PHS_units, model.TimePeriods, rule=PHS_conv_cons2)

        ### Expressions to aggregate unit parameters to PHS storage level ###
        
        def aggregate_PHS_discharge_vars(m, v1, v2, v3, s, t):
            #return sum(v1[s, u, t] for u in range(m.PHS_num_units[s])) 
            return sum(v1[s, u, t] + v2[s,u,t]*m.RegUP_efficiency[t] - v3[s,u,t]*m.RegDOWN_efficiency[t] for u in range(m.PHS_num_units[s])) 

        model.PHS_TotalOutput = Expression(model.PHS_Storage, model.TimePeriods, 
                                rule=lambda model, s, t: aggregate_PHS_discharge_vars(model, model.PHS_unit_Output, model.PHS_unit_RegUP, model.PHS_unit_RegDOWN, s, t))

        def aggregate_PHS_charge_vars(m, v1, s, t):
            return sum(v1[s, u, t] for u in range(m.PHS_num_units[s])) 

        model.PHS_TotalInput = Expression(model.PHS_Storage, model.TimePeriods, 
                                rule=lambda model, s, t: aggregate_PHS_charge_vars(model, model.PHS_unit_Input, s, t))

        def aggregate_PHS_AS_vars(m, v, s, t):
            return sum(v[s, u, t] for u in range(m.PHS_num_units[s]))
        
        model.PowerDischargePHS = Expression(model.PHS_Storage, model.TimePeriods, 
                                rule=lambda model, s, t: aggregate_PHS_charge_vars(model, model.PHS_unit_Output, s, t))
        model.PowerChargePHS = Expression(model.PHS_Storage, model.TimePeriods,
                                    rule=lambda m, s, t: m.PHS_TotalInput[s, t]
                                )
        model.PHS_TotalRegUP = Expression(model.PHS_Storage, model.TimePeriods, 
                                rule=lambda model, s, t: aggregate_PHS_AS_vars(model, model.PHS_unit_RegUP, s, t))
        
        model.PHS_TotalRegDOWN = Expression(model.PHS_Storage, model.TimePeriods, 
                                rule=lambda model, s, t: aggregate_PHS_AS_vars(model, model.PHS_unit_RegDOWN, s, t))

        model.PHS_TotalSP = Expression(model.PHS_Storage, model.TimePeriods, 
                            rule=lambda model, s, t: aggregate_PHS_AS_vars(model, model.PHS_unit_SP, s, t))
        
        model.PHS_TotalNSP = Expression(model.PHS_Storage, model.TimePeriods, 
                            rule=lambda model, s, t: aggregate_PHS_AS_vars(model, model.PHS_unit_NSP, s, t))

        model.PHS_TotalSUPP_ON = Expression(model.PHS_Storage, model.TimePeriods, 
                                rule=lambda model, s, t: aggregate_PHS_AS_vars(model, model.PHS_unit_SUPP_ON, s, t))
        
        model.PHS_TotalSUPP_OFF = Expression(model.PHS_Storage, model.TimePeriods, 
                                rule=lambda model, s, t: aggregate_PHS_AS_vars(model, model.PHS_unit_SUPP_OFF, s, t))
        
        model.PHS_TotalDischargeFlow = Expression(model.PHS_Storage, model.TimePeriods, 
                                rule=lambda model, s, t: aggregate_PHS_AS_vars(model, model.PHS_unit_Discharge_Flow, s, t))
        
        model.PHS_TotalChargeFlow = Expression(model.PHS_Storage, model.TimePeriods, 
                                rule=lambda model, s, t: aggregate_PHS_AS_vars(model, model.PHS_unit_Charge_Flow, s, t))
        
        def aggregate_PHS_supp_vars(model, s, t):
            return model.PHS_TotalSUPP_ON[s,t] + model.PHS_TotalSUPP_OFF[s,t]
        
        model.PHS_TotalSUPP = Expression(model.PHS_Storage, model.TimePeriods, rule=aggregate_PHS_supp_vars)
        

    def enforce_PHS_constraints(self):
        """
        Enforce constraints and define expressions for Pumped Hydro Storage (PHS) at the storage level.

        - Ancillary service (AS) constraints for PHS.
        - Minimum/maximum SoC constraints.
        - Energy conservation constraint for PHS.
        - Storage cost expression for PHS.
        """
        model = self.opt_model
        
        def create_AS_constraints(model, bin_var, output_var, suffix):
            model.add_component(f"EnforcePHS{suffix}PartA", Constraint(
                model.PHS_Storage, model.TimePeriods,
                rule=lambda m, s, t: 0 <= output_var[s, t]
            ))
            model.add_component(f"EnforcePHS{suffix}PartB", Constraint(
                model.PHS_Storage, model.TimePeriods,
                rule=lambda m, s, t: output_var[s, t] <= m.PHS_conversion_coefficient[s] * m.PHS_MaxWaterDischargeLevel[s] * bin_var[s, t]
            ))
        
        create_AS_constraints(model, model.BinStorage_reg, model.PHS_TotalRegUP, "PHS_RegUP_lim")
        create_AS_constraints(model, model.BinStorage_reg, model.PHS_TotalRegDOWN, "PHS_RegDOWN_lim")
        create_AS_constraints(model, model.BinStorage_SP, model.PHS_TotalSP, "PHS_SP_lim")
        create_AS_constraints(model, model.BinStorage_NSP, model.PHS_TotalNSP, "PHS_NSP_lim")
        create_AS_constraints(model, model.BinStorage_SUPP, model.PHS_TotalSUPP_ON, "PHS_SUPPON_lim")
        create_AS_constraints(model, model.BinStorage_SUPP, model.PHS_TotalSUPP_OFF, "PHS_SUPPOFF_lim")
        
        def PHS_min_soc_rule(m, s, t):
            return m.SocStorage[s,t] >= m.MinimumSocStorage[s] + (m.PHS_TotalSP[s,t] + \
                                                                m.PHS_TotalNSP[s,t]+ m.PHS_TotalSUPP[s,t] + \
                                                                m.PHS_TotalRegUP[s,t])/m.PHS_conversion_coefficient[s] * \
                                                                m.AS_SoC_time_requirement/m.PHS_UpperReservoirMaxLevel[s]
        model.PHSSocMinimum = Constraint(model.PHS_Storage, model.TimePeriods, rule=PHS_min_soc_rule)
        
        def PHS_max_soc_rule(m, s, t):
            return m.SocStorage[s,t] <= m.MaximumSocStorage[s] - m.PHS_TotalRegDOWN[s,t]/m.PHS_conversion_coefficient[s] \
                                                                    * m.AS_SoC_time_requirement/m.PHS_UpperReservoirMaxLevel[s]
        model.PHSSocMaximum = Constraint(model.PHS_Storage, model.TimePeriods, rule=PHS_max_soc_rule)
        
        ##########################################
        # storage energy conservation constraint #
        ##########################################
        def PHS_energy_conservation_rule(m, s, t):
            # storage s, time t
            if t == m.InitialTime:
                return  (m.SocStorage[s,t] == m.StorageSocOnT0[s] + 
                        (-m.PHS_TotalDischargeFlow[s,t]/m.PHS_GeneratorEfficiency[s] + 
                        m.PHS_TotalChargeFlow[s,t]*m.PHS_PumpEfficiency[s] + 
                        m.RegDOWN_efficiency[t]*m.PHS_TotalRegDOWN[s,t]*m.PHS_PumpEfficiency[s]/m.PHS_conversion_coefficient[s] - 
                        m.RegUP_efficiency[t]*m.PHS_TotalRegUP[s,t]/(m.PHS_GeneratorEfficiency[s]*m.PHS_conversion_coefficient[s]) - 
                        m.SP_selector[t]*m.PHS_TotalSP[s,t]/(m.PHS_GeneratorEfficiency[s]*m.PHS_conversion_coefficient[s])    - 
                        m.NSP_selector[t]*m.PHS_TotalNSP[s,t]/(m.PHS_GeneratorEfficiency[s]*m.PHS_conversion_coefficient[s])  -
                        m.SUPP_selector[t]*m.PHS_TotalSUPP[s,t]/(m.PHS_GeneratorEfficiency[s]*m.PHS_conversion_coefficient[s]))*m.TimePeriodLengthHours/m.PHS_UpperReservoirMaxLevel[s])
            else:
                return  (m.SocStorage[s,t] == m.SocStorage[s,t-1] + 
                        (-m.PHS_TotalDischargeFlow[s,t]/m.PHS_GeneratorEfficiency[s] + 
                        m.PHS_TotalChargeFlow[s,t]*m.PHS_PumpEfficiency[s] + 
                        m.RegDOWN_efficiency[t]*m.PHS_TotalRegDOWN[s,t]*m.PHS_PumpEfficiency[s]/m.PHS_conversion_coefficient[s] - 
                        m.RegUP_efficiency[t]*m.PHS_TotalRegUP[s,t]/(m.PHS_GeneratorEfficiency[s]*m.PHS_conversion_coefficient[s]) - 
                        m.SP_selector[t]*m.PHS_TotalSP[s,t]/(m.PHS_GeneratorEfficiency[s]*m.PHS_conversion_coefficient[s])    - 
                        m.NSP_selector[t]*m.PHS_TotalNSP[s,t]/(m.PHS_GeneratorEfficiency[s]*m.PHS_conversion_coefficient[s])  -
                        m.SUPP_selector[t]*m.PHS_TotalSUPP[s,t]/(m.PHS_GeneratorEfficiency[s]*m.PHS_conversion_coefficient[s]))*m.TimePeriodLengthHours/m.PHS_UpperReservoirMaxLevel[s])
        model.PHSEnergyConservation = Constraint(model.PHS_Storage, model.TimePeriods, rule=PHS_energy_conservation_rule)
        
        #################################
        # PHS cost func
        ################################
        def PHS_cost_rule(m, s, t):
            
            return (sum(m.PHS_gen_startup_cost[s]*m.PHS_unit_genstart[s,u,t] + m.PHS_pump_startup_cost[s]*m.PHS_unit_pumpstart[s,u,t] \
                        for u in range(model.PHS_num_units[s])))
            
        model.PHS_cost = Expression(model.PHS_Storage, model.TimePeriods, rule=PHS_cost_rule)

    

