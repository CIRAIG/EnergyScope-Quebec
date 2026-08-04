"""Compute EnergyScope recycling rates from the literature source data --
recycling-rate counterpart to mi_pipeline/aggregate.py.

Reuses mi_pipeline.canonical (technology scope) and mi_pipeline.mapping
(Mapping/Overrides loading + validation) as-is, since both are already
workbook-path-parametrized and the Mapping sheet schema is identical between
Material_intensities_energyscope.xlsx and Recycling_rates.xlsx.

Deliberately simpler than mi_pipeline/aggregate.py: a recycling rate has no
per-vehicle g/vehicle -> t/(pkm/h) unit conversion (ref_size lookup) to do,
and Recycling_rates.xlsx has no MS_Energy_Disag/MS_Energy_Ag sheets yet, so
the market-share-weighted 'aggregate' branch (blending several subtechs by
year-varying market share) isn't implemented -- only hit once RR_Energy
actually needs it, which it doesn't yet (see sources.load_rr_energy).
"""
import pandas as pd

from mi_pipeline import canonical
from mi_pipeline.mapping import load_mapping, load_overrides, validate_mapping

from . import sources

YEARS = ['YEAR_2020', 'YEAR_2025', 'YEAR_2030', 'YEAR_2035', 'YEAR_2040', 'YEAR_2045', 'YEAR_2050']


def _raw_tech_rate(tech, row, rr_all):
    """Series indexed by material (all of rr_all.index), the recycling rate
    for `tech` -- constant across YEARS (the source data has no year axis),
    unlike mi_pipeline's market-share-blended intensities."""
    if row['mapping_type'] == 'not_mapped':
        return pd.Series(float('nan'), index=rr_all.index)

    if row['mapping_type'] in ('direct', 'disaggregate'):
        if len(row['subtechs']) != 1:
            raise ValueError(f"{tech}: '{row['mapping_type']}' expects exactly 1 subtech, got {row['subtechs']}")
        return rr_all[row['subtechs'][0]]

    if row['mapping_type'] == 'aggregate':
        if row['energy_source']:
            raise NotImplementedError(
                f"{tech}: mapping_type='aggregate' with energy_source={row['energy_source']!r} needs "
                f"market-share-weighted blending, but {sources.SOURCE_XLSX.name} has no MS_Energy_Disag/"
                f"MS_Energy_Ag sheets yet (see mi_pipeline.aggregate._weights_for_year for that logic "
                f"once it's needed here)."
            )
        # No market-share category -> fixed equal-weight sum across the listed subtechs.
        return sum(rr_all[subtech] for subtech in row['subtechs'])

    raise ValueError(f"{tech}: unknown mapping_type {row['mapping_type']!r}")


def compute_tech_rate(tech, row, rr_all):
    """DataFrame indexed by material, one column per YEAR -- the recycling
    rate replicated across every target year (see _raw_tech_rate's docstring
    for why there's nothing to interpolate here)."""
    rate = _raw_tech_rate(tech, row, rr_all)
    return pd.DataFrame({year: rate for year in YEARS}, index=rr_all.index)


def apply_overrides(rates, overrides):
    """Mutate `rates` (dict tech -> DataFrame(material x YEARS)) in place,
    forcing specific (tech[, material]) entries to a fixed value across all
    years -- same convention as mi_pipeline.aggregate.apply_overrides."""
    for _, orow in overrides.iterrows():
        tech, material, value = orow['energyscope_tech'], orow['material'], orow['override_value']
        if tech not in rates:
            continue
        if material:
            rates[tech].loc[material, :] = value
        else:
            rates[tech].loc[:, :] = value


def compute_all(scenario='baseline'):
    """Return dict {energyscope_tech: DataFrame(material x YEARS)} for every
    tech in the Mapping sheet, with `scenario`'s Overrides sheet rows applied
    on top -- recycling-rate counterpart to mi_pipeline.aggregate.compute_all."""
    mapping = load_mapping(path=sources.SOURCE_XLSX)
    validate_mapping(mapping, path=sources.SOURCE_XLSX)

    rr_energy = sources.load_rr_energy()
    rr_vehicles = sources.load_rr_vehicles()
    rr_vehicles_public = sources.load_rr_vehicles_public()
    rr_h2 = sources.load_rr_h2()
    rr_all = pd.concat([rr_energy, rr_vehicles, rr_vehicles_public, rr_h2], axis=1)
    rr_all = rr_all.loc[:, ~rr_all.columns.duplicated()]  # RR_Vehicles_Public currently duplicates 'Vehicle_private'

    rates = {tech: compute_tech_rate(tech, row, rr_all) for tech, row in mapping.iterrows()}

    overrides = load_overrides(path=sources.SOURCE_XLSX, scenario=scenario)
    apply_overrides(rates, overrides)
    return rates


if __name__ == '__main__':
    rates = compute_all()
    print(f"Computed recycling rates for {len(rates)} techs.")
    for tech in ['CAR_EV', 'CAR_DIESEL', 'WIND_ONSHORE_DD_EESG']:
        df = rates[tech]
        print(f"\n{tech}:")
        print(df.loc[['Co', 'Cu', 'Nd']])
