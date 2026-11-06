#!/usr/bin/env python3
"""Build the website copy of the dashboards (GitHub Pages): one folder per scenario of site_scenarios.json, named with its name on the site.

For each scenario, out/<case>/ is copied to <site>/<name>/ (graphs, plotly.min.js, 0_Summary.html; no pkl), the run name is replaced by the site
name in the pages, the 'Scenario' pages are rebuilt with the description of the scenario, and index.html is rebuilt so that the scenario
selector of every dashboard lists the site names. <site>/index.html redirects to the overview of the first scenario.
Add a scenario by adding an entry (case, name, description, and 'overrides' if the run loaded extra .dat files of material data) to site_scenarios.json, then rerun this script and push <site>."""
import argparse
import pickle
import re
import shutil
import sys
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


def build(site=DEFAULT_SITE, only=None):
    site = Path(site).expanduser()
    plot_results = pf.load_plot_results()
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
    first = pf.load_site_scenarios()[0]['name']  # the first scenario of the file, whatever --only selects
    (site / 'index.html').write_text(f'<meta http-equiv="refresh" content="0; url={first}/graphs/index.html#scenario-overview">\n', encoding='utf-8')
    (site / '.nojekyll').touch()
    print(f"[run_build_site] {len(scenarios)} scenario(s) written to {site}")


def _cli():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--site', default=str(DEFAULT_SITE), help=f"Folder of the website repository (default {DEFAULT_SITE}).")
    parser.add_argument('--only', nargs='+', help="Build only these scenarios (run folder or name on the site); the others are left as they are.")
    args = parser.parse_args()
    build(args.site, args.only)


if __name__ == '__main__':
    _cli()
