# Bornes de puissance installee PGIRE (optionnel, desactive par defaut): run_pathway(..., extra_files=['.../PGIRE_mix.mod'])
# A VERIFIER
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
