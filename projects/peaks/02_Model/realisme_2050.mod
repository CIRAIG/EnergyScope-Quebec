# Contrainte pour forcer certaines technologies à 0
subject to Fix_Techs_To_Zero {y in YEARS, t in TECHNOLOGIES}:
    if t in {'DEC_THHP_GAS','DEC_THHP_BIOGAS','DHN_HP_ELEC'} then  #'NG_PYROLYSIS_PLASMA','NG_PYROLYSIS_THERMAL' ,'HYDRO_STORAGE','HT_LT_DEC',
        F_Mult[y, t] = 0;