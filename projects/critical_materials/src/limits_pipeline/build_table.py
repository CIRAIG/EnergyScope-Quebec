"""Build ampl_files/Material_limits.dat from excel_files/Material_limits.xlsx's
'Material_limits' sheet (annual production/reserve caps per material, [t/year]).

That workbook is read-only input -- this module never writes to it.
"""
from pathlib import Path

import pandas as pd

from mi_pipeline.sources import load_materials

_PROJ_ROOT = Path(__file__).resolve().parents[2]  # .../projects/critical_materials
SOURCE_XLSX = _PROJ_ROOT / 'excel_files' / 'Material_limits.xlsx'
LIMITS_SHEET = 'Material_limits'

YEARS = [2020, 2025, 2030, 2035, 2040, 2045, 2050]
# 2020/2025 are always left at their AMPL default (Infinity), whatever the sheet says --
# the 2020_2025 build phase is fixed by historical calibration (fmin_perc_mob, cf.
# shared/data/Shares/out_shares.dat), not by any decision the model can adjust to respect an
# early material limit, so constraining those two years would only risk spurious infeasibility.
WRITTEN_YEARS = [2030, 2035, 2040, 2045, 2050]


def load_limits(path=SOURCE_XLSX):
    """DataFrame indexed by short material code, one column per year in YEARS,
    values in [t/year] (NaN where the sheet has no data for that material)."""
    materials = load_materials()  # {full_name: short_code}, from Material_intensities.xlsx
    df = pd.read_excel(path, sheet_name=LIMITS_SHEET, index_col=0)
    df.columns = [int(c) for c in df.columns]
    unmapped = [name for name in df.index if name not in materials]
    if unmapped:
        raise ValueError(f"{LIMITS_SHEET} has materials with no short-code mapping: {unmapped}")
    df.index = df.index.map(materials)
    return df


def build(path=SOURCE_XLSX, out_dir=None, write_dat=True):
    """Regenerate ampl_files/Material_limits.dat (unless write_dat=False). Returns
    the DataFrame of limits actually written (short material code index,
    WRITTEN_YEARS columns) either way."""
    df = load_limits(path)
    written = df[WRITTEN_YEARS].dropna(how='all')

    if not write_dat:
        return written

    out_dir = Path(out_dir) if out_dir else (_PROJ_ROOT / 'ampl_files')
    out_path = out_dir / 'Material_limits.dat'
    with open(out_path, 'w', encoding='utf-8', newline='\n') as f:
        f.write("data;\n\n")
        f.write("# Limites annuelles de materiau [t/year] (limit_material_year), regenere depuis\n")
        f.write(f"# excel_files/{SOURCE_XLSX.name} (feuille '{LIMITS_SHEET}') par run_build_limits.py --\n")
        f.write("# ne pas editer a la main : modifier la feuille Excel, puis relancer le script.\n")
        f.write("#\n")
        f.write("# 2020/2025 : toujours Infinity (donc rien n'est ecrit ici pour ces deux annees --\n")
        f.write("# c'est deja la valeur par defaut du parametre), quelle que soit la feuille -- le mix\n")
        f.write("# 2020_2025 est fige par calibration historique (fmin_perc_mob, cf.\n")
        f.write("# shared/data/Shares/out_shares.dat), pas par une decision du modele, donc y imposer\n")
        f.write("# une limite ne ferait que risquer une infeasibilite artificielle.\n\n")
        for mat in written.index:
            for year in WRITTEN_YEARS:
                value = written.loc[mat, year]
                if pd.isna(value):
                    continue
                f.write(f"let limit_material_year['YEAR_{year}','{mat}'] := {value:.6g} ;\n")

    return written
