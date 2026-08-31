
param direct_op {YEARS,INDICATORS,TECHNOLOGIES} default 0;
param limit_direct_year {YEARS,INDICATORS} default Infinity;
param limit_direct {INDICATORS} default Infinity;
var DIRECT_op {PHASE,INDICATORS,TECHNOLOGIES};
var PhaseDIRECT {PHASE,INDICATORS};
var TotalDIRECT {INDICATORS};

# Operation
subject to direct_op_calc {p in PHASE_WND union PHASE_UP_TO, y_start in PHASE_START[p], y_stop in PHASE_STOP[p], id in INDICATORS, i in TECHNOLOGIES}:
  DIRECT_op[p,id,i] =
    (direct_op[y_start,id,i] * sum {t in PERIODS} (t_op[t] * F_Mult_t[y_start,i,t])
    + direct_op[y_stop,id,i] * sum {t in PERIODS} (t_op[t] * F_Mult_t[y_stop,i,t])) / 2
    * t_phase;

subject to phaseDIRECT_calc_r {p in PHASE_WND union PHASE_UP_TO, id in INDICATORS}:
  PhaseDIRECT[p,id] = sum {i in TECHNOLOGIES} DIRECT_op[p,id,i];

subject to totalDIRECT_calc_r {id in INDICATORS}:
  TotalDIRECT[id] = sum {p in PHASE_WND union PHASE_UP_TO} PhaseDIRECT[p,id];

subject to phaseDIRECT_limit {p in PHASE_WND union PHASE_UP_TO, id in INDICATORS, y_start in PHASE_START[p], y_stop in PHASE_STOP[p]}:
  PhaseDIRECT[p,id] <= t_phase * (limit_direct_year[y_start,id] + limit_direct_year[y_stop,id]) / 2;

subject to totalDIRECT_limit {id in INDICATORS}:
  TotalDIRECT[id] <= limit_direct[id];

var TotalDIRECT_REQD;
subject to DIRECT_REQD_cal:
  TotalDIRECT_REQD = TotalDIRECT['REQD'] + TotalTransitionCost*1e-6;

var TotalDIRECT_RHHD;
subject to DIRECT_RHHD_cal:
  TotalDIRECT_RHHD = TotalDIRECT['RHHD'] + TotalTransitionCost*1e-6;

