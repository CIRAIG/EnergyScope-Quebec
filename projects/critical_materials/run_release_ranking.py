#!/usr/bin/env python3
"""Runs the limited scenario with some material limits already released, then releases one more limit at a time (dashboards included).

With RELEASED = ['Dy'], the runs are 1_baseline_limits03_free_Dy (reference), then _DyAg, _DyPt, _DyNd, ... one per candidate.
To look for the third limit, use RELEASED = ['Dy', 'Pt'] (runs _DyPt, then _DyPtAg, _DyPtNd, ...).

    python run_release_ranking.py
    python run_release_ranking.py --released Dy Pt --candidates Ag Nd Ge
From a notebook: from run_release_ranking import run_all; run_all()
"""
import argparse
import sys
import tempfile
from pathlib import Path

_REPO_DIR = Path(__file__).resolve().parents[2]

STEM = '1_baseline_limits03_free'               # the limited scenario; runs are named <STEM>_<released materials>
RELEASED = ['Dy']                               # limits already released in every run
CANDIDATES = ['Ag', 'Pt', 'Nd', 'Ge', 'In', 'Li', 'Te']
RUN_OPTIONS = dict(materials=True, materials_recycling=True, materials_recycling_cost=False, force_max_recycling=True,
                   force_immediate_recycled_use=False, materials_limit=True, build_dashboard=True, open_dashboard=False,
                   verbose=True)


def case_name(materials):
    return STEM + ('_' + ''.join(materials) if materials else '')


# AMPL file read after the data: all the annual limits of these materials set to Infinity
def _release_file(materials, folder):
    path = Path(folder) / f'release_{"".join(materials)}.mod'
    path.write_text(''.join(f"let {{y in YEARS}} limit_material_year[y,'{m}'] := Infinity;\n" for m in materials), encoding='utf-8')
    return str(path)


# The reference run (RELEASED released), then one run per candidate with its limit released too. Runs already on disk are not solved
# again (reuse=True), only their dashboard is rebuilt: delete out/<case> to redo one.
def run_all(candidates=CANDIDATES, released=RELEASED, mip_gap=None, reuse=True):
    if str(_REPO_DIR) not in sys.path:
        sys.path.insert(0, str(_REPO_DIR))
    from shared.utils import run_pathway

    folder = tempfile.mkdtemp(prefix='release_')
    reference = case_name(released)
    print(f'\n===== {reference}: reference, limits of {released} released =====', flush=True)
    run_pathway(reference, extra_files=[_release_file(released, folder)] if released else None, skip_if_exists=reuse,
                mip_gap=mip_gap, **RUN_OPTIONS)
    for material in (m for m in candidates if m not in released):
        materials = released + [material]
        print(f'\n===== {case_name(materials)}: limit of {material} released as well =====', flush=True)
        run_pathway(case_name(materials), extra_files=[_release_file(materials, folder)], skip_if_exists=reuse,
                    mip_gap=mip_gap, **RUN_OPTIONS)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--released', nargs='*', default=RELEASED, help=f"Limits released in every run (default: {' '.join(RELEASED)}).")
    parser.add_argument('--candidates', nargs='+', default=CANDIDATES, help=f"Limits released one at a time (default: {' '.join(CANDIDATES)}).")
    parser.add_argument('--mip-gap', type=float, default=None, help="Gurobi MIPGap (default: Gurobi's own).")
    args = parser.parse_args()
    run_all(args.candidates, args.released, mip_gap=args.mip_gap)
