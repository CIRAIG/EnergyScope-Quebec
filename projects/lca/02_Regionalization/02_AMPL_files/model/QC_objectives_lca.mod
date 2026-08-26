
set INDICATORS;

param lcia_op {YEARS,INDICATORS,TECHNOLOGIES} default 0;
param lcia_constr {YEARS,INDICATORS,TECHNOLOGIES} default 0;
param lcia_decom {YEARS,INDICATORS,TECHNOLOGIES} default 0;
param lcia_res {YEARS,INDICATORS,RESOURCES} default 0;
param limit_lcia {YEARS,INDICATORS} default Infinity;
var LCIA_constr {YEARS,INDICATORS,TECHNOLOGIES};
var LCIA_decom {YEARS,INDICATORS,TECHNOLOGIES};
var LCIA_op {YEARS,INDICATORS,TECHNOLOGIES};
var LCIA_res {YEARS,INDICATORS,RESOURCES};
var TotalLCIA {YEARS,INDICATORS};

# Construction
subject to lcia_constr_calc {y in YEARS_WND diff YEAR_ONE, id in INDICATORS, i in TECHNOLOGIES}:
  LCIA_constr[y,id,i] = lcia_constr[y,id,i] * F_Mult[y,i] / lifetime[y,i];

# Decommission
subject to lcia_decom_calc {y in YEARS_WND diff YEAR_ONE, id in INDICATORS, i in TECHNOLOGIES}:
  LCIA_decom[y,id,i] = lcia_decom[y,id,i] * F_Mult[y,i] / lifetime[y,i];

# Operation
subject to lcia_op_calc {y in YEARS_WND diff YEAR_ONE, id in INDICATORS, i in TECHNOLOGIES}:
  LCIA_op[y,id,i] = lcia_op[y,id,i] * sum {t in PERIODS} (t_op[t] * F_Mult_t[y,i,t]);

# Resources
subject to lcia_res_calc {y in YEARS_WND diff YEAR_ONE, id in INDICATORS, r in RESOURCES}:
  LCIA_res[y,id,r] = lcia_res[y,id,r] * sum {t in PERIODS} (t_op[t] * F_Mult_t[y,r,t]);

subject to totalLCIA_calc_r {y in YEARS_WND diff YEAR_ONE, id in INDICATORS}:
  TotalLCIA[y,id] = sum {i in TECHNOLOGIES} (LCIA_constr[y,id,i] + LCIA_decom[y,id,i] + LCIA_op[y,id,i]) + sum{r in RESOURCES} (LCIA_res[y,id,r]);

subject to totalLCIA_limit {y in YEARS_WND diff YEAR_ONE, id in INDICATORS}:
  TotalLCIA[y,id] <= limit_lcia[y,id];

var TotalLCIA_m_CCS_all{y in YEARS};
subject to LCIA_m_CCS_all_cal{y in YEARS_WND diff YEAR_ONE}:
  TotalLCIA_m_CCS_all[y] = TotalLCIA[y,'m_CCS_all'] + TotalCost[y]*1e-6;

var TotalLCIA_REQD{y in YEARS};
subject to LCIA_REQD_cal{y in YEARS_WND diff YEAR_ONE}:
  TotalLCIA_REQD[y] = TotalLCIA[y,'REQD'] + TotalCost[y]*1e-6;

var TotalLCIA_RHHD{y in YEARS};
subject to LCIA_RHHD_cal{y in YEARS_WND diff YEAR_ONE}:
  TotalLCIA_RHHD[y] = TotalLCIA[y,'RHHD'] + TotalCost[y]*1e-6;