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
years_order = ['YEAR_2020','YEAR_2025','YEAR_2030','YEAR_2035','YEAR_2040','YEAR_2045','YEAR_2050']

# sector -> y-axis label used by plot_new_positive. 'elec_prod' plots F_new as-is
# (GW); 'priv_mob' converts pkm/h to a vehicle count first (see _period_end_year
# and plot_new_positive below).
SECTOR_Y_LABELS = {
    'elec_prod': 'Capacity [GW]',
    'priv_mob': 'Number of vehicles',
    'h2_prod': 'Capacity [GW]',
}


def _period_end_year(period):
    """'2020_2025' -> 'YEAR_2025': F_new's commissioning year for that rolling-
    horizon window, same convention as the YEARS used in mi_pipeline.aggregate
    to look up ref_size."""
    return 'YEAR_' + period.split('_')[1]

def def_elec_positive(results_materials):
    technologies = [t for t in results_materials['F_new'].loc['2020_2025'].index
                    if any(results_materials['F_new'].loc[period].loc[t].squeeze() > 0 for period in periods)]


    elec_techs = [t for t in results_materials['F_new'].loc['2020_2025'].index 
                if any(kw in t for kw in elec_keywords) and not t.startswith(('COAL_GAS', 'HYDRO_STORAGE', 'UNMINEABLE_COAL_SEAM'))]

    elec_techs_positive = [t for t in elec_techs
                        if any(results_materials['F_new'].loc[period].loc[t].squeeze() > 0 for period in periods)]
    
    return elec_techs_positive

def def_priv_mob_positive(results_materials):

    priv_mob_techs = [t for t in results_materials['F_new'].loc['2020_2025'].index
                if any(kw in t for kw in priv_mob_keywords) and not t.endswith(('_LD', '_MD', '_SD', '_ELD')) ]

    priv_mob_techs_positive = [t for t in priv_mob_techs
                        if any(results_materials['F_new'].loc[period].loc[t].squeeze() > 0 for period in periods)]

    return priv_mob_techs_positive

def def_h2_prod_positive(results_materials):

    h2_techs = [t for t in results_materials['F_new'].loc['2020_2025'].index
                if t in canonical.ELECTROLYSIS_TECHS]

    h2_techs_positive = [t for t in h2_techs
                        if any(results_materials['F_new'].loc[period].loc[t].squeeze() > 0 for period in periods)]

    return h2_techs_positive

def _phase_tech_bar(df_phase_tech, techs_positive, sector, title):
    """Shared by plot_new_positive/plot_old_positive/plot_decom_positive:
    df_phase_tech is a single-column DataFrame indexed by (Phases, Technologies)
    -- same shape as results_materials['F_new']/['F_old']. Converts pkm/h to a
    vehicle count for priv_mob (same lookup as mi_pipeline.aggregate)."""
    df_plot = pd.DataFrame(
        {period: df_phase_tech.loc[period].loc[techs_positive].squeeze() for period in periods},
        index=techs_positive
    )

    if sector == 'priv_mob':
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

    df_melted = df_plot.T.reset_index().rename(columns={'index': 'Period'}).melt(
        id_vars='Period', var_name='Technologies', value_name='Capacity'
    )

    fig = px.bar(df_melted, x='Period', y='Capacity', color='Technologies', barmode='stack')
    fig.update_layout(xaxis_title='Period', yaxis_title=SECTOR_Y_LABELS.get(sector, 'Capacity [GW]'), title=title,
                       showlegend=True)  # plotly hides the legend by default when there's only 1 trace (e.g. h2_prod with a single positive tech)
    return fig


def plot_new_positive(results_materials, techs_positive, sector='elec_prod'):
    return _phase_tech_bar(results_materials['F_new'], techs_positive, sector, 'F_new')


def plot_old_positive(results_materials, techs_positive, sector='elec_prod'):
    """Retired capacity each phase (F_old) -- same (Phases, Technologies) shape as F_new."""
    return _phase_tech_bar(results_materials['F_old'], techs_positive, sector, 'F_old')


def plot_decom_positive(results_materials, techs_positive, sector='elec_prod'):
    """Decommissioned capacity each phase (F_decom). Unlike F_new/F_old, the raw
    F_decom variable is indexed by (decom-phase, built-phase, Technologies) --
    sum over the built-phase dimension by position (its exact index-level name
    isn't fixed) to get the same (Phases, Technologies) shape as F_new/F_old."""
    f_decom = results_materials['F_decom'].groupby(level=[0, -1]).sum()
    f_decom.index.names = ['Phases', 'Technologies']
    return _phase_tech_bar(f_decom, techs_positive, sector, 'F_decom')


def plot_mult_positive(results_materials, sector = 'elec_prod'):

    f_mult = results_materials['F_Mult'].reset_index()

    if sector== 'elec_prod':
        f_mult = f_mult[f_mult['Technologies'].apply(lambda t: any(kw in t for kw in elec_keywords) and not t.startswith(('COAL_GAS', 'HYDRO_STORAGE', 'UNMINEABLE_COAL_SEAM')))]
        f_mult = f_mult[f_mult['F_Mult'] > 0]  # enleve les lignes a zero

    if sector== 'priv_mob':
        f_mult = f_mult[f_mult['Technologies'].apply(lambda t: any(kw in t for kw in priv_mob_keywords) and not t.endswith(('_MD', '_LD', '_SD', '_ELD'))) ]
        f_mult = f_mult[f_mult['F_Mult'] > 0]  # enleve les lignes a zero

        # F_Mult is in pkm/h for private mobility -- divide by ref_size [pkm/h per
        # vehicle] (same lookup as plot_new_positive) to get a vehicle count instead.
        # F_Mult's 'Years' column is already 'YEAR_XXXX', so no period->year mapping needed.
        ref_size = canonical.load_ref_size()
        f_mult = f_mult.copy()

        def _to_vehicles(row):
            family = canonical.family_of(row['Technologies'])
            r = ref_size.get((row['Years'], family))
            if r is None:
                raise ValueError(f"{row['Technologies']}: no ref_size entry for family {family!r}, "
                                  f"year {row['Years']!r} in {canonical.REF_SIZE_PATH.name}")
            return row['F_Mult'] / r

        f_mult['F_Mult'] = f_mult.apply(_to_vehicles, axis=1)

    if sector== 'h2_prod':
        f_mult = f_mult[f_mult['Technologies'].isin(canonical.ELECTROLYSIS_TECHS)]
        f_mult = f_mult[f_mult['F_Mult'] > 0]  # enleve les lignes a zero

    y_label = SECTOR_Y_LABELS.get(sector, 'Capacity [GW]')
    fig = px.bar(f_mult, x='Years', y='F_Mult', color='Technologies',
                category_orders={'Years': years_order},
                title=f'F_Mult by technology and year -- {y_label}')
    fig.update_layout(yaxis_title=y_label, showlegend=True)
    return fig


def _techs_in_sector(sector, all_techs):
    """Filter `all_techs` down to one sector, using the same keyword logic as
    def_elec_positive/def_priv_mob_positive above (kept consistent with those)."""
    if sector == 'elec_prod':
        return [t for t in all_techs if any(kw in t for kw in elec_keywords)
                and not t.startswith(('COAL_GAS', 'HYDRO_STORAGE', 'UNMINEABLE_COAL_SEAM'))]
    if sector == 'priv_mob':
        return [t for t in all_techs if any(kw in t for kw in priv_mob_keywords)
                 and not t.endswith(('_MD', '_LD', '_SD', '_ELD')) ]
    if sector == 'h2_prod':
        return [t for t in all_techs if t in canonical.ELECTROLYSIS_TECHS]
    raise ValueError(f"Unknown sector {sector!r}, expected 'elec_prod', 'priv_mob', 'h2_prod', or None")


# Display name for each known sector -- add an entry here (and a case in
# _techs_in_sector above) as more sectors get material intensities.
SECTOR_LABELS = {'elec_prod': 'Electricity production', 'priv_mob': 'Private mobility', 'h2_prod': 'Hydrogen production'}


def _drop_priv_mob_size_variants(mcy):
    """Drop the SD/MD/LD/ELD distance-class variants of private-mobility techs
    (e.g. CAR_DIESEL_SD) from a Material_content_year series. F_new of the bare
    family tech (e.g. CAR_DIESEL) is constrained to equal the sum of F_new
    across its distance variants (fnew_base_private in QC_es_pathway.mod), and
    material_intensity is identical for the family and all its variants
    (mi_pipeline looks it up by family, see canonical.family_of) -- so the bare
    family's Material_content_year already equals the sum of its variants'.
    Counting both in a total/cross-sector sum would double true demand for
    every private-mobility material. Only used where we sum across *all*
    technologies (or bucket the "leftover" ones into 'other') -- sector-scoped
    views already exclude the variants via _techs_in_sector's priv_mob branch."""
    all_techs = mcy.index.get_level_values('Technologies').unique()
    variants = [t for t in all_techs
                if any(kw in t for kw in priv_mob_keywords) and t.endswith(('_SD', '_MD', '_LD', '_ELD'))]
    return mcy.loc[~mcy.index.get_level_values('Technologies').isin(variants)]


def _all_material_small_multiples(results_materials, content_key, sector=None, title='', y_title='[t/yr]'):
    """Shared by plot_all_material_demand and plot_all_material_recycled: one
    subplot per material (small multiples), a single bar series per year
    summed across the selected technologies. content_key is a key into
    results_materials whose DataFrame has a column of the same name (e.g.
    'Material_content_year' or 'Recycled_material')."""
    mcy = _drop_priv_mob_size_variants(results_materials[content_key][content_key])

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


def plot_all_material_demand(results_materials, sector=None, save_file=False, filepath=None):
    """sector: None (default) plots total demand across all technologies,
    'elec_prod' restricts to electricity-production techs, 'priv_mob' to
    private-mobility techs. Add a case to _techs_in_sector() above for new
    sectors as they get material intensities."""
    fig = _all_material_small_multiples(
        results_materials, 'Material_content_year', sector=sector,
        title='Annual material demand (pathway model + constraints)')

    if save_file:
        ncols = 6
        nrows = fig.layout.height // 300  # set to 300*nrows inside _all_material_small_multiples
        save_dir = os.path.expanduser(filepath)#'~/Library/Mobile Documents/com~apple~CloudDocs/EPFL/PdM/Plots/Elec_energy_infinite')
        os.makedirs(save_dir, exist_ok=True)

        suffix = f'_{sector}' if sector is not None else ''
        out_path = os.path.join(save_dir, f'tot_mat_elec_infinite{suffix}.png')
        fig.write_image(out_path, width=250*ncols, height=300*nrows)

    return fig


def plot_all_material_recycled(results_materials, sector=None):
    """Recycled-material counterpart to plot_all_material_demand: material
    recovered from decommissioned capacity (F_decom + F_old, cf.
    Constraints.mod's recycled_material_calc), not yet netted against demand."""
    return _all_material_small_multiples(
        results_materials, 'Recycled_material', sector=sector,
        title='Annual material recycled (from decommissioned capacity)')


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


def _material_by_sector_small_multiples(results_materials, content_key, title):
    """Shared by plot_material_demand_by_sector and
    plot_material_recycled_by_sector: one subplot per material (same
    small-multiples layout as _all_material_small_multiples), each a stacked
    bar by sector across years -- the cross-sector counterpart to
    plot_material_demand_detailed's per-sector, per-technology breakdown.
    Technologies not in any known sector (SECTOR_LABELS) are lumped into
    'Other'."""
    mcy = _drop_priv_mob_size_variants(results_materials[content_key][content_key])
    all_techs = mcy.index.get_level_values('Technologies').unique()

    tech_to_sector = {}
    for sector in SECTOR_LABELS:
        for tech in _techs_in_sector(sector, all_techs):
            tech_to_sector[tech] = sector

    demand_df = mcy.reset_index()
    demand_df['Sector'] = demand_df['Technologies'].map(tech_to_sector).fillna('other')

    total_by_sector = demand_df.groupby('Sector')[content_key].sum()
    sectors_present = total_by_sector[total_by_sector.fillna(0) != 0].index.tolist()  # drop sectors that are zero everywhere

    total_by_material = mcy.groupby('Materials').sum()
    materials = total_by_material[total_by_material.fillna(0) != 0].index.tolist()

    demand = demand_df.groupby(['Years', 'Sector', 'Materials'])[content_key].sum()
    years_present = sorted(mcy.index.get_level_values('Years').unique(), key=lambda y: int(y.replace('YEAR_', '')))
    years_x = [int(y.replace('YEAR_', '')) for y in years_present]

    sector_colors = _sector_color_map()

    n = len(materials)
    ncols = 6
    nrows = -(-n // ncols)
    fig = make_subplots(rows=nrows, cols=ncols, subplot_titles=materials)

    for i, material in enumerate(materials):
        row = i // ncols + 1
        col = i % ncols + 1
        for sector in sectors_present:
            values = [demand.get((year, sector, material), 0) for year in years_present]
            fig.add_trace(
                go.Bar(x=years_x, y=values, name=SECTOR_LABELS.get(sector, 'Other'),
                       legendgroup=sector, showlegend=(i == 0), marker_color=sector_colors[sector]),
                row=row, col=col
            )

    fig.update_layout(height=300 * nrows, barmode='stack', title=title)
    fig.update_yaxes(title_text='[t/yr]', col=1)
    fig.update_xaxes(tickmode='array', tickvals=years_x, tickangle=45)
    return fig


def plot_material_demand_by_sector(results_materials):
    return _material_by_sector_small_multiples(
        results_materials, 'Material_content_year', 'Annual material demand by sector')


def plot_material_recycled_by_sector(results_materials):
    """Recycled-material counterpart to plot_material_demand_by_sector."""
    return _material_by_sector_small_multiples(
        results_materials, 'Recycled_material', 'Annual material recycled by sector')


def plot_material_demand_detailed(results_materials, sector):
    """Like plot_all_material_demand but keeps the per-technology breakdown
    visible: same small-multiples layout (one subplot per material), each a
    stacked bar by technology instead of a single aggregated bar per year."""
    mcy = results_materials['Material_content_year']['Material_content_year']
    all_techs = mcy.index.get_level_values('Technologies').unique()
    sector_techs = _techs_in_sector(sector, all_techs)
    mcy = mcy.loc[mcy.index.get_level_values('Technologies').isin(sector_techs)]

    total_by_material = mcy.groupby('Materials').sum()
    materials = total_by_material[total_by_material.fillna(0) != 0].index.tolist()
    demand = mcy.groupby(['Years', 'Technologies', 'Materials']).sum()

    total_by_tech = mcy.groupby('Technologies').sum()
    techs_present = sorted(total_by_tech[total_by_tech.fillna(0) != 0].index.tolist())  # drop technologies that are zero everywhere
    years_present = sorted(mcy.index.get_level_values('Years').unique(), key=lambda y: int(y.replace('YEAR_', '')))
    years_x = [int(y.replace('YEAR_', '')) for y in years_present]

    tech_colors = _color_map(techs_present)

    n = len(materials)
    ncols = 6
    nrows = -(-n // ncols)
    fig = make_subplots(rows=nrows, cols=ncols, subplot_titles=materials)

    for i, material in enumerate(materials):
        row = i // ncols + 1
        col = i % ncols + 1
        for tech in techs_present:
            values = [demand.get((year, tech, material), 0) for year in years_present]
            fig.add_trace(
                go.Bar(x=years_x, y=values, name=tech, legendgroup=tech, showlegend=(i == 0),
                       marker_color=tech_colors[tech]),
                row=row, col=col
            )

    fig.update_layout(height=300 * nrows, barmode='stack',
                       title=f'Annual material demand by sub-technology -- {sector} sector')
    fig.update_yaxes(title_text='[t/yr]', col=1)
    fig.update_xaxes(tickmode='array', tickvals=years_x, tickangle=45)
    return fig


def _material_demand_by_sector_series(results_materials, material, content_key):
    """Shared by plot_single_material_demand_by_sector: demand for one
    material, grouped by (Years, Sector), from results_materials[content_key]
    -- either 'Material_content_year' (annual) or 'Material_content_cumulative'
    (running total over Years), both sharing the same (Years, Technologies,
    Materials) index shape. Returns (series, years_present, sectors_present)."""
    mcy = _drop_priv_mob_size_variants(results_materials[content_key][content_key])
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
    name (see run_pathway_materials.py). Used for the dashboard's
    one-page-per-material sections. Uses the same sector color map as
    plot_material_demand_by_sector/plot_material_recycled_by_sector so colors
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
    return _single_material_by_sector_fig(
        results_materials, material,
        content_keys=('Material_content_year', 'Material_content_cumulative'),
        title=f'Demand for {material} by sector',
        subplot_titles=('Annual demand', 'Cumulative demand'),
    )


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


def _save_html(fig, path, title):
    """Write `fig` as a self-contained HTML page (plotly.js bundled inline) --
    same convention as projects/pathway/src/plot_results.py's _save()."""
    html = fig.to_html(full_html=True, include_plotlyjs=True)
    html = html.replace('<head>', f'<head><title>{title}</title>', 1)
    with open(path, 'w', encoding='utf-8') as f:
        f.write(html)


def _dashboard_index_html(sections):
    """sections: list of (section_title_or_None, [(filename, label), ...]).
    A None title renders its pages at the top level; a given title wraps its
    pages in a collapsible <details> sub-section (native HTML, no JS needed
    for the collapse itself). Sidebar + iframe viewer, same shell pattern as
    pathway's create_dashboard() (graphs/index.html) -- plain Python
    string-building, no templating lib."""
    blocks = []
    first = None
    for title, pages in sections:
        if first is None and pages:
            first = pages[0][0]
        items = '\n'.join(
            f'<div class="nav-item" onclick="load(\'{fname}\')">{label}</div>'
            for fname, label in pages
        )
        if title is None:
            blocks.append(items)
        else:
            blocks.append(f'<details open><summary>{title}</summary>{items}</details>')
    nav_html = '\n'.join(blocks)
    return f'''<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<title>Material demand -- dashboard</title>
<style>
  body {{ margin: 0; display: flex; font-family: Arial, sans-serif; height: 100vh; }}
  #sidebar {{ width: 280px; background: #1e1e2e; color: #eee; overflow-y: auto; padding: 10px; box-sizing: border-box; }}
  .nav-item {{ padding: 8px 10px 8px 24px; cursor: pointer; border-radius: 4px; }}
  .nav-item:hover {{ background: #333; }}
  summary {{ padding: 8px 10px; cursor: pointer; font-weight: bold; border-radius: 4px; }}
  summary:hover {{ background: #333; }}
  #viewer {{ flex: 1; border: none; }}
</style>
</head>
<body>
<div id="sidebar">{nav_html}</div>
<iframe id="viewer" src="{first or ''}"></iframe>
<script>
function load(src) {{ document.getElementById('viewer').src = src; }}
</script>
</body>
</html>'''


def build_materials_dashboard(results_materials, case_study, out_dir=None):
    """Write a browsable HTML dashboard for this critical-materials run:
    total demand and demand-by-sector at the top level, a "By material"
    section with one page per material (demand stacked by sector), a
    "Recycling" section (total/by-sector/per-material recycled material --
    only added if Recycled_material is non-zero, i.e. the run was made with
    materials_recycling=True and Material_recycling.dat populated, cf.
    run_pathway_materials.py), and one collapsible sub-section per sector --
    F_new, F_old, F_decom, F_Mult, material demand, and material demand
    detailed by sub-technology. Mirrors the structure of projects/pathway's
    out/<case_study>/graphs/index.html. Saved to
    out/<case_study>/materials_graphs/ (next to run_pathway_materials's own
    out/<case_study>/ output) unless out_dir is given."""
    if out_dir is None:
        out_dir = Path(__file__).resolve().parent / 'out' / case_study / 'materials_graphs'
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    sector_techs_positive = {
        'elec_prod': def_elec_positive(results_materials),
        'priv_mob': def_priv_mob_positive(results_materials),
        'h2_prod': def_h2_prod_positive(results_materials),
    }

    sections = []

    fig = plot_all_material_demand(results_materials)
    _save_html(fig, out_dir / '0_demand_total.html', 'Total demand')

    fig = plot_material_demand_by_sector(results_materials)
    _save_html(fig, out_dir / '0_demand_by_sector.html', 'Demand by sector')

    sections.append((None, [
        ('0_demand_total.html', 'Total demand'),
        ('0_demand_by_sector.html', 'Demand by sector'),
    ]))

    mcy = _drop_priv_mob_size_variants(results_materials['Material_content_year']['Material_content_year'])
    total_by_material = mcy.groupby('Materials').sum()
    materials_present = sorted(total_by_material[total_by_material.fillna(0) != 0].index.tolist())
    material_pages = []
    for material in materials_present:
        fig = plot_single_material_demand_by_sector(results_materials, material)
        fname = f'material_{material}.html'
        _save_html(fig, out_dir / fname, f'{material} demand')
        material_pages.append((fname, material))
    sections.append(('By material', material_pages))

    # Recycling pages are only added if some material was actually recycled --
    # collection_rate/recycling_rate default to 0 (cf. Constraints.mod), so a
    # run without materials_recycling=True (see run_pathway_materials.py) would
    # otherwise produce empty small-multiples with 0 materials, which crashes
    # make_subplots(rows=0, ...).
    rec_all = results_materials.get('Recycled_material')
    has_recycling = rec_all is not None and (rec_all['Recycled_material'].fillna(0) != 0).any()
    if has_recycling and 'Recycled_material_cumulative' not in results_materials:
        # Backward-compat: results_materials may come from a run_pathway_materials
        # call made before this key existed (or a stale in-memory dict from an
        # older cell run) -- compute it here instead of KeyError'ing, same
        # convention as run_pathway_materials.py's own computation.
        results_materials = dict(results_materials)  # don't mutate the caller's dict
        rec_cum_df = (rec_all['Recycled_material'] * 5).reset_index().sort_values(['Technologies', 'Materials', 'Years'])
        rec_cum_df['Recycled_material_cumulative'] = (
            rec_cum_df.groupby(['Technologies', 'Materials'])['Recycled_material'].cumsum()
        )
        results_materials['Recycled_material_cumulative'] = (
            rec_cum_df.set_index(['Years', 'Technologies', 'Materials'])[['Recycled_material_cumulative']].sort_index()
        )
    if has_recycling:
        fig = plot_all_material_recycled(results_materials)
        _save_html(fig, out_dir / '0_recycled_total.html', 'Total recycled')

        fig = plot_material_recycled_by_sector(results_materials)
        _save_html(fig, out_dir / '0_recycled_by_sector.html', 'Recycled by sector')

        rec = _drop_priv_mob_size_variants(rec_all['Recycled_material'])
        total_recycled_by_material = rec.groupby('Materials').sum()
        materials_recycled = sorted(total_recycled_by_material[total_recycled_by_material.fillna(0) != 0].index.tolist())
        recycled_pages = [
            ('0_recycled_total.html', 'Total recycled'),
            ('0_recycled_by_sector.html', 'Recycled by sector'),
        ]
        for material in materials_recycled:
            fig = plot_single_material_recycled_by_sector(results_materials, material)
            fname = f'recycled_{material}.html'
            _save_html(fig, out_dir / fname, f'{material} recycled')
            recycled_pages.append((fname, material))
        sections.append(('Recycling', recycled_pages))

    for sector, label in SECTOR_LABELS.items():
        techs = sector_techs_positive[sector]
        pages = []

        plots = [
            (f'new_{sector}.html', 'F_new',
             plot_new_positive(results_materials, techs, sector=sector)),
            (f'old_{sector}.html', 'F_old',
             plot_old_positive(results_materials, techs, sector=sector)),
            (f'decom_{sector}.html', 'F_decom',
             plot_decom_positive(results_materials, techs, sector=sector)),
            (f'mult_{sector}.html', 'F_Mult',
             plot_mult_positive(results_materials, sector=sector)),
            (f'demand_{sector}.html', 'Material demand',
             plot_all_material_demand(results_materials, sector=sector)),
            (f'demand_detail_{sector}.html', 'Material demand by sub-technology',
             plot_material_demand_detailed(results_materials, sector=sector)),
        ]
        for fname, page_label, fig in plots:
            _save_html(fig, out_dir / fname, f'{page_label} -- {label}')
            pages.append((fname, page_label))

        sections.append((label, pages))

    with open(out_dir / 'index.html', 'w', encoding='utf-8') as f:
        f.write(_dashboard_index_html(sections))

    total_pages = sum(len(pages) for _, pages in sections)
    print(f'[build_materials_dashboard] wrote {total_pages + 1} pages to {out_dir}')
    return out_dir / 'index.html'
