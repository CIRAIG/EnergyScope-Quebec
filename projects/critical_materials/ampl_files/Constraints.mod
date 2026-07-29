set MATERIALS;

param material_intensity {YEARS,TECHNOLOGIES,MATERIALS} >= 0 default 0;       # [t/GW] 
param limit_material_year {YEARS,MATERIALS} >= 0 default Infinity;            # [t/year] ou [kt/year] budget annuel (ex: x % part de la production miniere mondiale)
param limit_material {MATERIALS} >= 0 default Infinity;                       # [t] ou [kt] budget cumule sur l'horizon (ex: x % des reserves)
param recycling_rate {YEARS,TECHNOLOGIES,MATERIALS} >= 0, <= 1 default 0;     # [-] part du materiau recuperable au demantelement 
param collection_rate {YEARS,TECHNOLOGIES} >= 0, <= 1 default 1;              # [-] part de la capacite demantelee qui est effectivement collectee (avant recyclage)

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

# Materiau recupere sur la capacite demantelee pendant l'horizon, base sur l'intensite au moment
# ou la capacite avait ete construite. Deux sources de demantelement coexistent dans le modele :
# - F_decom[p_decom,p_built,tec] : remplacement anticipe/volontaire, deja ventile par millesime de construction.
#   p_built inclut "2015_2020" (parc d'avant l'horizon d'optimisation) -- meme convention que
#   QC_es_pathway.mod partout ou F_decom est somme sur son 2e indice (ex: phase_new_build,
#   investment_computation_CRF). L'oublier fait rater tout le F_decom dont le millesime est
#   anterieur a 2020 (frequent : c'est souvent le seul millesime avec F_decom > 0, ex. WIND_ONSHORE).
# - F_old[p_decom,tec] : sortie de flotte "naturelle" en fin de duree de vie ; son millesime de construction
#   n'est pas un indice de la variable mais est donne par le set AGE[tec,p_decom]
# collection_rate (par techno) s'applique avant recycling_rate (par materiau) : seule la part collectee
# de la capacite demantelee peut ensuite etre recyclee.
# Pas encore soustrait de Material_content_year/limit_material (a activer plus tard:
# Material_content_year nette = brut - Recycled_material).
subject to recycled_material_calc {p_decom in PHASE_WND union PHASE_UP_TO, y_decom in PHASE_STOP[p_decom], tec in TECHNOLOGIES, mat in MATERIALS}:
    Recycled_material[y_decom,tec,mat] = collection_rate[y_decom,tec] * recycling_rate[y_decom,tec,mat] / 5 * (
        sum {p_built in PHASE_WND union PHASE_UP_TO union {"2015_2020"}, y_built in PHASE_STOP[p_built]}
            material_intensity[y_built,tec,mat] * F_decom[p_decom,p_built,tec]
        + sum {p_built in AGE[tec,p_decom] diff {"STILL_IN_USE"}, y_built in PHASE_STOP[p_built]}
            material_intensity[y_built,tec,mat] * F_old[p_decom,tec]
    );