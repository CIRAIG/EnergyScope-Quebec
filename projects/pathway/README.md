# Adaptation of EnergyScope Pathway to the Québec context

## Usage

The recommended way to run the model is `run_pathway()` in `shared/utils.py`. See `docs/tutorial_pathway.ipynb` for a full walkthrough: basic runs, reading results, plotting, the CO2 budget option, and how to switch between perfect foresight and myopic (rolling horizon) optimisation with `N_year_opti`.

`src/run_main.py` also runs the model directly if you prefer editing a script over calling a function.

## Structure

    ├── docs/                               # Documentation and tutorial notebook
    │   └── tutorial_pathway.ipynb          # Walkthrough of run_pathway() usage
    ├── model/                              # Pathway-specific model and data files
    │   ├── EXTRA_INFOS.dat                 # Phase definitions, time parameters, and pathway-level sets
    │   ├── fix.mod                         # Generated at each time window to fix variables for the next window
    │   ├── PES_data_decom_allowed_2020.dat # decom_allowed parameter for all technologies and phases
    │   ├── PES_data_pathway.dat            # Pathway-specific data
    │   ├── PES_data_remaining.dat          # remaining_years parameter (all phases incl. 2015_2020)
    │   ├── PES_data_remaining_wnd.dat      # remaining_years parameter (window phases only)
    │   ├── PES_data_set_AGE_2020.dat       # AGE set definition for all technologies and phases
    │   ├── PES_data_years_active.dat       # years_active parameter (used in CRF formulation, currently inactive)
    │   ├── PES_main.mod                    # Pathway model constraints
    │   ├── PES_obj_pathway.mod             # Objective function definitions
    │   ├── PES_scenarios.mod               # Scenario parameters
    │   ├── PES_seq_opti.dat                # Control file used during sequential optimisation
    │   └── PES_store_variables.mod         # Variables stored to pass state between time windows
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
Finished (26-08-2026)

This branch implements two separate interest rates, defined per year in `model/PES_data_pathway.dat` (`SDR[y]` and `i_hurdle[y,i]`). The social discount rate (SDR) is used for actualisation, it brings a phase's cost back to its present value so that costs from different years can be compared. The hurdle rate (i_hurdle) is used for annualisation, through the capital recovery factor `tau` (defined in `shared/model/QC_es_main.mod`), which spreads a lump sum investment into equivalent yearly payments over a technology's lifetime, as if it were financed with a loan at that rate.

`PES_main.mod` computes the investment cost of a phase two ways. `C_inv_phase` is the lump sum cost of new installations in that phase, discounted with the SDR only, and this is the one actually used in the objective (`C_tot_capex`, `TotalTransitionCost`). Because it is a lump sum, a technology installed close to the end of the transition horizon is paid for in full even though part of its lifetime falls outside that horizon, so the salvage value (`C_inv_return`) must be subtracted to credit back that unused part, otherwise the cost is overstated. `C_inv_phase_CRF` is an alternative that annualises each installation's cost with the hurdle rate CRF spread over the years it stays active, still discounted with the SDR, so it naturally only counts years actually used and does not need a salvage correction. It is not used in the objective, only kept for reporting and to analyse cost recovery under a hurdle rate (see `src/plot_results.py`).

A few optional constraints were added during this work. They are not needed for a default run, but are available for specific scenarios. They are labelled S4 to S7 in `model/PES_data_pathway.dat` and `model/PES_scenarios.mod`, so search for those tags to find them.

S4 and S5 limit the change rate (how fast a technology's usage can grow or shrink between two phases) and the share of the total investment a single phase can represent. They keep the transition realistic but can make myopic optimisation infeasible.

S6 limits the amount of CO2 that can be captured and stored.

S7 increases the public mobility share for short distances and slightly reduces the aviation share. If the public mobility share is increased, the schoolbus_limit_1 and schoolbus_limit_2 constraints in `PES_scenarios.mod` (also labelled S7) must be reactivated too, otherwise schoolbus technology use grows unrealistically since its share is tied to the public mobility share. Both blocks are currently commented out.