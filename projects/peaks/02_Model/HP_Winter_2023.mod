# ===========================================================================
# DÉCLARATION DES PARAMÈTRES (Requis pour le .dat)
# ===========================================================================
#param cop_normal;
#param cop_winter;
#param cop_peak;

# ===========================================================================
# 1. Couplage flexible (Inégalités au lieu de Égalités)
# ===========================================================================
subject to link_hp_winter_capacity {y in YEARS}:
    F_Mult[y, 'DEC_HP_ELEC_WINTER'] <= F_Mult[y, 'DEC_HP_ELEC'];

subject to link_hp_peak_capacity {y in YEARS}:
    F_Mult[y, 'DEC_HP_ELEC_PEAK'] <= F_Mult[y, 'DEC_HP_ELEC'];

# ===========================================================================
# 2. Gestion de l'opération (Coupures nettes à 0)
# ===========================================================================
# En hiver (périodes 1, 2, 3 et 12, 13), la HP normale est coupée
subject to turn_off_normal_hp_new {y in YEARS, p in PERIODS: p <= 3 or p >= 12}:
    F_Mult_t[y, 'DEC_HP_ELEC', p] = 0;

# En été (périodes 4 à 11), la HP hiver est coupée
subject to turn_off_winter_hp_new {y in YEARS, p in PERIODS: p >= 4 and p <= 11}:
    F_Mult_t[y, 'DEC_HP_ELEC_WINTER', p] = 0;

# La HP de pointe est coupée sauf en période de pointe extrême (période 13)
subject to turn_off_peak_hp_new {y in YEARS, p in PERIODS: p <= 12}:
    F_Mult_t[y, 'DEC_HP_ELEC_PEAK', p] = 0;

# ===========================================================================
# 3. La contrainte combinée spécifique
# ===========================================================================
#subject to op_strategy_decen_1_winter_hp_combined {y in YEARS, t in PERIODS}:
#    (F_Mult_t [y, 'DEC_HP_ELEC', t] + F_Mult_t [y, 'DEC_HP_ELEC_WINTER', t] + F_Mult_t [y, 'DEC_HP_ELEC_PEAK', t])
#    + (X_Solar_Backup_Aux [y, 'DEC_HP_ELEC', t] + X_Solar_Backup_Aux [y, 'DEC_HP_ELEC_WINTER', t] + X_Solar_Backup_Aux [y, 'DEC_HP_ELEC_PEAK', t])
#    >=
#    (sum {t2 in PERIODS} (F_Mult_t [y, 'DEC_HP_ELEC', t2] * t_op [t2]) + sum {t2 in PERIODS} (F_Mult_t [y, 'DEC_HP_ELEC_WINTER', t2] * t_op [t2]) + sum {t2 in PERIODS} (F_Mult_t [y, 'DEC_HP_ELEC_PEAK', t2] * t_op [t2]))
#    * ((end_uses_input[y, "HEAT_LOW_T_HW"] / total_time + end_uses_input[y, "HEAT_LOW_T_SH"] * heating_month [t] / t_op [t]) / (end_uses_input[y, "HEAT_LOW_T_HW"] + end_uses_input[y, "HEAT_LOW_T_SH"]));