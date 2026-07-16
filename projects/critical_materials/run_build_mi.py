#!/usr/bin/env python3
"""CLI entry point for the material-intensity pipeline.

Regenerates excel_files/technologies_mi_all_years.xlsx and
ampl_files/Material_intensity.dat from tech_mapping.xlsx +
Material_intensities_energyscope.xlsx, then prints a coverage report of which
EnergyScope technologies are integrated / placeholder-zero / not mapped.

Usage (command line):
    python run_build_mi.py [--scenario baseline] [--no-xlsx] [--no-dat]

Usage (notebook, e.g. from projects/critical_materials/):
    from run_build_mi import main
    main()                          # same as the CLI defaults
    main(scenario='optimiste')      # apply the 'optimiste' scenario's overrides
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / 'src'))

from mi_pipeline.aggregate import compute_all
from mi_pipeline.build_table import build
from mi_pipeline.coverage import build_report, print_report, write_status_back
from mi_pipeline.mapping import load_mapping


def main(scenario='baseline', write_xlsx=True, write_dat=True):
    """Plain function, callable directly from a notebook -- no argparse/sys.argv
    involved here, so it isn't tripped up by Jupyter's own kernel launch arguments."""
    build(scenario=scenario, write_xlsx=write_xlsx, write_dat=write_dat)

    mapping = load_mapping()
    intensities = compute_all(scenario=scenario)
    report = build_report(mapping, intensities)
    print()
    print_report(report)
    write_status_back(report)


def _cli():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--scenario', default='baseline',
                         help="Scenario name from tech_mapping.xlsx's Overrides sheet (default: baseline, no overrides).")
    parser.add_argument('--no-xlsx', action='store_true', help="Skip writing technologies_mi_all_years.xlsx.")
    parser.add_argument('--no-dat', action='store_true', help="Skip writing Material_intensity.dat.")
    args = parser.parse_args()
    main(scenario=args.scenario, write_xlsx=not args.no_xlsx, write_dat=not args.no_dat)


if __name__ == '__main__':
    _cli()
