set MATERIALS;

param material_intensity {YEARS,TECHNOLOGIES,MATERIALS} >= 0 default 0;       # [kt/GW] (verifier vs. t/GW dans le .dat -> facteur 1000 a corriger si besoin)
param limit_material_year {YEARS,MATERIALS} >= 0 default Infinity;            # [kt/year] budget annuel (ex: part de la production miniere mondiale)
param limit_material {MATERIALS} >= 0 default Infinity;                       # [kt] budget cumule sur l'horizon (ex: reserves)
param recycling_rate {YEARS,TECHNOLOGIES,MATERIALS} >= 0, <= 1 default 0;     # [-] part du materiau recuperable au demantelement

# F_new[p,tec] est le total de capacite construite sur toute la phase (5 ans), pas un flux annuel.
# Material_content_year est donc annualise (divise par 5) pour etre comparable a un budget annuel d'extraction.
var Material_content_year {YEARS,TECHNOLOGIES,MATERIALS} >= 0;    # [kt/year]
var Material_content {TECHNOLOGIES,MATERIALS} >= 0;               # [kt] cumule sur l'horizon d'optimisation
var Recycled_material {YEARS,TECHNOLOGIES,MATERIALS} >= 0;        # [kt/year] materiau recupere au demantelement (pas encore deduit de la demande, cf. TODO plus bas)

subject to material_content_year_calc {p in PHASE_WND union PHASE_UP_TO, y in PHASE_STOP[p], tec in TECHNOLOGIES, mat in MATERIALS}:
    Material_content_year[y,tec,mat] = material_intensity[y,tec,mat] * F_new[p,tec] / 5;

subject to material_content_calc {tec in TECHNOLOGIES, mat in MATERIALS}:
    Material_content[tec,mat] = sum {y in YEARS_WND diff YEAR_ONE} Material_content_year[y,tec,mat] * 5;

subject to material_content_year_limit {y in YEARS_WND diff YEAR_ONE, mat in MATERIALS}:
    sum {tec in TECHNOLOGIES} Material_content_year[y,tec,mat] <= limit_material_year[y,mat];

subject to material_content_limit {mat in MATERIALS}:
    sum {tec in TECHNOLOGIES} Material_content[tec,mat] <= limit_material[mat];

# Materiau recupere sur la capacite demantelee (F_decom) pendant l'horizon, base sur l'intensite
# au moment ou la capacite avait ete construite. Pas encore soustrait de Material_content_year/limit_material
# (a activer plus tard: Material_content_year nette = brut - Recycled_material).
subject to recycled_material_calc {p_decom in PHASE_WND union PHASE_UP_TO, y_decom in PHASE_STOP[p_decom], tec in TECHNOLOGIES, mat in MATERIALS}:
    Recycled_material[y_decom,tec,mat] = recycling_rate[y_decom,tec,mat] *
        sum {p_built in PHASE_WND union PHASE_UP_TO, y_built in PHASE_STOP[p_built]}
            material_intensity[y_built,tec,mat] * F_decom[p_decom,p_built,tec] / 5;