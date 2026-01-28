<a id="top"></a>

<div style="text-align: center;">
    <img src="Images/pcm_logo.png" width = 600 alt="Quest_Logo_RGB" />
</div>

# **QuESt PCM**: A Production Cost Modeling Tool with High-Fidelity Models of Energy Storage Systems

Current release version: 1.0.0

## Table of Contents
- [Introduction](#intro)
- [Key Features of QuESt PCM](#key-features)
- [Getting Started](#getting-started)
- [Running QuESt PCM](#running-pcm)
- [Example Simulation](#example_simulation)
- [Acknowledgement](#acknowledgement)
- [Contact Details](#contact_details)

## Introduction 
<a id="intro"></a>

Production cost models (PCM) are computational tools that simulate power system operations by optimizing the commitment and dispatch of generation resources to meet demand at least cost, while respecting technical and reliability constraints. QuESt PCM is an open-source power system production cost modeling tool designed for high-fidelity representation of energy storage systems (ESS). Built in Python, it uses the Pyomo optimization interface to formulate technology-specific storage models and to capture diverse storage operational constraints. The tool also models market participation capabilities of storage systems, helping assess their impacts on day-ahead and real-time price signals. Python wrappers allow seamless simulation of market operations, and [EGRET](https://github.com/grid-parity-exchange/Egret/tree/main) serves as the optimization engine for security-constrained unit commitment and economic dispatch. This tool is part of [QuESt 2.0](https://github.com/sandialabs/snl-quest): Open-source Platform for Energy Storage Analytics. Below is a high-level overview of the QuESt PCM tool.
<div style="text-align: center;">
<img src = "Images/QuEST_PCM_IO.png" alt="overview" />
</div>

[Back to Top](#top)
## Key Features of QuESt PCM
<a id="Key-features"></a>
Key features of the QuESt PCM tool include:

- **Cost-Optimal Dispatch and Commitment:** Coordinates day-ahead and real-time simulations to determine least-cost generation dispatch while respecting technical and reliability constraints. The tool ensures proper initialization and coupling of intertemporal variables, maintaining consistency between day-ahead and real-time operations. Optimization problems are solved using EGRET, enabling accurate modeling of multi-period dispatch and commitment decisions.

- **High-Fidelity Energy Storage Modeling:** Accurately represents a broad range of energy storage technologies, capturing technology-specific operational constraints, charge/discharge behavior, efficiency characteristics, and degradation effects. Examples include cycling and aging characteristics of battery storage, as well as generator and pump dynamics of pumped hydro storage. The tool also evaluates the impact of storage operation on system flexibility, reliability, and cost.

- **Market Participation Simulation:** Models storage participation in both day-ahead and real-time markets to assess revenue potential and influence on market price signals. The tool addresses key challenges in integrating storage systems into production cost models, including ancillary service state-of-charge constraints, and incorporates rolling-horizon coordination to align day-ahead and real-time storage schedules.

- **Flexible Scenario Analysis:** Enables exploration of multiple operational and market scenarios to evaluate sensitivities under varying conditions. Users can configure real-time market clearing frequencies, lookahead horizons, and flexible allocation of ancillary services, including regulation, spinning, non-spinning, and supplemental reserves. Storage participation levels in these services can also be customized.

- **Open-Source and Extensible:** Built in Python with transparent, modifiable code for research, teaching, and practical power system studies.

[Back to Top](#top)
## Getting started
<a id="getting-started"></a>
### Installing Python
1. Installers can be found at: https://www.python.org/downloads/release/python-31212/
2. Make sure to check the box "Add Python to PATH" at the bottom of the installer prompt.

### Installing Git
- Visit [git-scm.com](https://git-scm.com/) to download Git for your operating system.
- Follow the installation instructions provided on the website.

### Solver Installation

Ensure an optimization solver is installed on your machine. For best performance, use a commercial solver such as Gurobi and Cplex. Solvers to consider include:

**Commercial Solvers**
- [Gurobi](<https://www.gurobi.com/>)
- [Cplex](<https://www.ibm.com/products/ilog-cplex-optimization-studio>)

**Open-source Solvers**
- [Cbc](<https://github.com/coin-or/Cbc>)
- [HiGHs](<https://highs.dev/#top>)

### Setting Up a Virtual Environment
1. Install `virtualenv` (if not already installed):
    ```bash
    python -m pip install virtualenv
    ```

2. Create a virtual environment (named `venv`):
    ```bash
    python -m virtualenv venv
    ```

3. Activate the virtual environment:
   - On Windows:
     ```bash
     .\venv\Scripts\activate
     ```
   - On macOS/Linux:
     ```
     source <env_name>/bin/activate
     ```

### Cloning the Repository and Installing Dependencies
1. Clone the repository:
    ```bash
    git clone <repository_url>
    ```
   Replace `<repository_url>` with the URL of the QuESt PCM repository.

2. Navigate to the QuESt PCM Directory:
    ```bash
    cd path/to/quest_PCM
    ```
   Replace `path/to/quest_PCM` with the name of the directory where QuESt PCM was cloned.

3. Install Dependencies:
    ```bash
    python -m pip install -r requirements.txt
    ```
[Back to Top](#top)

## Running QuESt PCM
<a id="running-pcm"></a>

### Setup the Input CSV Files

The network, generator, reserve, and storage data are all input as .csv files. They must be present within the [Data](Data/) directory. Each file must follow the specific format required by QuESt PCM. For detailed instructions on how to populate these files, see the [input_readme](Data/data_readme.md).

### Configure the Input File

Before running the simulation, configure the input yaml file in [Config](config/) directory with the specific simulation parameters. Open the file in a text editor and adjust the parameters according to your requirements. The guidelines for setting up the config files are present in [config_readme](config/config_readme.md).
### Run the Program

Use the example script to run the simulation. Before running, update the main_data_path and yaml_path variables in the script to point to your desired system. Then, with your virtual environment activated, execute the script from the command line as follows:
```
python example_script.py
```
### Analyze the Results

Simulation results are stored in the [Results](Results/) directory. Separate timestamp folders are generated for each simulation run. Some key results from each simulation run include: system generation dispatch, operation costs, ancillary service allocations, and storage dispatch characteristics. Detailed decription of QuESt PCM outputs and file organization are present in the [output_readme](Results/output_readme.md).

[Back to Top](#top)
## Example Simulation
<a id="example_simulation"></a>
Two test cases are included with the initial release of QuESt PCM. One test case includes a purely synthetic 5-bus system derived from [Prescient](https://github.com/grid-parity-exchange/Prescient/tree/main) examples. Users can use this system for quick tests. Another test case includes the IEEE [RTS-GMLC](https://github.com/GridMod/RTS-GMLC) synthetic grid, which is a publicly available test system that is derived from IEEE RTS-96 test system. Figure 1 displays the nodal model of the RTS-GMLC test case included within the tool. 

<img src = "Images/rts_gmlc.png" width="500" alt="Results" />

**Figure 1:** IEEE RTS-GMLC Test Case nodal model

Some outputs of Quest PCM for a 5-day RTS-GMLC simulation (included in the [config](config/GMLC_config.yaml) file) are illustrated as follows:

### System Operation 
 QuESt PCM provides detailed results for system operation, including chronological unit commitment and economic dispatch decisions, nodal power flows, and generator production levels. While the full set of detailed results is available to users through summary Excel files and structured .json outputs, QuESt PCM also offers system-level operational overview plots for visualization and analysis. For example, Figure 2 illustrates system dispatch, generation costs, and interactive locational marginal price (LMP) plots obtained from the RTS-GMLC simulation.

<img src = "Images/dispatch.png" width="386" alt="Results" />  <img src = "Images/cost.png" width="409" alt="Results" /> 

<img src = "Images/LMP_image.png" width="800" alt="Results" />

**Figure 2:** 5-day dispatch, costs, and LMPs of the IEEE RTS-GMLC test case.

### Ancillary Services
QuESt PCM also emphasizes on modeling the system ancillary services. It enables users to analyze the revenues earned by generators and storage resources from ancillary service participation through summary Excel sheets and visual plots. Figure 3 presents example plots of real-time ancillary service market-clearing results produced by QuESt PCM for the RTS-GMLC system, with storage systems also contributing to operational reserves.

<img src = "Images/regup_plot.png" width="397" alt="Results" />  <img src = "Images/regdown_plot.png" width="397" alt="Results" /> 

<img src = "Images/as_clearing_prices_plot.png" width="800" alt="Results" />

**Figure 3:** Ancillary service market clearing results for RTS-GMLC.

### Storage Participation in Energy and Ancillary Service Markets 
QuESt PCM provides extensive modeling and visualization capabilities for energy storage systems within production cost models. Currently, the tool supports three distinct storage models: generic, battery, and pumped hydro. Each storage system is equipped with its own set of operational constraints. Figure 4 illustrates the operation of a generic 50 MW, 150 MWh energy storage system with charging and discharging-only capability over a five-day simulation of the RTS-GMLC system. Figure 5 presents a comparison of the dispatch characteristics of battery energy storage (BESS) and pumped hydro storage (PHS) units of equivalent capacity, replacing the generic storage model and participating in ancillary service markets.

<table>
  <tr>
    <td>
      <img src="Images/storage_dispatch_plot.png" width="395" alt="Dispatch">
    </td>
    <td valign="middle">
      <img src="Images/storage_SoC_plot.png" width="395" alt="State of Charge">
    </td>
  </tr>
</table>

**Figure 4:** Storage dispatch and state-of-charge in RTS-GMLC.

<img src = "Images/BESS_dispatch_plot.png" width="395" alt="Results" />  <img src = "Images/PHS_dispatch_plot.png" width="395" alt="Results" /> 

**Figure 5:** Battery and pumped hydro storage dispatch in RTS-GMLC with ancillary service participation.

### Detailed Storage Tech-Specific Modeling

QuESt PCM also provides detailed modeling of technology-specific storage operation. In the current release, tech-specific models for two storage technologies are supported: batteries and pumped hydro. For batteries, QuESt PCM evaluates potential degradation arising from system operation. For example, Figure 6 presents two plots showing battery degradation when participating in energy markets only versus participation in both energy and reserve markets. The degradation models used for this evaluation are based on cyclic degradation data from the [batteryarchive](https://www.batteryarchive.org/index.html). Similarly, for pumped-hydro systems, unit-level control constraints are included, such as generator and pump operation limits, flow dynamics, and reservoir interactions. Figure 7 illustrates an example visualization of pumped-hydro unit operation status from the RTS-GMLC five-day simulation.

<img src = "Images/BESS_degradation_arbitrage.png" width="397" alt="Results" />  <img src = "Images/BESS_degradation_ancillaries.png" width="397" alt="Results" /> 

**Figure 6:** Potential degradation of BESS for different cathode chemistries with charging discharging only (first figure) vs ancillary service participation (second figure).

<img src = "Images/PHS_schedules.png" width="800" alt="Results" />

**Figure 7:** Generator/Pump unit operation schedule of pumped hydro storage in RTS-GMLC.

[Back to Top](#top)
## Acknowledgment
<a id="acknowledgement"></a>
The QuESt PCM tool is developed and maintained by the [Energy Storage Analytics Group](<https://energy.sandia.gov/programs/energy-storage/analytics/>) at [Sandia National Laboratories](<https://www.sandia.gov/>). This material is based upon work supported by the **U.S. Department of Energy, Office of Electricity (OE), Energy Storage Division**.

**Project team:**
- Dilip Pandit
- Cody Newlun
- Atri Bera
- Tu Nguyen
<p>
  <img src="Images/SNL_Logo.jpg" width="260" alt="SNL"> <img src="Images/DOE_logo.jpg" width="350" alt="DOE">
</p>

[Back to Top](#top)
## Contact Details
<a id="contact_details"></a>
For reporting bugs and other issues, please use the "Issues" feature of this repository. For more information regarding the tool and collaboration opportunities, please contact project developer: Dilip Pandit (`dpandit@sandia.gov`).


