#!/usr/bin/env python3
"""Regenerate ampl_files/Material_limits.dat from Material_limits.xlsx (read-only input)."""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / 'src'))

from limits_pipeline.build_table import build


# Callable from a notebook (no argparse/sys.argv)
def main(write_dat=True):
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
