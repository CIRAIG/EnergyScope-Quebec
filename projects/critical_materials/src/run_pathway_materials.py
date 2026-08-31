# -*- coding: utf-8 -*-
"""
Run the pathway model with the critical-materials constraints
(Constraints.mod / Material_intensity.dat / Material_limits.dat) and return all
results in a single dict of DataFrames.

Usage from a notebook (run from projects/critical_materials/, with src/ on
sys.path):

    import sys
    sys.path.insert(0, 'src')
    from run_pathway_materials import run_pathway_materials

    results = run_pathway_materials('my_first_run')
    results['F_new']
    results['Material_content_year']
    results['Material_content_cumulative']  # running total over Years, see below
    results['Decommissioned_material']  # [t/year] mechanical, before any recycling decision
    results['Recycled_material']
    results['Recycled_material_cumulative']  # running total over Years, see below
    results['Disposed_material']  # [t/year] Decommissioned_material - Recycled_material
    results['Recycling_benefit']  # [M$/year] avoided cost vs disposal+virgin material
    results['Recycling_benefit_cumulative']  # running total over Years, see below

It mirrors shared.utils.run_pathway (same file lists, same rolling horizon
loop, same AmplObject/AmplPreProcessor/AmplCollector classes, imported
read-only from projects/pathway/pylib), with two differences:

Constraints.mod, Material_intensity.dat and Material_limits.dat (in this
project's ampl_files/) are inserted into mod_1_path / mod_2_path.

This operates directly on projects/pathway/model/ (like shared.utils.run_pathway
does) -- its scratch/state files (fix.mod, PES_seq_opti.dat, PES_data_remaining*.dat,
...) get overwritten at every run, same as running the plain pathway model would.
Don't run two of these (or one of these and a plain run_pathway) at the same time:
they'd stomp on each other's state files.

Material_content_year and Recycled_material are extracted window by window
via the existing (unmodified) AmplObject.get_elem() and merged into the same
dict as everything AmplCollector produces (F_new, Assets, TotalCost, ...) --
their 3-level index (Years, Technologies, Materials) isn't one of the shapes
AmplCollector.init_storage knows about, so they're accumulated separately
and merged in only at the end, rather than by patching AmplCollector itself.

Recycling economics (Recycled_material/Disposed_material/Recycling_benefit,
via C_material -> TotalTransitionCost) live inside the same optimization as
F_new/investment decisions. An earlier attempt at this made C_material an
undiscounted lump sum while C_inv is properly discounted (annualised_factor),
which let the optimizer discover that overbuilding capacity purely to
decommission-and-recycle it later looked artificially profitable and blew up
F_new for unrelated technologies. Fixed by discounting Recycling_benefit/
C_material with the same annualised_factor[p,y] C_inv uses -- see
Constraints.mod's recycling_benefit_calc/material_cost_calc.
"""
import os, sys, pickle, time
from pathlib import Path
import pandas as pd

curr_dir = Path(os.path.dirname(__file__))         # .../projects/critical_materials/src
pth_proj = curr_dir.parent                          # .../projects/critical_materials
pth_repo = pth_proj.parent.parent                   # .../EnergyScope-Quebec

pth_pathway       = pth_repo / 'projects' / 'pathway'
pth_pathway_model = pth_pathway / 'model'           # scratch/state files (fix.mod, ...) get overwritten here at each run
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


def _build_dashboard(results, case_study):
    """Import kept local to avoid Plot_functions' plotly/mi_pipeline import cost
    for callers who pass build_dashboard=False. Also refreshes out/index.html
    (the scenario selector) so it never goes stale -- it used to require a
    separate manual build_scenario_selector() call, which was easy to forget
    and left it pointing at case_study folders that had since been deleted."""
    if str(pth_proj) not in sys.path:
        sys.path.insert(0, str(pth_proj))
    from Plot_functions import build_materials_dashboard, build_scenario_selector
    build_materials_dashboard(results, case_study)
    build_scenario_selector()


def run_pathway_materials(
        case_study: str,
        *,
        N_year_opti: int = 30,
        N_year_overlap: int = 0,
        gwp_budget=False,
        gwp_budget_val: float = 1224935.4,
        CO2_neutrality_2050=True,
        CO2_neutrality_2050_val: float = 0,
        description: str = '',
        save_pkl: bool = True,
        skip_if_exists: bool = False,
        verbose: bool = False,
        crossover: int = 0,
        materials_limit: bool = False,
        materials_recycling: bool = False,
        materials_recycling_cost: bool = True,
        follow_objective: bool = False,
        follow_objective_full: bool = False,
        materials_recycling_process: bool = False,
        build_dashboard: bool = True,
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
    materials_recycling : bool
        If True, loads Material_recycling.dat (recycling_rate/recycling_cost/
        primary_material_cost/disposal_cost from the RR_*/Cost_* sheets,
        regenerated by run_build_rr.py) -- the optimizer decides Recycled_material
        jointly with F_new, weighing recycling economics (discounted the same
        way as investment costs, see Constraints.mod's recycling_benefit_calc)
        against the rest of the system. Without this, no recycling happens at
        all (recycling_rate defaults to 0).
    materials_recycling_cost : bool
        Only meaningful when materials_recycling=True. If False, zeroes out
        recycling_cost/primary_material_cost after Material_recycling.dat loads
        (disposal_cost stays at a tiny nonzero value to avoid indifference) --
        Recycled_material is then driven purely by the recycling_rate technical
        ceiling, not by C_material/cost. Default True (real costs, as loaded).
    follow_objective : bool
        Only meaningful when materials_recycling=True. If True, forces the
        model to recycle EXACTLY recycling_objective_share[y,mat] (Recycling_objective
        sheet) of each material's decommissioned amount, aggregated across
        recyclable technologies (recycled_material_objective equality in
        Constraints.mod) -- an equality, not a minimum, so the optimizer loses
        the freedom to recycle more even when it would otherwise want to. If
        False (default), the optimizer decides freely how much to recycle,
        bounded by recycling_rate's ceiling and by whether it's economical
        (discounted recycling_cost vs primary_material_cost + disposal_cost).
    follow_objective_full : bool
        Only meaningful when materials_recycling=True. Implies follow_objective=True,
        but overrides recycling_objective_share to 100% of the true weighted-achievable
        rate (collection_rate*recycling_rate weighted by Decommissioned_material) per
        (year, material), instead of the 85%-calibrated values baked into the
        Recycling_objective sheet / Material_recycling.dat -- forces maximal recycling
        via an equality, decoupled from cost (see Material_recycling_objective_full.mod).
    materials_recycling_process : bool
        If True, loads Constraints_recycling_technologies.mod (competing
        recycling processes -- currently PV c-Si module/infrastructure only,
        see rt_pipeline/run_build_rt.py) and Material_recycling_process.dat.
        Fully independent from materials_recycling/follow_objective (own
        param/var names, own .dat file) -- both can be True together (they
        touch disjoint technologies today: PV vs vehicles) or either alone.
    build_dashboard : bool
        If True (default), writes out/<case_study>/materials_graphs/ (see
        Plot_functions.build_materials_dashboard) right after the run, or
        right after loading from disk when skip_if_exists kicks in.

    Always feeds ampl_files/Material_intensity.dat -- whatever
    run_build_mi.main(vehicle_source=...) last wrote there. To compare
    'watari' vs 'bieuville', build with one, run this and save/rename the
    results, then build with the other and run again.

    Returns
    -------
    dict
        All the standard pathway results (F_new, F_Mult, Assets, TotalCost,
        Resources, ...) plus 'Material_content_year', 'Material_content_cumulative',
        'Decommissioned_material' (mechanical, before any recycling decision --
        see Constraints.mod), 'Recycled_material', 'Recycled_material_cumulative',
        'Disposed_material' (Decommissioned_material - Recycled_material),
        'Recycling_benefit' and 'Recycling_benefit_cumulative' ([M$/year],
        annualised_factor[p,y] * (primary_material_cost + disposal_cost -
        recycling_cost) * Recycled_material -- discounted avoided cost of
        recycling vs disposing + buying virgin material, folded into
        C_material/TotalCost via material_cost_calc), each a pandas
        DataFrame. The '_cumulative' ones are running totals over Years per
        (Technologies, Materials) -- the last year's value is the total over
        the whole period. 'Recycling_shortfall' ([t/year], indexed by Years x
        Materials only -- no Technologies) is only populated when
        follow_objective or follow_objective_full is True: > 0 wherever
        recycling_objective_share couldn't be reached even at the technical
        ceiling (see Constraints.mod's recycled_material_objective/
        recycling_shortfall_penalty_calc) -- purely an accounting gap, not a
        real material flow.
    """
    output_folder = pth_output_all / case_study
    output_file = str(output_folder / '_Results.pkl')
    materials_output_file = str(output_folder / '_Materials_Results.pkl')
    output_folder.mkdir(parents=True, exist_ok=True)

    if skip_if_exists and save_pkl and os.path.exists(output_file) and os.path.exists(materials_output_file):
        print(f'[run_pathway_materials] {case_study} — pkl exists, loading from disk.')
        with open(output_file, 'rb') as f:
            results = pickle.load(f)
        with open(materials_output_file, 'rb') as f:
            results.update(pickle.load(f))
        if build_dashboard:
            _build_dashboard(results, case_study)
        return results

    # --- operate directly on the real projects/pathway/model/ (see module docstring) ---
    pth_model = str(pth_pathway_model)

    # --- file lists (mirrors run_main.py's 'MO' branch) ---
    # ! The order of the files in the list is important !
    mod_1_path = [str(pth_shared_model / 'QC_es_main.mod'),
                  os.path.join(pth_model, 'PES_main.mod'),
                  str(pth_materials / 'Constraints.mod')]  # needs PHASE_WND/F_new/F_decom from PES_main.mod above

    if(materials_recycling_process):
        mod_1_path.append(str(pth_materials / 'Constraints_recycling_technologies.mod'))  # needs Constraints.mod's hooks above

    mod_1_path += [os.path.join(pth_model, 'PES_obj_pathway.mod'),
                   os.path.join(pth_model, 'PES_store_variables.mod')]

    mod_2_path = [os.path.join(pth_model, 'EXTRA_INFOS.dat'),
                  str(pth_data / 'QC_data.dat'),
                  os.path.join(pth_model, 'PES_scenarios.mod'),
                  str(pth_data / 'EUD/out_eud.dat'),
                  str(pth_data / 'Techs/out_techs.dat'),
                  str(pth_data / 'Shares/out_shares.dat'),
                  os.path.join(pth_model, 'PES_data_pathway.dat'),
                  os.path.join(pth_model, 'PES_data_decom_allowed_2020.dat'),
                  str(pth_materials / 'Material_intensity.dat')]  # after TECHNOLOGIES is fully populated
    
    if(materials_limit):
        mod_2_path.append(str(pth_materials / 'Material_limits.dat'))  # manual limit_material / limit_material_year overrides

    if(materials_recycling):
        mod_2_path.append(str(pth_materials / 'Material_recycling.dat'))  # recycling_rate/costs, regenerated by run_build_rr.py from Recycling_rates.xlsx
        if(not materials_recycling_cost):
            mod_2_path.append(str(pth_materials / 'Material_recycling_zero_cost.mod'))  # overrides costs so Recycled_material is driven only by the recycling_rate ceiling
        if(follow_objective_full):
            mod_2_path.append(str(pth_materials / 'Material_recycling_objective_full.mod'))  # overrides recycling_objective_share to 100% of the achievable ceiling

    if(materials_recycling_process):
        mod_2_path.append(str(pth_materials / 'Material_recycling_process.dat'))  # regenerated by run_build_rt.py from Recycling_rates.xlsx

    mod_2_path.append(os.path.join(pth_model, 'fix.mod'))

    dat_path = [os.path.join(pth_model, 'PES_data_years_active.dat'),
                os.path.join(pth_model, 'PES_seq_opti.dat'),
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

    materials_results = {
        'Material_content_year': None,
        'Decommissioned_material': None,
        'Recycled_material': None,
        'Recycled_material_by_process': None,
        'Disposed_material': None,
        'Recycling_benefit': None,
        'Recycling_shortfall': None,
    }

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
        if follow_objective or follow_objective_full:
            ampl.set_params('follow_objective', 1)

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
        for var_name in ('Material_content_year', 'Decommissioned_material', 'Recycled_material', 'Disposed_material', 'Recycling_benefit'):
            df = ampl.get_elem(var_name)
            df.index.names = ['Years', 'Technologies', 'Materials']
            df = df.loc[df.index.get_level_values('Years').isin(curr_years_wnd), :]
            if materials_results[var_name] is None:
                materials_results[var_name] = df
            else:
                combined = pd.concat([materials_results[var_name], df])
                materials_results[var_name] = combined.loc[~combined.index.duplicated(keep='last')].sort_index()

        if follow_objective or follow_objective_full:
            # 2-index (Years, Materials) -- no Technologies dimension, unlike the vars above.
            shortfall_df = ampl.get_elem('Recycling_shortfall')
            shortfall_df.index.names = ['Years', 'Materials']
            shortfall_df = shortfall_df.loc[shortfall_df.index.get_level_values('Years').isin(curr_years_wnd), :]
            if materials_results['Recycling_shortfall'] is None:
                materials_results['Recycling_shortfall'] = shortfall_df
            else:
                combined = pd.concat([materials_results['Recycling_shortfall'], shortfall_df])
                materials_results['Recycling_shortfall'] = combined.loc[~combined.index.duplicated(keep='last')].sort_index()

        if materials_recycling_process:
            df_proc = ampl.get_elem('Recycled_material_process')
            df_proc.index.names = ['Years', 'Technologies', 'Materials', 'RECYCLING_PROCESS']
            df_proc = df_proc.loc[df_proc.index.get_level_values('Years').isin(curr_years_wnd), :]
            if materials_results.get('Recycled_material_by_process') is None:
                materials_results['Recycled_material_by_process'] = df_proc
            else:
                combined = pd.concat([materials_results['Recycled_material_by_process'], df_proc])
                materials_results['Recycled_material_by_process'] = combined.loc[~combined.index.duplicated(keep='last')].sort_index()

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
        if materials_results[k] is not None:
            materials_results[k].dropna(how='all', inplace=True)

    # 'Recycled_material' is the TOTAL recycled, whichever approach(es) produced it: the simple-rate
    # approach's own var (always present, possibly all-zero) plus the competing-processes approach's
    # Recycled_material_process summed over process (only present when materials_recycling_process=True).
    # Kept as one unified series so dashboard code doesn't need to know which approach was used.
    if materials_results.get('Recycled_material_by_process') is not None:
        proc_summed = (materials_results['Recycled_material_by_process']['Recycled_material_process']
                       .groupby(level=['Years', 'Technologies', 'Materials']).sum())
        materials_results['Recycled_material']['Recycled_material'] = (
            materials_results['Recycled_material']['Recycled_material'].add(proc_summed, fill_value=0)
        )

    # Cumulative material demand, running sum over Years per (Technologies,
    # Materials). Material_content_year is annualised [t/year] (divided by 5,
    # see Constraints.mod's comment), so it's multiplied back by 5 before
    # summing -- same conversion the AMPL model itself uses for its own
    # Material_content variable (cumulative total over a window's years).
    # The last year's value is the total demand at the end of the period.
    mcy = materials_results['Material_content_year']['Material_content_year']
    cum_df = (mcy * 5).reset_index().sort_values(['Technologies', 'Materials', 'Years'])
    cum_df['Material_content_cumulative'] = (
        cum_df.groupby(['Technologies', 'Materials'])['Material_content_year'].cumsum()
    )
    materials_results['Material_content_cumulative'] = (
        cum_df.set_index(['Years', 'Technologies', 'Materials'])[['Material_content_cumulative']].sort_index()
    )

    # Same running-sum convention for Recycled_material (also annualised, cf.
    # Constraints.mod's recycled_material_max/material_cost_calc) -- last
    # year's value is the total material recovered over the whole period.
    rec = materials_results['Recycled_material']['Recycled_material']
    rec_cum_df = (rec * 5).reset_index().sort_values(['Technologies', 'Materials', 'Years'])
    rec_cum_df['Recycled_material_cumulative'] = (
        rec_cum_df.groupby(['Technologies', 'Materials'])['Recycled_material'].cumsum()
    )
    materials_results['Recycled_material_cumulative'] = (
        rec_cum_df.set_index(['Years', 'Technologies', 'Materials'])[['Recycled_material_cumulative']].sort_index()
    )

    # Same running-sum convention for Recycling_benefit (avoided cost of recycling
    # vs disposal+virgin material, see Constraints.mod's recycling_benefit_calc) --
    # last year's value is the total avoided cost [M$] over the whole period.
    benefit = materials_results['Recycling_benefit']['Recycling_benefit']
    benefit_cum_df = (benefit * 5).reset_index().sort_values(['Technologies', 'Materials', 'Years'])
    benefit_cum_df['Recycling_benefit_cumulative'] = (
        benefit_cum_df.groupby(['Technologies', 'Materials'])['Recycling_benefit'].cumsum()
    )
    materials_results['Recycling_benefit_cumulative'] = (
        benefit_cum_df.set_index(['Years', 'Technologies', 'Materials'])[['Recycling_benefit_cumulative']].sort_index()
    )

    if save_pkl:
        with open(materials_output_file, 'wb') as f:
            pickle.dump(materials_results, f)

    # --- merge everything into a single dict, like shared.utils.run_pathway ---
    results = dict(ampl_collector.results)
    results.update(materials_results)
    if build_dashboard:
        _build_dashboard(results, case_study)
    return results


if __name__ == '__main__':
    run_pathway_materials(
        'Materials_test',
        description='Pathway run with critical-materials constraints (Constraints.mod / Material_intensity.dat)',
        verbose=True,
    )
