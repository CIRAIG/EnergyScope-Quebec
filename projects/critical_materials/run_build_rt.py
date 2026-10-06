#!/usr/bin/env python3
"""Regenerate ampl_files/Material_recycling_process.dat from the recycling-process sheets of Recycling_rates.xlsx (read-only)."""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / 'src'))

from rt_pipeline.build_table import build


# Callable from a notebook (no argparse/sys.argv)
def main(write_dat=True):
    recovery_rows, cbe_rows, collection_rows = build(write_dat=write_dat)

    has_cost = {(tech, mat, proc) for tech, mat, proc, *_ in cbe_rows}
    all_combos = {(tech, mat, proc) for tech, mat, proc, _stream, _rate in recovery_rows}
    missing = sorted(all_combos - has_cost)

    print("\nCoverage report:")
    print(f"  recovery rate defined : {len(all_combos)} (tech, material, process) combos")
    print(f"  cost/revenue          : {len(has_cost)} (tech, material, process) combos")
    print(f"  missing cost data     : {len(missing)} -- these fall back to recycling_cost_process=0 (free recycling)")
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
