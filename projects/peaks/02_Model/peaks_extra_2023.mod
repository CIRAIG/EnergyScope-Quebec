# 1. Déclaration des ensembles spécifiques aux pointes
set PEAK_PERIODS;

# Limite de la capacité de la centrale à gaz (Taille globale du parc)
subject to CCGT_F_Mult_fixed:
    F_Mult["CCGT"] = 0.411;

# Retirer la centrale à gaz lors de périodes normales et estivales (Mois 1 à 12)
subject to CCGT_zero_selected_periods {p in PERIODS : p in {1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12}}:
    F_Mult_t["CCGT", p] = 0;

subject to CCGT_force_max_during_peaks {p in PERIODS : p >= 13}:
    F_Mult_t["CCGT", p] = 0.411;


