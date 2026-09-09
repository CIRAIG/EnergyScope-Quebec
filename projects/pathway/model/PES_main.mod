######################################################												
# 	Swiss-EnergyScope (SES) MILP modeling framework
#   Model file for pathway
#   Author: Mattia Zimmermann
#   Date: 27.04.2026
#   Model documentation: Limpens, G., Rixhon, X., Contino, F., & Jeanmart, H. (2024). EnergyScope Pathway: An open-source model to optimise the energy transition pathways of a regional whole-energy system. Applied Energy, 358, 122501. https://doi.org/10.1016/j.apenergy.2023.122501
#   For terms of use and how to cite this work please check the ReadMe file. 
#   Reference for code : G. Limpens (2021). Optimisation of energy transition pathways - application to the case of Belgium. PhD thesis 	
######################################################	


## Complementary sets for Pathway model :
set PHASE ordered;
set PHASE_START {PHASE} within YEARS;
set PHASE_STOP  {PHASE} within YEARS;
set PHASE_WND within PHASE;
set PHASE_UP_TO within PHASE;
set YEAR_ONE_NEXT within YEARS;


# AGE is calculated a priori. It defines when a technology should have been built given the phase. 
set AGE {TECHNOLOGIES,PHASE} within PHASE union {"2015_2020"} union {"STILL_IN_USE"};

## Compl. parameters for pathway model :

param max_inv_phase {PHASE} default Infinity; # Unlimited
param max_share_cost_phase >= 0, <= 1, default 1; # Max share of the total (non-actualised) transition cost, excluding the 2015_2020 initialisation, that a single phase can represent
param t_phase ;
param diff_2015_phase {PHASE};
param gwp_limit_transition >=0 default Infinity; # To limit CO2 emissions over the transition
param decom_allowed {PHASE,PHASE union {"2015_2020"},TECHNOLOGIES} default 0;
param remaining_years {TECHNOLOGIES,PHASE} >=0;
param ccs_limit {YEARS} >=0 default Infinity; # To limit CO2 sequestration over the transition [kt CO2-eq./year]
param limit_LT_renovation >= 0;
param limit_HT_renovation >= 0;
param limit_elec_renovation >= 0;
param limit_pass_mob_changes >= 0;
param limit_freight_changes >= 0;
param efficiency {YEARS} >=0 default 1;
param gwp_limit {YEARS} default 0;#>= 0 default 0;    # [ktCO2-eq./year] maximum gwp emissions allowed.

param actualisation_factor {p in PHASE, y in YEARS} := 1 / ((1 + SDR[y])^diff_2015_phase[p] ); # Actualisation factor

param years_active {TECHNOLOGIES,PHASE,PHASE} default 0; # Number of years a technology is active in a phase, used for CRF calculation of investment costs. Calculated a priori based on AGE and PHASE_START/STOP.
#param years_active {TECHNOLOGIES, PHASE union {"2015_2020"}, PHASE union {"2015_2020"}} >= 0; # Number of years a technology is active in a phase, used for CRF calculation of investment costs. Calculated a priori based on AGE and PHASE_START/STOP.

## Compl. variables for pathway model :

var F_new {PHASE union {"2015_2020"}, TECHNOLOGIES} >= 0; #[GW/GWh] Accounts for the additional new capacity installed in a new phase
var F_decom {PHASE,PHASE union {"2015_2020"}, TECHNOLOGIES} >= 0; #[GW] Accounts for the decommissioned capacity in a new phase
var F_old {PHASE,TECHNOLOGIES} >=0, default 0; #[GW] Retired capacity during a phase with respect to the main output
var C_inv_phase {PHASE} >=0; #[M$CAD/GW] Phase total annualised investment cost
var C_inv_phase_no_actu {PHASE} >=0; #[M$CAD/GW] Phase total investment cost, without actualisation factor
var C_inv_phase_tech {PHASE,TECHNOLOGIES} >=0; #[M$CAD/GW] Phase total annualised investment cost, per technology
var C_inv_phase_tech_no_actu {PHASE,TECHNOLOGIES} >=0; #[M$CAD/GW] Phase total investment cost per technology, without actualisation factor
var C_op_phase_tech {PHASE,TECHNOLOGIES} >= 0;
var C_op_phase_tech_no_actu {PHASE,TECHNOLOGIES} >= 0;
var C_op_phase_res {PHASE,RESOURCES} >= 0;
var C_op_phase_res_no_actu {PHASE,RESOURCES} >= 0;
var C_inv_return {TECHNOLOGIES} >=0; #[M$CAD] Money given back for existing technologies after 2050 to compute the objective function
var C_inv_return_phase {PHASE union {"2015_2020"}, TECHNOLOGIES} >=0; #[M$CAD] Return investment per installation phase and technology
#var Fixed_phase_investment;
var C_opex {YEARS} >=0;
var C_tot_opex >=0;
var C_tot_capex >=0;
var TotalGWPTransition >=0;
var Delta_change {PHASE,TECHNOLOGIES} >=0;
var Gwp_tot_cost >=0;


### Definition of Model constraints 


## Resources used
var Res {YEARS diff {'YEAR_2015'}, RESOURCES} >= 0, default 0; #[GWh] Annual resource use (for reporting)
subject to store_res {y in YEARS_WND diff YEAR_ONE, j in RESOURCES}:
	Res [y, j] = sum {t in PERIODS} (F_Mult_t [y,j,t] * t_op [t]);

## Per-period resource use for cost computation (supports period-dependent c_op)
var Res_t {YEARS diff {'YEAR_2015'}, RESOURCES, PERIODS} >= 0, default 0; #[GWh] Resource use per period
subject to store_res_t {y in YEARS_WND diff YEAR_ONE, j in RESOURCES, t in PERIODS}:
	Res_t [y, j, t] = F_Mult_t [y,j,t] * t_op [t];


# Total cost of each resource / Res_t is fixed for past years (unlike F_Mult_t which is free) — supports period-dependent c_op
subject to op_cost_calc2 {y in YEARS_UP_TO union YEARS_WND, i in RESOURCES}:
    C_op [y,i] = sum {t in PERIODS} c_op [y,i,t] * Res_t [y, i, t] ;

# [Eq. 34]  constraint to reduce the GWP subject to gwp_limit :
subject to minimum_GWP_reduction  {y in YEARS_WND diff YEAR_ONE} :
	TotalGWP [y] <= gwp_limit [y];

# [Eq. 23] total transition gwp calculation
subject to totalGWPTransition_calculation : # category: GWP_calc
	TotalGWPTransition =
		sum {p in PHASE_UP_TO union PHASE_WND, y_start in PHASE_START [p], y_stop in PHASE_STOP [p]} (
			t_phase / 2 * (
				  TotalGWP [y_start]
				+ TotalGWP [y_stop]
			)
		);
	

## Define technologies change during phases:
#-------------------------------------------


# [Eq. 08] Relate the installed capacity between years
subject to phase_new_build {p in PHASE_WND, y_start in PHASE_START[p], y_stop in PHASE_STOP[p], i in TECHNOLOGIES}:
	F_Mult[y_stop,i] = F_Mult[y_start,i] + F_new[p,i] - F_old [p,i] 
  											     - sum {p2 in {PHASE_WND union PHASE_UP_TO union {"2015_2020"}}} F_decom[p,p2,i];

# [Eq. 09] Impose decom_allowed to 0 when not physical
subject to define_f_decom_properly {p_decom in PHASE, p_built in PHASE union {"2015_2020"}, i in TECHNOLOGIES}:
	if decom_allowed[p_decom,p_built,i] == 0 then F_decom [p_decom,p_built,i] = 0;

# [Eq. 11] Intialise the first phase based on YEAR_2015 results
subject to F_new_initialisation {tech in TECHNOLOGIES}:
	F_new ["2015_2020",tech] = F_Mult["YEAR_2020",tech]; # Generate F_new2015_2020

# [Eq. 10] Impose the exact capacity that reaches its lifetime
subject to phase_out_assignement {i in TECHNOLOGIES, p in PHASE_WND, age in AGE [i,p]}:
	F_old [p,i] = if (age == "STILL_IN_USE") then  0 
					else F_new [age,i]    - sum {p2 in PHASE_WND union PHASE_UP_TO} F_decom [p2,age,i];

# Ensures that a Technology is not decomissioned if not built 
subject to no_decom_if_no_built {i in TECHNOLOGIES, p in PHASE_WND union PHASE_UP_TO union {"2015_2020"}}:
	F_new [p, i] -  sum {p2 in PHASE_WND union PHASE_UP_TO} F_decom [p2,p,i] >= 0;

# Limit renovation rate:
# [Eq. 12] Define the amount of change between years
var F_used_year_start{YEARS_WND, TECHNOLOGIES} >= 0;
subject to compute_F_used_year_start{p in PHASE_WND, y_start in PHASE_START[p] diff YEAR_ONE, j in TECHNOLOGIES} :
	F_used_year_start[y_start,j] = (sum {t in PERIODS} F_Mult_t [y_start,j, t] * t_op[t]);

subject to delta_change_definition {p in PHASE_WND, y_start in PHASE_START[p], y_stop in PHASE_STOP[p], j in TECHNOLOGIES} :
	Delta_change [p,j] >= F_used_year_start[y_start,j] - (sum {t in PERIODS} F_Mult_t [y_stop,j, t] * t_op[t]) ;

# Symetric constaints to take into account increase of technologies in the renovation limit
subject to delta_change_definition_sym {p in PHASE_WND, y_start in PHASE_START[p], y_stop in PHASE_STOP[p], j in TECHNOLOGIES} :
      Delta_change [p,j] >= (sum {t in PERIODS} F_Mult_t [y_stop,j, t] * t_op[t]) - F_used_year_start[y_start,j] ;

# [Eq. 13] Limit the amount of change for low temperature heating
subject to limit_changes_heat {p in PHASE_WND union PHASE_UP_TO, y_start in PHASE_START[p], y_stop in PHASE_STOP[p]} :
	sum {euc in END_USES_TYPES_OF_CATEGORY["HEAT_LOW_T"], j in TECHNOLOGIES_OF_END_USES_TYPE[euc]} Delta_change[p,j] 
		<= limit_LT_renovation * (end_uses_input[y_start,"HEAT_LOW_T_HW"] + end_uses_input[y_start,"HEAT_LOW_T_SH"]) ;

# New equation : similar to Eq. 13 but for high temperature heating
subject to limit_changes_heat_high {p in PHASE_WND union PHASE_UP_TO, y_start in PHASE_START[p], y_stop in PHASE_STOP[p]} :
	sum {euc in END_USES_TYPES_OF_CATEGORY["HEAT_HIGH_T"], j in TECHNOLOGIES_OF_END_USES_TYPE[euc]} Delta_change[p,j] 
		<= limit_HT_renovation * end_uses_input[y_start,"HEAT_HIGH_T"] ;

# New equation : similar to Eq. 13 but for electicity production
subject to limit_changes_elec {p in PHASE_WND union PHASE_UP_TO, y_start in PHASE_START[p], y_stop in PHASE_STOP[p]} :
	sum {euc in END_USES_TYPES_OF_CATEGORY["ELECTRICITY_LV"] union END_USES_TYPES_OF_CATEGORY["ELECTRICITY_MV"] union END_USES_TYPES_OF_CATEGORY["ELECTRICITY_HV"] union END_USES_TYPES_OF_CATEGORY["ELECTRICITY_EHV"], j in TECHNOLOGIES_OF_END_USES_TYPE[euc]} Delta_change[p,j] 
		<= limit_elec_renovation * (sum{elec in {"ELECTRICITY_LV", "ELECTRICITY_MV", "ELECTRICITY_HV", "ELECTRICITY_EHV"}} end_uses_input[y_start,elec]);

# [Eq. 14] Limit the amount of change for passenger mobility
subject to limit_changes_mob {p in PHASE_WND union PHASE_UP_TO, y_start in PHASE_START[p], y_stop in PHASE_STOP[p]} :
	sum {euc in END_USES_TYPES_OF_CATEGORY["MOBILITY_PASSENGER_SD"] union END_USES_TYPES_OF_CATEGORY["MOBILITY_PASSENGER_MD"] union END_USES_TYPES_OF_CATEGORY["MOBILITY_PASSENGER_LD"] union END_USES_TYPES_OF_CATEGORY["MOBILITY_PASSENGER_ELD"], j in TECHNOLOGIES_OF_END_USES_TYPE[euc]} Delta_change[p,j] 
		<= limit_pass_mob_changes * (sum{mob_pass in {"MOBILITY_PASSENGER_SD", "MOBILITY_PASSENGER_MD", "MOBILITY_PASSENGER_LD", "MOBILITY_PASSENGER_ELD"}} end_uses_input[y_start,mob_pass]);

# [Eq. 15] Limit the amount of change for freight mobility
subject to limit_changes_freight {p in PHASE_WND union PHASE_UP_TO, y_start in PHASE_START[p], y_stop in PHASE_STOP[p]} :
	sum {euc in END_USES_TYPES_OF_CATEGORY["MOBILITY_FREIGHT_SD"] union END_USES_TYPES_OF_CATEGORY["MOBILITY_FREIGHT_MD"] union END_USES_TYPES_OF_CATEGORY["MOBILITY_FREIGHT_LD"] union END_USES_TYPES_OF_CATEGORY["MOBILITY_FREIGHT_ELD"], j in TECHNOLOGIES_OF_END_USES_TYPE[euc]} Delta_change[p,j] 
		<= limit_freight_changes * (sum{mob_f in {"MOBILITY_FREIGHT_SD","MOBILITY_FREIGHT_MD","MOBILITY_FREIGHT_LD","MOBILITY_FREIGHT_ELD"} }end_uses_input[y_start,mob_f]);



## Compute cost during phase:
#----------------------------
var C_inv_phase_CRF {PHASE} >= 0;#[M$CAD/GW] Phase total annualised investment cost, calculated with CRF to be used in the objective function
# [Eq. 17] Compute capital expenditure for transition
subject to total_capex: # category: COST_calc
	C_tot_capex = sum{p in PHASE_WND union PHASE_UP_TO union {"2015_2020"}} C_inv_phase_CRF[p];
#	Replace "C_inv_phase_CRF[p]""  by this variable to switch back to the single rate investment cost calculation  :  C_inv_phase[p] - sum {i in TECHNOLOGIES} C_inv_return [i];
					  

# [Eq. 21] Compute the total investment cost per phase
# Note: GRIDS use a special cost formula (c_inv is in M$CAD/GW/km), so they are handled separately (ref : Schnidrig, J., Cherkaoui, R., Calisesi, Y., Margni, M., & Maréchal, F. (2023). On the role of energy infrastructure in the energy transition. Case study of an energy independent and CO2 neutral energy system for Switzerland. Frontiers in Energy Research, 11. https://doi.org/10.3389/fenrg.2023.1164813)
subject to investment_computation {p in PHASE_WND union PHASE_UP_TO union {"2015_2020"}, y_start in PHASE_START[p], y_stop in PHASE_STOP[p]}:
	 C_inv_phase [p] = sum {i in TECHNOLOGIES diff GRIDS} F_new [p,i] * (actualisation_factor [p,y_start]+actualisation_factor [p,y_stop]) * ( c_inv [y_start,i] + c_inv [y_stop,i] ) / 4
	                 + sum {i in GRIDS} F_new [p,i] * (actualisation_factor [p,y_start]+actualisation_factor [p,y_stop]) * ( c_inv [y_start,i] + c_inv [y_stop,i] ) * l_grid_ext[i] * k_security[i] / n_stations[i] / 4; #In b$CAD


subject to investment_computation_no_actu {p in PHASE_WND union PHASE_UP_TO union {"2015_2020"}, y_start in PHASE_START[p], y_stop in PHASE_STOP[p]}:
	 C_inv_phase_no_actu [p] = sum {i in TECHNOLOGIES diff GRIDS} F_new [p,i] *  ( c_inv [y_start,i] + c_inv [y_stop,i] ) / 2
	                 + sum {i in GRIDS} F_new [p,i] * ( c_inv [y_start,i] + c_inv [y_stop,i] ) * l_grid_ext[i] * k_security[i] / n_stations[i] / 2; #In b$CAD



subject to investment_computation_CRF {p in PHASE_WND union PHASE_UP_TO union {"2015_2020"}, y_start in PHASE_START[p], y_stop in PHASE_STOP[p]}:
    C_inv_phase_CRF [p] =
		sum {i in TECHNOLOGIES diff GRIDS,
			p_inst in PHASE_WND union PHASE_UP_TO union {"2015_2020"},
			ys_inst in PHASE_START[p_inst],
			ye_inst in PHASE_STOP[p_inst] :
			years_active[i, p_inst, p] > 0}
            F_new[p_inst, i] * tau[ys_inst, i]
			*(actualisation_factor [p,y_start]+actualisation_factor [p,y_stop])
            * (c_inv[ys_inst, i] + c_inv[ye_inst, i]) 
            * years_active[i, p_inst, p]/ 4
        +
		sum {i in GRIDS,
			p_inst in PHASE_WND union PHASE_UP_TO union {"2015_2020"},
			ys_inst in PHASE_START[p_inst],
			ye_inst in PHASE_STOP[p_inst] :
			years_active[i, p_inst, p] > 0}
            F_new[p_inst, i] * tau[ys_inst, i]
			*(actualisation_factor [p,y_start]+actualisation_factor [p,y_stop])
            * (c_inv[ys_inst, i] + c_inv[ye_inst, i]) 
            * years_active[i, p_inst, p]
            * l_grid_ext[i] * k_security[i] / (4*n_stations[i]);

# Compute the total investment cost per phase and per technologies 
subject to investment_computation_tech {p in PHASE_WND union PHASE_UP_TO union {"2015_2020"}, y_start in PHASE_START[p], y_stop in PHASE_STOP[p], i in TECHNOLOGIES}:
	 C_inv_phase_tech [p,i] = if i in GRIDS
	                          then F_new [p,i] * (actualisation_factor [p,y_start]+actualisation_factor [p,y_stop]) * ( c_inv [y_start,i] + c_inv [y_stop,i] ) / 4 * l_grid_ext[i] * k_security[i] / n_stations[i]
	                          else F_new [p,i] * (actualisation_factor [p,y_start]+actualisation_factor [p,y_stop]) * ( c_inv [y_start,i] + c_inv [y_stop,i] ) / 4;

# Compute the total investment cost per phase and per technologies, without actualisation factor
subject to investment_computation_tech_no_actu {p in PHASE_WND union PHASE_UP_TO union {"2015_2020"}, y_start in PHASE_START[p], y_stop in PHASE_STOP[p], i in TECHNOLOGIES}:
	 C_inv_phase_tech_no_actu [p,i] = if i in GRIDS
	                          then F_new [p,i] * ( c_inv [y_start,i] + c_inv [y_stop,i] ) / 2 * l_grid_ext[i] * k_security[i] / n_stations[i]
	                          else F_new [p,i] * ( c_inv [y_start,i] + c_inv [y_stop,i] ) / 2;

# [Eq. 22] Compute the return investment per phase and technology
subject to investment_return_phase_tech {p in PHASE_WND union PHASE_UP_TO union {"2015_2020"}, i in TECHNOLOGIES diff GRIDS, y_start in PHASE_START [p], y_stop in PHASE_STOP [p]}:
	C_inv_return_phase [p,i] =
	( remaining_years [i,p] / lifetime [y_start,i] * (F_new [p,i] - sum {p2 in PHASE_WND union PHASE_UP_TO} (F_decom [p2,p,i]) )  * (1/((1+SDR[y_start])^35)) * ( c_inv [y_start,i] + c_inv [y_stop,i] ) / 2 ) ;
subject to investment_return_phase_tech_grid {p in PHASE_WND union PHASE_UP_TO union {"2015_2020"}, i in GRIDS, y_start in PHASE_START [p], y_stop in PHASE_STOP [p]}:
	C_inv_return_phase [p,i] =
	( remaining_years [i,p] / lifetime [y_start,i] * (F_new [p,i] - sum {p2 in PHASE_WND union PHASE_UP_TO} (F_decom [p2,p,i]) )  * (1/((1+SDR[y_start])^35)) * ( c_inv [y_start,i] + c_inv [y_stop,i] ) / 2 * l_grid_ext[i] * k_security[i] / n_stations[i] ) ;

# [Eq. 22] Aggregate return investment per technology
subject to investment_return {i in TECHNOLOGIES diff GRIDS}:
	C_inv_return [i] = sum {p in PHASE_WND union PHASE_UP_TO union {"2015_2020"}} C_inv_return_phase [p,i];
subject to investment_return_grid {i in GRIDS}:
	C_inv_return [i] = sum {p in PHASE_WND union PHASE_UP_TO union {"2015_2020"}} C_inv_return_phase [p,i];

# [Eq. 18] Compute operating cost for transition
subject to Opex_tot_cost_calculation :
	C_tot_opex = C_opex["YEAR_2020"] 
				 + t_phase *  sum {p in PHASE_WND union PHASE_UP_TO,y_start in PHASE_START [p],y_stop in PHASE_STOP [p]} ( 
					                 (C_opex [y_start] + C_opex [y_stop])/2 *(actualisation_factor [p,y_start]+actualisation_factor [p,y_stop])/2) ; 

# [Eq. 20] Compute operating cost for years
subject to Opex_cost_calculation{y in YEARS_WND union YEARS_UP_TO} : 
	C_opex [y] = sum {j in TECHNOLOGIES} C_maint [y,j] + sum {i in RESOURCES} C_op [y,i]; 

# Compute operating cost for phase and for tech.
subject to operation_computation_tech {p in PHASE_WND union PHASE_UP_TO, y_start in PHASE_START[p], y_stop in PHASE_STOP[p], i in TECHNOLOGIES}:
	C_op_phase_tech [p,i] = t_phase *   ((C_maint [y_start,i] + C_maint [y_stop,i])/2 *(actualisation_factor [p,y_start]+actualisation_factor [p,y_stop])/2) ; 


subject to operation_computation_tech_no_actu {p in PHASE_WND union PHASE_UP_TO, y_start in PHASE_START[p], y_stop in PHASE_STOP[p], i in TECHNOLOGIES}:
	C_op_phase_tech_no_actu [p,i] = t_phase *   ((C_maint [y_start,i] + C_maint [y_stop,i])/2);
# Compute operating cost for phase and for resources
subject to operation_computation_res {p in PHASE_WND union PHASE_UP_TO, y_start in PHASE_START[p], y_stop in PHASE_STOP[p], i in RESOURCES}:
	C_op_phase_res [p,i] = t_phase *   ((C_op [y_start,i] + C_op [y_stop,i])/2 *(actualisation_factor [p,y_start]+actualisation_factor [p,y_stop])/2) ; 

subject to operation_computation_res_no_actu {p in PHASE_WND union PHASE_UP_TO, y_start in PHASE_START[p], y_stop in PHASE_STOP[p], i in RESOURCES}:
	C_op_phase_res_no_actu [p,i] = t_phase *   ((C_op [y_start,i] + C_op [y_stop,i])/2 ) ;

# We could either limit the max investment on a period or fix that these investments must be equals in $CAD_2015
subject to maxInvestment {p in PHASE_WND union {"2015_2020"}}:
	 C_inv_phase [p] <= max_inv_phase[p]; #
# subject to sameInvestmentPerPhase {p in PHASE}:
# 	 C_inv_phase [p] = Fixed_phase_investment;

# Limit the investment cost of a single phase to a maximum share of the total non-actualised investment cost.
# The 2015_2020 initialisation phase is excluded from both sides: its investment is a fixed historical given
# (not a decision), and it would otherwise dominate the total.
subject to limit_cost_share_phase {p in PHASE_WND}:
	sum {i in TECHNOLOGIES} C_inv_phase_tech_no_actu [p,i]
	<= max_share_cost_phase * sum {p2 in PHASE_WND union PHASE_UP_TO, i in TECHNOLOGIES} C_inv_phase_tech_no_actu [p2,i];





### Additional constraints MATTIA 2026

# Impose that F_Mult of a storage tech in coherent STO_NG = NG_STO installed
subject to capacity_storage_equal_in_out_NG {y in YEARS_UP_TO union YEARS_WND}: 
	F_Mult[y,"STO_NG"] = F_Mult[y,"NG_STO"];
subject to capacity_storage_equal_in_out_SNG {y in YEARS_UP_TO union YEARS_WND}: 
	F_Mult[y,"STO_SNG"] = F_Mult[y,"SNG_STO"];
subject to capacity_storage_equal_in_out_H2 {y in YEARS_UP_TO union YEARS_WND}: 
	F_Mult[y,"STO_H2"] = F_Mult[y,"H2_STO"];
subject to capacity_storage_equal_in_out_DIE {y in YEARS_UP_TO union YEARS_WND}: 
	F_Mult[y,"STO_DIE"] = F_Mult[y,"DIE_STO"];
subject to capacity_storage_equal_in_out_GASO {y in YEARS_UP_TO union YEARS_WND}: 
	F_Mult[y,"STO_GASO"] = F_Mult[y,"GASO_STO"];
subject to capacity_storage_equal_in_out_ELEC {y in YEARS_UP_TO union YEARS_WND}: 
	F_Mult[y,"STO_ELEC"] = F_Mult[y,"ELEC_STO"];
subject to capacity_storage_equal_in_out_CO2 {y in YEARS_UP_TO union YEARS_WND}: 
	F_Mult[y,"STO_CO2"] = F_Mult[y,"CO2_STO"];

/*
# Set ELectricity importations 
subject to elec_import_low {y in YEARS_UP_TO union YEARS_WND diff {"YEAR_2020","YEAR_2025"}}:
	Res[y,"ELECTRICITY_EHV"] <= 35556;
subject to elec_import_up {y in YEARS_UP_TO union YEARS_WND}:
	Res[y,"ELECTRICITY_EHV"] >= 35556;
*/
# Impose electricity import 
subject to elec_import {y in YEARS_UP_TO union YEARS_WND diff {"YEAR_2020","YEAR_2025"}}:
	Annual_Res[y,'ELECTRICITY_EHV'] = 33889;



# Distribute decommissioning of 2015_2020 stock uniformly for all non-mobility technologies.
# Cumulative formulation: by phase p, cumulative 2015_2020 decom >= k * uniform_rate,
# where k = number of STILL_IN_USE phases up to p.
# This allows early decommissioning: if the model fully decommissions a tech in an early
# phase, subsequent phases automatically satisfy the constraint. New installs are unaffected
# since the constraint only covers the "2015_2020" vintage of F_decom.

subject to distribution_init_general {p in PHASE_WND, t in TECHNOLOGIES diff STORAGE_TECH diff INFRASTRUCTURE diff {"HYDRO_DAM", "HYDRO_RIVER"}
    diff (setof {m in {"MOB_PRIVATE_ROAD_SD","MOB_PRIVATE_ROAD_MD","MOB_PRIVATE_ROAD_LD","MOB_PRIVATE_ROAD_ELD","MOB_PUBLIC_RAIL_SD","MOB_PUBLIC_RAIL_MD","MOB_PUBLIC_RAIL_LD","MOB_PUBLIC_RAIL_ELD","MOB_FREIGHT_ROAD_SD","MOB_FREIGHT_ROAD_MD","MOB_FREIGHT_RAIL_LD","MOB_FREIGHT_RAIL_ELD","MOB_PUBLIC_ROAD_SD","MOB_PUBLIC_ROAD_MD","MOB_PUBLIC_ROAD_LD","MOB_PUBLIC_ROAD_ELD","MOB_FREIGHT_ROAD_LD","MOB_FREIGHT_ROAD_ELD","MOB_PUBLIC_AIR_LD","MOB_PUBLIC_AIR_ELD","MOB_FREIGHT_MARITIME_ELD","MOB_FREIGHT_AIR_ELD"}, tt in TECHNOLOGIES_OF_MOB_TYPE[m]} tt):
    "STILL_IN_USE" in AGE[t,p]}:
    sum {p2 in PHASE_WND union PHASE_UP_TO: ord(p2,PHASE) <= ord(p,PHASE)}
        F_decom[p2, "2015_2020", t]
    >=
    card({p2 in PHASE_WND union PHASE_UP_TO:
        ord(p2,PHASE) <= ord(p,PHASE) and "STILL_IN_USE" in AGE[t,p2]})
    * (5 * F_new["2015_2020", t] / lifetime["YEAR_2020", t]);

# For mobility impose to the value, assuming the technology needs to be used until the end of its lifetime 
subject to distribution_init {p in PHASE_WND, m in {"MOB_PRIVATE_ROAD_SD","MOB_PRIVATE_ROAD_MD","MOB_PRIVATE_ROAD_LD","MOB_PRIVATE_ROAD_ELD","MOB_PUBLIC_RAIL_SD","MOB_PUBLIC_RAIL_MD","MOB_PUBLIC_RAIL_LD","MOB_PUBLIC_RAIL_ELD","MOB_FREIGHT_ROAD_SD","MOB_FREIGHT_ROAD_MD","MOB_FREIGHT_RAIL_LD","MOB_FREIGHT_RAIL_ELD","MOB_PUBLIC_ROAD_SD","MOB_PUBLIC_ROAD_MD","MOB_PUBLIC_ROAD_LD","MOB_PUBLIC_ROAD_ELD","MOB_FREIGHT_ROAD_LD","MOB_FREIGHT_ROAD_ELD","MOB_PUBLIC_AIR_LD","MOB_PUBLIC_AIR_ELD","MOB_FREIGHT_MARITIME_ELD","MOB_FREIGHT_AIR_ELD"}, t in TECHNOLOGIES_OF_MOB_TYPE[m]: "STILL_IN_USE" in AGE[t,p]}:
	F_decom [p,"2015_2020",t] = 5*F_new["2015_2020",t]/lifetime["YEAR_2020",t];



# Link F_new of base mobility techs to sum of their distance variants (mirrors snapshot privatemob_installed_pertech1)
subject to fnew_base_private {p in PHASE union {"2015_2020"}, j in TECHNOLOGIES_OF_PRIVATEMOB_ALL_DISTANCES}:
	F_new[p, j] = sum{i in MODELS_OF_TECHNOLOGIES_OF_PRIVATEMOB_ALL_DISTANCES[j]} F_new[p, i];
subject to fnew_base_public {p in PHASE union {"2015_2020"}, j in TECHNOLOGIES_OF_PUBLICMOB_ALL_DISTANCES}:
	F_new[p, j] = sum{i in MODELS_OF_TECHNOLOGIES_OF_PUBLICMOB_ALL_DISTANCES[j]} F_new[p, i];
subject to fnew_base_freight {p in PHASE union {"2015_2020"}, j in TECHNOLOGIES_OF_FREIGHTMOB_ALL_DISTANCES}:
	F_new[p, j] = sum{i in MODELS_OF_TECHNOLOGIES_OF_FREIGHTMOB_ALL_DISTANCES[j]} F_new[p, i];


# Link F_decom of base mobility techs to sum of their distance variants
subject to decom_base_private {p in PHASE_WND union PHASE_UP_TO, p_b in PHASE union {"2015_2020"}, j in TECHNOLOGIES_OF_PRIVATEMOB_ALL_DISTANCES}:
	F_decom[p, p_b, j] = sum{i in MODELS_OF_TECHNOLOGIES_OF_PRIVATEMOB_ALL_DISTANCES[j]} F_decom[p, p_b, i];
subject to decom_base_public {p in PHASE_WND union PHASE_UP_TO, p_b in PHASE union {"2015_2020"}, j in TECHNOLOGIES_OF_PUBLICMOB_ALL_DISTANCES}:
	F_decom[p, p_b, j] = sum{i in MODELS_OF_TECHNOLOGIES_OF_PUBLICMOB_ALL_DISTANCES[j]} F_decom[p, p_b, i];
subject to decom_base_freight {p in PHASE_WND union PHASE_UP_TO, p_b in PHASE union {"2015_2020"}, j in TECHNOLOGIES_OF_FREIGHTMOB_ALL_DISTANCES}:
	F_decom[p, p_b, j] = sum{i in MODELS_OF_TECHNOLOGIES_OF_FREIGHTMOB_ALL_DISTANCES[j]} F_decom[p, p_b, i];


#### TOTAL COST #####

var TotalTransitionCost >= 0; 
var TotalEmission ;

# Parameter for Pareton front generation
param max_cost_budget default Infinity; # [M$CAD] — overridden by sweep script
param max_co2_budget  default Infinity; # [ktCO2-eq.] — overridden by sweep script

# [Eq.16] Total transition cost 
subject to total_cost_transition:
	TotalTransitionCost = C_tot_capex + C_tot_opex;
subject to max_cost_transition:
	TotalTransitionCost <= max_cost_budget;


subject to total_emissions:
	TotalEmission = sum{y in YEARS_WND} TotalGWP[y];
subject to max_co2_transition:
	TotalGWPTransition <= max_co2_budget;#TotalEmission


/*
subject to no_backslide_elec_heat {p in PHASE_WND, y_start in PHASE_START[p], y_stop in PHASE_STOP[p]}:
    sum{t in PERIODS} (F_Mult_t[y_stop,'DEC_DIRECT_ELEC',t] + F_Mult_t[y_stop,'DEC_HP_ELEC',t] + F_Mult_t[y_stop,'DHN_HP_ELEC',t]) * t_op[t]
    >=
    sum{t in PERIODS} (F_Mult_t[y_start,'DEC_DIRECT_ELEC',t] + F_Mult_t[y_start,'DEC_HP_ELEC',t] + F_Mult_t[y_start,'DHN_HP_ELEC',t]) * t_op[t];
	*/