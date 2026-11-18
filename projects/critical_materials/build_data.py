#!/usr/bin/env python3
"""Generate the AMPL data files of the materials from the Excel workbooks (read-only inputs) and the runs.

    python build_data.py intensity [--vehicle-source watari|bieuville] [--no-dat]   Material_intensities.xlsx -> ampl_files/Material_intensity.dat
    python build_data.py recycling [--no-dat]                                       Recycling_rates.xlsx -> ampl_files/Material_recycling.dat
    python build_data.py recycling-process [--no-dat]                               Recycling_rates.xlsx -> ampl_files/Material_recycling_process.dat
    python build_data.py limits [--no-dat]                                          Material_limits.xlsx -> ampl_files/Material_limits.dat
    python build_data.py vehicle-choice                                             Material_intensities.xlsx -> ampl_files/Vehicle_choice.dat
    python build_data.py big-m [--references RUN ...] [--margin 2] [--no-dat]       runs of out/ -> ampl_files/Material_bigM.dat

--no-dat computes and prints the coverage report without writing the .dat. From a notebook:
    from build_data import build_intensity, build_recycling, build_recycling_process, build_limits, build_vehicle_choice, build_big_m

The code is organised in sections, one per file generated: material intensities, recycling rates, recycling processes, limits,
vehicle choice (body / motor / battery parts of the vehicle intensities) and big M of the K approach."""
import argparse
import pickle
import re
import sys
import time
from pathlib import Path

import pandas as pd

_PROJ_ROOT = Path(__file__).resolve().parent  # .../projects/critical_materials
sys.path.insert(0, str(_PROJ_ROOT / 'src'))

from mi_pipeline import canonical  # technology lists of QC_data.dat, also used by Plot_functions.py

AMPL_DIR = _PROJ_ROOT / 'ampl_files'
RR_XLSX = _PROJ_ROOT / 'excel_files' / 'Recycling_rates.xlsx'  # recycling rates and recycling processes


# ======================================================================================================================
# 1. Material intensities
# Material_intensities.xlsx -> ampl_files/Material_intensity.dat
# ======================================================================================================================


# ---- Load Material_intensities.xlsx (read-only) into tidy DataFrames

MI_XLSX = _PROJ_ROOT / 'excel_files' / 'Material_intensities.xlsx'

MATERIALS_SHEET = 'Materials'


# {full_name: short_code} from the 'Materials' sheet (row order = output column order)
def load_materials(path=MI_XLSX):
    df = pd.read_excel(path, sheet_name=MATERIALS_SHEET)
    return dict(zip(df['Full_Name'], df['Short_Code']))


# MI_Energy by short material code x literature sub-technology, in t/GW
def load_mi_energy(path=MI_XLSX):
    materials = load_materials(path)
    df = pd.read_excel(path, sheet_name='MI_Energy', index_col=0)
    unmapped = [name for name in df.index if name not in materials]
    if unmapped:
        raise ValueError(f"MI_Energy has materials with no short-code mapping: {unmapped}")
    df.index = df.index.map(materials)
    return df


# MI_H2 by short material code x electrolyzer, in t/GW
def load_mi_h2(path=MI_XLSX):
    materials = load_materials(path)
    df = pd.read_excel(path, sheet_name='MI_H2', index_col=0)
    unmapped = [name for name in df.index if name not in materials]
    if unmapped:
        raise ValueError(f"MI_H2 has materials with no short-code mapping: {unmapped}")
    df.index = df.index.map(materials)
    return df


SOURCE_VEHICLE_POWERTRAINS = ['ICEV', 'HEV', 'PHEV', 'EV', 'FCV']


# MI_Vehicles by short material code x powertrain (ICEV/HEV/PHEV/EV/FCV), in g/vehicle
def load_mi_vehicles(path=MI_XLSX):
    materials = load_materials(path)
    raw = pd.read_excel(path, sheet_name='MI_Vehicles', header=None)
    end = 1
    while end < len(raw) and pd.notna(raw.iloc[end, 0]):
        end += 1
    df = pd.read_excel(path, sheet_name='MI_Vehicles', index_col=0, nrows=end - 1)
    df = df[SOURCE_VEHICLE_POWERTRAINS]
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
def load_mi_vehicles_bieuville(path=MI_XLSX):
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
def load_vehicle_stats(path=MI_XLSX):
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
def load_mi_vehicles_public(path=MI_XLSX):
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
def load_bus_vehicle_stats(path=MI_XLSX):
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
def load_battery_motor_market_share(path=MI_XLSX):
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
def load_ms_disag(path=MI_XLSX):
    df = pd.read_excel(path, sheet_name='MS_Energy_Disag')
    df['Decade'] = df['Decade'].astype(int)
    return df


# Ref&Hp reference/hypothesis notes, keyed by spreadsheet name
def load_ref_hp(path=MI_XLSX):
    df = pd.read_excel(path, sheet_name='Ref&Hp')
    df = df.rename(columns={df.columns[3]: 'Ref_full'})
    df['Spreadsheet_name'] = df['Spreadsheet_name'].ffill()
    return df


# ---- Load and validate the Mapping/Overrides sheets of Material_intensities.xlsx

MAPPING_XLSX = MI_XLSX

VALID_MAPPING_TYPES = {'direct', 'aggregate', 'disaggregate', 'not_mapped'}


# Mapping sheet indexed by energyscope_tech, with subtechs parsed into a list of MI_Energy columns
def load_mapping(path=MAPPING_XLSX):
    df = pd.read_excel(path, sheet_name='Mapping', dtype=str).fillna('')
    df['subtechs'] = df['subtechs'].apply(lambda s: [t.strip() for t in s.split(',') if t.strip()])
    df = df.set_index('energyscope_tech', drop=False)
    return df


# Cross-check the mapping against the canonical tech list; raise ValueError listing every problem
def validate_mapping(df, path=MAPPING_XLSX):
    problems = []

    canonical_techs = set(canonical.all_target_techs())
    mapped_techs = set(df.index)
    missing = canonical_techs - mapped_techs
    if missing:
        problems.append(f"Techs in scope but missing from {path.name}: {sorted(missing)}")

    # Only techs that actually claim real data (mapping_type != 'not_mapped') need
    # to exist in QC_data.dat -- a not_mapped row for e.g. a heat/mobility tech the
    # Mapping sheet doesn't yet cover computation for is expected and silent.
    claims_real_data = df.index[df['mapping_type'] != 'not_mapped']
    not_yet_modeled = set(claims_real_data) - canonical_techs
    if not_yet_modeled:
        print(f"[mapping] Note: {sorted(not_yet_modeled)} are in {path.name} but not yet in "
              f"QC_data.dat -- pre-filled for later, skipped when writing output.")

    bad_types = set(df['mapping_type']) - VALID_MAPPING_TYPES
    if bad_types:
        problems.append(f"Invalid mapping_type value(s): {sorted(bad_types)} (expected one of {VALID_MAPPING_TYPES})")

    for tech, row in df.iterrows():
        if row['mapping_type'] in ('direct', 'aggregate', 'disaggregate') and not row['subtechs']:
            problems.append(f"{tech}: mapping_type='{row['mapping_type']}' but 'subtechs' is empty")
        if row['mapping_type'] == 'direct' and len(row['subtechs']) != 1:
            problems.append(f"{tech}: mapping_type='direct' expects exactly 1 subtech, got {row['subtechs']}")

    if problems:
        raise ValueError(f"{path.name}'s Mapping sheet validation failed:\n- " + "\n- ".join(problems))


# ---- Compute EnergyScope material intensities from the literature source data

# Public-transit powertrains are a distinct vocabulary from the private-fleet ones
# above (ICEV/HEV/PHEV/EV/FCV) -- a bus's 'ICEV' isn't the same g/vehicle number as
# a car's, so they need their own labels rather than colliding in the same table.
PUBLIC_TRANSIT_POWERTRAINS = {'ICEV_PUBLIC', 'HEV_PUBLIC', 'EV_PUBLIC'}
VEHICLE_POWERTRAINS = set(SOURCE_VEHICLE_POWERTRAINS) | PUBLIC_TRANSIT_POWERTRAINS  # {'ICEV','HEV','PHEV','EV','FCV', + public transit}

YEARS = ['YEAR_2020', 'YEAR_2025', 'YEAR_2030', 'YEAR_2035', 'YEAR_2040', 'YEAR_2045', 'YEAR_2050']

# Each target year maps to (decade, None) when it lands exactly on a decade in the
# source data, or (decade1, decade2) to average across when it falls exactly halfway
# between two decades -- same averaging rule as period_to_decades in
# tot_material_demand_ex_post.ipynb, just keyed directly by output year instead of by
# optimization window.
YEAR_TO_DECADES = {
    'YEAR_2020': (2020, None),
    'YEAR_2025': (2020, 2030),
    'YEAR_2030': (2030, None),
    'YEAR_2035': (2030, 2040),
    'YEAR_2040': (2040, None),
    'YEAR_2045': (2040, 2050),
    'YEAR_2050': (2050, None),
}


# Weight of each MI_Energy subtech within energy_source for year (interpolated from MS_Energy_Disag)
def _weights_for_year(energy_source, year, ms_disag):
    matches = ms_disag[ms_disag['Energy_Sources'] == energy_source]
    if matches.empty:
        raise ValueError(
            f"No rows in MS_Energy_Disag match energy_source={energy_source!r}. "
            f"Check the Mapping sheet's energy_source spelling against what's actually "
            f"in the sheet. Available: {sorted(ms_disag['Energy_Sources'].dropna().unique())}"
        )
    rows = matches.set_index('Decade').drop(columns=['Energy_Sources'])
    rows = rows.apply(pd.to_numeric, errors='coerce')
    d1, d2 = YEAR_TO_DECADES[year]
    if d2 is None:
        return rows.loc[d1]
    return (rows.loc[d1] + rows.loc[d2]) / 2


# True if every subtech is an MI_Vehicles powertrain (needs the g/vehicle -> t/GW conversion)
def _is_vehicle_row(row):
    return bool(row['subtechs']) and set(row['subtechs']) <= VEHICLE_POWERTRAINS


# Intensity by material x YEARS in the source table's native unit (t/GW or g/vehicle)
def _raw_tech_intensity(tech, row, mi_all, ms_disag):
    materials = mi_all.index

    if row['mapping_type'] == 'not_mapped':
        # NaN, not 0 -- an unmapped tech has no data, which should render as a blank
        # cell (and be skipped entirely by the .dat writer), not a claimed zero value.
        return pd.DataFrame(float('nan'), index=materials, columns=YEARS)

    if row['mapping_type'] in ('direct', 'disaggregate'):
        # A single literature data point, replicated across every target year --
        # the source table itself doesn't vary by year, only the sub-tech market-share
        # mix does, and there's only one sub-tech here so there's nothing to blend.
        if len(row['subtechs']) != 1:
            raise ValueError(f"{tech}: '{row['mapping_type']}' expects exactly 1 subtech, got {row['subtechs']}")
        subtech = row['subtechs'][0]
        col = mi_all[subtech]
        return pd.DataFrame({year: col for year in YEARS}, index=materials)

    if row['mapping_type'] == 'aggregate':
        out = pd.DataFrame(0.0, index=materials, columns=YEARS)
        if not row['energy_source']:
            # No market-share category given -> a fixed equal-weight sum across the
            # listed subtechs (e.g. a fossil archetype + a flat CCS addendum), with
            # no time variation.
            total = sum(mi_all[subtech] for subtech in row['subtechs'])
            for year in YEARS:
                out[year] = total
            return out
        for year in YEARS:
            weights = _weights_for_year(row['energy_source'], year, ms_disag)
            for subtech in row['subtechs']:
                out[year] = out[year] + weights.get(subtech, 0.0) * mi_all[subtech]
        return out

    raise ValueError(f"{tech}: unknown mapping_type {row['mapping_type']!r}")


# Value of series at year_int, linearly interpolated between the two nearest available years
def _interpolate_to_year(series, year_int):
    available = sorted(series.index)
    if year_int in available:
        return series[year_int]
    lower = max((y for y in available if y <= year_int), default=None)
    upper = min((y for y in available if y >= year_int), default=None)
    if lower is None:
        return series[upper]
    if upper is None:
        return series[lower]
    if lower == upper:
        return series[lower]
    frac = (year_int - lower) / (upper - lower)
    return series[lower] + frac * (series[upper] - series[lower])


# {powertrain: DataFrame(material x YEARS)} in g/vehicle, from MI_Vehicles_2 + MS_Battery_Motor_LDV
def compute_vehicle_intensities_bieuville(materials):
    bieuville = load_mi_vehicles_bieuville()
    vehicle_stats = load_vehicle_stats()
    battery_size, motor_size = vehicle_stats['battery'], vehicle_stats['motor']
    battery_ms, motor_ms = load_battery_motor_market_share()
    mi_vehicles = load_mi_vehicles()

    battery_cols = [c for c in bieuville.columns if c.startswith(BIEUVILLE_BATTERY_PREFIX)]
    chem_of = {c: c[len(BIEUVILLE_BATTERY_PREFIX):].split(' [')[0] for c in battery_cols}
    missing_ms = set(chem_of.values()) - set(battery_ms.index)
    if missing_ms:
        raise ValueError(f"MS_Battery_Motor_LDV has no market share for chemistries: {sorted(missing_ms)}")

    motor = bieuville[BIEUVILLE_MOTOR_COLUMNS].reindex(materials).fillna(0)
    # motor is g/vehicle for a BIEUVILLE_MOTOR_REFERENCE_KW motor -- rescale per powertrain below.
    motor_per_kw = (motor['PM-Motor'] * motor_ms['PM'] + motor['Ind-Motor'] * motor_ms['Ind']) / BIEUVILLE_MOTOR_REFERENCE_KW

    result = {}
    for powertrain, body_col in BIEUVILLE_BODY_COLUMNS.items():
        body_vals = bieuville[body_col].reindex(materials).fillna(0)
        out = pd.DataFrame(index=materials, columns=YEARS, dtype=float)
        if powertrain == 'ICEV':
            for year in YEARS:
                out[year] = body_vals
            result[powertrain] = out
            continue
        weighted_motor = motor_per_kw * motor_size[powertrain]
        for year in YEARS:
            year_int = int(year.replace('YEAR_', ''))
            weighted_battery = sum(
                bieuville[col].reindex(materials).fillna(0) * _interpolate_to_year(battery_ms.loc[chem], year_int)
                for col, chem in chem_of.items()
            )
            out[year] = body_vals + battery_size[powertrain] * weighted_battery + weighted_motor
        result[powertrain] = out

    result['FCV'] = pd.DataFrame({year: mi_vehicles['FCV'].reindex(materials) for year in YEARS}, index=materials)
    return result


# {ICEV/HEV/EV_PUBLIC: DataFrame(material x YEARS)} in g/vehicle, from MI_Vehicles_Public + MS_Battery_Motor_LDV
def compute_vehicle_intensities_public_transit(materials):
    public = load_mi_vehicles_public()
    stats = load_bus_vehicle_stats()
    battery_ms, motor_ms = load_battery_motor_market_share()

    battery_cols = [c for c in public.columns if c.startswith(BIEUVILLE_BATTERY_PREFIX)]
    chem_of = {c: c[len(BIEUVILLE_BATTERY_PREFIX):].split(' [')[0] for c in battery_cols}
    missing_ms = set(chem_of.values()) - set(battery_ms.index)
    if missing_ms:
        raise ValueError(f"MS_Battery_Motor_LDV has no market share for chemistries: {sorted(missing_ms)}")

    weighted_motor_per_kw = sum(
        public[col].reindex(materials).fillna(0) * motor_ms[motor_type]
        for motor_type, col in PUBLIC_MOTOR_COLUMNS.items()
    )

    icev_body = public[PUBLIC_BODY_COLUMNS['ICEV']].reindex(materials).fillna(0)
    icev_engine = public[PUBLIC_ENGINE_COLUMNS['ICEV']].reindex(materials).fillna(0)
    out = pd.DataFrame({year: icev_body + icev_engine for year in YEARS}, index=materials)
    result = {'ICEV_PUBLIC': out}

    for powertrain in ('HEV', 'EV'):
        body = public[PUBLIC_BODY_COLUMNS[powertrain]].reindex(materials).fillna(0)
        engine_col = PUBLIC_ENGINE_COLUMNS.get(powertrain)
        engine = public[engine_col].reindex(materials).fillna(0) if engine_col else 0
        out = pd.DataFrame(index=materials, columns=YEARS, dtype=float)
        for year in YEARS:
            year_int = int(year.replace('YEAR_', ''))
            weighted_battery = sum(
                public[col].reindex(materials).fillna(0) * _interpolate_to_year(battery_ms.loc[chem], year_int)
                for col, chem in chem_of.items()
            )
            out[year] = (body + engine
                          + stats['battery'][powertrain] * weighted_battery
                          + stats['motor'][powertrain] * weighted_motor_per_kw)
        result[f'{powertrain}_PUBLIC'] = out

    return result


# _raw_tech_intensity with the g/vehicle -> material_intensity conversion (via ref_size) for vehicle rows
def compute_tech_intensity(tech, row, mi_all, ms_disag, ref_size,
                            vehicle_intensities_g=None):
    if row['mapping_type'] == 'not_mapped' or not _is_vehicle_row(row):
        return _raw_tech_intensity(tech, row, mi_all, ms_disag)

    powertrain = row['subtechs'][0]
    if vehicle_intensities_g is not None and powertrain in vehicle_intensities_g:
        raw_g = vehicle_intensities_g[powertrain]
    else:
        raw_g = _raw_tech_intensity(tech, row, mi_all, ms_disag)

    family = canonical.family_of(tech)
    out = pd.DataFrame(index=raw_g.index, columns=YEARS, dtype=float)
    for year in YEARS:
        r = ref_size.get((year, family))
        if r is None:
            raise ValueError(f"{tech}: no ref_size entry for family {family!r}, year {year!r} "
                              f"in {canonical.REF_SIZE_PATH.name}")
        out[year] = raw_g[year] * 1e-6 / r
    return out


# {energyscope_tech: DataFrame(material x YEARS)} for every tech in the Mapping sheet
def mi_compute_all(vehicle_source='bieuville'):
    if vehicle_source not in ('watari', 'bieuville'):
        raise ValueError(f"vehicle_source must be 'watari' or 'bieuville', got {vehicle_source!r}")

    mapping = load_mapping()
    validate_mapping(mapping)

    mi_energy = load_mi_energy()
    mi_vehicles = load_mi_vehicles()
    mi_h2 = load_mi_h2()
    mi_all = pd.concat([mi_energy, mi_vehicles, mi_h2], axis=1)
    ms_disag = load_ms_disag()
    ref_size = canonical.load_ref_size()

    vehicle_intensities_g = compute_vehicle_intensities_public_transit(mi_all.index)
    if vehicle_source == 'bieuville':
        vehicle_intensities_g.update(compute_vehicle_intensities_bieuville(mi_all.index))

    intensities = {
        tech: compute_tech_intensity(tech, row, mi_all, ms_disag, ref_size,
                                      vehicle_intensities_g=vehicle_intensities_g)
        for tech, row in mapping.iterrows()
    }

    return intensities


# ---- Console-only coverage report: which techs have usable material-intensity data (vs placeholder zeros, unmapped)

STATUS_ORDER = ['not_mapped', 'not_yet_modeled', 'placeholder_zero', 'integrated']


# DataFrame by energyscope_tech: mapping_type + status (not_mapped / not_yet_modeled / placeholder_zero / integrated)
def build_report(mapping, intensities):
    canonical_techs = set(canonical.all_target_techs())
    rows = []
    for tech, row in mapping.iterrows():
        if row['mapping_type'] == 'not_mapped':
            status = 'not_mapped'
        elif tech not in canonical_techs:
            status = 'not_yet_modeled'
        elif (intensities[tech] == 0).all().all():
            status = 'placeholder_zero'
        else:
            status = 'integrated'
        rows.append({
            'energyscope_tech': tech,
            'mapping_type': row['mapping_type'],
            'status': status,
        })
    return pd.DataFrame(rows).set_index('energyscope_tech')


def print_report(report):
    counts = report['status'].value_counts().reindex(STATUS_ORDER, fill_value=0)
    print("Coverage report:")
    for status in STATUS_ORDER:
        print(f"  {status:17s}: {counts[status]}")
    for status in STATUS_ORDER:
        techs = sorted(report.index[report['status'] == status])
        if techs:
            print(f"\n{status} ({len(techs)}):")
            for t in techs:
                print(f"  - {t}")


# ---- Assemble the long-format Metal_Intensity table and write Material_intensity.dat

OUT_DAT_NAME = 'Material_intensity'


# Material output order: short codes of the 'Materials' sheet, in row order
def load_material_output_order(path=MI_XLSX):
    return list(load_materials(path).values())


MATERIAL_OUTPUT_ORDER = load_material_output_order()


# Long-format rows for every tech in the Mapping sheet (not_mapped techs get blank Values)
def _mapped_rows(mapping, intensities, vehicle_source='bieuville'):
    rows = []
    for tech, row in mapping.iterrows():
        df = intensities[tech]
        is_vehicle = bool(row['subtechs']) and set(row['subtechs']) <= VEHICLE_POWERTRAINS
        is_fcv = is_vehicle and row['subtechs'][0] == 'FCV'
        is_public = is_vehicle and row['subtechs'][0] in PUBLIC_TRANSIT_POWERTRAINS
        unit = 't/(pkm/h)' if is_vehicle else 't/GW'
        if row['mapping_type'] == 'not_mapped':
            comment = "[not_mapped]"
        else:
            subtechs = ','.join(row['subtechs'])
            if not is_vehicle:
                source = 'Bieuville et al. 2025 (MI_Energy)'
            elif is_public:
                source = 'Månberger & Stenqvist 2018 (MI_Vehicles_Public + MS_Battery_Motor_LDV)'
            elif is_fcv or vehicle_source == 'watari':
                # FCV always falls back to MI_Vehicles regardless of vehicle_source (Bieuville doesn't cover it)
                source = 'Watari et al. 2019 / Fishman et al. 2018 (MI_Vehicles)'
            else:
                source = 'Bieuville et al. 2025 (MI_Vehicles_2 + MS_Battery_Motor_LDV)'
            comment = (f"{source}; "
                       f"mapping: {row['mapping_type']} <- {subtechs}. See the Mapping sheet.")
        for material in MATERIAL_OUTPUT_ORDER:
            for year in YEARS:
                raw_value = df.loc[material, year]
                value = None if pd.isna(raw_value) else float(raw_value)
                rows.append(('material_intensity', year, tech, material, value, unit, comment))
    return rows


# Write ampl_files/{file_name}.dat from a long-format DataFrame
def create_dat_file_from_excel(df, file_name, out_dir=None, materials=MATERIAL_OUTPUT_ORDER):
    out_dir = out_dir or (_PROJ_ROOT / 'ampl_files')
    out_path = Path(out_dir) / f'{file_name}.dat'
    with open(out_path, 'w', encoding='utf-8', newline='\n') as f:
        f.write("data;\n\n")
        f.write(f"set MATERIALS := {' '.join(materials)} ;\n \n")
        for _, row in df.iterrows():
            value = row['Value']
            if pd.isna(value):
                continue  # skip missing values, params already default to 0
            param_name = row['Parameter']
            index0 = row['index0']
            index1 = row['index1']
            index2 = row['index2']
            unit = '-' if pd.isna(row.get('Unit')) else str(row.get('Unit'))
            comment = '' if pd.isna(row.get('Comment')) else str(row.get('Comment'))
            if pd.isna(index1) and pd.isna(index2):
                f.write(f"let {param_name}['{index0}'] := {value} ; # [{unit}] {comment}\n")
            elif pd.isna(index2):
                f.write(f"let {param_name}['{index0}','{index1}'] := {value} ; # [{unit}] {comment}\n")
            else:
                f.write(f"let {param_name}['{index0}','{index1}','{index2}'] := {value} ; # [{unit}] {comment}\n")
    return out_path


# Build the table and write the .dat (vehicle_source: 'bieuville' = MI_Vehicles_2, 'watari' = flat MI_Vehicles)
def mi_build_table(vehicle_source='bieuville', write_dat=True):
    t0 = time.time()
    mapping = load_mapping()

    # A not_mapped tech is always safe to include (it only ever produces blank
    # cells, which create_dat_file_from_excel skips) -- but a tech claiming *real*
    # data has to already be declared in QC_data.dat, or AMPL chokes on an
    # out-of-set subscript when the .dat file is loaded. Mapping rows for a
    # not-yet-modelled tech stay in the Mapping sheet for later, just excluded
    # from output until it's added to the model.
    canonical_techs = set(canonical.all_target_techs())
    claims_real_data = mapping['mapping_type'] != 'not_mapped'
    not_yet_modeled = set(mapping.index[claims_real_data]) - canonical_techs
    if not_yet_modeled:
        print(f"[build_table] skipping (not yet in QC_data.dat): {sorted(not_yet_modeled)}")
    mapped_scope = set(mapping.index) - not_yet_modeled
    mapping = mapping.loc[sorted(mapped_scope)]

    intensities = mi_compute_all(vehicle_source=vehicle_source)
    print(f"[build_table] computed {len(intensities)} tech intensities in {time.time()-t0:.1f}s")

    mapped_rows = _mapped_rows(mapping, intensities, vehicle_source=vehicle_source)
    print(f"[build_table] built {len(mapped_rows)} rows for the Mapping sheet's {len(mapping)} technologies in {time.time()-t0:.1f}s")

    if write_dat:
        df = pd.DataFrame(mapped_rows, columns=['Parameter', 'index0', 'index1', 'index2', 'Value', 'Unit', 'Comment'])
        out_path = create_dat_file_from_excel(df, OUT_DAT_NAME)
        print(f"[build_table] wrote {out_path.name} in {time.time()-t0:.1f}s")

    print(f"[build_table] total: {time.time()-t0:.1f}s")
    return mapped_rows




# Callable from a notebook; vehicle_source 'bieuville' or 'watari' (both overwrite the same .dat)
def build_intensity(vehicle_source='bieuville', write_dat=True):
    mi_build_table(vehicle_source=vehicle_source, write_dat=write_dat)

    mapping = load_mapping()
    intensities = mi_compute_all(vehicle_source=vehicle_source)
    report = build_report(mapping, intensities)
    print()
    print_report(report)


# ======================================================================================================================
# 2. Recycling rates
# Recycling_rates.xlsx -> ampl_files/Material_recycling.dat
# ======================================================================================================================


# ---- Load Recycling_rates.xlsx (read-only) into tidy DataFrames

# {full_name: short_code} from the 'Materials' sheet of Recycling_rates.xlsx (same convention as load_materials)
def rr_load_materials(path=RR_XLSX):
    return load_materials(path)


YEARS_INT = [2020, 2025, 2030, 2035, 2040, 2045, 2050]


# Sheet as {year: DataFrame(short material code x sub-technology/category)} of recycling-rate fractions
def _load_rr_sheet(sheet_name, path=RR_XLSX):
    import openpyxl
    materials = rr_load_materials(path)
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
def load_rr_energy(path=RR_XLSX):
    return _load_rr_sheet('RR_Energy', path)


# Road-vehicle recycling rates (private + public/freight) by powertrain category
def load_rr_vehicles(path=RR_XLSX):
    return _load_rr_sheet('RR_Vehicles', path)


# Electrolyzer recycling rates (same sub-tech names as MI_H2); all-NaN until populated
def load_rr_h2(path=RR_XLSX):
    return _load_rr_sheet('RR_H2', path)


# RR_Global per-year recycling rates by short material code (YEAR_2020..YEAR_2050), fallback for unmapped techs
def load_rr_global(path=RR_XLSX):
    materials = rr_load_materials(path)
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
def _load_cost_sheet(sheet_name, path=RR_XLSX):
    materials = rr_load_materials(path)
    df = pd.read_excel(path, sheet_name=sheet_name, index_col=0)
    df = df.loc[df.index.notna()]
    unmapped = [name for name in df.index if name not in materials]
    if unmapped:
        raise ValueError(f"{sheet_name} has materials with no short-code mapping: {unmapped}")
    first_col = df.iloc[:, 0]
    return {materials[name]: float(v) for name, v in first_col.items() if pd.notna(v)}


# {short_code: (recycling_cost, primary_material_cost)} in CAD/t, from Cost_recycling_global and Cost_material_global
def load_rr_costs(path=RR_XLSX):
    recycling = _load_cost_sheet('Cost_recycling_global', path)
    primary = _load_cost_sheet('Cost_material_global', path)
    return {mat: (recycling.get(mat, 0.0), primary.get(mat, 0.0)) for mat in recycling.keys() | primary.keys()}


# {short_code: disposal_cost} in CAD/t from Cost_disposal_global (empty until data is added)
def load_disposal_costs(path=RR_XLSX):
    return _load_cost_sheet('Cost_disposal_global', path)


# ---- Compute EnergyScope recycling rates from the literature source data

# Recycling rate by material for tech at one year, read literally from the sheet
def _raw_tech_rate(tech, row, rr_year):
    if row['mapping_type'] == 'not_mapped':
        return pd.Series(float('nan'), index=rr_year.index)

    if row['mapping_type'] in ('direct', 'disaggregate'):
        if len(row['subtechs']) != 1:
            raise ValueError(f"{tech}: '{row['mapping_type']}' expects exactly 1 subtech, got {row['subtechs']}")
        return rr_year[row['subtechs'][0]]

    if row['mapping_type'] == 'aggregate':
        if row['energy_source']:
            raise NotImplementedError(
                f"{tech}: mapping_type='aggregate' with energy_source={row['energy_source']!r} needs "
                f"market-share-weighted blending, but {RR_XLSX.name} has no MS_Energy_Disag/"
                f"MS_Energy_Ag sheets yet (see _weights_for_year for that logic "
                f"once it's needed here)."
            )
        # No market-share category -> fixed equal-weight sum across the listed subtechs.
        return sum(rr_year[subtech] for subtech in row['subtechs'])

    raise ValueError(f"{tech}: unknown mapping_type {row['mapping_type']!r}")


# Recycling rate by material x YEARS for tech, each year read from its own block of the sheet
def compute_tech_rate(tech, row, rr_all_by_year):
    first_year_df = rr_all_by_year[YEARS_INT[0]]
    return pd.DataFrame(
        {f'YEAR_{year_int}': _raw_tech_rate(tech, row, rr_all_by_year[year_int]) for year_int in YEARS_INT},
        index=first_year_df.index,
    )


# {energyscope_tech: DataFrame(material x YEARS)} for every tech in Mapping
def rr_compute_all():
    mapping = load_mapping(path=RR_XLSX)
    validate_mapping(mapping, path=RR_XLSX)

    rr_energy = load_rr_energy()
    rr_vehicles = load_rr_vehicles()
    rr_h2 = load_rr_h2()
    rr_all_by_year = {}
    for year_int in YEARS_INT:
        combined = pd.concat([rr_energy[year_int], rr_vehicles[year_int], rr_h2[year_int]], axis=1)
        rr_all_by_year[year_int] = combined.loc[:, ~combined.columns.duplicated()]

    rates = {tech: compute_tech_rate(tech, row, rr_all_by_year) for tech, row in mapping.iterrows()}

    return rates


# ---- Assemble the long-format recycling-rate table and write Material_recycling.dat

RR_DAT_PATH = _PROJ_ROOT / 'ampl_files' / 'Material_recycling.dat'
_MI_DAT_PATH = _PROJ_ROOT / 'ampl_files' / 'Material_intensity.dat'
_MI_LET_RE = re.compile(r"let material_intensity\['[^']+','([^']+)','([^']+)'\]\s*:=\s*([0-9.eE+-]+)")


# Long-format (year, tech, material, value, comment) rows for every tech in scope
def _rate_rows(mapping, rates, global_rates, canonical_techs):
    rows = []
    fallback_comment = "RR_Global (edited/tiered year-by-year in the sheet itself)"
    for tech, row in mapping.iterrows():
        if tech not in canonical_techs:
            continue
        is_mapped = row['mapping_type'] != 'not_mapped'
        df = rates[tech] if is_mapped else None
        if is_mapped:
            subtechs = ','.join(row['subtechs'])
            specific_comment = f"mapping: {row['mapping_type']} <- {subtechs}. See the Mapping sheet."
        for material in set(global_rates.index) | (set(df.index) if is_mapped else set()):
            for year in YEARS:
                raw_value = df.loc[material, year] if (is_mapped and material in df.index) else float('nan')
                if pd.notna(raw_value):
                    rows.append((year, tech, material, float(raw_value), specific_comment))
                elif material in global_rates.index and pd.notna(global_rates.loc[material, year]):
                    rows.append((year, tech, material, float(global_rates.loc[material, year]), fallback_comment))
    return rows


# {(year, material): best recycling_rate across technologies} (feeds the 'EOL-RR_ramped' sheet)
def _max_achievable_rate(mapped_rows):
    best = {}
    for year, _tech, material, value, _comment in mapped_rows:
        key = (year, material)
        if value > best.get(key, 0.0):
            best[key] = value
    return best


# {material: set(techs)} for techs with a nonzero material_intensity (scopes recycling_cost)
def _techs_with_material(path=_MI_DAT_PATH):
    result = {}
    with open(path, encoding='utf-8') as f:
        for line in f:
            m = _MI_LET_RE.match(line)
            if m is None:
                continue
            tech, material, value = m.group(1), m.group(2), float(m.group(3))
            if value > 0:
                result.setdefault(material, set()).add(tech)
    return result


# (tech, material, recycling_cost) rows, only for techs that contain the material
def _cost_rows(canonical_techs, costs, techs_with_material):
    rows = []
    for material, (recycling_cost, _primary_cost) in costs.items():
        if recycling_cost <= 0:
            continue
        relevant_techs = techs_with_material.get(material, set()) & canonical_techs
        for tech in sorted(relevant_techs):
            rows.append((tech, material, recycling_cost))
    return rows


# (material, primary_material_cost) rows, material-level only
def _primary_cost_rows(costs):
    return [(material, primary_cost) for material, (_rc, primary_cost) in costs.items() if primary_cost > 0]


# (material, disposal_cost) rows, material-level only (empty until Cost_disposal_global has data)
def _disposal_cost_rows(disposal_costs):
    return [(material, value) for material, value in disposal_costs.items() if value > 0]


# Write the recycling_rate / recycling_cost / primary_material_cost / disposal_cost `let` lines (no set header)
def _rr_write_dat(rows, cost_rows, primary_cost_rows, disposal_cost_rows, path=RR_DAT_PATH):
    with open(path, 'w', encoding='utf-8', newline='\n') as f:
        f.write("data;\n\n")
        f.write("# Auto-generated by build_data.py (recycling) from Recycling_rates.xlsx -- do not hand-edit.\n")
        f.write("# recycling_gwp / disposal_gwp are NOT written here (no source data yet) -- AMPL defaults\n")
        f.write("# apply (0). disposal_cost defaults to 50 unless overridden below (Cost_disposal_global sheet).\n\n")
        for year, tech, material, value, comment in rows:
            f.write(f"let recycling_rate['{year}','{tech}','{material}'] := {value} ; # [-] {comment}\n")
        f.write("\n# recycling_cost[tec,mat] (Cost_recycling_global sheet, material-level broadcast to every tech in scope).\n")
        for tech, material, value in cost_rows:
            f.write(f"let recycling_cost['{tech}','{material}'] := {value} ; # [$/t]\n")
        f.write("\n# primary_material_cost[mat] (Cost_material_global sheet, avoided cost of virgin material when recycling).\n")
        for material, value in primary_cost_rows:
            f.write(f"let primary_material_cost['{material}'] := {value} ; # [$/t]\n")
        f.write("\n# disposal_cost[mat] (Cost_disposal_global sheet, overrides the 50 AMPL default).\n")
        for material, value in disposal_cost_rows:
            f.write(f"let disposal_cost['{material}'] := {value} ; # [$/t]\n")
    return path


def rr_build_table(write_dat=True):
    t0 = time.time()
    mapping = load_mapping(path=RR_XLSX)

    # Same not-yet-in-QC_data.dat filtering as mi_build_table.
    canonical_techs = set(canonical.all_target_techs())
    claims_real_data = mapping['mapping_type'] != 'not_mapped'
    not_yet_modeled = set(mapping.index[claims_real_data]) - canonical_techs
    if not_yet_modeled:
        print(f"[rr_build_table] skipping (not yet in QC_data.dat): {sorted(not_yet_modeled)}")
    mapped_scope = set(mapping.index) - not_yet_modeled
    mapping = mapping.loc[sorted(mapped_scope)]

    rates = rr_compute_all()
    print(f"[rr_build_table] computed {len(rates)} tech recycling rates in {time.time()-t0:.1f}s")

    global_rates = load_rr_global()
    rows = _rate_rows(mapping, rates, global_rates, canonical_techs)
    print(f"[rr_build_table] built {len(rows)} rows for {len(mapping)} technologies "
          f"(specific rate or RR_Global fallback) in {time.time()-t0:.1f}s")

    costs = load_rr_costs()
    techs_with_material = _techs_with_material()
    cost_rows = _cost_rows(canonical_techs, costs, techs_with_material)
    primary_cost_rows = _primary_cost_rows(costs)
    print(f"[rr_build_table] built {len(cost_rows)} recycling_cost (scoped to techs that actually "
          f"contain the material) + {len(primary_cost_rows)} primary_material_cost rows "
          f"({len(costs)} materials with cost data) in {time.time()-t0:.1f}s")

    disposal_costs = load_disposal_costs()
    disposal_cost_rows = _disposal_cost_rows(disposal_costs)
    print(f"[rr_build_table] built {len(disposal_cost_rows)} disposal_cost rows "
          f"({len(disposal_costs)} materials with disposal cost data) in {time.time()-t0:.1f}s")

    if write_dat:
        out_path = _rr_write_dat(rows, cost_rows, primary_cost_rows, disposal_cost_rows)
        n_lines = len(rows) + len(cost_rows) + len(primary_cost_rows) + len(disposal_cost_rows)
        print(f"[rr_build_table] wrote {out_path.name} ({n_lines} lines) in {time.time()-t0:.1f}s")

    print(f"[rr_build_table] total: {time.time()-t0:.1f}s")
    return rows




# Callable from a notebook (no argparse/sys.argv)
def build_recycling(write_dat=True):
    rr_build_table(write_dat=write_dat)

    mapping = load_mapping(path=RR_XLSX)
    rates = rr_compute_all()
    report = build_report(mapping, rates)
    print()
    print_report(report)


# ======================================================================================================================
# 3. Recycling processes
# Recycling_rates.xlsx -> ampl_files/Material_recycling_process.dat
# ======================================================================================================================


# ---- Load the recycling-process sheets of Recycling_rates.xlsx (read-only) into tidy DataFrames

# The only technology with real data today: c-Si PV modules, same physical
# panel type mounted on a roof or on the ground -- both AMPL techs share the
# same recycling data. Extend this dict (one entry per new "Technology"
# block that gets filled in) rather than trying to auto-parse the sheets'
# free-text "Subtechnology"/"Sub-technology" labels, which are informational
# only and not always consistent with the real Mapping sheet (e.g.
# Recycling_technologies lists "Sol_C-si_Silver ; Sol_C-si_Copper" for a
# column that, per the real Mapping sheet, only PV_ROOF_C_SI's Silver stream
# actually uses -- Copper isn't wired into material_intensity at all).
PV_C_SI_TECHS = ['PV_ROOF_C_SI', 'PV_GROUND_C_SI']

# Mock technology (no real study yet): Li-ion EV battery
# packs, same NMC-type chemistry assumed for both AMPL techs. CAR_EV/SUV_EV are the two
# highest-volume private EV techs with real material_intensity data (Bieuville).
EV_BATTERY_TECHS = ['CAR_EV', 'SUV_EV']

# Wind turbine PMSG generators -- the only wind sub-techs with permanent-magnet (Nd/Pr/Dy)
# content (DFIG_SCIG/EESG variants have none). Family-level tech names only (no distance-class
# variants exist for wind, so this is a non-issue here, but keep the convention explicit).
WIND_MOTOR_DD_TECHS = ['WIND_ONSHORE_DD_PMSG', 'NEW_WIND_ONSHORE_DD_PMSG']
WIND_MOTOR_GB_TECHS = ['WIND_ONSHORE_GB_PMSG', 'NEW_WIND_ONSHORE_GB_PMSG']
WIND_MOTOR_TECHS = WIND_MOTOR_DD_TECHS + WIND_MOTOR_GB_TECHS

# Every "Technology" label variant seen across the two sheets (Recycling_technologies uses
# 'PV'/'EV'/'Wind'; Recycling_cost's free-text 'Technology' column uses 'Solar PV'/'EV Battery'/
# 'Wind DD'/'Wind GB') -> the EnergyScope techs it applies to. One dict for both sheets since a
# (sheet, label) pair always resolves to the same underlying tech list -- add one entry per new
# label variant rather than trying to normalize the sheets' own free text.
#
# Wind needs 3 label variants, not the usual 1: Recycling_technologies/Collection_rate use plain
# 'Wind' (recovery rate % and collection rate are tech-agnostic within a stream, fine to apply to
# both PMSG variants at once) but Recycling_cost needs DD and GB split into 'Wind DD'/'Wind GB' --
# their Nd:Pr:Dy magnet composition ratios differ enough (see the material intensities section) that a single MCAD/GW
# figure applied to both would convert to inconsistent $/t once divided by each tech's own
# material_intensity (_cost_benefit_rows enforces this consistency per tech).
TECHNOLOGY_LABEL_TO_TECHS = {
    'PV': PV_C_SI_TECHS,
    'Solar PV': PV_C_SI_TECHS,
    'EV': EV_BATTERY_TECHS,
    'EV Battery': EV_BATTERY_TECHS,
    'Wind': WIND_MOTOR_TECHS,
    'Wind DD': WIND_MOTOR_DD_TECHS,
    'Wind GB': WIND_MOTOR_GB_TECHS,
}

# Recycling_technologies' row-3 sub-part label -> RECYCLING_STREAM name. Hand-maintained (not
# auto-derived from the label text) so a typo in the sheet (e.g. 'PV_infrastucture', missing an
# 'r') can't silently produce a stream name that doesn't match what's declared in
# Constraints_recycling_technologies.mod's RECYCLING_STREAM set. Each technology gets its own,
# physically-meaningful stream names -- there's no requirement that every technology have the
# same number of streams or reuse PV's MODULE/INFRASTRUCTURE naming (EV genuinely has three
# separate physical components: battery, chassis, motor).
SUBPART_TO_STREAM = {
    'PV_infrastucture': 'INFRASTRUCTURE',
    'PV_module': 'MODULE',
    'PV module': 'MODULE',
    'EV_battery': 'BATTERY',
    'EV_chassis': 'CHASSIS',
    'EV_motor': 'MOTOR',
    'Wind_motor': 'MOTOR',
}

# Collection_rate's row labels -> which RECYCLING_STREAM they describe (see
# load_collection_rate). "Sol_C-si_Silver" and "Sol_C-si_Copper" are two rows
# both describing the MODULE stream's collection rate (a sheet-authoring
# artifact -- filled in per mapped-material row instead of once per stream).
COLLECTION_RATE_ROW_TO_STREAM = {
    'PV_infrastruture': 'INFRASTRUCTURE',
    'Sol_C-si_Silver': 'MODULE',
    'Sol_C-si_Copper': 'MODULE',
    'EV_battery': 'BATTERY',
    'EV_chassis': 'CHASSIS',
    'EV_motor': 'MOTOR',
    'Wind_motor': 'MOTOR',
}

# Same row labels -> which Technology group they belong to (see TECHNOLOGY_LABEL_TO_TECHS).
COLLECTION_RATE_ROW_TO_TECH_LABEL = {
    'PV_infrastruture': 'PV',
    'Sol_C-si_Silver': 'PV',
    'Sol_C-si_Copper': 'PV',
    'EV_battery': 'EV',
    'EV_chassis': 'EV',
    'EV_motor': 'EV',
    'Wind_motor': 'Wind',
}


def rt_load_materials(path=RR_XLSX):
    return load_materials(path)


# Recycling_technologies in long format: (technology, process, stream, material, recovery_rate)
def load_recycling_technologies(path=RR_XLSX):
    materials = rt_load_materials(path)
    raw = pd.read_excel(path, sheet_name='Recycling_technologies', header=None)

    header_rows = raw.index[raw[0].astype(str).str.strip() == 'Technology']
    if len(header_rows) == 0:
        raise ValueError("Could not find the 'Technology' header row in Recycling_technologies")
    tech_row = header_rows[0]
    subpart_row = tech_row + 1
    process_row = tech_row - 1  # process name lives one row above "Technology"

    data_start = tech_row + 2
    if str(raw.iloc[data_start, 0]).strip() == 'Subtechnology':
        data_start += 1  # skip the informational "Subtechnology" annotation row

    material_col = raw.iloc[data_start:, 0]
    is_material_row = material_col.isin(materials)
    data = raw.iloc[data_start:][is_material_row]

    rows = []
    for col in raw.columns[1:]:
        subpart = raw.iloc[subpart_row, col]
        if pd.isna(subpart):
            continue  # not part of any technology block (e.g. blank spacer column)
        technology = raw.iloc[tech_row, col]
        if pd.isna(technology):
            continue
        subpart_raw = str(subpart).strip()
        subpart_clean = subpart_raw.upper().replace(' ', '_')
        if subpart_raw not in SUBPART_TO_STREAM:
            raise ValueError(f"Recycling_technologies has sub-part {subpart_raw!r} with no entry "
                              f"in SUBPART_TO_STREAM -- add one (see the PV_module/EV_battery pattern)")
        stream_name = SUBPART_TO_STREAM[subpart_raw]
        process = raw.iloc[process_row, col]
        process_name = str(process).strip().upper().replace(' ', '_').removesuffix('_PROCESS') \
            if pd.notna(process) else subpart_clean
        col_values = data[col]
        if col_values.isna().all():
            continue  # e.g. the empty "Sol_CdTe" stub column
        for material_full, value in zip(data[0], col_values):
            if pd.isna(value):
                continue
            rows.append({
                'technology': str(technology).strip(),
                'process': process_name,
                'stream': stream_name,
                'material': materials[material_full],
                'recovery_rate': float(value),
            })
    return pd.DataFrame(rows)


# Recycling_cost sheet: cost [MCAD/GW processed] and revenue [MCAD/kt recovered] per (tech, metal, process)
def load_recycling_cost(path=RR_XLSX):
    materials = rt_load_materials(path)
    df = pd.read_excel(path, sheet_name='Recycling_cost')
    df = df.dropna(subset=['Recycling cost'])
    unmapped = [name for name in df['Metal'] if name not in materials]
    if unmapped:
        raise ValueError(f"Recycling_cost has metals with no short-code mapping: {sorted(set(unmapped))}")
    df['material'] = df['Metal'].map(materials)
    df['process'] = df['Recycling process'].astype(str).str.strip().str.upper()
    return df


# Collection_rate sheet (first table): {technology: {stream: {year: rate}}}
def load_collection_rate(path=RR_XLSX):
    df = pd.read_excel(path, sheet_name='Collection_rate', index_col=0, usecols='A:G')
    df = df.dropna(how='all')  # usecols still reads down to the sheet's overall max_row (a second,
    # unrelated table sits further right and extends past row 6) -- drop the resulting blank tail rows.
    df.columns = [int(c) for c in df.columns]

    unknown = set(df.index) - set(COLLECTION_RATE_ROW_TO_STREAM)
    if unknown:
        raise ValueError(f"Collection_rate has unrecognized row label(s): {sorted(unknown)} "
                          f"-- add them to COLLECTION_RATE_ROW_TO_STREAM/COLLECTION_RATE_ROW_TO_TECH_LABEL")

    result = {}
    for row_label, values in df.iterrows():
        technology = COLLECTION_RATE_ROW_TO_TECH_LABEL[row_label]
        stream = COLLECTION_RATE_ROW_TO_STREAM[row_label]
        year_rates = {year: float(rate) for year, rate in values.items() if pd.notna(rate)}
        by_stream = result.setdefault(technology, {})
        if stream in by_stream and by_stream[stream] != year_rates:
            raise ValueError(f"Collection_rate has conflicting values for {technology!r}/{stream!r}: "
                              f"{by_stream[stream]} (from an earlier row) vs {year_rates} ({row_label!r})")
        by_stream[stream] = year_rates
    return result


# ---- Assemble the long-format competing-recycling-process table and write Material_recycling_process.dat

RT_DAT_PATH = _PROJ_ROOT / 'ampl_files' / 'Material_recycling_process.dat'


def _techs_for_label(label, source_sheet):
    techs = TECHNOLOGY_LABEL_TO_TECHS.get(label)
    if techs is None:
        raise ValueError(f"{source_sheet} has Technology {label!r} with no entry in "
                          f"TECHNOLOGY_LABEL_TO_TECHS -- add one (see PV_C_SI_TECHS/"
                          f"EV_BATTERY_TECHS for the pattern)")
    return techs


# (tech, material, process, stream, recovery_rate) rows for every technology block in Recycling_technologies
def _recovery_rate_rows():
    rt = load_recycling_technologies()
    rows = []
    for _, row in rt.iterrows():
        for tech in _techs_for_label(row['technology'], 'Recycling_technologies'):
            rows.append((tech, row['material'], row['process'], row['stream'], row['recovery_rate']))
    return rows


# (tech, material, process, cost, benefit) rows in $/t, converted from per-GW units via material_intensity
def _cost_benefit_rows(material_intensities):
    cost_df = load_recycling_cost()

    converted = []
    for _, row in cost_df.iterrows():
        mat, proc = row['material'], row['process']
        for tech in _techs_for_label(row['Technology'], 'Recycling_cost'):
            mi = material_intensities[tech]
            mi_t_per_gw = mi.loc[mat, YEARS[0]] if mat in mi.index else 0
            if not mi_t_per_gw or pd.isna(mi_t_per_gw):
                continue  # can't derive a $/t figure with zero t/GW to divide by
            cost_dollar_per_t = row['Recycling cost'] * 1e6 / mi_t_per_gw       # MCAD/GW -> $/t
            benefit_dollar_per_t = row['Revenue'] * 1000                        # MCAD/kt -> $/t
            converted.append((tech, mat, proc, cost_dollar_per_t, benefit_dollar_per_t))

    cost_by_tech_proc = {}
    for tech, mat, proc, cost, _benefit in converted:
        key = (tech, proc)
        if key not in cost_by_tech_proc:
            cost_by_tech_proc[key] = cost
        elif abs(cost_by_tech_proc[key] - cost) > 1e-6 * max(abs(cost), 1):
            raise ValueError(f"Recycling_cost gives inconsistent costs for {tech!r}/{proc!r}: "
                              f"{cost_by_tech_proc[key]:.4g} $/t vs {cost:.4g} $/t (from {mat!r}) "
                              f"-- recycling_cost_process is a per-process figure, every material "
                              f"under the same (Technology, process) must agree once converted")

    rows = [(tech, mat, proc, cost_by_tech_proc[(tech, proc)], benefit)
            for tech, mat, proc, _cost, benefit in converted]
    return rows


# (year, tech, stream, rate) rows for collection_rate_process (one rate per tech and stream)
def _collection_rate_rows():
    by_tech_label = load_collection_rate()
    rows = []
    for technology, by_stream in by_tech_label.items():
        for tech in _techs_for_label(technology, 'Collection_rate'):
            for stream, year_rates in by_stream.items():
                for year_int, rate in year_rates.items():
                    rows.append((f'YEAR_{year_int}', tech, stream, rate))
    return rows


def _rt_write_dat(recovery_rows, cbe_rows, collection_rows, path=RT_DAT_PATH):
    # RECYCLING_STREAM_OF/RECYCLING_PROCESS_OF_STREAM gate Capacity_recycled's domain;
    # RECYCLING_PROCESS_OF gates Recycled_material_process's -- all grouped here (one
    # assignment per tech/stream/material pair, since AMPL sets can only be assigned once).
    processes_by_tech_mat = {}
    streams_by_tech = {}
    processes_by_tech_stream = {}
    for tech, mat, proc, stream, _rate in recovery_rows:
        processes_by_tech_mat.setdefault((tech, mat), []).append(proc)
        streams_by_tech.setdefault(tech, [])
        if stream not in streams_by_tech[tech]:
            streams_by_tech[tech].append(stream)
        processes_by_tech_stream.setdefault((tech, stream), [])
        if proc not in processes_by_tech_stream[(tech, stream)]:
            processes_by_tech_stream[(tech, stream)].append(proc)

    with open(path, 'w', encoding='utf-8', newline='\n') as f:
        f.write("data;\n\n")
        f.write("# Auto-generated by build_data.py (recycling-process) from Recycling_rates.xlsx -- do not hand-edit.\n")
        f.write("# 'recycling_materials_technologies' approach -- entirely separate from Material_recycling.dat\n")
        f.write("# (the simple-rate approach). No set MATERIALS/RECYCLING_PROCESS/RECYCLING_STREAM header here --\n")
        f.write("# already declared in Constraints.mod / Constraints_recycling_technologies.mod.\n\n")

        f.write("# RECYCLING_STREAM_OF / RECYCLING_PROCESS_OF_STREAM: which processes compete for the same\n")
        f.write("# physical batch, grouped by stream (MODULE vs INFRASTRUCTURE) -- see build_data.py.\n")
        for tech, streams in streams_by_tech.items():
            stream_list = ', '.join(f"'{s}'" for s in streams)
            f.write(f"let RECYCLING_STREAM_OF['{tech}'] := {{{stream_list}}} ;\n")
            for stream in streams:
                procs = processes_by_tech_stream[(tech, stream)]
                proc_list = ', '.join(f"'{p}'" for p in procs)
                f.write(f"let RECYCLING_PROCESS_OF_STREAM['{tech}','{stream}'] := {{{proc_list}}} ;\n")

        f.write("\n# RECYCLING_PROCESS_OF: which processes are eligible per (tech, material)\n")
        for (tech, mat), procs in processes_by_tech_mat.items():
            proc_list = ', '.join(f"'{p}'" for p in procs)
            f.write(f"let RECYCLING_PROCESS_OF['{tech}','{mat}'] := {{{proc_list}}} ;\n")

        f.write("\n# recovery rate, same value for every YEAR (no year axis in Recycling_technologies)\n")
        for tech, mat, proc, _stream, rate in recovery_rows:
            for year in YEARS:
                f.write(f"let recovery_rate_process['{tech}','{mat}','{proc}'] := {rate} ;\n")

        f.write("\n# collection rate, per (tech, stream) -- shared by every material of that stream\n")
        for year, tech, stream, rate in collection_rows:
            f.write(f"let collection_rate_process['{year}','{tech}','{stream}'] := {rate} ;\n")

        f.write("\n# cost [$/t] / revenue [$/t] -- converted from Recycling_cost's per-GW-of-source-tech\n")
        f.write("# units using this tech's own material_intensity (see build_data.py)\n")
        for tech, mat, proc, cost, benefit in cbe_rows:
            f.write(f"let recycling_cost_process['{tech}','{mat}','{proc}'] := {cost} ;\n")
            f.write(f"let recycling_benefit_process['{mat}','{proc}'] := {benefit} ;\n")
    return path


# Process every technology block found in the sheets (a new one is a data change only) and write the .dat
def rt_build_table(write_dat=True):
    t0 = time.time()

    material_intensities = mi_compute_all()
    print(f"[rt_build_table] loaded material intensities in {time.time()-t0:.1f}s")

    recovery_rows = _recovery_rate_rows()
    cbe_rows = _cost_benefit_rows(material_intensities)
    collection_rows = _collection_rate_rows()
    print(f"[rt_build_table] built {len(recovery_rows)} recovery-rate rows, {len(cbe_rows)} cost/revenue rows, "
          f"{len(collection_rows)} collection-rate rows in {time.time()-t0:.1f}s")

    if write_dat:
        out_path = _rt_write_dat(recovery_rows, cbe_rows, collection_rows)
        print(f"[rt_build_table] wrote {out_path.name} in {time.time()-t0:.1f}s")

    print(f"[rt_build_table] total: {time.time()-t0:.1f}s")
    return recovery_rows, cbe_rows, collection_rows




# Callable from a notebook (no argparse/sys.argv)
def build_recycling_process(write_dat=True):
    recovery_rows, cbe_rows, collection_rows = rt_build_table(write_dat=write_dat)

    has_cost = {(tech, mat, proc) for tech, mat, proc, *_ in cbe_rows}
    all_combos = {(tech, mat, proc) for tech, mat, proc, _stream, _rate in recovery_rows}
    missing = sorted(all_combos - has_cost)

    print("\nCoverage report:")
    print(f"  recovery rate defined : {len(all_combos)} (tech, material, process) combos")
    print(f"  cost/revenue          : {len(has_cost)} (tech, material, process) combos")
    print(f"  missing cost data     : {len(missing)} -- these fall back to recycling_cost_process=0 (free recycling)")
    if missing:
        for tech, mat, proc in missing:
            print(f"    - {tech} / {mat} / {proc}")


# ======================================================================================================================
# 4. Availability limits
# Material_limits.xlsx -> ampl_files/Material_limits.dat
# ======================================================================================================================


# ---- Build Material_limits.dat from the 'Material_limits' sheet of Material_limits.xlsx (read-only input)

LIMITS_XLSX = _PROJ_ROOT / 'excel_files' / 'Material_limits.xlsx'
LIMITS_SHEET = 'Material_limits'

LIMITS_YEARS = [2020, 2025, 2030, 2035, 2040, 2045, 2050]
# 2020/2025 are always left at their AMPL default (Infinity), whatever the sheet says --
# the 2020_2025 build phase is fixed by historical calibration (fmin_perc_mob, cf.
# shared/data/Shares/out_shares.dat), not by any decision the model can adjust to respect an
# early material limit, so constraining those two years would only risk spurious infeasibility.
WRITTEN_YEARS = [2030, 2035, 2040, 2045, 2050]


# Limits [t/year] by short material code x YEARS (NaN where the sheet has no data)
def load_limits(path=LIMITS_XLSX):
    materials = load_materials()  # {full_name: short_code}, from Material_intensities.xlsx
    df = pd.read_excel(path, sheet_name=LIMITS_SHEET, index_col=0)
    df.columns = [int(c) for c in df.columns]
    unmapped = [name for name in df.index if name not in materials]
    if unmapped:
        raise ValueError(f"{LIMITS_SHEET} has materials with no short-code mapping: {unmapped}")
    df.index = df.index.map(materials)
    return df


# Regenerate Material_limits.dat (unless write_dat=False); return the limits actually written
def limits_build_table(path=LIMITS_XLSX, out_dir=None, write_dat=True):
    df = load_limits(path)
    written = df[WRITTEN_YEARS].dropna(how='all')

    if not write_dat:
        return written

    out_dir = Path(out_dir) if out_dir else (_PROJ_ROOT / 'ampl_files')
    out_path = out_dir / 'Material_limits.dat'
    with open(out_path, 'w', encoding='utf-8', newline='\n') as f:
        f.write("data;\n\n")
        f.write("# Annual material limits [t/year] (limit_material_year), regenerated from\n")
        f.write(f"# excel_files/{LIMITS_XLSX.name} (sheet '{LIMITS_SHEET}') by build_data.py limits --\n")
        f.write("# do not edit by hand: modify the Excel sheet, then rerun the script.\n")
        f.write("#\n")
        f.write("# 2020/2025: always Infinity (so nothing is written here for these two years --\n")
        f.write("# it is already the default value of the parameter), whatever the sheet -- the mix\n")
        f.write("# 2020_2025 is frozen by the historical calibration (fmin_perc_mob, see\n")
        f.write("# shared/data/Shares/out_shares.dat), not by a decision of the model, so imposing\n")
        f.write("# a limit there would only risk an artificial infeasibility.\n\n")
        for mat in written.index:
            for year in WRITTEN_YEARS:
                value = written.loc[mat, year]
                if pd.isna(value):
                    continue
                f.write(f"let limit_material_year['YEAR_{year}','{mat}'] := {value:.6g} ;\n")

    return written




# Callable from a notebook (no argparse/sys.argv)
def build_limits(write_dat=True):
    written = limits_build_table(write_dat=write_dat)
    n_materials = len(written)
    n_values = int(written.notna().sum().sum())
    print(f"[build_data limits] {n_materials} materials, {n_values} (year, material) limits written.")
    return written


# ======================================================================================================================
# 5. Vehicle choice
# body / motor / battery parts of the vehicle intensities -> ampl_files/Vehicle_choice.dat
# ======================================================================================================================



BATTERY_POWERTRAINS = {'HEV', 'PHEV', 'EV', 'HEV_PUBLIC', 'EV_PUBLIC'}
MOBILITY_VARIANTS = re.compile(r'_(SD|MD|LD|ELD)$')

_original_shares = load_battery_motor_market_share  # the real reader, put back once the one-hot shares are no longer needed
BATTERY_MS = MOTOR_MS = CHEMISTRIES = None  # market shares of the Excel, read when build_vehicle_choice() starts
MOTORS = ['PM', 'Ind']


def _with_shares(battery_one_hot=None, motor_one_hot=None):
    """Replace the market shares read by the pipeline: all zero, except one chemistry and/or one motor type at 1."""
    global load_battery_motor_market_share
    battery = BATTERY_MS * 0.0
    if battery_one_hot is not None:
        battery.loc[battery_one_hot] = 1.0
    motor = {m: 0.0 for m in MOTORS}
    if motor_one_hot is not None:
        motor[motor_one_hot] = 1.0
    load_battery_motor_market_share = lambda path=MI_XLSX: (battery, motor)


def _grams_per_vehicle():
    """{powertrain: DataFrame(material x YEARS)} in g/vehicle, with the shares set by _with_shares."""
    materials = list(MATERIAL_OUTPUT_ORDER)
    out = compute_vehicle_intensities_public_transit(materials)
    out.update(compute_vehicle_intensities_bieuville(materials))
    return out


def _parts():
    global load_battery_motor_market_share
    try:
        _with_shares()
        body = _grams_per_vehicle()
        motor, battery = {}, {}
        for m in MOTORS:
            _with_shares(motor_one_hot=m)
            motor[m] = {pt: df - body[pt] for pt, df in _grams_per_vehicle().items()}
        for c in CHEMISTRIES:
            _with_shares(battery_one_hot=c)
            battery[c] = {pt: df - body[pt] for pt, df in _grams_per_vehicle().items()}
    finally:
        load_battery_motor_market_share = _original_shares
    return body, motor, battery


def _battery_techs(mapping):
    """{technology: powertrain} of the model's bare vehicle families that carry a battery and a motor."""
    canonical_techs = set(canonical.all_target_techs())
    techs = {}
    for tech, row in mapping.iterrows():
        if (row['mapping_type'] != 'not_mapped' and tech in canonical_techs and _is_vehicle_row(row)
                and row['subtechs'][0] in BATTERY_POWERTRAINS and not MOBILITY_VARIANTS.search(tech)):
            techs[tech] = row['subtechs'][0]
    return techs


def build_vehicle_choice():
    global BATTERY_MS, MOTOR_MS, CHEMISTRIES
    BATTERY_MS, MOTOR_MS = _original_shares()
    CHEMISTRIES = list(BATTERY_MS.index)
    mapping = load_mapping()
    techs = _battery_techs(mapping)
    ref_size = canonical.load_ref_size()
    body, motor, battery = _parts()
    clip = lambda df: df.where(df.abs() > 1e-12, 0.0).clip(lower=0.0)  # round-off of the differences

    def unit(tech, raw_g):  # g/vehicle -> unit of Material_intensity.dat (same conversion as mi_pipeline.aggregate.compute_tech_intensity)
        family = canonical.family_of(tech)
        return pd.DataFrame({year: raw_g[year] * 1e-6 / ref_size[(year, family)] for year in YEARS}, index=raw_g.index)

    # Check: body + motor shares + battery shares of the Excel = Material_intensity.dat
    pat = re.compile(r"let material_intensity\['(YEAR_\d+)','([^']+)','([^']+)'\] := ([^ ;]+) ;")
    committed = {(m.group(2), m.group(3), m.group(1)): float(m.group(4)) for m in pat.finditer((AMPL_DIR / 'Material_intensity.dat').read_text(encoding='utf-8'))}
    worst = 0.0
    for tech, pt in techs.items():
        for year in YEARS:
            year_int = int(year[5:])
            for mat in MATERIAL_OUTPUT_ORDER:
                total = body[pt].loc[mat, year] + sum(MOTOR_MS[m] * motor[m][pt].loc[mat, year] for m in MOTORS) \
                    + sum(_interpolate_to_year(BATTERY_MS.loc[c], year_int) * battery[c][pt].loc[mat, year] for c in CHEMISTRIES)
                ref = committed.get((tech, mat, year), 0.0)
                value = total * 1e-6 / ref_size[(year, canonical.family_of(tech))]
                worst = max(worst, abs(value - ref) / max(1.0, abs(ref)))
    print(f"[build_data vehicle-choice] {len(techs)} families; body + motor + battery at the Excel shares vs Material_intensity.dat: largest relative gap {worst:.2e}")
    if worst > 1e-9:
        raise SystemExit("the decomposition does not reproduce Material_intensity.dat")

    lines = ["# Intensity of the electric and hybrid vehicles in three additive parts: body, motor (PM / Ind), battery (6 chemistries).",
             "# Generated by build_data.py vehicle-choice; to load after Vehicle_choice.mod: extra_files=['.../Vehicle_choice.mod', '.../Vehicle_choice.dat']", ""]
    for tech, pt in techs.items():
        for year in YEARS:
            for mat in MATERIAL_OUTPUT_ORDER:
                v = float(clip(unit(tech, body[pt]))[year][mat])
                if v:
                    lines.append(f"let veh_body_int['{year}','{tech}','{mat}'] := {v!r} ;")
    for tech, pt in techs.items():
        for m in MOTORS:
            df = clip(unit(tech, motor[m][pt]))
            for year in YEARS:
                for mat in MATERIAL_OUTPUT_ORDER:
                    if df.loc[mat, year]:
                        lines.append(f"let veh_motor_int['{year}','{tech}','{m}','{mat}'] := {float(df.loc[mat, year])!r} ;")
        for c in CHEMISTRIES:
            df = clip(unit(tech, battery[c][pt]))
            for year in YEARS:
                for mat in MATERIAL_OUTPUT_ORDER:
                    if df.loc[mat, year]:
                        lines.append(f"let veh_batt_int['{year}','{tech}','{c}','{mat}'] := {float(df.loc[mat, year])!r} ;")
    # Market shares of MS_Battery_Motor_LDV by year: used for the part that is not free (motor_market_share / batteries_market_share = True)
    lines.append("")
    lines.append("# Market shares of MS_Battery_Motor_LDV: applied to the part that is not free (motor_market_share / batteries_market_share = True)")
    for c in CHEMISTRIES:
        for year in YEARS:
            lines.append(f"let batt_share_ref['{year}','{c}'] := {float(_interpolate_to_year(BATTERY_MS.loc[c], int(year[5:])))!r} ;")
    for m in MOTORS:
        lines.append(f"let motor_share_ref['{m}'] := {float(MOTOR_MS[m])!r} ;")
    (AMPL_DIR / 'Vehicle_choice.dat').write_text('\n'.join(lines) + '\n', encoding='utf-8', newline='\n')
    print(f"[build_data vehicle-choice] wrote Vehicle_choice.dat ({len(lines) - 3} lines)")
    print(f"[build_data vehicle-choice] families: {sorted(techs)}")
    return techs


# ======================================================================================================================
# 6. Big M of the K approach
# Net_demand of reference runs in out/ -> ampl_files/Material_bigM.dat
# ======================================================================================================================



OUT_PATH = _PROJ_ROOT / 'ampl_files' / 'Material_bigM.dat'


def _default_references():
    out = _PROJ_ROOT / 'out'
    return ['1_baseline'] + sorted(p.name for p in out.glob('1_baseline_limits03*') if (p / '_Materials_Results.pkl').exists())


# Callable from a notebook (no argparse/sys.argv); returns the (materials x years) table of M [t]
def build_big_m(references=None, margin=2.0, write_dat=True):
    references = references or _default_references()
    limits = limits_build_table(write_dat=False)  # materials x years [t/yr], NaN = no limit
    net_demand = []
    for case in references:
        path = _PROJ_ROOT / 'out' / case / '_Materials_Results.pkl'
        with open(path, 'rb') as f:
            net_demand.append(pickle.load(f)['Net_demand']['Net_demand'].rename(case))
    peak = pd.concat(net_demand, axis=1).max(axis=1)  # (Years, Materials) -> highest net demand over the reference runs

    big_m = pd.DataFrame(index=limits.index, columns=limits.columns, dtype=float)
    for mat in limits.index:
        for year in limits.columns:
            limit = limits.loc[mat, year]
            if pd.isna(limit):
                continue
            demand = peak.get((f'YEAR_{year}', mat), 0.0)
            big_m.loc[mat, year] = max(margin * (0.0 if pd.isna(demand) else demand) - limit, limit, 1.0)

    if write_dat:
        with open(OUT_PATH, 'w', encoding='utf-8', newline='\n') as f:
            f.write("data;\n\n")
            f.write("# Big M [t] of the K approach (M_relax of Constraints.mod) per (year, material), regenerated by build_data.py big-m --\n")
            f.write("# do not edit by hand. M = max(margin * highest net demand of the reference runs - limit, limit, 1).\n")
            f.write(f"# Reference runs: {', '.join(references)}; margin = {margin:g}.\n")
            f.write("# Load with k.mod: extra_files=['.../ampl_files/k.mod', '.../ampl_files/Material_bigM.dat'].\n\n")
            for mat in big_m.index:
                for year in big_m.columns:
                    if pd.notna(big_m.loc[mat, year]):
                        f.write(f"let M_relax['YEAR_{year}','{mat}'] := {big_m.loc[mat, year]:.6g} ;\n")
    values = big_m.stack()
    print(f"[build_data big-m] {len(values)} (year, material) values from {len(references)} reference run(s), margin {margin:g}: "
          f"M from {values.min():.3g} t ({values.idxmin()[0]}, {values.idxmin()[1]}) to {values.max():.3g} t ({values.idxmax()[0]}, {values.idxmax()[1]}).")
    return big_m


# ======================================================================================================================
# Command line
# ======================================================================================================================

def _cli():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    targets = parser.add_subparsers(dest='target', required=True, metavar='target')
    no_dat = "Compute and print the report without writing the .dat."

    intensity = targets.add_parser('intensity', help="Material_intensity.dat from Material_intensities.xlsx, with a coverage report.")
    intensity.add_argument('--vehicle-source', default='bieuville', choices=['watari', 'bieuville'],
                           help="Vehicle material-intensity source: 'bieuville' (default) or 'watari'.")
    recycling = targets.add_parser('recycling', help="Material_recycling.dat from Recycling_rates.xlsx, with a coverage report.")
    processes = targets.add_parser('recycling-process', help="Material_recycling_process.dat from the recycling-process sheets of Recycling_rates.xlsx.")
    limits = targets.add_parser('limits', help="Material_limits.dat from Material_limits.xlsx.")
    for sub in (intensity, recycling, processes, limits):
        sub.add_argument('--no-dat', action='store_true', help=no_dat)
    targets.add_parser('vehicle-choice', help="Vehicle_choice.dat: body / motor / battery parts of the vehicle intensities.")
    big_m = targets.add_parser('big-m', help="Material_bigM.dat: big M of the K approach, from the Net_demand of reference runs in out/.")
    big_m.add_argument('--references', nargs='+', help="Runs of out/ whose Net_demand sets the size of M (default: 1_baseline and 1_baseline_limits03*).")
    big_m.add_argument('--margin', type=float, default=2.0, help="Safety factor on the highest net demand (default 2).")
    big_m.add_argument('--no-dat', action='store_true', help="Skip writing Material_bigM.dat.")

    args = parser.parse_args()
    if args.target == 'intensity':
        build_intensity(vehicle_source=args.vehicle_source, write_dat=not args.no_dat)
    elif args.target == 'recycling':
        build_recycling(write_dat=not args.no_dat)
    elif args.target == 'recycling-process':
        build_recycling_process(write_dat=not args.no_dat)
    elif args.target == 'limits':
        build_limits(write_dat=not args.no_dat)
    elif args.target == 'vehicle-choice':
        build_vehicle_choice()
    elif args.target == 'big-m':
        build_big_m(references=args.references, margin=args.margin, write_dat=not args.no_dat)


if __name__ == '__main__':
    _cli()
