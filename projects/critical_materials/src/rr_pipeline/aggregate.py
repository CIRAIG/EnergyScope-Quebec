# Compute EnergyScope recycling rates from the literature source data (counterpart of mi_pipeline/aggregate.py)
import pandas as pd

from mi_pipeline import canonical
from mi_pipeline.mapping import load_mapping, load_overrides, validate_mapping

from . import sources

YEARS = ['YEAR_2020', 'YEAR_2025', 'YEAR_2030', 'YEAR_2035', 'YEAR_2040', 'YEAR_2045', 'YEAR_2050']


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
                f"market-share-weighted blending, but {sources.SOURCE_XLSX.name} has no MS_Energy_Disag/"
                f"MS_Energy_Ag sheets yet (see mi_pipeline.aggregate._weights_for_year for that logic "
                f"once it's needed here)."
            )
        # No market-share category -> fixed equal-weight sum across the listed subtechs.
        return sum(rr_year[subtech] for subtech in row['subtechs'])

    raise ValueError(f"{tech}: unknown mapping_type {row['mapping_type']!r}")


# Recycling rate by material x YEARS for tech, each year read from its own block of the sheet
def compute_tech_rate(tech, row, rr_all_by_year):
    first_year_df = rr_all_by_year[sources.YEARS_INT[0]]
    return pd.DataFrame(
        {f'YEAR_{year_int}': _raw_tech_rate(tech, row, rr_all_by_year[year_int]) for year_int in sources.YEARS_INT},
        index=first_year_df.index,
    )


# Force specific (tech[, material]) rates to a fixed value across all years, in place
def apply_overrides(rates, overrides):
    for _, orow in overrides.iterrows():
        tech, material, value = orow['energyscope_tech'], orow['material'], orow['override_value']
        if tech not in rates:
            continue
        if material:
            rates[tech].loc[material, :] = value
        else:
            rates[tech].loc[:, :] = value


# {energyscope_tech: DataFrame(material x YEARS)} for every tech in Mapping, with the scenario's Overrides applied
def compute_all(scenario='baseline'):
    mapping = load_mapping(path=sources.SOURCE_XLSX)
    validate_mapping(mapping, path=sources.SOURCE_XLSX)

    rr_energy = sources.load_rr_energy()
    rr_vehicles = sources.load_rr_vehicles()
    rr_h2 = sources.load_rr_h2()
    rr_all_by_year = {}
    for year_int in sources.YEARS_INT:
        combined = pd.concat([rr_energy[year_int], rr_vehicles[year_int], rr_h2[year_int]], axis=1)
        rr_all_by_year[year_int] = combined.loc[:, ~combined.columns.duplicated()]

    rates = {tech: compute_tech_rate(tech, row, rr_all_by_year) for tech, row in mapping.iterrows()}

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
