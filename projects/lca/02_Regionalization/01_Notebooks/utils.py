import pandas as pd
import ast
import energyscope
from energyscope.models import Model
from energyscope.colors import Colors, Color
from energyscope.energyscope import Energyscope
from energyscope.result import postprocessing
from mescal import *
import plotly.io as pio
import plotly.express as px
import plotly.graph_objects as go
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.patches import Patch
from matplotlib.lines import Line2D
import bw2data as bd
import matplotlib
from shared.utils import load_snapshot, collapse_temporal_index
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent  # EnergyScope-Québec / projects / lca / 02_Regionalization
DATA_DIR = PROJECT_ROOT / '01_Notebooks' / 'Data'
AMPL_FILES_DIR = PROJECT_ROOT / '02_AMPL_files'
LCA_DATA_FILES_DIR = PROJECT_ROOT / '03_Results' / 'LCA'
REF_RESULTS = PROJECT_ROOT / '03_Results' / 'Tables' / 'reference'

matplotlib.rcParams.update({
    "figure.facecolor": "white",
    "axes.facecolor": "white",
    "savefig.facecolor": "white"
})
plt.style.use('default')

plt.rcParams['hatch.linewidth'] = 0.6

pio.templates["custom"] = pio.templates["plotly_white"]
pio.templates["custom"].layout.font.family = "Arial"
pio.templates["custom"].layout.font.color = "black"
pio.templates["custom"].layout.xaxis.color = "black"
pio.templates["custom"].layout.xaxis.showline = True
pio.templates["custom"].layout.xaxis.linecolor = "black"
pio.templates["custom"].layout.xaxis.ticks = "outside"
pio.templates["custom"].layout.xaxis.tickcolor = "black"
pio.templates["custom"].layout.yaxis.color = "black"
pio.templates["custom"].layout.yaxis.showline = True
pio.templates["custom"].layout.yaxis.linecolor = "black"
pio.templates["custom"].layout.yaxis.ticks = "outside"
pio.templates["custom"].layout.yaxis.tickcolor = "black"
pio.templates["custom"].layout.xaxis.mirror = True
pio.templates["custom"].layout.yaxis.mirror = True
pio.templates.default = "custom"

N_capita_2021 = 8.57e6
N_capita_2023 = 8.85e6
N_capita_2050 = 9.9e6  # scenario reference 2024

run_order_2020 = [
    'Def.',
    'Spat.',
    'Spat.+Fore.',
    'Spat.+Back.',
    'Spat.+Fore.+Back.',
]

run_order_2050 = [
    'Def.\n\nSSP5-H',
    'IAM\n\nSSP5-H',
    'IAM\nSpat.\n\nSSP5-H',
    'IAM\nSpat.\nFore.\n\nSSP5-H',
    'IAM\nSpat.\nBack.\n\nSSP5-H',
    'IAM\nSpat.\nFore.\nBack.\n\nSSP5-H',

    'IAM\n\nSSP2-L',
    'IAM\nSpat.\n\nSSP2-L',
    'IAM\nSpat.\nFore.\n\nSSP2-L',
    'IAM\nSpat.\nBack.\n\nSSP2-L',
    'IAM\nSpat.\nFore.\nBack.\n\nSSP2-L',
]

run_order_burden_shifts = ['None', 'aCC', 'rEQ', 'rHH', 'aCC rEQ', 'aCC rHH', 'rHH rEQ', 'All']

impact_category_colors = {
    # Human health
    'Climate change, human health, long term': '#0072B2',  # Dark blue
    'Climate change, human health, short term': '#56B4E9',  # Light blue
    'Human toxicity cancer, long term': '#D55E00',  # Burnt orange
    'Human toxicity cancer, short term': '#E69F00',  # Orange
    'Human toxicity non-cancer, long term': '#CC79A7',  # Magenta
    'Human toxicity non-cancer, short term': '#F7CAE0',  # Light pink
    'Ionizing radiations, human health': '#999933',  # Olive green
    'Ozone layer depletion': '#00CED1',  # Dark turquoise
    'Particulate matter formation': '#7F7F7F',  # Medium grey
    'Photochemical ozone formation, human health': '#9E5BBA',  # Soft violet
    'Water availability, human health': '#009E73',  # Teal green

    'Climate change, human health, long term, CO2 uptake': '#0072B2',
    'Climate change, human health, long term, biogenic': '#0072B2',
    'Climate change, human health, long term, fossil': '#0072B2',
    'Climate change, human health, long term, land transformation': '#0072B2',
    'Climate change, human health, short term, CO2 uptake': '#56B4E9',
    'Climate change, human health, short term, biogenic': '#56B4E9',
    'Climate change, human health, short term, fossil': '#56B4E9',
    'Climate change, human health, short term, land transformation': '#56B4E9',

    # Ecosystem quality
    'Climate change, ecosystem quality, long term': '#0072B2',  # Dark blue
    'Climate change, ecosystem quality, short term': '#56B4E9',  # Light blue
    'Fisheries impact': '#1B9E77',  # Sea green
    'Freshwater acidification': '#8DA0CB',  # Periwinkle
    'Freshwater ecotoxicity, long term': '#984EA3',  # Dark purple
    'Freshwater ecotoxicity, short term': '#DDA0DD',  # Plum
    'Freshwater eutrophication': '#A6CEE3',  # Light cyan
    'Ionizing radiations, ecosystem quality': '#999933',  # Olive green
    'Land occupation, biodiversity': '#A65628',  # Rust brown
    'Land transformation, biodiversity': '#E6AB02',  # Mustard yellow
    'Marine acidification, long term': '#00CED1',  # Dark turquoise
    'Marine acidification, short term': '#ADD8E6',  # Light blue
    'Marine ecotoxicity, long term': '#984EA3',  # Dark purple
    'Marine ecotoxicity, short term': '#DDA0DD',  # Plum
    'Marine eutrophication': '#1B9E77',  # Sea green
    'Photochemical ozone formation, ecosystem quality': '#9E5BBA',  # Soft violet
    'Terrestrial acidification': '#FDB462',  # Light orange
    'Terrestrial ecotoxicity, long term': '#BC80BD',  # Lavender
    'Terrestrial ecotoxicity, short term': '#F7CAE0',  # Light pink
    'Thermally polluted water': '#E377C2',  # Pink
    'Water availability, freshwater ecosystem': '#009E73',  # Teal green
    'Water availability, terrestrial ecosystem': '#66C2A5',  # Light teal

    'Climate change, ecosystem quality, long term, CO2 uptake': '#0072B2',
    'Climate change, ecosystem quality, long term, biogenic': '#0072B2',
    'Climate change, ecosystem quality, long term, fossil': '#0072B2',
    'Climate change, ecosystem quality, long term, land transformation': '#0072B2',
    'Climate change, ecosystem quality, short term, CO2 uptake': '#56B4E9',
    'Climate change, ecosystem quality, short term, biogenic': '#56B4E9',
    'Climate change, ecosystem quality, short term, fossil': '#56B4E9',
    'Climate change, ecosystem quality, short term, land transformation': '#56B4E9',

    # Other
    'Other': '#D3D3D3',  # Light grey
}

sector_colors = {
    'Other': '#BDBDBD',  # Light grey
    'Passenger mobility': '#ADD8E6',  # Light blue
    'Freight mobility': '#2166AC',  # Strong blue
    'Domestic heat': '#E66101',  # Burnt orange
    'Industrial heat': '#FDB863',  # Light orange
    'Electricity': '#F0E442',  # Bright yellow
    'Imports': '#BC80BD',  # Lavender
    'Energy resources': '#BC80BD',  # Lavender
    'Energy resources (excl. electricity)': '#BC80BD',  # Lavender
    'Carbon capture': '#7F7F7F',  # Medium grey
    'Biomass': '#4DAF4A',  # Green
    'Grid infrastructure': '#35978F',  # Teal
    'Energy storage': '#762A83',  # Deep purple
    'Carbon storage': '#4D5B66',  # Slate grey-blue
    'Alternative fuels': '#C51B7D',  # Magenta
}

es_tech_df = pd.read_csv(DATA_DIR / 'technology_dictionary.csv')
techs_color_map = dict(zip(es_tech_df['Long name'], es_tech_df['Color'].astype(str)))
techs_color_map["Other"] = "#A8A29E"
techs_color_map["Wood"] = "#166534"
techs_color_map["Wet biomass"] = "#92400E"
techs_color_map["Waste"] = "#B45309"

phase_colors = {
    "Infrastructure": "#377eb8",
    "Operation (direct)": "#ff7f00",
    "Operation (indirect)": "#ff7f00",
    "Operation (carbon capture)": "#ff7f00",
    "Resource": "#4daf4a",
    "Resource (biomass)": "#4daf4a",
    "Resource (wo biomass)": "#4daf4a",
    "Resource (rest)": "#4daf4a",
    "Resource (CO2 uptake)": "#4daf4a",
}

region_colors = {
    "CA-QC": "#003DA5",  # Quebec Blue
    "CA": "#FF0000",     # Canada Red
    "US": "#3C3B6E",     # US Navy Blue
    "RoW": "#006400",    # Dark Green
    "Other": "#888888",  # Gray
    'Not spatialized': '#D3D3D3',  # Light grey
}

default_colors_sankey = Colors({
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

obj_name_dict = {
    'TotalLCIA_m_CCS_all': 'Climate change, short term',
    'TotalLCIA_TTHH_bio': 'Total human health',
    'TotalLCIA_TTEQ_bio': 'Total ecosystem quality',
}

reg_level_name_dict = {
    'base': 'Def.',
    'spat': 'Spat.',
    'spat_fore': 'Spat.+Fore.',
    'spat_back': 'Spat.+Back.',
    'spat_fore_back': 'Spat.+Fore.+Back.',
}

reg_level_name_dict_2050 = {
    'base_wo_iam-SSP5-H': 'Def.++SSP5-H',
    'base-SSP5-H': 'IAM++SSP5-H',
    'spat-SSP5-H': 'IAM+Spat.++SSP5-H',
    'spat_fore-SSP5-H': 'IAM+Spat.+Fore.++SSP5-H',
    'spat_back-SSP5-H': 'IAM+Spat.+Back.++SSP5-H',
    'spat_fore_back-SSP5-H': 'IAM+Spat.+Fore.+Back.++SSP5-H',

    'base-SSP2-L': 'IAM++SSP2-L',
    'spat-SSP2-L': 'IAM+Spat.++SSP2-L',
    'spat_fore-SSP2-L': 'IAM+Spat.+Fore.++SSP2-L',
    'spat_back-SSP2-L': 'IAM+Spat.+Back.++SSP2-L',
    'spat_fore_back-SSP2-L': 'IAM+Spat.+Fore.+Back.++SSP2-L',

    'base_wo_iam': 'Def.',
    'base': 'IAM',
    'spat': 'IAM+Spat.',
    'spat_fore': 'IAM+Spat.+Fore.',
    'spat_back': 'IAM+Spat.+Back.',
    'spat_fore_back': 'IAM+Spat.+Fore.+Back.',
}

unit_dict_plotly = {
    'Total human health': 'DALY/(cap.yr)',
    'Remaining human health': 'DALY/(cap.yr)',
    'Climate change, short term': 't CO<sub>2</sub>-eq/(cap.yr)',
    'Climate change, short term (abroad)': 't CO<sub>2</sub>-eq/(cap.yr)',
    'Climate change, short term (territorial)': 't CO<sub>2</sub>-eq/(cap.yr)',
    'Total ecosystem quality': 'PDF.m<sup>2</sup>.yr/(cap.yr)',
    'Remaining ecosystem quality': 'PDF.m<sup>2</sup>.yr/(cap.yr)',
    'Total human health (direct emissions)': 'DALY/(cap.yr)',
    'Climate change, short term (direct emissions)': 't CO<sub>2</sub>-eq/(cap.yr)',
    'Total ecosystem quality (direct emissions)': 'PDF.m<sup>2</sup>.yr/(cap.yr)',
}

unit_dict_plt = {
    'Total human health': 'DALY/(cap.yr)',
    'Remaining human health': 'DALY/(cap.yr)',
    'Climate change, short term': 't CO$_2$-eq/(cap.yr)',
    'Climate change, short term (abroad)': 't CO$_2$-eq/(cap.yr)',
    'Climate change, short term (territorial)': 't CO$_2$-eq/(cap.yr)',
    'Total ecosystem quality': 'PDF.m$^2$.yr/(cap.yr)',
    'Remaining ecosystem quality': 'PDF.m$^2$.yr/(cap.yr)',
    'Total human health (direct emissions)': 'DALY/(cap.yr)',
    'Climate change, short term (direct emissions)': 't CO$_2$-eq/(cap.yr)',
    'Total ecosystem quality (direct emissions)': 'PDF.m$^2$.yr/(cap.yr)',
}

wood_list = [
    'BIOMASS_FORESTRY_UNEXPLOITED',
    'BIOMASS_FORESTRY_RESIDUAL',
    'BIOMASS_FORESTRY_LEFTOVER1',
    'BIOMASS_FORESTRY_LEFTOVER2',
    'BIOMASS_AGRICULTURE_RESIDUAL',
    'BIOMASS_WASTE_BUILDING',

    'Unharvested wood',
    'Residual forest biomass',
    'By-products from primary processing',
    'By-products from secondary processing',
    'Crop production and residues',
    'Construction, renovation, and demolition wood waste',
]

wet_biomass_list = [
    'BIOMASS_AGRICULTURE_DEJECTION',
    'BIOMASS_WASTE_PAPER_FABRIC',
    'BIOMASS_WASTE_MUNICIPAL',

    'Animal manure',
    'Pulp and paper mill residues',
    'Municipal sludge',

]

waste_list = [
    'BIOMASS_WASTE_ORGANIC',
    'BIOMASS_WASTE_PAPER',

    'Food waste, green waste, and other organic matter',
    'Paper and cardboard',

]

carbon_carrier_dict = {
    'GASOLINE': 'Gasoline',
    'DIESEL': 'Diesel',
    'BIO_DIESEL': 'Bio diesel',
    'NG_EHP': 'Natural gas',
    'NG_HP': 'Natural gas',
    'NG_MP': 'Natural gas',
    'NG_LP': 'Natural gas',
    'SNG_EHP': 'Synthetic natural gas',
    'SNG_HP': 'Synthetic natural gas',
    'SNG_MP': 'Synthetic natural gas',
    'SNG_LP': 'Synthetic natural gas',
    'COAL': 'Coal',
    'LFO': 'Lfo',
    'BIO_LFO': 'Bio lfo',
    'JETFUEL': 'Jetfuel',
    'BIO_JETFUEL': 'Bio jetfuel',
    'PROPANE': 'Propane',
    'HFO': 'Hfo',
    'BIO_HFO': 'Bio hfo',
    'METHANOL': 'Methanol',
    'BIO_METHANOL': 'Bio methanol',
    'ETHANOL': 'Ethanol',
    'BIO_ETHANOL': 'Bio ethanol',
}

def category_to_sector(row) -> str:
    category = row['Category']
    name = row['index']
    if 'Main production' in row:
        main_prod = row['Main production']
    else:
        main_prod = ''
    if isinstance(category, str):
        if category.startswith('ELECTRICITY_'):
            return 'Electricity'
        elif category.startswith('HEAT_LOW_T_'):
            return 'Domestic heat'
        elif category.startswith('HEAT_HIGH_T'):
            return 'Industrial heat'
        elif category.startswith('MOB_FREIGHT_'):
            return 'Freight mobility'
        elif category.startswith('MOB_PUBLIC_') | category.startswith('MOB_PRIVATE_'):
            return 'Passenger mobility'
        elif name in ['CARBON_MINERALIZATION', 'CARBON_TRANSPORT_INJECTION', 'STO_CO2', 'CO2_STO']:
            return 'Carbon storage'
        elif name.startswith('CARBON_CAPTURE') or name in ['DAC_HT', 'DAC_LT']:
            return 'Carbon capture'
        elif name.endswith('_STO') or name.startswith('STO_') or name in ['HYDRO_STORAGE', 'BATTERY', 'DHN_TH_STORAGE', 'DEC_TH_STORAGE']:
            return 'Energy storage'
        elif name.endswith('_GRID') or name.startswith('TRAFO_') or '_EXP_' in name or '_COMP_' in name or name in ['DHN']:
            return 'Grid infrastructure'
        elif main_prod.startswith(('H2_', 'SNG_', 'BIO_', 'METHANOL')) or name in ['CO2_TO_DIESEL', 'CO2_TO_JETFUELS', 'WOOD_METHANOL', 'ETHANOL_TO_JETFUELS']:
            return 'Alternative fuels'
        else:
            return 'Other'
    else:
        return 'Other'

def compare_config(results, n_run_1, n_run_2):

    annual_prod = results.variables['Annual_Prod']
    annual_prod_run_1 = annual_prod[annual_prod.Run == n_run_1].reset_index()
    annual_prod_run_2 = annual_prod[annual_prod.Run == n_run_2].reset_index()

    annual_res = results.variables['Annual_Res']
    annual_res_run_1 = annual_res[annual_res.Run == n_run_1].reset_index()
    annual_res_run_2 = annual_res[annual_res.Run == n_run_2].reset_index()

    df_compare_prod = pd.merge(
        left=annual_prod_run_1,
        right=annual_prod_run_2,
        on='index',
        suffixes=(f'_run_{n_run_1}', f'_run_{n_run_2}')
    )

    df_compare_res = pd.merge(
        left=annual_res_run_1,
        right=annual_res_run_2,
        on='index',
        suffixes=(f'_run_{n_run_1}', f'_run_{n_run_2}')
    )

    df_compare_prod['diff'] = df_compare_prod['Annual_Prod_run_' + str(n_run_2)] - df_compare_prod['Annual_Prod_run_' + str(n_run_1)]
    df_compare_prod['diff_ratio'] = df_compare_prod['diff'] / df_compare_prod['Annual_Prod_run_' + str(n_run_1)]
    df_compare_prod = df_compare_prod[abs(df_compare_prod['diff']) > 0.01]

    df_compare_res['diff'] = df_compare_res['Annual_Res_run_' + str(n_run_2)] - df_compare_res['Annual_Res_run_' + str(n_run_1)]
    df_compare_res['diff_ratio'] = df_compare_res['diff'] / df_compare_res['Annual_Res_run_' + str(n_run_1)]
    df_compare_res = df_compare_res[abs(df_compare_res['diff']) > 0.01]

    return df_compare_prod.sort_values(by='diff', ascending=False), df_compare_res.sort_values(by='diff', ascending=False)

def rename_bio_resources(row: pd.Series, col: str = 'index', name_type = 'short'):
    if name_type == 'short':
        if row[col] in wood_list:
            row[col] = 'Wood'
        elif row[col] in wet_biomass_list:
            row[col] = 'Wet biomass'
        elif row[col] in waste_list:
            row[col] = 'Waste'
    else:
        if row[col] in wood_list:
            row[col] = 'Waste Wood from Industry, Agriculture and Forestry'
        elif row[col] in wet_biomass_list:
            row[col] = 'Wet Biomass Waste from Industry, Agriculture and Municipalities'
        elif row[col] in waste_list:
            row[col] = 'Organic and Paper Waste'

    return row

def aggregate_mobility_submodels(df: pd.DataFrame) -> pd.DataFrame:
    df['index'] = df['index'].str.replace('_SD', '')
    df['index'] = df['index'].str.replace('_MD', '')
    df['index'] = df['index'].str.replace('_LD', '')
    df['index'] = df['index'].str.replace('_ELD', '')
    group_cols = ['index', 'Run']
    for col in ['Sector', 'Phase', 'Type', 'SSP-RCP', 'Regionalization level', 'Impact category', 'Assessment level']:
        if col in df.columns:
            group_cols.append(col)
    df = df.groupby(group_cols, as_index=False).sum()

    return df

def aggregate_bio_resources(df_annual_res: pd.DataFrame, keep_sub_resources: bool = False) -> pd.DataFrame:

    # Aggregate the resources
    for run in df_annual_res['Run'].unique():
        mask = df_annual_res['Run'] == run
        wood_sum = df_annual_res[mask & df_annual_res['index'].isin(wood_list)]['Annual_Res'].sum()
        wet_biomass_sum = df_annual_res[mask & df_annual_res['index'].isin(wet_biomass_list)]['Annual_Res'].sum()
        waste_sum = df_annual_res[mask & df_annual_res['index'].isin(waste_list)]['Annual_Res'].sum()

        df_annual_res.loc[mask & (df_annual_res['index'] == 'WOOD'), 'Annual_Res'] = wood_sum
        df_annual_res.loc[mask & (df_annual_res['index'] == 'WET_BIOMASS'), 'Annual_Res'] = wet_biomass_sum
        df_annual_res.loc[mask & (df_annual_res['index'] == 'WASTE'), 'Annual_Res'] = waste_sum

    # Remove the individual resources
    if not keep_sub_resources:
        df_annual_res = df_annual_res[~df_annual_res['index'].isin(wood_list + wet_biomass_list + waste_list)]

    return df_annual_res

def update_existing_infrastructure_metrics(
        df_impact_2050: pd.DataFrame,
        df_impact_2020: pd.DataFrame,
        list_existing_techs: list[str],
        col_name: str = 'Name',
        col_type: str = 'Type',
) -> pd.DataFrame:

    df_impact_2050 = df_impact_2050[~((df_impact_2050[col_name].isin(list_existing_techs)) & (df_impact_2050[col_type] == 'Construction'))]
    df_impact_2020 = df_impact_2020[(df_impact_2020[col_name].isin(list_existing_techs)) & (df_impact_2020[col_type] == 'Construction')]
    return pd.concat([df_impact_2050, df_impact_2020], ignore_index=True)

def run_opti(
        reg_level: str = 'spat_fore',
        ssp_rcp: str = 'SSP5-H',
        validation: bool = False,
        year: int = 2050,
        returns: str = 'results',
        other_emissions: bool = True,
        constraint_on_remaining_eq: bool = False,
        constraint_on_remaining_hh: bool = False,
        constraint_on_foreign_ghg_emissions: bool = False,
        constraint_on_territorial_ghg_emissions: bool = True,
        carbon_tax: bool = False,
        dual_variables: bool = False,
) -> Energyscope or energyscope.result.Result or tuple[Energyscope,energyscope.result.Result]:

    path_model = AMPL_FILES_DIR / 'model'
    path_data = AMPL_FILES_DIR / 'data' / str(year)

    # Define the solver options
    solver_options = {
        'solver': 'gurobi' if not dual_variables else 'gurobiasl',
        'solver_msg': 0,
    }

    if year == 2050:
        # Adjust the remaining AoP limits constraints: the remaining AoP should not exceed 2023 levels
        with open(path_data / 'QC_scenarios.dat', 'r') as f:
            lines = f.readlines()

        df_max_AoP = pd.read_csv(path_data / reg_level / ssp_rcp / 'QC_techs_lca_max.csv')
        remaining_aop_2023 = pd.read_csv(REF_RESULTS / 'remaining_aop.csv')
        adjustment_ratios = pd.read_csv(REF_RESULTS / 'adjustment_ratios.csv')

        max_HH = df_max_AoP[df_max_AoP.Abbrev == 'RHHD'].max_unit.iloc[0]
        max_EQ = df_max_AoP[df_max_AoP.Abbrev == 'REQD'].max_unit.iloc[0]

        if reg_level == 'base_wo_iam':
            reg_level_lim_aop = 'base'
        else:
            reg_level_lim_aop = reg_level

        rhhd_2023 = remaining_aop_2023[
            (remaining_aop_2023.Run == reg_level_lim_aop)
            & (remaining_aop_2023['Impact category'] == 'Remaining human health')
        ]['Total'].values[0]

        reqd_2023 = remaining_aop_2023[
            (remaining_aop_2023.Run == reg_level_lim_aop)
            & (remaining_aop_2023['Impact category'] == 'Remaining ecosystem quality')
        ]['Total'].values[0]

        if reg_level == 'base_wo_iam':
            adjustment_ratio_rhhd = 1.0
            adjustment_ratio_reqd = 1.0

        else:
            adjustment_ratio_rhhd = adjustment_ratios[
                (adjustment_ratios['Impact category'] == 'Remaining human health')
                & (adjustment_ratios['RCP'] == ssp_rcp)
                & (adjustment_ratios['Regionalization level'] == reg_level_lim_aop)
            ]['Ratio'].values[0]

            adjustment_ratio_reqd = adjustment_ratios[
                (adjustment_ratios['Impact category'] == 'Remaining ecosystem quality')
                & (adjustment_ratios['RCP'] == ssp_rcp)
                & (adjustment_ratios['Regionalization level'] == reg_level_lim_aop)
            ]['Ratio'].values[0]

        adjustment_ratio_rhhd = min(adjustment_ratio_rhhd, 1.0)  # Ensure that the adjustment ratio does not exceed 1
        adjustment_ratio_reqd = min(adjustment_ratio_reqd, 1.0)

        lines[1] = f"{'#' if not constraint_on_remaining_hh else ''}let limit_lcia['YEAR_2050','RHHD'] := {adjustment_ratio_rhhd} * {rhhd_2023} / {max_HH} ; # (scenario-specific adjustment factor) * (limit [M DALY] / max_HH)\n"
        lines[2] = f"{'#' if not constraint_on_remaining_eq else ''}let limit_lcia['YEAR_2050','REQD'] := {adjustment_ratio_reqd} * {reqd_2023} / {max_EQ} ; # (scenario-specific adjustment factor) * (limit [M PDF.m2.yr] / max_EQ)\n"

        df_max_AoP = pd.read_csv(path_data / reg_level / ssp_rcp / 'QC_techs_lca_max.csv')
        ccst_2023 = pd.read_csv(REF_RESULTS / 'ccst_terr_abroad.csv', keep_default_na=False)
        adjustment_ratios = pd.read_csv(REF_RESULTS / 'adjustment_ratios.csv')

        max_CCS_tot = df_max_AoP[df_max_AoP.Abbrev == 'm_CCS_all'].max_unit.iloc[0]

        if reg_level == 'base_wo_iam':
            reg_level_lim_ccs = 'base'
        else:
            reg_level_lim_ccs = reg_level

        ccs_abroad_2023 = ccst_2023[
            (ccst_2023['Run'] == reg_level_name_dict[reg_level_lim_ccs])
        ]['Abroad CC'].values[0]

        if reg_level == 'base_wo_iam':
            adjustment_ratio_ccs_abroad = 1.0

        else:
            adjustment_ratio_ccs_abroad = adjustment_ratios[
                (adjustment_ratios['Impact category'] == 'Climate change, short term, total')
                & (adjustment_ratios['RCP'] == ssp_rcp)
                & (adjustment_ratios['Regionalization level'] == reg_level_lim_ccs)
            ]['Ratio'].values[0]

        adjustment_ratio_ccs_abroad = min(adjustment_ratio_ccs_abroad, 1.0)  # Ensure that the adjustment ratio does not exceed 1

        lines[5] = f"{'#' if not constraint_on_foreign_ghg_emissions else ''}let limit_abroad['YEAR_2050','m_CCS_all'] := ({adjustment_ratio_ccs_abroad}) * {ccs_abroad_2023} / {max_CCS_tot} ; # (scenario-specific adjustment factor) * (limit [kt CO2-eq] / max_CCS_all)\n"

        df_max_AoP = pd.read_csv(path_data / reg_level / ssp_rcp / 'QC_techs_lca_max.csv')
        max_CCS_tot = df_max_AoP[df_max_AoP.Abbrev == 'm_CCS_all'].max_unit.iloc[0]

        lines[6] = f"{'#' if not constraint_on_territorial_ghg_emissions else ''}let limit_territorial['YEAR_2050','m_CCS_all'] := 0.0 ; # -11.8e3 / {max_CCS_tot} ; # (limit [kt CO2-eq] / max_CCS_all) the limit of 11.8 Mt corresponds to hard-to-abate emissions in QC in 2023. \n"

        with open(path_data / 'QC_scenarios.dat', 'w') as f:
            f.writelines(lines)

    path_lca_files = path_data / reg_level / ssp_rcp if year == 2050 else path_data / reg_level

    if other_emissions:

        ampl_files = [
            ('mod', path_model / 'QC_objectives_lca.mod'),
            # ('mod', path_model / 'QC_objectives_lca_direct.mod'),
            ('mod', path_model / 'QC_objectives_lca_territorial.mod'),
            ('mod', path_model / 'QC_objectives_function.mod'),
            ('dat', path_lca_files / 'QC_techs_lca.dat'),
            # ('dat', path_lca_files / 'QC_techs_lca_direct.dat'),
            ('dat', path_lca_files / 'QC_techs_lca_territorial.dat'),
            ('dat', path_lca_files / 'QC_lyrios_CO2.dat'),
        ]

    else:
        ampl_files = [
            ('mod', path_model / 'QC_objectives_lca.mod'),
            ('mod', path_model / 'QC_objectives_function.mod'),
            ('dat', path_lca_files / 'QC_techs_lca.dat'),
            ('dat', path_lca_files / 'QC_lyrios_CO2.dat'),
        ]

    if carbon_tax:
        ampl_files.insert(2, ('mod', path_model / 'QC_carbon_tax.mod'))

    if not validation:
        ampl_files.append(('dat', path_data / 'QC_scenarios.dat'))  # territorial net-zero emissions

    # Initialize the QC model with .mod and .dat files
    model = load_snapshot(year=year, scenario=False)
    model += Model(ampl_files)  # adding LCA files

    # Initialize the EnergyScope model
    es = Energyscope(model=model, solver_options=solver_options)

    if returns == 'model':
        return es

    # Solve the model and get results
    res = es.calc()
    res = filter_numerical_errors(res)
    res = collapse_temporal_index(res)
    res = postprocessing(res)

    if returns == 'both':
        return es, res

    return res


def filter_numerical_errors(
        results,
        threshold: float = 1e-7,
):
    # Filter numerical errors
    results.variables['F_Mult'] = results.variables['F_Mult'].map(lambda x: 0 if abs(x) < threshold else x)
    results.variables['F_Mult_t'] = results.variables['F_Mult_t'].map(lambda x: 0 if abs(x) < threshold else x)
    results.variables['Annual_Prod'] = results.variables['Annual_Prod'].map(lambda x: 0 if abs(x) < threshold else x)
    results.variables['Annual_Res'] = results.variables['Annual_Res'].map(lambda x: 0 if abs(x) < threshold else x)
    return results


def get_impact_scores(
        impact_category: tuple or list[tuple],
        df_impact_scores: pd.DataFrame,
        df_results: energyscope.result.Result,
        assessment_type: str = 'esm',
        n_run: int or list[int] = None,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame] or pd.DataFrame:

    if isinstance(impact_category, tuple):
        impact_category = [impact_category]

    if isinstance(n_run, int):
        n_run = [n_run]

    if type(df_impact_scores.Impact_category.iloc[0]) is tuple:
        pass
    elif type(df_impact_scores.Impact_category.iloc[0]) is str:
        df_impact_scores.Impact_category = df_impact_scores.Impact_category.apply(lambda x: ast.literal_eval(x))

    df_lifetime = df_results.parameters['lifetime'].reset_index()
    df_f_mult = df_results.variables['F_Mult'].reset_index()
    df_annual_prod = df_results.variables['Annual_Prod'].reset_index()
    df_annual_res = df_results.variables['Annual_Res'].reset_index()
    df_costs = df_results.postprocessing['df_annual'].reset_index()[['Run', 'index', 'Category', 'C_inv_an', 'C_op', 'C_maint']].drop_duplicates()

    if n_run is not None:
        df_f_mult = df_f_mult[df_f_mult.Run.isin(n_run)]
        df_annual_prod = df_annual_prod[df_annual_prod.Run.isin(n_run)]
        df_annual_res = df_annual_res[df_annual_res.Run.isin(n_run)]
        df_lifetime = df_lifetime[df_lifetime.Run.isin(n_run)]
        df_costs = df_costs[df_costs.Run.isin(n_run)]

    df_f_mult = df_f_mult.merge(df_lifetime[['index', 'lifetime', 'Run']], on=['index', 'Run'], how='left')
    df_f_mult = df_f_mult.merge(df_costs[['Run', 'index', 'Category', 'C_inv_an', 'C_maint']], on=['index', 'Run'], how='left')
    df_annual_prod = df_annual_prod.merge(df_costs[['Run', 'index', 'Category']], on=['index', 'Run'], how='left')
    df_annual_res = df_annual_res.merge(df_costs[['Run', 'index', 'Category', 'C_op']], on=['index', 'Run'], how='left')

    for cat in impact_category:
        impact_scores_cat = df_impact_scores[df_impact_scores.Impact_category == cat]
        if len(impact_scores_cat) == 0:
            print(f'Warning: impact category {cat} not found in impact scores data frame.')
            continue

        if assessment_type == 'esm':
            df_f_mult = df_f_mult.merge(impact_scores_cat[impact_scores_cat.Type == 'Construction'][['Name', 'Value']],
                                        left_on='index', right_on='Name', how='left')
            df_f_mult[cat[-1]] = df_f_mult.F_Mult * df_f_mult.Value / df_f_mult.lifetime
            df_f_mult.drop(columns=['Name', 'Value'], inplace=True)

            df_annual_res = df_annual_res.merge(impact_scores_cat[impact_scores_cat.Type == 'Resource'][['Name', 'Value']],
                                                left_on='index', right_on='Name', how='left')
            df_annual_res[cat[-1]] = df_annual_res.Annual_Res * df_annual_res.Value
            df_annual_res.drop(columns=['Name', 'Value'], inplace=True)

        df_annual_prod = df_annual_prod.merge(impact_scores_cat[impact_scores_cat.Type == 'Operation'][['Name', 'Value']],
                                              left_on='index', right_on='Name', how='left')
        df_annual_prod[cat[-1]] = df_annual_prod.Annual_Prod * df_annual_prod.Value
        df_annual_prod.drop(columns=['Name', 'Value'], inplace=True)

    if assessment_type == 'esm':
        return df_f_mult, df_annual_prod, df_annual_res
    else:
        return df_annual_prod


def get_life_cycle_phase_impact_per_capita(
        df_f_mult: pd.DataFrame,
        df_annual_prod: pd.DataFrame,
        df_annual_res: pd.DataFrame,
        df_annual_prod_direct: pd.DataFrame,
        impact_category: str,
        N_capita: int,
        N_digits: int = 3,
) -> tuple[float, float, float, float, float]:
    operation = df_annual_prod[impact_category].sum() / N_capita
    construction = df_f_mult[impact_category].sum() / N_capita
    resource = df_annual_res[impact_category].sum() / N_capita
    total_from_impact_scores = operation + construction + resource

    operation_direct = df_annual_prod_direct[impact_category].sum() / N_capita

    if impact_category == 'Climate change, short term':
        total_from_impact_scores *= 1e-3  # Convert from kg CO2-eq to t CO2-eq
        operation *= 1e-3
        construction *= 1e-3
        resource *= 1e-3
        operation_direct *= 1e-3

    unit = get_impact_category_unit(impact_category)
    print(f'Life-cycle carbon footprint per capita: {round(total_from_impact_scores, N_digits)} {unit} / capita')
    print(f'Percentage due to operation: {round(operation / total_from_impact_scores * 100, N_digits)} %')
    print(f'Including direct emissions: {round(operation_direct / total_from_impact_scores * 100, N_digits)} %')
    print(f'Percentage due to construction: {round(construction / total_from_impact_scores * 100, N_digits)} %')
    print(f'Percentage due to resource: {round(resource / total_from_impact_scores * 100, N_digits)} %')

    return total_from_impact_scores, operation, construction, resource, operation_direct


def get_life_cycle_phase_cost_per_capita(
        df_results: pd.DataFrame,
        N_capita: int,
        N_digits: int = 3,
) -> tuple[float, float, float, float]:
    df_c_inv_an = pd.merge(
        left=df_results.variables['C_inv'],
        right=df_results.parameters['tau'],
        left_index=True,
        right_index=True,
    )

    df_c_inv_an['C_inv_an'] = df_c_inv_an['C_in'] * df_c_inv_an['tau']
    total_cost = 1e6 * float(df_results.variables['TotalCost'].TotalCost.iloc[0]) / N_capita

    maintenance_cost = 1e6 * df_results.variables['C_maint'].C_maint.sum() / N_capita
    operation_cost = 1e6 * df_results.variables['C_op'].C_op.sum() / N_capita
    annualized_investment_cost = 1e6 * df_c_inv_an['C_inv_an'].sum() / N_capita

    print(f'Total cost: {int(total_cost)} CAD / cap / year')
    print(f'Maintenance cost ratio: {round(100 * maintenance_cost / total_cost, N_digits)} %')
    print(f'Operation cost ratio: {round(100 * operation_cost / total_cost, N_digits)} %')
    print(f'Annualized investment cost ratio: {round(100 * annualized_investment_cost / total_cost, N_digits)} %')

    return total_cost, maintenance_cost, operation_cost, annualized_investment_cost


def get_impact_category_unit(
        impact_category: str,
) -> str:
    if impact_category == 'Climate change, short term':
        return 't CO2-eq'
    elif impact_category == 'Total human health':
        return 'DALY'
    elif impact_category == 'Total ecosystem quality':
        return 'PDF.m2.yr'
    else:
        raise ValueError(f"Unknown impact category: {impact_category}")


def get_contribution_df(
        df: pd.DataFrame,
        impact_category_list: str or list[str],
        N: int = -1,
        n_run: int = 0,
) -> pd.DataFrame:
    if isinstance(impact_category_list, str):
        impact_category_list = [impact_category_list]
    if len(impact_category_list) > 1 and N > 0:
        raise ValueError('N should be set to -1 when multiple impact categories are selected')
    if 'Annual_Prod' in df.columns:
        df_type = 'Annual_Prod'
    elif 'F_Mult' in df.columns:
        df_type = 'F_Mult'
    elif 'Annual_Res' in df.columns:
        df_type = 'Annual_Res'
    else:
        raise ValueError('Unknown data frame type')
    df = df[df.Run == n_run]
    df = df[['Run', 'index', df_type] + impact_category_list]
    total_type = df[df_type].sum()
    for impact_category in impact_category_list:
        total_impact = df[impact_category].sum()
        if N > 0:
            df = df.sort_values(impact_category, ascending=False)
            df = df.head(N).reset_index(drop=True)
            total_impact_in_top_N = df[impact_category].sum()
            total_type_in_top_N = df[df_type].sum()
            df = df[['Run', 'index', df_type, impact_category]]
            df.loc[len(df)] = [n_run, 'OTHER', total_type - total_type_in_top_N, total_impact - total_impact_in_top_N]
        df[f'{impact_category} (ratio)'] = df[impact_category] / total_impact
    if df_type == 'Annual_Res':  # other df have different units, so ratios are meaningless
        df[f'{df_type} (ratio)'] = df[df_type] / total_type
    df.rename(columns={'index': 'Name'}, inplace=True)
    df.dropna(inplace=True)
    return df


def get_elementary_flows_contribution_df(
        df_results_ef_contribution_analysis: pd.DataFrame,
        df_results_tech: pd.DataFrame,
        df_results_res: pd.DataFrame,
        N_cap: int,
        impact_category: tuple,
) -> pd.DataFrame:

    # Construction part
    df_results_contrib_ef_constr = df_results_ef_contribution_analysis[
        df_results_ef_contribution_analysis['act_type'] == 'Construction'
        ].merge(df_results_tech[['Name', 'Installed capacity']], left_on='act_name', right_on='Name').drop(columns=['Name'])
    df_results_contrib_ef_constr['scaled_score'] = (df_results_contrib_ef_constr['Installed capacity']
                                                    * df_results_contrib_ef_constr['score'] / N_cap)
    df_results_contrib_ef_constr['scaled_amount'] = (df_results_contrib_ef_constr['Installed capacity']
                                                     * df_results_contrib_ef_constr['amount'] / N_cap)
    df_results_contrib_ef_constr.drop(
        df_results_contrib_ef_constr[df_results_contrib_ef_constr['scaled_score'] == 0].index,
        inplace=True
    )

    # Operation part
    df_results_contrib_ef_op = df_results_ef_contribution_analysis[
        df_results_ef_contribution_analysis['act_type'] == 'Operation'
        ].merge(df_results_tech[['Name', 'Production']], left_on='act_name', right_on='Name').drop(columns=['Name'])
    df_results_contrib_ef_op['scaled_score'] = (df_results_contrib_ef_op['Production']
                                                * df_results_contrib_ef_op['score'] / N_cap)
    df_results_contrib_ef_op['scaled_amount'] = (df_results_contrib_ef_op['Production']
                                                 * df_results_contrib_ef_op['amount'] / N_cap)
    df_results_contrib_ef_op.drop(
        df_results_contrib_ef_op[df_results_contrib_ef_op['scaled_score'] == 0].index,
        inplace=True
    )

    # Resource part
    df_results_contrib_ef_res = df_results_ef_contribution_analysis[
        df_results_ef_contribution_analysis['act_type'] == 'Resource'
        ].merge(df_results_res[['Name', 'Import']], left_on='act_name', right_on='Name').drop(columns=['Name'])
    df_results_contrib_ef_res['scaled_score'] = (df_results_contrib_ef_res['Import']
                                                 * df_results_contrib_ef_res['score'] / N_cap)
    df_results_contrib_ef_res['scaled_amount'] = (df_results_contrib_ef_res['Import']
                                                  * df_results_contrib_ef_res['amount'] / N_cap)
    df_results_contrib_ef_res.drop(
        df_results_contrib_ef_res[df_results_contrib_ef_res['scaled_score'] == 0].index,
        inplace=True
    )

    # Concatenate all parts
    df_results_contrib_ef = pd.concat(
        [df_results_contrib_ef_constr, df_results_contrib_ef_op, df_results_contrib_ef_res],
        ignore_index=True
    )

    # Filter for given impact category
    df_results_contrib_ef = df_results_contrib_ef[df_results_contrib_ef.impact_category == impact_category]

    # Add elementary flow location
    df_results_contrib_ef['ef_loc'] = df_results_contrib_ef.apply(
        lambda x: get_ef_location(x['ef_name'], x['ef_database']), axis=1
    )

    return df_results_contrib_ef


def get_ef_location(ef_name, ef_database):
    if ef_database == 'biosphere3_spatialized_flows':
        ef_loc = ef_name.split(', ')[-1]
    else:
        ef_loc = 'Not spatialized'
    return ef_loc


def add_rhhd_and_reqd_to_impact_scores_df(
        R_long: pd.DataFrame,
        impact_abbrev: pd.DataFrame
) -> tuple[pd.DataFrame, pd.DataFrame]:

    eq_cat_name = "'IMPACT World+ Damage 2.1_regionalized for ecoinvent v3.10', 'Ecosystem quality'"
    hh_cat_name = "'IMPACT World+ Damage 2.1_regionalized for ecoinvent v3.10', 'Human health'"
    bio_eq_cat_name = "'IMPACT World+ Damage 2.1 for ecoinvent v3.10 (incl. CO2 uptake)', 'Ecosystem quality'"

    df_remaining_aop_scores = R_long.pivot_table(
        values="Value",
        index=['Name', 'Type', 'New_code'],
        columns='Impact_category'
    ).reset_index()

    df_remaining_aop_scores[f"({eq_cat_name}, 'Remaining ecosystem quality')"] = \
    df_remaining_aop_scores[f"({eq_cat_name}, 'Total ecosystem quality')"] - (
            df_remaining_aop_scores[f"({eq_cat_name}, 'Climate change, ecosystem quality, short term')"] +
            df_remaining_aop_scores[f"({eq_cat_name}, 'Climate change, ecosystem quality, long term')"]
    ) + (
            - df_remaining_aop_scores[f"({eq_cat_name}, 'Marine acidification, short term')"]
            - df_remaining_aop_scores[f"({eq_cat_name}, 'Marine acidification, long term')"]
            + df_remaining_aop_scores[f"({bio_eq_cat_name}, 'Marine acidification, short term')"]
            + df_remaining_aop_scores[f"({bio_eq_cat_name}, 'Marine acidification, long term')"]
    )

    df_remaining_aop_scores[f"({hh_cat_name}, 'Remaining human health')"] = \
    df_remaining_aop_scores[f"({hh_cat_name}, 'Total human health')"] - (
            df_remaining_aop_scores[f"({hh_cat_name}, 'Climate change, human health, short term')"] +
            df_remaining_aop_scores[f"({hh_cat_name}, 'Climate change, human health, long term')"]
    )

    df_remaining_aop_scores = df_remaining_aop_scores.melt(
        id_vars=['Name', 'Type', 'New_code'],
        value_vars=[
            f"({eq_cat_name}, 'Remaining ecosystem quality')",
            f"({hh_cat_name}, 'Remaining human health')"
        ],
        value_name='Value',
    )

    df_remaining_aop_abbrev = pd.DataFrame([
        [f"({eq_cat_name}, 'Remaining ecosystem quality')", 'PDF.m2.yr', 'REQD', 'EQ', True],
        [f"({hh_cat_name}, 'Remaining human health')", 'DALY', 'RHHD', 'HH', True],
    ],
        columns=['Impact_category', 'Unit', 'Abbrev', 'AoP', 'Regionalized'],
    )
    
    R_long = pd.concat(
        [R_long, df_remaining_aop_scores],
        ignore_index=True,
    )
    
    impact_abbrev = pd.concat(
        [impact_abbrev, df_remaining_aop_abbrev],
        ignore_index=True,
    )

    return R_long, impact_abbrev


def add_biogenic_climate_change_to_impact_scores_df(
        R_long: pd.DataFrame,
        impact_abbrev: pd.DataFrame
) -> tuple[pd.DataFrame, pd.DataFrame]:

    # TODO: to remove when metrics are re-computed with waste datasets for WOOD (no LULUC impacts because waste recovery)
    R_long['Value'] = R_long.apply(lambda x:
                                   x['Value']
                                   - R_long[
                                       (R_long['Name'] == x['Name'])
                                       & (R_long['Impact_category (level 1)'] == 'Ecosystem quality')
                                       & (R_long['Impact_category (level 2)'] == 'Land occupation, biodiversity')]['Value'].iloc[0]
                                   - R_long[
                                       (R_long['Name'] == x['Name'])
                                       & (R_long['Impact_category (level 1)'] == 'Ecosystem quality')
                                       & (R_long['Impact_category (level 2)'] == 'Land transformation, biodiversity')]['Value'].iloc[0]
                                   if (
            (x['Name'] in wood_list)
            & (x['Impact_category (level 2)'] == 'Total ecosystem quality')
    ) else x['Value'], axis=1)

    R_long['Value'] = R_long.apply(lambda x: 0 if (
            (x['Name'] in wood_list)
            & (x['Impact_category (level 1)'] == 'Ecosystem quality')
            & (x['Impact_category (level 2)'] in ['Land occupation, biodiversity', 'Land transformation, biodiversity'])
    ) else x['Value'], axis=1)

    end_eq_cat_name = "'IMPACT World+ Damage 2.1_regionalized for ecoinvent v3.10', 'Ecosystem quality'"
    end_hh_cat_name = "'IMPACT World+ Damage 2.1_regionalized for ecoinvent v3.10', 'Human health'"
    end_bio_eq_cat_name = "'IMPACT World+ Damage 2.1 for ecoinvent v3.10 (incl. CO2 uptake)', 'Ecosystem quality'"
    end_bio_hh_cat_name = "'IMPACT World+ Damage 2.1 for ecoinvent v3.10 (incl. CO2 uptake)', 'Human health'"

    df_biogenic_cc_scores = R_long.pivot_table(
        values="Value",
        index=['Name', 'Type', 'New_code'],
        columns='Impact_category'
    ).reset_index()

    df_biogenic_cc_scores[f"({end_eq_cat_name}, 'Total ecosystem quality (biogenic)')"] = (
        df_biogenic_cc_scores[f"({end_eq_cat_name}, 'Total ecosystem quality')"]
        - df_biogenic_cc_scores[f"({end_eq_cat_name}, 'Climate change, ecosystem quality, short term')"]
        - df_biogenic_cc_scores[f"({end_eq_cat_name}, 'Climate change, ecosystem quality, long term')"]
        - df_biogenic_cc_scores[f"({end_eq_cat_name}, 'Marine acidification, short term')"]
        - df_biogenic_cc_scores[f"({end_eq_cat_name}, 'Marine acidification, long term')"]
        + df_biogenic_cc_scores[f"({end_bio_eq_cat_name}, 'Climate change, ecosystem quality, short term, total')"]
        + df_biogenic_cc_scores[f"({end_bio_eq_cat_name}, 'Climate change, ecosystem quality, long term, total')"]
        + df_biogenic_cc_scores[f"({end_bio_eq_cat_name}, 'Marine acidification, short term')"]
        + df_biogenic_cc_scores[f"({end_bio_eq_cat_name}, 'Marine acidification, long term')"]
    )

    df_biogenic_cc_scores[f"({end_hh_cat_name}, 'Total human health (biogenic)')"] = (
        df_biogenic_cc_scores[f"({end_hh_cat_name}, 'Total human health')"]
        - df_biogenic_cc_scores[f"({end_hh_cat_name}, 'Climate change, human health, short term')"]
        - df_biogenic_cc_scores[f"({end_hh_cat_name}, 'Climate change, human health, long term')"]
        + df_biogenic_cc_scores[f"({end_bio_hh_cat_name}, 'Climate change, human health, short term, total')"]
        + df_biogenic_cc_scores[f"({end_bio_hh_cat_name}, 'Climate change, human health, long term, total')"]
    )

    df_biogenic_cc_scores = df_biogenic_cc_scores.melt(
        id_vars=['Name', 'Type', 'New_code'],
        value_vars=[
            f"({end_eq_cat_name}, 'Total ecosystem quality (biogenic)')",
            f"({end_hh_cat_name}, 'Total human health (biogenic)')",
        ],
        value_name='Value',
    )

    df_biogenic_cc_abbrev = pd.DataFrame([
        [f"({end_eq_cat_name}, 'Total ecosystem quality (biogenic)')", 'PDF.m2.yr', 'TTEQ_bio', 'EQ', True],
        [f"({end_hh_cat_name}, 'Total human health (biogenic)')", 'DALY', 'TTHH_bio', 'HH', True],
    ],
        columns=['Impact_category', 'Unit', 'Abbrev', 'AoP', 'Regionalized'],
    )

    R_long = pd.concat(
        [R_long, df_biogenic_cc_scores],
        ignore_index=True,
    )

    impact_abbrev = pd.concat(
        [impact_abbrev, df_biogenic_cc_abbrev],
        ignore_index=True,
    )

    return R_long, impact_abbrev


def is_territorial(row: pd.Series, main_db_dict_code: dict):
    if row['act_name'] in wood_list+wet_biomass_list+waste_list:
        # biomass resources are assumed to be fully harvested in QC, this is necessary to overlook regioinvent database
        # which does not include QC in its consumption markets.
        return 'CA-QC'
    elif row['database'].startswith('regiopremise'):
        return 'GLO'  # QC not in regioinvent
    elif row['database'].startswith('EnergyScope'):
        return 'CA-QC'  # foreground inventory is QC
    else:
        return main_db_dict_code[row['database'], row['code']]['location']


def compute_territorial_emissions(contrib_processes: pd.DataFrame, main_db: Database):
    main_db_dict_code = main_db.db_as_dict_code
    contrib_processes.drop(columns=['act_database', 'act_code'], inplace=True)
    contrib_processes['process_location'] = contrib_processes.apply(lambda row: is_territorial(row, main_db_dict_code), axis=1)

    contrib_processes['territorial'] = contrib_processes.apply(
        lambda x: True if (
                (x['process_location'] == 'CA-QC')  # process located in the ESM location
        ) else False, axis=1)

    group_cols = ['act_name', 'act_type', 'impact_category']
    contrib_processes = contrib_processes.groupby(
        group_cols + ['territorial']
    ).sum()[['score', 'amount']].reset_index()

    return contrib_processes


def update_ampl_files(
        reg_level: str = 'all',
        year = None,
        specific_lcia_abbrev: list[str] = None,
        main_database: Database = None,
        ssp_rcp: str = 'SSP5-H',
        direct_emissions_files: bool = True,
        territorial_emissions_files: bool = True,
) -> None:

    if year is None:
        year_list = [2023, 2050]
    else:
        year_list = [year]

    if reg_level == 'all':
        reg_level_list = ['base_wo_iam', 'base', 'spat', 'spat_back', 'spat_fore', 'spat_fore_back']
    else:
        reg_level_list = [reg_level]

    for year in year_list:

        for reg_level in reg_level_list:

            if (reg_level == 'base_wo_iam' and year == 2023) or (reg_level == 'base_wo_iam' and year == 2050 and ssp_rcp != 'SSP5-H'):
                # Skip the base_wo_iam for 2020
                continue

            path_inputs = DATA_DIR
            path_data = AMPL_FILES_DIR / 'data' / str(year)
            if year == 2050:
                path_results = LCA_DATA_FILES_DIR / str(year) / reg_level / ssp_rcp
                path_data_lca = path_data / reg_level / ssp_rcp
            else:
                path_results = LCA_DATA_FILES_DIR / str(year) / reg_level
                path_data_lca = path_data / reg_level

            impact_abbrev = pd.read_csv(path_inputs / 'impact_abbrev.csv')
            R_long = pd.read_csv(path_results / 'impact_scores.csv')
            R_long_direct_emissions = pd.read_csv(path_results / 'impact_scores_direct_emissions.csv')
            if territorial_emissions_files:
                contrib_processes = pd.read_csv(path_results / 'contribution_analysis_all_processes_ccst.csv')
            contrib_direct_emissions = pd.read_csv(path_results / 'contribution_analysis_direct_emissions.csv')
            model = pd.read_csv(path_inputs / f'model_{year}.csv')

            if year == 2050:
                if reg_level == 'base_wo_iam':
                    reg_level_2023 = 'base'
                else:
                    reg_level_2023 = reg_level
                R_long_2023 = pd.read_csv(LCA_DATA_FILES_DIR / '2023' / reg_level_2023 / 'impact_scores.csv')
                if territorial_emissions_files:
                    contrib_processes_2023 = pd.read_csv(LCA_DATA_FILES_DIR / '2023' / reg_level_2023 / 'contribution_analysis_all_processes_ccst.csv')

                R_long = update_existing_infrastructure_metrics(
                    R_long,
                    R_long_2023,
                    ['HYDRO_DAM', 'HYDRO_RIVER', 'WIND_ONSHORE'],
                )

                if territorial_emissions_files:
                    contrib_processes = update_existing_infrastructure_metrics(
                        contrib_processes,
                        contrib_processes_2023,
                        ['HYDRO_DAM', 'HYDRO_RIVER', 'WIND_ONSHORE'],
                        'act_name',
                        'act_type',
                    )

            if territorial_emissions_files:
                contrib_processes = compute_territorial_emissions(contrib_processes, main_database)

            R_long, impact_abbrev = add_biogenic_climate_change_to_impact_scores_df(R_long, impact_abbrev)
            R_long_direct_emissions = add_biogenic_climate_change_to_impact_scores_df(R_long_direct_emissions, impact_abbrev)[0]
            R_long, impact_abbrev = add_rhhd_and_reqd_to_impact_scores_df(R_long, impact_abbrev)
            R_long_direct_emissions = add_rhhd_and_reqd_to_impact_scores_df(R_long_direct_emissions, impact_abbrev)[0]

            techs_to_drop = ['SNG_NG', 'WASTE', 'ELEC_EXPORT', 'TRAIN_FREIGHT_H2_HYBRID_ELD', 'TRAIN_FREIGHT_H2_HYBRID_LD']
            if year == 2023:
                techs_to_drop.append('NEW_WIND_ONSHORE')
            R_long = R_long[~R_long.Name.isin(techs_to_drop)].reset_index(drop=True)
            R_long_direct_emissions = R_long_direct_emissions[~R_long_direct_emissions.Name.isin(techs_to_drop)].reset_index(drop=True)
            if territorial_emissions_files:
                contrib_processes = contrib_processes[~contrib_processes.act_name.isin(techs_to_drop)].reset_index(drop=True)

            metadata = {
                'ecoinvent_version': '3.10.1',
                'year': year,
                'iam': 'image',
                'ssp_rcp': ssp_rcp,
            }

            methods = [
                'IMPACT World+ Midpoint 2.1_regionalized for ecoinvent v3.10',
                'IMPACT World+ Damage 2.1_regionalized for ecoinvent v3.10',
                'IMPACT World+ Midpoint 2.1 for ecoinvent v3.10 (incl. CO2 uptake)',
            ]

            esm = ESM(
                # Mandatory inputs
                mapping=pd.DataFrame(),
                unit_conversion=pd.DataFrame(),
                model=pd.DataFrame(),
                mapping_esm_flows_to_CPC_cat=pd.DataFrame(),
                main_database=main_database if main_database is not None else Database(db_as_list=[]),
                main_database_name=None if main_database is not None else "",
                esm_db_name=f'EnergyScope_CA-QC_{year}_{reg_level}',
                esm_location='CA-QC',
                accepted_locations=['CA-QC'],
            )

            esm.pathway = True
            R_long['Year'] = 2025 if year == 2023 else year
            R_long_direct_emissions['Year'] = 2025 if year == 2023 else year
            contrib_processes['Year'] = 2025 if year == 2023 else year

            # Create .dat file
            esm.normalize_lca_metrics(
                R=R_long,
                mip_gap=1e-6,
                lcia_methods=methods,
                specific_lcia_abbrev=specific_lcia_abbrev,
                impact_abbrev=impact_abbrev,
                path=path_data_lca,
                metadata=metadata,
                file_name='QC_techs_lca',
            )

            # Create .dat file for direct emissions
            if direct_emissions_files:
                esm.normalize_lca_metrics(
                    assessment_type='direct emissions',
                    R=R_long,
                    R_direct=R_long_direct_emissions,
                    mip_gap=1e-6,
                    lcia_methods=methods,
                    specific_lcia_abbrev=specific_lcia_abbrev,
                    impact_abbrev=impact_abbrev,
                    path=path_data_lca,
                    metadata=metadata,
                    file_name='QC_techs_lca_direct',
                )

            # Create .dat file for territorial emissions
            if territorial_emissions_files:
                esm.normalize_lca_metrics(
                    assessment_type='territorial emissions',
                    R=R_long,
                    contrib_processes=contrib_processes,
                    mip_gap=1e-6,
                    lcia_methods=methods,
                    specific_lcia_abbrev=['m_CCS_all'],
                    impact_abbrev=impact_abbrev,
                    path=path_data_lca,
                    metadata=metadata,
                    file_name='QC_techs_lca_territorial',
                )

            # Create the .dat files with CO2 layers_in_out aligned with LCA results
            contrib_direct_emissions[['ef_name', 'ef_categories']] = pd.DataFrame(
                contrib_direct_emissions.apply(lambda x: get_emissions_info(x), axis=1).tolist(),
                index=contrib_direct_emissions.index
            )

            contrib_direct_emissions = contrib_direct_emissions[
                (contrib_direct_emissions.impact_category.str.contains("'Midpoint', 'Climate change, short term, total'"))
                & (contrib_direct_emissions.ef_name.isin(['Carbon dioxide, fossil', 'Carbon dioxide, non-fossil']))
                ][['act_name', 'amount']].groupby('act_name').sum().reset_index()

            df = pd.merge(
                model[(model.Flow.isin(['CO2_E', 'CO2_A'])) & (~model.Name.isin(['CO2_E']))],  # co2 emissions only
                contrib_direct_emissions,
                how='inner',
                left_on='Name',
                right_on='act_name',
            ).drop(columns=['act_name'])

            # Excluding CC technologies
            df = df[~df.Name.str.startswith('CARBON_CAPTURE')]
            df = df[~df.Name.str.startswith('DAC_')]

            with open(f'{path_data_lca}QC_lyrios_CO2.dat', 'w') as f:
                for index, row in df.iterrows():
                    f.write(f"let layers_in_out['YEAR_{2025 if year == 2023 else year}','{row['Name']}','{row['Flow']}'] := {row['amount']} ;\n")

def get_emissions_info(row):
    flow = bd.Database(row['database']).get(row['code'])
    return flow.as_dict()['name'], flow.as_dict()['categories']

def plot_impact_categories_contribution(
        df_results_categories: pd.DataFrame,
        impact_category: str,
        save_results: bool = False,
        cutoff: float = 0.0,
        year: int = 2020,
        df_results_constraints: pd.DataFrame = None,
        show_direct_emissions_markers: bool = True,
        show_regionalized_impact_markers: bool = True,
        separate_negative_bars: bool = False,
) -> None:

    if year == 2020:
        run_col = 'Regionalization level'
        run_order = run_order_2020
    else:
        run_col = 'Run'
        run_order = run_order_2050

    if 'biogenic' in impact_category:
        cc_cat_bio_wo_uptake = [
            'Climate change, human health, long term, biogenic',
            'Climate change, human health, long term, fossil',
            'Climate change, human health, long term, land transformation',
            'Climate change, human health, short term, biogenic',
            'Climate change, human health, short term, fossil',
            'Climate change, human health, short term, land transformation',
            'Climate change, ecosystem quality, long term, biogenic',
            'Climate change, ecosystem quality, long term, fossil',
            'Climate change, ecosystem quality, long term, land transformation',
            'Climate change, ecosystem quality, short term, biogenic',
            'Climate change, ecosystem quality, short term, fossil',
            'Climate change, ecosystem quality, short term, land transformation',
        ]
        # drop string after third comma
        df_results_categories['Impact category'] = df_results_categories['Impact category'].apply(
            lambda x: ', '.join(x.split(', ')[:3]) if x in cc_cat_bio_wo_uptake else x
        )

    # Filtering out impact categories below the cutoff
    if cutoff > 0:
        df_results_categories_grouped = df_results_categories.groupby(
            [run_col, 'Impact category']
        ).sum()[[impact_category]].reset_index()

        df_results_categories_grouped = df_results_categories_grouped.merge(
            df_results_categories_grouped.groupby(run_col)[[impact_category]].apply(lambda x: np.sum(np.abs(x), axis=0)).rename(columns={impact_category: "Total level"}),
            on=run_col,
            how='left',
        )

        df_results_categories_grouped["Relative impact"] = df_results_categories_grouped[impact_category] / df_results_categories_grouped["Total level"]

        # Grouping by impact category to find the maximum relative impact among regionalization levels
        df_results_categories_grouped_1 = df_results_categories_grouped.groupby(
            ['Impact category']).max('Relative impact').reset_index()[['Impact category', 'Relative impact']].rename(
            columns={'Relative impact': 'Max relative impact'})
        df_results_categories_grouped_2 = df_results_categories_grouped.groupby(
            ['Impact category']).min('Relative impact').reset_index()[['Impact category', 'Relative impact']].rename(
            columns={'Relative impact': 'Min relative impact'})

        df_results_categories = df_results_categories.merge(
            pd.merge(
                df_results_categories_grouped_1[['Impact category', 'Max relative impact']],
                df_results_categories_grouped_2[['Impact category', 'Min relative impact']],
                on=['Impact category'],
            ),
            on=['Impact category'],
            how='left',
        )

        df_results_categories['Impact category'] = df_results_categories.apply(
            lambda row: "Other" if (
                    abs(row["Max relative impact"]) < cutoff
                    and row["Min relative impact"] > 0  # we keep negative contributions because specific interest
            ) else row["Impact category"],
            axis=1,
        )

    # Categories and styling
    bar_width = .5
    line_width = .6
    hatch_map = {'Direct': '///', 'Indirect': ''}
    impact_categories = df_results_categories['Impact category'].sort_values().unique()
    impact_categories = [i for i in impact_categories if i != 'Other'] + ['Other']  # putting 'Other' at last
    regionalized_categories = df_results_categories[df_results_categories['Regionalized'] == True]['Impact category'].unique()
    scopes = df_results_categories['Scope'].unique()

    # Settings
    fig, ax = plt.subplots(figsize=(bar_width * len(run_order) + .9 if year == 2020 else bar_width * len(run_order), 4.2))
    fig.set_constrained_layout(True)

    # Black frame (spines)
    for spine in ax.spines.values():
        spine.set_color('black')
        spine.set_linewidth(1)

    # Order the x-axis categories
    x_pos = np.arange(len(run_order))

    # Initialize bar bottoms for stacking
    bottoms_pos = {level: 0 for level in run_order}
    bottoms_neg = {level: 0 for level in run_order}

    if separate_negative_bars:
        df_filtered = pd.concat([
            df_results_categories[df_results_categories[impact_category] >= 0].groupby(
                [run_col, 'Impact category', 'Scope']).sum()[[impact_category]].reset_index(),
            df_results_categories[df_results_categories[impact_category] < 0].groupby(
                [run_col, 'Impact category', 'Scope']).sum()[[impact_category]].reset_index(),
        ])
    else:
        df_filtered = df_results_categories.groupby([run_col, 'Impact category', 'Scope']).sum()[[impact_category]].reset_index()

    # Plot bars
    for cat in impact_categories:
        for scope in scopes:
            df_filtered_cat = df_filtered[
                (df_filtered['Impact category'] == cat) &
                (df_filtered['Scope'] == scope)
                ]
            for _, row in df_filtered_cat.iterrows():
                level = row[run_col]
                x_index = run_order.index(level)
                height_val = row[impact_category]

                # distinguish between positive and negative bars
                if height_val > 1e-6:
                    ax.bar(
                        x=x_index,
                        height=height_val,
                        width=bar_width,
                        bottom=bottoms_pos[level],
                        color=impact_category_colors[cat],
                        edgecolor='black',
                        linewidth=line_width,
                        hatch=hatch_map[scope]
                    )
                    bottoms_pos[level] += height_val
                elif height_val < -1e-6:
                    ax.bar(
                        x=x_index,
                        height=height_val,
                        width=bar_width,
                        bottom=bottoms_neg[level],
                        color=impact_category_colors[cat],
                        edgecolor='black',
                        linewidth=line_width,
                        hatch=hatch_map[scope]
                    )
                    bottoms_neg[level] += height_val

    if 'biogenic' in impact_category:
        impact_categories = [cat for cat in impact_categories if 'CO2 uptake' not in cat]

    # Build legend handles
    legend_color_patches = [
        Patch(facecolor=impact_category_colors[cat], edgecolor='black', label=cat, linewidth=line_width) for cat in
        impact_categories]
    legend_scope_patches = [
        Patch(facecolor='white', edgecolor='white', linewidth=line_width, hatch='', label='Emission scope'),
        Patch(facecolor='white', edgecolor='black', linewidth=line_width, hatch='///', label='Direct'),
        Patch(facecolor='white', edgecolor='black', linewidth=line_width, hatch='', label='Indirect'),
        Patch(facecolor='white', edgecolor='white', linewidth=line_width, hatch='', label=''),
        Patch(facecolor='white', edgecolor='white', linewidth=line_width, hatch='', label='Impact category'),
    ]

    # Place both legends in one call using fig.legend (outside the axes)
    legend_color_patches = legend_color_patches[::-1]
    all_patches = legend_scope_patches + legend_color_patches
    legend = fig.legend(
        handles=all_patches,
        loc='upper left',
        bbox_to_anchor=(1.03, 1),
        borderaxespad=0.,
        frameon=False
    )

    # Direct emissions per regionalization level
    direct_emissions = df_results_categories[df_results_categories['Scope'] == 'Direct'].groupby(run_col)[impact_category].sum()
    total_emissions = df_results_categories.groupby(run_col)[impact_category].sum()
    total_emissions_cc = df_results_categories[df_results_categories['Impact category'].str.contains('Climate change')].groupby(run_col)[impact_category].sum()
    total_emissions_remaining = df_results_categories[~df_results_categories['Impact category'].str.contains('Climate change')].groupby(run_col)[impact_category].sum()
    # percent_direct = 100 * direct_emissions / total_emissions

    # Impact being regionalized per regionalization level
    regionalized_impact = df_results_categories[df_results_categories['Regionalized'] == True].groupby(run_col)[impact_category].sum()
    percent_regionalized = 100 * regionalized_impact / total_emissions

    break_idx = 5

    # ax2 = ax.twinx()

    if show_direct_emissions_markers:
        x = [i for i in range(len(run_order))]
        y = [direct_emissions.get(level, 0) for level in run_order]
        x, y = break_line(x, y, break_idx)
        ax.plot(x, y, color='blue', marker='d', linestyle='-')

    if show_regionalized_impact_markers:
        ax2 = ax.twinx()
        x = [i for i in range(len(run_order))]
        y = [percent_regionalized.get(level, 0) for level in run_order]
        x, y = break_line(x, y, break_idx)
        ax2.plot(x, y, color='red', marker='o', linestyle='-')
        ax2.set_ylabel("Damage from regionalized categories (%)", color='red')
        ax2.set_ylim([-5, 105])
        ax2.tick_params(axis='y', colors='red')

    x = [i for i in range(len(run_order))]
    y = [total_emissions_cc.get(level, 0) for level in run_order]
    x, y = break_line(x, y, break_idx)
    ax.plot(x, y, color='black', marker='*', linestyle='-')

    if df_results_constraints is not None:
        y = [total_emissions_remaining.get(level, 0) for level in run_order]
        y = break_line(x, y, break_idx)[1]
        ax.plot(x, y, color='purple', marker='D', linestyle='-', markersize=5)

    y = [total_emissions.get(level, 0) for level in run_order]
    y = break_line(x, y, break_idx)[1]
    ax.plot(x, y, color='black', marker='o', linestyle='-')

    if year == 2050 and df_results_constraints is not None:
        if 'Human health' in impact_category:
            x = df_results_constraints['Run']
            y = df_results_constraints['Limit RHHD'] * 1e6 / N_capita_2050
            ax.plot(x, y, color='purple', marker='_', linestyle='', markersize=15, mew=2.5)
        elif 'Ecosystem quality' in impact_category:
            x = df_results_constraints['Run']
            y = df_results_constraints['Limit REQD'] * 1e6 / N_capita_2050
            ax.plot(x, y, color='purple', marker='_', linestyle='', markersize=15, mew=2.5)

    # Set axis
    ax.set_xticks(x_pos)
    ax.set_xticklabels([i.replace("+", "\n") for i in run_order], rotation=0, ha='center')
    ax.set_xlabel(run_col)
    impact_category = impact_category.replace(' (biogenic)', '')
    ax.set_ylabel(f"{impact_category} damage ({unit_dict_plt[f'Total {impact_category.lower()}']})")

    dot_handles = []

    # if show_regionalized_impact_markers:
    #     dot_handles.append(Line2D([0], [0], color='red', marker='s', linestyle='', label='Regionalized impact', markersize=8))

    if show_direct_emissions_markers:
        dot_handles.append(Line2D([0], [0], color='blue', marker='d', linestyle='', label='Direct emissions damage', markersize=8))

    dot_handles.insert(0, Line2D([0], [0], marker='', linestyle='', label=''))
    if df_results_constraints is not None:
        dot_handles.insert(
            0, Line2D([0], [0], color='purple', marker='_', linestyle='', label='Remaining damage limit',
                   markersize=15, mew=2.5),
        )
        dot_handles.insert(
            0, Line2D([0], [0], color='purple', marker='D', linestyle='', label='Remaining damage', markersize=5),
        )
    dot_handles.insert(
        0, Line2D([0], [0], color='black', marker='*', linestyle='', label='Climate change net damage', markersize=8),
    )
    dot_handles.insert(0, Line2D([0], [0], color='black', marker='o', linestyle='', label='Total net damage', markersize=8))

    if impact_category == 'Ecosystem quality':
        bbox_to_anchor_x = 0.30
    elif impact_category == 'Human health':
        bbox_to_anchor_x = 0.42
    else:
        raise ValueError("Impact category should be 'Human health' or 'Ecosystem quality'")

    # Add the dot legend outside the plot (right side)
    fig.legend(
        handles=dot_handles,
        loc='upper left',
        bbox_to_anchor=(1.03, bbox_to_anchor_x),
        borderaxespad=0.,
        frameon=False,
    )

    for text in legend.get_texts():
        label = text.get_text()
        if label in impact_categories:
            text.set_color('red' if (label in regionalized_categories and label != 'Other') else ('darkorange' if (label in regionalized_categories and label == 'Other') else 'black'))

    if year == 2050:
        ax.set_xlabel('Prospective-regionalization modeling level')
        plt.axvline(x=0.5, color='black', linestyle='--', linewidth=1)
        plt.axvline(x=5.5, color='black', linestyle='--', linewidth=1)
        plt.figtext(0.395, 0.08, "SSP5-H", wrap=True, horizontalalignment='center', fontsize=11, color='black')
        plt.figtext(0.78, 0.08, "SSP2-L", wrap=True, horizontalalignment='center', fontsize=11, color='black')
        ax.set_xticklabels(
            [i.replace("\nSSP5-H", "").replace("\nSSP2-L", "") for i in run_order]
        )

    if save_results:
        if year==2020:
            plt.savefig(
                f'../03_Results/Figures/reference/regionalization_levels_impact_categories_{impact_category.replace(" ", "_")}.pdf',
                bbox_inches='tight',
            )
        elif year==2050:
            plt.savefig(
                f'../03_Results/Figures/2050/regionalization_levels_impact_categories_{impact_category.replace(" ", "_")}_2050.pdf',
                bbox_inches='tight',
            )

    plt.show()

phase_order = [
    'Operation (carbon capture)',
    'Resource (CO2 uptake)',
    'Infrastructure',
    'Operation (direct)',
    'Operation (indirect)',
    'Resource', 'Resource (biomass)', 'Resource (wo biomass)',
    'Resource (rest)',
]

phase_hatches = {
    'Infrastructure': '',
    'Operation (direct)': '///',
    'Operation (indirect)': '',
    'Operation (carbon capture)': '\\\\\\',
    'Resource': '',
    'Resource (biomass)': '',
    'Resource (wo biomass)': '',
    'Resource (CO2 uptake)': '\\\\\\',
    'Resource (rest)': '',
}

phase_hatches_plotly = {
    'Direct': '/',
    'Indirect': '',
}

def plot_cc_phases_contribution(
        df: pd.DataFrame,
        save_results: bool = False,
        year: int = 2020,
) -> None:

    if year == 2020:
        x_label_name = 'Regionalization level'
    elif year == 2050:
        x_label_name = 'Prospective-regionalization modeling level'
    else:
        raise ValueError("Year must be either 2020 or 2050")

    df[x_label_name] = df[x_label_name].apply(lambda x: x.replace("+", "\n"))
    df.rename(columns={'Construction': 'Infrastructure'}, inplace=True)

    df = df.drop(columns='Total').melt(
        id_vars=[x_label_name],
        var_name='Life-cycle phase',
        value_name='Climate change, short term [t CO2-eq/(cap.yr)]',
    )

    # Pivot to have phases as rows and x_labels as columns
    data = df.pivot_table(
        index='Life-cycle phase',
        columns=x_label_name,
        values='Climate change, short term [t CO2-eq/(cap.yr)]',
        aggfunc='sum'
    ).reindex(phase_order)

    if year == 2050:
        data = data[run_order_2050]

    # Get x categories
    x_labels = data.columns.tolist()
    x = np.arange(len(x_labels))
    bar_width = .6
    line_width = .6

    # Plot
    fig, ax = plt.subplots(figsize=(bar_width * len(phase_order) + 3.5, 4.5))

    bottom_pos = np.zeros(len(x_labels))
    bottom_neg = np.zeros(len(x_labels))
    for phase in phase_order:
        values = data.loc[phase].values
        pos_values = np.where(values > 1e-6, values, 0)
        neg_values = np.where(values < -1e-6, values, 0)

        if np.any(pos_values):
            ax.bar(
                x,
                pos_values,
                width=bar_width,
                bottom=bottom_pos,
                label=phase,
                color=phase_colors[phase],
                hatch=phase_hatches[phase],
                edgecolor='black',
                linewidth=line_width,
            )
            bottom_pos += pos_values

        if np.any(neg_values):
            ax.bar(
                x,
                neg_values,
                width=bar_width,
                bottom=bottom_neg,
                label=phase,
                color=phase_colors[phase],
                hatch=phase_hatches[phase],
                edgecolor='black',
                linewidth=line_width,
            )
            bottom_neg += neg_values

    totals = data.sum(axis=0).values

    ax.scatter(
        x,
        totals,
        color='black',
        marker='D',
        label='Net carbon footprint',
        s=50,
        zorder=5,
    )

    # Customizations
    ax.set_xticks(x)
    ax.set_xticklabels(x_labels, rotation=0)
    ax.set_ylabel('Climate change, short term [t CO2-eq/(cap.yr)]')
    ax.set_xlabel(x_label_name)

    # set y axis limits
    y_min = min(bottom_neg) * 1.1 if min(bottom_neg) < 0 else 0
    y_max = max(bottom_pos) * 1.1 if max(bottom_pos) > 0 else 0
    ax.set_ylim(y_min, y_max)

    # Reverse legend order
    handles, labels = ax.get_legend_handles_labels()
    ax.legend(handles[::-1], labels[::-1], title='Life-cycle phase',
              loc='upper left', bbox_to_anchor=(1, 1), frameon=False)

    plt.tight_layout()

    if save_results:
        if year == 2020:
            plt.savefig('../03_Results/Figures/reference/regionalization_levels_life_cycle_phases_ccst.pdf')
        elif year == 2050:
            plt.savefig(f'../03_Results/Figures/2050/regionalization_levels_life_cycle_phases_ccst.pdf')

    plt.show()

def plot_impact_location(df, impact_category, cutoff: float = 0, save_results: bool = False) -> None:

    df['location'] = df.apply(
        lambda row: "Other" if abs(row["max_rel_scaled_score_tot"]) < cutoff else row["location"], axis=1)
    df = df.groupby(['Run', 'location']).sum().reset_index()

    df['Run'] = df['Run'].apply(lambda x: reg_level_name_dict[x])
    df['Run'] = df['Run'].apply(lambda x: x.replace("+", "<br>"))
    df['rel_scaled_score_tot'] *= 100  # Convert to percentage
    df.rename({
        'Run': 'Regionalization level',
        'location': 'Impact location',
        'rel_scaled_score_tot': f'Damage on {impact_category.lower()} [%]'
    }, axis=1, inplace=True)
    
    fig = px.bar(
        df.sort_values(f'Damage on {impact_category.lower()} [%]', ascending=False),
        x='Regionalization level',
        y=f'Damage on {impact_category.lower()} [%]',
        color='Impact location',
        color_discrete_map=region_colors,
        template='custom',
        orientation='v',
        barmode='stack',
        category_orders={
            'Regionalization level': [i.replace("+", "<br>") for i in reg_level_name_dict.values()],
            'Impact location': ['Not spatialized', 'CA-QC', 'CA', 'US', 'RoW', 'Other'],
        },
        height=330,
        width=430,
    )

    fig.update_yaxes(range=[-5, 105])
    fig.update_layout(legend_traceorder="reversed", margin=dict(t=5, b=5, l=5, r=5))
    fig.update_traces(marker_line_color='black', marker_line_width=.6, width=.6)

    if save_results:
        fig.write_html(
            f'../03_Results/Figures/reference/regionalization_levels_regionalized_impacts_loc_{impact_category.replace(" ", "_")}.html')
        fig.write_image(
            f'../03_Results/Figures/reference/regionalization_levels_regionalized_impacts_loc_{impact_category.replace(" ", "_")}.pdf')

    fig.show()

def plot_contribution_by_sector(
        df: pd.DataFrame,
        imp_cat: str,
        save_results: bool = False,
        showlegend: bool = False,
        show_regionalized_marker: bool = True,
        show_total_marker: bool = True,
        show_direct_marker: bool = True,
        hatch_phase: bool = False,
        x_label_name: str = 'Prospective-regionalization level',
        return_fig: bool = False,
        show_fig: bool = True,
        group_by: str = 'Sector',
        cutoff: float = 0.0,
        df_ccst_terr_abroad: pd.DataFrame = None,
        df_results_constraints: pd.DataFrame = None,
        year: int = 2050,
        uncertainty_analysis: bool = False,
        multiple_rcp: bool = True,
        study: str = 'reg',
) -> None or go.Figure:

    if group_by == 'Sector':
        if showlegend:
            if year == 2020:
                width=500
            else:
                if uncertainty_analysis:
                    width=500
                else:
                    width=680 if "Remaining" in imp_cat else 630
        else:
            if year == 2020:
                width=270
            else:
                if uncertainty_analysis:
                    width=300
                else:
                    width=450
        height = 450
    elif group_by == 'index':
        df = df.apply(lambda x: rename_bio_resources(row=x, name_type='long'), axis=1)
        if showlegend:
            if year == 2020:
                width=500
            else:
                if uncertainty_analysis:
                    width=575
                else:
                    width=800
        else:
            if year == 2020:
                width=360
            else:
                if uncertainty_analysis:
                    width=300
                else:
                    width=450
        height=460
    else:
        raise ValueError('group_by must be "Sector" or "index"')

    df = df.rename(columns={
        'Climate change, short term, total': 'Climate change, short term',
        'Climate change, short term, total (abroad)': 'Climate change, short term (abroad)',
        'Climate change, short term, total (territorial)': 'Climate change, short term (territorial)'
    })
    if imp_cat in ['Climate change, short term, total', 'Climate change, short term, total (abroad)',
                   'Climate change, short term, total (territorial)']:
        imp_cat = imp_cat.replace(', total', '')

    if not uncertainty_analysis:
        df['Run_hover'] = df['Run'].apply(lambda x: x.replace("+", " ").replace("Def.  SSP5-H", "Default"))
        df['Run'] = df['Run'].apply(lambda x: x.replace("+", "<br>"))
    else:
        df['Run'] = df['Run'].astype(str)

    if year == 2050:
        if study == 'reg':
            if uncertainty_analysis:
                run_order = df['Run'].unique().tolist()
            else:
                run_order = [i.replace("\n", "<br>") for i in run_order_2050]
        elif study == 'burden':
            run_order = run_order_burden_shifts
        else:
            raise ValueError(f'Unexpected study name: {study}')
        N_cap = N_capita_2050
    elif year == 2020:
        run_order = [i.replace("+", "<br>") for i in run_order_2020]
        N_cap = N_capita_2023
    else:
        raise ValueError("Year must be either 2020 or 2050")

    if df_ccst_terr_abroad is not None:
        if not uncertainty_analysis:
            df_ccst_terr_abroad['Run'] = df_ccst_terr_abroad['Run'].apply(lambda x: x.replace("+", "<br>"))
        else:
            df_ccst_terr_abroad['Run'] = df_ccst_terr_abroad['Run'].astype(str)

    # Filtering out technologies/resources below the cutoff
    if cutoff > 0 and group_by == 'index':
        df_grouped = df.groupby(
            ['Run', 'index']
        )[[imp_cat]].apply(lambda x: np.sum(np.abs(x), axis=0)).reset_index()

        df_grouped = df_grouped.merge(
            df.groupby('Run')[[imp_cat]].apply(lambda x: np.sum(np.abs(x), axis=0)).rename(columns={imp_cat: "Total level"}),
            on='Run',
            how='left',
        )

        df_grouped["Relative impact"] = abs(df_grouped[imp_cat] / df_grouped["Total level"])

        # Grouping by technologies/resources to find the maximum relative impact among regionalization levels
        df_grouped = df_grouped.groupby(
            ['index']).max('Relative impact').reset_index()[['index', 'Relative impact']].rename(
            columns={'Relative impact': 'Max relative impact'})

        df = df.merge(
            df_grouped[['index', 'Max relative impact']],
            on=['index'],
            how='left',
        )

        df['index'] = df.apply(
            lambda row: "Other" if abs(row["Max relative impact"]) < cutoff else row["index"],
            axis=1,
        )

    if hatch_phase:
        df['Phase'] = df['Phase'].apply(lambda x: 'Direct' if x == 'Operation (direct)' else 'Indirect')

    if group_by == 'index':
        df_grouped_index = df.groupby(['Run', group_by])[imp_cat].sum().reset_index()
        index_order = [
                tec for tec in
                df_grouped_index[df_grouped_index[imp_cat] < 0].sort_values(by=imp_cat, ascending=False)[group_by].unique().tolist() +
                df_grouped_index[df_grouped_index[imp_cat] > 0].sort_values(by=imp_cat, ascending=False)[group_by].unique().tolist()
                if tec != 'Other'
            ] + ['Other']

    hover_vars = ['Run', 'Run_hover', group_by]
    if hatch_phase:
        hover_vars.append('Phase')

    grouped_df = (
        df.groupby(hover_vars)[imp_cat]
        .sum()
        .reset_index()
        .sort_values(imp_cat, ascending=False)
    )

    fig = px.bar(
        grouped_df[grouped_df[imp_cat] != 0],
        y=imp_cat,
        x='Run',
        color=group_by,
        pattern_shape='Phase' if hatch_phase else None,
        pattern_shape_map=phase_hatches_plotly if hatch_phase else None,
        color_discrete_map=sector_colors if group_by == 'Sector' else techs_color_map,
        barmode='relative',
        orientation='v',
        template='custom',
        height=height,
        width=width,
        category_orders={
            'Run': run_order,
            group_by: [
                'Carbon capture',
                'Biomass',
                'Energy resources', 'Energy resources (excl. electricity)', 'Imports',
                'Electricity',
                'Passenger mobility',
                'Freight mobility',
                'Domestic heat',
                'Industrial heat',
                'Energy storage',
                'Carbon storage',
                'Grid infrastructure',
                'Alternative fuels',
                'Other',
            ] if group_by == 'Sector' else index_order,
        },
        labels={
            imp_cat: f'{imp_cat} {"damage" if not imp_cat.startswith("Climate change, short term") else ""} ({unit_dict_plotly[imp_cat]})',
            'Run': x_label_name,
        },
        hover_data=hover_vars,
    )

    hover_text = (
        f"<b>Prosp.-reg. level:</b> %{{customdata[0]}}<br>"
        f"<b>{group_by if group_by != 'index' else 'Technology or resource'}:</b> %{{customdata[1]}}<br>"
    )

    if hatch_phase:
        hover_text += "<b>Phase:</b> %{customdata[1]}<br>"

    if 'Climate change' in imp_cat:
        hover_text += f"<b>Value:</b> %{{y:,.2f}} {unit_dict_plotly[imp_cat]}<extra></extra>"
    else:
        hover_text += f"<b>Value:</b> %{{y:.2e}} {unit_dict_plotly[imp_cat]}<extra></extra>"

    fig.update_layout(legend_traceorder="reversed", margin=dict(t=5, b=5, l=5, r=5), showlegend=showlegend)
    fig.update_traces(marker_line_color='black', marker_line_width=0.3, width=.6, marker_pattern_fgcolor='black', hovertemplate=hover_text)

    if group_by == 'index':
        fig.for_each_trace(lambda t: t.update(name=t.name.replace('Long Distance Semi-trailer truck', 'Truck')))
        fig.for_each_trace(lambda t: t.update(name=t.name.replace('Short Distance Semi-trailer truck', 'Truck')))
        fig.for_each_trace(lambda t: t.update(name=t.name.replace('Long Distance Truck', 'Truck')))
        fig.for_each_trace(lambda t: t.update(name=t.name.replace('Short Distance Truck', 'Truck')))

    fig.add_trace(go.Scatter(
        x=[None],
        y=[None],
        mode='markers',
        marker=dict(size=0.1, color='white', line=dict(width=0.1, color='white')),
        showlegend=True,
        name="Technology or resource" if group_by=='index' else group_by,
    ))
    
    fig.add_trace(go.Scatter(
        x=[None],
        y=[None],
        mode='markers',
        marker=dict(size=0.1, color='white', line=dict(width=0.1, color='white')),
        showlegend=True,
        name="",
    ))

    break_idx = 5

    scatter_hover = f"<b>Prosp.-reg. level:</b> %{{customdata[0]}}<br>"
    if 'Climate change' in imp_cat:
        scatter_hover += f"<b>Value:</b> %{{y:,.2f}} {unit_dict_plotly[imp_cat]}<extra></extra>"
    else:
        scatter_hover += f"<b>Value:</b> %{{y:.2e}} {unit_dict_plotly[imp_cat]}<extra></extra>"

    if imp_cat in ['Total human health', 'Total ecosystem quality'] and show_regionalized_marker:
        regionalized_damage = df[['Run', f"{imp_cat} (regionalized part)"]].groupby('Run').sum().reindex(run_order).reset_index()
        x = regionalized_damage["Run"]
        y = regionalized_damage[f"{imp_cat} (regionalized part)"]
        if year == 2050 and not uncertainty_analysis:
            x, y = break_line(x, y, break_idx)
        scatter_customdata = pd.DataFrame(
            data=[i.replace("<br>", " ").replace("Def.  SSP5-H", "Default") if isinstance(i, str) else i for i in x],
            columns=['Run_hover'],
        )
        fig.add_trace(
            go.Scatter(
                x=x,
                y=y,
                marker=dict(color="red", size=8, symbol="square", line=dict(width=2.5, color="red")),
                name="Regionalized impact",
                hovertemplate=scatter_hover,
                customdata=scatter_customdata,
            )
        )

    if uncertainty_analysis:
        scatter_mode = 'markers'
        fig.update_layout(
            xaxis=dict(
                ticktext=list(range(1, len(run_order)+1)),
                tickvals=run_order,
            )
        )
    else:
        scatter_mode = 'markers+lines' if study == 'reg' else 'markers'

    if show_direct_marker:
        direct_emissions = df[df.Phase == 'Operation (direct)'][['Run', imp_cat]].groupby('Run').sum().reindex(run_order).reset_index()
        x = direct_emissions["Run"]
        y = direct_emissions[imp_cat]
        if year == 2050 and not uncertainty_analysis:
            x, y = break_line(x, y, break_idx)
        scatter_customdata = pd.DataFrame(
            data=[i.replace("<br>", " ").replace("Def.  SSP5-H", "Default") if isinstance(i, str) else i for i in x],
            columns=['Run_hover'],
        )
        fig.add_trace(
            go.Scatter(
                x=x,
                y=y,
                mode=scatter_mode,
                marker=dict(color="blue", size=8, symbol="diamond-tall", line=dict(width=2.5, color="blue")),
                name="Direct emissions impact",
                hovertemplate=scatter_hover,
                customdata=scatter_customdata,
            )
        )

    if show_total_marker:
        total_impact = df[['Run', imp_cat]].groupby('Run').sum().reindex(run_order).reset_index()
        x = total_impact["Run"]
        y = total_impact[imp_cat]
        if year == 2050 and not uncertainty_analysis:
            x, y = break_line(x, y, break_idx)
        scatter_customdata = pd.DataFrame(
            data=[i.replace("<br>", " ").replace("Def.  SSP5-H", "Default") if isinstance(i, str) else i for i in x],
            columns=['Run_hover'],
        )
        fig.add_trace(
            go.Scatter(
                x=x,
                y=y,
                mode=scatter_mode,
                marker=dict(color="black", size=5, symbol="circle", line=dict(width=2.5, color="black")),
                name="Net impact",
                hovertemplate=scatter_hover,
                customdata=scatter_customdata,
            )
        )

    if imp_cat.startswith('Climate change, short term') and df_ccst_terr_abroad is not None:

        if imp_cat == 'Climate change, short term':
            x = df_ccst_terr_abroad["Run"]
            y = df_ccst_terr_abroad['Territorial CC'] * 1e3 / N_cap
            if year == 2050 and not uncertainty_analysis:
                x, y = break_line(x, y, break_idx)
            scatter_customdata = pd.DataFrame(
                data=[i.replace("<br>", " ").replace("Def.  SSP5-H", "Default") if isinstance(i, str) else i for i in x],
                columns=['Run_hover'],
            )
            fig.add_trace(
                go.Scatter(
                    x=x,
                    y=y,
                    mode=scatter_mode,
                    marker=dict(color="blue", size=5, symbol="circle", line=dict(width=2.5, color="blue")),
                    name="Territorial impact",
                    hovertemplate=scatter_hover,
                    customdata=scatter_customdata,
                )
            )

        if year == 2050 and imp_cat in ['Climate change, short term', 'Climate change, short term (territorial)']:
            x = df_ccst_terr_abroad["Run"]
            y = df_ccst_terr_abroad['Limit terr CC'] * 1e3 / N_cap
            c = 'blue' if imp_cat == 'Climate change, short term' else 'red'
            scatter_customdata = pd.DataFrame(
                data=[i.replace("<br>", " ").replace("Def.  SSP5-H", "Default") if isinstance(i, str) else i for i in x],
                columns=['Run_hover'],
            )
            fig.add_trace(
                go.Scatter(
                    x=x,
                    y=y,
                    mode="markers",
                    marker=dict(color=c, size=6, symbol="triangle-down", line_width=4, line_color=c),
                    name="Territorial impact limit",
                    hovertemplate=scatter_hover,
                    customdata=scatter_customdata,
                )
            )

        if imp_cat == 'Climate change, short term':
            x = df_ccst_terr_abroad["Run"]
            y = df_ccst_terr_abroad['Abroad CC'] * 1e3 / N_cap
            if year == 2050 and not uncertainty_analysis:
                x, y = break_line(x, y, break_idx)
            scatter_customdata = pd.DataFrame(
                data=[i.replace("<br>", " ").replace("Def.  SSP5-H", "Default") if isinstance(i, str) else i for i in x],
                columns=['Run_hover'],
            )
            fig.add_trace(
                go.Scatter(
                    x=x,
                    y=y,
                    mode=scatter_mode,
                    marker=dict(color="purple", size=5, symbol="circle", line=dict(width=2.5, color="purple")),
                    name="Abroad impact",
                    hovertemplate=scatter_hover,
                    customdata=scatter_customdata,
                )
            )

        if year == 2050 and imp_cat in ['Climate change, short term', 'Climate change, short term (abroad)']:
            x = df_ccst_terr_abroad["Run"]
            y = df_ccst_terr_abroad['Limit abroad CC'] * 1e3 / N_cap
            c = "purple" if imp_cat == 'Climate change, short term' else "red"
            scatter_customdata = pd.DataFrame(
                data=[i.replace("<br>", " ").replace("Def.  SSP5-H", "Default") if isinstance(i, str) else i for i in x],
                columns=['Run_hover'],
            )
            fig.add_trace(
                go.Scatter(
                    x=x,
                    y=y,
                    mode="markers",
                    marker=dict(color=c, size=6, symbol="triangle-down", line_width=4, line_color=c),
                    name="Abroad impact limit",
                    hovertemplate=scatter_hover,
                    customdata=scatter_customdata,
                )
            )

    fig.update_layout(
        legend=dict(
            yanchor="top",
            y=1,
            xanchor="left",
            x=1.05,
            title="",
        )
    )

    if year == 2050 and multiple_rcp and not uncertainty_analysis:
        fig.add_vline(x=0.5, line_width=1, line_dash="dash", line_color="black")
        fig.add_vline(x=5.5, line_width=1, line_dash="dash", line_color="black")
        fig.add_annotation(
            text="SSP5-H",
            xref="paper",
            yref="paper",
            x=2.8/11,
            y=0,
            yshift=-80,
            showarrow=False,
            font=dict(size=15, color="black")
        )

        fig.add_annotation(
            text="SSP2-L",
            xref="paper",
            yref="paper",
            x=9.1/11,
            y=0,
            yshift=-80,
            showarrow=False,
            font=dict(size=15, color="black")
        )

        x_vals = run_order

        x_text = [
            r.replace("<br>SSP5-H", "")
            .replace("<br>SSP2-L", "")
            for r in x_vals
        ]

        fig.update_xaxes(
            tickmode="array",
            tickvals=x_vals,
            ticktext=x_text,
        )

    if df_ccst_terr_abroad is not None and uncertainty_analysis:

        if imp_cat in ['Total human health', 'Total ecosystem quality']:
            fig.add_trace(
                go.Scatter(
                    x=df_ccst_terr_abroad['Run'],
                    y=df_ccst_terr_abroad['TotalLCIA'],
                    mode=scatter_mode,
                    marker=dict(color="red", size=5, symbol="circle"),
                    name="Remaining damage",
                )
            )

            fig.add_trace(
                go.Scatter(
                    x=run_order,
                    y=df_ccst_terr_abroad['limit_lcia'],
                    mode=scatter_mode,
                    marker=dict(color="red", size=6, symbol="triangle-down", line_width=4, line_color="red"),
                    name="Remaining damage upper limit",
                )
            )

    if imp_cat in ['Remaining human health', 'Remaining ecosystem quality'] and df_results_constraints is not None:
        df_results_constraints['Run_hover'] = df_results_constraints['Run'].apply(lambda x: x.replace("<br>", " ").replace("Def.  SSP5-H", "Default"))
        scatter_customdata = df_results_constraints[['Run_hover']]
        fig.add_trace(
            go.Scatter(
                x=df_results_constraints['Run'],
                y=df_results_constraints['Limit RHHD' if imp_cat == 'Remaining human health' else 'Limit REQD'] * 1e6 / N_cap,
                mode='markers',
                marker=dict(color="red", size=6, symbol="triangle-down", line_width=4, line_color="red"),
                name="Remaining damage upper limit",
                hovertemplate=scatter_hover,
                customdata=scatter_customdata,
            )
        )

    if show_fig:
        fig.show()

    if save_results:
        imp_cat = imp_cat.replace(" ", "_").replace(",", "").replace("(", "").replace(")", "").lower()
        if year == 2050:
            fig.write_image(
                f'../03_Results/Figures/2050/regionalization_levels_{group_by}_contrib_{imp_cat}_2050.pdf'
            )
            fig.update_layout(width=None, height=None)
            fig.write_html(
                f'../03_Results/Figures/2050/regionalization_levels_{group_by}_contrib_{imp_cat}_2050.html',
                include_plotlyjs=True,
                full_html=True,
            )
        elif year==2020:
            fig.write_image(
                f'../03_Results/Figures/reference/regionalization_levels_{group_by}_contrib_{imp_cat}.pdf',
                )
            fig.update_layout(width=None, height=None)
            fig.write_html(
                f'../03_Results/Figures/reference/regionalization_levels_{group_by}_contrib_{imp_cat}.html',
                include_plotlyjs=True,
                full_html=True,
            )
    if return_fig:
        return fig

def break_line(x, y, break_idx):
    x = list(x)
    y = list(y)

    x.insert(break_idx + 1, None)
    y.insert(break_idx + 1, None)

    return x, y

def plot_configuration_sector(
        model: pd.DataFrame,
        sector: str,
        cutoff: float = 0.0,
        annual_prod: pd.DataFrame = None,
        annual_prod_2023: pd.DataFrame = None,
        f_mult: pd.DataFrame = None,
        f_mult_2023: pd.DataFrame = None,
        save_results: bool = False,
        save_path: str = None,
        uncertainty_analysis: bool = False,
        sensitivity: str = None,
        scenario: bool = False,
        return_df: bool = False,
        return_fig: bool = False,
        show_fig: bool=True,
        show_delta: bool = False,
        fm_unit: bool = False,
):

    if annual_prod is not None and f_mult is None:
        quantity = 'Annual_Prod'
        quantity_name = 'production'
        quantity_unit = 'TWh/year'
        df_quantity = annual_prod.copy(deep=True)
        df_quantity_2023 = annual_prod_2023.copy(deep=True)
    elif f_mult is not None and annual_prod is None:
        quantity = 'F_Mult'
        quantity_name = 'capacity'
        quantity_unit = 'GW'
        df_quantity = f_mult.copy(deep=True)
        df_quantity_2023 = f_mult_2023.copy(deep=True)
    else:
        raise ValueError("You must provide either annual_prod or f_mult, but not both")

    if sector == 'Heat':
        layers=['HEAT_HIGH_T', 'HEAT_LOW_T_DECEN', 'HEAT_LOW_T_DHN']
        exclude_techs=['High Temperature to Low Temperature Conversion',
                       'High Temperature to Low Temperature Conversion in Decentralized Systems']
        x_axis_label = f'Heat {quantity_name} ({quantity_unit})'
    elif sector == 'Electricity':
        layers=['ELECTRICITY_LV', 'ELECTRICITY_MV', 'ELECTRICITY_HV', 'ELECTRICITY_EHV']
        exclude_techs=[
            'Extra High to High Voltage Transformer',
            'High to Extra High Voltage Transformer',
            'High to Medium Voltage Transformer',
            'Low to Medium Voltage Transformer',
            'Medium to High Voltage Transformer',
            'Medium to Low Voltage Transformer',
            'Storage Electricity',
        ]
        x_axis_label = f'Electricity {quantity_name} ({quantity_unit})'
    elif sector == 'Passenger mobility':
        layers=['MOB_PUBLIC', 'MOB_PRIVATE']
        exclude_techs=[]
        x_axis_label = 'Passenger mobility (Gpkm/year)'
    elif sector == 'Freight mobility':
        layers=['MOB_FREIGHT']
        exclude_techs=[]
        x_axis_label = 'Freight mobility (Gtkm/year)'
    elif sector == 'Carbon capture':
        layers=['CO2_C']
        exclude_techs=['CO2 Storage (output)', 'CO2 Storage (input)']
        x_axis_label = 'Carbon capture (Mt CO<sub>2</sub>/year)'
    elif sector == 'Carbon storage and utilization':
        layers=['CO2_C']
        exclude_techs=['CO2 Storage (output)', 'CO2 Storage (input)']
        x_axis_label = 'Carbon storage and utilization (Mt CO<sub>2</sub>/year)'
    elif sector == 'Storage':
        layers=['DIESEL_S', 'GASOLINE_S', 'ELEC_S', 'NG_S', 'H2_S', 'SNG_S']
        exclude_techs = []
        x_axis_label = 'Energy storage (TWh)'  # only capacity is displayed for storage
    elif sector == 'Other':
        layers=[layer for layer in model[model.Amount > 0].Flow.unique() if layer not in [
            'HEAT_HIGH_T', 'HEAT_LOW_T_DECEN', 'HEAT_LOW_T_DHN',
            'ELECTRICITY_LV', 'ELECTRICITY_MV', 'ELECTRICITY_HV', 'ELECTRICITY_EHV',
            'MOB_PUBLIC', 'MOB_PRIVATE', 'MOB_FREIGHT',
            'CO2_A', 'CO2_C', 'CO2_E', 'CO2_S', 'CO2_CS',
            'ELEC_S', 'SNG_S', 'NG_S', 'GASOLINE_S', 'DIESEL_S',
            'RES_GEO', 'RES_HYDRO', 'RES_SOLAR', 'RES_TIDAL',
            'HEAT_WASTE',
        ]]
        exclude_techs=[tech for tech in model.Name.unique() if
                       (tech.startswith('Natural Gas Expansion'))
                       | (tech.startswith('Natural Gas Compression'))
                       | (tech.startswith('Synthetic Natural Gas Expansion'))
                       | (tech.startswith('Synthetic Natural Gas Compression'))
                       | (tech.startswith('Hydrogen Expansion'))
                       | (tech.startswith('Hydrogen Compression'))
                       | (tech.startswith('Storage to'))
                       | (tech.endswith('to Storage'))
                       ]
        x_axis_label = f'Alternative fuels {quantity_name} ({quantity_unit})'
    else:
        raise ValueError('Sector not recognized. Choose among Heat, Electricity, Passenger mobility, Freight mobility or Other.')

    df = model.copy(deep=True)

    if sector == 'Storage':
        df.loc[model.index.max() + 1] = ['Hydro Storage', 'ELEC_S', 1.0]  # add manually because no layers_in_out in model
        df_quantity[quantity] *= 1e-3  # from GWh to TWh capacity
        df_quantity_2023[quantity] *= 1e-3

    if sensitivity is not None:
        if sector == 'Carbon storage and utilization':
            df = df[
                (df.Amount < 0)
                & (df.Flow.isin(layers))
                ]
            df['Amount'] *= -1.0
        else:
            df = df[
                ((df.Amount > 0) & (df.Flow.isin(layers)))
                | ((df.Name.str.contains('Direct Air Capture')) & (df.Flow.isin(layers)))
                ]
    else:
        if sector == 'Carbon storage and utilization':
            df = df[
                (df.Amount < 0)
                & (df.Flow.isin(layers))
                ]
            df['Amount'] *= -1.0
        else:
            df = df[
                (df.Amount > 0)
                & (df.Flow.isin(layers))
            ]

    if uncertainty_analysis:
        df = df[df.Run.isin(df_quantity.Run.unique())]

    df = df[~df.Name.isin(exclude_techs)]

    if sensitivity == 'carbon_tax':
        df_quantity = df_quantity[['index', 'Run', 'env_tax', quantity]].drop_duplicates(subset=['index', 'Run', 'env_tax'])
    elif sensitivity == 'fossil_cost':
        df_quantity = df_quantity[['index', 'Run', quantity, 'C_inv_an']].drop_duplicates(subset=['index', 'Run'])
    else:
        df_quantity = df_quantity[['index', 'Run', quantity]].drop_duplicates(subset=['index', 'Run'])
        df_quantity_2023 = df_quantity_2023[['index', 'Run', quantity]].drop_duplicates(subset=['index', 'Run'])

    df_2023 = pd.merge(
        df,
        df_quantity_2023,
        left_on=['Name', 'Run'] if uncertainty_analysis else ['Name'],
        right_on=['index', 'Run'] if uncertainty_analysis else ['index'],
        how='left',
    ).fillna(0)

    df = pd.merge(
        df,
        df_quantity,
        left_on=['Name', 'Run'] if uncertainty_analysis else ['Name'],
        right_on=['index', 'Run'] if uncertainty_analysis else ['index'],
        how='left',
    ).fillna(0)

    df = df[df.Run != 0]
    df_2023 = df_2023[df_2023.Run == 'base']

    if sector in ['Freight mobility', 'Passenger mobility']:
        df['Production'] = df[quantity] / (1e3 if quantity == 'Annual_Prod' else 1)  # output lyrios are always 1, and avoid summing up lyrios of distance levels
        df_2023['Production'] = df_2023[quantity] / (1e3 if quantity == 'Annual_Prod' else 1)  # output lyrios are always 1, and avoid summing up lyrios of distance levels
    else:
        df['Production'] = df['Amount'] * df[quantity] / (1e3 if quantity == 'Annual_Prod' else 1)  # from GWh to TWh
        df_2023['Production'] = df_2023['Amount'] * df_2023[quantity] / (1e3 if quantity == 'Annual_Prod' else 1)  # from GWh to TWh

    if sensitivity is not None and sector in ['Electricity', 'Heat']:
        df = df[(df.Production > 0) | (df.Name.str.contains('Direct Air Capture'))]
    else:
        df = df[df.Production > 0]
        df_2023 = df_2023[df_2023.Production > 0]

    df = pd.merge(df, df.groupby(['Run']).sum()['Production'].rename('Total_production').reset_index(), on='Run', how='left')
    df['Production share'] = df['Production'] / df['Total_production']
    df = pd.merge(df, df.groupby(['Name']).max()['Production share'].rename('Max production share').reset_index(), on='Name', how='left')
    if sector != "Carbon capture":
        df['Name'] = df.apply(lambda x: x['Name'] if x['Max production share'] > cutoff or "Direct Air Capture" in x['Name'] else 'Other', axis=1)
    if sector == 'Storage':
        df['Name'] = df['Name'].str.replace(' to', '')

    if uncertainty_analysis:

        df.Run = df.Run.astype(str)

        fig = px.bar(
            df.groupby(['Run', 'Name']).sum().reset_index(),
            y='Run',
            x='Production',
            orientation='h',
            color='Name',
            color_discrete_map=techs_color_map,
            height=400 if sector != 'Freight mobility' else 450,
            width=650,
            labels={
                'Run': 'Cluster',
                'Production': x_axis_label,
                'Name': 'Technology',
            }
        )

        fig.update_layout(
            yaxis=dict(
                ticktext=list(range(1, len(df.Run.unique())+1)),
                tickvals=list(range(len(df.Run.unique()))),
            ),
            margin=dict(l=20, r=20, t=20, b=200),
            legend=dict(
                orientation="h",
                yanchor="top",
                y=-0.4,
                xanchor="center",
                x=0.5
            )
        )

        fig.show()

    if sensitivity is not None:

        if sector in ['Freight mobility', 'Passenger mobility']:
            df['mob_type'] = df['index'].apply(lambda x: x.split(' ')[-1])
            df = df.sort_values(by='mob_type')

        df_pivot = df.pivot_table(
            index='env_tax' if sensitivity == 'carbon_tax' else 'Run',
            columns='Name',
            values='Production',
        ).fillna(0)

        if sector not in ['Freight mobility', 'Passenger mobility']:
            df_pivot = df_pivot.sort_values(by=df_pivot.index.unique().max(), ascending=False, axis=1)

        if sector != 'Carbon capture':
            techs = [tech for tech in df_pivot.columns if 'Direct Air Capture' not in tech]
        else:
            techs = [tech for tech in df_pivot.columns]

        x = df_pivot.index / (1e3 if sensitivity in ['carbon_capture_avail', 'carbon_seq_avail'] else 1)
        y = df_pivot[techs]

        fig, ax1 = plt.subplots()

        ax1.stackplot(x, y.T, labels=techs)#, colors=[techs_color_map[tec] for tec in techs])
        if sensitivity == 'carbon_tax':
            y_label_name = 'Carbon tax (CAD / t CO$_2$-eq)'
        elif sensitivity == 'fossil_cost':
            y_label_name = 'Relative cost of fossil fuels with respect to 2023 (-)'
        elif sensitivity == 'carbon_capture_cost':
            y_label_name = 'Relative cost of carbon capture with respect to 2023 (-)'
        elif sensitivity == 'co2_limit':
            y_label_name = 'Territorial GHG emissions constraint (kt CO2-eq)'
        elif sensitivity == 'ng_cost':
            y_label_name = 'Cost of natural gas (CAD$_{2023}$/kWh)'
        elif sensitivity == 'carbon_capture_avail':
            y_label_name = 'Carbon capture availability (Mt CO$_2$/year)'
        elif sensitivity == 'carbon_seq_avail':
            y_label_name = 'Carbon capture and storage availability (Mt CO$_2$/year)'
        else:
            y_label_name = 'Run'
        ax1.set_xlabel(y_label_name)
        ax1.set_ylabel(x_axis_label)
        ax1.set_ylim(bottom=y.sum(axis=1).max() * -0.05, top=y.sum(axis=1).max() * 1.05)

        if sector in ['Electricity', 'Heat'] and sensitivity == 'carbon_tax':
            ax2 = ax1.twinx()
            dac_techs = [tech for tech in df_pivot.columns if 'Direct Air Capture' in tech]
            for dac_tech in dac_techs:
                if df_pivot[dac_tech].abs().sum() > 0:
                    y = -1.0*df_pivot[dac_tech]
                    ax2.plot(x, y, label=dac_tech, color='red', linestyle='--')
                ax2.set_ylabel(x_axis_label.replace('production', 'consumption of DAC'), color='red')

            ax2.legend(
                reverse=True,
                bbox_to_anchor=(0., -0.25, 1., .102),
                loc='upper left',
                borderaxespad=0.,
            )

        elif sensitivity == 'fossil_cost':
            ax2 = ax1.twinx()
            ax2.plot(
                df.groupby('Run').sum().index,
                df.groupby('Run').sum()['C_inv_an'] / df.groupby('Run').sum()['C_inv_an'].loc[1.0],
                color='red',
                linewidth=2,
            )
            ax2.set_ylabel(f'Annualized investment cost for {sector.lower() if sector != "Other" else "alternative fuels"}\n(relative to initial run) (-)', color='red')
            ax2.set_ylim(-0.05, 1.05 * df.groupby('Run').sum()['C_inv_an'].max() / df.groupby('Run').sum()['C_inv_an'].loc[1.0])
            ax2.tick_params(axis='y', colors='red')

        ax1.legend(
            reverse=True,
            bbox_to_anchor=(0.5, -0.15),
            loc='upper center',
            borderaxespad=0.,
            ncol=1 if sector in ['Heat', 'Freight mobility', 'Other'] else 2,
        )

        plt.show()

    else:

        df.Run = df.Run.apply(lambda x: x.replace("+", " "))

        if sector in ['Freight mobility', 'Passenger mobility']:
            df['mob_type'] = df['index'].apply(lambda x: x.split(' ')[-1])
            df_grouped = df.groupby(['Run', 'Name']).sum().reset_index().sort_values(['mob_type', quantity], ascending=False)
        else:
            df_agg = df.groupby(['Run', 'index'])[quantity].sum().reset_index()
            full_index = pd.MultiIndex.from_product([df['Run'].unique(), df['index'].unique()], names=['Run', 'index'])
            df_full = (
                df_agg.set_index(['Run', 'index'])
                .reindex(full_index)
                .reset_index()
            )
            df_full[quantity] = df_full[quantity].fillna(0)
            stats = df_full.groupby('index')[quantity].agg(['std', 'mean']).reset_index()
            stats = stats.rename(columns={'std': f'{quantity}_std', 'mean': f'{quantity}_mean'})
            df = pd.merge(df, stats, how='left', on='index')
            df[f'{quantity}_cov'] = df[f'{quantity}_std'] / df[f'{quantity}_mean']
            df_grouped = df.groupby(['Run', 'Name']).sum().reset_index()
            df_grouped['_sort_key'] = df_grouped['Name'] == 'Other'  # Sort by cov, but force "Other" to the end
            df_grouped = df_grouped.sort_values(['_sort_key', f'{quantity}_cov'], ascending=[True, True])
            df_grouped = df_grouped.drop(columns='_sort_key')

        if fm_unit and sector == 'Electricity':
            df_grouped['Production'] *= 1000/8760  # from TWh/yr to GW.yr/yr
            df_2023['Production'] *= 1000/8760
            x_axis_label = x_axis_label.replace("TWh/year", "GW.year/year")

        if show_delta:
            # Get the reference data (default scenario)
            df_def = df_grouped[df_grouped['Run'] == 'Def.  SSP5-H'][['Name', 'Run', 'Production']].copy()
            total_prod_def = float(df_def['Production'].sum())
            
            # Ensure every Name in the reference has an entry for every Run in df_grouped
            for name in df_def['Name'].unique():
                for run in df_grouped['Run'].unique():
                    if run != 'Def.  SSP5-H':  # Skip the default run
                        if len(df_grouped[(df_grouped['Name'] == name) & (df_grouped['Run'] == run)]) == 0:
                            # Add a row with Production=0
                            new_row = {'Name': name, 'Run': run, 'Production': 0}
                            df_grouped = pd.concat([df_grouped, pd.DataFrame([new_row])], ignore_index=True)
            
            df_grouped = df_grouped.merge(df_grouped[df_grouped['Run'] == 'Def.  SSP5-H'][['Name', 'Run', 'Production']], how='outer', on=['Name'], suffixes=('', '_def'))
            df_grouped['Production_def'] = df_grouped['Production_def'].fillna(0)
            df_grouped['Production'] = df_grouped['Production'].fillna(0)
            df_grouped['Delta'] = df_grouped['Production'] - df_grouped['Production_def']
            df_grouped['Delta_perc'] = 100 * df_grouped['Delta'] / total_prod_def
            df_grouped = df_grouped[df_grouped['Run'] != 'Def.  SSP5-H']

        df_grouped['Run_hover'] = df_grouped['Run'].apply(lambda x: x.replace("Def.  SSP5-H", "Default"))
        hover_vars = ['Name', 'Production'] + (['Run_hover'] if not scenario else [])

        fig = px.bar(
            df_grouped,
            y='Run',
            x='Production' if not show_delta else 'Delta_perc',
            orientation='h',
            color='Name',
            color_discrete_map=techs_color_map,
            category_orders={
                'Run': [i.replace('\n', ' ') for i in run_order_2050] if not scenario else [
                        'Groupe_1', 'Groupe_1 (NZ)', 'Groupe_2', 'Groupe_2 (NZ)', 'Groupe_3', 'Groupe_3 (NZ)',
                        'Actuel (2023)',
                        'Brut', 'Brut (NZ)',
                        'Acc. verte', 'Acc. verte (NZ)',
                        'Sobre', 'Sobre (NZ)', 'Sobre_Lim. CC (NZ)',
                        'EnergyScope', 'EnergyScope (NZ)',
                    ] + run_order_burden_shifts
            },
            height=280 + 12*len(df['Name'].unique()) + (30 if sector in ['Heat', 'Freight mobility'] else 0),
            width=650,
            labels={
                'Run': 'Prospective-regionalization level' if not scenario else 'Scenario',
                'Production': x_axis_label,
                'Delta': f'Difference with default in {x_axis_label[0].lower() + x_axis_label[1:]}',
                'Delta_perc': f'Difference with default in {x_axis_label.split("(")[0].lower()} (%)',
                'Name': 'Technology',
            },
            hover_data=hover_vars,
        )

        if not scenario:
            hover_text = (
                f"<b>Prosp.-reg. level:</b> %{{customdata[0]}}<br>"
                f"<b>Technology:</b> %{{customdata[1]}}<br>"
            )

            hover_text += f"<b>Value:</b> %{{x:,.2f}} {x_axis_label.split('(')[-1].replace(')', '') if not show_delta else '%'}<extra></extra>"

        fig.update_layout(
            margin=dict(l=5, r=5, t=5, b=5),
            legend=dict(
                orientation="h",
                yanchor="top",
                y=-0.25,
                xanchor="center",
                x=0.35,
            )
        )

        if not scenario:
            fig.update_traces(
                width=.6,
                hovertemplate=hover_text,
            )

        if sector == 'Heat':
            fig.for_each_trace(lambda t: t.update(name=t.name.replace('District Heating Network', 'DHN')))
            fig.for_each_trace(lambda t: t.update(name=t.name.replace('Industrial', 'Ind.')))
            fig.for_each_trace(lambda t: t.update(name=t.name.replace('Decentralized', 'Dec.')))

        if not scenario:
            if not show_delta:
                fig.add_hline(y=9.5, line_width=1, line_dash="dash", line_color="black")
            fig.add_hline(y=4.5, line_width=1, line_dash="dash", line_color="black")
            fig.add_annotation(
                text="SSP5-H",
                xref="paper",
                yref="paper",
                textangle=-90,
                y=8.9/11 if not show_delta else 9.7/11,
                x=0,
                xshift=-140,
                showarrow=False,
                font=dict(size=15, color="black")
            )

            fig.add_annotation(
                text="SSP2-L",
                xref="paper",
                yref="paper",
                textangle=-90,
                y=1/11,
                x=-0,
                xshift=-140,
                showarrow=False,
                font=dict(size=15, color="black")
            )

            x_vals = [i.replace('\n', ' ') for i in run_order_2050]

            x_text = [
                r.replace(" SSP5-H", "")
                .replace(" SSP2-L", "")
                for r in x_vals
            ]

            fig.update_yaxes(
                tickmode="array",
                tickvals=x_vals,
                ticktext=x_text,
            )

            if not show_delta:
                total_2023 = float(df_2023['Production'].sum())
                fig.add_vline(
                    x=total_2023,
                    line_dash="dot",
                    line_color="red",
                    line_width=3.5,
                    opacity=0.9,
                    annotation_text="2023",
                    annotation_font=dict(color="red", size=17),
                    annotation_position="right" if total_2023 == 0 else "left",
                    annotation_textangle=-90,
                )

        if show_fig:
            fig.show()

    if save_results:
        if uncertainty_analysis:
            fig.write_image(f'../03_Results/Figures/uncertainty_analysis/clustering_config_{sector.lower().replace(" ", "_")}.pdf')
        elif sensitivity is not None:
            if save_path is None:
                save_path = f'../03_Results/Figures/sensitivity_analysis/{sensitivity}/'
            fig.savefig(f'{save_path}{sensitivity}_config_{sector.lower().replace(" ", "_")}.pdf', bbox_inches='tight')
        else:
            fig.write_image(f'../03_Results/Figures/2050/{quantity.lower()}_{sector.lower().replace(" ", "_")}{"_delta" if show_delta else ""}{"_gwyr" if fm_unit else ""}.pdf')
            fig.update_layout(width=None, height=None)
            fig.write_html(
                f'../03_Results/Figures/2050/{quantity.lower()}_{sector.lower().replace(" ", "_")}{"_delta" if show_delta else ""}{"_gwyr" if fm_unit else ""}.html',
                include_plotlyjs=True,
                full_html=True,
            )

    df['Sector'] = sector
    df['Unit'] = x_axis_label.split("(")[-1].replace(")", "")

    if return_df and not return_fig:
        return df
    elif return_fig and not return_df:
        return fig
    elif return_df and return_fig:
        return df, fig

def plot_sankey_carbon_flows(
        run: str | int,
        df_total_impact: pd.DataFrame,
        model: pd.DataFrame,
        cutoff: float = 0,
        aggregate_technologies: bool = False,
        show_figure: bool = True,
        save_results: bool = False,
        per_capita: bool = True,
        year: int = 2050,
        mode: str = 'accounting',
        return_df: bool = False,
        return_figure: bool = False,
):

    ccst_cat_name = 'Climate change, short term, total'
    df = df_total_impact[df_total_impact.Run == run][
        ['index', 'Phase', ccst_cat_name, 'Capacity or production']
    ].rename(columns={ccst_cat_name: 'value'})

    # Emissions
    df_em = df[df['value'] >= 0][['index', 'Phase', 'value']].rename(columns={'index': 'source', 'Phase': 'target'})
    df_em_dir = df_em[df_em['target'] == 'Operation (direct)']  # Direct emissions
    df_em_ind = df_em[df_em['target'] != 'Operation (direct)']  # Indirect emissions

    df_em_dir_carbon_carrier = pd.merge(
        df_em_dir,
        model[(model.Amount < 0) & (model.Flow.isin(carbon_carrier_dict.keys()))],
        how='inner',
        left_on='source',
        right_on='Name',
    )[['Flow', 'source', 'value']].rename(columns={'Flow': 'source', 'source': 'target'})
    df_em_dir_carbon_carrier['source'] = df_em_dir_carbon_carrier['source'].apply(lambda x: carbon_carrier_dict[x] if x in carbon_carrier_dict.keys() else x)

    # df_em_ind['source'] = df_em_ind.apply(lambda x: f"{x['source']} ({x['target'].replace(' (indirect)', '')})", axis=1)
    df_em_dir = pd.merge(df_em_dir, model[model.Flow == 'CO2_A'], how='left', left_on='source', right_on='Name')
    df_em_dir_conc = df_em_dir[~df_em_dir.Flow.isna()]  # Concentrated direct emissions
    df_em_dir_non_conc = df_em_dir[df_em_dir.Flow.isna()]  # Non-concentrated direct emissions

    concentrated_direct_emissions_total = float(df_em_dir_conc['value'].sum())
    non_concentrated_direct_emissions_total = float(df_em_dir_non_conc['value'].sum())
    direct_emissions_total = float(df_em_dir['value'].sum())
    indirect_emissions_total = float(df_em_ind['value'].sum())

    df_em_dir_conc['target'] = 'Concentrated'
    df_em_dir_non_conc['target'] = 'Non-concentrated'

    # Capture/absorption
    df_cap = df[
        (df['value'] < 0)
        & (df['Phase'].isin(['Operation (direct)', 'Resource']))
    ].rename(columns={'index': 'target', 'Phase': 'source'})
    df_cap['value'] *= -1.0
    captured_emissions_total = float(df_cap[~(df_cap['target'].str.startswith(('BIOMASS_', 'Bio ')))]['value'].sum())
    biomass_absorption_total = float(df_cap[df_cap['target'].str.startswith(('BIOMASS_', 'Bio '))]['value'].sum())

    if mode == 'accounting':
        df_cap['source'] = df_cap.apply(lambda x: 'Photosynthesis' if x['target'].startswith(('BIOMASS_', 'Bio ')) else 'Total', axis=1)
    elif mode == 'mfa':
        df_cap['source'] = df_cap.apply(
            lambda x: 'Photosynthesis' if x['target'].startswith(('BIOMASS_', 'Bio ')) else 'Concentrated', axis=1)
    df_cap = pd.concat([
        df_cap,
        pd.DataFrame(
            columns=['source', 'target', 'value'],
            data=[[row['target'], 'Captured', row['value']]
                  for idx, row in df_cap[~df_cap['target'].str.startswith(('BIOMASS_', 'Bio '))].iterrows()])
    ])
    df_cap = df_cap.apply(lambda row: rename_bio_resources(row, col='target'), axis=1)

    if year == 2050:
        # Sequestration and utilization
        df_seq_uti = pd.merge(
            df[df.Phase == 'Operation (direct)'],
            model[(model.Flow == 'CO2_C') & (model.Amount < 0) & (model.Name != 'CO2 Storage (input)')],
            how='right',
            left_on='index',
            right_on='Name',
        )[['Name', 'Capacity or production', 'Amount']].rename(columns={'Name': 'target'}).dropna()
        df_seq_uti['value'] = -1.0 * 1e3 * df_seq_uti['Capacity or production'] * df_seq_uti['Amount'] / N_capita_2050
        df_seq_uti['source'] = 'Captured'
        df_seq_uti = df_seq_uti[['source', 'target', 'value']]

        if mode == 'mfa':
            df_permanent_seq = pd.merge(
                df[df.Phase == 'Operation (direct)'],
                model[(model.Flow == 'CO2_S') & (model.Amount > 0)],
                how='right',
                left_on='index',
                right_on='Name',
            )[['Name', 'Capacity or production', 'Amount']].rename(columns={'Name': 'source'}).dropna()
            df_permanent_seq['value'] = 1e3 * df_permanent_seq['Capacity or production'] * df_permanent_seq['Amount'] / N_capita_2050
            df_permanent_seq['target'] = 'Addition to technosphere stock'
            df_permanent_seq = df_permanent_seq[['source', 'target', 'value']]
            df_seq_uti = pd.concat([df_seq_uti, df_permanent_seq])

            # Add permanent sequestration amounts to df_em_dir_carbon_carrier (which values are based on direct emissions amounts)
            df_em_dir_carbon_carrier['value'] = df_em_dir_carbon_carrier.apply(
                lambda x: x['value'] + float(df_permanent_seq[df_permanent_seq.source == x['target']]['value'].iloc[0]) if x['target'] in df_permanent_seq.source.unique()
                else x['value'], axis=1)

    if mode == 'accounting':
        df_em_dir = pd.concat([
            df_em_dir_conc[['source', 'target', 'value']],
            df_em_dir_non_conc[['source', 'target', 'value']],
            df_em_dir_carbon_carrier[['source', 'target', 'value']],
            pd.DataFrame(columns=['source', 'target', 'value'], data=[
                ['Concentrated', 'Direct', concentrated_direct_emissions_total],
                ['Non-concentrated', 'Direct', non_concentrated_direct_emissions_total],
            ])
        ])
        df_em_ind['target'] = 'Indirect'

    elif mode == 'mfa':
        df_em_dir = pd.concat([
            df_em_dir_conc[['source', 'target', 'value']],
            df_em_dir_non_conc[['source', 'target', 'value']],
            df_em_dir_carbon_carrier[['source', 'target', 'value']],
            pd.DataFrame(columns=['source', 'target', 'value'], data=[
                ['Non-concentrated', 'Atmosphere', indirect_emissions_total + non_concentrated_direct_emissions_total],
            ])
        ])
        df_em_ind['target'] = 'Non-concentrated'
        df_em_ind['source'] = 'Other indirect economic activities for the energy system'

    if mode == 'accounting':
        # Total emissions and links with direct/indirect/captured/not captured
        df_link = pd.DataFrame(
            columns=['source', 'target', 'value'],
            data=[
                ['Indirect', 'Total', indirect_emissions_total],
                ['Direct', 'Total', direct_emissions_total],
                ['Total', 'Not captured', direct_emissions_total + indirect_emissions_total - captured_emissions_total],
                ['Not captured', 'Net emissions',
                 direct_emissions_total + indirect_emissions_total - captured_emissions_total - biomass_absorption_total],
                ['Not captured', 'Photosynthesis', biomass_absorption_total],
            ],
        )
    elif mode == 'mfa':
        df_link = pd.DataFrame(
            columns=['source', 'target', 'value'],
            data=[
                ['Concentrated', 'Atmosphere', concentrated_direct_emissions_total - captured_emissions_total],
                ['Atmosphere', 'Photosynthesis', biomass_absorption_total],
                ['Atmosphere', 'Addition to atmosphere stock',
                 direct_emissions_total + indirect_emissions_total - captured_emissions_total - biomass_absorption_total],
            ],
        )

    # Feedback loops between biomass resources and bio-fuels
    df_link_biomass = pd.merge(df[df.Phase == 'Operation (direct)'], model[model.Amount < 0], how='left', left_on='index', right_on='Name').dropna()
    df_link_biomass = df_link_biomass[
        (df_link_biomass.Flow.str.startswith('BIO_'))
        | (df_link_biomass.Flow.isin(['WOOD', 'WET_BIOMASS', 'WASTE']))
    ][['Capacity or production', 'index', 'Flow', 'Amount']]
    df_link_biomass['Capacity or production'] *= df_link_biomass['Amount']
    df_link_biomass['Total production'] = df_link_biomass.groupby('Flow')['Capacity or production'].transform('sum')
    df_link_biomass['Relative production'] = df_link_biomass['Capacity or production'] / df_link_biomass['Total production']
    df_cap_grouped = df_cap.groupby('target').sum()[['value']].reset_index()
    df_cap_grouped['target'] = df_cap_grouped['target'].str.upper().str.replace(' ', '_').str.replace('-', '_')
    df_link_biomass = df_link_biomass.merge(df_cap_grouped, left_on='Flow', right_on='target')
    df_link_biomass['value'] = df_link_biomass['value'] * df_link_biomass['Relative production']
    df_link_biomass = df_link_biomass[['index', 'Flow', 'value']].rename(columns={'index': 'target', 'Flow': 'source'})

    if year == 2050:
        df_link_biofuels = pd.merge(df[df.Phase == 'Operation (direct)'], model[model.Amount > 0], how='left', left_on='index', right_on='Name')
        df_link_biofuels = df_link_biofuels[
            (df_link_biofuels.Flow.str.startswith('BIO_'))
            | (df_link_biofuels.Flow.str.startswith('SNG_'))
            | (df_link_biofuels['index'] == 'Conversion of CO2 to Diesel')
        ][['Capacity or production', 'index', 'Flow', 'Amount']]
        df_link_biofuels['Capacity or production'] *= df_link_biofuels['Amount']
        df_link_biofuels['Total production'] = df_link_biofuels.groupby('index')['Capacity or production'].transform('sum')
        df_link_biofuels['Relative production'] = df_link_biofuels['Capacity or production'] / df_link_biofuels['Total production']

        df_link_biofuels = df_link_biofuels.merge(
            df_em_dir[df_em_dir['source'].isin(df_link_biofuels['index'].unique())],
            how='left',
            left_on='index',
            right_on='source',
        ).rename(columns={'value': 'value_em_dir'})

        df_link_biofuels = df_link_biofuels.merge(
            pd.concat([df_link_biomass[['target', 'value']], df_seq_uti[['target', 'value']]]).groupby('target').sum().reset_index(),
            how='left',
            left_on='index',
            right_on='target',
        )
        df_link_biofuels['value'] = df_link_biofuels['value'] - df_link_biofuels['value_em_dir']
        df_link_biofuels['value'] = df_link_biofuels['value'] * df_link_biofuels['Relative production']
        df_link_biofuels = df_link_biofuels[['index', 'Flow', 'value']].rename(columns={'index': 'source', 'Flow': 'target'})
        df_link_biomass = pd.concat([df_link_biomass, df_link_biofuels])

    df_link_biomass['source'] = df_link_biomass.apply(lambda x: x['source'].capitalize().replace('_', ' ') if
    ((x['source'].startswith('BIO_')) | (x['source'] in ['WOOD', 'WET_BIOMASS', 'WASTE', 'DIESEL', 'GASOLINE'])) else x['source'], axis=1)
    df_link_biomass['target'] = df_link_biomass.apply(lambda x: x['target'].capitalize().replace('_', ' ') if
    ((x['target'].startswith('BIO_')) | (x['target'] in ['WOOD', 'WET_BIOMASS', 'WASTE', 'DIESEL', 'GASOLINE'])) else x['target'], axis=1)
    df_link_biomass['target'] = df_link_biomass['target'].apply(lambda x: carbon_carrier_dict[x] if x in carbon_carrier_dict else x)

    # Aggregation of technology groups
    techno_list = ['Boiler', 'Coach', 'School Bus', 'Powered Bus', 'Semi-trailer truck', 'Plane', 'Conversion of CO2', 'Powered Car',
                   'Light Commercial Vehicle', 'Train', 'Sport Utility Vehicle', 'Ship', 'Heat Pump', 'Natural Gas Expansion',
                   'Electric Grid', 'Natural Gas Grid', 'Hydrogen Grid', 'Long Distance Truck', 'Short Distance Truck']

    if aggregate_technologies:
        df_em_ind = aggregated_sankey_technologies(df_em_ind, techno_list)
        df_em_dir = aggregated_sankey_technologies(df_em_dir, techno_list)

    # Applying cutoff
    df_em_dir['source'] = df_em_dir.apply(lambda x: x['source'] if (
            x['value'] > cutoff
            or x['source'] in (df_link_biomass.target.unique())
            # or x['source'] in (df_seq_uti.target.unique() if year == 2050 else [])
            or x['source'] in techno_list
    ) else 'Other (direct)', axis=1)
    if mode != 'mfa':
        df_em_ind['source'] = df_em_ind.apply(lambda x: x['source'] if (
                x['value'] > cutoff
                or x['source'] in df_em_dir.source.unique()
        ) else 'Other (indirect)', axis=1)

    kept_sources = list(df_em_dir['source'].unique()) + list(df_em_ind['source'].unique()) + [
        'Indirect', 'Direct', 'Total', 'Captured', 'Not captured', 'Photosynthesis', 'Concentrated', 'Non-concentrated', 'Net emissions', 'Atmosphere',
    ]
    df_em_dir['target'] = df_em_dir.apply(lambda x: x['target'] if x['target'] in kept_sources else 'Other (direct)', axis=1)
    if mode != 'mfa':
        df_em_ind['target'] = df_em_ind.apply(lambda x: x['target'] if x['target'] in kept_sources else 'Other (indirect)', axis=1)

    if year == 2050:
        df_flow = pd.concat([df_em_dir, df_em_ind, df_cap, df_link, df_link_biomass, df_seq_uti]).reset_index(drop=True)
    else:
        df_flow = pd.concat([df_em_dir, df_em_ind, df_cap, df_link, df_link_biomass]).reset_index(drop=True)
    df_flow = df_flow.groupby(['source', 'target']).sum('value').reset_index()

    if aggregate_technologies:
        df_flow = aggregated_sankey_technologies(df_flow, techno_list)
        df_flow = df_flow.groupby(['source', 'target']).sum('value').reset_index()

    if not per_capita:
        if year == 2050:
            df_flow['value'] *= N_capita_2050 / 1e6
        else:
            df_flow['value'] *= N_capita_2023 / 1e6

    colors = Colors(techs_color_map)
    df_flow['color'] = df_flow.apply(lambda row: str(colors[row['target']] | colors[row['source']]), axis=1)
    node = np.unique(np.concatenate((df_flow['source'].unique(), df_flow['target'].unique())))
    df_sankey = df_flow.replace(node, range(len(node)))

    # Plotting
    opacity = 0.5

    fig = go.Figure(data=[go.Sankey(
        valueformat=".2f",
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
            # color=df_sankey['color'].apply(lambda c: Color(c).rgba(opacity))
        )
    )])
    fig.update_layout(
        title_text=f"Sankey diagram of GHG emissions" + (" (t CO<sub>2</sub>-eq per capita and per year)" if per_capita else " (Mt CO<sub>2</sub>-eq/year)"),
        font_size=10,
        template="plotly",
        font_color="black",
    )
    if show_figure:
        fig.show()

    reg_level_name_dict_2050_inv = {value: key for key, value in reg_level_name_dict_2050.items()}

    if save_results:
        if year == 2050:
            fig.write_html(f'../03_Results/Figures/2050/sankey_carbon_{reg_level_name_dict_2050_inv[run]}.html')
        else:
            fig.write_html(f'../03_Results/Figures/reference/sankey_carbon_{year}.html')

    if return_df and not return_figure:
        return df_flow
    elif return_figure and not return_df:
        return fig
    elif return_df and return_figure:
        return df_flow, fig

def aggregated_sankey_technologies(df_flow: pd.DataFrame, techno_list: list[str]):

    # Iterate over technologies for aggregation
    for tech in techno_list:
        df_flow.loc[
            (df_flow['target'].str.contains(tech)), 'target'
        ] = tech.replace('Powered ', '')

        df_flow.loc[
            (df_flow['source'].str.contains(tech)), 'source'
        ] = tech.replace('Powered ', '')

    return df_flow
