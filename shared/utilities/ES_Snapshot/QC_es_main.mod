######################################################
#
# Swiss-EnergyScope (SES) MILP modeling framework
# Model file
# Author: Stefano Moret
# Date: 27.10.2017
# Model documentation: Moret S. (2017). "Strategic Energy Planning under Uncertainty". PhD Thesis n. 7961, EPFL, Switzerland (Chapter 1). (http://dx.doi.org/10.5075/epfl-thesis-7961)
# For terms of use and how to cite this work please check the ReadMe file. 
#
######################################################

### SETS [Figure 1.3] ###

## MAIN SETS: Sets whose elements are input directly in the data file
set PERIODS; # time periods
set SECTORS; # sectors of the energy system
set END_USES_INPUT; # Types of demand (end-uses). Input to the model
set END_USES_CATEGORIES; # Categories of demand (end-uses): electricity, heat, mobility
set END_USES_TYPES_OF_CATEGORY {END_USES_CATEGORIES}; # Types of demand (end-uses).
set RESOURCES; # Resources: fuels (wood and fossils) and electricity imports 
set BIOMASS within RESOURCES;
set EXPORT within RESOURCES; # exported resources        #要不要考虑化工产品出口？？?:Should we consider exporting chemical products?
set END_USES_TYPES := setof {i in END_USES_CATEGORIES, j in END_USES_TYPES_OF_CATEGORY [i]} j; # secondary set
set TECHNOLOGIES_OF_END_USES_TYPE {END_USES_TYPES}; # set all energy conversion technologies (excluding storage technologies)
set STORAGE_TECH; # set of storage technologies 
#set STORAGE_ALL;
set INFRASTRUCTURE; # Infrastructure: DHN, grid, and intermediate energy conversion technologies (i.e. not directly supplying end-use demand)
set TECHNOLOGIES_OF_IND; # Cement
set INTERMIDIATE_RESOURCES within RESOURCES;
set RENEW within RESOURCES;
set PV_TECH;


## Biomasss
set BIO_PRODUCT;
#set TECHNOLOGIES_OF_BIOMASS;
#set TECHNOLOGIES_OF_BIOMASS_CCU within TECHNOLOGIES_OF_BIOMASS;

## set for CCUS
set CO2_CATEGORY;
set TECHNOLOGIES_OF_CC;
set TECHNOLOGIES_OF_CCS;
set TECHNOLOGIES_OF_CCU;
set TECHNOLOGIES_OF_CCUS:=TECHNOLOGIES_OF_CC union TECHNOLOGIES_OF_CCS union TECHNOLOGIES_OF_CCU;
set ENERGY_TECHNOLOGIES_WITH_CC;

# Mobility sets
set TECHNOLOGIES_OF_PRIVATEMOB_ALL_DISTANCES;
set MODELS_OF_TECHNOLOGIES_OF_PRIVATEMOB_ALL_DISTANCES {TECHNOLOGIES_OF_PRIVATEMOB_ALL_DISTANCES}; # Makes the link between a given private mobility tech and its corresponding SD,MD,LD,ELD model  
set TECHNOLOGIES_OF_FREIGHTMOB_ALL_DISTANCES;
set MODELS_OF_TECHNOLOGIES_OF_FREIGHTMOB_ALL_DISTANCES {TECHNOLOGIES_OF_FREIGHTMOB_ALL_DISTANCES}; # Makes the link between a given freight mobility tech and its corresponding SD,MD,LD,ELD model
set TECHNOLOGIES_OF_PUBLICMOB_ALL_DISTANCES;
set MODELS_OF_TECHNOLOGIES_OF_PUBLICMOB_ALL_DISTANCES {TECHNOLOGIES_OF_PUBLICMOB_ALL_DISTANCES}; # Makes the link between a given public mobility tech and its corresponding SD,MD,LD,ELD model 
set MOBILITY_TYPE;
set TECHNOLOGIES_OF_MOB_TYPE {MOBILITY_TYPE};
set MODELS_OF_TECHNOLOGIES_MARITIME_BULK_CARRIER;
set MODELS_OF_TECHNOLOGIES_MARITIME_CONTAINER;
set MODELS_OF_TECHNOLOGIES_MARITIME_OIL_TANKER;

## SECONDARY SETS: a secondary set is defined by operations on MAIN SETS
set LAYERS := (RESOURCES diff EXPORT) union END_USES_TYPES; # Layers are used to balance resources/products in the system
set TECHNOLOGIES := (setof {i in END_USES_TYPES, j in TECHNOLOGIES_OF_END_USES_TYPE [i]} j) union STORAGE_TECH union INFRASTRUCTURE union TECHNOLOGIES_OF_CCUS union TECHNOLOGIES_OF_IND union TECHNOLOGIES_OF_PRIVATEMOB_ALL_DISTANCES union TECHNOLOGIES_OF_PUBLICMOB_ALL_DISTANCES union TECHNOLOGIES_OF_FREIGHTMOB_ALL_DISTANCES; 
set TECHNOLOGIES_OF_END_USES_CATEGORY {i in END_USES_CATEGORIES} within TECHNOLOGIES := setof {j in END_USES_TYPES_OF_CATEGORY[i], k in TECHNOLOGIES_OF_END_USES_TYPE [j]} k; 

## Grid infrastructure sets
set ELECTRICITY_LAYERS within LAYERS;
set HEAT_LAYERS within LAYERS;
set NG_LAYERS within LAYERS;
set SNG_LAYERS within LAYERS;
set H2_LAYERS within LAYERS;
set GRIDS_OF_LAYERS{ELECTRICITY_LAYERS union NG_LAYERS union H2_LAYERS};
set GRIDS;

# Printing sets
set INFRASTRUCTURE_ELEC_GRID;
set INFRASTRUCTURE_GAS_GRID;
set INFRASTRUCTURE_ELEC_STORAGE;
set INFRASTRUCTURE_GAS_STORAGE;


## Tax sets [@Xiang Li, Jonas Schnidrig]
#------------------------------------------------------------------
set FOSSIL_FUELS within RESOURCES; # Fossil fuels for taxation
set BIO_FUELS within RESOURCES; # Biofuels

## Additional SETS: only needed for printing out results
set COGEN within TECHNOLOGIES; # cogeneration tech
set BOILERS within TECHNOLOGIES; # boiler tech

## Mobility sets
set BUSES within TECHNOLOGIES;
set SCHOOLBUSES within TECHNOLOGIES;
set TRAINS within TECHNOLOGIES;
set SUVS within TECHNOLOGIES;
# For NG storage


### PARAMETERS [Table 1.1] ###
param end_uses_demand_year {END_USES_INPUT, SECTORS} >= 0 default 0; # end_uses_year: table end-uses demand vs sectors (input to the model). Yearly values.
param end_uses_input {i in END_USES_INPUT} := sum {s in SECTORS} (end_uses_demand_year [i,s]); # Figure 1.4: total demand for each type of end-uses across sectors (yearly energy) as input from the demand-side model
param i_rate > 0; # discount rate (real discount rate)

# Share public vs private mobility
param share_mobility_public_min_sd >= 0, <= 1 default 0; # % min limit for penetration of public mobility over total mobility 
param share_mobility_public_max_sd >= 0, <= 1 default 1; # % max limit for penetration of public mobility over total mobility
param share_mobility_public_min_md >= 0, <= 1 default 0; # % min limit for penetration of public mobility over total mobility 
param share_mobility_public_max_md >= 0, <= 1 default 1; # % max limit for penetration of public mobility over total mobility 
param share_mobility_public_min_ld >= 0, <= 1 default 0; # % min limit for penetration of public mobility over total mobility 
param share_mobility_public_max_ld >= 0, <= 1 default 1; # % max limit for penetration of public mobility over total mobility 
param share_mobility_public_min_eld >= 0, <= 1 default 0; # % min limit for penetration of public mobility over total mobility 
param share_mobility_public_max_eld >= 0, <= 1 default 1; # % max limit for penetration of public mobility over total mobility 

param share_public_rail_min_sd >= 0, <= 1 default 0; # % min limit for penetration of rail in public transportation
param share_public_rail_max_sd >= 0, <= 1 default 1; # % max limit for penetration of rail in public transportation
param share_public_rail_min_md >= 0, <= 1 default 0; # % min limit for penetration of rail in public transportation
param share_public_rail_max_md >= 0, <= 1 default 1; # % max limit for penetration of rail in public transportation
param share_public_rail_min_ld >= 0, <= 1 default 0; # % min limit for penetration of rail in public transportation
param share_public_rail_max_ld >= 0, <= 1 default 1; # % max limit for penetration of rail in public transportation
param share_public_rail_min_eld >= 0, <= 1 default 0; # % min limit for penetration of rail in public transportation
param share_public_rail_max_eld >= 0, <= 1 default 1; # % max limit for penetration of rail in public transportation

param share_public_air_min_ld >= 0, <= 1 default 0; # % min limit for penetration of air in public transportation
param share_public_air_max_ld >= 0, <= 1 default 1; # % max limit for penetration of air in public transportation
param share_public_air_min_eld >= 0, <= 1 default 0; # % min limit for penetration of air in public transportation
param share_public_air_max_eld >= 0, <= 1 default 1; # % max limit for penetration of air in public transportation


# Share train vs truck vs plane in freight transportation
param share_freight_rail_min_ld >= 0, <= 1 default 0; # % min limit for penetration of train in freight transportation for LD
param share_freight_rail_max_ld >= 0, <= 1 default 1; # % max limit for penetration of train in freight transportation for LD
param share_freight_rail_min_eld >= 0, <= 1 default 0; # % min limit for penetration of train in freight transportation for ELD
param share_freight_rail_max_eld >= 0, <= 1 default 1; # % max limit for penetration of train in freight transportation for ELD
param share_freight_air_min_eld >= 0, <= 1 default 0; # % min limit for penetration of air in freight transportation for ELD
param share_freight_air_max_eld >= 0, <= 1 default 1; # % max limit for penetration of air in freight transportation for ELD
param share_freight_maritime_min_eld >=0, <=1 default 0; # % min limit for penetration of maritime in freight transportation for ELD
param share_freight_maritime_max_eld >=0, <=1 default 1; # % max limit for penetration of maritime in freight transportation for ELD

param share_freight_maritime_bulk_carrier >=0, <=1 default 0495; # % limit for penetration of bulk carrier in maritime freight transportation
param share_freight_maritime_container >=0, <=1 default 0.15; # % limit for penetration of container in maritime freight transportation
param share_freight_maritime_oil_tanker >=0, <=1 default 0.23; # % limit for penetration of oil tanker in maritime freight transportation

# Share schoolbus in SD public mobility
param share_public_schoolbus_min_sd >= 0, <= 1 default 0; # % min limit for penetration of schoolbuses in SD public mobility
param share_public_schoolbus_max_sd >= 0, <= 1 default 1; # % max limit for penetration of schoolbuses in SD public mobility

# Share dhn vs decentralized for low-T heating
param share_heat_dhn_min >= 0, <= 1 default 0; # % min limit for penetration of dhn in low-T heating
param share_heat_dhn_max >= 0, <= 1 default 1; # % max limit for penetration of dhn in low-T heating

param t_op {PERIODS}; # duration of each time period [h]
param total_time := sum {t in PERIODS} (t_op [t]); # added just to simplify equations
param lighting_month {PERIODS} >= 0, <= 1; # %_lighting: factor for sharing lighting across months (adding up to 1)
param heating_month {PERIODS} >= 0, <= 1; # %_sh: factor for sharing space heating across months (adding up to 1), hot water (HW) not included which is considered to be constant over months
param elec_export_month {PERIODS} >= 0, <= 1; # %_electricity_export: factor for sharing electricity exports across months (adding up to 1)
param cooling_month {PERIODS} >= 0, <= 1; # %_sc: factor for sharing space cooling across months (adding up to 1)

# f: input/output Resources/Technologies to Layers. Reference is one unit ([GW] or [Mpkm/h] or [Mtkm/h]) of (main) output of the resource/technology. input to layer (output of technology) > 0.
param layers_in_out {RESOURCES union TECHNOLOGIES diff STORAGE_TECH, LAYERS union CO2_CATEGORY union {"HEAT_WASTE"}} default 0;

# Attributes of TECHNOLOGIES
param ref_size {TECHNOLOGIES} >= 0 default 0.001; # f_ref: reference size of each technology, expressed in the same units as the layers_in_out table. Refers to main output (heat for cogen technologies). storage level [GWh] for STORAGE_TECH
param c_inv {TECHNOLOGIES} >= 0 default 0; # Specific investment cost [MCHF/GW].[MCHF/GWh] for STORAGE_TECH
param c_maint {TECHNOLOGIES} >= 0 default 0; # O&M cost [MCHF/GW/year]: O&M cost does not include resource (fuel) cost. [MCHF/GWh] for STORAGE_TECH
param lifetime {TECHNOLOGIES} >= 0 default 20; # n: lifetime [years]
param f_max {TECHNOLOGIES} >= 0 default 10000; # Maximum feasible installed capacity [GW], refers to main output. storage level [GWh] for STORAGE_TECH
param f_min {TECHNOLOGIES} >= 0 default 0; # Minimum feasible installed capacity [GW], refers to main output. storage level [GWh] for STORAGE_TECH
param fmax_perc {TECHNOLOGIES} >= 0, <= 1 default 1; # value in [0,1]: this is to fix that a technology can at max produce a certain % of the total output of its sector over the entire year
param fmin_perc {TECHNOLOGIES} >= 0, <= 1 default 0; # value in [0,1]: this is to fix that a technology can at min produce a certain % of the total output of its sector over the entire year
param fmax_perc_mob {TECHNOLOGIES} >= 0, <= 1 default 1; # value in [0,1]: this is to fix that a technology can at max produce a certain % of the total output of its sector over the entire year
param fmin_perc_mob {TECHNOLOGIES} >= 0, <= 1 default 0; # value in [0,1]: this is to fix that a technology can at min produce a certain % of the total output of its sector over the entire year

param c_p_t {TECHNOLOGIES, PERIODS} >= 0, <= 1 default 1; # capacity factor of each technology and resource, defined on monthly basis. Different than 1 if F_Mult_t (t) <= c_p_t (t) * F_Mult
param c_p {TECHNOLOGIES} >= 0, <= 1 default 1; # capacity factor of each technology, defined on annual basis. Different than 1 if sum {t in PERIODS} F_Mult_t (t) * t_op (t) <= c_p * F_Mult
param tau {i in TECHNOLOGIES} := i_rate * (1 + i_rate)^lifetime [i] / (((1 + i_rate)^lifetime [i]) - 1); # Annualisation factor for each different technology
param gwp_constr {TECHNOLOGIES} >= 0 default 0; # GWP emissions associated to the construction of technologies [ktCO2-eq./GW]. Refers to [GW] of main output
param trl {TECHNOLOGIES} >=0 default 9; # Technlogy Readiness Level

# Attributes of RESOURCES
param c_op {RESOURCES,PERIODS} >= 0 default 0; # cost of resources in the different periods [MCHF/GWh]
param avail {RESOURCES} >= 0 default 0; # Yearly availability of resources [GWh/y]
# param gwp_op {RESOURCES} >= 0 default 0; # GWP emissions associated to the use of resources [ktCO2-eq./GWh]. Includes extraction/production/transportation and combustion => modification: excluding the combustion 
# param carbon_content {RESOURCES union CO2_CATEGORY} >= 0 default 0.07; #kt-C/GWh
param gwp_e{RESOURCES,PERIODS} >=0 default 0; # [ktCO2-eq/GWh] GWP due to minning, transportation in resource importation

param f_grid_ext {GRIDS} default 0; # existing grid size [GW]
param l_grid_ext {GRIDS} default 0; # existing grid length [km]
param n_stations {GRIDS} default 1; # number of transformation stations [-]
param l_grid_ref {g in GRIDS} := l_grid_ext [g]/ n_stations [g] ; # average grid transition length per energytron [km]
param k_security {GRIDS} default 0; # Conversion factor from model-observation-security [-]

# Attributes of RESOURCES & TECHNOLOGIES
param c_tax {LAYERS union CO2_CATEGORY} >= 0 default 0; # Tax costs ([MCHF/MtCO2] mobility, [MCHF/GWh] heating): taxation costs for CO2 tax of technology related resources emissions
param e_density {RESOURCES} >= 0 default 0; # volumetric energy density [Wh/l]
param c_tax_co2 >= 0 default 0; # Tax per emitted CO2 [CHF/tCO2] https://www.fedlex.admin.ch/eli/cc/2012/855/en §29.1
param c_tax_fuel >= 0 default 0; # Compensation tax motor fuels [CHF/l] https://www.fedlex.admin.ch/eli/cc/2012/855/en §26.3
param c_tax_res {RESOURCES} >= 0 default 0; # [CHF/1000l]import tax for mineral oils 
param c_tax_import {RESOURCES} >= 0 default 0; # [MCHF/GWh]import tax for mineral oils

# Attributes of STORAGE_TECH
param storage_eff_in {STORAGE_TECH, LAYERS} >= 0, <= 1 default 0; # eta_sto_in: efficiency of input to storage from layers.  If 0 storage_tech/layer are incompatible
param storage_eff_out {STORAGE_TECH, LAYERS} >= 0, <= 1 default 0; # eta_sto_out: efficiency of output from storage to layers. If 0 storage_tech/layer are incompatible

# Losses in the networks
param loss_coeff {END_USES_TYPES} >= 0 default 0; # 0 in all cases apart from electricity grid and DHN
param peak_dhn_factor >= 0;

# Control pamameters
param co2_limit default Infinity;
param co2_limit_max default 0;

param sng_min default 0;
param renew default 0;
param trl_min default 1;
param trl_max default 9;
param bio_ratio default 0;

# for monthly variable carbon intensity of electricity import
#param co2_int_ratio{TECHNOLOGIES union RESOURCES,PERIODS}>=0, <=1 default 1;


## VARIABLES [Tables 1.2, 1.3] ###
#var End_Uses {LAYERS union BIO_PRODUCT, PERIODS} >= 0; # total demand for each type of end-uses (monthly power). Defined for all layers (0 if not demand)
var End_Uses {LAYERS, PERIODS} >= 0; # total demand for each type of end-uses (monthly power). Defined for all layers (0 if not demand)

#var Number_Of_Units {TECHNOLOGIES} integer; # N: number of units of size ref_size which are installed.
var F_Mult {TECHNOLOGIES} >= 0; # F: installed size, multiplication factor with respect to the values in layers_in_out table
var F_Mult_t {RESOURCES union TECHNOLOGIES, PERIODS} >= 0; # F_t: Operation in each period. multiplication factor with respect to the values in layers_in_out table. Takes into account c_p
var C_inv {TECHNOLOGIES} >= 0; # Total investment cost of each technology
var C_maint {TECHNOLOGIES} >= 0; # Total O&M cost of each technology (excluding resource cost)
var C_op {RESOURCES} >= 0; # Total O&M cost of each resource
var C_tax_tech {TECHNOLOGIES,PERIODS} >= 0; # Total tax costs of each technology related resource
var C_tax_res {RESOURCES,PERIODS} >= 0; # Total tax costs of each technology related resource
var CC_tax_reduction{t in PERIODS} >=0; # Carbon capture tax reduction
var Storage_In {i in STORAGE_TECH, LAYERS, PERIODS} >= 0; # Sto_in: Power [GW] input to the storage in a certain period
var Storage_Out {i in STORAGE_TECH, LAYERS, PERIODS} >= 0; # Sto_out: Power [GW] output from the storage in a certain period



#param Share_Mobility_Public_SD default 0.3;
#let Share_Mobility_Public_SD := 0.3;
#param Share_Mobility_Public_MD default 0.3;
#let Share_Mobility_Public_MD := 0.3;
#param Share_Mobility_Public_LD default 0.3;
#let Share_Mobility_Public_LD := 0.3;
#param Share_Mobility_Public_ELD default 0.3;
#let Share_Mobility_Public_ELD := 0.3;

var Share_Mobility_Public_SD >= share_mobility_public_min_sd, <= share_mobility_public_max_sd; # %_Public: % of passenger SD mobility attributed to public transportation
var Share_Mobility_Public_MD >= share_mobility_public_min_md, <= share_mobility_public_max_md; # %_Public: % of passenger MD mobility attributed to public transportation
var Share_Mobility_Public_LD >= share_mobility_public_min_ld, <= share_mobility_public_max_ld; # %_Public: % of passenger LD mobility attributed to public transportation
var Share_Mobility_Public_ELD >= share_mobility_public_min_eld, <= share_mobility_public_max_eld; # %_Public: % of passenger ELD mobility attributed to public transportation

#var Share_Public_Rail_SD, >= share_public_rail_min_sd, <= share_public_rail_max_sd; # %_Rail: % of SD public mobility attributed to rail transportation
#var Share_Public_Rail_MD, >= share_public_rail_min_md, <= share_public_rail_max_md; # %_Rail: % of MD public mobility attributed to rail transportation
#var Share_Public_Rail_LD, >= share_public_rail_min_ld, <= share_public_rail_max_ld; # %_Rail: % of LD public mobility attributed to rail transportation
#var Share_Public_Rail_ELD, >= share_public_rail_min_eld, <= share_public_rail_max_eld; # %_Rail: % of ELD public mobility attributed to rail transportation
#
#var Share_Public_Air_LD, >= share_public_air_min_ld, <= share_public_air_max_ld; # %_Air: % of public LD mobility attributed to air transportation
#var Share_Public_Air_ELD, >= share_public_air_min_eld, <= share_public_air_max_eld; # %_Air: % of public ELD mobility attributed to air transportation
#
#var Share_Freight_Rail_LD, >= share_freight_rail_min_ld, <= share_freight_rail_max_ld; # %_Rail: % of freight mobility attributed to rail transportation
#var Share_Freight_Rail_ELD, >= share_freight_rail_min_eld, <= share_freight_rail_max_eld; # %_Rail: % of freight mobility attributed to rail transportation
#var Share_Freight_Air_ELD, >= share_freight_air_min_eld, <= share_freight_air_max_eld; # %_Air: % of freight mobility attributed to air transportation

var Share_Heat_Dhn, >= share_heat_dhn_min, <= share_heat_dhn_max; # %_Dhn: % of low-T heat demand attributed to DHN
var Y_Solar_Backup {TECHNOLOGIES} binary; # Y_Solar: binary variable. if 1, identifies the decentralized technology (only 1) which is backup for solar. 0 for all other technologies
var Losses {END_USES_TYPES, PERIODS} >= 0; # Loss: Losses in the networks (normally electricity grid and DHN)
var GWP_constr {TECHNOLOGIES} >= 0; # Total emissions of the technologies [ktCO2-eq.]
var TotalGWP; # GWP_tot: Total global warming potential (GWP) emissions in the system [ktCO2-eq./y]
var TotalCost >= 0; # C_tot: Total GWP emissions in the system [ktCO2-eq./y]

# variables added for recording the output results 
var Monthly_Prod{TECHNOLOGIES,PERIODS}; #[GWh] the production in each time period except storage technologies
var Annual_Prod{TECHNOLOGIES diff STORAGE_TECH};
var Annual_Res{RESOURCES};
var STO{STORAGE_TECH,PERIODS};   #[GWh], real stored energy in a certain technology, with efficiency considered
var GWP{CO2_CATEGORY,PERIODS}; # for CO2_A CO2_C CO2_S CO2_E CO2_CS at each time period, unit: kt/h
var Total_emission{PERIODS};

# variables for ng storage
var STO_NG_LEVEL{PERIODS} >= 0; 
var STO_CO2_LEVEL{PERIODS} >=0;
var STO_H2_LEVEL{PERIODS} >=0;

# variables of INFRASTRUCTURE
var C_inv_grid_help{GRIDS} >= 0;
### CONSTRAINTS ###

## End-uses demand calculation constraints 

# [Figure 1.4] From annual energy demand to monthly power demand. End_Uses is non-zero only for demand layers.
subject to end_uses_t {l in LAYERS, t in PERIODS}:
	End_Uses [l,t] = (if l == "ELECTRICITY_LV" then
			(end_uses_input[l] / total_time + end_uses_input["LIGHTING"] * lighting_month [t] / t_op [t] + end_uses_input["HEAT_LOW_T_SC"] * cooling_month [t] / t_op [t] + Losses [l,t])
		else (if l == "ELECTRICITY_MV" then
			end_uses_input[l] / total_time  + Losses [l,t]
		else (if l == "ELECTRICITY_HV" then
			end_uses_input[l] / total_time  + Losses [l,t]
		else (if l == "ELECTRICITY_EHV" then
			end_uses_input[l] / total_time  + end_uses_input["ELECTRICITY_EHV_EXPORT"] * elec_export_month [t] / t_op [t]+ Losses [l,t]
		else (if l == "HEAT_LOW_T_DHN" then
			(end_uses_input["HEAT_LOW_T_HW"] / total_time + end_uses_input["HEAT_LOW_T_SH"] * heating_month [t] / t_op [t]) * Share_Heat_Dhn + Losses [l,t]
		else (if l == "HEAT_LOW_T_DECEN" then
			(end_uses_input["HEAT_LOW_T_HW"] / total_time + end_uses_input["HEAT_LOW_T_SH"] * heating_month [t] / t_op [t]) * (1 - Share_Heat_Dhn)

# Sum sur toutes les tech d'un type bornée: sum F_mutl_t *t_op <= share_rail * end_use_demand
		#Passenger Mobility
#		else (if l == "MOB_PUBLIC_RAIL_SD" then
#			(end_uses_input["MOBILITY_PASSENGER_SD"] / total_time) * Share_Mobility_Public_SD * Share_Public_Rail_SD
#		else (if l == "MOB_PUBLIC_ROAD_SD" then
#			(end_uses_input["MOBILITY_PASSENGER_SD"] / total_time) * Share_Mobility_Public_SD * (1-Share_Public_Rail_SD)
#		else (if l == "MOB_PRIVATE_ROAD_SD" then
#			(end_uses_input["MOBILITY_PASSENGER_SD"] / total_time) * (1-Share_Mobility_Public_SD)
#		else (if l == "MOB_PUBLIC_RAIL_MD" then
#			(end_uses_input["MOBILITY_PASSENGER_MD"] / total_time) * Share_Mobility_Public_MD * Share_Public_Rail_MD
#		else (if l == "MOB_PUBLIC_ROAD_MD" then
#			(end_uses_input["MOBILITY_PASSENGER_MD"] / total_time) * Share_Mobility_Public_MD * (1-Share_Public_Rail_MD)
#		else (if l == "MOB_PRIVATE_ROAD_MD" then
#			(end_uses_input["MOBILITY_PASSENGER_MD"] / total_time) * (1-Share_Mobility_Public_MD)
#		else (if l == "MOB_PUBLIC_RAIL_LD" then
#			(end_uses_input["MOBILITY_PASSENGER_LD"] / total_time) * Share_Mobility_Public_LD * Share_Public_Rail_LD
#		else (if l == "MOB_PUBLIC_AIR_LD" then
#			(end_uses_input["MOBILITY_PASSENGER_LD"] / total_time) * Share_Mobility_Public_LD * Share_Public_Air_LD
#		else (if l == "MOB_PUBLIC_ROAD_LD" then
#			(end_uses_input["MOBILITY_PASSENGER_LD"] / total_time) * Share_Mobility_Public_LD * (1-Share_Public_Rail_LD-Share_Public_Air_LD)
#		else (if l == "MOB_PRIVATE_ROAD_LD" then
#			(end_uses_input["MOBILITY_PASSENGER_LD"] / total_time) * (1-Share_Mobility_Public_LD)
#		else (if l == "MOB_PUBLIC_RAIL_ELD" then
#			(end_uses_input["MOBILITY_PASSENGER_ELD"] / total_time) * Share_Mobility_Public_ELD * Share_Public_Rail_ELD
#		else (if l == "MOB_PUBLIC_AIR_ELD" then
#			(end_uses_input["MOBILITY_PASSENGER_ELD"] / total_time) * Share_Mobility_Public_ELD * Share_Public_Air_ELD
#		else (if l == "MOB_PUBLIC_ROAD_ELD" then
#			(end_uses_input["MOBILITY_PASSENGER_ELD"] / total_time) * Share_Mobility_Public_ELD * (1-Share_Public_Rail_ELD-Share_Public_Air_ELD)
#		else (if l == "MOB_PRIVATE_ROAD_ELD" then
#			(end_uses_input["MOBILITY_PASSENGER_ELD"] / total_time) * (1-Share_Mobility_Public_ELD)
#
#		#Freight Mobility
#		else (if l == "MOB_FREIGHT_ROAD_SD" then
#			(end_uses_input["MOBILITY_FREIGHT_SD"] / total_time)
#		else (if l == "MOB_FREIGHT_ROAD_MD" then
#			(end_uses_input["MOBILITY_FREIGHT_MD"] / total_time)
#		else (if l == "MOB_FREIGHT_RAIL_LD" then
#			(end_uses_input["MOBILITY_FREIGHT_LD"] / total_time) * Share_Freight_Rail_LD
#		else (if l == "MOB_FREIGHT_ROAD_LD" then
#			(end_uses_input["MOBILITY_FREIGHT_LD"] / total_time) * (1-Share_Freight_Rail_LD)
#		else (if l == "MOB_FREIGHT_RAIL_ELD" then
#			(end_uses_input["MOBILITY_FREIGHT_ELD"] / total_time) * Share_Freight_Rail_ELD
#		else (if l == "MOB_FREIGHT_AIR_ELD" then
#			(end_uses_input["MOBILITY_FREIGHT_ELD"] / total_time) * Share_Freight_Air_ELD
#		else (if l == "MOB_FREIGHT_ROAD_ELD" then
#			(end_uses_input["MOBILITY_FREIGHT_ELD"] / total_time) * (1-Share_Freight_Rail_ELD-Share_Freight_Air_ELD)


		#Passenger Mobility
		else (if l == "MOB_PUBLIC_SD" then
			(end_uses_input["MOBILITY_PASSENGER_SD"] / total_time) * Share_Mobility_Public_SD
		else (if l == "MOB_PRIVATE_SD" then
			(end_uses_input["MOBILITY_PASSENGER_SD"] / total_time) * (1-Share_Mobility_Public_SD)
		else (if l == "MOB_PUBLIC_MD" then
			(end_uses_input["MOBILITY_PASSENGER_MD"] / total_time) * Share_Mobility_Public_MD
		else (if l == "MOB_PRIVATE_MD" then
			(end_uses_input["MOBILITY_PASSENGER_MD"] / total_time) * (1-Share_Mobility_Public_MD)
		else (if l == "MOB_PUBLIC_LD" then
			(end_uses_input["MOBILITY_PASSENGER_LD"] / total_time) * Share_Mobility_Public_LD
		else (if l == "MOB_PRIVATE_LD" then
			(end_uses_input["MOBILITY_PASSENGER_LD"] / total_time) * (1-Share_Mobility_Public_LD)
		else (if l == "MOB_PUBLIC_ELD" then
			(end_uses_input["MOBILITY_PASSENGER_ELD"] / total_time) * Share_Mobility_Public_ELD
		else (if l == "MOB_PRIVATE_ELD" then
			(end_uses_input["MOBILITY_PASSENGER_ELD"] / total_time) * (1-Share_Mobility_Public_ELD)

		#Freight Mobility
		else (if l == "MOB_FREIGHT_SD" then
			(end_uses_input["MOBILITY_FREIGHT_SD"] / total_time)
		else (if l == "MOB_FREIGHT_MD" then
			(end_uses_input["MOBILITY_FREIGHT_MD"] / total_time)
		else (if l == "MOB_FREIGHT_LD" then
			(end_uses_input["MOBILITY_FREIGHT_LD"] / total_time)
		else (if l == "MOB_FREIGHT_ELD" then
			(end_uses_input["MOBILITY_FREIGHT_ELD"] / total_time)



		else (if l == "HEAT_HIGH_T" then
			end_uses_input[l] / total_time
		else (if l == "METHANOL" then
			end_uses_input["METHANOL"] / total_time
		else (if l == "PHENOL" then
			end_uses_input["PHENOL"] / total_time
		else (if l == "ACETIC_ACID" then
			end_uses_input["ACETIC_ACID"] / total_time
		else (if l == "ACETONE" then
			end_uses_input["ACETONE"] / total_time
		else (if l == "PE" then
			end_uses_input["PE"] / total_time
		else (if l == "PET" then
			end_uses_input["PET"] / total_time
		else (if l == "PVC" then
			end_uses_input["PVC"] / total_time
		else (if l == "PP" then
			end_uses_input["PP"] / total_time
		else (if l == "PS" then
			end_uses_input["PS"] / total_time
		else (if l == "ALUMINUM" then
			end_uses_input["ALUMINUM"] / total_time
		else (if l == "PAPER" then
			end_uses_input["PAPER"] / total_time
		else (if l == "CEMENT" then
			end_uses_input["CEMENT"] / total_time
		else (if l == "STEEL" then
			end_uses_input["STEEL"] / total_time
		else (if l == "FOOD" then
			end_uses_input["FOOD"] / total_time
		else 
			0 ))))))))))))))))))))))))))))))))); # For all layers which don't have an end-use demand






## Layers

# [Eq. 1.13] Layer balance equation with storage. Layers: input > 0, output < 0. Demand > 0. Storage: in > 0, out > 0;
# output from technologies/resources/storage - input to technologies/storage = demand. Demand has default value of 0 for layers which are not end_uses
# 这里包括了电力输出
# 转换效率在layer balance不予考虑，因为就到达层的能量而言，都是经过了效率转换的，效率转换在具体的
subject to layer_balance {l in LAYERS union CO2_CATEGORY diff {"H2_S","NG_S","CO2_CS","HEAT_WASTE","ELEC_S","DIESEL_S","GASOLINE_S"}, t in PERIODS}:
	0 = (if (l=="CO2_A" or l=="CO2_S") then
	   #unit for ccus technology: kt/h, operational net emission
		sum {i in RESOURCES union TECHNOLOGIES diff STORAGE_TECH} (layers_in_out[i, l] * F_Mult_t [i, t]) - GWP [l, t]
	else (if l=="CO2_E" then
		sum {i in RESOURCES union TECHNOLOGIES diff STORAGE_TECH} (layers_in_out[i, l] * F_Mult_t [i, t]) - GWP [l, t] 
		#+ 1/total_time * sum {k in TECHNOLOGIES} GWP_constr[k] # the construction emission goes to CO2_E which can only be captuerd by DAC
	else (if l=="CO2_EE" then
		#sum {i in RESOURCES} (layers_in_out[i, l] * F_Mult_t [i, t] * co2_int_ratio[i,t] * carbon_content[i]) - GWP [l, t]
		sum {i in RESOURCES} (F_Mult_t [i, t] * gwp_e[i,t]) - GWP [l, t]
	else (if l=="CO2_C" then
		sum {i in RESOURCES union TECHNOLOGIES diff STORAGE_TECH} (layers_in_out[i, l] * F_Mult_t [i, t]) 
	else
		(sum {i in RESOURCES union TECHNOLOGIES diff STORAGE_TECH} (layers_in_out[i, l] * F_Mult_t [i, t]) 
		+ sum {j in STORAGE_TECH} (Storage_Out [j, l, t] - Storage_In [j, l, t])
		- End_Uses [l, t]
		))))); #even no accumulation of intermi 

/*       
subject to co2_no_accu{t in PERIODS}:
	GWP["CO2_C",t]=0;
*/
# only the CO2_A emission from carbon-intensive fields that could be captured	
subject to co2_caputrable{t in PERIODS}:
	GWP["CO2_A",t]>=0;
subject to co2_imp{t in PERIODS}:
	GWP["CO2_EE",t]>=0;

# For avoiding F_Mult[i] tends to be a large number while all F_Mult_t[i,t] = 0
subject to f_mult_prevention{i in TECHNOLOGIES}:
	F_Mult[i]<=1000000 * sum{t in PERIODS} F_Mult_t[i,t];

## Multiplication factor

# [Eq. 1.7] Number of purchased technologies. Integer variable (so that we have only integer multiples of the reference size)
#subject to number_of_units {i in TECHNOLOGIES diff INFRASTRUCTURE}:
#	Number_Of_Units [i] = F_Mult [i] / ref_size [i]; 
	
# [Eq. 1.6] min & max limit to the size of each technology
subject to size_limit {i in TECHNOLOGIES}:
	f_min [i] <= F_Mult [i] <= f_max [i];
	
# [Eq. 1.8] relation between mult_t and mult via period capacity factor. This forces max monthly output (e.g. renewables)
subject to capacity_factor_t {i in TECHNOLOGIES diff {"H2_STO","NG_STO","CO2_STO","ELEC_STO","GASO_STO","DIE_STO"}, t in PERIODS}:
	F_Mult_t [i, t] <= F_Mult [i] * c_p_t [i, t];

# X.Li
subject to capacity_factor_Sto_ng{i in {"NG_STO"}, t in PERIODS}:
	STO_NG_LEVEL[t] <= F_Mult[i];
subject to capacity_factor_Sto_co2{i in {"CO2_STO"}, t in PERIODS}:
	STO_CO2_LEVEL[t] <= F_Mult[i];
subject to capacity_factor_Sto_h2{i in {"H2_STO"}, t in PERIODS}:
	STO_H2_LEVEL[t] <= F_Mult[i];

# [Eq. 1.9] relation between mult_t and mult via yearly capacity factor. This one forces total annual output
subject to capacity_factor {i in TECHNOLOGIES}: #for ccus technology, unit: F_Mult_t: t/h
	sum {t in PERIODS} (F_Mult_t [i, t] * t_op [t]) <= F_Mult [i] * c_p [i] * total_time;	
	
# [Eq. 1.19] Operating strategy in the for decentralized heat supply: output heat in each month proportional to installed capacity (more realistic).
# Note that in Moret (2017), page 20, Eq. 1.19 is not correctly reported. In fact, if there are losses in the DHN, the concise formulation using the EndUses variable cannot be used, and should be replaced by the extended version here below.
# When solar thermal is installed, it replaces one technology which is chosen as backup. The sum of the % production of solar + backup must respect the minimum share of the backup technology
# Here written in a compact non linear form, below it is linearized  
# subject to op_strategy_decen_1 {i in TECHNOLOGIES_OF_END_USES_TYPE["HEAT_LOW_T_DECEN"] diff {"DEC_SOLAR"}, t in PERIODS}:
#	  F_Mult_t [i, t] + F_Mult_t ["DEC_SOLAR", t] * y_solar_backup [i] >= sum {t2 in PERIODS} (F_Mult_t [i, t2] * t_op [t2]) * ((end_uses_input["HEAT_LOW_T_HW"] / total_time + end_uses_input["HEAT_LOW_T_SH"] * heating_month [t] / t_op [t]) / (end_uses_input["HEAT_LOW_T_HW"] + end_uses_input["HEAT_LOW_T_SH"]));

# Linearization of Eq. 1.19
# Auxiliary variable 
var X_Solar_Backup_Aux {TECHNOLOGIES_OF_END_USES_TYPE["HEAT_LOW_T_DECEN"] diff {"DEC_SOLAR"}, t in PERIODS} >= 0;

subject to op_strategy_decen_1_linear {i in TECHNOLOGIES_OF_END_USES_TYPE["HEAT_LOW_T_DECEN"] diff {"DEC_SOLAR"}, t in PERIODS}:
	F_Mult_t [i, t] + X_Solar_Backup_Aux [i, t] >= sum {t2 in PERIODS} (F_Mult_t [i, t2] * t_op [t2]) * ((end_uses_input["HEAT_LOW_T_HW"] / total_time + end_uses_input["HEAT_LOW_T_SH"] * heating_month [t] / t_op [t]) / (end_uses_input["HEAT_LOW_T_HW"] + end_uses_input["HEAT_LOW_T_SH"]));

# These three constraints impose that: X_solar_backup_aux [i, t] = F_Mult_t ["DEC_SOLAR", t] * y_solar_backup [i]
# from: http://www.leandro-coelho.com/linearization-product-variables/
subject to op_strategy_decen_1_linear_1 {i in TECHNOLOGIES_OF_END_USES_TYPE["HEAT_LOW_T_DECEN"] diff {"DEC_SOLAR"}, t in PERIODS}:
	X_Solar_Backup_Aux [i, t] <= f_max ["DEC_SOLAR"] * Y_Solar_Backup [i];

subject to op_strategy_decen_1_linear_2 {i in TECHNOLOGIES_OF_END_USES_TYPE["HEAT_LOW_T_DECEN"] diff {"DEC_SOLAR"}, t in PERIODS}:
	X_Solar_Backup_Aux [i, t] <= F_Mult_t ["DEC_SOLAR", t];

subject to op_strategy_decen_1_linear_3 {i in TECHNOLOGIES_OF_END_USES_TYPE["HEAT_LOW_T_DECEN"] diff {"DEC_SOLAR"}, t in PERIODS}:
	X_Solar_Backup_Aux [i, t] >= F_Mult_t ["DEC_SOLAR", t] - (1 - Y_Solar_Backup [i]) * f_max ["DEC_SOLAR"];

# [Eq. 1.20] Only one technology can be backup of solar
subject to op_strategy_decen_2:
	sum {i in TECHNOLOGIES} Y_Solar_Backup [i] <= 1;


## Resources

# [Eq. 1.12] Resources availability equation
subject to resource_availability {i in RESOURCES}:
	sum {t in PERIODS} (F_Mult_t [i, t] * t_op [t]) <= avail [i];

## Storage

# [Eq. 1.15-1.16] Each storage technology can have input/output only to certain layers. If incompatible then the variable is set to 0
# 如果没有这个约束，即使该储能科技与某个layer不配，Storage_In很可能被赋予一个非0值
# ceil (x) operator rounds a number to the highest nearest integer. 
subject to storage_layer_in {i in STORAGE_TECH, l in LAYERS, t in PERIODS}:
	Storage_In [i, l, t] * (ceil (storage_eff_in [i, l]) - 1) = 0;

subject to storage_layer_out {i in STORAGE_TECH, l in LAYERS, t in PERIODS}:
	Storage_Out [i, l, t] * (ceil (storage_eff_out [i, l]) - 1) = 0;

# [Eq. 1.17] Storage can't be a transfer unit in a given period: either output or input.
# Note that in Moret (2017), page 20, Eq. 1.17 is not correctly reported (the "<= 1" term is missing)
# Nonlinear formulation would be as follows:
# subject to storage_no_transfer {i in STORAGE_TECH, t in PERIODS}:
# 	ceil (sum {l in LAYERS: storage_eff_in [i,l] > 0} (Storage_In [i, l, t] * storage_eff_in_mult [i, l])  * t_op [t] / f_max [i]) +
# 	ceil (sum {l in LAYERS: storage_eff_out [i,l] > 0} (Storage_Out [i, l, t] / storage_eff_out_mult [i, l])  * t_op [t] / f_max [i]) <= 1;
# Could be written in a linear way as follows (3 equations):

# Linearization of Eq. 1.17
var Y_Sto_In {STORAGE_TECH, PERIODS} binary;
var Y_Sto_Out {STORAGE_TECH, PERIODS} binary;


## LF: Modified version to athorize f_max=0. TOMO
subject to storage_no_transfer_1 {i in STORAGE_TECH, t in PERIODS}:
	(sum {l in LAYERS: storage_eff_in [i,l] > 0} (Storage_In [i, l, t] * storage_eff_in [i, l])) * t_op [t]  <= Y_Sto_In [i, t] * f_max[i];
	
subject to storage_no_transfer_2 {i in STORAGE_TECH, t in PERIODS}:
	(sum {l in LAYERS: storage_eff_out [i,l] > 0} (Storage_Out [i, l, t] / storage_eff_out [i, l])) * t_op [t]  <= Y_Sto_Out [i, t] * f_max[i];

subject to storage_no_transfer_3 {i in STORAGE_TECH, t in PERIODS}:
	Y_Sto_In [i,t] + Y_Sto_Out [i,t] <= 1;
/*
subject to storage_no_transfer_1b {i in STORAGE_TECH, t in PERIODS: f_max[i] > 0}:
    (sum {l in LAYERS: storage_eff_in[i,l] > 0} (Storage_In[i, l, t] * storage_eff_in[i, l])) * t_op[t] / f_max[i] <= Y_Sto_In[i, t];

subject to storage_no_transfer_2b {i in STORAGE_TECH, t in PERIODS: f_max[i] > 0}:
	(sum {l in LAYERS: storage_eff_out [i,l] > 0} (Storage_Out [i, l, t] / storage_eff_out [i, l])) * t_op [t] / f_max [i] <= Y_Sto_Out [i, t];

*/


# [Eq. 1.14] The level of the storage represents the amount of energy stored at a certain time.
subject to storage_level {i in STORAGE_TECH, t in PERIODS}:
	F_Mult_t [i, t] = (if t == 1 then
	 			F_Mult_t [i, card(PERIODS)] + ((sum {l in LAYERS: storage_eff_in [i,l] > 0} (Storage_In [i, l, t] * storage_eff_in [i, l])) 
					- (sum {l in LAYERS: storage_eff_out [i,l] > 0} (Storage_Out [i, l, t] / storage_eff_out [i, l]))) * t_op [t]
	else
	 			F_Mult_t [i, t-1] + ((sum {l in LAYERS: storage_eff_in [i,l] > 0} (Storage_In [i, l, t] * storage_eff_in [i, l])) 
					- (sum {l in LAYERS: storage_eff_out [i,l] > 0} (Storage_Out [i, l, t] / storage_eff_out [i, l]))) * t_op [t]);
								
## [Eq. 1.18] Calculation of losses for each end-use demand type (normally for electricity and DHN)
subject to network_losses {i in END_USES_TYPES, t in PERIODS}:
	Losses [i,t] = (sum {j in RESOURCES union TECHNOLOGIES diff STORAGE_TECH: layers_in_out [j, i] > 0} ((layers_in_out[j, i]) * F_Mult_t [j, t])) * loss_coeff [i];

## Additional constraints: Constraints needed for the application to Switzerland (not needed in standard MILP formulation)

# [Eq 1.22] Definition of min/max output of each technology as % of total output in a given layer. 
# Normally for a tech should use either f_max/f_min or f_max_%/f_min_%
subject to f_max_perc {i in END_USES_TYPES, j in TECHNOLOGIES_OF_END_USES_TYPE[i]}:
	sum {t in PERIODS} (F_Mult_t [j, t] * t_op[t]) <= fmax_perc [j] * sum {j2 in TECHNOLOGIES_OF_END_USES_TYPE[i], t2 in PERIODS} (F_Mult_t [j2, t2] * t_op [t2]);

subject to f_min_perc {i in END_USES_TYPES, j in TECHNOLOGIES_OF_END_USES_TYPE[i]}:
	sum {t in PERIODS} (F_Mult_t [j, t] * t_op[t])  >= fmin_perc [j] * sum {j2 in TECHNOLOGIES_OF_END_USES_TYPE[i], t2 in PERIODS} (F_Mult_t [j2, t2] * t_op [t2]);

# [Eq ] Definition of min/max output of each technology as % of total output in a given layer. 
# Normally for a tech should use either f_max/f_min or f_max_%/f_min_%
subject to f_max_perc_mob {i in MOBILITY_TYPE, j in TECHNOLOGIES_OF_MOB_TYPE[i]}:
	sum {t in PERIODS} (F_Mult_t [j, t] * t_op[t]) <= fmax_perc_mob [j] * sum {j2 in TECHNOLOGIES_OF_MOB_TYPE[i], t2 in PERIODS} (F_Mult_t [j2, t2] * t_op [t2]);

subject to f_min_perc_mob {i in MOBILITY_TYPE, j in TECHNOLOGIES_OF_MOB_TYPE[i]}:
	sum {t in PERIODS} (F_Mult_t [j, t] * t_op[t])  >= fmin_perc_mob [j] * sum {j2 in TECHNOLOGIES_OF_MOB_TYPE[i], t2 in PERIODS} (F_Mult_t [j2, t2] * t_op [t2]);

## [Eq. 1.24] Seasonal storage in hydro dams.
# When installed power of new dams 0 -> 0.44, maximum storage capacity changes linearly 0 -> 2400 GWh/y
subject to storage_level_hydro_dams: 
	F_Mult ["HYDRO_STORAGE"]*(f_max ["NEW_HYDRO_DAM"] - f_min ["NEW_HYDRO_DAM"]) <= f_min ["HYDRO_STORAGE"] + (f_max ["HYDRO_STORAGE"] - f_min ["HYDRO_STORAGE"]) * (F_Mult ["NEW_HYDRO_DAM"] - f_min ["NEW_HYDRO_DAM"]);

# [Eq. 1.25] Hydro dams can only shift production. Efficiency is 1, "storage" is actually only avoided production shifted to different months
subject to hydro_dams_shift {t in PERIODS}: 
	Storage_In ["HYDRO_STORAGE", "ELECTRICITY_EHV", t] <= (F_Mult_t ["HYDRO_DAM", t] + F_Mult_t ["NEW_HYDRO_DAM", t]);

## TOMO HERE maybe?
## Tax constraints
#----------------------
# LF: Modification all road technologies
#subject to mobility_tax {tec in TECHNOLOGIES_OF_END_USES_TYPE["MOB_PUBLIC_ROAD_SD"] union TECHNOLOGIES_OF_END_USES_TYPE["MOB_PUBLIC_ROAD_MD"] union TECHNOLOGIES_OF_END_USES_TYPE["MOB_PUBLIC_ROAD_LD"] union TECHNOLOGIES_OF_END_USES_TYPE["MOB_PUBLIC_ROAD_ELD"] 
#	union TECHNOLOGIES_OF_END_USES_TYPE["MOB_PRIVATE_ROAD_SD"] union TECHNOLOGIES_OF_END_USES_TYPE["MOB_PRIVATE_ROAD_MD"] union TECHNOLOGIES_OF_END_USES_TYPE["MOB_PRIVATE_ROAD_LD"] union TECHNOLOGIES_OF_END_USES_TYPE["MOB_PRIVATE_ROAD_ELD"]
#	union TECHNOLOGIES_OF_END_USES_TYPE["MOB_FREIGHT_ROAD_SD"] union TECHNOLOGIES_OF_END_USES_TYPE["MOB_FREIGHT_ROAD_MD"] union TECHNOLOGIES_OF_END_USES_TYPE["MOB_FREIGHT_ROAD_LD"] union TECHNOLOGIES_OF_END_USES_TYPE["MOB_FREIGHT_ROAD_ELD"], t in PERIODS}: # XL: should have truck also . XL ok assuming no NG in mobility 
#	C_tax_tech[tec,t] = sum{res in FOSSIL_FUELS}(-F_Mult_t[tec,t]*layers_in_out[tec,res]*c_tax[res])*t_op[t];


/*
## LF: Commented the tax section because does not applies to QC.

## JS: Adding all road technologies
#subject to mobility_tax {tec in TECHNOLOGIES_OF_END_USES_TYPE["MOB_PRIVATE_LONGD"] union TECHNOLOGIES_OF_END_USES_TYPE["MOB_PUBLIC_LOCAL"] union TECHNOLOGIES_OF_END_USES_TYPE["MOB_PRIVATE_LOCAL"] union TECHNOLOGIES_OF_END_USES_TYPE["MOB_PUBLIC_LONGD"] union TECHNOLOGIES_OF_END_USES_TYPE["MOB_FREIGHT_ROAD"], t in PERIODS}: # XL: should have truck also . XL ok assuming no NG in mobility 
#	C_tax_tech[tec,t] = sum{res in FOSSIL_FUELS}(-F_Mult_t[tec,t]*layers_in_out[tec,res]*c_tax[res])*t_op[t];

#subject to heating_tax {tec in TECHNOLOGIES_OF_END_USES_TYPE["HEAT_LOW_T_DECEN"] union TECHNOLOGIES_OF_END_USES_TYPE["HEAT_LOW_T_DHN"] , t in PERIODS}:
#	C_tax_tech[tec,t] = sum{l in {'CO2_A'}}(F_Mult_t[tec,t]*layers_in_out[tec,l]*c_tax[l]);
# modified by XL
set TECH_TAX_FREE within TECHNOLOGIES;
param share_ind_tax default 1; #dummy value 0.1, representing ratio of industry + DHN (bio exc.) that pay tax , not in ETS
subject to heating_tax1 {tec in TECHNOLOGIES_OF_END_USES_TYPE["HEAT_HIGH_T"] union TECHNOLOGIES_OF_END_USES_TYPE["HEAT_LOW_T_DHN"] diff TECH_TAX_FREE, t in PERIODS}:
	C_tax_tech[tec,t] = share_ind_tax * sum{l in {'CO2_A'}}(F_Mult_t[tec,t]*layers_in_out[tec,l]*c_tax[l]*t_op[t])/1000;
subject to heating_tax2 {tec in TECHNOLOGIES_OF_END_USES_TYPE["HEAT_LOW_T_DECEN"] diff {"DEC_BOILER_WOOD"}, t in PERIODS}:
	C_tax_tech[tec,t] = sum{l in {'CO2_E'}}(F_Mult_t[tec,t]*layers_in_out[tec,l]*c_tax[l]*t_op[t])/1000;


# ---added by XL : should adpat since bio-capture should be excluded ?
# JS: I would keep it like that, as the modelling of the tax is almost impossible and this is the best assumption I see
subject to tax_reduction_cc{t in PERIODS}:
	CC_tax_reduction[t] = F_Mult_t['CARBON_CAPTURE',t]*layers_in_out['CARBON_CAPTURE','CO2_C']*c_tax_co2*t_op[t]/1000;
# ---
 
subject to import_tax {res in FOSSIL_FUELS, t in PERIODS}:
	C_tax_res[res,t] = F_Mult_t[res,t]*t_op[t]*c_tax_import[res];

*/

## [Eq. 1.26] DHN: assigning a cost to the network
# Note that in Moret (2017), page 26, there is a ">=" sign instead of an "=". The two formulations are equivalent as long as the problem minimises cost and the DHN has a cost > 0
subject to extra_dhn:
	F_Mult ["DHN"] = sum {j in TECHNOLOGIES_OF_END_USES_TYPE["HEAT_LOW_T_DHN"] diff {"DHN_RENOVATION"}} (F_Mult [j]);

# [Eq. 1.27] Calculation of max heat demand in DHN 
var Max_Heat_Demand_DHN >= 0;

subject to max_dhn_heat_demand {t in PERIODS}:
	Max_Heat_Demand_DHN >= End_Uses ["HEAT_LOW_T_DHN", t];

# Peak in DHN
subject to peak_dhn:
	sum {j in TECHNOLOGIES_OF_END_USES_TYPE["HEAT_LOW_T_DHN"]} (F_Mult [j]) >= peak_dhn_factor * Max_Heat_Demand_DHN;

# [Eq. 1.28] 9.4 BCHF is the extra investment needed if there is a big deployment of stochastic renewables
# Note that in Moret (2017), page 26, Eq. 1.28 is not correctly reported (the "1 +" term is missing).
# Also, in Moret (2017) there is a ">=" sign instead of an "=". The two formulations are equivalent as long as the problem minimises cost and the grid has a cost > 0
#subject to extra_grid:
#	F_Mult ["GRID"] = 1 + (9400 / c_inv["GRID"]) * (F_Mult ["WIND"] + F_Mult ["PV"]) / (f_max ["WIND"] + f_max ["PV"]);



# LF: Adaptation to CAN sets
# [Eq. 1.23] Operating strategy in private mobility (to make model more realistic)
# Mobility share is fixed as constant in the different months. This constraint is needed only if c_inv = 0 for mobility.
subject to op_strategy_mob_private {i in TECHNOLOGIES_OF_END_USES_CATEGORY["MOBILITY_PASSENGER_SD"] union TECHNOLOGIES_OF_END_USES_CATEGORY["MOBILITY_PASSENGER_MD"]
									 union TECHNOLOGIES_OF_END_USES_CATEGORY["MOBILITY_PASSENGER_LD"] union TECHNOLOGIES_OF_END_USES_CATEGORY["MOBILITY_PASSENGER_ELD"]
									 union TECHNOLOGIES_OF_END_USES_CATEGORY["MOBILITY_FREIGHT_SD"] union TECHNOLOGIES_OF_END_USES_CATEGORY["MOBILITY_FREIGHT_MD"]
									 union TECHNOLOGIES_OF_END_USES_CATEGORY["MOBILITY_FREIGHT_LD"] union TECHNOLOGIES_OF_END_USES_CATEGORY["MOBILITY_FREIGHT_ELD"] , t in PERIODS}:
	F_Mult_t [i, t]  >= sum {t2 in PERIODS} (F_Mult_t [i, t2] * t_op [t2] / total_time);

# MS: apply c_p of mobility technologies to their models, to avoid free dispatch of total Annual_Prod among models
subject to capacity_factor_mob_models_private {i in TECHNOLOGIES_OF_PRIVATEMOB_ALL_DISTANCES, j in MODELS_OF_TECHNOLOGIES_OF_PRIVATEMOB_ALL_DISTANCES [i]}:
	sum {t in PERIODS} (F_Mult_t [j, t] * t_op [t]) <= F_Mult [j] * c_p [i] * total_time;

subject to capacity_factor_mob_models_public {i in TECHNOLOGIES_OF_PUBLICMOB_ALL_DISTANCES, j in MODELS_OF_TECHNOLOGIES_OF_PUBLICMOB_ALL_DISTANCES [i]}:
	sum {t in PERIODS} (F_Mult_t [j, t] * t_op [t]) <= F_Mult [j] * c_p [i] * total_time;

subject to capacity_factor_mob_models_freight {i in TECHNOLOGIES_OF_FREIGHTMOB_ALL_DISTANCES, j in MODELS_OF_TECHNOLOGIES_OF_FREIGHTMOB_ALL_DISTANCES [i]}:
	sum {t in PERIODS} (F_Mult_t [j, t] * t_op [t]) <= F_Mult [j] * c_p [i] * total_time;


## [Eq. 1.23] Operating strategy in private mobility (to make model more realistic)
## Mobility share is fixed as constant in the different months. This constraint is needed only if c_inv = 0 for mobility.
#subject to op_strategy_mob_private {i in TECHNOLOGIES_OF_END_USES_CATEGORY["MOBILITY_PASSENGER_LONGD"] union TECHNOLOGIES_OF_END_USES_CATEGORY["MOBILITY_PASSENGER_LOCAL"] union TECHNOLOGIES_OF_END_USES_CATEGORY["MOBILITY_FREIGHT"], t in PERIODS}:
#	F_Mult_t [i, t]  >= sum {t2 in PERIODS} (F_Mult_t [i, t2] * t_op [t2] / total_time);

subject to privatemob_use_pertech1 {j in TECHNOLOGIES_OF_PRIVATEMOB_ALL_DISTANCES, t in PERIODS}: # connexion local/longd
	F_Mult_t [j,t] = sum {i in MODELS_OF_TECHNOLOGIES_OF_PRIVATEMOB_ALL_DISTANCES [j]} F_Mult_t [i,t];	

subject to freightmob_use_pertech1 {j in TECHNOLOGIES_OF_FREIGHTMOB_ALL_DISTANCES, t in PERIODS}: # connexion local/longd
	F_Mult_t [j,t] = sum {i in MODELS_OF_TECHNOLOGIES_OF_FREIGHTMOB_ALL_DISTANCES [j]} F_Mult_t [i,t];	

subject to publicmob_use_pertech1 {j in TECHNOLOGIES_OF_PUBLICMOB_ALL_DISTANCES, t in PERIODS}: # connexion local/longd
	F_Mult_t [j,t] = sum {i in MODELS_OF_TECHNOLOGIES_OF_PUBLICMOB_ALL_DISTANCES [j]} F_Mult_t [i,t];

subject to privatemob_installed_pertech1 {j in TECHNOLOGIES_OF_PRIVATEMOB_ALL_DISTANCES}: # connexion local/longd
	F_Mult [j] = sum {i in MODELS_OF_TECHNOLOGIES_OF_PRIVATEMOB_ALL_DISTANCES [j]} F_Mult [i];

subject to freightmob_installed_pertech1 {j in TECHNOLOGIES_OF_FREIGHTMOB_ALL_DISTANCES}: # connexion local/longd
	F_Mult [j] = sum {i in MODELS_OF_TECHNOLOGIES_OF_FREIGHTMOB_ALL_DISTANCES [j]} F_Mult [i];

subject to publicmob_installed_pertech1 {j in TECHNOLOGIES_OF_PUBLICMOB_ALL_DISTANCES}: # connexion local/longd
	F_Mult [j] = sum {i in MODELS_OF_TECHNOLOGIES_OF_PUBLICMOB_ALL_DISTANCES [j]} F_Mult [i];


## Grid calculations
# The grid size corresponds to the maximum of each period power
#subject to extra_ehv1 {l in ELECTRICITY_LAYERS, g in GRIDS_OF_LAYERS[l]}:
#	F_Mult [g] = sum {j in TECHNOLOGIES_OF_END_USES_TYPE[l]} (F_Mult [j]);
# Force connection of decentralized techs to grid at each Period t
#subject to extra_ehv2 {t in PERIODS, l in ELECTRICITY_LAYERS, g in GRIDS_OF_LAYERS[l]}:
#	F_Mult_t [g,t] = sum {j in TECHNOLOGIES_OF_END_USES_TYPE[l]} (F_Mult_t [j,t]);
/*
subject to extra_ehv1 {l in ELECTRICITY_LAYERS, g in GRIDS_OF_LAYERS[l]}:
	F_Mult [g] = sum {j in TECHNOLOGIES_OF_END_USES_TYPE[l]} (F_Mult [j]);
# Force connection of decentralized techs to grid at each Period t
subject to extra_ehv2 {t in PERIODS, l in ELECTRICITY_LAYERS, g in GRIDS_OF_LAYERS[l]}:
	F_Mult_t [g,t] = sum {j in TECHNOLOGIES_OF_END_USES_TYPE[l]} (F_Mult_t [j,t]);
*/
subject to grid_power1 {t in PERIODS, g in GRIDS}:
	F_Mult [g] >= F_Mult_t [g,t];
subject to grid_power2  {t in PERIODS, l in (ELECTRICITY_LAYERS union H2_LAYERS union NG_LAYERS), g in GRIDS_OF_LAYERS[l]}:
	#F_Mult_t [g,t] * n_stations[g] >= sum {j in TECHNOLOGIES diff STORAGE_TECH: layers_in_out[j,l]>0} (F_Mult_t [j,t]*layers_in_out[j,l]) + F_Mult_t [l,t];
	F_Mult_t [g,t] >= sum {j in TECHNOLOGIES diff STORAGE_TECH: layers_in_out[j,l]>0} (F_Mult_t [j,t]*layers_in_out[j,l]) + F_Mult_t [l,t];


#subject to grid_power1 {t in PERIODS, l in (ELECTRICITY_LAYERS union H2_LAYERS union NG_LAYERS), g in GRIDS_OF_LAYERS[l]}:
#	F_Mult_t [g,t] >= sum {j in TECHNOLOGIES diff STORAGE_TECH : layers_in_out[j,l]>0} (F_Mult_t [j,t]*layers_in_out[j,l]);
#subject to grid_power2  {t in PERIODS, l in (ELECTRICITY_LAYERS union H2_LAYERS union NG_LAYERS), g in GRIDS_OF_LAYERS[l]}:
#	F_Mult [g] >= F_Mult_t[g,t];

# Renewable penetration
subject to renw_penetratino:
	sum{i in RENEW, t in PERIODS} F_Mult_t[i,t] * t_op[t] >= renew * sum{ii in RESOURCES diff BIO_PRODUCT, tt in PERIODS} F_Mult_t[ii,tt] * t_op[tt];
/*
## Waste priority and uniformed over the whole year! X.Li
subject to waste_priority1{t in PERIODS}:
	F_Mult_t["WASTE_BIO",t]=avail["WASTE_BIO"]/total_time;
subject to waste_priority2{t in PERIODS}:
	F_Mult_t["WASTE_FOS",t]=avail["WASTE_FOS"]/total_time;
subject to waste_priority3{t in PERIODS}:
	F_Mult_t["WASTE",t]=avail["WASTE"]/total_time;
*/
/*
## Add the emission of CEMENT
subject to cement_emission{t in PERIODS}:
	F_Mult_t["CEMENT",t]=1;
*/
## Cost

# [Eq. 1.3] Investment cost of each technology
subject to investment_cost_calc_1 {i in TECHNOLOGIES diff {"DHN_RENOVATION","DEC_RENOVATION"} diff GRIDS}:
	C_inv [i] = c_inv [i] * F_Mult [i];
subject to investment_cost_calc_3:
	C_inv["DHN_RENOVATION"] = c_inv["DHN_RENOVATION"] * sum{t in PERIODS} (F_Mult_t["DHN_RENOVATION",t]*t_op[t]); #MCHF/GWh
subject to investment_cost_calc_4 {i in GRIDS}:
	C_inv [i] = (F_Mult[i] - f_grid_ext[i]) * c_inv [i] * l_grid_ext[i] * k_security[i] / n_stations[i] + C_inv_grid_help [i];	
subject to op_strategy_renovation {t in PERIODS}:
	F_Mult_t ["DHN_RENOVATION", t]  >= sum {t2 in PERIODS} (F_Mult_t ["DHN_RENOVATION", t2] * t_op [t2] / total_time);
subject to investment_cost_calc_5:
	C_inv["DEC_RENOVATION"] = c_inv["DEC_RENOVATION"] * sum{t in PERIODS} (F_Mult_t["DEC_RENOVATION",t]*t_op[t]); #MCHF/GWh
subject to op_strategy_renovation_2 {t in PERIODS}:
	F_Mult_t ["DEC_RENOVATION", t]  >= sum {t2 in PERIODS} (F_Mult_t ["DEC_RENOVATION", t2] * t_op [t2] / total_time);
	
# [Eq. 1.4] O&M cost of each technology
subject to main_cost_calc {i in TECHNOLOGIES}: # add storage investment
	C_maint [i] = c_maint [i] * F_Mult [i];		

# [Eq. 1.10] Total cost of each resource
subject to op_cost_calc {i in RESOURCES}:
	C_op [i] = sum {t in PERIODS} (c_op [i,t] * F_Mult_t [i, t] * t_op [t]);

# XL 
#var excise>=0;
#var co2_levy>=0;
#var mob_compensation>=0;
#subject to co2_heating_tax:# without exclusion of CC
#	co2_levy =sum {tec in TECHNOLOGIES_OF_END_USES_TYPE["HEAT_HIGH_T"] union TECHNOLOGIES_OF_END_USES_TYPE["HEAT_LOW_T_DECEN"] union TECHNOLOGIES_OF_END_USES_TYPE["HEAT_LOW_T_DHN"] diff TECH_TAX_FREE, t in PERIODS} C_tax_tech[tec,t]
#				 - sum {tech in COGEN diff TECH_TAX_FREE, tt in PERIODS, elec in ELECTRICITY_LAYERS} C_tax_tech[tech,tt] * layers_in_out[tech,elec]/(1+layers_in_out[tech,elec]);				 
#subject to co2_compensation:# without exclusion of CC
#	mob_compensation = sum {tec in TECHNOLOGIES_OF_END_USES_TYPE["MOB_PRIVATE_ROAD_SD"] union TECHNOLOGIES_OF_END_USES_TYPE["MOB_PRIVATE_ROAD_MD"] union TECHNOLOGIES_OF_END_USES_TYPE["MOB_PRIVATE_ROAD_LD"] union TECHNOLOGIES_OF_END_USES_TYPE["MOB_PRIVATE_ROAD_ELD"], t in PERIODS} C_tax_tech[tec,t];
#subject to excise_tax: 
#	excise =sum {res in RESOURCES, t in PERIODS} C_tax_res[res,t]; 


# [Eq. 1.1]	
subject to totalcost_cal:
	TotalCost = sum {i in TECHNOLOGIES} (tau [i] * C_inv [i] + C_maint [i]) + sum {j in RESOURCES} C_op [j]
	#+ excise
	#+ co2_levy
	#+ mob_compensation # XL: mob_compensation not included
	#- sum{t in PERIODS} CC_tax_reduction[t] # XL 
	;
## Emissions



# [Eq. 1.5]
subject to gwp_constr_calc {i in TECHNOLOGIES}:
	GWP_constr [i] = gwp_constr [i] * F_Mult [i]/lifetime[i];

# Only for saving data
subject to production{i in TECHNOLOGIES diff STORAGE_TECH, t in PERIODS}:
	Monthly_Prod[i,t]=F_Mult_t[i,t]*t_op[t];

subject to production2{i in TECHNOLOGIES diff STORAGE_TECH}:
	Annual_Prod[i]=sum{t in PERIODS} Monthly_Prod[i,t];

subject to res_import{r in RESOURCES}:
	Annual_Res[r] = sum{t in PERIODS} F_Mult_t[r,t]*t_op[t];
	
# [Eq.xl.1] in fact a storage technology corresponds to only one layer, and efficiency considered 
subject to storage{i in STORAGE_TECH, t in PERIODS}: 
	Monthly_Prod[i,t]=sum{l in LAYERS: storage_eff_out [i,l] > 0} (Storage_In[i,l,t] * storage_eff_in[i,l] - Storage_Out[i,l,t]/storage_eff_out[i,l]) * t_op[t];

subject to total_emission{t in PERIODS}:#kt
	Total_emission[t]=(GWP["CO2_A",t]+GWP["CO2_E",t])*t_op[t]; # do not consider the external gwp due to import
#   Total_emission[t]=(GWP["CO2_A",t]+GWP["CO2_E",t]+GWP["CO2_EE",t])*t_op[t];

/*
subject to co2_emission{t in PERIODS}:
	sum{tt in 1..t} Total_emission[tt] <= co2_limit;
*/

subject to co2_emission:
	sum{t in PERIODS} Total_emission[t] <= co2_limit;
subject to co2_emission2:
	sum{t in PERIODS} Total_emission[t] >= co2_limit_max;

subject to co2:
	TotalGWP = sum{t in PERIODS} Total_emission[t];

subject to sng_max{sng in SNG_LAYERS}:
	sum{i in TECHNOLOGIES diff STORAGE_TECH, t in PERIODS: layers_in_out[i,sng]>0} Monthly_Prod[i,t]*layers_in_out[i,sng]>=sng_min;
### enforcing full utilization of PV once installed
subject to pv_full_utilization{i in PV_TECH,t in PERIODS}:
	F_Mult_t[i,t] = F_Mult[i]*c_p_t[i,t];
/*
### enforcing full utilization of PV once installed
subject to pv_lv_full_utilization{t in PERIODS}:
	F_Mult_t["PV_LV",t] = F_Mult["PV_LV"]*c_p_t["PV_LV",t];
### enforcing full utilization of PV once installed
subject to pv_mv_full_utilization{t in PERIODS}:
	F_Mult_t["PV_MV",t] = F_Mult["PV_MV"]*c_p_t["PV_MV",t];
### enforcing full utilization of PV once installed
subject to pv_hv_full_utilization{t in PERIODS}:
	F_Mult_t["PV_HV",t] = F_Mult["PV_HV"]*c_p_t["PV_HV",t];
### enforcing full utilization of PV once installed
subject to pv_ehv_full_utilization{t in PERIODS}:
	F_Mult_t["PV_EHV",t] = F_Mult["PV_EHV"]*c_p_t["PV_EHV",t];
*/

#TOMO WIND
subject to solarthermal_full_utilization{t in PERIODS}:
	F_Mult_t["DEC_SOLAR",t] = F_Mult["DEC_SOLAR"]*c_p_t["DEC_SOLAR",t];

subject to wind_onshore_full_utilization{t in PERIODS}:
	F_Mult_t["WIND_ONSHORE",t] = F_Mult["WIND_ONSHORE"]*c_p_t["WIND_ONSHORE",t];
subject to wind_offshore_full_utilization{t in PERIODS}:
	F_Mult_t["WIND_OFFSHORE",t] = F_Mult["WIND_OFFSHORE"]*c_p_t["WIND_OFFSHORE",t];

# subject to hydro_dam_full_utilization{t in PERIODS}:
# 	F_Mult_t["HYDRO_DAM",t] = F_Mult["HYDRO_DAM"]*c_p_t["HYDRO_DAM",t];
subject to hydro_river_full_utilization{t in PERIODS}:
	F_Mult_t["HYDRO_RIVER",t] = F_Mult["HYDRO_RIVER"]*c_p_t["HYDRO_RIVER",t];


# Waste chp Once installed has to be fully used
/*
subject to waste_mode_1:
	F_Mult["IND_COGEN_WASTE_WIN"]>=0.5*(F_Mult["IND_COGEN_WASTE_WIN"]+F_Mult["IND_COGEN_WASTE_SUM"]);
subject to waste_mode_2:
	F_Mult["IND_COGEN_WASTE_SUM"]>=0.5*(F_Mult["IND_COGEN_WASTE_WIN"]+F_Mult["IND_COGEN_WASTE_SUM"]);
*/
# TRL choice
subject to trl_choice{i in TECHNOLOGIES: trl[i]>trl_max or trl[i]<trl_min}:
	F_Mult[i]=0;

subject to bio_peneration:
	#sum{t in PERIODS} (F_Mult_t["WOOD",t]+F_Mult_t["WET_BIOMASS",t]+F_Mult_t["PLANT",t])*t_op[t] >= bio_ratio*(avail["WOOD"]+avail["WET_BIOMASS"]+avail["PLANT"]);
	sum{t in PERIODS} (F_Mult_t["WOOD",t]+F_Mult_t["WET_BIOMASS",t])*t_op[t] >= bio_ratio*(avail["WOOD"]+avail["WET_BIOMASS"]);

# STORAGE
## NG_S level
subject to ng_storage{t in PERIODS: t > 1}:
	STO_NG_LEVEL[t]=STO_NG_LEVEL[t-1] + layers_in_out["NG_STO","NG_S"]*F_Mult_t["NG_STO",t]*t_op[t] + layers_in_out["STO_NG","NG_S"]*F_Mult_t["STO_NG",t]*t_op[t];
subject to ng_balance:
	STO_NG_LEVEL[1]=STO_NG_LEVEL[12] + layers_in_out["NG_STO","NG_S"]*F_Mult_t["NG_STO",1]*t_op[1] + layers_in_out["STO_NG","NG_S"]*F_Mult_t["STO_NG",1]*t_op[1];


var STO_IN{PERIODS} binary;
var STO_OUT{PERIODS} binary;

var HELP_STO{PERIODS}>=0;
var HELP_STO_OUT{PERIODS}>=0;

subject to bi_choice{t in PERIODS}:
	STO_IN[t]+STO_OUT[t]<=1;
## binary constraint
#subject to in_chocie{t in PERIODS}:
#	F_Mult_t["NG_STO",t]<=F_Mult["NG_STO"]*STO_IN[t];

## linerization
subject to in_chocie{t in PERIODS}:
	F_Mult_t["NG_STO",t]<=HELP_STO[t];
subject to aux_1{t in PERIODS}:
	HELP_STO [t] <= f_max ["NG_STO"] * STO_IN[t];
subject to aux_2{t in PERIODS}:
	HELP_STO [t] <= F_Mult_t ["NG_STO", t];
subject to aux_3{t in PERIODS}:
	HELP_STO [t] >= F_Mult_t ["NG_STO", t] - (1 - STO_IN [t]) * f_max ["NG_STO"];

subject to out_chocie{t in PERIODS}:
	F_Mult_t["STO_NG",t]<=HELP_STO_OUT[t];
subject to aux_1_out{t in PERIODS}:
	HELP_STO_OUT [t] <= f_max ["STO_NG"] * STO_OUT[t];
subject to aux_2_out{t in PERIODS}:
	HELP_STO_OUT [t] <= F_Mult_t ["STO_NG", t];
subject to aux_3_out{t in PERIODS}:
	HELP_STO_OUT [t] >= F_Mult_t ["STO_NG", t] - (1 - STO_OUT [t]) * f_max ["STO_NG"];

## CO2 Storage
subject to co2_storage{t in PERIODS: t > 1}:
	STO_CO2_LEVEL[t]=STO_CO2_LEVEL[t-1] + layers_in_out["CO2_STO","CO2_CS"]*F_Mult_t["CO2_STO",t]*t_op[t] + layers_in_out["STO_CO2","CO2_CS"]*F_Mult_t["STO_CO2",t]*t_op[t];
subject to co2_balance:
	STO_CO2_LEVEL[1]=STO_CO2_LEVEL[12] + layers_in_out["CO2_STO","CO2_CS"]*F_Mult_t["CO2_STO",1]*t_op[1] + layers_in_out["STO_CO2","CO2_CS"]*F_Mult_t["STO_CO2",1]*t_op[1];


var STO_IN_CO2{PERIODS} binary;
var STO_OUT_CO2{PERIODS} binary;

var HELP_STO_CO2{PERIODS}>=0;
var HELP_STO_OUT_CO2{PERIODS}>=0;

subject to bi_choice_co2{t in PERIODS}:
	STO_IN_CO2[t]+STO_OUT_CO2[t]<=1;

## linerization
subject to in_chocie_co2{t in PERIODS}:
	F_Mult_t["CO2_STO",t]<=HELP_STO_CO2[t];
subject to aux_1_co2{t in PERIODS}:
	HELP_STO_CO2 [t] <= f_max ["CO2_STO"] * STO_IN_CO2[t];
subject to aux_2_co2{t in PERIODS}:
	HELP_STO_CO2 [t] <= F_Mult_t ["CO2_STO", t];
subject to aux_3_co2{t in PERIODS}:
	HELP_STO_CO2 [t] >= F_Mult_t ["CO2_STO", t] - (1 - STO_IN_CO2 [t]) * f_max ["CO2_STO"];

subject to out_chocie_co2{t in PERIODS}:
	F_Mult_t["STO_CO2",t]<=HELP_STO_OUT_CO2[t];
subject to aux_1_out_co2{t in PERIODS}:
	HELP_STO_OUT_CO2[t] <= f_max ["STO_CO2"] * STO_OUT_CO2[t];
subject to aux_2_out_co2{t in PERIODS}:
	HELP_STO_OUT_CO2[t] <= F_Mult_t ["STO_CO2", t];
subject to aux_3_out_co2{t in PERIODS}:
	HELP_STO_OUT_CO2 [t] >= F_Mult_t ["STO_CO2", t] - (1 - STO_OUT_CO2 [t]) * f_max ["STO_CO2"];

## H2 Storage
subject to h2_storage{t in PERIODS: t > 1}:
	STO_H2_LEVEL[t]=STO_H2_LEVEL[t-1] + layers_in_out["H2_STO","H2_S"]*F_Mult_t["H2_STO",t]*t_op[t] + layers_in_out["STO_H2","H2_S"]*F_Mult_t["STO_H2",t]*t_op[t];
subject to h2_balance:
	STO_H2_LEVEL[1]=STO_H2_LEVEL[12] + layers_in_out["H2_STO","H2_S"]*F_Mult_t["H2_STO",1]*t_op[1] + layers_in_out["STO_H2","H2_S"]*F_Mult_t["STO_H2",1]*t_op[1];


var STO_IN_H2{PERIODS} binary;
var STO_OUT_H2{PERIODS} binary;

var HELP_STO_H2{PERIODS}>=0;
var HELP_STO_OUT_H2{PERIODS}>=0;

subject to bi_choice_h2{t in PERIODS}:
	STO_IN_H2[t]+STO_OUT_H2[t]<=1;

## linerization
subject to in_chocie_h2{t in PERIODS}:
	F_Mult_t["H2_STO",t]<=HELP_STO_H2[t];
subject to aux_1_h2{t in PERIODS}:
	HELP_STO_H2 [t] <= f_max ["H2_STO"] * STO_IN_H2[t];
subject to aux_2_h2{t in PERIODS}:
	HELP_STO_H2 [t] <= F_Mult_t ["H2_STO", t];
subject to aux_3_h2{t in PERIODS}:
	HELP_STO_H2 [t] >= F_Mult_t ["H2_STO", t] - (1 - STO_IN_H2 [t]) * f_max ["H2_STO"];

subject to out_chocie_h2{t in PERIODS}:
	F_Mult_t["STO_H2",t]<=HELP_STO_OUT_H2[t];
subject to aux_1_out_h2{t in PERIODS}:
	HELP_STO_OUT_H2[t] <= f_max ["STO_H2"] * STO_OUT_H2[t];
subject to aux_2_out_h2{t in PERIODS}:
	HELP_STO_OUT_H2[t] <= F_Mult_t ["STO_H2", t];
subject to aux_3_out_h2{t in PERIODS}:
	HELP_STO_OUT_H2 [t] >= F_Mult_t ["STO_H2", t] - (1 - STO_OUT_H2 [t]) * f_max ["STO_H2"];


## ELEC Storage

var STO_ELEC_LEVEL{PERIODS} >=0, <=0; # seasonal hydro storage

subject to capacity_factor_Sto_elec{i in {"ELEC_STO"}, t in PERIODS}:
	STO_ELEC_LEVEL[t] <= F_Mult[i];
subject to elec_storage{t in PERIODS: t > 1}:
	STO_ELEC_LEVEL[t]=STO_ELEC_LEVEL[t-1] + layers_in_out["ELEC_STO","ELEC_S"]*F_Mult_t["ELEC_STO",t]*t_op[t] + layers_in_out["STO_ELEC","ELEC_S"]*F_Mult_t["STO_ELEC",t]*t_op[t];
subject to elec_balance:
	STO_ELEC_LEVEL[1]=STO_ELEC_LEVEL[12] + layers_in_out["ELEC_STO","ELEC_S"]*F_Mult_t["ELEC_STO",1]*t_op[1] + layers_in_out["STO_ELEC","ELEC_S"]*F_Mult_t["STO_ELEC",1]*t_op[1];


var STO_IN_ELEC{PERIODS} binary;
var STO_OUT_ELEC{PERIODS} binary;

var HELP_STO_ELEC{PERIODS}>=0;
var HELP_STO_OUT_ELEC{PERIODS}>=0;

subject to bi_choice_elec{t in PERIODS}:
	STO_IN_ELEC[t]+STO_OUT_ELEC[t]<=1;

## linerization
subject to in_chocie_elec{t in PERIODS}:
	F_Mult_t["ELEC_STO",t]<=HELP_STO_ELEC[t];
subject to aux_1_elec{t in PERIODS}:
	HELP_STO_ELEC [t] <= f_max ["ELEC_STO"] * STO_IN_ELEC[t];
subject to aux_2_elec{t in PERIODS}:
	HELP_STO_ELEC [t] <= F_Mult_t ["ELEC_STO", t];
subject to aux_3_elec{t in PERIODS}:
	HELP_STO_ELEC [t] >= F_Mult_t ["ELEC_STO", t] - (1 - STO_IN_ELEC [t]) * f_max ["ELEC_STO"];

subject to out_chocie_elec{t in PERIODS}:
	F_Mult_t["STO_ELEC",t]<=HELP_STO_OUT_ELEC[t];
subject to aux_1_out_elec{t in PERIODS}:
	HELP_STO_OUT_ELEC[t] <= f_max ["STO_ELEC"] * STO_OUT_ELEC[t];
subject to aux_2_out_elec{t in PERIODS}:
	HELP_STO_OUT_ELEC[t] <= F_Mult_t ["STO_ELEC", t];
subject to aux_3_out_elec{t in PERIODS}:
	HELP_STO_OUT_ELEC [t] >= F_Mult_t ["STO_ELEC", t] - (1 - STO_OUT_ELEC [t]) * f_max ["STO_ELEC"];

# [Eq. 1.25] Hydro dams can only shift production. Efficiency is 1, "storage" is actually only avoided production shifted to different months
subject to hydro_dams_shift3 {t in PERIODS}: 
	F_Mult_t ["ELEC_STO", t] <= (F_Mult_t ["HYDRO_DAM", t] + F_Mult_t ["NEW_HYDRO_DAM", t]);



## DIE Storage

var STO_DIE_LEVEL{PERIODS} >=0, <=1000000; 

subject to capacity_factor_Sto_DIE{i in {"DIE_STO"}, t in PERIODS}:
	STO_DIE_LEVEL[t] <= F_Mult[i];
subject to DIE_storage{t in PERIODS: t > 1}:
	STO_DIE_LEVEL[t]=STO_DIE_LEVEL[t-1] + layers_in_out["DIE_STO","DIESEL_S"]*F_Mult_t["DIE_STO",t]*t_op[t] + layers_in_out["STO_DIE","DIESEL_S"]*F_Mult_t["STO_DIE",t]*t_op[t];
subject to DIE_balance:
	STO_DIE_LEVEL[1]=STO_DIE_LEVEL[12] + layers_in_out["DIE_STO","DIESEL_S"]*F_Mult_t["DIE_STO",1]*t_op[1] + layers_in_out["STO_DIE","DIESEL_S"]*F_Mult_t["STO_DIE",1]*t_op[1];


var STO_IN_DIE{PERIODS} binary;
var STO_OUT_DIE{PERIODS} binary;

var HELP_STO_DIE{PERIODS}>=0;
var HELP_STO_OUT_DIE{PERIODS}>=0;

subject to bi_choice_DIE{t in PERIODS}:
	STO_IN_DIE[t]+STO_OUT_DIE[t]<=1;

## linerization
subject to in_chocie_DIE{t in PERIODS}:
	F_Mult_t["DIE_STO",t]<=HELP_STO_DIE[t];
subject to aux_1_DIE{t in PERIODS}:
	HELP_STO_DIE [t] <= f_max ["DIE_STO"] * STO_IN_DIE[t];
subject to aux_2_DIE{t in PERIODS}:
	HELP_STO_DIE [t] <= F_Mult_t ["DIE_STO", t];
subject to aux_3_DIE{t in PERIODS}:
	HELP_STO_DIE [t] >= F_Mult_t ["DIE_STO", t] - (1 - STO_IN_DIE [t]) * f_max ["DIE_STO"];

subject to out_chocie_DIE{t in PERIODS}:
	F_Mult_t["STO_DIE",t]<=HELP_STO_OUT_DIE[t];
subject to aux_1_out_DIE{t in PERIODS}:
	HELP_STO_OUT_DIE[t] <= f_max ["STO_DIE"] * STO_OUT_DIE[t];
subject to aux_2_out_DIE{t in PERIODS}:
	HELP_STO_OUT_DIE[t] <= F_Mult_t ["STO_DIE", t];
subject to aux_3_out_DIE{t in PERIODS}:
	HELP_STO_OUT_DIE [t] >= F_Mult_t ["STO_DIE", t] - (1 - STO_OUT_DIE [t]) * f_max ["STO_DIE"];


## GASO Storage

var STO_GASO_LEVEL{PERIODS} >=0, <=100000;

subject to capacity_factor_Sto_GASO{i in {"GASO_STO"}, t in PERIODS}:
	STO_GASO_LEVEL[t] <= F_Mult[i];
subject to GASO_storage{t in PERIODS: t > 1}:
	STO_GASO_LEVEL[t]=STO_GASO_LEVEL[t-1] + layers_in_out["GASO_STO","GASOLINE_S"]*F_Mult_t["GASO_STO",t]*t_op[t] + layers_in_out["STO_GASO","GASOLINE_S"]*F_Mult_t["STO_GASO",t]*t_op[t];
subject to GASO_balance:
	STO_GASO_LEVEL[1]=STO_GASO_LEVEL[12] + layers_in_out["GASO_STO","GASOLINE_S"]*F_Mult_t["GASO_STO",1]*t_op[1] + layers_in_out["STO_GASO","GASOLINE_S"]*F_Mult_t["STO_GASO",1]*t_op[1];


var STO_IN_GASO{PERIODS} binary;
var STO_OUT_GASO{PERIODS} binary;

var HELP_STO_GASO{PERIODS}>=0;
var HELP_STO_OUT_GASO{PERIODS}>=0;

subject to bi_choice_GASO{t in PERIODS}:
	STO_IN_GASO[t]+STO_OUT_GASO[t]<=1;

## linerization
subject to in_chocie_GASO{t in PERIODS}:
	F_Mult_t["GASO_STO",t]<=HELP_STO_GASO[t];
subject to aux_1_GASO{t in PERIODS}:
	HELP_STO_GASO [t] <= f_max ["GASO_STO"] * STO_IN_GASO[t];
subject to aux_2_GASO{t in PERIODS}:
	HELP_STO_GASO [t] <= F_Mult_t ["GASO_STO", t];
subject to aux_3_GASO{t in PERIODS}:
	HELP_STO_GASO [t] >= F_Mult_t ["GASO_STO", t] - (1 - STO_IN_GASO [t]) * f_max ["GASO_STO"];

subject to out_chocie_GASO{t in PERIODS}:
	F_Mult_t["STO_GASO",t]<=HELP_STO_OUT_GASO[t];
subject to aux_1_out_GASO{t in PERIODS}:
	HELP_STO_OUT_GASO[t] <= f_max ["STO_GASO"] * STO_OUT_GASO[t];
subject to aux_2_out_GASO{t in PERIODS}:
	HELP_STO_OUT_GASO[t] <= F_Mult_t ["STO_GASO", t];
subject to aux_3_out_GASO{t in PERIODS}:
	HELP_STO_OUT_GASO [t] >= F_Mult_t ["STO_GASO", t] - (1 - STO_OUT_GASO [t]) * f_max ["STO_GASO"];


param out_max {TECHNOLOGIES} >= 0 default Infinity; # Maximum feasible output [GWh], refers to main output. storage level [GWh] for STORAGE_TECH
param out_min {TECHNOLOGIES} >= 0 default 0; # Maximum feasible installed capacity [GWh], refers to main output. storage level [GWh] for STORAGE_TECH
subject to prod_max{i in TECHNOLOGIES diff STORAGE_TECH}:
	Annual_Prod[i]<=out_max[i];
subject to prod_min{i in TECHNOLOGIES diff STORAGE_TECH}:
	Annual_Prod[i]>=out_min[i];


# ccu constraint
subject to ccu{t in PERIODS}:
	sum{i in TECHNOLOGIES diff STORAGE_TECH diff TECHNOLOGIES_OF_CCS diff {"CO2_STO"}: layers_in_out[i,"CO2_C"]<0} -Annual_Prod[i]*layers_in_out[i,"CO2_C"] >= STO_CO2_LEVEL[t];

## Renovation limit
param reno_share_max >=0, <=1, default 0.5;
param reno_share_min >=0, <=1, default 0;
param reno_max >=0, default 10000;
param reno_min >=0, default 0; #0
/*
subject to renovation_max:
	Annual_Prod["DHN_RENOVATION"] + Annual_Prod["DEC_RENOVATION"]<=reno_share_max*sum{s in SECTORS}(end_uses_demand_year["HEAT_LOW_T_SH",s] + end_uses_demand_year["HEAT_LOW_T_HW",s]);
subject to renovation_min:
	Annual_Prod["DHN_RENOVATION"] + Annual_Prod["DEC_RENOVATION"]>=reno_share_min*sum{s in SECTORS}(end_uses_demand_year["HEAT_LOW_T_SH",s] + end_uses_demand_year["HEAT_LOW_T_HW",s]);
*/
subject to renovation_max:
	Annual_Prod["DHN_RENOVATION"] + Annual_Prod["DEC_RENOVATION"]<=reno_max;
subject to renovation_min:
	Annual_Prod["DHN_RENOVATION"] + Annual_Prod["DEC_RENOVATION"]>=reno_min;

# enforce utilization of cc once it is installed
/*
subject to cc_strategy{t in PERIODS}:
	F_Mult_t["CARBON_CAPTURE",t] = layers_in_out["CARBON_CAPTURE","CO2_C"] * sum{i in TECHNOLOGIES diff STORAGE_TECH diff TECHNOLOGIES_OF_CCUS: layers_in_out[i,"CO2_A"]>0} F_Mult_t[i,t]*layers_in_out[i,"CO2_A"];  
*/
# param fossil_vec_share_min default 0; # in private passenger mobility
# param fossil_vec_share_max default 1;
# 
# subject to fuel_vehicle_min:
# 	sum{i in {"CAR_GASOLINE","CAR_DIESEL","SUV_DIESEL"}}Annual_Prod[i] >= fossil_vec_share_min * sum{ii in TECHNOLOGIES_OF_END_USES_TYPE["MOB_PRIVATE_ROAD_SD"] union TECHNOLOGIES_OF_END_USES_TYPE["MOB_PRIVATE_ROAD_MD"] union TECHNOLOGIES_OF_END_USES_TYPE["MOB_PRIVATE_ROAD_LD"] union TECHNOLOGIES_OF_END_USES_TYPE["MOB_PRIVATE_ROAD_ELD"]}Annual_Prod[ii];
# subject to fuel_vehicle_max:
# 	sum{i in {"CAR_GASOLINE","CAR_DIESEL","SUV_DIESEL"}}Annual_Prod[i] <= fossil_vec_share_max * sum{ii in TECHNOLOGIES_OF_END_USES_TYPE["MOB_PRIVATE_ROAD_SD"] union TECHNOLOGIES_OF_END_USES_TYPE["MOB_PRIVATE_ROAD_MD"] union TECHNOLOGIES_OF_END_USES_TYPE["MOB_PRIVATE_ROAD_LD"] union TECHNOLOGIES_OF_END_USES_TYPE["MOB_PRIVATE_ROAD_ELD"]}Annual_Prod[ii];


#TODO adapto to distances
#param bus_share_min default 0; # in mobility passenger (including private and public) currently 3.3% https://www.bfs.admin.ch/bfs/en/home/statistics/mobility-transport/passenger-transport/performance.html
#param bus_share_max default 1;

subject to share_public_rail_sd_1:
	sum{i in TECHNOLOGIES_OF_MOB_TYPE["MOB_PUBLIC_RAIL_SD"]}Annual_Prod[i] >= share_public_rail_min_sd * sum{s in SECTORS}(end_uses_demand_year['MOBILITY_PASSENGER_SD',s])*Share_Mobility_Public_SD;
subject to share_public_rail_sd_2:
	sum{i in TECHNOLOGIES_OF_MOB_TYPE["MOB_PUBLIC_RAIL_SD"]}Annual_Prod[i] <= share_public_rail_max_sd * sum{s in SECTORS}(end_uses_demand_year['MOBILITY_PASSENGER_SD',s])*Share_Mobility_Public_SD;

subject to share_public_rail_md_1:
	sum{i in TECHNOLOGIES_OF_MOB_TYPE["MOB_PUBLIC_RAIL_MD"]}Annual_Prod[i] >= share_public_rail_min_md * sum{s in SECTORS}(end_uses_demand_year['MOBILITY_PASSENGER_MD',s])*Share_Mobility_Public_MD;
subject to share_public_rail_md_2:
	sum{i in TECHNOLOGIES_OF_MOB_TYPE["MOB_PUBLIC_RAIL_MD"]}Annual_Prod[i] <= share_public_rail_max_md * sum{s in SECTORS}(end_uses_demand_year['MOBILITY_PASSENGER_MD',s])*Share_Mobility_Public_MD;

subject to share_public_rail_ld_1:
	sum{i in TECHNOLOGIES_OF_MOB_TYPE["MOB_PUBLIC_RAIL_LD"]}Annual_Prod[i] >= share_public_rail_min_ld * sum{s in SECTORS}(end_uses_demand_year['MOBILITY_PASSENGER_LD',s])*Share_Mobility_Public_LD;
subject to share_public_rail_ld_2:
	sum{i in TECHNOLOGIES_OF_MOB_TYPE["MOB_PUBLIC_RAIL_LD"]}Annual_Prod[i] <= share_public_rail_max_ld * sum{s in SECTORS}(end_uses_demand_year['MOBILITY_PASSENGER_LD',s])*Share_Mobility_Public_LD;

subject to share_public_rail_eld_1:
	sum{i in TECHNOLOGIES_OF_MOB_TYPE["MOB_PUBLIC_RAIL_ELD"]}Annual_Prod[i] >= share_public_rail_min_eld * sum{s in SECTORS}(end_uses_demand_year['MOBILITY_PASSENGER_ELD',s])*Share_Mobility_Public_ELD;
subject to share_public_rail_eld_2:
	sum{i in TECHNOLOGIES_OF_MOB_TYPE["MOB_PUBLIC_RAIL_ELD"]}Annual_Prod[i] <= share_public_rail_max_eld * sum{s in SECTORS}(end_uses_demand_year['MOBILITY_PASSENGER_ELD',s])*Share_Mobility_Public_ELD;



subject to share_public_air_ld_1:
	sum{i in TECHNOLOGIES_OF_MOB_TYPE["MOB_PUBLIC_AIR_LD"]}Annual_Prod[i] >= share_public_air_min_ld * sum{s in SECTORS}(end_uses_demand_year['MOBILITY_PASSENGER_LD',s])*Share_Mobility_Public_LD;
subject to share_public_air_ld_2:
	sum{i in TECHNOLOGIES_OF_MOB_TYPE["MOB_PUBLIC_AIR_LD"]}Annual_Prod[i] <= share_public_air_max_ld * sum{s in SECTORS}(end_uses_demand_year['MOBILITY_PASSENGER_LD',s])*Share_Mobility_Public_LD;

subject to share_public_air_eld_1:
	sum{i in TECHNOLOGIES_OF_MOB_TYPE["MOB_PUBLIC_AIR_ELD"]}Annual_Prod[i] >= share_public_air_min_eld * sum{s in SECTORS}(end_uses_demand_year['MOBILITY_PASSENGER_ELD',s])*Share_Mobility_Public_ELD;
subject to share_public_air_eld_2:
	sum{i in TECHNOLOGIES_OF_MOB_TYPE["MOB_PUBLIC_AIR_ELD"]}Annual_Prod[i] <= share_public_air_max_eld * sum{s in SECTORS}(end_uses_demand_year['MOBILITY_PASSENGER_ELD',s])*Share_Mobility_Public_ELD;
subject to share_freight_rail_ld_1:
	sum{i in TECHNOLOGIES_OF_MOB_TYPE["MOB_FREIGHT_RAIL_LD"]}Annual_Prod[i] >= share_freight_rail_min_ld * sum{s in SECTORS}(end_uses_demand_year['MOBILITY_FREIGHT_LD',s]);
subject to share_freight_rail_ld_2:
	sum{i in TECHNOLOGIES_OF_MOB_TYPE["MOB_FREIGHT_RAIL_LD"]}Annual_Prod[i] <= share_freight_rail_max_ld * sum{s in SECTORS}(end_uses_demand_year['MOBILITY_FREIGHT_LD',s]);

subject to share_freight_rail_eld_1:
	sum{i in TECHNOLOGIES_OF_MOB_TYPE["MOB_FREIGHT_RAIL_ELD"]}Annual_Prod[i] >= share_freight_rail_min_eld * sum{s in SECTORS}(end_uses_demand_year['MOBILITY_FREIGHT_ELD',s]);
subject to share_freight_rail_eld_2:
	sum{i in TECHNOLOGIES_OF_MOB_TYPE["MOB_FREIGHT_RAIL_ELD"]}Annual_Prod[i] <= share_freight_rail_max_eld * sum{s in SECTORS}(end_uses_demand_year['MOBILITY_FREIGHT_ELD',s]);

subject to share_freight_air_eld_1:
	sum{i in TECHNOLOGIES_OF_MOB_TYPE["MOB_FREIGHT_AIR_ELD"]}Annual_Prod[i] >= share_freight_air_min_eld * sum{s in SECTORS}(end_uses_demand_year['MOBILITY_FREIGHT_ELD',s]);
subject to share_freight_air_eld_2:
	sum{i in TECHNOLOGIES_OF_MOB_TYPE["MOB_FREIGHT_AIR_ELD"]}Annual_Prod[i] <= share_freight_air_max_eld * sum{s in SECTORS}(end_uses_demand_year['MOBILITY_FREIGHT_ELD',s]);

subject to share_freight_maritime_eld_1:
	sum{i in TECHNOLOGIES_OF_MOB_TYPE["MOB_FREIGHT_MARITIME_ELD"]}Annual_Prod[i] >= share_freight_maritime_min_eld * sum{s in SECTORS}(end_uses_demand_year['MOBILITY_FREIGHT_ELD',s]);
subject to share_freight_maritime_eld_2:
	sum{i in TECHNOLOGIES_OF_MOB_TYPE["MOB_FREIGHT_MARITIME_ELD"]}Annual_Prod[i] <= share_freight_maritime_max_eld * sum{s in SECTORS}(end_uses_demand_year['MOBILITY_FREIGHT_ELD',s]);

subject to f_min_perc_container:
    sum{t in PERIODS, j in MODELS_OF_TECHNOLOGIES_MARITIME_CONTAINER} (F_Mult_t[j, t] * t_op[t]) >=
    share_freight_maritime_container * sum{j in TECHNOLOGIES_OF_MOB_TYPE["MOB_FREIGHT_MARITIME_ELD"], t in PERIODS} (F_Mult_t[j, t] * t_op[t]);

subject to f_min_perc_bulk_carrier:
    sum{t in PERIODS, j in MODELS_OF_TECHNOLOGIES_MARITIME_BULK_CARRIER} (F_Mult_t[j, t] * t_op[t]) >=
    share_freight_maritime_bulk_carrier * sum{j in TECHNOLOGIES_OF_MOB_TYPE["MOB_FREIGHT_MARITIME_ELD"], t in PERIODS} (F_Mult_t[j, t] * t_op[t]);

subject to f_min_perc_oil_tanker:
    sum{t in PERIODS, j in MODELS_OF_TECHNOLOGIES_MARITIME_OIL_TANKER} (F_Mult_t[j, t] * t_op[t]) >=
    share_freight_maritime_oil_tanker * sum{j in TECHNOLOGIES_OF_MOB_TYPE["MOB_FREIGHT_MARITIME_ELD"], t in PERIODS} (F_Mult_t[j, t] * t_op[t]);

subject to share_public_schoolbus_sd_1:
	sum{i in SCHOOLBUSES}Annual_Prod[i] >= share_public_schoolbus_min_sd * sum{s in SECTORS}(end_uses_demand_year['MOBILITY_PASSENGER_SD',s])*Share_Mobility_Public_SD;
subject to share_public_schoolbus_sd_2:
	sum{i in SCHOOLBUSES}Annual_Prod[i] <= share_public_schoolbus_max_sd * sum{s in SECTORS}(end_uses_demand_year['MOBILITY_PASSENGER_SD',s])*Share_Mobility_Public_SD;
	
var Share_Public_Schoolbus_SD >= share_public_schoolbus_min_sd, <= share_public_schoolbus_max_sd;
subject to share_public_schoolbus_sd_3:
	Share_Public_Schoolbus_SD = sum{i in SCHOOLBUSES}Annual_Prod[i] / (sum{s in SECTORS}(end_uses_demand_year['MOBILITY_PASSENGER_SD',s])*Share_Mobility_Public_SD);

/*
param truck_share_min default 0.2;
param truck_share_max default 0.5;

subject to fuel_truck_min:
	sum{i in {"TRUCK","TRUCK_SNG"}}Annual_Prod[i] >= truck_share_min * end_uses_demand_year['MOBILITY_FREIGHT','TRANSPORTATION'];
subject to fuel_truck_max:
	sum{i in {"TRUCK","TRUCK_SNG"}}Annual_Prod[i] <= truck_share_max * end_uses_demand_year['MOBILITY_FREIGHT','TRANSPORTATION'];
*/

/*
subject to thermal_sto{t in PERIODS}:
	F_Mult_t["DEC_TH_STORAGE",t] <= F_Mult_t["DEC_SOLAR",t];
subject to thermal_sto2{t in PERIODS}:
	F_Mult_t["DHN_TH_STORAGE",t] = 0;
*/
#subject to battery:
#	F_Mult["BATTERY"]=0.2848*F_Mult["PV"]-3.5319;
