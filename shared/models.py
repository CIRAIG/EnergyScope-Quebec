from pathlib import Path
from energyscope.models import Model

# Get the absolute path to the directory containing this file
_MODEL_DIR = Path(__file__).parent.absolute()

# Define the path to the utilities directory (in the same shared folder)
_UTILITIES_DIR = _MODEL_DIR / 'utilities' / 'ES_snapshot'


energyscope_original_snapshot_2023 = Model([
    ('mod', str(_UTILITIES_DIR / 'QC_es_main.mod')),
    ('mod', str(_UTILITIES_DIR / 'QC_objective_function.mod')),
    ('dat', str(_UTILITIES_DIR / 'QC_data.dat')),
    ('dat', str(_UTILITIES_DIR / 'QC_mob_techs_dist_B2D.dat')),
    ('dat', str(_UTILITIES_DIR / 'QC_techs_B2D.dat')),
    ('dat', str(_UTILITIES_DIR / 'QC_mob_params.dat')),
    ('dat', str(_UTILITIES_DIR / 'QC_validation_2023.dat')),
])

energyscope_original_snapshot_2021 = Model([
    ('mod', str(_UTILITIES_DIR / 'QC_es_main.mod')),
    ('mod', str(_UTILITIES_DIR / 'QC_objective_function.mod')),
    ('dat', str(_UTILITIES_DIR / 'QC_data.dat')),
    ('dat', str(_UTILITIES_DIR / 'QC_mob_techs_dist_B2D.dat')),
    ('dat', str(_UTILITIES_DIR / 'QC_techs_B2D.dat')),
    ('dat', str(_UTILITIES_DIR / 'QC_mob_params.dat')),
    ('dat', str(_UTILITIES_DIR / 'QC_validation_2021.dat')),
])