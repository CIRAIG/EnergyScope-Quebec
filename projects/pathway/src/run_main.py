# -*- coding: utf-8 -*-
"""
Created on Mon May 17 10:21 2021

@author: Xavier Rixhon
"""

#%% Import Python packages and paths creation
import os, sys
from pathlib import Path

import time # To print the time needed for one optimisation
import faulthandler
faulthandler.enable()

curr_dir = Path(os.path.dirname(__file__)) # .../projects/pathway/src
pth_proj = curr_dir.parent                 # .../projects/pathway
pth_repo = pth_proj.parent.parent          # .../EnergyScope-Quebec

pth_model        = os.path.join(pth_proj, 'model')               # pathway-specific files
pth_data         = os.path.join(pth_repo, 'shared', 'data')      # shared data files
pth_shared_model = os.path.join(pth_repo, 'shared', 'model')     # shared model files
pth_output_all   = os.path.join(pth_proj, 'out')

pymodPath = os.path.abspath(os.path.join(pth_proj, 'pylib'))
sys.path.insert(0, pymodPath)

#%% Linked objects

from ampl_object import AmplObject
from ampl_preprocessor import AmplPreProcessor
from ampl_collector import AmplCollector
import importlib.util as _ilu


#%% Options of this run_main.py

type_of_model = 'MO' # Define the time resolution of the model. 'TD' for hourly
                     # model and 'MO' for monthly model

gwp_budget = True # True if limiting the overall GWP of the whole transition
gwp_budget_val = 883428 # GWP budget for the whole transition [ktCO2,eq]
CO2_neutrality_2050 = False # True if setting the GWP of 2050 to carbon-
                            # neutrality
CO2_neutrality_2050_val = 0#3406.92 # Value equivalent to CO2-neutrality in 2050
                                  # [ktCO2,eq]
                                  
run_opti = True # True to run optimisation
graph = True # True to plot graphs for deterministic run

case_study = 'Case_study_name' # Give here the name of the case study for 
                      # deterministic run
expl_text = 'Case study description' # Give here explanation text to describe the
                        # case study
        
#%% Join the .dat and .mod files depending on the type of model (MO or TD).
# ! The order of the files in the list is important !

if type_of_model == 'MO':
    mod_1_path = [os.path.join(pth_shared_model,'QC_es_main.mod'),
                  os.path.join(pth_model,'PES_main.mod'),
                  os.path.join(pth_model,'PES_obj_pathway.mod'),
                  os.path.join(pth_model,'PES_store_variables.mod')]
    # QC_data.dat uses both data syntax and for/let scripts → must be loaded
    # with ampl.read() (mod_2_path) FIRST so YEARS set is defined before
    # Techs/EUT files reference it. It contains data;/model; markers.
    # PES_scenarios.mod is loaded after QC_data.dat so that YEARS is populated
    # before any indexed 'let' statements in scenarios execute.
    mod_2_path = [os.path.join(pth_model,'EXTRA_INFOS.dat'),
                  os.path.join(pth_data,'QC_data.dat'),
                  os.path.join(pth_model,'PES_scenarios.mod'),
                  os.path.join(pth_data,'EUD/out_eud.dat'),
                  os.path.join(pth_data,'Techs/out_techs.dat'),
                  os.path.join(pth_data,'Shares/out_shares.dat'),
                  os.path.join(pth_model,'PES_data_pathway.dat'),
                  os.path.join(pth_model,'PES_data_decom_allowed_2020.dat'),
                  os.path.join(pth_model,'fix.mod')]
    dat_path = [os.path.join(pth_model,'PES_data_years_active.dat')]
else:
    mod_1_path = [os.path.join(pth_model,'PESTD_model.mod'),
                  os.path.join(pth_model,'PES_store_variables.mod')]
    mod_2_path = [os.path.join(pth_model,'PESTD_initialise_2020.mod'),
                  os.path.join(pth_model,'fix.mod')]
    dat_path = [os.path.join(pth_model,'PESTD_data_all_years.dat'),
                os.path.join(pth_model,'PESTD_12TD.dat')]

dat_path += [os.path.join(pth_model,'PES_seq_opti.dat'),
             os.path.join(pth_model,'PES_data_set_AGE_2020.dat')]

dat_path_0 = dat_path + [os.path.join(pth_model,'PES_data_remaining.dat')]

dat_path += [os.path.join(pth_model,'PES_data_remaining_wnd.dat')]

#%% Options for ampl and gurobi

gurobi_options = ['predual=-1',
                'method=2',
                'crossover=0',
                'threads=0',
                'prepasses=3',
                'barconvtol=1e-6',
                'presolve=-1',
                #'BarHomogeneous=1',
                #'ScaleFlag=2',
                #'NumericFocus=2',
                'iisfind=1',
                'outlev=1',
                'mipgap=0.0005',
                ]
                
gurobi_options_str = ' '.join(gurobi_options)

ampl_options = {'show_stats': 1,
                'log_file': os.path.join(pth_proj,'log.txt'),
                'presolve': 0,
                'presolve_eps': 1e-6,
                'presolve_fixeps': 1e-6,
                'show_boundtol': 0,
                'gurobi_options': gurobi_options_str,
                '_log_input_only': False}

###############################################################################
''' main script '''
###############################################################################

#%% Actual script part
if __name__ == '__main__':
    
    N_year_opti = 30 # Duration of the time window to optimise. Must be a
                     # multiple of 5, between 5 and 30.
    N_year_overlap = 0 # Duration of the overlap between two consecutives
                       # time windows. Must be a multiple of 5 and smaller 
                       # than the duration of the time window

    # To do once at initialisation of the environment
    i = 0
    
    output_folder = os.path.join(pth_output_all,case_study)
    output_file = os.path.join(output_folder,'_Results.pkl')
    
    # Empty fix.mod before loading (may contain stale content from a previous run)
    open(os.path.join(pth_model, 'fix.mod'), 'w').close()

    # Creation of Ampl object to instantiate pre-processor and collector
    ampl_0 = AmplObject(mod_1_path, mod_2_path, dat_path_0, ampl_options,
                        type_model = type_of_model, working_dir = pth_model)
    ampl_0.clean_history()
    ampl_pre = AmplPreProcessor(ampl_0, N_year_opti, N_year_overlap)
    ampl_collector = AmplCollector(ampl_pre, output_file, expl_text)
    
    # To keep track of the time needed to run a whole-horizon optimisation
    t = time.time()

    #%% Run optimisation
    if run_opti:
        
        # For-loop for every time window of the transition
        for i in range(len(ampl_pre.years_opti)):

            t_i = time.time()
            
            # Update sets of EnergyScope depending on the time window
            curr_years_wnd = ampl_pre.write_seq_opti(i).copy()
            ampl_pre.remaining_update(i)
            
            # Ampl object created for each time window
            ampl = AmplObject(mod_1_path, mod_2_path, dat_path,
                              ampl_options, type_model = type_of_model, working_dir = pth_model)

            ampl.ampl.eval("shell 'gurobi -v';")


            # Set the actual gwp limit in 2025
            # ampl.set_params('gwp_limit',{('YEAR_2025'):124000})
            
            if gwp_budget:
                ampl.set_params('max_co2_budget',gwp_budget_val)
                
            if CO2_neutrality_2050:
                ampl.set_params('gwp_limit',{('YEAR_2050'):
                                             CO2_neutrality_2050_val})

            #%% Run deterministic optimisation and collect results
            solve_result, solve_result_num = ampl.run_ampl()
            sys.stdout.flush()
            if solve_result in ('infeasible', 'limit', 'failure'):
                print("\n=== INFEASIBLE - Reading IIS (computed during solve) ===")
                from collections import Counter
                ampl_iis_path = os.path.join(curr_dir.parent, 'ampl_iis.txt')
                ampl_iis_path_fwd = ampl_iis_path.replace('\\', '/')
                ampl.ampl.eval(f"""
                    option display_width 300;
                    display {{j in 1.._ncons: _con[j].iis != 0}}
                        (_conname[j], _con[j].iis) > "{ampl_iis_path_fwd}";
                """)
                if os.path.exists(ampl_iis_path):
                    with open(ampl_iis_path, 'r') as f:
                        lines = [l.strip() for l in f if l.strip() and ':=' not in l and l.strip() != ';' and 'mem' in l]
                    if lines:
                        types = Counter(l.split('[')[0].strip() for l in lines if l)
                        print("IIS constraint types:")
                        for name, count in types.most_common(15):
                            print(f"  {count:4d}  {name}")
                        print("\nFirst 100 IIS constraints:")
                        for l in lines[:100]:
                            print(f"  {l}")
                    else:
                        print("IIS suffix empty — solve result was 'limit', not proven infeasible.")
                raise RuntimeError(f"Infeasible at window {i+1} ({ampl_pre.years_opti[i]})")
            
            ampl.get_total_cost()
            ampl.get_cost_breakdown()
            ampl.get_cost_return()
            ampl.get_total_gwp()
            ampl.get_gwp_transition()
            ampl.get_resources()
            ampl.get_assets()
            ampl.get_annual_monthly_prod()
            ampl.get_new_old_decom()
            ampl.get_F_decom()
            ampl.get_number_of_units()
            ampl.get_year_balance()
            ampl.get_sto_levels()

            if i==0:
                ampl_collector.init_storage(ampl)
            else:
                curr_years_wnd.remove(ampl_pre.year_to_rm)
            ampl_collector.update_storage(ampl,curr_years_wnd,i)
            ampl.set_init_sol()

            elapsed_i = time.time()-t_i
            print('Time to solve the window #'+str(i+1)+': ',elapsed_i, flush=True)
            
            # When reaching the end of the transition, clean and pickle the 
            # collector of results
            if i == len(ampl_pre.years_opti)-1:
                elapsed = time.time()-t
                print('Time to solve the whole problem: ',elapsed)
                
                ampl_collector.clean_collector()
                ampl_collector.pkl()
                break
            
    #%% Plot graphs for deterministic runs
    if graph:
        _spec = _ilu.spec_from_file_location(
            'plot_results',
            os.path.join(curr_dir, 'plot_results.py')
        )
        _pr = _ilu.module_from_spec(_spec)
        _spec.loader.exec_module(_pr)
        _pr.run(case_study)
        
    ###############################################################################
    ''' main script ends here '''
    ###############################################################################

