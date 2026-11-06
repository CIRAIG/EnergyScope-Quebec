# Choix libre du moteur (aimants permanents PM / induction Ind) et de la batterie (6 chimies) des vehicules electriques et hybrides.
# Charge par run_pathway(..., materials=True, motor_market_share=False, batteries_market_share=False) avec Vehicle_choice.dat (run_build_vehicle_choice.py).
# Chaque famille de vehicules garde une seule capacite F_new / F_decom ; on la repartit entre types de moteur et entre chimies de batterie. La matiere
# d'un vehicule est la somme de trois parts (carrosserie, moteur, batterie), donc les deux repartitions sont independantes et le modele reste lineaire.
# Sans cout par moteur ni par chimie (pas de donnees), le choix ne depend que des limites de materiaux. Une part qui n'est pas libre
# (free_motor_choice / free_battery_choice = 0) est forcee aux parts de marche de MS_Battery_Motor_LDV (batt_share_ref, motor_share_ref).

set VEH_CHOICE_TECHS within TECHNOLOGIES := {'CAR_EV','CAR_HEV','CAR_PHEV','SUV_EV','SUV_HY_GASOLINE','SUV_PHEV_GASOLINE',
                                             'BUS_EV','BUS_HY_DIESEL','COACH_EV','COACH_HY_DIESEL','SCHOOLBUS_EV','SCHOOLBUS_HY_DIESEL'};
set BATT_CHEM := {'Gr-LFP','Gr-LMFP','Gr-NMC','Gr-NCA','Gr-LMO','Na-ion'};
set MOTOR_TYPE := {'PM','Ind'};

param free_motor_choice binary default 0;      # 1: l'optimiseur choisit le type de moteur ; 0: parts de marche (run_pathway fixe ce parametre)
param free_battery_choice binary default 0;    # 1: l'optimiseur choisit la chimie de batterie ; 0: parts de marche (run_pathway fixe ce parametre)
param batt_share_ref {YEARS,BATT_CHEM} >= 0 default 0;
param motor_share_ref {MOTOR_TYPE} >= 0 default 0;

# Intensites [meme unite que material_intensity] : carrosserie, moteur par type, batterie par chimie
param veh_body_int  {YEARS,VEH_CHOICE_TECHS,MATERIALS} >= 0 default 0;
param veh_motor_int {YEARS,VEH_CHOICE_TECHS,MOTOR_TYPE,MATERIALS} >= 0 default 0;
param veh_batt_int  {YEARS,VEH_CHOICE_TECHS,BATT_CHEM,MATERIALS} >= 0 default 0;

# Capacite neuve et decommissionnee par type de moteur / chimie (generations construites par le modele ; le parc existant de 2015_2020 garde ses intensites)
var F_new_motor   {PHASE_WND union PHASE_UP_TO, VEH_CHOICE_TECHS, MOTOR_TYPE} >= 0;
var F_new_batt    {PHASE_WND union PHASE_UP_TO, VEH_CHOICE_TECHS, BATT_CHEM} >= 0;
var F_decom_motor {PHASE_WND union PHASE_UP_TO, PHASE_WND union PHASE_UP_TO, VEH_CHOICE_TECHS, MOTOR_TYPE} >= 0;
var F_decom_batt  {PHASE_WND union PHASE_UP_TO, PHASE_WND union PHASE_UP_TO, VEH_CHOICE_TECHS, BATT_CHEM} >= 0;

subject to veh_new_motor_split {p in PHASE_WND union PHASE_UP_TO, tec in VEH_CHOICE_TECHS}:
    sum {m in MOTOR_TYPE} F_new_motor[p,tec,m] = F_new[p,tec];
subject to veh_new_batt_split {p in PHASE_WND union PHASE_UP_TO, tec in VEH_CHOICE_TECHS}:
    sum {c in BATT_CHEM} F_new_batt[p,tec,c] = F_new[p,tec];
subject to veh_decom_motor_split {pd in PHASE_WND union PHASE_UP_TO, pb in PHASE_WND union PHASE_UP_TO, tec in VEH_CHOICE_TECHS}:
    sum {m in MOTOR_TYPE} F_decom_motor[pd,pb,tec,m] = F_decom[pd,pb,tec];
subject to veh_decom_batt_split {pd in PHASE_WND union PHASE_UP_TO, pb in PHASE_WND union PHASE_UP_TO, tec in VEH_CHOICE_TECHS}:
    sum {c in BATT_CHEM} F_decom_batt[pd,pb,tec,c] = F_decom[pd,pb,tec];

# On ne decommissionne pas plus d'un type que la generation n'en a installe
subject to veh_cohort_motor {pb in PHASE_WND union PHASE_UP_TO, tec in VEH_CHOICE_TECHS, m in MOTOR_TYPE}:
    sum {pd in PHASE_WND union PHASE_UP_TO} F_decom_motor[pd,pb,tec,m] <= F_new_motor[pb,tec,m];
subject to veh_cohort_batt {pb in PHASE_WND union PHASE_UP_TO, tec in VEH_CHOICE_TECHS, c in BATT_CHEM}:
    sum {pd in PHASE_WND union PHASE_UP_TO} F_decom_batt[pd,pb,tec,c] <= F_new_batt[pb,tec,c];

# Part non libre : parts de marche
subject to veh_new_motor_ref {p in PHASE_WND union PHASE_UP_TO, tec in VEH_CHOICE_TECHS, m in MOTOR_TYPE: free_motor_choice == 0}:
    F_new_motor[p,tec,m] = motor_share_ref[m] * F_new[p,tec];
subject to veh_decom_motor_ref {pd in PHASE_WND union PHASE_UP_TO, pb in PHASE_WND union PHASE_UP_TO, tec in VEH_CHOICE_TECHS, m in MOTOR_TYPE: free_motor_choice == 0}:
    F_decom_motor[pd,pb,tec,m] = motor_share_ref[m] * F_decom[pd,pb,tec];
subject to veh_new_batt_ref {p in PHASE_WND union PHASE_UP_TO, y in PHASE_STOP[p], tec in VEH_CHOICE_TECHS, c in BATT_CHEM: free_battery_choice == 0}:
    F_new_batt[p,tec,c] = batt_share_ref[y,c] * F_new[p,tec];
subject to veh_decom_batt_ref {pd in PHASE_WND union PHASE_UP_TO, pb in PHASE_WND union PHASE_UP_TO, y in PHASE_STOP[pb], tec in VEH_CHOICE_TECHS, c in BATT_CHEM: free_battery_choice == 0}:
    F_decom_batt[pd,pb,tec,c] = batt_share_ref[y,c] * F_decom[pd,pb,tec];

# Demande brute : remplace material_content_year_calc de Constraints.mod pour ces familles (generations construites par le modele)
drop {p in PHASE_WND union PHASE_UP_TO, y in PHASE_STOP[p], tec in VEH_CHOICE_TECHS, mat in MATERIALS} material_content_year_calc[p,y,tec,mat];
subject to veh_material_content_year {p in PHASE_WND union PHASE_UP_TO, y in PHASE_STOP[p], tec in VEH_CHOICE_TECHS, mat in MATERIALS}:
    Material_content_year[y,tec,mat] = (veh_body_int[y,tec,mat] * F_new[p,tec]
        + sum {m in MOTOR_TYPE} veh_motor_int[y,tec,m,mat] * F_new_motor[p,tec,m]
        + sum {c in BATT_CHEM} veh_batt_int[y,tec,c,mat] * F_new_batt[p,tec,c]) / 5;

# Matiere decommissionnee : remplace decommissioned_material_calc de Constraints.mod pour ces familles.
# Decommissionnement anticipe (parc existant, puis generations du modele) et fin de vie de la generation `age` (F_old = F_new - decommissionne en avance)
drop {pd in PHASE_WND union PHASE_UP_TO, yd in PHASE_STOP[pd], tec in VEH_CHOICE_TECHS, mat in MATERIALS} decommissioned_material_calc[pd,yd,tec,mat];
subject to veh_decommissioned_material {pd in PHASE_WND union PHASE_UP_TO, yd in PHASE_STOP[pd], tec in VEH_CHOICE_TECHS, mat in MATERIALS}:
    Decommissioned_material[yd,tec,mat] = 1/5 * (
        sum {yb in PHASE_STOP["2015_2020"]} material_intensity[yb,tec,mat] * F_decom[pd,"2015_2020",tec]
        + sum {pb in PHASE_WND union PHASE_UP_TO, yb in PHASE_STOP[pb]} (
              veh_body_int[yb,tec,mat] * F_decom[pd,pb,tec]
              + sum {m in MOTOR_TYPE} veh_motor_int[yb,tec,m,mat] * F_decom_motor[pd,pb,tec,m]
              + sum {c in BATT_CHEM} veh_batt_int[yb,tec,c,mat] * F_decom_batt[pd,pb,tec,c])
        + sum {pb in AGE[tec,pd] diff {"STILL_IN_USE"} diff (PHASE_WND union PHASE_UP_TO), yb in PHASE_STOP[pb]}
              material_intensity[yb,tec,mat] * F_old[pd,tec]
        + sum {pb in AGE[tec,pd] inter (PHASE_WND union PHASE_UP_TO), yb in PHASE_STOP[pb]} (
              veh_body_int[yb,tec,mat] * F_old[pd,tec]
              + sum {m in MOTOR_TYPE} veh_motor_int[yb,tec,m,mat] * (F_new_motor[pb,tec,m] - sum {p2 in PHASE_WND union PHASE_UP_TO} F_decom_motor[p2,pb,tec,m])
              + sum {c in BATT_CHEM} veh_batt_int[yb,tec,c,mat] * (F_new_batt[pb,tec,c] - sum {p2 in PHASE_WND union PHASE_UP_TO} F_decom_batt[p2,pb,tec,c]))
    );
