#!/usr/bin/env python3
"""Build the website copy of the dashboards (GitHub Pages): one folder per scenario of site_scenarios.json, named with its name on the site.

For each scenario, out/<case>/ is copied to <site>/<name>/ (graphs, plotly.min.js, 0_Summary.html; no pkl), the run name is replaced by the site
name in the pages, the 'Scenario' pages are rebuilt with the description of the scenario, and index.html is rebuilt so that the scenario
selector of every dashboard lists the site names. <site>/index.html is the landing page: the scenarios by group (site_scenarios.json), each with its description,
transition cost and links to its dashboard and summary.
Add a scenario by adding an entry (case, name, description, group, optionally 'reference' (scenario the cost is compared with) and 'overrides' if the run loaded extra .dat files of material data) to site_scenarios.json, then rerun this script and push <site>."""
import argparse
import html
import pickle
import re
import shutil
import sys
from datetime import date
from pathlib import Path

_PROJ_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(_PROJ_ROOT))
sys.path.insert(0, str(_PROJ_ROOT.parents[1]))  # repo root, for shared

import Plot_functions as pf

DEFAULT_SITE = Path.home() / 'dashboard-test'


# Copy the dashboard of a run to <site>/<name>/ and rebuild its 'Scenario' pages (everything but index.html, built once all scenarios are in place).
# overrides: .dat files of the run's extra_files, so that the intensity and recycling pages show the values the run really used
def _stage(plot_results, case, name, site, overrides=()):
    src, dst = _PROJ_ROOT / 'out' / case, site / name
    if dst.exists():
        shutil.rmtree(dst)  # a folder written by this script
    shutil.copytree(src / 'graphs', dst / 'graphs', ignore=shutil.ignore_patterns('.DS_Store', 'index.html'))
    for extra in ('plotly.min.js', '0_Summary.html'):
        if (src / extra).exists():
            shutil.copy2(src / extra, dst / extra)

    # The run name sits in the chart titles: replace it by the name on the site (the lookahead keeps 1_baseline out of 1_baseline_limits03)
    run_name = re.compile(re.escape(case) + r'(?![A-Za-z0-9_])')
    for page in [*(dst / 'graphs').glob('*.html'), dst / '0_Summary.html']:
        if page.exists():
            text = page.read_text(encoding='utf-8')
            new_text = run_name.sub(name, text)
            if new_text != text:
                page.write_text(new_text, encoding='utf-8')

    results = pickle.load(open(src / '_Results.pkl', 'rb'))
    results.update(pickle.load(open(src / '_Materials_Results.pkl', 'rb')))
    graphs = dst / 'graphs'
    pf._save_scenario_pages(results, pf._drop_year_2020(results), name, graphs,
                            lambda fig, f: plot_results._save(fig, str(graphs), f), case_dir=src, public=True, overrides=overrides)

LANDING_TITLE = 'Critical materials in the EnergyScope-Québec transition – pathway model'
LANDING_INTRO = ("This site accompanies the report and gives access to the interactive dashboard for each simulated scenario. "
                 "This work adds the Scenario and Materials sections to the dashboard.")
LANDING_ENTRY = 'materials-definitions'  # page of the dashboard that the button opens: the 'Definitions' page of the 'Materials' section (slug of the menu item)
GROUP_NOTES = {  # one line under the title of each group of site_scenarios.json
    'Baselines': 'Reference runs, without and with limits on the annual production of materials.',
    'Sensitivity analyses on the limited baseline': 'One assumption changed at a time, compared with Baseline_limited.',
    'Relaxed availability constraints': 'The limits of the most critical materials are removed one after the other.',
    'Other scenarios': 'Alternative energy-system scenarios, with the material limits at 0.3 % of world production.',
}
_LANDING_CSS = """
:root { --bg: #f2f4f7; --surface: #ffffff; --line: #e3e7ee; --ink: #1b2130; --ink2: #5b6577; --navy: #152238; --accent: #2563eb; --accent-soft: #eaf0fe;
        --up-bg: #fdeceb; --up-ink: #b42318; --down-bg: #e7f6ee; --down-ink: #12805c; }
* { box-sizing: border-box; }
body { margin: 0; background: var(--bg); color: var(--ink); font: 15px/1.5 'Inter', -apple-system, 'Segoe UI', Roboto, Helvetica, sans-serif; }
header { background: var(--navy); color: #fff; }
.wrap { max-width: 1120px; margin: 0 auto; padding: 0 24px; }
header .wrap { padding-top: 44px; padding-bottom: 40px; }
h1 { font-size: 28px; line-height: 1.25; font-weight: 700; margin: 0 0 12px; max-width: 720px; }
.intro { color: #c7d2e5; margin: 0; max-width: 700px; }
main { padding: 8px 0 56px; }
.group { margin-top: 36px; }
.group h2 { font-size: 18px; margin: 0 0 4px; display: flex; align-items: center; gap: 10px; }
.group h2 .count { font-size: 12px; font-weight: 600; color: var(--accent); background: var(--accent-soft); border-radius: 999px; padding: 2px 9px; }
.group .note { color: var(--ink2); margin: 0 0 16px; font-size: 14px; }
.grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(320px, 1fr)); gap: 16px; }
.card { background: var(--surface); border: 1px solid var(--line); border-radius: 12px; padding: 18px 20px; display: flex; flex-direction: column; }
.card { scroll-margin-top: 90px; }
.card:target { border-color: var(--accent); box-shadow: 0 0 0 3px var(--accent), 0 10px 28px rgba(37, 99, 235, .20); }  /* link <site>/#<name>: the card of that scenario is framed */
.card h3 { margin: 0 0 6px; font-size: 16px; font-weight: 600; }
.card .desc { color: var(--ink2); font-size: 13.5px; margin: 0 0 16px; flex: 1; }
.figures { display: flex; align-items: baseline; flex-wrap: wrap; gap: 6px 10px; margin-bottom: 14px; }
.cost { font-size: 24px; font-weight: 700; font-variant-numeric: tabular-nums; letter-spacing: -.01em; }
.cost small { font-size: 12.5px; font-weight: 500; color: var(--ink2); letter-spacing: 0; }
.pill { font-size: 12px; font-weight: 600; border-radius: 999px; padding: 2px 9px; font-variant-numeric: tabular-nums; }
.pill.up { background: var(--up-bg); color: var(--up-ink); } .pill.down { background: var(--down-bg); color: var(--down-ink); }
.vs { font-size: 12px; color: var(--ink2); }
.actions { display: flex; gap: 8px; }
.btn { font-size: 13px; font-weight: 600; text-decoration: none; border-radius: 8px; padding: 7px 14px; background: var(--accent); color: #fff; }
.btn:hover { background: #1d4ed8; } .btn.ghost { background: transparent; color: var(--accent); border: 1px solid #c9d6f7; } .btn.ghost:hover { background: var(--accent-soft); }
footer { color: var(--ink2); font-size: 12.5px; padding: 0 0 40px; }
"""


# Transition cost [B$CAD] of a run, as on the 'Transition cost' page of its dashboard (2020-2050)
def _transition_cost(plot_results, case):
    results = pickle.load(open(_PROJ_ROOT / 'out' / case / '_Results.pkl', 'rb'))
    table = plot_results.transition_cost_by_phase_category(results)
    return float(table[table.index.get_level_values('Phases').isin(plot_results.TRANS_PHASES)].to_numpy().sum())


# <site>/index.html: the scenarios of site_scenarios.json that are on the site, as cards by group, with description, cost and links
def _landing_page(site, plot_results):
    scenarios = [s for s in pf.load_site_scenarios() if (site / s['name'] / 'graphs').exists()]
    cost = {s['name']: _transition_cost(plot_results, s['case']) for s in scenarios}
    sections = []
    for group in dict.fromkeys(s.get('group', 'Scenarios') for s in scenarios):  # in order of appearance
        members = [x for x in scenarios if x.get('group', 'Scenarios') == group]
        cards = []
        for s in members:
            name, ref = s['name'], s.get('reference')
            pill = ''
            if ref in cost:
                diff = cost[name] - cost[ref]
                pill = (f'<span class="pill {"up" if diff > 0 else "down"}">{diff:+,.1f} ({100 * diff / cost[ref]:+.1f} %)</span>'
                        f'<span class="vs">vs {html.escape(ref)}</span>')
            cards.append(f'<article class="card" id="{html.escape(name)}"><h3>{html.escape(name)}</h3><p class="desc">{html.escape(s["description"])}</p>'
                         f'<div class="figures"><span class="cost">{cost[name]:,.0f} <small>B CAD</small></span>{pill}</div>'
                         f'<div class="actions"><a class="btn" href="{name}/graphs/index.html#{LANDING_ENTRY}">Open dashboard</a></div></article>')
        note = f'<p class="note">{html.escape(GROUP_NOTES[group])}</p>' if group in GROUP_NOTES else ''
        sections.append(f'<section class="group"><h2>{html.escape(group)} <span class="count">{len(members)}</span></h2>{note}<div class="grid">{"".join(cards)}</div></section>')
    page = (f'<!DOCTYPE html>\n<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">\n'
            f'<title>{LANDING_TITLE}</title>\n'
            f'<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap">\n<style>{_LANDING_CSS}</style></head>\n'
            f'<body><header><div class="wrap"><h1>{LANDING_TITLE}</h1><p class="intro">{LANDING_INTRO}</p></div></header>\n'
            f'<main><div class="wrap">\n' + '\n'.join(sections)
            + f'\n</div></main>\n<footer><div class="wrap">Updated {date.today():%Y-%m-%d}</div></footer>\n</body></html>\n')
    (site / 'index.html').write_text(page, encoding='utf-8')
    return len(scenarios)


def build(site=DEFAULT_SITE, only=None, landing_only=False):
    site = Path(site).expanduser()
    plot_results = pf.load_plot_results()
    if landing_only:
        print(f"[run_build_site] landing page with {_landing_page(site, plot_results)} scenario(s) written to {site / 'index.html'}")
        return
    scenarios = [s for s in pf.load_site_scenarios() if not only or s['name'] in only or s['case'] in only]
    if not scenarios:
        raise SystemExit("No scenario to build: check site_scenarios.json and --only")
    site.mkdir(parents=True, exist_ok=True)
    for s in scenarios:
        print(f"[run_build_site] {s['case']} -> {s['name']}")
        _stage(plot_results, s['case'], s['name'], site, [_PROJ_ROOT / o for o in s.get('overrides', [])])
    # index.html of every scenario on the site, including those of previous builds, so that all selectors list the same scenarios
    for s in pf.load_site_scenarios():
        if (site / s['name'] / 'graphs').exists():
            plot_results.create_dashboard(str(site / s['name'] / 'graphs'), s['name'], auto_open=False)
    _landing_page(site, plot_results)
    (site / '.nojekyll').touch()
    print(f"[run_build_site] {len(scenarios)} scenario(s) written to {site}")


def _cli():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--site', default=str(DEFAULT_SITE), help=f"Folder of the website repository (default {DEFAULT_SITE}).")
    parser.add_argument('--only', nargs='+', help="Build only these scenarios (run folder or name on the site); the others are left as they are.")
    parser.add_argument('--landing-only', action='store_true', help="Only rewrite <site>/index.html (the landing page), without copying any dashboard.")
    args = parser.parse_args()
    build(args.site, args.only, args.landing_only)


if __name__ == '__main__':
    _cli()
