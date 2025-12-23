# Input Data Structure

QuESt PCM reads system input data from CSV files. To ensure the inputs are parsed correctly, the data directory must follow a specific structure, shown below. Click the options to see details on how to populate each CSV file. The file organization is largely based on the RTS-GMLC input data format (see the [RTS_GMLC](https://github.com/GridMod/RTS-GMLC/) repository for details). 

- System_Name/
    - [bus.csv](#bus)
    - [branch.csv](#branch)
    - [gen.csv](#gen)
    - [penalites.csv](#penalties)
    - [load_timeseries/](#load_timeseries)
        - load_timeseries_DA.csv
        - load_timeseries_RT.csv
    - [renewables_timeseries/](#ren_timeseries)
        - renewables_timeseries_DA.csv
        - renewables_timeseries_RT.csv
    - [reserves/](#reserves)
        - [DA_reserves_fixed_percentage.csv](#DA_reserve_default)
        - [RT_reserves_fixed_percentage.csv](#RT_reserve_default)
        - [reserve_deployment.csv](#reserves_deployment)
        - [reserves_timeseries/](#reserves_timeseries)
            - ReserveName_timeseries_DA.csv
            - ReserveName_timeseries_RT.csv
    - [storage/](#storage)
        - [generic_storage.csv](#generic_storage)
        - [battery_storage.csv](#battery_storage)
        - [pumped_hydro.csv](#pumped_hydro)
    

## `bus.csv`
<a id="bus"></a>

| Column       | Description                       |
|--------------|-----------------------------------|
| Bus ID       | Numeric Bus ID                    |
| Bus Name     | Bus name               |
| BaseKV       | Bus voltage rating                |
| Bus Type     | Bus control type                  |
| MW Load      | Real power demand                 |
| MVAR Load    | Reactive power demand             |
| Area         | Bus region                    |

[Back to Top](#top)
## `branch.csv`
<a id="branch"></a>

| Column       | Description                           |
|--------------|---------------------------------------|
| Line ID           | Unique branch ID                      |
| From Bus     | From Bus ID                           |
| To Bus       | To Bus ID                             |
| R            | Branch resistance p.u.                |
| X            | Branch reactance p.u.                 |
| B            | Branch line charging susceptance p.u. |
| Cont Rating  | Continuous MW flow limit              |
| LTE Rating   | Long term MW flow limit               |
| STE Rating   | Short term MW flow limit              |
| Tr Ratio     | Transformer winding ratio             |

[Back to Top](#top)
## `gen.csv`
<a id="gen"></a>

| Column                   | Description                                                      |
|--------------------------|------------------------------------------------------------------|
| GEN UID                  | Unique generator ID   |
| Bus ID                   | Connection Bus ID                                                |
| Gen ID                   | Index of generator units at each bus                             |                                   |
| Unit Type                | Unit type                                                        |
| Unit Category               | Category of unit within unit type  
| Fuel                     | Unit fuel                                                        |
| Initial Power MW                  | Power generation at simulation start    |
| Initital status Hr                 | Initial on/off duration before simulation start (positive = on, negative = off)
| PMax MW                  | Maximum real power injection (Unit Capacity)                     |
| PMin MW                  | Minimum real power injection (Unit minimum stable level)         |
| QMax MVAR                | Maximum reactive power injection                                 |
| QMin MVAR                | Minimum reactive power injection                                 |
| Min Down Time Hr         | Minimum off time required before unit restart                    |
| Min Up Time Hr           | Minimum on time required before unit shutdown                    |
| Ramp Rate MW/Min         | Maximum ramp up and ramp down rate                               |
| Start Time Cold Hr       | Time since shutdown after which a cold start is required |
| Start Time Hot Hr        | Time since shutdown after which a hot start is required |
| Start Time Warm Hr       | Transition time between hot and cold statuses after a shutdown |
| Start Heat Cold MMBTU     | Heat required to startup from cold in million BTU per startup   |
| Start Heat Hot MMBTU      | Heat required to startup from hot in million BTU per startup    |
| Fuel Price $/MMBTU       | Fuel price in Dollars per million BTU                            |
| Output_pct_0             | Output point 0 on heat rate curve as a percentage of PMax        |
| Output_pct_1             | Output point 1 on heat rate curve as a percentage of PMax        |
| Output_pct_2             | Output point 2 on heat rate curve as a percentage of PMax        |
| Output_pct_3             | Output point 3 on heat rate curve as a percentage of PMax        |
| HR_Avg_0                 | Average heat rate between 0 and output point 0 in BTU/kWh        |
| HR_Incr_1                | Incremental heat rate between output points 0 and 1 in BTU/kWh   |
| HR_Incr_2                | Incremental heat rate between output points 1 and 2 in BTU/kWh   |
| HR_Incr_3                | Incremental heat rate between output points 2 and 3 (PMax) in BTU/kWh           |
|Fast start | Boolean flag indicating if a unit can start in RT-SCED and provide non-spinning reserves |
|AGC capable| Boolean flag indicating if a unit can provide regulation reserve |
|Reg Offer $/MW/hr| Offer price per MW of regulation up or down capacity, per hour|
|Pmax AGC MW| Upper limit for providing regulation |
|Pmin AGC MW| Lower limit for providing regulation |
|Spin offer MW| Maximum capacity offered for spinning reserve. |
|Spin Offer $/MW/hr| Offer price per MW of spinning reserve, per hour|
|NonSpin offer MW| Maximum capacity offered for non-spinning reserve. |
|NonSpin Offer $/MW/hr| Offer price per MW of non-spinning reserve, per hour|
|Supp offer MW| Maximum capacity offered for supplemental reserve. |
|Supp Offer $/MW/hr| Offer price per MW of supplemental reserve, per hour|

[Back to Top](#top)
## `penalties.csv`
<a id="penalties"></a>

This CSV file specifies the penalty prices applied to system load curtailment and ancillary service shortfalls. The load curtailment penalty must always be set higher than all other penalties. In addition, a penalty for contingency transmission line flow violations must also be provided.

[Back to Top](#top)
## `load_timeseries/`
<a id="load_timeseries"></a>

This folder contains two CSV files.
`load_timeseries_DA.csv` provides the forecasted day-ahead power demand, while `load_timeseries_RT.csv`contains the actual power demand at 5-minute intervals. Demand values are organized by columns, and users may choose one of two formats:
1. Area-based: Columns correspond to region names listed in the Area column of [bus.csv](#bus)
2. Nodal-based: Columns correspond to individual Bus IDs from [bus.csv](#bus)

In the configuration YAML file, set the `load_timeseries_aggregation_level` parameter to either `area` or `node` to match the chosen format.

[Back to Top](#top)
## `renewables_timeseries/`
<a id="load_timeseries"></a>

This folder contains two CSV files.
`renewables_timeseries_DA.csv` provides the forecasted day-ahead capacity of renewable energy resources (RER), while `renewables_timeseries_RT.csv` contains the actual avalable RER capacitites. Data must be provided for all generators whose `Unit Type` in [gen.csv](#gen) is listed under `renewable_types` or `fixed_renewable_types` in the YAML configuration. Each CSV is organized by columns, where each column corresponds to a generator and is labeled using its `Gen UID`.

[Back to Top](#top)
## `reserves/`
<a id="reserves"></a>
Currently, several reserve products can be included in QuEST PCM: `System reserve`, `Regulation Up`, `Regulation Down`, `Spinning Reserve`, `NonSpinning Reserve`, `Supplemental Reserve`, `
Flexible Ramp Up`, and `Flexible Ramp Down`. For these reserves, within the configuration YAML file, users are prompted to select reserve activation options as follows:
1. `None`: The reserve is not active.
2. `Fixed`: Fixed value of reserve requirement dervied from [DA_reserves_fixed_percentage.csv](#DA_reserve_default) and [RT_reserves_fixed_percentage.csv](#RT_reserve_default.csv) are used.
3. `Percentage`: User provided percentage of demand from [DA_reserves_fixed_percentage.csv](#DA_reserve_default) and [RT_reserves_fixed_percentage.csv](#RT_reserve_default.csv) are assigned as reserve requirement.
4. `Timeseries`: User provides timeseries reserve requirements in the [reserves_timeseries](#reserves_timeseries) folder.


### DA_reserves_fixed_percentage.csv
<a id="DA_reserve_default"></a>

| Column                   | Description                                                      |
|--------------------------|------------------------------------------------------------------|
| Reserve Type                  | Type of reserve. Must be among: `System reserve`, `Regulation Up`, `Regulation Down`, `Spinning Reserve`, `NonSpinning Reserve`, `Supplemental Reserve`, `Flexible Ramp Up`, and `Flexible Ramp Down`.   |
| System Fixed Requirement MW                 | Constant system wide requirement for corresponding reserve type. Activated if `fixed` option is selected for this reserve type in the configuration file                                                |
| System Percentage Requirement                 | Required reserve as a percentage of total system demand. Activated when `percentage` option is selected in the configuration file|
| Area Fixed Requirement MW                 | Constant area wide requirement for corresponding reserve type. Activated if `fixed` option is selected for this reserve type in the configuration file                                                |
| Area Percentage Requirement                 | Required reserve as a percentage of regional system demand. Activated when `percentage` option is selected in the configuration file|
| Eligible Areas                 | Specifies the areas where fixed or percentage reserve requirements should be applied |
| Remarks| Brief description of the reserve |

### RT_reserves_fixed_percentage.csv
<a id="RT_reserve_default"></a>

This CSV file is formatted the exact same way as the [DA_reserves_fixed_percentage.csv](#DA_reserves_default) file. One key distinction is that the `System Reserve` is not allocated in the real-time economic dispatch.

### reserve_deployment.csv
<a id="reserves_deployment"></a>

QuESt PCM also allows users to model reserve deployments and evaluate their impacts on generator revenues, storage revenues, and storage state of charge. This CSV file is used to specify time-series values for reserve deployments.

For regulation up and regulation down reserves, users must provide the fraction of the procured regulation capacity that was actually deployed in real time. For spinning, non-spinning, and supplemental reserves, users must specify the duration (in minutes) for which the reserves were actually deployed. Within this [test CSV file](../Data/5bus/reserves/reserve_deployment.csv), we have included reserve deployment data derived from CAISO and PJM markets for regulation up, down, and spinning reserves.

### reserves_timeseries/
<a id="reserves_timeseries"></a>

This folder contains timeseries CSV files for reserve requirements. For any reserve type configured with the `Timeseries` option in the YAML file, QuESt PCM reads the corresponding timeseries CSV from this folder.

Each reserve timeseries file must follow the naming convention:

* Reserve Type_timeseries_DA.csv for day-ahead reserves, where reserve type must be among: `System reserve`, `Regulation Up`, `Regulation Down`, `Spinning Reserve`, `NonSpinning Reserve`, `Supplemental Reserve`, `Flexible Ramp Up`, and `Flexible Ramp Down`.   

* Reserve Type_timeseries_RT.csv for real-time reserves

Within each CSV, reserve requirements are specified by columns. System-wide reserves must use the column name `System`. Area-specific reserves must use column names in the form `Area <AreaName>`, where `<AreaName>` matches the area name defined in [bus.csv](#bus).

[Back to Top](#top)
## storage/
<a id="storage"></a>

Currently, QuESt PCM supports three storage system models: generic, battery, and pumped hydro. The generic storage model represents a conventional storage system that does not participate in ancillary service markets. In contrast, the battery and pumped hydro models incorporate technology-specific operational constraints and explicitly model participation in ancillary service markets.

Details on how to populate the input data for each of these three storage models are provided below.

### generic_storage.csv
<a id="generic_storage"></a>

| Column                      | Description                                                                                    |
| --------------------------- | ---------------------------------------------------------------------------------------------- |
| Storage ID                  | Unique identifier for the storage unit.                                                        |
| Bus ID                      | Identifier of the bus to which the storage unit is connected.                                  |
| In Service                  | Boolean flag indicating whether the storage unit is available for operation.                   |
| Charge Rating MW            | Maximum charging power of the storage unit (MW).                                               |
| Min Charge Rating MW        | Minimum charging power when the unit is charging (MW).                                         |
| Discharge Rating MW         | Maximum discharging power of the storage unit (MW).                                            |
| Min Discharge Rating MW     | Minimum discharging power when the unit is discharging (MW).                                   |
| Rated Capacity MWh          | Total energy storage capacity of the unit (MWh).                                               |
| Charging Efficiency         | Efficiency of converting electrical energy into stored energy.                                 |
| Discharging Efficiency      | Efficiency of converting stored energy into electrical output.                                 |
| Charging Cost $/MWh         | Marginal cost incurred when charging the storage unit.                                         |
| Discharging Cost $/MWh      | Marginal cost incurred when discharging the storage unit.                                      |
| Initial SoC                 | State of charge at the beginning of the simulation, expressed as a fraction of rated capacity. |
| Minimum SoC                 | Minimum allowable state of charge during operation.                                            |
| Charging RampUP MW/min      | Maximum rate at which charging power can increase (MW/min).                                    |
| Charging RampDOWN MW/min    | Maximum rate at which charging power can decrease (MW/min).                                    |
| Discharging RampUP MW/min   | Maximum rate at which discharging power can increase (MW/min).                                 |
| Discharging RampDOWN MW/min | Maximum rate at which discharging power can decrease (MW/min).                                 |


### battery_storage.csv
<a id="battery_storage"></a>

| Column                         | Description                                                                                    |
| ------------------------------ | ---------------------------------------------------------------------------------------------- |
| Storage ID                     | Unique identifier for the storage unit.                                                        |
| Bus ID                         | Identifier of the bus to which the storage unit is connected.                                  |
| In Service                     | Boolean flag indicating whether the storage unit is available for operation.                   |
| Rated Power MW                 | Maximum charging or discharging power capacity of the storage unit (MW).                       |
| Rated Capacity MWh             | Total energy storage capacity of the unit (MWh).                                               |
| Capacity Retention Rate        | Fraction of stored energy retained at end-of-hour, accounting for self-discharge.             |
| Conversion Efficiency          | Round-trip efficiency for converting stored energy to electrical output.                       |
| Battery Discharging Cost $/MWh | Marginal cost incurred when discharging energy from the storage unit.                          |
| Initial SoC                    | State of charge at the beginning of the simulation, expressed as a fraction of rated capacity. |
| Minimum SoC                    | Minimum allowable state of charge during operation.                                            |
| Maximum SoC                    | Maximum allowable state of charge during operation.                                            |

### pumped_hydro.csv
<a id="pumped_hydro"></a>

| Column                                  | Description                                                                                                          |
| --------------------------------------- | -------------------------------------------------------------------------------------------------------------------- |
| Storage ID                              | Unique identifier for the pumped hydro storage unit.                                                                 |
| Bus ID                                  | Identifier of the bus to which the storage unit is connected.                                                        |
| In Service                              | Boolean flag indicating whether the storage unit is available for operation.                                         |
| Supports HSC                            | Boolean flag indicating whether the unit supports hydraulic short-circuit operation (HSC).                                |
| Units                                   | Number of identical pumped hydro units.                                                    |
| Pmax Generator MW                       | Maximum generator (discharge) power output (MW).                                                                     |
| Pmin Generator MW                       | Minimum generator (discharge) power output (MW).                                                                     |
| Prated Pump MW                          | Rated pumping (charging) power (MW).                                                                                 |
| Max Gen Discharge Flow-Rate m³/s        | Maximum water flow rate during generation (m³/s).                                                                    |
| Min Gen Discharge Flow-Rate m³/s        | Minimum water flow rate during generation (m³/s).                                                                    |
| Max Pumping Flow-Rate m³/s              | Maximum water flow rate during pumping (m³/s).                                                                       |
| Power-Flow Conversion Coefficient MW/m³ | Conversion factor between water flow rate and electrical power output.                                               |
| Generator Efficiency                    | Efficiency of converting hydraulic energy to electrical energy during generation.                                    |
| Pump Efficiency                         | Efficiency of converting electrical energy to hydraulic energy during pumping.                                       |
| Generator Startup Cost $                | Startup cost incurred when initiating generation mode.                                                               |
| Pump Startup Cost $                     | Startup cost incurred when initiating pumping mode.                                                                  |
| Max Upper Reservoir Volume m³           | Maximum storage volume of the upper reservoir.                                                                       |
| Initial SoC                             | Initial state of charge (reservoir level) at the start of the simulation, expressed as a fraction of maximum volume. |
| Minimum SoC                             | Minimum allowable state of charge during operation.                                                                  |
| Maximum SoC                             | Maximum allowable state of charge during operation.                                                                  |

[Back to Top](#top)