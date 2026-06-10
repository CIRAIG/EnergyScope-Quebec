# Contrainte pour forcer certaines technologies à 0
subject to Fix_Techs_To_Zero {y in YEARS, t in TECHNOLOGIES}:
    if t in {'DEC_THHP_GAS','DEC_THHP_BIOGAS','HT_LT_DEC', 'NG_PYROLYSIS_PLASMA','NG_PYROLYSIS_THERMAL','DHN_HP_ELEC'} then #,'HYDRO_STORAGE'
        F_Mult[y, t] = 0;