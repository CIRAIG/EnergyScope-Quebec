
param territorial_op {IAM,SSP_RCP,YEARS,INDICATORS,TECHNOLOGIES} default 0;
param territorial_constr {IAM,SSP_RCP,YEARS,INDICATORS,TECHNOLOGIES} default 0;
param territorial_decom {IAM,SSP_RCP,YEARS,INDICATORS,TECHNOLOGIES} default 0;
param territorial_res {IAM,SSP_RCP,YEARS,INDICATORS,RESOURCES} default 0;
param limit_territorial {IAM,SSP_RCP,YEARS,INDICATORS} default Infinity;
var TERRITORIAL_constr {IAM,SSP_RCP,YEARS,INDICATORS,TECHNOLOGIES};
var TERRITORIAL_decom {IAM,SSP_RCP,YEARS,INDICATORS,TECHNOLOGIES};
var TERRITORIAL_op {IAM,SSP_RCP,YEARS,INDICATORS,TECHNOLOGIES};
var TERRITORIAL_res {IAM,SSP_RCP,YEARS,INDICATORS,RESOURCES};
var TotalTERRITORIAL {IAM,SSP_RCP,YEARS,INDICATORS};

param limit_abroad {IAM,SSP_RCP,YEARS,INDICATORS} default Infinity;
var ABROAD_constr {IAM,SSP_RCP,YEARS,INDICATORS,TECHNOLOGIES};
var ABROAD_decom {IAM,SSP_RCP,YEARS,INDICATORS,TECHNOLOGIES};
var ABROAD_op {IAM,SSP_RCP,YEARS,INDICATORS,TECHNOLOGIES};
var ABROAD_res {IAM,SSP_RCP,YEARS,INDICATORS,RESOURCES};
var TotalABROAD {IAM,SSP_RCP,YEARS,INDICATORS};

# Construction
subject to territorial_constr_calc {m in IAM, sr in SSP_RCP, y in YEARS_WND diff YEAR_ONE, id in INDICATORS, i in TECHNOLOGIES}:
  TERRITORIAL_constr[m,sr,y,id,i] = territorial_constr[m,sr,y,id,i] * F_Mult[y,i] / lifetime[y,i];

# Decommission
subject to territorial_decom_calc {m in IAM, sr in SSP_RCP, y in YEARS_WND diff YEAR_ONE, id in INDICATORS, i in TECHNOLOGIES}:
  TERRITORIAL_decom[m,sr,y,id,i] = territorial_decom[m,sr,y,id,i] * F_Mult[y,i] / lifetime[y,i];

# Operation
subject to territorial_op_calc {m in IAM, sr in SSP_RCP, y in YEARS_WND diff YEAR_ONE, id in INDICATORS, i in TECHNOLOGIES}:
  TERRITORIAL_op[m,sr,y,id,i] = territorial_op[m,sr,y,id,i] * sum {t in PERIODS} (t_op[t] * F_Mult_t[y,i,t]);

# Resources
subject to territorial_res_calc {m in IAM, sr in SSP_RCP, y in YEARS_WND diff YEAR_ONE, id in INDICATORS, r in RESOURCES}:
  TERRITORIAL_res[m,sr,y,id,r] = territorial_res[m,sr,y,id,r] * sum {t in PERIODS} (t_op[t] * F_Mult_t[y,r,t]);

# Abroad impacts
subject to abroad_constr_calc {m in IAM, sr in SSP_RCP, y in YEARS_WND diff YEAR_ONE, id in INDICATORS, i in TECHNOLOGIES}:
  ABROAD_constr[m,sr,y,id,i] = LCIA_constr[m,sr,y,id,i] - TERRITORIAL_constr[m,sr,y,id,i];

subject to abroad_decom_calc {m in IAM, sr in SSP_RCP, y in YEARS_WND diff YEAR_ONE, id in INDICATORS, i in TECHNOLOGIES}:
  ABROAD_decom[m,sr,y,id,i] = LCIA_decom[m,sr,y,id,i] - TERRITORIAL_decom[m,sr,y,id,i];

subject to abroad_op_calc {m in IAM, sr in SSP_RCP, y in YEARS_WND diff YEAR_ONE, id in INDICATORS, i in TECHNOLOGIES}:
  ABROAD_op[m,sr,y,id,i] = LCIA_op[m,sr,y,id,i] - TERRITORIAL_op[m,sr,y,id,i];

subject to abroad_res_calc {m in IAM, sr in SSP_RCP, y in YEARS_WND diff YEAR_ONE, id in INDICATORS, r in RESOURCES}:
  ABROAD_res[m,sr,y,id,r] = LCIA_res[m,sr,y,id,r] - TERRITORIAL_res[m,sr,y,id,r];

subject to totalTERRITORIAL_calc_r {m in IAM, sr in SSP_RCP, y in YEARS_WND diff YEAR_ONE, id in INDICATORS}:
  TotalTERRITORIAL[m,sr,y,id] = sum {i in TECHNOLOGIES} (TERRITORIAL_constr[m,sr,y,id,i] + TERRITORIAL_decom[m,sr,y,id,i] + TERRITORIAL_op[m,sr,y,id,i]) + sum{r in RESOURCES} (TERRITORIAL_res[m,sr,y,id,r]);

subject to totalABROAD_calc_r {m in IAM, sr in SSP_RCP, y in YEARS_WND diff YEAR_ONE, id in INDICATORS}:
  TotalABROAD[m,sr,y,id] = sum {i in TECHNOLOGIES} (ABROAD_constr[m,sr,y,id,i] + ABROAD_decom[m,sr,y,id,i] + ABROAD_op[m,sr,y,id,i]) + sum{r in RESOURCES} (ABROAD_res[m,sr,y,id,r]);

subject to totalTERRITORIAL_limit {m in IAM, sr in SSP_RCP, y in YEARS_WND diff YEAR_ONE, id in INDICATORS}:
  TotalTERRITORIAL[m,sr,y,id] <= limit_territorial[m,sr,y,id];

var TotalTERRITORIAL_m_CCS_all{m in IAM, sr in SSP_RCP, y in YEARS};
subject to TERRITORIAL_m_CCS_all_cal{m in IAM, sr in SSP_RCP, y in YEARS_WND diff YEAR_ONE}:
  TotalTERRITORIAL_m_CCS_all[m,sr,y] = TotalTERRITORIAL[m,sr,y,'m_CCS_all'] + TotalCost[y]*1e-6;

subject to totalABROAD_limit {m in IAM, sr in SSP_RCP, y in YEARS_WND diff YEAR_ONE, id in INDICATORS}:
  TotalABROAD[m,sr,y,id] <= limit_abroad[m,sr,y,id];

var TotalABROAD_m_CCS_all{m in IAM, sr in SSP_RCP, y in YEARS};
subject to ABROAD_m_CCS_all_cal{m in IAM, sr in SSP_RCP, y in YEARS_WND diff YEAR_ONE}:
  TotalABROAD_m_CCS_all[m,sr,y] = TotalABROAD[m,sr,y,'m_CCS_all'] + TotalCost[y]*1e-6;

