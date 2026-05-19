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
        v = float(eval(expr.strip().replace('Infinity', 'float("inf")')))
        return 0.0 if abs(v) < 1e-5 else v
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
    """Write out_techs.dat, out_eud.dat, and (optionally) out_shares.dat in AMPL matrix format.

    Args:
        techs_dir:               directory containing QC_techs_<year>.dat files
        eud_dir:                 directory containing QC_eud_<year>.dat files
        shares_dir:              directory containing QC_shares_<year>.dat files (optional)
        
    """
    techs_dir = str(techs_dir)
    eud_dir   = str(eud_dir)
    out_techs = os.path.join(techs_dir, 'out_techs.dat')
    out_eud   = os.path.join(eud_dir,   'out_eud.dat')

    print(f'Loading techs from {techs_dir} ...')
    techs_data = load_techs(techs_dir, YEARS)

    print(f'Loading EUD from {eud_dir} ...')
    eud_data = load_eud(eud_dir, YEARS)

    yr_vals = [f'YEAR_{y}' for y in YEARS]

    with open(out_techs, 'w', encoding='utf-8') as f:
        f.write('# Tech parameters in matrix format\n')
        f.write('# Generated by write_matrix_dat.py\n\n')

        for param in ['c_inv', 'c_maint', 'c_p', 'lifetime', 'trl', 'f_min', 'f_max',
                      'f_min_perc', 'f_max_perc', 'gwp_constr', 'c_p_max', 'ref_size',
                      'loss_coeff', 'avail', 'out_max']:
            d = techs_data.get(param, {})
            if not d:
                continue
            techs = sorted(set(k[1] for k in d))
            write_2d_param(f, param, d, yr_vals, techs)

        for param in ['storage_eff_in', 'storage_eff_out']:
            d = techs_data.get(param, {})
            if not d:
                continue
            techs  = sorted(set(k[1] for k in d))
            layers = sorted(set(k[2] for k in d))
            write_3d_param(f, param, d, YEARS, techs, layers)

        d = techs_data.get('layers_in_out', {})
        if d:
            techs  = sorted(set(k[1] for k in d))
            layers = sorted(set(k[2] for k in d))
            write_3d_param(f, 'layers_in_out', d, YEARS, techs, layers)

        d = techs_data.get('c_p_t', {})
        if d:
            techs   = sorted(set(k[1] for k in d))
            periods = sorted(set(k[2] for k in d), key=int)
            write_3d_param(f, 'c_p_t', d, YEARS, techs, periods)

        d = techs_data.get('c_op', {})
        if d:
            resources = sorted(set(k[1] for k in d))
            periods   = sorted(set(k[2] for k in d), key=int)
            write_3d_param(f, 'c_op', d, YEARS, resources, periods)

    print(f'  Saved: {out_techs}')

    with open(out_eud, 'w', encoding='utf-8') as f:
        f.write('# End-use demand parameters in matrix format\n')
        f.write('# Generated by write_matrix_dat.py\n\n')

        d = eud_data.get('end_uses_demand_year', {})
        if d:
            layers  = sorted(set(k[1] for k in d))
            sectors = sorted(set(k[2] for k in d))
            write_3d_param(f, 'end_uses_demand_year', d, YEARS, layers, sectors)

    print(f'  Saved: {out_eud}')

    if shares_dir is not None:
        shares_dir = str(shares_dir)
        out_shares = os.path.join(shares_dir, 'out_shares.dat')
        print(f'Loading shares from {shares_dir} ...')
        shares_data = load_shares(shares_dir, YEARS)

        _SCALAR_SHARE_PARAMS = [
            'share_mobility_public_min_sd', 'share_mobility_public_max_sd',
            'share_mobility_public_min_md', 'share_mobility_public_max_md',
            'share_mobility_public_min_ld', 'share_mobility_public_max_ld',
            'share_mobility_public_min_eld', 'share_mobility_public_max_eld',
            'share_public_rail_min_sd',  'share_public_rail_max_sd',
            'share_public_rail_min_md',  'share_public_rail_max_md',
            'share_public_rail_min_ld',  'share_public_rail_max_ld',
            'share_public_rail_min_eld', 'share_public_rail_max_eld',
            'share_public_air_min_ld',   'share_public_air_max_ld',
            'share_public_air_min_eld',  'share_public_air_max_eld',
            'share_freight_rail_min_ld',  'share_freight_rail_max_ld',
            'share_freight_rail_min_eld', 'share_freight_rail_max_eld',
            'share_freight_air_min_eld',  'share_freight_air_max_eld',
            'share_freight_maritime_min_eld', 'share_freight_maritime_max_eld',
            'share_freight_maritime_bulk_carrier',
            'share_freight_maritime_container',
            'share_freight_maritime_oil_tanker',
            'share_public_schoolbus_min_sd', 'share_public_schoolbus_max_sd',
            'share_heat_dhn_min', 'share_heat_dhn_max',
        ]

        with open(out_shares, 'w', encoding='utf-8') as f:
            f.write('# Share parameters in matrix format\n')
            f.write('# Generated by write_matrix_dat.py\n\n')

            for param in _SCALAR_SHARE_PARAMS:
                d = shares_data.get(param, {})
                write_1d_param(f, param, d, yr_vals)

            for param, fill in [('fmin_perc_mob', 0), ('fmax_perc_mob', 1),
                                  ('fmin_perc', 0),     ('fmax_perc', 1)]:
                d = shares_data.get(param, {})
                if not d:
                    continue
                techs = sorted(set(k[1] for k in d))
                write_2d_param(f, param, d, yr_vals, techs, fill=fill)

        print(f'  Saved: {out_shares}')

    print('Done.')


def main():
    if len(sys.argv) != 3:
        print("Usage: python write_matrix_dat.py <techs_dir> <eud_dir>")
        sys.exit(1)
    run(sys.argv[1], sys.argv[2])


if __name__ == '__main__':
    main()
