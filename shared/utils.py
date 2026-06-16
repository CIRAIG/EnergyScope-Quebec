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
        save_pkl: bool = False,
        description: str = '',
        plot: bool = False,
        skip_if_exists: bool = False,
        verbose: bool = False,
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
    save_pkl : bool
        If True, writes results to out/<case_study>/_Results.pkl. Default False.
    description : str
        Short description stored in the recap CSV (only when save_pkl=True).
    plot : bool
        If True, generates HTML charts via plot_results after the run. Default False.
    skip_if_exists : bool
        If True and save_pkl=True, skip the optimisation when a pkl already
        exists and return the saved results instead.
    verbose : bool
        If True, print AMPL statistics and Gurobi solver log. Default False.

    Returns
    -------
    dict
        AmplCollector.results — ~30 named pandas DataFrames with the same
        structure expected by plot_results.run().
    """
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
        with open(output_file, 'rb') as _f:
            return pickle.load(_f)

    _extra = list(extra_files or [])

    mod_1_path = [
        os.path.join(_pth_shared_model, 'QC_es_main.mod'),
        os.path.join(_pth_model,        'QC_es_pathway.mod'),
        os.path.join(_pth_model,        'QC_es_obj_pathway.mod'),
        os.path.join(_pth_model,        'PES_store_variables.mod'),
    ]
    mod_2_path = [
        os.path.join(_pth_model, 'EXTRA_INFOS.dat'),
        os.path.join(_pth_data,  'QC_data.dat'),
        os.path.join(_pth_model, 'PES_scenarios.mod'),
        os.path.join(_pth_data,  'EUD/out_eud.dat'),
        os.path.join(_pth_data,  'Techs/out_techs.dat'),
        os.path.join(_pth_data,  'Shares/out_shares.dat'),
        os.path.join(_pth_model, 'QC_data_pathway.dat'),
        os.path.join(_pth_model, 'PES_data_decom_allowed_2020.dat'),
    ] + _extra + [
        os.path.join(_pth_model, 'fix.mod'),
    ]

    dat_path_base = [
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
            ampl.set_params('gwp_limit_transition', budget_val)

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