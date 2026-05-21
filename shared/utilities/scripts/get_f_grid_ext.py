"""
get_f_grid_ext.py
Run the 2021 validation snapshot and print F_Mult for all GRIDS.
These values are what should be set as f_grid_ext in QC_data.dat.

Run from the repo root:
    python shared/utilities/scripts/get_f_grid_ext.py
"""

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parents[3]))  # repo root

from shared.models import energyscope_original_snapshot_2021
from shared.utils import run_model


def main():
    print('Running 2021 validation snapshot ...')
    res = run_model(energyscope_original_snapshot_2021)

    grids = set(res.sets['GRIDS']['GRIDS'].tolist())

    _ORDER = [
        'LV_GRID', 'MV_GRID', 'HV_GRID', 'EHV_GRID',
        'LP_H2_GRID', 'MP_H2_GRID', 'HP_H2_GRID', 'EHP_H2_GRID',
        'LP_NG_GRID', 'MP_NG_GRID', 'HP_NG_GRID', 'EHP_NG_GRID',
    ]
    _rank = {g: i for i, g in enumerate(_ORDER)}

    df = res.variables['F_Mult'].reset_index()
    idx_col = df.columns[0]
    df = df[df[idx_col].isin(grids)]
    df = df.sort_values(idx_col, key=lambda s: s.map(lambda g: _rank.get(g, len(_ORDER))))

    print('\nF_Mult for GRIDS (→ use as f_grid_ext):')
    print(f'{"Grid":<20} {"F_Mult":>25}')
    print('-' * 47)
    for _, row in df.iterrows():
        print(f'{row[idx_col]:<20} {row["F_Mult"]:>25.15g}')

    print('\nparam f_grid_ext :=')
    for _, row in df.iterrows():
        if row['F_Mult'] != 0:
            print(f'{row[idx_col]:<16}\t{row["F_Mult"]}')
    print(';')


if __name__ == '__main__':
    main()
