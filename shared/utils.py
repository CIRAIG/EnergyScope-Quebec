import os
import re
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
        force_max_recycling: bool = False,
        force_immediate_recycled_use: bool = True,
        materials_recycling_process: bool = False,
        build_dashboard: bool = True,
        open_dashboard: bool = True,
        iis_find: bool = True,
        mip_gap: float = None,
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
    materials_limit, materials_recycling, materials_recycling_cost, force_max_recycling,
    force_immediate_recycled_use, materials_recycling_process,
    build_dashboard : bool / float / int
        Only meaningful when materials=True — see _run_pathway_materials's
        docstring at the end of this file. Ignored (no-op) when materials=False,
        matching plain run_pathway's behaviour before this parameter existed.
    open_dashboard : bool
        If False, the dashboard is still built (when plot=True / materials=True
        with build_dashboard=True) but its browser tab isn't auto-opened.
        Default True. Set to False in batch/regen scripts looping over many
        case studies, to avoid a tab popping open per case.

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
            extra_files=extra_files,
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
            force_max_recycling=force_max_recycling,
            force_immediate_recycled_use=force_immediate_recycled_use,
            materials_recycling_process=materials_recycling_process,
            build_dashboard=build_dashboard,
            open_dashboard=open_dashboard,
            iis_find=iis_find,
            mip_gap=mip_gap,
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
                outdir=os.path.join(output_folder, 'graphs'),
                auto_open=open_dashboard)

    return ampl_collector.results


#ADDED BY PAOLO (to validate)
def _build_materials_dashboard(results, case_study, pth_critical_materials, open_dashboard=True):
    """Build the dashboard of a materials=True run in out/<case_study>/graphs/.

    plot_results.run() writes the standard pages, then Plot_functions.build_materials_dashboard()
    adds the materials pages to the same folder and rebuilds index.html; out/index.html (scenario
    selector) is refreshed too. open_dashboard=False writes the files without opening the browser.
    Imports are local to avoid the plotly cost when build_dashboard=False.
    """
    _pathway_src = str(_UTILS_DIR.parent / 'projects' / 'pathway' / 'src')
    if _pathway_src not in sys.path:
        sys.path.insert(0, _pathway_src)
    import plot_results
    # auto_open=False: this index.html has no materials pages yet, only the rebuilt one below should open
    plot_results.run(results, case_study=case_study,
                      outdir=str(pth_critical_materials / 'out' / case_study / 'graphs'),
                      auto_open=False)

    if str(pth_critical_materials) not in sys.path:
        sys.path.insert(0, str(pth_critical_materials))
    from Plot_functions import build_materials_dashboard, build_scenario_selector
    build_materials_dashboard(results, case_study, auto_open=open_dashboard)
    build_scenario_selector()


#ADDED BY PAOLO (to validate)
def _run_pathway_materials(
        case_study: str,
        *,
        N_year_opti: int = 30,
        N_year_overlap: int = 0,
        gwp_budget=False,
        extra_files=None,
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
        materials_recycling_cost: bool = False,
        force_max_recycling: bool = False,
        force_immediate_recycled_use: bool = True,
        materials_recycling_process: bool = False,
        build_dashboard: bool = True,
        open_dashboard: bool = True,
        iis_find: bool = True,
        mip_gap: float = None,
) -> dict:
    """Run the transition pathway with critical-materials tracking (called by run_pathway(materials=True)).

    Same rolling-horizon loop as run_pathway, but projects/critical_materials' Constraints.mod and data
    files are loaded, the material-flow variables are extracted window by window, and results, pkl and
    dashboard go to projects/critical_materials/out/<case_study>/.

    Parameters
    ----------
    case_study, N_year_opti, N_year_overlap, gwp_budget, extra_files, description, save_pkl,
    skip_if_exists, verbose :
        Same as run_pathway.
    gwp_budget_val : float
        Cap used when gwp_budget=True [kt CO2-eq.]. Default 1 224 935.
    CO2_neutrality_2050 : bool
        If True, fixes the 2050 gwp_limit to CO2_neutrality_2050_val. Default True.
    CO2_neutrality_2050_val : float
        2050 GWP limit [kt CO2-eq.]. Default 0.
    crossover : int
        Gurobi crossover option (0 = off). Default 0.
    materials_limit : bool
        If True, loads Material_limits.dat (limit_material / limit_material_year caps). Default False.
    materials_recycling : bool
        If True, loads Material_recycling.dat (recycling rates and costs). Default False.
    materials_recycling_cost : bool
        If True, recycling has a real cost/benefit and Recycled_material is an economic choice;
        if False, these costs are zeroed. Default True when called through run_pathway.
    force_max_recycling : bool
        If True, Recycled_material is forced to the recycling_rate ceiling. Meant for
        materials_recycling_cost=False, where it is otherwise solver-arbitrary. Default False.
    force_immediate_recycled_use : bool
        If True, Used_recycled_material = min(gross demand, available) every year (big-M
        complementarity in Constraints.mod), so recycled material is not banked in Material_stock
        while demand remains. False restores the old banking behaviour. Default True. The ~290
        extra binaries can slow the MIP root node on some scenarios.
    materials_recycling_process : bool
        If True, adds the competing recycling processes (Constraints_recycling_technologies.mod,
        Material_recycling_process.dat). Default False.
    build_dashboard : bool
        If True, builds the plot_results + materials dashboard after the run. Default True.
    open_dashboard : bool
        If False, the dashboard is built but not opened in the browser. Default True.
    iis_find : bool
        If False, skips Gurobi's IIS computation on infeasibility. Default True.
    mip_gap : float, optional
        Gurobi MIPGap. Default None keeps Gurobi's own (~1e-4). e.g. 0.001 stops within 0.1% of the
        best bound; prefer it to interrupting a solve, which aborts without any results.

    Notes
    -----
    stocking_price (artificial [$/t/yr] cost on Material_stock, see Constraints.mod) is set
    automatically: 1 if materials_limit=True and force_immediate_recycled_use=False, else 1000.
    With force_immediate_recycled_use=True a price of 0 makes the MIP very slow (no integer
    solution after 10+ min instead of ~6 min with 1000).

    Returns
    -------
    dict
        The standard run_pathway results plus, as DataFrames: 'Material_content_year',
        'Decommissioned_material', 'Recycled_material', 'Disposed_material' [t/year],
        'Recycling_benefit' [M$/year, discounted], 'Used_recycled_material', 'Material_stock',
        'Net_demand' (gross minus Used_recycled_material, by (Years, Materials)), the running totals
        over Years 'Material_content_cumulative', 'Recycled_material_cumulative',
        'Recycling_benefit_cumulative', 'Net_demand_cumulative', and 'limit_material_year'
        (None without materials_limit), 'Recycled_material_by_process' (materials_recycling_process
        only), plus the scalars 'C_material' and 'C_material_recycling_tech'.
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
            _build_materials_dashboard(results, case_study, _CRITICAL_MATERIALS_DIR, open_dashboard=open_dashboard)
        return results

    # --- file lists (mirrors run_pathway's plain-pathway body above) ---
    mod_1_path = [_pth_shared_model + '/QC_es_main.mod',
                  os.path.join(_pth_model, 'PES_main.mod'),
                  str(_pth_materials / 'Constraints.mod'),  # needs PHASE_WND/F_new/F_decom from PES_main.mod above
                  str(_pth_materials / 'Subtechs.mod')]  # PV/wind sub-technologies (the aggregated ones stay at capacity 0)

    if materials_recycling_process:
        mod_1_path.append(str(_pth_materials / 'Constraints_recycling_technologies.mod'))  # needs Constraints.mod's hooks above

    mod_1_path += [os.path.join(_pth_model, 'PES_obj_pathway.mod'),
                   os.path.join(_pth_model, 'PES_store_variables.mod')]

    mod_2_path = [os.path.join(_pth_model, 'EXTRA_INFOS.dat'),
                  _pth_data + '/QC_data.dat',
                  str(_pth_materials / 'Subtechs_sets.dat'),
                  os.path.join(_pth_model, 'PES_scenarios.mod'),
                  _pth_data + '/EUD/out_eud.dat',
                  _pth_data + '/Techs/out_techs.dat',
                  str(_pth_materials / 'Subtechs_techs.dat'),
                  _pth_data + '/Shares/out_shares.dat',
                  os.path.join(_pth_model, 'PES_data_pathway.dat'),
                  os.path.join(_pth_model, 'PES_data_decom_allowed_2020.dat'),
                  str(_pth_materials / 'Subtechs_pathway.dat'),
                  str(_pth_materials / 'Material_intensity.dat'),  # after TECHNOLOGIES is fully populated
                  str(_pth_materials / 'Material_mob_family_exclusion.dat')]  # always loaded: MATERIAL_TECHS then excludes the _SD/_MD/_LD/_ELD mobility variants

    if materials_limit:
        mod_2_path.append(str(_pth_materials / 'Material_limits.dat'))  # manual limit_material / limit_material_year overrides

    if materials_recycling:
        mod_2_path.append(str(_pth_materials / 'Material_recycling.dat'))  # recycling_rate/costs, regenerated by run_build_rr.py from Recycling_rates.xlsx

    if materials_recycling_process:
        mod_2_path.append(str(_pth_materials / 'Material_recycling_process.dat'))  # regenerated by run_build_rt.py from Recycling_rates.xlsx

    mod_2_path += list(extra_files or [])  # same convention as plain run_pathway: after standard data, before fix.mod
    mod_2_path.append(os.path.join(_pth_model, 'fix.mod'))

    # main's years_active / remaining_years / AGE tables + the sub-technologies' rows (see subtechs.py)
    if str(_CRITICAL_MATERIALS_DIR) not in sys.path:
        sys.path.insert(0, str(_CRITICAL_MATERIALS_DIR))
    from subtechs import merged_tables
    import tempfile
    _tables_dir = tempfile.TemporaryDirectory()  # deleted when the run ends
    years_active_file, remaining_file, age_file = merged_tables(_pth_model, _tables_dir.name)

    dat_path_base = [
        years_active_file,
        os.path.join(_pth_model, 'PES_seq_opti.dat'),
        age_file,
    ]
    dat_path_0 = dat_path_base + [remaining_file]
    dat_path = dat_path_base + [os.path.join(_pth_model, 'PES_data_remaining_wnd.dat')]

    _outlev = 1 if verbose else 0
    #ADDED BY PAOLO (to validate)
    # iis_find=False skips Gurobi's IIS computation on infeasibility (can take longer than the solve itself)
    gurobi_opts_parts = [
        'predual=-1', 'method=2', f'crossover={crossover}', 'threads=0',
        'prepasses=3', 'barconvtol=1e-6', 'presolve=-1',
        f'iisfind={1 if iis_find else 0}', f'outlev={_outlev}',
    ]
    # mip_gap is opt-in (mipfocus=1 was tried and made some scenarios get stuck at the MIP root node)
    if mip_gap is not None:
        gurobi_opts_parts.append(f'mipgap={mip_gap}')
    gurobi_opts = ' '.join(gurobi_opts_parts)
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
        'limit_material_year': None,
        'Material_content_year': None,
        'Decommissioned_material': None,
        'Recycled_material': None,
        'Recycled_material_by_process': None,
        'Disposed_material': None,
        'Recycling_benefit': None,
        'Used_recycled_material': None,
        'Material_stock': None,
        'C_material': None,
        'C_material_recycling_tech': None,
    }

    t_total = _time_mod.time()

    for i in range(len(ampl_pre.years_opti)):
        t_i = _time_mod.time()

        curr_years_wnd = ampl_pre.write_seq_opti(i).copy()
        ampl_pre.remaining_update(i, file_in=remaining_file)

        ampl = AmplObject(mod_1_path, mod_2_path, dat_path,
                          ampl_options, type_model='MO', working_dir=_pth_model)
        if _silence:
            ampl.ampl.set_output_handler(_silence)

        if i == 0 and materials_limit:
            # Static input, same in every window: extract once. Stays None without materials_limit
            # (the "no limits" state plot_material_limit_heatmap expects).
            materials_results['limit_material_year'] = ampl.get_elem('limit_material_year', type_of_elem='Param')

        if gwp_budget is not False:
            budget_val = gwp_budget_val if gwp_budget is True else float(gwp_budget)
            ampl.set_params('max_co2_budget', budget_val)
        if CO2_neutrality_2050:
            ampl.set_params('gwp_limit', {('YEAR_2050'): CO2_neutrality_2050_val})
        #ADDED BY PAOLO (to validate)
        if materials_recycling and not materials_recycling_cost:
            # No cost/benefit: the solver has no reason to recycle, use force_max_recycling to pin the amount
            ampl.ampl.eval('let {tec in TECHNOLOGIES, mat in MATERIALS} recycling_cost[tec,mat] := 0;')
            ampl.ampl.eval('let {mat in MATERIALS} primary_material_cost[mat] := 0;')
            ampl.ampl.eval('let {mat in MATERIALS} disposal_cost[mat] := 0;')
        if force_max_recycling:
            # Recycled_material = recycling_rate ceiling (Constraints.mod's recycled_material_forced_max)
            ampl.set_params('force_recycling_max', 1)
        if not force_immediate_recycled_use:
            # Constraints.mod defaults to 1 (big-M complementarity): only override to disable it
            ampl.set_params('force_immediate_recycled_use', 0)
        # stocking_price from the run config: 1 with limits and force_immediate_recycled_use=False, else 1000
        # (0 with force_immediate_recycled_use=True leaves the MIP relaxation flat: no integer solution for 10+ min)
        _stocking_price = 1 if (materials_limit and not force_immediate_recycled_use) else 1000
        ampl.set_params('stocking_price', _stocking_price)
        if materials_recycling_process:
            # Release Recycled_material_process_total's upper bound (0 by default) so the process equalities drive it
            ampl.ampl.eval('let {tec in TECHNOLOGIES, mat in MATERIALS} recycled_material_process_total_ub[tec,mat] := Infinity;')

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

        # Same merge, for variables indexed by {Years,Materials} only (already aggregated across technologies)
        for var_name in ('Used_recycled_material', 'Material_stock'):
            df = ampl.get_elem(var_name)
            df.index.names = ['Years', 'Materials']
            df = df.loc[df.index.get_level_values('Years').isin(curr_years_wnd), :]
            if materials_results[var_name] is None:
                materials_results[var_name] = df
            else:
                combined = pd.concat([materials_results[var_name], df])
                materials_results[var_name] = combined.loc[~combined.index.duplicated(keep='last')].sort_index()

        if materials_recycling_process:
            df_proc = ampl.get_elem('Recycled_material_process')
            df_proc.index.names = ['Years', 'Technologies', 'Materials', 'RECYCLING_PROCESS']
            df_proc = df_proc.loc[df_proc.index.get_level_values('Years').isin(curr_years_wnd), :]
            if materials_results.get('Recycled_material_by_process') is None:
                materials_results['Recycled_material_by_process'] = df_proc
            else:
                combined = pd.concat([materials_results['Recycled_material_by_process'], df_proc])
                materials_results['Recycled_material_by_process'] = combined.loc[~combined.index.duplicated(keep='last')].sort_index()

        #ADDED BY PAOLO (to validate)
        # Whole-horizon scalars (no Years index): the last window's value covers the full horizon
        materials_results['C_material'] = float(ampl.get_elem('C_material').iloc[0, 0])
        materials_results['C_material_recycling_tech'] = float(ampl.get_elem('C_material_recycling_tech').iloc[0, 0])

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
        if isinstance(materials_results[k], pd.DataFrame):
            materials_results[k].dropna(how='all', inplace=True)

    # 'Recycled_material' = total recycled: the simple-rate variable plus the competing-process one (summed over process)
    if materials_results.get('Recycled_material_by_process') is not None:
        proc_summed = (materials_results['Recycled_material_by_process']['Recycled_material_process']
                       .groupby(level=['Years', 'Technologies', 'Materials']).sum())
        materials_results['Recycled_material']['Recycled_material'] = (
            materials_results['Recycled_material']['Recycled_material'].add(proc_summed, fill_value=0)
        )

    # Cumulative demand: running sum over Years per (Technologies, Materials), annualised values * 5 as in Constraints.mod
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

    # Net demand = gross (mobility variants dropped, as in MATERIAL_TECHS) - Used_recycled_material,
    # i.e. the LHS of material_content_year_limit
    if str(_CRITICAL_MATERIALS_DIR) not in sys.path:
        sys.path.insert(0, str(_CRITICAL_MATERIALS_DIR))
    from Plot_functions import _drop_mob_size_variants

    gross_by_year_mat = (_drop_mob_size_variants(materials_results['Material_content_year']['Material_content_year'])
                         .groupby(['Years', 'Materials']).sum())
    used_by_year_mat = materials_results['Used_recycled_material']['Used_recycled_material']
    materials_results['Net_demand'] = gross_by_year_mat.sub(used_by_year_mat, fill_value=0).to_frame('Net_demand')

    # Cumulative net demand per Materials (flat where Net_demand is 0, unlike Material_content_cumulative), same * 5 convention
    net_cum_df = (materials_results['Net_demand']['Net_demand'] * 5).reset_index().sort_values(['Materials', 'Years'])
    net_cum_df['Net_demand_cumulative'] = (
        net_cum_df.groupby(['Materials'])['Net_demand'].cumsum()
    )
    materials_results['Net_demand_cumulative'] = (
        net_cum_df.set_index(['Years', 'Materials'])[['Net_demand_cumulative']].sort_index()
    )

    if save_pkl:
        with open(materials_output_file, 'wb') as f:
            pickle.dump(materials_results, f)

    # --- merge everything into a single dict, like the plain-pathway path above ---
    results = dict(ampl_collector.results)
    results.update(materials_results)
    if build_dashboard:
        _build_materials_dashboard(results, case_study, _CRITICAL_MATERIALS_DIR, open_dashboard=open_dashboard)
    return results