#subject to ni_ng_import {y in {"YEAR_2045","YEAR_2050"}, res in {"NG_EHP","GASOLINE","DIESEL","LFO","JETFUEL"}}:
#    Res[y,"NG_EHP"] = 0;
#let max_co2_budget := 335225;
/*
subject to limit_emissions:
    sum{t in PERIODS} GWP['YEAR_2050','CO2_A',t] = 0;

# ── Limit GROSS emissions to prevent "emit-and-capture" strategies ────────────
# Without these constraints the model satisfies net-zero by emitting large gross
# CO₂ and compensating with CARBON_CAPTURE / DAC.
# Reference (current unconstrained solution):
#   2020: gross CO2_A = 23 475 kt/y,  gross CO2_E = 57 752 kt/y
#   2050: gross CO2_A = 47 928 kt/y,  gross CO2_E = 39 269 kt/y  (net = 0 each)
#
# f_max_gross_co2a[y] — total CO2_A produced BEFORE CARBON_CAPTURE [kt CO2/y]
#   Limits how much point-source CO2 the system can generate regardless of capture.
#   Example: 20000 in 2050 forces real phase-out, not just massive CCS deployment.
#
# f_max_gross_co2e[y] — sum of positive CO2_E contributions BEFORE DAC [kt CO2/y]
#   Limits diffuse combustion/transport emissions before DAC compensation.
#   Example: 15000 in 2050 forces electrification/modal-shift, not DAC reliance.

param f_max_gross_co2a {YEARS} default Infinity;
param f_max_gross_co2e {YEARS} default Infinity;

# Uncomment and set values to activate:
let f_max_gross_co2a['YEAR_2050'] := 2000;
let f_max_gross_co2e['YEAR_2050'] := 30000;
# Or ramp linearly across all years, e.g.:
# let {y in YEARS} f_max_gross_co2a[y] := ...;

subject to limit_gross_co2a {y in YEARS_WND diff YEAR_ONE}:
    sum{t in PERIODS, i in RESOURCES union TECHNOLOGIES diff STORAGE_TECH:
        layers_in_out[y,i,"CO2_A"] > 0}
        (layers_in_out[y,i,"CO2_A"] * F_Mult_t[y,i,t] * t_op[t])
    <= f_max_gross_co2a[y];

subject to limit_gross_co2e {y in YEARS_WND diff YEAR_ONE}:
    sum{t in PERIODS, i in RESOURCES union TECHNOLOGIES diff STORAGE_TECH:
        layers_in_out[y,i,"CO2_E"] > 0}
        (layers_in_out[y,i,"CO2_E"] * F_Mult_t[y,i,t] * t_op[t])
    <= f_max_gross_co2e[y];

subject to fixed_schoolbus {y in YEARS_WND diff YEAR_ONE diff {"YEAR_2025"} diff {"YEAR_2020"},t in {"SCHOOLBUS_CNG_SD","SCHOOLBUS_DIESEL_SD","SCHOOLBUS_GASOLINE_SD","SCHOOLBUS_BIOETOH_E10_SD","SCHOOLBUS_ETOH_E10_SD","SCHOOLBUS_PROPANE_SD","SCHOOLBUS_CSNG_SD","SCHOOLBUS_EV_SD"}}:
    F_Mult[y,t] = F_Mult["YEAR_2025",t];
*/

var Number_Of_Units {YEARS,TECHNOLOGIES diff INFRASTRUCTURE} >= 0;
# [Eq. 1.7] Number of purchased technologies. Integer variable (so that we have only integer multiples of the reference size)
subject to number_of_units {y in YEARS_WND diff YEAR_ONE, i in TECHNOLOGIES diff INFRASTRUCTURE}:
	Number_Of_Units [y,i] = F_Mult [y,i] / ref_size [y,i];

/*
subject to wind_min :
    F_Mult["YEAR_2050","WIND_ONSHORE"] >= 10;

subject to PV_min :
    F_Mult["YEAR_2050","PV_ROOF"] >= 0.36;

subject to hydro_min :
    F_Mult["YEAR_2050","HYDRO_DAM"]+F_Mult["YEAR_2050","HYDRO_RIVER"] >= F_Mult["YEAR_2020","HYDRO_DAM"]+F_Mult["YEAR_2020","HYDRO_RIVER"] + 4;
    */

## Investment rate
for{y in YEARS} {
    let i_rate[y] := 0.04; # Global interest rate for discounting (social discount rate)
}
/*
let i_rate['YEAR_2015'] := 0.08;
let i_rate['YEAR_2020'] := 0.08;
let i_rate['YEAR_2025'] := 0.08;
let i_rate['YEAR_2030'] := 0.08;   
let i_rate['YEAR_2035'] := 0.02;
let i_rate['YEAR_2040'] := 0.02;
let i_rate['YEAR_2045'] := 0.02;
let i_rate['YEAR_2050'] := 0.02;
*/
##Co2 budget 
let max_co2_budget  := 883428; #in kton Co2quivalent, for 2020-2050 cumulative emissions.