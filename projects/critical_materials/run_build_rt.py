#!/usr/bin/env python3
"""CLI entry point for the recycling-technologies (Approach 2) pipeline --
counterpart to run_build_rr.py (Approach 1) and run_build_mi.py.

Regenerates ampl_files/Material_recycling_process.dat from
Recycling_rates.xlsx's Recycling_technologies (recovery rate per material x
process), Recycling_cost (cost + revenue), Electricity_use (energy) and
Recycling_scenario_technologies (minimum-collection-rate floor) sheets, then
prints which materials have a recovery rate but are still missing
cost/energy/revenue data (i.e. what's left to fill in before the process
choice reflects real economics instead of just AMPL defaults).

Usage (command line):
    python run_build_rt.py [--no-dat]

Usage (notebook, e.g. from projects/critical_materials/):
    from run_build_rt import main
    main()
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / 'src'))

from rt_pipeline import sources
from rt_pipeline.build_table import build


def main(write_dat=True):
    """Plain function, callable directly from a notebook -- no argparse/sys.argv
    involved here."""
    recovery_rows, cbe_rows, min_collection_rows = build(write_dat=write_dat)

    has_cost = {(tech, mat, proc) for tech, mat, proc, *_ in cbe_rows}
    missing = sorted({(tech, mat, proc) for tech, mat, proc, _ in recovery_rows} - has_cost)

    print("\nCoverage report:")
    print(f"  recovery rate defined : {len({(t, m, p) for t, m, p, _ in recovery_rows})} (tech, material, process) combos")
    print(f"  cost/energy/revenue   : {len(has_cost)} (tech, material, process) combos")
    print(f"  missing cost data     : {len(missing)} -- these fall back to recycling_cost=0 (free recycling)")
    if missing:
        for tech, mat, proc in missing:
            print(f"    - {tech} / {mat} / {proc}")


def _cli():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--no-dat', action='store_true', help="Skip writing Material_recycling_process.dat.")
    args = parser.parse_args()
    main(write_dat=not args.no_dat)


if __name__ == '__main__':
    _cli()
