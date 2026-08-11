# Capacite installee minimale (F_Mult)

subject to NEW_HYDRO_DAM:
    F_Mult['YEAR_2050',"NEW_HYDRO_DAM"] >= 4.00;

# Limite de captage de CO2 (CCS)
param ccs_limit_capture default 0.00 >= 0;

subject to co2_capture_limit_1:
    sum{t in PERIODS, i in RESOURCES union TECHNOLOGIES diff STORAGE_TECH:
        layers_in_out['YEAR_2050',i,"."] > 0}
        (abs(layers_in_out['YEAR_2050',i,"CO2_C"]) * F_Mult_t['YEAR_2050',i,t] * t_op[t])
    <= ccs_limit_capture;

