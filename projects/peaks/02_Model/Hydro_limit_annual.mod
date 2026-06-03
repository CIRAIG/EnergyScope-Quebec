# Déclaration du facteur limite (0.705 pour 70.5%)
param max_hydro_utilization_rate := 0.705;

# La contrainte pour 2050 basée sur la capacité annuelle globale F_Mult
subject to LIMIT_TOTAL_HYDRO_2050 :
    sum {t in PERIODS} (
        Monthly_Prod["HYDRO_DAM", t] +
        Monthly_Prod["HYDRO_RIVER", t] +
        Monthly_Prod["NEW_HYDRO_DAM", t] +
        Monthly_Prod["NEW_HYDRO_RIVER", t]
    )
    <=
    max_hydro_utilization_rate * (sum {t in PERIODS} t_op[t]) * (
        F_Mult["HYDRO_DAM"] * f_max["HYDRO_DAM"] +
        F_Mult["HYDRO_RIVER"] * f_max["HYDRO_RIVER"] +
        F_Mult["NEW_HYDRO_DAM"] * f_max["NEW_HYDRO_DAM"] +
        F_Mult["NEW_HYDRO_RIVER"] * f_max["NEW_HYDRO_RIVER"]
    );