"""Load the literature source workbook (Material_intensities_energyscope.xlsx) into
tidy pandas DataFrames.

This file is treated as read-only input: nothing in this module writes to it.
"""
from pathlib import Path
import pandas as pd

_PROJ_ROOT = Path(__file__).resolve().parents[2]  # .../projects/critical_materials
SOURCE_XLSX = _PROJ_ROOT / 'excel_files' / 'Material_intensities_energyscope.xlsx'

MATERIALS_SHEET = 'Materials'


def load_materials(path=SOURCE_XLSX):
    """{full_name: short_code} for every material in the pipeline, read from
    the 'Materials' sheet in row order (also the output column order -- see
    build_table.load_material_output_order()). This is the *only* place that
    needs a new row to add a material -- nothing in the code has to change,
    the MI_*/Mapping loaders below and build_table's output all derive from
    this sheet."""
    df = pd.read_excel(path, sheet_name=MATERIALS_SHEET)
    return dict(zip(df['Full_Name'], df['Short_Code']))


def load_mi_energy(path=SOURCE_XLSX):
    """Return MI_Energy as a DataFrame indexed by short material code, one column
    per literature sub-technology, values in t/GW."""
    materials = load_materials(path)
    df = pd.read_excel(path, sheet_name='MI_Energy', index_col=0)
    unmapped = [name for name in df.index if name not in materials]
    if unmapped:
        raise ValueError(f"MI_Energy has materials with no short-code mapping: {unmapped}")
    df.index = df.index.map(materials)
    return df


def load_mi_h2(path=SOURCE_XLSX):
    """Return MI_H2 as a DataFrame indexed by short material code, one column
    per electrolyzer (Alkaline_Electrolysis/SOEC_Electrolysis/PEM_electrolysis),
    values in t/GW -- same convention as MI_Energy, no unit conversion needed."""
    materials = load_materials(path)
    df = pd.read_excel(path, sheet_name='MI_H2', index_col=0)
    unmapped = [name for name in df.index if name not in materials]
    if unmapped:
        raise ValueError(f"MI_H2 has materials with no short-code mapping: {unmapped}")
    df.index = df.index.map(materials)
    return df


VEHICLE_POWERTRAINS = ['ICEV', 'HEV', 'PHEV', 'EV', 'FCV']


def load_mi_vehicles(path=SOURCE_XLSX):
    """Return MI_Vehicles as a DataFrame indexed by short material code, one
    column per powertrain (ICEV/HEV/PHEV/EV/FCV), values in g/vehicle -- already
    complete per-vehicle totals (Watari et al. 2019 + Fishman et al. 2018), no
    further battery/motor blending needed. Stops at the first blank row (the
    sheet also has a sum row and an unrelated body/battery/motor breakdown
    block further down that isn't part of this table) rather than a fixed
    row count, so adding a material row doesn't require updating this."""
    materials = load_materials(path)
    raw = pd.read_excel(path, sheet_name='MI_Vehicles', header=None)
    end = 1
    while end < len(raw) and pd.notna(raw.iloc[end, 0]):
        end += 1
    df = pd.read_excel(path, sheet_name='MI_Vehicles', index_col=0, nrows=end - 1)
    df = df[VEHICLE_POWERTRAINS]
    unmapped = [name for name in df.index if name not in materials]
    if unmapped:
        raise ValueError(f"MI_Vehicles has materials with no short-code mapping: {unmapped}")
    df.index = df.index.map(materials)
    return df


MI_VEHICLES_BIEUVILLE_SHEET = 'MI_Vehicles_Bieuville_Clean'
_BIEUVILLE_SENTINEL_ROWS = {'source'}  # footer row(s) to drop, matched case/whitespace-insensitively

# Body/motor/battery columns all live side by side in one sheet; matched by
# name so reordering the sheet's columns doesn't break this (renaming them
# does -- these names are the contract with the Excel side).
BIEUVILLE_BODY_COLUMNS = {'ICEV': 'ICEV', 'HEV': 'HEV-body', 'PHEV': 'PHEV-body', 'EV': 'EV-body'}
BIEUVILLE_MOTOR_COLUMNS = ['PM-Motor', 'Ind-Motor']
BIEUVILLE_BATTERY_PREFIX = 'Batt-'


def load_mi_vehicles_bieuville(path=SOURCE_XLSX):
    """Return the main table of MI_VEHICLES_BIEUVILLE_SHEET, indexed by short
    material code: body (per powertrain, BIEUVILLE_BODY_COLUMNS), motor (per
    motor type, BIEUVILLE_MOTOR_COLUMNS) and battery (per chemistry, g/kWh,
    columns prefixed BIEUVILLE_BATTERY_PREFIX) all as columns of the same
    table. Stops at the first blank row (the sheet has a separate 'Vehicle
    statistics' block further down -- see load_battery_size -- which isn't
    part of this table). FCV isn't covered here -- see
    aggregate.compute_vehicle_intensities_bieuville, which falls back to
    load_mi_vehicles()'s FCV column for that powertrain."""
    raw = pd.read_excel(path, sheet_name=MI_VEHICLES_BIEUVILLE_SHEET, header=None)
    end = 1
    while end < len(raw) and pd.notna(raw.iloc[end, 0]):
        end += 1
    df = pd.read_excel(path, sheet_name=MI_VEHICLES_BIEUVILLE_SHEET, index_col=0, nrows=end - 1)
    df = df.rename(index=lambda name: name.strip() if isinstance(name, str) else name)
    df = df.loc[[name for name in df.index
                 if not (isinstance(name, str) and name.strip().lower() in _BIEUVILLE_SENTINEL_ROWS)]]
    df = df.apply(pd.to_numeric, errors='coerce')
    materials = load_materials(path)
    unmapped = [name for name in df.index if name not in materials]
    if unmapped:
        raise ValueError(f"{MI_VEHICLES_BIEUVILLE_SHEET} has materials with no short-code mapping: {unmapped}")
    df.index = df.index.map(materials)
    return df


def load_battery_size(path=SOURCE_XLSX):
    """{'HEV': 1.3, 'PHEV': 21.8, 'EV': 62.5} kWh battery capacity per
    powertrain (no entry for ICEV -- it has no battery), from the 'Vehicle
    statistics' block in MI_VEHICLES_BIEUVILLE_SHEET. Found by searching for
    the 'Vehicle part' label rather than a fixed row/column position, so it
    tolerates that block moving if the sheet is edited. The sheet calls the
    battery-electric column 'BEV'; renamed to 'EV' here to match
    VEHICLE_POWERTRAINS."""
    raw = pd.read_excel(path, sheet_name=MI_VEHICLES_BIEUVILLE_SHEET, header=None)
    header_rows = raw.index[raw[0].astype(str).str.strip() == 'Vehicle part']
    if len(header_rows) == 0:
        raise ValueError(f"Could not find a 'Vehicle part' row in {MI_VEHICLES_BIEUVILLE_SHEET}")
    header_row = header_rows[0]
    data_row = header_row + 1
    header = raw.iloc[header_row]
    sizes = {}
    for col in range(1, raw.shape[1]):
        label = header[col]
        if isinstance(label, str) and label.strip() in ('HEV', 'PHEV', 'BEV'):
            sizes[label.strip()] = float(raw.iloc[data_row, col])
    sizes['EV'] = sizes.pop('BEV')
    return sizes


MI_VEHICLES_PUBLIC_SHEET = 'MI_Vehicles_Public'

# Same side-by-side-columns-in-one-sheet layout as MI_Vehicles_Bieuville_Clean,
# but with the combustion engine (flat g/vehicle) split out from the electric
# propulsion motor (per kW, PUBLIC_MOTOR_COLUMNS below) -- a bus/coach/schoolbus's
# electric motor is sized very differently across HEV/EV, unlike the private
# fleet's fixed motor mix. No PHEV column (not a real public-transit powertrain).
PUBLIC_BODY_COLUMNS = {'ICEV': 'ICEV-body', 'HEV': 'HEV-body', 'EV': 'EV-body'}
PUBLIC_ENGINE_COLUMNS = {'ICEV': 'ICEV-motor', 'HEV': 'HEV-motor'}  # flat g/vehicle combustion engine; EV has none
PUBLIC_MOTOR_COLUMNS = {'PM': 'PM-Motor [g/kW]', 'Ind': 'Ind-Motor [g/kW]'}  # electric propulsion motor, HEV/EV only


def load_mi_vehicles_public(path=SOURCE_XLSX):
    """Return the main table of MI_VEHICLES_PUBLIC_SHEET, indexed by short
    material code -- mirrors load_mi_vehicles_bieuville's parsing (stops at
    the first blank row, drops the footer 'Source' row). FCV column is
    present but entirely zero (no hydrogen-bus data yet)."""
    raw = pd.read_excel(path, sheet_name=MI_VEHICLES_PUBLIC_SHEET, header=None)
    end = 1
    while end < len(raw) and pd.notna(raw.iloc[end, 0]):
        end += 1
    df = pd.read_excel(path, sheet_name=MI_VEHICLES_PUBLIC_SHEET, index_col=0, nrows=end - 1)
    df = df.rename(index=lambda name: name.strip() if isinstance(name, str) else name)
    df = df.loc[[name for name in df.index
                 if not (isinstance(name, str) and name.strip().lower() in _BIEUVILLE_SENTINEL_ROWS)]]
    df = df.apply(pd.to_numeric, errors='coerce')
    materials = load_materials(path)
    unmapped = [name for name in df.index if name not in materials]
    if unmapped:
        raise ValueError(f"{MI_VEHICLES_PUBLIC_SHEET} has materials with no short-code mapping: {unmapped}")
    df.index = df.index.map(materials)
    return df


def load_bus_vehicle_stats(path=SOURCE_XLSX):
    """{'battery': {'HEV': 5.0, 'EV': 62.5}} [kWh] and {'motor': {'HEV': 180.0,
    'EV': 300.0}} [kW] from the 'Bus part' block in MI_VEHICLES_PUBLIC_SHEET
    ('Battery' and 'Motor' rows) -- found by label, same tolerant-to-editing
    approach as load_battery_size."""
    raw = pd.read_excel(path, sheet_name=MI_VEHICLES_PUBLIC_SHEET, header=None)
    header_rows = raw.index[raw[0].astype(str).str.strip() == 'Bus part']
    if len(header_rows) == 0:
        raise ValueError(f"Could not find a 'Bus part' row in {MI_VEHICLES_PUBLIC_SHEET}")
    header = raw.iloc[header_rows[0]]
    cols = {label.strip(): col for col, label in header.items()
            if isinstance(label, str) and label.strip() in ('HEV', 'BEV')}

    stats = {}
    for row_label in ('Battery', 'Motor'):
        row_idx = raw.index[raw[0].astype(str).str.strip() == row_label]
        if len(row_idx) == 0:
            raise ValueError(f"Could not find a {row_label!r} row in {MI_VEHICLES_PUBLIC_SHEET}")
        values = {pt: float(raw.iloc[row_idx[0], col]) for pt, col in cols.items()}
        values['EV'] = values.pop('BEV')
        stats[row_label.lower()] = values
    return stats


def load_battery_motor_market_share(path=SOURCE_XLSX):
    """Return (battery_share, motor_share) from MS_Battery_Motor_LDV:
    battery_share is a DataFrame indexed by chemistry name with int-year
    columns (whatever years are actually present in the sheet, e.g. 2014-2030
    then 2040/2050 -- see aggregate._interpolate_to_year for how in-between
    target years like YEAR_2035 are handled); motor_share is a
    {'PM': .., 'Ind': ..} dict (fixed, no year variation in the source data).
    Anchor-based parsing (searches for the 'Battery_type'/'Motor_type' label
    rows and reads until the next blank row, rather than fixed row counts) so
    it tolerates rows being inserted/removed elsewhere in the sheet."""
    raw = pd.read_excel(path, sheet_name='MS_Battery_Motor_LDV', header=None)

    batt_header_row = raw.index[raw[0].astype(str).str.strip() == 'Battery_type'][0]
    header = raw.iloc[batt_header_row]
    year_cols = [c for c in range(2, raw.shape[1])
                 if pd.notna(header[c]) and str(header[c]).replace('.0', '').isdigit()]
    years = [int(header[c]) for c in year_cols]

    end = batt_header_row + 1
    while end < len(raw) and pd.notna(raw.iloc[end, 0]):
        end += 1
    battery_share = raw.iloc[batt_header_row + 1:end, [0] + year_cols].copy()
    battery_share.columns = ['Battery_type'] + years
    battery_share = battery_share.set_index('Battery_type').apply(pd.to_numeric)

    motor_header_row = raw.index[raw[0].astype(str).str.strip() == 'Motor_type'][0]
    motor_cols = raw.iloc[motor_header_row, 1:3].tolist()
    motor_vals = raw.iloc[motor_header_row + 1, 1:3].tolist()
    motor_share = dict(zip(motor_cols, motor_vals))

    return battery_share, motor_share


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
