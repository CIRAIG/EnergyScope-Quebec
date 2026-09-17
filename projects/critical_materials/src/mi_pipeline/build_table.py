"""Assemble the final long-format Metal_Intensity table and write
ampl_files/Material_intensity.dat.

Every technology in the Mapping sheet (Material_intensities.xlsx) is
recomputed on every run: techs with a real mapping_type get their values from the
literature source data (currently only the ~35 electricity/fuel-cell ones -- see
canonical.py), techs marked not_mapped get blank cells (skipped by
create_dat_file_from_excel).
"""
import time
from pathlib import Path

import pandas as pd

from . import canonical, sources
from .aggregate import VEHICLE_POWERTRAINS, PUBLIC_TRANSIT_POWERTRAINS, YEARS, compute_all
from .mapping import load_mapping

_PROJ_ROOT = Path(__file__).resolve().parents[2]  # .../projects/critical_materials
OUT_DAT_NAME = 'Material_intensity'


def load_material_output_order(path=sources.SOURCE_XLSX):
    """Output column order for materials -- the short codes from the
    'Materials' sheet, in row order. Add a material by adding a row there
    (see sources.load_materials()); nothing here needs to change."""
    return list(sources.load_materials(path).values())


MATERIAL_OUTPUT_ORDER = load_material_output_order()


def _mapped_rows(mapping, intensities, vehicle_source='bieuville'):
    """Long-format rows for every technology in the Mapping sheet (in scope), in
    tech -> MATERIAL_OUTPUT_ORDER -> YEARS order. not_mapped techs get blank
    (None) Values, which create_dat_file_from_excel then skips entirely."""
    rows = []
    for tech, row in mapping.iterrows():
        df = intensities[tech]
        is_vehicle = bool(row['subtechs']) and set(row['subtechs']) <= VEHICLE_POWERTRAINS
        is_fcv = is_vehicle and row['subtechs'][0] == 'FCV'
        is_public = is_vehicle and row['subtechs'][0] in PUBLIC_TRANSIT_POWERTRAINS
        unit = 't/(pkm/h)' if is_vehicle else 't/GW'
        if row['mapping_type'] == 'not_mapped':
            comment = "[not_mapped]"
        else:
            subtechs = ','.join(row['subtechs'])
            if not is_vehicle:
                source = 'Bieuville et al. 2025 (MI_Energy)'
            elif is_public:
                source = 'Månberger & Stenqvist 2018 (MI_Vehicles_Public + MS_Battery_Motor_LDV)'
            elif is_fcv or vehicle_source == 'watari':
                # FCV always falls back to MI_Vehicles regardless of vehicle_source (Bieuville doesn't cover it)
                source = 'Watari et al. 2019 / Fishman et al. 2018 (MI_Vehicles)'
            else:
                source = 'Bieuville et al. 2025 (MI_Vehicles_2 + MS_Battery_Motor_LDV)'
            comment = (f"{source}; "
                       f"mapping: {row['mapping_type']} <- {subtechs}. See the Mapping sheet.")
        for material in MATERIAL_OUTPUT_ORDER:
            for year in YEARS:
                raw_value = df.loc[material, year]
                value = None if pd.isna(raw_value) else float(raw_value)
                rows.append(('material_intensity', year, tech, material, value, unit, comment))
    return rows


def create_dat_file_from_excel(df, file_name, out_dir=None, materials=MATERIAL_OUTPUT_ORDER):
    """Adapted from `New parameters and constraints.ipynb` (cell 5) -- writes
    ampl_files/{file_name}.dat from a long-format DataFrame
    (Parameter/index0/index1/index2/Value/Unit/Comment).

    The `set MATERIALS := ...` line is derived from `materials` (MATERIAL_OUTPUT_ORDER
    by default) instead of being duplicated as a separate hardcoded string. Both that
    and MATERIAL_OUTPUT_ORDER itself come from the 'Materials' sheet (sources.py) --
    adding a material there is enough, nothing in this code needs to change."""
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


def build(vehicle_source='bieuville', write_dat=True):
    """vehicle_source: 'bieuville' (default) uses MI_Vehicles_2 +
    MS_Battery_Motor_LDV (see aggregate.compute_vehicle_intensities_bieuville).
    'watari' is the original flat MI_Vehicles-based computation instead.
    Either way this writes to the same Material_intensity.dat filename --
    rerunning with a different vehicle_source overwrites it, it doesn't keep
    both around. To compare the two, build+run_pathway_materials with one,
    save/rename the results, then build+run again with the other."""
    t0 = time.time()
    mapping = load_mapping()

    # A not_mapped tech is always safe to include (it only ever produces blank
    # cells, which create_dat_file_from_excel skips) -- but a tech claiming *real*
    # data has to already be declared in QC_data.dat, or AMPL chokes on an
    # out-of-set subscript when the .dat file is loaded. Mapping rows for a
    # not-yet-modelled tech stay in the Mapping sheet for later, just excluded
    # from output until it's added to the model.
    canonical_techs = set(canonical.all_target_techs())
    claims_real_data = mapping['mapping_type'] != 'not_mapped'
    not_yet_modeled = set(mapping.index[claims_real_data]) - canonical_techs
    if not_yet_modeled:
        print(f"[build_table] skipping (not yet in QC_data.dat): {sorted(not_yet_modeled)}")
    mapped_scope = set(mapping.index) - not_yet_modeled
    mapping = mapping.loc[sorted(mapped_scope)]

    intensities = compute_all(vehicle_source=vehicle_source)
    print(f"[build_table] computed {len(intensities)} tech intensities in {time.time()-t0:.1f}s")

    mapped_rows = _mapped_rows(mapping, intensities, vehicle_source=vehicle_source)
    print(f"[build_table] built {len(mapped_rows)} rows for the Mapping sheet's {len(mapping)} technologies in {time.time()-t0:.1f}s")

    if write_dat:
        df = pd.DataFrame(mapped_rows, columns=['Parameter', 'index0', 'index1', 'index2', 'Value', 'Unit', 'Comment'])
        out_path = create_dat_file_from_excel(df, OUT_DAT_NAME)
        print(f"[build_table] wrote {out_path.name} in {time.time()-t0:.1f}s")

    print(f"[build_table] total: {time.time()-t0:.1f}s")
    return mapped_rows


if __name__ == '__main__':
    build()
