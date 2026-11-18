# PV/wind sub-technologies, loaded only with materials=True (see Subtechs_*.dat).
# The aggregated technologies of main (PV_ROOF, PV_GROUND, WIND_ONSHORE, NEW_WIND_ONSHORE, WIND_OFFSHORE)
# stay in the model with f_min = f_max = 0: only their sub-technologies produce.
set PV_SUBTECH;
set WIND_TECH;
set TECHNOLOGIES_OF_ELECGEN_FAMILIES;
set MODELS_OF_TECHNOLOGIES_OF_ELECGEN_FAMILIES {TECHNOLOGIES_OF_ELECGEN_FAMILIES};

# Full use of the installed wind capacity (PV_SUBTECH is covered by PV_TECH in QC_es_main.mod)
subject to wind_full_utilization {y in YEARS_WND diff YEAR_ONE, i in WIND_TECH, t in PERIODS}:
	F_Mult_t[y,i,t] = F_Mult[y,i]*c_p_t[y,i,t];
