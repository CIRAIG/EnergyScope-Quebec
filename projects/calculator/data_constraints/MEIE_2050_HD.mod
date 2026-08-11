# Capacite installee minimale (F_Mult)

# Limite de captage de CO2 (CCS)
param ccs_limit_capture default 25.00 >= 0;

subject to co2_capture_limit_1:
    sum{t in PERIODS, i in RESOURCES union TECHNOLOGIES diff STORAGE_TECH:
        layers_in_out['YEAR_2050',i,"CO2_C"] > 0}
        (abs(layers_in_out['YEAR_2050',i,"CO2_C"]) * F_Mult_t['YEAR_2050',i,t] * t_op[t])
    <= ccs_limit_capture;

