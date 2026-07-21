"""Technology grouping + per-group colors, used for the Metal_Intensity sheet's
column-C fill (the `group` column in the Mapping sheet is maintained by hand in
Excel, not written by this code).

Rules and hex colors mirror projects/pathway/src/plot_results.py's
CATEGORY_RULES/CATEGORY_COLORS (used for the pathway plots) so the same
technology reads as the same color in both the Excel sheet and the plots --
except ELECTRICITY, which plot_results.py has as orange (#FFA15A); this module
follows that too (technologies_mi_all_years.xlsx previously used light blue for
it, kept only for backward-compat reference in comments/history).
"""

# Order matters: first match wins.
CATEGORY_RULES = [
    ('HEAT_LOW_T',     ['DHN', 'DEC_']),
    ('HEAT_HIGH_T',    ['IND_BOILER', 'IND_COGEN', 'IND_DIRECT', 'IND_HP']),
    ('STORAGE',        ['HYDRO_STORAGE', 'BATTERY', 'TH_STORAGE', 'MINES_STORAGE',
                        'STO_DIE', 'STO_ELEC', 'STO_GASO', 'STO_H2', 'STO_NG', 'STO_SNG',
                        'DIE_STO', 'GASO_STO', 'ELEC_STO', 'H2_STO', 'NG_STO', 'SNG_STO']),
    ('CO2',            ['CO2_', 'DAC_', 'DEEP_SALINE', 'UNMINEABLE', 'EOR', 'DOGR',
                        'STO_CO2', 'CEMENT_PROD', 'CARBON_']),
    ('H2_SYNFUELS',    ['ELECTROLYSIS', 'ALKALINE_ELECTROLYSIS', 'PEM_ELECTROLYSIS',
                        'SOEC_ELECTROLYSIS', 'SMR', 'ATR', 'BIOGAS_', 'BIOMASS_GAS',
                        'COAL_GAS', 'GASIFICATION', 'METHANATION', 'PYROLYSIS',
                        'NG_PYROLYSIS', 'SNG_PYROLYSIS', 'REFORMING', 'NG_REFORMING',
                        'SNG_REFORMING', 'H2_COMP', 'H2_EXP', 'NG_COMP', 'NG_EXP',
                        'SNG_COMP', 'SNG_EXP', 'FT', 'METATHESIS', 'CUMENE',
                        'METHANOL', 'BIOMETHANOL', 'METHANE_TO', 'WOOD_METHANOL',
                        'ETHANOL_TO', 'BIOETHANOL_TO', 'BIOMETHANE_TO', 'CROPS_TO',
                        'ETHANE_', 'AN_DIG']),
    ('ELECTRICITY',    ['PV_', 'WIND_', 'NEW_WIND', 'HYDRO', 'NEW_HYDRO', 'NUCLEAR',
                        'CCGT', 'H2_CCGT', 'H2_NG_CCGT', 'H2_SNG_CCGT', 'COAL_',
                        'OCGT_', 'TIDAL', 'GEOTHERMAL', 'AFC', 'PAFC', 'PEMFC', 'SOFC']),
    ('MOB_PRIVATE',    ['CAR_', 'SUV_']),
    ('MOB_PUBLIC',     ['BUS_', 'TRAMWAY', 'SCHOOLBUS_', 'COMMUTER_RAIL', 'COACH_',
                        'PLANE_SH', 'PLANE_LH', 'TRAIN_DIESEL', 'TRAIN_BIODIESEL',
                        'TRAIN_ELEC', 'TRAIN_H2', 'TRAIN_NG', 'TRAIN_SNG']),
    ('MOB_FREIGHT',    ['TRUCK_', 'SEMI_', 'LCV_', 'TRAIN_FREIGHT', 'BULK_CARRIER',
                        'CONTAINER', 'OIL_TANKER', 'PLANE_FREIGHT']),
    ('INFRASTRUCTURE', ['_GRID', 'TRAFO_', 'HT_LT', 'HYDRO_GAS', 'LT_DEC_WH',
                        'LT_DHN_WH', 'DHN_RENOVATION', 'DEC_RENOVATION', 'DIRECT_USAGE']),
    ('INDUSTRY',       ['AL_MAKING', 'FOOD_PROD', 'PAPER_MAKING', 'STEEL_MAKING',
                        'CEMENT', 'ETHYLENE', 'PET_', 'PVC_', 'POLYPROPYLENE',
                        'STYRENE', 'SMART_PROCESS']),
]

GROUP_COLORS = {
    'HEAT_LOW_T':     'EF553B',  # red
    'HEAT_HIGH_T':    'B6E880',  # light green
    'STORAGE':        'FECB52',  # yellow
    'CO2':            '636363',  # dark grey
    'H2_SYNFUELS':    '17BECF',  # teal
    'ELECTRICITY':    'FFA15A',  # orange
    'MOB_PRIVATE':    '636EFA',  # blue-violet
    'MOB_PUBLIC':     '19D3F3',  # cyan
    'MOB_FREIGHT':    'AB63FA',  # purple
    'INFRASTRUCTURE': 'BAB0AC',  # grey-brown
    'INDUSTRY':       '8C564B',  # brown
}

GROUP_LABELS = {
    'HEAT_LOW_T':     'Heat (low temperature)',
    'HEAT_HIGH_T':    'Heat (high temperature)',
    'STORAGE':        'Storage',
    'CO2':            'CO2 capture / storage',
    'H2_SYNFUELS':    'H2 & synfuels',
    'ELECTRICITY':    'Electricity production',
    'MOB_PRIVATE':    'Private mobility',
    'MOB_PUBLIC':     'Public mobility',
    'MOB_FREIGHT':    'Freight mobility',
    'INFRASTRUCTURE': 'Infrastructure',
    'INDUSTRY':       'Industry',
}

UNGROUPED = 'OTHER'


def categorize(tech_name):
    """First matching group for `tech_name`, or UNGROUPED if nothing matches.

    A keyword matches as a *prefix* of tech_name (e.g. 'OCGT_' only matches techs
    starting with OCGT_, so 'OCGT_BIOGAS_CC' lands in ELECTRICITY rather than
    H2_SYNFUELS just because 'BIOGAS_' appears in the middle of the name) --
    except a keyword starting with '_' (e.g. '_GRID'), which can never be a
    prefix by construction and is matched anywhere in the name instead.
    """
    upper = tech_name.upper()
    for group, keywords in CATEGORY_RULES:
        for kw in keywords:
            if kw.startswith('_'):
                if kw in upper:
                    return group
            elif upper.startswith(kw):
                return group
    return UNGROUPED
