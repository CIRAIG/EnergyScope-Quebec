"""
plot_results.py
Usage:
  python plot_results.py [case_study]
"""
import os, sys, pickle, re, glob as _glob
import json
from typing import Union
import numpy as np
import colorsys
import webbrowser
from collections import defaultdict
import pandas as pd
import plotly.graph_objects as go
import plotly.io as pio
import plotly.colors as pc
from plotly.subplots import make_subplots

# EnergyScope color utilities (inlined from ES_plot_files/colors.py, py3.7-compatible)
class _ES_Color:
    def __init__(self, color):
        self.__color = color

    @staticmethod
    def cast(color):
        return color if isinstance(color, _ES_Color) else _ES_Color(color)

    def __or__(self, other):
        return _ES_Color.cast(other) if (self.__color == '#000000') else self

    def __eq__(self, other):
        return self.__color == _ES_Color.cast(other).__color

    def __str__(self):
        return self.__color

    def rgba(self, alpha=None):
        color = self.__color.lstrip('#')
        r, g, b = int(color[0:2], 16), int(color[2:4], 16), int(color[4:6], 16)
        a = alpha if alpha is not None else (int(color[6:8], 16) / 255.0 if len(color) == 8 else 1.0)
        return 'rgba({}, {}, {}, {:.2f})'.format(r, g, b, a)


class _ES_Colors:
    def __init__(self, colors=None, fallback=None):
        self._colors = {k: _ES_Color.cast(c) for k, c in colors.items()} if colors else {}

    @staticmethod
    def cast(colors):
        return colors if isinstance(colors, _ES_Colors) else _ES_Colors(colors)

    def __getitem__(self, key):
        if not key:
            return _ES_Color('#000000')
        if key in self._colors:
            return self._colors[key]
        return self[key.rpartition('_')[0]]

    def __or__(self, colors):
        other = colors._colors if isinstance(colors, _ES_Colors) else colors
        return _ES_Colors({**self._colors, **other})


_ES_default_colors = _ES_Colors({
    'GASOLINE': '#808080',  'BIO_DIESEL': '#6B8E23', 'DIESEL': '#D3D3D3',
    'URANIUM': '#66ff33',   'NG': '#FFD700',          'SNG': '#FFE100',
    'LFO': '#8B008B',       'COAL': '#A0522D',        'HYDRO': '#00CED1',
    'WASTE': '#FA8072',     'SOLAR': '#FFFF00',       'GEOTHERMAL': '#FF0000',
    'H2': '#FF00FF',        'RES_WIND': '#FFA500',    'HEAT_HT': '#DC143C',
    'ELECTRICITY': '#00BFFF', 'EUD_ELECTRICITY': '#00BFFF',
    'LIGHTING': '#00BFFF',   'HEAT_LOW_T_SC': '#FF4500',
    'ETHANOL': '#E1DA00',   'AMMONIA': '#C3DA00',     'METHANOL': '#A5DA00',
    'CO2': '#545454',       'WOOD': '#CD853F',        'WET_BIOMASS': '#b37b44',
    'HEAT': '#B51F1F',      'MOB': '#FF69B4',
    'WIND': '#0000FF',      'PV': '#FFD700',
})

pio.templates.default = 'simple_white'


class _NpEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, (np.integer,)):  return int(obj)
        if isinstance(obj, (np.floating,)): return float(obj)
        if isinstance(obj, np.ndarray):     return obj.tolist()
        return super().default(obj)

def _jdumps(obj): return json.dumps(obj, cls=_NpEncoder)

DEFAULT_CASE = 'Test'
OUT_DIR      = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'out')
SHOW         = False
SHOW_DISTANCE_VARIANTS = False   # True → keep _SD/_MD/_LD/_ELD suffixes; False → aggregate to base tech

# ===========================================================================
# PLOT SELECTION — set to False to skip a plot group
# ===========================================================================
PLOTS = {
    'summary':          True,   # 0  — summary dashboard (energy mix + KPI %)
    #'mobility_recap':   False,  # removed — merged into summary dashboard
    'gwp':              True,   # 00 — total GWP over time
    'transition_cost':  True,   # 01 — transition cost
    'capex_breakdown':  True,   # 03 — capex breakdown by tech
    'opex_breakdown':   True,   # 04 — opex breakdown by tech
    'total_cost':       True,   # 05 — total cost breakdown
    'resources':        True,   # 06 — resource use
    'annual_prod':      True,   # 07 — annual production by tech
    'monthly_prod':     True,   # 08 — monthly production profiles
    'monthly_resources': True,  # 08b — monthly resource use profiles
    'monthly_co2_storage': True, # 08c — monthly CO2_S throughput [kt CO₂]
    'load_factor':      True,   # 09 — load factor heatmap
    'mobility_pies':    True,   # 10 — mobility share pies
    'f_new':            True,   # 2x — new capacity by category
    'f_old':            True,   # 3x — old/kept capacity by category
    'f_decom':          True,   # 4x — decommissioned capacity by category
    'number_of_units':  True,   # 9x — number of installed units by category
    'electricity_layer':True,   # 12 — electricity layer balance
    'heat_layer':       True,   # 13 — heat layer balance
    'h2_layer':         True,   # 12 — hydrogen layer balance
    'ng_layer':         True,   # 12c — natural gas layer balance
    'mobility_layer':   True,   # 13 — mobility layer balance
    'sankey':           True,   # 16 — Sankey energy flow (ES library style)
    'storage_levels':   True,   # 15 — storage fill levels by month and year
    'gwp_breakdown':    True,   # 14 — GWP breakdown by tech
    'monthly_h2':       True,   # 99 — TEMPORARY monthly H2 layer balance
    'sankey_co2':       True,   # 17 — CO₂ flow Sankey per year
    'monthly_electricity': True, # 18 — monthly electricity layer balance (signed, per tech)
}

YEARS_ORDER = ['2020','2025','2030','2035','2040','2045','2050']

def _to_int_years(year_strings):
    """Convert list of year strings to sorted integers for linear x-axis."""
    return sorted(int(y) for y in year_strings)


# ===========================================================================
# CONSTANTS
# ===========================================================================

QC_DATA_DAT   = os.path.join('ES_Transition_QC_2', 'QC_data.dat')
TECHS_B2D_DAT = os.path.join('ES_Transition_QC_2', 'QC_techs_B2D.dat')

PHASES_ORDER = ['2015_2020', '2020_2025','2025_2030','2030_2035',
                '2035_2040','2040_2045','2045_2050']
INIT_PHASE   = '2015_2020'   # initialisation pseudo-phase — shown separately
TRANS_PHASES = [p for p in PHASES_ORDER if p != INIT_PHASE]

MONTH_LABELS = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec']

_T_OP = {1: 744, 2: 672, 3: 744, 4: 720, 5: 744, 6: 720,
         7: 744, 8: 744, 9: 720, 10: 744, 11: 720, 12: 744}

ELEC_LAYERS = ['ELECTRICITY_LV', 'ELECTRICITY_MV', 'ELECTRICITY_HV', 'ELECTRICITY_EHV']
ELEC_LAYER_LABELS = {
    'ELECTRICITY_LV':  'LV',
    'ELECTRICITY_MV':  'MV',
    'ELECTRICITY_HV':  'HV',
    'ELECTRICITY_EHV': 'EHV',
}

HEAT_LAYERS = ['HEAT_HIGH_T', 'HEAT_LOW_T_DECEN', 'HEAT_LOW_T_DHN', 'HEAT_WASTE']
HEAT_LAYER_LABELS = {
    'HEAT_HIGH_T':       'High T',
    'HEAT_LOW_T_DECEN':  'Low T decen.',
    'HEAT_LOW_T_DHN':    'Low T DHN',
    'HEAT_WASTE':        'Waste heat',
}

H2_LAYERS = ['H2_LP', 'H2_MP', 'H2_HP', 'H2_EHP']
H2_LAYER_LABELS = {
    'H2_LP':  'LP',
    'H2_MP':  'MP',
    'H2_HP':  'HP',
    'H2_EHP': 'EHP',
}

NG_LAYERS = ['NG_LP', 'NG_MP', 'NG_HP', 'NG_EHP', 'SNG_LP', 'SNG_MP', 'SNG_HP', 'SNG_EHP']
NG_LAYER_LABELS = {
    'NG_LP':   'NG_LP',
    'NG_MP':   'NG_MP',
    'NG_HP':   'NG_HP',
    'NG_EHP':  'NG_EHP',
    'SNG_LP':  'SNG_LP',
    'SNG_MP':  'SNG_MP',
    'SNG_HP':  'SNG_HP',
    'SNG_EHP': 'SNG_EHP',
}

MOB_PASSENGER_LAYERS = [
    'MOB_PRIVATE_SD', 'MOB_PUBLIC_SD',
    'MOB_PRIVATE_MD', 'MOB_PUBLIC_MD',
    'MOB_PRIVATE_LD', 'MOB_PUBLIC_LD',
    'MOB_PRIVATE_ELD', 'MOB_PUBLIC_ELD',
]
MOB_FREIGHT_LAYERS = [
    'MOB_FREIGHT_SD', 'MOB_FREIGHT_MD',
    'MOB_FREIGHT_LD', 'MOB_FREIGHT_ELD',
]
MOB_LAYER_LABELS = {
    'MOB_PRIVATE_SD':  'Private SD',
    'MOB_PUBLIC_SD':   'Public SD',
    'MOB_PRIVATE_MD':  'Private MD',
    'MOB_PUBLIC_MD':   'Public MD',
    'MOB_PRIVATE_LD':  'Private LD',
    'MOB_PUBLIC_LD':   'Public LD',
    'MOB_PRIVATE_ELD': 'Private ELD',
    'MOB_PUBLIC_ELD':  'Public ELD',
    'MOB_FREIGHT_SD':  'Freight SD',
    'MOB_FREIGHT_MD':  'Freight MD',
    'MOB_FREIGHT_LD':  'Freight LD',
    'MOB_FREIGHT_ELD': 'Freight ELD',
}
MOB_LAYER_UNITS = {
    'MOB_PRIVATE_SD':  'Mpkm/y',
    'MOB_PUBLIC_SD':   'Mpkm/y',
    'MOB_PRIVATE_MD':  'Mpkm/y',
    'MOB_PUBLIC_MD':   'Mpkm/y',
    'MOB_PRIVATE_LD':  'Mpkm/y',
    'MOB_PUBLIC_LD':   'Mpkm/y',
    'MOB_PRIVATE_ELD': 'Mpkm/y',
    'MOB_PUBLIC_ELD':  'Mpkm/y',
    'MOB_FREIGHT_SD':  'Mtkm/y',
    'MOB_FREIGHT_MD':  'Mtkm/y',
    'MOB_FREIGHT_LD':  'Mtkm/y',
    'MOB_FREIGHT_ELD': 'Mtkm/y',
}


# ===========================================================================
# HELPERS
# ===========================================================================

# ---------------------------------------------------------------------------
# Color utils
# ---------------------------------------------------------------------------

_PALETTE = (
    pc.qualitative.Vivid + pc.qualitative.Bold + pc.qualitative.Safe +
    pc.qualitative.Pastel + pc.qualitative.Dark2 + pc.qualitative.Set1
)

_FIXED_COLORS = {
    'HYDRO_DAM':   '#1f77b4',   # blue
    'RES_HYDRO':   '#1f77b4',   # blue
    'NG_EHP':      '#ff7f0e',   # orange
}

def _tech_color(name):
    """Deterministic color for a tech/resource name — same name → same color always."""
    if name in _FIXED_COLORS:
        return _FIXED_COLORS[name]
    return _PALETTE[hash(name) % len(_PALETTE)]

CATEGORY_RULES = [
    ('MOB_PUBLIC',       ['TRAMWAY','TROLLEY','BUS_CNG','BUS_EV','BUS_FC',
                          'BUS_BIODIESEL','BUS_CSNG','BUS_GASOLINE','BUS_DIESEL',
                          'BUS_HY','BUS_PROPANE','TRAIN_PUB','METRO']),
    ('MOB_PRIVATE',      ['CAR_']),
    ('MOB_FREIGHT',      ['TRUCK_','BOAT_','BULK_','CONTAINER_','TANKER_',
                          'TRAIN_FREIGHT','MOB_FREIGHT']),
    ('ELECTRICITY',      ['PV','WIND','HYDRO','NUCLEAR','CCGT','GEOTHERMAL',
                          'BIOMASS_GAS','BIOGAS','TIDAL','WAVE']),
    ('HEAT_LOW_T_DHN',   ['DHN_']),
    ('HEAT_LOW_T_DECEN', ['DEC_']),
    ('HEAT_HIGH_T',      ['IND_']),
    ('STORAGE',          ['BATTERY','BATT','TS_','_STORAGE','_STO','PHS',
                          'SEASONAL_','BEV_BATT','PHEV_BATT']),
    ('H2',               ['ELECTROLYSIS','SMR','ATR','H2_']),
    ('INFRASTRUCTURE',   ['GRID_','NETWORK_','PIPE_','GASIFICATION']),
]

CATEGORY_COLORS = {
    'MOB_PRIVATE':       '#636EFA',
    'MOB_PUBLIC':        '#19D3F3',
    'MOB_FREIGHT':       '#AB63FA',
    'ELECTRICITY':       '#FFA15A',
    'HEAT_LOW_T_DHN':    '#EF553B',
    'HEAT_LOW_T_DECEN':  '#FF6692',
    'HEAT_HIGH_T':       '#B6E880',
    'STORAGE':           '#FECB52',
    'H2':                '#00CC96',
    'INFRASTRUCTURE':    '#BAB0AC',
    'OTHER':             '#D3D3D3',
}


def _categorise(tech_name):
    tech_upper = str(tech_name).upper()
    for cat, keywords in CATEGORY_RULES:
        for kw in keywords:
            if kw.upper() in tech_upper:
                return cat
    return 'OTHER'

def _year_label(y):
    return str(y).replace('YEAR_', '')

def _reset(df):
    out = df.copy().reset_index()
    out.columns = [str(c) for c in out.columns]
    return out

def _years_col(df):
    for col in df.columns:
        sample = df[col].dropna()
        if not sample.empty and str(sample.iloc[0]).startswith('YEAR_'):
            return col
    return None

def _val_col(df, exclude):
    for col in df.columns:
        if col not in exclude and pd.api.types.is_numeric_dtype(df[col]):
            return col
    return None

def _save(fig, outdir, filename):
    os.makedirs(outdir, exist_ok=True)
    path = os.path.join(outdir, filename)
    html = fig.to_html(full_html=True, include_plotlyjs=True)
    try:
        page_title = fig.layout.title.text or filename.replace('.html', '')
    except Exception:
        page_title = filename.replace('.html', '')
    html = html.replace(
        '<head><meta charset="utf-8" /></head>',
        f'<head><meta charset="utf-8" /><title>{page_title}</title></head>',
        1)
    with open(path, 'w', encoding='utf-8') as f:
        f.write(html)
    print(f"  Saved: {path}")
    if SHOW:
        pio.show(fig)


# ===========================================================================
# LOAD
# ===========================================================================

def load_results(case_study):
    pkl_path = os.path.join(OUT_DIR, case_study, '_Results.pkl')
    if not os.path.exists(pkl_path):
        raise FileNotFoundError(f"Not found: {pkl_path}")
    with open(pkl_path, 'rb') as f:
        results = pickle.load(f)
    print(f"Loaded: {pkl_path}")
    print(f"  Keys: {[k for k in results if results[k] is not None]}")
    return results


# ===========================================================================
# INITIAL CONFIGURATION (2015_2020)
# ===========================================================================

def plot_initial_config(results, outdir, case_study):
    """Generate 00_* plots showing the 2020 starting configuration."""

    # Group definitions: (suffix, category filter, y-axis label override or None)
    GROUPS = [
        ('energy',     lambda c: not c.startswith('MOB_'),          None),
        ('passenger',  lambda c: c in ('MOB_PRIVATE', 'MOB_PUBLIC'), 'Mpkm/h'),
        ('freight',    lambda c: c == 'MOB_FREIGHT',                 'Mtkm/h'),
    ]

    def _stacked_bar_fig(df_in, cat_col, tech_col, val_col, title, yaxis):
        fig = go.Figure()
        for cat in sorted(df_in[cat_col].unique()):
            sub = df_in[df_in[cat_col] == cat]
            for _, row in sub.iterrows():
                fig.add_bar(x=[cat], y=[row[val_col]], name=row[tech_col],
                            marker_color=_tech_color(row[tech_col]),
                            legendgroup=cat, showlegend=True)
        fig.update_layout(title=title, barmode='stack',
                          xaxis_title=cat_col, yaxis_title=yaxis,
                          legend=dict(x=1.01, y=1, xanchor='left'))
        return fig

    # --- 00a: Installed capacity (F_Mult YEAR_2020) by category ---
    fm = results.get('F_Mult')
    if fm is not None:
        df = fm.copy().reset_index()
        df.columns = ['Years', 'Technologies', 'F_Mult']
        df = df[df['Years'] == 'YEAR_2020'].copy()
        df['F_Mult'] = pd.to_numeric(df['F_Mult'], errors='coerce').fillna(0)
        df['Category'] = df['Technologies'].apply(_fnew_category)
        df = _apply_mob_dist(df)
        df_cat = df.groupby(['Category', 'Technologies'])['F_Mult'].sum().reset_index()
        df_cat = df_cat[df_cat['F_Mult'] > 0.01]

        for gname, gfilter, ylabel in GROUPS:
            sub = df_cat[df_cat['Category'].apply(gfilter)]
            if sub.empty: continue
            unit_a = ylabel or 'GW'
            fig = _stacked_bar_fig(sub, 'Category', 'Technologies', 'F_Mult',
                                   f'{case_study} — Initial installed capacity 2020 [{gname}] [{unit_a}]',
                                   unit_a)
            _save(fig, outdir, f'00a_Init_capacity_{gname}.html')

    # --- 00b: Annual production YEAR_2020 by category ---
    ap = results.get('Annual_Prod')
    if ap is not None:
        df = ap.copy().reset_index()
        df.columns = ['Years', 'Technologies', 'Annual_Prod']
        df = df[df['Years'] == 'YEAR_2020'].copy()
        df['Annual_Prod'] = pd.to_numeric(df['Annual_Prod'], errors='coerce').fillna(0) / 1000
        df['Category'] = df['Technologies'].apply(_fnew_category)
        df = _apply_mob_dist(df)
        df = df.groupby(['Years', 'Category', 'Technologies'])['Annual_Prod'].sum().reset_index()
        df = df[df['Annual_Prod'] > 0.01]

        for gname, gfilter, ylabel in GROUPS:
            sub = df[df['Category'].apply(gfilter)]
            if sub.empty: continue
            unit = 'Mpkm/y' if gname == 'passenger' else ('Mtkm/y' if gname == 'freight' else 'TWh/y')
            fig = _stacked_bar_fig(sub, 'Category', 'Technologies', 'Annual_Prod',
                                   f'{case_study} — Initial annual production 2020 [{gname}] [{unit}]',
                                   unit)
            _save(fig, outdir, f'00b_Init_annual_prod_{gname}.html')

    # --- 00c: CAPEX breakdown for 2015_2020 phase ---
    ci = results.get('C_inv_phase_tech')
    if ci is not None:
        df = ci.copy().reset_index()
        df.columns = ['Phases', 'Technologies', 'C_inv']
        df = df[df['Phases'] == INIT_PHASE].copy()
        df['C_inv'] = pd.to_numeric(df['C_inv'], errors='coerce').fillna(0) / 1000
        df['Category'] = df['Technologies'].apply(_fnew_category)
        df = _apply_mob_dist(df)
        df = df.groupby(['Phases', 'Category', 'Technologies'])['C_inv'].sum().reset_index()
        df = df[df['C_inv'] > 0.0001]

        fig = _stacked_bar_fig(df, 'Category', 'Technologies', 'C_inv',
                               f'{case_study} — Initial CAPEX 2015–2020 [B$CAD]',
                               'B$CAD')
        _save(fig, outdir, '00c_Init_capex.html')

    # --- 00d: Resources used in YEAR_2020 ---
    res_df = results.get('Resources')
    if res_df is not None:
        df = res_df.copy().reset_index()
        df.columns = [str(c) for c in df.columns]
        yr_col  = _years_col(df)
        val_col = _val_col(df, {yr_col, df.columns[1]})
        res_col = [c for c in df.columns if c not in (yr_col, val_col)][0] if yr_col else None
        if yr_col and val_col:
            df = df[df[yr_col] == 'YEAR_2020'].copy()
            df[val_col] = pd.to_numeric(df[val_col], errors='coerce').fillna(0)
            df = df[df[val_col] > 0.01]
            fig = go.Figure()
            fig.add_bar(x=df[df.columns[1]], y=df[val_col] / 1000,
                        marker_color='steelblue')
            fig.update_layout(
                title=f'{case_study} — Resources used 2020 [TWh/y]',
                xaxis_title='Resource', yaxis_title='TWh/y',
            )
            _save(fig, outdir, '00d_Init_resources.html')


# ---------------------------------------------------------------------------
# CO2 SANKEY — shared node colours (used by plot_sankey_co2 and plot_sankey_carbon_full)
# ---------------------------------------------------------------------------
_CO2_NODE_COLORS = {
    'CO2_E':              '#87CEEB',
    'DAC':                '#2d6a4f',
    'Biomass sequest.':   '#228B22',
    'CO2_A':              '#DAA520',
    'CO2_C':              '#1a7a4a',
    'CO2_S':              '#4a4a6a',
    'Transport':          '#636EFA',
    'Elec. import':       '#FFD700',
    'H2 prod.':           '#00BFFF',
    'Ind. combustion':    '#FF7F0E',
    'Biofuel conv.':      '#6ab04c',
    'Buildings':          '#FF6692',
    'CCS (fugitive)':     '#b5b5b5',
    'Other emitters':     '#AAAAAA',
    'Methanation':        '#9932CC',
    'CO2-to-diesel':      '#8B4513',
    'Methanol synth.':    '#FF69B4',
    'Biomethanol synth.': '#e88fbd',
    'CO2 utiliz.':        '#badc58',
    'Net CO2 emiss.':     '#FF4040',
    'Net CO2 remov.':     '#228B22',
}

# ---------------------------------------------------------------------------
# GWP TRAJECTORY
# ---------------------------------------------------------------------------

def plot_gwp(results, outdir, case_study):
    key = 'TotalGwp'
    if results.get(key) is None:
        print(f"[SKIP] {key} not in results"); return

    df = results[key].copy().reset_index()
    df.columns = [str(c) for c in df.columns]
    year_col = df.columns[0]
    df['Year'] = df[year_col].str.replace('YEAR_', '').astype(int)
    df = df[df['Year'].isin([int(y) for y in YEARS_ORDER])].sort_values('Year')
    df['GWP_Mt']   = pd.to_numeric(df.get('TotalGWP',  df.iloc[:,1]), errors='coerce') / 1000
    df['Limit_Mt'] = pd.to_numeric(df.get('Gwp_limit', df.get('gwp_limit')), errors='coerce') / 1000

    fig = go.Figure()
    fig.add_bar(x=df['Year'], y=df['GWP_Mt'], name='GWP', marker_color='steelblue')
    if df['Limit_Mt'].notna().any():
        fig.add_scatter(x=df['Year'], y=df['Limit_Mt'], mode='lines+markers',
                        name='GWP limit', line=dict(color='red', dash='dash'))
    fig.update_layout(
        title=f'{case_study} — Annual GHG emissions [MtCO2-eq/y]',
        xaxis=dict(title='Year', type='linear', dtick=5),
        yaxis_title='MtCO2-eq/y',
    )
    _save(fig, outdir, '0_GWP.html')


# ---------------------------------------------------------------------------
# TOTAL TRANSITION COST
# ---------------------------------------------------------------------------

def plot_transition_cost(results, outdir, case_study):
    tc  = results.get('Transition_cost')
    cap = results.get('C_tot_capex')
    op  = results.get('C_tot_opex')
    if tc is None:
        print('[SKIP] Transition_cost not in results'); return

    def _prep(df):
        d = df.copy().reset_index()
        d.columns = [str(c) for c in d.columns]
        d['Year'] = d.iloc[:, 0].str.replace('YEAR_', '').astype(int)
        d = d[d['Year'].isin([int(y) for y in YEARS_ORDER])].sort_values('Year')
        d['val'] = pd.to_numeric(d.iloc[:, 1], errors='coerce') / 1000  # M$ → B$
        return d.set_index('Year')['val']

    tc_s  = _prep(tc)
    years = tc_s.index.tolist()
    if cap is not None:
        cap_s = _prep(cap)
    if op is not None:
        op_s = _prep(op)

    fig = go.Figure()
    if cap is not None:
        fig.add_bar(x=years, y=cap_s.reindex(years).fillna(0).tolist(),
                    name='CAPEX (cumul.)', marker_color='#EF553B')
    if op is not None:
        fig.add_bar(x=years, y=op_s.reindex(years).fillna(0).tolist(),
                    name='OPEX (cumul.)', marker_color='#636EFA')
    fig.add_scatter(x=years, y=tc_s.tolist(), mode='lines+markers',
                    name='Total transition cost', line=dict(color='black', width=2))
    final = tc_s.iloc[-1] if not tc_s.empty else None
    title_suffix = f'  |  Total = {final:.1f} B$CAD' if final else ''
    fig.update_layout(
        title=f'{case_study} — Cumulative transition cost [B$CAD]{title_suffix}',
        xaxis=dict(title='Year', type='linear', dtick=5),
        yaxis_title='B$CAD',
        barmode='stack',
    )
    _save(fig, outdir, '0b_Transition_cost.html')


# ===========================================================================
# PLOTS
# ===========================================================================

def _drilldown_html(case_study, title, filename, outdir,
                    df_cat, df_tech, phases, value_col, cat_col, tech_col,
                    sub_tech_data=None):
    """
    Generate a self-contained HTML with two or three Plotly charts:
      - Top: stacked bars by category
      - Middle: stacked bars by individual tech, updated on legend click above
      - Bottom (optional): stacked bars by sub-tech (e.g. distance variants),
        updated on legend click on middle chart
    df_cat  : aggregated  [Phases, Category, value_col]
    df_tech : tech-level  [Phases, tech_col, Category, value_col]
    sub_tech_data : dict {tech_name: [{plotly trace dict}, ...]} for 3rd level
    """
    has_sub = bool(sub_tech_data)

    cats = (df_cat.groupby(cat_col)[value_col].sum()
            .sort_values(ascending=False).index.tolist())

    # --- category traces ---
    cat_traces = []
    for cat in cats:
        sub = (df_cat[df_cat[cat_col] == cat]
               .set_index('Phases').reindex(phases)[value_col].fillna(0))
        cat_traces.append({
            'type': 'bar', 'name': cat,
            'x': phases, 'y': sub.tolist(),
            'marker': {'color': CATEGORY_COLORS.get(cat, '#D3D3D3')},
            'customdata': [cat] * len(phases),
        })

    # --- tech traces per category ---
    tech_by_cat = {}
    for cat in cats:
        sub = df_tech[df_tech[cat_col] == cat]
        techs = (sub.groupby(tech_col)[value_col].sum()
                 .sort_values(ascending=False).index.tolist())
        traces = []
        for tech in techs:
            vals = (sub[sub[tech_col] == tech]
                    .groupby('Phases')[value_col].sum()
                    .reindex(phases).fillna(0))
            if vals.abs().sum() < 1e-6:
                continue
            traces.append({
                'type': 'bar', 'name': tech,
                'x': phases, 'y': vals.tolist(),
                'marker': {'color': _tech_color(tech)},
            })
        tech_by_cat[cat] = traces

    cat_layout = {
        'title': title + '  <i>(click a legend item to drill down)</i>',
        'barmode': 'stack', 'hovermode': 'x unified',
        'xaxis': {'title': 'Phase'}, 'yaxis': {'title': 'B$CAD'},
        'height': 420,
    }
    detail_note = '  <i>(click a technology for distance variants)</i>' if has_sub else ''
    detail_layout = {
        'title': 'Detail — click a category above' + detail_note,
        'barmode': 'stack', 'hovermode': 'x unified',
        'xaxis': {'title': 'Phase'}, 'yaxis': {'title': 'B$CAD'},
        'height': 420,
    }
    sub_layout = {
        'title': 'Distance variants — click a technology above',
        'barmode': 'stack', 'hovermode': 'x unified',
        'xaxis': {'title': 'Phase'}, 'yaxis': {'title': 'B$CAD'},
        'height': 420,
    }

    sub_div = '<div id="chart-sub" style="width:100%;display:none"></div>' if has_sub else ''

    if has_sub:
        sub_js = f"""
var subTechData = {json.dumps(sub_tech_data)};
var subLayout = {json.dumps(sub_layout)};
Plotly.newPlot('chart-sub', [], subLayout);
document.getElementById('chart-detail').on('plotly_legendclick', function(data) {{
    var tech = data.data[data.curveNumber].name;
    var traces = subTechData[tech] || [];
    var subEl = document.getElementById('chart-sub');
    if (traces.length > 0) {{
        subEl.style.display = 'block';
        Plotly.react('chart-sub', traces, Object.assign({{}}, subLayout, {{title: 'Distance variants — ' + tech}}));
    }} else {{
        subEl.style.display = 'none';
    }}
    return false;
}});"""
    else:
        sub_js = ''

    html = f"""<!DOCTYPE html><html><head><meta charset="utf-8">
<title>{case_study} — {title}</title>
<script src="https://cdn.plot.ly/plotly-latest.min.js"></script>
</head><body>
<div id="chart-cat" style="width:100%"></div>
<div id="chart-detail" style="width:100%"></div>
{sub_div}
<script>
var techData = {json.dumps(tech_by_cat)};
var catLayout = {json.dumps(cat_layout)};
var detailLayout = {json.dumps(detail_layout)};
Plotly.newPlot('chart-cat', {json.dumps(cat_traces)}, catLayout);
Plotly.newPlot('chart-detail', [], detailLayout);
var selectedCat = null;
document.getElementById('chart-cat').on('plotly_legendclick', function(data) {{
    var cat = data.data[data.curveNumber].name;
    if (cat === selectedCat) {{
        selectedCat = null;
        Plotly.react('chart-detail', [], Object.assign({{}}, detailLayout, {{title: 'Detail — click a legend item above'}}));
    }} else {{
        selectedCat = cat;
        var traces = techData[cat] || [];
        Plotly.react('chart-detail', traces, Object.assign({{}}, detailLayout, {{title: 'Detail — ' + cat}}));
    }}
    return false;
}});
{sub_js}
</script></body></html>"""

    path = os.path.join(outdir, filename)
    with open(path, 'w', encoding='utf-8') as f:
        f.write(html)
    print(f"  Saved: {path}")


def _parse_mob_base_to_variants(dat_file):
    """Parse MODELS_OF_TECHNOLOGIES_OF_*_ALL_DISTANCES from QC_data.dat.
    Returns {base_tech: [variant1, variant2, ...]}."""
    mob_maps = {}
    pat = re.compile(
        r'set MODELS_OF_TECHNOLOGIES_OF_\w+_ALL_DISTANCES\s*\["(\w+)"\]\s*:=(.*?);',
        re.DOTALL
    )
    with open(dat_file, encoding='utf-8', errors='replace') as f:
        content = ''.join(line for line in f if not line.lstrip().startswith('#'))
    for m in pat.finditer(content):
        base = m.group(1)
        variants = re.findall(r'\b([A-Z][A-Z0-9_]+)\b', m.group(2))
        mob_maps[base] = variants
    return mob_maps


def plot_capex_breakdown(results, outdir, case_study):
    key = 'C_inv_phase_tech'
    if results.get(key) is None:
        print(f'[SKIP] {key} not in results'); return

    df = results[key].copy().reset_index()
    df.columns = ['Phases', 'Technologies', 'C_inv']
    df['C_inv'] = pd.to_numeric(df['C_inv'], errors='coerce').fillna(0) / 1000
    df['Phases'] = df['Phases'].astype(str)
    df = df[df['Phases'] != INIT_PHASE]
    df['Category'] = df['Technologies'].apply(_fnew_category)
    phases = [p for p in TRANS_PHASES if p in df['Phases'].unique()]

    # Build 3rd-level sub-tech data: split base mob tech C_inv proportionally
    # by F_Mult of each distance variant at the phase start year.
    sub_tech_data = {}
    f_mult_raw = results.get('F_Mult')
    dat_file = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                            '..', '..', '..', 'shared', 'data', 'QC_data.dat')
    if f_mult_raw is not None and os.path.exists(dat_file):
        mob_maps = _parse_mob_base_to_variants(dat_file)
        fm = f_mult_raw.reset_index()
        fm.columns = ['Years', 'Technologies', 'F_Mult']
        fm['F_Mult'] = pd.to_numeric(fm['F_Mult'], errors='coerce').fillna(0)

        for base, variants in mob_maps.items():
            if not variants:
                continue
            base_rows = df[df['Technologies'] == base]
            if base_rows['C_inv'].abs().sum() < 1e-9:
                continue

            base_cinv = base_rows.set_index('Phases')['C_inv']
            traces = []
            for variant in variants:
                series = []
                for phase in phases:
                    start_year = 'YEAR_' + phase.split('_')[0]
                    year_fm = fm[fm['Years'] == start_year]
                    var_shares = {}
                    for v in variants:
                        row = year_fm[year_fm['Technologies'] == v]['F_Mult']
                        var_shares[v] = float(row.values[0]) if len(row) > 0 else 0.0
                    total = sum(var_shares.values())
                    share = var_shares.get(variant, 0.0) / total if total > 0 else 1.0 / len(variants)
                    series.append(float(base_cinv.get(phase, 0.0)) * share)

                if sum(abs(v) for v in series) < 1e-9:
                    continue
                traces.append({
                    'type': 'bar', 'name': variant,
                    'x': phases, 'y': series,
                    'marker': {'color': _tech_color(variant)},
                })
            if traces:
                sub_tech_data[base] = traces

    df_cat = df.groupby(['Phases', 'Category'])['C_inv'].sum().reset_index()
    _drilldown_html(
        case_study,
        title=f'{case_study} — CAPEX breakdown [B$CAD/phase]',
        filename='1b_CAPEX_breakdown.html',
        outdir=outdir,
        df_cat=df_cat, df_tech=df,
        phases=phases, value_col='C_inv', cat_col='Category', tech_col='Technologies',
        sub_tech_data=sub_tech_data if sub_tech_data else None,
    )


def plot_opex_breakdown(results, outdir, case_study):
    frames = []
    op_tech = results.get('C_op_phase_tech')
    op_res  = results.get('C_op_phase_res')
    if op_tech is None and op_res is None:
        print('[SKIP] C_op_phase_tech and C_op_phase_res not in results'); return

    if op_tech is not None:
        d = op_tech.copy().reset_index()
        d.columns = ['Phases', 'Label', 'C_op']
        d['Category'] = d['Label'].apply(_fnew_category)
        frames.append(d)
    if op_res is not None:
        d = op_res.copy().reset_index()
        d.columns = ['Phases', 'Label', 'C_op']
        d['Category'] = 'RESOURCES'
        frames.append(d)

    df = pd.concat(frames, ignore_index=True)
    df['C_op'] = pd.to_numeric(df['C_op'], errors='coerce').fillna(0) / 1000
    df['Phases'] = df['Phases'].astype(str)
    df = df[df['Phases'] != INIT_PHASE]
    phases = [p for p in TRANS_PHASES if p in df['Phases'].unique()]
    df_cat = df.groupby(['Phases', 'Category'])['C_op'].sum().reset_index()
    _drilldown_html(
        case_study,
        title=f'{case_study} — OPEX breakdown [B$CAD/phase]',
        filename='1c_OPEX_breakdown.html',
        outdir=outdir,
        df_cat=df_cat, df_tech=df,
        phases=phases, value_col='C_op', cat_col='Category', tech_col='Label',
    )


def plot_total_cost_breakdown(results, outdir, case_study):
    frames = []
    capex   = results.get('C_inv_phase_tech')
    op_tech = results.get('C_op_phase_tech')
    op_res  = results.get('C_op_phase_res')

    if capex is not None:
        d = capex.copy().reset_index()
        d.columns = ['Phases', 'Label', 'Cost']
        d['Category'] = d['Label'].apply(_fnew_category)
        frames.append(d)
    if op_tech is not None:
        d = op_tech.copy().reset_index()
        d.columns = ['Phases', 'Label', 'Cost']
        d['Category'] = d['Label'].apply(_fnew_category)
        frames.append(d)
    if op_res is not None:
        d = op_res.copy().reset_index()
        d.columns = ['Phases', 'Label', 'Cost']
        d['Category'] = 'RESOURCES'
        frames.append(d)

    if not frames:
        print('[SKIP] No cost data for total breakdown'); return

    df = pd.concat(frames, ignore_index=True)
    df['Cost'] = pd.to_numeric(df['Cost'], errors='coerce').fillna(0) / 1000
    df['Phases'] = df['Phases'].astype(str)
    df = df[df['Phases'] != INIT_PHASE]
    phases = [p for p in TRANS_PHASES if p in df['Phases'].unique()]
    df_cat = df.groupby(['Phases', 'Category'])['Cost'].sum().reset_index()
    _drilldown_html(
        case_study,
        title=f'{case_study} — Total cost (CAPEX+OPEX) [B$CAD/phase]',
        filename='1d_Total_cost_breakdown.html',
        outdir=outdir,
        df_cat=df_cat, df_tech=df,
        phases=phases, value_col='Cost', cat_col='Category', tech_col='Label',
    )


# ---------------------------------------------------------------------------
# PRIMARY RESOURCES — stacked area
# ---------------------------------------------------------------------------

def plot_resources(results, outdir, case_study):
    key = 'Resources'
    if results.get(key) is None:
        print(f"[SKIP] {key} not in results"); return

    df = results[key].copy().reset_index()
    df.columns = [str(c) for c in df.columns]
    year_col = df.columns[0]
    res_col  = df.columns[1]
    val_col  = df.columns[2]

    df['Year'] = df[year_col].str.replace('YEAR_', '').astype(int)
    df = df[df['Year'].isin([int(y) for y in YEARS_ORDER])]
    df[val_col] = pd.to_numeric(df[val_col], errors='coerce').fillna(0)
    df['TWh'] = df[val_col] / 1000

    years = _to_int_years(df['Year'].unique())
    resources = df.groupby(res_col)['TWh'].sum()
    resources = resources[resources > 0].sort_values(ascending=False).index.tolist()

    fig = go.Figure()
    for idx, res in enumerate(resources):
        sub = df[df[res_col] == res].set_index('Year').reindex(years)
        fig.add_trace(go.Scatter(
            x=years, y=sub['TWh'].fillna(0).tolist(),
            name=res, stackgroup='one', mode='none',
            fillcolor=_tech_color(res),
            line=dict(width=0),
        ))

    fig.update_layout(
        title=f'{case_study} — Primary energy supply [TWh/y]',
        xaxis=dict(title='Year', type='linear', dtick=5),
        yaxis_title='TWh/y',
        hovermode='x unified',
    )
    _save(fig, outdir, '4_Resources.html')


# ---------------------------------------------------------------------------
# ANNUAL & MONTHLY PRODUCTION
# ---------------------------------------------------------------------------

def _prod_fig(df_cat, x_vals, x_col, y_col, title, use_bars=False, series_col='Technologies', y_label=None):
    """Stacked area (annual) or relative bar (monthly) production plot per tech."""
    active = df_cat.groupby(series_col)[y_col].apply(lambda s: s.abs().sum())
    active_techs = active[active > 0].sort_values(ascending=False).index.tolist()
    fig = go.Figure()
    for tech in active_techs:
        vals = df_cat[df_cat[series_col] == tech].set_index(x_col).reindex(x_vals)[y_col].fillna(0)
        color = _tech_color(tech)
        if use_bars:
            fig.add_trace(go.Bar(
                x=x_vals, y=vals.tolist(), name=tech,
                marker_color=color,
            ))
        else:
            fig.add_trace(go.Scatter(
                x=x_vals, y=vals.tolist(), name=tech,
                stackgroup='one', mode='none',
                fillcolor=color, line=dict(width=0),
            ))
    # use linear axis when x values are integers (years), categorical otherwise (months)
    x_is_numeric = x_vals and isinstance(x_vals[0], (int, float))
    layout = dict(title=title, yaxis_title=y_label if y_label else y_col, hovermode='x unified',
                  xaxis=dict(title=x_col, type='linear', dtick=5) if x_is_numeric
                        else dict(title=x_col))
    if use_bars:
        layout['barmode'] = 'relative'
    fig.update_layout(**layout)
    return fig, bool(active_techs)


def plot_annual_prod(results, outdir, case_study):
    key = 'Annual_Prod'
    if results.get(key) is None:
        print(f"[SKIP] {key} not in results"); return

    df = results[key].copy().reset_index()
    df.columns = ['Years', 'Technologies', 'TWh']
    df = df[~df['Technologies'].str.contains('_EXP_|TRAFO_|DEC_TH_STORAGE|LT_DEC_WH|_STO|STO_|_COMP_',na=False)]
    df['Year'] = df['Years'].str.replace('YEAR_', '').astype(int)
    df = df[df['Year'].isin([int(y) for y in YEARS_ORDER])]
    df['TWh'] = pd.to_numeric(df['TWh'], errors='coerce').fillna(0) / 1000
    df['Category'] = df['Technologies'].apply(_fnew_category)
    years = _to_int_years(df['Year'].unique())

    for cat in sorted(df['Category'].unique()):
        sub = df[df['Category'] == cat].copy()
        if cat.startswith('MOB_'):
            if SHOW_DISTANCE_VARIANTS:
                sub = sub[sub['Technologies'].str.contains(_DIST_RE)].copy()
            else:
                sub['Technologies'] = sub['Technologies'].apply(_strip_dist)
                sub = sub.groupby(['Years', 'Technologies', 'Year', 'Category'], as_index=False)['TWh'].sum()
        unit = 'Mton CO2/y' if cat == 'CO2' else (_mob_unit(cat) or 'TWh/y')
        fig, has_data = _prod_fig(sub, years, 'Year', 'TWh',
                                   f'{case_study} — Annual prod [{cat}] [{unit}]',
                                   y_label=unit)
        if has_data:
            _save(fig, outdir, f'5_Annual_prod_{cat}.html')


def plot_monthly_prod(results, outdir, case_study):
    key = 'Monthly_Prod'
    if results.get(key) is None:
        print(f"[SKIP] {key} not in results"); return

    df = results[key].copy().reset_index()
    df.columns = ['Years', 'Technologies', 'Periods', 'GWh']
    df = df[~df['Technologies'].str.contains('DEC_TH_STORAGE|LT_DEC_WH|TRAFO_',na=False)]
    df['Year'] = df['Years'].str.replace('YEAR_', '')
    df['GWh'] = pd.to_numeric(df['GWh'], errors='coerce').fillna(0)/1000
    df['Month'] = df['Periods'].apply(lambda p: MONTH_LABELS[int(p) - 1])
    df['Category'] = df['Technologies'].apply(_fnew_category)
    # CO2_STO / STO_CO2 Monthly_Prod is in kt CO₂, not GWh — exclude from energy plots
    df = df[~df['Technologies'].str.upper().isin(['CO2_STO', 'STO_CO2'])]

    for year in [y for y in YEARS_ORDER if y in df['Year'].unique()]:
        for cat in sorted(df['Category'].unique()):
            sub = df[(df['Year'] == year) & (df['Category'] == cat)].copy()
            if cat.startswith('MOB_'):
                if SHOW_DISTANCE_VARIANTS:
                    sub = sub[sub['Technologies'].str.contains(_DIST_RE)].copy()
                else:
                    sub['Technologies'] = sub['Technologies'].apply(_strip_dist)
                    sub = sub.groupby(['Years', 'Technologies', 'Periods', 'Year', 'Month', 'Category'], as_index=False)['GWh'].sum()
            unit = 'Mton CO2' if cat == 'CO2' else (_mob_unit(cat, 'month') or 'TWh')
            fig, has_data = _prod_fig(sub, MONTH_LABELS, 'Month', 'GWh',
                                       f'{case_study} — Monthly prod {year} [{cat}] [{unit}]',
                                       use_bars=True, y_label=unit)
            if has_data:
                _save(fig, outdir, f'6_Monthly_prod_{year}_{cat}.html')


def plot_monthly_resources(results, outdir, case_study):
    key = 'F_Mult_t_resources'
    if results.get(key) is None:
        print(f"[SKIP] {key} not in results"); return

    df = results[key].copy().reset_index()
    df.columns = ['Years', 'Resources', 'Periods', 'GWh']
    df['Year']  = df['Years'].str.replace('YEAR_', '')
    df['GWh']   = pd.to_numeric(df['GWh'], errors='coerce').fillna(0)
    # F_Mult_t is in GW; multiply by t_op [h] to get GWh, then /1000 for TWh
    df['t_op']  = df['Periods'].apply(lambda p: _T_OP[int(p)])
    df['TWh']   = df['GWh'] * df['t_op'] / 1000
    df['Month'] = df['Periods'].apply(lambda p: MONTH_LABELS[int(p) - 1])

    for year in [y for y in YEARS_ORDER if y in df['Year'].unique()]:
        sub = df[df['Year'] == year].copy()
        fig, has_data = _prod_fig(sub, MONTH_LABELS, 'Month', 'TWh',
                                   f'{case_study} — Monthly resource use {year} [TWh]',
                                   use_bars=True, series_col='Resources')
        if has_data:
            _save(fig, outdir, f'6b_Monthly_resources_{year}.html')


def plot_monthly_co2_storage(results, outdir, case_study):
    """Monthly CO2_S throughput in kt CO₂ (CO2_STO / STO_CO2).
    Monthly_Prod = F_Mult_t [kt/h] × t_op [h] → kt CO₂ per period."""
    key = 'Monthly_Prod'
    if results.get(key) is None:
        print(f'[SKIP] {key} not in results'); return

    df = results[key].copy().reset_index()
    df.columns = ['Years', 'Technologies', 'Periods', 'kt']
    df = df[df['Technologies'].str.upper().isin(['CO2_STO', 'STO_CO2'])]
    if df.empty:
        print('[SKIP] No CO2_STO / STO_CO2 in Monthly_Prod'); return

    df['Year']  = df['Years'].str.replace('YEAR_', '')
    df['kt']    = pd.to_numeric(df['kt'], errors='coerce').fillna(0)
    df['Month'] = df['Periods'].apply(lambda p: MONTH_LABELS[int(p) - 1])

    for year in [y for y in YEARS_ORDER if y in df['Year'].unique()]:
        sub = df[df['Year'] == year].copy()
        fig, has_data = _prod_fig(sub, MONTH_LABELS, 'Month', 'kt',
                                   f'{case_study} — Monthly CO2_S throughput {year} [kt CO₂]',
                                   use_bars=True)
        if has_data:
            _save(fig, outdir, f'6c_Monthly_CO2_storage_{year}.html')


# ---------------------------------------------------------------------------
# LOAD FACTOR HEATMAP (capacity utilisation per tech × month)
# ---------------------------------------------------------------------------

_STO_KEYWORDS  = ['BATTERY','BATT','TS_','_STORAGE','SEASONAL_','BEV_BATT',
                   'PHEV_BATT','PHS','HYDRO_STORAGE','MINES_STORAGE',
                   'STO_','_STO']
_MOB_KEYWORDS  = ['CAR_','SUV_','BUS_','TRUCK_','SEMI_','LCV_','TRAIN_',
                   'TRAMWAY','METRO','BOAT_','PLANE_','BULK_','CONTAINER',
                   'TANKER','COMMUTER','SCHOOLBUS','COACH_']

def _tech_group(tech):
    t = tech.upper()
    if any(k in t for k in _STO_KEYWORDS):  return 'storage'
    if any(k in t for k in _MOB_KEYWORDS):  return 'mobility'
    return 'standard'

_GROUP_META = {
    'standard': {'label': ' [Standard]', 'cap_unit': 'GW',       'suffix': '_standard'},
    'storage':  {'label': ' [Storage]',  'cap_unit': 'varies',   'suffix': '_storage'},
    'mobility': {'label': ' [Mobility]', 'cap_unit': 'Mpkm/h or Mtkm/h', 'suffix': '_mobility'},
}

def _sto_cap_unit(tech):
    """Return the capacity unit for a storage technology.

    Techs whose F_Mult is used as a storage LEVEL (GWh tank size):
      H2_STO/STO_H2, ELEC_STO/STO_ELEC, NG/SNG/DIE/GASO storages.
    Techs whose F_Mult is a power capacity (GW):
      Thermal daily storages (TH_STORAGE).
    """
    t = tech.upper()
    if 'CO2' in t:                                    return 'kt CO₂'
    if 'H2' in t:                                     return 'GWh'
    if 'ELEC' in t:                                   return 'GWh'
    if any(k in t for k in ('DIE', 'GASO', 'NG', 'SNG', 'BATT', 'PHS',
                             'HYDRO_STORAGE', 'MINES')):
                                                       return 'GWh'
    if any(k in t for k in ('TH_STORAGE', 'TH_STO')): return 'GW (th)'
    return 'GWh'

def _lf_heatmap(merged, fc, case_study, yr_label, group, outdir, prefix='7', note=''):
    meta = _GROUP_META[group]

    pivot = merged.pivot_table(index='Technologies', columns='Month',
                               values='LF', aggfunc='mean')
    pivot = pivot.reindex(columns=MONTH_LABELS)
    total = merged.groupby('Technologies')['F_Mult_t'].sum().sort_values(ascending=True)
    pivot = pivot.reindex(total.index)
    fc_sorted = fc.set_index('Technologies').reindex(total.index)['F_Mult']

    fig = make_subplots(rows=1, cols=2, column_widths=[0.72, 0.28],
                        shared_yaxes=True, horizontal_spacing=0.02)

    fig.add_trace(go.Heatmap(
        z=pivot.values, x=MONTH_LABELS, y=pivot.index.tolist(),
        colorscale='RdYlGn', zmin=0, zmax=100,
        colorbar=dict(title='Load factor %', len=0.8, x=1.02),
        hovertemplate='%{y}<br>%{x}: %{z:.1f}%<extra></extra>',
    ), row=1, col=1)

    if group == 'storage':
        units = [_sto_cap_unit(t) for t in fc_sorted.index]
        hover_texts = [f'{v:.2f} {u}' for v, u in zip(fc_sorted.values, units)]
        bar_labels  = [f'{v:.2f} {u}' for v, u in zip(fc_sorted.values, units)]
        cap_axis_title = 'Capacity (unit varies — see hover)'
    else:
        hover_texts = [f'{v:.2f} {meta["cap_unit"]}' for v in fc_sorted.values]
        bar_labels  = [f'{v:.2f}' for v in fc_sorted.values]
        cap_axis_title = f'{meta["cap_unit"]} (log scale)'

    fig.add_trace(go.Bar(
        x=fc_sorted.values, y=fc_sorted.index.tolist(),
        orientation='h', marker_color='steelblue',
        text=bar_labels,
        textposition='outside', cliponaxis=False,
        customdata=hover_texts,
        hovertemplate='%{y}: %{customdata}<extra></extra>',
        showlegend=False,
    ), row=1, col=2)

    title_text = f'{case_study} — Load factor & installed capacity {yr_label}{meta["label"]}'
    if note:
        title_text += f'<br><sup><i>{note}</i></sup>'
    fig.update_layout(
        title=dict(text=title_text, x=0.5),
        height=max(400, 22 * len(pivot)),
        xaxis2_title=cap_axis_title,
        margin=dict(r=220, t=80),
    )
    fig.update_xaxes(title_text='Month', row=1, col=1)
    fig.update_xaxes(type='log', row=1, col=2)
    _save(fig, outdir, f'{prefix}_Load_factor_{yr_label}{meta["suffix"]}.html')


def plot_load_factor_heatmap(results, outdir, case_study):
    fmt = results.get('F_Mult_t')
    fm  = results.get('F_Mult')
    if fmt is None or fm is None:
        print('[SKIP] F_Mult_t or F_Mult not in results'); return

    fmt_df = fmt.copy().reset_index()
    fmt_df.columns = ['Years', 'Technologies', 'Periods', 'F_Mult_t']
    fm_df  = fm.copy().reset_index()
    fm_df.columns  = ['Years', 'Technologies', 'F_Mult']

    for year in [f'YEAR_{y}' for y in YEARS_ORDER]:
        ft = fmt_df[fmt_df['Years'] == year].copy()
        fc = fm_df[fm_df['Years'] == year].copy()
        if ft.empty or fc.empty:
            continue

        fc = fc[fc['F_Mult'] > 0.01]
        ft = ft[ft['Technologies'].isin(fc['Technologies'])]

        merged = ft.merge(fc[['Technologies', 'F_Mult']], on='Technologies')
        merged['Group'] = merged['Technologies'].apply(_tech_group)

        # Storage LF calculation:
        # • GWh storages (F_Mult = tank size in GWh, F_Mult_t = power in GW):
        #   LF = |F_Mult_t| × t_op / F_Mult  → fraction of energy capacity cycled.
        #   Detected when max(|F_Mult_t|) / F_Mult < 0.01 (ratio < 0.01 h⁻¹).
        # • GW storages (F_Mult = power capacity in GW, F_Mult_t in GW):
        #   LF = F_Mult_t / F_Mult  → standard power utilisation.
        lf_vals = merged['F_Mult_t'].abs().copy()
        for tech in merged[merged['Group'] == 'storage']['Technologies'].unique():
            mask = merged['Technologies'] == tech
            peak = lf_vals[mask].max()
            cap  = merged.loc[mask, 'F_Mult'].iloc[0]
            if cap > 0 and (peak / cap) < 0.01:
                # GWh storage: use energy-fraction formula
                lf_vals[mask] = merged.loc[mask].apply(
                    lambda row: abs(row['F_Mult_t'])
                                * _T_OP.get(int(row['Periods']), 720)
                                / cap * 100,
                    axis=1,
                )
            else:
                lf_vals[mask] = lf_vals[mask] / cap * 100

        # Non-storage: standard GW / GW ratio
        non_sto = merged['Group'] != 'storage'
        lf_vals[non_sto] = (merged.loc[non_sto, 'F_Mult_t']
                            / merged.loc[non_sto, 'F_Mult'] * 100)
        merged['LF']    = lf_vals.clip(0, 100)
        merged['Month'] = merged['Periods'].apply(lambda p: MONTH_LABELS[int(p) - 1])
        fc['Group']     = fc['Technologies'].apply(_tech_group)

        yr_label = year.replace('YEAR_', '')
        for group in ['standard', 'storage', 'mobility']:
            m_grp = merged[merged['Group'] == group].copy()
            f_grp = fc[fc['Group'] == group].copy()
            if group == 'mobility':
                if SHOW_DISTANCE_VARIANTS:
                    m_grp = m_grp[m_grp['Technologies'].str.contains(_DIST_RE)]
                    f_grp = f_grp[f_grp['Technologies'].str.contains(_DIST_RE)]
                else:
                    m_grp = m_grp[~m_grp['Technologies'].str.contains(_DIST_RE)]
                    f_grp = f_grp[~f_grp['Technologies'].str.contains(_DIST_RE)]
            if m_grp.empty:
                continue
            note = (
                'GWh storages (H2, NG, diesel, gasoline…): LF = energy cycled / tank capacity. '
                'GW storages (thermal daily buffers): LF = power / rated power.'
            ) if group == 'storage' else ''
            _lf_heatmap(m_grp, f_grp, case_study, yr_label, group, outdir, note=note)


# ---------------------------------------------------------------------------
# MOBILITY MIX PIE CHARTS
# ---------------------------------------------------------------------------

def _mob_type(t):
    t = t.upper()
    if any(k in t for k in ['TRUCK_','SEMI_','LCV_','TRAIN_FREIGHT','BULK_CARRIER',
                              'CONTAINER','OIL_TANKER','PLANE_FREIGHT']):
        return 'FREIGHT'
    if any(k in t for k in ['CAR_','SUV_']):
        return 'PRIVATE'
    if any(k in t for k in ['BUS_','TRAMWAY','SCHOOLBUS_','COMMUTER_RAIL','COACH_',
                              'TRAIN_DIESEL','TRAIN_ELEC','TRAIN_H2_','TRAIN_NG_',
                              'TRAIN_SNG','TRAIN_BIODIESEL','PLANE_SH','PLANE_LH']):
        return 'PUBLIC'
    return None

def _mob_distance(t):
    t = t.upper()
    if t.endswith('_ELD'): return 'ELD'
    if t.endswith('_LD'):  return 'LD'
    if t.endswith('_MD'):  return 'MD'
    if t.endswith('_SD'):  return 'SD'
    return None

_DIST_RE = re.compile(r'_(SD|MD|LD|ELD)$', re.IGNORECASE)

def _strip_dist(t):
    if SHOW_DISTANCE_VARIANTS:
        return t
    return _DIST_RE.sub('', t)

def _apply_mob_dist(df):
    """Handle distance variant display for dataframes with 'Category' and 'Technologies' columns.
    SHOW_DISTANCE_VARIANTS=True  → keep suffixes, drop base techs (no _SD/_MD/_LD/_ELD)
    SHOW_DISTANCE_VARIANTS=False → strip suffixes, aggregate (original behaviour)
    """
    mob = df['Category'].str.startswith('MOB_')
    if SHOW_DISTANCE_VARIANTS:
        has_suffix = df['Technologies'].str.contains(_DIST_RE)
        return df[~mob | has_suffix].copy()
    df = df.copy()
    df.loc[mob, 'Technologies'] = df.loc[mob, 'Technologies'].apply(_strip_dist)
    return df

def _mob_unit(cat, time='y'):
    """Return the correct unit label for a mobility category (values are /1000 from raw)."""
    if cat == 'MOB_FREIGHT':
        return f'Gtkm/{time}'
    if cat in ('MOB_PRIVATE', 'MOB_PUBLIC'):
        return f'Gpkm/{time}'
    return None


def plot_mobility_pies(results, outdir, case_study):
    assets = results.get('Assets')
    if assets is None:
        print('[SKIP] Assets not in results'); return

    df = assets[['F_year']].copy().reset_index()
    df.columns = ['Years', 'Technologies', 'GWh']
    df['Year']     = df['Years'].str.replace('YEAR_', '')
    df['GWh']      = pd.to_numeric(df['GWh'], errors='coerce').fillna(0)
    df['MobType']  = df['Technologies'].apply(_mob_type)
    df['Distance'] = df['Technologies'].apply(_mob_distance)
    df['Label']    = df['Technologies'].apply(_strip_dist)
    df = df[df['MobType'].notna() & df['Distance'].notna() & (df['GWh'] > 1.0)]

    MOB_TYPES = ['PRIVATE', 'PUBLIC', 'FREIGHT']
    DISTANCES = ['SD', 'MD', 'LD', 'ELD']
    years = [y for y in YEARS_ORDER if y in df['Year'].unique()]

    for mob in MOB_TYPES:
        mob_unit = 'Mtkm/y' if mob == 'FREIGHT' else 'Mpkm/y'
        sub_mob = df[df['MobType'] == mob]
        active_dist = [d for d in DISTANCES if not sub_mob[sub_mob['Distance'] == d].empty]
        if not active_dist or not years:
            continue

        n_rows = len(active_dist)
        n_cols = len(years)
        specs = [[{'type': 'pie'}] * n_cols for _ in range(n_rows)]
        fig = make_subplots(
            rows=n_rows, cols=n_cols, specs=specs,
            row_titles=active_dist,
            column_titles=years,
            horizontal_spacing=0.04,
            vertical_spacing=0.08,
        )

        for r, dist in enumerate(active_dist, 1):
            for c, year in enumerate(years, 1):
                data = sub_mob[(sub_mob['Distance'] == dist) & (sub_mob['Year'] == year)]
                if data.empty:
                    continue
                fig.add_trace(go.Pie(
                    labels=data['Label'].tolist(),
                    values=data['GWh'].tolist(),
                    hole=0.35,
                    textposition='inside',
                    textinfo='percent',
                    marker_colors=[_tech_color(t) for t in data['Technologies'].tolist()],
                    hovertemplate='%{label}: %{value:.0f} ' + mob_unit + ' (%{percent})<extra></extra>',
                    showlegend=False,
                ), row=r, col=c)

        fig.update_layout(
            title=f'{case_study} — Mobility mix [{mob}]',
            height=max(300, 220 * n_rows),
        )
        _save(fig, outdir, f'8_Mobility_{mob}.html')


# ---------------------------------------------------------------------------
# F_NEW / F_OLD by category
# ---------------------------------------------------------------------------

# Order matters: first match wins
_FNEW_CAT_RULES = [
    ('HEAT_LOW_T',    ['DHN', 'DEC_']),
    ('HEAT_HIGH_T',   ['IND_BOILER', 'IND_COGEN', 'IND_DIRECT', 'IND_HP']),
    ('STORAGE',       ['HYDRO_STORAGE', 'BATTERY', 'TH_STORAGE', 'MINES_STORAGE',
                       'STO_DIE', 'STO_ELEC', 'STO_GASO', 'STO_H2', 'STO_NG', 'STO_SNG',
                       'DIE_STO', 'GASO_STO', 'ELEC_STO', 'H2_STO', 'NG_STO', 'SNG_STO']),
    ('CO2',           ['CO2_', 'DAC_', 'DEEP_SALINE', 'UNMINEABLE', 'EOR', 'DOGR',
                       'STO_CO2', 'CEMENT_PROD', 'CARBON_']),
    ('H2_SYNFUELS',   ['ELECTROLYSIS', 'SMR', 'ATR', 'BIOGAS_', 'BIOMASS_GAS',
                       'COAL_GAS', 'GASIFICATION', 'METHANATION', 'PYROLYSIS',
                       'REFORMING', 'H2_COMP', 'H2_EXP', 'NG_COMP', 'NG_EXP',
                       'SNG_COMP', 'SNG_EXP', 'FT', 'METATHESIS', 'CUMENE',
                       'METHANOL', 'ETHANOL_TO', 'CROPS_TO', 'ETHANE_', 'AN_DIG']),
    ('ELECTRICITY',   ['PV_', 'WIND_', 'HYDRO', 'NUCLEAR', 'CCGT', 'COAL_', 'OCGT_',
                       'TIDAL', 'GEOTHERMAL', 'AFC', 'PAFC', 'PEMFC', 'SOFC']),
    ('MOB_PRIVATE',   ['CAR_', 'SUV_']),
    ('MOB_PUBLIC',    ['BUS_', 'TRAMWAY', 'SCHOOLBUS_', 'COMMUTER_RAIL', 'COACH_',
                       'PLANE_SH', 'PLANE_LH', 'TRAIN_DIESEL', 'TRAIN_BIODIESEL',
                       'TRAIN_ELEC', 'TRAIN_H2', 'TRAIN_NG', 'TRAIN_SNG']),
    ('MOB_FREIGHT',   ['TRUCK_', 'SEMI_', 'LCV_', 'TRAIN_FREIGHT', 'BULK_CARRIER',
                       'CONTAINER', 'OIL_TANKER', 'PLANE_FREIGHT']),
    ('INFRASTRUCTURE',['_GRID', 'TRAFO_', 'HT_LT', 'HYDRO_GAS', 'LT_DEC_WH',
                       'LT_DHN_WH', 'DHN_RENOVATION', 'DEC_RENOVATION', 'DIRECT_USAGE']),
    ('INDUSTRY',      ['AL_MAKING', 'FOOD_PROD', 'PAPER_MAKING', 'STEEL_MAKING',
                       'CEMENT', 'ETHYLENE', 'PET_', 'PVC_', 'POLYPROPYLENE',
                       'STYRENE', 'SMART_PROCESS']),
]

def _fnew_category(tech):
    t = str(tech).upper()
    for cat, kws in _FNEW_CAT_RULES:
        for kw in kws:
            if kw.upper() in t:
                return cat
    return 'OTHER'


def _get_fnew_df(results, col):
    """Return DataFrame with index [Phases, Technologies], single column named col."""
    if col == 'F_decom':
        df = results.get('F_decom')
        if df is None:
            print("[DEBUG] F_decom not found in results dict")
            return None
        # F_decom has 3-level index: (phase_decom, phase_built, tech)
        # Aggregate over phase_built to get (phase_decom, tech)
        df = df.copy()
        # Robust rename: use position rather than assuming column name
        if len(df.columns) == 1:
            df.columns = ['F_decom']
        elif 'F_decom' not in df.columns:
            df = df.iloc[:, [0]]
            df.columns = ['F_decom']
        nlevels = df.index.nlevels
        if nlevels == 3:
            df = df.groupby(level=[0, 2]).sum()
        elif nlevels == 2:
            df = df.groupby(level=[0, 1]).sum()
        else:
            print(f"[DEBUG] Unexpected nlevels={nlevels}, skipping groupby")
        df.index.names = ['Phases', 'Technologies']
        return df
    if results.get(col) is not None:
        return results[col].copy()
    # fallback: extract from New_old_decom
    nod = results.get('New_old_decom')
    if nod is not None and col in nod.columns:
        return nod[[col]].copy()
    return None


def plot_fnew_by_category(results, outdir, case_study, col='F_new', prefix='2'):
    df_all = _get_fnew_df(results, col)
    if df_all is None:
        print(f"[SKIP] {col} not available"); return

    df_all = df_all.reset_index()
    df_all.columns = ['Phases', 'Technologies', col]
    df_all[col] = pd.to_numeric(df_all[col], errors='coerce').fillna(0)
    df_all['Phases'] = df_all['Phases'].astype(str)
    df_all['Category'] = df_all['Technologies'].apply(_fnew_category)

    # drop initialisation pseudo-phase and CO2 storage (inconsistent units)
    df_all = df_all[df_all['Phases'] != INIT_PHASE]
    df_all = df_all[~df_all['Technologies'].str.upper().isin(['CO2_STO', 'STO_CO2'])]

    # sort phases
    phase_order = [p for p in TRANS_PHASES if p in df_all['Phases'].unique()]

    for cat in sorted(df_all['Category'].unique()):
        sub = df_all[df_all['Category'] == cat].copy()
        if cat.startswith('MOB_'):
            if SHOW_DISTANCE_VARIANTS:
                sub = sub[sub['Technologies'].str.contains(_DIST_RE)].copy()
            else:
                sub['Technologies'] = sub['Technologies'].apply(_strip_dist)
                sub = sub.groupby(['Phases', 'Technologies', 'Category'], as_index=False)[col].sum()
        # keep only techs with at least one non-zero value
        active = sub.groupby('Technologies')[col].sum()
        active_techs = active[active > 0].index.tolist()
        sub = sub[sub['Technologies'].isin(active_techs)]
        if sub.empty:
            continue

        fig = go.Figure()
        for tech in sorted(active_techs):
            vals = (sub[sub['Technologies'] == tech]
                    .set_index('Phases')
                    .reindex(phase_order)[col]
                    .fillna(0).tolist())
            fig.add_bar(
                x=phase_order, y=vals, name=tech,
                marker_color=_tech_color(tech),
                text=[tech if v > 0 else '' for v in vals],
                textposition='inside',
                insidetextanchor='middle',
                textfont=dict(size=10, color='white'),
            )
        if cat == 'MOB_FREIGHT':   unit = 'Mtkm/h'
        elif cat.startswith('MOB'): unit = 'Mpkm/h'
        else:                       unit = 'GW'
        fig.update_layout(
            title=f'{case_study} — {col} [{cat}] [{unit}]',
            xaxis_title='Phase', yaxis_title=unit,
            barmode='stack',
            showlegend=True,
            legend=dict(x=1.01, y=1, xanchor='left'),
            uniformtext=dict(minsize=8, mode='hide'),
        )
        fname = f'{prefix}_{col}_{cat}.html'
        _save(fig, outdir, fname)


# ---------------------------------------------------------------------------
# NUMBER OF UNITS
# ---------------------------------------------------------------------------

def plot_number_of_units(results, outdir, case_study):
    nou = results.get('Number_Of_Units')
    if nou is None:
        print('[SKIP] Number_Of_Units not in results'); return

    df = nou.copy().reset_index()
    df.columns = ['Years', 'Technologies', 'Number_Of_Units']
    df['Number_Of_Units'] = pd.to_numeric(df['Number_Of_Units'], errors='coerce').fillna(0)
    df['Years'] = df['Years'].astype(str).str.replace('YEAR_', '', regex=False)
    df['Category'] = df['Technologies'].apply(_fnew_category)

    year_order = [y for y in YEARS_ORDER if y in df['Years'].unique()]

    for cat in sorted(df['Category'].unique()):
        sub = df[df['Category'] == cat].copy()
        if cat.startswith('MOB_'):
            if SHOW_DISTANCE_VARIANTS:
                sub = sub[sub['Technologies'].str.contains(_DIST_RE)].copy()
            else:
                sub['Technologies'] = sub['Technologies'].apply(_strip_dist)
                sub = sub.groupby(['Years', 'Technologies', 'Category'], as_index=False)['Number_Of_Units'].sum()

        active = sub.groupby('Technologies')['Number_Of_Units'].sum()
        active_techs = active[active > 0].index.tolist()
        sub = sub[sub['Technologies'].isin(active_techs)]
        if sub.empty:
            continue

        fig = go.Figure()
        for tech in sorted(active_techs):
            vals = (sub[sub['Technologies'] == tech]
                    .set_index('Years')
                    .reindex(year_order)['Number_Of_Units']
                    .fillna(0).tolist())
            fig.add_bar(
                x=year_order, y=vals, name=tech,
                marker_color=_tech_color(tech),
                text=[tech if v > 0 else '' for v in vals],
                textposition='inside',
                insidetextanchor='middle',
                textfont=dict(size=10, color='white'),
            )
        fig.update_layout(
            title=f'{case_study} — Number of units [{cat}]',
            xaxis_title='Year', yaxis_title='Units',
            barmode='stack',
            showlegend=True,
            legend=dict(x=1.01, y=1, xanchor='left'),
            uniformtext=dict(minsize=8, mode='hide'),
        )
        _save(fig, outdir, f'9_NumberOfUnits_{cat}.html')


# ---------------------------------------------------------------------------
# ELECTRIFICATION OF SOCIETY
# ---------------------------------------------------------------------------

# Classify a technology name into its primary energy carrier.
# Order matters: first match wins. Use '_KW_' patterns to avoid false
# positives like 'NG_' matching 'MAKING_'.
_ELEC_FUEL_RULES = [
    # --- exclude from the energy balance (no net energy output) ---
    ('_EXCLUDE_', ['TRAFO_', '_GRID', 'EHV_GRID', 'HV_GRID', 'MV_GRID', 'LV_GRID',
                   'HT_LT', 'DAC_', 'DEEP_SALINE', 'UNMINEABLE', 'EOR', 'DOGR',
                   'CO2_STO', 'STO_CO2', 'CARBON_', 'DIRECT_USAGE', 'SMART_PROCESS',
                   'LT_DEC_WH', 'LT_DHN_WH',
                   'NG_EXP_', 'NG_COMP_', 'SNG_EXP_', 'SNG_COMP_',  # NG/SNG pressure regulators
                   'H2_EXP_', 'H2_COMP_',                            # H2 pressure regulators
                   'DEC_TH_STORAGE', 'TH_STORAGE', 'STO_TH',         # thermal storage
                   'DIE_STO', 'STO_DIE', 'GASO_STO', 'STO_GASO',    # fuel storage
                   'H2_STO', 'STO_H2', 'STO_ELEC', 'ELEC_STO',      # H2/elec storage
                   'PHEV_GASOLINE', 'PHEV_DIESEL',                   # fossil PHEVs → not electric
                   ]),
    # --- electric & storage ---
    ('Electric',  ['_EV', 'BEV_', 'PHEV_', '_EHP', 'EHP_', '_HP_ELEC', 'HP_ELEC',
                   'HEAT_PUMP', 'TRAMWAY', 'METRO', 'TRAIN_ELEC', 'ELECTROLYSIS',
                   'PV_', 'WIND_', 'HYDRO', 'NUCLEAR', 'TIDAL', 'GEOTHERMAL',
                   'ELEC_', '_ELEC', 'BATTERY', 'MINES_STORAGE',
                   'DIE_STO', 'GASO_STO', 'STO_ELEC', 'ELEC_STO']),
    # --- H2 & synthetic fuels ---
    ('H2 / Synfuel', ['_H2', 'H2_', 'AFC', 'PAFC', 'PEMFC', 'SOFC',
                      '_FC_H2', 'FC_H2', 'SMR', 'ATR', 'METHANATION',
                      'PYROLYSIS', '_FT', 'FT_', '_SNG', 'SNG_',
                      'METHANOL', 'ETHANOL', '_MEOH', 'MEOH_',
                      'CO2_TO_']),
    # --- biofuels & organic ---
    ('Biofuel',   ['BIO', 'WOOD', 'WET_BIOMASS', 'BIOGAS', 'BIODIESEL',
                   'PROPANE', '_CNG', 'CNG_', 'AN_DIG', 'WASTE']),
    # --- fossil gas & oil ---
    ('Gas / Oil', ['_BOILER_GAS', 'BOILER_OIL', '_COGEN_GAS', 'COGEN_OIL',
                   'CCGT', 'OCGT', 'COAL', 'GASOLINE', 'DIESEL',
                   'PLANE_', 'BULK_CARRIER', 'CONTAINER', 'OIL_TANKER',
                   'HY_DIESEL', '_HEV', 'CAR_HEV', 'SUV_HEV',
                   'BOILER_GAS', 'COGEN_GAS', '_NG_', 'NG_CCGT',
                   'NG_REFORM', 'NG_PYROLY', 'LP_NG', 'MP_NG', 'HP_NG',
                   '_GAS',
                   'EHP_NG', 'TRAIN_NG', 'TRAIN_DIESEL', 'BUS_DIESEL',
                   'TRUCK_LH_DIESEL', 'TRUCK_SH_DIESEL',
                   'SEMI_LH_DIESEL', 'SEMI_SH_DIESEL', 'LCV_DIESEL',
                   'CAR_DIESEL', 'SUV_DIESEL', 'CAR_GASOLINE', 'SUV_GASOLINE']),
    # --- industry (last, catch-all for industrial processes) ---
    ('Industry',  ['AL_MAKING', 'STEEL_MAKING', 'CEMENT', 'FOOD_PROD',
                   'PAPER_MAKING', 'ETHYLENE', 'ETHANE_', 'POLYPROP',
                   'PET_FORM', 'PVC_FORM', 'STYRENE', 'CUMENE',
                   'METATHESIS', 'CARBONYLATION', '_TO_OLEFINS',
                   '_TO_AROMATICS']),
]

_FUEL_COLORS = {
    'Electric':      '#1f77b4',
    'H2 / Synfuel':  '#9467bd',
    'Biofuel':       '#2ca02c',
    'Gas / Oil':     '#d62728',
    'Industry':      '#ff7f0e',
    'Other':         '#aec7e8',
}

def _fuel_type(tech):
    for label, keywords in _ELEC_FUEL_RULES:
        if any(kw.upper() in tech.upper() for kw in keywords):
            return label
    return 'Other'


# ---------------------------------------------------------------------------
# ELECTRICITY LAYER — production (+) and consumption (-) per voltage level
# ---------------------------------------------------------------------------

def _elec_layer_fig(layer_df, title):
    """Stacked area chart for one electricity layer (TWh/y, pos=prod, neg=cons)."""
    # layer_df columns: Year (int), Elements (str), Value (GWh)
    active = layer_df.groupby('Elements')['Value'].apply(lambda s: s.abs().sum())
    active_elems = active[active > 1e-3].index.tolist()
    layer_df = layer_df[layer_df['Elements'].isin(active_elems)]
    if layer_df.empty:
        return None, False

    prod_sums = (layer_df[layer_df['Value'] > 0]
                 .groupby('Elements')['Value'].sum())
    prod_order = prod_sums[prod_sums > 1].sort_values(ascending=False).index.tolist()

    cons_sums = (layer_df[layer_df['Value'] < 0]
                 .groupby('Elements')['Value'].sum())
    cons_order = cons_sums[cons_sums < -1].sort_values(ascending=True).index.tolist()

    years = sorted(layer_df['Year'].unique())
    fig = go.Figure()
    for elem in prod_order:
        sub = layer_df[layer_df['Elements'] == elem].set_index('Year').reindex(years)
        vals = (sub['Value'].where(sub['Value'].abs() > 1e-3) / 1000).fillna(0).tolist()
        fig.add_trace(go.Scatter(x=years, y=vals, name=elem,
                                 stackgroup='pos', mode='none',
                                 fillcolor=_tech_color(elem), line=dict(width=0)))
    for elem in cons_order:
        sub = layer_df[layer_df['Elements'] == elem].set_index('Year').reindex(years)
        vals = (sub['Value'].where(sub['Value'].abs() > 1e-3) / 1000).fillna(0).tolist()
        fig.add_trace(go.Scatter(x=years, y=vals, name=elem,
                                 stackgroup='neg', mode='none',
                                 fillcolor=_tech_color(elem), line=dict(width=0)))

    fig.update_layout(
        title=title,
        xaxis=dict(title='Year', type='linear', dtick=5),
        yaxis_title='TWh/y',
        hovermode='x unified',
    )
    return fig, True


def plot_electricity_layer(results, outdir, case_study):
    key = 'Year_balance'
    if results.get(key) is None:
        print(f'[SKIP] {key} not in results'); return

    df = results[key].copy().reset_index()
    df.columns = [str(c) for c in df.columns]

    layers_present = [l for l in ELEC_LAYERS if l in df.columns]
    if not layers_present:
        print('[SKIP] No electricity layers in Year_balance'); return

    df['Year'] = df['Years'].str.replace('YEAR_', '').astype(int)
    df = df[df['Year'].isin([int(y) for y in YEARS_ORDER])]

    for col in layers_present:
        df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)

    # Merge ELEC_EXPORT_FIXED (fixed demand) + ELEC_EXPORT (optional Res) into one element
    if 'ELEC_EXPORT_FIXED' in df['Elements'].astype(str).values:
        df['Elements'] = df['Elements'].astype(str).replace('ELEC_EXPORT_FIXED', 'ELEC_EXPORT')
        df = df.groupby(['Year', 'Elements'], as_index=False)[layers_present].sum()

    # --- per-voltage-level plots ---
    for layer in layers_present:
        sub = (df[['Year', 'Elements', layer]]
               .rename(columns={layer: 'Value'})
               .copy())
        label = ELEC_LAYER_LABELS.get(layer, layer)
        fig, ok = _elec_layer_fig(sub, f'{case_study} — Electricity layer [{label}] [TWh/y]')
        if ok:
            _save(fig, outdir, f'10_Elec_layer_{label}.html')

    # --- combined (all voltage levels) ---
    sub_all = df[['Year', 'Elements'] + layers_present].copy()
    sub_all['Value'] = sub_all[layers_present].sum(axis=1)
    fig_all, ok_all = _elec_layer_fig(
        sub_all[['Year', 'Elements', 'Value']],
        f'{case_study} — Electricity layer [ALL] [TWh/y]',
    )
    if ok_all:
        _save(fig_all, outdir, '10_Elec_layer_ALL.html')


# ---------------------------------------------------------------------------
# HEAT LAYER — production (+) and consumption (-) per heat type
# ---------------------------------------------------------------------------

def plot_heat_layer(results, outdir, case_study):
    key = 'Year_balance'
    if results.get(key) is None:
        print(f'[SKIP] {key} not in results'); return

    df = results[key].copy().reset_index()
    df.columns = [str(c) for c in df.columns]

    layers_present = [l for l in HEAT_LAYERS if l in df.columns]
    if not layers_present:
        print('[SKIP] No heat layers in Year_balance'); return

    # exclude storage techs (DHN_TH_STORAGE etc. have buggy values)
    _EXCL_STO = ['_STORAGE', 'TS_', 'SEASONAL_']
    df = df[~df['Elements'].apply(
        lambda n: any(p.upper() in n.upper() for p in _EXCL_STO)).astype(bool)]

    df['Year'] = df['Years'].str.replace('YEAR_', '').astype(int)
    df = df[df['Year'].isin([int(y) for y in YEARS_ORDER])]

    for col in layers_present:
        df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)

    # --- per-layer plots ---
    for layer in layers_present:
        sub = (df[['Year', 'Elements', layer]]
               .rename(columns={layer: 'Value'})
               .copy())
        label = HEAT_LAYER_LABELS.get(layer, layer)
        fig, ok = _elec_layer_fig(sub, f'{case_study} — Heat layer [{label}] [TWh/y]')
        if ok:
            _save(fig, outdir, f'11_Heat_layer_{label.replace(" ", "_")}.html')

    # --- combined (all heat layers) ---
    sub_all = df[['Year', 'Elements'] + layers_present].copy()
    sub_all['Value'] = sub_all[layers_present].sum(axis=1)
    fig_all, ok_all = _elec_layer_fig(
        sub_all[['Year', 'Elements', 'Value']],
        f'{case_study} — Heat layer [ALL] [TWh/y]',
    )
    if ok_all:
        _save(fig_all, outdir, '11_Heat_layer_ALL.html')


# ---------------------------------------------------------------------------
# HYDROGEN LAYER — production (+) and consumption (-) per pressure level
# ---------------------------------------------------------------------------

def plot_h2_layer(results, outdir, case_study):
    key = 'Year_balance'
    if results.get(key) is None:
        print(f'[SKIP] {key} not in results'); return

    df = results[key].copy().reset_index()
    df.columns = [str(c) for c in df.columns]

    layers_present = [l for l in H2_LAYERS if l in df.columns]
    if not layers_present:
        print('[SKIP] No H2 layers in Year_balance'); return

    df['Year'] = df['Years'].str.replace('YEAR_', '').astype(int)
    df = df[df['Year'].isin([int(y) for y in YEARS_ORDER])]

    for col in layers_present:
        df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)

    # --- per-pressure-level plots ---
    for layer in layers_present:
        sub = (df[['Year', 'Elements', layer]]
               .rename(columns={layer: 'Value'})
               .copy())
        label = H2_LAYER_LABELS.get(layer, layer)
        fig, ok = _elec_layer_fig(sub, f'{case_study} — H2 layer [{label}] [TWh/y]')
        if ok:
            _save(fig, outdir, f'12b_H2_layer_{label}.html')

    # --- combined (all H2 pressure levels) ---
    sub_all = df[['Year', 'Elements'] + layers_present].copy()
    sub_all['Value'] = sub_all[layers_present].sum(axis=1)
    fig_all, ok_all = _elec_layer_fig(
        sub_all[['Year', 'Elements', 'Value']],
        f'{case_study} — H2 layer [ALL] [TWh/y]',
    )
    if ok_all:
        _save(fig_all, outdir, '12b_H2_layer_ALL.html')


def plot_ng_layer(results, outdir, case_study):
    key = 'Year_balance'
    if results.get(key) is None:
        print(f'[SKIP] {key} not in results'); return

    df = results[key].copy().reset_index()
    df.columns = [str(c) for c in df.columns]

    layers_present = [l for l in NG_LAYERS if l in df.columns]
    if not layers_present:
        print('[SKIP] No NG layers in Year_balance'); return

    df['Year'] = df['Years'].str.replace('YEAR_', '').astype(int)
    df = df[df['Year'].isin([int(y) for y in YEARS_ORDER])]

    for col in layers_present:
        df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)

    for layer in layers_present:
        sub = (df[['Year', 'Elements', layer]]
               .rename(columns={layer: 'Value'})
               .copy())
        label = NG_LAYER_LABELS.get(layer, layer)
        fig, ok = _elec_layer_fig(sub, f'{case_study} — NG layer [{label}] [TWh/y]')
        if ok:
            _save(fig, outdir, f'12c_NG_layer_{label}.html')

    sub_all = df[['Year', 'Elements'] + layers_present].copy()
    sub_all['Value'] = sub_all[layers_present].sum(axis=1)
    fig_all, ok_all = _elec_layer_fig(
        sub_all[['Year', 'Elements', 'Value']],
        f'{case_study} — NG layer [ALL] [TWh/y]',
    )
    if ok_all:
        _save(fig_all, outdir, '12c_NG_layer_ALL.html')


# ---------------------------------------------------------------------------
# MOBILITY LAYER — supply (+) per distance category
# ---------------------------------------------------------------------------

def _mob_layer_fig(layer_df, title, unit):
    """Stacked area chart for one mobility layer (pos=supply, neg=consumption)."""
    active = layer_df.groupby('Elements')['Value'].apply(lambda s: s.abs().sum())
    active_elems = active[active > 1e-3].index.tolist()
    layer_df = layer_df[layer_df['Elements'].isin(active_elems)]
    if layer_df.empty:
        return None, False

    prod_sums = layer_df[layer_df['Value'] > 0].groupby('Elements')['Value'].sum()
    prod_order = prod_sums[prod_sums > 1].sort_values(ascending=False).index.tolist()
    cons_sums = layer_df[layer_df['Value'] < 0].groupby('Elements')['Value'].sum()
    cons_order = cons_sums[cons_sums < -1].sort_values(ascending=True).index.tolist()

    years = sorted(layer_df['Year'].unique())
    fig = go.Figure()
    for elem in prod_order:
        sub = layer_df[layer_df['Elements'] == elem].set_index('Year').reindex(years)
        vals = sub['Value'].where(sub['Value'].abs() > 1e-3).fillna(0).tolist()
        fig.add_trace(go.Scatter(x=years, y=vals, name=elem,
                                 stackgroup='pos', mode='none',
                                 fillcolor=_tech_color(elem), line=dict(width=0)))
    for elem in cons_order:
        sub = layer_df[layer_df['Elements'] == elem].set_index('Year').reindex(years)
        vals = sub['Value'].where(sub['Value'].abs() > 1e-3).fillna(0).tolist()
        fig.add_trace(go.Scatter(x=years, y=vals, name=elem,
                                 stackgroup='neg', mode='none',
                                 fillcolor=_tech_color(elem), line=dict(width=0)))
    fig.update_layout(
        title=title,
        xaxis=dict(title='Year', type='linear', dtick=5),
        yaxis_title=unit,
        hovermode='x unified',
    )
    return fig, True


def plot_mobility_layer(results, outdir, case_study):
    key = 'Year_balance'
    if results.get(key) is None:
        print(f'[SKIP] {key} not in results'); return

    df = results[key].copy().reset_index()
    df.columns = [str(c) for c in df.columns]
    df['Year'] = df['Years'].str.replace('YEAR_', '').astype(int)
    df = df[df['Year'].isin([int(y) for y in YEARS_ORDER])]

    all_mob_layers = MOB_PASSENGER_LAYERS + MOB_FREIGHT_LAYERS
    layers_present = [l for l in all_mob_layers if l in df.columns]
    if not layers_present:
        print('[SKIP] No mobility layers in Year_balance'); return

    for col in layers_present:
        df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)

    # --- one plot per passenger distance (private + public combined) ---
    for dist in ['SD', 'MD', 'LD', 'ELD']:
        dist_layers = [l for l in [f'MOB_PRIVATE_{dist}', f'MOB_PUBLIC_{dist}'] if l in layers_present]
        if not dist_layers:
            continue
        sub = df[['Year', 'Elements'] + dist_layers].copy()
        sub['Value'] = sub[dist_layers].sum(axis=1)
        fig, ok = _mob_layer_fig(sub[['Year', 'Elements', 'Value']],
                                 f'{case_study} — Passenger mobility [{dist}] [Mpkm/y]', 'Mpkm/y')
        if ok:
            _save(fig, outdir, f'13_Mob_Passenger_{dist}.html')

    # --- one plot per freight distance ---
    for dist in ['SD', 'MD', 'LD', 'ELD']:
        layer = f'MOB_FREIGHT_{dist}'
        if layer not in layers_present:
            continue
        sub = df[['Year', 'Elements', layer]].rename(columns={layer: 'Value'}).copy()
        fig, ok = _mob_layer_fig(sub, f'{case_study} — Freight mobility [{dist}] [Mtkm/y]', 'Mtkm/y')
        if ok:
            _save(fig, outdir, f'13_Mob_Freight_{dist}.html')

    # --- combined passenger (all distances) ---
    pass_present = [l for l in MOB_PASSENGER_LAYERS if l in layers_present]
    if pass_present:
        sub_p = df[['Year', 'Elements'] + pass_present].copy()
        sub_p['Value'] = sub_p[pass_present].sum(axis=1)
        fig, ok = _mob_layer_fig(sub_p[['Year', 'Elements', 'Value']],
                                 f'{case_study} — Passenger mobility [ALL distances] [Mpkm/y]', 'Mpkm/y')
        if ok:
            _save(fig, outdir, '13_Mob_Passenger_ALL.html')

    # --- combined freight (all distances) ---
    frt_present = [l for l in MOB_FREIGHT_LAYERS if l in layers_present]
    if frt_present:
        sub_f = df[['Year', 'Elements'] + frt_present].copy()
        sub_f['Value'] = sub_f[frt_present].sum(axis=1)
        fig, ok = _mob_layer_fig(sub_f[['Year', 'Elements', 'Value']],
                                 f'{case_study} — Freight mobility [ALL distances] [Mtkm/y]', 'Mtkm/y')
        if ok:
            _save(fig, outdir, '13_Mob_Freight_ALL.html')


# ---------------------------------------------------------------------------
# STORAGE LEVELS — seasonal fill fraction per storage type, one line per year
# ---------------------------------------------------------------------------

def plot_storage_levels(results, outdir, case_study):
    """Line plot of storage fill levels per month, one line per year,
    one subplot per active storage type.
    Values already in [0,1] are plotted as fractions; absolute GWh values are
    normalised to [0,1] by dividing by the column maximum."""
    key = 'Sto_levels'
    if results.get(key) is None:
        print(f'[SKIP] {key} not in results'); return

    df = results[key].copy().reset_index()
    df['Year'] = df['Years'].str.replace('YEAR_', '').astype(int)
    df['Month'] = df['Periods'].astype(int)

    sto_cols = [c for c in df.columns if c not in ('Years', 'Periods', 'Year', 'Month')]
    active = [c for c in sto_cols if df[c].notna().any()]
    if not active:
        print('[SKIP storage_levels] no active storage data'); return

    # Reindex to ensure all 12 months × all years exist.
    # clean_collector drops rows where ALL storage columns are NaN (i.e. all were 0),
    # so months where every storage is empty simply don't exist in the pkl.
    years_present = sorted(df['Year'].unique())
    full_idx = pd.MultiIndex.from_product([years_present, range(1, 13)], names=['Year', 'Month'])
    df = (df.set_index(['Year', 'Month'])[active]
            .reindex(full_idx)
            .reset_index())

    # NaN in Sto_levels means the original AMPL value was 0 (get_sto_levels replaces 0→NaN),
    # or the row was dropped by clean_collector because all storages were 0 that month.
    # A zero level is meaningful (storage empty), so always restore NaN→0.
    for c in active:
        df[c] = df[c].fillna(0)

    # Normalise per-year so each year's seasonal pattern is visible at its own scale.
    # (Global normalisation would flatten years with small absolute levels, e.g. early CO2 storage.)
    # Then invert: the AMPL STO_*_LEVEL variable decreases when *_STO (charging) is active
    # and increases when STO_* (discharging) is active, so 1−level gives the physical fill level.
    for yr in df['Year'].unique():
        mask = df['Year'] == yr
        for c in active:
            yr_max = df.loc[mask, c].max()
            if pd.notna(yr_max) and yr_max > 1.0:
                df.loc[mask, c] = df.loc[mask, c] / yr_max
        #for c in active:
            #df.loc[mask, c] = 1 - df.loc[mask, c]

    years = sorted(df['Year'].unique())
    months = list(range(1, 13))
    n = len(active)

    year_colors = {y: c for y, c in zip(years,
        ['#1f77b4','#ff7f0e','#2ca02c','#d62728','#9467bd','#8c564b','#e377c2'])}

    # --- CO2_CS annual throughput from Year_balance ---
    co2_annual = None
    yb = results.get('Year_balance')
    if yb is not None and 'CO2_CS' in yb.columns:
        co2cs = yb['CO2_CS'].dropna().reset_index()
        co2cs.columns = ['Years', 'Elements', 'Value']
        co2cs['Year'] = co2cs['Years'].str.replace('YEAR_', '').astype(int)
        co2cs = co2cs[co2cs['Elements'].isin(['CO2_STO', 'STO_CO2'])]
        if not co2cs.empty:
            co2_annual = co2cs

    has_co2 = co2_annual is not None and not co2_annual.empty
    n_rows = 2 if has_co2 else 1
    row_heights = [0.6, 0.4] if has_co2 else [1.0]

    fig = make_subplots(
        rows=n_rows, cols=n,
        subplot_titles=[f'STO_{s}_LEVEL' for s in active] + (['CO2_CS annual throughput [kton CO₂/y]'] if has_co2 else []),
        shared_yaxes=True,
        row_heights=row_heights,
        vertical_spacing=0.14,
    )

    shown = set()
    for ci, sto in enumerate(active, start=1):
        for yr in years:
            sub = df[df['Year'] == yr][['Month', sto]].set_index('Month').reindex(months)
            vals = sub[sto].tolist()
            show_leg = yr not in shown
            if show_leg: shown.add(yr)
            fig.add_trace(go.Scatter(
                x=months, y=vals,
                name=str(yr),
                mode='lines+markers',
                line=dict(color=year_colors.get(yr, '#888'), width=2),
                marker=dict(size=5),
                legendgroup=str(yr),
                showlegend=show_leg,
                hovertemplate=f'Month %{{x}} — %{{y:.3f}}<extra>{sto} {yr}</extra>',
                connectgaps=True,
            ), row=1, col=ci)

    # Row 2: CO2_CS annual bar chart (positive = into storage, negative = out)
    if has_co2:
        ann_years = sorted(co2_annual['Year'].unique())
        for elem, color in [('CO2_STO', '#2ca02c'), ('STO_CO2', '#d62728')]:
            sub = co2_annual[co2_annual['Elements'] == elem].set_index('Year').reindex(ann_years)['Value'].fillna(0)
            fig.add_trace(go.Bar(
                x=ann_years, y=sub.tolist(),
                name=elem,
                marker_color=color,
                legendgroup=elem,
                showlegend=True,
                hovertemplate='%{x}: %{y:.2f} kton CO₂<extra>' + elem + '</extra>',
            ), row=2, col=1)

    fig.update_layout(
        title=dict(text=f'{case_study} — Storage fill levels [normalised 0–1]', x=0.5),
        hovermode='x unified',
        height=550 if has_co2 else 400,
        legend=dict(title='', orientation='v'),
        barmode='relative',
    )
    fig.update_xaxes(title_text='Month', tickvals=months,
                     ticktext=['J','F','M','A','M','J','J','A','S','O','N','D'], row=1)
    fig.update_xaxes(title_text='Year', row=2)
    fig.update_yaxes(title_text='Fill level [0–1]', range=[0, 1.05], col=1, row=1)
    if has_co2:
        fig.update_yaxes(title_text='kton CO₂/y', row=2, col=1)

    _save(fig, outdir, '15_Storage_levels.html')



# ---------------------------------------------------------------------------
# SANKEY — energy flow per year (EnergyScope library style)
# ---------------------------------------------------------------------------



def _create_es_sankey_figure(df_flow, colors):
    colors = _ES_Colors.cast(colors)
    df_flow = df_flow.copy()
    df_flow["color"] = df_flow.apply(
        lambda row: str(colors[row["target"]] | colors[row["source"]]), axis=1)
    node = np.unique(np.concatenate((df_flow["source"].unique(), df_flow["target"].unique())))
    df_sankey = df_flow.replace(node, range(len(node)))
    fig = go.Figure(data=[go.Sankey(
        valueformat=".0f",
        valuesuffix=" GWh",
        node=dict(pad=15, thickness=15,
                  line=dict(color="black", width=0.5),
                  label=node, color="#DCDCDC"),
        link=dict(
            source=df_sankey["source"],
            target=df_sankey["target"],
            value=df_sankey["value"],
            label=df_sankey["value"],
            color=df_flow["color"].apply(lambda c: _ES_Color(c).rgba(0.5)),
        )
    )])
    fig.update_layout(title_text="Sankey", font_size=10,
                      template="plotly", font_color="black")
    return fig


_SKIP_INFRA_RE = re.compile(
    r'^(TRAFO_|H2_COMP_|H2_EXP_|NG_COMP_|NG_EXP_|SNG_COMP_|SNG_EXP_)',
    re.IGNORECASE)

_SKIP_TECHS = {
    'DEC_TH_STORAGE', 'TH_STORAGE', 'STO_TH', 'DHN_TH_STORAGE',
}

_EUD_DIR = os.path.join('ES_Transition_QC_2', 'EUD')

_EUD_LAYER_PREFIXES = {
    # EUD demand-category prefix → Sankey carrier name
    'ELECTRICITY': 'ELECTRICITY',
    'HEAT_LOW_T':  'HEAT_LOW_T',
    'HEAT_HIGH_T': 'HEAT_HIGH_T',
}
_EUD_SKIP_SECTORS = {'EXPORT', 'TRANSPORTATION'}

def _parse_all_eud_shares(year_int):
    """Return {carrier: {sector: share}} for all splittable carriers, for the given year."""
    fpath = os.path.join(_EUD_DIR, f'QC_eud_{year_int}.dat')
    pat = re.compile(
        r"end_uses_demand_year\['YEAR_\d+','([^']+)','([^']+)'\]\s*:=\s*([\d.e+\-]+)")
    raw = {}
    try:
        with open(fpath) as f:
            for line in f:
                m = pat.search(line)
                if not m: continue
                eud_layer, sector, val = m.group(1), m.group(2), float(m.group(3))
                if sector in _EUD_SKIP_SECTORS: continue
                for prefix, carrier in _EUD_LAYER_PREFIXES.items():
                    if eud_layer.startswith(prefix):
                        raw.setdefault(carrier, {})
                        raw[carrier][sector] = raw[carrier].get(sector, 0) + val
                        break
    except FileNotFoundError:
        return {}
    return {carrier: {s: v / sum(d.values()) for s, v in d.items()}
            for carrier, d in raw.items() if sum(d.values()) > 0}


_ELEC_LV_EMBEDDED = {'LIGHTING', 'HEAT_LOW_T_SC'}   # EUD types embedded in ELECTRICITY_LV balance (model constraint)

def _parse_elec_voltage_sector_shares(year_int):
    """Return (shares, totals) where each is {layer: {sector: value_or_share}}.
    Covers ELECTRICITY_LV/MV/HV/EHV plus embedded layers (LIGHTING)."""
    fpath = os.path.join(_EUD_DIR, f'QC_eud_{year_int}.dat')
    pat = re.compile(
        r"end_uses_demand_year\['YEAR_\d+','([^']+)','([^']+)'\]\s*:=\s*([\d.e+\-]+)")
    raw = {}
    _target = set(ELEC_LAYERS) | _ELEC_LV_EMBEDDED
    try:
        with open(fpath) as f:
            for line in f:
                m = pat.search(line)
                if not m: continue
                eud_layer, sector, val = m.group(1), m.group(2), float(m.group(3))
                if sector in _EUD_SKIP_SECTORS or eud_layer not in _target: continue
                raw.setdefault(eud_layer, {})
                raw[eud_layer][sector] = raw[eud_layer].get(sector, 0) + val
    except FileNotFoundError:
        return {}, {}
    totals = {layer: sum(d.values()) for layer, d in raw.items()}
    shares = {layer: {s: v / totals[layer] for s, v in d.items()}
              for layer, d in raw.items() if totals[layer] > 0}
    return shares, totals


def _eud_sector(layer):
    """Map a layer name consumed by END_USES to its EUD sector node."""
    l = layer.upper()
    if l.startswith('MOB_PRIVATE') or l.startswith('MOB_PUBLIC'):
        return 'MOBILITY_PASSENGER'
    if l.startswith('MOB_FREIGHT'):
        return 'MOBILITY_FREIGHT'
    if l.startswith('ELECTRICITY'):
        return '_EUD_SPLIT_ELECTRICITY'
    if l.startswith('HEAT_LOW_T'):
        return '_EUD_SPLIT_HEAT_LOW_T'
    if l.startswith('HEAT_HIGH_T'):
        return '_EUD_SPLIT_HEAT_HIGH_T'
    return 'END_USES'


_TECH_GROUP_RULES = [
    # order matters — first match wins
    ('CAR',       ['CAR_']),
    ('SUV',       ['SUV_']),
    ('TRUCK',     ['TRUCK_']),
    ('LCV',       ['LCV_']),
    ('SEMI',      ['SEMI_']),
    ('TRAIN',     ['TRAIN_']),
    ('PLANE',     ['PLANE_']),
    ('SHIP',      ['BULK_CARRIER', 'CONTAINER', 'OIL_TANKER']),
    ('COMMUTER',  ['COMMUTER_']),
    ('BUS',       ['BUS_', 'COACH_', 'SCHOOLBUS_']),
    ('BOILER',    ['_BOILER_', 'BOILER_', 'IND_BOILER', 'DHN_BOILER', 'DEC_BOILER']),
    ('COGEN',     ['_COGEN_', 'COGEN_', 'IND_COGEN', 'DHN_COGEN', 'DEC_COGEN',
                   'IND_ADVCOGEN', 'DEC_ADVCOGEN']),
    ('BIOMASS',   ['BIOMASS_']),
]

def _group_tech(t):
    u = t.upper()
    for group, patterns in _TECH_GROUP_RULES:
        for p in patterns:
            if p.upper() in u:
                return group
    return t


def _build_sankey_df(results, year_str):
    """Build (source, target, value) DataFrame from Year_balance for one year."""
    year_int = int(year_str.split('_')[-1])
    yb = results["Year_balance"].reset_index()
    yb.columns = [str(c) for c in yb.columns]
    yb = yb[yb["Years"] == year_str].copy()

    layer_cols = [c for c in yb.columns if c not in ("Years", "Elements")]
    df = yb.melt(id_vars="Elements", value_vars=layer_cols,
                 var_name="Flow", value_name="value")
    df.rename(columns={"Elements": "Technologies"}, inplace=True)
    df["value"] = pd.to_numeric(df["value"], errors="coerce").fillna(0)
    df["Technologies"] = df["Technologies"].astype(str)
    df["Flow"]         = df["Flow"].astype(str)
    df = df[df["value"].abs() > 0]

    # Strip distance variants then group families (CAR_EV_SD → CAR_EV → CAR, etc.)
    df["Technologies"] = df["Technologies"].apply(
        lambda t: re.sub(r'_(SD|MD|LD|ELD)$', '', t, flags=re.IGNORECASE))
    df["Technologies"] = df["Technologies"].apply(_group_tech)

    # positive = tech produces layer; negative = tech consumes layer
    df.rename(columns={"Technologies": "target", "Flow": "source"}, inplace=True)
    mask = df["value"] > 0
    df.loc[mask, ["target", "source"]] = df.loc[mask, ["source", "target"]].to_numpy()
    df["value"] = df["value"].abs()
    df = df.groupby(["source", "target"]).sum().reset_index()

    # Drop grid infrastructure (TRAFO, COMP, EXP) and excluded tech nodes
    skip = lambda s: bool(_SKIP_INFRA_RE.match(s)) or s in _SKIP_TECHS
    df = df[~df["source"].apply(skip) & ~df["target"].apply(skip)]

    # Resources that supply their own layer → prefix IMP_
    imp_mask = df["source"] == df["target"]
    df.loc[imp_mask, "source"] = "IMP_" + df.loc[imp_mask, "source"]
    df = df[~df["source"].str.startswith("IMP_RES")]

    # Drop CO2 flows (keep fuel-producing techs that consume CO2)
    co2_keep = {"CO2_TO_DIESEL", "CO2_TO_JETFUELS", "CO2_METHANOL"}
    df = df[(~df["source"].str.contains("CO2_")) | df["source"].isin(co2_keep)]
    df = df[(~df["target"].str.contains("CO2_")) | df["target"].isin(co2_keep)]

    # Extract electricity EUD rows before layer collapse to preserve voltage-level detail
    _ELEC_LAYERS_SET = set(ELEC_LAYERS)
    _elec_eud_mask = (df["target"] == "END_USES") & df["source"].isin(_ELEC_LAYERS_SET)
    _elec_eud_df   = df[_elec_eud_mask].copy()
    df = df[~_elec_eud_mask]

    # Aggregate pressure/delivery levels → single carrier nodes
    _H2_SET      = set(H2_LAYERS)
    _NG_SET      = set(NG_LAYERS)
    _ELEC_SET    = set(ELEC_LAYERS)
    _HEAT_LT_SET = {'HEAT_LOW_T_DECEN', 'HEAT_LOW_T_DHN'}
    for layers, name in [(_H2_SET, "H2"), (_NG_SET, "NG"), (_ELEC_SET, "ELECTRICITY"),
                         (_HEAT_LT_SET, "HEAT_LOW_T")]:
        df["source"] = df["source"].apply(lambda x: name if x in layers else x)
        df["target"] = df["target"].apply(lambda x: name if x in layers else x)

    # Aggregate MOB distance-variant layers → MOB_PRIVATE / MOB_PUBLIC / MOB_FREIGHT
    def _agg_mob_layer(x):
        for pfx in ("MOB_PRIVATE_", "MOB_PUBLIC_", "MOB_FREIGHT_"):
            if x.upper().startswith(pfx):
                return pfx.rstrip("_")
        return x
    df["source"] = df["source"].apply(_agg_mob_layer)
    df["target"] = df["target"].apply(_agg_mob_layer)

    df = df.groupby(["source", "target"]).sum().reset_index()
    df = df[df["source"] != df["target"]]

    # Add electricity voltage-level intermediate nodes (ELECTRICITY → LV/MV/HV/EHV → sector)
    # Embedded EUD types (LIGHTING) are embedded in the LV balance value — shown as separate nodes.
    if not _elec_eud_df.empty:
        _elec_voltage_shares, _elec_voltage_dat_totals = _parse_elec_voltage_sector_shares(year_int)
        _voltage_rows = []
        _lv_balance = _elec_eud_df.groupby("source")["value"].sum()
        for voltage_layer, balance_total in _lv_balance.items():
            # Subtract embedded EUD layers from the voltage node value
            embedded_total = sum(_elec_voltage_dat_totals.get(e, 0) for e in _ELEC_LV_EMBEDDED) \
                if voltage_layer == 'ELECTRICITY_LV' else 0
            net_total = max(balance_total - embedded_total, 0)
            _voltage_rows.append({"source": "ELECTRICITY", "target": voltage_layer, "value": net_total})
            for sector, share in _elec_voltage_shares.get(voltage_layer, {}).items():
                _voltage_rows.append({"source": voltage_layer, "target": sector,
                                      "value": net_total * share})
        # Add embedded EUD nodes at the same level as voltage nodes
        for embedded_layer in _ELEC_LV_EMBEDDED:
            emb_total = _elec_voltage_dat_totals.get(embedded_layer, 0)
            if emb_total > 0:
                _voltage_rows.append({"source": "ELECTRICITY", "target": embedded_layer, "value": emb_total})
                for sector, share in _elec_voltage_shares.get(embedded_layer, {}).items():
                    _voltage_rows.append({"source": embedded_layer, "target": sector,
                                          "value": emb_total * share})
        if _voltage_rows:
            df = pd.concat([df, pd.DataFrame(_voltage_rows)], ignore_index=True)

    # Fix mobility unit mismatch: replace pkm/tkm output values with energy input (GWh).
    # Must be done here, before EUD renaming, while MOB_PRIVATE/PUBLIC/FREIGHT nodes exist.
    # When a grouped tech (e.g. PLANE = passenger + freight) outputs to multiple MOB_* nodes,
    # split energy_in proportionally rather than assigning the full total to each output.
    _MOB_NODES = {"MOB_PRIVATE", "MOB_PUBLIC", "MOB_FREIGHT"}
    mob_out_mask = df["target"].isin(_MOB_NODES)
    for tech in df.loc[mob_out_mask, "source"].unique():
        energy_in = df.loc[
            (df["target"] == tech) & ~df["source"].isin(_MOB_NODES), "value"
        ].sum()
        if energy_in <= 0:
            continue
        tech_mob_mask = (df["source"] == tech) & mob_out_mask
        total_mob_out = df.loc[tech_mob_mask, "value"].sum()
        if total_mob_out > 0:
            fractions = df.loc[tech_mob_mask, "value"] / total_mob_out
            df.loc[tech_mob_mask, "value"] = fractions * energy_in
        else:
            df.loc[tech_mob_mask, "value"] = energy_in
    # Fix MOB_* → END_USES values to match the corrected GWh totals
    for mob_node in _MOB_NODES:
        node_mask = (df["source"] == mob_node) & (df["target"] == "END_USES")
        if node_mask.any():
            total_gwh = df.loc[df["target"] == mob_node, "value"].sum()
            if total_gwh > 0:
                df.loc[node_mask, "value"] = total_gwh

    # Replace END_USES target with sector EUD nodes based on the source layer
    eu_mask = df["target"] == "END_USES"
    df.loc[eu_mask, "target"] = df.loc[eu_mask, "source"].apply(_eud_sector)

    # Expand _EUD_SPLIT_* placeholders → per-sector rows using EUD proportions
    eud_shares = _parse_all_eud_shares(year_int)
    split_mask = df["target"].str.startswith("_EUD_SPLIT_")
    if split_mask.any():
        split_rows = df[split_mask].copy()
        df = df[~split_mask]
        new_rows = []
        for _, row in split_rows.iterrows():
            carrier = row["target"].replace("_EUD_SPLIT_", "")
            shares = eud_shares.get(carrier, {})
            if shares:
                for sector, share in shares.items():
                    new_rows.append({"source": row["source"], "target": sector,
                                     "value": row["value"] * share})
            else:
                new_rows.append({"source": row["source"], "target": carrier + "_DEMAND",
                                 "value": row["value"]})
        if new_rows:
            df = pd.concat([df, pd.DataFrame(new_rows)], ignore_index=True)

    # Rename electricity export element
    for col in ("source", "target"):
        df[col] = df[col].str.replace(
            "ELEC_EXPORT_FIXED", "EUD_ELECTRICITY_EHV_EXPORT", regex=False)

    # Final aggregation after all renaming
    df = df.groupby(["source", "target"]).sum().reset_index()
    df = df[df["source"] != df["target"]]

    df = df[df["value"] > 1]
    return df


def plot_sankey(results, outdir, case_study):
    """One Sankey HTML per year using the EnergyScope library flow logic."""
    if results.get("Year_balance") is None:
        print("[SKIP] Year_balance not in results"); return

    for year in YEARS_ORDER:
        year_str = f"YEAR_{year}"
        try:
            df_flow = _build_sankey_df(results, year_str)
        except Exception as e:
            print(f"[SKIP] Sankey {year}: {e}"); continue
        if df_flow.empty:
            continue
        fig = _create_es_sankey_figure(df_flow, _ES_default_colors)
        fig.update_layout(title_text=f"{case_study} — Energy flow {year} [GWh]")
        _save(fig, outdir, f"16_Sankey_{year}.html")


# ---------------------------------------------------------------------------
# GWP breakdown — EUD-based sector allocation
# ---------------------------------------------------------------------------

# Year_balance layer → EUD demand layers it ultimately serves
# Used to compute per-sector consumption fractions from the dat files.
_YB_TO_EUD_LAYERS = {
    # ELECTRICITY_LV balance also carries lighting and space-cooling demand
    'ELECTRICITY_LV':   ['ELECTRICITY_LV', 'LIGHTING', 'HEAT_LOW_T_SC'],
    'ELECTRICITY_MV':   ['ELECTRICITY_MV'],
    'ELECTRICITY_HV':   ['ELECTRICITY_HV'],
    # EHV balance includes electricity export
    'ELECTRICITY_EHV':  ['ELECTRICITY_EHV', 'ELECTRICITY_EHV_EXPORT'],
    'HEAT_HIGH_T':      ['HEAT_HIGH_T'],
    # DHN and DECEN both serve the same aggregate HW+SH demand; the DHN/DECEN split is global
    'HEAT_LOW_T_DECEN': ['HEAT_LOW_T_HW', 'HEAT_LOW_T_SH'],
    'HEAT_LOW_T_DHN':   ['HEAT_LOW_T_HW', 'HEAT_LOW_T_SH'],
    'MOB_PRIVATE_SD':   ['MOBILITY_PASSENGER_SD'],
    'MOB_PRIVATE_MD':   ['MOBILITY_PASSENGER_MD'],
    'MOB_PRIVATE_LD':   ['MOBILITY_PASSENGER_LD'],
    'MOB_PRIVATE_ELD':  ['MOBILITY_PASSENGER_ELD'],
    'MOB_PUBLIC_SD':    ['MOBILITY_PASSENGER_SD'],
    'MOB_PUBLIC_MD':    ['MOBILITY_PASSENGER_MD'],
    'MOB_PUBLIC_LD':    ['MOBILITY_PASSENGER_LD'],
    'MOB_PUBLIC_ELD':   ['MOBILITY_PASSENGER_ELD'],
    'MOB_FREIGHT_SD':   ['MOBILITY_FREIGHT_SD'],
    'MOB_FREIGHT_MD':   ['MOBILITY_FREIGHT_MD'],
    'MOB_FREIGHT_LD':   ['MOBILITY_FREIGHT_LD'],
    'MOB_FREIGHT_ELD':  ['MOBILITY_FREIGHT_ELD'],
}
_PASSENGER_MOB_YB = frozenset({
    'MOB_PRIVATE_SD', 'MOB_PRIVATE_MD', 'MOB_PRIVATE_LD', 'MOB_PRIVATE_ELD',
    'MOB_PUBLIC_SD',  'MOB_PUBLIC_MD',  'MOB_PUBLIC_LD',  'MOB_PUBLIC_ELD',
})
_FREIGHT_MOB_YB = frozenset({
    'MOB_FREIGHT_SD', 'MOB_FREIGHT_MD', 'MOB_FREIGHT_LD', 'MOB_FREIGHT_ELD',
})

_GWP_SECTOR_COLORS = {
    'HOUSEHOLDS':           '#F58518',
    'SERVICES':             '#EECA3B',
    'INDUSTRY':             '#72B7B2',
    'Passenger transport':  '#E45756',
    'Freight transport':    '#B279A2',
    'AGRICULTURE':          '#54A24B',
    'EXPORT':               '#4C78A8',
    'Carbon capture':       '#17BECF',
    'Biogenic carbon':      '#90EE90',
    'Other':                '#AAAAAA',
}

_GWP_RES_COLORS = {
    'NG': '#FFD700', 'DIESEL': '#D3D3D3', 'GASOLINE': '#808080',
    'COAL': '#A0522D', 'LFO': '#8B008B', 'WOOD': '#CD853F',
}

_EUD_DAT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                             '..', '..', '..', 'shared', 'data', 'EUD')


def _load_eud_sector_fracs():
    """Parse QC_eud_*.dat → {year: {yb_layer: {sector: fraction}}}.

    TRANSPORTATION in EUD is split into 'Passenger transport' (for passenger
    mobility layers) and 'Freight transport' (for freight layers).
    Returns {} when no dat files are found (fallback mode).
    """
    rows = []
    for path in sorted(_glob.glob(os.path.join(_EUD_DAT_DIR, 'QC_eud_*.dat'))):
        m = re.search(r'_(\d+)\.dat$', path)
        if not m:
            continue
        year = int(m.group(1))
        with open(path, encoding='utf-8') as fh:
            content = fh.read()
        for match in re.finditer(
            r"end_uses_demand_year\['[^']+','([^']+)','([^']+)'\]\s*:=\s*([\d.eE+\-*]+)",
            content,
        ):
            layer, sector, val_str = match.group(1), match.group(2), match.group(3)
            try:
                parts = val_str.split('*')
                val = float(parts[0]) * float(parts[1]) if len(parts) == 2 else float(parts[0])
            except (ValueError, IndexError):
                val = 0.0
            rows.append((year, layer, sector, val))

    if not rows:
        return {}

    eud_df = pd.DataFrame(rows, columns=['Year', 'Layer', 'Sector', 'Demand'])
    result = {}
    for year, year_df in eud_df.groupby('Year'):
        result[int(year)] = {}
        for yb_layer, eud_layers in _YB_TO_EUD_LAYERS.items():
            sub = year_df[year_df['Layer'].isin(eud_layers)].groupby('Sector')['Demand'].sum()
            total = float(sub.sum())
            if total == 0:
                result[int(year)][yb_layer] = {}
                continue
            fracs = {}
            for sector, dem in sub.items():
                if sector == 'TRANSPORTATION':
                    sector = ('Passenger transport' if yb_layer in _PASSENGER_MOB_YB
                              else 'Freight transport')
                fracs[sector] = fracs.get(sector, 0.0) + float(dem) / total
            result[int(year)][yb_layer] = fracs
    return result


def _gwp_sector_fallback(tech):
    """Name-based sector assignment when EUD allocation is not possible."""
    t = tech.upper()
    if any(k in t for k in ('BIOMASS_', 'WET_BIOMASS', 'WASTE_BIO')):
        return 'Biogenic carbon'
    if any(k in t for k in ('DAC_', 'CO2_STO', 'STO_CO2', 'DEEP_SALINE',
                             'UNMINEABLE', 'EOR', 'DOGR', 'CO2_CAPTURED',
                             'CARBON_CAPTURE', 'CARBON_')):
        return 'Carbon capture'
    if any(k in t for k in ('TRUCK_', 'SEMI_', 'LCV_', 'TRAIN_FREIGHT',
                             'BULK_CARRIER', 'CONTAINER', 'OIL_TANKER', 'PLANE_FREIGHT')):
        return 'Freight transport'
    if any(k in t for k in ('CAR_', 'SUV_', 'BUS_', 'COACH_', 'TRAMWAY', 'METRO',
                             'TRAIN_', 'PLANE_', 'SCHOOLBUS_', 'COMMUTER_RAIL')):
        return 'Passenger transport'
    if any(k in t for k in ('IND_', 'AL_MAKING', 'CEMENT', 'FOOD_PROD',
                             'PAPER_MAKING', 'STEEL_MAKING', 'METHANOL', 'ETHANOL',
                             'SMR', 'ATR', 'CO2_TO_', 'GASIFICATION', 'PYROLYSIS',
                             'AN_DIG', 'FT_', 'NG_PYROLYSIS', 'METHANATION', 'BIOGAS_')):
        return 'INDUSTRY'
    if any(k in t for k in ('DEC_', 'LT_DEC', 'HT_LT', 'DHN_')):
        return 'HOUSEHOLDS'
    return 'Other'


def _allocate_gwp_to_sectors(results, eud_fracs=None):
    """Allocate CO₂ from Year_balance to EUD sectors.

    For each (year, tech) with CO₂ ≠ 0:
      - If the tech produces one or more EUD-mapped layers, split its CO₂
        proportionally to the sector fractions of those layers, weighted by
        the production amount.  This handles multi-sector techs (e.g. a gas
        boiler serving HOUSEHOLDS 67% / SERVICES 25% / INDUSTRY 7%).
      - Otherwise fall back to name-based sector assignment.

    Returns DataFrame [Year, Tech, Sector, GWP_kt].
    """
    yb = results.get('Year_balance')
    if yb is None:
        return pd.DataFrame(columns=['Year', 'Tech', 'Sector', 'GWP_kt'])
    co2_cols = [c for c in ('CO2_A', 'CO2_E') if c in yb.columns]
    if not co2_cols:
        return pd.DataFrame(columns=['Year', 'Tech', 'Sector', 'GWP_kt'])

    if eud_fracs is None:
        eud_fracs = _load_eud_sector_fracs()

    eud_mapped = set(_YB_TO_EUD_LAYERS.keys())
    yb_eud_cols = [c for c in yb.columns if c in eud_mapped]

    rows = []
    for (year_str, tech), row in yb.iterrows():
        gwp = float(np.nansum([pd.to_numeric(row.get(c, 0), errors='coerce')
                                for c in co2_cols]))
        if abs(gwp) < 0.01:
            continue

        year = int(str(year_str).replace('YEAR_', ''))
        year_fracs = eud_fracs.get(year, {})

        # Positive production in EUD-mapped layers
        layer_prod = {}
        for l in yb_eud_cols:
            raw = row.get(l)
            if raw is None:
                continue
            val = pd.to_numeric(raw, errors='coerce')
            if pd.notna(val) and float(val) > 0.0:
                layer_prod[l] = float(val)

        total_prod = sum(layer_prod.values())
        if total_prod > 0.0 and year_fracs:
            sec_weights = {}
            for l, prod in layer_prod.items():
                for sec, frac in year_fracs.get(l, {}).items():
                    sec_weights[sec] = sec_weights.get(sec, 0.0) + prod * frac
            total_w = sum(sec_weights.values())
            if total_w > 0.0:
                for sec, w in sec_weights.items():
                    rows.append({'Year': year, 'Tech': tech,
                                 'Sector': sec, 'GWP_kt': gwp * w / total_w})
                continue

        rows.append({'Year': year, 'Tech': tech,
                     'Sector': _gwp_sector_fallback(tech), 'GWP_kt': gwp})

    if not rows:
        return pd.DataFrame(columns=['Year', 'Tech', 'Sector', 'GWP_kt'])
    return pd.DataFrame(rows)


def plot_gwp_breakdown(results, outdir, case_study):
    """GWP breakdown: L1 = EUD sector, L2 = individual technology.

    Emissions are allocated to HOUSEHOLDS / SERVICES / INDUSTRY /
    Passenger transport / Freight transport / AGRICULTURE / EXPORT
    in proportion to each sector's share of the relevant end-use demand.
    Technologies serving multiple sectors (e.g. a gas boiler serving both
    households and services) are split proportionally — no double-counting.
    Click a sector bar in the legend to reveal contributing technologies.
    """
    yb = results.get('Year_balance')
    if yb is None:
        print('[SKIP] Year_balance not in results'); return

    eud_fracs = _load_eud_sector_fracs()
    if not eud_fracs:
        print('[WARN] EUD dat files not found — using fallback sector assignment')

    alloc_df = _allocate_gwp_to_sectors(results, eud_fracs)
    if alloc_df.empty:
        print('[SKIP] No GWP data'); return

    # Aggregate distance variants (CAR_GASOLINE_SD/MD/LD → CAR_GASOLINE)
    alloc_df['Tech'] = alloc_df['Tech'].apply(_strip_dist)
    alloc_df = alloc_df.groupby(['Year', 'Tech', 'Sector'], as_index=False)['GWP_kt'].sum()

    years = sorted(alloc_df['Year'].unique().tolist())

    # Consistency check: allocated total vs Year_balance total per year
    co2_cols = [c for c in ('CO2_A', 'CO2_E') if c in yb.columns]
    for yr in years:
        yb_yr  = yb.xs(f'YEAR_{yr}', level='Years')
        yb_tot = sum(float(pd.to_numeric(yb_yr[c], errors='coerce').fillna(0).sum())
                     for c in co2_cols)
        al_tot = float(alloc_df[alloc_df['Year'] == yr]['GWP_kt'].sum())
        if abs(yb_tot - al_tot) > 1.0:
            print(f'[WARN] GWP {yr}: Year_balance={yb_tot:.1f} kt, '
                  f'allocated={al_tot:.1f} kt (diff={al_tot - yb_tot:.1f} kt)')

    # ---- L1: sector totals ----
    l1 = alloc_df.groupby(['Year', 'Sector'], as_index=False)['GWP_kt'].sum()

    # ---- L2: individual tech traces per sector ----
    l2_by_sector = {}
    for sec in l1['Sector'].unique():
        sec_df = alloc_df[alloc_df['Sector'] == sec]
        tech_totals = sec_df.groupby('Tech')['GWP_kt'].sum().sort_values(ascending=False)
        traces = []
        for tech in tech_totals.index:
            tdf = (sec_df[sec_df['Tech'] == tech]
                   .groupby('Year')['GWP_kt'].sum()
                   .reindex(years).fillna(0))
            if tdf.abs().sum() < 0.1:
                continue
            traces.append({
                'type': 'bar', 'name': tech,
                'x': years,
                'y': (tdf / 1000).tolist(),
                'marker': {'color': _GWP_RES_COLORS.get(tech, _tech_color(tech))},
                'hovertemplate': '%{y:.3f} Mt CO₂-eq.<extra>' + tech + '</extra>',
            })
        l2_by_sector[sec] = traces

    # ---- TotalGWP model check line ----
    total_line_trace = None
    gwp_total = results.get('TotalGwp')
    if gwp_total is not None:
        tg = gwp_total.copy().reset_index()
        tg.columns = [str(c) for c in tg.columns]
        gwp_col = 'TotalGWP' if 'TotalGWP' in tg.columns else tg.columns[1]
        tg['Year'] = tg.iloc[:, 0].str.replace('YEAR_', '').astype(int)
        tg[gwp_col] = pd.to_numeric(tg[gwp_col], errors='coerce')
        tg = tg[tg['Year'].isin(years)].sort_values('Year')
        total_line_trace = {
            'type': 'scatter', 'name': 'TotalGWP (model check)',
            'x': [int(v) for v in tg['Year']],
            'y': [float(v) / 1000 for v in tg[gwp_col]],
            'mode': 'lines+markers',
            'line': {'color': 'black', 'width': 2, 'dash': 'dash'},
            'hovertemplate': '%{y:.2f} Mt CO₂-eq.<extra>TotalGWP (model)</extra>',
        }

    # ---- Cumulative line (y2) ----
    total_by_year = l1.groupby('Year')['GWP_kt'].sum().reindex(years).fillna(0)
    cumulative    = (total_by_year / 1000 * 5).cumsum().shift(1).fillna(0)
    total_gt      = float((total_by_year / 1000 * 5).sum()) / 1000

    cumul_trace = {
        'type': 'scatter', 'name': f'Cumulative ({total_gt:.2f} Gt CO₂)',
        'x': years, 'y': cumulative.tolist(),
        'mode': 'lines+markers',
        'line': {'color': 'darkred', 'width': 2.5},
        'marker': {'size': 6},
        'yaxis': 'y2',
        'hovertemplate': '%{y:.0f} Mt CO₂-eq.<extra>Cumulative</extra>',
    }

    # ---- L1 sector bar traces ----
    sec_totals = l1.groupby('Sector')['GWP_kt'].sum()

    def _sec_key(s):
        tot = float(sec_totals.get(s, 0))
        return (tot < 0, s in ('Other', 'Biogenic carbon'), -tot)

    sectors = sorted(l1['Sector'].unique().tolist(), key=_sec_key)
    overlay_names = {'TotalGWP (model check)', f'Cumulative ({total_gt:.2f} Gt CO₂)'}

    l1_traces = []
    for sec in sectors:
        sub = l1[l1['Sector'] == sec].set_index('Year').reindex(years)
        l1_traces.append({
            'type': 'bar', 'name': sec,
            'x': years,
            'y': (sub['GWP_kt'].fillna(0) / 1000).tolist(),
            'marker': {'color': _GWP_SECTOR_COLORS.get(sec, '#AAAAAA')},
            'hovertemplate': '%{y:.3f} Mt CO₂-eq.<extra>' + sec + '</extra>',
        })
    if total_line_trace:
        l1_traces.append(total_line_trace)
    l1_traces.append(cumul_trace)

    # ---- y-axis range ----
    neg_yr = alloc_df[alloc_df['GWP_kt'] < 0].groupby('Year')['GWP_kt'].sum().reindex(years).fillna(0)
    pos_yr = alloc_df[alloc_df['GWP_kt'] > 0].groupby('Year')['GWP_kt'].sum().reindex(years).fillna(0)
    y1_min = min((neg_yr / 1000).min() * 1.1, 0)
    y1_max = max((pos_yr / 1000).max() * 1.1, 0.1)
    y2_max = float(cumulative.max()) * 1.1 or 1.0
    neg_frac = abs(y1_min) / (abs(y1_min) + y1_max) if y1_min < 0 else 0
    y2_min   = -y2_max * neg_frac / (1 - neg_frac) if neg_frac < 1 else 0

    l1_layout = {
        'title': (f'{case_study} — GHG emissions by sector [Mt CO₂-eq./y]  '
                  '<i style="font-size:13px">(click a sector in the legend to drill down)</i>'),
        'barmode': 'relative', 'hovermode': 'x unified',
        'xaxis': {'title': 'Year', 'type': 'linear', 'dtick': 5},
        'yaxis': {'title': 'Mt CO₂-eq./y', 'range': [y1_min, y1_max]},
        'yaxis2': {
            'title': 'Cumulative [Mt CO₂-eq.]',
            'range': [y2_min, y2_max],
            'overlaying': 'y', 'side': 'right',
            'showgrid': False,
            'tickfont': {'color': 'darkred'},
            'titlefont': {'color': 'darkred'},
        },
        'legend': {'orientation': 'h', 'y': -0.25},
        'height': 540,
        'annotations': [{
            'x': years[-1], 'y': float(cumulative.iloc[-1]),
            'xref': 'x', 'yref': 'y2',
            'text': f'<b>Total: {total_gt:.2f} Gt CO₂</b>',
            'showarrow': True, 'arrowhead': 2,
            'ax': 40, 'ay': -30,
            'font': {'color': 'darkred', 'size': 12},
            'bgcolor': 'rgba(255,255,255,0.8)',
            'bordercolor': 'darkred',
        }] if years else [],
    }
    l2_layout = {
        'title': 'Technologies — click a sector above',
        'barmode': 'relative', 'hovermode': 'x unified',
        'xaxis': {'title': 'Year', 'type': 'linear', 'dtick': 5},
        'yaxis': {'title': 'Mt CO₂-eq./y (sector share)'},
        'legend': {'orientation': 'h', 'y': -0.3},
        'showlegend': True,
        'height': 440,
    }

    html = f"""<!DOCTYPE html><html><head><meta charset="utf-8">
<title>{case_study} — GHG emissions by sector</title>
<script src="https://cdn.plot.ly/plotly-latest.min.js"></script>
</head><body>
<div id="chart-l1" style="width:100%"></div>
<div id="chart-l2" style="width:100%;display:none"></div>
<script>
var l2Data = {_jdumps(l2_by_sector)};
var l1Layout = {_jdumps(l1_layout)};
var l2Layout = {_jdumps(l2_layout)};
var overlayNames = {_jdumps(list(overlay_names))};
var selectedSector = null;
Plotly.newPlot('chart-l1', {_jdumps(l1_traces)}, l1Layout);

document.getElementById('chart-l1').on('plotly_legendclick', function(data) {{
    var trace = data.data[data.curveNumber];
    var sec = trace.name;
    if (overlayNames.indexOf(sec) >= 0) return;
    var l2El = document.getElementById('chart-l2');
    if (sec === selectedSector) {{
        selectedSector = null;
        l2El.style.display = 'none';
    }} else {{
        selectedSector = sec;
        var traces = l2Data[sec] || [];
        l2El.style.display = 'block';
        Plotly.newPlot('chart-l2', traces,
            Object.assign({{}}, l2Layout,
                {{title: sec + ' — contributing technologies [Mt CO₂-eq./y, sector share]'}}));
    }}
    return false;
}});
</script></body></html>"""

    path = os.path.join(outdir, '14_GWP_breakdown.html')
    with open(path, 'w', encoding='utf-8') as f:
        f.write(html)
    print(f'[SAVE] {path}')




# ===========================================================================

# ===========================================================================
# DASHBOARD (stub — will list graphs as links)
# ===========================================================================

def create_dashboard(outdir, case_study):
    graphs = sorted(f for f in os.listdir(outdir) if f.endswith('.html') and f != 'index.html')

    def _label(fname):
        return fname.replace('.html', '').replace('_', ' ')

    def _prefix(fname):
        """Return the leading alphanumeric prefix, e.g. '2' or '3b' for '3b_F_decom_*.html'."""
        m = re.match(r'^(\d+[a-z]?)_', fname)
        return m.group(1) if m else fname

    def _prefix_sort_key(x):
        """Sort '0','0b','1','2','3','3b','4',... correctly."""
        m = re.match(r'^(\d+)([a-z]?)$', x)
        if m:
            return (int(m.group(1)), m.group(2))
        return (999, x)

    # group files by numeric prefix; groups with >1 file become collapsible sections
    groups = defaultdict(list)
    for g in graphs:
        groups[_prefix(g)].append(g)

    # Split into init (00_*) and transition sections
    init_prefixes  = [p for p in groups if re.match(r'^00', p)]
    trans_prefixes = [p for p in groups if not re.match(r'^00', p)]

    summary_path = os.path.join(os.path.dirname(outdir), '0_Summary.html')
    has_summary  = os.path.exists(summary_path)

    nav_html = ''
    if has_summary:
        nav_html += '<li class="section-header">Summary</li>\n'
        nav_html += '<li><a href="#" onclick="load(\'../0_Summary.html\');return false;">System summary</a></li>\n'

    first = '../0_Summary.html' if has_summary else (graphs[0] if graphs else '')

    def _render_prefix_group(prefix):
        nonlocal nav_html
        files = groups[prefix]
        if len(files) == 1:
            g = files[0]
            nav_html += f'<li><a href="#" onclick="load(\'{g}\');return false;">{_label(g)}</a></li>\n'
        else:
            stems = [re.sub(r'^\d+[a-z]?_', '', f.replace('.html', '')) for f in files]
            stem = os.path.commonprefix(stems).rstrip('_').replace('_', ' ')
            year_map = defaultdict(list)
            no_year = []
            for g in files:
                m = re.search(r'_(20\d\d)_', g)
                if m:
                    year_map[m.group(1)].append(g)
                else:
                    no_year.append(g)
            nav_html += f'<li class="group"><span class="group-title" onclick="toggleGroup(this)">▶ {stem}</span><ul class="sublist">\n'
            if year_map:
                for yr in sorted(year_map):
                    yr_files = year_map[yr]
                    nav_html += f'  <li class="group"><span class="group-title year-title" onclick="toggleGroup(this)">▶ {yr}</span><ul class="sublist sublist2">\n'
                    for g in yr_files:
                        sub_label = re.sub(r'^.*_20\d\d_', '', g.replace('.html', '')).replace('_', ' ')
                        nav_html += f'    <li><a href="#" onclick="load(\'{g}\');return false;">{sub_label}</a></li>\n'
                    nav_html += '  </ul></li>\n'
                for g in no_year:
                    sub_label = re.sub(r'^.*_([^_]+)$', r'\1', g.replace('.html', ''))
                    nav_html += f'  <li><a href="#" onclick="load(\'{g}\');return false;">{sub_label}</a></li>\n'
            else:
                for g in files:
                    sub_label = re.sub(r'^.*_([^_]+)$', r'\1', g.replace('.html', ''))
                    nav_html += f'  <li><a href="#" onclick="load(\'{g}\');return false;">{sub_label}</a></li>\n'
            nav_html += '</ul></li>\n'

    if init_prefixes:
        nav_html += '<li class="section-header">Initial Configuration (2020)</li>\n'
        for prefix in sorted(init_prefixes, key=_prefix_sort_key):
            _render_prefix_group(prefix)

    if trans_prefixes:
        nav_html += '<li class="section-header">Transition (2020–2050)</li>\n'
        for prefix in sorted(trans_prefixes, key=_prefix_sort_key):
            _render_prefix_group(prefix)

    html = f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<title>{case_study}</title>
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ display: flex; height: 100vh; font-family: sans-serif; background: #f4f4f4; }}
  #sidebar {{
    width: 260px; min-width: 180px; background: #1e1e2e; color: #cdd6f4;
    display: flex; flex-direction: column; overflow-y: auto; flex-shrink: 0;
  }}
  #sidebar h2 {{ padding: 16px 14px 10px; font-size: 14px; color: #89b4fa;
                 border-bottom: 1px solid #313244; }}
  #nav {{ list-style: none; padding: 8px 0; }}
  #nav li a {{
    display: block; padding: 7px 14px; color: #cdd6f4; text-decoration: none;
    font-size: 13px; border-left: 3px solid transparent;
  }}
  #nav li a:hover {{ background: #313244; color: #89b4fa; }}
  #nav li a.active {{ border-left-color: #89b4fa; background: #313244; }}
  .group-title {{
    display: block; padding: 7px 14px; font-size: 13px; font-weight: bold;
    color: #89b4fa; cursor: pointer; user-select: none;
  }}
  .group-title:hover {{ background: #313244; }}
  .sublist {{ list-style: none; display: none; background: #181825; }}
  .sublist.open {{ display: block; }}
  .sublist li a {{ padding-left: 28px; font-size: 12px; }}
  .year-title {{ padding-left: 24px; font-size: 12px; color: #a6e3a1; }}
  .sublist2 {{ background: #11111b; }}
  .sublist2 li a {{ padding-left: 44px; font-size: 11px; }}
  .section-header {{
    display: block; padding: 10px 14px 4px; font-size: 11px; font-weight: bold;
    text-transform: uppercase; letter-spacing: 0.08em;
    color: #f38ba8; border-top: 1px solid #313244; margin-top: 6px;
  }}
  #content {{ flex: 1; display: flex; flex-direction: column; }}
  #frame-title {{ padding: 10px 16px; background: #fff; border-bottom: 1px solid #ddd;
                  font-size: 14px; color: #555; }}
  iframe {{ flex: 1; border: none; width: 100%; height: 100%; }}
</style>
</head>
<body>
<div id="sidebar">
  <h2>{case_study}</h2>
  <ul id="nav">
{nav_html}
  </ul>
</div>
<div id="content">
  <div id="frame-title">Select a graph</div>
  <iframe id="viewer" src="{first}"></iframe>
</div>
<script>
  function load(src) {{
    document.getElementById('viewer').src = src;
    document.getElementById('frame-title').textContent = src.replace('.html','').replace(/_/g,' ');
    document.querySelectorAll('#nav a').forEach(a => a.classList.remove('active'));
    document.querySelectorAll('#nav a').forEach(a => {{
      if (a.getAttribute('onclick') && a.getAttribute('onclick').includes("'" + src + "'"))
        a.classList.add('active');
    }});
  }}
  function toggleGroup(el) {{
    var sub = el.nextElementSibling;
    sub.classList.toggle('open');
    el.textContent = (sub.classList.contains('open') ? '▼ ' : '▶ ') + el.textContent.slice(2);
  }}
  var first = document.querySelector('#nav li a');
  if (first) first.classList.add('active');
</script>
</body>
</html>"""

    path = os.path.join(outdir, 'index.html')
    with open(path, 'w', encoding='utf-8') as f:
        f.write(html)
    print(f"  Dashboard: {path}")
    webbrowser.open(f'file:///{os.path.abspath(path).replace(os.sep, "/")}')


# ===========================================================================
# SUMMARY DASHBOARD
# ===========================================================================

def plot_summary_dashboard(results, outdir, case_study):
    """
    Two-panel summary figure:
      Left  — stacked area: energy mix by fuel type [TWh/y]
      Right — KPI lines: Renewable %, Fossil %, Electrification %, H2 share %
    """
    key = 'Annual_Prod'
    if results.get(key) is None:
        print(f'[SKIP summary_dashboard] {key} not in results'); return

    df = results[key].copy().reset_index()
    df.columns = ['Years', 'Technologies', 'GWh']
    df['Year'] = df['Years'].str.replace('YEAR_', '').astype(int)
    df = df[df['Year'].isin([int(y) for y in YEARS_ORDER])]
    df['GWh'] = pd.to_numeric(df['GWh'], errors='coerce').fillna(0)
    df = df[df['GWh'] > 0]
    df['FuelType'] = df['Technologies'].apply(_fuel_type)
    df = df[df['FuelType'] != '_EXCLUDE_']

    # Mobility techs produce in Mpkm/Mtkm, not GWh — exclude both base and variants.
    all_techs = set(df['Technologies'].unique())
    _dist_sfx = ('_SD', '_MD', '_LD', '_ELD')
    mob_variants = {t for t in all_techs if any(t.endswith(s) for s in _dist_sfx)}
    base_mob_techs = {t for t in all_techs if any(f'{t}{s}' in all_techs for s in _dist_sfx)}
    df = df[~df['Technologies'].isin(mob_variants | base_mob_techs)]

    df['TWh'] = df['GWh'] / 1000

    years = sorted(df['Year'].unique())
    fuel_order = ['Electric', 'H2 / Synfuel', 'Biofuel', 'Gas / Oil', 'Industry', 'Other']
    agg = df.groupby(['Year', 'FuelType'])['TWh'].sum().reset_index()

    total_per_year = agg.groupby('Year')['TWh'].sum().reindex(years).replace(0, pd.NA)

    def _share(fuel):
        s = agg[agg['FuelType'] == fuel].set_index('Year').reindex(years)['TWh'].fillna(0)
        return (s / total_per_year * 100).fillna(0)

    renewable_pct    = _share('Electric')
    fossil_pct       = _share('Gas / Oil')
    h2_pct           = _share('H2 / Synfuel')
    biofuel_pct      = _share('Biofuel')

    # electrification rate (end-use met by electricity, same logic as plot_electrification)
    elec_per_year  = agg[agg['FuelType'] == 'Electric'].set_index('Year').reindex(years)['TWh'].fillna(0)
    elec_rate      = (elec_per_year / total_per_year * 100).fillna(0)

    # ── Prepare mobility data (row 2) ──────────────────────────────────────────
    mob_df = results[key].copy().reset_index()
    mob_df.columns = ['Years', 'Technologies', 'Val']
    mob_df['Year'] = mob_df['Years'].str.replace('YEAR_', '').astype(int)
    mob_df = mob_df[mob_df['Year'].isin([int(y) for y in YEARS_ORDER])]
    mob_df['Val'] = pd.to_numeric(mob_df['Val'], errors='coerce').fillna(0)
    mob_df = mob_df[mob_df['Val'] > 0]
    _dist_sfx = ('_SD', '_MD', '_LD', '_ELD')
    mob_df = mob_df[mob_df['Technologies'].apply(lambda t: any(t.endswith(s) for s in _dist_sfx))]
    _PASS_KW = ('CAR_', 'SUV_', 'BUS_', 'COACH_', 'TRAMWAY', 'METRO',
                'COMMUTER_RAIL', 'TRAIN_ELEC', 'TRAIN_H2', 'TRAIN_NG',
                'TRAIN_DIESEL', 'PLANE_SH', 'SCHOOLBUS')
    _FRGT_KW = ('SEMI_', 'TRUCK_', 'LCV_', 'BULK_CARRIER', 'CONTAINER',
                'OIL_TANKER', 'TRAIN_FREIGHT', 'PLANE_FREIGHT')
    def _mob_cat(tech):
        t = tech.upper()
        if any(kw.upper() in t for kw in _PASS_KW): return 'passenger'
        if any(kw.upper() in t for kw in _FRGT_KW): return 'freight'
        return None
    mob_df['MobCat'] = mob_df['Technologies'].apply(_mob_cat)
    mob_df['FuelType'] = mob_df['Technologies'].apply(_fuel_type)
    mob_df = mob_df[mob_df['MobCat'].notna()]
    mob_df = mob_df[mob_df['FuelType'] != '_EXCLUDE_']

    # ── Build figure: 2 rows ───────────────────────────────────────────────────
    fig = make_subplots(
        rows=2, cols=2,
        row_heights=[0.52, 0.48],
        column_widths=[0.58, 0.42],
        subplot_titles=['Energy mix [TWh/y]', 'Key indicators [%]',
                        'Passenger mobility [Mpkm/y]', 'Freight mobility [Mtkm/y]'],
        specs=[[{'secondary_y': False}, {'secondary_y': False}],
               [{'secondary_y': False}, {'secondary_y': False}]],
        shared_xaxes=False,
        vertical_spacing=0.12,
    )

    # Pre-compute per-tech data (for drill-down)
    tech_agg = df.groupby(['Year', 'FuelType', 'Technologies'])['TWh'].sum().reset_index()

    def _shade(hex_color, idx, n):
        hex_color = hex_color.lstrip('#')
        r, g, b = (int(hex_color[i:i+2], 16) / 255 for i in (0, 2, 4))
        h, s, v = colorsys.rgb_to_hsv(r, g, b)
        v2 = v + (0.95 - v) * (idx / max(n - 1, 1))
        r2, g2, b2 = colorsys.hsv_to_rgb(h, s * (1 - idx / max(n - 1, 1) * 0.5), v2)
        return '#{:02x}{:02x}{:02x}'.format(int(r2*255), int(g2*255), int(b2*255))

    # ── ROW 1 LEFT: overview traces ──
    for fuel in fuel_order:
        sub = agg[agg['FuelType'] == fuel].set_index('Year').reindex(years)['TWh'].fillna(0)
        fig.add_trace(go.Scatter(
            x=years, y=sub.tolist(),
            name=fuel, mode='lines', stackgroup='mix',
            fillcolor=_FUEL_COLORS.get(fuel, '#aaa'),
            line=dict(color=_FUEL_COLORS.get(fuel, '#aaa'), width=0.5),
            legendgroup='overview', legendgrouptitle_text='Energy mix',
            visible=True,
            hovertemplate='%{y:.1f} TWh<extra>' + fuel + '</extra>',
        ), row=1, col=1)

    n_overview = len(fuel_order)
    detail_trace_meta = []

    # ── ROW 1 LEFT: detail traces (hidden) ──
    for fuel in fuel_order:
        base_color = _FUEL_COLORS.get(fuel, '#aaaaaa')
        tech_sub = tech_agg[tech_agg['FuelType'] == fuel]
        techs = (tech_sub.groupby('Technologies')['TWh'].sum()
                 .sort_values(ascending=False).index.tolist())
        for k, tech in enumerate(techs):
            ts = tech_sub[tech_sub['Technologies'] == tech].set_index('Year').reindex(years)['TWh'].fillna(0)
            shade = _shade(base_color, k, len(techs))
            fig.add_trace(go.Scatter(
                x=years, y=ts.tolist(),
                name=tech, mode='lines', stackgroup='detail',
                fillcolor=shade, line=dict(color=shade, width=0.3),
                legendgroup=f'detail_{fuel}', legendgrouptitle_text=fuel,
                visible=False,
                hovertemplate='%{y:.1f} TWh<extra>' + tech + '</extra>',
            ), row=1, col=1)
            detail_trace_meta.append(fuel)

    n_detail = len(detail_trace_meta)

    # ── ROW 1 RIGHT: KPI lines ──
    kpi_traces = [
        ('Renewable (Electric) %', renewable_pct, '#1f77b4', 'solid'),
        ('Fossil %',               fossil_pct,    '#d62728', 'solid'),
        ('Biofuel %',              biofuel_pct,   '#2ca02c', 'dot'),
        ('H2 / Synfuel %',         h2_pct,        '#9467bd', 'dot'),
    ]
    n_kpi = len(kpi_traces)
    for label, series, color, dash in kpi_traces:
        fig.add_trace(go.Scatter(
            x=years, y=series.tolist(), name=label,
            mode='lines+markers',
            line=dict(color=color, width=2, dash=dash), marker=dict(size=6),
            legendgroup='kpi', legendgrouptitle_text='KPIs',
            hovertemplate='%{y:.1f}%<extra>' + label + '</extra>',
        ), row=1, col=2)

    # ── ROW 2: mobility — Scatter+stackgroup, visibility tracked in insertion order
    mob_fuel_order = ['Electric', 'H2 / Synfuel', 'Biofuel', 'Gas / Oil', 'Other']
    # Single ordered list — one entry per trace, in exact insertion order:
    #   ('ov', fuel) | ('det', fuel) | ('elec', None)
    mob_trace_meta = []

    mob_tagg = mob_df.groupby(['Year', 'MobCat', 'FuelType', 'Technologies'])['Val'].sum().reset_index()
    shown_mob_leg = set()

    for col, cat, unit in [(1, 'passenger', 'Mpkm'), (2, 'freight', 'Mtkm')]:
        sub = mob_df[mob_df['MobCat'] == cat]
        magg = sub.groupby(['Year', 'FuelType'])['Val'].sum().reset_index()
        total_mob = magg.groupby('Year')['Val'].sum().reindex(years).replace(0, pd.NA)
        sg_ov  = f'mob_ov_{col}'
        sg_det = f'mob_det_{col}'

        # Overview traces — inserted first for this panel
        for fuel in mob_fuel_order:
            s = magg[magg['FuelType'] == fuel].set_index('Year').reindex(years)['Val'].fillna(0)
            if s.sum() < 1: continue
            show_leg = fuel not in shown_mob_leg
            if show_leg: shown_mob_leg.add(fuel)
            fig.add_trace(go.Scatter(
                x=years, y=s.tolist(), name=fuel,
                mode='lines', stackgroup=sg_ov,
                fillcolor=_FUEL_COLORS.get(fuel, '#aaa'),
                line=dict(color=_FUEL_COLORS.get(fuel, '#aaa'), width=0.5),
                legendgroup=f'mob_ov_{fuel}', legendgrouptitle_text='Mobility mix',
                showlegend=show_leg, visible=True,
                hovertemplate=f'%{{y:,.0f}} {unit}<extra>' + fuel + f' ({cat})</extra>',
            ), row=2, col=col)
            mob_trace_meta.append(('ov', fuel))   # ← insertion-order record

        # Detail traces — inserted second for this panel
        tech_sub = mob_tagg[mob_tagg['MobCat'] == cat]
        for fuel in mob_fuel_order:
            base_color = _FUEL_COLORS.get(fuel, '#aaaaaa')
            fs = tech_sub[tech_sub['FuelType'] == fuel]
            techs = (fs.groupby('Technologies')['Val'].sum()
                     .sort_values(ascending=False).index.tolist())
            for k, tech in enumerate(techs):
                ts = fs[fs['Technologies'] == tech].set_index('Year').reindex(years)['Val'].fillna(0)
                shade = _shade(base_color, k, len(techs))
                fig.add_trace(go.Scatter(
                    x=years, y=ts.tolist(), name=tech,
                    mode='lines', stackgroup=sg_det,
                    fillcolor=shade, line=dict(color=shade, width=0.3),
                    legendgroup=f'mob_det_{cat}_{fuel}',
                    legendgrouptitle_text=f'{cat.capitalize()} — {fuel}',
                    showlegend=True, visible=False,
                    hovertemplate=f'%{{y:,.0f}} {unit}<extra>' + tech + '</extra>',
                ), row=2, col=col)
                mob_trace_meta.append(('det', fuel))   # ← insertion-order record


    n_mob = len(mob_trace_meta)

    # ── Buttons ─────────────────────────────────────────────────────────────────
    # Order of all traces:
    #   [n_overview energy ov] + [n_detail energy det] + [n_kpi] +
    # mob_trace_meta is in exact trace-insertion order — visibility must match it

    def _make_vis(show_energy_ov, show_energy_fuel=None, show_mob_fuel=None):
        e_ov  = [show_energy_ov] * n_overview
        e_det = [(detail_trace_meta[i] == show_energy_fuel) if not show_energy_ov else False
                 for i in range(n_detail)]
        kpi_v = [True] * n_kpi
        # Mob: iterate in exact insertion order from mob_trace_meta
        mob_v = []
        for typ, fuel in mob_trace_meta:
            if typ == 'elec':
                mob_v.append(True)
            elif typ == 'ov':
                mob_v.append(show_mob_fuel is None)
            else:  # 'det'
                mob_v.append(fuel == show_mob_fuel if show_mob_fuel else False)
        return e_ov + e_det + kpi_v + mob_v

    # Energy drill-down buttons
    energy_buttons = [dict(
        label='← Energy overview', method='update',
        args=[{'visible': _make_vis(True)},
              {'title': f'{case_study} — System summary'}],
    )]
    for fuel in fuel_order:
        n_techs = sum(1 for f in detail_trace_meta if f == fuel)
        energy_buttons.append(dict(
            label=f'{fuel} ({n_techs})',
            method='update',
            args=[{'visible': _make_vis(False, show_energy_fuel=fuel)},
                  {'title': f'{case_study} — Energy: {fuel}'}],
        ))

    # Mobility drill-down buttons
    mob_fuels_present = list(dict.fromkeys(
        fuel for typ, fuel in mob_trace_meta if typ == 'ov'
    ))
    mob_buttons = [dict(
        label='← Mob. overview', method='update',
        args=[{'visible': _make_vis(True, show_mob_fuel=None)},
              {'title': f'{case_study} — System summary'}],
    )]
    for fuel in mob_fuels_present:
        n_techs = sum(1 for typ, f in mob_trace_meta if typ == 'det' and f == fuel)
        mob_buttons.append(dict(
            label=f'{fuel} ({n_techs})',
            method='update',
            args=[{'visible': _make_vis(True, show_mob_fuel=fuel)},
                  {'title': f'{case_study} — Mobility: {fuel}'}],
        ))

    fig.update_layout(
        title=dict(text=f'{case_study} — System summary', x=0.5),
        height=860,
        hovermode='x unified',
        legend=dict(orientation='v', x=1.02, y=1, xanchor='left', yanchor='top',
                    tracegroupgap=10),
        updatemenus=[
            dict(  # energy drill-down — above figure (clear of title)
                type='buttons', direction='right',
                x=0.0, xanchor='left', y=1.13, yanchor='top',
                bgcolor='#e8f0fe', bordercolor='#aaaacc',
                font=dict(size=11), buttons=energy_buttons,
            ),
            dict(  # mobility drill-down — below figure (clear of x-axis label)
                type='buttons', direction='right',
                x=0.0, xanchor='left', y=-0.12, yanchor='top',
                bgcolor='#e8fee8', bordercolor='#aaccaa',
                font=dict(size=11), buttons=mob_buttons,
            ),
        ],
        margin=dict(t=100, b=100),
    )
    fig.update_xaxes(title_text='Year', dtick=5)
    fig.update_yaxes(title_text='TWh/y', row=1, col=1)
    fig.update_yaxes(title_text='Share [%]', range=[0, 105], row=1, col=2)
    fig.update_yaxes(title_text='Mpkm/y', row=2, col=1)
    fig.update_yaxes(title_text='Mtkm/y', row=2, col=2)

    _save(fig, outdir, '0_Summary.html')



# ===========================================================================
# TEMPORARY: Monthly H2 layer balance (exploratory)
# ===========================================================================

def plot_monthly_h2_layer(results, outdir, case_study):
    """Monthly H2 layer balance: production (+) and consumption (-) per tech [GWh].
    TEMPORARY — helps understand H2 storage cycle."""
    fmt_key = 'F_Mult_t'
    yb_key  = 'Year_balance'
    if results.get(fmt_key) is None or results.get(yb_key) is None:
        print(f'[SKIP] {fmt_key} or {yb_key} not in results'); return

    yb = results[yb_key].reset_index()
    yb.columns = [str(c) for c in yb.columns]
    layers_present = [l for l in H2_LAYERS if l in yb.columns]
    if not layers_present:
        print('[SKIP] No H2 flow layers in Year_balance'); return

    for l in layers_present:
        yb[l] = pd.to_numeric(yb[l], errors='coerce').fillna(0)
    yb['h2_total'] = yb[layers_present].sum(axis=1)

    # techs with any meaningful H2 flow
    sig_techs = set(yb[yb['h2_total'].abs() > 0.01]['Elements'])

    fmt = results[fmt_key].reset_index()
    fmt.columns = ['Years', 'Technologies', 'Periods', 'GW']
    fmt = fmt[fmt['Technologies'].isin(sig_techs)].copy()
    fmt['GW']    = pd.to_numeric(fmt['GW'], errors='coerce').fillna(0)
    fmt['t_op']  = fmt['Periods'].apply(lambda p: _T_OP[int(p)])
    fmt['GWh']   = fmt['GW'] * fmt['t_op']
    fmt['Year']  = fmt['Years'].str.replace('YEAR_', '')
    fmt['Month'] = fmt['Periods'].apply(lambda p: MONTH_LABELS[int(p) - 1])

    # sign per (year, tech) from annual Year_balance
    yb['Year'] = yb['Years'].str.replace('YEAR_', '')
    sign_map = {(row['Year'], row['Elements']): (1 if row['h2_total'] > 0 else -1)
                for _, row in yb[yb['h2_total'].abs() > 0.01].iterrows()}

    fmt['sign']       = fmt.apply(lambda r: sign_map.get((r['Year'], r['Technologies']), 1), axis=1)
    fmt['GWh_signed'] = fmt['GWh'] * fmt['sign']

    for year in [y for y in YEARS_ORDER if y in fmt['Year'].unique()]:
        sub = fmt[fmt['Year'] == year].copy()
        if sub['GWh_signed'].abs().sum() < 1:
            continue

        # keep only techs with non-negligible H2 flows this year
        tech_totals = sub.groupby('Technologies')['GWh_signed'].sum().abs()
        keep = tech_totals[tech_totals > 0.1].index.tolist()
        sub = sub[sub['Technologies'].isin(keep)]

        fig = go.Figure()
        for tech in sorted(keep):
            ts = sub[sub['Technologies'] == tech]
            fig.add_trace(go.Bar(
                x=ts['Month'],
                y=ts['GWh_signed'],
                name=tech,
            ))
        fig.update_layout(
            barmode='relative',
            title=f'{case_study} — Monthly H2 layer balance {year} [GWh]',
            xaxis_title='Month',
            yaxis_title='GWh',
            xaxis={'categoryorder': 'array', 'categoryarray': MONTH_LABELS},
            legend_title='Technology',
            height=500,
        )
        _save(fig, outdir, f'99_H2_monthly_{year}.html')


# ---------------------------------------------------------------------------
# CO₂ SANKEY — per-year CO₂ flow diagram (inspired by _build_sankey_df)
# ---------------------------------------------------------------------------

_CO2_LAYERS_SET = {'CO2_A', 'CO2_C', 'CO2_E', 'CO2_S', 'CO2_CS'}

# Layers that are NOT carbon-containing fuels — exclude from upstream fuel links
_CO2_SK_EXCL_RE = re.compile(
    r'^(ELECTRICITY|H2_HP|H2_LP|H2_HT|HEAT_|MOB_PRIVATE|MOB_PUBLIC|MOB_FREIGHT'
    r'|END_USES|HOUSEHOLDS|SERVICES|INDUSTRY|AGRICULTURE|EXPORT'
    r'|LIGHTING|APPLIANCE|SPACE_|WATER_HEAT|RES_)',
    re.IGNORECASE)

_CO2_SK_NODE_COLORS = {
    'CO2_A':  '#DAA520',
    'CO2_C':  '#1a7a4a',
    'CO2_E':  '#87CEEB',
    'CO2_S':  '#4a4a6a',
    'CO2_CS': '#8888AA',
}


def _build_co2_sankey_df(results, year_str, min_val=1.0):
    """Same pipeline as _build_sankey_df but keeps CO₂ layers as hub nodes
    and filters to CO₂-relevant flows only."""
    yb = results["Year_balance"].reset_index()
    yb.columns = [str(c) for c in yb.columns]
    yb = yb[yb["Years"] == year_str].copy()

    layer_cols = [c for c in yb.columns if c not in ("Years", "Elements")]

    df = yb.melt(id_vars="Elements", value_vars=layer_cols,
                 var_name="Flow", value_name="value")
    df.rename(columns={"Elements": "Technologies"}, inplace=True)
    df["value"]        = pd.to_numeric(df["value"], errors="coerce").fillna(0)
    df["Technologies"] = df["Technologies"].astype(str)
    df["Flow"]         = df["Flow"].astype(str)
    df = df[df["value"].abs() > 0]

    # Strip distance variants then apply family grouping (same as energy Sankey)
    df["Technologies"] = df["Technologies"].apply(
        lambda t: re.sub(r'_(SD|MD|LD|ELD)$', '', t, flags=re.IGNORECASE))
    df["Technologies"] = df["Technologies"].apply(_group_tech)

    # Sign convention: positive = tech produces layer → (tech→layer)
    #                  negative = tech consumes layer → (layer→tech)
    df.rename(columns={"Technologies": "target", "Flow": "source"}, inplace=True)
    mask = df["value"] > 0
    df.loc[mask, ["target", "source"]] = df.loc[mask, ["source", "target"]].to_numpy()
    df["value"] = df["value"].abs()

    # Merge resource pressure variants into a single node before groupby so that
    # self-supply detection (source == target → IMP_) works correctly.
    _CO2_RES_MERGE = {'NG_LP': 'NG', 'NG_MP': 'NG', 'NG_HP': 'NG'}
    df["source"] = df["source"].replace(_CO2_RES_MERGE)
    df["target"] = df["target"].replace(_CO2_RES_MERGE)

    df = df.groupby(["source", "target"]).sum().reset_index()

    # Self-supply resource elements → IMP_ prefix (e.g. WOOD element → IMP_WOOD)
    imp_mask = df["source"] == df["target"]
    df.loc[imp_mask, "source"] = "IMP_" + df.loc[imp_mask, "source"]

    # Drop grid/compression infrastructure
    skip = lambda s: bool(_SKIP_INFRA_RE.match(s)) or s in _SKIP_TECHS
    df = df[~df["source"].apply(skip) & ~df["target"].apply(skip)]
    df = df[df["source"] != df["target"]]

    # --- Filter to CO₂-relevant flows ---
    # 1) All nodes that directly touch a CO₂ layer
    co2_connected = set()
    for layer in _CO2_LAYERS_SET:
        co2_connected |= set(df.loc[df["source"] == layer, "target"])
        co2_connected |= set(df.loc[df["target"] == layer, "source"])
    co2_connected -= _CO2_LAYERS_SET

    # 2) Carbon-containing resources consumed by CO₂-connected techs
    #    (exclude electricity, heat, H2, mobility services)
    # Electricity-layer nodes (ELECTRICITY_EHV etc.) can be CO₂-connected via a
    # direct CO₂_E emission factor on the import tech, but their *producers*
    # (HYDRO_DAM, HYDRO_RIVER …) must not be treated as carbon fuels — they supply
    # a non-carbon energy carrier, not a combustion feedstock.
    _co2_fuel_targets = {t for t in co2_connected if not _CO2_SK_EXCL_RE.match(t)}
    carbon_resources = {
        s for s in df.loc[df["target"].isin(_co2_fuel_targets), "source"]
        if not _CO2_SK_EXCL_RE.match(s)
        and s not in _CO2_LAYERS_SET
        and not s.startswith("IMP_")
    }

    # 3) Keep rows matching any of these roles:
    #    a) CO₂ layer on either side (core CO₂ flows)
    #    b) carbon resource → CO₂-connected tech (upstream fuel input)
    #    c) IMP_ → carbon resource (import of that fuel)
    #    d) CO₂-connected tech → carbon resource (tech produces a resource, e.g. loops)
    co2_side      = df["source"].isin(_CO2_LAYERS_SET) | df["target"].isin(_CO2_LAYERS_SET)
    fuel_to_tech  = df["source"].isin(carbon_resources) & df["target"].isin(_co2_fuel_targets)
    import_to_res = df["source"].str.startswith("IMP_") & df["target"].isin(carbon_resources)
    tech_to_res   = df["source"].isin(co2_connected) & df["target"].isin(carbon_resources)

    df = df[co2_side | fuel_to_tech | import_to_res | tech_to_res].copy()

    # ── Rescale ALL resource/import links to kt CO₂ for flow balance ─────────
    # All links must share the same unit so that width-in = width-out at every node.
    # CO₂ layer links are already in kt CO₂.  Resource/import links are in GWh.
    #
    # Algorithm:
    #   1. For each resource→tech link: replace GWh with the fraction of the tech's
    #      CO₂ output attributable to that resource (proportional to GWh inputs).
    #   2. For each resource node: rescale its supply links (IMP_→res, tech→res) so
    #      that total supply = total CO₂ flowing out, minus any CO₂ already flowing
    #      in from CO₂ layers (e.g. CO2_E→BIOMASS biogenic absorption).
    #      This makes BIOMASS node balance: biogenic + import = combustion CO₂.

    # CO₂ output of each non-layer node: sum of its outgoing flows to CO₂ layers
    _co2_out = (
        df[~df["source"].isin(_CO2_LAYERS_SET) & df["target"].isin(_CO2_LAYERS_SET)]
        .groupby("source")["value"].sum()
    )
    # CO₂ already flowing IN to each resource node from CO₂ layers
    _co2_in_from_layer = (
        df[df["source"].isin(_CO2_LAYERS_SET) & df["target"].isin(carbon_resources)]
        .groupby("target")["value"].sum()
    )

    # Step 1 — resource→tech links: split each tech's CO₂ output proportionally
    # across its resource inputs (by original GWh fractions)
    res_tech_mask = df["source"].isin(carbon_resources) & df["target"].isin(co2_connected)
    if res_tech_mask.any():
        rt = df[res_tech_mask].copy()
        gwh_per_tech = rt.groupby("target")["value"].transform("sum")
        rt["value"] = (
            rt["value"] / gwh_per_tech.replace(0, 1)
            * rt["target"].map(_co2_out).fillna(0)
        )
        df.loc[res_tech_mask, "value"] = rt["value"].values

    # Step 2 — supply links (IMP_→res and tech→res): rescale so resource node balances.
    # needed = total CO₂ out from resource − CO₂ already in from CO₂ layers
    for res in carbon_resources:
        out_total = df.loc[df["source"] == res, "value"].sum()
        in_from_layer = _co2_in_from_layer.get(res, 0.0)
        needed = max(0.0, out_total - in_from_layer)
        supply_mask = ~df["source"].isin(_CO2_LAYERS_SET) & (df["target"] == res)
        if not supply_mask.any():
            continue
        if needed == 0.0:
            df.loc[supply_mask, "value"] = 0.0
        else:
            cur = df.loc[supply_mask, "value"].sum()
            if cur > 0:
                df.loc[supply_mask, "value"] *= needed / cur

    # Step 3 — clip CO₂_A / CO₂_C inflows to non-layer nodes so those nodes balance.
    # CO₂_E (biogenic absorption) is intentionally excluded: it covers the full carbon
    # in the resource, including fractions that travel via WET_BIOMASS → AN_DIG →
    # BIOGAS → CO₂_A paths shown elsewhere in the diagram.  Clipping CO₂_E would
    # under-count the atmospheric sink and make CO₂_E appear net-positive.
    _CO2_CLIPPABLE = _CO2_LAYERS_SET - {"CO2_E"}
    all_layer_targets = (
        set(df.loc[df["source"].isin(_CO2_LAYERS_SET), "target"]) - _CO2_LAYERS_SET
    )
    for node in all_layer_targets:
        out_total = df.loc[df["source"] == node, "value"].sum()
        layer_in_mask = df["source"].isin(_CO2_CLIPPABLE) & (df["target"] == node)
        if not layer_in_mask.any() or out_total <= 0:
            continue
        layer_in_total = df.loc[layer_in_mask, "value"].sum()
        if layer_in_total > out_total:
            df.loc[layer_in_mask, "value"] *= out_total / layer_in_total

    # Step 4 — synthetic CO2_A → CO2_E link for uncaptured point-source emissions.
    # The model has no explicit "vent CO2_A to atmosphere" tech; CO2_A is produced
    # by combustion/industry but only consumed if CARBON_CAPTURE is deployed.
    # Uncaptured CO2_A must physically reach the atmosphere (CO2_E).
    co2a_produced = df.loc[df["target"] == "CO2_A", "value"].sum()
    co2a_captured = df.loc[df["source"] == "CO2_A", "value"].sum()
    co2a_uncaptured = co2a_produced - co2a_captured
    if co2a_uncaptured > min_val:
        vent = pd.DataFrame([{
            "source": "CO2_A", "target": "CO2_E", "value": co2a_uncaptured
        }])
        df = pd.concat([df, vent], ignore_index=True)

    df = df[df["value"] >= min_val]
    return df


def plot_sankey_co2(results, outdir, case_study):
    """CO₂ Sankey per year: imports → resources → techs ↔ CO₂ layers → sequestration / utilization.

    All link widths in kt CO₂: resource/import links are rescaled from GWh so that
    every node is flow-balanced (width in = width out).
    CO₂ layer nodes coloured distinctively; IMP_* nodes in light blue.
    """
    if results.get("Year_balance") is None:
        print("[SKIP] Year_balance not in results"); return

    for year in YEARS_ORDER:
        year_str = f"YEAR_{year}"
        try:
            df = _build_co2_sankey_df(results, year_str)
        except Exception as e:
            print(f"[SKIP] CO2 Sankey {year}: {e}"); continue
        if df.empty:
            continue

        all_nodes = list(dict.fromkeys(
            list(df["source"].unique()) + list(df["target"].unique())))
        node_idx = {n: i for i, n in enumerate(all_nodes)}

        def node_color(n):
            if n in _CO2_SK_NODE_COLORS: return _CO2_SK_NODE_COLORS[n]
            if n.startswith("IMP_"):      return '#D4E6F1'
            return '#D5D8DC'

        fig = go.Figure(data=[go.Sankey(
            valueformat=".0f",
            arrangement="snap",
            node=dict(
                pad=10, thickness=12,
                line=dict(color="black", width=0.5),
                label=all_nodes,
                color=[node_color(n) for n in all_nodes],
            ),
            link=dict(
                source=[node_idx[s] for s in df["source"]],
                target=[node_idx[t] for t in df["target"]],
                value=df["value"].tolist(),
            ),
        )])
        fig.update_layout(
            title_text=f"{case_study} — CO₂ flows {year}  [kt CO₂]",
            font_size=10,
            height=800,
        )
        _save(fig, outdir, f"17_CO2_Sankey_{year}.html")


# ===========================================================================
# MAIN
# ===========================================================================

# ---------------------------------------------------------------------------
# MONTHLY ELECTRICITY LAYER — production (+) and consumption (-) per tech
# ---------------------------------------------------------------------------

def plot_monthly_electricity_layer(results, outdir, case_study):
    """Monthly electricity layer balance per tech [GWh], one file per year.

    Uses Monthly_Prod which already carries the sign for storage:
      +  producing / discharging  (PV, WIND, HYDRO_DAM, HYDRO_STORAGE discharging…)
      -  consuming / charging     (HYDRO_STORAGE charging, demand…)

    Techs are filtered to those with a non-zero annual electricity flow in Year_balance.
    """
    mp_key = 'Monthly_Prod'
    yb_key = 'Year_balance'
    if results.get(mp_key) is None or results.get(yb_key) is None:
        print(f'[SKIP] {mp_key} or {yb_key} not in results'); return

    yb = results[yb_key].reset_index()
    yb.columns = [str(c) for c in yb.columns]
    layers_present = [l for l in ELEC_LAYERS if l in yb.columns]
    if not layers_present:
        print('[SKIP] No electricity layers in Year_balance'); return

    for l in layers_present:
        yb[l] = pd.to_numeric(yb[l], errors='coerce').fillna(0)
    yb['elec_total'] = yb[layers_present].sum(axis=1)
    elec_techs = set(yb[yb['elec_total'].abs() > 0.01]['Elements'])

    mp = results[mp_key].reset_index()
    mp.columns = ['Years', 'Technologies', 'Periods', 'GWh']
    mp = mp[mp['Technologies'].isin(elec_techs)].copy()
    mp['GWh']   = pd.to_numeric(mp['GWh'], errors='coerce').fillna(0)
    mp['Year']  = mp['Years'].str.replace('YEAR_', '')
    mp['Month'] = mp['Periods'].apply(lambda p: MONTH_LABELS[int(p) - 1])

    # For non-storage techs, Monthly_Prod is always positive; apply sign from Year_balance
    # For storage techs (e.g. HYDRO_STORAGE), Monthly_Prod already carries +/- sign
    yb['Year'] = yb['Years'].str.replace('YEAR_', '')
    sign_map = {(row['Year'], row['Elements']): (1 if row['elec_total'] >= 0 else -1)
                for _, row in yb[yb['elec_total'].abs() > 0.01].iterrows()}

    _sto_re = re.compile('|'.join(re.escape(k) for k in _STO_KEYWORDS), re.IGNORECASE)

    def _signed(row):
        if _sto_re.search(row['Technologies']):
            return row['GWh']   # storage: Monthly_Prod already signed
        return row['GWh'] * sign_map.get((row['Year'], row['Technologies']), 1)

    mp['GWh_signed'] = mp.apply(_signed, axis=1)

    for year in [y for y in YEARS_ORDER if y in mp['Year'].unique()]:
        sub = mp[mp['Year'] == year].copy()
        if sub['GWh_signed'].abs().sum() < 1:
            continue

        tech_totals = sub.groupby('Technologies')['GWh_signed'].apply(lambda s: s.abs().sum())
        keep = tech_totals[tech_totals > 0.1].index.tolist()
        sub = sub[sub['Technologies'].isin(keep)]

        fig = go.Figure()
        for tech in sorted(keep):
            ts = sub[sub['Technologies'] == tech].copy()
            fig.add_trace(go.Bar(
                x=ts['Month'],
                y=ts['GWh_signed'],
                name=tech,
                marker_color=str(_tech_color(tech)),
            ))
        fig.update_layout(
            barmode='relative',
            title=f'{case_study} — Monthly electricity balance {year} [GWh]',
            xaxis_title='Month',
            yaxis_title='GWh',
            xaxis={'categoryorder': 'array', 'categoryarray': MONTH_LABELS},
            legend_title='Technology',
            height=600,
        )
        _save(fig, outdir, f'18_Elec_monthly_{year}.html')


def run(case_study):
    results = load_results(case_study)
    outdir  = os.path.join(OUT_DIR, case_study, 'graphs')
    os.makedirs(outdir, exist_ok=True)
    # remove stale html files before regenerating
    for f in os.listdir(outdir):
        if f.endswith('.html'):
            os.remove(os.path.join(outdir, f))
    print(f"Output: {outdir}\n")

    plot_initial_config(results, outdir, case_study)

    if PLOTS.get('summary'):           plot_summary_dashboard(results, os.path.join(OUT_DIR, case_study), case_study)
    if PLOTS.get('gwp'):               plot_gwp(results, outdir, case_study)
    if PLOTS.get('transition_cost'):   plot_transition_cost(results, outdir, case_study)
    if PLOTS.get('capex_breakdown'):   plot_capex_breakdown(results, outdir, case_study)
    if PLOTS.get('opex_breakdown'):    plot_opex_breakdown(results, outdir, case_study)
    if PLOTS.get('total_cost'):        plot_total_cost_breakdown(results, outdir, case_study)
    if PLOTS.get('resources'):         plot_resources(results, outdir, case_study)
    if PLOTS.get('annual_prod'):       plot_annual_prod(results, outdir, case_study)
    if PLOTS.get('monthly_prod'):      plot_monthly_prod(results, outdir, case_study)
    if PLOTS.get('monthly_resources'):   plot_monthly_resources(results, outdir, case_study)
    if PLOTS.get('monthly_co2_storage'): plot_monthly_co2_storage(results, outdir, case_study)
    if PLOTS.get('load_factor'):       plot_load_factor_heatmap(results, outdir, case_study)
    if PLOTS.get('mobility_pies'):     plot_mobility_pies(results, outdir, case_study)
    if PLOTS.get('f_new'):             plot_fnew_by_category(results, outdir, case_study, col='F_new',   prefix='2')
    if PLOTS.get('f_old'):             plot_fnew_by_category(results, outdir, case_study, col='F_old',   prefix='3')
    if PLOTS.get('f_decom'):           plot_fnew_by_category(results, outdir, case_study, col='F_decom', prefix='3b')
    if PLOTS.get('number_of_units'):   plot_number_of_units(results, outdir, case_study)
    if PLOTS.get('electricity_layer'): plot_electricity_layer(results, outdir, case_study)
    if PLOTS.get('heat_layer'):        plot_heat_layer(results, outdir, case_study)
    if PLOTS.get('h2_layer'):          plot_h2_layer(results, outdir, case_study)
    if PLOTS.get('ng_layer'):          plot_ng_layer(results, outdir, case_study)
    if PLOTS.get('mobility_layer'):    plot_mobility_layer(results, outdir, case_study)
    if PLOTS.get('sankey'):            plot_sankey(results, outdir, case_study)
    if PLOTS.get('gwp_breakdown'):     plot_gwp_breakdown(results, outdir, case_study)
    if PLOTS.get('storage_levels'):    plot_storage_levels(results, outdir, case_study)
    if PLOTS.get('monthly_h2'):        plot_monthly_h2_layer(results, outdir, case_study)
    if PLOTS.get('sankey_co2'):        plot_sankey_co2(results, outdir, case_study)
    if PLOTS.get('monthly_electricity'): plot_monthly_electricity_layer(results, outdir, case_study)


    create_dashboard(outdir, case_study)
    print("Done.")


if __name__ == '__main__':
    case = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_CASE
    run(case)
