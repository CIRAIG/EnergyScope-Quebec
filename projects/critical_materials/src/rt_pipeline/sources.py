"""Load the "recycling_materials_technologies" (competing recycling
processes) sheets of Recycling_rates.xlsx into tidy pandas DataFrames.

This file is treated as read-only input: nothing in this module writes to it.

Unlike rr_pipeline (Approach 1, one simple recycling_rate per (tech,
material), sourced from the Mapping sheet like mi_pipeline), these sheets
don't use the Mapping sheet at all -- Recycling_technologies/Recycling_cost/
Collection_rate use their own ad-hoc "Technology"/"Sub-technology" labels
(not EnergyScope tech names). PV c-Si has real study-backed data; EV battery
(CAR_EV/SUV_EV) is a mock filled in with illustrative-but-directionally-
sensible literature values (see the sheets' own Comment/Reference columns)
so the multi-technology architecture is exercised end-to-end before real
numbers exist. So instead of a generic Mapping-driven lookup, this module
uses a small hand-maintained table (TECHNOLOGY_LABEL_TO_TECHS below) mapping
those labels to the EnergyScope AMPL techs they apply to -- extend it by hand
as more "Technology" blocks get filled in.
"""
from pathlib import Path

import pandas as pd

from mi_pipeline.sources import load_materials as _load_materials

_PROJ_ROOT = Path(__file__).resolve().parents[2]  # .../projects/critical_materials
SOURCE_XLSX = _PROJ_ROOT / 'excel_files' / 'Recycling_rates.xlsx'

# The only technology with real data today: c-Si PV modules, same physical
# panel type mounted on a roof or on the ground -- both AMPL techs share the
# same recycling data. Extend this dict (one entry per new "Technology"
# block that gets filled in) rather than trying to auto-parse the sheets'
# free-text "Subtechnology"/"Sub-technology" labels, which are informational
# only and not always consistent with the real Mapping sheet (e.g.
# Recycling_technologies lists "Sol_C-si_Silver ; Sol_C-si_Copper" for a
# column that, per the real Mapping sheet, only PV_ROOF_C_SI's Silver stream
# actually uses -- Copper isn't wired into material_intensity at all).
PV_C_SI_TECHS = ['PV_ROOF_C_SI', 'PV_GROUND_C_SI']

# Mock technology (no real study yet -- see run_build_rt.py docstring): Li-ion EV battery
# packs, same NMC-type chemistry assumed for both AMPL techs. CAR_EV/SUV_EV are the two
# highest-volume private EV techs with real material_intensity data (Bieuville).
EV_BATTERY_TECHS = ['CAR_EV', 'SUV_EV']

# Wind turbine PMSG generators -- the only wind sub-techs with permanent-magnet (Nd/Pr/Dy)
# content (DFIG_SCIG/EESG variants have none). Family-level tech names only (no distance-class
# variants exist for wind, so this is a non-issue here, but keep the convention explicit).
WIND_MOTOR_DD_TECHS = ['WIND_ONSHORE_DD_PMSG', 'NEW_WIND_ONSHORE_DD_PMSG']
WIND_MOTOR_GB_TECHS = ['WIND_ONSHORE_GB_PMSG', 'NEW_WIND_ONSHORE_GB_PMSG']
WIND_MOTOR_TECHS = WIND_MOTOR_DD_TECHS + WIND_MOTOR_GB_TECHS

# Every "Technology" label variant seen across the two sheets (Recycling_technologies uses
# 'PV'/'EV'/'Wind'; Recycling_cost's free-text 'Technology' column uses 'Solar PV'/'EV Battery'/
# 'Wind DD'/'Wind GB') -> the EnergyScope techs it applies to. One dict for both sheets since a
# (sheet, label) pair always resolves to the same underlying tech list -- add one entry per new
# label variant rather than trying to normalize the sheets' own free text.
#
# Wind needs 3 label variants, not the usual 1: Recycling_technologies/Collection_rate use plain
# 'Wind' (recovery rate % and collection rate are tech-agnostic within a stream, fine to apply to
# both PMSG variants at once) but Recycling_cost needs DD and GB split into 'Wind DD'/'Wind GB' --
# their Nd:Pr:Dy magnet composition ratios differ enough (see mi_pipeline) that a single MCAD/GW
# figure applied to both would convert to inconsistent $/t once divided by each tech's own
# material_intensity (build_table.py's _cost_benefit_rows enforces this consistency per tech).
TECHNOLOGY_LABEL_TO_TECHS = {
    'PV': PV_C_SI_TECHS,
    'Solar PV': PV_C_SI_TECHS,
    'EV': EV_BATTERY_TECHS,
    'EV Battery': EV_BATTERY_TECHS,
    'Wind': WIND_MOTOR_TECHS,
    'Wind DD': WIND_MOTOR_DD_TECHS,
    'Wind GB': WIND_MOTOR_GB_TECHS,
}

# Recycling_technologies' row-3 sub-part label -> RECYCLING_STREAM name. Hand-maintained (not
# auto-derived from the label text) so a typo in the sheet (e.g. 'PV_infrastucture', missing an
# 'r') can't silently produce a stream name that doesn't match what's declared in
# Constraints_recycling_technologies.mod's RECYCLING_STREAM set. Each technology gets its own,
# physically-meaningful stream names -- there's no requirement that every technology have the
# same number of streams or reuse PV's MODULE/INFRASTRUCTURE naming (EV genuinely has three
# separate physical components: battery, chassis, motor).
SUBPART_TO_STREAM = {
    'PV_infrastucture': 'INFRASTRUCTURE',
    'PV_module': 'MODULE',
    'PV module': 'MODULE',
    'EV_battery': 'BATTERY',
    'EV_chassis': 'CHASSIS',
    'EV_motor': 'MOTOR',
    'Wind_motor': 'MOTOR',
}

# Collection_rate's row labels -> which RECYCLING_STREAM they describe (see
# load_collection_rate). "Sol_C-si_Silver" and "Sol_C-si_Copper" are two rows
# both describing the MODULE stream's collection rate (a sheet-authoring
# artifact -- filled in per mapped-material row instead of once per stream).
COLLECTION_RATE_ROW_TO_STREAM = {
    'PV_infrastruture': 'INFRASTRUCTURE',
    'Sol_C-si_Silver': 'MODULE',
    'Sol_C-si_Copper': 'MODULE',
    'EV_battery': 'BATTERY',
    'EV_chassis': 'CHASSIS',
    'EV_motor': 'MOTOR',
    'Wind_motor': 'MOTOR',
}

# Same row labels -> which Technology group they belong to (see TECHNOLOGY_LABEL_TO_TECHS).
COLLECTION_RATE_ROW_TO_TECH_LABEL = {
    'PV_infrastruture': 'PV',
    'Sol_C-si_Silver': 'PV',
    'Sol_C-si_Copper': 'PV',
    'EV_battery': 'EV',
    'EV_chassis': 'EV',
    'EV_motor': 'EV',
    'Wind_motor': 'Wind',
}


def load_materials(path=SOURCE_XLSX):
    return _load_materials(path)


def load_recycling_technologies(path=SOURCE_XLSX):
    """Melt the wide Recycling_technologies sheet into long-format rows:
    (technology, process, stream, material, recovery_rate). One row per
    (process, material) cell that actually has a value -- each material has
    data in exactly one process column-group by construction (module
    processes XOR the infrastructure column, confirmed empirically), so no
    fractional split of material_intensity is needed downstream.

    `technology` is the sheet's own row-1 label (e.g. 'PV', 'EV') -- look it
    up in TECHNOLOGY_LABEL_TO_TECHS to get the EnergyScope techs it applies
    to (build_table.py does this per technology block, not globally).

    `stream` groups processes that physically compete for the same
    decommissioned batch (e.g. MECHANICAL/THERMAL/CHEMICAL all process the
    same PV module) vs a physically separate component with its own stream
    (e.g. PV_INFRASTUCTURE, or EV's battery/chassis/motor) -- looked up from
    the sheet's own sub-part label via SUBPART_TO_STREAM (a hand-maintained
    table, not auto-parsed from the label text, so a sheet typo can't
    silently produce a stream name that doesn't match Constraints_
    recycling_technologies.mod's RECYCLING_STREAM set). No fixed stream
    count or naming per technology -- PV has 2 (MODULE/INFRASTRUCTURE), EV
    has 3 (BATTERY/CHASSIS/MOTOR), a future technology could have any number.

    Column layout (3 header rows, read with header=None): row 0 = process
    name (blank for the infrastructure column), row 1 = "Technology" (e.g.
    "PV"), row 2 = sub-part (e.g. "PV_infrastucture" / "PV_module"). Material
    rows start right after. Columns with no data at all in any material row
    (e.g. the empty "Sol_CdTe" stub column) are skipped automatically.
    """
    materials = load_materials(path)
    raw = pd.read_excel(path, sheet_name='Recycling_technologies', header=None)

    header_rows = raw.index[raw[0].astype(str).str.strip() == 'Technology']
    if len(header_rows) == 0:
        raise ValueError("Could not find the 'Technology' header row in Recycling_technologies")
    tech_row = header_rows[0]
    subpart_row = tech_row + 1
    process_row = tech_row - 1  # process name lives one row above "Technology"

    data_start = tech_row + 2
    if str(raw.iloc[data_start, 0]).strip() == 'Subtechnology':
        data_start += 1  # skip the informational "Subtechnology" annotation row

    material_col = raw.iloc[data_start:, 0]
    is_material_row = material_col.isin(materials)
    data = raw.iloc[data_start:][is_material_row]

    rows = []
    for col in raw.columns[1:]:
        subpart = raw.iloc[subpart_row, col]
        if pd.isna(subpart):
            continue  # not part of any technology block (e.g. blank spacer column)
        technology = raw.iloc[tech_row, col]
        if pd.isna(technology):
            continue
        subpart_raw = str(subpart).strip()
        subpart_clean = subpart_raw.upper().replace(' ', '_')
        if subpart_raw not in SUBPART_TO_STREAM:
            raise ValueError(f"Recycling_technologies has sub-part {subpart_raw!r} with no entry "
                              f"in SUBPART_TO_STREAM -- add one (see the PV_module/EV_battery pattern)")
        stream_name = SUBPART_TO_STREAM[subpart_raw]
        process = raw.iloc[process_row, col]
        process_name = str(process).strip().upper().replace(' ', '_').removesuffix('_PROCESS') \
            if pd.notna(process) else subpart_clean
        col_values = data[col]
        if col_values.isna().all():
            continue  # e.g. the empty "Sol_CdTe" stub column
        for material_full, value in zip(data[0], col_values):
            if pd.isna(value):
                continue
            rows.append({
                'technology': str(technology).strip(),
                'process': process_name,
                'stream': stream_name,
                'material': materials[material_full],
                'recovery_rate': float(value),
            })
    return pd.DataFrame(rows)


def load_recycling_cost(path=SOURCE_XLSX):
    """Recycling_cost sheet: cost [MCAD/GW of source tech processed] and
    revenue [MCAD/kt of material recovered], per (Technology, Sub-technology,
    Metal, process). Only Aluminum/PV-c-Si/all 3 processes filled in so far."""
    materials = load_materials(path)
    df = pd.read_excel(path, sheet_name='Recycling_cost')
    df = df.dropna(subset=['Recycling cost'])
    unmapped = [name for name in df['Metal'] if name not in materials]
    if unmapped:
        raise ValueError(f"Recycling_cost has metals with no short-code mapping: {sorted(set(unmapped))}")
    df['material'] = df['Metal'].map(materials)
    df['process'] = df['Recycling process'].astype(str).str.strip().str.upper()
    return df


def load_collection_rate(path=SOURCE_XLSX):
    """Collection_rate sheet (its first table, columns A-G -- a second,
    unrelated generic per-material reference table sits further right in the
    same sheet and is ignored here since it isn't indexed by column A) ->
    {technology: {stream: {year: rate}}}. Per the user: the fraction of a
    whole physical stream (module or infrastructure) that's actually
    collected, before any recycling-process choice -- not per-material. The
    two PV MODULE rows ('Sol_C-si_Silver'/'Sol_C-si_Copper') are asserted to
    carry identical values (a sheet-authoring artifact, see
    COLLECTION_RATE_ROW_TO_STREAM); raises if they ever diverge rather than
    silently picking one."""
    df = pd.read_excel(path, sheet_name='Collection_rate', index_col=0, usecols='A:G')
    df = df.dropna(how='all')  # usecols still reads down to the sheet's overall max_row (a second,
    # unrelated table sits further right and extends past row 6) -- drop the resulting blank tail rows.
    df.columns = [int(c) for c in df.columns]

    unknown = set(df.index) - set(COLLECTION_RATE_ROW_TO_STREAM)
    if unknown:
        raise ValueError(f"Collection_rate has unrecognized row label(s): {sorted(unknown)} "
                          f"-- add them to COLLECTION_RATE_ROW_TO_STREAM/COLLECTION_RATE_ROW_TO_TECH_LABEL")

    result = {}
    for row_label, values in df.iterrows():
        technology = COLLECTION_RATE_ROW_TO_TECH_LABEL[row_label]
        stream = COLLECTION_RATE_ROW_TO_STREAM[row_label]
        year_rates = {year: float(rate) for year, rate in values.items() if pd.notna(rate)}
        by_stream = result.setdefault(technology, {})
        if stream in by_stream and by_stream[stream] != year_rates:
            raise ValueError(f"Collection_rate has conflicting values for {technology!r}/{stream!r}: "
                              f"{by_stream[stream]} (from an earlier row) vs {year_rates} ({row_label!r})")
        by_stream[stream] = year_rates
    return result


if __name__ == '__main__':
    rt = load_recycling_technologies()
    print("Recycling_technologies:", rt.shape)
    print(rt)
    print("\nRecycling_cost:")
    print(load_recycling_cost())
    print("\nCollection_rate:")
    print(load_collection_rate())
