"""

Reads per-year Techs/*.dat and EUD/*.dat files and rewrites them in
AMPL matrix format (same style as ESMY/STEP_2_Pathway_Model/PES_data_year_related.dat).

Outputs:
  out_techs.dat  — all tech params (c_inv, c_maint, c_p, lifetime, trl,
                                    f_min, f_max, layers_in_out, c_op, gwp_constr)
  out_eud.dat    — end_uses_demand_year

Usage:
  python scripts/write_matrix_dat.py <techs_dir> <eud_dir>
"""

import os, re, sys
from collections import defaultdict


YEARS = ['2020','2025','2030','2035','2040','2045','2050']

# Parser: reads all `let param[...] := val ;` lines from a dat file.
# Returns dict: {param_name: {key_tuple: float_value}}

RE_LET = re.compile(
    r"let\s+(\w+)\s*\[([^\]]+)\]\s*:=\s*(Infinity|[\d.\-+eE*/ ]+)\s*;"
)

def _eval_val(expr):
    """Evaluate simple arithmetic expressions like '0.07*1.0'."""
    try:
        return float(eval(expr.strip().replace('Infinity', 'float("inf")')))
    except Exception:
        return None


def _fmt(val):
    """Format a float for AMPL output, converting Python inf to Infinity."""
    import math
    return 'Infinity' if math.isinf(float(val)) else str(val)


def parse_dat(path):
    """Parse a .dat file and return {param: {key_tuple: float_value}}."""
    data = defaultdict(dict)
    with open(path, encoding='utf-8', errors='replace') as f:
        for line in f:
            m = RE_LET.search(line)
            if not m:
                continue
            param = m.group(1)
            raw_keys = m.group(2)
            val = _eval_val(m.group(3))
            if val is None:
                continue
            # parse keys: strip quotes, split by comma
            keys = tuple(k.strip().strip("'\"") for k in raw_keys.split(','))
            data[param][keys] = val
    return data


def _filter_techs(techs_data, substrings):
    """Remove all entries whose tech name (key position 1) contains any of the substrings."""
    if not substrings:
        return techs_data
    pattern = re.compile('|'.join(re.escape(s) for s in substrings))
    for param in list(techs_data.keys()):
        techs_data[param] = {
            k: v for k, v in techs_data[param].items()
            if len(k) < 2 or not pattern.search(k[1])
        }
    return techs_data


def load_shares(directory, years):
    """Load and merge all QC_shares_<year>.dat files from directory."""
    merged = defaultdict(dict)
    for yr in years:
        fpath = os.path.join(directory, f'QC_shares_{yr}.dat')
        if not os.path.exists(fpath):
            continue
        d = parse_dat(fpath)
        for param, entries in d.items():
            merged[param].update(entries)
    return merged


def load_eud(directory, years):
    """Load and merge all QC_eud_<year>.dat files from directory."""
    merged = defaultdict(dict)
    for yr in years:
        fpath = os.path.join(directory, f'QC_eud_{yr}.dat')
        if not os.path.exists(fpath):
            continue
        d = parse_dat(fpath)
        for param, entries in d.items():
            merged[param].update(entries)
    return merged


def load_techs(directory, years):
    """Load and merge all QC_techs_<year>.dat files from directory."""
    merged = defaultdict(dict)
    for yr in years:
        fpath = os.path.join(directory, f'QC_techs_{yr}.dat')
        if not os.path.exists(fpath):
            continue
        d = parse_dat(fpath)
        for param, entries in d.items():
            merged[param].update(entries)
    return merged


# Writers

def write_1d_param(f, name, data, dim0_vals):
    """Write param[dim0] as a simple AMPL list."""
    if not data:
        return
    f.write(f'param {name} :=\n')
    for d0 in dim0_vals:
        val = data.get((d0,))
        if val is not None:
            f.write(f'{d0}\t{_fmt(val)}\n')
    f.write(';\n\n')


def write_2d_param(f, name, data, dim0_vals, dim1_vals, fill=0):
    """Write param[dim0, dim1] as matrix: rows=dim0, cols=dim1."""
    if not data:
        return
    f.write(f'param {name} :\t' + '\t'.join(dim1_vals) + '\t:=\n')
    for d0 in dim0_vals:
        row = [_fmt(data.get((d0, d1), fill)) for d1 in dim1_vals]
        f.write(f'{d0}\t' + '\t'.join(row) + '\n')
    f.write(';\n\n')


def write_3d_param(f, name, data, yr_vals, dim1_vals, dim2_vals):
    """Write param[year, dim1, dim2] as per-year [year,*,*] blocks."""
    if not data:
        return
    f.write(f'param {name} :=\n')
    for yr in yr_vals:
        f.write(f'["YEAR_{yr}",*,*]:\t' + '\t'.join(dim2_vals) + '\t:=\n')
        for d1 in dim1_vals:
            row = [_fmt(data.get((f'YEAR_{yr}', d1, d2), 0)) for d2 in dim2_vals]
            if any(v not in ('0', '0.0') for v in row):
                f.write(f'{d1}\t' + '\t'.join(row) + '\n')
    f.write(';\n\n')


# Main

def run(techs_dir, eud_dir, shares_dir=None):
    """Concatenate per-year dat files into single output files (preserving every let statement).

    Using concatenation instead of matrix format avoids spurious fill-value zeros
    for sparse parameters (f_max, layers_in_out, etc.) where 0 != model default.

    Args:
        techs_dir:  directory containing QC_techs_<year>.dat files
        eud_dir:    directory containing QC_eud_<year>.dat files
        shares_dir: directory containing QC_shares_<year>.dat files (optional)
    """
    techs_dir = str(techs_dir)
    eud_dir   = str(eud_dir)
    out_techs = os.path.join(techs_dir, 'out_techs.dat')
    out_eud   = os.path.join(eud_dir,   'out_eud.dat')

    print(f'Loading techs from {techs_dir} ...')
    with open(out_techs, 'w', encoding='utf-8') as f:
        f.write('# Tech parameters - concatenated from per-year files\n')
        f.write('# Generated by write_matrix_dat.py\n\n')
        for yr in YEARS:
            fpath = os.path.join(techs_dir, f'QC_techs_{yr}.dat')
            if os.path.exists(fpath):
                with open(fpath, encoding='utf-8', errors='replace') as yr_f:
                    f.write(yr_f.read())
    print(f'  Saved: {out_techs}')

    print(f'Loading EUD from {eud_dir} ...')
    with open(out_eud, 'w', encoding='utf-8') as f:
        f.write('# EUD parameters - concatenated from per-year files\n')
        f.write('# Generated by write_matrix_dat.py\n\n')
        for yr in YEARS:
            fpath = os.path.join(eud_dir, f'QC_eud_{yr}.dat')
            if os.path.exists(fpath):
                with open(fpath, encoding='utf-8', errors='replace') as yr_f:
                    f.write(yr_f.read())
    print(f'  Saved: {out_eud}')

    if shares_dir is not None:
        shares_dir = str(shares_dir)
        out_shares = os.path.join(shares_dir, 'out_shares.dat')
        print(f'Loading shares from {shares_dir} ...')
        with open(out_shares, 'w', encoding='utf-8') as f:
            f.write('# Shares parameters - concatenated from per-year files\n')
            f.write('# Generated by write_matrix_dat.py\n\n')
            for yr in YEARS:
                fpath = os.path.join(shares_dir, f'QC_shares_{yr}.dat')
                if os.path.exists(fpath):
                    with open(fpath, encoding='utf-8', errors='replace') as yr_f:
                        f.write(yr_f.read())
        print(f'  Saved: {out_shares}')

    print('Done.')


def main():
    if len(sys.argv) != 3:
        print("Usage: python write_matrix_dat.py <techs_dir> <eud_dir>")
        sys.exit(1)
    run(sys.argv[1], sys.argv[2])


if __name__ == '__main__':
    main()
