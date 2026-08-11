set MATERIALS;
set RECYCLING_PROCESS;
data;
set RECYCLING_PROCESS := "DEFAULT" "MECHANICAL" "THERMAL" "CHEMICAL" "PV_INFRASTUCTURE" ;
model;

# Procedes eligibles par (techno, materiau) -- ecrit par rr_pipeline/rt_pipeline, pas derive de
# recycling_rate>0 ici. Sans ca, Recycled_material serait declaree sur TECHNOLOGIES x MATERIALS x
# RECYCLING_PROCESS (>1M instances) au lieu des ~150 combinaisons qui ont vraiment des donnees --
# le temps de solve/extraction depend de la taille declaree, pas du nombre de valeurs non nulles.
set RECYCLING_PROCESS_OF {TECHNOLOGIES,MATERIALS} within RECYCLING_PROCESS default {};

param material_intensity {YEARS,TECHNOLOGIES,MATERIALS} >= 0 default 0;       # [t/GW]
param limit_material_year {YEARS,MATERIALS} >= 0 default Infinity;            # [t/year]
param limit_material {MATERIALS} >= 0 default Infinity;                       # [t]

param recycling_rate {YEARS,TECHNOLOGIES,MATERIALS,RECYCLING_PROCESS} >= 0, <= 1 default 0;   # [-]
param collection_rate {YEARS,TECHNOLOGIES} >= 0, <= 1 default 1;              # [-]
param recycling_cost {TECHNOLOGIES,MATERIALS,RECYCLING_PROCESS} >= 0 default 0;               # [$/t]
param disposal_cost {MATERIALS} >= 0 default 0.01;                            # [$/t]
param recycling_gwp {TECHNOLOGIES,MATERIALS,RECYCLING_PROCESS} >= 0 default 0;                # [ktCO2-eq./kt]
param disposal_gwp {MATERIALS} >= 0 default 0;                                # [ktCO2-eq./kt]
param recycling_energy_elec {TECHNOLOGIES,MATERIALS,RECYCLING_PROCESS} >= 0 default 0;        # [GWh/t] informatif, pas dans C_material
param recycling_benefit {MATERIALS,RECYCLING_PROCESS} >= 0 default 0;                         # [$/t]

# Planchers IMPOSES (pas des plafonds) -- forcent une part minimum a recycler malgre l'absence
# d'incitatif de cout par defaut. min_collection_rate = Approche 2 (par techno/materiau), cf.
# Recycling_scenario_technologies. recycling_scenario_share = Approche 1 (par materiau, agrege
# sur toutes les technos), cf. Recycling_scenario.
param min_collection_rate {YEARS,TECHNOLOGIES,MATERIALS} >= 0, <= 1 default 0;
param recycling_scenario_share {YEARS,MATERIALS} >= 0, <= 1 default 0;

var Material_content_year {YEARS,TECHNOLOGIES,MATERIALS} >= 0;    # [kt/year]
var Material_content {TECHNOLOGIES,MATERIALS} >= 0;               # [kt] cumule sur l'horizon
var Decommissioned_material {YEARS,TECHNOLOGIES,MATERIALS} >= 0;  # [kt/year]
var Recycled_material {y in YEARS, tec in TECHNOLOGIES, mat in MATERIALS, proc in RECYCLING_PROCESS_OF[tec,mat]} >= 0;  # [kt/year]
var Disposed_material {YEARS,TECHNOLOGIES,MATERIALS} >= 0;        # [kt/year]
# C_material et Material_GWP: declares dans QC_es_pathway.mod / shared/model/QC_es_main.mod

subject to material_content_year_calc {p in PHASE_WND union PHASE_UP_TO, y in PHASE_STOP[p], tec in TECHNOLOGIES, mat in MATERIALS}:
    Material_content_year[y,tec,mat] = material_intensity[y,tec,mat] * F_new[p,tec] / 5;

subject to material_content_calc {tec in TECHNOLOGIES, mat in MATERIALS}:
    Material_content[tec,mat] = sum {y in YEARS_WND diff YEAR_ONE} Material_content_year[y,tec,mat] * 5;

subject to material_content_year_limit {y in YEARS_WND diff YEAR_ONE, mat in MATERIALS}:
    sum {tec in TECHNOLOGIES} Material_content_year[y,tec,mat]
    - sum {tec in TECHNOLOGIES, proc in RECYCLING_PROCESS_OF[tec,mat]} Recycled_material[y,tec,mat,proc] <= limit_material_year[y,mat];

# Relachee pour l'instant (demande explicite) -- decommenter pour reactiver.
#subject to net_demand_nonneg {y in YEARS_WND diff YEAR_ONE, mat in MATERIALS}:
#    sum {tec in TECHNOLOGIES} Material_content_year[y,tec,mat]
#    - sum {tec in TECHNOLOGIES, proc in RECYCLING_PROCESS_OF[tec,mat]} Recycled_material[y,tec,mat,proc] >= 0;

subject to material_content_limit {mat in MATERIALS}:
    sum {tec in TECHNOLOGIES} Material_content[tec,mat]
    - sum {y in YEARS_WND diff YEAR_ONE, tec in TECHNOLOGIES, proc in RECYCLING_PROCESS_OF[tec,mat]} Recycled_material[y,tec,mat,proc] * 5 <= limit_material[mat];

# F_decom[p_decom,p_built,tec]: p_built inclut "2015_2020" (parc pre-horizon). F_old[p_decom,tec]:
# millesime donne par AGE[tec,p_decom], pas un indice de la variable.
subject to decommissioned_material_calc {p_decom in PHASE_WND union PHASE_UP_TO, y_decom in PHASE_STOP[p_decom], tec in TECHNOLOGIES, mat in MATERIALS}:
    Decommissioned_material[y_decom,tec,mat] = 1/5 * (
        sum {p_built in PHASE_WND union PHASE_UP_TO union {"2015_2020"}, y_built in PHASE_STOP[p_built]}
            material_intensity[y_built,tec,mat] * F_decom[p_decom,p_built,tec]
        + sum {p_built in AGE[tec,p_decom] diff {"STILL_IN_USE"}, y_built in PHASE_STOP[p_built]}
            material_intensity[y_built,tec,mat] * F_old[p_decom,tec]
    );

subject to recycled_material_max {y in YEARS_WND diff YEAR_ONE, tec in TECHNOLOGIES, mat in MATERIALS, proc in RECYCLING_PROCESS_OF[tec,mat]}:
    Recycled_material[y,tec,mat,proc] <= collection_rate[y,tec] * recycling_rate[y,tec,mat,proc] * Decommissioned_material[y,tec,mat];

subject to disposed_material_calc {y in YEARS_WND diff YEAR_ONE, tec in TECHNOLOGIES, mat in MATERIALS}:
    Disposed_material[y,tec,mat] = Decommissioned_material[y,tec,mat] - sum {proc in RECYCLING_PROCESS_OF[tec,mat]} Recycled_material[y,tec,mat,proc];

subject to min_collection_forced {y in YEARS_WND diff YEAR_ONE, tec in TECHNOLOGIES, mat in MATERIALS}:
    sum {proc in RECYCLING_PROCESS_OF[tec,mat]} Recycled_material[y,tec,mat,proc] >= min_collection_rate[y,tec,mat] * Decommissioned_material[y,tec,mat];

subject to min_recycled_aggregate {y in YEARS_WND diff YEAR_ONE, mat in MATERIALS}:
    sum {tec in TECHNOLOGIES, proc in RECYCLING_PROCESS_OF[tec,mat]} Recycled_material[y,tec,mat,proc]
    >= recycling_scenario_share[y,mat] * sum {tec in TECHNOLOGIES} Decommissioned_material[y,tec,mat];

subject to material_cost_calc:
    C_material =
        sum {y in YEARS_WND diff YEAR_ONE, tec in TECHNOLOGIES, mat in MATERIALS, proc in RECYCLING_PROCESS_OF[tec,mat]}
            (recycling_cost[tec,mat,proc] - recycling_benefit[mat,proc])
            * Recycled_material[y,tec,mat,proc] * 5 * 1000
        + sum {y in YEARS_WND diff YEAR_ONE, tec in TECHNOLOGIES, mat in MATERIALS}
            disposal_cost[mat] * Disposed_material[y,tec,mat] * 5 * 1000;
        # *1000 : Recycled_material/Disposed_material en [kt], couts/benefice en [$/t]

subject to material_gwp_calc {y in YEARS_WND diff YEAR_ONE}:
    Material_GWP[y] = sum {tec in TECHNOLOGIES, mat in MATERIALS, proc in RECYCLING_PROCESS_OF[tec,mat]}
        (recycling_gwp[tec,mat,proc] * Recycled_material[y,tec,mat,proc])
        + sum {tec in TECHNOLOGIES, mat in MATERIALS} disposal_gwp[mat] * Disposed_material[y,tec,mat];
