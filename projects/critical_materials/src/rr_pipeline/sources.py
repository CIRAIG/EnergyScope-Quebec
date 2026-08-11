"""Load the literature source workbook (Recycling_rates.xlsx) into tidy pandas
DataFrames -- recycling-rate counterpart to mi_pipeline/sources.py.

This file is treated as read-only input: nothing in this module writes to it.

Unlike mi_pipeline's MI_Energy/MI_Vehicles/MI_H2 (material mass per GW or per
vehicle), a recycling rate is already a dimensionless fraction [0,1] -- no
per-vehicle unit conversion (ref_size, g/vehicle) is needed here, which is
what keeps this pipeline noticeably simpler than mi_pipeline's.
"""
from pathlib import Path

from mi_pipeline.sources import load_materials as _load_materials

_PROJ_ROOT = Path(__file__).resolve().parents[2]  # .../projects/critical_materials
SOURCE_XLSX = _PROJ_ROOT / 'excel_files' / 'Recycling_rates.xlsx'


def load_materials(path=SOURCE_XLSX):
    """{full_name: short_code}, same 'Materials' sheet convention as
    mi_pipeline.sources.load_materials (verified byte-identical between the
    two workbooks) -- just pointed at this workbook by default."""
    return _load_materials(path)


def _load_rr_sheet(sheet_name, path=SOURCE_XLSX):
    """Return `sheet_name` as a DataFrame indexed by short material code, one
    column per literature sub-technology/category, values already
    dimensionless recycling-rate fractions -- same read pattern as
    mi_pipeline.sources.load_mi_energy (row 0 = header, column 0 = material
    full name), no unit conversion needed."""
    import pandas as pd
    materials = load_materials(path)
    df = pd.read_excel(path, sheet_name=sheet_name, index_col=0)
    df = df.loc[df.index.notna()]  # drop footer/reference rows (no material name)
    unmapped = [name for name in df.index if name not in materials]
    if unmapped:
        raise ValueError(f"{sheet_name} has materials with no short-code mapping: {unmapped}")
    df.index = df.index.map(materials)
    return df


def load_rr_energy(path=SOURCE_XLSX):
    """Electricity/fuel-cell sub-technologies (Sol_*/Wind_*/Nuclear_*/...),
    same sub-tech naming as mi_pipeline.sources.load_mi_energy's MI_Energy.
    Empty (all-NaN) until RR_Energy is populated in the workbook."""
    return _load_rr_sheet('RR_Energy', path)


def load_rr_vehicles(path=SOURCE_XLSX):
    """Private-mobility recycling rates -- currently a single 'Vehicle_private'
    column (one rate per material, not split by powertrain), the only sheet
    with real data so far."""
    return _load_rr_sheet('RR_Vehicles', path)


def load_rr_vehicles_public(path=SOURCE_XLSX):
    """Public-mobility recycling rates. Empty (all-NaN) until populated."""
    return _load_rr_sheet('RR_Vehicles_Public', path)


def load_rr_h2(path=SOURCE_XLSX):
    """Electrolyzer recycling rates (Alkaline_Electrolysis/SOEC_Electrolysis/
    PEM_electrolysis), same sub-tech naming as mi_pipeline.sources.load_mi_h2.
    Empty (all-NaN) until populated."""
    return _load_rr_sheet('RR_H2', path)


def load_recycling_scenario(path=SOURCE_XLSX):
    """Approach 1's system-wide minimum-recycled-share floor: DataFrame
    indexed by short material code, one column per year (int, e.g. 2025..2050
    -- no 2020 column in the sheet, YEAR_2020 stays at the AMPL default 0),
    values already dimensionless shares [0,1]. Empty (all-NaN) until the
    Recycling_scenario sheet is populated."""
    import pandas as pd
    materials = load_materials(path)
    df = pd.read_excel(path, sheet_name='Recycling_scenario', index_col=0)
    df.columns = [int(c) for c in df.columns]
    unmapped = [name for name in df.index if name not in materials]
    if unmapped:
        raise ValueError(f"Recycling_scenario has materials with no short-code mapping: {unmapped}")
    df.index = df.index.map(materials)
    return df


if __name__ == '__main__':
    rr = load_rr_vehicles()
    print("RR_Vehicles:", rr.shape, "materials x subtechs")
    print(rr[rr['Vehicle_private'].notna()])
