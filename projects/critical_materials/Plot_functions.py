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

periods = ['2020_2025', '2025_2030', '2030_2035', '2035_2040', '2040_2045', '2045_2050']
years = ['2025', '2030', '2035', '2040', '2045', '2050']
elec_keywords = ['PV_', 'WIND_', 'HYDRO', 'NUCLEAR', 'CCGT', 'COAL_', 'OCGT_', 'TIDAL', 'GEOTHERMAL', 'AFC', 'PAFC', 'PEMFC', 'SOFC', 'WAVE']
priv_mob_keywords = ['CAR_', 'SUV_']
pub_mob_keywords = ['BUS_', 'SCHOOLBUS_', 'COACH_']

# sector -> y-axis label used by plot_new_positive. 'elec_prod' plots F_new as-is
# (GW); 'priv_mob'/'pub_mob' convert pkm/h to a vehicle count first (see
# _period_end_year and plot_new_positive below).
SECTOR_Y_LABELS = {
    'elec_prod': 'Capacity [GW]',
    'priv_mob': 'Number of vehicles',
    'pub_mob': 'Number of vehicles',
    'h2_prod': 'Capacity [GW]',
}


def _period_end_year(period):
    """'2020_2025' -> 'YEAR_2025': F_new's commissioning year for that rolling-
    horizon window, same convention as the YEARS used in mi_pipeline.aggregate
    to look up ref_size."""
    return 'YEAR_' + period.split('_')[1]

def _phase_series(df_phase_tech, period):
    """`.loc[period]` as a flat pd.Series indexed by Technologies (its single
    value column, whatever it's named) -- avoids `.squeeze()` collapsing to a
    bare scalar when only one technology is present that period."""
    return df_phase_tech.loc[period].iloc[:, 0]


def _tech_ever_positive(df_phase_tech, techs_candidate):
    """Technologies from techs_candidate with a positive value in ANY period.
    Not every period has a row for every technology (only those eligible for
    construction/decommissioning that phase are present) -- reindex to 0
    rather than KeyError on the ones missing that period."""
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

def _phase_tech_bar(df_phase_tech, techs_positive, sector, title):
    """Shared by plot_new_positive/plot_leaving_positive: df_phase_tech is a
    single-column DataFrame indexed by (Phases, Technologies) -- same shape as
    results_materials['F_new']/['F_old']. Converts pkm/h to a vehicle count for
    priv_mob/pub_mob (same lookup as mi_pipeline.aggregate)."""
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

    #ADDED BY PAOLO (to validate) -- same style as plot_results.py's Capacity-section charts
    # (2_F_new_*/3_F_old_*): _tech_color() for a color stable across every chart/case-study,
    # and the tech name written on the bar segment itself instead of relying on the legend.
    tech_color = _import_plot_results()._tech_color
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


#ADDED BY PAOLO (to validate)
def plot_leaving_positive(results_materials, techs_positive, sector='elec_prod'):
    """Everything leaving the technology mix each phase, combined into one
    chart: F_old (natural end-of-life retirement) + F_decom (forced early
    decommissioning, summed over the built-phase dimension -- same convention
    as plot_decom_positive), added together into one (Phases, Technologies)
    series so both exit routes show on the same stacked bars."""
    f_old = results_materials['F_old'].iloc[:, 0]
    f_decom = results_materials['F_decom'].groupby(level=[0, -1]).sum().iloc[:, 0]
    f_decom.index.names = f_old.index.names
    leaving = f_old.add(f_decom, fill_value=0).to_frame('F_leaving')
    return _phase_tech_bar(leaving, techs_positive, sector, 'F_old + F_decom (leaving the mix)')


def _techs_in_sector(sector, all_techs):
    """Filter `all_techs` down to one sector, by keyword/electrolysis-tech
    membership."""
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


def _load_mob_variant_techs():
    """Parse ampl_files/Material_mob_family_exclusion.dat's `set
    MOB_VARIANT_TECHS := "..." "..." ... ;` -- the SAME auto-generated,
    verified list of mobility distance-variant tech names excluded from
    Constraints.mod's MATERIAL_TECHS (single source of truth, kept in sync
    with the AMPL model instead of a separate hand-maintained Python keyword
    list)."""
    path = Path(__file__).resolve().parent / 'ampl_files' / 'Material_mob_family_exclusion.dat'
    text = path.read_text()
    block = text.split('set MOB_VARIANT_TECHS :=', 1)[1].split(';', 1)[0]
    return set(re.findall(r'"([^"]+)"', block))


_MOB_VARIANT_TECHS = _load_mob_variant_techs()


def _drop_mob_size_variants(mcy):
    """Drop the SD/MD/LD/ELD distance-class variants of every mobility
    "family" tech (private/public/freight, road/rail/air/marine -- e.g.
    CAR_DIESEL_SD, COACH_DIESEL_MD, TRUCK_SH_EV_MD, TRAIN_FREIGHT_ELEC_LD)
    from a Material_content_year-shaped series. F_new of the bare family tech
    (e.g. CAR_DIESEL, TRUCK_SH_EV) is constrained to equal the sum of F_new
    across its distance variants (fnew_base_private/fnew_base_public/
    fnew_base_freight in QC_es_pathway.mod), and material_intensity is
    identical for the family and all its variants (mi_pipeline looks it up by
    family, see canonical.family_of) -- so the bare family's
    Material_content_year already equals the sum of its variants'. Counting
    both in a total/cross-sector sum would double true demand for every
    material with mobility content. Convention: ALWAYS the family, NEVER the
    variants -- same as Constraints.mod's MATERIAL_TECHS (_MOB_VARIANT_TECHS
    is the exact same list, loaded from the same generated .dat file). Only
    used where we sum across *all* technologies (or bucket the "leftover"
    ones into 'other') -- sector-scoped views already exclude the variants via
    _techs_in_sector's priv_mob/pub_mob branches."""
    all_techs = mcy.index.get_level_values('Technologies').unique()
    variants = [t for t in all_techs if t in _MOB_VARIANT_TECHS]
    return mcy.loc[~mcy.index.get_level_values('Technologies').isin(variants)]


#ADDED BY PAOLO (to validate)
def _real_net_demand(results_materials):
    """Net demand exactly as the solver sees it: gross demand (Material_content_year,
    aggregated across MATERIAL_TECHS) minus Used_recycled_material -- the real AMPL
    banking variables (Constraints.mod's material_stock_calc/used_recycled_material_cap),
    not a reporting-layer reconstruction. This is the LHS of material_content_year_limit,
    the constraint limit_material_year actually bounds. Returns a Series indexed by
    (Years, Materials)."""
    mcy = _drop_mob_size_variants(results_materials['Material_content_year']['Material_content_year']).groupby(['Years', 'Materials']).sum()
    used = results_materials['Used_recycled_material']['Used_recycled_material']
    return mcy.sub(used, fill_value=0)


def _negative_marker_colors(values, negative_color='#ff7f0e', positive_color='#d62728', size=8):
    """Marker style for a net-demand line: any negative point (should never happen for the
    annual net demand, used_recycled_material_cap always caps it >= 0 -- but can legitimately
    happen for the cumulative one, see plot_single_material_demand_by_sector) stands out in
    orange against the line's usual red, so it's visible at a glance rather than needing to
    read axis values."""
    return dict(color=[negative_color if v < 0 else positive_color for v in values], size=size)


def _all_material_small_multiples(results_materials, content_key, sector=None, title='', y_title='[t/yr]'):
    """Used by plot_material_recycling_benefit: one subplot per material
    (small multiples), a single bar series per year summed across the
    selected technologies. content_key is a key into results_materials whose
    DataFrame has a column of the same name (e.g. 'Recycling_benefit')."""
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


#ADDED BY PAOLO (to validate)
def plot_material_limit_heatmap(results_materials):
    """(Material x Year) heatmap of net demand as a share of limit_material_year --
    i.e. how close each material comes to its manual production/reserve cap
    (Material_limits.dat, or an extra_files override), the same net-demand
    quantity Constraints.mod's material_content_year_limit constraint itself
    compares against the limit (gross Material_content_year minus
    Used_recycled_material -- see _real_net_demand -- summed over
    MATERIAL_TECHS). Materials never given a limit (limit stays at its
    Infinity default) are dropped entirely -- a 0% cell would misleadingly
    read as "comfortable margin" when there's really no constraint at all.
    Materials-level only, no sector breakdown -- the constraint itself has none."""
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


#ADDED BY PAOLO (to validate)
def plot_material_recycling_benefit(results_materials, sector=None):
    """Economic benefit of recycling per material, year by year: avoided
    primary-material + disposal cost, net of the recycling process's own cost
    (Constraints.mod's recycling_benefit_calc), summed across technologies --
    same small-multiples layout as plot_material_recycled_view, but in
    M$/yr instead of t/yr. Can go negative for a material/tech pair whose
    recycling cost outweighs the avoided primary-material and disposal cost."""
    return _all_material_small_multiples(
        results_materials, 'Recycling_benefit', sector=sector,
        title='Annual recycling benefit by material', y_title='[M$/yr]')


def plot_recycled_by_tech_and_process(results_materials, sector=None):
    """One subplot per material (small multiples), each a stacked bar by
    (Technology, RECYCLING_PROCESS) combined series -- shows which
    sub-technology's decommissioned stock was recycled through which
    competing process (MECHANICAL/THERMAL/CHEMICAL/PV_INFRASTUCTURE). Needs
    results_materials['Recycled_material_by_process'] (cf.
    shared.utils.run_pathway (materials=True)) -- only present/meaningful for runs with
    materials_recycling_process=True; the simple-rate approach has no
    process notion at all."""
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


def _color_map(names):
    """Assign each name a fixed color from a qualitative palette, keyed by
    sorted name so the same name always gets the same color. Needed because
    go.Bar traces added across subplots in a loop are colored by trace order,
    not by name/legendgroup -- without this the legend color and the bar
    color for the same name can differ between subplots."""
    palette = px.colors.qualitative.Plotly
    return {name: palette[i % len(palette)] for i, name in enumerate(sorted(names))}


def _sector_color_map():
    """Consistent color per sector (by code, including 'other'), reused by
    plot_material_demand_by_sector and the per-material dashboard pages so
    the same sector always has the same color everywhere."""
    return _color_map(list(SECTOR_LABELS) + ['other'])


#ADDED BY PAOLO (to validate)
def plot_material_recycled_view(results_materials, sector='ALL'):
    """Consolidated 'Recycled by sector' dashboard page -- same aggregate-vs-
    drill-down Sector chip as plot_material_decommissioned_view and
    plot_material_demand_by_sector_view: sector='ALL' (default) stacks every
    sector on one chart (replaces the old plot_material_recycled_by_sector
    page, and before that the separate 'Total recycled' page -- summing the
    stack recovers that total, so it isn't kept as its own page), a specific
    sector instead breaks THAT sector's own technologies down individually."""
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


#ADDED BY PAOLO (to validate)
def plot_material_decommissioned_view(results_materials, sector='ALL'):
    """Consolidated 'Old/decommissioned by sector' dashboard page -- replaces the
    old separate plot_all_material_decommissioned('20_Material_decommissioned_total'),
    plot_material_decommissioned_by_sector('20_Material_decommissioned_by_sector') and
    the first cut's '20_Material_decommissioned_bytech_*' pages, folding all three
    into ONE sidebar entry with a single Sector chip -- sector='ALL' (default) stacks
    every sector on one chart (its top edge IS the old "Total decommissioned" figure),
    a specific sector instead breaks THAT sector's own technologies down individually
    (the old "by technology" page). Same aggregate-vs-drill-down pattern already used
    elsewhere in the dashboard for one dim, e.g. '10_Elec_layer_ALL' vs '..._EHV'/'_HV'.

    Named "Old/decommissioned" (not just "Decommissioned") because the underlying
    quantity, Decommissioned_material (Constraints.mod's decommissioned_material_calc),
    already combines BOTH F_decom (active/early decommissioning ahead of natural
    end-of-life) and F_old (natural end-of-life retirement) -- materials leaving the
    mix generally, not "decommissioned" in the narrow early-retirement-only sense.
    This is BEFORE any recycling decision splits it into Recycled_material (kept) vs
    Disposed_material (landfill/incineration)."""
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


#ADDED BY PAOLO (to validate)
def plot_material_demand_by_sector_view(results_materials, view='gross', sector='ALL'):
    """Consolidated 'Gross/net demand by sector' dashboard page -- one sidebar
    entry with a View (gross/net) selector (same dims mechanism already used
    e.g. for 1b_CAPEX_(View)) and a Sector selector: sector='ALL' (default)
    stacks every sector on one chart (replaces the old separate
    plot_all_material_demand('20_Material_demand_total') and
    plot_material_demand_by_sector('20_Material_demand_by_sector') pages --
    summing the stack recovers the old total), a specific sector instead
    breaks THAT sector's own technologies down individually (the old 'Gross/net
    demand by technology' page -- showing every technology from every sector in
    one stacked bar is unreadably dense, so picking a sector first is required
    there). Same aggregate-vs-drill-down pattern as
    plot_material_decommissioned_view's Sector chip (ALL vs elec_prod/...), and
    as e.g. '10_Elec_layer_ALL' vs '..._EHV'/'_HV' elsewhere in the dashboard.

    view='net' subtracts Recycled_material -- same net-demand quantity used
    everywhere else in this dashboard (e.g. the limit-closeness heatmap)."""
    if view not in ('gross', 'net'):
        raise ValueError(f"view must be 'gross' or 'net', got {view!r}")
    if sector != 'ALL' and sector not in SECTOR_LABELS:
        raise ValueError(f"sector must be 'ALL' or one of {list(SECTOR_LABELS)}, got {sector!r}")

    mcy = _drop_mob_size_variants(results_materials['Material_content_year']['Material_content_year'])
    if view == 'net':
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

    if sector == 'ALL':
        title = f"Annual {view} material demand by sector"
    else:
        title = f"Annual {view} material demand by technology -- {SECTOR_LABELS[sector]}"
    fig.update_layout(height=300 * nrows, barmode='relative', title=title)
    fig.update_yaxes(title_text='[t/yr]', col=1)
    fig.update_xaxes(tickmode='array', tickvals=years_x, tickangle=45)
    return fig


def _material_demand_by_sector_series(results_materials, material, content_key):
    """Shared by plot_single_material_demand_by_sector: demand for one
    material, grouped by (Years, Sector), from results_materials[content_key]
    -- either 'Material_content_year' (annual) or 'Material_content_cumulative'
    (running total over Years), both sharing the same (Years, Technologies,
    Materials) index shape. Returns (series, years_present, sectors_present)."""
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


def _single_material_by_sector_fig(results_materials, material, content_keys, title, subplot_titles):
    """Shared by plot_single_material_demand_by_sector and
    plot_single_material_recycled_by_sector: two subplots side by side for a
    single material -- annual value by sector (left) and cumulative value by
    sector (right -- running total over Years, so the last bar is the total
    over the whole period). content_keys is (annual_key, cumulative_key), each
    a key into results_materials whose DataFrame has a column of the same
    name (see shared.utils.run_pathway (materials=True)). Used for the dashboard's
    one-page-per-material sections. Uses the same sector color map as
    plot_material_demand_by_sector_view/plot_material_recycled_view so colors
    match across pages."""
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
    #ADDED BY PAOLO (to validate) -- stacked bars are gross demand (Material_content_year) by
    # sector; the annual net-demand line is gross minus Used_recycled_material, the real AMPL
    # banking mechanism (see _real_net_demand) -- structurally >= 0 (used_recycled_material_cap
    # never lets Used exceed gross demand), so a negative point here would signal a bug, not a
    # legitimate banking surplus; marked in orange + a zero line as a sanity-check aid. The
    # cumulative net-demand line (right subplot) stays plain gross-minus-Recycled_material --
    # banking doesn't change the whole-horizon total -- so it CAN legitimately go negative on
    # its own (more ever recycled than ever demanded, e.g. Glass), also marked the same way.
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

    mcy_cum = _drop_mob_size_variants(results_materials['Material_content_cumulative']['Material_content_cumulative']).xs(material, level='Materials')
    rec_cum = _drop_mob_size_variants(results_materials['Recycled_material_cumulative']['Recycled_material_cumulative']).xs(material, level='Materials')
    gross_cum_by_year = mcy_cum.groupby('Years').sum()
    rec_cum_by_year = rec_cum.groupby('Years').sum()
    net_cum_vals = [gross_cum_by_year.get(y, 0) - rec_cum_by_year.get(y, 0) for y in years_present]

    fig.add_trace(
        go.Scatter(x=years_x, y=net_cum_vals, name='Net demand (cumulative, all sectors)', mode='lines+markers',
                    line_color='#d62728', marker=_negative_marker_colors(net_cum_vals),
                    legendgroup='net_demand', showlegend=False),
        row=1, col=2
    )
    fig.add_hline(y=0, line_dash='dot', line_color='gray', row=1, col=2)
    return fig


def plot_single_material_recycled_by_sector(results_materials, material):
    """Recycled-material counterpart to plot_single_material_demand_by_sector:
    material recovered from decommissioned capacity (F_decom + F_old, cf.
    Constraints.mod's recycled_material_calc), not yet netted against demand."""
    return _single_material_by_sector_fig(
        results_materials, material,
        content_keys=('Recycled_material', 'Recycled_material_cumulative'),
        title=f'Recycled {material} by sector',
        subplot_titles=('Annual recycled', 'Cumulative recycled'),
    )


def plot_material_recycled_disposed_net(results_materials, material):
    """Two panels for a single material, aggregated across all TECHNOLOGIES
    (same aggregation level as Constraints.mod's material_content_year_limit --
    recycled material is fongible across technologies, not tied to its source):
    left = Decommissioned_material split into Recycled_material (kept) vs
    Disposed_material (landfill/incineration); right = gross demand
    (Material_content_year) vs net demand. Net demand here is gross minus
    Used_recycled_material, the real AMPL banking mechanism (see
    _real_net_demand) -- structurally >= 0 (used_recycled_material_cap never
    lets Used exceed gross demand), so a negative point would signal a bug;
    marked in orange + a zero line as a sanity-check aid, same as
    plot_single_material_demand_by_sector."""
    rec = _drop_mob_size_variants(results_materials['Recycled_material']['Recycled_material']).xs(material, level='Materials')
    disp = _drop_mob_size_variants(results_materials['Disposed_material']['Disposed_material']).xs(material, level='Materials')
    mcy = _drop_mob_size_variants(results_materials['Material_content_year']['Material_content_year']).xs(material, level='Materials')
    net_demand = _real_net_demand(results_materials).xs(material, level='Materials')

    years_present = sorted(mcy.index.get_level_values('Years').unique(), key=lambda y: int(y.replace('YEAR_', '')))
    years_x = [int(y.replace('YEAR_', '')) for y in years_present]

    rec_by_year = rec.groupby('Years').sum()
    disp_by_year = disp.groupby('Years').sum()
    gross_by_year = mcy.groupby('Years').sum()

    rec_vals = [rec_by_year.get(y, 0) for y in years_present]
    disp_vals = [disp_by_year.get(y, 0) for y in years_present]
    gross_vals = [gross_by_year.get(y, 0) for y in years_present]
    net_vals = [net_demand.get(y, 0) for y in years_present]

    fig = make_subplots(rows=1, cols=2, subplot_titles=('Decommissioned: recycled vs disposed', 'Demand: gross vs net'))

    fig.add_trace(go.Bar(x=years_x, y=rec_vals, name='Recycled', marker_color='#2ca02c'), row=1, col=1)
    fig.add_trace(go.Bar(x=years_x, y=disp_vals, name='Disposed', marker_color='#7f7f7f'), row=1, col=1)

    fig.add_trace(go.Bar(x=years_x, y=gross_vals, name='Gross demand', marker_color='#1f77b4'), row=1, col=2)
    fig.add_trace(go.Scatter(x=years_x, y=net_vals, name='Net demand', mode='lines+markers',
                              line_color='#d62728', marker=_negative_marker_colors(net_vals)), row=1, col=2)
    fig.add_hline(y=0, line_dash='dot', line_color='gray', row=1, col=2)

    fig.update_layout(barmode='stack', title=f'{material}: recycling impact on demand')
    fig.update_yaxes(title_text='[t/yr]', col=1)
    fig.update_yaxes(title_text='[t/yr]', col=2)
    fig.update_xaxes(tickmode='array', tickvals=years_x, tickangle=45)
    return fig


#ADDED BY PAOLO (to validate)
def plot_material_stock(results_materials):
    """(Material x Year) small multiples of Material_stock -- the real AMPL variable
    (Constraints.mod's material_stock_calc), the banked surplus of recycled material
    not yet needed that year, same source _real_net_demand's net-demand lines
    (plot_single_material_demand_by_sector/plot_material_recycled_disposed_net) draw
    on via Used_recycled_material. A material's stock only grows in a year where it
    was recycled beyond that year's own gross demand, and only shrinks in a later
    year where gross demand exceeds that year's own recycling and the bank gets
    drawn down to cover the gap. Materials that never bank anything (stock stays 0
    the whole horizon) are dropped. Returns None when there's nothing to show at all."""
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
            go.Bar(x=years_x, y=values, name=material, showlegend=False, marker_color='#2ca02c'),
            row=row, col=col
        )

    fig.update_layout(height=300 * nrows, title='Material stock (banked recycled surplus, drawn down as needed)')
    fig.update_yaxes(title_text='[t]', col=1)
    fig.update_xaxes(tickmode='array', tickvals=years_x, tickangle=45)
    return fig


#ADDED BY PAOLO (to validate)
def _drop_year_2020(results_materials):
    """Drop YEAR_2020 (phase "2015_2020", the pre-existing fleet) from every
    Years-indexed table before plotting. It's the historical baseline, not a
    transition decision the model made, and material_content_year_calc's
    union {"2015_2020"} fix now computes it correctly instead of leaving it
    near 0 -- correct, but still not comparable to the 2025+ demand/recycling
    the charts are meant to show. Non-Years-indexed entries (scalars, None,
    limit_material with no Years level) pass through untouched."""
    filtered = {}
    for key, val in results_materials.items():
        if isinstance(val, (pd.DataFrame, pd.Series)) and 'Years' in (val.index.names or []):
            filtered[key] = val[val.index.get_level_values('Years') != 'YEAR_2020']
        else:
            filtered[key] = val
    return filtered


#ADDED BY PAOLO (to validate)
def _import_plot_results():
    """Local import of projects/pathway/src/plot_results.py -- kept lazy for the
    same reason as the module-level docstring on _build_dashboard (avoid paying
    its plotly/kaleido import cost for callers who don't build a dashboard)."""
    pathway_src = str(Path(__file__).resolve().parent.parent / 'pathway' / 'src')
    if pathway_src not in sys.path:
        sys.path.insert(0, pathway_src)
    import plot_results
    return plot_results


#ADDED BY PAOLO (to validate)
def build_materials_dashboard(results_materials, case_study, out_dir=None, auto_open=True):
    """Write this critical-materials run's charts into the SAME
    out/<case_study>/graphs/ folder that plain run_pathway's plot_results.run()
    uses, with filenames matching plot_results.py's _DASH_SPECS ('Materials'
    section) -- so plot_results.create_dashboard() (called at the end of this
    function) builds ONE sidebar covering both the standard pathway charts and
    these, in the same visual style. No separate materials_graphs/ dashboard
    or index.html of its own anymore.

    Pages: gross/net demand by sector (View + Sector chips, Sector including
    "All" for the sector-stacked view alongside each individual sector's own
    sub-technology breakdown), old/decommissioned material by sector (same
    Sector-with-"All" chip), a "Demand by material" family (one chip per
    material, gross by sector with net overlaid), and a "Recycling" family
    (by-sector/per-material recycled material -- only added if Recycled_material
    is non-zero, i.e. the run was made with materials_recycling=True and
    Material_recycling.dat populated). Saved to out/<case_study>/graphs/
    unless out_dir is given."""
    plot_results = _import_plot_results()
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

    n_pages = 0

    for sector in SECTOR_LABELS:
        techs = sector_techs_positive[sector]

        fig = plot_new_positive(results_materials, techs, sector=sector)
        _save(fig, f'24_Material_new_{sector}.html'); n_pages += 1

        fig = plot_leaving_positive(results_materials, techs, sector=sector)
        _save(fig, f'24_Material_leaving_{sector}.html'); n_pages += 1

    for view in ('gross', 'net'):
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

    # Recycling pages are only added if some material was actually recycled --
    # collection_rate/recycling_rate default to 0 (cf. Constraints.mod), so a
    # run without materials_recycling=True (see run_pathway's materials=True
    # path in shared/utils.py) would otherwise produce empty small-multiples
    # with 0 materials, which crashes make_subplots(rows=0, ...).
    rec_all = results_materials.get('Recycled_material')
    has_recycling = rec_all is not None and (rec_all['Recycled_material'].fillna(0) != 0).any()
    if has_recycling and 'Recycled_material_cumulative' not in results_materials:
        # Backward-compat: results_materials may come from a run made before
        # this key existed (or a stale in-memory dict from an older cell run) --
        # compute it here instead of KeyError'ing, same convention as
        # shared.utils._run_pathway_materials' own computation.
        results_materials = dict(results_materials)  # don't mutate the caller's dict
        rec_cum_df = (rec_all['Recycled_material'] * 5).reset_index().sort_values(['Technologies', 'Materials', 'Years'])
        rec_cum_df['Recycled_material_cumulative'] = (
            rec_cum_df.groupby(['Technologies', 'Materials'])['Recycled_material'].cumsum()
        )
        results_materials['Recycled_material_cumulative'] = (
            rec_cum_df.set_index(['Years', 'Technologies', 'Materials'])[['Recycled_material_cumulative']].sort_index()
        )
    if has_recycling:
        # Whole-run avoided-cost total shown as a subtitle on this page (rather than
        # a dedicated stats widget -- the shared sidebar has no such slot, and total
        # cost itself is already covered by the standard dashboard's own "Transition
        # cost" page, so it isn't duplicated here). Combines both approaches: approach 1's
        # Recycling_benefit_cumulative (per material/tech/year) and approach 2's
        # C_material_recycling_tech (a single whole-horizon scalar, negated -- it's a COST term,
        # so a net benefit shows up as negative). Omitting the latter would silently under-report
        # (or show 0) whenever a run uses materials_recycling_process=True with materials_recycling=False.
        benefit_cum_all = results_materials.get('Recycling_benefit_cumulative')
        total_recycling_benefit = None
        if benefit_cum_all is not None and not benefit_cum_all.empty:
            last_year = benefit_cum_all.index.get_level_values('Years').max()
            total_recycling_benefit = float(
                benefit_cum_all.xs(last_year, level='Years')['Recycling_benefit_cumulative'].sum())
        c_material_recycling_tech = results_materials.get('C_material_recycling_tech')
        if c_material_recycling_tech:
            total_recycling_benefit = (total_recycling_benefit or 0) - c_material_recycling_tech

        # Recycling_benefit is tied only to approach 1's Recycled_material (recycling_benefit_calc) --
        # unlike has_recycling above, it does NOT pick up approach 2's Recycled_material_process, so a
        # materials_recycling_process=True, materials_recycling=False run has has_recycling=True (from
        # the merge a few lines up) but an all-zero Recycling_benefit -- guard separately here.
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

        fig = plot_material_stock(results_materials)
        if fig is not None:  # None when no material ever banks anything
            _save(fig, '23c_Material_stock.html'); n_pages += 1

    plot_results.create_dashboard(str(out_dir), case_study, auto_open=auto_open)
    print(f'[build_materials_dashboard] wrote {n_pages} pages to {out_dir}')
    return out_dir / 'index.html'


def build_scenario_selector(out_dir=None):
    """Write out/index.html: a dropdown listing every scenario that has its
    own dashboard (out/<case_study>/graphs/index.html, cf.
    build_materials_dashboard), switching an iframe between them -- a shell
    on top of the existing per-scenario dashboards, not a rebuild of them.
    Auto-discovers scenarios by scanning out/ each time it's called (no
    manual list to keep in sync) -- call this again after any new run to
    pick it up. Sorted by most-recently-modified first, so the latest run
    is the default selection."""
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
