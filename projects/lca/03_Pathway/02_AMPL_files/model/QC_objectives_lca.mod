
set INDICATORS;

param lcia_op {YEARS,INDICATORS,TECHNOLOGIES} default 0;
param lcia_constr {YEARS,INDICATORS,TECHNOLOGIES} default 0;
param lcia_decom {YEARS,INDICATORS,TECHNOLOGIES} default 0;
param lcia_res {YEARS,INDICATORS,RESOURCES} default 0;
param limit_lcia_year {YEARS,INDICATORS} default Infinity;
param limit_lcia {INDICATORS} default Infinity;
var LCIA_constr {PHASE,INDICATORS,TECHNOLOGIES};
var LCIA_decom {PHASE,INDICATORS,TECHNOLOGIES};
var LCIA_op {PHASE,INDICATORS,TECHNOLOGIES};
var LCIA_res {PHASE,INDICATORS,RESOURCES};
var PhaseLCIA {PHASE,INDICATORS};
var TotalLCIA {INDICATORS};

# Construction
subject to lcia_constr_calc {p in PHASE_WND union PHASE_UP_TO, id in INDICATORS, i in TECHNOLOGIES}:
  LCIA_constr[p,id,i] =
    sum {p_inst in PHASE_WND union PHASE_UP_TO,
      ys_inst in PHASE_START[p_inst],
      ye_inst in PHASE_STOP[p_inst]:
      years_active[i,p_inst,p] > 0}
      (lcia_constr[ys_inst,id,i] + lcia_constr[ye_inst,id,i]) / 2
      * F_new[p_inst,i] * years_active[i, p_inst, p] / ((lifetime[ys_inst,i] + lifetime[ye_inst,i]) / 2);

# Decommission
subject to lcia_decom_calc {p in PHASE_WND union PHASE_UP_TO, id in INDICATORS, i in TECHNOLOGIES}:
  LCIA_decom[p,id,i] =
    sum {p_inst in PHASE_WND union PHASE_UP_TO,
      ys_inst in PHASE_START[p_inst],
      ye_inst in PHASE_STOP[p_inst]:
      years_active[i,p_inst,p] > 0}
      (lcia_decom[ys_inst,id,i] + lcia_decom[ye_inst,id,i]) / 2
      * F_new[p_inst,i] * years_active[i, p_inst, p] / ((lifetime[ys_inst,i] + lifetime[ye_inst,i]) / 2);

# Operation
subject to lcia_op_calc {p in PHASE_WND union PHASE_UP_TO, y_start in PHASE_START[p], y_stop in PHASE_STOP[p], id in INDICATORS, i in TECHNOLOGIES}:
  LCIA_op[p,id,i] =
    (lcia_op[y_start,id,i] * sum {t in PERIODS} (t_op[t] * F_Mult_t[y_start,i,t])
    + lcia_op[y_stop,id,i] * sum {t in PERIODS} (t_op[t] * F_Mult_t[y_stop,i,t])) / 2
    * t_phase;

# Resources
subject to lcia_res_calc {p in PHASE_WND union PHASE_UP_TO, y_start in PHASE_START[p], y_stop in PHASE_STOP[p], id in INDICATORS, r in RESOURCES}:
  LCIA_res[p,id,r] =
    (lcia_res[y_start,id,r] * sum {t in PERIODS} (t_op[t] * F_Mult_t[y_start,r,t])
    + lcia_res[y_stop,id,r] * sum {t in PERIODS} (t_op[t] * F_Mult_t[y_stop,r,t])) / 2
    * t_phase;

subject to phaseLCIA_calc_r {p in PHASE_WND union PHASE_UP_TO, id in INDICATORS}:
  PhaseLCIA[p,id] = sum {i in TECHNOLOGIES} (LCIA_constr[p,id,i] + LCIA_decom[p,id,i]
+ LCIA_op[p,id,i]) + sum{r in RESOURCES} (LCIA_res[p,id,r]);

subject to totalLCIA_calc_r {id in INDICATORS}:
  TotalLCIA[id] = sum {p in PHASE_WND union PHASE_UP_TO} PhaseLCIA[p,id];

subject to phaseLCIA_limit {p in PHASE_WND union PHASE_UP_TO, id in INDICATORS, y_start in PHASE_START[p], y_stop in PHASE_STOP[p]}:
  PhaseLCIA[p,id] <= t_phase * (limit_lcia_year[y_start,id] + limit_lcia_year[y_stop,id]) / 2;

subject to totalLCIA_limit {id in INDICATORS}:
  TotalLCIA[id] <= limit_lcia[id];

var TotalLCIA_REQD;
subject to LCIA_REQD_cal:
  TotalLCIA_REQD = TotalLCIA['REQD'] + TotalTransitionCost*1e-6;

var TotalLCIA_RHHD;
subject to LCIA_RHHD_cal:
  TotalLCIA_RHHD = TotalLCIA['RHHD'] + TotalTransitionCost*1e-6;

