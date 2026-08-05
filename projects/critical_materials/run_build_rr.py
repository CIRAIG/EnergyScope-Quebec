#!/usr/bin/env python3
"""CLI entry point for the recycling-rate pipeline -- counterpart to
run_build_mi.py.

Regenerates ampl_files/Material_recycling.dat from Recycling_rates.xlsx
(RR_Energy/RR_Vehicles/RR_Vehicles_Public/RR_H2 for source data, Mapping/
Overrides for the tech matching table -- same schema as
Material_intensities_energyscope.xlsx), then prints a coverage report of
which EnergyScope technologies have a usable recycling rate. That workbook is
read-only input -- this script never writes to it.

Only `recycling_rate` is regenerated here. `collection_rate` (no source data
yet) and `recycling_cost`/`disposal_cost`/`recycling_gwp`/`disposal_gwp`
(never sourced from this workbook) aren't written by anything right now --
they stay at their AMPL defaults (collection_rate=1, everything else=0)
until a future source sheet is added and this pipeline is extended to cover
them.

Usage (command line):
    python run_build_rr.py [--scenario baseline] [--no-dat]

Usage (notebook, e.g. from projects/critical_materials/):
    from run_build_rr import main
    main()
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / 'src'))

from mi_pipeline.coverage import build_report, print_report
from mi_pipeline.mapping import load_mapping
from rr_pipeline import sources
from rr_pipeline.aggregate import compute_all
from rr_pipeline.build_table import build


def main(scenario='baseline', write_dat=True):
    """Plain function, callable directly from a notebook -- no argparse/sys.argv
    involved here."""
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
