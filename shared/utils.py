import os
import sys
from pathlib import Path
import pandas as pd
from energyscope.models import Model
from energyscope.energyscope import Energyscope
from energyscope.result import postprocessing, Result

_GWP_BUDGET_DEFAULT = 883428  # [kt CO2-eq.] default whole-transition GWP budget

# Get the absolute path to the directory containing this file
_UTILS_DIR = Path(__file__).parent.absolute()
_DATA_DIR = _UTILS_DIR / 'data'
_MODEL_DIR = _UTILS_DIR / 'model'
_SCENARIOS_DIR = _UTILS_DIR / 'scenarios'


def collapse_temporal_index(result: Result, year: str = None) -> Result:
    """Remove the YEARS index level from a Result object.

    Snapshot models that share a .mod file with the pathway model inherit a YEARS
    index on all variables/parameters. This function collapses that single-year
    dimension so that postprocessing() receives the index structure it expects:
    (Technologies, ...) instead of (YEARS, Technologies, ...).

    Parameters
    ----------
    result : Result
        Object returned by parse_result().
    year : str, optional
        Year to select, e.g. 'YEAR_2030'. Auto-detected when None (works as long
        as only one year is present, which is always the case for a snapshot model).

    Raises
    ------
    ValueError
        If year is None and multiple distinct years are found (ambiguous collapse).
    """

    def _find_year_level(df: pd.DataFrame):
        if df is None or df.empty:
            return None, None
        if isinstance(df.index, pd.MultiIndex):
            for i in range(df.index.nlevels):
                vals = df.index.get_level_values(i).unique()
                year_vals = [v for v in vals if str(v).startswith('YEAR_')]
                if year_vals:
                    return i, year_vals
        else:
            year_vals = [v for v in df.index.unique() if str(v).startswith('YEAR_')]
            if year_vals:
                return 0, year_vals
        return None, None

    def _auto_detect_year(dicts):
        for d in dicts:
            for df in d.values():
                _, year_vals = _find_year_level(df)
                if year_vals:
                    return year_vals
        return None

    if year is None:
        found = _auto_detect_year([result.variables, result.parameters, result.objectives])
        if found is None:
            return result
        if len(found) > 1:
            raise ValueError(
                f"Multiple years found {found}. "
                "Pass the desired year explicitly via the `year` argument."
            )
        year = str(found[0])

    def _collapse(df: pd.DataFrame) -> pd.DataFrame:
        if df is None or df.empty:
            return df
        level, _ = _find_year_level(df)
        if level is None:
            return df
        df = df.copy()
        if isinstance(df.index, pd.MultiIndex):
            out = df.xs(year, level=level)
            if isinstance(out.index, pd.MultiIndex):
                out.index.names = [f'index{i}' for i in range(out.index.nlevels)]
            else:
                out.index.name = 'index'
            return out
        else:
            return df.loc[df.index == year].reset_index(drop=True)

    def _process(d: dict) -> dict:
        return {k: _collapse(v) for k, v in d.items()}

    return Result(
        constraints=result.constraints,
        parameters=_process(result.parameters),
        objectives=_process(result.objectives),
        sets=result.sets,
        variables=_process(result.variables),
        postprocessing=result.postprocessing,
    )


def run_model(
        model: Model,
        apply_postprocessing: bool = True,
) -> Result:
    solver_options = {
        'solver': 'gurobi',
        'solver_msg': 0,
    }

    es = Energyscope(model=model, solver_options=solver_options)
    res = es.calc()
    if apply_postprocessing:
        res = collapse_temporal_index(res)
        res = postprocessing(res)

    return res


def load_snapshot(year: int, scenario: bool = True) -> Model:

    # The year 2020 is approximated with 2021 data, and 2025 with 2023 data (until we have more recent data)
    if year == 2021:
        year = 2020
    elif year == 2023:
        year = 2025

    # To load a snapshot model using the transition framework, we set one unique time step
    # Therefore, we re-write QC_set_snapshot.dat accordingly
    snapshot_file = _DATA_DIR / 'QC_set_snapshot.dat'
    with open(snapshot_file, 'w') as f:
        f.write(f'set YEARS := YEAR_{year};\n')
        f.write('set YEAR_ONE := ;\n')
        f.write(f'set YEARS_WND := YEAR_{year};\n')
        f.write(f'set YEARS_UP_TO := YEAR_{year};')

    files = [
        ('mod', str(_MODEL_DIR / 'QC_es_main.mod')),
        ('mod', str(_MODEL_DIR / 'QC_objective_function.mod')),
        ('dat', str(snapshot_file)),
        ('dat', str(_DATA_DIR / 'QC_data.dat')),
        ('dat', str(_DATA_DIR / 'Techs' / f'QC_techs_{year}.dat')),
        ('dat', str(_DATA_DIR / 'Shares' / f'QC_shares_{year}.dat')),
        ('dat', str(_DATA_DIR / 'EUD' / f'QC_eud_{year}.dat')),
    ]

    if year == 2050 and scenario:
        files.append(('dat', str(_SCENARIOS_DIR / f'QC_generic_scenario_{year}.dat')))

    return Model(files)


def run_pathway(
        case_study: str,
        *,
        N_year_opti: int = 30,
        N_year_overlap: int = 0,
        gwp_budget=False,
        extra_files=None,
        save_pkl: bool = None,
        description: str = '',
        plot: bool = False,
        skip_if_exists: bool = False,
        verbose: bool = False,
        #ADDED BY PAOLO (to validate)
        materials: bool = False,
        gwp_budget_val: float = 1224935.4,
        CO2_neutrality_2050: bool = True,
        CO2_neutrality_2050_val: float = 0,
        crossover: int = 0,
        materials_limit: bool = False,
        materials_recycling: bool = False,
        materials_recycling_cost: bool = True,
        follow_objective: bool = False,
        follow_objective_full: bool = False,
        materials_recycling_process: bool = False,
        build_dashboard: bool = True,
) -> dict:
    """Run the EnergyScope transition-pathway model and return the results dict.

    Parameters
    ----------
    case_study : str
        Name for this run, used as the output folder name when save_pkl=True.
    N_year_opti : int
        Duration of each rolling-horizon window [years]. Default 30.
    N_year_overlap : int
        Overlap between consecutive windows [years]. Default 0.
    gwp_budget : bool or float
        Whole-transition cumulative GWP cap [kt CO2-eq.].
        False  → disabled (default).
        True   → uses the built-in default (1 224 935 kt).
        float  → your custom cap.
        NOTE: requires the gwp_limit_transition constraint to be active in the model.
    extra_files : list of str, optional
        Paths to additional .mod or mixed .dat files injected into the model
        after the standard data files but before fix.mod.
        Use for extra constraints, scenario overrides, or custom parameters.
    save_pkl : bool, optional
        If True, writes results to out/<case_study>/_Results.pkl. Default None,
        which resolves to False for materials=False (unchanged) and True for
        materials=True (matches _run_pathway_materials' own historical default).
    description : str
        Short description stored in the recap CSV (only when save_pkl=True).
    plot : bool
        If True, generates HTML charts via plot_results after the run. Default False.
    skip_if_exists : bool
        If True and save_pkl=True, skip the optimisation when a pkl already
        exists and return the saved results instead.
    verbose : bool
        If True, print AMPL statistics and Gurobi solver log. Default False.
    materials : bool
        If True, loads projects/critical_materials' Constraints.mod /
        Material_intensity.dat and returns the additional material-flow
        results alongside the standard ones (see _run_pathway_materials at
        the end of this file for the materials_* parameters below, which are
        only meaningful when materials=True). Default False (identical
        behaviour/output to before this parameter existed).
    gwp_budget_val, CO2_neutrality_2050, CO2_neutrality_2050_val, crossover,
    materials_limit, materials_recycling, materials_recycling_cost,
    follow_objective, follow_objective_full, materials_recycling_process,
    build_dashboard : bool / float / int
        Only meaningful when materials=True — see _run_pathway_materials's
        docstring at the end of this file. Ignored (no-op) when materials=False,
        matching plain run_pathway's behaviour before this parameter existed.

    Returns
    -------
    dict
        AmplCollector.results — ~30 named pandas DataFrames with the same
        structure expected by plot_results.run() — plus, when materials=True,
        the additional material-flow results (see _run_pathway_materials).
    """
    #ADDED BY PAOLO (to validate)
    if not materials:
        _materials_only = {
            'materials_limit': materials_limit, 'materials_recycling': materials_recycling,
            'follow_objective': follow_objective, 'follow_objective_full': follow_objective_full,
            'materials_recycling_process': materials_recycling_process,
        }
        _set_anyway = [k for k, v in _materials_only.items() if v]
        if _set_anyway:
            raise ValueError(
                f"{_set_anyway} were passed but materials=False, so they'd be silently "
                f"ignored (Constraints.mod never gets loaded). Pass materials=True too."
            )
    if materials:
        if save_pkl is None:
            save_pkl = True  # _run_pathway_materials' own historical default
        return _run_pathway_materials(
            case_study,
            N_year_opti=N_year_opti,
            N_year_overlap=N_year_overlap,
            gwp_budget=gwp_budget,
            gwp_budget_val=gwp_budget_val,
            CO2_neutrality_2050=CO2_neutrality_2050,
            CO2_neutrality_2050_val=CO2_neutrality_2050_val,
            crossover=crossover,
            description=description,
            save_pkl=save_pkl,
            skip_if_exists=skip_if_exists,
            verbose=verbose,
            materials_limit=materials_limit,
            materials_recycling=materials_recycling,
            materials_recycling_cost=materials_recycling_cost,
            follow_objective=follow_objective,
            follow_objective_full=follow_objective_full,
            materials_recycling_process=materials_recycling_process,
            build_dashboard=build_dashboard,
        )
    if save_pkl is None:
        save_pkl = False  # plain run_pathway's own historical default

    import importlib.util as _ilu
    import pickle
    import time as _time_mod

    _REPO_DIR         = _UTILS_DIR.parent
    _PATHWAY_DIR      = _REPO_DIR / 'projects' / 'pathway'
    _pth_model        = str(_PATHWAY_DIR / 'model')
    _pth_data         = str(_UTILS_DIR / 'data')
    _pth_shared_model = str(_UTILS_DIR / 'model')

    _pylib = str(_PATHWAY_DIR / 'pylib')
    if _pylib not in sys.path:
        sys.path.insert(0, _pylib)

    from ampl_object       import AmplObject
    from ampl_preprocessor import AmplPreProcessor
    from ampl_collector    import AmplCollector

    output_folder = str(_PATHWAY_DIR / 'out' / case_study)
    output_file   = os.path.join(output_folder, '_Results.pkl')

    if skip_if_exists and save_pkl and os.path.exists(output_file):
        print(f'[run_pathway] {case_study} — pkl exists, loading from disk.')
        try:
            with open(output_file, 'rb') as _f:
                return pickle.load(_f)
        except Exception as _e:
            print(f'[run_pathway] WARNING: pkl load failed ({_e}). Re-running optimisation.')
            os.remove(output_file)

    _extra = list(extra_files or [])

    mod_1_path = [
        os.path.join(_pth_shared_model, 'QC_es_main.mod'),
        os.path.join(_pth_model,        'PES_main.mod'),
        os.path.join(_pth_model,        'PES_obj_pathway.mod'),
        os.path.join(_pth_model,        'PES_store_variables.mod'),
    ]
    mod_2_path = [
        os.path.join(_pth_model, 'EXTRA_INFOS.dat'),
        os.path.join(_pth_data,  'QC_data.dat'),
        os.path.join(_pth_model, 'PES_scenarios.mod'),
        os.path.join(_pth_data,  'EUD/out_eud.dat'),
        os.path.join(_pth_data,  'Techs/out_techs.dat'),
        os.path.join(_pth_data,  'Shares/out_shares.dat'),
        os.path.join(_pth_model, 'PES_data_pathway.dat'),
        os.path.join(_pth_model, 'PES_data_decom_allowed_2020.dat'),
    ] + _extra + [
        os.path.join(_pth_model, 'fix.mod'),
    ]

    dat_path_base = [
        os.path.join(_pth_model, 'PES_data_years_active.dat'),
        os.path.join(_pth_model, 'PES_seq_opti.dat'),
        os.path.join(_pth_model, 'PES_data_set_AGE_2020.dat'),
    ]
    dat_path_0 = dat_path_base + [os.path.join(_pth_model, 'PES_data_remaining.dat')]
    dat_path   = dat_path_base + [os.path.join(_pth_model, 'PES_data_remaining_wnd.dat')]

    _outlev = 1 if verbose else 0
    gurobi_opts = ' '.join([
        'predual=-1', 'method=2', 'crossover=0', 'threads=0',
        'prepasses=3', 'barconvtol=1e-6', 'presolve=-1',
        f'iisfind=1', f'outlev={_outlev}',
    ])
    ampl_options = {
        'show_stats':      1 if verbose else 0,
        'log_file':        os.path.join(str(_PATHWAY_DIR), 'log.txt'),
        'presolve':        0,
        'presolve_eps':    1e-6,
        'presolve_fixeps': 1e-6,
        'show_boundtol':   0,
        'gurobi_options':  gurobi_opts,
        '_log_input_only': False,
    }

    open(os.path.join(_pth_model, 'fix.mod'), 'w').close()

    class _SilentHandler:
        def output(self, kind, msg): pass
    _silence = _SilentHandler() if not verbose else None

    ampl_0 = AmplObject(mod_1_path, mod_2_path, dat_path_0, ampl_options,
                        type_model='MO', working_dir=_pth_model)
    if _silence:
        ampl_0.ampl.set_output_handler(_silence)
    ampl_0.clean_history()
    ampl_pre       = AmplPreProcessor(ampl_0, N_year_opti, N_year_overlap)
    ampl_collector = AmplCollector(ampl_pre, output_file, description)

    t_total = _time_mod.time()

    for i in range(len(ampl_pre.years_opti)):
        t_i = _time_mod.time()

        curr_years_wnd = ampl_pre.write_seq_opti(i).copy()
        ampl_pre.remaining_update(i)

        ampl = AmplObject(mod_1_path, mod_2_path, dat_path, ampl_options,
                          type_model='MO', working_dir=_pth_model)
        if _silence:
            ampl.ampl.set_output_handler(_silence)

        if gwp_budget is not False:
            budget_val = _GWP_BUDGET_DEFAULT if gwp_budget is True else float(gwp_budget)
            ampl.set_params('max_co2_budget', budget_val)

        solve_result, _ = ampl.run_ampl()
        sys.stdout.flush()

        if solve_result in ('infeasible', 'limit', 'failure'):
            raise RuntimeError(
                f"[run_pathway] Infeasible at window {i + 1} "
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

        if i == 0:
            ampl_collector.init_storage(ampl)
        else:
            curr_years_wnd.remove(ampl_pre.year_to_rm)
        ampl_collector.update_storage(ampl, curr_years_wnd, i)
        ampl.set_init_sol()

        print(f'[run_pathway] Window {i + 1}/{len(ampl_pre.years_opti)} done '
              f'in {_time_mod.time() - t_i:.1f}s', flush=True)

        if i == len(ampl_pre.years_opti) - 1:
            print(f'[run_pathway] Total time: {_time_mod.time() - t_total:.1f}s')
            ampl_collector.clean_collector()
            if save_pkl:
                ampl_collector.pkl()

    if plot:
        _plot_src = str(_PATHWAY_DIR / 'src' / 'plot_results.py')
        _spec = _ilu.spec_from_file_location('plot_results', _plot_src)
        _pr   = _ilu.module_from_spec(_spec)
        _spec.loader.exec_module(_pr)
        _pr.run(ampl_collector.results,
                case_study=case_study,
                outdir=os.path.join(output_folder, 'graphs'))

    return ampl_collector.results


#ADDED BY PAOLO (to validate)
def _build_materials_dashboard(results, case_study, pth_critical_materials):
    """Import kept local to avoid plot_results'/Plot_functions' plotly/mi_pipeline
    import cost for callers who pass build_dashboard=False. Builds the COMPLETE
    dashboard for a materials=True run: plot_results.run() first (the standard
    Overview/Costs/Capacity/... pages, same as a plain run_pathway(plot=True)
    would produce) into out/<case_study>/graphs/, then
    Plot_functions.build_materials_dashboard() writes its own pages into that
    SAME folder and rebuilds index.html to cover both -- one dashboard, one
    sidebar, matching plot_results' style throughout (see its 'Materials'
    _DASH_SPECS entries). Also refreshes out/index.html (the scenario
    selector) so it never goes stale."""
    _pathway_src = str(_UTILS_DIR.parent / 'projects' / 'pathway' / 'src')
    if _pathway_src not in sys.path:
        sys.path.insert(0, _pathway_src)
    import plot_results
    plot_results.run(results, case_study=case_study,
                      outdir=str(pth_critical_materials / 'out' / case_study / 'graphs'))

    if str(pth_critical_materials) not in sys.path:
        sys.path.insert(0, str(pth_critical_materials))
    from Plot_functions import build_materials_dashboard, build_scenario_selector
    build_materials_dashboard(results, case_study)
    build_scenario_selector()


#ADDED BY PAOLO (to validate)
def _run_pathway_materials(
        case_study: str,
        *,
        N_year_opti: int = 30,
        N_year_overlap: int = 0,
        gwp_budget=False,
        gwp_budget_val: float = 1224935.4,
        CO2_neutrality_2050: bool = True,
        CO2_neutrality_2050_val: float = 0,
        crossover: int = 0,
        description: str = '',
        save_pkl: bool = True,
        skip_if_exists: bool = False,
        verbose: bool = False,
        materials_limit: bool = False,
        materials_recycling: bool = False,
        materials_recycling_cost: bool = True,
        follow_objective: bool = False,
        follow_objective_full: bool = False,
        materials_recycling_process: bool = False,
        build_dashboard: bool = True,
) -> dict:
    """Implements run_pathway(..., materials=True, ...) -- see run_pathway's
    own docstring for the materials_* parameters. Called only from run_pathway;
    not meant to be imported/called directly.

    Mirrors run_pathway's plain-pathway body above (same rolling-horizon loop,
    same AmplObject/AmplPreProcessor/AmplCollector classes) with three
    differences: (1) projects/critical_materials/ampl_files/Constraints.mod
    and friends are inserted into mod_1_path/mod_2_path, (2) material-flow
    variables (Material_content_year, Recycled_material, ...) are extracted
    window by window and merged into the same results dict, (3) results/pkl/
    dashboard are written under projects/critical_materials/out/<case_study>/
    rather than projects/pathway/out/<case_study>/, so existing critical_materials
    tooling (Plot_functions.build_materials_dashboard, the scenario selector)
    keeps working unchanged.

    Recycling economics (Recycled_material/Disposed_material/Recycling_benefit,
    via C_material -> TotalTransitionCost) live inside the same optimisation as
    F_new/investment decisions. C_material is a free variable in PES_main.mod,
    fixed to 0 by default there (safe for plain run_pathway, which never loads
    Constraints.mod); Constraints.mod unfixes it and pins it via material_cost_calc
    once this materials path is active.

    Returns, in addition to the standard pathway results (F_new, F_Mult, Assets,
    TotalCost, Resources, ...): 'Material_content_year', 'Material_content_cumulative',
    'Decommissioned_material' (mechanical, before any recycling decision),
    'Recycled_material', 'Recycled_material_cumulative', 'Disposed_material'
    (Decommissioned_material - Recycled_material), 'Recycling_benefit' and
    'Recycling_benefit_cumulative' ([M$/year], discounted avoided cost of
    recycling vs disposing + buying virgin material), each a pandas DataFrame.
    The '_cumulative' ones are running totals over Years per (Technologies,
    Materials) -- the last year's value is the total over the whole period.
    'Recycling_shortfall' ([t/year], indexed by Years x Materials only) is only
    populated when follow_objective or follow_objective_full is True: > 0
    wherever recycling_objective_share couldn't be reached even at the
    technical ceiling -- purely an accounting gap, not a real material flow.
    """
    import pickle
    import time as _time_mod

    _REPO_DIR = _UTILS_DIR.parent
    _PATHWAY_DIR = _REPO_DIR / 'projects' / 'pathway'
    _pth_model = str(_PATHWAY_DIR / 'model')
    _pth_data = str(_UTILS_DIR / 'data')
    _pth_shared_model = str(_UTILS_DIR / 'model')

    _CRITICAL_MATERIALS_DIR = _REPO_DIR / 'projects' / 'critical_materials'
    _pth_materials = _CRITICAL_MATERIALS_DIR / 'ampl_files'

    _pylib = str(_PATHWAY_DIR / 'pylib')
    if _pylib not in sys.path:
        sys.path.insert(0, _pylib)

    from ampl_object import AmplObject
    from ampl_preprocessor import AmplPreProcessor
    from ampl_collector import AmplCollector

    output_folder = _CRITICAL_MATERIALS_DIR / 'out' / case_study
    output_file = str(output_folder / '_Results.pkl')
    materials_output_file = str(output_folder / '_Materials_Results.pkl')
    output_folder.mkdir(parents=True, exist_ok=True)

    if skip_if_exists and save_pkl and os.path.exists(output_file) and os.path.exists(materials_output_file):
        print(f'[run_pathway] {case_study} — pkl exists, loading from disk.')
        with open(output_file, 'rb') as f:
            results = pickle.load(f)
        with open(materials_output_file, 'rb') as f:
            results.update(pickle.load(f))
        if build_dashboard:
            _build_materials_dashboard(results, case_study, _CRITICAL_MATERIALS_DIR)
        return results

    # --- file lists (mirrors run_pathway's plain-pathway body above) ---
    mod_1_path = [_pth_shared_model + '/QC_es_main.mod',
                  os.path.join(_pth_model, 'PES_main.mod'),
                  str(_pth_materials / 'Constraints.mod')]  # needs PHASE_WND/F_new/F_decom from PES_main.mod above

    if materials_recycling_process:
        mod_1_path.append(str(_pth_materials / 'Constraints_recycling_technologies.mod'))  # needs Constraints.mod's hooks above

    mod_1_path += [os.path.join(_pth_model, 'PES_obj_pathway.mod'),
                   os.path.join(_pth_model, 'PES_store_variables.mod')]

    mod_2_path = [os.path.join(_pth_model, 'EXTRA_INFOS.dat'),
                  _pth_data + '/QC_data.dat',
                  os.path.join(_pth_model, 'PES_scenarios.mod'),
                  _pth_data + '/EUD/out_eud.dat',
                  _pth_data + '/Techs/out_techs.dat',
                  _pth_data + '/Shares/out_shares.dat',
                  os.path.join(_pth_model, 'PES_data_pathway.dat'),
                  os.path.join(_pth_model, 'PES_data_decom_allowed_2020.dat'),
                  str(_pth_materials / 'Material_intensity.dat')]  # after TECHNOLOGIES is fully populated

    if materials_limit:
        mod_2_path.append(str(_pth_materials / 'Material_limits.dat'))  # manual limit_material / limit_material_year overrides

    if materials_recycling:
        mod_2_path.append(str(_pth_materials / 'Material_recycling.dat'))  # recycling_rate/costs, regenerated by run_build_rr.py from Recycling_rates.xlsx
        if not materials_recycling_cost:
            mod_2_path.append(str(_pth_materials / 'Material_recycling_zero_cost.mod'))  # overrides costs so Recycled_material is driven only by the recycling_rate ceiling
        if follow_objective_full:
            mod_2_path.append(str(_pth_materials / 'Material_recycling_objective_full.mod'))  # overrides recycling_objective_share to 100% of the achievable ceiling

    if materials_recycling_process:
        mod_2_path.append(str(_pth_materials / 'Material_recycling_process.dat'))  # regenerated by run_build_rt.py from Recycling_rates.xlsx
        #ADDED BY PAOLO (to validate)
        mod_2_path.append(str(_pth_materials / 'Material_recycling_process_enable.mod'))  # releases Recycled_material_process_total's upper bound (0 by default, see Constraints.mod)

    mod_2_path.append(os.path.join(_pth_model, 'fix.mod'))

    dat_path_base = [
        os.path.join(_pth_model, 'PES_data_years_active.dat'),
        os.path.join(_pth_model, 'PES_seq_opti.dat'),
        os.path.join(_pth_model, 'PES_data_set_AGE_2020.dat'),
    ]
    dat_path_0 = dat_path_base + [os.path.join(_pth_model, 'PES_data_remaining.dat')]
    dat_path = dat_path_base + [os.path.join(_pth_model, 'PES_data_remaining_wnd.dat')]

    _outlev = 1 if verbose else 0
    gurobi_opts = ' '.join([
        'predual=-1', 'method=2', f'crossover={crossover}', 'threads=0',
        'prepasses=3', 'barconvtol=1e-6', 'presolve=-1',
        'iisfind=1', f'outlev={_outlev}',
    ])
    ampl_options = {
        'show_stats': 1 if verbose else 0,
        'log_file': str(output_folder / 'log.txt'),
        'presolve': 0,
        'presolve_eps': 1e-6,
        'presolve_fixeps': 1e-6,
        'show_boundtol': 0,
        'gurobi_options': gurobi_opts,
        '_log_input_only': False,
    }

    class _SilentHandler:
        def output(self, kind, msg): pass
    _silence = _SilentHandler() if not verbose else None

    open(os.path.join(_pth_model, 'fix.mod'), 'w').close()

    ampl_0 = AmplObject(mod_1_path, mod_2_path, dat_path_0, ampl_options,
                        type_model='MO', working_dir=_pth_model)
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

    t_total = _time_mod.time()

    for i in range(len(ampl_pre.years_opti)):
        t_i = _time_mod.time()

        curr_years_wnd = ampl_pre.write_seq_opti(i).copy()
        ampl_pre.remaining_update(i)

        ampl = AmplObject(mod_1_path, mod_2_path, dat_path,
                          ampl_options, type_model='MO', working_dir=_pth_model)
        if _silence:
            ampl.ampl.set_output_handler(_silence)

        if gwp_budget is not False:
            budget_val = gwp_budget_val if gwp_budget is True else float(gwp_budget)
            ampl.set_params('max_co2_budget', budget_val)
        if CO2_neutrality_2050:
            ampl.set_params('gwp_limit', {('YEAR_2050'): CO2_neutrality_2050_val})
        if follow_objective or follow_objective_full:
            ampl.set_params('follow_objective', 1)

        solve_result, solve_result_num = ampl.run_ampl()
        sys.stdout.flush()
        if solve_result in ('infeasible', 'limit', 'failure'):
            raise RuntimeError(
                f"[run_pathway] Infeasible at window {i + 1} "
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

        print(f'[run_pathway] Window {i + 1}/{len(ampl_pre.years_opti)} done '
              f'in {_time_mod.time() - t_i:.1f}s', flush=True)

        if i == len(ampl_pre.years_opti) - 1:
            print(f'[run_pathway] Total time: {_time_mod.time() - t_total:.1f}s')
            ampl_collector.clean_collector()
            if save_pkl:
                ampl_collector.pkl()

    for k in materials_results:
        if materials_results[k] is not None:
            materials_results[k].dropna(how='all', inplace=True)

    # 'Recycled_material' is the TOTAL recycled, whichever approach(es) produced it: the simple-rate
    # approach's own var (always present, possibly all-zero) plus the competing-processes approach's
    # Recycled_material_process summed over process (only present when materials_recycling_process=True).
    if materials_results.get('Recycled_material_by_process') is not None:
        proc_summed = (materials_results['Recycled_material_by_process']['Recycled_material_process']
                       .groupby(level=['Years', 'Technologies', 'Materials']).sum())
        materials_results['Recycled_material']['Recycled_material'] = (
            materials_results['Recycled_material']['Recycled_material'].add(proc_summed, fill_value=0)
        )

    # Cumulative material demand, running sum over Years per (Technologies, Materials).
    # Material_content_year is annualised [t/year] (divided by 5), so it's multiplied back
    # by 5 before summing -- same convention the AMPL model itself uses for Material_content.
    mcy = materials_results['Material_content_year']['Material_content_year']
    cum_df = (mcy * 5).reset_index().sort_values(['Technologies', 'Materials', 'Years'])
    cum_df['Material_content_cumulative'] = (
        cum_df.groupby(['Technologies', 'Materials'])['Material_content_year'].cumsum()
    )
    materials_results['Material_content_cumulative'] = (
        cum_df.set_index(['Years', 'Technologies', 'Materials'])[['Material_content_cumulative']].sort_index()
    )

    # Same running-sum convention for Recycled_material.
    rec = materials_results['Recycled_material']['Recycled_material']
    rec_cum_df = (rec * 5).reset_index().sort_values(['Technologies', 'Materials', 'Years'])
    rec_cum_df['Recycled_material_cumulative'] = (
        rec_cum_df.groupby(['Technologies', 'Materials'])['Recycled_material'].cumsum()
    )
    materials_results['Recycled_material_cumulative'] = (
        rec_cum_df.set_index(['Years', 'Technologies', 'Materials'])[['Recycled_material_cumulative']].sort_index()
    )

    # Same running-sum convention for Recycling_benefit.
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

    # --- merge everything into a single dict, like the plain-pathway path above ---
    results = dict(ampl_collector.results)
    results.update(materials_results)
    if build_dashboard:
        _build_materials_dashboard(results, case_study, _CRITICAL_MATERIALS_DIR)
    return results