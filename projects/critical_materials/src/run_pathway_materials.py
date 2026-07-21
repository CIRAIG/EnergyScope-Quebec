# -*- coding: utf-8 -*-
"""
Run the pathway model with the critical-materials constraints
(Constraints.mod / Material_intensity.dat / Material_limits.dat) and return all
results in a single dict of DataFrames, without touching anything under
projects/pathway/.

Usage from a notebook (run from projects/critical_materials/, with src/ on
sys.path):

    import sys
    sys.path.insert(0, 'src')
    from run_pathway_materials import run_pathway_materials

    results = run_pathway_materials('my_first_run')
    results['F_new']
    results['Material_content_year']
    results['Recycled_material']

It mirrors shared.utils.run_pathway (same file lists, same rolling horizon
loop, same AmplObject/AmplPreProcessor/AmplCollector classes, imported
read-only from projects/pathway/pylib), with two differences:

1. Constraints.mod, Material_intensity.dat and Material_limits.dat (in this
   project's ampl_files/) are inserted into mod_1_path / mod_2_path.
2. The pathway model's scratch/state files (fix.mod, PES_seq_opti.dat,
   PES_data_remaining*.dat, ...) are never written in-place under
   projects/pathway/model/. Instead, that directory is copied once into
   out/<case_study>/pathway_model_workdir/ and the run operates entirely on
   that local copy, so nothing outside projects/critical_materials/ is ever
   modified.

Material_content_year and Recycled_material are extracted window by window
via the existing (unmodified) AmplObject.get_elem() and merged into the same
dict as everything AmplCollector produces (F_new, Assets, TotalCost, ...) --
their 3-level index (Years, Technologies, Materials) isn't one of the shapes
AmplCollector.init_storage knows about, so they're accumulated separately
and merged in only at the end, rather than by patching AmplCollector itself.
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
pth_materials     = pth_proj / 'ampl_files'         # Constraints.mod, Material_intensity.dat, Material_limits.dat
pth_output_all    = pth_proj / 'out'

pymodPath = str(pth_pathway / 'pylib')              # read-only import of existing classes
if pymodPath not in sys.path:
    sys.path.insert(0, pymodPath)

from ampl_object import AmplObject
from ampl_preprocessor import AmplPreProcessor
from ampl_collector import AmplCollector


def run_pathway_materials(
        case_study: str,
        *,
        N_year_opti: int = 30,
        N_year_overlap: int = 0,
        gwp_budget=False,
        gwp_budget_val: float = 1224935.4,
        CO2_neutrality_2050=False,
        CO2_neutrality_2050_val: float = 0,
        description: str = '',
        save_pkl: bool = True,
        skip_if_exists: bool = False,
        verbose: bool = False,
        crossover: int = 0,
        hydro_quebec_constraints: bool = True,
        materials_limit: bool = False,
) -> dict:
    """Run the pathway model with critical-materials constraints and return the results dict.

    Parameters
    ----------
    case_study : str
        Name for this run, used as the output folder name (out/<case_study>/).
    N_year_opti : int
        Duration of each rolling-horizon window [years]. Default 30.
    N_year_overlap : int
        Overlap between consecutive windows [years]. Default 0.
    gwp_budget : bool or float
        Whole-transition cumulative GWP cap [kt CO2-eq.]. False disables it (default).
    CO2_neutrality_2050 : bool
        If True, forces gwp_limit['YEAR_2050'] = CO2_neutrality_2050_val.
    description : str
        Short description stored in the recap CSV.
    save_pkl : bool
        If True, writes out/<case_study>/_Results.pkl and _Materials_Results.pkl.
    skip_if_exists : bool
        If True and save_pkl=True, skip the optimisation when a pkl already
        exists and return the saved results instead.
    verbose : bool
        If True, print AMPL/Gurobi solver logs. Default False.

    Returns
    -------
    dict
        All the standard pathway results (F_new, F_Mult, Assets, TotalCost,
        Resources, ...) plus 'Material_content_year' and 'Recycled_material',
        each a pandas DataFrame.
    """
    output_folder = pth_output_all / case_study
    output_file = str(output_folder / '_Results.pkl')
    materials_output_file = str(output_folder / '_Materials_Results.pkl')

    if skip_if_exists and save_pkl and os.path.exists(output_file) and os.path.exists(materials_output_file):
        print(f'[run_pathway_materials] {case_study} — pkl exists, loading from disk.')
        with open(output_file, 'rb') as f:
            results = pickle.load(f)
        with open(materials_output_file, 'rb') as f:
            results.update(pickle.load(f))
        return results

    # --- self-contained working copy of projects/pathway/model ---
    pth_model = output_folder / 'pathway_model_workdir'
    if pth_model.exists():
        shutil.rmtree(pth_model)
    shutil.copytree(pth_pathway_model, pth_model)
    pth_model = str(pth_model)

    # --- file lists (mirrors run_main.py's 'MO' branch) ---
    # ! The order of the files in the list is important !
    mod_1_path = [str(pth_shared_model / 'QC_es_main.mod'),
                  os.path.join(pth_model, 'QC_es_pathway.mod'),
                  str(pth_materials / 'Constraints.mod'),  # needs PHASE_WND/F_new/F_decom from QC_es_pathway.mod above
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
                  str(pth_materials / 'Material_intensity.dat')]  # after TECHNOLOGIES is fully populated
    
    if(not hydro_quebec_constraints):
        mod_2_path.append(str(pth_materials / 'relax_min.mod'))
    
    if(materials_limit):
        mod_2_path.append(str(pth_materials / 'Material_limits.dat'))  # manual limit_material / limit_material_year overrides

    mod_2_path.append(os.path.join(pth_model, 'fix.mod'))

    dat_path = [os.path.join(pth_model, 'PES_seq_opti.dat'),
                os.path.join(pth_model, 'PES_data_set_AGE_2020.dat')]

    dat_path_0 = dat_path + [os.path.join(pth_model, 'PES_data_remaining.dat')]
    dat_path += [os.path.join(pth_model, 'PES_data_remaining_wnd.dat')]

    # --- ampl / gurobi options ---
    _outlev = 1 if verbose else 0
    gurobi_options = ['predual=-1', 'method=2', f'crossover={crossover}', 'threads=0',
                       'prepasses=3', 'barconvtol=1e-6', 'presolve=-1',
                       'iisfind=1', f'outlev={_outlev}']
    gurobi_options_str = ' '.join(gurobi_options)

    ampl_options = {'show_stats': 1 if verbose else 0,
                    'log_file': str(output_folder / 'log.txt'),
                    'presolve': 0,
                    'presolve_eps': 1e-6,
                    'presolve_fixeps': 1e-6,
                    'show_boundtol': 0,
                    'gurobi_options': gurobi_options_str,
                    '_log_input_only': False}

    class _SilentHandler:
        def output(self, kind, msg): pass
    _silence = _SilentHandler() if not verbose else None

    # --- run ---
    open(os.path.join(pth_model, 'fix.mod'), 'w').close()

    ampl_0 = AmplObject(mod_1_path, mod_2_path, dat_path_0, ampl_options,
                        type_model='MO', working_dir=pth_model)
    if _silence:
        ampl_0.ampl.set_output_handler(_silence)
    ampl_0.clean_history()
    ampl_pre = AmplPreProcessor(ampl_0, N_year_opti, N_year_overlap)
    ampl_collector = AmplCollector(ampl_pre, output_file, description)

    materials_results = {'Material_content_year': None, 'Recycled_material': None}

    t_total = time.time()

    for i in range(len(ampl_pre.years_opti)):
        t_i = time.time()

        curr_years_wnd = ampl_pre.write_seq_opti(i).copy()
        ampl_pre.remaining_update(i)

        ampl = AmplObject(mod_1_path, mod_2_path, dat_path,
                          ampl_options, type_model='MO', working_dir=pth_model)
        if _silence:
            ampl.ampl.set_output_handler(_silence)

        if gwp_budget is not False:
            budget_val = gwp_budget_val if gwp_budget is True else float(gwp_budget)
            ampl.set_params('gwp_limit_transition', budget_val)
        if CO2_neutrality_2050:
            ampl.set_params('gwp_limit', {('YEAR_2050'): CO2_neutrality_2050_val})

        solve_result, solve_result_num = ampl.run_ampl()
        sys.stdout.flush()
        if solve_result in ('infeasible', 'limit', 'failure'):
            raise RuntimeError(
                f"[run_pathway_materials] Infeasible at window {i + 1} "
                f"({ampl_pre.years_opti[i]}) for case_study='{case_study}'"
            )

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

        # --- material variables: extracted locally, merged into results at the end ---
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

        print(f'[run_pathway_materials] Window {i + 1}/{len(ampl_pre.years_opti)} done '
              f'in {time.time() - t_i:.1f}s', flush=True)

        if i == len(ampl_pre.years_opti) - 1:
            print(f'[run_pathway_materials] Total time: {time.time() - t_total:.1f}s')
            ampl_collector.clean_collector()
            if save_pkl:
                ampl_collector.pkl()

    for k in materials_results:
        materials_results[k].dropna(how='all', inplace=True)

    if save_pkl:
        with open(materials_output_file, 'wb') as f:
            pickle.dump(materials_results, f)

    # --- merge everything into a single dict, like shared.utils.run_pathway ---
    results = dict(ampl_collector.results)
    results.update(materials_results)
    return results


if __name__ == '__main__':
    run_pathway_materials(
        'Materials_test',
        description='Pathway run with critical-materials constraints (Constraints.mod / Material_intensity.dat)',
        verbose=True,
    )
