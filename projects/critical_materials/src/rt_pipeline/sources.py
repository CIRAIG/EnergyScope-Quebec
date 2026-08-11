"""Load the "Approach 2" (competing recycling technologies/processes) sheets
of Recycling_rates.xlsx into tidy pandas DataFrames.

This file is treated as read-only input: nothing in this module writes to it.

Unlike rr_pipeline (Approach 1, one simple recycling_rate per (tech,
material), sourced from the Mapping sheet like mi_pipeline), these sheets
don't use the Mapping sheet at all -- Recycling_technologies/Recycling_cost/
Electricity_use use their own ad-hoc "Technology"/"Sub-technology" labels
(not EnergyScope tech names), and only one technology (PV c-Si) has any real
data so far. So instead of a generic Mapping-driven lookup, this module uses
a small hand-maintained table (PV_C_SI_TECHS below) mapping those labels to
the EnergyScope AMPL techs they apply to -- extend it by hand as more
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


def load_materials(path=SOURCE_XLSX):
    return _load_materials(path)


def load_recycling_technologies(path=SOURCE_XLSX):
    """Melt the wide Recycling_technologies sheet into long-format rows:
    (process, material, recovery_rate). One row per (process, material) cell
    that actually has a value -- each material has data in exactly one
    process column by construction (module processes XOR the infrastructure
    column, confirmed empirically), so no fractional split of
    material_intensity is needed downstream.

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
        process = raw.iloc[process_row, col]
        process_name = str(process).strip().upper().replace(' ', '_').removesuffix('_PROCESS') \
            if pd.notna(process) else str(subpart).strip().upper().replace(' ', '_')
        col_values = data[col]
        if col_values.isna().all():
            continue  # e.g. the empty "Sol_CdTe" stub column
        for material_full, value in zip(data[0], col_values):
            if pd.isna(value):
                continue
            rows.append({
                'process': process_name,
                'material': materials[material_full],
                'recovery_rate': float(value),
            })
    return pd.DataFrame(rows)


def _load_long_sheet(sheet_name, value_col, path=SOURCE_XLSX):
    """Shared reader for Recycling_cost / Electricity_use: already long
    format (Technology | Sub-technology | Metal | Recycling process |
    <value_col> | Unit | ...). Returns a DataFrame with a 'material' short
    code column added and rows with no value dropped."""
    materials = load_materials(path)
    df = pd.read_excel(path, sheet_name=sheet_name)
    df = df.dropna(subset=[value_col])
    unmapped = [name for name in df['Metal'] if name not in materials]
    if unmapped:
        raise ValueError(f"{sheet_name} has metals with no short-code mapping: {sorted(set(unmapped))}")
    df['material'] = df['Metal'].map(materials)
    df['process'] = df['Recycling process'].astype(str).str.strip().str.upper()
    return df


def load_recycling_cost(path=SOURCE_XLSX):
    """Recycling_cost sheet: cost [MCAD/GW of source tech processed] and
    revenue [MCAD/kt of material recovered], per (Technology, Sub-technology,
    Metal, process). Only Aluminum/PV-c-Si filled in so far."""
    return _load_long_sheet('Recycling_cost', 'Recycling cost', path)


def load_electricity_use(path=SOURCE_XLSX):
    """Electricity_use sheet: same long format as Recycling_cost, energy use
    [GWh/GW of source tech processed] (the value column is mislabeled
    "Recycling cost" in the sheet itself -- a copy-paste artifact from the
    Recycling_cost template, not an actual cost). Only 1 row filled in so
    far (Aluminum/Mechanical)."""
    return _load_long_sheet('Electricity_use', 'Recycling cost', path)


def load_recycling_scenario_technologies(path=SOURCE_XLSX):
    """Approach 2's minimum-collection-rate floor: DataFrame indexed by row
    label (a material-or-category identity -- "PV_infrastructure" applies to
    every infrastructure material at once, "Sol_C-si_Silver"/"Sol_C-si_Copper"
    apply to one material each, see MATERIAL_ROW_LABELS below), one column
    per year (int), values already shares [0,1]."""
    df = pd.read_excel(path, sheet_name='Recycling_scenario_technologies', index_col=0)
    df.columns = [int(c) for c in df.columns]
    return df


# Maps Recycling_scenario_technologies' row labels to a material short code
# (for the two subtech-specific rows) -- hand-maintained for the same reason
# as PV_C_SI_TECHS above. "PV_infrastructure" isn't in here: it's handled
# separately in build_table.py by broadcasting to every infrastructure
# material (i.e. every material Recycling_technologies assigns a recovery
# rate to under a non-module process).
SCENARIO_TECH_ROW_TO_MATERIAL = {
    'Sol_C-si_Silver': 'Ag',
    'Sol_C-si_Copper': 'Cu',
}


if __name__ == '__main__':
    rt = load_recycling_technologies()
    print("Recycling_technologies:", rt.shape)
    print(rt)
    print("\nRecycling_cost:")
    print(load_recycling_cost())
    print("\nElectricity_use:")
    print(load_electricity_use())
    print("\nRecycling_scenario_technologies:")
    print(load_recycling_scenario_technologies())
