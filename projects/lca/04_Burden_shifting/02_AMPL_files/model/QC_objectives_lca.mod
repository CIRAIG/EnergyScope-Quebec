
set INDICATORS;

set IAM;
set SSP_RCP;

param lcia_op {IAM,SSP_RCP,YEARS,INDICATORS,TECHNOLOGIES} default 0;
param lcia_constr {IAM,SSP_RCP,YEARS,INDICATORS,TECHNOLOGIES} default 0;
param lcia_decom {IAM,SSP_RCP,YEARS,INDICATORS,TECHNOLOGIES} default 0;
param lcia_res {IAM,SSP_RCP,YEARS,INDICATORS,RESOURCES} default 0;
param limit_lcia {IAM,SSP_RCP,YEARS,INDICATORS} default Infinity;
var LCIA_constr {IAM,SSP_RCP,YEARS,INDICATORS,TECHNOLOGIES};
var LCIA_decom {IAM,SSP_RCP,YEARS,INDICATORS,TECHNOLOGIES};
var LCIA_op {IAM,SSP_RCP,YEARS,INDICATORS,TECHNOLOGIES};
var LCIA_res {IAM,SSP_RCP,YEARS,INDICATORS,RESOURCES};
var TotalLCIA {IAM,SSP_RCP,YEARS,INDICATORS};

# Construction
subject to lcia_constr_calc {m in IAM, sr in SSP_RCP, y in YEARS_WND diff YEAR_ONE, id in INDICATORS, i in TECHNOLOGIES}:
  LCIA_constr[m,sr,y,id,i] = lcia_constr[m,sr,y,id,i] * F_Mult[y,i] / lifetime[y,i];

# Decommission
subject to lcia_decom_calc {m in IAM, sr in SSP_RCP, y in YEARS_WND diff YEAR_ONE, id in INDICATORS, i in TECHNOLOGIES}:
  LCIA_decom[m,sr,y,id,i] = lcia_decom[m,sr,y,id,i] * F_Mult[y,i] / lifetime[y,i];

# Operation
subject to lcia_op_calc {m in IAM, sr in SSP_RCP, y in YEARS_WND diff YEAR_ONE, id in INDICATORS, i in TECHNOLOGIES}:
  LCIA_op[m,sr,y,id,i] = lcia_op[m,sr,y,id,i] * sum {t in PERIODS} (t_op[t] * F_Mult_t[y,i,t]);

# Resources
subject to lcia_res_calc {m in IAM, sr in SSP_RCP, y in YEARS_WND diff YEAR_ONE, id in INDICATORS, r in RESOURCES}:
  LCIA_res[m,sr,y,id,r] = lcia_res[m,sr,y,id,r] * sum {t in PERIODS} (t_op[t] * F_Mult_t[y,r,t]);

subject to totalLCIA_calc_r {m in IAM, sr in SSP_RCP, y in YEARS_WND diff YEAR_ONE, id in INDICATORS}:
  TotalLCIA[m,sr,y,id] = sum {i in TECHNOLOGIES} (LCIA_constr[m,sr,y,id,i] + LCIA_decom[m,sr,y,id,i] + LCIA_op[m,sr,y,id,i]) + sum{r in RESOURCES} (LCIA_res[m,sr,y,id,r]);

subject to totalLCIA_limit {m in IAM, sr in SSP_RCP, y in YEARS_WND diff YEAR_ONE, id in INDICATORS}:
  TotalLCIA[m,sr,y,id] <= limit_lcia[m,sr,y,id];

var TotalLCIA_m_CCS_all{m in IAM, sr in SSP_RCP, y in YEARS};
subject to LCIA_m_CCS_all_cal{m in IAM, sr in SSP_RCP, y in YEARS_WND diff YEAR_ONE}:
  TotalLCIA_m_CCS_all[m,sr,y] = TotalLCIA[m,sr,y,'m_CCS_all'] + TotalCost[y]*1e-6;

var TotalLCIA_REQD{m in IAM, sr in SSP_RCP, y in YEARS};
subject to LCIA_REQD_cal{m in IAM, sr in SSP_RCP, y in YEARS_WND diff YEAR_ONE}:
  TotalLCIA_REQD[m,sr,y] = TotalLCIA[m,sr,y,'REQD'] + TotalCost[y]*1e-6;

var TotalLCIA_RHHD{m in IAM, sr in SSP_RCP, y in YEARS};
subject to LCIA_RHHD_cal{m in IAM, sr in SSP_RCP, y in YEARS_WND diff YEAR_ONE}:
  TotalLCIA_RHHD[m,sr,y] = TotalLCIA[m,sr,y,'RHHD'] + TotalCost[y]*1e-6;