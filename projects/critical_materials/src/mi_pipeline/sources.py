"""Load the literature source workbook (Material_intensities_energyscope.xlsx) into
tidy pandas DataFrames.

This file is treated as read-only input: nothing in this module writes to it.
"""
from pathlib import Path
import pandas as pd

_PROJ_ROOT = Path(__file__).resolve().parents[2]  # .../projects/critical_materials
SOURCE_XLSX = _PROJ_ROOT / 'excel_files' / 'Material_intensities_energyscope.xlsx'

# MI_Energy spells out full element/material names; the rest of the pipeline (and the
# AMPL `set MATERIALS`) uses short codes. This is the complete 38-entry correspondence.
MATERIAL_NAME_TO_CODE = {
    'Aluminum': 'Al', 'Boron': 'B', 'Cadmium': 'Cd', 'Chromium': 'Cr', 'Cobalt': 'Co',
    'Concrete': 'Concrete', 'Copper': 'Cu', 'Dysprosium': 'Dy', 'Gallium': 'Ga',
    'Germanium': 'Ge', 'Glass': 'Glass', 'Hafnium': 'Hf', 'Indium': 'In', 'Iron': 'Fe',
    'Lead': 'Pb', 'Lithium': 'Li', 'Magnesium': 'Mg', 'Manganese': 'Mn',
    'Molybdenum': 'Mo', 'Neodymium': 'Nd', 'Nickel': 'Ni', 'Niobium': 'Nb',
    'Polymers': 'Polymers', 'Praesodymium': 'Pr', 'Selenium': 'Se', 'Silicon': 'Si',
    'Silver': 'Ag', 'Tantalum': 'Ta', 'Tellurium': 'Te', 'Terbium': 'Tb', 'Tin': 'Sn',
    'Tungsten': 'W', 'Vanadium': 'V', 'Yttrium': 'Y', 'Zinc': 'Zn', 'Zirconium': 'Zr',
    'Platinum': 'Pt', 'Palladium': 'Pd',
}


def load_mi_energy(path=SOURCE_XLSX):
    """Return MI_Energy as a DataFrame indexed by short material code, one column
    per literature sub-technology, values in t/GW."""
    df = pd.read_excel(path, sheet_name='MI_Energy', index_col=0)
    unmapped = [name for name in df.index if name not in MATERIAL_NAME_TO_CODE]
    if unmapped:
        raise ValueError(f"MI_Energy has materials with no short-code mapping: {unmapped}")
    df.index = df.index.map(MATERIAL_NAME_TO_CODE)
    return df


VEHICLE_POWERTRAINS = ['ICEV', 'HEV', 'PHEV', 'EV', 'FCV']


def load_mi_vehicles(path=SOURCE_XLSX):
    """Return MI_Vehicles as a DataFrame indexed by short material code, one
    column per powertrain (ICEV/HEV/PHEV/EV/FCV), values in g/vehicle -- already
    complete per-vehicle totals (Watari et al. 2019 + Fishman et al. 2018), no
    further battery/motor blending needed. Only the first 38 material rows are
    read; the sheet also has a sum row and an unrelated body/battery/motor
    breakdown block below that isn't part of this table."""
    df = pd.read_excel(path, sheet_name='MI_Vehicles', index_col=0, nrows=38)
    df = df[VEHICLE_POWERTRAINS]
    unmapped = [name for name in df.index if name not in MATERIAL_NAME_TO_CODE]
    if unmapped:
        raise ValueError(f"MI_Vehicles has materials with no short-code mapping: {unmapped}")
    df.index = df.index.map(MATERIAL_NAME_TO_CODE)
    return df


def _load_market_share(sheet_name, path=SOURCE_XLSX):
    """MS_Energy_Disag / MS_Energy_Ag: long format (Decade, Energy_Sources, then one
    column per sub-technology with its market share for that decade/category)."""
    df = pd.read_excel(path, sheet_name=sheet_name)
    df['Decade'] = df['Decade'].astype(int)
    return df


def load_ms_disag(path=SOURCE_XLSX):
    return _load_market_share('MS_Energy_Disag', path)


def load_ms_ag(path=SOURCE_XLSX):
    return _load_market_share('MS_Energy_Ag', path)


def load_ref_hp(path=SOURCE_XLSX):
    """Ref&Hp: reference + hypothesis notes, keyed by spreadsheet name. Column B
    ('Data') and the header-less 4th column (full citation text) are forward-filled
    since the sheet only labels the first row of each spreadsheet's reference block."""
    df = pd.read_excel(path, sheet_name='Ref&Hp')
    df = df.rename(columns={df.columns[3]: 'Ref_full'})
    df['Spreadsheet_name'] = df['Spreadsheet_name'].ffill()
    return df


if __name__ == '__main__':
    mi = load_mi_energy()
    print("MI_Energy:", mi.shape, "materials x subtechs")
    print(mi.loc[['Pt', 'Pd']])
    ms_disag = load_ms_disag()
    print("\nMS_Energy_Disag:", ms_disag.shape)
    ms_ag = load_ms_ag()
    print("MS_Energy_Ag:", ms_ag.shape)
    ref_hp = load_ref_hp()
    print("\nRef&Hp rows for MI_Energy:")
    print(ref_hp[ref_hp['Spreadsheet_name'] == 'MI_Energy'])
