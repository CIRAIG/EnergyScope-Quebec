set MATERIALS;

param material_intensity {YEARS,TECHNOLOGIES,MATERIALS} >= 0 default 0;       # [t/GW]
param limit_material_year {YEARS,MATERIALS} >= 0 default Infinity;            # [t/year]
param limit_material {MATERIALS} >= 0 default Infinity;                       # [t]

param recycling_rate {YEARS,TECHNOLOGIES,MATERIALS} >= 0, <= 1 default 0;     # [-] plafond technique de recuperation
param collection_rate {YEARS,TECHNOLOGIES} >= 0, <= 1 default 1;              # [-] plafond de collecte
param recycling_cost {TECHNOLOGIES,MATERIALS} >= 0 default 0;                 # [$/t]
param disposal_cost {MATERIALS} >= 0 default 50;                              # [$/t] estimation generique (pas de donnee Cost_disposal_global)
param primary_material_cost {MATERIALS} >= 0 default 0;                       # [$/t] cout matiere vierge evitee si recycle

param recycling_objective_share {YEARS,MATERIALS} >= 0, <= 1 default 0;       # [-] cible si follow_objective=1
param follow_objective binary default 0;

var Material_content_year {YEARS,TECHNOLOGIES,MATERIALS} >= 0;    # [t/year]
var Material_content {TECHNOLOGIES,MATERIALS} >= 0;               # [t] cumule sur l'horizon

var Decommissioned_material {YEARS,TECHNOLOGIES,MATERIALS} >= 0;  # [t/year] materiau demantele (mecanique)
var Recycled_material {YEARS,TECHNOLOGIES,MATERIALS} >= 0;        # [t/year] materiau recycle (decision, <= plafond)
var Disposed_material {YEARS,TECHNOLOGIES,MATERIALS} >= 0;        # [t/year] materiau enfoui/incinere
var Recycling_benefit {YEARS,TECHNOLOGIES,MATERIALS};             # [M$/year, actualise] cout evite en recyclant
# C_material: declare dans QC_es_pathway.mod (extension hook)

subject to material_content_year_calc {p in PHASE_WND union PHASE_UP_TO, y in PHASE_STOP[p], tec in TECHNOLOGIES, mat in MATERIALS}:
    Material_content_year[y,tec,mat] = material_intensity[y,tec,mat] * F_new[p,tec] / 5;

subject to material_content_calc {tec in TECHNOLOGIES, mat in MATERIALS}:
    Material_content[tec,mat] = sum {y in YEARS_WND diff YEAR_ONE} Material_content_year[y,tec,mat] * 5;

# Nette de Recycled_material, agrege par materiau (fongible entre technos)
subject to material_content_year_limit {y in YEARS_WND diff YEAR_ONE, mat in MATERIALS}:
    sum {tec in TECHNOLOGIES} Material_content_year[y,tec,mat]
    - sum {tec in TECHNOLOGIES} Recycled_material[y,tec,mat] <= limit_material_year[y,mat];

subject to material_content_limit {mat in MATERIALS}:
    sum {tec in TECHNOLOGIES} Material_content[tec,mat]
    - sum {y in YEARS_WND diff YEAR_ONE, tec in TECHNOLOGIES} Recycled_material[y,tec,mat] * 5 <= limit_material[mat];

# F_decom[p_decom,p_built,tec]: p_built inclut "2015_2020" (parc pre-horizon)
# F_old[p_decom,tec]: millesime de construction donne par AGE[tec,p_decom]
subject to decommissioned_material_calc {p_decom in PHASE_WND union PHASE_UP_TO, y_decom in PHASE_STOP[p_decom], tec in TECHNOLOGIES, mat in MATERIALS}:
    Decommissioned_material[y_decom,tec,mat] = 1/5 * (
        sum {p_built in PHASE_WND union PHASE_UP_TO union {"2015_2020"}, y_built in PHASE_STOP[p_built]}
            material_intensity[y_built,tec,mat] * F_decom[p_decom,p_built,tec]
        + sum {p_built in AGE[tec,p_decom] diff {"STILL_IN_USE"}, y_built in PHASE_STOP[p_built]}
            material_intensity[y_built,tec,mat] * F_old[p_decom,tec]
    );

subject to recycled_material_max {y in YEARS_WND diff YEAR_ONE, tec in TECHNOLOGIES, mat in MATERIALS}:
    Recycled_material[y,tec,mat] <= collection_rate[y,tec] * recycling_rate[y,tec,mat] * Decommissioned_material[y,tec,mat];

subject to disposed_material_calc {y in YEARS_WND diff YEAR_ONE, tec in TECHNOLOGIES, mat in MATERIALS}:
    Disposed_material[y,tec,mat] = Decommissioned_material[y,tec,mat] - Recycled_material[y,tec,mat];

# Actualise avec annualised_factor[p,y] (meme facteur que C_inv) pour rester comparable a l'investissement.
# /1e6 : Recycled_material est en tonnes, couts en $/t -> $ ; on convertit en M$ comme C_inv.
subject to recycling_benefit_calc {p in PHASE_WND union PHASE_UP_TO, y in PHASE_STOP[p] diff YEAR_ONE, tec in TECHNOLOGIES, mat in MATERIALS}:
    Recycling_benefit[y,tec,mat] = annualised_factor[p,y] * (primary_material_cost[mat] + disposal_cost[mat] - recycling_cost[tec,mat]) * Recycled_material[y,tec,mat] / 1e6;

# Egalite (pas un plancher) si follow_objective=1, sinon degenere en 0=0. Restreint aux technos avec
# recycling_rate>0 pour eviter de se diluer dans le Decommissioned_material des technos non mappees.
subject to recycled_material_objective {y in YEARS_WND diff YEAR_ONE, mat in MATERIALS}:
    follow_objective * sum {tec in TECHNOLOGIES : recycling_rate[y,tec,mat] > 0} Recycled_material[y,tec,mat]
    = follow_objective * recycling_objective_share[y,mat] * sum {tec in TECHNOLOGIES : recycling_rate[y,tec,mat] > 0} Decommissioned_material[y,tec,mat];

subject to material_cost_calc:
    C_material = sum {p in PHASE_WND union PHASE_UP_TO, y in PHASE_STOP[p] diff YEAR_ONE, tec in TECHNOLOGIES, mat in MATERIALS}
        annualised_factor[p,y] *
        (recycling_cost[tec,mat] * Recycled_material[y,tec,mat]
         - primary_material_cost[mat] * Recycled_material[y,tec,mat]
         + disposal_cost[mat] * Disposed_material[y,tec,mat]) * 5 / 1e6;
