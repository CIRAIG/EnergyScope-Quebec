"""
Generates the AMPL AGE .dat file for all QC technologies.

AGE[tech, phase_now] tells the model the renewal status of the stock
installed in 2015_2020 at each subsequent phase:

  - STILL_IN_USE : the 2015_2020 stock is still within its lifetime
  - phase_label  : the 2015_2020 stock has expired; this is the phase when
                   the first renewal of that stock occurs

Rule (phases_wnd indexed from 0 starting at 2025_2030):
  STILL_IN_USE  if  i * 5 < lifetime
  all_phases[i - lifetime//5 + 1]  otherwise

OUTPUT:
    PES_data_set_AGE_2020.dat  (covers phases 2025_2030 -> 2045_2050)
"""

import re
import os
import sys
import math

ALL_PHASES = [
    '2015_2020', '2020_2025', '2025_2030', '2030_2035',
    '2035_2040', '2040_2045', '2045_2050'
]
PHASES_WND = ALL_PHASES


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


def compute_age(lifetime, phases_wnd, all_phases):
    """For each tech and phase, compute AGE value.
    STILL_IN_USE if i*5 < lifetime, else the renewal phase label.
    """
    result = {}
    for tech, lt in sorted(lifetime.items()):
        entries = []
        for i, phase_now in enumerate(phases_wnd):
            if i * 5 < lt:
                entries.append((phase_now, 'STILL_IN_USE'))
            else:
                idx_val = i - math.ceil(lt / 5)
                entries.append((phase_now, all_phases[idx_val]))
        result[tech] = entries
    return result


def write_output(result, output_file):
    """Write AGE set declarations to output_file in AMPL syntax.

    Args:
        result:      {tech: [(phase_now, value), ...]} as returned by compute_age()
        output_file: path to the output .dat file
    """
    lines = []
    for tech, entries in sorted(result.items()):
        for phase_now, val in entries:
            lines.append(f"set AGE ['{tech}','{phase_now}'] := {val} ;")
        lines.append('')
    with open(output_file, 'w') as f:
        f.write('\n'.join(lines) + '\n')


def run(out_techs_file, output_file):
    """Regenerate PES_data_set_AGE_2020.dat from out_techs.dat.

    Args:
        out_techs_file: path to ES_Transition_QC_2/Techs/out_techs.dat
        output_file:    path to write the output AGE .dat file
    """
    print(f"Loading lifetimes from: {out_techs_file}")
    lifetime = load_lifetimes_from_out_techs(str(out_techs_file))
    print(f"  -> {len(lifetime)} technologies found\n")

    result = compute_age(lifetime, PHASES_WND, ALL_PHASES)
    write_output(result, str(output_file))

    total = sum(len(v) for v in result.values())
    print(f"Generated {total} entries for {len(result)} techs")
    print(f"Output written to: {output_file}")


def main():
    if len(sys.argv) != 3:
        print("Usage: python Create_data_set_age_2020.py <out_techs.dat> <output_AGE.dat>")
        sys.exit(1)
    run(sys.argv[1], sys.argv[2])


if __name__ == '__main__':
    main()
