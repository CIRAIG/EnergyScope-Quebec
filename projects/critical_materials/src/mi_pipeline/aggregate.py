"""Compute EnergyScope material intensities from the literature source data.

Generalizes the tech_groups / get_ms() weighted-average pattern prototyped in
tot_material_demand_ex_post.ipynb (cells 8-9) to every technology in the Mapping
sheet, every material, and the 7 EnergyScope target years.
"""
import pandas as pd

from . import canonical, sources
from .mapping import load_mapping, load_overrides, validate_mapping

# Public-transit powertrains are a distinct vocabulary from the private-fleet ones
# above (ICEV/HEV/PHEV/EV/FCV) -- a bus's 'ICEV' isn't the same g/vehicle number as
# a car's, so they need their own labels rather than colliding in the same table.
PUBLIC_TRANSIT_POWERTRAINS = {'ICEV_PUBLIC', 'HEV_PUBLIC', 'EV_PUBLIC'}
VEHICLE_POWERTRAINS = set(sources.VEHICLE_POWERTRAINS) | PUBLIC_TRANSIT_POWERTRAINS  # {'ICEV','HEV','PHEV','EV','FCV', + public transit}

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


def _weights_for_year(energy_source, ms_table, year, ms_disag, ms_ag):
    """Weight of each MI_Energy subtech within `energy_source` for `year`, interpolated
    from the one or two nearest decades in MS_Energy_Disag/Ag. Both sheets share the
    same 'Energy_Sources' naming scheme (e.g. 'Electricity_Coal')."""
    ms = ms_disag if ms_table == 'Disag' else ms_ag
    matches = ms[ms['Energy_Sources'] == energy_source]
    if matches.empty:
        raise ValueError(
            f"No rows in MS_Energy_{ms_table} match energy_source={energy_source!r}. "
            f"Check the Mapping sheet's energy_source spelling against what's actually "
            f"in the sheet. Available: {sorted(ms['Energy_Sources'].dropna().unique())}"
        )
    rows = matches.set_index('Decade').drop(columns=['Energy_Sources'])
    rows = rows.apply(pd.to_numeric, errors='coerce')
    d1, d2 = YEAR_TO_DECADES[year]
    if d2 is None:
        return rows.loc[d1]
    return (rows.loc[d1] + rows.loc[d2]) / 2


def _is_vehicle_row(row):
    """True if every subtech is one of the MI_Vehicles powertrains (ICEV/HEV/
    PHEV/EV/FCV) -- these need the g/vehicle -> material_intensity unit
    conversion (via ref_size), electricity subtechs don't (already t/GW)."""
    return bool(row['subtechs']) and set(row['subtechs']) <= VEHICLE_POWERTRAINS


def _raw_tech_intensity(tech, row, mi_all, ms_disag, ms_ag):
    """DataFrame indexed by material (all of mi_all.index), one column per YEAR,
    in whatever unit the source table uses natively (t/GW for MI_Energy
    subtechs, g/vehicle for MI_Vehicles powertrains -- compute_tech_intensity()
    converts the latter afterwards)."""
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
            weights = _weights_for_year(row['energy_source'], row['ms_table'], year, ms_disag, ms_ag)
            for subtech in row['subtechs']:
                out[year] = out[year] + weights.get(subtech, 0.0) * mi_all[subtech]
        return out

    raise ValueError(f"{tech}: unknown mapping_type {row['mapping_type']!r}")


def _interpolate_to_year(series, year_int):
    """Value of `series` (indexed by int year) at `year_int`, linearly
    interpolating between the two nearest available years if year_int isn't
    itself one of the series' own years -- e.g. MS_Battery_Motor_LDV has
    2014-2030 then jumps to 2040/2050, so YEAR_2035/YEAR_2045 fall in between.
    Generic over whatever years are actually present, so it keeps working if
    the source sheet's year columns change."""
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


def compute_vehicle_intensities_bieuville(materials):
    """Return {powertrain: DataFrame(material x YEARS)} in g/vehicle, built
    from MI_Vehicles_Bieuville_Clean + MS_Battery_Motor_LDV instead of the
    flat MI_Vehicles table -- used when compute_all(vehicle_source='bieuville').

    ICEV = body only. HEV/PHEV/EV = body + battery_kWh * (battery chemistry
    mix for that year, weighted average of the 6 chemistries) + (fixed PM/
    Induction motor mix, no year variation in the source data). FCV isn't
    covered by Bieuville at all -- falls back to load_mi_vehicles()'s FCV
    column unchanged (flat across years, same as the 'watari' path)."""
    bieuville = sources.load_mi_vehicles_bieuville()
    battery_size = sources.load_battery_size()
    battery_ms, motor_ms = sources.load_battery_motor_market_share()
    mi_vehicles = sources.load_mi_vehicles()

    battery_cols = [c for c in bieuville.columns if c.startswith(sources.BIEUVILLE_BATTERY_PREFIX)]
    chem_of = {c: c[len(sources.BIEUVILLE_BATTERY_PREFIX):].split(' [')[0] for c in battery_cols}
    missing_ms = set(chem_of.values()) - set(battery_ms.index)
    if missing_ms:
        raise ValueError(f"MS_Battery_Motor_LDV has no market share for chemistries: {sorted(missing_ms)}")

    motor = bieuville[sources.BIEUVILLE_MOTOR_COLUMNS].reindex(materials).fillna(0)
    weighted_motor = motor['PM-Motor'] * motor_ms['PM'] + motor['Ind-Motor'] * motor_ms['Ind']

    result = {}
    for powertrain, body_col in sources.BIEUVILLE_BODY_COLUMNS.items():
        body_vals = bieuville[body_col].reindex(materials).fillna(0)
        out = pd.DataFrame(index=materials, columns=YEARS, dtype=float)
        if powertrain == 'ICEV':
            for year in YEARS:
                out[year] = body_vals
            result[powertrain] = out
            continue
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


def compute_vehicle_intensities_public_transit(materials):
    """Return {'ICEV_PUBLIC': DataFrame(material x YEARS), 'HEV_PUBLIC': ...,
    'EV_PUBLIC': ...} in g/vehicle, from MI_Vehicles_Public + MS_Battery_Motor_LDV
    (chemistry/motor-type market share -- no bus/heavy-duty-specific mix table
    exists, so the light-duty one is reused as the best available proxy).
    ICEV_PUBLIC = body + (flat) combustion engine. HEV_PUBLIC additionally has
    its own electric drivetrain on top (still needs an ICE alongside it);
    EV_PUBLIC has no combustion engine at all. Both HEV/EV add battery_kWh *
    (chemistry mix) + motor_kW * (PM/Induction mix), sized per powertrain
    (sources.load_bus_vehicle_stats) unlike the private fleet's fixed motor
    size. No FCV_PUBLIC -- MI_Vehicles_Public's FCV column has no data at all
    (no hydrogen-bus source yet), and no not_mapped Mapping row references it
    anyway. Always used regardless of vehicle_source -- public transit has
    only this one data source, no 'watari'-equivalent flat table."""
    public = sources.load_mi_vehicles_public()
    stats = sources.load_bus_vehicle_stats()
    battery_ms, motor_ms = sources.load_battery_motor_market_share()

    battery_cols = [c for c in public.columns if c.startswith(sources.BIEUVILLE_BATTERY_PREFIX)]
    chem_of = {c: c[len(sources.BIEUVILLE_BATTERY_PREFIX):].split(' [')[0] for c in battery_cols}
    missing_ms = set(chem_of.values()) - set(battery_ms.index)
    if missing_ms:
        raise ValueError(f"MS_Battery_Motor_LDV has no market share for chemistries: {sorted(missing_ms)}")

    weighted_motor_per_kw = sum(
        public[col].reindex(materials).fillna(0) * motor_ms[motor_type]
        for motor_type, col in sources.PUBLIC_MOTOR_COLUMNS.items()
    )

    icev_body = public[sources.PUBLIC_BODY_COLUMNS['ICEV']].reindex(materials).fillna(0)
    icev_engine = public[sources.PUBLIC_ENGINE_COLUMNS['ICEV']].reindex(materials).fillna(0)
    out = pd.DataFrame({year: icev_body + icev_engine for year in YEARS}, index=materials)
    result = {'ICEV_PUBLIC': out}

    for powertrain in ('HEV', 'EV'):
        body = public[sources.PUBLIC_BODY_COLUMNS[powertrain]].reindex(materials).fillna(0)
        engine_col = sources.PUBLIC_ENGINE_COLUMNS.get(powertrain)
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


def compute_tech_intensity(tech, row, mi_all, ms_disag, ms_ag, ref_size,
                            vehicle_intensities_g=None):
    """_raw_tech_intensity(), with the g/vehicle -> material_intensity unit
    conversion applied for vehicle rows: material_intensity = (g/vehicle * 1e-6)
    / ref_size, where ref_size [pkm/h per vehicle] comes from
    shared/data/Techs/out_techs.dat, looked up by the tech's base family (size
    classes share one vehicle spec and one ref_size). This conversion lives
    entirely here -- never written to or documented in the Excel.

    vehicle_intensities_g holds public-transit powertrains (ICEV_PUBLIC/
    HEV_PUBLIC/EV_PUBLIC) unconditionally, plus private-fleet ones
    (compute_vehicle_intensities_bieuville()'s year-varying values) when
    compute_all(vehicle_source='bieuville') -- whenever a tech's powertrain is
    a key in there, it overrides the g/vehicle numerator; otherwise this falls
    back to _raw_tech_intensity's flat MI_Vehicles lookup (private fleet,
    vehicle_source='watari' only -- public transit has no such flat table)."""
    if row['mapping_type'] == 'not_mapped' or not _is_vehicle_row(row):
        return _raw_tech_intensity(tech, row, mi_all, ms_disag, ms_ag)

    powertrain = row['subtechs'][0]
    if vehicle_intensities_g is not None and powertrain in vehicle_intensities_g:
        raw_g = vehicle_intensities_g[powertrain]
    else:
        raw_g = _raw_tech_intensity(tech, row, mi_all, ms_disag, ms_ag)

    family = canonical.family_of(tech)
    out = pd.DataFrame(index=raw_g.index, columns=YEARS, dtype=float)
    for year in YEARS:
        r = ref_size.get((year, family))
        if r is None:
            raise ValueError(f"{tech}: no ref_size entry for family {family!r}, year {year!r} "
                              f"in {canonical.REF_SIZE_PATH.name}")
        out[year] = raw_g[year] * 1e-6 / r
    return out


def apply_overrides(intensities, overrides):
    """Mutate `intensities` (dict tech -> DataFrame(material x YEARS)) in place,
    forcing specific (tech[, material]) entries to a fixed value across all years."""
    for _, orow in overrides.iterrows():
        tech, material, value = orow['energyscope_tech'], orow['material'], orow['override_value']
        if tech not in intensities:
            continue
        if material:
            intensities[tech].loc[material, :] = value
        else:
            intensities[tech].loc[:, :] = value


def compute_all(scenario='baseline', vehicle_source='bieuville'):
    """Return dict {energyscope_tech: DataFrame(material x YEARS)} for every tech in
    the Mapping sheet, with `scenario`'s Overrides sheet rows applied on top.

    vehicle_source: 'bieuville' (default) uses compute_vehicle_intensities_bieuville()
    for the private fleet -- body + battery (chemistry-mix-weighted per year) + motor,
    from MI_Vehicles_Bieuville_Clean + MS_Battery_Motor_LDV -- except for FCV, which
    Bieuville doesn't cover and which always falls back to the MI_Vehicles value
    either way. 'watari' uses the flat MI_Vehicles table instead (same value for
    every year). Public transit (BUS_/SCHOOLBUS_/COACH_) is unaffected by
    vehicle_source -- it always uses compute_vehicle_intensities_public_transit(),
    its only data source."""
    if vehicle_source not in ('watari', 'bieuville'):
        raise ValueError(f"vehicle_source must be 'watari' or 'bieuville', got {vehicle_source!r}")

    mapping = load_mapping()
    validate_mapping(mapping)

    mi_energy = sources.load_mi_energy()
    mi_vehicles = sources.load_mi_vehicles()
    mi_h2 = sources.load_mi_h2()
    mi_all = pd.concat([mi_energy, mi_vehicles, mi_h2], axis=1)
    ms_disag = sources.load_ms_disag()
    ms_ag = sources.load_ms_ag()
    ref_size = canonical.load_ref_size()

    vehicle_intensities_g = compute_vehicle_intensities_public_transit(mi_all.index)
    if vehicle_source == 'bieuville':
        vehicle_intensities_g.update(compute_vehicle_intensities_bieuville(mi_all.index))

    intensities = {
        tech: compute_tech_intensity(tech, row, mi_all, ms_disag, ms_ag, ref_size,
                                      vehicle_intensities_g=vehicle_intensities_g)
        for tech, row in mapping.iterrows()
    }

    overrides = load_overrides(scenario=scenario)
    apply_overrides(intensities, overrides)
    return intensities


if __name__ == '__main__':
    intensities = compute_all()
    print(f"Computed intensities for {len(intensities)} techs.")
    for tech in ['PV_ROOF', 'WIND_ONSHORE', 'NUCLEAR', 'AFC', 'PEMFC']:
        df = intensities[tech]
        print(f"\n{tech} Pd/Pt:")
        print(df.loc[['Pd', 'Pt']])
