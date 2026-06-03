# ===========================================================================
# 1. Contrainte de couplage des capacités
# ===========================================================================
subject to link_hp_normal_capacity {y in YEARS}:
    F_Mult[y, 'DEC_HP_ELEC'] = F_Mult[y, 'DEC_HP_ELEC_WINTER'];

subject to link_hp_peak_capacity {y in YEARS}:
    F_Mult[y, 'DEC_HP_ELEC_PEAK'] = F_Mult[y, 'DEC_HP_ELEC_WINTER'];

# ===========================================================================
# 2. Gestion de l'opération
# ===========================================================================
subject to turn_off_normal_hp_new {y in YEARS, p in PERIODS: p <= 3 or p >= 12}:
    F_Mult_t[y, 'DEC_HP_ELEC', p] <= 0.00001 * F_Mult[y, 'DEC_HP_ELEC_WINTER'];

subject to turn_off_winter_hp_new {y in YEARS, p in PERIODS: (p >= 4 and p <= 11) or p >= 13}:
    F_Mult_t[y, 'DEC_HP_ELEC_WINTER', p] <= 0.00001 * F_Mult[y, 'DEC_HP_ELEC_WINTER'];

subject to turn_off_peak_hp_new {y in YEARS, p in PERIODS: p <= 12}:
    F_Mult_t[y, 'DEC_HP_ELEC_PEAK', p] <= 0.00001 * F_Mult[y, 'DEC_HP_ELEC_WINTER'];

# ===========================================================================
# 3. La contrainte combinée spécifique
# ===========================================================================
subject to op_strategy_decen_1_winter_hp_combined {y in YEARS, t in PERIODS}:
    (F_Mult_t [y, 'DEC_HP_ELEC', t] + F_Mult_t [y, 'DEC_HP_ELEC_WINTER', t] + F_Mult_t [y, 'DEC_HP_ELEC_PEAK', t])
    + (X_Solar_Backup_Aux ['DEC_HP_ELEC', t] + X_Solar_Backup_Aux ['DEC_HP_ELEC_WINTER', t] + X_Solar_Backup_Aux ['DEC_HP_ELEC_PEAK', t])
    >=
    (sum {t2 in PERIODS} (F_Mult_t [y, 'DEC_HP_ELEC', t2] * t_op [t2]) + sum {t2 in PERIODS} (F_Mult_t [y, 'DEC_HP_ELEC_WINTER', t2] * t_op [t2]) + sum {t2 in PERIODS} (F_Mult_t [y, 'DEC_HP_ELEC_PEAK', t2] * t_op [t2]))
    * ((end_uses_input["HEAT_LOW_T_HW"] / total_time + end_uses_input["HEAT_LOW_T_SH"] * heating_month [t] / t_op [t]) / (end_uses_input["HEAT_LOW_T_HW"] + end_uses_input["HEAT_LOW_T_SH"]));