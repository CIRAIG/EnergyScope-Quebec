"""Assemble the long-format recycling-rate table and write
ampl_files/Material_recycling.dat -- recycling-rate counterpart to
mi_pipeline/build_table.py.

Every technology in Recycling_rates.xlsx's Mapping sheet is recomputed on
every run, per (tech, material) cell: the tech-specific literature rate
(RR_Energy/RR_Vehicles/RR_Vehicles_Public/RR_H2, via the Mapping sheet) is
used wherever it has a value, and RR_Global's material-level rate is the
fallback for every cell that doesn't -- whether because the tech has no
mapping at all, or because it's mapped but the mapped source column simply
doesn't cover that particular material yet (e.g. wind, mapped to a single
Sol_*/Wind_* column with only 1 of 41 materials filled in so far -- see
_rate_rows). A single simple recycling_rate per (tech, material) -- plus
recycling_objective_share (the recycled_material_objective equality's target,
from the Recycling_objective sheet, clipped to each material's actual
achievable rate, see _max_achievable_rate) and recycling_cost/primary_material_cost
(Cost_recycling_global/Cost_material_global sheets, material-level, broadcast
only to techs that actually contain that material -- see _cost_rows/
_primary_cost_rows and sources.load_rr_costs). `collection_rate` /
`recycling_gwp` / `disposal_gwp` have no source data yet -- none of them are
written here, so they stay at their AMPL defaults (collection_rate=1, rest=0)
unless a future source sheet is added and this module is extended to cover
them. disposal_cost defaults to 50 (a generic estimate -- Cost_disposal_global
has no data yet; the previous 0.01 default, chosen to "force" free recycling
in an earlier cost-free iteration, created a numerically tiny coefficient
next to recycling_cost/primary_material_cost values up to ~200k $/t once
folded into C_material, degrading solver conditioning).
"""
import re
import time
from pathlib import Path

import pandas as pd

from mi_pipeline import canonical
from mi_pipeline.mapping import load_mapping

from . import sources
from .aggregate import YEARS, compute_all

_PROJ_ROOT = Path(__file__).resolve().parents[2]  # .../projects/critical_materials
OUT_DAT_PATH = _PROJ_ROOT / 'ampl_files' / 'Material_recycling.dat'
_MI_DAT_PATH = _PROJ_ROOT / 'ampl_files' / 'Material_intensity.dat'
_MI_LET_RE = re.compile(r"let material_intensity\['[^']+','([^']+)','([^']+)'\]\s*:=\s*([0-9.eE+-]+)")


def _rate_rows(mapping, rates, global_rates, canonical_techs):
    """Long-format (year, tech, material, value, comment) rows for every
    technology in canonical_techs scope (a tech outside it would make AMPL
    choke on an out-of-set subscript when Material_recycling.dat is loaded).
    Per (tech, material) cell: the mapped literature rate wins whenever it
    has a value; RR_Global's material-level rate (sources.load_rr_global)
    fills every cell that doesn't -- not_mapped techs (no value anywhere) and
    partially-mapped techs (e.g. wind, real data for only 1 of 41 materials)
    are handled identically here, cell by cell."""
    rows = []
    fallback_comment = "RR_Global fallback (Graedel et al. 2022, first of 3 literature sources)"
    for tech, row in mapping.iterrows():
        if tech not in canonical_techs:
            continue
        is_mapped = row['mapping_type'] != 'not_mapped'
        df = rates[tech] if is_mapped else None
        if is_mapped:
            subtechs = ','.join(row['subtechs'])
            confidence_tag = f"[{row['confidence']}] " if row['confidence'] else ''
            specific_comment = f"{confidence_tag}mapping: {row['mapping_type']} <- {subtechs}. See the Mapping sheet."
        for material in global_rates.keys() | (set(df.index) if is_mapped else set()):
            for year in YEARS:
                raw_value = df.loc[material, year] if (is_mapped and material in df.index) else float('nan')
                if pd.notna(raw_value):
                    rows.append((year, tech, material, float(raw_value), specific_comment))
                elif material in global_rates:
                    rows.append((year, tech, material, global_rates[material], fallback_comment))
    return rows


def _max_achievable_rate(mapped_rows):
    """{(year, material): max recycling_rate across technologies} -- the
    aggregate value recycled_material_objective can hit exactly (a weighted average
    across technologies can never exceed the best technology's own rate), used
    to clip recycling_objective_share below so follow_objective=True can't force
    an infeasible floor on materials with little or no RR_ data."""
    best = {}
    for year, _tech, material, value, _comment in mapped_rows:
        key = (year, material)
        if value > best.get(key, 0.0):
            best[key] = value
    return best


def _objective_rows(objective_df, max_rate_by_year_mat):
    """Long-format (year, material, value) rows for recycling_objective_share,
    from the Recycling_objective sheet -- only the years actually present as
    columns (2025..2050 today, no 2020). Clipped to max_rate_by_year_mat[year,
    material] (0 if the material has no RR_ data at all for that year) --
    the raw sheet is dummy placeholder values applied uniformly to every
    material, most of which have no real recycling_rate to back them up."""
    rows = []
    for material in objective_df.index:
        for year_int in objective_df.columns:
            raw_value = objective_df.loc[material, year_int]
            if pd.isna(raw_value):
                continue
            year = f'YEAR_{year_int}'
            ceiling = max_rate_by_year_mat.get((year, material), 0.0)
            value = min(float(raw_value), ceiling)
            if value < raw_value:
                print(f"[rr_build_table] clipping recycling_objective_share[{year},{material}] "
                      f"{raw_value} -> {value} (max achievable recycling_rate)")
            rows.append((year, material, value))
    return rows


def _techs_with_material(path=_MI_DAT_PATH):
    """{material: set(techs)} for every (tech, material) pair with a nonzero
    material_intensity anywhere in Material_intensity.dat -- used to scope
    recycling_cost to only the techs that actually contain a given material.
    Writing recycling_cost broadcast to EVERY tech in scope regardless of
    relevance (the original approach) put huge, physically-meaningless
    coefficients (e.g. Germanium's ~$2M/t) on thousands of (tech,material)
    variables that are structurally always 0 anyway (Decommissioned_material=0
    for that combo) -- confirmed via an isolation test to wreck Gurobi's
    numerical conditioning for the whole MIP (6447 unrelated binary storage
    variables elsewhere in the model) enough to produce a degenerate,
    single-year-concentrated solution instead of a sensible one spread across
    the horizon. Scoping to only relevant (tech,material) pairs keeps the
    coefficient matrix sparse and physically meaningful."""
    result = {}
    with open(path, encoding='utf-8') as f:
        for line in f:
            m = _MI_LET_RE.match(line)
            if m is None:
                continue
            tech, material, value = m.group(1), m.group(2), float(m.group(3))
            if value > 0:
                result.setdefault(material, set()).add(tech)
    return result


def _cost_rows(canonical_techs, costs, techs_with_material):
    """(tech, material, recycling_cost) rows -- only for techs that actually
    contain that material (see _techs_with_material), broadcasting
    Cost_recycling_global's material-level recycling cost to each of them.
    Only materials with a nonzero cost are written; the rest stay at AMPL's
    recycling_cost default (0)."""
    rows = []
    for material, (recycling_cost, _primary_cost) in costs.items():
        if recycling_cost <= 0:
            continue
        relevant_techs = techs_with_material.get(material, set()) & canonical_techs
        for tech in sorted(relevant_techs):
            rows.append((tech, material, recycling_cost))
    return rows


def _primary_cost_rows(costs):
    """(material, primary_material_cost) rows -- material-level only, no tech
    axis (primary_material_cost {MATERIALS} in Constraints.mod)."""
    return [(material, primary_cost) for material, (_rc, primary_cost) in costs.items() if primary_cost > 0]


def _disposal_cost_rows(disposal_costs):
    """(material, disposal_cost) rows -- material-level only, no tech axis
    (disposal_cost {MATERIALS} in Constraints.mod). Empty today (see
    sources.load_disposal_costs), ready for whenever the Cost_disposal_global
    sheet gets real data."""
    return [(material, value) for material, value in disposal_costs.items() if value > 0]


def _write_dat(rows, objective_rows, cost_rows, primary_cost_rows, disposal_cost_rows, path=OUT_DAT_PATH):
    """`let recycling_rate['YEAR_XXXX','TECH','MAT'] := value ; # comment`,
    `let recycling_objective_share['YEAR_XXXX','MAT'] := value ;`,
    `let recycling_cost['TECH','MAT'] := value ;`,
    `let primary_material_cost['MAT'] := value ;` and
    `let disposal_cost['MAT'] := value ;` lines -- no
    `set MATERIALS := ...;` header, since Material_intensity.dat (loaded
    earlier in shared.utils.run_pathway (materials=True)'s file list) already declares it and
    AMPL sets shouldn't be redeclared."""
    with open(path, 'w', encoding='utf-8', newline='\n') as f:
        f.write("data;\n\n")
        f.write("# Auto-generated by rr_pipeline (run_build_rr.py) from Recycling_rates.xlsx -- do not hand-edit.\n")
        f.write("# collection_rate / recycling_gwp / disposal_gwp are NOT written here (no source data yet)\n")
        f.write("# -- AMPL defaults apply (collection_rate=1, rest=0). disposal_cost defaults to 50 unless\n")
        f.write("# overridden below (Cost_disposal_global sheet).\n\n")
        for year, tech, material, value, comment in rows:
            f.write(f"let recycling_rate['{year}','{tech}','{material}'] := {value} ; # [-] {comment}\n")
        f.write("\n# recycled_material_objective's target when follow_objective=1 (Recycling_objective sheet).\n")
        for year, material, value in objective_rows:
            f.write(f"let recycling_objective_share['{year}','{material}'] := {value} ; # [-]\n")
        f.write("\n# recycling_cost[tec,mat] (Cost_recycling_global sheet, material-level broadcast to every tech in scope).\n")
        for tech, material, value in cost_rows:
            f.write(f"let recycling_cost['{tech}','{material}'] := {value} ; # [$/t]\n")
        f.write("\n# primary_material_cost[mat] (Cost_material_global sheet, avoided cost of virgin material when recycling).\n")
        for material, value in primary_cost_rows:
            f.write(f"let primary_material_cost['{material}'] := {value} ; # [$/t]\n")
        f.write("\n# disposal_cost[mat] (Cost_disposal_global sheet, overrides the 50 AMPL default).\n")
        for material, value in disposal_cost_rows:
            f.write(f"let disposal_cost['{material}'] := {value} ; # [$/t]\n")
    return path


def build(scenario='baseline', write_dat=True):
    t0 = time.time()
    mapping = load_mapping(path=sources.SOURCE_XLSX)

    # Same not-yet-in-QC_data.dat filtering as mi_pipeline.build_table.build.
    canonical_techs = set(canonical.all_target_techs())
    claims_real_data = mapping['mapping_type'] != 'not_mapped'
    not_yet_modeled = set(mapping.index[claims_real_data]) - canonical_techs
    if not_yet_modeled:
        print(f"[rr_build_table] skipping (not yet in QC_data.dat): {sorted(not_yet_modeled)}")
    mapped_scope = set(mapping.index) - not_yet_modeled
    mapping = mapping.loc[sorted(mapped_scope)]

    rates = compute_all(scenario=scenario)
    print(f"[rr_build_table] computed {len(rates)} tech recycling rates in {time.time()-t0:.1f}s")

    global_rates = sources.load_rr_global()
    rows = _rate_rows(mapping, rates, global_rates, canonical_techs)
    print(f"[rr_build_table] built {len(rows)} rows for {len(mapping)} technologies "
          f"(specific rate or RR_Global fallback) in {time.time()-t0:.1f}s")

    max_rate_by_year_mat = _max_achievable_rate(rows)
    objective_df = sources.load_recycling_objective()
    objective_rows = _objective_rows(objective_df, max_rate_by_year_mat)
    print(f"[rr_build_table] built {len(objective_rows)} recycling_objective_share rows in {time.time()-t0:.1f}s")

    costs = sources.load_rr_costs()
    techs_with_material = _techs_with_material()
    cost_rows = _cost_rows(canonical_techs, costs, techs_with_material)
    primary_cost_rows = _primary_cost_rows(costs)
    print(f"[rr_build_table] built {len(cost_rows)} recycling_cost (scoped to techs that actually "
          f"contain the material) + {len(primary_cost_rows)} primary_material_cost rows "
          f"({len(costs)} materials with cost data) in {time.time()-t0:.1f}s")

    disposal_costs = sources.load_disposal_costs()
    disposal_cost_rows = _disposal_cost_rows(disposal_costs)
    print(f"[rr_build_table] built {len(disposal_cost_rows)} disposal_cost rows "
          f"({len(disposal_costs)} materials with disposal cost data) in {time.time()-t0:.1f}s")

    if write_dat:
        out_path = _write_dat(rows, objective_rows, cost_rows, primary_cost_rows, disposal_cost_rows)
        n_lines = len(rows) + len(objective_rows) + len(cost_rows) + len(primary_cost_rows) + len(disposal_cost_rows)
        print(f"[rr_build_table] wrote {out_path.name} ({n_lines} lines) in {time.time()-t0:.1f}s")

    print(f"[rr_build_table] total: {time.time()-t0:.1f}s")
    return rows


if __name__ == '__main__':
    build()
