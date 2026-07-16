
param direct_op {YEARS,INDICATORS,TECHNOLOGIES} default 0;
param limit_direct {YEARS,INDICATORS} default Infinity;
var DIRECT_op {YEARS,INDICATORS,TECHNOLOGIES};
var TotalDIRECT {YEARS,INDICATORS};

# Operation
subject to direct_op_calc {y in YEARS_WND diff YEAR_ONE, id in INDICATORS, i in TECHNOLOGIES}:
  DIRECT_op[y,id,i] = direct_op[y,id,i] * sum {t in PERIODS} (t_op[t] * F_Mult_t[y,i,t]);

subject to totalDIRECT_calc_r {y in YEARS_WND diff YEAR_ONE, id in INDICATORS}:
  TotalDIRECT[y,id] = sum {i in TECHNOLOGIES} DIRECT_op[y,id,i];

subject to totalDIRECT_limit {y in YEARS_WND diff YEAR_ONE, id in INDICATORS}:
  TotalDIRECT[y,id] <= limit_direct[y,id];

var TotalDIRECT_m_CCS_all{y in YEARS};
subject to DIRECT_m_CCS_all_cal{y in YEARS_WND diff YEAR_ONE}:
  TotalDIRECT_m_CCS_all[y] = TotalDIRECT[y,'m_CCS_all'] + TotalCost[y]*1e-6;

var TotalDIRECT_REQD{y in YEARS};
subject to DIRECT_REQD_cal{y in YEARS_WND diff YEAR_ONE}:
  TotalDIRECT_REQD[y] = TotalDIRECT[y,'REQD'] + TotalCost[y]*1e-6;

var TotalDIRECT_RHHD{y in YEARS};
subject to DIRECT_RHHD_cal{y in YEARS_WND diff YEAR_ONE}:
  TotalDIRECT_RHHD[y] = TotalDIRECT[y,'RHHD'] + TotalCost[y]*1e-6;