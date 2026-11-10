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
        backend: str = 'ampl',
        solver_options: dict = None,
        mip_gap: float = 1e-4,
) -> Result:
    """Solve a snapshot model and return its results.

    Parameters
    ----------
    model : Model
        Model returned by ``load_snapshot``. Files appended to ``model.files`` after that (for example
        ``('mod', 'my_changes.dat')``) are applied on top of the standard data, with either backend.
    apply_postprocessing : bool
        Collapse the single-year index and add the ``postprocessing`` tables (default True).
    backend : {'ampl', 'julia'}
        'ampl'  : AMPL (default; needs AMPL and a solver license, Gurobi unless ``solver_options`` says otherwise).
        'julia' : open-source JuMP + HiGHS model (no AMPL, no license). Same ``Result`` object as the AMPL route.
    solver_options : dict, optional
        AMPL route only. Default ``{'solver': 'gurobi', 'solver_msg': 0}``.
    mip_gap : float
        Julia route only: relative accuracy requested from HiGHS (1e-4 is its default).
    """
    if backend == 'julia':
        year = getattr(model, 'snapshot_year', None)
        if year is None:
            raise ValueError("backend='julia' needs a model built by load_snapshot(year).")
        from shared.julia_backend import run_snapshot as _run_snapshot_julia
        changes = [path for _, path in model.files[model.snapshot_n_base_files:]]
        res, _ = _run_snapshot_julia(year, mip_gap=mip_gap, changes=changes, scenario=model.snapshot_scenario)
    elif backend == 'ampl':
        if solver_options is None:
            solver_options = {
                'solver': 'gurobi',
                'solver_msg': 0,
            }
        es = Energyscope(model=model, solver_options=solver_options)
        res = es.calc()
    else:
        raise ValueError(f"backend must be 'ampl' or 'julia', not {backend!r}")
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

    model = Model(files)
    # Remembered for run_model(..., backend='julia'), which rebuilds the same snapshot from the year
    model.snapshot_year = year
    model.snapshot_scenario = scenario
    model.snapshot_n_base_files = len(files)
    return model


class PathwayResults(dict):
    """Results dictionary of run_pathway (a plain dict of DataFrames) that remembers its output folder.

    ``plot_results.run(results, case_study=...)`` uses ``out_dir`` to write the charts next to the
    run (``projects/pathway/out`` for AMPL, ``projects/opensource/out`` for Julia).
    """
    def __init__(self, data=(), out_dir=None):
        super().__init__(data)
        self.out_dir = out_dir


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
        backend: str = 'ampl',
        mip_gap: float = None,
        time_limit: float = None,
        materials: bool = False,
        **materials_options,
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
        True   → uses the built-in default (883 428 kt).
        float  → your custom cap.
        NOTE: requires the gwp_limit_transition constraint to be active in the model.
    extra_files : list of str, optional
        Paths to additional .mod or mixed .dat files injected into the model
        after the standard data files but before fix.mod.
        Use for extra constraints, scenario overrides, or custom parameters.
    save_pkl : bool, optional
        If True, writes results to out/<case_study>/_Results.pkl (projects/pathway/out for AMPL,
        projects/opensource/out for Julia). Default None,
        which resolves to False for materials=False (unchanged) and True for
        materials=True (matches run_pathway_materials' own historical default).
    description : str
        Short description stored in the recap CSV (only when save_pkl=True).
    plot : bool
        If True, generates HTML charts via plot_results after the run. Default False.
    skip_if_exists : bool
        If True and save_pkl=True, skip the optimisation when a pkl already
        exists and return the saved results instead.
    verbose : bool
        If True, print AMPL statistics and Gurobi solver log. Default False.
    backend : {'ampl', 'julia'}
        'ampl'  : AMPL + Gurobi (default).
        'julia' : open-source JuMP + HiGHS model, no AMPL and no license. Same results dict, same output folder, same
                  plots. Perfect foresight (N_year_opti=30) and myopic runs (shorter windows) both work, with the
                  same windows as AMPL. `extra_files` must be plain data files (let / for / fix / subject to).
    mip_gap : float, optional
        Relative MIP gap at which the solver stops. Julia backend: default 5e-4 (a much tighter value, e.g. 1e-4, can make
        the solve far longer: the root relaxation of the full pathway is already at about 1.5e-4). With ``materials=True`` it
        is forwarded to run_pathway_materials. Other AMPL runs: set it in the solver options instead.
    time_limit : float, optional
        Julia backend only: time limit of the solver for each window [s], default 3600. When it is reached, run_pathway
        stops with an error that says so; raise ``time_limit`` or loosen ``mip_gap``.
    materials : bool
        If True, runs projects/critical_materials' run_pathway_materials (Constraints.mod, material data,
        extra material-flow results). Default False: identical behaviour to before this parameter existed.
    **materials_options
        Only with materials=True, forwarded to run_pathway_materials: materials_limit,
        materials_recycling, materials_recycling_cost, force_max_recycling,
        force_immediate_recycled_use, materials_recycling_process, mip_gap, build_dashboard,
        open_dashboard. See its docstring.

    Returns
    -------
    dict
        AmplCollector.results — ~30 named pandas DataFrames with the same
        structure expected by plot_results.run() — plus, when materials=True,
        the additional material-flow results (see run_pathway_materials).
    """
    if materials:
        if backend != 'ampl':
            raise ValueError("materials=True is only available with backend='ampl': the critical-materials model "
                             "has no Julia version.")
        if time_limit is not None:
            raise ValueError("time_limit is only used by backend='julia'.")
        if mip_gap is not None:
            materials_options['mip_gap'] = mip_gap
        _cm_dir = str(_UTILS_DIR.parent / 'projects' / 'critical_materials')
        if _cm_dir not in sys.path:
            sys.path.insert(0, _cm_dir)
        from run_pathway_materials import run_pathway_materials
        run_options = dict(N_year_opti=N_year_opti, N_year_overlap=N_year_overlap, gwp_budget=gwp_budget,
                           extra_files=extra_files, description=description, skip_if_exists=skip_if_exists,
                           verbose=verbose, save_pkl=True if save_pkl is None else save_pkl)
        return run_pathway_materials(case_study, run_options, **materials_options)
    if materials_options:
        raise ValueError(f"{sorted(materials_options)} were passed but materials=False, so they'd be silently "
                         f"ignored. Pass materials=True too.")
    if save_pkl is None:
        save_pkl = False  # plain run_pathway's own historical default
    if backend == 'ampl' and (mip_gap is not None or time_limit is not None):
        raise ValueError("mip_gap and time_limit are only used by backend='julia' (with AMPL, set the solver options).")

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

    if backend not in ('ampl', 'julia'):
        raise ValueError(f"backend must be 'ampl' or 'julia', not {backend!r}")
    # AMPL results go to projects/pathway/out, Julia results to projects/opensource/out (kept apart)
    _out_root     = _REPO_DIR / 'projects' / 'opensource' / 'out' if backend == 'julia' else _PATHWAY_DIR / 'out'
    output_folder = str(_out_root / case_study)
    output_file   = os.path.join(output_folder, '_Results.pkl')

    if skip_if_exists and save_pkl and os.path.exists(output_file):
        print(f'[run_pathway] {case_study} — pkl exists, loading from disk.')
        try:
            with open(output_file, 'rb') as _f:
                return PathwayResults(pickle.load(_f), out_dir=output_folder)
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
        'presolve':        1,
        'presolve_eps':    1e-6,
        'presolve_fixeps': 1e-6,
        'show_boundtol':   0,
        'gurobi_options':  gurobi_opts,
        '_log_input_only': False,
    }

    if backend == 'ampl':
        open(os.path.join(_pth_model, 'fix.mod'), 'w').close()

    class _SilentHandler:
        def output(self, kind, msg): pass
    _silence = _SilentHandler() if not verbose else None

    if backend == 'julia':
        import tempfile as _tempfile
        from shared.julia_pathway import JuliaSession, julia_amplobject_class, window_source
        _jl_tmp = _tempfile.TemporaryDirectory()      # copies of the files the AMPL routine rewrites: repository untouched
        _JuliaObject = julia_amplobject_class()
        ampl_0 = window_source(_pth_model, _jl_tmp.name)
    else:
        ampl_0 = AmplObject(mod_1_path, mod_2_path, dat_path_0, ampl_options,
                            type_model='MO', working_dir=_pth_model)
        if _silence:
            ampl_0.ampl.set_output_handler(_silence)
        ampl_0.clean_history()
    ampl_pre       = AmplPreProcessor(ampl_0, N_year_opti, N_year_overlap)
    ampl_collector = AmplCollector(ampl_pre, output_file, description)

    if backend == 'julia':
        # one Julia process for all windows; it reads the sets of window i from the files AmplPreProcessor writes for AMPL
        _jl_session = JuliaSession(os.path.join(_jl_tmp.name, 'julia'), len(ampl_pre.years_opti), changes=_extra,
                                   mip_gap=5e-4 if mip_gap is None else mip_gap,
                                   time_limit=3600.0 if time_limit is None else time_limit)
        _jl_session.write_windows(ampl_pre)

    t_total = _time_mod.time()

    try:
        for i in range(len(ampl_pre.years_opti)):
            t_i = _time_mod.time()

            curr_years_wnd = ampl_pre.write_seq_opti(i).copy()
            ampl_pre.remaining_update(i)

            if backend == 'julia':
                ampl = _JuliaObject(_jl_session, i)
            else:
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
                _reason = {
                    'infeasible': 'the model is infeasible',
                    'limit': 'the solver reached its time limit before the requested accuracy'
                             + (' (raise time_limit, or loosen mip_gap)' if backend == 'julia' else ''),
                    'failure': 'the solver failed',
                }[solve_result]
                raise RuntimeError(
                    f"[run_pathway] Window {i + 1} ({ampl_pre.years_opti[i]}) of case_study='{case_study}': {_reason}."
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
    finally:
        if backend == 'julia':                  # also after an error: release Julia's files, remove the temporary folder
            _jl_session.close()
            try:
                _jl_tmp.cleanup()
            except OSError:
                pass

    if plot:
        _plot_src = str(_PATHWAY_DIR / 'src' / 'plot_results.py')
        _spec = _ilu.spec_from_file_location('plot_results', _plot_src)
        _pr   = _ilu.module_from_spec(_spec)
        _spec.loader.exec_module(_pr)
        _pr.run(ampl_collector.results,
                case_study=case_study,
                outdir=os.path.join(output_folder, 'graphs'))

    return PathwayResults(ampl_collector.results, out_dir=output_folder)