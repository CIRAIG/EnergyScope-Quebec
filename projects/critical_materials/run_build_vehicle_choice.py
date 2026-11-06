#!/usr/bin/env python3
"""Generate ampl_files/Vehicle_choice.dat (data of Vehicle_choice.mod): the material intensity of electric and hybrid vehicles split in
three additive parts -- body (everything but motor and battery), one motor per type (permanent magnet 'PM' / induction 'Ind') and one
battery per chemistry -- so that the optimiser can pick the motor and the battery of each vehicle family and phase instead of the fixed
market shares of MS_Battery_Motor_LDV.

Every part is computed by the usual pipeline with the market shares replaced by 0 or 1, then converted to the unit of
Material_intensity.dat. With the market shares of the Excel the three parts add up to Material_intensity.dat (checked, any difference stops the script).
The market shares of the Excel are written too: the part of the choice that is not free (motor_market_share / batteries_market_share = True) is forced to them."""
import re
import sys
from pathlib import Path

import pandas as pd

_PROJ_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(_PROJ_ROOT / 'src'))

from mi_pipeline import canonical, sources
from mi_pipeline.aggregate import (YEARS, _interpolate_to_year, _is_vehicle_row, compute_vehicle_intensities_bieuville,
                                   compute_vehicle_intensities_public_transit)
from mi_pipeline.build_table import MATERIAL_OUTPUT_ORDER
from mi_pipeline.mapping import load_mapping

AMPL_DIR = _PROJ_ROOT / 'ampl_files'
BATTERY_POWERTRAINS = {'HEV', 'PHEV', 'EV', 'HEV_PUBLIC', 'EV_PUBLIC'}
MOBILITY_VARIANTS = re.compile(r'_(SD|MD|LD|ELD)$')

_original_shares = sources.load_battery_motor_market_share
BATTERY_MS, MOTOR_MS = _original_shares()
CHEMISTRIES = list(BATTERY_MS.index)
MOTORS = ['PM', 'Ind']


def _with_shares(battery_one_hot=None, motor_one_hot=None):
    """Replace the market shares read by the pipeline: all zero, except one chemistry and/or one motor type at 1."""
    battery = BATTERY_MS * 0.0
    if battery_one_hot is not None:
        battery.loc[battery_one_hot] = 1.0
    motor = {m: 0.0 for m in MOTORS}
    if motor_one_hot is not None:
        motor[motor_one_hot] = 1.0
    sources.load_battery_motor_market_share = lambda path=sources.SOURCE_XLSX: (battery, motor)


def _grams_per_vehicle():
    """{powertrain: DataFrame(material x YEARS)} in g/vehicle, with the shares set by _with_shares."""
    materials = list(MATERIAL_OUTPUT_ORDER)
    out = compute_vehicle_intensities_public_transit(materials)
    out.update(compute_vehicle_intensities_bieuville(materials))
    return out


def _parts():
    _with_shares()
    body = _grams_per_vehicle()
    motor, battery = {}, {}
    for m in MOTORS:
        _with_shares(motor_one_hot=m)
        motor[m] = {pt: df - body[pt] for pt, df in _grams_per_vehicle().items()}
    for c in CHEMISTRIES:
        _with_shares(battery_one_hot=c)
        battery[c] = {pt: df - body[pt] for pt, df in _grams_per_vehicle().items()}
    sources.load_battery_motor_market_share = _original_shares
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


def build():
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
    print(f"[run_build_vehicle_choice] {len(techs)} families; body + motor + battery at the Excel shares vs Material_intensity.dat: largest relative gap {worst:.2e}")
    if worst > 1e-9:
        raise SystemExit("the decomposition does not reproduce Material_intensity.dat")

    lines = ["# Intensite des vehicules electriques et hybrides en trois parts additives : carrosserie, moteur (PM / Ind), batterie (6 chimies).",
             "# Genere par run_build_vehicle_choice.py ; a charger apres Vehicle_choice.mod : extra_files=['.../Vehicle_choice.mod', '.../Vehicle_choice.dat']", ""]
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
    lines.append("# Parts de marche de MS_Battery_Motor_LDV : appliquees a la part qui n'est pas libre (motor_market_share / batteries_market_share = True)")
    for c in CHEMISTRIES:
        for year in YEARS:
            lines.append(f"let batt_share_ref['{year}','{c}'] := {float(_interpolate_to_year(BATTERY_MS.loc[c], int(year[5:])))!r} ;")
    for m in MOTORS:
        lines.append(f"let motor_share_ref['{m}'] := {float(MOTOR_MS[m])!r} ;")
    (AMPL_DIR / 'Vehicle_choice.dat').write_text('\n'.join(lines) + '\n', encoding='utf-8', newline='\n')
    print(f"[run_build_vehicle_choice] wrote Vehicle_choice.dat ({len(lines) - 3} lines)")
    print(f"[run_build_vehicle_choice] families: {sorted(techs)}")
    return techs


if __name__ == '__main__':
    build()
