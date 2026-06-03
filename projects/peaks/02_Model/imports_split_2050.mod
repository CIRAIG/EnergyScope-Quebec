# ==========================================
# EXTENSION : LIMITES DE PUISSANCE HORAIRES (CORRIGÉ)
# ==========================================

# 1. Déclaration et assignation du paramètre (2D)
param f_mult_max {r in RESOURCES, p in PERIODS} :=
    if r == 'CHURCHILL_FALLS' then 7.2
    else if r == 'ELECTRICITY_OTHER' then 10.0
    else 1e8;

# 2. Contrainte branchée sur la variable EnergyScope
subject to limit_puissance_importation {r in RESOURCES, p in PERIODS}:
    F_Mult_t[r, p] <= f_mult_max[r, p];