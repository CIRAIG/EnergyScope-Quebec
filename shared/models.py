from energyscope.models import Model

energyscope_quebec = Model([
    ('mod', '../model/QC_es_main.mod'),
    ('mod', '../model/QC_objective_function.mod'),
    ('dat', '../data/QC_data.dat'),
    ('dat', '../data/QC_mob_techs_dist_B2D.dat'),
    ('dat', '../data/QC_techs_B2D.dat'),
    ('dat', '../data/QC_mob_params.dat'),
    ('dat', '../data/QC_validation_2023.dat'),
])