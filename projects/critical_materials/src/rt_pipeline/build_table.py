"""Assemble the long-format Approach-2 (competing recycling processes) table
and write ampl_files/Material_recycling_process.dat -- kept separate from
rr_pipeline's Material_recycling.dat (Approach 1) so the two can be loaded
independently for a side-by-side comparison run (see run_pathway_materials.py's
materials_recycling_process kwarg).

Recycling_cost's cost [MCAD/GW of source tech processed] and revenue
[MCAD/kt of material recovered] use different units than Constraints.mod's
recycling_cost/recycling_benefit [$/t of material] -- both are converted
here using each AMPL tech's own material_intensity [t/GW] (from
mi_pipeline, the same numbers already driving Material_intensity.dat), not
a value assumed by the Excel sheet's author. Electricity_use's energy
[GWh/GW] is converted the same way, to [GWh/t].
"""
import time
from pathlib import Path

import pandas as pd

from mi_pipeline.aggregate import YEARS, compute_all as compute_material_intensities

from . import sources

_PROJ_ROOT = Path(__file__).resolve().parents[2]  # .../projects/critical_materials
OUT_DAT_PATH = _PROJ_ROOT / 'ampl_files' / 'Material_recycling_process.dat'

INFRASTRUCTURE_PROCESS = 'PV_INFRASTUCTURE'  # from sources.load_recycling_technologies, matches the sheet's own spelling


def _cost_benefit_energy_rows(techs, material_intensities):
    """Long-format (tech, material, process, recycling_cost[$/t],
    recycling_energy_elec[GWh/t], recycling_benefit[$/t]) rows, converted
    from Recycling_cost/Electricity_use's per-GW-of-source-tech units using
    `techs`' own material_intensity (t/GW, constant across years for the
    'direct'-mapped PV c-Si rows -- any year works as the reference)."""
    cost_df = sources.load_recycling_cost()
    energy_df = sources.load_electricity_use()

    rows = []
    for tech in techs:
        mi = material_intensities[tech]
        for _, row in cost_df.iterrows():
            mat, proc = row['material'], row['process']
            mi_t_per_gw = mi.loc[mat, YEARS[0]] if mat in mi.index else 0
            if not mi_t_per_gw or pd.isna(mi_t_per_gw):
                continue  # can't derive a $/t figure with zero t/GW to divide by
            cost_dollar_per_t = row['Recycling cost'] * 1e6 / mi_t_per_gw       # MCAD/GW -> $/t
            benefit_dollar_per_t = row['Revenue'] * 1000                        # MCAD/kt -> $/t
            energy_match = energy_df[(energy_df['material'] == mat) & (energy_df['process'] == proc)]
            energy_gwh_per_t = (energy_match['Recycling cost'].iloc[0] / mi_t_per_gw) if not energy_match.empty else 0.0
            rows.append((tech, mat, proc, cost_dollar_per_t, energy_gwh_per_t, benefit_dollar_per_t))
    return rows


def _recovery_rate_rows(techs):
    """Long-format (tech, material, process, recovery_rate) rows, unchanged
    (already a dimensionless fraction) -- same value for every AMPL tech in
    `techs` (they share the same underlying module/panel type) and every
    YEAR (Recycling_technologies has no year axis)."""
    rt = sources.load_recycling_technologies()
    rows = []
    for tech in techs:
        for _, row in rt.iterrows():
            rows.append((tech, row['material'], row['process'], row['recovery_rate']))
    return rows


def _min_collection_rows(techs, recovery_rows):
    """Long-format (year, tech, material, share) rows for min_collection_rate,
    from Recycling_scenario_technologies -- the two named subtech rows map to
    one material each (sources.SCENARIO_TECH_ROW_TO_MATERIAL), the
    "PV_infrastructure" row broadcasts to every material the infrastructure
    process covers, Concrete included -- but its share is clipped to its own
    max achievable recovery rate (0.0 under PV_INFRASTUCTURE, i.e. "not
    recoverable this way"), written out explicitly as 0 rather than silently
    omitted, so it's visible in Material_recycling_process.dat that this was
    a deliberate choice, not a gap. Forcing an unclipped 0.9 floor on it
    would directly contradict recycled_material_max's ceiling and make the
    model infeasible -- see also _validate_floors_against_ceilings, which
    still catches any other (tech, material) this clipping doesn't cover."""
    scenario = sources.load_recycling_scenario_technologies()
    rt = sources.load_recycling_technologies()
    infra_materials = sorted(rt.loc[rt['process'] == INFRASTRUCTURE_PROCESS, 'material'].unique())

    max_rate = {}
    for tech, mat, _proc, rate in recovery_rows:
        max_rate[(tech, mat)] = max_rate.get((tech, mat), 0.0) + rate

    rows = []
    for row_label, year_values in scenario.iterrows():
        row_label = row_label.strip()
        if row_label in sources.SCENARIO_TECH_ROW_TO_MATERIAL:
            materials = [sources.SCENARIO_TECH_ROW_TO_MATERIAL[row_label]]
        elif 'infrastru' in row_label.lower():  # sheet has a typo ("infrastruture"), match loosely
            materials = infra_materials
        else:
            print(f"[rt_build_table] skipping unrecognized Recycling_scenario_technologies row: {row_label!r}")
            continue
        for year_int, share in year_values.items():
            if pd.isna(share):
                continue
            for tech in techs:
                for mat in materials:
                    clipped = min(float(share), max_rate.get((tech, mat), 0.0))
                    if clipped < float(share):
                        print(f"[rt_build_table] clipping min_collection_rate['{tech}','{mat}'] "
                              f"from {share} to {clipped} (max achievable recovery rate)")
                    rows.append((f'YEAR_{year_int}', tech, mat, clipped))
    return rows


def _write_dat(recovery_rows, cbe_rows, min_collection_rows, path=OUT_DAT_PATH):
    # RECYCLING_PROCESS_OF[tech,material] gates Recycled_material's domain in Constraints.mod --
    # grouped here (all processes for a (tech,material) pair in one assignment, since AMPL sets
    # can only be assigned once) rather than repeated per recovery_rows row.
    processes_by_tech_mat = {}
    for tech, mat, proc, _rate in recovery_rows:
        processes_by_tech_mat.setdefault((tech, mat), []).append(proc)

    with open(path, 'w', encoding='utf-8', newline='\n') as f:
        f.write("data;\n\n")
        f.write("# Auto-generated by rt_pipeline (run_build_rt.py) from Recycling_rates.xlsx -- do not hand-edit.\n")
        f.write("# Approach 2 (competing recycling processes) -- see Material_recycling.dat (Approach 1,\n")
        f.write("# process 'DEFAULT') for the simple-rate counterpart. No set MATERIALS/RECYCLING_PROCESS\n")
        f.write("# header here -- both already declared (Material_intensity.dat / Constraints.mod).\n\n")

        f.write("# RECYCLING_PROCESS_OF: which processes are eligible per (tech, material)\n")
        for (tech, mat), procs in processes_by_tech_mat.items():
            proc_list = ', '.join(f"'{p}'" for p in procs)
            f.write(f"let RECYCLING_PROCESS_OF['{tech}','{mat}'] := {{{proc_list}}} ;\n")

        f.write("\n# recovery rate, same value for every YEAR (no year axis in Recycling_technologies)\n")
        for tech, mat, proc, rate in recovery_rows:
            for year in YEARS:
                f.write(f"let recycling_rate['{year}','{tech}','{mat}','{proc}'] := {rate} ;\n")

        f.write("\n# cost [$/t] / energy [GWh/t] / revenue [$/t] -- converted from Recycling_cost/Electricity_use's\n")
        f.write("# per-GW-of-source-tech units using this tech's own material_intensity (see build_table.py)\n")
        for tech, mat, proc, cost, energy, benefit in cbe_rows:
            f.write(f"let recycling_cost['{tech}','{mat}','{proc}'] := {cost} ;\n")
            if energy:
                f.write(f"let recycling_energy_elec['{tech}','{mat}','{proc}'] := {energy} ;\n")
            f.write(f"let recycling_benefit['{mat}','{proc}'] := {benefit} ;\n")

        f.write("\n# minimum-collection-rate floor (Recycling_scenario_technologies)\n")
        for year, tech, mat, share in min_collection_rows:
            f.write(f"let min_collection_rate['{year}','{tech}','{mat}'] := {share} ;\n")
    return path


def _validate_floors_against_ceilings(recovery_rows, min_collection_rows):
    """The min_collection_rate floor (sum over processes) must not exceed the
    max achievable recovery rate (sum over processes) for the same
    (tech, material), or recycled_material_max's ceiling makes the model
    infeasible. Raises with a clear message instead of writing infeasible
    data silently."""
    max_rate = {}
    for tech, mat, _proc, rate in recovery_rows:
        max_rate[(tech, mat)] = max_rate.get((tech, mat), 0.0) + rate
    problems = [
        f"{tech}/{mat}: floor {share} > max achievable {max_rate.get((tech, mat), 0.0)} (year {year})"
        for year, tech, mat, share in min_collection_rows
        if share > max_rate.get((tech, mat), 0.0)
    ]
    if problems:
        raise ValueError("min_collection_rate exceeds the achievable recovery rate for:\n  " + "\n  ".join(problems))


def build(write_dat=True):
    t0 = time.time()
    techs = sources.PV_C_SI_TECHS

    material_intensities = compute_material_intensities()
    print(f"[rt_build_table] loaded material intensities in {time.time()-t0:.1f}s")

    recovery_rows = _recovery_rate_rows(techs)
    cbe_rows = _cost_benefit_energy_rows(techs, material_intensities)
    min_collection_rows = _min_collection_rows(techs, recovery_rows)
    print(f"[rt_build_table] built {len(recovery_rows)} recovery-rate rows, {len(cbe_rows)} cost/energy/revenue "
          f"rows, {len(min_collection_rows)} floor rows in {time.time()-t0:.1f}s")

    _validate_floors_against_ceilings(recovery_rows, min_collection_rows)

    if write_dat:
        out_path = _write_dat(recovery_rows, cbe_rows, min_collection_rows)
        print(f"[rt_build_table] wrote {out_path.name} in {time.time()-t0:.1f}s")

    print(f"[rt_build_table] total: {time.time()-t0:.1f}s")
    return recovery_rows, cbe_rows, min_collection_rows


if __name__ == '__main__':
    build()
