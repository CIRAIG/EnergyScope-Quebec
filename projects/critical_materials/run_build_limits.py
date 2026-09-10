#!/usr/bin/env python3
"""CLI entry point for the material-limits pipeline -- counterpart to
run_build_mi.py/run_build_rr.py.

Regenerates ampl_files/Material_limits.dat from Material_limits.xlsx's
'Material_limits' sheet ([t/year] production/reserve caps per material, by
year). That workbook is read-only input -- this script never writes to it.

2020/2025 are always left at their AMPL default (Infinity) regardless of what
the sheet says -- see limits_pipeline.build_table.WRITTEN_YEARS for why.

Usage (command line):
    python run_build_limits.py [--no-dat]

Usage (notebook, e.g. from projects/critical_materials/):
    from run_build_limits import main
    main()
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / 'src'))

from limits_pipeline.build_table import build


def main(write_dat=True):
    """Plain function, callable directly from a notebook -- no argparse/sys.argv
    involved here."""
    written = build(write_dat=write_dat)
    n_materials = len(written)
    n_values = int(written.notna().sum().sum())
    print(f"[run_build_limits] {n_materials} materials, {n_values} (year, material) limits written.")
    return written


def _cli():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--no-dat', action='store_true', help="Skip writing Material_limits.dat.")
    args = parser.parse_args()
    main(write_dat=not args.no_dat)


if __name__ == '__main__':
    _cli()
