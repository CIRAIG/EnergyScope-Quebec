# Adaptation of EnergyScope Pathway to the Québec context

## Structure

    ├── model/                              # Pathway-specific model and data files
    │   ├── EXTRA_INFOS.dat                 # Phase definitions, time parameters, and pathway-level sets
    │   ├── fix.mod                         # Generated at each time window to fix variables for the next window
    │   ├── PES_data_decom_allowed_2020.dat # decom_allowed parameter for all technologies and phases
    │   ├── PES_data_remaining.dat          # remaining_years parameter (all phases incl. 2015_2020)
    │   ├── PES_data_remaining_wnd.dat      # remaining_years parameter (window phases only)
    │   ├── PES_data_set_AGE_2020.dat       # AGE set definition for all technologies and phases
    │   ├── PES_data_years_active.dat       # years_active parameter (used in CRF formulation, currently inactive)
    │   ├── PES_scenarios.mod               # Scenario parameters
    │   ├── PES_seq_opti.dat                # Control file used during sequential optimisation
    │   ├── PES_store_variables.mod         # Variables stored to pass state between time windows
    │   ├── QC_data_pathway.dat             # Pathway-specific data
    │   ├── QC_es_obj_pathway.mod           # Objective function definitions
    │   └── QC_es_pathway.mod               # Pathway model constraints
    ├── pylib/                              # Python utility library
    │   ├── ampl_object.py                  # AMPL interface and solver management
    │   ├── ampl_preprocessor.py            # Pre-processing of data files before optimisation
    │   ├── ampl_collector.py               # Post-processing: collects and formats AMPL results
    │   └── ampl_graph.py                   # Plotting functions for results visualisation
    ├── src/                                # Run scripts
    │   ├── plot_results.py                 # Script used to present results   
    │   ├── run_main.py                     # Main script to run the pathway model
    └── README.md

## Main author
- [**Mattia Zimmermann**](mailto:mattia.zimmermann@epfl.ch)

## Supervisors
- [**Jonas Schnidrig**](mailto:jonas.schnidrig@epfl.ch)
- [**Matthieu Souttre**](mailto:matthieu.souttre@polymtl.ca)

## Project status
Ongoing