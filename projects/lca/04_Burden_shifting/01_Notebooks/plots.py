import pandas as pd
import plotly.express as px
import plotly.graph_objs as go
from plotly.subplots import make_subplots
import numpy as np
import sys
from pathlib import Path
from plotly.colors import sample_colorscale
import math

NOTEBOOK_DIR = Path.cwd()
LCA_PROJECTS_ROOT = NOTEBOOK_DIR.parent.parent
sys.path.insert(1, str(LCA_PROJECTS_ROOT / '00_Shared'))
from utils import (
    wood_list, waste_list, wet_biomass_list,
    sector_unit_dict, unit_dict_plotly,
)

str_to_num_ccs_limit = {
    'Infinity': 50,
    '40': 40,
    '30': 30,
    '20': 20,
    '10': 10,
}

str_to_num_grouping = {
    'all': 0,
    'ssp_rcp': 1,
    # 'iam': 2,
    # 'individual': 3,
}

str_to_num_ssp_rcp = {
    'low': 0,
    'medium': 1,
    'high': 2,
}

str_to_num_iam = {
    'image': 0,
    'remind': 1,
    'message': 2,
    'tiam-ucl': 3,
}

str_to_num_burden_shifting_policy = {
    'None': 0,
    # 'REQ': 1,
    # 'RHH': 2,
    # 'CCA': 3,
    # 'RHH REQ': 4,
    # 'CCA REQ': 5,
    # 'CCA RHH': 6,
    'All': 1,
}

def plot_parallel_coord(
        df_total_impact: pd.DataFrame,
        results_folder: str,
        show_fig: bool=False,
        save_fig: bool=False
):

    group_by_dims = ['Grouping', 'GHG emissions level', 'IAM', 'Carbon policy', 'Burden shifting policy', 'CCS limit']
    indicator_dims = [
        # 'Remaining ecosystem quality',
        # 'Remaining human health',
        # 'Climate change, short term, total (abroad)',
        'Cost',
    ]
    tech_res_dims = [
        'New Wind Energy Onshore',
        'Natural gas',
        'Carbon Transport and Injection',
        'Carbon Mineralization',
    ]

    df_paral_coord = df_total_impact[  # filtering the runs we want to see
        (df_total_impact['Grouping'].isin(['all', 'ssp_rcp']))
    ]
    df_paral_coord = df_paral_coord.groupby(group_by_dims)[indicator_dims].sum()
    df_paral_coord = pd.merge(
        df_paral_coord,
        df_total_impact[df_total_impact['Phase'].isin(['Operation (direct)', 'Resource'])].pivot(index=group_by_dims, columns='index', values='Capacity or production')[tech_res_dims].fillna(0),
        left_index=True,
        right_index=True,
    ).reset_index()

    df_paral_coord['CCS'] = df_paral_coord['Carbon Transport and Injection'] + df_paral_coord['Carbon Mineralization']
    tech_res_dims = [i for i in tech_res_dims if i not in ['Carbon Transport and Injection', 'Carbon Mineralization']] + ['CCS']

    df_paral_coord['Grouping'] = df_paral_coord['Grouping'].apply(lambda x: str_to_num_grouping[x])
    df_paral_coord['IAM'] = df_paral_coord['IAM'].apply(lambda x: str_to_num_iam[x])
    df_paral_coord['GHG emissions level'] = df_paral_coord['GHG emissions level'].apply(lambda x: str_to_num_ssp_rcp[x])
    df_paral_coord['Burden shifting policy'] = df_paral_coord['Burden shifting policy'].apply(lambda x: str_to_num_burden_shifting_policy[x])

    if df_paral_coord['CCS limit'].dtype == float:
        df_paral_coord['CCS limit'] = df_paral_coord['CCS limit'].apply(lambda x: str(int(x)) if x != np.Inf else 'Infinity')
    df_paral_coord['CCS limit'] = df_paral_coord['CCS limit'].apply(lambda x: str_to_num_ccs_limit[x])

    if df_paral_coord['Carbon policy'].dtype != int:
        df_paral_coord['Carbon policy'] = df_paral_coord['Carbon policy'].astype(int)

    fig = px.parallel_coordinates(
        df_paral_coord,
        dimensions=group_by_dims + indicator_dims + tech_res_dims,
        color='GHG emissions level',
        color_continuous_scale=px.colors.cyclical.Phase,
        color_continuous_midpoint=2,
        # labels={},
    )

    fig.update_coloraxes(showscale=False)

    fig.data[0].dimensions[0].update(tickvals=list(str_to_num_grouping.values()), ticktext=list(str_to_num_grouping.keys()))
    fig.data[0].dimensions[1].update(tickvals=list(str_to_num_ssp_rcp.values()), ticktext=list(str_to_num_ssp_rcp.keys()))
    fig.data[0].dimensions[2].update(tickvals=list(str_to_num_iam.values()), ticktext=list(str_to_num_iam.keys()))
    fig.data[0].dimensions[4].update(tickvals=list(str_to_num_burden_shifting_policy.values()), ticktext=list(str_to_num_burden_shifting_policy.keys()))
    fig.data[0].dimensions[5].update(tickvals=list(str_to_num_ccs_limit.values()), ticktext=list(str_to_num_ccs_limit.keys()))

    if show_fig:
        fig.show()

    if save_fig:
        fig.write_html(f'../03_Results/Figures/{results_folder}/parallel_coord.html')

color_dict = {
    # IAM
    'image':    '#0072B2',  # blue (Okabe-Ito)
    'message':  '#D55E00',  # vermillion (Okabe-Ito)
    'remind':   '#009E73',  # bluish green (Okabe-Ito)
    'tiam-ucl': '#CC79A7',  # reddish purple (Okabe-Ito)

    # GHG emissions level
    'low':    '#56B4E9',    # sky blue (Okabe-Ito)
    'medium': '#E69F00',    # amber (Okabe-Ito)
    'high':   '#D55E00',    # vermillion (Okabe-Ito)

    # Burden shifting policy
    'All':  '#0072B2',      # blue (Okabe-Ito)
    'None': '#D55E00',      # vermillion (Okabe-Ito)

    # Carbon policy — ColorBrewer Greens 7 (steps 3–7, light→dark)
    '-12':  '#74C476',      # medium-light green
    '-9':   '#41AB5D',      # medium green
    '-6':   '#238B45',      # medium-dark green
    '-3':   '#006D2C',      # dark green
    '0':    '#00441B',      # very dark green
    -12.:  '#74C476',      # medium-light green
    -9.:   '#41AB5D',      # medium green
    -6.:   '#238B45',      # medium-dark green
    -3.:   '#006D2C',      # dark green
    0.:    '#00441B',      # very dark green

    # CCS availability limit — ColorBrewer Purples 7 (steps 3–7, light→dark)
    '10':    '#BCBDDC',  # medium-light purple
    '20':    '#9E9AC8',  # medium purple
    '30':    '#807DBA',  # medium-dark purple
    '40':    '#6A51A3',  # dark purple
    'Infinity': '#4A1486',  # very dark purple

    # Grouping
    'individual': "rgb(136, 204, 238)",
    'iam': "rgb(204, 102, 119)",
    'spp_rcp': "rgb(221, 204, 119)",
    "all": "rgb(17, 119, 51)",

    'any': 'grey',
}

def plot_box_distribution_with_mean(
        df_total_impact: pd.DataFrame,
        x_axis: str,
        y_axis: str,
):
    category_orders = {
        'CCS limit': ['10', '20', '30', '40', 'Infinity'],
        'Carbon policy': ['-12', '-9', '-6', '-3', '0'],
        'Burden shifting policy': ['None', 'All'],
        'GHG emissions level': ['low', 'medium', 'high', 'any'],
    }

    group_by_dims = ['Grouping', 'Key', 'GHG emissions level', 'IAM', 'Carbon policy', 'Burden shifting policy', 'CCS limit']

    if y_axis in ['Natural gas', 'New Wind Energy Onshore']:
        df_plot = df_total_impact[
            (df_total_impact['Grouping'] == 'all')
            & (df_total_impact['index'] == y_axis)
        ].groupby(group_by_dims).sum().rename(columns={'Capacity or production': y_axis})[[y_axis]].reset_index()
        df_plot['IAM'] = 'any'
        df_plot['GHG emissions level'] = 'any'
        df_plot = df_plot.drop_duplicates()
        df_plot[y_axis] *= 1e-3  # from GWh to TWh
    else:
        df_plot = df_total_impact[df_total_impact['Grouping'] == 'all'].groupby(group_by_dims).sum()[[y_axis]].reset_index()
        if y_axis == 'Cost':
            df_plot['IAM'] = 'any'
            df_plot['GHG emissions level'] = 'any'
            df_plot = df_plot.drop_duplicates()

    fig_box = px.box(
        df_plot,
        y=y_axis,
        x=x_axis,
        points="all",
        category_orders=category_orders,
        hover_data=['GHG emissions level', 'IAM', 'Carbon policy', 'Burden shifting policy'],
    )

    df_mean = df_plot.copy()
    df_mean = df_mean.groupby(x_axis)[[y_axis]].mean().reset_index()

    if x_axis in category_orders:
        df_mean[x_axis] = pd.Categorical(
            df_mean[x_axis],
            categories=category_orders[x_axis],
            ordered=True,
        )
        df_mean = df_mean.sort_values(x_axis).reset_index(drop=True)

    fig_line = px.line(
        df_mean,
        y=y_axis,
        x=x_axis,
        markers=True,
        category_orders=category_orders,
    )

    fig_line.update_traces(
        line=dict(color='black'),
        marker=dict(color='black', size=12),
    )

    return fig_box, fig_line, df_mean


def plot_contrib_aop(
        df_total_impact: pd.DataFrame,
        impact_categories_list: list,
        results_folder: str,
        aop,
        cutoff: float = 0.05,
        save_fig: bool = False,
):
    aop_impact_categories_list = [i[-1] for i in impact_categories_list if i[1] == aop]
    groupby_dims = ['Grouping', 'Key', 'GHG emissions level', 'IAM', 'Carbon policy', 'Burden shifting policy',
                    'CCS limit']

    df_plot = df_total_impact[
        df_total_impact['Grouping'] == 'all'
        ].groupby(groupby_dims).sum().reset_index().melt(
        id_vars=groupby_dims,
        value_vars=aop_impact_categories_list,
        var_name='Impact category',
    )

    df_plot['Cutoff criteria'] = abs(df_plot['value']) / df_plot['value'].max()

    df_plot = pd.merge(
        df_plot,
        df_plot.groupby(['Impact category'])['Cutoff criteria'].max().reset_index(),
        on='Impact category',
        how='left',
        suffixes=('', ' max'),
    )

    df_plot = df_plot[~df_plot['Impact category'].isin([f'Remaining {aop.lower()}', f'Total {aop.lower()} (biogenic)'])]
    df_plot['Impact category'] = df_plot.apply(
        lambda x: x['Impact category'] if abs(x['Cutoff criteria max']) >= cutoff else 'Other', axis=1)
    df_plot = df_plot.groupby(groupby_dims + ['Impact category']).sum().reset_index()
    df_plot['Policy'] = df_plot.apply(lambda x: f"{x['Carbon policy']}-{x['Burden shifting policy']}", axis=1)
    df_plot = df_plot.sort_values(by='value', ascending=False)
    for r in ((f'{aop.lower()}, ', ''), ('(beta)', ''), (', total', '')):
        df_plot['Impact category'] = df_plot['Impact category'].apply(lambda x: x.replace(*r))

    df_reference = pd.read_csv('../03_Results/Tables/reference/adjustment_ratios.csv')
    df_reference = df_reference[
        (df_reference['Impact category'].isin(aop_impact_categories_list))
        & (~df_reference['Impact category'].isin([f'Remaining {aop.lower()}', f'Total {aop.lower()} (biogenic)']))
        ][['Impact category', 'Total', 'Year', 'IAM', 'SSP-RCP']].rename(
        columns={'Total': 'value', 'SSP-RCP': 'GHG emissions level'})
    for r in ((f'{aop.lower()}, ', ''), ('(beta)', ''), (', total', '')):
        df_reference['Impact category'] = df_reference['Impact category'].apply(lambda x: x.replace(*r))
    df_reference['Impact category'] = df_reference.apply(
        lambda x: x['Impact category'] if x['Impact category'] in df_plot['Impact category'].unique() else 'Other',
        axis=1)

    df_reference_projected = df_reference[df_reference['Year'] == 2050].groupby(
        ['Impact category', 'Year', 'IAM', 'GHG emissions level']).sum().reset_index().drop(columns=['Year'])
    df_reference_projected['Policy'] = 'Reference (projected)'
    df_reference_real = df_reference[df_reference['Year'] == 2023].groupby(
        ['Impact category']).sum().reset_index().drop(columns=['Year'])

    fig = px.box(
        pd.concat([df_plot, df_reference_projected]),
        x='Impact category',
        y='value',
        color='Policy',
        points='all',
        hover_data=['GHG emissions level', 'IAM', 'CCS limit'],
        category_orders={'Policy': ['Reference (projected)', 'NZ-None', 'NZ-All', 'NN-None', 'NN-All']},
        labels={
            'value': f"Damage on {aop.lower()}<br>(1e6 {'DALY/yr' if aop == 'Human health' else 'PDF.m<sup>2</sup>.yr/yr'})"}
    )

    fig.add_trace(
        go.Scatter(
            x=df_reference_real['Impact category'],
            y=df_reference_real['value'],
            mode='markers',
            name='Reference (real)',
            marker=dict(
                color='black',
                size=10,
            )
        )
    )

    if save_fig:
        fig.write_html(f'../03_Results/Figures/{results_folder}/contrib_{'hh' if aop == 'Human health' else 'eq'}.html')

imp_cat_code_dict = {
    'Remaining ecosystem quality': 'REQ',
    'Remaining human health': 'RHH',
    'Total ecosystem quality': 'TTEQ',
    'Total human health': 'TTHH',
    'Total ecosystem quality (biogenic)': 'TTEQ',
    'Total human health (biogenic)': 'TTHH',
    'Climate change, short term, total (territorial)': 'CCT',
    'Climate change, short term, total (abroad)': 'CCA',
    'Climate change, short term, total': 'CC',
    'Cost': 'TC',
}

def plot_active_burden_shifting_constraints(
        active_constraints: pd.DataFrame,
        df_total_impact: pd.DataFrame,
        results_folder: str,
        split_by: str,
        save_fig: bool = False,
):
    imp_cat_dims = [
        'Climate change, short term, total (abroad)',
        'Remaining human health',
        'Remaining ecosystem quality',
    ]

    df_active_constraints = active_constraints[
        (active_constraints['Grouping'] == 'all')
        & (active_constraints['Burden shifting policy'] == 'All')
        & (active_constraints['Constraint'].isin(['RHH', 'REQ', 'CCA']))
    ]

    # Add an 'any' entry: if the constraint is reached for at least one background scenario
    df_active_constraints = df_active_constraints.drop(columns=['SSP-RCP'])
    df_active_constraints_copy = df_active_constraints.copy(deep=True)
    df_active_constraints['IAM' if split_by == 'GHG emissions level' else 'GHG emissions level'] = 'any'
    df_active_constraints_copy['IAM'] = 'any'
    df_active_constraints_copy['GHG emissions level'] = 'any'
    if split_by in ['IAM', 'GHG emissions level']:
        df_active_constraints = pd.concat([df_active_constraints, df_active_constraints_copy])
    else:
        df_active_constraints = df_active_constraints_copy
    df_active_constraints = df_active_constraints.groupby([i for i in df_active_constraints.columns if i != 'Active']).sum().reset_index()
    df_active_constraints['Active'] = df_active_constraints['Active'].apply(lambda x: True if x > 0 else False)

    df_plot_freq = pd.merge(
        df_active_constraints.groupby(['Constraint', split_by])[['Active']].sum().reset_index(),
        df_active_constraints.groupby(['Constraint'] + ([split_by] if split_by in ['IAM', 'GHG emissions level'] else []))[['Active']].count().rename(columns={'Active': 'Count'}).reset_index(),
        how='left',
        on=['Constraint'] + ([split_by] if split_by in ['IAM', 'GHG emissions level'] else []),
    ).reset_index()

    df_plot_freq = pd.merge(
        df_plot_freq.groupby(['Constraint', split_by])[['Active', 'Count']].sum().reset_index(),
        df_active_constraints.groupby(['Constraint', split_by])[['Active']].count().rename(columns={'Active': 'Count per type'}).reset_index(),
        how='left',
        on=['Constraint', split_by],
    ).reset_index()

    df_plot_freq['Frequency'] = 100 * df_plot_freq['Active'] / df_plot_freq['Count']
    df_plot_freq['Text'] = df_plot_freq.apply(lambda x: f"{x['Active']} / {x['Count per type']}", axis=1)

    groupby_dims = ['Grouping', 'Key', 'IAM', 'GHG emissions level', 'Carbon policy', 'Burden shifting policy','CCS limit']
    df_plot_delta = df_total_impact[(df_total_impact['Grouping'] == 'all')].groupby(groupby_dims)[imp_cat_dims].sum().reset_index()
    df_plot_delta = pd.merge(
        df_plot_delta[df_plot_delta['Burden shifting policy'] == 'All'],
        df_plot_delta[df_plot_delta['Burden shifting policy'] == 'None'],
        suffixes=('_all', '_none'),
        how='outer',
        on=['Key', 'IAM', 'GHG emissions level', 'Carbon policy', 'CCS limit'],
    )

    for imp_cat in imp_cat_dims:
        df_plot_delta[imp_cat_code_dict[imp_cat]] = 100 * (df_plot_delta[f'{imp_cat}_all'] - df_plot_delta[f'{imp_cat}_none']) / df_plot_delta[f'{imp_cat}_none']

    df_plot_delta = df_plot_delta.melt(id_vars=['Key', 'IAM', 'GHG emissions level', 'Carbon policy', 'CCS limit'], value_vars=['CCA', 'REQ', 'RHH'])

    df_plot_delta = df_plot_delta.merge(
        df_active_constraints[['Key', 'IAM', 'GHG emissions level', 'Carbon policy', 'CCS limit', 'Constraint', 'Active']].rename(columns={'Constraint': 'variable'}),
        how='left',
        on=['Key', 'IAM', 'GHG emissions level', 'Carbon policy', 'CCS limit', 'variable'],
    )

    fig = make_subplots(rows=1, cols=2, shared_yaxes=True, horizontal_spacing=0.05, column_widths=[0.3, 0.7])

    sub_fig_1 = px.bar(
        df_plot_freq,
        x='Frequency',
        y='Constraint',
        color=split_by,
        color_discrete_map=color_dict,
        text='Text',
        hover_data=['Frequency', 'Active', 'Count per type', 'Count'],
        category_orders={
            'GHG emissions level': ['high', 'medium', 'low', 'any'],
            'IAM': ['message', 'tiam-ucl', 'remind', 'image', 'any'],
            'CCS limit': ['10', '20', '30', '40', 'Infinity'],
            'Carbon policy': ['-12', '-9', '-6', '-3', '0'],
        },
    )

    sub_fig_2 = px.strip(
        df_plot_delta,
        x='value',
        y='variable',
        color=split_by,
        # points='all',
        color_discrete_map=color_dict,
        hover_data=['IAM', 'GHG emissions level', 'Carbon policy', 'CCS limit', 'Active'],
        category_orders={
            'GHG emissions level': ['high', 'medium', 'low', 'any'],
            'IAM': ['message', 'tiam-ucl', 'remind', 'image', 'any'],
            'CCS limit': ['10', '20', '30', '40', 'Infinity'],
            'Carbon policy': ['-12', '-9', '-6', '-3', '0'],
        },
    )

    if split_by == 'Carbon policy':
        unit = 'Mt CO<sub>2</sub>-eq'
    elif split_by == 'CCS limit':
        unit = 'Mt CO<sub>2</sub>'
    else:
        unit = None

    i = 0
    for trace in sub_fig_1.data:
        if i == 0:
            trace.legendgrouptitle = dict(text=split_by + (f' ({unit})' if unit is not None else ''))
        i+=1
        if split_by not in ['IAM', 'GHG emissions level']:
            trace.width = 0.5
        fig.add_trace(trace, row=1, col=1)

    for trace in sub_fig_2.data:
        trace.showlegend = False
        fig.add_trace(trace, row=1, col=2)

    fig.update_xaxes(
        title_text='Activation of burden<br>shifting constraints (%)',
        row=1, col=1,
        range=[0, 100],
    )

    fig.update_xaxes(
        title_text=r'$\Delta_{rel}^{y_{BS}}(IMP) = \frac{IMP(P(y_{BS}=1)) - IMP(P(y_{BS}=0))}{IMP(P(y_{BS}=0)} \quad \text{(%)}$',
        row=1, col=2,
        range=[-30, 20],
    )

    fig.update_layout(
        boxmode='group',
        barmode='group' if split_by in ['GHG emissions level', 'IAM'] else 'stack',
        legend_traceorder="reversed",
        margin=dict(t=5, b=5, l=5, r=5),
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="center",
            x=0.5,
        ),
    )

    if save_fig:
        fig.write_html(f'../03_Results/Figures/{results_folder}/active_constraints_{split_by.lower().replace(' ', '_')}.html', include_mathjax="cdn")
        fig.update_layout(width=800, height=400)
        fig.write_image(f'../03_Results/Figures/{results_folder}/active_constraints_{split_by.lower().replace(' ', '_')}.pdf')


replacements = {
    'District Heating Network': 'DHN',
    'Industrial': 'Ind.',
    'Decentralized': 'Dec.',
    'Heat Pump Electricity': 'HP',
    ' Combustion': '',
    ' Solar Energy': '',
    'Geothermal Heat': 'Geothermal',
    'Hydroelectric': 'Hydro',
    'River Flow': 'River',
    '-Powered': '',
    'Long Distance': 'LD',
    'Short Distance': 'SD',
    'Compressed Natural Gas': 'CNG',
    'Compressed Synthetic Natural Gas': 'CSNG',
    'Light Commercial Vehicle': 'LCV',
    'Sport Utility Vehicle': 'SUV',
}

def shorten(name):
    for old, new in replacements.items():
        name = name.replace(old, new)
    return name

def plot_utilization_frequency_and_distribution(
        df_total_impact: pd.DataFrame,
        results_folder: str,
        split_by: str,
        sector_list: list[str],
        file_name: str,
        save_fig: bool = False,
        return_fig: bool = False,
):
    i = 0

    if sector_list == ['Electricity', 'Heat', 'Resource']:
        row_heights = [7 / (7 + 13 + 15), 13 / (7 + 13 + 15), 15 / (7 + 13 + 15)]
        height_per_sector = 420
    elif sector_list == ['Alternative fuels', 'Carbon storage']:
        row_heights = [14 / (14 + 2), 2 / (14 + 2)]
        height_per_sector = 300
    elif sector_list == ['Freight mobility', 'Passenger mobility']:
        row_heights = [11 / (11 + 13), 13 / (11 + 13)]
        height_per_sector = 580
    else:
        row_heights = [1 / len(sector_list) for i in sector_list]
        height_per_sector = 420

    fig = make_subplots(
        rows=len(sector_list),
        cols=3,
        shared_yaxes=True,
        shared_xaxes=True if sector_list == ['Electricity', 'Heat', 'Resource'] else False,
        vertical_spacing=0.03 if sector_list == ['Electricity', 'Heat', 'Resource'] else 0.06,
        horizontal_spacing=0.05,
        column_widths=[0.15, 0.6, 0.25],
        row_heights=row_heights,
    )

    groupby_dims = ['Grouping', 'Key', 'Carbon policy', 'Burden shifting policy', 'CCS limit']
    value_col = 'Capacity or production'
    item_cols = ['index', 'Phase', 'Sector']

    for k, sector in enumerate(sector_list):

        if sector == 'Resource':
            phase = 'Resource'
        else:
            phase = 'Operation (direct)'

        df_plot = df_total_impact[
            (df_total_impact['Grouping'] == 'all')
            & (df_total_impact['Phase'] == phase)
            ].groupby(groupby_dims + item_cols)[[value_col]].mean().reset_index()

        # --- fill missing (run, index) combinations with zeros ---
        runs = df_plot[groupby_dims].drop_duplicates()
        items = df_plot[item_cols].drop_duplicates()
        full_grid = runs.merge(items, how='cross')  # every run x every index

        df_plot = full_grid.merge(df_plot, on=groupby_dims + item_cols, how='left')
        df_plot[value_col] = df_plot[value_col].fillna(0)

        if phase != 'Resource':
            if sector == 'Heat':
                df_plot = df_plot[df_plot['Sector'].isin(['Industrial heat', 'Domestic heat'])]
            else:
                df_plot = df_plot[df_plot['Sector'] == sector]

        df_plot['Capacity or production'] *= 1e-3  # from GWh to TWh

        if phase == 'Resource':
            # aggregating biomass resources in 3 main categories
            df_wood = df_plot[df_plot['index'].isin(wood_list)].groupby(groupby_dims)[['Capacity or production']].sum().reset_index()
            df_wood['index'] = 'Wood'
            df_wood['Phase'] = 'Resource'
            df_wet_biomass = df_plot[df_plot['index'].isin(wet_biomass_list)].groupby(groupby_dims)[['Capacity or production']].sum().reset_index()
            df_wet_biomass['index'] = 'Wet biomass'
            df_wet_biomass['Phase'] = 'Resource'
            df_waste = df_plot[df_plot['index'].isin(waste_list)].groupby(groupby_dims).sum()[['Capacity or production']].reset_index()
            df_waste['index'] = 'Waste'
            df_waste['Phase'] = 'Resource'
            df_plot = df_plot[~df_plot['index'].isin(wood_list+wet_biomass_list+waste_list+['CO2_E', 'Electricity import'])]
            df_plot = pd.concat([df_plot, df_wood, df_wet_biomass, df_waste])

        else:
            sub_names_to_exclude = ['Transformer', 'CO2 Storage']
            df_plot = df_plot[~df_plot['index'].str.contains('|'.join(sub_names_to_exclude))]

        df_plot['index'] = df_plot['index'].map(shorten)
        N_run = len(df_plot[[i for i in groupby_dims if i != split_by]].drop_duplicates())
        df_freq = df_plot[df_plot['Capacity or production'] != 0].groupby(['index', split_by])[['Capacity or production']].count().reset_index().rename(columns={'Capacity or production': 'Count'})
        df_freq['Frequency'] = 100 * df_freq['Count'] / N_run
        df_freq = df_freq.merge(
            df_plot.groupby(['index'])[['Capacity or production']].mean(),
            how='left',
            on=['index'],
        )
        sorted_order = df_freq.groupby('index')['Capacity or production'].first().sort_values(ascending=True).index.tolist()

        df_delta = pd.merge(
            df_plot[df_plot['Burden shifting policy'] == 'None'],
            df_plot[df_plot['Burden shifting policy'] == 'All'],
            on=[i for i in groupby_dims if i != 'Burden shifting policy'] + ['index', 'Phase'],
            suffixes=('_none', '_all'),
            how='outer',
        )

        df_delta['Capacity or production_none'] = df_delta['Capacity or production_none'].fillna(0)
        df_delta['Capacity or production_all'] = df_delta['Capacity or production_all'].fillna(0)
        df_delta['Delta'] = df_delta['Capacity or production_all'] - df_delta['Capacity or production_none']
        # df_delta['Delta_perc'] = 100 * df_delta['Delta'] / df_delta['Capacity or production_none']

        sub_fig_1 = px.bar(
            df_freq,
            x='Frequency',
            y='index',
            color=split_by,
            color_discrete_map=color_dict,
            hover_data=['Count'],
            category_orders={split_by: ['All', 'None']}
        )

        sub_fig_2 = px.box(
            df_plot,
            x='Capacity or production',
            y='index',
            color=split_by,
            points=False,
            hover_data=['Carbon policy', 'CCS limit'],
            color_discrete_map=color_dict,
            category_orders={split_by: ['All', 'None']}
        )

        sub_fig_3 = px.box(
            df_delta,
            x='Delta',
            y='index',
            points=False,
            hover_data=['Carbon policy', 'CCS limit'],
            color_discrete_sequence=['black'],
        )

        for trace in sub_fig_1.data:
            if i == 0 and k == 0:
                trace.legendgrouptitle = dict(text=split_by)
            if k > 0:
                trace.showlegend = False
            i+=1
            fig.add_trace(trace, row=k+1, col=1)

        for trace in sub_fig_2.data:
            trace.showlegend = False
            fig.add_trace(trace, row=k+1, col=2)

        for trace in sub_fig_3.data:
            trace.showlegend = False
            trace.width = 0.6
            trace.marker.color = 'black'
            trace.line.color = 'black'
            fig.add_trace(trace, row=k+1, col=3)

        n_cats = len(sorted_order)
        fig.update_yaxes(
            categoryorder='array',
            categoryarray=sorted_order,
            range=[-0.5, n_cats - 0.5],
            row=k+1
        )

    fig.update_xaxes(
        title_text='Utilization frequency (%)',
        range=[0, 100],
        row=len(sector_list), col=1
    )

    if sector_list == ['Electricity', 'Heat', 'Resource']:
        unit = 'TWh/year'
        fig.update_xaxes(
            range=[-5, 250],
            row=len(sector_list), col=2
        )
        fig.update_xaxes(
            range=[-70, 190],
            row=len(sector_list), col=3
        )
    elif sector_list == ['Freight mobility', 'Passenger mobility']:
        unit = 'Gtkm/year or Gpkm/year'
    elif sector_list == ['Alternative fuels', 'Carbon storage']:
        unit = 'TWh/year or Mt CO2/year'

    fig.update_xaxes(
        title_text=f'Utilization ({unit})',
        row=len(sector_list), col=2
    )

    fig.update_xaxes(
        title_text=f'Utilization difference with<br>burden shifting constraints<br>({unit})',
        row=len(sector_list), col=3
    )

    fig.update_yaxes(showticklabels=False, col=2)
    fig.update_yaxes(showticklabels=False, col=3)

    fig.update_layout(
        boxmode='group',
        barmode='group',
        margin=dict(t=5, b=5, l=5, r=5),
        legend_traceorder="reversed",
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="center",
            x=0.5,
        ),
    )

    if save_fig:
        fig.write_html(f'../03_Results/Figures/{results_folder}/{file_name}.html')
        fig.update_layout(width=1000, height=height_per_sector*len(sector_list))
        fig.write_image(f'../03_Results/Figures/{results_folder}/{file_name}.pdf')

    if return_fig:
        return fig

def plot_delta(
        df_total_impact: pd.DataFrame,
        results_folder: str,
        dim: str,
        delta_dim: str = 'Burden shifting policy',
        relative: bool = True,
        save_fig: bool = False,
        return_fig: bool = False,
        return_df: bool = False,
):

    groupby_dims = ['Grouping', 'Key', 'Burden shifting policy', 'CCS limit', 'Carbon policy']

    if dim in ['Natural gas', 'New Wind Energy Onshore']:
        df_plot = df_total_impact[(df_total_impact['index'] == dim) & (df_total_impact['Phase'].isin(['Resource', 'Operation (direct)']))]
        new_dim = 'Capacity or production'
        df_plot = df_plot[groupby_dims + [new_dim]].drop_duplicates()
    else:
        df_plot = df_total_impact[groupby_dims + [dim]].drop_duplicates()
        new_dim = dim

    df_plot = df_plot.groupby(groupby_dims)[[new_dim]].sum().reset_index()

    if delta_dim == 'Burden shifting policy':

        df_plot_delta = pd.merge(
            df_plot[df_plot['Burden shifting policy'] == 'All'],
            df_plot[df_plot['Burden shifting policy'] == 'None'],
            on=['Grouping', 'Key', 'CCS limit', 'Carbon policy'],
            how='left',  # in case 'All' is infeasible
            suffixes=('_all', '_none'),
        ).reset_index()

        df_plot_delta['Delta'] = df_plot_delta[f'{new_dim}_all'] - df_plot_delta[f'{new_dim}_none']
        df_plot_delta['Delta_rel'] = 100 * (df_plot_delta['Delta']) / df_plot_delta[f'{new_dim}_none']

    elif delta_dim == 'Grouping':

        df_plot_delta = pd.merge(
            df_plot[df_plot['Grouping'] != 'all'],
            df_plot[df_plot['Grouping'] == 'all'],
            on=['Burden shifting policy', 'CCS limit', 'Carbon policy'],
            how='right',  # in case 'all' is infeasible
            suffixes=('', '_all'),
        ).reset_index()

        df_plot_delta['Delta'] = df_plot_delta[f'{new_dim}_all'] - df_plot_delta[f'{new_dim}']
        df_plot_delta['Delta_rel'] = 100 * (df_plot_delta['Delta']) / df_plot_delta[f'{new_dim}']

    else:
        raise ValueError(f"Delta dimension '{delta_dim}' not supported.")

    # df_plot_delta['Scenario'] = df_plot_delta.apply(lambda x: f"{x['Carbon policy']} - {x['CCS limit']}", axis=1)

    if not relative and dim != 'Cost':
        df_plot_delta['Delta'] *= 1e-3  # from GWh to TWh

    fig = px.strip(
        df_plot_delta,
        x='Delta_rel' if relative else 'Delta',
        y='Key',
        color='Burden shifting policy' if delta_dim == 'Grouping' else None,
        color_discrete_sequence=px.colors.qualitative.Safe if delta_dim == 'Grouping' else ['Black'],
        # points='all',
        # symbol='CCS limit',
        # opacity=0.7,
        hover_data=['CCS limit', 'Carbon policy'] + (['Burden shifting policy'] if delta_dim == 'Grouping' else []),
        labels={
            'Delta_rel': "Relative difference (%)",
            'Delta': f"Difference in the utilization of {dim.lower()} (TWh/yr)" if dim != 'Cost' else "Difference in cost (MCAD/yr)",
        },
        category_orders={
            'Grouping': ['all', 'ssp_rcp', 'iam', 'individual'],
            'Key': [
                "image-high",
                "image-medium",
                "image-low",
                "message-high",
                "message-medium",
                "message-low",
                "remind-high",
                "remind-medium",
                "remind-low",
                "tiam-ucl-high",
                "tiam-ucl-medium",
                "tiam-ucl-low",
                "image",
                "message",
                "remind",
                "tiam-ucl",
                "high",
                "medium",
                "low",
                "all"
            ]
        }
    )

    fig.add_hline(y=0.5, line_dash="dot", line_color="black")
    fig.add_hline(y=3.5, line_dash="dot", line_color="black")
    fig.add_hline(y=7.5, line_dash="dot", line_color="black")

    if save_fig:
        fig.write_html(f'../03_Results/Figures/{results_folder}/{dim.lower().replace(' ', '_')}_{delta_dim.lower().replace(' ', '_')}_distrib_grouping.html')

    if return_fig and not return_df:
        return fig
    if return_df and not return_fig:
        return df_plot_delta
    if return_fig and return_df:
        return fig, df_plot_delta

def plot_relative_cost_difference_heatmap(
        df: pd.DataFrame,
        difference_type: str,
        save_fig: bool,
        results_folder: str,
        file_name: str,
):
    # ---------- settings ----------
    x_order = [
        "image-high", "image-medium", "image-low",
        "message-high", "message-medium", "message-low",
        "remind-high", "remind-medium", "remind-low",
        "tiam-ucl-high", "tiam-ucl-medium", "tiam-ucl-low",
        "image", "message", "remind", "tiam-ucl",
        "high", "medium", "low", "all",
    ]  # key order, now plotted top -> bottom
    x_separators = [("tiam-ucl-low", "image"), ("tiam-ucl", "high"), ("low", "all")]

    grouping = difference_type == 'grouping'
    min_cost = difference_type == 'min_cost'
    min_imp = difference_type in ['Remaining human health', 'Remaining ecosystem quality', 'Climate change, short term, total (abroad)', 'Climate change, short term, total (territorial)']

    if grouping:
        x_order = [i for i in x_order if i != 'all']
        x_separators = [i for i in x_separators if i != ("low", "all")]

    if min_imp:
        x_order = [i for i in x_order if i not in ["image", "message", "remind", "tiam-ucl", "high", "medium", "low", "all"]]
        x_separators = []

    # burden shifting policy: value in the dataframe -> compact label
    BS_COL = "Burden shifting policy"
    bs_levels = ["All", "None"] if grouping or min_cost or min_imp else [None]
    bs_label = {"All": "1", "None": "0"}
    w = len(bs_levels)                                # sub-rows per key

    KNEE = 2.5 if grouping else (0 if min_cost or min_imp else 2.0)
    FRAC = 0.8

    # ---------- data ----------
    if grouping or min_cost or min_imp:
        if min_imp:
            active = df.pivot(index=["Key", BS_COL], columns=["CCS limit", "Carbon policy"], values="Active")
        df = df.pivot(index=["Key", BS_COL], columns=["CCS limit", "Carbon policy"], values="imp_cat" if min_imp else "Delta_rel")
        new_index = pd.MultiIndex.from_product([x_order, bs_levels])
    else:
        df = df.pivot(index="Key", columns=["CCS limit", "Carbon policy"], values="Delta_rel")
        new_index = x_order

    ccs_levels = sorted(df.columns.get_level_values(0).unique(), key=float)
    carbon_levels = sorted(df.columns.get_level_values(1).unique(), key=float)
    full = pd.MultiIndex.from_product([ccs_levels, carbon_levels], names=df.columns.names)

    df = df.reindex(index=new_index, columns=full)    # missing combinations -> NaN
    if min_imp:
        # same reindexing as df; missing cells become NaN -> eq(True) turns them into False
        active = active.reindex(index=new_index, columns=full).eq(True)
    cols = list(df.columns)
    n = len(cols)                                     # number of (CCS, carbon) columns

    z = df.values                                     # rows = (Key, BS), cols = (CCS, carbon)
    nx = z.shape[0]                                   # number of rows (keys x BS levels)
    x = np.arange(n)                                  # horizontal: one column per (CCS, carbon)
    y = np.arange(nx)                                 # vertical: key i -> rows i*w ... i*w + w - 1

    def fmt(v):
        v = float(v)
        return "Infinity" if np.isinf(v) else f"{v:g}"

    # ---------- piecewise colour scale ----------
    def knee_colorscale(zmax, knee=KNEE, frac=FRAC, base="RdYlGn_r", n_stops=60):
        brk = knee / zmax
        u = np.linspace(0, 1, n_stops)
        p = np.where(u <= frac, u / frac * brk, brk + (u - frac) / (1 - frac) * (1 - brk))
        p = np.clip(p, 0, 1)
        p[0], p[-1] = 0.0, 1.0
        colors = sample_colorscale(base, list(u))
        return [[float(pi), c] for pi, c in zip(p, colors)]

    # --- handle log10(0) = -inf ---
    neg_inf = np.isneginf(z)
    z_finite = np.where(neg_inf, np.nan, z)

    zmax = max(np.nanmax(z_finite), KNEE * 1.01)
    zmin = np.nanmin(z_finite) if min_cost or min_imp else 0
    z_plot = z.copy()
    z_plot[np.isneginf(z_plot)] = zmin      # finite replacement

    if min_cost:  # center colorscale on 0
        lim = max(abs(zmin), abs(zmax))
        zmin, zmax = -lim, lim
    elif min_imp:
        if difference_type == 'Climate change, short term, total (abroad)':
            rounding = 10
            delta_step = 0.26
        elif difference_type == 'Climate change, short term, total (territorial)':
            rounding = 10
            delta_step = 0.2
        elif difference_type == 'Remaining human health':
            rounding = 100
            delta_step = 0.005
        else: # REQD
            rounding = 0.01
            delta_step = 200
        zmin = math.floor(rounding * zmin) / rounding
        zmax = math.ceil(rounding * zmax) / rounding

    if min_cost:
        tickvals = list(np.linspace(-2.0, 2.0, 5))
        ticktext = [str(10**i) for i in tickvals]
    elif min_imp:
        tickvals = list(np.linspace(zmin, zmax, int((zmax - zmin) / delta_step) + 1))
    else:
        tickvals = ([0, 1, 2, 3] if grouping else [0, 0.5, 1.0, 1.5]) + list(range(int(KNEE), int(zmax) + 1, 2))[1:]
    tickvals = sorted(set(tickvals))

    # per-cell hover info: (key, CCS limit, carbon policy, burden shifting); shape (nx, n, 4)
    key_labels = [k for k in x_order for _ in bs_levels]
    bs_labels = [bs_label.get(b, "-") for _ in x_order for b in bs_levels]
    key_grid = np.tile(np.array(key_labels)[:, None], (1, n))
    bs_grid = np.tile(np.array(bs_labels)[:, None], (1, n))
    ccs_grid = np.tile(np.array([fmt(c[0]) for c in cols])[None, :], (nx, 1))
    carbon_grid = np.tile(np.array([fmt(c[1]) for c in cols])[None, :], (nx, 1))
    customdata = np.dstack((key_grid, ccs_grid, carbon_grid, bs_grid))

    hover = ("Key: %{customdata[0]}<br>CCS limit: %{customdata[1]}"
             "<br>Carbon policy: %{customdata[2]}")
    if grouping or min_cost or min_imp:
        hover += "<br>Burden shifting: %{customdata[3]}"
    hover += "<br>Value: %{z:.3f}<extra></extra>"

    # ---------- figure ----------
    fig = go.Figure(go.Heatmap(
        z=z_plot, x=x, y=y,
        zmin=zmin, zmax=zmax,
        colorscale="RdYlGn_r" if min_cost or min_imp else knee_colorscale(zmax),
        xgap=1, ygap=1,
        hoverongaps=False,
        customdata=customdata,
        hovertemplate=hover,
        colorbar=dict(x=1.0, xanchor="left", xpad=60, tickvals=tickvals),
    ))

    if min_cost:
        fig.update_traces(colorbar=dict(tickvals=tickvals, ticktext=ticktext))

    fig.update_layout(
        plot_bgcolor="lightgrey",
        paper_bgcolor="white",
        width=max(700, 28 * n + 330), height=max(500, 20 * nx + 190),
        margin=dict(l=100, r=5, t=50, b=50),
    )
    # vertical axis: keys (first key at the top), labels on the left
    fig.update_yaxes(
        tickmode="array",
        tickvals=[i * w + (w - 1) / 2 for i in range(len(x_order))],   # centre of each key
        ticktext=x_order,
        tickangle=0, showgrid=False, zeroline=False,
        range=[nx - 0.5, -0.5],
    )
    # horizontal axis: (CCS, carbon) columns, labeled manually
    fig.update_xaxes(
        range=[-0.5, n - 0.5], showticklabels=False, showgrid=False,
        zeroline=False, ticks="",
    )

    # bottom: carbon policy labels
    for i, (ccs, carbon) in enumerate(cols):
        fig.add_annotation(x=i, xref="x", y=0, yref="paper", yanchor="top", yshift=-2,
                           text=fmt(carbon), showarrow=False, xanchor="center")

    # top: CCS labels + thick vertical separators
    ccs_list = [c[0] for c in cols]
    start = 0
    for k, ccs in enumerate(dict.fromkeys(ccs_list)):
        size = ccs_list.count(ccs)
        fig.add_annotation(x=start + (size - 1) / 2, xref="x", y=1, yref="paper", yanchor="bottom", yshift=2,
                           text=f"<b>{fmt(ccs)}</b>", showarrow=False, xanchor="center")
        if k > 0:
            fig.add_shape(type="line", xref="x", yref="paper",
                          x0=start - 0.5, x1=start - 0.5, y0=0, y1=1,
                          line=dict(color="black", width=2))
        start += size

    # thick horizontal separators between key groups (boundary after the last sub-row of a)
    for a, b in x_separators:
        pos = x_order.index(a) * w + (w - 1) + 0.5
        fig.add_shape(type="line", xref="paper", yref="y",
                      x0=0, x1=1, y0=pos, y1=pos,
                      line=dict(color="black", width=2))

    # right side: burden shifting policy (1 / 0) next to every row + a title
    if grouping or min_cost or min_imp:
        for j in range(nx):
            fig.add_annotation(x=1, xref="paper", y=j, yref="y", xanchor="left", xshift=4,
                               text=bs_labels[j], showarrow=False, font=dict(size=11))
        fig.add_annotation(x=1, xref="paper", y=0.5, yref="paper", xanchor="left", xshift=24,
                           text="Burden shifting policy", showarrow=False, textangle=90,
                           font=dict(size=13, color="black"))

    # marker on the -inf cell
    if min_cost and neg_inf.any():
        r, c = np.where(neg_inf)
        fig.add_trace(go.Scatter(
            x=c, y=r, mode="markers", hoverinfo="skip", showlegend=False,
            marker=dict(symbol="star", size=6, color="white",
                        line=dict(color="black", width=1)),
        ))

    # marker on binding constraints
    if min_imp:
        active_z = active.values
        r, c = np.where(active_z)
        fig.add_trace(go.Scatter(
            x=c, y=r, mode="markers", hoverinfo="skip", showlegend=False,
            marker=dict(symbol="circle", size=6, color="black",
                        line=dict(color="white", width=1)),
        ))

    # axis titles (top: CCS, bottom: carbon policy)
    fig.add_annotation(
        x=0.5, xref="paper", y=1, yref="paper", yanchor="bottom", yshift=24,
        text="<i>limit<sub>CCS</sub></i> (Mt CO<sub>2</sub>)",
        showarrow=False, font=dict(size=14),
    )

    fig.add_annotation(
        x=0.5, xref="paper", y=0, yref="paper", yanchor="top", yshift=-26,
        text="<i>territorial<sub>obj</sub></i> (Mt CO<sub>2</sub>-eq)",
        showarrow=False, font=dict(size=14),
    )

    if grouping:
        label = r'$\begin{array}{c}\Delta_{rel}^{all}C_{tot} \\ \text{(%)}\end{array}$'
    elif min_cost:
        label = r'$\begin{array}{c}\Delta_{rel}^{min}C_{tot} \\ \text{(%)}\end{array}$'
    elif min_imp:
        label = f'{imp_cat_code_dict[difference_type]}<br>({unit_dict_plotly[difference_type]})'
    else:
        label = r'$\begin{array}{c}\Delta_{rel}^{y_{BS}}C_{tot} \\ \text{(%)}\end{array}$'

    # colorbar title, above the colorbar
    fig.add_annotation(
        x=0.92 if min_imp else 0.95, xref="paper", xanchor="left", xshift=60,
        y=1.00, yref="paper", yanchor="bottom",
        text=label, showarrow=False, textangle=0,
        font=dict(size=14 if min_imp else 18),
    )

    if save_fig:
        fig.write_html(f'../03_Results/Figures/{results_folder}/{file_name}.html', include_mathjax="cdn")
        # fig.update_layout(height=600, width=800)
        # fig.write_image(f'../03_Results/Figures/{results_folder}/{file_name}.pdf')

def plot_box_rel_delta(
        df: pd.DataFrame,
        cat: str,
        results_folder: str = None,
        save_fig: bool = False,
        return_fig: bool = False,
        file_name: str = None,
):
    df_plot = df.copy()

    if cat not in ['bs', 'all']:
        df_plot = df_plot[df_plot.Grouping == 'all']
        df_plot = pd.merge(
            df_plot[df_plot['Burden shifting policy'] == 'All'],
            df_plot[df_plot['Burden shifting policy'] == 'None'],
            on=['Grouping', 'Key', 'Carbon policy', 'CCS limit'],
            suffixes=('_all', '_none'),
        )
        df_plot['Delta_rel'] = 100 * (df_plot['imp_cat_all'] - df_plot['imp_cat_none']) / df_plot['imp_cat_none']

    else:
        df_plot['Delta_rel'] = df_plot['Delta_rel'].apply(lambda x: x if x >= 0.01 else 0.01)  # values below 0.01% are rounded for log compatibility

    df_plot['CCS limit - Territorial emissions limit'] = df_plot.apply(lambda x: f"({x['CCS limit']}, {x["Carbon policy"]})", axis=1)
    df_plot['Carbon policy'] = df_plot['Carbon policy'].astype(float)
    df_plot = df_plot.sort_values(['CCS limit', 'Carbon policy'], ascending=True)
    fig = px.box(
        df_plot if cat not in ['bs', 'all'] else df_plot[df_plot['CCS limit - Territorial emissions limit'] != '(10, -3)'],
        y='Delta_rel',
        log_y=False if cat not in ['bs', 'all'] else True,
        x='CCS limit - Territorial emissions limit',
        color='Carbon policy',
        color_discrete_map={
            -12.:  '#74C476',      # medium-light green
            -9.:   '#41AB5D',      # medium green
            -6.:   '#238B45',      # medium-dark green
            -3.:   '#006D2C',      # dark green
            0.:    '#00441B',      # very dark green
        },
        points=False,
        category_orders={'CCS limit - Territorial emissions limit': df_plot['CCS limit - Territorial emissions limit'].unique()},
    )

    if cat in ['bs', 'all']:
        scatter_fig = px.scatter(
            df_plot[
                (df_plot.Grouping != 'individual')
                    | (
                        (df_plot.Grouping == 'individual')
                        & (df_plot['CCS limit - Territorial emissions limit'] == "(10, -3)")
                )
            ],
            y='Delta_rel',
            log_y=True,
            x='CCS limit - Territorial emissions limit',
            color='Grouping',
            color_discrete_map={
                'individual': '#006D2C',
                'iam': '#d62728',
                'ssp_rcp': '#1f77b4',
                'all': 'black',
            },
            symbol='Grouping',
            symbol_map={
                'individual': 'circle',
                'iam': 'square',
                'ssp_rcp': 'diamond',
                'all': 'x',
            },
            category_orders={'Grouping': ['individual', 'iam', 'ssp_rcp', 'all']}
        )
        fig.add_traces(scatter_fig.data)

    fig.update_layout(showlegend=False, margin=dict(t=5, l=5, r=5), boxmode='overlay')
    if cat not in ['bs', 'all']:
        fig.update_yaxes(title_text=fr'$\Delta_{{rel}}^{{y_{{BS}}}}{imp_cat_code_dict[cat]} \ \text{{(%)}}$')
    elif cat == 'bs':
        fig.update_yaxes(title_text=r'$\Delta_{rel}^{y_{BS}}{C_{tot}} \ \text{(%)}$')
    else:
        fig.update_yaxes(title_text=r'$\Delta_{rel}^{all}{C_{tot}} \ \text{(%)}$')
    fig.update_xaxes(title_text='(<i>limit<sub>CCS</sub></i>, <i>territorial<sub>obj</sub></i>)')

    if save_fig:
        if cat not in ['bs', 'all'] and file_name is None:
            file_name = f"box_delta_rel_{imp_cat_code_dict[cat].lower()}"
        fig.write_html(f'../03_Results/Figures/{results_folder}/{file_name}.html', include_mathjax="cdn")
        # fig.update_layout(height=420, width=800)
        # fig.write_image(f'../03_Results/Figures/{results_folder}/{file_name}.pdf')

    if return_fig:
        return fig