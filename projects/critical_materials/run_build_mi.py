#!/usr/bin/env python3
"""CLI entry point for the material-intensity pipeline.

Regenerates ampl_files/Material_intensity.dat from Material_intensities.xlsx
(the various MI_*/MS_*/Ref&Hp sheets for source data, Mapping for the tech
matching table), then prints a coverage report of which EnergyScope
technologies are integrated / placeholder-zero / not mapped. That workbook is
read-only input -- this script never writes to it.

Usage (command line):
    python run_build_mi.py [--no-dat]

Usage (notebook, e.g. from projects/critical_materials/):
    from run_build_mi import main
    main()                          # same as the CLI defaults
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / 'src'))

from mi_pipeline.aggregate import compute_all
from mi_pipeline.build_table import build
from mi_pipeline.coverage import build_report, print_report
from mi_pipeline.mapping import load_mapping


def main(vehicle_source='bieuville', write_dat=True):
    """Plain function, callable directly from a notebook -- no argparse/sys.argv
    involved here, so it isn't tripped up by Jupyter's own kernel launch arguments.

    vehicle_source: 'bieuville' (default) or 'watari' -- both write to the same
    Material_intensity.dat filename, overwriting whatever was last built. To
    compare the two, build+run_pathway_materials with one, save/rename the
    results, then build+run again with the other (see
    mi_pipeline.aggregate.compute_vehicle_intensities_bieuville)."""
    build(vehicle_source=vehicle_source, write_dat=write_dat)

    mapping = load_mapping()
    intensities = compute_all(vehicle_source=vehicle_source)
    report = build_report(mapping, intensities)
    print()
    print_report(report)


def _cli():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--vehicle-source', default='bieuville', choices=['watari', 'bieuville'],
                         help="Vehicle material-intensity source: 'bieuville' (default) or 'watari'.")
    parser.add_argument('--no-dat', action='store_true', help="Skip writing Material_intensity.dat.")
    args = parser.parse_args()
    main(vehicle_source=args.vehicle_source, write_dat=not args.no_dat)


if __name__ == '__main__':
    _cli()
