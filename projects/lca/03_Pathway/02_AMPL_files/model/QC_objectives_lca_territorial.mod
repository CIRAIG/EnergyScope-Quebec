
param territorial_op {YEARS,INDICATORS,TECHNOLOGIES} default 0;
param territorial_constr {YEARS,INDICATORS,TECHNOLOGIES} default 0;
param territorial_decom {YEARS,INDICATORS,TECHNOLOGIES} default 0;
param territorial_res {YEARS,INDICATORS,RESOURCES} default 0;
param limit_territorial_year {YEARS,INDICATORS} default Infinity;
param limit_territorial {INDICATORS} default Infinity;
var TERRITORIAL_constr {PHASE,INDICATORS,TECHNOLOGIES};
var TERRITORIAL_decom {PHASE,INDICATORS,TECHNOLOGIES};
var TERRITORIAL_op {PHASE,INDICATORS,TECHNOLOGIES};
var TERRITORIAL_res {PHASE,INDICATORS,RESOURCES};
var PhaseTERRITORIAL {PHASE,INDICATORS};
var TotalTERRITORIAL {INDICATORS};

param limit_abroad_year {YEARS,INDICATORS} default Infinity;
param limit_abroad {INDICATORS} default Infinity;
var ABROAD_constr {PHASE,INDICATORS,TECHNOLOGIES};
var ABROAD_decom {PHASE,INDICATORS,TECHNOLOGIES};
var ABROAD_op {PHASE,INDICATORS,TECHNOLOGIES};
var ABROAD_res {PHASE,INDICATORS,RESOURCES};
var PhaseABROAD {PHASE,INDICATORS};
var TotalABROAD {INDICATORS};

# Construction
subject to territorial_constr_calc {p in PHASE_WND union PHASE_UP_TO, id in INDICATORS, i in TECHNOLOGIES}:
  TERRITORIAL_constr[p,id,i] =
    sum {p_inst in PHASE_WND union PHASE_UP_TO,
      ys_inst in PHASE_START[p_inst],
      ye_inst in PHASE_STOP[p_inst]:
      years_active[i,p_inst,p] > 0}
      (territorial_constr[ys_inst,id,i] + territorial_constr[ye_inst,id,i]) / 2
      * F_new[p_inst,i] * years_active[i, p_inst, p] / ((lifetime[ys_inst,i] + lifetime[ye_inst,i]) / 2);

# Decommission
subject to territorial_decom_calc {p in PHASE_WND union PHASE_UP_TO, id in INDICATORS, i in TECHNOLOGIES}:
  TERRITORIAL_decom[p,id,i] =
    sum {p_inst in PHASE_WND union PHASE_UP_TO,
      ys_inst in PHASE_START[p_inst],
      ye_inst in PHASE_STOP[p_inst]:
      years_active[i,p_inst,p] > 0}
      (territorial_decom[ys_inst,id,i] + territorial_decom[ye_inst,id,i]) / 2
      * F_new[p_inst,i] * years_active[i, p_inst, p] / ((lifetime[ys_inst,i] + lifetime[ye_inst,i]) / 2);

# Operation
subject to territorial_op_calc {p in PHASE_WND union PHASE_UP_TO, y_start in PHASE_START[p], y_stop in PHASE_STOP[p], id in INDICATORS, i in TECHNOLOGIES}:
  TERRITORIAL_op[p,id,i] =
    (territorial_op[y_start,id,i] * sum {t in PERIODS} (t_op[t] * F_Mult_t[y_start,i,t])
    + territorial_op[y_stop,id,i] * sum {t in PERIODS} (t_op[t] * F_Mult_t[y_stop,i,t])) / 2
    * t_phase;

# Resources
subject to territorial_res_calc {p in PHASE_WND union PHASE_UP_TO, y_start in PHASE_START[p], y_stop in PHASE_STOP[p], id in INDICATORS, r in RESOURCES}:
  TERRITORIAL_res[p,id,r] =
    (territorial_res[y_start,id,r] * sum {t in PERIODS} (t_op[t] * F_Mult_t[y_start,r,t])
    + territorial_res[y_stop,id,r] * sum {t in PERIODS} (t_op[t] * F_Mult_t[y_stop,r,t])) / 2
    * t_phase;

# Abroad impacts
subject to abroad_constr_calc {p in PHASE_WND union PHASE_UP_TO, id in INDICATORS, i in TECHNOLOGIES}:
  ABROAD_constr[p,id,i] = LCIA_constr[p,id,i] - TERRITORIAL_constr[p,id,i];

subject to abroad_decom_calc {p in PHASE_WND union PHASE_UP_TO, id in INDICATORS, i in TECHNOLOGIES}:
  ABROAD_decom[p,id,i] = LCIA_decom[p,id,i] - TERRITORIAL_decom[p,id,i];

subject to abroad_op_calc {p in PHASE_WND union PHASE_UP_TO, id in INDICATORS, i in TECHNOLOGIES}:
  ABROAD_op[p,id,i] = LCIA_op[p,id,i] - TERRITORIAL_op[p,id,i];

subject to abroad_res_calc {p in PHASE_WND union PHASE_UP_TO, id in INDICATORS, r in RESOURCES}:
  ABROAD_res[p,id,r] = LCIA_res[p,id,r] - TERRITORIAL_res[p,id,r];

subject to phaseTERRITORIAL_calc_r {p in PHASE_WND union PHASE_UP_TO, id in INDICATORS}:
  PhaseTERRITORIAL[p,id] = sum {i in TECHNOLOGIES} (TERRITORIAL_constr[p,id,i] + TERRITORIAL_decom[p,id,i]
+ TERRITORIAL_op[p,id,i]) + sum{r in RESOURCES} (TERRITORIAL_res[p,id,r]);

subject to totalTERRITORIAL_calc_r {id in INDICATORS}:
  TotalTERRITORIAL[id] = sum {p in PHASE_WND union PHASE_UP_TO} PhaseTERRITORIAL[p,id];

subject to phaseABROAD_calc_r {p in PHASE_WND union PHASE_UP_TO, id in INDICATORS}:
  PhaseABROAD[p,id] = sum {i in TECHNOLOGIES} (ABROAD_constr[p,id,i] + ABROAD_decom[p,id,i]
+ ABROAD_op[p,id,i]) + sum{r in RESOURCES} (ABROAD_res[p,id,r]);

subject to totalABROAD_calc_r {id in INDICATORS}:
  TotalABROAD[id] = sum {p in PHASE_WND union PHASE_UP_TO} PhaseABROAD[p,id];

subject to phaseTERRITORIAL_limit {p in PHASE_WND union PHASE_UP_TO, id in INDICATORS, y_start in PHASE_START[p], y_stop in PHASE_STOP[p]}:
  PhaseTERRITORIAL[p,id] <= t_phase * (limit_territorial_year[y_start,id] + limit_territorial_year[y_stop,id]) / 2;

subject to totalTERRITORIAL_limit {id in INDICATORS}:
  TotalTERRITORIAL[id] <= limit_territorial[id];

var TotalTERRITORIAL_REQD;
subject to TERRITORIAL_REQD_cal:
  TotalTERRITORIAL_REQD = TotalTERRITORIAL['REQD'] + TotalTransitionCost*1e-6;

var TotalTERRITORIAL_RHHD;
subject to TERRITORIAL_RHHD_cal:
  TotalTERRITORIAL_RHHD = TotalTERRITORIAL['RHHD'] + TotalTransitionCost*1e-6;

subject to phaseABROAD_limit {p in PHASE_WND union PHASE_UP_TO, id in INDICATORS, y_start in PHASE_START[p], y_stop in PHASE_STOP[p]}:
  PhaseABROAD[p,id] <= t_phase * (limit_abroad_year[y_start,id] + limit_abroad_year[y_stop,id]) / 2;

subject to totalABROAD_limit {id in INDICATORS}:
  TotalABROAD[id] <= limit_abroad[id];

var TotalABROAD_REQD;
subject to ABROAD_REQD_cal:
  TotalABROAD_REQD = TotalABROAD['REQD'] + TotalTransitionCost*1e-6;

var TotalABROAD_RHHD;
subject to ABROAD_RHHD_cal:
  TotalABROAD_RHHD = TotalABROAD['RHHD'] + TotalTransitionCost*1e-6;

