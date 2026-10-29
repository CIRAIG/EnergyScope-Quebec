#!/usr/bin/env python3
"""Regenerate ampl_files/Material_bigM.dat: the big-M (Constraints.mod's M_relax) of the K approach, per (year, material).

M must exceed how far the net demand can go above a limit when the material is relaxed. A single huge M (1e9 t) makes the LP
relaxation ignore the limits, and lets the solver's integrality tolerance (1e-5) relax 1e-5 * M t while Relax_material still counts
as 0. Here M[y,m] = max(margin * highest net demand of the reference runs - limit, limit, 1), so it follows the size of each material.
After a K run, check that the net demand of the relaxed material stays below limit + M; if not, raise --margin and rerun.
Needs the runs in out/ (Net_demand in _Materials_Results.pkl): 1_baseline and the 1_baseline_limits03* runs by default."""
import argparse
import pickle
import sys
from pathlib import Path

import pandas as pd

_PROJ_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(_PROJ_ROOT / 'src'))

from limits_pipeline.build_table import build

OUT_PATH = _PROJ_ROOT / 'ampl_files' / 'Material_bigM.dat'


def _default_references():
    out = _PROJ_ROOT / 'out'
    return ['1_baseline'] + sorted(p.name for p in out.glob('1_baseline_limits03*') if (p / '_Materials_Results.pkl').exists())


# Callable from a notebook (no argparse/sys.argv); returns the (materials x years) table of M [t]
def main(references=None, margin=2.0, write_dat=True):
    references = references or _default_references()
    limits = build(write_dat=False)  # materials x years [t/yr], NaN = no limit
    net_demand = []
    for case in references:
        path = _PROJ_ROOT / 'out' / case / '_Materials_Results.pkl'
        with open(path, 'rb') as f:
            net_demand.append(pickle.load(f)['Net_demand']['Net_demand'].rename(case))
    peak = pd.concat(net_demand, axis=1).max(axis=1)  # (Years, Materials) -> highest net demand over the reference runs

    big_m = pd.DataFrame(index=limits.index, columns=limits.columns, dtype=float)
    for mat in limits.index:
        for year in limits.columns:
            limit = limits.loc[mat, year]
            if pd.isna(limit):
                continue
            demand = peak.get((f'YEAR_{year}', mat), 0.0)
            big_m.loc[mat, year] = max(margin * (0.0 if pd.isna(demand) else demand) - limit, limit, 1.0)

    if write_dat:
        with open(OUT_PATH, 'w', encoding='utf-8', newline='\n') as f:
            f.write("data;\n\n")
            f.write("# Grand M [t] de l'approche K (M_relax de Constraints.mod) par (annee, materiau), regenere par run_build_bigM.py --\n")
            f.write("# ne pas editer a la main. M = max(marge * demande nette max des runs de reference - limite, limite, 1).\n")
            f.write(f"# Runs de reference : {', '.join(references)} ; marge = {margin:g}.\n")
            f.write("# Charger avec k.mod : extra_files=['.../ampl_files/k.mod', '.../ampl_files/Material_bigM.dat'].\n\n")
            for mat in big_m.index:
                for year in big_m.columns:
                    if pd.notna(big_m.loc[mat, year]):
                        f.write(f"let M_relax['YEAR_{year}','{mat}'] := {big_m.loc[mat, year]:.6g} ;\n")
    values = big_m.stack()
    print(f"[run_build_bigM] {len(values)} (year, material) values from {len(references)} reference run(s), margin {margin:g}: "
          f"M from {values.min():.3g} t ({values.idxmin()[0]}, {values.idxmin()[1]}) to {values.max():.3g} t ({values.idxmax()[0]}, {values.idxmax()[1]}).")
    return big_m


def _cli():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--references', nargs='+', help="Runs of out/ whose Net_demand sets the size of M (default: 1_baseline and 1_baseline_limits03*).")
    parser.add_argument('--margin', type=float, default=2.0, help="Safety factor on the highest net demand (default 2).")
    parser.add_argument('--no-dat', action='store_true', help="Skip writing Material_bigM.dat.")
    args = parser.parse_args()
    main(references=args.references, margin=args.margin, write_dat=not args.no_dat)


if __name__ == '__main__':
    _cli()
