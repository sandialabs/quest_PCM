import os
import datetime
import json
import re
import pandas as pd
from openpyxl.utils import get_column_letter

class ResultExporter:
    """Helper to write simulation outputs to disk.

    The class is intentionally lightweight: callers construct an
    instance and invoke the export methods to persist DA/RT JSON
    dumps and create a summarized Excel workbook for quick review.
    """

    def __init__(self):
        """Create a ResultExporter instance.

        No configuration is stored on the instance; methods are
        pure helpers that accept the data and target directories as
        arguments.
        """
        pass

    def export_json_outputs(self, ref_dict, output_directory, DA_output, RT_output):
        """Write DA and RT outputs to JSON files.

        This method performs two conveniences before writing:
        1. Recursively converts non-JSON-native objects (tuple keys,
                date/datetime objects) into JSON-safe representations.
        2. Removes values that are already present in `ref_dict`
                to avoid duplicating input configuration in the output
                dumps.

        Parameters
        - ref_dict (dict): Reference/input dictionary; keys present
            here will be removed from the written outputs.
        - output_directory (str): Directory to write `DA_results.json`
            and `RT_results.json`.
        - DA_output (dict): Day-ahead results structure to serialize.
        - RT_output (dict): Real-time results structure to serialize.

        The function writes two files under `output_directory`:
        `DA_results.json` and `RT_results.json`.
        """

        def json_safe(obj):
            """Recursively convert an object to JSON-safe types.

            - tuple keys are joined with underscores and converted to
                strings.
            - date/datetime objects are converted with `isoformat()`.
            """
            if isinstance(obj, dict):
                new_dict = {}
                for k, v in obj.items():
                    if isinstance(k, tuple):
                        new_k = "_".join(map(str, k))  # e.g. ('Gen1','2020-07-06') -> "Gen1_2020-07-06"
                    else:
                        new_k = str(k)
                    new_dict[new_k] = json_safe(v)
                return new_dict
            elif isinstance(obj, (list, tuple)):
                return [json_safe(x) for x in obj]
            elif isinstance(obj, (datetime.date, datetime.datetime)):
                return obj.isoformat()
            else:
                return obj
            
        def dict_difference(d1, d2):
            """Return a shallow recursive difference of two dicts.

            Keys that are present in `d2` are removed from `d1`. For
            nested dicts the comparison is applied recursively, and
            only entries unique to `d1` are kept.
            """
            result = {}
            for k, v in d1.items():
                if k not in d2:
                    if isinstance(v, dict):
                        # Instead of keeping v as-is, compare its contents with d2
                        nested_diff = dict_difference(v, d2)
                        if nested_diff:
                            result[k] = nested_diff
                    else:
                        result[k] = v
                else:
                    if isinstance(v, dict) and isinstance(d2[k], dict):
                        nested_diff = dict_difference(v, d2[k])
                        if nested_diff:
                            result[k] = nested_diff
                    # else: skip
            return result
        
        json_safe_DA = json_safe(DA_output)
        json_safe_RT = json_safe(RT_output)
        # Remove any keys from output that are also in input (to avoid duplication)
        json_safe_RT = dict_difference(json_safe_RT, ref_dict)
        json_safe_DA = dict_difference(json_safe_DA, ref_dict)
        with open(os.path.join(output_directory, "DA_results.json"), "w") as f:
            dumper = json.dumps(json_safe_DA, indent=2, separators=(",", ": "))
            # Collapse lists (any [...] across lines -> one line)
            dumper = re.sub(r"\[\s+([^]]*?)\s+\]", 
                        lambda m: "[" + " ".join(m.group(1).split()) + "]", 
                        dumper, flags=re.DOTALL)
            f.write(dumper)
        with open(os.path.join(output_directory, "RT_results.json"), "w") as f:
            dumper = json.dumps(json_safe_RT, indent=2, separators=(",", ": "))
            # Collapse lists (any [...] across lines -> one line)
            dumper = re.sub(r"\[\s+([^]]*?)\s+\]", 
                        lambda m: "[" + " ".join(m.group(1).split()) + "]", 
                        dumper, flags=re.DOTALL)
            f.write(dumper)

    def export_excel_file(self, RT_data, config, output_directory):
        """Create an Excel summary workbook from real-time results.

        Builds a multi-sheet workbook containing a daily summary and
        per-asset totals for thermal generators, renewables and
        storage. Additionally includes sheets for high line loadings
        and contingencies.

        Parameters
        - RT_data (dict): Mapping of date -> day result dictionaries
            produced by the real-time simulation.
        - config (dict): Configuration flags used to determine which
            revenue streams to include (reserve/regulation settings).
        - output_directory (str): Directory where
            `simulation_summary.xlsx` will be written.
        """

        daily_summary_rows = []
        generator_totals = {}
        renewable_totals = {}
        storage_totals = {}

        congestion_totals = []
        contingency_totals = []
        for day, day_dict in RT_data.items():

            time_factor = day_dict["system"]["time_period_length_minutes"] / 60
            # initialize daily summary row
            summary_row = {}
            summary_row["Date"] = day
            summary_row["Total Demand (MWh)"] = 0
            summary_row["Load Curtailed (MWh)"] = 0
            summary_row["Total Thermal Generation (MWh)"] = 0
            summary_row["Total Variable Generation (MWh)"] = 0
            summary_row["Total Storage Discharge (MWh)"] = 0
            summary_row["Total Storage Charge (MWh)"] = 0
            summary_row["Variable Generation Curtailment (MWh)"] = 0
            summary_row["Thermal Fixed Cost ($)"] = 0
            summary_row["Thermal Variable Cost ($)"] = 0
            summary_row["Variable Generation Cost ($)"] = 0
            summary_row["Storage Cost ($)"] = 0
            summary_row["Total Cost ($)"] = 0
            summary_row["Cost per MWh ($)"] = 0

            # Bus data
            bus_dict = day_dict["elements"]["bus"]
            total_load = 0
            total_curtailment = 0
            total_over_generation = 0
            for bus_num, bus_data in bus_dict.items():
                total_load += sum(bus_data["pl"]["values"]) * time_factor
                curtailment_vals = bus_data.get("p_balance_violation", {}).get("values", [])
                total_curtailment += sum(v for v in curtailment_vals if v > 0) * time_factor
                
            summary_row["Total Demand (MWh)"] = total_load
            summary_row["Load Curtailed (MWh)"] = total_curtailment
            
            #Branch and contingency (if enabled) data
            branch_dict = day_dict["elements"]["branch"]
            contingency_dict = day_dict["elements"].get("contingency", {})
            for branch_key, branch_data in branch_dict.items():
                branch_limit = branch_data.get("rating_long_term", None)
                power_flow = branch_data.get("pf", {}).get("values", [])
                for flow_idx, flow_val in enumerate(power_flow):
                    loading = abs(flow_val)/branch_limit * 100
                    if loading >= 99:
                        row = {}
                        row["Date"] = day
                        row["Time"] = day_dict["system"]["timestamp"][flow_idx]
                        row["Branch"] = branch_key
                        row["Flow (MW)"] = flow_val
                        row["Loading (%)"] = loading
                        congestion_totals.append(row)

                if contingency_dict.get(branch_key,{}).get("monitored_branches", None):
                    branch_flows = contingency_dict[branch_key]["monitored_branches"]["values"]
                    
                    for viol_time, viol_dat in enumerate(branch_flows):
                        for viol_branch, viol_values in viol_dat.items():
                            violation_val = viol_values['pf']
                            branch_ST = branch_dict[viol_branch]['rating_short_term']
                            branch_ER = branch_dict[viol_branch]['rating_emergency']
                            violation_percent_cont = (abs(violation_val) / branch_limit) * 100
                            violation_percent_ST = (abs(violation_val) / branch_ST) * 100
                            violation_percent_ER = (abs(violation_val) / branch_ER) * 100
                            if any(
                                vp >= 100.05
                                for vp in (
                                    violation_percent_cont,
                                    violation_percent_ST,
                                    violation_percent_ER,
                                )
                            ):
                                row = {}
                                row["Date"] = day
                                row["Time"] = day_dict["system"]["timestamp"][viol_time]
                                row["Outage Branch"] = branch_key
                                row["Monitored Branch"] = viol_branch
                                row["Flow (MW)"] = violation_val
                                row["Cont. Loading (%)"] = violation_percent_cont
                                row["STE Loading (%)"] = violation_percent_ST
                                row["LTE Loading (%)"] = violation_percent_ER
                                contingency_totals.append(row)

            # Thermal generator data
            gen_dict_all = day_dict["elements"]["generator"]
            for gen_num, gen_dict in gen_dict_all.items():
                if gen_dict.get("generator_type") != "thermal":
                    continue

                if gen_num not in generator_totals:
                    # Initialize totals for this generator
                    generator_totals[gen_num] = {
                        "Generator ID": gen_num,
                        "Total committed hours": 0,
                        "Total generation (MWh)": 0,
                        "Fixed cost ($)": 0,
                        "Variable cost ($)": 0,
                        "Total cost ($)": 0,
                        "Energy Revenue ($)": 0
                    }
                    # Only add reserve revenue if config enables it
                    if config.get("System Reserve") is not None:
                        generator_totals[gen_num]["Reserve Revenue ($)"] = 0
                    # Only add regulation revenue if config enables it
                    if config.get("Regulation Up") is not None or config.get("Regulation Down") is not None:
                        generator_totals[gen_num]["Regulation Revenue ($)"] = 0
                    if config.get("Spinning Reserve") is not None:
                        generator_totals[gen_num]["Spinning Reserve Revenue ($)"] = 0
                    if config.get("NonSpinning Reserve") is not None:
                        generator_totals[gen_num]["Non-Spinning Reserve Revenue ($)"] = 0
                    if config.get("Supplemental Reserve") is not None:
                        generator_totals[gen_num]["Supplemental Reserve Revenue ($)"] = 0
                    if config.get("Flexible Ramp Up") is not None or config.get("Flexible Ramp Down") is not None:
                        generator_totals[gen_num]["Flex Ramp Revenue ($)"] = 0
                    generator_totals[gen_num]["Total Revenue ($)"] = 0
                    generator_totals[gen_num]["Uplift ($)"] = 0

                c = lambda k: gen_dict.get(k, {}).get("values", [])

                generator_totals[gen_num]["Total committed hours"] += sum(c("commitment")) * time_factor
                generator_totals[gen_num]["Total generation (MWh)"] += sum(c("pg")) * time_factor
                gen_fixed_cost = sum(c("commitment_cost"))
                gen_variable_cost = sum(c("production_cost"))
                generator_totals[gen_num]["Fixed cost ($)"] += gen_fixed_cost
                generator_totals[gen_num]["Variable cost ($)"] += gen_variable_cost
                generator_totals[gen_num]["Total cost ($)"] += gen_fixed_cost + gen_variable_cost

                gen_energy_rev = sum(c("energy_revenue"))
                generator_totals[gen_num]["Energy Revenue ($)"] += gen_energy_rev
                gen_rev_daily = gen_energy_rev
                if config.get("System Reserve") is not None:
                    gen_res_daily = sum(c("DA_reserve_revenue"))
                    generator_totals[gen_num]["Reserve Revenue ($)"] += gen_res_daily
                    gen_rev_daily += gen_res_daily

                if config.get("Regulation Up") is not None or config.get("Regulation Down") is not None:
                    gen_reg_up_daily = sum(c("regulation_up_revenue"))
                    gen_reg_down_daily = sum(c("regulation_down_revenue"))
                    generator_totals[gen_num]["Regulation Revenue ($)"] += gen_reg_up_daily + gen_reg_down_daily
                    gen_rev_daily += gen_reg_up_daily + gen_reg_down_daily

                if config.get("Spinning Reserve") is not None:
                    gen_spin_res_daily = sum(c('spinning_reserve_revenue'))
                    generator_totals[gen_num]["Spinning Reserve Revenue ($)"] += gen_spin_res_daily
                    gen_rev_daily += gen_spin_res_daily

                if config.get("NonSpinning Reserve") is not None:
                    gen_nonspin_res_daily = sum(c('non_spinning_reserve_revenue'))
                    generator_totals[gen_num]["Non-Spinning Reserve Revenue ($)"] += gen_nonspin_res_daily
                    gen_rev_daily += gen_nonspin_res_daily

                if config.get("Supplemental Reserve") is not None:
                    gen_supp_res_daily = sum(c('supplemental_reserve_revenue'))
                    generator_totals[gen_num]["Supplemental Reserve Revenue ($)"] += gen_supp_res_daily
                    gen_rev_daily += gen_supp_res_daily

                if config.get("Flexible Ramp Up") is not None or config.get("Flexible Ramp Down") is not None:
                    gen_flex_ramp_up_daily = sum(c("flexible_ramp_up_revenue"))
                    gen_flex_ramp_down_daily = sum(c("flexible_ramp_down_revenue"))
                    generator_totals[gen_num]["Flex Ramp Revenue ($)"] += gen_flex_ramp_up_daily + gen_flex_ramp_down_daily
                    gen_rev_daily += gen_flex_ramp_up_daily + gen_flex_ramp_down_daily

                generator_totals[gen_num]["Total Revenue ($)"] += gen_rev_daily
                generator_totals[gen_num]["Uplift ($)"] += max(0, - gen_rev_daily + gen_variable_cost + gen_fixed_cost)

                summary_row["Total Thermal Generation (MWh)"] += sum(c("pg")) * time_factor
                summary_row["Thermal Fixed Cost ($)"] += gen_fixed_cost
                summary_row["Thermal Variable Cost ($)"] += gen_variable_cost
                summary_row["Total Cost ($)"] += gen_fixed_cost + gen_variable_cost

            # Renewable generation data
            for gen_num, gen_dict in gen_dict_all.items():
                if gen_dict["generator_type"] != "renewable":   # <-- FIXED
                    continue
                if gen_num not in renewable_totals:
                    renewable_totals[gen_num] = {
                        "Generator ID": gen_num,
                        "Total generation (MWh)": 0,
                        "Cost ($)": 0,
                        "Curtailed energy (MWh)": 0,
                        "Total Revenue ($)": 0
                    }
                c = lambda k: gen_dict.get(k, {}).get("values", [])
        
                renewable_totals[gen_num]["Total generation (MWh)"] += sum(c('pg')) * time_factor
                var_prod_cost = sum(c('production_cost'))
                renewable_totals[gen_num]["Cost ($)"] += var_prod_cost
                curtailed_energy = sum(c('p_max')[i] - c('pg')[i] for i in range(len(c('pg')))) * time_factor
                curtailed_energy = curtailed_energy if abs(curtailed_energy) > 1e-2 else 0
                renewable_totals[gen_num]["Curtailed energy (MWh)"] += curtailed_energy
                renewable_totals[gen_num]["Total Revenue ($)"] += sum(c('energy_revenue'))

                summary_row["Total Variable Generation (MWh)"] += sum(c("pg")) * time_factor
                summary_row["Variable Generation Curtailment (MWh)"] += curtailed_energy
                summary_row["Variable Generation Cost ($)"] += var_prod_cost
                summary_row["Total Cost ($)"] += var_prod_cost

            # Storage Data
            storage_dict = day_dict["elements"]["storage"]
            for storage_num, storage_dict in storage_dict.items():
                if storage_num not in storage_totals:
                    storage_totals[storage_num] = {
                        "Storage ID": storage_num,
                        "Total charge (MWh)": 0,
                        "Total discharge (MWh)": 0,
                        "Approx. Throughput (MWh)": 0,
                        "Cost ($)": 0,
                        "Energy Revenue ($)": 0
                    }
                    # Only add regulation revenue if config enables it
                    if config.get("Regulation Up") is not None or config.get("Regulation Down") is not None:
                        storage_totals[storage_num]["Regulation Revenue ($)"] = 0
                    if config.get("Spinning Reserve") is not None:
                        storage_totals[storage_num]["Spinning Reserve Revenue ($)"] = 0
                    if config.get("NonSpinning Reserve") is not None:
                        storage_totals[storage_num]["Non-Spinning Reserve Revenue ($)"] = 0
                    if config.get("Supplemental Reserve") is not None:
                        storage_totals[storage_num]["Supplemental Reserve Revenue ($)"] = 0
                    storage_totals[storage_num]["Total Revenue ($)"] = 0

                # Safe helpers (optional)
                c = lambda k: storage_dict.get(k, {}).get("values", [])
                charge_energy = sum(c('p_charge')) * time_factor
                discharge_energy = sum(c('p_discharge')) * time_factor
                storage_totals[storage_num]["Total charge (MWh)"] +=  charge_energy
                storage_totals[storage_num]["Total discharge (MWh)"] += discharge_energy
                storage_totals[storage_num]["Approx. Throughput (MWh)"] += discharge_energy + charge_energy
                sto_operational_cost = sum(c('operational_cost'))
                storage_totals[storage_num]["Cost ($)"] += sto_operational_cost

                sto_energy_rev = sum(c('energy_revenue'))
                storage_totals[storage_num]["Energy Revenue ($)"] += sto_energy_rev 
                daily_sto_rev = sto_energy_rev

                if config["Regulation Up"] is not None or config["Regulation Down"] is not None:
                    sto_reg_rev_daily = sum(c('regulation_up_revenue')) + sum(c('regulation_down_revenue'))
                    storage_totals[storage_num]["Regulation Revenue ($)"] += sto_reg_rev_daily
                    daily_sto_rev += sto_reg_rev_daily

                if config["Spinning Reserve"] is not None:
                    sto_spin_rev_daily = sum(c('spinning_reserve_revenue'))
                    storage_totals[storage_num]["Spinning Reserve Revenue ($)"] += sto_spin_rev_daily
                    daily_sto_rev += sto_spin_rev_daily

                if config["NonSpinning Reserve"] is not None:
                    sto_nspin_rev_daily = sum(c('non_spinning_reserve_revenue'))
                    storage_totals[storage_num]["Non-Spinning Reserve Revenue ($)"] += sto_nspin_rev_daily
                    daily_sto_rev += sto_nspin_rev_daily

                if config["Supplemental Reserve"] is not None:
                    sto_supp_rev_daily = sum(c('supplemental_reserve_revenue'))
                    storage_totals[storage_num]["Supplemental Reserve Revenue ($)"] += sto_supp_rev_daily
                    daily_sto_rev += sto_supp_rev_daily

                storage_totals[storage_num]["Total Revenue ($)"] += daily_sto_rev

                summary_row["Total Storage Discharge (MWh)"] += discharge_energy
                summary_row["Total Storage Charge (MWh)"] += charge_energy
                summary_row["Storage Cost ($)"] += sto_operational_cost
                summary_row["Total Cost ($)"] += sto_operational_cost

            summary_row["Cost per MWh ($)"] = summary_row["Total Cost ($)"] / summary_row["Total Demand (MWh)"]
            daily_summary_rows.append(summary_row)
        
        df_daily_summary = pd.DataFrame(daily_summary_rows)
        df_thermal = pd.DataFrame.from_dict(generator_totals, orient="index")
        df_ren = pd.DataFrame.from_dict(renewable_totals, orient="index")
        df_storage = pd.DataFrame.from_dict(storage_totals, orient="index")
        df_congestion = pd.DataFrame(congestion_totals)
        df_contingency = pd.DataFrame(contingency_totals)
        if not df_contingency.empty:
            dt = pd.to_datetime(
                    df_contingency["Date"].astype(str) + " " + df_contingency["Time"],
                    format="%Y-%m-%d %H:%M"
                )
            df_contingency = df_contingency.loc[dt.sort_values().index]

        with pd.ExcelWriter(os.path.join(output_directory, "simulation_summary.xlsx"), engine="openpyxl") as writer:
            df_daily_summary.to_excel(writer, sheet_name="daily_summary", index=False)
            df_thermal.to_excel(writer, sheet_name="Thermals", index=False)
            df_ren.to_excel(writer, sheet_name="Renewables", index=False)
            df_storage.to_excel(writer, sheet_name="Storage", index=False)
            df_congestion.to_excel(writer, sheet_name="High Line Loadings", index=False)
            df_contingency.to_excel(writer, sheet_name="Contingencies", index=False)
            # Enable header text wrapping for all sheets
            # Format all sheets
            for sheet_name, df in [
                ("daily_summary", df_daily_summary),
                ("Thermals", df_thermal),
                ("Renewables", df_ren),
                ("Storage", df_storage),
                ("High Line Loadings", df_congestion),
                ("Contingencies", df_contingency),
            ]:
                ws = writer.sheets[sheet_name]

                # ---- 1. Wrap header text (vertical expansion) ----
                header_row = 1
                for cell in ws[header_row]:
                    cell.alignment = cell.alignment.copy(wrap_text=True)

                ws.row_dimensions[header_row].height = None  # Let Excel auto-adjust height