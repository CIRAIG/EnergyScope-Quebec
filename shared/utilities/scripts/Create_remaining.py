"""
Generates PES_data_remaining.dat and PES_data_remaining_wnd.dat from out_techs.dat.

remaining_years[tech, phase] = max(0, lifetime - (HORIZON_END - midpoint_of_phase))

This represents how many years of useful life an asset built in `phase` still has
after the end of the planning horizon (2050), used in the investment return calculation.

Both files contain all 7 phases; the model loads them at different stages of the
rolling-horizon solve.

OUTPUT:
    PES_data_remaining.dat
    PES_data_remaining_wnd.dat
"""

import os
import re
import sys

PHASES = [
    ('2015_2020', 2017.5),
    ('2020_2025', 2022.5),
    ('2025_2030', 2027.5),
    ('2030_2035', 2032.5),
    ('2035_2040', 2037.5),
    ('2040_2045', 2042.5),
    ('2045_2050', 2047.5),
]
HORIZON_END = 2050


def load_lifetimes_from_out_techs(filepath):
    """Parse the param lifetime matrix block from out_techs.dat.
    Returns {tech: lifetime} using YEAR_2020 values.
    """
    lifetime = {}
    with open(filepath, 'r', encoding='utf-8', errors='replace') as f:
        lines = f.readlines()

    start = None
    for i, line in enumerate(lines):
        if 'param lifetime' in line:
            start = i
            break
    if start is None:
        raise ValueError("Could not find 'param lifetime' block in " + filepath)

    block = []
    for line in lines[start:]:
        block.append(line.strip())
        if ';' in line:
            break

    header = block[0].replace('param lifetime', '').replace(':', '').replace(':=', '')
    techs = re.split(r'\s+', header.strip())

    for line in block[1:]:
        if line.startswith('YEAR_2020'):
            values = re.split(r'\s+', line.strip())
            for tech, val in zip(techs, values[1:]):
                try:
                    v = float(val)
                    if v > 0:
                        lifetime[tech] = v
                except ValueError:
                    pass
            break

    return lifetime


def compute_remaining(lifetime):
    """Compute remaining_years for each phase."""
    return {phase: max(0.0, lifetime - (HORIZON_END - mid)) for phase, mid in PHASES}


def write_remaining(lifetime_map, output_file):
    """Write param remaining_years as an AMPL matrix table to output_file.

    Args:
        lifetime_map: {tech: lifetime_years} dict
        output_file:  path to the output .dat file
    """
    phase_labels = [p for p, _ in PHASES]
    header = 'param remaining_years :\t' + '\t'.join(phase_labels) + '\t:=\n'
    rows = []
    for tech in sorted(lifetime_map):
        rem = compute_remaining(lifetime_map[tech])
        vals = '\t'.join(str(rem[p]) for p in phase_labels)
        rows.append(f'{tech}\t{vals}')
    body = '\n'.join(rows)
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(header + body + '\n;\n')


def run(out_techs_file, remaining_file, remaining_wnd_file):
    """Regenerate both remaining_years dat files from out_techs.dat.

    Args:
        out_techs_file:     path to ES_Transition_QC_2/Techs/out_techs.dat
        remaining_file:     path to write PES_data_remaining.dat
        remaining_wnd_file: path to write PES_data_remaining_wnd.dat
    """
    print(f"Loading lifetimes from: {out_techs_file}")
    lifetime_map = load_lifetimes_from_out_techs(str(out_techs_file))
    print(f"  -> {len(lifetime_map)} technologies found")

    write_remaining(lifetime_map, str(remaining_file))
    print(f"Written: {remaining_file}")

    write_remaining(lifetime_map, str(remaining_wnd_file))
    print(f"Written: {remaining_wnd_file}")


def main():
    if len(sys.argv) != 4:
        print("Usage: python Create_remaining.py <out_techs.dat> <remaining.dat> <remaining_wnd.dat>")
        sys.exit(1)
    run(sys.argv[1], sys.argv[2], sys.argv[3])


if __name__ == '__main__':
    main()
