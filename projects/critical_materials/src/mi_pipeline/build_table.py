"""Assemble the final long-format Metal_Intensity table and write both output
artifacts: technologies_mi_all_years.xlsx and ampl_files/Material_intensity.dat.

Only the ~35 electricity/fuel-cell technologies (see canonical.py) are recomputed
from the literature source data on every run; every other EnergyScope technology's
rows are carried through unchanged from the current technologies_mi_all_years.xlsx.

Performance note: rows are written with openpyxl's write_only Workbook, which streams
straight to disk instead of building an in-memory cell index -- the normal-mode
per-cell-style approach used to hand-edit this file degrades badly past ~100k rows
(confirmed: 4h15 to write 184k rows). write_only avoids that entirely.
"""
import time
from pathlib import Path

import openpyxl
import pandas as pd
from openpyxl import Workbook
from openpyxl.cell import WriteOnlyCell
from openpyxl.styles import Font, PatternFill

from . import canonical
from .aggregate import YEARS, compute_all
from .mapping import load_mapping

_PROJ_ROOT = Path(__file__).resolve().parents[2]  # .../projects/critical_materials
CURRENT_XLSX = _PROJ_ROOT / 'excel_files' / 'technologies_mi_all_years.xlsx'
OUT_XLSX = CURRENT_XLSX
OUT_DAT_NAME = 'Material_intensity'

FONT_A = Font(name='Arial', size=12)
FILL_VIOLET = PatternFill(start_color='FF636EFA', end_color='FF636EFA', fill_type='solid')
FILL_LIGHTBLUE = PatternFill(start_color='FFADD8E6', end_color='FFADD8E6', fill_type='solid')

# Matches the material ordering convention already used throughout the sheet: Pd
# right after Nb, Pt right after Pr (see conversation history for how this was set).
MATERIAL_OUTPUT_ORDER = [
    'Al', 'B', 'Cd', 'Cr', 'Co', 'Concrete', 'Cu', 'Dy', 'Ga', 'Ge', 'Glass', 'Hf',
    'In', 'Fe', 'Pb', 'Li', 'Mg', 'Mn', 'Mo', 'Nd', 'Ni', 'Nb', 'Pd', 'Polymers',
    'Pr', 'Pt', 'Se', 'Si', 'Ag', 'Ta', 'Te', 'Tb', 'Sn', 'W', 'V', 'Y', 'Zn', 'Zr',
]


# HYDRO_STORAGE is in this pipeline's compute/mapping scope (canonical.all_target_techs())
# but is a storage asset, not an electricity-production one, so it's excluded from the
# "Electricity production" legend color.
_ELECTRICITY_FILL_TECHS = set(canonical.electricity_techs()) | set(canonical.fuel_cell_techs())


def _column_fill(tech):
    if tech.startswith('CAR_') or tech.startswith('SUV_'):
        return FILL_VIOLET
    if tech in _ELECTRICITY_FILL_TECHS:
        return FILL_LIGHTBLUE
    return None


def _read_existing_non_electricity_rows(electricity_scope):
    """Read technologies_mi_all_years.xlsx's Metal_Intensity sheet and return every
    row (as a 7-tuple) whose tech isn't in `electricity_scope`, in their original order."""
    wb = openpyxl.load_workbook(CURRENT_XLSX, data_only=False)
    ws = wb['Metal_Intensity']
    rows = []
    for r in range(2, ws.max_row + 1):
        row = tuple(ws.cell(row=r, column=c).value for c in range(1, 8))
        if row[2] not in electricity_scope:
            rows.append(row)
    return rows


def _electricity_rows(mapping, intensities):
    """Long-format rows for the ~35 recomputed technologies, in
    tech -> MATERIAL_OUTPUT_ORDER -> YEARS order."""
    rows = []
    for tech, row in mapping.iterrows():
        df = intensities[tech]
        if row['mapping_type'] == 'not_mapped':
            comment = f"[not_mapped] {row['notes']}".strip()
        else:
            subtechs = ','.join(row['subtechs'])
            comment = (f"[{row['confidence']}] Bieuville et al. 2025 (MI_Energy); "
                       f"mapping: {row['mapping_type']} <- {subtechs}. See tech_mapping.xlsx.")
        for material in MATERIAL_OUTPUT_ORDER:
            for year in YEARS:
                raw_value = df.loc[material, year]
                value = None if pd.isna(raw_value) else float(raw_value)
                rows.append(('material_intensity', year, tech, material, value, 't/GW', comment))
    return rows


def _write_xlsx(all_rows, path=OUT_XLSX):
    wb = Workbook(write_only=True)

    ws = wb.create_sheet('Metal_Intensity')
    header = ['Parameter', 'index0', 'index1', 'index2', 'Value', 'Unit', 'Comment']
    header_cells = [WriteOnlyCell(ws, value=h) for h in header]
    for cell in header_cells:
        cell.font = Font(name='Calibri', size=11, bold=True)
    ws.append(header_cells)

    for row in all_rows:
        param_cell = WriteOnlyCell(ws, value=row[0])
        param_cell.font = FONT_A
        tech_cell = WriteOnlyCell(ws, value=row[2])
        fill = _column_fill(row[2])
        if fill is not None:
            tech_cell.fill = fill
        ws.append([param_cell, row[1], tech_cell, row[3], row[4], row[5], row[6]])

    legend = wb.create_sheet('Legend')
    b3 = WriteOnlyCell(legend, value=None)
    b3.fill = FILL_LIGHTBLUE
    b4 = WriteOnlyCell(legend, value=None)
    b4.fill = FILL_VIOLET
    legend.append([None, None, 'Legend'])
    legend.append([None, None])
    legend.append([None, b3, 'Electricity production'])
    legend.append([None, b4, 'Private mobility'])

    wb.save(path)


def create_dat_file_from_excel(df, file_name, out_dir=None, materials=MATERIAL_OUTPUT_ORDER):
    """Adapted from `New parameters and constraints.ipynb` (cell 5) -- writes
    ampl_files/{file_name}.dat from a long-format DataFrame
    (Parameter/index0/index1/index2/Value/Unit/Comment).

    The `set MATERIALS := ...` line is derived from `materials` (MATERIAL_OUTPUT_ORDER
    by default) instead of being duplicated as a separate hardcoded string, so adding a
    new material only means adding it in one place (MATERIAL_OUTPUT_ORDER +
    MATERIAL_NAME_TO_CODE in sources.py)."""
    out_dir = out_dir or (_PROJ_ROOT / 'ampl_files')
    out_path = Path(out_dir) / f'{file_name}.dat'
    with open(out_path, 'w', encoding='utf-8', newline='\n') as f:
        f.write("data;\n\n")
        f.write(f"set MATERIALS := {' '.join(materials)} ;\n \n")
        for _, row in df.iterrows():
            value = row['Value']
            if pd.isna(value):
                continue  # skip missing values, params already default to 0
            param_name = row['Parameter']
            index0 = row['index0']
            index1 = row['index1']
            index2 = row['index2']
            unit = '-' if pd.isna(row.get('Unit')) else str(row.get('Unit'))
            comment = '' if pd.isna(row.get('Comment')) else str(row.get('Comment'))
            if pd.isna(index1) and pd.isna(index2):
                f.write(f"let {param_name}['{index0}'] := {value} ; # [{unit}] {comment}\n")
            elif pd.isna(index2):
                f.write(f"let {param_name}['{index0}','{index1}'] := {value} ; # [{unit}] {comment}\n")
            else:
                f.write(f"let {param_name}['{index0}','{index1}','{index2}'] := {value} ; # [{unit}] {comment}\n")
    return out_path


def build(scenario='baseline', write_dat=True, write_xlsx=True):
    t0 = time.time()
    mapping = load_mapping()

    # Only techs both mapped AND already declared in QC_data.dat get output rows --
    # a mapping row for a not-yet-modelled tech (e.g. NEW_WIND_OFFSHORE) is kept in
    # tech_mapping.xlsx for later, but writing it to the .dat file now would make
    # AMPL choke on an out-of-set subscript.
    canonical_techs = set(canonical.all_target_techs())
    electricity_scope = set(mapping.index) & canonical_techs
    skipped = set(mapping.index) - canonical_techs
    if skipped:
        print(f"[build_table] skipping (not yet in QC_data.dat): {sorted(skipped)}")
    mapping = mapping.loc[sorted(electricity_scope)]

    intensities = compute_all(scenario=scenario)
    print(f"[build_table] computed {len(intensities)} tech intensities in {time.time()-t0:.1f}s")

    non_electricity_rows = _read_existing_non_electricity_rows(electricity_scope)
    print(f"[build_table] kept {len(non_electricity_rows)} existing non-electricity rows in {time.time()-t0:.1f}s")

    electricity_rows = _electricity_rows(mapping, intensities)
    print(f"[build_table] built {len(electricity_rows)} electricity rows in {time.time()-t0:.1f}s")

    all_rows = non_electricity_rows + electricity_rows

    if write_xlsx:
        _write_xlsx(all_rows)
        print(f"[build_table] wrote {OUT_XLSX.name} ({len(all_rows)} rows) in {time.time()-t0:.1f}s")

    if write_dat:
        df = pd.DataFrame(all_rows, columns=['Parameter', 'index0', 'index1', 'index2', 'Value', 'Unit', 'Comment'])
        out_path = create_dat_file_from_excel(df, OUT_DAT_NAME)
        print(f"[build_table] wrote {out_path.name} in {time.time()-t0:.1f}s")

    print(f"[build_table] total: {time.time()-t0:.1f}s")
    return all_rows


if __name__ == '__main__':
    build()
