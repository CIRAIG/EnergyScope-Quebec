"""
Generates PES_data_years_active.dat from out_techs.dat.

years_active[i, p_inst, p] = number of years technology i, installed during phase p_inst,
is active during phase p.

Formula:
    mid_inst    = midpoint year of p_inst
    end_of_life = mid_inst + lifetime[i]
    years_active[i, p_inst, p] = max(0, min(end_of_life, y_stop[p]) - max(mid_inst, y_start[p]))
    If p_inst is after p (mid_inst >= y_stop[p]), set to 0.

OUTPUT:
    PES_data_years_active.dat
"""

import os
import re
import sys

# (label, y_start, y_stop, midpoint)
PHASE_BOUNDS = [
    ('2015_2020', 2015, 2020, 2017.5),
    ('2020_2025', 2020, 2025, 2022.5),
    ('2025_2030', 2025, 2030, 2027.5),
    ('2030_2035', 2030, 2035, 2032.5),
    ('2035_2040', 2035, 2040, 2037.5),
    ('2040_2045', 2040, 2045, 2042.5),
    ('2045_2050', 2045, 2050, 2047.5),
]


def load_lifetimes_from_out_techs(filepath):
    """Parse let lifetime['YEAR_2020','tech'] := val; lines from out_techs.dat.
    Returns {tech: lifetime}.
    """
    lifetime = {}
    pat = re.compile(r"let\s+lifetime\s*\['YEAR_2020'\s*,\s*'([^']+)'\]\s*:=\s*([\d.eE+\-]+)\s*;")
    with open(filepath, 'r', encoding='utf-8', errors='replace') as f:
        for line in f:
            m = pat.search(line)
            if m:
                try:
                    v = float(m.group(2))
                    if v > 0:
                        lifetime[m.group(1)] = v
                except ValueError:
                    pass
    return lifetime


def compute_years_active_row(lifetime, p_inst_mid, p_inst_stop):
    """Compute years_active[p_inst, p] for all p.

    p_inst is considered 'after' p if mid_inst >= y_stop[p], giving 0.
    """
    end_of_life = p_inst_mid + lifetime
    row = {}
    for label, y_start, y_stop, _ in PHASE_BOUNDS:
        if p_inst_mid >= y_stop:
            row[label] = 0.0
        else:
            row[label] = max(0.0, min(end_of_life, y_stop) - max(p_inst_mid, y_start))
    return row


def write_years_active(lifetime_map, output_file):
    """Write param years_active as per-tech [tech,*,*] AMPL blocks to output_file.

    Args:
        lifetime_map: {tech: lifetime_years} dict
        output_file:  path to the output .dat file
    """
    phase_labels = [p for p, _, _, _ in PHASE_BOUNDS]
    col_header = '\t'.join(phase_labels)
    lines = ['param years_active :=\n']
    for tech in sorted(lifetime_map):
        lt = lifetime_map[tech]
        lines.append(f'[{tech}, *, *] :\t{col_header}\t:=\n')
        for p_inst, _, p_inst_stop, p_inst_mid in PHASE_BOUNDS:
            row = compute_years_active_row(lt, p_inst_mid, p_inst_stop)
            vals = '\t'.join(str(row[p]) for p in phase_labels)
            lines.append(f'{p_inst}\t{vals}\n')
    lines.append(';\n')
    with open(output_file, 'w', encoding='utf-8') as f:
        f.writelines(lines)


def run(out_techs_file, years_active_file):
    """Regenerate PES_data_years_active.dat from out_techs.dat.

    Args:
        out_techs_file:    path to ES_Transition_QC_2/Techs/out_techs.dat
        years_active_file: path to write PES_data_years_active.dat
    """
    print(f"Loading lifetimes from: {out_techs_file}")
    lifetime_map = load_lifetimes_from_out_techs(str(out_techs_file))
    print(f"  -> {len(lifetime_map)} technologies found")
    write_years_active(lifetime_map, str(years_active_file))
    print(f"Written: {years_active_file}")


def main():
    if len(sys.argv) != 3:
        print("Usage: python Create_years_active.py <out_techs.dat> <years_active.dat>")
        sys.exit(1)
    run(sys.argv[1], sys.argv[2])


if __name__ == '__main__':
    main()
