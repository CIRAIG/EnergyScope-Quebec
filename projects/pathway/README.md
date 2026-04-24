# Adaptation of EnergyScope Pathway to the Québec context

## Structure

    ├──ES_Transition_QC_2           # Fusion of Québec Snapshot model and Pathway Belgium model
    │   ├── EUD
    │   │   ├── out_eud.dat         # End uses demand in matrix form for all years
    │   │   ├── QC_eud_2020.dat     # End uses demand in line for year 2020
    │   │   ├── QC_eud_2025.dat     # End uses demand in line for year 2025
    │   │   ├── QC_eud_2030.dat     # End uses demand in line for year 2030
    │   │   ├── QC_eud_2035.dat     # End uses demand in line for year 2035
    │   │   ├── QC_eud_2040.dat     # End uses demand in line for year 2040
    │   │   ├── QC_eud_2045.dat     # End uses demand in line for year 2045
    │   │   ├── QC_eud_2050.dat     # End uses demand in line for year 2050
    │   ├── Techs
    │   │   ├── out_techs_zero.dat  # Definition of the technologies paraeters for all years in matrix form (0 instead of small values (1e-7))
    │   │   ├── out_techs.dat       # Definition of the technologies parameters for all years in matrix form
    │   │   ├── QC_techs_2020.dat   # Definition of the technologies parameters for year 2020 in line 
    │   │   ├── QC_techs_2025.dat   # Definition of the technologies parameters for year 2025 in line
    │   │   ├── QC_techs_2030.dat   # Definition of the technologies parameters for year 2030 in line
    │   │   ├── QC_techs_2035.dat   # Definition of the technologies parameters for year 2035 in line
    │   │   ├── QC_techs_2040.dat   # Definition of the technologies parameters for year 2040 in line
    │   │   ├── QC_techs_2045.dat   # Definition of the technologies parameters for year 2045 in line
    │   │   ├── QC_techs_2050.dat   # Definition of the technologies parameters for year 2050 in line
    │   ├── fix.mod                         # file created at each time window end to fixe data for next time window
    │   ├── log.txt                         # logs
    │   ├── PES_data_decom_allowed_2025.dat # Definition of parameter decom_allowed for all technologies
    │   ├── PES_data_remaining_wnd.dat      # Definition of parameter remaining_years for all technologies and phase
    │   ├── PES_data_remaining.dat          # Same with phase 2015_2020 also
    │   ├── PES_data_set_AGE_2025.dat       # Definition of set AGE for all technologies and phases
    │   ├── PES_initialise_2020.mod         # Initialisation of the first year (2020)
    │   ├── PES_seq_opti.dat                # File used during the optimisation 
    │   ├── PES_store_variable.mod          # Variable stored in order to be transmitted between each time windows
    │   ├── QC_data.dat                     # Québec set definition
    │   ├── QC_es_main.mod                  # Model definition (constraints)
    │   ├── QC_mob_params.dat               # Mobility share parameters definition
    │   ├── QC_mob_techs_dist_B2D.dat       # Mobility layers_in_out parameter definition for all years and all mobility technologies
    │   ├── QC_techs_B2D.dat                # Definition of all parameters for all years and technologies
    ├── ESMY                        # data and model files of the pathway and hourly version of EnergyScope (Belgium data)
    │   ├── STEP_1_TD_selection     # selection of typical days (going from monthly to hourly time resolution)
    │   └── STEP_2_Pathway_Model    # pathway model (going from snapshot to pathway)
    ├── pylib                       # ampl functions
    ├── src                         # script to run energyscope
    └── README.md

## Main author
- [**Mattia Zimmermann**](mailto:mattia.zimmermann@epfl.ch)

## Supervisors
- [**Jonas Schnidrig**](mailto:jonas.schnidrig@epfl.ch)
- [**Matthieu Souttre**](mailto:matthieu.souttre@polymtl.ca)

## Project status
Ongoing