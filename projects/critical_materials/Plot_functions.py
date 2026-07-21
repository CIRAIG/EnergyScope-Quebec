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
    'elec_prod': 'Capacité [GW]',
    'priv_mob': 'Nombre de véhicules',
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
                if any(kw in t for kw in priv_mob_keywords) and not t.endswith(('_LD', '_MD', '_SD')) ]

    priv_mob_techs_positive = [t for t in priv_mob_techs
                        if any(results_materials['F_new'].loc[period].loc[t].squeeze() > 0 for period in periods)]

    return priv_mob_techs_positive

def plot_new_positive(results_materials, techs_positive, sector='elec_prod'):

    df_plot = pd.DataFrame(
        {period: results_materials['F_new'].loc[period].loc[techs_positive].squeeze() for period in periods},
        index=techs_positive
    )

    if sector == 'priv_mob':
        # F_new is in pkm/h for private mobility -- divide by ref_size [pkm/h per
        # vehicle] (same lookup as mi_pipeline.aggregate.compute_tech_intensity)
        # to get a vehicle count instead.
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

    df_melted = df_plot.T.reset_index().rename(columns={'index': 'Période'}).melt(
        id_vars='Période', var_name='Technologies', value_name='Capacité'
    )

    fig = px.bar(df_melted, x='Période', y='Capacité', color='Technologies', barmode='stack')
    fig.update_layout(xaxis_title='Période', yaxis_title=SECTOR_Y_LABELS.get(sector, 'Capacité [GW]'))
    fig.show()


def plot_mult_positive(results_materials, sector = 'elec_prod'):

    f_mult = results_materials['F_Mult'].reset_index()

    if sector== 'elec_prod':
        f_mult = f_mult[f_mult['Technologies'].apply(lambda t: any(kw in t for kw in elec_keywords) and not t.startswith(('COAL_GAS', 'HYDRO_STORAGE', 'UNMINEABLE_COAL_SEAM')))]
        f_mult = f_mult[f_mult['F_Mult'] > 0]  # enleve les lignes a zero

    if sector== 'priv_mob':
        f_mult = f_mult[f_mult['Technologies'].apply(lambda t: any(kw in t for kw in priv_mob_keywords) and not t.endswith(('_MD', '_LD', '_SD'))) ]
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

    y_label = SECTOR_Y_LABELS.get(sector, 'Capacité [GW]')
    fig = px.bar(f_mult, x='Years', y='F_Mult', color='Technologies',
                category_orders={'Years': years_order},
                title=f'Capacité installée (F_Mult) par technologie et par année -- {y_label}')
    fig.update_layout(yaxis_title=y_label)
    fig.show()


def _techs_in_sector(sector, all_techs):
    """Filter `all_techs` down to one sector, using the same keyword logic as
    def_elec_positive/def_priv_mob_positive above (kept consistent with those)."""
    if sector == 'elec_prod':
        return [t for t in all_techs if any(kw in t for kw in elec_keywords)
                and not t.startswith(('COAL_GAS', 'HYDRO_STORAGE', 'UNMINEABLE_COAL_SEAM'))]
    if sector == 'priv_mob':
        return [t for t in all_techs if any(kw in t for kw in priv_mob_keywords)
                 and not t.endswith(('_MD', '_LD', '_SD')) ]
    raise ValueError(f"Unknown sector {sector!r}, expected 'elec_prod', 'priv_mob', or None")


def plot_all_material_demand(results_materials, sector=None, save_file=False, filepath=None):
    """sector: None (default) plots total demand across all technologies,
    'elec_prod' restricts to electricity-production techs, 'priv_mob' to
    private-mobility techs. Add a case to _techs_in_sector() above for new
    sectors as they get material intensities."""

    mcy = results_materials['Material_content_year']['Material_content_year']

    if sector is not None:
        all_techs = mcy.index.get_level_values('Technologies').unique()
        sector_techs = _techs_in_sector(sector, all_techs)
        mcy = mcy.loc[mcy.index.get_level_values('Technologies').isin(sector_techs)]

    demand = mcy.groupby(['Years', 'Materials']).sum().unstack('Materials')  # index=Years, colonnes=Materials
    demand = demand.loc[:, (demand.fillna(0) != 0).any(axis=0)]  # enleve les materiaux a zero partout

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

    title = 'Demande annuelle en matériau (modèle pathway + contraintes)'
    if sector is not None:
        title += f' -- secteur {sector}'
    fig.update_layout(height=300 * nrows, title=title)
    fig.update_yaxes(title_text='[t/an]', col=1)
    fig.update_xaxes(tickmode='array', tickvals=years_x, tickangle=45)
    fig.show()

    if save_file:
        save_dir = os.path.expanduser(filepath)#'~/Library/Mobile Documents/com~apple~CloudDocs/EPFL/PdM/Plots/Elec_energy_infinite')
        os.makedirs(save_dir, exist_ok=True)

        suffix = f'_{sector}' if sector is not None else ''
        out_path = os.path.join(save_dir, f'tot_mat_elec_infinite{suffix}.png')
        fig.write_image(out_path, width=250*ncols, height=300*nrows)
