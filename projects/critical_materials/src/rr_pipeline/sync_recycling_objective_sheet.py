# Write the 'EOL-RR_ramped' table back into Recycling_rates.xlsx as a readable mirror (not read by build)
import openpyxl

from mi_pipeline import canonical
from mi_pipeline.mapping import load_mapping

from . import build_table, sources
from .aggregate import YEARS, compute_all

_ALL_YEAR_COLS = [int(y.split('_')[1]) for y in YEARS]  # 2020..2050


# {material: {year: value}} of the best recycling_rate across techs, from the hand-edited sheets
def compute_max_achievable_table():
    mapping = load_mapping(path=sources.SOURCE_XLSX)
    canonical_techs = set(canonical.all_target_techs())
    claims_real_data = mapping['mapping_type'] != 'not_mapped'
    not_yet_modeled = set(mapping.index[claims_real_data]) - canonical_techs
    mapping = mapping.loc[sorted(set(mapping.index) - not_yet_modeled)]

    rates = compute_all()
    global_rates = sources.load_rr_global()
    rows = build_table._rate_rows(mapping, rates, global_rates, canonical_techs)
    max_rate_by_year_mat = build_table._max_achievable_rate(rows)

    materials = {mat for (_year, mat) in max_rate_by_year_mat}
    return {
        material: {
            year_int: max_rate_by_year_mat.get((f'YEAR_{year_int}', material), 0.0)
            for year_int in _ALL_YEAR_COLS
        }
        for material in materials
    }


def _write_sheet(wb, sheet_name, header_label, year_cols, table, full_to_short, get_value):
    if sheet_name in wb.sheetnames:
        ws = wb[sheet_name]
    else:
        ws = wb.create_sheet(sheet_name)
        ws.cell(row=1, column=1, value=header_label)
        for i, year_int in enumerate(year_cols, start=2):
            ws.cell(row=1, column=i, value=year_int)
        for i, full_name in enumerate(sorted(full_to_short), start=2):
            ws.cell(row=i, column=1, value=full_name)

    header = {cell.value: cell.column for cell in ws[1]}
    written, skipped = 0, 0
    for row in ws.iter_rows(min_row=2):
        full_name = row[0].value
        if full_name is None:
            continue
        material = full_to_short.get(full_name)
        if material is None or material not in table:
            skipped += 1
            continue
        for year_int, col in header.items():
            if not isinstance(year_int, int) or year_int not in table[material]:
                continue
            ws.cell(row=row[0].row, column=col, value=round(get_value(table[material][year_int]), 6))
            written += 1
    return written, skipped


def sync(path=sources.SOURCE_XLSX):
    max_table = compute_max_achievable_table()
    full_to_short = sources.load_materials(path)

    wb = openpyxl.load_workbook(path)

    w1, s1 = _write_sheet(
        wb, 'EOL-RR_ramped', 'Max-achievable EOL-RR across technologies [%]',
        _ALL_YEAR_COLS, max_table, full_to_short, lambda v: v,
    )
    print(f"[sync_recycling_objective_sheet] EOL-RR_ramped: wrote {w1} cells, skipped {s1} rows (no recycling_rate data)")

    wb.save(path)
    print(f"[sync_recycling_objective_sheet] saved -> {path}")


if __name__ == '__main__':
    sync()
