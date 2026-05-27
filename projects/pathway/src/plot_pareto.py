"""
plot_pareto.py — Pareto front from _Recap.csv

Objectives (both minimised):
  - TotalCost_M€      : total transition cost (CAPEX + OPEX)
  - CumulativeCO2_Mt  : cumulative GHG emissions over transition

Usage:
  python plot_pareto.py               # reads out/_Recap.csv
  python plot_pareto.py --out mydir   # reads mydir/_Recap.csv
"""
import argparse, os, sys
from pathlib import Path
import numpy as np
import pandas as pd
import plotly.graph_objects as go
import plotly.io as pio

pio.templates.default = 'simple_white'

_SRC_DIR   = Path(os.path.dirname(os.path.abspath(__file__)))
OUT_DIR    = str(_SRC_DIR.parent / 'out')
RECAP_FILE = '_Recap.csv'


# ---------------------------------------------------------------------------
# Pareto helpers
# ---------------------------------------------------------------------------

def pareto_front(costs, co2):
    """Return boolean mask of non-dominated points (minimise both objectives)."""
    n = len(costs)
    dominated = np.zeros(n, dtype=bool)
    for i in range(n):
        for j in range(n):
            if i == j:
                continue
            # j dominates i if j is <= in both and < in at least one
            if (costs[j] <= costs[i] and co2[j] <= co2[i] and
                    (costs[j] < costs[i] or co2[j] < co2[i])):
                dominated[i] = True
                break
    return ~dominated


def sort_pareto(df_pf):
    """Sort Pareto points by cost (left to right on the front)."""
    return df_pf.sort_values('TotalCost_M€')


# ---------------------------------------------------------------------------
# Plot
# ---------------------------------------------------------------------------

def plot_pareto(recap_path, out_dir):
    df = pd.read_csv(recap_path)

    # Only include runs whose Case_study starts with 'Pareto_'
    df = df[df['Case_study'].str.startswith('Pareto_', na=False)].copy()

    # Drop rows missing either objective
    df = df.dropna(subset=['TotalCost_M€', 'CumulativeCO2_Mt'])

    if df.empty:
        print('[ERROR] No valid rows in Recap CSV.')
        return

    # Convert to B$CAD for readability
    df['Cost_B'] = df['TotalCost_M€'] / 1000

    # Tag sweep direction
    df['Direction'] = 'other'
    df.loc[df['Case_study'].str.contains('minCO2',    case=False), 'Direction'] = 'min_co2'
    df.loc[df['Case_study'].str.contains('minCost',   case=False), 'Direction'] = 'min_cost'
    df.loc[df['Case_study'].str.contains('weighted',  case=False), 'Direction'] = 'weighted'

    is_pareto = pareto_front(df['Cost_B'].values, df['CumulativeCO2_Mt'].values)
    df['Pareto'] = is_pareto

    pf = sort_pareto(df[df['Pareto']])
    dominated = df[~df['Pareto']]

    DIR_STYLE = {
        'min_co2':  dict(color='steelblue',   symbol='circle',   name='Pareto-optimal (min CO2)'),
        'min_cost': dict(color='darkorange',  symbol='diamond',  name='Pareto-optimal (min cost)'),
        'weighted': dict(color='seagreen',    symbol='star',     name='Pareto-optimal (weighted)'),
        'other':    dict(color='mediumpurple', symbol='square',  name='Pareto-optimal (other)'),
    }
    DOM_STYLE = {
        'min_co2':  dict(color='lightblue',  symbol='circle'),
        'min_cost': dict(color='moccasin',   symbol='diamond'),
        'weighted': dict(color='lightgreen', symbol='star'),
        'other':    dict(color='lightgray',  symbol='square'),
    }

    # Hover text
    def hover(row):
        lines = [
            f"<b>{row['Case_study']}</b>",
            f"Cost: {row['Cost_B']:.0f} B$CAD",
            f"CO2:  {row['CumulativeCO2_Mt']:.0f} Mt",
            f"CAPEX: {row['CAPEX_M€']/1000:.0f} B$ | OPEX: {row['OPEX_M€']/1000:.0f} B$",
        ]
        if pd.notna(row.get('Comment', None)) and str(row.get('Comment','')).strip():
            comment = str(row['Comment']).strip()
            words = comment.split()
            wrapped, line = [], []
            for w in words:
                line.append(w)
                if len(' '.join(line)) > 60:
                    wrapped.append(' '.join(line))
                    line = []
            if line:
                wrapped.append(' '.join(line))
            lines.append('<br>'.join(wrapped))
        return '<br>'.join(lines)

    fig = go.Figure()

    # Pareto front line (connecting all Pareto-optimal points)
    if len(pf) > 1:
        fig.add_trace(go.Scatter(
            x=pf['Cost_B'], y=pf['CumulativeCO2_Mt'],
            mode='lines',
            line=dict(color='gray', width=1.5, dash='dot'),
            showlegend=False,
            hoverinfo='skip',
        ))

    # Dominated points — one trace per direction
    for direction, style in DOM_STYLE.items():
        sub = dominated[dominated['Direction'] == direction]
        if sub.empty:
            continue
        fig.add_trace(go.Scatter(
            x=sub['Cost_B'], y=sub['CumulativeCO2_Mt'],
            mode='markers',
            name=f'Dominated ({direction})',
            marker=dict(size=9, color=style['color'], symbol=style['symbol'],
                        line=dict(color='gray', width=0.8)),
            text=[hover(r) for _, r in sub.iterrows()],
            hovertemplate='%{text}<extra></extra>',
        ))

    # Pareto-optimal points — one trace per direction
    for direction, style in DIR_STYLE.items():
        sub = pf[pf['Direction'] == direction]
        if sub.empty:
            continue
        fig.add_trace(go.Scatter(
            x=sub['Cost_B'], y=sub['CumulativeCO2_Mt'],
            mode='markers',
            name=style['name'],
            marker=dict(size=13, color=style['color'], symbol=style['symbol'],
                        line=dict(color='black', width=1.2)),
            hovertext=[hover(r) for _, r in sub.iterrows()],
            hovertemplate='%{hovertext}<extra></extra>',
        ))

    # Summary stats in title
    n_total = len(df)
    n_pf    = is_pareto.sum()
    cost_range = f"{df['Cost_B'].min():.0f} - {df['Cost_B'].max():.0f} B$CAD"
    co2_range  = f"{df['CumulativeCO2_Mt'].min():.0f} - {df['CumulativeCO2_Mt'].max():.0f} Mt"

    fig.update_layout(
        title=(f'Pareto front - Transition cost vs Cumulative GHG<br>'
               f'<sup>{n_pf} Pareto-optimal / {n_total} runs | '
               f'Cost: {cost_range} | CO2: {co2_range}</sup>'),
        xaxis=dict(title='Total transition cost [B$CAD]'),
        yaxis=dict(title='Cumulative GHG emissions [Mt CO2-eq.]'),
        hovermode='closest',
        legend=dict(x=0.99, y=0.99, xanchor='right', yanchor='top'),
        height=550,
    )

    out_path = os.path.join(out_dir, 'pareto_front.html')
    fig.write_html(out_path)
    print(f'Saved → {out_path}')

    # Print Pareto table
    print('\nPareto-optimal solutions:')
    print(pf[['Case_study', 'Cost_B', 'CumulativeCO2_Mt', 'CAPEX_M€', 'OPEX_M€']]
          .rename(columns={'Cost_B': 'Cost_B$', 'CumulativeCO2_Mt': 'CO2_Mt'})
          .to_string(index=False))


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--out', default=OUT_DIR, help='Output directory containing _Recap.csv')
    args = parser.parse_args()

    recap_path = os.path.join(args.out, RECAP_FILE)
    if not os.path.exists(recap_path):
        print(f'[ERROR] Not found: {recap_path}')
        raise SystemExit(1)

    plot_pareto(recap_path, args.out)
