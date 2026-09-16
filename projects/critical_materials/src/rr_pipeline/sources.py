"""Load the literature source workbook (Recycling_rates.xlsx) into tidy pandas
DataFrames -- recycling-rate counterpart to mi_pipeline/sources.py.

This file is treated as read-only input: nothing in this module writes to it.

Unlike mi_pipeline's MI_Energy/MI_Vehicles/MI_H2 (material mass per GW or per
vehicle), a recycling rate is already a dimensionless fraction [0,1] -- no
per-vehicle unit conversion (ref_size, g/vehicle) is needed here, which is
what keeps this pipeline noticeably simpler than mi_pipeline's.
"""
from pathlib import Path

import pandas as pd

from mi_pipeline.sources import load_materials as _load_materials

_PROJ_ROOT = Path(__file__).resolve().parents[2]  # .../projects/critical_materials
SOURCE_XLSX = _PROJ_ROOT / 'excel_files' / 'Recycling_rates.xlsx'


def load_materials(path=SOURCE_XLSX):
    """{full_name: short_code}, same 'Materials' sheet convention as
    mi_pipeline.sources.load_materials (verified byte-identical between the
    two workbooks) -- just pointed at this workbook by default."""
    return _load_materials(path)


YEARS_INT = [2020, 2025, 2030, 2035, 2040, 2045, 2050]


def _load_rr_sheet(sheet_name, path=SOURCE_XLSX):
    """Return `sheet_name` as {year_int: DataFrame(short material code x
    sub-technology/category)}, values already dimensionless recycling-rate
    fractions. Sheet layout: one table, one row per material (row 3+); each
    sub-technology is a group of 7 columns (2020..2050) -- row 1 names the
    sub-technology on the first column of its group (blank on the other 6,
    forward-filled here), row 2 gives the year for every column. Literal,
    hand-editable input -- nothing computed here."""
    import openpyxl
    materials = load_materials(path)
    wb = openpyxl.load_workbook(path, data_only=True)
    ws = wb[sheet_name]

    subtech_by_col = {}
    current_subtech = None
    for c in range(2, ws.max_column + 1):
        label = ws.cell(row=1, column=c).value
        if label is not None:
            current_subtech = label
        year_cell = ws.cell(row=2, column=c).value
        if current_subtech is None or year_cell is None:
            continue
        subtech_by_col[c] = (current_subtech, int(year_cell))

    rows_by_year = {year_int: {} for year_int in YEARS_INT}
    for r in range(3, ws.max_row + 1):
        name = ws.cell(row=r, column=1).value
        if name is None:
            continue
        if name not in materials:
            raise ValueError(f"{sheet_name} has a material with no short-code mapping: {name!r}")
        short = materials[name]
        for c, (subtech, year_int) in subtech_by_col.items():
            value = ws.cell(row=r, column=c).value
            if value is not None:
                rows_by_year[year_int].setdefault(short, {})[subtech] = value

    subtechs = sorted({subtech for subtech, _year in subtech_by_col.values()})
    return {
        year_int: pd.DataFrame.from_dict(rows_by_year[year_int], orient='index', columns=subtechs)
        for year_int in YEARS_INT
    }


def load_rr_energy(path=SOURCE_XLSX):
    """Electricity/fuel-cell sub-technologies (Sol_*/Wind_*/Nuclear_*/...),
    same sub-tech naming as mi_pipeline.sources.load_mi_energy's MI_Energy.
    Empty (all-NaN) until RR_Energy is populated in the workbook."""
    return _load_rr_sheet('RR_Energy', path)


def load_rr_vehicles(path=SOURCE_XLSX):
    """Road-vehicle recycling rates -- covers both private (car/SUV) and
    public/freight (bus/coach/schoolbus/LCV/truck) mobility, split by
    powertrain: 'Vehicle_elec' (EV/hybrid), 'Vehicle_icev' (combustion),
    'Vehicle_fcv' (hydrogen fuel cell) -- see the Mapping sheet. RR_Vehicles_
    Public was merged into this sheet (same powertrain-level rates apply
    regardless of private/public/freight use)."""
    return _load_rr_sheet('RR_Vehicles', path)


def load_rr_h2(path=SOURCE_XLSX):
    """Electrolyzer recycling rates (Alkaline_Electrolysis/SOEC_Electrolysis/
    PEM_electrolysis), same sub-tech naming as mi_pipeline.sources.load_mi_h2.
    Empty (all-NaN) until populated."""
    return _load_rr_sheet('RR_H2', path)


def load_rr_global(path=SOURCE_XLSX):
    """DataFrame indexed by short material code, columns 'YEAR_2020'..
    'YEAR_2050' -- read directly from RR_Global's own year columns (B-H),
    which hold the literal per-year recycling_rate to use, hand-editable
    directly in the workbook -- nothing computed here. RR_Global's own further
    per-source literature columns (further right, Graedel/etc + Source/
    Reference year/Coverage) stay purely informational/reference, not read by
    the pipeline. A material-level fallback recycling_rate, used for
    technologies with no tech-specific mapping at all (mapping_type=
    'not_mapped') -- techs WITH a specific mapping (RR_Energy/RR_Vehicles/
    RR_H2) never get overridden by this. Not every
    material has a value (e.g. Concrete/Glass/Polymers aren't covered by this
    kind of literature) -- those stay absent, AMPL default (0) applies."""
    materials = load_materials(path)
    df = pd.read_excel(path, sheet_name='RR_Global', index_col=0)
    df = df.loc[df.index.notna()]
    unmapped = [name for name in df.index if name not in materials]
    if unmapped:
        raise ValueError(f"RR_Global has materials with no short-code mapping: {unmapped}")
    year_cols = [c for c in df.columns if isinstance(c, (int, float))]
    df = df[year_cols].rename(columns={c: f'YEAR_{int(c)}' for c in year_cols})
    df.index = df.index.map(materials)
    return df


def _load_cost_sheet(sheet_name, path=SOURCE_XLSX):
    """{short_code: value} from a dedicated cost sheet (Cost_recycling_global /
    Cost_material_global / Cost_disposal_global) -- column A is the material
    full name (index), column B onward are one or more literature-source
    value columns (same 'always take the first column' convention as
    load_rr_global). Materials with no value are absent from the dict."""
    materials = load_materials(path)
    df = pd.read_excel(path, sheet_name=sheet_name, index_col=0)
    df = df.loc[df.index.notna()]
    unmapped = [name for name in df.index if name not in materials]
    if unmapped:
        raise ValueError(f"{sheet_name} has materials with no short-code mapping: {unmapped}")
    first_col = df.iloc[:, 0]
    return {materials[name]: float(v) for name, v in first_col.items() if pd.notna(v)}


def load_rr_costs(path=SOURCE_XLSX):
    """{short_code: (recycling_cost, primary_material_cost)} in CAD/t, from the
    Cost_recycling_global and Cost_material_global sheets (each material's own
    dedicated cost sheet, migrated out of RR_Global for readability -- see
    load_disposal_costs for the third, currently-empty cost sheet). Only
    16/41 materials have data today, always both values together (never one
    without the other, confirmed) -- the rest are absent from the returned
    dict, so callers should default missing entries to 0.0 for both (an
    unmodeled-cost default, not a claim that virgin material is free)."""
    recycling = _load_cost_sheet('Cost_recycling_global', path)
    primary = _load_cost_sheet('Cost_material_global', path)
    return {mat: (recycling.get(mat, 0.0), primary.get(mat, 0.0)) for mat in recycling.keys() | primary.keys()}


def load_disposal_costs(path=SOURCE_XLSX):
    """{short_code: disposal_cost} in CAD/t, from Cost_disposal_global --
    empty today (no data yet, see Constraints.mod's disposal_cost default of
    50), ready for whenever real disposal-cost data is added there."""
    return _load_cost_sheet('Cost_disposal_global', path)


if __name__ == '__main__':
    rr = load_rr_vehicles()
    df2020 = rr[2020]
    print("RR_Vehicles 2020:", df2020.shape, "materials x subtechs")
    print(df2020[df2020['Vehicle_elec'].notna()])
