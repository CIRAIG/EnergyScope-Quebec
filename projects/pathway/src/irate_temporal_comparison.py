"""
irate_temporal_comparison.py – Compare EnergyScope-Quebec results across
time-varying discount-rate profiles.

Companion to run_irate_temporal.py.  Loads the four scenario pkl files and
produces figures saved as PNG + PDF in:
    projects/pathway/out/iRate_temporal_comparison/

Figures
-------
fig0_rate_profiles       – i_rate and discount factor per phase × scenario
fig1_summary             – Transition cost / GHG / renewable share
fig2_capex_frontloading  – CAPEX per phase (when is capital deployed?)
fig3_tech_mix_snapshot   – Installed capacity in 2035 and 2050
fig4_investment_timing   – F_new per technology across scenarios (key techs)
fig5_cost_decomposition  – CAPEX vs OPEX breakdown per phase × scenario
"""

import pickle
import warnings
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import matplotlib.patches as mpatches
from pathlib import Path

warnings.filterwarnings("ignore")

# ─── Configuration ────────────────────────────────────────────────────────────
OUT_DIR = Path(r"C:\Users\matti\Desktop\EnergyScope-Quebec\projects\pathway\out")
FIG_DIR = OUT_DIR / "iRate_temporal_comparison"
FIG_DIR.mkdir(exist_ok=True)

SCENARIOS = [
    "iRate_Constant",
    "iRate_Decreasing",
    "iRate_Increasing",
    "iRate_PolicyStep",
]
LABELS = {
    "iRate_Constant":   "Constant 4%",
    "iRate_Decreasing": "Decreasing\n8%→2%",
    "iRate_Increasing": "Increasing\n2%→8%",
    "iRate_PolicyStep": "Policy Step\n8%→2% (2030)",
}
COLORS = {
    "iRate_Constant":   "#2196F3",   # bleu flash
    "iRate_Decreasing": "#00C853",   # vert flash
    "iRate_Increasing": "#F44336",   # rouge flash
    "iRate_PolicyStep": "#FF6D00",   # orange flash
}

YEARS  = [2020, 2025, 2030, 2035, 2040, 2045, 2050]
PHASES = ["2015_2020", "2020_2025", "2025_2030",
          "2030_2035", "2035_2040", "2040_2045", "2045_2050"]
PHASE_MID = {
    "2015_2020": 2017, "2020_2025": 2022, "2025_2030": 2027,
    "2030_2035": 2032, "2035_2040": 2037, "2040_2045": 2042, "2045_2050": 2047,
}

# i_rate profiles (must match run_irate_temporal.py)
RATE_PROFILES = {
    "iRate_Constant":   {p: 0.04 for p in PHASES},
    "iRate_Decreasing": {
        "2015_2020": 0.08, "2020_2025": 0.07, "2025_2030": 0.06,
        "2030_2035": 0.05, "2035_2040": 0.04, "2040_2045": 0.03, "2045_2050": 0.02,
    },
    "iRate_Increasing": {
        "2015_2020": 0.02, "2020_2025": 0.03, "2025_2030": 0.04,
        "2030_2035": 0.05, "2035_2040": 0.06, "2040_2045": 0.07, "2045_2050": 0.08,
    },
    "iRate_PolicyStep": {
        "2015_2020": 0.08, "2020_2025": 0.08, "2025_2030": 0.08,
        "2030_2035": 0.02, "2035_2040": 0.02, "2040_2045": 0.02, "2045_2050": 0.02,
    },
}

RENEW_SET = frozenset({
    "RES_WIND_ONSHORE", "RES_WIND_OFFSHORE", "RES_TIDAL", "RES_SOLAR",
    "RES_HYDRO", "RES_GEO", "WOOD", "WET_BIOMASS",
    "BIOMASS_FORESTRY_UNEXPLOITED", "BIOMASS_FORESTRY_RESIDUAL",
    "BIOMASS_FORESTRY_LEFTOVER1", "BIOMASS_FORESTRY_LEFTOVER2",
    "BIOMASS_AGRICULTURE_DEJECTION", "BIOMASS_AGRICULTURE_RESIDUAL",
    "BIOMASS_WASTE_ORGANIC", "BIOMASS_WASTE_PAPER",
    "BIOMASS_WASTE_PAPER_FABRIC", "BIOMASS_WASTE_BUILDING",
    "BIOMASS_WASTE_MUNICIPAL",
})

# Unit label per technology category (default: "GW" for energy/heat)
TECH_UNIT = {
    # Private mobility — Mpkm/h
    "CAR_EV":       "Mpkm/h",
    "CAR_GASOLINE": "Mpkm/h",
    "CAR_HEV":      "Mpkm/h",
    "SUV_GASOLINE": "Mpkm/h",
    # Public transport — Mpkm/h
    "BUS_DIESEL":         "Mpkm/h",
    "BUS_CNG":            "Mpkm/h",
    "COACH_DIESEL":       "Mpkm/h",
    "COACH_CNG":          "Mpkm/h",
    "COACH_GASOLINE":     "Mpkm/h",
    "SCHOOLBUS_DIESEL":   "Mpkm/h",
    "SCHOOLBUS_CNG":      "Mpkm/h",
    "SCHOOLBUS_GASOLINE": "Mpkm/h",
    "TRAIN_ELEC":         "Mpkm/h",
    "TRAIN_DIESEL":       "Mpkm/h",
    "PLANE_SH":           "Mpkm/h",
    "PLANE_SH_BIO":       "Mpkm/h",
    # Freight road — Mtkm/h
    "SEMI_LH_DIESEL":    "Mtkm/h",
    "SEMI_LH_FC_H2":     "Mtkm/h",
    "SEMI_LH_CNG":       "Mtkm/h",
    "SEMI_SH_DIESEL":    "Mtkm/h",
    "SEMI_SH_HY_DIESEL": "Mtkm/h",
    "LCV_DIESEL":        "Mtkm/h",
    "LCV_GASOLINE":      "Mtkm/h",
    "LCV_FC_H2":         "Mtkm/h",
    "TRUCK_SH_DIESEL":   "Mtkm/h",
    "TRUCK_SH_GASOLINE": "Mtkm/h",
    # Freight rail / maritime — Mtkm/h
    "TRAIN_FREIGHT_ELEC":   "Mtkm/h",
    "TRAIN_FREIGHT_DIESEL": "Mtkm/h",
    "BULK_CARRIER":         "Mtkm/h",
    "BULK_CARRIER_MEOH":    "Mtkm/h",
    "CONTAINER":            "Mtkm/h",
    "OIL_TANKER":           "Mtkm/h",
    "OIL_TANKER_MEOH":      "Mtkm/h",
}

# Key technologies for Fig 4 (investment timing detail)
KEY_TECHS = [
    "WIND_ONSHORE", "CAR_EV", "CAR_GASOLINE", "CAR_HEV",
    "NEW_HYDRO_DAM",
    "IND_BOILER_GAS", "IND_BOILER_WOOD",
    "DEC_HP_ELEC", "DEC_BOILER_GAS",
    "TRAIN_FREIGHT_ELEC", "TRAIN_FREIGHT_DIESEL",
    "SEMI_LH_FC_H2", "SEMI_LH_DIESEL",
]

plt.rcParams.update({
    "font.family":     "sans-serif",
    "font.size":       10,
    "axes.spines.top":  False,
    "axes.spines.right": False,
    "axes.titlesize":  11,
    "axes.labelsize":  10,
    "figure.dpi":      150,
})

# ─── Helpers ──────────────────────────────────────────────────────────────────

def _save(fig, name: str):
    for ext in ("png", "pdf"):
        fig.savefig(FIG_DIR / f"{name}.{ext}", bbox_inches="tight", dpi=150)
    print(f"    Saved {FIG_DIR / name}.png / .pdf")


def _numeric_sum(df) -> float:
    if df is None:
        return np.nan
    return float(pd.to_numeric(df.values.flatten(), errors="coerce").sum())


# ─── Data loading ─────────────────────────────────────────────────────────────

def load_all() -> dict:
    data = {}
    for sc in SCENARIOS:
        pkl = OUT_DIR / sc / "_Results.pkl"
        with open(pkl, "rb") as f:
            data[sc] = pickle.load(f)
        print(f"  Loaded {sc}")
    return data


# ─── Extractors ───────────────────────────────────────────────────────────────

def capex_opex(res) -> tuple:
    """Return (capex_B$, opex_B$) total over the transition."""
    inv = _numeric_sum(res.get("C_inv_phase"))
    tc  = _numeric_sum(res.get("Transition_cost"))
    if np.isnan(tc):
        tc = _numeric_sum(res.get("TotalCost"))
    opex = tc - inv if not np.isnan(tc) and not np.isnan(inv) else np.nan
    return inv / 1e3, max(opex, 0.0) / 1e3   # M$CAD → B$CAD


def renew_share_by_year(res) -> dict:
    df = res.get("Resources")
    if df is None:
        return {}
    df = df.reset_index().copy()
    df.columns = [str(c) for c in df.columns]
    ycol, rcol, vcol = df.columns[0], df.columns[1], df.columns[2]
    df[vcol] = pd.to_numeric(df[vcol], errors="coerce").fillna(0).clip(lower=0)
    df["yr"] = df[ycol].str.replace("YEAR_", "", regex=False).astype(int)
    out = {}
    for yr, g in df.groupby("yr"):
        total = g[vcol].sum()
        renew = g.loc[g[rcol].isin(RENEW_SET), vcol].sum()
        out[yr] = renew / total * 100 if total > 0 else 0.0
    return out


def gwp_by_year(res) -> dict:
    df = res.get("TotalGwp")
    if df is None:
        return {}
    df = df.reset_index().copy()
    df.columns = [str(c) for c in df.columns]
    ycol   = df.columns[0]
    gwpcol = "TotalGWP" if "TotalGWP" in df.columns else df.columns[1]
    df["yr"]   = df[ycol].str.replace("YEAR_", "", regex=False).astype(int)
    df[gwpcol] = pd.to_numeric(df[gwpcol], errors="coerce").fillna(0)
    return dict(zip(df["yr"], df[gwpcol] / 1e3))   # kt → Mt


def capex_by_phase(res) -> dict:
    """Return {phase_str: C_inv_phase_M$} — NPV values as stored in the model."""
    df = res.get("C_inv_phase")
    if df is None:
        return {}
    df = df.reset_index().copy()
    df.columns = [str(c) for c in df.columns]
    phase_col, val_col = df.columns[0], df.columns[1]
    df[val_col] = pd.to_numeric(df[val_col], errors="coerce").fillna(0)
    return dict(zip(df[phase_col], df[val_col]))


def opex_by_phase(res) -> dict:
    """Return {phase_str: C_op_phase_M$} summed over all resources + techs."""
    out = {}
    for key in ("C_op_phase_tech", "C_op_phase_res"):
        df = res.get(key)
        if df is None:
            continue
        df = df.reset_index().copy()
        df.columns = [str(c) for c in df.columns]
        phase_col, _, val_col = df.columns[0], df.columns[1], df.columns[2]
        df[val_col] = pd.to_numeric(df[val_col], errors="coerce").fillna(0)
        for phase, g in df.groupby(phase_col):
            out[phase] = out.get(phase, 0.0) + g[val_col].sum()
    return out


def fnew_df(res) -> pd.DataFrame:
    """Return DataFrame [Phase, Technologies, F_new]."""
    df = res.get("F_new")
    if df is None:
        return pd.DataFrame(columns=["Phase", "Technologies", "F_new"])
    df = df.reset_index().copy()
    df.columns = ["Phase", "Technologies", "F_new"]
    df["F_new"] = pd.to_numeric(df["F_new"], errors="coerce").fillna(0)
    return df


def fmult_df(res) -> pd.DataFrame:
    """Return DataFrame [Year, Technologies, F_Mult]."""
    df = res.get("F_Mult")
    if df is None:
        return pd.DataFrame(columns=["Year", "Technologies", "F_Mult"])
    df = df.reset_index().copy()
    df.columns = ["Years", "Technologies", "F_Mult"]
    df["F_Mult"] = pd.to_numeric(df["F_Mult"], errors="coerce").fillna(0)
    df["Year"] = df["Years"].str.replace("YEAR_", "", regex=False).astype(int)
    return df[["Year", "Technologies", "F_Mult"]]


# ─── Annualised factor helpers ─────────────────────────────────────────────────

def _annualised_factors(rate_profile: dict) -> dict:
    """Compute compound-discounted annualised_factor for each phase."""
    factors    = {}
    cumulative = 1.0
    prev_diff  = 0.0
    phase_diff = {
        "2015_2020": 0.0, "2020_2025": 5.0, "2025_2030": 10.0,
        "2030_2035": 15.0, "2035_2040": 20.0, "2040_2045": 25.0, "2045_2050": 30.0,
    }
    for p in PHASES:
        d = phase_diff[p]
        years_in = d - prev_diff
        r = rate_profile.get(p, 0.04)
        cumulative *= (1.0 + r) ** years_in
        factors[p] = 1.0 / cumulative
        prev_diff = d
    return factors


# ─── Figure 0 – Rate profiles & discount factors ──────────────────────────────

def fig_rate_profiles():
    """
    Panel (a): i_rate per phase for each scenario (step plot).
    Panel (b): Resulting annualised_factor (compound discount factor to 2015).
    """
    fig, axes = plt.subplots(1, 2, figsize=(13, 5))
    fig.suptitle(
        "Discount-rate profiles: temporal variation scenarios",
        fontsize=13, fontweight="bold", y=1.02,
    )

    midpoints = [PHASE_MID[p] for p in PHASES]

    # (a) Rate per phase
    ax = axes[0]
    for sc in SCENARIOS:
        profile = RATE_PROFILES[sc]
        rates   = [profile[p] * 100 for p in PHASES]
        ax.step(midpoints, rates, where="mid",
                color=COLORS[sc], lw=2.5, label=LABELS[sc].replace("\n", " "))
        ax.plot(midpoints, rates, "o", color=COLORS[sc], ms=5)
    ax.set_xticks(midpoints)
    ax.set_xticklabels([f"{p[:4]}\n–{p[5:]}" for p in PHASES], fontsize=8)
    ax.yaxis.set_major_formatter(mticker.FuncFormatter(lambda v, _: f"{v:.0f}%"))
    ax.set(xlabel="Phase", ylabel="Discount rate (%)",
           title="(a) i_rate per 5-year phase", ylim=(0, 10))
    ax.legend(fontsize=8, loc="upper right")
    ax.grid(ls="--", alpha=0.3)

    # (b) Annualised factor (discount to 2015)
    ax = axes[1]
    for sc in SCENARIOS:
        factors = _annualised_factors(RATE_PROFILES[sc])
        vals    = [factors[p] for p in PHASES]
        ax.plot(midpoints, vals, "-o", color=COLORS[sc], lw=2.5, ms=5,
                label=LABELS[sc].replace("\n", " "))
    ax.set_xticks(midpoints)
    ax.set_xticklabels([f"{p[:4]}\n–{p[5:]}" for p in PHASES], fontsize=8)
    ax.set(xlabel="Phase",
           ylabel="Annualised factor  [1 / (1+r)^Δ]",
           title="(b) Compound discount factor to 2015")
    ax.yaxis.set_major_formatter(mticker.FuncFormatter(lambda v, _: f"{v:.2f}"))
    ax.legend(fontsize=8, loc="upper right")
    ax.grid(ls="--", alpha=0.3)

    fig.tight_layout()
    _save(fig, "fig0_rate_profiles")
    plt.close(fig)


# ─── Figure 1 – Key summary metrics ──────────────────────────────────────────

def fig_summary(data: dict):
    fig, axes = plt.subplots(1, 3, figsize=(17, 5))
    fig.suptitle(
        "Impact of time-varying discount rate on the Quebec energy transition",
        fontsize=13, fontweight="bold", y=1.02,
    )
    x         = np.arange(len(SCENARIOS))
    sc_labels = [LABELS[sc] for sc in SCENARIOS]
    cols      = [COLORS[sc] for sc in SCENARIOS]

    # (a) Transition cost
    ax = axes[0]
    caps, ops = [], []
    for sc in SCENARIOS:
        c, o = capex_opex(data[sc])
        caps.append(c)
        ops.append(o)
    ax.bar(x, caps, 0.6, label="CAPEX", color="#EF553B", zorder=3)
    ax.bar(x, ops,  0.6, bottom=caps, label="OPEX", color="#636EFA", zorder=3)
    totals = [c + o for c, o in zip(caps, ops)]
    ax.plot(x, totals, "ko-", ms=5, lw=1.8, label="Total", zorder=4)
    for xi, tot in enumerate(totals):
        ax.text(xi, tot + tot * 0.01, f"{tot:.0f}", ha="center",
                va="bottom", fontsize=8, fontweight="bold")
    ax.set_xticks(x)
    ax.set_xticklabels(sc_labels, fontsize=8)
    ax.set(xlabel="", ylabel="B$CAD (NPV to 2015)", title="(a) Total transition cost")
    ax.legend(fontsize=8)
    ax.grid(axis="y", ls="--", alpha=0.4)

    # (b) Renewable share in 2050
    ax = axes[1]
    renew_vals_2050 = []
    for sc in SCENARIOS:
        rs = renew_share_by_year(data[sc])
        renew_vals_2050.append(rs.get(2050, np.nan))
    ax.bar(x, renew_vals_2050, 0.6, color=cols, zorder=3)
    for xi, v in enumerate(renew_vals_2050):
        ax.text(xi, v + 0.5, f"{v:.1f}%", ha="center", va="bottom",
                fontsize=8, fontweight="bold")
    ax.set_xticks(x)
    ax.set_xticklabels(sc_labels, fontsize=8)
    ax.yaxis.set_major_formatter(mticker.FuncFormatter(lambda v, _: f"{v:.0f}%"))
    ax.set(xlabel="", ylabel="%", title="(b) Renewable energy share — 2050",
           ylim=(0, 105))
    ax.grid(axis="y", ls="--", alpha=0.4)

    # (c) GHG emissions per modelled year
    ax = axes[2]
    for sc in SCENARIOS:
        g    = gwp_by_year(data[sc])
        yrs  = sorted(y for y in g if y in YEARS)
        vals = [g[y] for y in yrs]
        ax.plot(yrs, vals, "-o", ms=5, lw=2.5,
                color=COLORS[sc], label=LABELS[sc].replace("\n", " "))
    ax.set(xlabel="Year", ylabel="MtCO₂eq / year",
           title="(c) GHG emissions by modelled year")
    ax.set_xticks(YEARS)
    ax.set_xticklabels([str(y) for y in YEARS], rotation=30, ha="right")
    ax.axhline(0, color="black", lw=0.8, ls="--", alpha=0.5)
    ax.legend(fontsize=8)
    ax.grid(ls="--", alpha=0.3)

    fig.tight_layout()
    _save(fig, "fig1_summary")
    plt.close(fig)


# ─── Figure 2 – CAPEX front-loading per phase ─────────────────────────────────

def fig_capex_frontloading(data: dict):
    """
    Stacked horizontal bar: each scenario = one row, segments = phases.
    Shows how capital spending is distributed over time.
    Also includes a line-plot panel showing cumulative CAPEX as % of total.
    """
    fig, axes = plt.subplots(1, 2, figsize=(15, 5))
    fig.suptitle(
        "Investment front-loading: when is capital deployed?",
        fontsize=13, fontweight="bold", y=1.02,
    )

    # Panel (a): Stacked bar per phase
    ax = axes[0]
    phase_cmap = plt.cm.Blues(np.linspace(0.25, 0.9, len(PHASES)))

    y_pos = np.arange(len(SCENARIOS))
    lefts = np.zeros(len(SCENARIOS))
    for k, ph in enumerate(PHASES):
        if ph == "2015_2020":
            continue   # baseline phase, minimal/no investment
        vals = np.array([
            capex_by_phase(data[sc]).get(ph, 0.0) / 1e3   # M$ → B$
            for sc in SCENARIOS
        ])
        ax.barh(y_pos, vals, left=lefts, color=phase_cmap[k],
                label=f"{ph[:4]}–{ph[5:]}", edgecolor="white", linewidth=0.5)
        lefts += vals

    ax.set_yticks(y_pos)
    ax.set_yticklabels([LABELS[sc] for sc in SCENARIOS], fontsize=9)
    ax.set(xlabel="B$CAD (NPV to 2015)", title="(a) CAPEX per phase")
    ax.legend(title="Phase", fontsize=7, ncol=2, loc="lower left")
    ax.grid(axis="x", ls="--", alpha=0.3)
    for pos, left in enumerate(lefts):
        ax.text(left + left * 0.01, pos, f"{left:.0f}", va="center",
                fontsize=8, fontweight="bold")

    # Panel (b): Cumulative CAPEX share (front-loading curve)
    ax = axes[1]
    active_phases = [p for p in PHASES if p != "2015_2020"]
    phase_mids    = [PHASE_MID[p] for p in active_phases]

    for sc in SCENARIOS:
        cbp = capex_by_phase(data[sc])
        vals    = np.array([cbp.get(p, 0.0) for p in active_phases])
        total   = vals.sum()
        if total <= 0:
            continue
        cumul = np.cumsum(vals) / total * 100
        ax.plot(phase_mids, cumul, "-o", color=COLORS[sc], lw=2.5, ms=6,
                label=LABELS[sc].replace("\n", " "))

    ax.axhline(50, ls=":", color="gray", lw=1.2, alpha=0.7, label="50% mark")
    ax.set_xticks(phase_mids)
    ax.set_xticklabels(
        [f"{p[:4]}–{p[5:]}" for p in active_phases], rotation=30, ha="right", fontsize=8
    )
    ax.yaxis.set_major_formatter(mticker.FuncFormatter(lambda v, _: f"{v:.0f}%"))
    ax.set(xlabel="Phase end", ylabel="Cumulative CAPEX (%)",
           title="(b) Front-loading curve (% of total CAPEX)",
           ylim=(0, 105))
    ax.legend(fontsize=8)
    ax.grid(ls="--", alpha=0.3)

    fig.tight_layout()
    _save(fig, "fig2_capex_frontloading")
    plt.close(fig)


# ─── Figure 3 – Technology snapshot (installed capacity in 2035 & 2050) ────────

def fig_tech_mix_snapshot(data: dict):
    """
    Side-by-side bar charts of F_Mult for KEY_TECHS in 2035 and 2050.
    Groups bars by technology, coloured by scenario.
    """
    snapshot_years = [2035, 2050]
    n_sc = len(SCENARIOS)
    group_width = 0.8
    bar_w = group_width / n_sc

    fig, axes = plt.subplots(1, 2, figsize=(16, 6))
    fig.suptitle(
        "Installed capacity snapshot — key technologies",
        fontsize=13, fontweight="bold", y=1.02,
    )

    # Collect active techs (any non-zero value)
    frames = {sc: fmult_df(data[sc]) for sc in SCENARIOS}

    for ax_idx, yr in enumerate(snapshot_years):
        ax = axes[ax_idx]

        active_techs = [
            t for t in KEY_TECHS
            if any(
                frames[sc].loc[
                    (frames[sc]["Technologies"] == t) & (frames[sc]["Year"] == yr),
                    "F_Mult"
                ].sum() > 1e-3
                for sc in SCENARIOS
            )
        ]
        if not active_techs:
            ax.set_visible(False)
            continue

        x = np.arange(len(active_techs))
        for k, sc in enumerate(SCENARIOS):
            offsets = x - group_width / 2 + (k + 0.5) * bar_w
            fm = frames[sc]
            vals = [
                fm.loc[
                    (fm["Technologies"] == t) & (fm["Year"] == yr),
                    "F_Mult"
                ].sum()
                for t in active_techs
            ]
            ax.bar(offsets, vals, bar_w * 0.9, color=COLORS[sc],
                   label=LABELS[sc].replace("\n", " "), zorder=3)

        ax.set_xticks(x)
        ax.set_xticklabels(
            [t.replace("_", "\n") for t in active_techs],
            fontsize=7, ha="center"
        )
        ax.set(ylabel="GW (or fleet equiv.)", title=f"({'ab'[ax_idx]}) Year {yr}",
               ylim=(0, None))
        ax.grid(axis="y", ls="--", alpha=0.3)
        if ax_idx == 1:
            ax.legend(fontsize=7, loc="upper right")

    fig.tight_layout()
    _save(fig, "fig3_tech_mix_snapshot")
    plt.close(fig)


# ─── Figure 4 – F_new per technology per phase (investment timing detail) ────

def fig_investment_timing(data: dict):
    """
    Grid of bar-cluster charts: one subplot per KEY tech.
    X-axis = phase, bars grouped by scenario.
    Shows WHEN (not how much total) each tech is built.
    """
    frames = {sc: fnew_df(data[sc]) for sc in SCENARIOS}
    active_phases = [p for p in PHASES if p != "2015_2020"]
    n_sc     = len(SCENARIOS)
    bar_w    = 0.8 / n_sc
    x        = np.arange(len(active_phases))

    active_techs = [
        t for t in KEY_TECHS
        if any(
            frames[sc].loc[frames[sc]["Technologies"] == t, "F_new"].sum() > 1e-3
            for sc in SCENARIOS
        )
    ]
    if not active_techs:
        print("  No active techs for fig4_investment_timing")
        return

    ncols = 4
    nrows = (len(active_techs) + ncols - 1) // ncols
    fig, axes = plt.subplots(nrows, ncols, figsize=(4 * ncols, 3.2 * nrows), squeeze=False)
    fig.suptitle(
        "New investments per phase (F_new) — key technologies",
        fontsize=12, fontweight="bold", y=1.01,
    )

    for idx, tech in enumerate(active_techs):
        r, c = divmod(idx, ncols)
        ax = axes[r][c]

        for k, sc in enumerate(SCENARIOS):
            fm = frames[sc]
            vals = [
                fm.loc[
                    (fm["Technologies"] == tech) & (fm["Phase"] == ph),
                    "F_new"
                ].sum()
                for ph in active_phases
            ]
            offsets = x - 0.4 + (k + 0.5) * bar_w
            ax.bar(offsets, vals, bar_w * 0.9, color=COLORS[sc],
                   label=LABELS[sc].replace("\n", " "), zorder=3)

        ax.set_title(tech.replace("_", " "), fontsize=8, pad=3)
        ax.set_xticks(x)
        ax.set_xticklabels(
            [f"{p[:4]}\n–{p[5:]}" for p in active_phases], fontsize=6.5
        )
        ax.set_ylabel(TECH_UNIT.get(tech, "GW"), fontsize=7)
        ax.tick_params(labelsize=7)
        ax.set_ylim(bottom=0)
        ax.grid(axis="y", ls="--", alpha=0.3)

    # Hide unused subplots
    for idx in range(len(active_techs), nrows * ncols):
        r, c = divmod(idx, ncols)
        axes[r][c].set_visible(False)

    # Shared legend
    handles = [
        mpatches.Patch(color=COLORS[sc], label=LABELS[sc].replace("\n", " "))
        for sc in SCENARIOS
    ]
    fig.legend(handles=handles, loc="lower center", ncol=n_sc,
               fontsize=8, bbox_to_anchor=(0.5, -0.02), framealpha=0.9)

    fig.tight_layout()
    _save(fig, "fig4_investment_timing")
    plt.close(fig)


# ─── Figure 5 – Cost decomposition per phase (CAPEX + OPEX) ──────────────────

def fig_cost_decomposition(data: dict):
    """
    For each scenario, stacked-bar showing CAPEX + OPEX per phase (excl. 2015_2020).
    Panels: one per scenario, so comparisons across phases are clear.
    """
    active_phases = [p for p in PHASES if p != "2015_2020"]
    phase_labels  = [f"{p[:4]}–{p[5:]}" for p in active_phases]
    x = np.arange(len(active_phases))

    fig, axes = plt.subplots(1, len(SCENARIOS), figsize=(5 * len(SCENARIOS), 5), sharey=True)
    fig.suptitle(
        "Cost decomposition per phase: CAPEX vs. OPEX",
        fontsize=13, fontweight="bold", y=1.02,
    )

    for ax_idx, sc in enumerate(SCENARIOS):
        ax = axes[ax_idx]
        cbp = capex_by_phase(data[sc])
        obp = opex_by_phase(data[sc])
        caps = np.array([cbp.get(p, 0.0) / 1e3 for p in active_phases])   # B$
        ops  = np.array([obp.get(p, 0.0) / 1e3 for p in active_phases])

        ax.bar(x, caps, 0.65, color="#EF553B", label="CAPEX", zorder=3)
        ax.bar(x, ops,  0.65, bottom=caps, color="#636EFA", label="OPEX",  zorder=3)
        totals = caps + ops
        ax.plot(x, totals, "ko-", ms=4, lw=1.5, zorder=4)

        ax.set_xticks(x)
        ax.set_xticklabels(phase_labels, rotation=35, ha="right", fontsize=8)
        ax.set_title(LABELS[sc].replace("\n", " "), fontsize=10, fontweight="bold")
        ax.grid(axis="y", ls="--", alpha=0.3)
        if ax_idx == 0:
            ax.set_ylabel("B$CAD (NPV to 2015)")
            ax.legend(fontsize=8)

    fig.tight_layout()
    _save(fig, "fig5_cost_decomposition")
    plt.close(fig)


# ─── Main ─────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("Generating rate-profile figures (no data needed)...")
    fig_rate_profiles()

    print("\nLoading scenario results...")
    data = load_all()

    print("\nFig 1 – Summary metrics...")
    fig_summary(data)

    print("\nFig 2 – CAPEX front-loading...")
    fig_capex_frontloading(data)

    print("\nFig 3 – Technology mix snapshots...")
    fig_tech_mix_snapshot(data)

    print("\nFig 4 – Investment timing detail...")
    fig_investment_timing(data)

    print("\nFig 5 – Cost decomposition per phase...")
    fig_cost_decomposition(data)

    print(f"\nAll figures saved to: {FIG_DIR}")
