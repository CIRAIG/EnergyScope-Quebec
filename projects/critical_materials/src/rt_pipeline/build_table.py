"""Assemble the long-format "recycling_materials_technologies" (competing
recycling processes) table and write ampl_files/Material_recycling_process.dat
-- kept separate from rr_pipeline's Material_recycling.dat (Approach 1) and
from every Approach-1 param name, so the two approaches never mix (see
run_pathway_materials.py's materials_recycling_process kwarg).

Recycling_cost's cost [MCAD/GW of source tech processed] and revenue
[MCAD/kt of material recovered] use different units than
Constraints_recycling_technologies.mod's recycling_cost_process/
recycling_benefit_process [$/t of material] -- both are converted here using
each AMPL tech's own material_intensity [t/GW] (from mi_pipeline, the same
numbers already driving Material_intensity.dat), not a value assumed by the
Excel sheet's author.
"""
import time
from pathlib import Path

import pandas as pd

from mi_pipeline.aggregate import YEARS, compute_all as compute_material_intensities

from . import sources

_PROJ_ROOT = Path(__file__).resolve().parents[2]  # .../projects/critical_materials
OUT_DAT_PATH = _PROJ_ROOT / 'ampl_files' / 'Material_recycling_process.dat'


def _techs_for_label(label, source_sheet):
    techs = sources.TECHNOLOGY_LABEL_TO_TECHS.get(label)
    if techs is None:
        raise ValueError(f"{source_sheet} has Technology {label!r} with no entry in "
                          f"sources.TECHNOLOGY_LABEL_TO_TECHS -- add one (see PV_C_SI_TECHS/"
                          f"EV_BATTERY_TECHS for the pattern)")
    return techs


def _recovery_rate_rows():
    """Long-format (tech, material, process, stream, recovery_rate) rows for every
    technology block in Recycling_technologies, expanded to that block's own
    EnergyScope techs (sources.TECHNOLOGY_LABEL_TO_TECHS) -- same recovery_rate
    value for every tech sharing a block (they share the same underlying
    module/panel/pack type) and every YEAR (Recycling_technologies has no year axis)."""
    rt = sources.load_recycling_technologies()
    rows = []
    for _, row in rt.iterrows():
        for tech in _techs_for_label(row['technology'], 'Recycling_technologies'):
            rows.append((tech, row['material'], row['process'], row['stream'], row['recovery_rate']))
    return rows


def _cost_benefit_rows(material_intensities):
    """Long-format (tech, material, process, recycling_cost_process[$/t],
    recycling_benefit_process[$/t]) rows, converted from Recycling_cost's
    per-GW-of-source-tech units using each row's own EnergyScope techs' own
    material_intensity (t/GW, constant across years for 'direct'-mapped rows
    -- any year works as the reference).

    recycling_cost_process is a property of the PROCESS, not of which metal
    happens to be recovered -- a recycler charges to run a batch through
    Pyrometallurgical/Hydrometallurgical/whatever, not per element extracted
    from it. The sheet still stores one 'Recycling cost' figure per (Technology,
    Sub-technology, Metal, process) row -- because it's most naturally sourced
    per metal (see e.g. the PV Aluminum/Mechanical row's $922/t-of-aluminum
    reference) -- so after converting each row to $/t individually, this
    collapses every row sharing a (tech, process) down to one cost (the first
    one found; raises if rows meant to share a process disagree once
    converted, which would mean the sheet's per-metal $/t figures are
    genuinely inconsistent, not just an artifact of the MCAD/GW conversion).
    recycling_benefit_process stays per-material -- market value legitimately
    differs by what's recovered."""
    cost_df = sources.load_recycling_cost()

    converted = []
    for _, row in cost_df.iterrows():
        mat, proc = row['material'], row['process']
        for tech in _techs_for_label(row['Technology'], 'Recycling_cost'):
            mi = material_intensities[tech]
            mi_t_per_gw = mi.loc[mat, YEARS[0]] if mat in mi.index else 0
            if not mi_t_per_gw or pd.isna(mi_t_per_gw):
                continue  # can't derive a $/t figure with zero t/GW to divide by
            cost_dollar_per_t = row['Recycling cost'] * 1e6 / mi_t_per_gw       # MCAD/GW -> $/t
            benefit_dollar_per_t = row['Revenue'] * 1000                        # MCAD/kt -> $/t
            converted.append((tech, mat, proc, cost_dollar_per_t, benefit_dollar_per_t))

    cost_by_tech_proc = {}
    for tech, mat, proc, cost, _benefit in converted:
        key = (tech, proc)
        if key not in cost_by_tech_proc:
            cost_by_tech_proc[key] = cost
        elif abs(cost_by_tech_proc[key] - cost) > 1e-6 * max(abs(cost), 1):
            raise ValueError(f"Recycling_cost gives inconsistent costs for {tech!r}/{proc!r}: "
                              f"{cost_by_tech_proc[key]:.4g} $/t vs {cost:.4g} $/t (from {mat!r}) "
                              f"-- recycling_cost_process is a per-process figure, every material "
                              f"under the same (Technology, process) must agree once converted")

    rows = [(tech, mat, proc, cost_by_tech_proc[(tech, proc)], benefit)
            for tech, mat, proc, _cost, benefit in converted]
    return rows


def _collection_rate_rows():
    """Long-format (year, tech, stream, rate) rows for collection_rate_process
    -- one shared rate per (tech, stream), not per material (see
    sources.load_collection_rate), expanded to each technology block's own
    EnergyScope techs."""
    by_tech_label = sources.load_collection_rate()
    rows = []
    for technology, by_stream in by_tech_label.items():
        for tech in _techs_for_label(technology, 'Collection_rate'):
            for stream, year_rates in by_stream.items():
                for year_int, rate in year_rates.items():
                    rows.append((f'YEAR_{year_int}', tech, stream, rate))
    return rows


def _write_dat(recovery_rows, cbe_rows, collection_rows, path=OUT_DAT_PATH):
    # RECYCLING_STREAM_OF/RECYCLING_PROCESS_OF_STREAM gate Capacity_recycled's domain;
    # RECYCLING_PROCESS_OF gates Recycled_material_process's -- all grouped here (one
    # assignment per tech/stream/material pair, since AMPL sets can only be assigned once).
    processes_by_tech_mat = {}
    streams_by_tech = {}
    processes_by_tech_stream = {}
    for tech, mat, proc, stream, _rate in recovery_rows:
        processes_by_tech_mat.setdefault((tech, mat), []).append(proc)
        streams_by_tech.setdefault(tech, [])
        if stream not in streams_by_tech[tech]:
            streams_by_tech[tech].append(stream)
        processes_by_tech_stream.setdefault((tech, stream), [])
        if proc not in processes_by_tech_stream[(tech, stream)]:
            processes_by_tech_stream[(tech, stream)].append(proc)

    with open(path, 'w', encoding='utf-8', newline='\n') as f:
        f.write("data;\n\n")
        f.write("# Auto-generated by rt_pipeline (run_build_rt.py) from Recycling_rates.xlsx -- do not hand-edit.\n")
        f.write("# 'recycling_materials_technologies' approach -- entirely separate from Material_recycling.dat\n")
        f.write("# (the simple-rate approach). No set MATERIALS/RECYCLING_PROCESS/RECYCLING_STREAM header here --\n")
        f.write("# already declared in Constraints.mod / Constraints_recycling_technologies.mod.\n\n")

        f.write("# RECYCLING_STREAM_OF / RECYCLING_PROCESS_OF_STREAM: which processes compete for the same\n")
        f.write("# physical batch, grouped by stream (MODULE vs INFRASTRUCTURE) -- see build_table.py docstring.\n")
        for tech, streams in streams_by_tech.items():
            stream_list = ', '.join(f"'{s}'" for s in streams)
            f.write(f"let RECYCLING_STREAM_OF['{tech}'] := {{{stream_list}}} ;\n")
            for stream in streams:
                procs = processes_by_tech_stream[(tech, stream)]
                proc_list = ', '.join(f"'{p}'" for p in procs)
                f.write(f"let RECYCLING_PROCESS_OF_STREAM['{tech}','{stream}'] := {{{proc_list}}} ;\n")

        f.write("\n# RECYCLING_PROCESS_OF: which processes are eligible per (tech, material)\n")
        for (tech, mat), procs in processes_by_tech_mat.items():
            proc_list = ', '.join(f"'{p}'" for p in procs)
            f.write(f"let RECYCLING_PROCESS_OF['{tech}','{mat}'] := {{{proc_list}}} ;\n")

        f.write("\n# recovery rate, same value for every YEAR (no year axis in Recycling_technologies)\n")
        for tech, mat, proc, _stream, rate in recovery_rows:
            for year in YEARS:
                f.write(f"let recovery_rate_process['{tech}','{mat}','{proc}'] := {rate} ;\n")

        f.write("\n# collection rate, per (tech, stream) -- shared by every material of that stream\n")
        for year, tech, stream, rate in collection_rows:
            f.write(f"let collection_rate_process['{year}','{tech}','{stream}'] := {rate} ;\n")

        f.write("\n# cost [$/t] / revenue [$/t] -- converted from Recycling_cost's per-GW-of-source-tech\n")
        f.write("# units using this tech's own material_intensity (see build_table.py)\n")
        for tech, mat, proc, cost, benefit in cbe_rows:
            f.write(f"let recycling_cost_process['{tech}','{mat}','{proc}'] := {cost} ;\n")
            f.write(f"let recycling_benefit_process['{mat}','{proc}'] := {benefit} ;\n")
    return path


def build(write_dat=True):
    """Processes every technology block found in the sheets (see
    sources.TECHNOLOGY_LABEL_TO_TECHS) -- adding a new one is purely a data
    change (fill in the sheets, add one dict entry), no code change needed."""
    t0 = time.time()

    material_intensities = compute_material_intensities()
    print(f"[rt_build_table] loaded material intensities in {time.time()-t0:.1f}s")

    recovery_rows = _recovery_rate_rows()
    cbe_rows = _cost_benefit_rows(material_intensities)
    collection_rows = _collection_rate_rows()
    print(f"[rt_build_table] built {len(recovery_rows)} recovery-rate rows, {len(cbe_rows)} cost/revenue rows, "
          f"{len(collection_rows)} collection-rate rows in {time.time()-t0:.1f}s")

    if write_dat:
        out_path = _write_dat(recovery_rows, cbe_rows, collection_rows)
        print(f"[rt_build_table] wrote {out_path.name} in {time.time()-t0:.1f}s")

    print(f"[rt_build_table] total: {time.time()-t0:.1f}s")
    return recovery_rows, cbe_rows, collection_rows


if __name__ == '__main__':
    build()
