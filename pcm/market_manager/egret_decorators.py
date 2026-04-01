"""
Module for applying custom decorators to EGRET models.

This module modifies EGRET's behavior to handle additional storage types like PHS and BESS.
"""
import egret
from pyomo.environ import *
import sys
import importlib
# ===========================
# Helper Functions for a decorator
# ===========================
def _preallocated_list(other_iter):
    """Create a preallocated list."""
    return [0.0 for _ in other_iter]

def _time_series_dict(values):
    """Create a time series dictionary."""
    return {'data_type': 'time_series', 'values': values}

def _populate_storage_dicts(storage, data_time_periods, baseMVA_val, model):
    '''Populate storage dictionaries with time series data from the pyomo model.'''
    time_series_keys = [
                "regulation_up_supplied", "regulation_down_supplied", "spinning_reserve_supplied", "non_spinning_reserve_supplied", "supplemental_reserve_supplied",
                "binvar_input", "binvar_output", "binvar_Reg", "binvar_SP", "binvar_NSP", "binvar_SUPP", "soc_mismatch_DA", "p_charge_only", "p_discharge_only"
            ]
    for s, s_dict in storage.items():
        # Build time series for each key
        time_series_dicts = {key: _preallocated_list(data_time_periods) for key in time_series_keys}    
        for dt, mt in enumerate(model.TimePeriods):
            time_series_dicts["binvar_input"][dt] = value(model.InputStorage[s, mt])
            time_series_dicts["binvar_output"][dt] = value(model.OutputStorage[s, mt])
            time_series_dicts["soc_mismatch_DA"][dt] = value(model.soc_slack[s, mt]) 

            ch_var_name = f"PowerCharge{ s_dict['category'] }"
            time_series_dicts["p_charge_only"][dt] = value(getattr(model, ch_var_name)[s, mt]) * baseMVA_val
            disch_var_name = f"PowerDischarge{ s_dict['category'] }"
            time_series_dicts["p_discharge_only"][dt] = value(getattr(model, disch_var_name)[s, mt]) * baseMVA_val
            if s_dict.get("storage_type") != "Generic":
                time_series_dicts["regulation_up_supplied"][dt] = value(model.OutputStorage_RegUP[s, mt]) * baseMVA_val
                time_series_dicts["regulation_down_supplied"][dt] = value(model.InputStorage_RegDOWN[s, mt]) * baseMVA_val
                time_series_dicts["spinning_reserve_supplied"][dt] = value(model.OutputStorage_SP[s, mt]) * baseMVA_val
                time_series_dicts["non_spinning_reserve_supplied"][dt] = value(model.OutputStorage_NSP[s, mt]) * baseMVA_val
                time_series_dicts["supplemental_reserve_supplied"][dt] = value(model.OutputStorage_SUPP[s, mt]) * baseMVA_val

                time_series_dicts["binvar_Reg"][dt] = value(model.BinStorage_reg[s, mt])
                time_series_dicts["binvar_SP"][dt] = value(model.BinStorage_SP[s, mt])
                time_series_dicts["binvar_NSP"][dt] = value(model.BinStorage_NSP[s, mt])
                time_series_dicts["binvar_SUPP"][dt] = value(model.BinStorage_SUPP[s, mt])
        # Assign time series dictionaries to storage
        for key, values in time_series_dicts.items():
            s_dict[key] = _time_series_dict(values)
        if s_dict["storage_type"] == "PHS":
            s_dict["Unit_GenMode"] = {}
            s_dict["Unit_PumpMode"] = {}
            s_dict["Unit_GenStart"] = {}
            s_dict["Unit_PumpStart"] = {}
            unit_conventional_mode_var = _preallocated_list(data_time_periods)
            for dt, mt in enumerate(model.TimePeriods):
                unit_conventional_mode_var[dt] = int(round(value(model.PHS_conv_var[s, mt])))
            s_dict["PHSConventionalMode"] = _time_series_dict(unit_conventional_mode_var)
            for u in range(s_dict["num_units"]):
                unit_keys = ["Unit_GenMode", "Unit_PumpMode", "Unit_GenStart", "Unit_PumpStart"]
                unit_dicts = {key: _preallocated_list(data_time_periods) for key in unit_keys}
                for dt, mt in enumerate(model.TimePeriods):
                    unit_dicts["Unit_GenMode"][dt] = int(round(value(model.PHS_unit_genmode[s, u, mt])))
                    unit_dicts["Unit_PumpMode"][dt] = int(round(value(model.PHS_unit_pumpmode[s, u, mt])))
                    unit_dicts["Unit_GenStart"][dt] = int(round(value(model.PHS_unit_genstart[s, u, mt])))
                    unit_dicts["Unit_PumpStart"][dt] = int(round(value(model.PHS_unit_pumpstart[s, u, mt])))    
                for key, values in unit_dicts.items():
                    s_dict[key][s, u] = _time_series_dict(values)
# ===========================
# EGRET Decorators
# ===========================
def modify_generator(original_func):
    """Decorator to modify the binary variable generator."""
    def wrapper(*args, **kwargs):
        yield from original_func(*args, **kwargs)  # Unpack args properly
        obj = args[0]  # Assuming the first argument holds the attributes
        if value(obj.PHS_present) or value(obj.BESS_present):
            yield obj.BinStorage_reg
            yield obj.BinStorage_SP
            yield obj.BinStorage_NSP
            yield obj.BinStorage_SUPP
        if value(obj.PHS_present):
            yield obj.PHS_unit_genmode
            yield obj.PHS_unit_pumpmode
            yield obj.PHS_unit_genstart
            yield obj.PHS_unit_pumpstart
            yield obj.PHS_conv_var
    return wrapper

def modify_generator2(original_func):
    """Decorator to modify the UC results saving function."""
    def wrapper(*args, **kwargs):
        model = args[0]  # Unpack both expected arguments
        md = model.model_data
        storage = dict(md.elements(element_type='storage'))
        data_time_periods = md.data['system']['time_keys']
        baseMVA_val = md.data['system']['baseMVA']
        _populate_storage_dicts(storage, data_time_periods, baseMVA_val, model)
        return original_func(model, **kwargs)
    return wrapper
# ===========================
# Apply Decorators
# ===========================
def apply_egret_decorators():
    """Apply custom decorators to EGRET."""
    # Replace module
    old_module_name = "egret.model_library.unit_commitment.services"
    new_module = importlib.import_module("pcm.storage_manager.storage_main")
    sys.modules[old_module_name] = new_module
    # Apply first decorator
    from egret.common.lazy_ptdf_utils import _binary_var_generator
    egret.common.lazy_ptdf_utils._binary_var_generator = modify_generator(_binary_var_generator)
    # Apply second decorator
    from egret.models.unit_commitment import _save_uc_results as original_uc_result_module
    egret.models.unit_commitment._save_uc_results = modify_generator2(original_uc_result_module)
    # After applying decorators, import necessary modules from EGRET
    from egret.models.unit_commitment import create_tight_unit_commitment_model, _solve_unit_commitment, _save_uc_results
    #from egret.models.unit_commitment import uc_model_generator
    return create_tight_unit_commitment_model, _solve_unit_commitment, _save_uc_results