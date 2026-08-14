"""Load the "recycling_materials_technologies" (competing recycling
processes) sheets of Recycling_rates.xlsx into tidy pandas DataFrames.

This file is treated as read-only input: nothing in this module writes to it.

Unlike rr_pipeline (Approach 1, one simple recycling_rate per (tech,
material), sourced from the Mapping sheet like mi_pipeline), these sheets
don't use the Mapping sheet at all -- Recycling_technologies/Recycling_cost
use their own ad-hoc "Technology"/"Sub-technology" labels (not EnergyScope
tech names), and only one technology (PV c-Si) has any real data so far. So
instead of a generic Mapping-driven lookup, this module uses a small
hand-maintained table (PV_C_SI_TECHS below) mapping those labels to the
EnergyScope AMPL techs they apply to -- extend it by hand as more
"Technology" blocks get filled in (e.g. a future CdTe block).
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

# Collection_rate's row labels -> which RECYCLING_STREAM they describe (see
# load_collection_rate). "Sol_C-si_Silver" and "Sol_C-si_Copper" are two rows
# both describing the MODULE stream's collection rate (a sheet-authoring
# artifact -- filled in per mapped-material row instead of once per stream).
COLLECTION_RATE_ROW_TO_STREAM = {
    'PV_infrastruture': 'INFRASTRUCTURE',
    'Sol_C-si_Silver': 'MODULE',
    'Sol_C-si_Copper': 'MODULE',
}


def load_materials(path=SOURCE_XLSX):
    return _load_materials(path)


def load_recycling_technologies(path=SOURCE_XLSX):
    """Melt the wide Recycling_technologies sheet into long-format rows:
    (process, stream, material, recovery_rate). One row per (process,
    material) cell that actually has a value -- each material has data in
    exactly one process column-group by construction (module processes XOR
    the infrastructure column, confirmed empirically), so no fractional
    split of material_intensity is needed downstream.

    `stream` groups processes that physically compete for the same
    decommissioned batch (e.g. MECHANICAL/THERMAL/CHEMICAL all process the
    same module) vs PV_INFRASTUCTURE (a physically separate component, its
    own stream) -- derived directly from the sheet's own sub-part label
    ("PV_module" -> "MODULE", "PV_infrastucture" -> "INFRASTRUCTURE").

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
        subpart_clean = str(subpart).strip().upper().replace(' ', '_')
        stream_name = 'MODULE' if 'MODULE' in subpart_clean else 'INFRASTRUCTURE'
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
    """Collection_rate sheet -> {stream: {year: rate}}. Per the user: the
    fraction of a whole physical stream (module or infrastructure) that's
    actually collected, before any recycling-process choice -- not
    per-material. The two MODULE rows ('Sol_C-si_Silver'/'Sol_C-si_Copper')
    are asserted to carry identical values (a sheet-authoring artifact, see
    COLLECTION_RATE_ROW_TO_STREAM); raises if they ever diverge rather than
    silently picking one."""
    df = pd.read_excel(path, sheet_name='Collection_rate', index_col=0)
    df.columns = [int(c) for c in df.columns]

    unknown = set(df.index) - set(COLLECTION_RATE_ROW_TO_STREAM)
    if unknown:
        raise ValueError(f"Collection_rate has unrecognized row label(s): {sorted(unknown)} "
                          f"-- add them to COLLECTION_RATE_ROW_TO_STREAM")

    result = {}
    for row_label, values in df.iterrows():
        stream = COLLECTION_RATE_ROW_TO_STREAM[row_label]
        year_rates = {year: float(rate) for year, rate in values.items() if pd.notna(rate)}
        if stream in result and result[stream] != year_rates:
            raise ValueError(f"Collection_rate has conflicting values for stream {stream!r}: "
                              f"{result[stream]} (from an earlier row) vs {year_rates} ({row_label!r})")
        result[stream] = year_rates
    return result


if __name__ == '__main__':
    rt = load_recycling_technologies()
    print("Recycling_technologies:", rt.shape)
    print(rt)
    print("\nRecycling_cost:")
    print(load_recycling_cost())
    print("\nCollection_rate:")
    print(load_collection_rate())
