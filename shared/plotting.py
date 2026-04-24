from typing import Union

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

from energyscope.colors import Color, Colors
from energyscope.result import Result

default_colors = Colors({
    "GASOLINE": "#808080",
    "BIO_DIESEL": "#6B8E23",
    "DIESEL": "#D3D3D3",
    "URANIUM": "#66ff33",
    "NG": "#FFD700",
    "SNG": "#FFE100",
    "LFO": "#8B008B",
    "COAL": "#A0522D",
    "HYDRO": "#00CED1",
    "WASTE": "#FA8072",
    "SOLAR": "#FFFF00",
    "GEOTHERMAL": "#FF0000",
    "H2": "#FF00FF",
    "RES_WIND": "#FFA500",
    "HEAT_HT": "#DC143C",
    "ELECTRICITY": "#00BFFF",
    "EUD_ELECTRICITY": "#00BFFF",
    "EUD_LIGHTING": "#00BFFF",
    "ETHANOL": "#E1DA00",
    "AMMONIA": "#C3DA00",
    "METHANOL": "#A5DA00",
    "DME": "#87DA00",
    "CO2": '#545454',
    "WOOD": "#CD853F",
    "WET_BIOMASS": "#b37b44",
    "PLANT": "#d4904e",
    "HEAT": "#B51F1F",
    "EUD_HEAT": "#B51F1F",
    "MOB": "#FF69B4",

    # Categories
    "Electricity": "#00BFFF",  # Light Blue
    "Mobility": "#8B0000",  # Dark Red (Combined-Cycle Gas)
    "Electric Infrastructure": "#000000",  # Black (Oil)
    "Gas Infrastructure": "#B22222",  # Firebrick (Open-Cycle Gas)
    "Wind": "#0000FF",  # Blue (Onshore Wind)
    "WIND": "#0000FF",  # Blue (Onshore Wind)
    "PV": "#FFD700",  # Gold (Solar)
    "Geothermal": "#D3B9DA",  # Light Purple (Geothermal)
    "Hydro River & Dam": "#008080",  # Teal (Reservoir & Dam)
    "Industry": "#006400",  # Dark Green (Biomass)
    "Low Temperature Heat": "#FFA500",  # Orange (Nuclear)
    "Hydro Storage": "#00CED1",  # Dark Turquoise (Pumped Hydro Storage)
    "Storage": "#ADD8E6",  # Light Blue (Offshore Wind AC)
    "Electrolysis": "#66CDAA",  # Medium Aquamarine (Run of River)
    "Carbon Capture": "#A52A2A"  # Brown (Lignite)
})

def _create_sankey_figure(df_flow: pd.DataFrame, colors: Colors) -> go.Figure:
    """
    Creates a Sankey diagram from the processed flow data.

    This function generates a Sankey diagram using the provided flow data.
    It supports custom color mappings for different technologies and applies
    them to the links in the diagram. The resulting figure can be displayed
    or saved as an HTML file.

    Args:
        df_flow (pd.DataFrame):
            A DataFrame containing the processed flow data, with columns
            for 'source', 'target', and 'value' representing the flow
            between different nodes.

        colors (dict, optional):
            A dictionary of custom colors mapping technology names to
            hexadecimal color codes. If provided, these colors will override
            the default color mappings for the corresponding technologies.
            The dictionary format should be:
            {"TECH_NAME": "#HEXCOLOR", ...}

            Example:
                custom_colors = {
                    "GASOLINE": "#FF0000CC",
                    "BIO_DIESEL": "#00FF00CC",
                    "DIESEL": "#0000FFCC",
                    # Add more as needed
                }

    Returns:
        go.Figure:
            A Plotly Figure object representing the Sankey diagram. This
            can be displayed using `fig.show()` or saved to an HTML file
            using `fig.write_html()`.

    Example:
        # Assuming df_flow is your processed data and you want to apply custom colors:
        fig = _build_sankey(df_flow, custom_colors={"GASOLINE": "#FF0000CC"})
        fig.show()  # To display the diagram
        fig.write_html("output/sankey_diagram.html")  # To save the diagram
    """

    pd.set_option('future.no_silent_downcasting', True)

    df_flow['color'] = df_flow.apply(lambda row: str(colors[row['target']] | colors[row['source']]), axis=1)
    node = np.unique(np.concatenate((df_flow['source'].unique(), df_flow['target'].unique())))
    df_sankey = df_flow.replace(node, range(len(node)))

    opacity = 0.5

    fig = go.Figure(data=[go.Sankey(
        valueformat=".0f",
        valuesuffix="",
        node=dict(
            pad=15,
            thickness=15,
            line=dict(color="black", width=0.5),
            label=node,
            color="#DCDCDC"
        ),
        link=dict(
            source=df_sankey['source'],
            target=df_sankey['target'],
            value=df_sankey['value'],
            label=df_sankey['value'],
            color=df_sankey['color'].apply(lambda c: Color(c).rgba(opacity))
        )
    )])
    fig.update_layout(title_text="Sankey Diagram", font_size=10, template="plotly", font_color="black")

    return fig


def generate_sankey_flows(results: Result, aggregate_mobility, aggregate_grid, aggregate_technology,
                          run_id) -> pd.DataFrame:
    """
    Processes the `Result` object to transform and filter flow data for Sankey diagram visualization.

    This function takes in a `Result` object, which contains various data frames and parameters
    from an energy modeling process, and performs several transformations and aggregations.
    The goal is to prepare the flow data for use in a Sankey diagram.

    Args:
        results (Result):
            A `Result` object containing dictionaries of data frames for constraints,
            parameters, objectives, sets, and variables.

    Returns:
        pd.DataFrame:
            A processed DataFrame with 'source', 'target', and 'value' columns,
            ready for Sankey diagram visualization.
    """

    df_flow = results.postprocessing['df_monthly'].loc[results.postprocessing['df_monthly']['Run'] == run_id, :]

    df_flow = df_flow.groupby(['Technologies', 'Flow']).sum().rename(columns={'Monthly_flow': 'value'}).loc[:,
              ['value']].reset_index()

    # Swap target and source for positive values and take absolute value
    df_flow.rename(columns={'Technologies': 'target', 'Flow': 'source'}, inplace=True)
    df_flow.loc[df_flow['value'] > 0, ['target', 'source']] = df_flow.loc[
        df_flow['value'] > 0, ['source', 'target']].to_numpy()
    df_flow['value'] = abs(df_flow['value'])

    # Aggregate and clean data
    df_flow = df_flow.groupby(['target', 'source']).sum().reset_index()
    df_flow.loc[df_flow['target'] == df_flow['source'], 'source'] = 'IMP_' + df_flow.loc[
        df_flow['target'] == df_flow['source'], 'source'].astype(str)
    df_flow = df_flow[~df_flow['source'].str.startswith('IMP_RES')]

    # Drop CO2 flows except specified ones
    df_flow = df_flow[
        (~df_flow['source'].str.contains("CO2_"))
        | (df_flow['source'].isin(['CO2_TO_DIESEL', 'CO2_TO_JETFUELS', 'CO2_METHANOL']))
    ]
    df_flow = df_flow[
        (~df_flow['target'].str.contains("CO2_"))
        | (df_flow['target'].isin(['CO2_TO_DIESEL', 'CO2_TO_JETFUELS', 'CO2_METHANOL']))
    ]

    # Rename ship technos
    for ship_type in ['OIL_TANKER_', 'CONTAINER_', 'BULK_CARRIER_']:
        df_flow['source'] = df_flow['source'].apply(lambda x: x.replace(ship_type, 'SHIP_' + ship_type))
        df_flow['target'] = df_flow['target'].apply(lambda x: x.replace(ship_type, 'SHIP_' + ship_type))

    # Remove waste heat flow (waste heat is not modelled)
    df_flow = df_flow[~df_flow['source'].str.contains("LT_DEC_WH")]
    df_flow = df_flow[~df_flow['target'].str.contains("LT_DEC_WH")]

    # Remove biomass subcategories
    sub_biomass_list = [
        'BIOMASS_FORESTRY_UNEXPLOITED',
        'BIOMASS_FORESTRY_RESIDUAL',
        'BIOMASS_FORESTRY_LEFTOVER1',
        'BIOMASS_FORESTRY_LEFTOVER2',
        'BIOMASS_AGRICULTURE_RESIDUAL',
        'BIOMASS_WASTE_BUILDING',
        'BIOMASS_AGRICULTURE_DEJECTION',
        'BIOMASS_WASTE_PAPER_FABRIC',
        'BIOMASS_WASTE_MUNICIPAL',
        'BIOMASS_WASTE_ORGANIC',
        'BIOMASS_WASTE_PAPER'
    ]

    df_flow = df_flow[~df_flow['source'].isin(sub_biomass_list)]

    df_flow.sort_values('source', inplace=True)

    # Transform pkm & tkm into GWh
    techno_mob = df_flow.loc[df_flow['target'].str.startswith('MOB_'), :]['target'].unique().tolist()

    df_flow.loc[df_flow['target'].isin(techno_mob), 'value'] = (
        df_flow.loc[df_flow['target'].isin(df_flow.loc[df_flow['target'].isin(techno_mob), 'source']), :]
        .groupby('target')
        .sum()
        .reset_index()
        .sort_values('target')['value']
        .values
    )

    ## Add EUD
    # TODO Aggregate flow of the different type of elec
    EUD = results.parameters['end_uses_demand_year']
    EUD = EUD.loc[EUD['Run'] == run_id, :]
    EUD = EUD.loc[EUD['end_uses_demand_year'] > 0, :]
    EUD = EUD.reset_index().groupby('index0').sum().reset_index().loc[:, ['index0', 'end_uses_demand_year']]
    EUD = EUD.rename(columns={'index0': 'source', 'end_uses_demand_year': 'value'})
    EUD_elec = EUD.loc[(EUD['source'].str.contains('ELECTRICITY'))
                  | (EUD['source'].str.contains('LIGHTING'))
                  | (EUD['source'].str.contains('HEAT_LOW_T_SC')), :].copy()
    EUD_elec['target'] = 'EUD_' + EUD_elec['source']

    EUD_heat = EUD.loc[(EUD['source'].str.contains('HEAT_HIGH_T'))
                       | (EUD['source'].str.contains('HEAT_LOW_T_HW'))
                       | (EUD['source'].str.contains('HEAT_LOW_T_SH')), :].copy()
    EUD_heat['target'] = 'EUD_' + EUD_heat['source']

    df_flow = pd.concat([df_flow, EUD_elec, EUD_heat]).reset_index().drop(columns='index')

    ## Add EUD to sectors
    EUD = results.parameters['end_uses_demand_year']
    EUD = EUD.loc[EUD['Run'] == run_id, :]
    EUD = EUD.loc[EUD['end_uses_demand_year'] > 0, :]
    EUD = EUD.reset_index().loc[:, ['index0', 'index1', 'end_uses_demand_year']]
    EUD = EUD.rename(columns={'index0': 'source', 'index1': 'target', 'end_uses_demand_year': 'value'})
    EUD_elec_sector = EUD.loc[
                      ((EUD['source'].str.contains('ELECTRICITY')) & (~EUD['source'].str.contains('EXPORT')))
                      | (EUD['source'].str.contains('LIGHTING'))
                      | (EUD['source'].str.contains('HEAT_LOW_T_SC')), :].copy()
    EUD_elec_sector['source'] = 'EUD_' + EUD_elec_sector['source']

    EUD_heat_sector = EUD.loc[
                      (EUD['source'].str.contains('HEAT_HIGH_T'))
                      | (EUD['source'].str.contains('HEAT_LOW_T_HW'))
                      | (EUD['source'].str.contains('HEAT_LOW_T_SH')), :].copy()
    EUD_heat_sector['source'] = 'EUD_' + EUD_heat_sector['source']

    df_flow = pd.concat([df_flow, EUD_elec_sector, EUD_heat_sector]).reset_index().drop(columns='index')

    ## Aggregate EUD types
    EUD_types = results.sets['END_USES_TYPES_OF_CATEGORY']
    EUD_types_reverse = {item: key for key, values in EUD_types.items() for item in values}

    # Create a mask for rows where 'target' and 'source' need changes
    mask_target = df_flow['target'].isin(EUD_types_reverse.keys())
    mask_source = df_flow['source'].isin(EUD_types_reverse.keys())

    # Apply mapping to 'target' and 'source' columns
    df_flow.loc[mask_target, 'target'] = df_flow.loc[mask_target, 'target'].map(EUD_types_reverse)
    df_flow.loc[mask_source, 'source'] = df_flow.loc[mask_source, 'source'].map(EUD_types_reverse)

    # Ensure consistency: if 'target' changes, update corresponding 'source' if necessary
    for index, row in df_flow.iterrows():
        if row['target'] in EUD_types_reverse.values() and row['source'] in EUD_types_reverse.keys():
            df_flow.at[index, 'source'] = EUD_types_reverse[row['source']]

    if aggregate_mobility:
        ## Aggregation of mobility flows
        # Extract rows concerning mobility
        mob_flow = df_flow.loc[df_flow['target'].str.startswith('MOBILITY_'), :]
        mob_flow_2 = df_flow.loc[df_flow['target'].isin(
            df_flow.loc[df_flow['target'].str.startswith('MOBILITY_'), :]['source'].unique()), :]
        # Drop rows concerning mobility as they will be merged
        df_flow = df_flow.loc[~df_flow['target'].str.startswith('MOBILITY_') * ~df_flow['target'].isin(
            df_flow.loc[df_flow['target'].str.startswith('MOBILITY_'), :]['source'].unique()), :]
        # Aggregate value on type of technologies (source) and on type of mobility (target)
        mob_flow = mob_flow.groupby([mob_flow['source'].str.split('_', expand=True).loc[:, 0],
                                     mob_flow['target'].str.rsplit('_', n=1, expand=True).loc[:, 0]]).sum()
        mob_flow_2 = mob_flow_2.groupby(
            [mob_flow_2['target'].str.split('_', expand=True).loc[:, 0], mob_flow_2['source'].values]).sum()
        # Clean df
        mob_flow = mob_flow.drop(['source', 'target'], axis=1)
        mob_flow_2 = mob_flow_2.drop(['source', 'target'], axis=1)
        # Reset index
        mob_flow.reset_index(names=['source', 'target'], inplace=True)
        mob_flow_2.reset_index(names=['target', 'source'], inplace=True)
        # Concat dfs
        df_flow = pd.concat([df_flow, mob_flow, mob_flow_2]).reset_index().drop(columns='index')

    if aggregate_grid:
        ## Add EUD
        # TODO Aggregate flow of the different type of elec
        EUD = results.parameters['end_uses_demand_year']
        EUD = EUD.loc[EUD['end_uses_demand_year'] > 0, :]
        EUD = EUD.reset_index().groupby('index0').sum().reset_index().loc[:, ['index0', 'end_uses_demand_year']]
        EUD = EUD.rename(columns={'index0': 'source', 'end_uses_demand_year': 'value'})
        EUD = EUD.loc[EUD['source'].str.contains('ELECTRICITY'), :]
        EUD['source'] = "ELECTRICITY"
        EUD['target'] = 'EUD_' + EUD['source']

        ## Aggregation of grids flows
        techno_grids = (
        'EXP', 'TRAFO', 'COMP')  # TODO might be replaced by a sets: INFRASTRUCTURE_GAS_GRID INFRASTRUCTURE_ELEC_GRID
        # Extract all flows that have an input/output of ELECTRICITY
        df_elec = df_flow.loc[
                  df_flow['target'].str.contains('ELECTRICITY_') + df_flow['source'].str.contains('ELECTRICITY_'), :]
        # Exception for exports, space cooling and lighting
        df_elec = df_elec.loc[~df_elec['target'].str.contains('EXPORT')]
        df_flow.loc[df_flow['target'].str.contains('EXPORT'), 'source'] = "ELECTRICITY"
        df_elec = df_elec.loc[~df_elec['target'].str.contains('LIGHTING')]
        df_flow.loc[df_flow['target'].str.contains('LIGHTING'), 'source'] = "ELECTRICITY"
        df_elec = df_elec.loc[~df_elec['target'].str.contains('HEAT_LOW_T_SC')]
        df_flow.loc[df_flow['target'].str.contains('HEAT_LOW_T_SC'), 'source'] = "ELECTRICITY"
        # Low T heat
        df_flow.loc[df_flow['target'].str.contains('HEAT_LOW_T_HW'), 'source'] = "HEAT_LOW_T"
        df_flow.loc[df_flow['target'].str.contains('HEAT_LOW_T_SH'), 'source'] = "HEAT_LOW_T"
        # Drop them from the main df
        df_flow = df_flow.drop(df_elec.index)
        # Remove the flows related to the grid infrastructure
        df_elec = df_elec.loc[~df_elec['target'].str.contains('|'.join(techno_grids)) * ~df_elec['source'].str.contains(
            '|'.join(techno_grids)), :]
        # Rename ELECTRICITY_XXX layers
        df_elec = df_elec.replace(results.sets['ELECTRICITY_LAYERS'].loc[:, 'ELECTRICITY_LAYERS'].values, 'ELECTRICITY')

        # Aggregation for NG
        df_ng = df_flow.loc[df_flow['target'].str.contains('NG_') + df_flow['source'].str.contains('NG_'), :]
        df_flow = df_flow.drop(df_ng.index)
        df_ng = df_ng.loc[~df_ng['target'].str.contains('|'.join(techno_grids)) * ~df_ng['source'].str.contains(
            '|'.join(techno_grids)), :]
        df_ng = df_ng.replace(results.sets['NG_LAYERS'].loc[:, 'NG_LAYERS'].values, 'NG')

        # Aggregation for H2
        df_h2 = df_flow.loc[df_flow['target'].str.contains('H2_') + df_flow['source'].str.contains('H2_'), :]
        df_flow = df_flow.drop(df_h2.index)
        df_h2 = df_h2.loc[~df_h2['target'].str.contains('|'.join(techno_grids)) * ~df_h2['source'].str.contains(
            '|'.join(techno_grids)), :]
        df_h2 = df_h2.replace(results.sets['H2_LAYERS'].loc[:, 'H2_LAYERS'].values, 'H2')

        df_flow = pd.concat([df_flow, df_elec, df_ng, df_h2]).reset_index().drop(columns='index')

    if aggregate_technology:
        # List of technology types to aggregate
        techno_list = ['COGEN', 'BOILER', 'HP', 'DIRECT_ELEC', 'PV', 'RENOVATION']

        # Define a regex pattern with non-capturing groups to match flows like NG_EHP, H2_EHP, IMP_H2_EHP, NG_HP, H2_HP, etc.
        exclude_pattern = r'(?:NG|H2|IMP_H2)_(?:EHP|HP)'

        # Create masks to identify rows with matching patterns in target and source
        exclude_mask_target = df_flow['target'].str.contains(exclude_pattern, regex=True)
        exclude_mask_source = df_flow['source'].str.contains(exclude_pattern, regex=True)

        # Iterate over technologies for aggregation, ensuring exclusions
        for tech in techno_list:
            # Replace only where the rows do not match the exclude pattern
            df_flow.loc[
                (df_flow['target'].str.contains(tech)) & ~exclude_mask_target, 'target'
            ] = tech

            df_flow.loc[
                (df_flow['source'].str.contains(tech)) & ~exclude_mask_source, 'source'
            ] = tech

    return df_flow


def plot_sankey(result: Result, aggregate_mobility: bool = True, aggregate_grid: bool = True,
                aggregate_technology: bool = True, run_id: int = 0, colors: Union[Colors, dict] = None) -> go.Figure:
    df_flow = generate_sankey_flows(result, aggregate_mobility=aggregate_mobility, aggregate_grid=aggregate_grid,
                                    aggregate_technology=aggregate_technology, run_id=run_id)
    return _create_sankey_figure(df_flow, Colors.cast(colors or default_colors))


def plot_distribution(result: list[Result]) -> None:
    return None


def plot_parametrisation(results, variable: str, category: str, labels: dict = None) -> go.Figure:
    """
    Plots the parametrization results by visualizing the specified variable over multiple runs, grouped by a given category.

    Parameters:
    -----------
    results : Result
        A Result object containing the processed output data.

    variable : str
        The name of the variable to be plotted. This should correspond to a column in the 'df_annual' DataFrame
        stored within the `results` object.

    category : str
        The grouping category for the plot. This should be a column in the 'df_annual' DataFrame, which will be
        used to group and color the results (e.g., 'Sector', 'Category').

    labels : dict, optional
        A dictionary of custom labels to use in the plot for axis titles and hover information. This can be used to
        provide more descriptive or human-readable labels for the plot. Default is an empty dictionary.

        Example:
        ```
        labels = {
            "Run": "Simulation Run",
            "variable": "Variable Name",
            "category": "Technology Sector"
        }
        ```

    Returns:
    --------
    go.Figure
        A Plotly Figure object. This can be displayed using `fig.show()` or saved to an HTML file
        using `fig.write_html()`.

    Example:
    --------
    To plot the annual investment costs for different sectors over multiple runs:

    ```
    plot_parametrisation(results, variable='C_inv_an', category='Sector', labels={'Run': 'Run Number', 'C_inv_an': 'Annual Investment Costs'})
    ```
    """
    labels = labels or {}
    df = results.postprocessing['df_annual']
    df_plot = df.groupby(['Run', category]).sum()
    df_plot['color'] = df_plot.index.get_level_values(1).map(lambda x: str(default_colors[x]))

    fig = px.area(df_plot.reset_index(), x="Run", y=variable, color=category, template="simple_white", labels=labels)
    return fig


def plot_comparison(results, variable, category, labels=None, run1=None, run2=None) -> go.Figure:
    """
    Plots the parametrization results by visualizing the specified variable for two selected runs using a mirror bar plot.

    Parameters:
    -----------
    results : Result
        A Result object containing the processed output data.

    variable : str
        The name of the variable to be plotted. This should correspond to a column in the 'df_annual' DataFrame
        stored within the `results` object.

    category : str
        The grouping category for the plot. This should be a column in the 'df_annual' DataFrame, which will be
        used to group and color the results (e.g., 'Sector', 'Category').

    labels : dict, optional
        A dictionary of custom labels to use in the plot for axis titles and hover information. Default is an empty dictionary.

    run1 : int, optional
        The first run to compare in the mirror bar plot.

    run2 : int, optional
        The second run to compare in the mirror bar plot.

    Returns:
    --------
    go.Figure
        A Plotly Figure object. This can be displayed using `fig.show()` or saved to an HTML file
        using `fig.write_html()`.
    """
    # Define category color mapping (only for specific categories)
    category_colors = {
        "Electricity": "#808080",  # Gray (Coal)
        "Mobility": "#8B0000",  # Dark Red (Combined-Cycle Gas)
        "Electric Infrastructure": "#000000",  # Black (Oil)
        "Gas Infrastructure": "#B22222",  # Firebrick (Open-Cycle Gas)
        "Wind": "#0000FF",  # Blue (Onshore Wind)
        "PV": "#FFD700",  # Gold (Solar)
        "Geothermal": "#D3B9DA",  # Light Purple (Geothermal)
        "Hydro River & Dam": "#008080",  # Teal (Reservoir & Dam)
        "Industry": "#006400",  # Dark Green (Biomass)
        "Industrial Heat": "#006400",  # Dark Green (Biomass)
        "Domestic Heat": "#FFA500",  # Orange (Nuclear)
        "Hydro Storage": "#00CED1",  # Dark Turquoise (Pumped Hydro Storage)
        "Storage": "#ADD8E6",  # Light Blue (Offshore Wind AC)
        "Electrolysis": "#66CDAA",  # Medium Aquamarine (Run of River)
        "Carbon Capture": "#A52A2A"  # Brown (Lignite)
    }

    # Extract the 'df_annual' DataFrame from the results object
    df = results.postprocessing['df_annual'].reset_index()  # Bring the multi-index levels as columns

    # Filter the DataFrame based on the selected runs
    df_run1 = df[df['Run'] == run1]
    df_run2 = df[df['Run'] == run2]

    # Group by category and sum for each run
    df_run1_grouped = df_run1.groupby(category).sum()[variable]
    df_run2_grouped = df_run2.groupby(category).sum()[variable]

    # Ensure that both DataFrames have the same categories for comparison
    categories = df_run1_grouped.index.union(df_run2_grouped.index)

    # Align the two DataFrames to have the same categories
    df_run1_grouped = df_run1_grouped.reindex(categories, fill_value=0)
    df_run2_grouped = df_run2_grouped.reindex(categories, fill_value=0)
    max_value = max(df_run1_grouped.max(), df_run2_grouped.max())

    # Apply natural breaks (e.g., multiples of 5, 10, 50, 100)
    scale_factor = 10 ** (len(str(int(max_value))) - 1)
    natural_break = np.ceil(max_value / scale_factor) * scale_factor
    tick_step = natural_break / 5  # 5 intervals
    tickvals = np.arange(-natural_break, natural_break + tick_step, tick_step)
    ticktext = [abs(int(i)) for i in tickvals]

    # Calculate the common and additional values between the two runs
    common_values = np.minimum(df_run1_grouped, df_run2_grouped)
    additional_run1 = df_run1_grouped - common_values
    additional_run2 = df_run2_grouped - common_values

    # Fallback to Plotly's default color palette if the theme has no colors
    default_colors = [
        "#636EFA", "#EF553B", "#00CC96", "#AB63FA", "#FFA15A",
        "#19D3F3", "#FF6692", "#B6E880", "#FF97FF", "#FECB52"
    ]

    # Use theme colors or fallback to the default Plotly color palette
    theme_colors = go.layout.Template().layout.colorway or default_colors

    # Fallback to theme colors for categories without predefined colors
    colors = [category_colors.get(cat, theme_colors[i % len(theme_colors)]) for i, cat in enumerate(categories)]

    # Calculate yshift dynamically based on the number of categories
    yshift_delta = int(max(10, 50 / len(categories)))  # Adjusts dynamically; minimum shift is 10

    # Create the mirror bar plot
    fig = go.Figure()

    # Add common values (with transparency) for run1 (negative side)
    fig.add_trace(go.Bar(
        y=categories,
        x=-common_values,  # Plot common values for run1 (negative side)
        orientation='h',
        showlegend=False,
        opacity=0.5,  # Add transparency
        marker=dict(color=colors)  # Apply category colors or theme fallback
    ))

    # Add additional values (without transparency) for run1 (negative side)
    fig.add_trace(go.Bar(
        y=categories,
        x=-additional_run1,  # Plot additional values for run1 (negative side)
        orientation='h',
        showlegend=False,
        marker=dict(color=colors)  # Apply category colors or theme fallback
    ))

    # Add common values (with transparency) for run2 (positive side)
    fig.add_trace(go.Bar(
        y=categories,
        x=common_values,  # Plot common values for run2 (positive side)
        orientation='h',
        showlegend=False,
        opacity=0.5,  # Add transparency
        marker=dict(color=colors)  # Apply category colors or theme fallback
    ))

    # Add additional values (without transparency) for run2 (positive side)
    fig.add_trace(go.Bar(
        y=categories,
        x=additional_run2,  # Plot additional values for run2 (positive side)
        orientation='h',
        showlegend=False,
        marker=dict(color=colors)  # Apply category colors or theme fallback
    ))

    # Add annotations for the total values at each extremity (outside the bar)
    for i, category in enumerate(categories):
        # Run1 (negative side): Total value (common + additional)
        if df_run1_grouped[category] != 0:
            fig.add_annotation(
                x=-df_run1_grouped[category],  # Position at the end of the bar
                y=category,  # Corresponding category
                text=f'{df_run1_grouped[category]:.0f}',  # Rounded to whole numbers
                showarrow=False,
                xanchor="right",  # Align text outside the negative bar (left side)
                font=dict(size=12),
                xshift=-5  # Shift text outside the bar
            )

        # Run2 (positive side): Total value (common + additional)
        if df_run2_grouped[category] != 0:
            fig.add_annotation(
                x=df_run2_grouped[category],  # Position at the end of the bar
                y=category,  # Corresponding category
                text=f'{df_run2_grouped[category]:.0f}',  # Rounded to whole numbers
                showarrow=False,
                xanchor="left",  # Align text outside the positive bar (right side)
                font=dict(size=12),
                xshift=5  # Shift text outside the bar
            )

        # Plot the difference above the difference bar (outside, higher than the bar)
        if additional_run1[category] > 0:  # For run1 (negative side)
            mid_point_run1 = -common_values[category] - (
                        additional_run1[category] / 2)  # Midpoint of the additional bar
            fig.add_annotation(
                x=mid_point_run1,  # Middle of the additional part for run1
                y=category,  # Corresponding category
                text=f'{abs(additional_run1[category]):.0f}',  # Difference (absolute value) rounded
                showarrow=False,
                bgcolor='rgba(255, 255, 255, 0.6)',  # Semi-transparent white background (RGBA format)
                # yshift=yshift_delta,  # Move the text higher above the bar
                font=dict(size=8)  # Smaller font for delta
            )

        if additional_run2[category] > 0:  # For run2 (positive side)
            mid_point_run2 = common_values[category] + (additional_run2[category] / 2)  # Midpoint of the additional bar
            fig.add_annotation(
                x=mid_point_run2,  # Middle of the additional part for run2
                y=category,  # Corresponding category
                text=f'{abs(additional_run2[category]):.0f}',  # Difference (absolute value) rounded
                showarrow=False,
                bgcolor='rgba(255, 255, 255, 0.6)',  # Semi-transparent white background (RGBA format)
                # yshift=yshift_delta,  # Move the text higher above the bar
                font=dict(size=8)  # Smaller font for delta
            )

    # Update layout
    fig.update_layout(
        template="plotly_white",
        title=f"Comparison {labels.get(variable, variable)} between Run {run1} and Run {run2}",
        xaxis=dict(
            title=labels.get(variable, variable) if labels else variable,
            range=[-natural_break, natural_break],  # Symmetrical x-axis limits
            tickvals=tickvals,  # Natural breaks (multiples of 5, 10, 50, 100)
            ticktext=ticktext,  # Symmetric labels
            zeroline=True  # Add zero line for mirror effect
        ),
        yaxis=dict(
            title=None,  # Remove y-axis title
            automargin=True,  # Automatically adjust margins for long labels
            ticklabelposition="outside",  # Ensure labels are placed outside the plot
            ticks="outside",  # Draw ticks outside the plot
            ticklen=20,  # Increase the tick length to add space between labels and plot
            tickcolor='rgba(0,0,0,0)'  # Make the tick marks fully transparent
        ),
        bargap=1 - 1 / 1.618,  # Make bars narrower
        barmode='relative'  # Use 'relative' to ensure stacking works for both positive and negative values
    )

    return fig
