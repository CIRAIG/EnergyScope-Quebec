set RECYCLING_PROCESS;
set RECYCLING_STREAM;
data;
set RECYCLING_PROCESS := "MECHANICAL" "THERMAL" "CHEMICAL" "PV_INFRASTUCTURE"
    "PYROMETALLURGICAL" "HYDROMETALLURGICAL" "DIRECT" "EV_CHASSIS" "EV_MOTOR" "WIND_MOTOR" ;
set RECYCLING_STREAM := "MODULE" "INFRASTRUCTURE" "BATTERY" "CHASSIS" "MOTOR" ;
model;

set RECYCLING_PROCESS_OF {TECHNOLOGIES,MATERIALS} within RECYCLING_PROCESS default {};
set RECYCLING_STREAM_OF {TECHNOLOGIES} within RECYCLING_STREAM default {};
set RECYCLING_PROCESS_OF_STREAM {TECHNOLOGIES,RECYCLING_STREAM} within RECYCLING_PROCESS default {};
set RECYCLING_PROCESS_OF_TECH {tec in TECHNOLOGIES} within RECYCLING_PROCESS :=
    union {str in RECYCLING_STREAM_OF[tec]} RECYCLING_PROCESS_OF_STREAM[tec,str];

param recovery_rate_process {TECHNOLOGIES,MATERIALS,RECYCLING_PROCESS} >= 0, <= 1 default 0;      # [-]
param collection_rate_process {YEARS,TECHNOLOGIES,RECYCLING_STREAM} >= 0, <= 1 default 1;          # [-]
param recycling_cost_process {TECHNOLOGIES,MATERIALS,RECYCLING_PROCESS} >= 0 default 0;            # [$/t]
param recycling_benefit_process {MATERIALS,RECYCLING_PROCESS} >= 0 default 0;                      # [$/t]

# Decision de recyclage : PAS un choix libre par materiau -- un meme lot demantele (module ou
# infrastructure) passe par une repartition de procedes commune a tous ses materiaux. Le vrai choix
# est combien de capacite decommissionnee (GW-equivalent) router vers chaque procede ; le rendement
# de chaque materiau en decoule (recycled_material_from_capacity).
var Decommissioned_capacity {YEARS,TECHNOLOGIES} >= 0;             # [GW-eq/year]
var Capacity_recycled {y in YEARS, tec in TECHNOLOGIES, proc in RECYCLING_PROCESS_OF_TECH[tec]} >= 0;  # [GW-eq/year]
var Recycled_material_process {y in YEARS, tec in TECHNOLOGIES, mat in MATERIALS, proc in RECYCLING_PROCESS_OF[tec,mat]} >= 0;  # [kt/year]

# Capacite (GW-eq), pas de ponderation par materiau -- meme structure que decommissioned_material_calc
# sans material_intensity, F_old vaut deja 0 si rien n'atteint sa fin de vie (cf. phase_out_assignement).
subject to decommissioned_capacity_calc {p_decom in PHASE_WND union PHASE_UP_TO, y_decom in PHASE_STOP[p_decom], tec in TECHNOLOGIES}:
    Decommissioned_capacity[y_decom,tec] = 1/5 * (
        sum {p_built in PHASE_WND union PHASE_UP_TO union {"2015_2020"}} F_decom[p_decom,p_built,tec]
        + F_old[p_decom,tec]
    );

# Par flux (module vs infrastructure) : chacun peut independamment aller jusqu'a collection_rate_process
# de la capacite decommissionnee -- ce sont deux composants physiques separes, ils ne partagent pas un pool.
subject to capacity_recycled_max {y in YEARS_WND diff YEAR_ONE, tec in TECHNOLOGIES, str in RECYCLING_STREAM_OF[tec]}:
    sum {proc in RECYCLING_PROCESS_OF_STREAM[tec,str]} Capacity_recycled[y,tec,proc]
    <= collection_rate_process[y,tec,str] * Decommissioned_capacity[y,tec];

# Rendement matiere = fonction directe de la capacite routee vers ce procede -- tous les materiaux
# d'un meme procede recoivent donc la MEME base (Capacity_recycled), seul recovery_rate_process differe.
# Hypothese : material_intensity constant sur les annees pour les technos avec plusieurs procedes
# (vrai aujourd'hui pour PV c-Si, mapping_type='direct') -- sinon le millesime exact se perdrait ici.
subject to recycled_material_from_capacity {y in YEARS_WND diff YEAR_ONE, tec in TECHNOLOGIES, mat in MATERIALS, proc in RECYCLING_PROCESS_OF[tec,mat]}:
    Recycled_material_process[y,tec,mat,proc] = recovery_rate_process[tec,mat,proc] * material_intensity[y,tec,mat] * Capacity_recycled[y,tec,proc];

# Fold vers les hooks de Constraints.mod. Recycled_material_process_total's upper bound (0 by default,
# see Constraints.mod) is raised to Infinity by shared/utils.py (after data loads) before this equality
# is generated -- can't do it here, this file loads pre-data (mod_1_path).
subject to recycled_material_process_total_calc {y in YEARS_WND diff YEAR_ONE, tec in TECHNOLOGIES, mat in MATERIALS}:
    Recycled_material_process_total[y,tec,mat] = sum {proc in RECYCLING_PROCESS_OF[tec,mat]} Recycled_material_process[y,tec,mat,proc];

# Actualise avec actualisation_factor[p,y] (meme convention que material_cost_calc) pour rester
# comparable a l'investissement -- sans ca, un "cycle construire->demanteler->recycler" non actualise
# peut sembler artificiellement rentable. /1e6 : Recycled_material_process est en tonnes brutes
# malgre le commentaire [kt/year] (meme convention que Recycled_material), couts en $/t -> $ -> M$.
unfix C_material_recycling_tech;  # Constraints.mod fixes it to 0 by default; free it here to let the equality below drive it
# MATERIAL_TECHS (Constraints.mod), not TECHNOLOGIES: avoids double-counting a mobility family tech
# alongside its distance-class variants, same as material_cost_calc.
subject to c_material_recycling_tech_calc:
    C_material_recycling_tech = sum {p in PHASE_WND union PHASE_UP_TO, y in PHASE_STOP[p] diff YEAR_ONE, tec in MATERIAL_TECHS, mat in MATERIALS, proc in RECYCLING_PROCESS_OF[tec,mat]}
        actualisation_factor[p,y] * (recycling_cost_process[tec,mat,proc] - recycling_benefit_process[mat,proc]) * Recycled_material_process[y,tec,mat,proc] * 5 / 1e6;
