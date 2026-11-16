set MATERIALS;

# Distance variants (_SD/_MD/_LD/_ELD, Material_mob_family_exclusion.dat): excluded to avoid
# counting the material twice, since it is already carried by F_new of the "family" technology.
set MOB_VARIANT_TECHS within TECHNOLOGIES default {};
set MATERIAL_TECHS := TECHNOLOGIES diff MOB_VARIANT_TECHS;

# -----------------PARAMETERS------------------------------------------------------------------------------------------------

param material_intensity {YEARS,TECHNOLOGIES,MATERIALS} >= 0 default 0;       # [t/GW]
param limit_material_year {YEARS,MATERIALS} >= 0 default Infinity;#1000000000;            # [t/year]
param limit_material {MATERIALS} >= 0 default Infinity;#1000000000;                       # [t]

param recycling_rate {YEARS,TECHNOLOGIES,MATERIALS} >= 0, <= 1 default 0;     # [%] End-of-Life recycling rate (technical recovery ceiling)
param recycling_cost {TECHNOLOGIES,MATERIALS} >= 0 default 0;                 # [$/t]
param disposal_cost {MATERIALS} >= 0 default 0;                           # [$/t] generic estimate
param primary_material_cost {MATERIALS} >= 0 default 0;                       # [$/t] cost of the avoided virgin material if recycled

param force_recycling_max binary default 0;                                   # [-]

# Artificial penalty (not a real cost) on Material_stock, always active to 'force' the use of the recycled material.
# This cost has a negligible impact
param stocking_price >= 0 default 0;                                       # [$/t/year] artificial

param force_immediate_recycled_use binary default 1;                          # [-]

param K_relax >= 0 default 0;                  # [-] number of materials whose limits are relaxed
param M_relax {YEARS,MATERIALS} >= 0 default 1e9;   # [t] big M per (year, material): must exceed the possible excess of demand above the limit.
                                                    # A too large M makes the relaxation useless and lets the integrality tolerance (1e-5) relax 1e-5*M t with Relax_material at "0":
                                                    # Material_bigM.dat (run_build_bigM.py) provides a tight M per (year, material)
var Relax_material {MATERIALS} binary;         # 1 = limits of the material relaxed

# -----------------VARIABLES------------------------------------------------------------------------------------------------

var Material_content_year {YEARS,TECHNOLOGIES,MATERIALS} >= 0;    # [t/year]
var Material_content {TECHNOLOGIES,MATERIALS} >= 0;               # [t] cumulated over the horizon

var Decommissioned_material {YEARS,TECHNOLOGIES,MATERIALS} >= 0;  # [t/year] decommissioned material (mechanical)
var Recycled_material {YEARS,TECHNOLOGIES,MATERIALS} >= 0;        # [t/year] recycled material (decision, <= ceiling)
var Disposed_material {YEARS,TECHNOLOGIES,MATERIALS} >= 0;        # [t/year] landfilled/incinerated material
var Recycling_benefit {YEARS,TECHNOLOGIES,MATERIALS};             # [M$/year, discounted] cost avoided by recycling
var C_material >= 0;                                              # [M$, discounted] cost of the materials, added to the transition cost (see total_cost_transition_materials)

var Material_stock {YEARS,MATERIALS} >= 0;                          # [t] cumulated since the beginning of the horizon (when recycling > gross demand)
var Used_recycled_material {YEARS_WND diff YEAR_ONE,MATERIALS} >= 0; # [t/year] recycled material (of this year + stock) actually used against the gross demand of this year

#-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
# Hooks for Constraints_recycling_technologies.mod (approach with recycling technologies), loaded before the data.
param recycled_material_process_total_ub {TECHNOLOGIES,MATERIALS} >= 0 default 0;  # raised to Infinity (utils.py) when active
var Recycled_material_process_total {y in YEARS, tec in TECHNOLOGIES, mat in MATERIALS} >= 0, <= recycled_material_process_total_ub[tec,mat];  # [t/year]
var C_material_recycling_tech;                                            # [M$, discounted] -- no >=0 bound, a process can be net beneficial
fix C_material_recycling_tech := 0;  # default when Constraints_recycling_technologies.mod is not loaded
#-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------

# ---------------------------GROSS MATERIAL DEMAND------------------------------------------------------------------------------------------------------------------------------------

subject to material_content_year_calc {p in PHASE_WND union PHASE_UP_TO union {"2015_2020"}, y in PHASE_STOP[p], tec in TECHNOLOGIES, mat in MATERIALS}:
    Material_content_year[y,tec,mat] = material_intensity[y,tec,mat] * F_new[p,tec] / 5; #Gross demand per year

subject to material_content_calc {tec in TECHNOLOGIES, mat in MATERIALS}:
    Material_content[tec,mat] = sum {y in YEARS_WND diff YEAR_ONE} Material_content_year[y,tec,mat] * 5;#Total gross demand

# ---------------------------DECOMMISSIONED MATERIAL------------------------------------------------------------------------------------------------------------------------------------

# Decommissioned material per year
subject to decommissioned_material_calc {p_decom in PHASE_WND union PHASE_UP_TO, y_decom in PHASE_STOP[p_decom], tec in MATERIAL_TECHS, mat in MATERIALS}:
    Decommissioned_material[y_decom,tec,mat] = 1/5 * (
        sum {p_built in PHASE_WND union PHASE_UP_TO union {"2015_2020"}, y_built in PHASE_STOP[p_built]}
            material_intensity[y_built,tec,mat] * F_decom[p_decom,p_built,tec]
        + sum {p_built in AGE[tec,p_decom] diff {"STILL_IN_USE"}, y_built in PHASE_STOP[p_built]}
            material_intensity[y_built,tec,mat] * F_old[p_decom,tec]
    );

# ---------------------------RECYCLED MATERIAL------------------------------------------------------------------------------------------------------------------------------------

# Computation of what is recycled
subject to recycled_material_max {y in YEARS_WND diff YEAR_ONE, tec in MATERIAL_TECHS, mat in MATERIALS}:
    Recycled_material[y,tec,mat] <= recycling_rate[y,tec,mat] * Decommissioned_material[y,tec,mat];

#Force the recycling to its maximum potential
subject to recycled_material_forced_max {y in YEARS_WND diff YEAR_ONE, tec in MATERIAL_TECHS, mat in MATERIALS}:
    force_recycling_max * Recycled_material[y,tec,mat]
    >= force_recycling_max * recycling_rate[y,tec,mat] * Decommissioned_material[y,tec,mat];

# ---------------------------DISPOSED MATERIAL------------------------------------------------------------------------------------------------------------------------------------

# Computation of what is disposed
subject to disposed_material_calc {y in YEARS_WND diff YEAR_ONE, tec in MATERIAL_TECHS, mat in MATERIALS}:
    Disposed_material[y,tec,mat] = Decommissioned_material[y,tec,mat] - Recycled_material[y,tec,mat] - Recycled_material_process_total[y,tec,mat];

# ---------------------------NET DEMAND / USED RECYCLED MATERIAL------------------------------------------------------------------------------------------------------------------------------------

# Net demand = gross demand - Used_recycled_material, capped (used_recycled_material_cap) at the gross demand: never negative, the excess is stocked (Material_stock) rather than counted negatively.
subject to material_content_year_limit {y in YEARS_WND diff YEAR_ONE, mat in MATERIALS}:
    sum {tec in MATERIAL_TECHS} Material_content_year[y,tec,mat] - Used_recycled_material[y,mat] <= limit_material_year[y,mat] + M_relax[y,mat] * Relax_material[mat];

subject to relax_budget:
    sum {mat in MATERIALS} Relax_material[mat] <= K_relax;

subject to used_recycled_material_cap {y in YEARS_WND diff YEAR_ONE, mat in MATERIALS}:
    Used_recycled_material[y,mat] <= sum {tec in MATERIAL_TECHS} Material_content_year[y,tec,mat];

# ---------------------------MATERIAL STOCK------------------------------------------------------------------------------------------------------------------------------------

# Computation of the material stock
subject to material_stock_calc {p in PHASE_WND union PHASE_UP_TO, y in PHASE_STOP[p] diff YEAR_ONE, mat in MATERIALS}:
    Material_stock[y,mat] = sum {p2 in PHASE_WND union PHASE_UP_TO, y2 in PHASE_STOP[p2] diff YEAR_ONE : ord(p2,PHASE) <= ord(p,PHASE)}
        (sum {tec in MATERIAL_TECHS} (Recycled_material[y2,tec,mat] + Recycled_material_process_total[y2,tec,mat]) - Used_recycled_material[y2,mat]);

param M_material_stock_force default 1e7;  # [t] # Big M (if force_immediate_recycled_use=1): each year, either the stock is 0 or the demand is covered.
var Recycled_material_binding {YEARS_WND diff YEAR_ONE, MATERIALS} binary;

subject to used_recycled_material_forced_stock_zero {y in YEARS_WND diff YEAR_ONE, mat in MATERIALS}:
    force_immediate_recycled_use * Material_stock[y,mat]
    <= M_material_stock_force * (1 - Recycled_material_binding[y,mat]);

subject to used_recycled_material_forced_demand_covered {y in YEARS_WND diff YEAR_ONE, mat in MATERIALS}:
    force_immediate_recycled_use * (sum {tec in MATERIAL_TECHS} Material_content_year[y,tec,mat] - Used_recycled_material[y,mat])
    <= M_material_stock_force * Recycled_material_binding[y,mat];

# ---------------------------CUMULATIVE AVAILABILITY LIMIT------------------------------------------------------------------------------------------------------------------------------------

# Maximum availability -- Used_recycled_material (not Recycled_material): only the material actually
subject to material_content_limit {mat in MATERIALS}:
    sum {tec in MATERIAL_TECHS} Material_content[tec,mat]
    - sum {y in YEARS_WND diff YEAR_ONE} Used_recycled_material[y,mat] * 5 <= limit_material[mat];

# ------------Equation for cost of recycling----------------------------------------------

# Computation of the recycling benefit
subject to recycling_benefit_calc {p in PHASE_WND union PHASE_UP_TO, y in PHASE_STOP[p] diff YEAR_ONE, tec in MATERIAL_TECHS, mat in MATERIALS}:
    Recycling_benefit[y,tec,mat] = actualisation_factor[p,y] * (primary_material_cost[mat] + disposal_cost[mat] - recycling_cost[tec,mat]) * Recycled_material[y,tec,mat] / 1e6;

drop total_cost_transition;  # PES_main.mod: without C_material
subject to total_cost_transition_materials:
    TotalTransitionCost = C_tot_capex + C_tot_opex + C_material;

subject to material_cost_calc:
    C_material = sum {p in PHASE_WND union PHASE_UP_TO, y in PHASE_STOP[p] diff YEAR_ONE, tec in MATERIAL_TECHS, mat in MATERIALS}
        actualisation_factor[p,y] *
        (recycling_cost[tec,mat] * Recycled_material[y,tec,mat]
         - primary_material_cost[mat] * Recycled_material[y,tec,mat]
         + disposal_cost[mat] * Disposed_material[y,tec,mat]) * 5 / 1e6
        + C_material_recycling_tech
        + sum {y in YEARS_WND diff YEAR_ONE, mat in MATERIALS} stocking_price * Material_stock[y,mat] * 5 / 1e6; # Forces the immediate use of the recycled material (see stocking_price above)
