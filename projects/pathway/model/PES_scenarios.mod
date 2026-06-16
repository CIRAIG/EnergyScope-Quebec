var Number_Of_Units {YEARS,TECHNOLOGIES diff INFRASTRUCTURE} >= 0;
# [Eq. 1.7] Number of purchased technologies. Integer variable (so that we have only integer multiples of the reference size)
subject to number_of_units {y in YEARS_WND diff YEAR_ONE, i in TECHNOLOGIES diff INFRASTRUCTURE}:
	Number_Of_Units [y,i] = F_Mult [y,i] / ref_size [y,i];


#Plan Hydro Québec : 10GW d'éolien installé / 0.3GW de pv/ ajout de 4GW de Hydro 

subject to wind_onshore_min {y in {"YEAR_2035","YEAR_2040","YEAR_2045","YEAR_2050"}}:
    F_Mult[y,"WIND_ONSHORE"] + F_Mult[y,"NEW_WIND_ONSHORE"] >= 10;

subject to pv_roof_min {y in {"YEAR_2035","YEAR_2040","YEAR_2045","YEAR_2050"}}:
    F_Mult[y,"PV_ROOF"]  >= 0.3;

subject to hydro_min {y in {"YEAR_2035","YEAR_2040","YEAR_2045","YEAR_2050"}}:
    F_Mult[y,"HYDRO_DAM"]+F_Mult[y,"HYDRO_RIVER"]+F_Mult[y,"NEW_HYDRO_DAM"]+F_Mult[y,"NEW_HYDRO_RIVER"] >= F_Mult["YEAR_2020","HYDRO_DAM"]+F_Mult["YEAR_2020","HYDRO_RIVER"] + 4;
/*
subject to co2_sequestration_limit {y in YEARS_WND diff YEAR_ONE}:
    sum{t in PERIODS, i in RESOURCES union TECHNOLOGIES diff STORAGE_TECH:
        layers_in_out[y,i,"CO2_S"] > 0}
        (abs(layers_in_out[y,i,"CO2_S"]) * F_Mult_t[y,i,t] * t_op[t])
    <= 5000;
*/

# No Elec trains
subject to no_electric_trains {y in YEARS_WND diff YEAR_ONE,t in {"TRAIN_FREIGHT_ELEC_LD","TRAIN_FREIGHT_ELEC_ELD"}}:
    F_Mult[y,t] = 0;


