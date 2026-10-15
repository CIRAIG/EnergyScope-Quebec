#!/usr/bin/env python3
"""Regenerate ampl_files/Material_recycling.dat from Recycling_rates.xlsx (read-only) and print a coverage report."""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / 'src'))

from mi_pipeline.coverage import build_report, print_report
from mi_pipeline.mapping import load_mapping
from rr_pipeline import sources
from rr_pipeline.aggregate import compute_all
from rr_pipeline.build_table import build


# Callable from a notebook (no argparse/sys.argv)
def main(scenario='baseline', write_dat=True):
    build(scenario=scenario, write_dat=write_dat)

    mapping = load_mapping(path=sources.SOURCE_XLSX)
    rates = compute_all(scenario=scenario)
    report = build_report(mapping, rates)
    print()
    print_report(report)


def _cli():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--scenario', default='baseline',
                         help="Scenario name from the Overrides sheet (default: baseline, no overrides).")
    parser.add_argument('--no-dat', action='store_true', help="Skip writing Material_recycling.dat.")
    args = parser.parse_args()
    main(scenario=args.scenario, write_dat=not args.no_dat)


if __name__ == '__main__':
    _cli()
