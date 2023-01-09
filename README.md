# ResSim-GateFailures
Scripts to support programmatically failing gates in HEC-ResSim models (optionally in HEC-WAT)


# FIles:

`\scripts`: Contains the scripts needed to run the model.
- `Gate Control Rule with Linear Ramping.py`: Use this rule as the highest priority rule in each zone to simulate gate failures for a given gate.
- `Gate Failure SV_Init.py`: Use this state variable to load the configuration for each gate failure scenario to be modeled.

`\shared\gates`: contains example configuration files
- `config.csv`: general configuration
- `gates.csv`: list of gate failure scenarios to model

`\sdi`: contains example input files for HEC-WAT Stochastic Data Importer as the source of hydrology, repeating a series of pre-computed storms.