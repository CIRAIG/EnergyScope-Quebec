# Prototype of recycling technologies equations, not final

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

# Capacity_recycled is the real decision (shared across a lot's materials, for batch consistency);
# each material's recycled amount is just its own yield applied to that shared capacity.
var Decommissioned_capacity {YEARS,TECHNOLOGIES} >= 0;             # [GW-eq/year]
var Capacity_recycled {y in YEARS, tec in TECHNOLOGIES, proc in RECYCLING_PROCESS_OF_TECH[tec]} >= 0;  # [GW-eq/year]
var Recycled_material_process {y in YEARS, tec in TECHNOLOGIES, mat in MATERIALS, proc in RECYCLING_PROCESS_OF[tec,mat]} >= 0;  # [kt/year]

subject to decommissioned_capacity_calc {p_decom in PHASE_WND union PHASE_UP_TO, y_decom in PHASE_STOP[p_decom], tec in TECHNOLOGIES}:
    Decommissioned_capacity[y_decom,tec] = 1/5 * (
        sum {p_built in PHASE_WND union PHASE_UP_TO union {"2015_2020"}} F_decom[p_decom,p_built,tec]
        + F_old[p_decom,tec]
    );

# Each stream (module/infrastructure) collects independently -- separate physical components, no shared pool.
subject to capacity_recycled_max {y in YEARS_WND diff YEAR_ONE, tec in TECHNOLOGIES, str in RECYCLING_STREAM_OF[tec]}:
    sum {proc in RECYCLING_PROCESS_OF_STREAM[tec,str]} Capacity_recycled[y,tec,proc]
    <= collection_rate_process[y,tec,str] * Decommissioned_capacity[y,tec];

# Assumes material_intensity is constant across years for multi-process techs (true today for PV c-Si).
subject to recycled_material_from_capacity {y in YEARS_WND diff YEAR_ONE, tec in TECHNOLOGIES, mat in MATERIALS, proc in RECYCLING_PROCESS_OF[tec,mat]}:
    Recycled_material_process[y,tec,mat,proc] = recovery_rate_process[tec,mat,proc] * material_intensity[y,tec,mat] * Capacity_recycled[y,tec,proc];

# recycled_material_process_total_ub is raised to Infinity in shared/utils.py after data loads (this
# file is in mod_1_path, before data -- can't do it here).
subject to recycled_material_process_total_calc {y in YEARS_WND diff YEAR_ONE, tec in TECHNOLOGIES, mat in MATERIALS}:
    Recycled_material_process_total[y,tec,mat] = sum {proc in RECYCLING_PROCESS_OF[tec,mat]} Recycled_material_process[y,tec,mat,proc];

unfix C_material_recycling_tech;  # Constraints.mod fixes it to 0 by default; free it here to let the equality below drive it
subject to c_material_recycling_tech_calc:
    C_material_recycling_tech = sum {p in PHASE_WND union PHASE_UP_TO, y in PHASE_STOP[p] diff YEAR_ONE, tec in MATERIAL_TECHS, mat in MATERIALS, proc in RECYCLING_PROCESS_OF[tec,mat]}
        actualisation_factor[p,y] * (recycling_cost_process[tec,mat,proc] - recycling_benefit_process[mat,proc]) * Recycled_material_process[y,tec,mat,proc] * 5 / 1e6;
