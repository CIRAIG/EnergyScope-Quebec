import pandas as pd
import plotly.express as px
import plotly.graph_objs as go
from plotly.subplots import make_subplots
import numpy as np
import sys
from pathlib import Path

NOTEBOOK_DIR = Path.cwd()
LCA_PROJECTS_ROOT = NOTEBOOK_DIR.parent.parent
sys.path.insert(1, str(LCA_PROJECTS_ROOT / '00_Shared'))
from utils import (
    wood_list, waste_list, wet_biomass_list,
    sector_unit_dict,
)

str_to_num_ccs_limit = {
    'Infinity': 50,
    '40000': 40,
    '30000': 30,
    '20000': 20,
    '10000': 10,
}

str_to_num_grouping = {
    'all': 0,
    'iam': 1,
    'ssp_rcp': 2,
    'individual': 3,
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

str_to_num_carbon_policy = {
    'NZ': 0,
    'NN': 1,
}

str_to_num_burden_shifting_policy = {
    'None': 0,
    'REQ': 1,
    'RHH': 2,
    'CCA': 3,
    'RHH REQ': 4,
    'CCA REQ': 5,
    'CCA RHH': 6,
    'All': 7,
}

def plot_parallel_coord(
        df_total_impact: pd.DataFrame,
        results_folder: str,
        show_fig: bool=False,
        save_fig: bool=False
):

    group_by_dims = ['Grouping', 'Key', 'GHG emissions level', 'IAM', 'Carbon policy', 'Burden shifting policy', 'CCS limit']
    indicator_dims = [
        'Remaining ecosystem quality',
        'Remaining human health',
        'Climate change, short term, total (abroad)',
        'Cost',
    ]
    tech_res_dims = [
        'New Wind Energy Onshore',
        'Natural gas',
        'Carbon Transport and Injection',
        'Carbon Mineralization',
    ]

    df_paral_coord = df_total_impact.groupby(group_by_dims)[indicator_dims].sum()
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
    df_paral_coord['Carbon policy'] = df_paral_coord['Carbon policy'].apply(lambda x: str_to_num_carbon_policy[x])
    df_paral_coord['Burden shifting policy'] = df_paral_coord['Burden shifting policy'].apply(lambda x: str_to_num_burden_shifting_policy[x])

    if df_paral_coord['CCS limit'].dtype == float:
        df_paral_coord['CCS limit'] = df_paral_coord['CCS limit'].apply(lambda x: str(int(x)) if x != np.Inf else 'Infinity')
    df_paral_coord['CCS limit'] = df_paral_coord['CCS limit'].apply(lambda x: str_to_num_ccs_limit[x])

    fig = px.parallel_coordinates(
        df_paral_coord,
        dimensions=group_by_dims + indicator_dims + tech_res_dims,
        # color='GHG emissions level',
        # color_continuous_scale=px.colors.cyclical.Phase,
        # color_continuous_midpoint=2,
        # labels={},
    )

    fig.data[0].dimensions[0].update(tickvals=list(str_to_num_grouping.values()), ticktext=list(str_to_num_grouping.keys()))
    fig.data[0].dimensions[1].update(tickvals=list(str_to_num_ssp_rcp.values()), ticktext=list(str_to_num_ssp_rcp.keys()))
    fig.data[0].dimensions[2].update(tickvals=list(str_to_num_iam.values()), ticktext=list(str_to_num_iam.keys()))
    fig.data[0].dimensions[3].update(tickvals=list(str_to_num_carbon_policy.values()), ticktext=list(str_to_num_carbon_policy.keys()))
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

    # Carbon policy — Tol vibrant, nothing reused
    'NN':   '#EE3377',      # magenta (Tol vibrant)
    'NZ':   '#33BBEE',      # cyan (Tol vibrant)

    # CCS availability limit — ColorBrewer Purples 5 (sequential, light→dark)
    '10000':    '#DADAEB',  # light purple
    '20000':    '#BCBDDC',  # light-medium purple
    '30000':    '#9E9AC8',  # medium purple
    '40000':    '#756BB1',  # dark-medium purple
    'Infinity': '#54278F',  # dark purple

    'any': 'grey',
}

def plot_box_distribution_vs_ccs_availability(
        df_total_impact: pd.DataFrame,
        y_axis: str,
        split_by: str,
):

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

    fig = px.box(
        df_plot,
        y=y_axis,
        x="CCS limit",
        color=split_by,
        color_discrete_map=color_dict,
        points="all",
        category_orders={
            'CCS limit': ['10000', '20000', '30000', '40000', 'Infinity'],
            'GHG emissions level': ['low', 'medium', 'high', 'any'],
        },
        hover_data=['GHG emissions level', 'IAM', 'Carbon policy', 'Burden shifting policy'],
    )

    return fig


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

    df_plot_freq['Frequency'] = 100 * df_plot_freq['Active'] / df_plot_freq['Count']

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
        hover_data=['Frequency', 'Active', 'Count'],
        category_orders={
            'GHG emissions level': ['high', 'medium', 'low', 'any'],
            'IAM': ['message', 'tiam-ucl', 'remind', 'image', 'any'],
            'CCS limit': ['10000', '20000', '30000', '40000', 'Infinity'],
        },
    )

    sub_fig_2 = px.box(
        df_plot_delta,
        x='value',
        y='variable',
        color=split_by,
        points='all',
        color_discrete_map=color_dict,
        hover_data=['IAM', 'GHG emissions level', 'Carbon policy', 'CCS limit', 'Active'],
        category_orders={
            'GHG emissions level': ['high', 'medium', 'low', 'any'],
            'IAM': ['message', 'tiam-ucl', 'remind', 'image', 'any'],
            'CCS limit': ['10000', '20000', '30000', '40000', 'Infinity'],
        },
    )

    i = 0
    for trace in sub_fig_1.data:
        if i == 0:
            trace.legendgrouptitle = dict(text=split_by)
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
        title_text=f'Relative impact difference<br>with burden shifting constraints (%)',
        row=1, col=2,
        range=[-30, 15],
    )

    fig.update_layout(
        boxmode='group',
        barmode='group' if split_by in ['GHG emissions level', 'IAM'] else 'stack',
        legend_traceorder="reversed",
        margin=dict(t=5, b=5, l=5, r=5),
    )

    if save_fig:
        fig.write_html(f'../03_Results/Figures/{results_folder}/active_constraints_{split_by.lower().replace(' ', '_')}.html')
        fig.update_layout(width=800, height=400)
        fig.write_image(f'../03_Results/Figures/{results_folder}/active_constraints_{split_by.lower().replace(' ', '_')}.pdf')

def plot_utilization_frequency_and_distribution(
        df_total_impact: pd.DataFrame,
        results_folder: str,
        phase: str,
        split_by: str,
        sector: str = None,
        save_fig: bool = False,
):

    groupby_dims = ['Grouping', 'Key', 'Carbon policy', 'Burden shifting policy', 'CCS limit']

    df_plot = df_total_impact[
        (df_total_impact['Grouping'] == 'all')
        & (df_total_impact['Phase'] == phase)
    ].groupby(groupby_dims+['index', 'Phase', 'Sector'])[['Capacity or production']].mean().reset_index()

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
        sub_names_to_exclude = ['Transformer', 'Existing']
        df_plot = df_plot[~df_plot['index'].str.contains('|'.join(sub_names_to_exclude))]

    N_run = len(df_plot[[i for i in groupby_dims if i != split_by]].drop_duplicates())
    df_freq = df_plot.groupby(['index', split_by])[['Capacity or production']].count().reset_index()
    df_freq['Frequency'] = 100 * df_freq['Capacity or production'] / N_run
    df_freq = df_freq.merge(df_plot.groupby(['index'])[['Capacity or production']].mean(), how='left', on=['index'], suffixes=('', ' (mean)'))
    sorted_order = df_freq.groupby('index')['Capacity or production (mean)'].first().sort_values(ascending=True).index.tolist()

    fig = make_subplots(rows=1, cols=2, shared_yaxes=True, horizontal_spacing=0.02)

    sub_fig_1 = px.bar(
        df_freq,
        x='Frequency',
        y='index',
        color=split_by,
        color_discrete_map=color_dict,
    )

    sub_fig_2 = px.box(
        df_plot,
        x='Capacity or production',
        y='index',
        color=split_by,
        points='all',
        hover_data=['Carbon policy', 'CCS limit'],
        color_discrete_map=color_dict,
    )

    i = 0
    for trace in sub_fig_1.data:
        if i == 0:
            trace.legendgrouptitle = dict(text=split_by)
        i+=1
        fig.add_trace(trace, row=1, col=1)

    for trace in sub_fig_2.data:
        trace.showlegend = False
        fig.add_trace(trace, row=1, col=2)

    fig.update_xaxes(
        title_text='Utilization frequency (%)',
        row=1, col=1
    )

    fig.update_xaxes(
        title_text=f'Utilization ({sector_unit_dict[sector] if sector is not None else 'TWh/yr'})',
        row=1, col=2
    )

    fig.update_yaxes(
        categoryorder='array',
        categoryarray=sorted_order,
    )

    fig.update_layout(
        boxmode='group',
        barmode='group',
        margin=dict(t=20, b=20, l=20, r=20),
    )

    if save_fig:
        fig.write_html(f'../03_Results/Figures/{results_folder}/config_frequency_{'res' if phase == 'Resource' else f'op_{sector.lower().replace(' ', '_')}'}.html')

def plot_delta(
        df_total_impact: pd.DataFrame,
        results_folder: str,
        dim: str,
        delta_dim: str = 'Burden shifting policy',
        relative: bool = True,
        save_fig: bool = False,
        return_fig: bool = False,
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
            how='outer',
            suffixes=('_all', '_none'),
        ).reset_index()

        df_plot_delta['Delta'] = df_plot_delta[f'{new_dim}_all'] - df_plot_delta[f'{new_dim}_none']
        df_plot_delta['Delta_rel'] = 100 * (df_plot_delta['Delta']) / df_plot_delta[f'{new_dim}_none']

    elif delta_dim == 'Grouping':

        df_plot_delta = pd.merge(
            df_plot[df_plot['Grouping'] != 'all'],
            df_plot[df_plot['Grouping'] == 'all'],
            on=['Burden shifting policy', 'CCS limit', 'Carbon policy'],
            how='left',
            suffixes=('', '_all'),
        ).reset_index()

        df_plot_delta['Delta'] = df_plot_delta[f'{new_dim}_all'] - df_plot_delta[f'{new_dim}']
        df_plot_delta['Delta_rel'] = 100 * (df_plot_delta['Delta']) / df_plot_delta[f'{new_dim}']

    else:
        raise ValueError(f"Delta dimension '{delta_dim}' not supported.")

    if not relative and dim != 'Cost':
        df_plot_delta['Delta'] *= 1e-3  # from GWh to TWh

    fig = px.box(
        df_plot_delta.sort_values(by='Key', ascending=False),
        x='Delta_rel' if relative else 'Delta',
        y='Key',
        color='Grouping',
        color_discrete_sequence=px.colors.qualitative.Safe,
        points='all',
        hover_data=['CCS limit', 'Carbon policy'] + ['Burden shifting policy' if delta_dim == 'Grouping' else 'Burden shifting policy_none'],
        labels={
            'Delta_rel': "Relative difference (%)",
            'Delta': f"Difference in the utilization of {dim.lower()} (TWh/yr)" if dim != 'Cost' else "Difference in cost (MCAD/yr)",
        },
        category_orders={'Grouping': ['all', 'ssp_rcp', 'iam', 'individual']}
    )

    if delta_dim == 'Burden shifting policy':
        fig.add_hline(y=0.5, line_dash="dot", line_color="black")
        fig.add_hline(y=3.5, line_dash="dot", line_color="black")
        fig.add_hline(y=7.5, line_dash="dot", line_color="black")
    else:
        fig.add_hline(y=2.5, line_dash="dot", line_color="black")
        fig.add_hline(y=6.5, line_dash="dot", line_color="black")

    if save_fig:
        fig.write_html(f'../03_Results/Figures/{results_folder}/{dim.lower().replace(' ', '_')}_{delta_dim.lower().replace(' ', '_')}_distrib_grouping.html')

    if return_fig:
        return fig