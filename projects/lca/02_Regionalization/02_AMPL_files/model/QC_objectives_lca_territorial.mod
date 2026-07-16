
param territorial_op {YEARS,INDICATORS,TECHNOLOGIES} default 0;
param territorial_constr {YEARS,INDICATORS,TECHNOLOGIES} default 0;
param territorial_decom {YEARS,INDICATORS,TECHNOLOGIES} default 0;
param territorial_res {YEARS,INDICATORS,RESOURCES} default 0;
param limit_territorial {YEARS,INDICATORS} default Infinity;
var TERRITORIAL_constr {YEARS,INDICATORS,TECHNOLOGIES};
var TERRITORIAL_decom {YEARS,INDICATORS,TECHNOLOGIES};
var TERRITORIAL_op {YEARS,INDICATORS,TECHNOLOGIES};
var TERRITORIAL_res {YEARS,INDICATORS,RESOURCES};
var TotalTERRITORIAL {YEARS,INDICATORS};

param limit_abroad {YEARS,INDICATORS} default Infinity;
var ABROAD_constr {YEARS,INDICATORS,TECHNOLOGIES};
var ABROAD_decom {YEARS,INDICATORS,TECHNOLOGIES};
var ABROAD_op {YEARS,INDICATORS,TECHNOLOGIES};
var ABROAD_res {YEARS,INDICATORS,RESOURCES};
var TotalABROAD {YEARS,INDICATORS};

# Construction
subject to territorial_constr_calc {y in YEARS_WND diff YEAR_ONE, id in INDICATORS, i in TECHNOLOGIES}:
  TERRITORIAL_constr[y,id,i] = territorial_constr[y,id,i] * F_Mult[y,i] / lifetime[y,i];

# Decommission
subject to territorial_decom_calc {y in YEARS_WND diff YEAR_ONE, id in INDICATORS, i in TECHNOLOGIES}:
  TERRITORIAL_decom[y,id,i] = territorial_decom[y,id,i] * F_Mult[y,i] / lifetime[y,i];

# Operation
subject to territorial_op_calc {y in YEARS_WND diff YEAR_ONE, id in INDICATORS, i in TECHNOLOGIES}:
  TERRITORIAL_op[y,id,i] = territorial_op[y,id,i] * sum {t in PERIODS} (t_op[t] * F_Mult_t[y,i,t]);

# Resources
subject to territorial_res_calc {y in YEARS_WND diff YEAR_ONE, id in INDICATORS, r in RESOURCES}:
  TERRITORIAL_res[y,id,r] = territorial_res[y,id,r] * sum {t in PERIODS} (t_op[t] * F_Mult_t[y,r,t]);

# Abroad impacts
subject to abroad_constr_calc {y in YEARS_WND diff YEAR_ONE, id in INDICATORS, i in TECHNOLOGIES}:
  ABROAD_constr[y,id,i] = LCIA_constr[y,id,i] - TERRITORIAL_constr[y,id,i];

subject to abroad_decom_calc {y in YEARS_WND diff YEAR_ONE, id in INDICATORS, i in TECHNOLOGIES}:
  ABROAD_decom[y,id,i] = LCIA_decom[y,id,i] - TERRITORIAL_decom[y,id,i];

subject to abroad_op_calc {y in YEARS_WND diff YEAR_ONE, id in INDICATORS, i in TECHNOLOGIES}:
  ABROAD_op[y,id,i] = LCIA_op[y,id,i] - TERRITORIAL_op[y,id,i];

subject to abroad_res_calc {y in YEARS_WND diff YEAR_ONE, id in INDICATORS, r in RESOURCES}:
  ABROAD_res[y,id,r] = LCIA_res[y,id,r] - TERRITORIAL_res[y,id,r];

subject to totalTERRITORIAL_calc_r {y in YEARS_WND diff YEAR_ONE, id in INDICATORS}:
  TotalTERRITORIAL[y,id] = sum {i in TECHNOLOGIES} (TERRITORIAL_constr[y,id,i] + TERRITORIAL_decom[y,id,i] + TERRITORIAL_op[y,id,i]) + sum{r in RESOURCES} (TERRITORIAL_res[y,id,r]);

subject to totalABROAD_calc_r {y in YEARS_WND diff YEAR_ONE, id in INDICATORS}:
  TotalABROAD[y,id] = sum {i in TECHNOLOGIES} (ABROAD_constr[y,id,i] + ABROAD_decom[y,id,i] + ABROAD_op[y,id,i]) + sum{r in RESOURCES} (ABROAD_res[y,id,r]);

subject to totalTERRITORIAL_limit {y in YEARS_WND diff YEAR_ONE, id in INDICATORS}:
  TotalTERRITORIAL[y,id] <= limit_territorial[y,id];

var TotalTERRITORIAL_m_CCS_all{y in YEARS};
subject to TERRITORIAL_m_CCS_all_cal{y in YEARS_WND diff YEAR_ONE}:
  TotalTERRITORIAL_m_CCS_all[y] = TotalTERRITORIAL[y,'m_CCS_all'] + TotalCost[y]*1e-6;

subject to totalABROAD_limit {y in YEARS_WND diff YEAR_ONE, id in INDICATORS}:
  TotalABROAD[y,id] <= limit_abroad[y,id];

var TotalABROAD_m_CCS_all{y in YEARS};
subject to ABROAD_m_CCS_all_cal{y in YEARS_WND diff YEAR_ONE}:
  TotalABROAD_m_CCS_all[y] = TotalABROAD[y,'m_CCS_all'] + TotalCost[y]*1e-6;

