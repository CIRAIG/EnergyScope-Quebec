# Déclaration du facteur limite (0.705 pour 70.5%)
param max_hydro_utilization_rate := 0.705;

# La contrainte pour 2050 basée sur la capacité annuelle globale F_Mult
subject to LIMIT_TOTAL_HYDRO_2050 {y in YEARS}:
    sum {t in PERIODS} (
        Monthly_Prod[y, "HYDRO_DAM", t] +
        Monthly_Prod[y, "HYDRO_RIVER", t] +
        Monthly_Prod[y, "NEW_HYDRO_DAM", t] +
        Monthly_Prod[y, "NEW_HYDRO_RIVER", t]
    )
    <=
    max_hydro_utilization_rate * (sum {t in PERIODS} t_op[t]) * (
        F_Mult[y, "HYDRO_DAM"] * f_max[y, "HYDRO_DAM"] +
        F_Mult[y, "HYDRO_RIVER"] * f_max[y, "HYDRO_RIVER"] +
        F_Mult[y, "NEW_HYDRO_DAM"] * f_max[y, "NEW_HYDRO_DAM"] +
        F_Mult[y, "NEW_HYDRO_RIVER"] * f_max[y, "NEW_HYDRO_RIVER"]
    );