#Plan d'action d'HQ 2035 - https://www.hydroquebec.com/data/a-propos/pdf/plan-action-2035.pdf
subject to NEW_HYDRO_DAM:
    F_Mult['YEAR_2050',"NEW_HYDRO_DAM"] = 4;
subject to NEW_WIND:
    F_Mult['YEAR_2050',"WIND_ONSHORE"] >= 10;
subject to NEW_SOLAR_ROOF:
    F_Mult['YEAR_2050',"PV_ROOF"] >= 0.15;
subject to NEW_SOLAR_GROUND:
    F_Mult['YEAR_2050', "PV_GROUND"] >= 0.15;

#Ligne de transport: 5000 km de nouvelle ligne ?