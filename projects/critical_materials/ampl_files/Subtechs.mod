# Sous-technologies PV/eolien, chargees uniquement avec materials=True (voir Subtechs_*.dat).
# Les technologies agregees de main (PV_ROOF, PV_GROUND, WIND_ONSHORE, NEW_WIND_ONSHORE, WIND_OFFSHORE)
# restent dans le modele avec f_min = f_max = 0: seules leurs sous-technologies produisent.
set PV_SUBTECH;
set WIND_TECH;
set TECHNOLOGIES_OF_ELECGEN_FAMILIES;
set MODELS_OF_TECHNOLOGIES_OF_ELECGEN_FAMILIES {TECHNOLOGIES_OF_ELECGEN_FAMILIES};

# Utilisation pleine de l'eolien installe (PV_SUBTECH est couvert par PV_TECH dans QC_es_main.mod)
subject to wind_full_utilization {y in YEARS_WND diff YEAR_ONE, i in WIND_TECH, t in PERIODS}:
	F_Mult_t[y,i,t] = F_Mult[y,i]*c_p_t[y,i,t];
