# Load Recycling_rates.xlsx (read-only) into tidy DataFrames (counterpart of mi_pipeline/sources.py)
from pathlib import Path

import pandas as pd

from mi_pipeline.sources import load_materials as _load_materials

_PROJ_ROOT = Path(__file__).resolve().parents[2]  # .../projects/critical_materials
SOURCE_XLSX = _PROJ_ROOT / 'excel_files' / 'Recycling_rates.xlsx'


# {full_name: short_code} from the 'Materials' sheet (same convention as mi_pipeline.sources)
def load_materials(path=SOURCE_XLSX):
    return _load_materials(path)


YEARS_INT = [2020, 2025, 2030, 2035, 2040, 2045, 2050]


# Sheet as {year: DataFrame(short material code x sub-technology/category)} of recycling-rate fractions
def _load_rr_sheet(sheet_name, path=SOURCE_XLSX):
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


# Electricity/fuel-cell recycling rates (same sub-tech names as MI_Energy); all-NaN until populated
def load_rr_energy(path=SOURCE_XLSX):
    return _load_rr_sheet('RR_Energy', path)


# Road-vehicle recycling rates (private + public/freight) by powertrain category
def load_rr_vehicles(path=SOURCE_XLSX):
    return _load_rr_sheet('RR_Vehicles', path)


# Electrolyzer recycling rates (same sub-tech names as MI_H2); all-NaN until populated
def load_rr_h2(path=SOURCE_XLSX):
    return _load_rr_sheet('RR_H2', path)


# RR_Global per-year recycling rates by short material code (YEAR_2020..YEAR_2050), fallback for unmapped techs
def load_rr_global(path=SOURCE_XLSX):
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


# {short_code: value} from a dedicated cost sheet, taking its first literature column
def _load_cost_sheet(sheet_name, path=SOURCE_XLSX):
    materials = load_materials(path)
    df = pd.read_excel(path, sheet_name=sheet_name, index_col=0)
    df = df.loc[df.index.notna()]
    unmapped = [name for name in df.index if name not in materials]
    if unmapped:
        raise ValueError(f"{sheet_name} has materials with no short-code mapping: {unmapped}")
    first_col = df.iloc[:, 0]
    return {materials[name]: float(v) for name, v in first_col.items() if pd.notna(v)}


# {short_code: (recycling_cost, primary_material_cost)} in CAD/t, from Cost_recycling_global and Cost_material_global
def load_rr_costs(path=SOURCE_XLSX):
    recycling = _load_cost_sheet('Cost_recycling_global', path)
    primary = _load_cost_sheet('Cost_material_global', path)
    return {mat: (recycling.get(mat, 0.0), primary.get(mat, 0.0)) for mat in recycling.keys() | primary.keys()}


# {short_code: disposal_cost} in CAD/t from Cost_disposal_global (empty until data is added)
def load_disposal_costs(path=SOURCE_XLSX):
    return _load_cost_sheet('Cost_disposal_global', path)


if __name__ == '__main__':
    rr = load_rr_vehicles()
    df2020 = rr[2020]
    print("RR_Vehicles 2020:", df2020.shape, "materials x subtechs")
    print(df2020[df2020['Vehicle_elec'].notna()])
