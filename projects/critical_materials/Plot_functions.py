import re
import sys
from pathlib import Path

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import os

_SRC_DIR = str(Path(__file__).resolve().parent / 'src')
if _SRC_DIR not in sys.path:
    sys.path.insert(0, _SRC_DIR)

from mi_pipeline import canonical

sys.path.insert(0, str(Path(__file__).resolve().parent))
from impacts import absolute_impacts, cumulative_over_years

periods = ['2020_2025', '2025_2030', '2030_2035', '2035_2040', '2040_2045', '2045_2050']
years = ['2025', '2030', '2035', '2040', '2045', '2050']
elec_keywords = ['PV_', 'WIND_', 'HYDRO', 'NUCLEAR', 'CCGT', 'COAL_', 'OCGT_', 'TIDAL', 'GEOTHERMAL', 'AFC', 'PAFC', 'PEMFC', 'SOFC', 'WAVE']
priv_mob_keywords = ['CAR_', 'SUV_']
pub_mob_keywords = ['BUS_', 'SCHOOLBUS_', 'COACH_']

# sector -> y-axis label for plot_new_positive ('elec_prod' in GW; priv_mob/pub_mob converted from pkm/h to a vehicle count)
SECTOR_Y_LABELS = {
    'elec_prod': 'Capacity [GW]',
    'priv_mob': 'Number of vehicles',
    'pub_mob': 'Number of vehicles',
    'h2_prod': 'Capacity [GW]',
}


# '2020_2025' -> 'YEAR_2025' (commissioning year of that rolling-horizon window)
def _period_end_year(period):
    return 'YEAR_' + period.split('_')[1]

# .loc[period] as a flat Series indexed by Technologies (avoids .squeeze() collapsing to a scalar)
def _phase_series(df_phase_tech, period):
    return df_phase_tech.loc[period].iloc[:, 0]


# Technologies from techs_candidate with a positive value in any period (missing rows reindexed to 0)
def _tech_ever_positive(df_phase_tech, techs_candidate):
    any_positive = pd.Series(False, index=techs_candidate)
    for period in periods:
        vals = _phase_series(df_phase_tech, period).reindex(techs_candidate).fillna(0)
        any_positive = any_positive | (vals > 0)
    return list(any_positive[any_positive].index)


def def_elec_positive(results_materials):
    elec_techs = [t for t in results_materials['F_new'].loc['2020_2025'].index
                if any(kw in t for kw in elec_keywords) and not t.startswith(('COAL_GAS', 'HYDRO_STORAGE', 'UNMINEABLE_COAL_SEAM'))]
    return _tech_ever_positive(results_materials['F_new'], elec_techs)

def def_priv_mob_positive(results_materials):

    priv_mob_techs = [t for t in results_materials['F_new'].loc['2020_2025'].index
                if any(kw in t for kw in priv_mob_keywords) and not t.endswith(('_LD', '_MD', '_SD', '_ELD')) ]

    return _tech_ever_positive(results_materials['F_new'], priv_mob_techs)

def def_pub_mob_positive(results_materials):

    pub_mob_techs = [t for t in results_materials['F_new'].loc['2020_2025'].index
                if any(kw in t for kw in pub_mob_keywords) and not t.endswith(('_LD', '_MD', '_SD', '_ELD')) ]

    return _tech_ever_positive(results_materials['F_new'], pub_mob_techs)

def def_h2_prod_positive(results_materials):

    h2_techs = [t for t in results_materials['F_new'].loc['2020_2025'].index
                if t in canonical.ELECTROLYSIS_TECHS]

    return _tech_ever_positive(results_materials['F_new'], h2_techs)

# Shared by plot_new_positive/plot_leaving_positive: (Phases, Technologies) series; pkm/h -> vehicle count for priv_mob/pub_mob
def _phase_tech_bar(df_phase_tech, techs_positive, sector, title):
    df_plot = pd.DataFrame(
        {period: _phase_series(df_phase_tech, period).reindex(techs_positive).fillna(0) for period in periods},
        index=techs_positive
    )

    if sector in ('priv_mob', 'pub_mob'):
        ref_size = canonical.load_ref_size()
        for period in periods:
            year = _period_end_year(period)
            values = []
            for tech in techs_positive:
                family = canonical.family_of(tech)
                r = ref_size.get((year, family))
                if r is None:
                    raise ValueError(f"{tech}: no ref_size entry for family {family!r}, year {year!r} "
                                      f"in {canonical.REF_SIZE_PATH.name}")
                values.append(df_plot.loc[tech, period] / r)
            df_plot[period] = values

    # same style as plot_results.py's Capacity charts: stable _tech_color() and tech name written on the bar segment
    tech_color = load_plot_results()._tech_color
    fig = go.Figure()
    for tech in sorted(techs_positive):
        vals = df_plot.loc[tech, periods].tolist()
        fig.add_bar(
            x=periods, y=vals, name=tech,
            marker_color=tech_color(tech),
            text=[tech if v > 0 else '' for v in vals],
            textposition='inside',
            insidetextanchor='middle',
            textfont=dict(size=10, color='white'),
        )
    fig.update_layout(xaxis_title='Period', yaxis_title=SECTOR_Y_LABELS.get(sector, 'Capacity [GW]'), title=title,
                       showlegend=True, barmode='stack', uniformtext=dict(minsize=8, mode='hide'))
    return fig


def plot_new_positive(results_materials, techs_positive, sector='elec_prod'):
    return _phase_tech_bar(results_materials['F_new'], techs_positive, sector, 'F_new')


# Everything leaving the mix each phase in one chart: F_old (end-of-life) + F_decom (early decommissioning)
def plot_leaving_positive(results_materials, techs_positive, sector='elec_prod'):
    f_old = results_materials['F_old'].iloc[:, 0]
    f_decom = results_materials['F_decom'].groupby(level=[0, -1]).sum().iloc[:, 0]
    f_decom.index.names = f_old.index.names
    leaving = f_old.add(f_decom, fill_value=0).to_frame('F_leaving')
    return _phase_tech_bar(leaving, techs_positive, sector, 'F_old + F_decom (leaving the mix)')


# Filter all_techs down to one sector
def _techs_in_sector(sector, all_techs):
    if sector == 'elec_prod':
        return [t for t in all_techs if any(kw in t for kw in elec_keywords)
                and not t.startswith(('COAL_GAS', 'HYDRO_STORAGE', 'UNMINEABLE_COAL_SEAM'))]
    if sector == 'priv_mob':
        return [t for t in all_techs if any(kw in t for kw in priv_mob_keywords)
                 and not t.endswith(('_MD', '_LD', '_SD', '_ELD')) ]
    if sector == 'pub_mob':
        return [t for t in all_techs if any(kw in t for kw in pub_mob_keywords)
                 and not t.endswith(('_MD', '_LD', '_SD', '_ELD')) ]
    if sector == 'h2_prod':
        return [t for t in all_techs if t in canonical.ELECTROLYSIS_TECHS]
    raise ValueError(f"Unknown sector {sector!r}, expected 'elec_prod', 'priv_mob', 'pub_mob', 'h2_prod', or None")


# Display name for each known sector -- add an entry here (and a case in
# _techs_in_sector above) as more sectors get material intensities.
SECTOR_LABELS = {'elec_prod': 'Electricity production', 'priv_mob': 'Private mobility',
                  'pub_mob': 'Public mobility', 'h2_prod': 'Hydrogen production'}


# Parse MOB_VARIANT_TECHS from Material_mob_family_exclusion.dat (same list as Constraints.mod's exclusion)
def _load_mob_variant_techs():
    path = Path(__file__).resolve().parent / 'ampl_files' / 'Material_mob_family_exclusion.dat'
    text = path.read_text()
    block = text.split('set MOB_VARIANT_TECHS :=', 1)[1].split(';', 1)[0]
    return set(re.findall(r'"([^"]+)"', block))


_MOB_VARIANT_TECHS = _load_mob_variant_techs()


# Drop the SD/MD/LD/ELD variants of mobility family techs from a Material_content_year-shaped series:
# the bare family already carries their sum (same convention as MATERIAL_TECHS), so keeping both would double-count
def _drop_mob_size_variants(mcy):
    all_techs = mcy.index.get_level_values('Technologies').unique()
    variants = [t for t in all_techs if t in _MOB_VARIANT_TECHS]
    return mcy.loc[~mcy.index.get_level_values('Technologies').isin(variants)]


# Net demand as the solver sees it (gross - Used_recycled_material), Series by (Years, Materials)
# Uses results_materials['Net_demand'] if present (recomputed for older pkl); values within 1e-6 of 0 are set to 0.0
def _real_net_demand(results_materials):
    if 'Net_demand' in results_materials:
        net = results_materials['Net_demand']['Net_demand']
    else:
        mcy = _drop_mob_size_variants(results_materials['Material_content_year']['Material_content_year']).groupby(['Years', 'Materials']).sum()
        used = results_materials['Used_recycled_material']['Used_recycled_material']
        net = mcy.sub(used, fill_value=0)
    return net.where(net.abs() > 1e-6, 0.0)


# Marker colors for a net-demand line: negative points (possible for the cumulative one) in orange
def _negative_marker_colors(values, negative_color='#ff7f0e', positive_color='#d62728', size=8):
    return dict(color=[negative_color if v < 0 else positive_color for v in values], size=size)


# One subplot per material, one bar series per year summed across the selected techs (content_key into results_materials)
def _all_material_small_multiples(results_materials, content_key, sector=None, title='', y_title='[t/yr]'):
    mcy = _drop_mob_size_variants(results_materials[content_key][content_key])

    if sector is not None:
        all_techs = mcy.index.get_level_values('Technologies').unique()
        sector_techs = _techs_in_sector(sector, all_techs)
        mcy = mcy.loc[mcy.index.get_level_values('Technologies').isin(sector_techs)]

    demand = mcy.groupby(['Years', 'Materials']).sum().unstack('Materials')  # index=Years, columns=Materials
    demand = demand.loc[:, (demand.fillna(0) != 0).any(axis=0)]  # drop materials that are zero everywhere

    materials = demand.columns.tolist()
    n = len(materials)
    ncols = 6
    nrows = -(-n // ncols)

    fig = make_subplots(rows=nrows, cols=ncols, subplot_titles=materials)

    years_x = [int(y.replace('YEAR_', '')) for y in demand.index.tolist()]

    for i, material in enumerate(materials):
        row = i // ncols + 1
        col = i % ncols + 1
        fig.add_trace(
            go.Bar(x=years_x, y=demand[material].values, name=material, showlegend=False),
            row=row, col=col
        )

    full_title = title
    if sector is not None:
        full_title += f' -- {sector} sector'
    fig.update_layout(height=300 * nrows, title=full_title)
    fig.update_yaxes(title_text=y_title, col=1)
    fig.update_xaxes(tickmode='array', tickvals=years_x, tickangle=45)
    return fig


# (Material x Year) heatmap of net demand / limit_material_year; materials without a limit are dropped
def plot_material_limit_heatmap(results_materials):
    limit_df = results_materials.get('limit_material_year')
    if limit_df is None:
        return None
    limit = limit_df['limit_material_year']
    limit = limit[limit < float('inf')]
    if limit.empty:
        return None

    net_demand = _real_net_demand(results_materials)

    share = (net_demand / limit).dropna().unstack('Materials')
    share = share.reindex(index=[f'YEAR_{y}' for y in years if f'YEAR_{y}' in share.index])
    share.index = [y.replace('YEAR_', '') for y in share.index]
    share = share[sorted(share.columns, key=lambda m: -share[m].max())]  # tightest material first

    fig = go.Figure(go.Heatmap(
        z=share.values.T * 100, x=share.index, y=share.columns,
        colorscale='RdYlGn_r', zmin=0, zmax=100,
        xgap=2, ygap=2,  # visible gap between cells -- without it, adjacent green cells blend together
        colorbar=dict(title='% of limit', ticksuffix='%'),
        hovertemplate='%{y}, %{x}: %{z:.1f}% of limit<extra></extra>',
    ))
    fig.update_layout(
        title='Net demand as a share of the material production limit',
        xaxis_title='Year', yaxis_title=None,
        height=max(300, 28 * len(share.columns) + 120),
        plot_bgcolor='black',  # shows through xgap/ygap as the cell-delimiting grid lines
    )
    return fig


# Recycling benefit per material and year [M$/yr] (avoided primary + disposal cost minus recycling cost), summed over techs
def plot_material_recycling_benefit(results_materials, sector=None):
    return _all_material_small_multiples(
        results_materials, 'Recycling_benefit', sector=sector,
        title='Annual recycling benefit by material', y_title='[M$/yr]')


# One subplot per material: stacked bars by (Technology, RECYCLING_PROCESS); needs materials_recycling_process=True
def plot_recycled_by_tech_and_process(results_materials, sector=None):
    rm = results_materials['Recycled_material_by_process']['Recycled_material_process']
    rm = _drop_mob_size_variants(rm)

    if sector is not None:
        all_techs = rm.index.get_level_values('Technologies').unique()
        sector_techs = _techs_in_sector(sector, all_techs)
        rm = rm.loc[rm.index.get_level_values('Technologies').isin(sector_techs)]

    total_by_material = rm.groupby('Materials').sum()
    materials = sorted(total_by_material[total_by_material.fillna(0) != 0].index.tolist())
    years_present = sorted(rm.index.get_level_values('Years').unique(), key=lambda y: int(y.replace('YEAR_', '')))
    years_x = [int(y.replace('YEAR_', '')) for y in years_present]

    demand = rm.groupby(['Years', 'Technologies', 'RECYCLING_PROCESS', 'Materials']).sum()
    total_by_pair = rm.groupby(['Technologies', 'RECYCLING_PROCESS']).sum()
    tech_proc_pairs = sorted(total_by_pair[total_by_pair.fillna(0) != 0].index.tolist())
    labels = [f'{t} / {p}' for t, p in tech_proc_pairs]
    colors = _color_map(labels)

    ncols = 6
    nrows = max(1, -(-len(materials) // ncols))
    fig = make_subplots(rows=nrows, cols=ncols, subplot_titles=materials)

    legend_shown = set()
    for i, material in enumerate(materials):
        row = i // ncols + 1
        col = i % ncols + 1
        for (tech, proc), label in zip(tech_proc_pairs, labels):
            values = [demand.get((year, tech, proc, material), 0) for year in years_present]
            if all(v == 0 for v in values):
                continue
            fig.add_trace(
                go.Bar(x=years_x, y=values, name=label, legendgroup=label,
                       showlegend=(label not in legend_shown), marker_color=colors[label]),
                row=row, col=col
            )
            legend_shown.add(label)

    fig.update_layout(height=300 * nrows, barmode='stack', title='Recycled material by sub-technology and recycling process')
    fig.update_yaxes(title_text='[t/yr]', col=1)
    fig.update_xaxes(tickmode='array', tickvals=years_x, tickangle=45)
    return fig


# Fixed color per name (keyed by sorted name) so legend and bar colors match across subplots
def _color_map(names):
    palette = px.colors.qualitative.Plotly
    return {name: palette[i % len(palette)] for i, name in enumerate(sorted(names))}


# Consistent color per sector code (including 'other') across all dashboard pages
def _sector_color_map():
    return _color_map(list(SECTOR_LABELS) + ['other'])


# 'Recycled by sector' dashboard page: sector='ALL' stacks every sector, a specific sector breaks it down by technology
def plot_material_recycled_view(results_materials, sector='ALL'):
    if sector != 'ALL' and sector not in SECTOR_LABELS:
        raise ValueError(f"sector must be 'ALL' or one of {list(SECTOR_LABELS)}, got {sector!r}")

    content_key = 'Recycled_material'
    rec = _drop_mob_size_variants(results_materials[content_key][content_key])
    all_techs = rec.index.get_level_values('Technologies').unique()

    if sector == 'ALL':
        tech_to_group = {tech: sec for sec in SECTOR_LABELS for tech in _techs_in_sector(sec, all_techs)}
        group_colors = _sector_color_map()
        group_label = lambda g: SECTOR_LABELS.get(g, 'Other')
    else:
        sector_techs = _techs_in_sector(sector, all_techs)
        rec = rec.loc[rec.index.get_level_values('Technologies').isin(sector_techs)]
        tech_to_group = {tech: tech for tech in sector_techs}
        group_colors = _color_map(sorted(sector_techs))
        group_label = lambda g: g

    rec_df = rec.reset_index()
    rec_df['Group'] = rec_df['Technologies'].map(tech_to_group).fillna('other')

    total_by_group = rec_df.groupby('Group')[content_key].sum()
    groups_present = total_by_group[total_by_group.fillna(0) != 0].index.tolist()

    total_by_material = rec_df.groupby('Materials')[content_key].sum()
    materials = total_by_material[total_by_material.fillna(0) != 0].index.tolist()

    rec_grouped = rec_df.groupby(['Years', 'Group', 'Materials'])[content_key].sum()
    years_present = sorted(rec_df['Years'].unique(), key=lambda y: int(y.replace('YEAR_', '')))
    years_x = [int(y.replace('YEAR_', '')) for y in years_present]

    n = len(materials)
    ncols = 6
    nrows = max(1, -(-n // ncols))
    fig = make_subplots(rows=nrows, cols=ncols, subplot_titles=materials)

    for i, material in enumerate(materials):
        row, col = i // ncols + 1, i % ncols + 1
        for group in groups_present:
            values = [rec_grouped.get((year, group, material), 0) for year in years_present]
            fig.add_trace(
                go.Bar(x=years_x, y=values, name=group_label(group), legendgroup=group,
                       showlegend=(i == 0), marker_color=group_colors[group]),
                row=row, col=col
            )

    if sector == 'ALL':
        title = 'Annual material recycled by sector'
    else:
        title = f"Annual material recycled by technology -- {SECTOR_LABELS[sector]}"
    fig.update_layout(height=300 * nrows, barmode='stack', title=title)
    fig.update_yaxes(title_text='[t/yr]', col=1)
    fig.update_xaxes(tickmode='array', tickvals=years_x, tickangle=45)
    return fig


# 'Old/decommissioned by sector' page: sector='ALL' stacks every sector, a specific sector breaks it down by technology
# Decommissioned_material = F_decom + F_old, before the recycled/disposed split
def plot_material_decommissioned_view(results_materials, sector='ALL'):
    if sector != 'ALL' and sector not in SECTOR_LABELS:
        raise ValueError(f"sector must be 'ALL' or one of {list(SECTOR_LABELS)}, got {sector!r}")

    content_key = 'Decommissioned_material'
    decom = _drop_mob_size_variants(results_materials[content_key][content_key])
    all_techs = decom.index.get_level_values('Technologies').unique()

    if sector == 'ALL':
        tech_to_group = {tech: sec for sec in SECTOR_LABELS for tech in _techs_in_sector(sec, all_techs)}
        group_colors = _sector_color_map()
        group_label = lambda g: SECTOR_LABELS.get(g, 'Other')
    else:
        sector_techs = _techs_in_sector(sector, all_techs)
        decom = decom.loc[decom.index.get_level_values('Technologies').isin(sector_techs)]
        tech_to_group = {tech: tech for tech in sector_techs}
        group_colors = _color_map(sorted(sector_techs))
        group_label = lambda g: g

    decom_df = decom.reset_index()
    decom_df['Group'] = decom_df['Technologies'].map(tech_to_group).fillna('other')

    total_by_group = decom_df.groupby('Group')[content_key].sum()
    groups_present = total_by_group[total_by_group.fillna(0) != 0].index.tolist()

    total_by_material = decom_df.groupby('Materials')[content_key].sum()
    materials = total_by_material[total_by_material.fillna(0) != 0].index.tolist()

    decom_grouped = decom_df.groupby(['Years', 'Group', 'Materials'])[content_key].sum()
    years_present = sorted(decom_df['Years'].unique(), key=lambda y: int(y.replace('YEAR_', '')))
    years_x = [int(y.replace('YEAR_', '')) for y in years_present]

    n = len(materials)
    ncols = 6
    nrows = max(1, -(-n // ncols))
    fig = make_subplots(rows=nrows, cols=ncols, subplot_titles=materials)

    for i, material in enumerate(materials):
        row, col = i // ncols + 1, i % ncols + 1
        for group in groups_present:
            values = [decom_grouped.get((year, group, material), 0) for year in years_present]
            fig.add_trace(
                go.Bar(x=years_x, y=values, name=group_label(group), legendgroup=group,
                       showlegend=(i == 0), marker_color=group_colors[group]),
                row=row, col=col
            )

    if sector == 'ALL':
        title = 'Annual old/decommissioned material by sector (recycling potential)'
    else:
        title = f"Annual old/decommissioned material by technology -- {SECTOR_LABELS[sector]} (recycling potential)"
    fig.update_layout(height=300 * nrows, barmode='stack', title=title)
    fig.update_yaxes(title_text='[t/yr]', col=1)
    fig.update_xaxes(tickmode='array', tickvals=years_x, tickangle=45)
    return fig


_DEMAND_VIEW_TITLES = {'gross': 'Gross', 'after_recycling': 'After recycling'}


# 'Gross/after-recycling demand by sector' page: View (gross/after_recycling) and Sector ('ALL' or one sector's techs) chips
# after_recycling subtracts Recycled_material (not Used_recycled_material), so it differs from the solver's Net_demand
def plot_material_demand_by_sector_view(results_materials, view='gross', sector='ALL'):
    if view not in ('gross', 'after_recycling'):
        raise ValueError(f"view must be 'gross' or 'after_recycling', got {view!r}")
    if sector != 'ALL' and sector not in SECTOR_LABELS:
        raise ValueError(f"sector must be 'ALL' or one of {list(SECTOR_LABELS)}, got {sector!r}")

    mcy = _drop_mob_size_variants(results_materials['Material_content_year']['Material_content_year'])
    if view == 'after_recycling':
        rec = _drop_mob_size_variants(results_materials['Recycled_material']['Recycled_material'])
        demand_series = mcy.sub(rec.rename(mcy.name), fill_value=0)
    else:
        demand_series = mcy
    content_key = demand_series.name

    all_techs = demand_series.index.get_level_values('Technologies').unique()
    if sector == 'ALL':
        tech_to_group = {tech: sec for sec in SECTOR_LABELS for tech in _techs_in_sector(sec, all_techs)}
        group_colors = _sector_color_map()
        group_label = lambda g: SECTOR_LABELS.get(g, 'Other')
    else:
        sector_techs = _techs_in_sector(sector, all_techs)
        demand_series = demand_series.loc[demand_series.index.get_level_values('Technologies').isin(sector_techs)]
        tech_to_group = {tech: tech for tech in sector_techs}
        group_colors = _color_map(sorted(sector_techs))
        group_label = lambda g: g

    demand_df = demand_series.reset_index()
    demand_df['Group'] = demand_df['Technologies'].map(tech_to_group).fillna('other')

    total_by_group = demand_df.groupby('Group')[content_key].sum()
    groups_present = total_by_group[total_by_group.abs().fillna(0) > 1e-9].index.tolist()

    total_by_material = demand_df.groupby('Materials')[content_key].sum()
    materials = total_by_material[total_by_material.abs().fillna(0) > 1e-9].index.tolist()

    demand = demand_df.groupby(['Years', 'Group', 'Materials'])[content_key].sum()
    years_present = sorted(demand_df['Years'].unique(), key=lambda y: int(y.replace('YEAR_', '')))
    years_x = [int(y.replace('YEAR_', '')) for y in years_present]

    n = len(materials)
    ncols = 6
    nrows = max(1, -(-n // ncols))
    fig = make_subplots(rows=nrows, cols=ncols, subplot_titles=materials)

    for i, material in enumerate(materials):
        row, col = i // ncols + 1, i % ncols + 1
        for group in groups_present:
            values = [demand.get((year, group, material), 0) for year in years_present]
            fig.add_trace(
                go.Bar(x=years_x, y=values, name=group_label(group), legendgroup=group,
                       showlegend=(i == 0), marker_color=group_colors[group]),
                row=row, col=col
            )

    view_title = _DEMAND_VIEW_TITLES[view]
    if sector == 'ALL':
        title = f"{view_title} annual material demand by sector"
    else:
        title = f"{view_title} annual material demand by technology -- {SECTOR_LABELS[sector]}"
    fig.update_layout(height=300 * nrows, barmode='relative', title=title)
    fig.update_yaxes(title_text='[t/yr]', col=1)
    fig.update_xaxes(tickmode='array', tickvals=years_x, tickangle=45)
    return fig


# Demand of one material by (Years, Sector) from results_materials[content_key]; returns (series, years_present, sectors_present)
def _material_demand_by_sector_series(results_materials, material, content_key):
    mcy = _drop_mob_size_variants(results_materials[content_key][content_key])
    all_techs = mcy.index.get_level_values('Technologies').unique()

    tech_to_sector = {}
    for sector in SECTOR_LABELS:
        for tech in _techs_in_sector(sector, all_techs):
            tech_to_sector[tech] = sector

    demand_df = mcy.xs(material, level='Materials').reset_index()
    demand_df['Sector'] = demand_df['Technologies'].map(tech_to_sector).fillna('other')

    total_by_sector = demand_df.groupby('Sector')[content_key].sum()
    sectors_present = total_by_sector[total_by_sector.fillna(0) != 0].index.tolist()  # drop sectors that are zero for this material
    demand_df = demand_df[demand_df['Sector'].isin(sectors_present)]

    series = demand_df.groupby(['Years', 'Sector'])[content_key].sum()
    years_present = sorted(demand_df['Years'].unique(), key=lambda y: int(y.replace('YEAR_', '')))
    return series, years_present, sectors_present


# Two subplots for one material: annual (left) and cumulative (right) value by sector, from content_keys=(annual, cumulative)
def _single_material_by_sector_fig(results_materials, material, content_keys, title, subplot_titles):
    sector_colors = _sector_color_map()
    fig = make_subplots(rows=1, cols=2, subplot_titles=subplot_titles)

    for col, content_key in enumerate(content_keys, start=1):
        series, years_present, sectors_present = _material_demand_by_sector_series(
            results_materials, material, content_key)
        years_x = [int(y.replace('YEAR_', '')) for y in years_present]
        for sector in sectors_present:
            values = [series.get((year, sector), 0) for year in years_present]
            if col == 1:
                trace = go.Bar(x=years_x, y=values, name=SECTOR_LABELS.get(sector, 'Other'),
                                legendgroup=sector, showlegend=True, marker_color=sector_colors[sector])
            else:
                # Cumulative reads more naturally as a (stacked) line/area than bars.
                trace = go.Scatter(x=years_x, y=values, mode='lines', stackgroup='cumulative',
                                    name=SECTOR_LABELS.get(sector, 'Other'), legendgroup=sector,
                                    showlegend=False, line_color=sector_colors[sector])
            fig.add_trace(trace, row=1, col=col)
        fig.update_xaxes(tickvals=years_x, tickangle=45, row=1, col=col)

    fig.update_layout(barmode='stack', title=title, legend_title_text='Sector')
    fig.update_yaxes(title_text='[t/yr]', row=1, col=1)
    fig.update_yaxes(title_text='[t]', row=1, col=2)
    return fig


def plot_single_material_demand_by_sector(results_materials, material):
    # Bars: gross demand by sector; net-demand line = gross - Used_recycled_material (>= 0, a negative point is a bug: orange)
    # Cumulative net line = shared.utils' Net_demand_cumulative, not gross_cumulative - Recycled_material_cumulative
    fig = _single_material_by_sector_fig(
        results_materials, material,
        content_keys=('Material_content_year', 'Material_content_cumulative'),
        title=f'Demand for {material} by sector',
        subplot_titles=('Annual demand by sector (gross, net overlaid)', 'Cumulative demand by sector (gross, net overlaid)'),
    )

    mcy = _drop_mob_size_variants(results_materials['Material_content_year']['Material_content_year']).xs(material, level='Materials')
    years_present = sorted(mcy.index.get_level_values('Years').unique(), key=lambda y: int(y.replace('YEAR_', '')))
    years_x = [int(y.replace('YEAR_', '')) for y in years_present]
    net_demand = _real_net_demand(results_materials).xs(material, level='Materials')
    net_vals = [net_demand.get(y, 0) for y in years_present]

    fig.add_trace(
        go.Scatter(x=years_x, y=net_vals, name='Net demand (all sectors)', mode='lines+markers',
                    line_color='#d62728', marker=_negative_marker_colors(net_vals),
                    legendgroup='net_demand', showlegend=True),
        row=1, col=1
    )
    fig.add_hline(y=0, line_dash='dot', line_color='gray', row=1, col=1)

    if 'Net_demand_cumulative' in results_materials:
        net_cum_by_year = results_materials['Net_demand_cumulative']['Net_demand_cumulative'].xs(material, level='Materials')
    else:
        # Fallback for a pkl saved before Net_demand_cumulative existed: same computation
        # (running sum of the per-year net demand, annualised value * 5), done on the fly.
        net_cum_by_year = (net_demand.sort_index() * 5).cumsum()
    net_cum_vals = [net_cum_by_year.get(y, 0) for y in years_present]

    fig.add_trace(
        go.Scatter(x=years_x, y=net_cum_vals, name='Net demand (cumulative, all sectors)', mode='lines+markers',
                    line_color='#d62728', marker=_negative_marker_colors(net_cum_vals),
                    legendgroup='net_demand', showlegend=False),
        row=1, col=2
    )
    fig.add_hline(y=0, line_dash='dot', line_color='gray', row=1, col=2)
    return fig


# Recycled-material counterpart of plot_single_material_demand_by_sector (material recovered from F_decom + F_old)
def plot_single_material_recycled_by_sector(results_materials, material):
    return _single_material_by_sector_fig(
        results_materials, material,
        content_keys=('Recycled_material', 'Recycled_material_cumulative'),
        title=f'Recycled {material} by sector',
        subplot_titles=('Annual recycled', 'Cumulative recycled'),
    )


# Single material, all techs pooled. Left: Decommissioned = Recycled + Disposed.
# Right: gross = Net + Used (this period) + Used (from stock); from_stock = max(Material_stock[y-1] - Material_stock[y], 0)
def plot_material_recycled_disposed_net(results_materials, material):
    rec = _drop_mob_size_variants(results_materials['Recycled_material']['Recycled_material']).xs(material, level='Materials')
    disp = _drop_mob_size_variants(results_materials['Disposed_material']['Disposed_material']).xs(material, level='Materials')
    mcy = _drop_mob_size_variants(results_materials['Material_content_year']['Material_content_year']).xs(material, level='Materials')
    net_demand = _real_net_demand(results_materials).xs(material, level='Materials')
    stock = results_materials['Material_stock']['Material_stock'].xs(material, level='Materials')

    years_present = sorted(mcy.index.get_level_values('Years').unique(), key=lambda y: int(y.replace('YEAR_', '')))
    years_x = [int(y.replace('YEAR_', '')) for y in years_present]

    rec_by_year = rec.groupby('Years').sum()
    disp_by_year = disp.groupby('Years').sum()
    gross_by_year = mcy.groupby('Years').sum()

    rec_vals = [rec_by_year.get(y, 0) for y in years_present]
    disp_vals = [disp_by_year.get(y, 0) for y in years_present]
    gross_vals = [gross_by_year.get(y, 0) for y in years_present]
    net_vals = [net_demand.get(y, 0) for y in years_present]

    from_stock_vals, from_recycling_vals = [], []
    for i, y in enumerate(years_present):
        used = gross_vals[i] - net_vals[i]
        stock_prev = stock.get(years_present[i - 1], 0) if i > 0 else 0
        stock_curr = stock.get(y, 0)
        from_stock = max(stock_prev - stock_curr, 0)
        from_stock_vals.append(from_stock)
        from_recycling_vals.append(used - from_stock)

    fig = make_subplots(rows=1, cols=2, subplot_titles=('Decommissioned: recycled vs disposed', 'Demand: how net demand is reached'))

    fig.add_trace(go.Bar(x=years_x, y=rec_vals, name='Recycled', marker_color='#2ca02c'), row=1, col=1)
    fig.add_trace(go.Bar(x=years_x, y=disp_vals, name='Disposed', marker_color='#7f7f7f'), row=1, col=1)

    fig.add_trace(go.Bar(x=years_x, y=net_vals, name='Net demand', marker_color='#1f77b4',
                          legend='legend2', legendgroup='net_demand'), row=1, col=2)
    # Dotted line tracing the Net demand bar's top edge; shares its legendgroup, no second legend entry
    fig.add_trace(go.Scatter(x=years_x, y=net_vals, name='Net demand', mode='lines+markers',
                              line=dict(color='#d62728', dash='dot'), marker=dict(size=5),
                              legend='legend2', legendgroup='net_demand', showlegend=False), row=1, col=2)
    fig.add_trace(go.Bar(x=years_x, y=from_recycling_vals, name='Used: recycled this period', marker_color='#2ca02c', legend='legend2'), row=1, col=2)
    fig.add_trace(go.Bar(x=years_x, y=from_stock_vals, name='Used: from stock', marker_color='#ff7f0e', legend='legend2'), row=1, col=2)
    fig.add_trace(go.Scatter(x=years_x, y=gross_vals, name='Gross demand', mode='lines+markers',
                              line=dict(color='#1b1f27', dash='dot'), marker=dict(size=5), legend='legend2'), row=1, col=2)

    # 'Show as percentage' switch: left = share of the decommissioned material recycled / disposed, right = share of the gross demand
    # covered by each source (net demand + recycled this period + stock = 100 %). Lists follow the order the traces were added above.
    # Both data sets travel in layout.meta; _add_percentage_switch (applied when the page is saved) draws the switch that applies them
    def _share(values, totals):
        return [100 * v / t if t > 1e-9 else 0 for v, t in zip(values, totals)]
    decommissioned_vals = [r + d for r, d in zip(rec_vals, disp_vals)]
    absolute = [rec_vals, disp_vals, net_vals, net_vals, from_recycling_vals, from_stock_vals, gross_vals]
    percentage = [_share(rec_vals, decommissioned_vals), _share(disp_vals, decommissioned_vals), _share(net_vals, gross_vals),
                  _share(net_vals, gross_vals), _share(from_recycling_vals, gross_vals), _share(from_stock_vals, gross_vals),
                  _share(gross_vals, gross_vals)]
    hover_absolute = '%{x}: %{y:,.4g} t/yr<extra>%{fullData.name}</extra>'
    hover_percentage = '%{x}: %{y:.1f} %<extra>%{fullData.name}</extra>'
    switch = dict(
        absolute=dict(data={'y': absolute, 'hovertemplate': [hover_absolute] * len(absolute)},
                      layout={'yaxis.title.text': '[t/yr]', 'yaxis2.title.text': '[t/yr]', 'yaxis.ticksuffix': '', 'yaxis2.ticksuffix': '',
                              'yaxis.autorange': True, 'yaxis2.autorange': True}),
        percentage=dict(data={'y': percentage, 'hovertemplate': [hover_percentage] * len(percentage)},
                        layout={'yaxis.title.text': '[% of decommissioned]', 'yaxis2.title.text': '[% of gross demand]',
                                'yaxis.ticksuffix': '%', 'yaxis2.ticksuffix': '%', 'yaxis.range': [0, 105], 'yaxis2.range': [0, 105]}),
    )

    # One legend per subplot, placed inside the plot area: the page height follows the viewer's window,
    # so a position in the top margin collides with the subplot title. The switch sits in the top margin, right of the title
    fig.update_layout(
        barmode='stack',
        title=f'{material}: recycling impact on demand',
        legend=dict(x=0.45, y=0.99, xanchor='right', yanchor='top', bgcolor='rgba(255,255,255,0.8)'),
        legend2=dict(x=1.0, y=0.99, xanchor='right', yanchor='top', bgcolor='rgba(255,255,255,0.8)'),
        meta=dict(percentage_switch=switch),
        margin=dict(t=120),
    )
    fig.update_yaxes(title_text='[t/yr]', col=1)
    fig.update_yaxes(title_text='[t/yr]', col=2)
    fig.update_xaxes(tickmode='array', tickvals=years_x, tickangle=45)
    return fig


# iOS-style on/off switch (plotly's updatemenus only offer rectangular buttons). Added to a saved page whose figure carries
# layout.meta['percentage_switch'] = {'absolute': {data, layout}, 'percentage': {data, layout}}: off applies the first, on the second
_PERCENTAGE_SWITCH_HTML = """
<style>
  .pct-switch {position: fixed; top: 46px; right: 28px; z-index: 10; display: flex; align-items: center; gap: 10px; cursor: pointer;
               font: 13px "Open Sans", verdana, arial, sans-serif; color: #444; user-select: none; -webkit-user-select: none;}
  .pct-switch input {position: absolute; opacity: 0; width: 0; height: 0;}
  .pct-track {position: relative; width: 44px; height: 26px; border-radius: 13px; background: #d1d1d6; transition: background .2s;}
  .pct-track::after {content: ''; position: absolute; top: 2px; left: 2px; width: 22px; height: 22px; border-radius: 50%;
                     background: #fff; box-shadow: 0 2px 4px rgba(0, 0, 0, .3); transition: transform .2s;}
  .pct-switch input:checked + .pct-track {background: #34c759;}
  .pct-switch input:checked + .pct-track::after {transform: translateX(18px);}
  .pct-switch input:focus-visible + .pct-track {outline: 2px solid #1f77b4; outline-offset: 2px;}
</style>
<label class="pct-switch"><input type="checkbox" id="pct-toggle"><span class="pct-track"></span>Show as percentage</label>
<script>
  document.getElementById('pct-toggle').addEventListener('change', function () {
    var gd = document.querySelector('.plotly-graph-div');
    var view = gd.layout.meta.percentage_switch[this.checked ? 'percentage' : 'absolute'];
    Plotly.update(gd, view.data, view.layout);
  });
</script>
"""


def _add_percentage_switch(path):
    html = Path(path).read_text(encoding='utf-8')
    Path(path).write_text(html.replace('</body>', _PERCENTAGE_SWITCH_HTML + '</body>', 1), encoding='utf-8')


# (Material x Year) small multiples of Material_stock (banked recycled surplus); materials always at 0 are dropped, None if nothing to show
def plot_material_stock(results_materials):
    stock = results_materials['Material_stock']['Material_stock']

    total_by_material = stock.groupby('Materials').sum()
    materials = total_by_material[total_by_material.abs() > 1e-9].index.tolist()
    if not materials:
        return None

    years_present = sorted(stock.index.get_level_values('Years').unique(), key=lambda y: int(y.replace('YEAR_', '')))
    years_x = [int(y.replace('YEAR_', '')) for y in years_present]

    n = len(materials)
    ncols = 6
    nrows = max(1, -(-n // ncols))
    fig = make_subplots(rows=nrows, cols=ncols, subplot_titles=materials)

    for i, material in enumerate(materials):
        row, col = i // ncols + 1, i % ncols + 1
        values = [stock.get((year, material), 0) for year in years_present]
        fig.add_trace(
            go.Bar(x=years_x, y=values, name=material, showlegend=False, marker_color='#ff7f0e'),
            row=row, col=col
        )

    fig.update_layout(height=300 * nrows, title='Material stock (banked recycled surplus, drawn down as needed)')
    fig.update_yaxes(title_text='[t]', col=1)
    fig.update_xaxes(tickmode='array', tickvals=years_x, tickangle=45)
    return fig


# Materials of Material_impacts.dat that appear in the run, one 'Material impacts' page each
def material_impact_materials(results_materials, indicator='GWP'):
    total = absolute_impacts(results_materials)['Imp_materials_total']
    if total.empty or indicator not in total.index.get_level_values('Indicators'):
        return []
    return sorted(total.xs(indicator, level='Indicators').index.get_level_values('Materials').unique())


# Absolute climate-change impact of one material's flows, annual [kt eq./yr] (left) and cumulative [kt eq.] (right).
# Each bar is the same demand supplied entirely by primary material (no recycling), split into the primary supply still needed,
# the recycling process (hatched) and the impact avoided by recycling (light); the dashed line marks the no-recycling total
def plot_material_impacts(results_materials, material, indicator='GWP'):
    impacts = absolute_impacts(results_materials)
    prim, sec, avoided, reference = (impacts[k].xs(indicator, level='Indicators')
                                     for k in ('Imp_prim', 'Imp_sec', 'Imp_avoided', 'Imp_no_recycling'))
    components = [('primary supply', prim), ('recycling', sec), ('avoided by recycling', avoided)]
    cumulative = {label: cumulative_over_years(series).xs(material, level='Materials') for label, series in components}
    components = [(label, series.xs(material, level='Materials')) for label, series in components]
    reference = reference.xs(material, level='Materials')

    years_present = sorted(reference.index.unique(), key=lambda y: int(y.replace('YEAR_', '')))
    years_x = [int(y.replace('YEAR_', '')) for y in years_present]
    color = px.colors.qualitative.Plotly[0]  # same color on every material page
    # same outline on the three series, so the bars have the same width
    styles = {'primary supply': dict(color=color, line=dict(color=color, width=1.2)),
              'recycling': dict(color=color, pattern=dict(shape='/'), line=dict(color=color, width=1.2)),
              'avoided by recycling': dict(color='rgba({}, {}, {}, 0.3)'.format(*px.colors.hex_to_rgb(color)),
                                           line=dict(color=color, width=1.2))}

    fig = make_subplots(rows=1, cols=2, subplot_titles=('Annual [kt CO2-eq/yr]', 'Cumulative [kt CO2-eq]'))
    for label, series in components:
        fig.add_trace(go.Bar(x=years_x, y=[series.get(y, 0) for y in years_present], name=label,
                             legendgroup=label, marker=styles[label]), row=1, col=1)
        fig.add_trace(go.Bar(x=years_x, y=[cumulative[label].get(y, 0) for y in years_present], name=label,
                             legendgroup=label, showlegend=False, marker=styles[label]), row=1, col=2)

    ref_y = [float(reference.get(y, 0)) for y in years_present]
    ref_style = dict(mode='lines+markers', line=dict(color='black', dash='dash'), legendgroup='reference',
                     name='Without recycling (same demand, all primary)')
    fig.add_trace(go.Scatter(x=years_x, y=ref_y, **ref_style), row=1, col=1)
    fig.add_trace(go.Scatter(x=years_x, y=list(pd.Series(ref_y).mul(5).cumsum()), showlegend=False, **ref_style), row=1, col=2)

    fig.update_layout(barmode='stack', height=450, title=f'{material} {indicator} impact [kt CO2-eq]')
    fig.update_xaxes(tickmode='array', tickvals=years_x, tickangle=45)
    return fig


# Transition cost as optimised [M$], by (phase, sector). OPEX is exact (plot_results' canonical breakdown). CAPEX is C_inv_phase_CRF, the
# annuities of the objective, split by each sector's share of the annualised investment (Cost_breakdown C_inv, mean of the phase's years)
def cost_by_phase_sector(results):
    pr = load_plot_results()
    opex = pr.transition_cost_by_phase_category(results)['OPEX'] * 1000  # B$ -> M$
    opex.index = opex.index.set_levels(opex.index.levels[0].astype(str), level=0)
    cb = results['Cost_breakdown']['C_inv'].dropna().reset_index()
    cb['Category'] = cb['Elements'].apply(pr._fnew_category)
    annual = cb.groupby(['Years', 'Category'])['C_inv'].sum().unstack(fill_value=0)
    capex = {}
    for phase, value in results['C_inv_phase_CRF'].iloc[:, 0].items():
        start, stop = (int(y) for y in phase.split('_'))
        years = [f'YEAR_{y}' for y in sorted({max(start, 2020), stop})]
        share = annual.loc[[y for y in years if y in annual.index]].mean()
        for category, s in (share / share.sum()).items():
            capex[(phase, category)] = value * s
    capex = pd.Series(capex).rename_axis(['Phases', 'Category'])
    return pd.DataFrame({'CAPEX': capex, 'OPEX': opex}).fillna(0)


# First value of a result that is a number or a one-value table (C_material, Transition_cost); 0 if absent
def _scalar(value):
    import numpy as np
    return 0.0 if value is None else float(np.asarray(value).ravel()[0])


# Difference of the transition cost between a run and a reference run [M$]: DataFrame by (phase, sector) with CAPEX and OPEX, and the
# difference of C_material. Their total equals the difference of the Gurobi objective (Transition_cost)
def cost_difference(results, reference):
    diff = cost_by_phase_sector(results).sub(cost_by_phase_sector(reference), fill_value=0)
    return diff, _scalar(results.get('C_material')) - _scalar(reference.get('C_material'))


# Saved results of another run (out/<case>/), the reference of a cost comparison
def _load_reference_results(reference_case):
    import pickle
    folder = Path(__file__).resolve().parent / 'out' / reference_case
    if not (folder / '_Results.pkl').exists():
        raise FileNotFoundError(f"reference_case='{reference_case}': {folder / '_Results.pkl'} not found (run it with save_pkl=True)")
    with open(folder / '_Results.pkl', 'rb') as f:
        results = pickle.load(f)
    if (folder / '_Materials_Results.pkl').exists():
        with open(folder / '_Materials_Results.pkl', 'rb') as f:
            results.update(pickle.load(f))
    return results


# Where the transition cost difference vs a reference run comes from: by sector (left) and by phase (right). None if the costs are missing
def plot_cost_difference(results, reference, case, reference_case):
    try:
        diff, d_materials = cost_difference(results, reference)
    except KeyError:
        return None
    by_sector = diff.groupby(level='Category').sum()
    by_sector['Materials'] = 0.0
    by_sector.loc['MATERIALS (C_material)'] = [0.0, 0.0, d_materials]
    by_sector = by_sector.loc[by_sector.sum(axis=1).sort_values().index]
    total = float(diff.to_numpy().sum()) + d_materials
    objective = _scalar(results['Transition_cost']) - _scalar(reference['Transition_cost'])

    fig = make_subplots(rows=1, cols=2, column_widths=[0.45, 0.55], horizontal_spacing=0.12,
                        subplot_titles=('By sector, whole transition [M$]', 'By phase [M$]'))
    for column, label, color in (('CAPEX', 'CAPEX (annuities)', '#7F3C8D'), ('OPEX', 'OPEX', '#11A579'), ('Materials', 'Materials (C_material)', '#E73F74')):
        fig.add_trace(go.Bar(y=list(by_sector.index), x=by_sector[column], orientation='h', name=label, marker_color=color,
                             legendgroup=label), row=1, col=1)
    fig.add_trace(go.Scatter(y=list(by_sector.index), x=by_sector.sum(axis=1), mode='markers', name='Net', legendgroup='Net',
                             marker=dict(color='black', size=9, symbol='diamond')), row=1, col=1)
    per_phase = diff.sum(axis=1).unstack(fill_value=0)
    phases = [p for p in load_plot_results().TRANS_PHASES if p in per_phase.index]
    palette = px.colors.qualitative.Light24
    colors = {category: palette[i % len(palette)] for i, category in enumerate(sorted(per_phase.columns))}
    for category in per_phase.columns:
        fig.add_trace(go.Bar(x=phases, y=[per_phase.loc[p, category] for p in phases], name=category, marker_color=colors[category],
                             legendgroup=category), row=1, col=2)
    fig.add_trace(go.Scatter(x=phases, y=[per_phase.loc[p].sum() for p in phases], mode='markers', name='Phase total',
                             marker=dict(color='black', size=9, symbol='diamond')), row=1, col=2)
    fig.update_layout(barmode='relative', height=620,
                      title=f'{case} minus {reference_case}: transition cost {total:+,.1f} M CAD (Gurobi objective {objective:+,.1f} M CAD)')
    fig.update_xaxes(tickangle=45, row=1, col=2)
    return fig


_DEFINITIONS_GROUPS = [
    ('Dashboard terms', [
        ('Gross demand', '[t/yr]',
         "Material demand from newly-installed capacity that period"),
        ('Demand after recycling', '[t/yr]',
         "Gross demand minus that period's own Recycled_material"),
        ('Old / Decommissioned material', '[t/yr]',
         "Material from a technology that reaches end-of-life or is decommissioned that period -- "
         "the quantity available for recycling"),
        ('Recycled material', '[t/yr]',
         "Decommissioned material that is collected and treated, available to manufacture new "
         "technologies in Quebec that same period."),
        ('Disposed material', '[t/yr]',
         "Decommissioned material sent to landfill or incineration in Quebec instead of being "
         "recycled"),
        ('Material stock', '[t]',
         "Surplus of recycled material not needed against that period's gross demand -- banked, "
         "available for later use in the horizon."),
        #('Used recycled material', '[t/yr]',
         #"Recycled/banked material actually drawn on to offset gross demand that period"),
        ('Net demand', '[t/yr]',
         "Demand after use of recycled and stocked material"),
        ('Limit closeness', '%',
         "How close Net demand is to the imposed material-availability limit for that year."),
        ('Material impacts', '[kt CO2-eq/yr]',
         "Environmental impact of the material flows and the impact avoided due to recycling"),
    ]),
]


# Static HTML glossary page for the Materials dashboard section (written directly, not a Plotly figure)
def plot_material_definitions():
    groups_html = []
    for group, terms in _DEFINITIONS_GROUPS:
        rows = []
        for name, unit, desc in terms:
            rows.append(f"""
      <div class="row">
        <div class="row-head">
          <h3>{name}</h3>
          <span class="unit">{unit}</span>
        </div>
        <p>{desc}</p>
      </div>""")
        groups_html.append(f"""
    <section>
      <h2>{group}</h2>
      <div class="list">{''.join(rows)}
      </div>
    </section>""")

    return f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><title>Definitions</title>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=IBM+Plex+Mono:wght@500&display=swap">
<style>
  :root {{
    --bg: #f2f4f7; --surface: #ffffff; --line: #e5e8ee;
    --ink: #1b2130; --ink2: #667085; --ink3: #98a2b3;
    --accent: #2563eb; --accent-soft: #eaf0fe; --accent-ink: #1d4ed8;
  }}
  * {{ box-sizing: border-box; }}
  body {{
    font-family: 'Inter', -apple-system, 'Segoe UI', Roboto, Helvetica, sans-serif;
    color: var(--ink); background: var(--bg); margin: 0;
    padding: 36px clamp(20px, 4vw, 48px) 64px;
  }}
  header {{ max-width: 920px; margin: 0 auto 30px; }}
  .eyebrow {{
    font-family: 'IBM Plex Mono', ui-monospace, monospace; font-size: 11px;
    font-weight: 500; letter-spacing: .1em; text-transform: uppercase;
    color: var(--accent); margin: 0 0 8px;
  }}
  h1 {{ font-size: 24px; font-weight: 700; letter-spacing: -.01em; margin: 0; }}

  section {{ max-width: 920px; margin: 0 auto 8px; }}
  h2 {{
    font-size: 12px; font-weight: 700; text-transform: uppercase; letter-spacing: .09em;
    color: var(--ink3); margin: 36px 0 14px; padding-bottom: 10px;
    border-bottom: 1px solid var(--line);
  }}

  .list {{
    background: var(--surface); border: 1px solid var(--line); border-radius: 10px;
    overflow: hidden;
  }}
  .row {{ padding: 16px 20px; border-bottom: 1px solid var(--line); }}
  .row:last-child {{ border-bottom: none; }}
  .row-head {{
    display: flex; align-items: baseline; justify-content: space-between;
    gap: 12px; margin-bottom: 4px;
  }}
  .row h3 {{
    font-size: 14.5px; font-weight: 600; color: var(--accent-ink); margin: 0;
    line-height: 1.3;
  }}
  .row .unit {{
    flex-shrink: 0; font-family: 'IBM Plex Mono', ui-monospace, monospace;
    font-size: 11px; font-weight: 500; color: var(--accent-ink);
    background: var(--accent-soft); border-radius: 5px; padding: 2px 7px;
    white-space: nowrap;
  }}
  .row p {{ color: var(--ink2); font-size: 13px; line-height: 1.55; margin: 0; max-width: 68ch; }}
</style></head>
<body>
  <header>
    <p class="eyebrow">Materials dashboard</p>
    <h1>Definitions</h1>
  </header>
  {''.join(groups_html)}
</body></html>"""


# Drop YEAR_2020 (phase "2015_2020", pre-existing fleet) from every Years-indexed table; other entries pass through
def _drop_year_2020(results_materials):
    filtered = {}
    for key, val in results_materials.items():
        if isinstance(val, (pd.DataFrame, pd.Series)) and 'Years' in (val.index.names or []):
            filtered[key] = val[val.index.get_level_values('Years') != 'YEAR_2020']
        else:
            filtered[key] = val
    return filtered


# Fixed colors for the technologies compared on the same charts (hash colors can collide); registered in plot_results
TECH_COLORS = {
    'HYDRO_RIVER':                    'rgb(229, 134, 6)',
    'HYDRO_STORAGE':                  'rgb(136, 34, 85)',
    'NEW_HYDRO_DAM':                  'rgb(82, 188, 163)',
    'NEW_HYDRO_RIVER':                'rgb(153, 201, 69)',
    'WIND_ONSHORE_DD_EESG':           'rgb(204, 97, 176)',
    'WIND_ONSHORE_DD_PMSG':           'rgb(36, 121, 108)',
    'WIND_ONSHORE_GB_DFIG_SCIG':      'rgb(218, 165, 27)',
    'WIND_ONSHORE_GB_PMSG':           'rgb(47, 138, 196)',
    'WIND_OFFSHORE_DD_EESG':          'rgb(118, 78, 159)',
    'WIND_OFFSHORE_DD_PMSG':          'rgb(237, 100, 90)',
    'WIND_OFFSHORE_GB_DFIG_SCIG':     'rgb(165, 170, 153)',
    'WIND_OFFSHORE_GB_PMSG':          'rgb(127, 60, 141)',
    'NEW_WIND_ONSHORE_DD_EESG':       'rgb(17, 165, 121)',
    'NEW_WIND_ONSHORE_DD_PMSG':       'rgb(57, 105, 172)',
    'NEW_WIND_ONSHORE_GB_DFIG_SCIG':  'rgb(231, 63, 116)',
    'NEW_WIND_ONSHORE_GB_PMSG':       'rgb(128, 186, 90)',
    'PV_ROOF_A_SIGE':                 'rgb(0, 134, 149)',
    'PV_ROOF_CDTE':                   'rgb(207, 28, 144)',
    'PV_ROOF_CIGS':                   'rgb(249, 123, 114)',
    'PV_ROOF_C_SI':                   'rgb(204, 102, 119)',
    'PV_GROUND_A_SIGE':               'rgb(17, 119, 51)',
    'PV_GROUND_CDTE':                 'rgb(51, 34, 136)',
    'PV_GROUND_CIGS':                 'rgb(170, 68, 153)',
    'PV_GROUND_C_SI':                 'rgb(68, 170, 153)',
    'NUCLEAR':                        'rgb(153, 153, 51)',
    'BUS_EV':                         'rgb(221, 204, 119)',
}


# Dashboard pages of this folder: (filename regex, sidebar section, label, filter chips), registered in plot_results
MATERIALS_DASH_SPECS = [
    (r'19_Material_definitions',                    'Materials',         'Definitions',                  ()),
    (r'20_Material_demand_(?P<view>gross|after_recycling)_(?P<sector>ALL|elec_prod|priv_mob|pub_mob|h2_prod)', 'Materials', 'Demand by sector', ('View', 'Sector')),
    (r'21_Material_demand_(?P<d1>.+)',              'Materials',         'Demand by material',           ('Material',)),
    (r'20_Material_decommissioned_(?P<sector>ALL|elec_prod|priv_mob|pub_mob|h2_prod)', 'Materials', 'Old/decommissioned by sector', ('Sector',)),
    (r'22_Material_recycled_(?P<sector>ALL|elec_prod|priv_mob|pub_mob|h2_prod)', 'Materials', 'Recycled by sector', ('Sector',)),
    (r'22_Material_recycled_by_tech_process',       'Materials',         'Recycled by sub-tech/process', ()),
    (r'23_Material_recycled_(?P<d1>.+)',            'Materials',         'Recycled by material',         ('Material',)),
    (r'23c_Material_stock',                         'Materials',         'Material stock',               ()),
    (r'23b_Material_recycled_net_(?P<d1>.+)',       'Materials',         'Recycled vs disposed (net)',   ('Material',)),
    (r'22_Material_recycling_benefit_total',        'Materials',         'Recycling benefit',            ()),
    (r'20_Material_limit_heatmap',                  'Materials',         'Limit closeness (heatmap)',    ()),
    (r'24_Material_new_(?P<d1>.+)',                 'Materials',         'New installations -- materials', ('Sector',)),
    (r'24_Material_leaving_(?P<d1>.+)',             'Materials',         'Leaving the mix (old+decom)',  ('Sector',)),
    (r'26_Material_impacts_(?P<d1>.+)',             'Materials',         'Material impacts',             ('Material',)),
    (r'27_Cost_difference',                         'Costs',             'Cost difference vs reference', ()),
]


# Lazy import of projects/pathway/src/plot_results.py (avoids its plotly/kaleido import cost when no dashboard is built)
def load_plot_results():
    pathway_src = str(Path(__file__).resolve().parent.parent / 'pathway' / 'src')
    if pathway_src not in sys.path:
        sys.path.insert(0, pathway_src)
    import plot_results
    plot_results._FIXED_COLORS.update(TECH_COLORS)
    plot_results._DASH_SPECS.extend(s for s in MATERIALS_DASH_SPECS if s not in plot_results._DASH_SPECS)
    if 'Materials' not in plot_results._DASH_SECTION_ORDER:
        plot_results._DASH_SECTION_ORDER.insert(plot_results._DASH_SECTION_ORDER.index('Other'), 'Materials')
    for view in ('after_recycling', 'gross'):
        if view not in plot_results._DASH_DIM_ORDER:
            plot_results._DASH_DIM_ORDER.insert(1, view)
    return plot_results


# Write this run's material charts into out/<case_study>/graphs/ (or out_dir), then build the shared dashboard
# Recycling pages are only added if Recycled_material is non-zero
def build_materials_dashboard(results_materials, case_study, out_dir=None, auto_open=True, reference_case=None):
    plot_results = load_plot_results()
    results_full = results_materials  # with YEAR_2020, needed for the cost comparison
    results_materials = _drop_year_2020(results_materials)

    if out_dir is None:
        out_dir = Path(__file__).resolve().parent / 'out' / case_study / 'graphs'
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    _save = lambda fig, fname: plot_results._save(fig, str(out_dir), fname)

    sector_techs_positive = {
        'elec_prod': def_elec_positive(results_materials),
        'priv_mob': def_priv_mob_positive(results_materials),
        'pub_mob': def_pub_mob_positive(results_materials),
        'h2_prod': def_h2_prod_positive(results_materials),
    }

    for old_page in ('25_Material_avoided_impact.html', '26_Material_impacts.html'):  # replaced by 26_Material_impacts_<material>
        (out_dir / old_page).unlink(missing_ok=True)
    n_pages = 0

    with open(out_dir / '19_Material_definitions.html', 'w', encoding='utf-8') as f:
        f.write(plot_material_definitions())
    n_pages += 1

    for sector in SECTOR_LABELS:
        techs = sector_techs_positive[sector]

        fig = plot_new_positive(results_materials, techs, sector=sector)
        _save(fig, f'24_Material_new_{sector}.html'); n_pages += 1

        fig = plot_leaving_positive(results_materials, techs, sector=sector)
        _save(fig, f'24_Material_leaving_{sector}.html'); n_pages += 1

    for view in ('gross', 'after_recycling'):
        fig = plot_material_demand_by_sector_view(results_materials, view=view, sector='ALL')
        _save(fig, f'20_Material_demand_{view}_ALL.html'); n_pages += 1
        for sector in SECTOR_LABELS:
            fig = plot_material_demand_by_sector_view(results_materials, view=view, sector=sector)
            _save(fig, f'20_Material_demand_{view}_{sector}.html'); n_pages += 1

    mcy = _drop_mob_size_variants(results_materials['Material_content_year']['Material_content_year'])
    total_by_material = mcy.groupby('Materials').sum()
    materials_present = sorted(total_by_material[total_by_material.fillna(0) != 0].index.tolist())
    for material in materials_present:
        fig = plot_single_material_demand_by_sector(results_materials, material)
        _save(fig, f'21_Material_demand_{material}.html'); n_pages += 1

    fig = plot_material_decommissioned_view(results_materials, sector='ALL')
    _save(fig, '20_Material_decommissioned_ALL.html'); n_pages += 1
    for sector in SECTOR_LABELS:
        fig = plot_material_decommissioned_view(results_materials, sector=sector)
        _save(fig, f'20_Material_decommissioned_{sector}.html'); n_pages += 1

    fig = plot_material_limit_heatmap(results_materials)
    if fig is not None:  # None when no material has a real limit_material_year set
        _save(fig, '20_Material_limit_heatmap.html'); n_pages += 1

    # Recycling pages only if some material was recycled (otherwise make_subplots(rows=0) crashes)
    rec_all = results_materials.get('Recycled_material')
    has_recycling = rec_all is not None and (rec_all['Recycled_material'].fillna(0) != 0).any()
    if has_recycling and 'Recycled_material_cumulative' not in results_materials:
        # Backward-compat: recompute if the key is missing (pkl saved before it existed), as in shared.utils._run_pathway_materials
        results_materials = dict(results_materials)  # don't mutate the caller's dict
        rec_cum_df = (rec_all['Recycled_material'] * 5).reset_index().sort_values(['Technologies', 'Materials', 'Years'])
        rec_cum_df['Recycled_material_cumulative'] = (
            rec_cum_df.groupby(['Technologies', 'Materials'])['Recycled_material'].cumsum()
        )
        results_materials['Recycled_material_cumulative'] = (
            rec_cum_df.set_index(['Years', 'Technologies', 'Materials'])[['Recycled_material_cumulative']].sort_index()
        )
    if has_recycling:
        # Whole-run avoided cost shown as page subtitle: approach 1's Recycling_benefit_cumulative + approach 2's C_material_recycling_tech
        # (negated, it is a cost term), so runs with materials_recycling_process=True and materials_recycling=False aren't under-reported
        benefit_cum_all = results_materials.get('Recycling_benefit_cumulative')
        total_recycling_benefit = None
        if benefit_cum_all is not None and not benefit_cum_all.empty:
            last_year = benefit_cum_all.index.get_level_values('Years').max()
            total_recycling_benefit = float(
                benefit_cum_all.xs(last_year, level='Years')['Recycling_benefit_cumulative'].sum())
        c_material_recycling_tech = results_materials.get('C_material_recycling_tech')
        if c_material_recycling_tech:
            total_recycling_benefit = (total_recycling_benefit or 0) - c_material_recycling_tech

        # Recycling_benefit only covers approach 1's Recycled_material (all-zero with materials_recycling_process=True alone): guard
        benefit_all = results_materials.get('Recycling_benefit')
        has_recycling_benefit = benefit_all is not None and (benefit_all['Recycling_benefit'].fillna(0) != 0).any()
        if has_recycling_benefit:
            fig = plot_material_recycling_benefit(results_materials)
            _save(fig, '22_Material_recycling_benefit_total.html'); n_pages += 1

        fig = plot_material_recycled_view(results_materials, sector='ALL')
        if total_recycling_benefit is not None:
            fig.update_layout(title=f'{fig.layout.title.text} — total avoided cost: {total_recycling_benefit:,.0f} M$')
        _save(fig, '22_Material_recycled_ALL.html'); n_pages += 1
        for sector in SECTOR_LABELS:
            fig = plot_material_recycled_view(results_materials, sector=sector)
            _save(fig, f'22_Material_recycled_{sector}.html'); n_pages += 1

        if results_materials.get('Recycled_material_by_process') is not None:
            fig = plot_recycled_by_tech_and_process(results_materials)
            _save(fig, '22_Material_recycled_by_tech_process.html'); n_pages += 1

        rec = _drop_mob_size_variants(rec_all['Recycled_material'])
        total_recycled_by_material = rec.groupby('Materials').sum()
        materials_recycled = sorted(total_recycled_by_material[total_recycled_by_material.fillna(0) != 0].index.tolist())

        for material in materials_recycled:
            fig = plot_single_material_recycled_by_sector(results_materials, material)
            _save(fig, f'23_Material_recycled_{material}.html'); n_pages += 1

            fig = plot_material_recycled_disposed_net(results_materials, material)
            _save(fig, f'23b_Material_recycled_net_{material}.html'); n_pages += 1
            _add_percentage_switch(out_dir / f'23b_Material_recycled_net_{material}.html')

        fig = plot_material_stock(results_materials)
        if fig is not None:  # None when no material ever banks anything
            _save(fig, '23c_Material_stock.html'); n_pages += 1

        for material in material_impact_materials(results_materials):  # materials of Material_impacts.dat
            _save(plot_material_impacts(results_materials, material), f'26_Material_impacts_{material}.html'); n_pages += 1

    (out_dir / '27_Cost_difference.html').unlink(missing_ok=True)
    if reference_case is not None:
        fig = plot_cost_difference(results_full, _load_reference_results(reference_case), case_study, reference_case)
        if fig is not None:
            _save(fig, '27_Cost_difference.html'); n_pages += 1

    plot_results.create_dashboard(str(out_dir), case_study, auto_open=auto_open)
    print(f'[build_materials_dashboard] wrote {n_pages} pages to {out_dir}')
    return out_dir / 'index.html'


# Write out/index.html: dropdown over every scenario dashboard (scanned from out/, most recent first) switching an iframe
def build_scenario_selector(out_dir=None):
    if out_dir is None:
        out_dir = Path(__file__).resolve().parent / 'out'
    out_dir = Path(out_dir)

    scenarios = []
    for case_dir in out_dir.iterdir():
        index = case_dir / 'graphs' / 'index.html'
        if case_dir.is_dir() and index.exists():
            scenarios.append((case_dir.name, index.stat().st_mtime))
    scenarios.sort(key=lambda s: s[1], reverse=True)

    if not scenarios:
        print(f'[build_scenario_selector] no scenario dashboards found under {out_dir}, nothing written')
        return None

    options_html = '\n'.join(
        f'<option value="{name}/graphs/index.html">{name}</option>'
        for name, _mtime in scenarios
    )
    first_src = f'{scenarios[0][0]}/graphs/index.html'

    html = f'''<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<title>Critical materials -- scenario dashboard</title>
<style>
  body {{ margin: 0; display: flex; flex-direction: column; font-family: Arial, sans-serif; height: 100vh; }}
  #topbar {{ background: #1e1e2e; color: #eee; padding: 10px 16px; display: flex; align-items: center; gap: 10px; box-sizing: border-box; }}
  #topbar label {{ font-weight: bold; }}
  #scenario {{ font-size: 14px; padding: 4px 8px; border-radius: 4px; border: none; }}
  #viewer {{ flex: 1; border: none; }}
</style>
</head>
<body>
<div id="topbar">
  <label for="scenario">Scenario:</label>
  <select id="scenario" onchange="document.getElementById('viewer').src = this.value;">
{options_html}
  </select>
</div>
<iframe id="viewer" src="{first_src}"></iframe>
</body>
</html>'''

    out_path = out_dir / 'index.html'
    with open(out_path, 'w', encoding='utf-8') as f:
        f.write(html)
    print(f'[build_scenario_selector] wrote {out_path} with {len(scenarios)} scenario(s): '
          + ', '.join(name for name, _ in scenarios))
    return out_path
