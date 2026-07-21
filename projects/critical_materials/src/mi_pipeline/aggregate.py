"""Compute EnergyScope material intensities from the literature source data.

Generalizes the tech_groups / get_ms() weighted-average pattern prototyped in
tot_material_demand_ex_post.ipynb (cells 8-9) to every technology in the Mapping
sheet, every material, and the 7 EnergyScope target years.
"""
import pandas as pd

from . import sources
from .mapping import load_mapping, load_overrides, validate_mapping

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


def compute_tech_intensity(tech, row, mi_energy, ms_disag, ms_ag):
    """DataFrame indexed by material (all of mi_energy.index), one column per YEAR,
    for a single EnergyScope technology `tech` described by its Mapping-sheet `row`."""
    materials = mi_energy.index

    if row['mapping_type'] == 'not_mapped':
        # NaN, not 0 -- an unmapped tech has no data, which should render as a blank
        # cell (and be skipped entirely by the .dat writer), not a claimed zero value.
        return pd.DataFrame(float('nan'), index=materials, columns=YEARS)

    if row['mapping_type'] in ('direct', 'disaggregate'):
        # A single literature data point, replicated across every target year --
        # MI_Energy itself doesn't vary by year, only the sub-tech market-share mix
        # does, and there's only one sub-tech here so there's nothing to blend.
        if len(row['subtechs']) != 1:
            raise ValueError(f"{tech}: '{row['mapping_type']}' expects exactly 1 subtech, got {row['subtechs']}")
        subtech = row['subtechs'][0]
        col = mi_energy[subtech]
        return pd.DataFrame({year: col for year in YEARS}, index=materials)

    if row['mapping_type'] == 'aggregate':
        out = pd.DataFrame(0.0, index=materials, columns=YEARS)
        if not row['energy_source']:
            # No market-share category given -> a fixed equal-weight sum across the
            # listed subtechs (e.g. a fossil archetype + a flat CCS addendum), with
            # no time variation.
            total = sum(mi_energy[subtech] for subtech in row['subtechs'])
            for year in YEARS:
                out[year] = total
            return out
        for year in YEARS:
            weights = _weights_for_year(row['energy_source'], row['ms_table'], year, ms_disag, ms_ag)
            for subtech in row['subtechs']:
                out[year] = out[year] + weights.get(subtech, 0.0) * mi_energy[subtech]
        return out

    raise ValueError(f"{tech}: unknown mapping_type {row['mapping_type']!r}")


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


def compute_all(scenario='baseline'):
    """Return dict {energyscope_tech: DataFrame(material x YEARS)} for every tech in
    the Mapping sheet, with `scenario`'s Overrides sheet rows applied on top."""
    mapping = load_mapping()
    validate_mapping(mapping)

    mi_energy = sources.load_mi_energy()
    ms_disag = sources.load_ms_disag()
    ms_ag = sources.load_ms_ag()

    intensities = {
        tech: compute_tech_intensity(tech, row, mi_energy, ms_disag, ms_ag)
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
