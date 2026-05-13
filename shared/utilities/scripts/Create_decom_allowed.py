"""
Create_decom_allowed_file.py

Generates the AMPL decom_allowed .dat file for all technologies
in the transition model, reading lifetimes directly from out_techs.dat.

decom_allowed[phase_now, phase_built, tech] = 1
  when: phase_built < phase_now  AND  (phase_now - phase_built) < lifetime/5
  meaning: the tech is still within its lifetime but can be retired early.

OUTPUT:
    <pathway_dir>/PES_data_decom_allowed_2020.dat
"""

import os
import re
import sys

PHASES = [
    '2015_2020', '2020_2025', '2025_2030', '2030_2035',
    '2035_2040', '2040_2045', '2045_2050'
]


def load_lifetimes_from_out_techs(filepath):
    """
    Parse the param lifetime matrix block from out_techs.dat.
    Returns {tech: lifetime} using YEAR_2020 values.
    """
    lifetime = {}
    with open(filepath, 'r', encoding='utf-8', errors='replace') as f:
        lines = f.readlines()

    # Find the lifetime block
    start = None
    for i, line in enumerate(lines):
        if 'param lifetime' in line:
            start = i
            break
    if start == -1 or start is None:
        raise ValueError("Could not find 'param lifetime' block in " + filepath)

    # Extract block
    block = []
    for line in lines[start:]:
        block.append(line.strip())
        if ';' in line:
            break

    # Header (robust split)
    header = block[0]
    header = header.replace('param lifetime', '').replace(':', '').replace(':=', '')
    techs = re.split(r'\s+', header.strip())

    # YEAR_2020 row (robust split)
    for line in block[1:]:
        if line.startswith('YEAR_2020'):
            values = re.split(r'\s+', line.strip())
            for tech, val in zip(techs, values[1:]):
                try:
                    lifetime[tech] = float(val)
                except ValueError:
                    pass
            break

    return lifetime


def generate_decom_allowed(lifetime, phases):
    """
    For each tech, generate all (phase_now, phase_built) pairs where:
      - phase_built comes before phase_now
      - elapsed phases < lifetime / 5
    """
    lines = []
    for tech in sorted(lifetime.keys()):
        lt = lifetime[tech]
        if lt <= 0:
            continue
        max_phases = lt / 5.0

        for i, phase_now in enumerate(phases):
            for j, phase_built in enumerate(phases):
                if j >= i:
                    continue
                diff = i - j
                if diff < max_phases:
                    lines.append(
                        f"\tlet decom_allowed ['{phase_now}' , '{phase_built}' , '{tech}'] := 1;"
                    )
    return lines


def run(out_techs_file, output_file):
    """Regenerate PES_data_decom_allowed_2020.dat from out_techs.dat.

    Args:
        out_techs_file: path to ES_Transition_QC_2/Techs/out_techs.dat
        output_file:    path to write the output decom_allowed .dat file
    """
    print(f"Loading lifetimes from: {out_techs_file}")
    lifetime = load_lifetimes_from_out_techs(str(out_techs_file))
    print(f"  -> {len(lifetime)} technologies found\n")

    lines = generate_decom_allowed(lifetime, PHASES)
    print(f"Generated {len(lines)} decom_allowed entries for {len(lifetime)} techs")

    with open(str(output_file), 'w') as f:
        f.write('\n'.join(lines) + '\n')
    print(f"Output written to: {output_file}")


def main():
    if len(sys.argv) != 3:
        print("Usage: python Create_decom_allowed.py <out_techs.dat> <decom_allowed.dat>")
        sys.exit(1)
    run(sys.argv[1], sys.argv[2])


if __name__ == '__main__':
    main()
