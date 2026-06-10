from pathlib import Path
import pandas as pd
from energyscope.models import Model
from energyscope.energyscope import Energyscope
from energyscope.result import postprocessing, Result

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