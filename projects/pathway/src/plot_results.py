"""
plot_results.py
Usage:
  python plot_results.py [case_study]
"""
import os, sys, pickle, re, glob as _glob
import json
import zlib
import warnings
from typing import Union
import numpy as np
import colorsys
import webbrowser
warnings.filterwarnings('ignore', category=FutureWarning)
warnings.filterwarnings('ignore', category=UserWarning)

_chart_count = 0
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
    'capex_breakdown':        True,   # 03 — capex lump-sum breakdown by tech
    'capex_crf_breakdown':    True,   # 03b — capex CRF attributed to installation phase
    'capex_crf_active_phase': True,   # 03c — capex CRF distributed across active phases (Python)
    'capex_crf_ampl':         True,   # 03d — C_inv_phase_CRF directly from AMPL (total, no tech breakdown)
    'capex_no_actu':          True,   # 03d2 — C_inv_phase_no_actu directly from AMPL (total, non-actualised)
    'capex_no_actu_breakdown': True,  # 03d3 — C_inv_phase_tech_no_actu breakdown by tech, non-actualised
    'capex_summary':          True,   # 03e — 3-panel summary: lump-sum | CRF install | CRF active
    'opex_breakdown':   True,   # 04 — opex breakdown by tech
    'opex_no_actu_breakdown': True,  # 04b — opex breakdown by tech, non-actualised
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
    'f_mult':           True,   # 4c — installed capacity (F_Mult) by category over years
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

# Midpoint of each phase relative to the calendar — used for CRF reporting
_PHASE_MIDPOINTS = {
    '2015_2020': 2017.5, '2020_2025': 2022.5, '2025_2030': 2027.5,
    '2030_2035': 2032.5, '2035_2040': 2037.5, '2040_2045': 2042.5,
    '2045_2050': 2047.5,
}
_SDR_DEFAULT = 0.04   # Social Discount Rate — change here if it differs from 4 %

_YEARS_ACTIVE_DAT = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), '..', 'model', 'PES_data_years_active.dat'
)
_REMAINING_YEARS_DAT = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), '..', 'model', 'PES_data_remaining_wnd.dat'
)


def _load_years_active(dat_path=None):
    """Parse PES_data_years_active.dat into a dict {(tech, p_inst, p_active): float}."""
    path = dat_path or _YEARS_ACTIVE_DAT
    if not os.path.exists(path):
        print(f'[WARN] years_active dat not found: {path}')
        return {}
    ya = {}
    tech, col_phases = None, []
    with open(path, encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#') or line == 'param years_active :=':
                continue
            # Block header: [TECH, *, *] :  p1  p2  ...  :=
            m = re.match(r'\[([^,\]]+),\s*\*,\s*\*\]\s*:(.*):=', line)
            if m:
                tech = m.group(1).strip()
                col_phases = m.group(2).strip().split()
                continue
            # Data row: p_inst  v1  v2  ...
            if tech and col_phases and re.match(r'\d{4}_\d{4}', line):
                parts = line.split()
                p_inst = parts[0]
                for p, v in zip(col_phases, parts[1:]):
                    val = float(v)
                    if val > 0:
                        ya[(tech, p_inst, p)] = val
    return ya


def _load_remaining_years(dat_path=None):
    """Parse PES_data_remaining_wnd.dat into a dict {(tech, p_inst): remaining_years}."""
    path = dat_path or _REMAINING_YEARS_DAT
    if not os.path.exists(path):
        print(f'[WARN] remaining_years dat not found: {path}')
        return {}
    ry = {}
    col_phases = []
    with open(path, encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            if line.startswith('param remaining_years'):
                # header: param remaining_years : p1 p2 ... :=
                parts = line.split(':')
                if len(parts) >= 2:
                    col_phases = parts[1].replace(':=', '').split()
                continue
            if col_phases and re.match(r'[A-Z]', line):
                parts = line.split()
                tech = parts[0]
                for p, v in zip(col_phases, parts[1:]):
                    val = float(v)
                    if val > 0:
                        ry[(tech, p)] = val
    return ry


# Cache so the dat files are only parsed once per process
_YA_CACHE = None
_RY_CACHE = None

def _get_years_active():
    global _YA_CACHE
    if _YA_CACHE is None:
        _YA_CACHE = _load_years_active()
    return _YA_CACHE


def _get_remaining_years():
    global _RY_CACHE
    if _RY_CACHE is None:
        _RY_CACHE = _load_remaining_years()
    return _RY_CACHE


def _compute_salvage_per_phase(results):
    """Return a DataFrame with salvage value (negative) per (Phases, Technologies).

    Uses C_inv_return_phase directly from AMPL — exact values, no approximation.
    """
    crp = results.get('C_inv_return_phase')
    if crp is None:
        return None

    df = crp.copy().reset_index()
    df.columns = ['Phases', 'Technologies', 'salvage']
    df['salvage'] = -pd.to_numeric(df['salvage'], errors='coerce').fillna(0)
    df = df[df['Phases'] != INIT_PHASE]
    df = df[df['salvage'].abs() > 1e-9]
    if df.empty:
        return None
    return df.set_index(['Phases', 'Technologies'])


def transition_cost_by_phase_category(results):
    """Canonical system-cost breakdown: CAPEX (lump-sum, net of salvage via
    C_inv_return_phase) + OPEX (including the standalone C_opex[YEAR_2020]
    term), both excluding the 2015_2020 initialisation phase.

    This is the single source of truth for scenario-comparison cost totals
    (S0..S8): the CRF-annuity formulation (C_tot_capex, C_inv_phase_CRF)
    answers a different question (cost recovery under a hurdle rate) and is
    deliberately NOT used here — mixing the two conventions is what caused
    past scenario-summary totals to drift out of sync with the per-scenario
    dashboards (0b_Transition_cost.html / 1b_CAPEX_breakdown.html).

    Returns a pd.DataFrame indexed by (Phases, Category) — Category =
    _fnew_category(tech) for CAPEX/OPEX-tech rows, 'RESOURCES' for OPEX-res
    rows — with columns 'CAPEX' and 'OPEX', in B$CAD. Or None if none of the
    three underlying AMPL outputs are present."""
    cinv_tech = results.get('C_inv_phase_tech')
    op_tech = results.get('C_op_phase_tech')
    op_res = results.get('C_op_phase_res')
    if cinv_tech is None and op_tech is None and op_res is None:
        return None

    def _cat_rows(df, item_col):
        d = df.copy().reset_index()
        d.columns = ['Phases', item_col, 'C']
        d['Phases'] = d['Phases'].astype(str)
        d['C'] = pd.to_numeric(d['C'], errors='coerce').fillna(0) / 1000  # M$ -> B$
        d = d[d['Phases'] != INIT_PHASE]
        d['Category'] = 'RESOURCES' if item_col == 'Res' else d[item_col].apply(_fnew_category)
        return d.groupby(['Phases', 'Category'])['C'].sum()

    capex = _cat_rows(cinv_tech, 'Tech') if cinv_tech is not None else pd.Series(dtype=float)

    salvage_df = _compute_salvage_per_phase(results)
    if salvage_df is not None:
        s = salvage_df.reset_index()
        s.columns = ['Phases', 'Tech', 'salvage']
        s['salvage'] = s['salvage'] / 1000  # M$ -> B$
        s['Category'] = s['Tech'].apply(_fnew_category)
        capex = capex.add(s.groupby(['Phases', 'Category'])['salvage'].sum(), fill_value=0)

    opex_parts = []
    if op_tech is not None:
        opex_parts.append(_cat_rows(op_tech, 'Tech'))
    if op_res is not None:
        opex_parts.append(_cat_rows(op_res, 'Res'))
    opex = pd.concat(opex_parts).groupby(level=[0, 1]).sum() if opex_parts else pd.Series(dtype=float)

    # C_tot_opex = C_opex[YEAR_2020] + sum_p (C_op_phase_tech[p] + C_op_phase_res[p])
    # (Opex_tot_cost_calculation, PES_main.mod), and C_opex[y] = sum_tech C_maint[y,tech]
    # + sum_res C_op[y,res] (Opex_cost_calculation) — so the standalone YEAR_2020 term
    # is exactly recoverable, per-Element, from Cost_breakdown (indexed by Years,
    # Elements, with C_maint/C_op columns). Categorise it there instead of dumping it
    # into a catch-all 'OTHER' bucket, and fold it into the first active phase so OPEX
    # still reconciles exactly with C_tot_opex.
    cost_breakdown = results.get('Cost_breakdown')
    if cost_breakdown is not None:
        cb = cost_breakdown.reset_index()
        cb.columns = ['Years', 'Elements'] + list(cb.columns[2:])
        cb = cb[cb['Years'].astype(str) == 'YEAR_2020'].copy()
        cb['opex_2020'] = (pd.to_numeric(cb.get('C_maint'), errors='coerce').fillna(0)
                            + pd.to_numeric(cb.get('C_op'), errors='coerce').fillna(0)) / 1000  # M$ -> B$
        cb['Category'] = cb['Elements'].apply(_fnew_category)
        for cat, val in cb.groupby('Category')['opex_2020'].sum().items():
            key = (TRANS_PHASES[0], cat)
            opex[key] = opex.get(key, 0.0) + val
    else:
        c_tot_opex = results.get('C_tot_opex')
        if c_tot_opex is not None:
            residual = float(c_tot_opex.iloc[0, 0]) / 1000 - opex.sum()
            key = (TRANS_PHASES[0], 'OTHER')
            opex[key] = opex.get(key, 0.0) + residual

    out = pd.DataFrame({'CAPEX': capex, 'OPEX': opex}).fillna(0).reset_index()
    out['Phases'] = pd.Categorical(out['Phases'], categories=TRANS_PHASES, ordered=True)
    return out.sort_values(['Phases', 'Category']).set_index(['Phases', 'Category'])


def _compute_crf_install_capex(results, sdr=_SDR_DEFAULT):
    """
    Compute the total NPV of CRF annuities, attributed to each installation phase.

    For each (p_inst, tech) with p_inst in TRANS_PHASES:
        C_crf[p_inst, tech] = C_inv_phase_tech[p_inst, tech] * tau[YEAR_ys, tech] * S
    where
        S = sum_p  years_active[tech, p_inst, p] * (1/(1+sdr))^(mid_p - mid_p_inst)

    This equals the lump-sum when SDR == i_hurdle (factor 1+r/2), and differs
    correctly when the hurdle rate varies across scenarios.
    Returns a copy of C_inv_phase_tech with CRF values, or None if tau is missing.
    """
    cinv = results.get('C_inv_phase_tech')
    tau_df = results.get('tau')
    if cinv is None or tau_df is None:
        return None

    ya = _get_years_active()
    x = 1.0 / (1.0 + sdr)

    out = cinv.copy().astype(float)
    for (p_inst, tech), row in cinv.iterrows():
        if p_inst == INIT_PHASE:
            out.loc[(p_inst, tech)] = 0.0
            continue
        ys = int(p_inst.split('_')[0])
        ins_mid = _PHASE_MIDPOINTS[p_inst]
        year_key = f'YEAR_{ys}'
        try:
            tau_val = float(tau_df.loc[(year_key, tech)].iloc[0])
        except (KeyError, IndexError):
            tau_val = 1.0
        S = sum(
            v * x ** (_PHASE_MIDPOINTS[p] - ins_mid)
            for (t, pi, p), v in ya.items()
            if t == tech and pi == p_inst
        )
        out.loc[(p_inst, tech)] = float(row.iloc[0]) * tau_val * S
    return out


def _compute_crf_active_capex(results, sdr=_SDR_DEFAULT):
    """Distribute CRF annuities across active phases (excluding 2015_2020 installations).

    For each (p_active, tech):
        C_crf_active = sum_{p_inst != 2015_2020}
            C_inv_phase_tech[p_inst, tech] * tau[p_inst, tech]
            * years_active[tech, p_inst, p_active]
            * x^(mid_p_active - mid_p_inst)

    This matches what C_inv_phase_CRF from AMPL computes, but per technology
    and without the 2015_2020 contamination.
    """
    cinv  = results.get('C_inv_phase_tech')
    tau_df = results.get('tau')
    if cinv is None or tau_df is None:
        return None

    ya = _get_years_active()
    x  = 1.0 / (1.0 + sdr)

    techs = cinv.index.get_level_values('Technologies').unique()
    out   = {}

    for p_active in TRANS_PHASES:
        mid_p = _PHASE_MIDPOINTS[p_active]
        for tech in techs:
            total = 0.0
            for p_inst in TRANS_PHASES:
                try:
                    cinv_val = float(cinv.loc[(p_inst, tech)].iloc[0])
                except KeyError:
                    continue
                if abs(cinv_val) < 1e-12:
                    continue
                ya_val = ya.get((tech, p_inst, p_active), 0.0)
                if ya_val == 0.0:
                    continue
                ys = int(p_inst.split('_')[0])
                try:
                    tau_val = float(tau_df.loc[(f'YEAR_{ys}', tech)].iloc[0])
                except (KeyError, IndexError):
                    tau_val = 1.0
                mid_inst = _PHASE_MIDPOINTS[p_inst]
                total += cinv_val * tau_val * ya_val * x ** (mid_p - mid_inst)
            out[(p_active, tech)] = total

    idx = pd.MultiIndex.from_tuples(list(out.keys()), names=['Phases', 'Technologies'])
    ser = pd.Series(list(out.values()), index=idx)
    return ser.to_frame('C_inv_crf_active')


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

def _rgb_tuple(c):
    c = str(c)
    if c.startswith('#'):
        c = c.lstrip('#')
        return tuple(int(c[i:i + 2], 16) for i in (0, 2, 4))
    m = re.findall(r'[\d.]+', c)
    return tuple(int(float(x)) for x in m[:3])


def _spread_palette(colors, min_dist=40):
    """Keep only colors pairwise-distant in RGB, so distinct slots never look alike."""
    kept, kept_rgb = [], []
    for c in colors:
        rgb = _rgb_tuple(c)
        if all(sum((a - b) ** 2 for a, b in zip(rgb, k)) ** 0.5 >= min_dist
               for k in kept_rgb):
            kept.append(c)
            kept_rgb.append(rgb)
    return kept


_PALETTE = _spread_palette(
    pc.qualitative.Vivid + pc.qualitative.Bold + pc.qualitative.Safe +
    pc.qualitative.Dark2 + pc.qualitative.Set1 + pc.qualitative.Pastel
)

_FIXED_COLORS = {
    'HYDRO_DAM':       '#1f77b4',   # blue
    'RES_HYDRO':       '#1f77b4',   # blue
    'NG_EHP':          '#ff7f0e',   # orange
    'ELECTRICITY_EHV': 'rgb(93, 105, 177)',   # slate blue — crc32 collided with JETFUEL
}

def _tech_color(name):
    """Deterministic color for a tech/resource name — same name → same color always,
    across charts, case studies and plotting runs (crc32, not the per-process hash())."""
    if name in _FIXED_COLORS:
        return _FIXED_COLORS[name]
    return _PALETTE[zlib.crc32(str(name).encode()) % len(_PALETTE)]

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
    'MOB_PRIVATE':       '#636EFA',   # blue-violet
    'MOB_PUBLIC':        '#19D3F3',   # cyan
    'MOB_FREIGHT':       '#AB63FA',   # purple
    'ELECTRICITY':       '#FFA15A',   # orange
    'HEAT_LOW_T':        '#EF553B',   # red  (aggregated low-T heat)
    'HEAT_LOW_T_DHN':    '#EF553B',   # red
    'HEAT_LOW_T_DECEN':  '#FF6692',   # pink
    'HEAT_HIGH_T':       '#B6E880',   # light green
    'STORAGE':           '#FECB52',   # yellow
    'H2':                '#00CC96',   # green
    'H2_SYNFUELS':       '#17BECF',   # teal
    'INDUSTRY':          '#8C564B',   # brown
    'CO2':               '#636363',   # dark grey
    'RESOURCES':         '#BCBD22',   # olive
    'INFRASTRUCTURE':    '#BAB0AC',   # grey-brown
    'OTHER':             '#D3D3D3',   # light grey
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

def _ensure_plotlyjs(outdir):
    path = os.path.join(outdir, 'plotly.min.js')
    if not os.path.exists(path):
        from plotly.offline import get_plotlyjs
        with open(path, 'w', encoding='utf-8') as f:
            f.write(get_plotlyjs())


def _save(fig, outdir, filename):
    global _chart_count
    os.makedirs(outdir, exist_ok=True)
    _ensure_plotlyjs(outdir)
    path = os.path.join(outdir, filename)
    html = fig.to_html(full_html=True, include_plotlyjs='directory')
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
    _chart_count += 1
    sys.stdout.write(f'\r  Plotting [{_chart_count}]: {filename:<55}')
    sys.stdout.flush()
    if SHOW:
        pio.show(fig)


# ===========================================================================
# LOAD
# ===========================================================================

# DHN is the district-heating-network technology whose F_Mult/CAPEX is sized as the
# aggregate of the individual DHN_* production techs (DHN_HP_ELEC, DHN_BOILER_GAS, ...).
# Keeping it alongside those techs in plots double-counts the same capacity/cost, so it
# is dropped everywhere (exact match only — DHN_* techs are untouched).
_EXACT_TECH_EXCLUDE = {'DHN'}



# Salvage totals must reconcile with C_tot_capex (computed by AMPL over ALL
# technologies, DHN included) — filtering DHN out of these two keys would
# silently drop DHN's C_inv_return from every salvage total downstream
# (plot_capex_crf_ampl, _compute_salvage_per_phase), inflating "lump-sum -
# salvage" above the true C_tot_capex value.
_SALVAGE_KEYS_EXEMPT_FROM_EXCLUSION = {'Cost_return', 'C_inv_return_phase'}


def _drop_excluded_techs(results, excluded=_EXACT_TECH_EXCLUDE):
    for key, df in results.items():
        if key in _SALVAGE_KEYS_EXEMPT_FROM_EXCLUSION:
            continue
        if not isinstance(df, pd.DataFrame) or df.empty:
            continue
        if isinstance(df.index, pd.MultiIndex):
            for level_name in ('Technologies', 'Elements'):
                if level_name in (df.index.names or []):
                    vals = df.index.get_level_values(level_name)
                    if any(v in excluded for v in vals.unique()):
                        df = df[~vals.isin(excluded)]
        elif df.index.name in ('Technologies', 'Elements'):
            if any(v in excluded for v in df.index.unique()):
                df = df[~df.index.isin(excluded)]
        results[key] = df
    return results


def load_results(case_study):
    pkl_path = os.path.join(OUT_DIR, case_study, '_Results.pkl')
    if not os.path.exists(pkl_path):
        raise FileNotFoundError(f"Not found: {pkl_path}")
    with open(pkl_path, 'rb') as f:
        results = pickle.load(f)
    print(f"Loaded: {pkl_path}")
    print(f"  Keys: {[k for k in results if results[k] is not None]}")
    results = _drop_excluded_techs(results)
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

_CO2_LAYER_ELEMENTS = frozenset({'CO2_A', 'CO2_C', 'CO2_E', 'CO2_S', 'CO2_CS', 'CO2_EE'})


def plot_gwp(results, outdir, case_study):
    yb = results.get('Year_balance')
    if yb is None:
        print('[SKIP] Year_balance not in results for GWP plot'); return

    co2_cols = [c for c in ('CO2_A', 'CO2_E') if c in yb.columns]
    if not co2_cols:
        print('[SKIP] No CO2 columns in Year_balance'); return

    # Sum CO2_A + CO2_E per year, excluding electricity imports (out-of-territory)
    rows = []
    for (year_str, tech), row in yb.iterrows():
        if tech == 'ELECTRICITY_EHV' or tech in _CO2_LAYER_ELEMENTS:
            continue
        gwp = float(np.nansum([pd.to_numeric(row.get(c, 0), errors='coerce') for c in co2_cols]))
        rows.append({'Year': int(str(year_str).replace('YEAR_', '')), 'GWP_kt': gwp})
    if not rows:
        print('[SKIP] No GWP data'); return

    gwp_df = pd.DataFrame(rows).groupby('Year', as_index=False)['GWP_kt'].sum()
    gwp_df = gwp_df[gwp_df['Year'].isin([int(y) for y in YEARS_ORDER])].sort_values('Year')

    # GWP limit from TotalGwp result (model constraint)
    limit_df = None
    tg = results.get('TotalGwp')
    if tg is not None:
        tg = tg.copy().reset_index()
        tg.columns = [str(c) for c in tg.columns]
        tg['Year'] = tg.iloc[:, 0].str.replace('YEAR_', '').astype(int)
        lim_col = 'Gwp_limit' if 'Gwp_limit' in tg.columns else ('gwp_limit' if 'gwp_limit' in tg.columns else None)
        if lim_col:
            limit_df = tg[['Year', lim_col]].rename(columns={lim_col: 'Limit_kt'})
            limit_df['Limit_Mt'] = pd.to_numeric(limit_df['Limit_kt'], errors='coerce') / 1000

    _font     = {'family': 'Arial, Helvetica, sans-serif', 'color': '#333333'}
    _ax_base  = {
        'showgrid': False, 'linecolor': '#DDDDDD',
        'ticks': 'outside', 'tickcolor': '#DDDDDD',
        'tickfont': {'size': 12, 'color': '#555555'},
    }
    _ax_y = {**_ax_base, 'showgrid': True, 'gridcolor': '#EBEBEB', 'gridwidth': 1}

    fig = go.Figure()
    fig.add_bar(x=gwp_df['Year'], y=gwp_df['GWP_kt'] / 1000, name='GWP (excl. elec imports)',
                marker_color='steelblue')
    if limit_df is not None and limit_df['Limit_Mt'].notna().any():
        fig.add_scatter(x=limit_df['Year'], y=limit_df['Limit_Mt'], mode='lines+markers',
                        name='GWP limit', line=dict(color='red', dash='dash'))
    fig.update_layout(
        title={
            'text': (f'<b>Annual GHG emissions [Mt CO₂-eq./y]</b>'
                     f'<br><sup><i>{case_study} — excl. electricity imports</i></sup>'),
            'font': {'family': 'Arial, Helvetica, sans-serif', 'size': 18, 'color': '#1A1A2E'},
            'x': 0.0, 'xanchor': 'left', 'pad': {'l': 6, 't': 4},
        },
        font=_font,
        plot_bgcolor='#F7F9FC', paper_bgcolor='white',
        hovermode='x unified',
        xaxis={**_ax_base,
               'title': {'text': 'Year', 'font': {'size': 13, 'color': '#666666'}},
               'type': 'linear', 'dtick': 5},
        yaxis={**_ax_y,
               'title': {'text': 'Mt CO₂-eq./y', 'font': {'size': 13, 'color': '#666666'}}},
        legend={
            'orientation': 'h', 'y': -0.2,
            'font': {'size': 12, 'color': '#444444'},
            'bgcolor': 'rgba(255,255,255,0)', 'bordercolor': 'rgba(0,0,0,0)',
        },
        height=520,
        margin={'l': 65, 'r': 40, 't': 80, 'b': 100},
    )
    _save(fig, outdir, '0_GWP.html')


# ---------------------------------------------------------------------------
# TOTAL TRANSITION COST
# ---------------------------------------------------------------------------

#ADDED BY PAOLO (to validate)
def _derive_c_material(results):
    """C_material [B$CAD] derived as a residual from TotalTransitionCost = C_tot_capex +
    C_tot_opex + C_material (exact AMPL equality, PES_main.mod's total_cost_transition) --
    avoids adding a new AMPL extraction since Transition_cost/C_tot_capex/C_tot_opex are
    already collected for every run. Correctly comes out ~0 for a plain (non-materials) run,
    since C_material stays fixed at 0 there (see critical_materials/ampl_files/Constraints.mod) --
    safe to call unconditionally. Returns None if the three inputs aren't present."""
    tc = results.get('Transition_cost')
    capex = results.get('C_tot_capex')
    opex = results.get('C_tot_opex')
    if tc is None or capex is None or opex is None or tc.empty or capex.empty or opex.empty:
        return None
    return (float(tc.iloc[0, 0]) - float(capex.iloc[0, 0]) - float(opex.iloc[0, 0])) / 1000  # M$ -> B$


def plot_transition_cost(results, outdir, case_study):
    """CAPEX (lump-sum, net of salvage) + OPEX per phase, plus Materials (critical_materials'
    C_material, if any) as one extra bar, and cumulative total transition cost -- excluding the
    2015_2020 initialisation phase (its investment is a fixed historical given, not a transition
    decision — see max_share_cost_phase comment in PES_main.mod). Built from
    transition_cost_by_phase_category — see that function's docstring for why the CRF-annuity
    formulation (C_tot_capex) is deliberately not used for CAPEX/OPEX here. C_material, by
    contrast, IS the same quantity that feeds TotalTransitionCost either way (it has no separate
    CRF-vs-lump-sum convention of its own) — see _derive_c_material."""
    cost = transition_cost_by_phase_category(results)
    if cost is None:
        print('[SKIP] C_inv_phase_tech / C_op_phase_tech / C_op_phase_res not in results'); return

    by_phase = cost.groupby(level='Phases')[['CAPEX', 'OPEX']].sum()
    phases = [p for p in TRANS_PHASES if p in by_phase.index]
    capex_vals = by_phase['CAPEX'].reindex(phases).fillna(0)
    opex_vals  = by_phase['OPEX'].reindex(phases).fillna(0)

    #ADDED BY PAOLO (to validate)
    c_material = _derive_c_material(results)
    x_labels = list(phases)
    capex_bar = capex_vals.tolist()
    opex_bar = opex_vals.tolist()
    if c_material is not None and abs(c_material) > 1e-6:
        x_labels = x_labels + ['Materials']
        capex_bar = capex_bar + [0]
        opex_bar = opex_bar + [0]
    materials_bar = [0] * len(phases) + ([c_material] if c_material is not None and abs(c_material) > 1e-6 else [])
    total_cum = (pd.Series(capex_bar) + pd.Series(opex_bar) + pd.Series(materials_bar)).cumsum()

    fig = go.Figure()
    fig.add_bar(x=x_labels, y=capex_bar, name='CAPEX (net salvage)', marker_color='#EF553B')
    fig.add_bar(x=x_labels, y=opex_bar, name='OPEX', marker_color='#636EFA')
    if materials_bar and any(materials_bar):
        fig.add_bar(x=x_labels, y=materials_bar, name='Materials (recycling, net)', marker_color='#00CC96')
    fig.add_scatter(x=x_labels, y=total_cum.tolist(), mode='lines+markers',
                    name='Total transition cost (cumul.)', line=dict(color='black', width=2))
    final = total_cum.iloc[-1] if not total_cum.empty else None
    title_suffix = f'  |  Total = {final:.1f} B$CAD' if final is not None else ''
    fig.update_layout(
        title=f'{case_study} — Transition cost, hors phase initiale 2015_2020 [B$CAD]{title_suffix}',
        xaxis=dict(title='Phase'),
        yaxis_title='B$CAD',
        barmode='stack',
        legend=dict(orientation='h', y=1.08),
    )
    _save(fig, outdir, '0b_Transition_cost.html')


# ===========================================================================
# PLOTS
# ===========================================================================

def _drilldown_html(case_study, title, filename, outdir,
                    df_cat, df_tech, phases, value_col, cat_col, tech_col,
                    sub_tech_data=None, barmode='stack'):
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

    _dd_font   = {'family': 'Arial, Helvetica, sans-serif', 'color': '#333333'}
    _dd_axis   = {'linecolor': '#DDDDDD', 'ticks': 'outside', 'tickcolor': '#DDDDDD',
                  'tickfont': {'size': 12, 'color': '#555555'}, 'showgrid': False}
    _dd_yaxis  = {**_dd_axis, 'showgrid': True, 'gridcolor': '#EBEBEB', 'gridwidth': 1}

    detail_note = '  <i>(click a technology for distance variants)</i>' if has_sub else ''
    cat_layout = {
        'title': {
            'text': f'<b>{title}</b><br><sup><i>Click a category in the legend to drill down</i></sup>',
            'font': {'family': 'Arial, Helvetica, sans-serif', 'size': 18, 'color': '#1A1A2E'},
            'x': 0.0, 'xanchor': 'left', 'pad': {'l': 6, 't': 4},
        },
        'font': _dd_font,
        'barmode': barmode, 'hovermode': 'x unified',
        'plot_bgcolor': '#F7F9FC', 'paper_bgcolor': 'white',
        'xaxis': {**_dd_axis, 'title': {'text': 'Phase', 'font': {'size': 13, 'color': '#666666'}}},
        'yaxis': {**_dd_yaxis, 'title': {'text': 'B$CAD', 'font': {'size': 13, 'color': '#666666'}}},
        'legend': {'orientation': 'h', 'y': -0.2, 'font': {'size': 12, 'color': '#444444'},
                   'bgcolor': 'rgba(255,255,255,0)', 'bordercolor': 'rgba(0,0,0,0)'},
        'height': 480,
        'margin': {'l': 65, 'r': 40, 't': 80, 'b': 100},
    }
    detail_layout = {
        'title': {
            'text': '<b>Technologies</b> — click a category above' + detail_note,
            'font': {'family': 'Arial, Helvetica, sans-serif', 'size': 16, 'color': '#1A1A2E'},
            'x': 0.0, 'xanchor': 'left', 'pad': {'l': 6},
        },
        'font': _dd_font,
        'barmode': barmode, 'hovermode': 'x unified',
        'plot_bgcolor': '#F7F9FC', 'paper_bgcolor': 'white',
        'xaxis': {**_dd_axis, 'title': {'text': 'Phase', 'font': {'size': 13, 'color': '#666666'}}},
        'yaxis': {**_dd_yaxis, 'title': {'text': 'B$CAD', 'font': {'size': 13, 'color': '#666666'}}},
        'legend': {'orientation': 'h', 'y': -0.25, 'font': {'size': 12, 'color': '#444444'},
                   'bgcolor': 'rgba(255,255,255,0)', 'bordercolor': 'rgba(0,0,0,0)'},
        'height': 460,
        'margin': {'l': 65, 'r': 40, 't': 60, 'b': 100},
    }
    sub_layout = {
        'title': {
            'text': '<b>Distance variants</b> — click a technology above',
            'font': {'family': 'Arial, Helvetica, sans-serif', 'size': 16, 'color': '#1A1A2E'},
            'x': 0.0, 'xanchor': 'left', 'pad': {'l': 6},
        },
        'font': _dd_font,
        'barmode': barmode, 'hovermode': 'x unified',
        'plot_bgcolor': '#F7F9FC', 'paper_bgcolor': 'white',
        'xaxis': {**_dd_axis, 'title': {'text': 'Phase', 'font': {'size': 13, 'color': '#666666'}}},
        'yaxis': {**_dd_yaxis, 'title': {'text': 'B$CAD', 'font': {'size': 13, 'color': '#666666'}}},
        'legend': {'orientation': 'h', 'y': -0.25, 'font': {'size': 12, 'color': '#444444'},
                   'bgcolor': 'rgba(255,255,255,0)', 'bordercolor': 'rgba(0,0,0,0)'},
        'height': 460,
        'margin': {'l': 65, 'r': 40, 't': 60, 'b': 100},
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
        Plotly.react('chart-sub', traces, Object.assign({{}}, subLayout, {{
            title: Object.assign({{}}, subLayout.title, {{text: '<b>Distance variants — ' + tech + '</b>'}})
        }}));
    }} else {{
        subEl.style.display = 'none';
    }}
    return false;
}});"""
    else:
        sub_js = ''

    html = f"""<!DOCTYPE html><html><head><meta charset="utf-8">
<title>{title}</title>
<script src="plotly.min.js"></script>
<style>body{{font-family:Arial,Helvetica,sans-serif;background:white;margin:12px;}}</style>
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
        Plotly.react('chart-detail', [], Object.assign({{}}, detailLayout, {{
            title: Object.assign({{}}, detailLayout.title, {{text: '<b>Technologies</b> — click a legend item above'}})
        }}));
    }} else {{
        selectedCat = cat;
        var traces = techData[cat] || [];
        Plotly.react('chart-detail', traces, Object.assign({{}}, detailLayout, {{
            title: Object.assign({{}}, detailLayout.title, {{text: '<b>' + cat + '</b> — technologies'}})
        }}));
    }}
    return false;
}});
{sub_js}
</script></body></html>"""

    global _chart_count
    os.makedirs(outdir, exist_ok=True)
    _ensure_plotlyjs(outdir)
    path = os.path.join(outdir, filename)
    with open(path, 'w', encoding='utf-8') as f:
        f.write(html)
    _chart_count += 1
    sys.stdout.write(f'\r  Plotting [{_chart_count}]: {filename:<55}')
    sys.stdout.flush()


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

    # Add salvage value as negative bars per installation phase (distinct category so they don't net out)
    salvage_df = _compute_salvage_per_phase(results)
    if salvage_df is not None:
        sv = salvage_df.reset_index()
        sv['C_inv'] = sv['salvage'] / 1000
        sv['Category'] = 'Salvage value'
        sv = sv[sv['C_inv'].abs() > 1e-9][['Phases', 'Technologies', 'Category', 'C_inv']]
        df = pd.concat([df, sv], ignore_index=True)

    df_cat = df.groupby(['Phases', 'Category'])['C_inv'].sum().reset_index()
    _drilldown_html(
        case_study,
        title='CAPEX breakdown — lump-sum par phase d\'installation (salvage en négatif) [B$CAD]',
        filename='1b_CAPEX_breakdown.html',
        outdir=outdir,
        df_cat=df_cat, df_tech=df,
        phases=phases, value_col='C_inv', cat_col='Category', tech_col='Technologies',
        sub_tech_data=sub_tech_data if sub_tech_data else None,
        barmode='relative',
    )


def plot_capex_crf_breakdown(results, outdir, case_study):
    """CAPEX breakdown using CRF-per-installation cost (correct for i_rate sensitivity).
    Cost attributed to the installation phase, not spread over active phases.
    Excludes 2015_2020 cleanly. Requires tau in results (needs a new model run)."""
    crf_capex = _compute_crf_install_capex(results)
    if crf_capex is None:
        print('[SKIP] plot_capex_crf_breakdown: tau not in results (re-run the model)'); return

    df = crf_capex.reset_index()
    df.columns = ['Phases', 'Technologies', 'C_inv']
    df['C_inv'] = pd.to_numeric(df['C_inv'], errors='coerce').fillna(0) / 1000
    df['Phases'] = df['Phases'].astype(str)
    df = df[df['Phases'] != INIT_PHASE]
    df['Category'] = df['Technologies'].apply(_fnew_category)
    phases = [p for p in TRANS_PHASES if p in df['Phases'].unique()]
    df_cat = df.groupby(['Phases', 'Category'])['C_inv'].sum().reset_index()
    _drilldown_html(
        case_study,
        title='CAPEX — CRF par phase d\'INSTALLATION (Python, hors 2015_2020) [B$CAD]',
        filename='1b_CAPEX_CRF_par_installation.html',
        outdir=outdir,
        df_cat=df_cat, df_tech=df,
        phases=phases, value_col='C_inv', cat_col='Category', tech_col='Technologies',
    )


def plot_capex_crf_active_phase(results, outdir, case_study):
    """CAPEX distributed across active phases via CRF annuities.
    Mirrors C_inv_phase_CRF from AMPL but per technology and without 2015_2020 contamination."""
    crf_active = _compute_crf_active_capex(results)
    if crf_active is None:
        print('[SKIP] plot_capex_crf_active_phase: tau not in results (re-run the model)'); return

    df = crf_active.reset_index()
    df.columns = ['Phases', 'Technologies', 'C_inv']
    df['C_inv'] = pd.to_numeric(df['C_inv'], errors='coerce').fillna(0) / 1000
    df['Phases'] = df['Phases'].astype(str)
    df['Category'] = df['Technologies'].apply(_fnew_category)
    phases = [p for p in TRANS_PHASES if p in df['Phases'].unique()]
    df_cat = df.groupby(['Phases', 'Category'])['C_inv'].sum().reset_index()
    _drilldown_html(
        case_study,
        title='CAPEX — CRF par phase ACTIVE (Python, hors 2015_2020) [B$CAD]',
        filename='1b_CAPEX_CRF_par_phase_active.html',
        outdir=outdir,
        df_cat=df_cat, df_tech=df,
        phases=phases, value_col='C_inv', cat_col='Category', tech_col='Technologies',
    )


def plot_capex_no_actu_breakdown(results, outdir, case_study):
    """CAPEX breakdown by technology, without the actualisation factor (attributed to installation phase)."""
    key = 'C_inv_phase_tech_no_actu'
    if results.get(key) is None:
        print(f'[SKIP] {key} not in results'); return

    df = results[key].copy().reset_index()
    df.columns = ['Phases', 'Technologies', 'C_inv']
    df['C_inv'] = pd.to_numeric(df['C_inv'], errors='coerce').fillna(0) / 1000
    df['Phases'] = df['Phases'].astype(str)
    df = df[df['Phases'] != INIT_PHASE]
    df['Category'] = df['Technologies'].apply(_fnew_category)
    phases = [p for p in TRANS_PHASES if p in df['Phases'].unique()]
    df_cat = df.groupby(['Phases', 'Category'])['C_inv'].sum().reset_index()
    _drilldown_html(
        case_study,
        title='CAPEX breakdown — non-actualisé par phase d\'installation [B$CAD]',
        filename='1b_CAPEX_no_actu_breakdown.html',
        outdir=outdir,
        df_cat=df_cat, df_tech=df,
        phases=phases, value_col='C_inv', cat_col='Category', tech_col='Technologies',
    )


def plot_capex_summary(results, outdir, case_study):
    """3-panel summary: lump-sum breakdown | CRF par installation | CRF par phase active."""

    def _to_cat_series(df_raw, phases_list):
        """From (Phases, Technologies, C_inv) df → dict {cat: Series indexed by phase}."""
        df_raw['Category'] = df_raw['Technologies'].apply(_fnew_category)
        grouped = df_raw.groupby(['Phases', 'Category'])['C_inv'].sum()
        cats = df_raw.groupby('Category')['C_inv'].sum().sort_values(ascending=False).index.tolist()
        out = {}
        for cat in cats:
            s = grouped.xs(cat, level='Category') if cat in grouped.index.get_level_values('Category') else pd.Series(dtype=float)
            out[cat] = s.reindex(phases_list).fillna(0)
        return out

    phases_trans = [p for p in TRANS_PHASES]

    # --- Panel 1: lump-sum + salvage ---
    cinv_raw = results.get('C_inv_phase_tech')
    p1_data = None
    if cinv_raw is not None:
        df1 = cinv_raw.copy().reset_index()
        df1.columns = ['Phases', 'Technologies', 'C_inv']
        df1['C_inv'] = pd.to_numeric(df1['C_inv'], errors='coerce').fillna(0) / 1000
        df1 = df1[df1['Phases'] != INIT_PHASE]
        salvage_df = _compute_salvage_per_phase(results)
        if salvage_df is not None:
            sv = salvage_df.reset_index()
            sv['C_inv'] = sv['salvage'] / 1000
            sv['Category'] = 'Salvage value'
            sv = sv[sv['C_inv'].abs() > 1e-9][['Phases', 'Technologies', 'Category', 'C_inv']]
            df1 = pd.concat([df1, sv], ignore_index=True)
        p1_data = _to_cat_series(df1, phases_trans)

    # --- Panel 2: CRF par phase d'installation ---
    crf_install = _compute_crf_install_capex(results)
    p2_data = None
    if crf_install is not None:
        df2 = crf_install.reset_index()
        df2.columns = ['Phases', 'Technologies', 'C_inv']
        df2['C_inv'] = pd.to_numeric(df2['C_inv'], errors='coerce').fillna(0) / 1000
        df2 = df2[df2['Phases'] != INIT_PHASE]
        p2_data = _to_cat_series(df2, phases_trans)

    # --- Panel 3: CRF par phase active ---
    crf_active = _compute_crf_active_capex(results)
    p3_data = None
    if crf_active is not None:
        df3 = crf_active.reset_index()
        df3.columns = ['Phases', 'Technologies', 'C_inv']
        df3['C_inv'] = pd.to_numeric(df3['C_inv'], errors='coerce').fillna(0) / 1000
        p3_data = _to_cat_series(df3, phases_trans)

    if p1_data is None and p2_data is None and p3_data is None:
        print('[SKIP] plot_capex_summary: no data'); return

    def _total(data):
        if data is None:
            return None
        return sum(v for series in data.values() for v in series.tolist())

    totals = [_total(p1_data), _total(p2_data), _total(p3_data)]

    def _subtitle(label, total):
        t = f'{total:.1f} B$CAD' if total is not None else ''
        return f'{label}<br><sup>Total : <b>{t}</b></sup>'

    subtitles = [
        _subtitle('Lump-sum + salvage (par installation)', totals[0]),
        _subtitle('CRF — par phase d\'installation',       totals[1]),
        _subtitle('CRF — par phase active',                totals[2]),
    ]
    fig = make_subplots(
        rows=1, cols=3,
        subplot_titles=subtitles,
        shared_yaxes=True,
        horizontal_spacing=0.04,
    )

    all_cats = []
    for data in [p1_data, p2_data, p3_data]:
        if data:
            for c in data:
                if c not in all_cats:
                    all_cats.append(c)

    shown_legend = set()
    for col, data in enumerate([p1_data, p2_data, p3_data], start=1):
        if data is None:
            continue
        barmode_col = 'relative' if col == 1 else 'stack'
        for cat in all_cats:
            if cat not in data:
                continue
            vals = data[cat]
            show = cat not in shown_legend
            fig.add_trace(go.Bar(
                x=phases_trans,
                y=vals.tolist(),
                name=cat,
                marker_color=CATEGORY_COLORS.get(cat, '#D3D3D3'),
                legendgroup=cat,
                showlegend=show,
            ), row=1, col=col)
            shown_legend.add(cat)

    fig.update_layout(
        title=dict(
            text=f'<b>{case_study} — CAPEX : comparaison des formulations [B$CAD]</b>',
            font=dict(size=16), x=0.0, xanchor='left',
        ),
        barmode='relative',
        hovermode='x unified',
        height=520,
        legend=dict(orientation='h', y=-0.18, font=dict(size=11)),
        plot_bgcolor='#F7F9FC', paper_bgcolor='white',
        margin=dict(l=65, r=30, t=80, b=120),
    )
    for col in range(1, 4):
        fig.update_xaxes(title_text='Phase', tickangle=30, row=1, col=col)
    fig.update_yaxes(title_text='B$CAD', row=1, col=1)

    _save(fig, outdir, '1b_CAPEX_summary.html')


def plot_capex_crf_ampl(results, outdir, case_study):
    """Plot C_inv_phase_CRF directly from AMPL — total per active phase, includes 2015_2020 contamination."""
    key = 'C_inv_phase_CRF'
    cinv_lump = results.get('C_inv_phase')
    cinv_crf  = results.get(key)
    if cinv_crf is None:
        print(f'[SKIP] {key} not in results (re-run the model)'); return

    phases = ['2015_2020'] + [p for p in TRANS_PHASES]

    def _to_series(df, col):
        s = df.copy().reset_index()
        s.columns = ['Phases', col]
        s['Phases'] = s['Phases'].astype(str)
        s[col] = pd.to_numeric(s[col], errors='coerce').fillna(0) / 1000
        return s.set_index('Phases')[col]

    crf_s  = _to_series(cinv_crf,  'CRF')
    lump_s = _to_series(cinv_lump, 'Lump') if cinv_lump is not None else None

    # Salvage value for lump-sum total
    salvage = 0.0
    cost_return = results.get('Cost_return')
    if cost_return is not None and 'C_inv_return' in cost_return.columns:
        salvage = pd.to_numeric(cost_return['C_inv_return'], errors='coerce').fillna(0).sum() / 1000

    total_crf  = sum(crf_s.get(p, 0) for p in phases)
    total_lump = (sum(lump_s.get(p, 0) for p in phases) - salvage) if lump_s is not None else None

    x_all = phases + ['TOTAL']

    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=x_all,
        y=[crf_s.get(p, 0) for p in phases] + [total_crf],
        name='C_inv_phase_CRF (AMPL)',
        marker_color='steelblue',
    ))
    if lump_s is not None:
        fig.add_trace(go.Bar(
            x=x_all,
            y=[lump_s.get(p, 0) for p in phases] + [total_lump],
            name='C_inv_phase lump-sum − salvage (AMPL)',
            marker_color='tomato',
            opacity=0.6,
        ))
    fig.update_layout(
        title=f'{case_study} — C_inv_phase_CRF AMPL total (incl. 2015_2020) vs lump-sum [B$CAD]',
        barmode='group',
        xaxis_title='Phase',
        yaxis_title='B$CAD',
        legend=dict(orientation='h', y=1.08),
        shapes=[dict(
            type='line', xref='paper', x0=1 - 1/len(x_all)/2, x1=1 - 1/len(x_all)/2,
            yref='paper', y0=0, y1=1,
            line=dict(color='grey', dash='dot', width=1),
        )],
    )
    _save(fig, outdir, '1b_CAPEX_CRF_AMPL.html')


def plot_capex_no_actu(results, outdir, case_study):
    """Plot C_inv_phase_no_actu directly from AMPL — total per phase, without the actualisation factor."""
    key = 'C_inv_phase_no_actu'
    cinv_no_actu = results.get(key)
    if cinv_no_actu is None:
        print(f'[SKIP] {key} not in results (re-run the model)'); return

    phases = ['2015_2020'] + [p for p in TRANS_PHASES]

    s = cinv_no_actu.copy().reset_index()
    s.columns = ['Phases', 'NoActu']
    s['Phases'] = s['Phases'].astype(str)
    s['NoActu'] = pd.to_numeric(s['NoActu'], errors='coerce').fillna(0) / 1000
    no_actu_s = s.set_index('Phases')['NoActu']

    total_no_actu = sum(no_actu_s.get(p, 0) for p in phases)
    x_all = phases + ['TOTAL']

    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=x_all,
        y=[no_actu_s.get(p, 0) for p in phases] + [total_no_actu],
        name='C_inv_phase_no_actu (AMPL)',
        marker_color='seagreen',
    ))
    fig.update_layout(
        title=f'{case_study} — C_inv_phase_no_actu AMPL total, non-actualised [B$CAD]',
        xaxis_title='Phase',
        yaxis_title='B$CAD',
        legend=dict(orientation='h', y=1.08),
        shapes=[dict(
            type='line', xref='paper', x0=1 - 1/len(x_all)/2, x1=1 - 1/len(x_all)/2,
            yref='paper', y0=0, y1=1,
            line=dict(color='grey', dash='dot', width=1),
        )],
    )
    _save(fig, outdir, '1b_CAPEX_no_actu.html')


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
        title='OPEX breakdown [B$CAD/phase]',
        filename='1c_OPEX_breakdown.html',
        outdir=outdir,
        df_cat=df_cat, df_tech=df,
        phases=phases, value_col='C_op', cat_col='Category', tech_col='Label',
    )


def plot_opex_no_actu_breakdown(results, outdir, case_study):
    """OPEX breakdown by technology/resource, without the actualisation factor."""
    frames = []
    op_tech = results.get('C_op_phase_tech_no_actu')
    op_res  = results.get('C_op_phase_res_no_actu')
    if op_tech is None and op_res is None:
        print('[SKIP] C_op_phase_tech_no_actu and C_op_phase_res_no_actu not in results'); return

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
        title='OPEX breakdown — non-actualisé [B$CAD/phase]',
        filename='1c_OPEX_no_actu_breakdown.html',
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
        title='Total cost (CAPEX+OPEX) [B$CAD/phase]',
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
            sub = sub[sub['Technologies'].str.contains(_DIST_RE)].copy()
            if not SHOW_DISTANCE_VARIANTS:
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
                sub = sub[sub['Technologies'].str.contains(_DIST_RE)].copy()
                if not SHOW_DISTANCE_VARIANTS:
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
_GRID_KEYWORDS = ['_GRID','TRAFO_','NG_EXP','SNG_EXP','H2_EXP',
                   'NG_COMP','SNG_COMP','H2_COMP']

def _tech_group(tech):
    t = tech.upper()
    if any(k in t for k in _GRID_KEYWORDS): return 'grid'
    if any(k in t for k in _STO_KEYWORDS):  return 'storage'
    if any(k in t for k in _MOB_KEYWORDS):  return 'mobility'
    return 'standard'

_GROUP_META = {
    'standard': {'label': ' [Standard]', 'cap_unit': 'GW',       'suffix': '_standard'},
    'grid':     {'label': ' [Grid]',     'cap_unit': 'GW',       'suffix': '_grid'},
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

        fc = fc[fc['F_Mult'] > 0.001]
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
        for group in ['standard', 'grid', 'storage', 'mobility']:
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
    SHOW_DISTANCE_VARIANTS=False → drop base techs, strip suffixes from variants, then aggregate
    """
    mob = df['Category'].str.startswith('MOB_')
    has_suffix = df['Technologies'].str.contains(_DIST_RE)
    # Always drop base mob techs (no distance suffix): their F_Mult equals the sum of their
    # variants, so keeping them alongside the variants would double-count.
    df = df[~mob | has_suffix].copy()
    if SHOW_DISTANCE_VARIANTS:
        return df
    mob2 = df['Category'].str.startswith('MOB_')
    df.loc[mob2, 'Technologies'] = df.loc[mob2, 'Technologies'].apply(_strip_dist)
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
            uniformtext_minsize=10, uniformtext_mode='hide',
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
            sub = sub[sub['Technologies'].str.contains(_DIST_RE)].copy()
            if not SHOW_DISTANCE_VARIANTS:
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
# INSTALLED CAPACITY (F_MULT) BY CATEGORY OVER YEARS
# ---------------------------------------------------------------------------

def plot_f_mult_by_category(results, outdir, case_study):
    fm = results.get('F_Mult')
    if fm is None:
        print('[SKIP] F_Mult not in results'); return

    df = fm.copy().reset_index()
    df.columns = ['Years', 'Technologies', 'F_Mult']
    df['F_Mult'] = pd.to_numeric(df['F_Mult'], errors='coerce').fillna(0)
    df['Years'] = df['Years'].astype(str).str.replace('YEAR_', '', regex=False)
    df['Category'] = df['Technologies'].apply(_fnew_category)
    df = df[~df['Technologies'].str.upper().isin(['CO2_STO', 'STO_CO2'])]

    year_order = [y for y in YEARS_ORDER if y in df['Years'].unique()]

    for cat in sorted(df['Category'].unique()):
        sub = df[df['Category'] == cat].copy()
        if cat.startswith('MOB_'):
            # Always drop base mob techs (no distance suffix) to avoid double-counting
            # with their distance variants, which carry the same F_Mult via the
            # freightmob/privatemob/publicmob_installed_pertech1 equality constraint.
            sub = sub[sub['Technologies'].str.contains(_DIST_RE)].copy()
            if not SHOW_DISTANCE_VARIANTS:
                sub['Technologies'] = sub['Technologies'].apply(_strip_dist)
                sub = sub.groupby(['Years', 'Technologies', 'Category'], as_index=False)['F_Mult'].sum()
        active = sub.groupby('Technologies')['F_Mult'].max()
        active_techs = active[active > 0.01].index.tolist()
        sub = sub[sub['Technologies'].isin(active_techs)]
        if sub.empty:
            continue

        fig = go.Figure()
        for tech in sorted(active_techs):
            vals = (sub[sub['Technologies'] == tech]
                    .set_index('Years')
                    .reindex(year_order)['F_Mult']
                    .fillna(0).tolist())
            fig.add_bar(
                x=year_order, y=vals, name=tech,
                marker_color=_tech_color(tech),
                text=[tech if v > 0.01 else '' for v in vals],
                textposition='inside',
                insidetextanchor='middle',
                textfont=dict(size=10, color='white'),
            )
        if cat == 'MOB_FREIGHT':    unit = 'Mtkm/h'
        elif cat.startswith('MOB'): unit = 'Mpkm/h'
        else:                        unit = 'GW'
        fig.update_layout(
            title=f'{case_study} — F_Mult [{cat}] [{unit}]',
            xaxis_title='Year', yaxis_title=unit,
            barmode='stack',
            showlegend=True,
            legend=dict(x=1.01, y=1, xanchor='left'),
            uniformtext=dict(minsize=8, mode='hide'),
        )
        _save(fig, outdir, f'4c_F_Mult_{cat}.html')


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
            sub = sub[sub['Technologies'].str.contains(_DIST_RE)].copy()
            if not SHOW_DISTANCE_VARIANTS:
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
                   'AN_DIG', 'WASTE']),
    # --- fossil gas & oil --- (CNG/PROPANE are fossil, not biofuels; CSNG is
    # caught above by the 'SNG_' keyword in H2 / Synfuel, before this rule runs)
    ('Gas / Oil', ['_BOILER_GAS', 'BOILER_OIL', '_COGEN_GAS', 'COGEN_OIL',
                   'CCGT', 'OCGT', 'COAL', 'GASOLINE', 'DIESEL',
                   'PLANE_', 'BULK_CARRIER', 'CONTAINER', 'OIL_TANKER',
                   'HY_DIESEL', '_HEV', 'CAR_HEV', 'SUV_HEV',
                   'BOILER_GAS', 'COGEN_GAS', '_NG_', 'NG_CCGT',
                   'NG_REFORM', 'NG_PYROLY', 'LP_NG', 'MP_NG', 'HP_NG',
                   '_GAS', '_CNG', 'CNG_', 'PROPANE',
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

_EUD_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                        '..', '..', '..', 'shared', 'data', 'EUD')

_EUD_LAYER_PREFIXES = {
    # EUD demand-category prefix → Sankey carrier name
    'ELECTRICITY':        'ELECTRICITY',
    'HEAT_LOW_T':         'HEAT_LOW_T',
    'HEAT_HIGH_T':        'HEAT_HIGH_T',
    'MOBILITY_PASSENGER': 'MOBILITY_PASSENGER',
    'MOBILITY_FREIGHT':   'MOBILITY_FREIGHT',
}
_EUD_SKIP_SECTORS = {'EXPORT'}

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
        return '_EUD_SPLIT_MOBILITY_PASSENGER'
    if l.startswith('MOB_FREIGHT'):
        return '_EUD_SPLIT_MOBILITY_FREIGHT'
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
    ('DEC_WOOD_BOILER', ['DEC_BOILER_WOOD']),
    ('DEC_GAS_BOILER',  ['DEC_BOILER_GAS']),
    ('DEC_OIL_BOILER',  ['DEC_BOILER_OIL']),
    ('DEC_BOILER',      ['DEC_BOILER']),
    ('WOOD_BOILER',     ['_BOILER_WOOD', '_BOILER_WET']),
    ('GAS_BOILER',      ['_BOILER_GAS', '_BOILER_NG', '_BOILER_SNG']),
    ('OIL_BOILER',      ['_BOILER_OIL']),
    ('BOILER',          ['_BOILER_', 'BOILER_', 'IND_BOILER', 'DHN_BOILER']),
    ('COGEN',     ['_COGEN_', 'COGEN_', 'IND_COGEN', 'DHN_COGEN', 'DEC_COGEN',
                   'IND_ADVCOGEN', 'DEC_ADVCOGEN']),
    ('BIO_GASIF', ['BIOMASS_GAS_', 'BIOMASS_TO_']),
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
    'Electricity':          '#4C78A8',   # blue
    'Heat — Low T':         '#F58518',   # orange
    'Heat — High T':        '#72B7B2',   # teal
    'Mobility — Passenger': '#E45756',   # red
    'Mobility — Freight':   '#B279A2',   # purple
    'Processes':            '#EECA3B',   # yellow  (industrial processes + fuel conversion)
    'Carbon capture':       '#17BECF',   # cyan
    'Biogenic carbon':      '#90EE90',   # light green
    'Other':                '#AAAAAA',   # grey
}

_GWP_RES_COLORS = {
    'NG': '#FFD700', 'DIESEL': '#D3D3D3', 'GASOLINE': '#808080',
    'COAL': '#A0522D', 'LFO': '#8B008B', 'WOOD': '#CD853F',
}

# Rules: first match wins. Each entry is (category, [keywords]).
_GWP_TECH_CAT_RULES = [
    ('Carbon capture',       ['DAC_', 'CO2_STO', 'STO_CO2', 'DEEP_SALINE',
                              'UNMINEABLE', 'EOR', 'DOGR', 'CEMENT_PROD', 'CARBON_']),
    ('Biogenic carbon',      ['BIOMASS_', 'WET_BIOMASS', 'WASTE_BIO',
                              'BIOGAS_', 'AN_DIG', 'PYROLYSIS']),
    ('Electricity',          ['CCGT', 'OCGT', 'COAL_POWER', 'GEOTHERMAL_ELEC']),
    ('Heat — Low T',         ['DHN_', 'DEC_', 'LT_DEC', 'LT_DHN']),
    ('Heat — High T',        ['IND_']),
    ('Mobility — Passenger', ['CAR_', 'SUV_', 'BUS_', 'TRAMWAY', 'SCHOOLBUS_',
                              'COMMUTER_RAIL', 'COACH_', 'METRO',
                              'TRAIN_DIESEL', 'TRAIN_ELEC', 'TRAIN_H2',
                              'TRAIN_NG', 'TRAIN_SNG', 'TRAIN_BIODIESEL',
                              'PLANE_SH', 'PLANE_LH']),
    ('Mobility — Freight',   ['TRUCK_', 'SEMI_', 'LCV_', 'TRAIN_FREIGHT',
                              'BULK_CARRIER', 'CONTAINER', 'OIL_TANKER',
                              'PLANE_FREIGHT']),
]

def _classify_gwp_tech(tech):
    t = tech.upper()
    for cat, keywords in _GWP_TECH_CAT_RULES:
        if any(k.upper() in t for k in keywords):
            return cat
    return 'Processes'


def _allocate_gwp_simple(results):
    """Allocate CO₂ from Year_balance to tech-type categories (no EUD fraction split)."""
    yb = results.get('Year_balance')
    if yb is None:
        return pd.DataFrame(columns=['Year', 'Tech', 'Sector', 'GWP_kt'])
    co2_cols = [c for c in ('CO2_A', 'CO2_E') if c in yb.columns]
    if not co2_cols:
        return pd.DataFrame(columns=['Year', 'Tech', 'Sector', 'GWP_kt'])

    rows = []
    for (year_str, tech), row in yb.iterrows():
        if tech == 'ELECTRICITY_EHV' or tech in _CO2_LAYER_ELEMENTS:
            continue
        gwp = float(np.nansum([pd.to_numeric(row.get(c, 0), errors='coerce')
                                for c in co2_cols]))
        if abs(gwp) < 0.01:
            continue
        year = int(str(year_str).replace('YEAR_', ''))
        rows.append({'Year': year, 'Tech': tech,
                     'Sector': _classify_gwp_tech(tech), 'GWP_kt': gwp})

    if not rows:
        return pd.DataFrame(columns=['Year', 'Tech', 'Sector', 'GWP_kt'])
    return pd.DataFrame(rows)


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
    if any(k in t for k in ('BIOMASS_GAS_', 'BIOMASS_TO_', 'BIOMETHANE_', 'BIOMETHANOL_')):
        return 'INDUSTRY'
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

    # Technologies whose primary output is not an EUD layer (H2, SNG, synfuels…).
    # Their EUD-layer production is only a by-product; use the name-based fallback
    # instead of mis-allocating CO₂ to Services/Households via that by-product.
    # ELECTRICITY_EHV is an import resource whose CO₂ is out-of-territory — handled separately.
    _NON_EUD_PRIMARY = ('_H2', 'BIOMASS_GAS_', 'BIOGAS_', 'BIOMASS_GAS', 'SMR', 'ATR',
                        'NG_PYROLYSIS', 'METHANATION', 'FT_', 'CO2_TO_', 'PYROLYSIS',
                        'GASIFICATION', 'AN_DIG', 'BIOMETHANE_', 'BIOMETHANOL_')
    _ELEC_IMPORTS = frozenset({'ELECTRICITY_EHV'})

    rows = []
    for (year_str, tech), row in yb.iterrows():
        if tech in _CO2_LAYER_ELEMENTS:
            continue
        gwp = float(np.nansum([pd.to_numeric(row.get(c, 0), errors='coerce')
                                for c in co2_cols]))
        if abs(gwp) < 0.01:
            continue

        year = int(str(year_str).replace('YEAR_', ''))
        year_fracs = eud_fracs.get(year, {})

        # Electricity imports: CO₂ is out-of-territory — excluded from breakdown
        if tech in _ELEC_IMPORTS:
            continue

        # Skip EUD allocation for techs whose primary output is H2/SNG/synfuel
        if any(k in tech.upper() for k in _NON_EUD_PRIMARY):
            rows.append({'Year': year, 'Tech': tech,
                         'Sector': _gwp_sector_fallback(tech), 'GWP_kt': gwp})
            continue

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

    alloc_df = _allocate_gwp_simple(results)
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
        # Exclude ELECTRICITY_EHV (out-of-territory) from the reference total
        yb_yr_terr = yb_yr.drop(index='ELECTRICITY_EHV', errors='ignore')
        yb_tot = sum(float(pd.to_numeric(yb_yr_terr[c], errors='coerce').fillna(0).sum())
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

    # ---- Cumulative line (y2) — trapezoid rule to match TotalGWPTransition ----
    total_by_year = l1.groupby('Year')['GWP_kt'].sum().reindex(years).fillna(0)
    years_sorted  = sorted(years)
    vals          = total_by_year.reindex(years_sorted).fillna(0)  # kt/year
    t_phase       = 5
    running       = 0.0
    cumul_list    = []
    for i, y in enumerate(years_sorted):
        cumul_list.append(running / 1000)          # Mt at start of each interval
        if i < len(years_sorted) - 1:
            running += t_phase / 2 * (vals[y] + vals[years_sorted[i + 1]])
    cumulative = pd.Series(cumul_list, index=years_sorted)
    total_gt   = running / 1e6                     # kt → Gt

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

    _gwp_font = {'family': 'Arial, Helvetica, sans-serif', 'color': '#333333'}
    _gwp_axis = {
        'showgrid': False, 'linecolor': '#DDDDDD',
        'ticks': 'outside', 'tickcolor': '#DDDDDD',
        'tickfont': {'size': 12, 'color': '#555555'},
    }
    _gwp_yaxis = {**_gwp_axis, 'showgrid': True, 'gridcolor': '#EBEBEB', 'gridwidth': 1}

    l1_layout = {
        'title': {
            'text': ('<b>GHG emissions by source type [Mt CO₂-eq./y]</b>'
                     f'<br><sup><i>Click a category in the legend to drill down</i></sup>'),
            'font': {'family': 'Arial, Helvetica, sans-serif', 'size': 18, 'color': '#1A1A2E'},
            'x': 0.0, 'xanchor': 'left', 'pad': {'l': 6, 't': 4},
        },
        'font': _gwp_font,
        'barmode': 'relative', 'hovermode': 'x unified',
        'plot_bgcolor': '#F7F9FC', 'paper_bgcolor': 'white',
        'xaxis': {**_gwp_axis,
                  'title': {'text': 'Year', 'font': {'size': 13, 'color': '#666666'}},
                  'type': 'linear', 'dtick': 5},
        'yaxis': {**_gwp_yaxis,
                  'title': {'text': 'Mt CO₂-eq./y', 'font': {'size': 13, 'color': '#666666'}},
                  'range': [y1_min, y1_max]},
        'yaxis2': {
            'title': {'text': 'Cumulative [Mt CO₂-eq.]',
                      'font': {'size': 13, 'color': 'darkred'}},
            'range': [y2_min, y2_max],
            'overlaying': 'y', 'side': 'right',
            'showgrid': False, 'linecolor': '#DDDDDD',
            'tickfont': {'color': 'darkred', 'size': 12},
        },
        'legend': {
            'orientation': 'h', 'y': -0.2,
            'font': {'size': 12, 'color': '#444444'},
            'bgcolor': 'rgba(255,255,255,0)', 'bordercolor': 'rgba(0,0,0,0)',
        },
        'height': 560,
        'margin': {'l': 65, 'r': 80, 't': 80, 'b': 100},
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
        'title': {
            'text': '<b>Technologies</b> — click a category above',
            'font': {'family': 'Arial, Helvetica, sans-serif', 'size': 16, 'color': '#1A1A2E'},
            'x': 0.0, 'xanchor': 'left', 'pad': {'l': 6},
        },
        'font': _gwp_font,
        'barmode': 'relative', 'hovermode': 'x unified',
        'plot_bgcolor': '#F7F9FC', 'paper_bgcolor': 'white',
        'xaxis': {**_gwp_axis,
                  'title': {'text': 'Year', 'font': {'size': 13, 'color': '#666666'}},
                  'type': 'linear', 'dtick': 5},
        'yaxis': {**_gwp_yaxis,
                  'title': {'text': 'Mt CO₂-eq./y', 'font': {'size': 13, 'color': '#666666'}}},
        'legend': {
            'orientation': 'h', 'y': -0.25,
            'font': {'size': 12, 'color': '#444444'},
            'bgcolor': 'rgba(255,255,255,0)', 'bordercolor': 'rgba(0,0,0,0)',
        },
        'showlegend': True,
        'height': 460,
        'margin': {'l': 65, 'r': 40, 't': 60, 'b': 100},
    }

    html = f"""<!DOCTYPE html><html><head><meta charset="utf-8">
<title>{case_study} — GHG emissions by source type</title>
<script src="plotly.min.js"></script>
<style>body{{font-family:Arial,Helvetica,sans-serif;background:white;margin:12px;}}</style>
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

    global _chart_count
    os.makedirs(outdir, exist_ok=True)
    _ensure_plotlyjs(outdir)
    path = os.path.join(outdir, '14_GWP_breakdown.html')
    with open(path, 'w', encoding='utf-8') as f:
        f.write(html)
    _chart_count += 1
    sys.stdout.write(f'\r  Plotting [{_chart_count}]: 14_GWP_breakdown.html{" " * 35}')
    sys.stdout.flush()




# ===========================================================================

# ===========================================================================
# DASHBOARD — thematic nav + dimension chips over the generated chart files
# ===========================================================================

# Chart-family registry: filename-stem regex → (section, family label, dim names).
# Named groups: 'year' and/or 'd1'; their values become the chip dimensions.
_DASH_SPECS = [
    (r'0_GWP',                                      'Overview',          'GHG emissions',                ()),
    (r'0b_Transition_cost',                         'Overview',          'Transition cost',              ()),
    (r'1d_Total_cost_breakdown',                    'Overview',          'Total cost breakdown',         ()),
    (r'00a_Init_capacity_(?P<d1>.+)',               'Initial 2020',      'Installed capacity',           ('Type',)),
    (r'00b_Init_annual_prod_(?P<d1>.+)',            'Initial 2020',      'Annual production',            ('Type',)),
    (r'00c_Init_capex',                             'Initial 2020',      'CAPEX',                        ()),
    (r'00d_Init_resources',                         'Initial 2020',      'Resources',                    ()),
    (r'1b_CAPEX_(?P<d1>.+)',                        'Costs',             'CAPEX',                        ('View',)),
    (r'1c_OPEX_(?P<d1>.+)',                         'Costs',             'OPEX',                         ('View',)),
    (r'4c_F_Mult_(?P<d1>.+)',                       'Capacity',          'Installed (F_Mult)',           ('Category',)),
    (r'2_F_new_(?P<d1>.+)',                         'Capacity',          'New installations (F_new)',    ('Category',)),
    (r'3_F_old_(?P<d1>.+)',                         'Capacity',          'End of life (F_old)',          ('Category',)),
    (r'3b_F_decom_(?P<d1>.+)',                      'Capacity',          'Decommissioning (F_decom)',    ('Category',)),
    (r'9_NumberOfUnits_(?P<d1>.+)',                 'Capacity',          'Number of units',              ('Category',)),
    (r'4_Resources',                                'Production',        'Resources',                    ()),
    (r'5_Annual_prod_(?P<d1>.+)',                   'Production',        'Annual production',            ('Category',)),
    (r'6_Monthly_prod_(?P<year>20\d\d)_(?P<d1>.+)', 'Production',        'Monthly production',           ('Year', 'Category')),
    (r'6b_Monthly_resources_(?P<year>20\d\d)',      'Production',        'Monthly resources',            ('Year',)),
    (r'7_Load_factor_(?P<year>20\d\d)_(?P<d1>.+)',  'Production',        'Load factors',                 ('Year', 'Type')),
    (r'10_Elec_layer_(?P<d1>.+)',                   'Energy balances',   'Electricity layers',           ('Layer',)),
    (r'18_Elec_monthly_(?P<year>20\d\d)',           'Energy balances',   'Electricity monthly',          ('Year',)),
    (r'11_Heat_layer_(?P<d1>.+)',                   'Energy balances',   'Heat layers',                  ('Layer',)),
    (r'12b_H2_layer_(?P<d1>.+)',                    'Energy balances',   'H2 layers',                    ('Layer',)),
    (r'99_H2_monthly_(?P<year>20\d\d)',             'Energy balances',   'H2 monthly',                   ('Year',)),
    (r'12c_NG_layer_(?P<d1>.+)',                    'Energy balances',   'NG layers',                    ('Layer',)),
    (r'13_Mob_Passenger_(?P<d1>.+)',                'Mobility',          'Passenger demand',             ('Distance',)),
    (r'13_Mob_Freight_(?P<d1>.+)',                  'Mobility',          'Freight demand',               ('Distance',)),
    (r'8_Mobility_(?P<d1>.+)',                      'Mobility',          'Modal mix',                    ('Segment',)),
    (r'14_GWP_breakdown',                           'Emissions & flows', 'GHG by sector',                ()),
    (r'16_Sankey_(?P<year>20\d\d)',                 'Emissions & flows', 'Energy Sankey',                ('Year',)),
    (r'17_CO2_Sankey_(?P<year>20\d\d)',             'Emissions & flows', 'CO2 Sankey',                   ('Year',)),
    #ADDED BY PAOLO (to validate) -- critical_materials' Plot_functions.build_materials_dashboard
    # writes into this same graphs/ folder (when materials=True) so its pages share this one sidebar.
    (r'20_Material_demand_total',                   'Materials',         'Total demand',                 ()),
    (r'20_Material_demand_by_sector',               'Materials',         'Demand by sector',             ()),
    (r'20_Material_decommissioned_total',           'Materials',         'Total decommissioned',         ()),
    (r'20_Material_decommissioned_by_sector',       'Materials',         'Decommissioned by sector',     ()),
    (r'21_Material_demand_(?P<d1>.+)',              'Materials',         'Demand by material',           ('Material',)),
    (r'22_Material_recycled_total',                 'Materials',         'Total recycled',               ()),
    (r'22_Material_recycled_by_sector',             'Materials',         'Recycled by sector',           ()),
    (r'22_Material_recycled_by_tech_process',       'Materials',         'Recycled by sub-tech/process', ()),
    (r'23_Material_recycled_(?P<d1>.+)',            'Materials',         'Recycled by material',         ('Material',)),
    (r'23b_Material_recycled_net_(?P<d1>.+)',       'Materials',         'Recycled vs disposed (net)',   ('Material',)),
    (r'24_Material_new_(?P<d1>.+)',                 'Materials',         'New installations -- materials', ('Sector',)),
    (r'24_Material_old_(?P<d1>.+)',                 'Materials',         'End of life -- materials',     ('Sector',)),
    (r'24_Material_decom_(?P<d1>.+)',               'Materials',         'Decommissioning -- materials', ('Sector',)),
    (r'24_Material_mult_(?P<d1>.+)',                'Materials',         'Installed -- materials',       ('Sector',)),
    (r'25_Material_sector_demand_(?P<d1>.+)',       'Materials',         'Material demand -- by sector', ('Sector',)),
    (r'25_Material_sector_decom_(?P<d1>.+)',        'Materials',         'Material decom -- by sector',  ('Sector',)),
    (r'25_Material_sector_detail_(?P<d1>.+)',       'Materials',         'Material demand by sub-tech',  ('Sector',)),
]

_DASH_SECTION_ORDER = ['Overview', 'Initial 2020', 'Costs', 'Capacity', 'Production',
                       'Energy balances', 'Mobility', 'Emissions & flows', 'Materials', 'Other']

# Canonical ordering for chip values (years sort numerically before this applies)
_DASH_DIM_ORDER = ['ALL', 'SD', 'MD', 'LD', 'ELD',
                   'EHV', 'HV', 'MV', 'LV', 'EHP', 'HP', 'MP', 'LP',
                   'NG_EHP', 'NG_HP', 'NG_MP', 'NG_LP',
                   'ELECTRICITY', 'HEAT_LOW_T', 'HEAT_HIGH_T', 'H2_SYNFUELS',
                   'MOB_PRIVATE', 'MOB_PUBLIC', 'MOB_FREIGHT', 'INDUSTRY',
                   'INFRASTRUCTURE', 'STORAGE', 'CO2',
                   'High_T', 'Low_T_decen.', 'Waste_heat']

_DASH_ACRONYMS = {'CO2', 'H2', 'NG', 'SNG', 'EHV', 'HV', 'MV', 'LV', 'EHP', 'HP',
                  'MP', 'LP', 'SD', 'MD', 'LD', 'ELD', 'CRF', 'AMPL', 'GWP',
                  'CAPEX', 'OPEX', 'DHN', 'CCS', 'T'}


def _dash_dim_sort(values):
    def key(v):
        if re.fullmatch(r'20\d\d', v):
            return (0, int(v), '')
        if v in _DASH_DIM_ORDER:
            return (1, _DASH_DIM_ORDER.index(v), '')
        return (2, 0, v.lower())
    return sorted(values, key=key)


def _dash_pretty(v):
    out = []
    for p in re.split(r'[_\s]+', str(v).strip()):
        if p.upper().rstrip('.') in _DASH_ACRONYMS:
            out.append(p.upper())
        else:
            out.append(p if re.fullmatch(r'20\d\d', p) else p.capitalize())
    return ' '.join(out)


def create_dashboard(outdir, case_study):
    graphs = sorted(f for f in os.listdir(outdir) if f.endswith('.html') and f != 'index.html')

    families = {}
    others = []
    for g in graphs:
        stem = g[:-5]
        for order, (pat, section, family, dims) in enumerate(_DASH_SPECS):
            m = re.fullmatch(pat, stem)
            if not m:
                continue
            gd = m.groupdict()
            parts = [gd[k] for k in ('year', 'd1') if gd.get(k) is not None]
            fam = families.setdefault((section, family), {
                'order': order, 'dims': list(dims),
                'values': [set() for _ in dims], 'files': {},
            })
            for i, p in enumerate(parts):
                fam['values'][i].add(p)
            fam['files']['|'.join(parts)] = g
            break
        else:
            others.append(g)

    sections = defaultdict(list)
    for (section, family), fam in families.items():
        dims = [{'name': n, 'values': _dash_dim_sort(vs),
                 'labels': {v: _dash_pretty(v) for v in vs}}
                for n, vs in zip(fam['dims'], fam['values'])]
        files = fam['files']
        # Drop single-valued dimensions (no chips needed)
        keep = [i for i, d in enumerate(dims) if len(d['values']) > 1]
        if len(keep) != len(dims):
            new_files = {}
            for k, v in files.items():
                parts = k.split('|') if k else []
                new_files['|'.join(parts[i] for i in keep)] = v
            files = new_files
            dims = [dims[i] for i in keep]
        sections[section].append({'order': fam['order'], 'label': family,
                                  'dims': dims, 'files': files})
    for g in others:
        sections['Other'].append({'order': 999, 'dims': [], 'files': {'': g},
                                  'label': _dash_pretty(re.sub(r'^\d+[a-z]?_', '', g[:-5]))})

    for s in sections:
        sections[s].sort(key=lambda it: it['order'])

    if os.path.exists(os.path.join(os.path.dirname(outdir), '0_Summary.html')):
        sections['Overview'].insert(0, {'order': -1, 'label': 'System summary',
                                        'dims': [], 'files': {'': '../0_Summary.html'}})

    nav = ([{'section': s, 'items': sections[s]} for s in _DASH_SECTION_ORDER if s in sections]
           + [{'section': s, 'items': sections[s]} for s in sections if s not in _DASH_SECTION_ORDER])

    seen_slugs = set()
    for sec in nav:
        for it in sec['items']:
            base = re.sub(r'[^a-z0-9]+', '-', f"{sec['section']} {it['label']}".lower()).strip('-')
            slug, k = base, 2
            while slug in seen_slugs:
                slug, k = f'{base}-{k}', k + 1
            seen_slugs.add(slug)
            it['slug'] = slug

    out_root = os.path.dirname(os.path.dirname(os.path.abspath(outdir)))
    try:
        cases = sorted(d for d in os.listdir(out_root)
                       if d != case_study
                       and os.path.isdir(os.path.join(out_root, d, 'graphs')))
    except OSError:
        cases = []

    html_tpl = """<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<title>__CASE__</title>
<style>
  * { box-sizing: border-box; margin: 0; padding: 0; }
  :root {
    --bg: #f6f7f9; --panel: #ffffff; --line: #e5e7eb;
    --ink: #1b1f27; --ink2: #6b7280; --ink3: #9aa1ab;
    --accent: #2563eb; --accent-soft: #eef3fe;
    --side-bg: #152238; --side-line: #24344f; --side-ink: #c7d2e5;
    --side-ink2: #8fa3c4; --side-ink3: #64779b; --side-accent: #7db1ff;
  }
  body { display: flex; height: 100vh; background: var(--bg); color: var(--ink);
         font-family: -apple-system, 'Segoe UI', Roboto, Helvetica, sans-serif; }
  #sidebar { width: 248px; min-width: 200px; background: var(--side-bg);
             display: flex; flex-direction: column; flex-shrink: 0; }
  #sidebar header { padding: 16px 16px 12px; border-bottom: 1px solid var(--side-line); }
  .brand { font-size: 13px; font-weight: 700; letter-spacing: .02em; color: #ffffff; }
  .case  { font-size: 11.5px; color: var(--side-ink2); margin-top: 3px; word-break: break-all; }
  #casesel { width: 100%; margin-top: 5px; background: #0f1a2e; color: var(--side-ink);
             border: 1px solid var(--side-line); border-radius: 6px; font-size: 11.5px;
             padding: 3px 6px; font-family: inherit; cursor: pointer; }
  #casesel:hover { border-color: var(--side-accent); }
  #casesel:disabled { background: transparent; border-color: transparent; appearance: none;
                      padding-left: 0; cursor: default; color: var(--side-ink2); opacity: 1; }
  #nav { overflow-y: auto; padding: 6px 8px 20px; flex: 1; scrollbar-width: thin;
         scrollbar-color: #33456622 transparent; }
  #nav::-webkit-scrollbar { width: 8px; }
  #nav::-webkit-scrollbar-thumb { background: #334566; border-radius: 4px; }
  .sec { font-size: 12px; font-weight: 700; text-transform: uppercase;
         letter-spacing: .09em; color: #a9bedf; padding: 14px 8px 6px;
         border-top: 1px solid #3a4f78; margin-top: 26px; }
  .sec:first-child { border-top: 0; margin-top: 4px; }
  .item { display: flex; align-items: center; gap: 6px; width: 100%; text-align: left;
          border: 0; background: none;
          padding: 6px 9px; border-radius: 6px; font-size: 13px; color: var(--side-ink);
          cursor: pointer; font-family: inherit; }
  .itemlabel { flex: 1; min-width: 0; }
  .item .pin { opacity: 0; flex-shrink: 0; font-size: 12px; }
  .item:hover .pin { opacity: .6; }
  .item .pin:hover { opacity: 1; color: #ffd75e; }
  .item.pinned .pin { opacity: .9; color: #ffd75e; }
  .item:hover { background: rgba(255,255,255,.06); color: #ffffff; }
  .item.active { background: rgba(125,177,255,.16); color: var(--side-accent); font-weight: 600; }
  main { flex: 1; display: flex; flex-direction: column; min-width: 0; }
  #topbar { background: var(--side-bg); border-bottom: 1px solid var(--side-line);
            padding: 12px 18px; }
  #titlerow { display: flex; align-items: baseline; justify-content: space-between; gap: 12px; }
  #charttitle { font-size: 15px; font-weight: 600; color: #ffffff; }
  #charttitle small { font-weight: 400; color: var(--side-ink2); }
  #openraw { font-size: 12px; color: var(--side-accent); text-decoration: none; white-space: nowrap; }
  #openraw:hover { text-decoration: underline; }
  .chiprow { display: flex; align-items: center; gap: 6px; margin-top: 10px; flex-wrap: wrap; }
  .dimname { font-size: 10.5px; font-weight: 600; color: var(--side-ink3);
             text-transform: uppercase; letter-spacing: .06em; min-width: 62px; }
  .chip { border: 1px solid var(--side-line); background: transparent; border-radius: 999px;
          padding: 3px 11px; font-size: 12.5px; color: var(--side-ink); cursor: pointer;
          font-family: inherit; }
  .chip:hover { border-color: var(--side-accent); color: var(--side-accent); }
  .chip.on { background: var(--accent); border-color: var(--accent); color: #fff; }
  .chip.miss { color: #4d6188; border-style: dashed; }
  .step { border: 1px solid var(--side-line); background: transparent; border-radius: 6px;
          padding: 2px 8px; font-size: 12px; color: var(--side-ink2); cursor: pointer;
          font-family: inherit; }
  .step:hover { border-color: var(--side-accent); color: var(--side-accent); }
  .step.on { background: var(--accent); border-color: var(--accent); color: #fff; }
  #tools { display: flex; align-items: center; gap: 12px; }
  #cmpsel { background: #0f1a2e; color: var(--side-ink); border: 1px solid var(--side-line);
            border-radius: 6px; font-size: 12px; padding: 3px 6px; font-family: inherit;
            max-width: 240px; }
  #cmptools { display: none; align-items: center; gap: 4px; }
  #cmptools button { border: 1px solid var(--side-line); background: transparent;
               border-radius: 6px; padding: 3px 9px; font-size: 12px; color: var(--side-ink2);
               cursor: pointer; font-family: inherit; white-space: nowrap; }
  #cmptools button:hover { border-color: var(--side-accent); color: var(--side-accent); }
  #cmptools button.on { background: var(--accent); border-color: var(--accent); color: #fff; }
  #navsearch { margin: 10px 8px 0; padding: 5px 9px; width: calc(100% - 16px);
               background: #0f1a2e; border: 1px solid var(--side-line); border-radius: 6px;
               color: var(--side-ink); font-size: 12.5px; font-family: inherit; }
  #navsearch::placeholder { color: var(--side-ink3); }
  #navsearch:focus { outline: none; border-color: var(--side-accent); }
  #frames { flex: 1; display: flex; min-height: 0; }
  #frames.stacked { flex-direction: column; }
  .pane { flex: 1; display: flex; flex-direction: column; min-width: 0; min-height: 0; }
  .pane iframe { flex: 1; border: 0; width: 100%; background: #fff; }
  .panelabel { display: none; background: #0f1a2e; color: var(--side-ink2); font-size: 11px;
               padding: 4px 10px; border-bottom: 1px solid var(--side-line); text-align: center;
               overflow: hidden; text-overflow: ellipsis; white-space: nowrap; flex-shrink: 0; }
  #frames.cmp .panelabel { display: block; }
  #frames.flip .panelabel { cursor: pointer; }
  #pane2 { display: none; }
  #frames.cmp #pane2 { display: flex; border-left: 3px solid var(--side-bg); }
  #frames.cmp.stacked #pane2 { border-left: 0; border-top: 3px solid var(--side-bg); }
  #frames.cmp.flip #pane2 { border-left: 0; border-top: 0; }
  /* flip: keep both panes laid out full-size (visibility, not display) so the
     hidden Plotly plot always has the right width when it is revealed */
  #frames.cmp.flip { position: relative; }
  #frames.cmp.flip .pane { position: absolute; inset: 0; }
  #frames.cmp.flip #pane1:not(.show), #frames.cmp.flip #pane2:not(.show) { visibility: hidden; }
  #frames.swapped #pane1 { order: 2; }
  #frames.swapped #pane2 { order: 1; }
  #frames.cmp.swapped #pane2 { border-left: 0; border-top: 0; }
  #frames.cmp.swapped:not(.flip) #pane1 { border-left: 3px solid var(--side-bg); }
  #frames.cmp.stacked.swapped #pane1 { border-left: 0; border-top: 3px solid var(--side-bg); }
  #grid { flex: 1; display: none; overflow-y: auto; padding: 12px;
          grid-template-columns: repeat(auto-fill, minmax(430px, 1fr));
          grid-auto-rows: 360px; gap: 12px; background: var(--bg); }
  .gcell { display: flex; flex-direction: column; border: 1px solid var(--line);
           border-radius: 8px; background: #fff; overflow: hidden; }
  .gcell.cur { border-color: var(--accent); box-shadow: 0 0 0 1px var(--accent); }
  .gcell header { font-size: 12px; font-weight: 600; padding: 5px 10px; background: #f0f3f8;
                  color: #333; cursor: pointer; border-bottom: 1px solid var(--line);
                  flex-shrink: 0; }
  .gcell header:hover { color: var(--accent); }
  .gcell iframe { flex: 1; border: 0; width: 100%; }
  .gempty { flex: 1; display: flex; align-items: center; justify-content: center;
            color: var(--ink3); font-size: 20px; }
  #palette { display: none; position: fixed; inset: 0; background: rgba(10,16,28,.55);
             z-index: 50; }
  #palette.open { display: flex; align-items: flex-start; justify-content: center;
                  padding-top: 12vh; }
  #palbox { width: 560px; max-width: 90vw; background: var(--panel); border-radius: 10px;
            box-shadow: 0 12px 40px rgba(0,0,0,.35); overflow: hidden; }
  #palinput { width: 100%; border: 0; padding: 14px 16px; font-size: 15px;
              font-family: inherit; outline: none; border-bottom: 1px solid var(--line);
              color: var(--ink); background: var(--panel); }
  #palresults { max-height: 50vh; overflow-y: auto; }
  .palrow { padding: 9px 16px; font-size: 13.5px; cursor: pointer; color: var(--ink);
            overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .palrow.sel { background: var(--accent-soft); color: var(--accent); }
</style>
</head>
<body>
<aside id="sidebar">
  <header>
    <div class="brand">EnergyScope — pathway</div>
    <select id="casesel" title="Switch to another run"><option>__CASE__</option></select>
  </header>
  <input id="navsearch" type="search" placeholder="Filter charts…  ( / )">
  <nav id="nav"></nav>
</aside>
<main>
  <div id="topbar">
    <div id="titlerow">
      <h1 id="charttitle"></h1>
      <div id="tools">
        <select id="cmpsel"><option value="">Compare with…</option></select>
        <div id="cmptools">
          <button id="lay-stack" title="Stack the two cases vertically">⊟ stack</button>
          <button id="lay-side" title="Show the two cases side by side">◫ side</button>
          <button id="lay-flip" title="One case at a time — press space to flip">⇄ flip</button>
          <button id="cmpswap" title="Swap the order of the two cases">⇅ swap</button>
        </div>
        <a id="openraw" target="_blank">Open in new tab ↗</a>
      </div>
    </div>
    <div id="chips"></div>
  </div>
  <div id="frames" class="stacked">
    <div class="pane" id="pane1"><div class="panelabel" id="cmpA"></div><iframe id="viewer"></iframe></div>
    <div class="pane" id="pane2"><div class="panelabel" id="cmpB"></div><iframe id="viewer2"></iframe></div>
  </div>
  <div id="grid"></div>
</main>
<div id="palette"><div id="palbox">
  <input id="palinput" type="text" placeholder="Jump to chart, year, view…  (Ctrl+K)">
  <div id="palresults"></div>
</div></div>
<script>
const NAV = __NAV__;
const CASES = __CASES__;
const CASENAME = __CASENAME__;
const viewer  = document.getElementById('viewer');
const viewer2 = document.getElementById('viewer2');
const chipsEl = document.getElementById('chips');
const titleEl = document.getElementById('charttitle');
const openEl  = document.getElementById('openraw');
const navEl   = document.getElementById('nav');
const cmpsel  = document.getElementById('cmpsel');
const casesel = document.getElementById('casesel');
const framesEl = document.getElementById('frames');
const cmptools = document.getElementById('cmptools');
const pane1 = document.getElementById('pane1');
const pane2 = document.getElementById('pane2');
const layBtns = { stack: document.getElementById('lay-stack'),
                  side:  document.getElementById('lay-side'),
                  flip:  document.getElementById('lay-flip') };
const swapBtn  = document.getElementById('cmpswap');
const searchEl = document.getElementById('navsearch');
const gridEl   = document.getElementById('grid');
const paletteEl = document.getElementById('palette');
const palinput  = document.getElementById('palinput');
const palresults = document.getElementById('palresults');
let cmpLayout = localStorage.getItem('cmpLayout') || 'stack';
if (!(cmpLayout in layBtns)) cmpLayout = 'stack';
let cmpSwapped = false;
let flipShown = 0;
let playTimer = null;
let pinned = [];
try { pinned = JSON.parse(localStorage.getItem('pinnedCharts') || '[]'); } catch (e) {}
if (!Array.isArray(pinned)) pinned = [];
let pinBtnMap = {};
let pinHdr = null, pinList = null;
let gridDim = null;
const PAL = [];
let palSel = 0, palItems = [];
let cur = null;
const memo = {};
const BYSLUG = {};
const FLAT = [];
const navBtn = {};
let globalYear = null;
let syncYears = true;
let compareCase = '';
let lastHash = '';

function keyOf(sel) { return sel.join('|'); }

function defaultSel(item) {
  if (!item.dims.length) return [];
  let sels = [[]];
  for (const d of item.dims) {
    const next = [];
    for (const s of sels) for (const v of d.values) next.push(s.concat(v));
    sels = next;
  }
  for (const s of sels) if (item.files[keyOf(s)]) return s;
  return [];
}

function bestSel(item, dimIdx, value, prevSel) {
  let best = null, bestScore = -1;
  for (const k of Object.keys(item.files)) {
    const parts = k === '' ? [] : k.split('|');
    if (parts[dimIdx] !== value) continue;
    let score = 0;
    prevSel.forEach((v, i) => { if (i !== dimIdx && parts[i] === v) score++; });
    if (score > bestScore) { bestScore = score; best = parts; }
  }
  return best;
}

function applyGlobalYear(item, sel) {
  if (!syncYears || globalYear === null) return sel;
  const i = item.dims.findIndex(d => d.name === 'Year');
  if (i < 0 || sel[i] === globalYear || item.dims[i].values.indexOf(globalYear) < 0) return sel;
  const t = sel.slice(); t[i] = globalYear;
  if (item.files[keyOf(t)]) return t;
  return bestSel(item, i, globalYear, sel) || sel;
}

function selectItem(item, selOverride) {
  if (cur && cur.item !== item) gridDim = null;
  document.querySelectorAll('.item.active').forEach(b => b.classList.remove('active'));
  if (navBtn[item.slug]) {
    navBtn[item.slug].classList.add('active');
    navBtn[item.slug].scrollIntoView({ block: 'nearest' });
  }
  if (pinBtnMap[item.slug]) pinBtnMap[item.slug].classList.add('active');
  let sel = selOverride || memo[item.slug] || defaultSel(item);
  if (!selOverride) sel = applyGlobalYear(item, sel);
  cur = { item: item, sel: sel };
  render();
}

function pickChip(i, v) {
  const trial = cur.sel.slice(); trial[i] = v;
  if (cur.item.files[keyOf(trial)]) {
    cur.sel = trial;
  } else {
    const b = bestSel(cur.item, i, v, cur.sel);
    if (!b) return;
    cur.sel = b;
  }
  memo[cur.item.slug] = cur.sel;
  if (cur.item.dims[i] && cur.item.dims[i].name === 'Year') globalYear = cur.sel[i];
  render();
}

function stepDim(i, delta) {
  if (!cur || i < 0 || i >= cur.item.dims.length) return;
  const vals = cur.item.dims[i].values;
  const idx = vals.indexOf(cur.sel[i]) + delta;
  if (idx < 0 || idx >= vals.length) return;
  pickChip(i, vals[idx]);
}

function stepArrow(delta, shifted) {
  if (!cur || !cur.item.dims.length) return;
  const yi = cur.item.dims.findIndex(d => d.name === 'Year');
  let i;
  if (shifted) i = cur.item.dims.findIndex((d, j) => j !== yi);
  else i = yi >= 0 ? yi : 0;
  stepDim(i, delta);
}

function stepItem(delta) {
  if (!cur) return;
  let i = FLAT.indexOf(cur.item);
  do {
    i += delta;
    if (i < 0 || i >= FLAT.length) return;
  } while (navBtn[FLAT[i].slug].style.display === 'none');
  selectItem(FLAT[i]);
}

function filterNav(q) {
  q = q.trim().toLowerCase();
  NAV.forEach(sec => {
    let any = false;
    sec.items.forEach(item => {
      item._match = null;
      let hit = !q || item.label.toLowerCase().indexOf(q) >= 0
                   || sec.section.toLowerCase().indexOf(q) >= 0;
      if (!hit) {
        for (let i = 0; i < item.dims.length && !hit; i++) {
          const d = item.dims[i];
          for (let k = 0; k < d.values.length; k++) {
            const v = d.values[k];
            const lbl = String(d.labels[v] || v).toLowerCase();
            if (lbl.indexOf(q) >= 0 || String(v).toLowerCase().indexOf(q) >= 0) {
              hit = true; item._match = { i: i, v: v };
              break;
            }
          }
        }
      }
      navBtn[item.slug].style.display = hit ? '' : 'none';
      navBtn[item.slug].title = item._match
        ? 'Match — ' + item.dims[item._match.i].name + ': '
          + (item.dims[item._match.i].labels[item._match.v] || item._match.v)
        : '';
      if (hit) any = true;
    });
    if (sec._hdr) sec._hdr.style.display = any ? '' : 'none';
  });
}

function stopPlay() {
  if (playTimer) { clearInterval(playTimer); playTimer = null; }
}

function togglePlay() {
  if (playTimer) { stopPlay(); render(); return; }
  if (!cur || cur.item.dims.findIndex(d => d.name === 'Year') < 0) return;
  playTimer = setInterval(() => {
    if (!cur) { stopPlay(); return; }
    const i = cur.item.dims.findIndex(d => d.name === 'Year');
    if (i < 0) { stopPlay(); render(); return; }
    const vals = cur.item.dims[i].values;
    let idx = vals.indexOf(cur.sel[i]) + 1;
    if (idx >= vals.length) idx = 0;
    pickChip(i, vals[idx]);
  }, 1300);
  render();
}

function makeItemButton(item) {
  const b = document.createElement('button'); b.className = 'item';
  const lab = document.createElement('span'); lab.className = 'itemlabel';
  lab.textContent = item.label;
  const st = document.createElement('span'); st.className = 'pin';
  st.textContent = pinned.indexOf(item.slug) >= 0 ? '★' : '☆';
  st.title = 'Pin / unpin';
  st.onclick = e => { e.stopPropagation(); togglePin(item.slug); };
  b.appendChild(lab); b.appendChild(st);
  return b;
}

function togglePin(slug) {
  const i = pinned.indexOf(slug);
  if (i >= 0) pinned.splice(i, 1); else pinned.push(slug);
  localStorage.setItem('pinnedCharts', JSON.stringify(pinned));
  refreshPins();
}

function refreshPins() {
  Object.keys(navBtn).forEach(s => {
    const on = pinned.indexOf(s) >= 0;
    navBtn[s].classList.toggle('pinned', on);
    navBtn[s].querySelector('.pin').textContent = on ? '★' : '☆';
  });
  pinBtnMap = {};
  pinList.innerHTML = '';
  const valid = pinned.filter(s => BYSLUG[s]);
  pinHdr.style.display = valid.length ? '' : 'none';
  if (NAV.length && NAV[0]._hdr) {
    NAV[0]._hdr.style.borderTop = valid.length ? '' : '0';
    NAV[0]._hdr.style.marginTop = valid.length ? '' : '4px';
  }
  valid.forEach(s => {
    const item = BYSLUG[s];
    const b = makeItemButton(item);
    b.classList.add('pinned');
    b.onclick = () => selectItem(item);
    if (cur && cur.item.slug === s) b.classList.add('active');
    pinBtnMap[s] = b;
    pinList.appendChild(b);
  });
}

function toggleGrid(i) {
  gridDim = (gridDim === i) ? null : i;
  render();
}

function renderGrid() {
  const item = cur.item, gi = gridDim, d = item.dims[gi];
  gridEl.innerHTML = '';
  d.values.forEach(v => {
    const s = cur.sel.slice(); s[gi] = v;
    const f = item.files[keyOf(s)];
    const cell = document.createElement('div');
    cell.className = 'gcell' + (v === cur.sel[gi] ? ' cur' : '');
    const h = document.createElement('header');
    h.textContent = d.labels[v] || v;
    h.title = 'Open full size';
    h.onclick = () => { gridDim = null; pickChip(gi, v); };
    cell.appendChild(h);
    if (f) {
      const ifr = document.createElement('iframe');
      ifr.loading = 'lazy';
      ifr.src = f;
      cell.appendChild(ifr);
    } else {
      const ph = document.createElement('div'); ph.className = 'gempty';
      ph.textContent = 'not available';
      cell.appendChild(ph);
    }
    gridEl.appendChild(cell);
  });
}

function fuzzy(q, s) {
  s = s.toLowerCase();
  const idx = s.indexOf(q);
  if (idx >= 0) return 1000 - idx;
  let i = 0, score = 0, last = -2;
  for (let k = 0; k < q.length; k++) {
    if (q[k] === ' ') continue;
    i = s.indexOf(q[k], i);
    if (i < 0) return -1;
    score += (i === last + 1) ? 3 : 1;
    last = i; i++;
  }
  return score;
}

function setPalSel(i) {
  palSel = i;
  Array.from(palresults.children).forEach((el, j) => {
    el.classList.toggle('sel', j === palSel);
    if (j === palSel) el.scrollIntoView({ block: 'nearest' });
  });
}

function palRender() {
  const q = palinput.value.trim().toLowerCase();
  if (!q) {
    palItems = PAL.filter(p => p.dim === null).slice(0, 15);
  } else {
    const scored = [];
    PAL.forEach(p => { const s = fuzzy(q, p.text); if (s > 0) scored.push([s, p]); });
    scored.sort((a, b) => b[0] - a[0]);
    palItems = scored.slice(0, 12).map(x => x[1]);
  }
  if (palSel >= palItems.length) palSel = 0;
  palresults.innerHTML = '';
  palItems.forEach((p, i) => {
    const r = document.createElement('div');
    r.className = 'palrow' + (i === palSel ? ' sel' : '');
    r.textContent = p.text;
    r.onclick = () => palGo(p);
    r.onmouseenter = () => setPalSel(i);
    palresults.appendChild(r);
  });
}

function palGo(p) {
  closePalette();
  if (p.dim === null) { selectItem(p.item); return; }
  const base = memo[p.item.slug] || defaultSel(p.item);
  const sel = base[p.dim] === p.v ? base : bestSel(p.item, p.dim, p.v, base);
  selectItem(p.item, sel || base);
}

function openPalette() {
  paletteEl.classList.add('open');
  palinput.value = '';
  palSel = 0;
  palRender();
  palinput.focus();
}

function closePalette() {
  paletteEl.classList.remove('open');
  palinput.blur();
}

function pathFor(f, c) {
  if (!c) return f;
  if (f.indexOf('../') === 0) return '../../' + c + '/' + f.slice(3);
  return '../../' + c + '/graphs/' + f;
}

function updateHash() {
  if (!cur) return;
  let h = '#' + [cur.item.slug].concat(cur.sel.map(encodeURIComponent)).join('/');
  if (compareCase) h += '~' + encodeURIComponent(compareCase);
  lastHash = h;
  if (location.hash !== h) location.hash = h;
}

function applyHash() {
  let h = location.hash.slice(1);
  if (!h) return false;
  let cmp = '';
  const ti = h.indexOf('~');
  if (ti >= 0) { cmp = decodeURIComponent(h.slice(ti + 1)); h = h.slice(0, ti); }
  const parts = h.split('/').map(decodeURIComponent);
  const item = BYSLUG[parts[0]];
  if (!item) return false;
  compareCase = CASES.indexOf(cmp) >= 0 ? cmp : '';
  cmpsel.value = compareCase;
  let sel = parts.slice(1);
  if (sel.length !== item.dims.length || !item.files[keyOf(sel)]) sel = null;
  if (sel) {
    const yi = item.dims.findIndex(d => d.name === 'Year');
    if (yi >= 0) globalYear = sel[yi];
  }
  selectItem(item, sel);
  return true;
}

function updatePaneLabels() {
  const hint = (compareCase && cmpLayout === 'flip') ? '  ·  space or click to flip' : '';
  document.getElementById('cmpA').textContent = CASENAME + hint;
  document.getElementById('cmpB').textContent = (compareCase || '') + hint;
}

function nudgePlotResize() {
  // Best effort: blocked cross-frame under file:// in some browsers, hence try/catch.
  requestAnimationFrame(() => {
    [viewer, viewer2].forEach(fr => {
      try { fr.contentWindow.dispatchEvent(new Event('resize')); } catch (e) {}
    });
  });
}

function applyCmpLayout() {
  framesEl.classList.toggle('stacked', cmpLayout === 'stack');
  framesEl.classList.toggle('flip', cmpLayout === 'flip');
  framesEl.classList.toggle('swapped', cmpSwapped);
  Object.keys(layBtns).forEach(k => layBtns[k].classList.toggle('on', cmpLayout === k));
  swapBtn.style.display = cmpLayout === 'flip' ? 'none' : '';
  pane1.classList.toggle('show', flipShown === 0);
  pane2.classList.toggle('show', flipShown === 1);
  updatePaneLabels();
  nudgePlotResize();
}

function flipCase() {
  if (!compareCase || cmpLayout !== 'flip') return;
  flipShown = 1 - flipShown;
  pane1.classList.toggle('show', flipShown === 0);
  pane2.classList.toggle('show', flipShown === 1);
  nudgePlotResize();
}

function render() {
  const item = cur.item, sel = cur.sel;
  chipsEl.innerHTML = '';
  const yi = item.dims.findIndex(d => d.name === 'Year');
  item.dims.forEach((d, i) => {
    const row = document.createElement('div'); row.className = 'chiprow';
    const nm = document.createElement('span'); nm.className = 'dimname'; nm.textContent = d.name;
    row.appendChild(nm);
    const hint = (i === yi || (yi < 0 && i === 0)) ? '' : 'Shift+';
    const bp = document.createElement('button'); bp.className = 'step'; bp.textContent = '‹';
    bp.title = 'Previous ' + d.name + ' (' + hint + '←)';
    bp.onclick = () => stepDim(i, -1); row.appendChild(bp);
    d.values.forEach(v => {
      const c = document.createElement('button'); c.className = 'chip';
      c.textContent = d.labels[v] || v;
      if (sel[i] === v) {
        c.classList.add('on');
      } else {
        const t = sel.slice(); t[i] = v;
        if (!item.files[keyOf(t)]) c.classList.add('miss');
      }
      c.onclick = () => pickChip(i, v);
      row.appendChild(c);
    });
    const bn = document.createElement('button'); bn.className = 'step'; bn.textContent = '›';
    bn.title = 'Next ' + d.name + ' (' + hint + '→)';
    bn.onclick = () => stepDim(i, 1); row.appendChild(bn);
    if (d.values.length > 1) {
      const gb = document.createElement('button');
      gb.className = 'step' + (gridDim === i ? ' on' : '');
      gb.textContent = '⊞';
      gb.title = gridDim === i ? 'Back to single view (g / Esc)'
                               : 'Show every ' + d.name + ' in a grid (g)';
      gb.onclick = () => toggleGrid(i);
      row.appendChild(gb);
    }
    if (d.name === 'Year') {
      const pb = document.createElement('button');
      pb.className = 'step' + (playTimer ? ' on' : '');
      pb.textContent = playTimer ? '⏸' : '▶';
      pb.title = playTimer ? 'Pause (p)' : 'Play through the years (p)';
      pb.onclick = togglePlay;
      row.appendChild(pb);
      const sy = document.createElement('button');
      sy.className = 'step' + (syncYears ? ' on' : '');
      sy.textContent = 'sync';
      sy.title = 'Keep this year when switching chart families';
      sy.onclick = () => { syncYears = !syncYears; if (syncYears) globalYear = cur.sel[i]; render(); };
      row.appendChild(sy);
    }
    chipsEl.appendChild(row);
  });
  if (gridDim !== null && gridDim < item.dims.length) {
    framesEl.style.display = 'none';
    gridEl.style.display = 'grid';
    renderGrid();
    titleEl.innerHTML = item.label +
      ' <small>— every ' + item.dims[gridDim].name + '</small>';
    updateHash();
    return;
  }
  gridDim = null;
  framesEl.style.display = '';
  gridEl.style.display = 'none';
  gridEl.innerHTML = '';
  const f = item.files[keyOf(sel)];
  if (!f) return;
  if (viewer.getAttribute('src') !== f) viewer.src = f;
  openEl.href = f;
  if (compareCase) {
    const f2 = pathFor(f, compareCase);
    if (viewer2.getAttribute('src') !== f2) viewer2.src = f2;
    if (!framesEl.classList.contains('cmp')) {
      framesEl.classList.add('cmp');
      nudgePlotResize();
    }
    cmptools.style.display = 'flex';
  } else {
    framesEl.classList.remove('cmp');
    cmptools.style.display = 'none';
  }
  updatePaneLabels();
  titleEl.innerHTML = item.label + (sel.length
    ? ' <small>— ' + sel.map((v, i) => item.dims[i].labels[v] || v).join(' · ') + '</small>'
    : '');
  updateHash();
}

(function init() {
  pinHdr = document.createElement('div'); pinHdr.className = 'sec'; pinHdr.textContent = '★ Pinned';
  pinHdr.style.display = 'none';
  navEl.appendChild(pinHdr);
  pinList = document.createElement('div');
  navEl.appendChild(pinList);
  NAV.forEach(sec => {
    const h = document.createElement('div'); h.className = 'sec'; h.textContent = sec.section;
    sec._hdr = h;
    navEl.appendChild(h);
    sec.items.forEach(item => {
      BYSLUG[item.slug] = item;
      FLAT.push(item);
      const b = makeItemButton(item);
      b.onclick = () => {
        if (item._match) {
          const base = memo[item.slug] || defaultSel(item);
          const sel = base[item._match.i] === item._match.v
            ? base : bestSel(item, item._match.i, item._match.v, base);
          selectItem(item, sel || base);
        } else selectItem(item);
      };
      navBtn[item.slug] = b;
      navEl.appendChild(b);
    });
  });
  refreshPins();
  NAV.forEach(sec => sec.items.forEach(item => {
    PAL.push({ text: sec.section + ' › ' + item.label, item: item, dim: null, v: null });
    item.dims.forEach((d, i) => d.values.forEach(v => {
      PAL.push({ text: sec.section + ' › ' + item.label + ' › ' + d.name + ': '
                       + (d.labels[v] || v),
                 item: item, dim: i, v: v });
    }));
  }));
  palinput.oninput = () => { palSel = 0; palRender(); };
  palinput.addEventListener('keydown', e => {
    if (e.key === 'ArrowDown') { e.preventDefault(); setPalSel(Math.min(palSel + 1, palItems.length - 1)); }
    else if (e.key === 'ArrowUp') { e.preventDefault(); setPalSel(Math.max(palSel - 1, 0)); }
    else if (e.key === 'Enter') { if (palItems[palSel]) palGo(palItems[palSel]); }
    else if (e.key === 'Escape') closePalette();
    e.stopPropagation();
  });
  paletteEl.onclick = e => { if (e.target === paletteEl) closePalette(); };
  if (!CASES.length) cmpsel.style.display = 'none';
  CASES.forEach(c => {
    const o = document.createElement('option'); o.value = c; o.textContent = c;
    cmpsel.appendChild(o);
  });
  cmpsel.onchange = () => { compareCase = cmpsel.value; render(); };
  casesel.disabled = !CASES.length;
  CASES.forEach(c => {
    const o = document.createElement('option'); o.value = c; o.textContent = c;
    casesel.appendChild(o);
  });
  casesel.value = CASENAME;
  casesel.onchange = () => {
    const c = casesel.value;
    if (c === CASENAME) return;
    // Keep the current chart/selection via the hash; if we were comparing with
    // the run we switch to, compare back with the run we came from.
    let h = '';
    if (cur) {
      h = '#' + [cur.item.slug].concat(cur.sel.map(encodeURIComponent)).join('/');
      if (compareCase) h += '~' + encodeURIComponent(compareCase === c ? CASENAME : compareCase);
    }
    location.href = '../../' + encodeURIComponent(c) + '/graphs/index.html' + h;
  };
  Object.keys(layBtns).forEach(k => {
    layBtns[k].onclick = () => {
      cmpLayout = k;
      localStorage.setItem('cmpLayout', k);
      applyCmpLayout();
    };
  });
  swapBtn.onclick = () => { cmpSwapped = !cmpSwapped; applyCmpLayout(); };
  document.getElementById('cmpA').onclick = flipCase;
  document.getElementById('cmpB').onclick = flipCase;
  searchEl.oninput = () => filterNav(searchEl.value);
  applyCmpLayout();
  if (!applyHash()) {
    const first = NAV.length && NAV[0].items.length ? NAV[0].items[0] : null;
    if (first) selectItem(first);
  }
})();

window.addEventListener('hashchange', () => {
  if (location.hash === lastHash) return;
  applyHash();
});

document.addEventListener('keydown', e => {
  if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'k') {
    e.preventDefault();
    if (paletteEl.classList.contains('open')) closePalette(); else openPalette();
    return;
  }
  const t = e.target;
  if (t && (t.tagName === 'INPUT' || t.tagName === 'SELECT' || t.tagName === 'TEXTAREA')) {
    if (e.key === 'Escape' && t === searchEl) { searchEl.value = ''; filterNav(''); searchEl.blur(); }
    return;
  }
  if (e.key === 'ArrowLeft') stepArrow(-1, e.shiftKey);
  else if (e.key === 'ArrowRight') stepArrow(1, e.shiftKey);
  else if (e.key === 'ArrowUp') { e.preventDefault(); stepItem(-1); }
  else if (e.key === 'ArrowDown') { e.preventDefault(); stepItem(1); }
  else if (e.key === ' ') {
    if (compareCase && cmpLayout === 'flip') { e.preventDefault(); flipCase(); }
  }
  else if (e.key === 'p') togglePlay();
  else if (e.key === 'g') {
    if (cur && cur.item.dims.length) {
      if (gridDim !== null) toggleGrid(gridDim);
      else {
        const yi = cur.item.dims.findIndex(d => d.name === 'Year');
        toggleGrid(yi >= 0 ? yi : 0);
      }
    }
  }
  else if (e.key === 'Escape') {
    if (gridDim !== null) { gridDim = null; render(); }
  }
  else if (e.key === '/') { e.preventDefault(); searchEl.focus(); }
});
</script>
</body>
</html>"""

    html = (html_tpl
            .replace('__NAV__', _jdumps(nav))
            .replace('__CASES__', _jdumps(cases))
            .replace('__CASENAME__', _jdumps(case_study))
            .replace('__CASE__', case_study))

    path = os.path.join(outdir, 'index.html')
    with open(path, 'w', encoding='utf-8') as f:
        f.write(html)
    print(f"  Dashboard: {path}")
    webbrowser.open(f'file:///{os.path.abspath(path).replace(os.sep, "/")}')


# ===========================================================================
# SUMMARY DASHBOARD
# ===========================================================================

# Primary-resource grouping for the summary mix panel. Annual_Prod double-counts
# conversion chains (electricity producers AND the heat pumps consuming that
# electricity), so the mix is computed on the Resources result instead.
_RES_GROUP_ORDER = ['Hydro', 'Wind', 'Solar', 'Other renew.', 'Biomass',
                    'Biofuels (imp.)', 'Electricity (imp.)', 'H2 (imp.)',
                    'Uranium', 'Fossil fuels', 'Other']
_RES_RENEWABLE = ['Hydro', 'Wind', 'Solar', 'Other renew.', 'Biomass', 'Biofuels (imp.)']
_RES_COLORS = {
    'Hydro':              '#1f77b4',
    'Wind':               '#5bc0de',
    'Solar':              '#f2c14e',
    'Other renew.':       '#2ca089',
    'Biomass':            '#4a9d5f',
    'Biofuels (imp.)':    '#98d083',
    'Electricity (imp.)': '#9467bd',
    'H2 (imp.)':          '#7f7fd5',
    'Uranium':            '#e377c2',
    'Fossil fuels':       '#c0392b',
    'Other':              '#b0b0b0',
}
_RES_FOSSIL_NAMES = {'DIESEL', 'GASOLINE', 'LFO', 'HFO', 'LNG', 'JETFUEL',
                     'PROPANE', 'COAL', 'WASTE_FOS', 'WASTE', 'ETHANOL'}


def _res_group(res):
    r = str(res).upper()
    if r == 'RES_HYDRO':                    return 'Hydro'
    if r.startswith('RES_WIND'):            return 'Wind'
    if r == 'RES_SOLAR':                    return 'Solar'
    if r in ('RES_GEO', 'RES_TIDAL'):       return 'Other renew.'
    if r.startswith('BIOMASS_') or r in ('WOOD', 'WET_BIOMASS', 'WASTE_BIO'):
        return 'Biomass'
    if r.startswith('BIO_') or r.startswith('SNG'):
        return 'Biofuels (imp.)'
    if r == 'ELECTRICITY_EHV':              return 'Electricity (imp.)'
    if r.startswith('H2_') and not r.endswith('_S'):
        return 'H2 (imp.)'
    if r == 'URANIUM':                      return 'Uranium'
    if r in _RES_FOSSIL_NAMES or (r.startswith('NG_') and not r.endswith('_S')):
        return 'Fossil fuels'
    if (r.startswith('ELEC_EXPORT') or r.startswith('ELECTRICITY_')
            or r.startswith('CO2_') or r.endswith('_S')):
        return '_EXCLUDE_'
    return 'Other'


def plot_summary_dashboard(results, outdir, case_study):
    """
    Two-panel summary figure:
      Left  — stacked area: primary resource mix [TWh/y]
      Right — KPI lines: Renewable %, Fossil %, Biomass & biofuels %, Elec import %
    """
    key = 'Annual_Prod'
    if results.get(key) is None:
        print(f'[SKIP summary_dashboard] {key} not in results'); return
    if results.get('Resources') is None:
        print('[SKIP summary_dashboard] Resources not in results'); return

    df = results['Resources'].copy().reset_index()
    df.columns = ['Years', 'Technologies', 'GWh']
    df['Technologies'] = df['Technologies'].astype(str)
    df['Years'] = df['Years'].astype(str)
    df['Year'] = df['Years'].str.replace('YEAR_', '').astype(int)
    df = df[df['Year'].isin([int(y) for y in YEARS_ORDER])]
    df['GWh'] = pd.to_numeric(df['GWh'], errors='coerce').fillna(0)
    df = df[df['GWh'] > 0]
    df['FuelType'] = df['Technologies'].apply(_res_group)
    df = df[df['FuelType'] != '_EXCLUDE_']

    df['TWh'] = df['GWh'] / 1000

    years = sorted(df['Year'].unique())
    agg = df.groupby(['Year', 'FuelType'])['TWh'].sum().reset_index()
    fuel_order = [g for g in _RES_GROUP_ORDER if g in set(agg['FuelType'])]

    total_per_year = agg.groupby('Year')['TWh'].sum().reindex(years).replace(0, pd.NA)

    def _share(groups):
        s = (agg[agg['FuelType'].isin(groups)]
             .groupby('Year')['TWh'].sum().reindex(years).fillna(0))
        return (s / total_per_year * 100).fillna(0)

    renewable_pct = _share(_RES_RENEWABLE)
    fossil_pct    = _share(['Fossil fuels'])
    elec_imp_pct  = _share(['Electricity (imp.)'])
    bio_pct       = _share(['Biomass', 'Biofuels (imp.)'])

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
        subplot_titles=['Primary resources [TWh/y]', 'Key indicators [%]',
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
    # One legendgroup per trace: a legend click must hide only that fuel,
    # not the whole panel (default groupclick toggles the entire group).
    for fi, fuel in enumerate(fuel_order):
        sub = agg[agg['FuelType'] == fuel].set_index('Year').reindex(years)['TWh'].fillna(0)
        fig.add_trace(go.Scatter(
            x=years, y=sub.tolist(),
            name=fuel, mode='lines', stackgroup='mix',
            fillcolor=_RES_COLORS.get(fuel, '#aaa'),
            line=dict(color=_RES_COLORS.get(fuel, '#aaa'), width=0.5),
            legendgroup=f'ov_{fuel}',
            legendgrouptitle_text='Primary resources' if fi == 0 else None,
            visible=True,
            hovertemplate='%{y:.1f} TWh<extra>' + fuel + '</extra>',
        ), row=1, col=1)

    n_overview = len(fuel_order)
    detail_trace_meta = []

    # ── ROW 1 LEFT: detail traces (hidden) ──
    for fuel in fuel_order:
        base_color = _RES_COLORS.get(fuel, '#aaaaaa')
        tech_sub = tech_agg[tech_agg['FuelType'] == fuel]
        tech_totals = tech_sub.groupby('Technologies')['TWh'].sum()
        techs = (tech_totals[tech_totals > 1e-9]
                 .sort_values(ascending=False).index.tolist())
        for k, tech in enumerate(techs):
            ts = tech_sub[tech_sub['Technologies'] == tech].set_index('Year').reindex(years)['TWh'].fillna(0)
            shade = _shade(base_color, k, len(techs))
            fig.add_trace(go.Scatter(
                x=years, y=ts.tolist(),
                name=tech, mode='lines', stackgroup='detail',
                fillcolor=shade, line=dict(color=shade, width=0.3),
                legendgroup=f'detail_{fuel}_{tech}',
                legendgrouptitle_text=fuel if k == 0 else None,
                visible=False,
                hovertemplate='%{y:.1f} TWh<extra>' + tech + '</extra>',
            ), row=1, col=1)
            detail_trace_meta.append(fuel)

    n_detail = len(detail_trace_meta)

    # ── ROW 1 RIGHT: KPI lines ──
    kpi_traces = [
        ('Renewable %',          renewable_pct, '#1f77b4', 'solid'),
        ('Fossil %',             fossil_pct,    '#d62728', 'solid'),
        ('Biomass & biofuels %', bio_pct,       '#2ca02c', 'dot'),
        ('Electricity import %', elec_imp_pct,  '#9467bd', 'dot'),
    ]
    n_kpi = len(kpi_traces)
    for ki, (label, series, color, dash) in enumerate(kpi_traces):
        fig.add_trace(go.Scatter(
            x=years, y=series.tolist(), name=label,
            mode='lines+markers',
            line=dict(color=color, width=2, dash=dash), marker=dict(size=6),
            legendgroup=f'kpi_{label}',
            legendgrouptitle_text='KPIs' if ki == 0 else None,
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
                    legendgroup=f'mob_det_{cat}_{fuel}_{tech}',
                    legendgrouptitle_text=f'{cat.capitalize()} — {fuel}' if k == 0 else None,
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
        label='Resources — overview', method='update',
        args=[{'visible': _make_vis(True)},
              {'title.text': f'{case_study} — System summary'}],
    )]
    for fuel in fuel_order:
        n_techs = sum(1 for f in detail_trace_meta if f == fuel)
        energy_buttons.append(dict(
            label=f'{fuel} ({n_techs})',
            method='update',
            args=[{'visible': _make_vis(False, show_energy_fuel=fuel)},
                  {'title.text': f'{case_study} — Energy: {fuel}'}],
        ))

    # Mobility drill-down buttons
    mob_fuels_present = list(dict.fromkeys(
        fuel for typ, fuel in mob_trace_meta if typ == 'ov'
    ))
    mob_buttons = [dict(
        label='Mobility — overview', method='update',
        args=[{'visible': _make_vis(True, show_mob_fuel=None)},
              {'title.text': f'{case_study} — System summary'}],
    )]
    for fuel in mob_fuels_present:
        n_techs = sum(1 for typ, f in mob_trace_meta if typ == 'det' and f == fuel)
        mob_buttons.append(dict(
            label=f'{fuel} ({n_techs})',
            method='update',
            args=[{'visible': _make_vis(True, show_mob_fuel=fuel)},
                  {'title.text': f'{case_study} — Mobility: {fuel}'}],
        ))

    fig.update_layout(
        title=dict(text=f'{case_study} — System summary',
                   x=0.01, xanchor='left', y=0.985, yanchor='top',
                   font=dict(size=15)),
        height=860,
        hovermode='x unified',
        legend=dict(orientation='v', x=1.02, y=1, xanchor='left', yanchor='top',
                    tracegroupgap=2),
        updatemenus=[
            dict(  # energy drill-down — compact dropdown in its own band under the title
                type='dropdown', direction='down',
                x=0.0, xanchor='left', y=1.06, yanchor='bottom',
                bgcolor='#e8f0fe', bordercolor='#aaaacc',
                pad=dict(t=2, b=2),
                font=dict(size=11), buttons=energy_buttons,
            ),
            dict(  # mobility drill-down — dropdown below the figure, opens upward
                type='dropdown', direction='up',
                x=0.0, xanchor='left', y=-0.12, yanchor='top',
                bgcolor='#e8fee8', bordercolor='#aaccaa',
                pad=dict(t=2, b=2),
                font=dict(size=11), buttons=mob_buttons,
            ),
        ],
        margin=dict(t=140, b=100),
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

    fmt['sign']       = [sign_map.get((r['Year'], r['Technologies']), 1) for _, r in fmt.iterrows()]
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

_CO2_SK_NODE_COLORS = {
    'CO2_A': '#DAA520', 'CO2_C': '#1a7a4a',
    'CO2_E': '#87CEEB', 'CO2_S': '#4a4a6a', 'CO2_CS': '#8888AA',
}

# Node grouping applied after flow computation. First match wins.
_DEFAULT_TECH_GROUPS_CO2: dict = {
    # The bare 'BIOMASS' element is the biogenic-carbon accounting sink — rename it
    # so it is visually distinct from the BIOMASS *resource* node.
    'Biogenic sink': r'^BIOMASS$',
    # Resource groups (left side of Sankey)
    'BIOMASS':     r'^(BIOMASS_(FORESTRY|AGRICULTURE|WASTE)_|WET_BIOMASS$|WOOD$|WET_BIOMASS_|WOOD_)',
    # Technology groups
    'CAR':         r'^(CAR|SUV)_',
    'TRUCK':       r'^(SEMI|TRUCK|LCV)_',
    'BUS':         r'^(BUS|SCHOOLBUS|COACH)_',
    'PLANE':       r'^PLANE_',
    'Shipping':    r'^(BULK_CARRIER|OIL_TANKER|CONTAINER|FERRY)(_|$)',
    'TRAIN':       r'^(TRAIN|COMMUTER_RAIL)_',
    'NG':          r'^NG_EHP$',
    'SNG':         r'^SNG_EHP$',
    'H2':          r'^H2_EHP$',
    'COGEN':       r'COGEN',
    'BOILER':      r'BOILER',
    'DIRECT_ELEC': r'DIRECT_ELEC',
    'RENOVATION':  r'RENOVATION',
}


def _build_co2_sankey_flows(results, year_str, min_val=1.0, tech_groups=None):
    """CO₂ Sankey flow builder ported from shared/plotting.py.

    Converts Year_balance for the given year_str into a source/target/value
    DataFrame in kt CO₂/yr (Resources → Technologies → CO₂ layers).
    ELECTRICITY_EHV is excluded (out-of-territory emissions).
    """
    _CO2_LAYERS = {'CO2_A', 'CO2_C', 'CO2_E', 'CO2_S', 'CO2_CS'}

    # Build annual flow table from Year_balance
    yb_raw = results['Year_balance'].reset_index()
    yb_raw.columns = [str(c) for c in yb_raw.columns]
    yb_raw = yb_raw[
        (yb_raw['Years'] == year_str) &
        ~yb_raw['Elements'].isin(_CO2_LAYERS) &
        (yb_raw['Elements'] != 'ELECTRICITY_EHV')
    ].copy()

    layer_cols = [c for c in yb_raw.columns if c not in ('Years', 'Elements')]

    df_m = yb_raw.melt(id_vars='Elements', value_vars=layer_cols,
                       var_name='Flow', value_name='value')
    df_m.rename(columns={'Elements': 'Technologies'}, inplace=True)
    df_m['value'] = pd.to_numeric(df_m['value'], errors='coerce').fillna(0)
    df_m['Technologies'] = df_m['Technologies'].apply(
        lambda t: re.sub(r'_(SD|MD|LD|ELD)$', '', t, flags=re.IGNORECASE))

    yb = df_m.groupby(['Technologies', 'Flow'])['value'].sum().reset_index()
    yb = yb[yb['value'].abs() > 0]

    # Get resources set from the Resources result key
    res_df = results.get('Resources')
    if res_df is not None:
        res_reset = res_df.copy().reset_index()
        res_reset.columns = [str(c) for c in res_reset.columns]
        base_resources = set(res_reset.iloc[:, 1].unique().tolist())
    else:
        base_resources = set()

    # Normalize distribution-level pressure variants to their primary imported resource.
    # e.g. NG_LP/MP/HP/S → NG_EHP so that technologies consuming NG at any pressure
    # level are linked to the single imported resource node.  Grid infrastructure techs
    # that only redistribute pressure (NG_EXP_*) become net-zero and vanish.
    _PRESSURE_DIST = ('_LP', '_MP', '_HP', '_S')
    _layer_norm: dict = {}
    for r in base_resources:
        if r.endswith('_EHP'):
            base = r[:-4]  # e.g. 'NG_EHP' → 'NG'
            for suf in _PRESSURE_DIST:
                variant = base + suf
                if variant in layer_cols:
                    _layer_norm[variant] = r

    if _layer_norm:
        yb['Flow'] = yb['Flow'].replace(_layer_norm)
        yb = yb.groupby(['Technologies', 'Flow'])['value'].sum().reset_index()
        yb = yb[yb['value'].abs() > 0]

    resources = base_resources if base_resources else (set(layer_cols) & set(yb['Technologies'].unique()))

    # sign convention: value > 0 → tech produces into layer, < 0 → tech consumes from layer
    co2_df  = yb[yb['Flow'].isin(_CO2_LAYERS)]
    emit    = co2_df[co2_df['value'] > 0]
    capture = co2_df[co2_df['value'] < 0]

    tech_co2_emit_prelim = emit.groupby('Technologies')['value'].sum()

    # Expand resources: include ALL fuel layers consumed by CO₂-emitting techs that are
    # not already covered (e.g. WET_BIOMASS, WOOD, BIO_ETHANOL are intermediate layers
    # not listed in the external Resources key but directly burned for energy).
    _non_fuel_re = re.compile(
        r'^(ELECTRICITY|HEAT_|MOB_|RES_SOLAR|RES_HYDRO|RES_WIND|CO2_)',
        re.IGNORECASE)
    extra_resources = set(
        yb.loc[
            yb['Technologies'].isin(tech_co2_emit_prelim.index) &
            (yb['value'] < 0) &
            ~yb['Flow'].isin(_CO2_LAYERS) &
            ~yb['Flow'].apply(lambda x: bool(_non_fuel_re.match(x))),
            'Flow'
        ].unique()
    )
    resources = resources | extra_resources

    flows = pd.concat([
        emit   .rename(columns={'Technologies': 'source', 'Flow': 'target'})[['source', 'target', 'value']],
        capture.assign(value=lambda d: d['value'].abs())
               .rename(columns={'Flow': 'source', 'Technologies': 'target'})[['source', 'target', 'value']],
    ], ignore_index=True)

    tech_co2_emit    = emit.groupby('Technologies')['value'].sum()
    tech_co2_capture = capture.groupby('Technologies')['value'].sum().abs()

    # Electricity excluded (out-of-territory); CO2 layers excluded to avoid double-counting
    _exclude = yb['Flow'].str.contains('ELECTRICITY', case=False, na=False) | yb['Flow'].isin(_CO2_LAYERS)
    res_in  = yb[yb['Flow'].isin(resources) & (yb['value'] < 0) & ~_exclude].copy()
    res_in['value'] = res_in['value'].abs()
    res_out = yb[yb['Flow'].isin(resources) & (yb['value'] > 0) & ~_exclude].copy()

    # CO2 intensity (kt CO2/GWh) per resource, blended by volume across every producing tech
    res_co2_contrib: dict = {}  # {resource: {tech: (co2, gwh)}}

    def _set_contrib(res, tech, co2, gwh):
        res_co2_contrib.setdefault(res, {})[tech] = (co2, gwh)

    def _blended_intensity():
        out = {}
        for res, contribs in res_co2_contrib.items():
            total_gwh = sum(g for _, g in contribs.values())
            if total_gwh > 0:
                out[res] = sum(c for c, _ in contribs.values()) / total_gwh
        return out

    for tech, group in res_out.groupby('Technologies'):
        if tech not in tech_co2_capture.index:
            continue
        total_gwh = group['value'].sum()
        if total_gwh == 0:
            continue
        for _, row in group.iterrows():
            res = row['Flow']
            _set_contrib(res, tech, tech_co2_capture[tech] * (row['value'] / total_gwh), row['value'])
    res_co2_intensity = _blended_intensity()

    # Propagate biogenic CO2 intensity through conversion chains
    changed = True
    max_iter = 500
    n_iter = 0
    while changed and n_iter < max_iter:
        changed = False
        n_iter += 1
        for tech, out_group in res_out.groupby('Technologies'):
            if tech in tech_co2_capture.index:
                continue
            in_group    = res_in[res_in['Technologies'] == tech]
            biogenic_in = in_group[in_group['Flow'].isin(res_co2_intensity)]
            if biogenic_in.empty:
                continue
            co2_in   = sum(row['value'] * res_co2_intensity[row['Flow']]
                           for _, row in biogenic_in.iterrows())
            co2_pass = max(0.0, co2_in - tech_co2_emit.get(tech, 0.0))
            if co2_pass == 0:
                continue
            total_out = out_group['value'].sum()
            if total_out == 0:
                continue
            intensity = co2_pass / total_out
            for _, row in out_group.iterrows():
                res  = row['Flow']
                co2  = intensity * row['value']
                prev = res_co2_contrib.get(res, {}).get(tech)
                if prev is None or abs(prev[0] - co2) > 1e-6 or abs(prev[1] - row['value']) > 1e-6:
                    _set_contrib(res, tech, co2, row['value'])
                    changed = True
        res_co2_intensity = _blended_intensity()
    if n_iter >= max_iter:
        print(f'[WARN] CO2 Sankey {year_str}: biogenic intensity propagation hit {max_iter}-iteration limit (circular resource flow)')

    res_links = []

    # Capturing tech → resource
    for tech, group in res_out.groupby('Technologies'):
        if tech not in tech_co2_capture.index:
            continue
        total_gwh = group['value'].sum()
        if total_gwh == 0:
            continue
        for _, row in group.iterrows():
            res_links.append({
                'source': tech,
                'target': row['Flow'],
                'value' : tech_co2_capture[tech] * (row['value'] / total_gwh),
            })

    # Conversion tech → output resource (biogenic CO2 pass-through)
    tech_co2_passthrough: dict = {}
    for tech, out_group in res_out.groupby('Technologies'):
        if tech in tech_co2_capture.index:
            continue
        in_group    = res_in[res_in['Technologies'] == tech]
        biogenic_in = in_group[in_group['Flow'].isin(res_co2_intensity)]
        if biogenic_in.empty:
            continue
        co2_in   = sum(row['value'] * res_co2_intensity[row['Flow']]
                       for _, row in biogenic_in.iterrows())
        co2_pass = max(0.0, co2_in - tech_co2_emit.get(tech, 0.0))
        if co2_pass == 0:
            continue
        tech_co2_passthrough[tech] = co2_pass
        total_out = out_group['value'].sum()
        if total_out == 0:
            continue
        for _, row in out_group.iterrows():
            res_links.append({
                'source': tech,
                'target': row['Flow'],
                'value' : co2_pass * (row['value'] / total_out),
            })

    # Resource → tech
    for tech, group in res_in.groupby('Technologies'):
        if tech not in tech_co2_emit.index and tech not in tech_co2_passthrough:
            continue

        net_emit = max(0.0, tech_co2_emit.get(tech, 0.0) - tech_co2_capture.get(tech, 0.0))
        budget   = net_emit + tech_co2_passthrough.get(tech, 0.0)
        if budget == 0:
            continue

        biogenic = group[group['Flow'].isin(res_co2_intensity)]
        fossil   = group[~group['Flow'].isin(res_co2_intensity)]

        co2_biogenic   = sum(row['value'] * res_co2_intensity[row['Flow']]
                             for _, row in biogenic.iterrows())
        biogenic_scale = min(1.0, budget / co2_biogenic) if co2_biogenic > 0 else 1.0
        for _, row in biogenic.iterrows():
            val = row['value'] * res_co2_intensity[row['Flow']] * biogenic_scale
            if val > 0:
                res_links.append({'source': row['Flow'], 'target': tech, 'value': val})

        if not fossil.empty:
            co2_fossil       = max(0.0, budget - co2_biogenic * biogenic_scale)
            total_fossil_gwh = fossil['value'].sum()
            if total_fossil_gwh > 0 and co2_fossil > 0:
                scale = co2_fossil / total_fossil_gwh
                for _, row in fossil.iterrows():
                    res_links.append({'source': row['Flow'], 'target': tech,
                                      'value': row['value'] * scale})

    if res_links:
        flows = pd.concat([flows, pd.DataFrame(res_links)], ignore_index=True)

    flows = flows.groupby(['source', 'target'])['value'].sum().reset_index()

    # Uncaptured CO2_A is vented to atmosphere
    uncaptured = (flows.loc[flows['target'] == 'CO2_A', 'value'].sum()
                  - flows.loc[flows['source'] == 'CO2_A', 'value'].sum())
    if uncaptured > min_val:
        flows = pd.concat([
            flows,
            pd.DataFrame([{'source': 'CO2_A', 'target': 'CO2_E', 'value': uncaptured}]),
        ], ignore_index=True)

    if tech_groups:
        _compiled = [(re.compile(pat, re.IGNORECASE), name)
                     for name, pat in tech_groups.items()]
        def _rename(t):
            for pat, name in _compiled:
                if pat.search(t):
                    return name
            return t
        flows['source'] = flows['source'].apply(_rename)
        flows['target'] = flows['target'].apply(_rename)
        flows = flows.groupby(['source', 'target'])['value'].sum().reset_index()
        flows = flows[flows['source'] != flows['target']]

    return flows[flows['value'] >= min_val].reset_index(drop=True)


def plot_sankey_co2(results, outdir, case_study, year=None,
                    tech_groups=_DEFAULT_TECH_GROUPS_CO2, arrangement='freeform'):
    """CO₂ Sankey [kt CO₂/yr] per year — Resources → Technologies → CO₂ layers.

    If year is given (e.g. '2030'), only that year is plotted.
    Otherwise all years in YEARS_ORDER are plotted.
    """
    if results.get('Year_balance') is None:
        print('[SKIP] Year_balance not in results'); return

    res_df = results.get('Resources')
    if res_df is not None:
        res_reset = res_df.copy().reset_index()
        res_reset.columns = [str(c) for c in res_reset.columns]
        resources = set(res_reset.iloc[:, 1].unique().tolist())
    else:
        resources = set()

    years_to_plot = [year] if year is not None else YEARS_ORDER

    for yr in years_to_plot:
        year_str = f'YEAR_{yr}'
        try:
            df = _build_co2_sankey_flows(results, year_str, tech_groups=tech_groups)
        except Exception as e:
            print(f'[SKIP] CO2 Sankey {yr}: {e}'); continue
        if df.empty:
            continue

        all_nodes = list(dict.fromkeys(list(df['source']) + list(df['target'])))
        node_idx  = {n: i for i, n in enumerate(all_nodes)}

        def _node_color(n):
            if n in _CO2_SK_NODE_COLORS: return _CO2_SK_NODE_COLORS[n]
            if n in resources:           return '#F0D9B5'
            return '#D5D8DC'

        fig = go.Figure(data=[go.Sankey(
            valueformat='.0f', valuesuffix=' kt CO₂', arrangement=arrangement,
            node=dict(
                pad=10, thickness=12,
                line=dict(color='black', width=0.5),
                label=all_nodes,
                color=[_node_color(n) for n in all_nodes],
            ),
            link=dict(
                source=[node_idx[s] for s in df['source']],
                target=[node_idx[t] for t in df['target']],
                value=df['value'].tolist(),
            ),
        )])
        fig.update_layout(
            title_text=f'{case_study} — CO₂ flows {yr}  [kt CO₂/yr]',
            font_size=10, height=700,
            template='plotly', font_color='black',
        )
        _save(fig, outdir, f'17_CO2_Sankey_{yr}.html')


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


def _try_plot(fn, *args, **kwargs):
    try:
        fn(*args, **kwargs)
    except Exception as e:
        sys.stdout.write(f'\n[ERROR] {fn.__name__} skipped: {e}\n')
        sys.stdout.flush()


def _try_plot_timeout(fn, *args, timeout=30, **kwargs):
    import concurrent.futures
    ex = concurrent.futures.ThreadPoolExecutor(max_workers=1)
    future = ex.submit(fn, *args, **kwargs)
    try:
        future.result(timeout=timeout)
    except concurrent.futures.TimeoutError:
        sys.stdout.write(f'\n[TIMEOUT] {fn.__name__} exceeded {timeout}s, skipping\n')
        sys.stdout.flush()
    except Exception as e:
        sys.stdout.write(f'\n[ERROR] {fn.__name__} skipped: {e}\n')
        sys.stdout.flush()
    finally:
        ex.shutdown(wait=False)


def run(case_study_or_results, case_study=None, outdir=None):
    global _chart_count
    _chart_count = 0

    if isinstance(case_study_or_results, dict):
        results  = case_study_or_results
        cs       = case_study or 'unnamed'
        _outdir  = outdir or os.path.join(OUT_DIR, cs, 'graphs')
    else:
        cs       = case_study_or_results
        results  = load_results(cs)
        _outdir  = outdir or os.path.join(OUT_DIR, cs, 'graphs')

    _base_dir = os.path.dirname(_outdir)
    os.makedirs(_outdir, exist_ok=True)
    # remove stale html files before regenerating
    for f in os.listdir(_outdir):
        if f.endswith('.html'):
            os.remove(os.path.join(_outdir, f))
    print(f"Plotting to: {_outdir}")

    _try_plot(plot_initial_config, results, _outdir, cs)

    if PLOTS.get('summary'):                _try_plot(plot_summary_dashboard, results, _base_dir, cs)
    if PLOTS.get('gwp'):                    _try_plot(plot_gwp, results, _outdir, cs)
    if PLOTS.get('transition_cost'):        _try_plot(plot_transition_cost, results, _outdir, cs)
    if PLOTS.get('capex_breakdown'):        _try_plot(plot_capex_breakdown, results, _outdir, cs)
    if PLOTS.get('capex_crf_breakdown'):    _try_plot(plot_capex_crf_breakdown, results, _outdir, cs)
    if PLOTS.get('capex_crf_active_phase'): _try_plot(plot_capex_crf_active_phase, results, _outdir, cs)
    if PLOTS.get('capex_crf_ampl'):         _try_plot(plot_capex_crf_ampl, results, _outdir, cs)
    if PLOTS.get('capex_no_actu'):          _try_plot(plot_capex_no_actu, results, _outdir, cs)
    if PLOTS.get('capex_no_actu_breakdown'): _try_plot(plot_capex_no_actu_breakdown, results, _outdir, cs)
    if PLOTS.get('capex_summary'):          _try_plot(plot_capex_summary, results, _outdir, cs)
    if PLOTS.get('opex_breakdown'):         _try_plot(plot_opex_breakdown, results, _outdir, cs)
    if PLOTS.get('opex_no_actu_breakdown'): _try_plot(plot_opex_no_actu_breakdown, results, _outdir, cs)
    if PLOTS.get('total_cost'):             _try_plot(plot_total_cost_breakdown, results, _outdir, cs)
    if PLOTS.get('resources'):              _try_plot(plot_resources, results, _outdir, cs)
    if PLOTS.get('annual_prod'):            _try_plot(plot_annual_prod, results, _outdir, cs)
    if PLOTS.get('monthly_prod'):           _try_plot(plot_monthly_prod, results, _outdir, cs)
    if PLOTS.get('monthly_resources'):      _try_plot(plot_monthly_resources, results, _outdir, cs)
    if PLOTS.get('monthly_co2_storage'):    _try_plot(plot_monthly_co2_storage, results, _outdir, cs)
    if PLOTS.get('load_factor'):            _try_plot(plot_load_factor_heatmap, results, _outdir, cs)
    if PLOTS.get('mobility_pies'):          _try_plot(plot_mobility_pies, results, _outdir, cs)
    if PLOTS.get('f_new'):                  _try_plot(plot_fnew_by_category, results, _outdir, cs, col='F_new',   prefix='2')
    if PLOTS.get('f_old'):                  _try_plot(plot_fnew_by_category, results, _outdir, cs, col='F_old',   prefix='3')
    if PLOTS.get('f_decom'):                _try_plot(plot_fnew_by_category, results, _outdir, cs, col='F_decom', prefix='3b')
    if PLOTS.get('f_mult'):                 _try_plot(plot_f_mult_by_category, results, _outdir, cs)
    if PLOTS.get('number_of_units'):        _try_plot(plot_number_of_units, results, _outdir, cs)
    if PLOTS.get('electricity_layer'):      _try_plot(plot_electricity_layer, results, _outdir, cs)
    if PLOTS.get('heat_layer'):             _try_plot(plot_heat_layer, results, _outdir, cs)
    if PLOTS.get('h2_layer'):               _try_plot(plot_h2_layer, results, _outdir, cs)
    if PLOTS.get('ng_layer'):               _try_plot(plot_ng_layer, results, _outdir, cs)
    if PLOTS.get('mobility_layer'):         _try_plot(plot_mobility_layer, results, _outdir, cs)
    if PLOTS.get('sankey'):                 _try_plot(plot_sankey, results, _outdir, cs)
    if PLOTS.get('gwp_breakdown'):          _try_plot(plot_gwp_breakdown, results, _outdir, cs)
    if PLOTS.get('storage_levels'):         _try_plot(plot_storage_levels, results, _outdir, cs)
    if PLOTS.get('monthly_h2'):             _try_plot(plot_monthly_h2_layer, results, _outdir, cs)
    if PLOTS.get('sankey_co2'):
        for _yr in YEARS_ORDER:
            _try_plot_timeout(plot_sankey_co2, results, _outdir, cs, year=_yr)
    if PLOTS.get('monthly_electricity'):    _try_plot(plot_monthly_electricity_layer, results, _outdir, cs)

    create_dashboard(_outdir, cs)
    sys.stdout.write(f'\nDone — {_chart_count} charts saved to {_outdir}\n')
    sys.stdout.flush()


if __name__ == '__main__':
    case = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_CASE
    run(case)
