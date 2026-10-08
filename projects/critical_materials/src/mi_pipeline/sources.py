# Load Material_intensities.xlsx (read-only) into tidy DataFrames
from pathlib import Path
import pandas as pd

_PROJ_ROOT = Path(__file__).resolve().parents[2]  # .../projects/critical_materials
SOURCE_XLSX = _PROJ_ROOT / 'excel_files' / 'Material_intensities.xlsx'

MATERIALS_SHEET = 'Materials'


# {full_name: short_code} from the 'Materials' sheet (row order = output column order)
def load_materials(path=SOURCE_XLSX):
    df = pd.read_excel(path, sheet_name=MATERIALS_SHEET)
    return dict(zip(df['Full_Name'], df['Short_Code']))


# MI_Energy by short material code x literature sub-technology, in t/GW
def load_mi_energy(path=SOURCE_XLSX):
    materials = load_materials(path)
    df = pd.read_excel(path, sheet_name='MI_Energy', index_col=0)
    unmapped = [name for name in df.index if name not in materials]
    if unmapped:
        raise ValueError(f"MI_Energy has materials with no short-code mapping: {unmapped}")
    df.index = df.index.map(materials)
    return df


# MI_H2 by short material code x electrolyzer, in t/GW
def load_mi_h2(path=SOURCE_XLSX):
    materials = load_materials(path)
    df = pd.read_excel(path, sheet_name='MI_H2', index_col=0)
    unmapped = [name for name in df.index if name not in materials]
    if unmapped:
        raise ValueError(f"MI_H2 has materials with no short-code mapping: {unmapped}")
    df.index = df.index.map(materials)
    return df


VEHICLE_POWERTRAINS = ['ICEV', 'HEV', 'PHEV', 'EV', 'FCV']


# MI_Vehicles by short material code x powertrain (ICEV/HEV/PHEV/EV/FCV), in g/vehicle
def load_mi_vehicles(path=SOURCE_XLSX):
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


MI_VEHICLES_BIEUVILLE_SHEET = 'MI_Vehicles_2'  # renamed from 'MI_Vehicles_Bieuville_Clean'
_BIEUVILLE_SENTINEL_ROWS = {'source'}  # footer row(s) to drop, matched case/whitespace-insensitively

# Body/motor/battery columns all live side by side in one sheet; matched by
# name so reordering the sheet's columns doesn't break this (renaming them
# does -- these names are the contract with the Excel side).
BIEUVILLE_BODY_COLUMNS = {'ICEV': 'ICEV', 'HEV': 'HEV-body', 'PHEV': 'PHEV-body', 'EV': 'EV-body'}
BIEUVILLE_MOTOR_COLUMNS = ['PM-Motor', 'Ind-Motor']
BIEUVILLE_MOTOR_REFERENCE_KW = 70  # PM-Motor/Ind-Motor g/vehicle values are sized for a 70kW motor -- scale by actual_kW/70 per powertrain (load_vehicle_stats' 'motor' dict)
BIEUVILLE_BATTERY_PREFIX = 'Batt-'


# Main table of MI_VEHICLES_BIEUVILLE_SHEET: body (per powertrain), motor, battery (per chemistry)
def load_mi_vehicles_bieuville(path=SOURCE_XLSX):
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


# Battery [kWh] and motor [kW] sizes per powertrain, from the 'Vehicle statistics' block
def load_vehicle_stats(path=SOURCE_XLSX):
    raw = pd.read_excel(path, sheet_name=MI_VEHICLES_BIEUVILLE_SHEET, header=None)
    header_rows = raw.index[raw[0].astype(str).str.strip() == 'Vehicle part']
    if len(header_rows) == 0:
        raise ValueError(f"Could not find a 'Vehicle part' row in {MI_VEHICLES_BIEUVILLE_SHEET}")
    header = raw.iloc[header_rows[0]]
    cols = {label.strip(): col for col, label in header.items()
            if isinstance(label, str) and label.strip() in ('HEV', 'PHEV', 'BEV')}

    stats = {}
    for row_label in ('Battery', 'Motor'):
        row_idx = raw.index[raw[0].astype(str).str.strip() == row_label]
        if len(row_idx) == 0:
            raise ValueError(f"Could not find a {row_label!r} row in {MI_VEHICLES_BIEUVILLE_SHEET}")
        values = {pt: float(raw.iloc[row_idx[0], col]) for pt, col in cols.items()}
        values['EV'] = values.pop('BEV')
        stats[row_label.lower()] = values
    return stats


MI_VEHICLES_PUBLIC_SHEET = 'MI_Vehicles_Public'

# Same side-by-side-columns-in-one-sheet layout as MI_Vehicles_2 (MI_VEHICLES_BIEUVILLE_SHEET),
# but with the combustion engine (flat g/vehicle) split out from the electric
# propulsion motor (per kW, PUBLIC_MOTOR_COLUMNS below, scaled by load_bus_vehicle_stats'
# own 'motor' dict -- same per-kW-then-rescale approach as the private fleet's
# BIEUVILLE_MOTOR_REFERENCE_KW). No PHEV column (not a real public-transit powertrain).
PUBLIC_BODY_COLUMNS = {'ICEV': 'ICEV-body', 'HEV': 'HEV-body', 'EV': 'EV-body'}
PUBLIC_ENGINE_COLUMNS = {'ICEV': 'ICEV-motor', 'HEV': 'HEV-motor'}  # flat g/vehicle combustion engine; EV has none
PUBLIC_MOTOR_COLUMNS = {'PM': 'PM-Motor [g/kW]', 'Ind': 'Ind-Motor [g/kW]'}  # electric propulsion motor, HEV/EV only


# Main table of MI_VEHICLES_PUBLIC_SHEET by short material code (parsed like load_mi_vehicles_bieuville)
def load_mi_vehicles_public(path=SOURCE_XLSX):
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


# Bus battery [kWh] and motor [kW] sizes per powertrain, from the 'Bus part' block
def load_bus_vehicle_stats(path=SOURCE_XLSX):
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


# (battery_share, motor_share) from MS_Battery_Motor_LDV
def load_battery_motor_market_share(path=SOURCE_XLSX):
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


# MS_Energy_Disag in long format: Decade, Energy_Sources, then one market-share column per sub-technology
def load_ms_disag(path=SOURCE_XLSX):
    df = pd.read_excel(path, sheet_name='MS_Energy_Disag')
    df['Decade'] = df['Decade'].astype(int)
    return df


# Ref&Hp reference/hypothesis notes, keyed by spreadsheet name
def load_ref_hp(path=SOURCE_XLSX):
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
    ref_hp = load_ref_hp()
    print("\nRef&Hp rows for MI_Energy:")
    print(ref_hp[ref_hp['Spreadsheet_name'] == 'MI_Energy'])
