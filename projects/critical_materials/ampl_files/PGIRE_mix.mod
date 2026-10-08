# Bornes de puissance installee PGIRE (optionnel, desactive par defaut): run_pathway(..., extra_files=['.../PGIRE_mix.mod'])
# PGIRE_mix -- bornes de puissance installee totale par filiere (Plan de gestion integree des
# ressources energetiques du Quebec 2026-2050, p.42-43), lecture "total" (pas additionnel),
# eolien onshore seulement (WIND_ONSHORE+NEW_WIND_ONSHORE, pas WIND_OFFSHORE), solaire = PV_GROUND
# ("grands parcs") seulement, pas PV_ROOF (solaire decentralise, pas de chiffre dans le PGIRE).
# Hydro exclu (ambiguite perimetre Quebec vs imports Terre-Neuve-et-Labrador). Pas de bornes 2030
# (aucune fourchette donnee dans le PGIRE pour cette annee). Teste OK (faisable) le 2026-09-18.
subject to pgire_wind_min_2040:
    sum {i in MODELS_OF_TECHNOLOGIES_OF_ELECGEN_FAMILIES["WIND_ONSHORE"]} F_Mult["YEAR_2040",i]
  + sum {i in MODELS_OF_TECHNOLOGIES_OF_ELECGEN_FAMILIES["NEW_WIND_ONSHORE"]} F_Mult["YEAR_2040",i] >= 12;
subject to pgire_wind_max_2040:
    sum {i in MODELS_OF_TECHNOLOGIES_OF_ELECGEN_FAMILIES["WIND_ONSHORE"]} F_Mult["YEAR_2040",i]
  + sum {i in MODELS_OF_TECHNOLOGIES_OF_ELECGEN_FAMILIES["NEW_WIND_ONSHORE"]} F_Mult["YEAR_2040",i] <= 16;

subject to pgire_wind_min_2050:
    sum {i in MODELS_OF_TECHNOLOGIES_OF_ELECGEN_FAMILIES["WIND_ONSHORE"]} F_Mult["YEAR_2050",i]
  + sum {i in MODELS_OF_TECHNOLOGIES_OF_ELECGEN_FAMILIES["NEW_WIND_ONSHORE"]} F_Mult["YEAR_2050",i] >= 21;
subject to pgire_wind_max_2050:
    sum {i in MODELS_OF_TECHNOLOGIES_OF_ELECGEN_FAMILIES["WIND_ONSHORE"]} F_Mult["YEAR_2050",i]
  + sum {i in MODELS_OF_TECHNOLOGIES_OF_ELECGEN_FAMILIES["NEW_WIND_ONSHORE"]} F_Mult["YEAR_2050",i] <= 25;

subject to pgire_pv_ground_min_2040:
    sum {i in MODELS_OF_TECHNOLOGIES_OF_ELECGEN_FAMILIES["PV_GROUND"]} F_Mult["YEAR_2040",i] >= 1;
subject to pgire_pv_ground_max_2040:
    sum {i in MODELS_OF_TECHNOLOGIES_OF_ELECGEN_FAMILIES["PV_GROUND"]} F_Mult["YEAR_2040",i] <= 3;

subject to pgire_pv_ground_max_2050:
    sum {i in MODELS_OF_TECHNOLOGIES_OF_ELECGEN_FAMILIES["PV_GROUND"]} F_Mult["YEAR_2050",i] <= 5;
