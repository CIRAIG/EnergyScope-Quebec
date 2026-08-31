set MATERIALS;

param material_intensity {YEARS,TECHNOLOGIES,MATERIALS} >= 0 default 0;       # [t/GW]
param limit_material_year {YEARS,MATERIALS} >= 0 default Infinity;            # [t/year]
param limit_material {MATERIALS} >= 0 default Infinity;                       # [t]

param recycling_rate {YEARS,TECHNOLOGIES,MATERIALS} >= 0, <= 1 default 0;     # [-] plafond technique de recuperation
param collection_rate {YEARS,TECHNOLOGIES} >= 0, <= 1 default 1;              # [-] plafond de collecte
param recycling_cost {TECHNOLOGIES,MATERIALS} >= 0 default 0;                 # [$/t]
param disposal_cost {MATERIALS} >= 0 default 0.001;                              # [$/t] estimation generique (pas de donnee Cost_disposal_global)
param primary_material_cost {MATERIALS} >= 0 default 0;                       # [$/t] cout matiere vierge evitee si recycle

param recycling_objective_share {YEARS,MATERIALS} >= 0, <= 1 default 0;       # [-] cible si follow_objective=1
param follow_objective binary default 0;
param shortfall_penalty >= 0 default 10000000;                                # [$/t] >> tout cout reel

var Material_content_year {YEARS,TECHNOLOGIES,MATERIALS} >= 0;    # [t/year]
var Material_content {TECHNOLOGIES,MATERIALS} >= 0;               # [t] cumule sur l'horizon

var Decommissioned_material {YEARS,TECHNOLOGIES,MATERIALS} >= 0;  # [t/year] materiau demantele (mecanique)
var Recycled_material {YEARS,TECHNOLOGIES,MATERIALS} >= 0;        # [t/year] materiau recycle (decision, <= plafond)
var Disposed_material {YEARS,TECHNOLOGIES,MATERIALS} >= 0;        # [t/year] materiau enfoui/incinere
var Recycling_benefit {YEARS,TECHNOLOGIES,MATERIALS};             # [M$/year, actualise] cout evite en recyclant
var Recycling_shortfall {YEARS_WND diff YEAR_ONE, MATERIALS} >= 0; # [t/year] manque a l'objectif, comptable
# C_material, Recycling_shortfall_penalty_total: hooks dans PES_main.mod / PES_obj_pathway.mod

# Approche 2 (recycling_materials_technologies) : hooks pour Constraints_recycling_technologies.mod,
# libre de nombre entier -- pas de borne >=0 sur C_material_recycling_tech, un procede peut etre net
# benefique (revenue > cout).
#ADDED BY PAOLO (to validate) -- borne haute par parametre (default 0) plutot que "fix" indexe : Constraints.mod
# est charge dans mod_1_path, AVANT les donnees (YEARS/TECHNOLOGIES/MATERIALS vides a ce stade), donc un
# "fix {y in YEARS,...} := 0;" plante ("no data for set YEARS"). Un param/borne reste declaratif -- value
# seulement resolue a la generation du modele, une fois les donnees chargees.
param recycled_material_process_total_ub {TECHNOLOGIES,MATERIALS} >= 0 default 0;  # releve a Infinity par Material_recycling_process_enable.mod quand materials_recycling_process=True
var Recycled_material_process_total {y in YEARS, tec in TECHNOLOGIES, mat in MATERIALS} >= 0, <= recycled_material_process_total_ub[tec,mat];  # [t/year]
var C_material_recycling_tech;                                            # [M$, actualise]
#ADDED BY PAOLO (to validate)
fix C_material_recycling_tech := 0;  # safe default when Constraints_recycling_technologies.mod isn't loaded (materials_recycling_process=False) -- same free-variable exploit as C_material otherwise (drives TotalTransitionCost to 0)

subject to material_content_year_calc {p in PHASE_WND union PHASE_UP_TO, y in PHASE_STOP[p], tec in TECHNOLOGIES, mat in MATERIALS}:
    Material_content_year[y,tec,mat] = material_intensity[y,tec,mat] * F_new[p,tec] / 5;

subject to material_content_calc {tec in TECHNOLOGIES, mat in MATERIALS}:
    Material_content[tec,mat] = sum {y in YEARS_WND diff YEAR_ONE} Material_content_year[y,tec,mat] * 5;

# Nette de Recycled_material, agrege par materiau (fongible entre technos)
subject to material_content_year_limit {y in YEARS_WND diff YEAR_ONE, mat in MATERIALS}:
    sum {tec in TECHNOLOGIES} Material_content_year[y,tec,mat]
    - sum {tec in TECHNOLOGIES} (Recycled_material[y,tec,mat] + Recycled_material_process_total[y,tec,mat]) <= limit_material_year[y,mat];

subject to material_content_limit {mat in MATERIALS}:
    sum {tec in TECHNOLOGIES} Material_content[tec,mat]
    - sum {y in YEARS_WND diff YEAR_ONE, tec in TECHNOLOGIES} (Recycled_material[y,tec,mat] + Recycled_material_process_total[y,tec,mat]) * 5 <= limit_material[mat];

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
    Disposed_material[y,tec,mat] = Decommissioned_material[y,tec,mat] - Recycled_material[y,tec,mat] - Recycled_material_process_total[y,tec,mat];

# Actualise avec actualisation_factor[p,y] (meme facteur que C_inv) pour rester comparable a l'investissement.
# /1e6 : Recycled_material est en tonnes, couts en $/t -> $ ; on convertit en M$ comme C_inv.
subject to recycling_benefit_calc {p in PHASE_WND union PHASE_UP_TO, y in PHASE_STOP[p] diff YEAR_ONE, tec in TECHNOLOGIES, mat in MATERIALS}:
    Recycling_benefit[y,tec,mat] = actualisation_factor[p,y] * (primary_material_cost[mat] + disposal_cost[mat] - recycling_cost[tec,mat]) * Recycled_material[y,tec,mat] / 1e6;

# Plancher (pas egalite) : Recycling_shortfall absorbe l'ecart si la cible depasse recycled_material_max.
subject to recycled_material_objective {y in YEARS_WND diff YEAR_ONE, mat in MATERIALS}:
    follow_objective * (sum {tec in TECHNOLOGIES : recycling_rate[y,tec,mat] > 0} Recycled_material[y,tec,mat] + Recycling_shortfall[y,mat])
    >= follow_objective * recycling_objective_share[y,mat] * sum {tec in TECHNOLOGIES : recycling_rate[y,tec,mat] > 0} Decommissioned_material[y,tec,mat];

# Alimente l'objectif (PES_obj_pathway.mod), pas C_material -- garde TotalTransitionCost non fausse.
subject to recycling_shortfall_penalty_calc:
    Recycling_shortfall_penalty_total = sum {p in PHASE_WND union PHASE_UP_TO, y in PHASE_STOP[p] diff YEAR_ONE, mat in MATERIALS}
        actualisation_factor[p,y] * shortfall_penalty * Recycling_shortfall[y,mat] * 5 / 1e6;

#ADDED BY PAOLO (to validate)
unfix C_material;  # PES_main.mod fixes it to 0 by default (safe when this file isn't loaded); free it here to let the equality below drive it, including negative (net recycling benefit)
subject to material_cost_calc:
    C_material = sum {p in PHASE_WND union PHASE_UP_TO, y in PHASE_STOP[p] diff YEAR_ONE, tec in TECHNOLOGIES, mat in MATERIALS}
        actualisation_factor[p,y] *
        (recycling_cost[tec,mat] * Recycled_material[y,tec,mat]
         - primary_material_cost[mat] * Recycled_material[y,tec,mat]
         + disposal_cost[mat] * Disposed_material[y,tec,mat]) * 5 / 1e6
        + C_material_recycling_tech;
