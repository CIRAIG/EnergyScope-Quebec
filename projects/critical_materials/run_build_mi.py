#!/usr/bin/env python3
"""Regenerate ampl_files/Material_intensity.dat from Material_intensities.xlsx (read-only) and print a coverage report."""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / 'src'))

from mi_pipeline.aggregate import compute_all
from mi_pipeline.build_table import build
from mi_pipeline.coverage import build_report, print_report
from mi_pipeline.mapping import load_mapping


# Callable from a notebook; vehicle_source 'bieuville' or 'watari' (both overwrite the same .dat)
def main(vehicle_source='bieuville', write_dat=True):
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
