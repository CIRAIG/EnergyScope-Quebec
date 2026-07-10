# -*- coding: utf-8 -*-
"""
Standalone driver to run the pathway model with the critical-materials
constraints (test.mod / Material_intensity.dat), without touching anything
under projects/pathway/.

It mirrors projects/pathway/src/run_main.py (same file lists, same rolling
horizon loop, same AmplObject/AmplPreProcessor/AmplCollector classes, imported
read-only from projects/pathway/pylib), with two differences:

1. test.mod and Material_intensity.dat (in this project's ampl_files/) are
   inserted into mod_1_path / mod_2_path.
2. The pathway model's scratch/state files (fix.mod, PES_seq_opti.dat,
   PES_data_remaining*.dat, ...) are never written in-place under
   projects/pathway/model/. Instead, that directory is copied once into
   out/<case_study>/pathway_model_workdir/ and the run operates entirely on
   that local copy, so nothing outside projects/critical_materials/ is ever
   modified.

Material_content_year and Recycled_material are extracted window by window
via the existing (unmodified) AmplObject.get_elem() and accumulated locally
into their own pickle, separate from AmplCollector's _Results.pkl (their
3-level index (Years, Technologies, Materials) isn't one of the shapes
AmplCollector.init_storage knows about, and that file lives outside this
project so it isn't touched here).
"""
import os, sys, shutil, pickle, time
from pathlib import Path
import pandas as pd

curr_dir = Path(os.path.dirname(__file__))         # .../projects/critical_materials/src
pth_proj = curr_dir.parent                          # .../projects/critical_materials
pth_repo = pth_proj.parent.parent                   # .../EnergyScope-Quebec

pth_pathway       = pth_repo / 'projects' / 'pathway'
pth_pathway_model = pth_pathway / 'model'           # read-only source, never written to
pth_data          = pth_repo / 'shared' / 'data'
pth_shared_model  = pth_repo / 'shared' / 'model'
pth_materials     = pth_proj / 'ampl_files'         # test.mod, Material_intensity.dat

pymodPath = str(pth_pathway / 'pylib')              # read-only import of existing classes
sys.path.insert(0, pymodPath)

from ampl_object import AmplObject
from ampl_preprocessor import AmplPreProcessor
from ampl_collector import AmplCollector

#%% Options of this run

gwp_budget = False
gwp_budget_val = 1224935.4
CO2_neutrality_2050 = False
CO2_neutrality_2050_val = 0

run_opti = True
case_study = 'Materials_test'
expl_text = 'Pathway run with critical-materials constraints (test.mod / Material_intensity.dat)'

N_year_opti = 30
N_year_overlap = 0

#%% Self-contained working copy of projects/pathway/model
# (fix.mod, PES_seq_opti.dat, PES_data_remaining*.dat get rewritten at every
# window; this keeps that entirely inside critical_materials/out/)

pth_output_all = pth_proj / 'out'
output_folder = pth_output_all / case_study
pth_model = output_folder / 'pathway_model_workdir'

if pth_model.exists():
    shutil.rmtree(pth_model)
shutil.copytree(pth_pathway_model, pth_model)
pth_model = str(pth_model)

#%% Join the .dat and .mod files (mirrors run_main.py's 'MO' branch)
# ! The order of the files in the list is important !

mod_1_path = [str(pth_shared_model / 'QC_es_main.mod'),
              os.path.join(pth_model, 'QC_es_pathway.mod'),
              str(pth_materials / 'test.mod'),  # needs PHASE_WND/F_new/F_decom from QC_es_pathway.mod above
              os.path.join(pth_model, 'QC_es_obj_pathway.mod'),
              os.path.join(pth_model, 'PES_store_variables.mod')]

mod_2_path = [os.path.join(pth_model, 'EXTRA_INFOS.dat'),
              str(pth_data / 'QC_data.dat'),
              os.path.join(pth_model, 'PES_scenarios.mod'),
              str(pth_data / 'EUD/out_eud.dat'),
              str(pth_data / 'Techs/out_techs.dat'),
              str(pth_data / 'Shares/out_shares.dat'),
              os.path.join(pth_model, 'QC_data_pathway.dat'),
              os.path.join(pth_model, 'PES_data_decom_allowed_2020.dat'),
              str(pth_materials / 'Material_intensity.dat'),  # after TECHNOLOGIES is fully populated
              str(pth_materials / 'Material_limits.dat'),      # manual limit_material / limit_material_year overrides
              os.path.join(pth_model, 'fix.mod')]

dat_path = [os.path.join(pth_model, 'PES_seq_opti.dat'),
            os.path.join(pth_model, 'PES_data_set_AGE_2020.dat')]

dat_path_0 = dat_path + [os.path.join(pth_model, 'PES_data_remaining.dat')]
dat_path += [os.path.join(pth_model, 'PES_data_remaining_wnd.dat')]

#%% Options for ampl and gurobi

gurobi_options = ['predual=-1', 'method=2', 'crossover=0', 'threads=0',
                   'prepasses=3', 'barconvtol=1e-6', 'presolve=-1',
                   'iisfind=1', 'outlev=1']
gurobi_options_str = ' '.join(gurobi_options)

ampl_options = {'show_stats': 1,
                'log_file': str(output_folder / 'log.txt'),
                'presolve': 0,
                'presolve_eps': 1e-6,
                'presolve_fixeps': 1e-6,
                'show_boundtol': 0,
                'gurobi_options': gurobi_options_str,
                '_log_input_only': False}

#%% Actual script part
if __name__ == '__main__':

    i = 0
    output_file = str(output_folder / '_Results.pkl')
    materials_output_file = str(output_folder / '_Materials_Results.pkl')

    open(os.path.join(pth_model, 'fix.mod'), 'w').close()

    ampl_0 = AmplObject(mod_1_path, mod_2_path, dat_path_0, ampl_options,
                        type_model='MO', working_dir=pth_model)
    ampl_0.clean_history()
    ampl_pre = AmplPreProcessor(ampl_0, N_year_opti, N_year_overlap)
    ampl_collector = AmplCollector(ampl_pre, output_file, expl_text)

    materials_results = {'Material_content_year': None, 'Recycled_material': None}

    t = time.time()

    if run_opti:
        for i in range(len(ampl_pre.years_opti)):
            t_i = time.time()

            curr_years_wnd = ampl_pre.write_seq_opti(i).copy()
            ampl_pre.remaining_update(i)

            ampl = AmplObject(mod_1_path, mod_2_path, dat_path,
                              ampl_options, type_model='MO', working_dir=pth_model)

            if gwp_budget:
                ampl.set_params('gwp_limit_transition', gwp_budget_val)
            if CO2_neutrality_2050:
                ampl.set_params('gwp_limit', {('YEAR_2050'): CO2_neutrality_2050_val})

            solve_result, solve_result_num = ampl.run_ampl()
            sys.stdout.flush()
            if solve_result in ('infeasible', 'limit', 'failure'):
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

            # --- material variables: extracted locally, kept out of AmplCollector ---
            for var_name in ('Material_content_year', 'Recycled_material'):
                df = ampl.get_elem(var_name)
                df.index.names = ['Years', 'Technologies', 'Materials']
                df = df.loc[df.index.get_level_values('Years').isin(curr_years_wnd), :]
                if materials_results[var_name] is None:
                    materials_results[var_name] = df
                else:
                    combined = pd.concat([materials_results[var_name], df])
                    materials_results[var_name] = combined.loc[~combined.index.duplicated(keep='last')].sort_index()

            if i == 0:
                ampl_collector.init_storage(ampl)
            else:
                curr_years_wnd.remove(ampl_pre.year_to_rm)
            ampl_collector.update_storage(ampl, curr_years_wnd, i)
            ampl.set_init_sol()

            elapsed_i = time.time() - t_i
            print('Time to solve the window #' + str(i + 1) + ': ', elapsed_i, flush=True)

            if i == len(ampl_pre.years_opti) - 1:
                elapsed = time.time() - t
                print('Time to solve the whole problem: ', elapsed)

                ampl_collector.clean_collector()
                ampl_collector.pkl()

                for k in materials_results:
                    materials_results[k].dropna(how='all', inplace=True)
                with open(materials_output_file, 'wb') as f:
                    pickle.dump(materials_results, f)
                break
