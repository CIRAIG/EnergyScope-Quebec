"""
    PESMain

Julia/JuMP translation of the pathway model: `projects/pathway/model/PES_main.mod`, `PES_store_variables.mod`, `PES_scenarios.mod`
and `PES_obj_pathway.mod` (objective `obj`). It is added to the static model (`QC_es_main.jl`) through the extension point
`build_qc_model(db; extend! = add_pes!)`. Same variable and constraint names as in the `.mod` files, so that the number of
instances of each constraint can be compared with AMPL.

Scope: one optimization window per model (perfect foresight, or one window of the myopic mode). The window sets (`YEARS_WND`, `PHASE_WND`,
`YEARS_UP_TO`, `PHASE_UP_TO`, `YEAR_ONE`, `YEAR_ONE_NEXT`) are provided by `QCFiles` (`load_pathway`, `window_sets_text` or a `seq_<i>.dat` file).
"""
module PESMain

using JuMP
using ..AmplDat
using ..QCEsMain

export add_pes!, build_pathway_model, carry_over

"Sum of terms (`AffExpr`) without repeated `+`; returns 0 for an empty collection."
function asum(terms)
    e = AffExpr(0.0)
    for t in terms
        add_to_expression!(e, t)
    end
    e
end

const MOB_TYPES = ["MOB_PRIVATE_ROAD_SD", "MOB_PRIVATE_ROAD_MD", "MOB_PRIVATE_ROAD_LD", "MOB_PRIVATE_ROAD_ELD",
    "MOB_PUBLIC_RAIL_SD", "MOB_PUBLIC_RAIL_MD", "MOB_PUBLIC_RAIL_LD", "MOB_PUBLIC_RAIL_ELD", "MOB_FREIGHT_ROAD_SD",
    "MOB_FREIGHT_ROAD_MD", "MOB_FREIGHT_RAIL_LD", "MOB_FREIGHT_RAIL_ELD", "MOB_PUBLIC_ROAD_SD", "MOB_PUBLIC_ROAD_MD",
    "MOB_PUBLIC_ROAD_LD", "MOB_PUBLIC_ROAD_ELD", "MOB_FREIGHT_ROAD_LD", "MOB_FREIGHT_ROAD_ELD", "MOB_PUBLIC_AIR_LD",
    "MOB_PUBLIC_AIR_ELD", "MOB_FREIGHT_MARITIME_ELD", "MOB_FREIGHT_AIR_ELD"]               # PES_main.mod:321 and :331

"""
    add_pes!(c, db, S, v) -> NamedTuple

Adds the pathway variables and constraints to the static model, then sets the objective `obj` (transition cost).
"""
function add_pes!(c::Ctx, db::DataStore, S, v)
    m = c.m
    P(name) = par(db, name)
    iset = S.iset
    uni(args...) = unique!(vcat(args...))
    sset(name) = haskey(db.sets, name) ? strs(db.sets[name]) : String[]

    # --- sets (PES_main.mod:13-22) ---
    PHASE = sset("PHASE")                                          # ordered
    PW, PU = sset("PHASE_WND"), sset("PHASE_UP_TO")
    PWU = uni(PW, PU)                                              # PHASE_WND union PHASE_UP_TO
    PWU0 = uni(PW, PU, ["2015_2020"])                              # ... union {"2015_2020"}
    P0 = uni(PHASE, ["2015_2020"])                                 # PHASE union {"2015_2020"}
    ord = Dict(p => k for (k, p) in enumerate(PHASE))              # ord(p, PHASE)
    YEARS, YW, YU, YC, Y = S.YEARS, S.YEARS_WND, S.YEARS_UP_TO, S.YC, S.Y
    YEAR_ONE = S.YEAR_ONE
    YEAR_ONE_NEXT = sset("YEAR_ONE_NEXT")
    YEARS_no2015 = setdiff(YEARS, ["YEAR_2015"])
    TECH, RES, STO, GRIDS, PERIODS = S.TECHNOLOGIES, S.RESOURCES, S.STORAGE_TECH, S.GRIDS, S.PERIODS
    INFRA = sset("INFRASTRUCTURE")
    start_of(p) = iset("PHASE_START", p)
    stop_of(p) = iset("PHASE_STOP", p)
    age(i, p) = strs(get(get(db.isets, "AGE", Dict{Tuple,Vector{Any}}()), (i, p), Any[]))
    technos_of_type(euc) = iset("TECHNOLOGIES_OF_END_USES_TYPE", euc)
    types_of_cat(cats) = uni([iset("END_USES_TYPES_OF_CATEGORY", ct) for ct in cats]...)

    # --- parameters ---
    t_op, SDR, c_inv, c_maint, c_op = P("t_op"), P("SDR"), P("c_inv"), P("c_maint"), P("c_op")
    lifetime, i_hurdle = P("lifetime"), P("i_hurdle")
    t_phase, diff_2015 = P("t_phase")(), P("diff_2015_phase")
    l_grid_ext, k_security, n_stations = P("l_grid_ext"), P("k_security"), P("n_stations")
    years_active, decom_allowed, remaining_years = P("years_active"), P("decom_allowed"), P("remaining_years")
    max_inv_phase, max_share_cost_phase = P("max_inv_phase"), P("max_share_cost_phase")
    gwp_limit, ccs_limit = P("gwp_limit"), P("ccs_limit")
    max_cost_budget, max_co2_budget = P("max_cost_budget"), P("max_co2_budget")
    demand = P("end_uses_demand_year")
    eui(y, i) = sum(demand(y, i, s) for s in S.SECTORS)                                        # end_uses_input
    tau(y, i) = (h = i_hurdle(y, i); n = lifetime(y, i); h * (1 + h)^n / ((1 + h)^n - 1))
    af(p, y) = 1 / ((1 + SDR(y))^diff_2015(p))                                                 # actualisation_factor (:42)
    gridcost(i) = l_grid_ext(i) * k_security(i) / n_stations(i)                                # grid-specific factor

    # --- variables (PES_main.mod:49-68, :75, :80, :132, :172, :356-357) ---
    @variable(m, F_new[P0, TECH] >= 0)
    @variable(m, F_decom[PHASE, P0, TECH] >= 0)
    @variable(m, F_old[PHASE, TECH] >= 0)
    @variable(m, C_inv_phase[PHASE] >= 0)
    @variable(m, C_inv_phase_no_actu[PHASE] >= 0)
    @variable(m, C_inv_phase_tech[PHASE, TECH] >= 0)
    @variable(m, C_inv_phase_tech_no_actu[PHASE, TECH] >= 0)
    @variable(m, C_op_phase_tech[PHASE, TECH] >= 0)
    @variable(m, C_op_phase_tech_no_actu[PHASE, TECH] >= 0)
    @variable(m, C_op_phase_res[PHASE, RES] >= 0)
    @variable(m, C_op_phase_res_no_actu[PHASE, RES] >= 0)
    @variable(m, C_inv_return[TECH] >= 0)
    @variable(m, C_inv_return_phase[P0, TECH] >= 0)
    @variable(m, C_opex[YEARS] >= 0)
    @variable(m, C_tot_opex >= 0)
    @variable(m, C_tot_capex >= 0)
    @variable(m, TotalGWPTransition >= 0)
    @variable(m, Delta_change[PHASE, TECH] >= 0)
    @variable(m, Res[YEARS_no2015, RES] >= 0)
    @variable(m, Res_t[YEARS_no2015, RES, PERIODS] >= 0)
    @variable(m, F_used_year_start[YW, TECH] >= 0)
    @variable(m, C_inv_phase_CRF[PHASE] >= 0)
    @variable(m, TotalTransitionCost >= 0)
    @variable(m, TotalEmission)
    (; F_Mult, F_Mult_t, C_inv, C_maint, C_op, TotalGWP, Annual_Res) = v

    # ═══════════ Resources used (:76-91) ═══════════
    for y in Y, j in RES
        con!(c, "store_res", Res[y, j] - asum(F_Mult_t[y, j, t] * t_op(t) for t in PERIODS), :(==))
    end
    for y in Y, j in RES, t in PERIODS
        con!(c, "store_res_t", Res_t[y, j, t] - F_Mult_t[y, j, t] * t_op(t), :(==))
    end
    for y in YC, i in RES
        con!(c, "op_cost_calc2", C_op[y, i] - asum(c_op(y, i, t) * Res_t[y, i, t] for t in PERIODS), :(==))
    end
    for y in Y
        con!(c, "minimum_GWP_reduction", TotalGWP[y], :<=, gwp_limit(y))
    end

    # [Eq. 23] emissions of the transition (:94)
    con!(c, "totalGWPTransition_calculation",
         TotalGWPTransition - asum(t_phase / 2 * (TotalGWP[ys] + TotalGWP[ye])
                                   for p in PWU for ys in start_of(p) for ye in stop_of(p)), :(==))

    # ═══════════ Evolution of technologies between phases (:109-128) ═══════════
    for p in PW, ys in start_of(p), ye in stop_of(p), i in TECH                                   # [Eq. 08]
        con!(c, "phase_new_build",
             F_Mult[ye, i] - F_Mult[ys, i] - F_new[p, i] + F_old[p, i] +
             asum(F_decom[p, p2, i] for p2 in PWU0), :(==))
    end
    for pd in PHASE, pb in P0, i in TECH                                                          # [Eq. 09] conditional constraint
        # AMPL counts all combinations; the constraint only exists when the condition is true
        decom_allowed(pd, pb, i) == 0 ? con!(c, "define_f_decom_properly", F_decom[pd, pb, i], :(==)) : triv!(c, "define_f_decom_properly")
    end
    for t in TECH                                                                                 # [Eq. 11]
        con!(c, "F_new_initialisation", F_new["2015_2020", t] - F_Mult["YEAR_2020", t], :(==))
    end
    for i in TECH, p in PW, ag in age(i, p)                                                       # [Eq. 10]
        rhs = ag == "STILL_IN_USE" ? AffExpr(0.0) : F_new[ag, i] - asum(F_decom[p2, ag, i] for p2 in PWU)
        con!(c, "phase_out_assignement", F_old[p, i] - rhs, :(==))
    end
    for i in TECH, p in PWU0
        con!(c, "no_decom_if_no_built", F_new[p, i] - asum(F_decom[p2, p, i] for p2 in PWU), :>=)
    end

    # [Eq. 12] limit on the rate of change (:133-166)
    for p in PW, ys in setdiff(start_of(p), YEAR_ONE), j in TECH
        con!(c, "compute_F_used_year_start",
             F_used_year_start[ys, j] - asum(F_Mult_t[ys, j, t] * t_op(t) for t in PERIODS), :(==))
    end
    for p in PW, ys in start_of(p), ye in stop_of(p), j in TECH
        used_end = asum(F_Mult_t[ye, j, t] * t_op(t) for t in PERIODS)
        con!(c, "delta_change_definition", Delta_change[p, j] - F_used_year_start[ys, j] + used_end, :>=)
    end
    for p in PW, ys in start_of(p), ye in stop_of(p), j in TECH
        used_end = asum(F_Mult_t[ye, j, t] * t_op(t) for t in PERIODS)
        con!(c, "delta_change_definition_sym", Delta_change[p, j] - used_end + F_used_year_start[ys, j], :>=)
    end
    function limit_changes(name, cats, limit, rhs_terms)
        types = types_of_cat(cats)
        for p in PWU, ys in start_of(p), ye in stop_of(p)
            lhs = asum(Delta_change[p, j] for euc in types for j in technos_of_type(euc))
            con!(c, name, lhs, :<=, limit * sum(eui(ys, x) for x in rhs_terms))
        end
    end
    limit_changes("limit_changes_heat", ["HEAT_LOW_T"], P("limit_LT_renovation")(), ["HEAT_LOW_T_HW", "HEAT_LOW_T_SH"])
    limit_changes("limit_changes_heat_high", ["HEAT_HIGH_T"], P("limit_HT_renovation")(), ["HEAT_HIGH_T"])
    limit_changes("limit_changes_elec", ["ELECTRICITY_LV", "ELECTRICITY_MV", "ELECTRICITY_HV", "ELECTRICITY_EHV"],
                  P("limit_elec_renovation")(), ["ELECTRICITY_LV", "ELECTRICITY_MV", "ELECTRICITY_HV", "ELECTRICITY_EHV"])
    limit_changes("limit_changes_mob", ["MOBILITY_PASSENGER_SD", "MOBILITY_PASSENGER_MD", "MOBILITY_PASSENGER_LD", "MOBILITY_PASSENGER_ELD"],
                  P("limit_pass_mob_changes")(), ["MOBILITY_PASSENGER_SD", "MOBILITY_PASSENGER_MD", "MOBILITY_PASSENGER_LD", "MOBILITY_PASSENGER_ELD"])
    limit_changes("limit_changes_freight", ["MOBILITY_FREIGHT_SD", "MOBILITY_FREIGHT_MD", "MOBILITY_FREIGHT_LD", "MOBILITY_FREIGHT_ELD"],
                  P("limit_freight_changes")(), ["MOBILITY_FREIGHT_SD", "MOBILITY_FREIGHT_MD", "MOBILITY_FREIGHT_LD", "MOBILITY_FREIGHT_ELD"])

    # ═══════════ Investment costs per phase (:174-239) ═══════════
    con!(c, "total_capex", C_tot_capex - asum(C_inv_phase_CRF[p] for p in PWU0), :(==))             # [Eq. 17]
    noGRIDS = setdiff(TECH, GRIDS)
    for p in PWU0, ys in start_of(p), ye in stop_of(p)
        f = af(p, ys) + af(p, ye)
        con!(c, "investment_computation",                                                           # [Eq. 21]
             C_inv_phase[p] -
             asum(F_new[p, i] * f * (c_inv(ys, i) + c_inv(ye, i)) / 4 for i in noGRIDS) -
             asum(F_new[p, i] * f * (c_inv(ys, i) + c_inv(ye, i)) * gridcost(i) / 4 for i in GRIDS), :(==))
    end
    for p in PWU0, ys in start_of(p), ye in stop_of(p)
        con!(c, "investment_computation_no_actu",
             C_inv_phase_no_actu[p] -
             asum(F_new[p, i] * (c_inv(ys, i) + c_inv(ye, i)) / 2 for i in noGRIDS) -
             asum(F_new[p, i] * (c_inv(ys, i) + c_inv(ye, i)) * gridcost(i) / 2 for i in GRIDS), :(==))
    end
    for p in PWU0, ys in start_of(p), ye in stop_of(p)
        f = af(p, ys) + af(p, ye)
        e = AffExpr(0.0)
        for pi in PWU0, ysi in start_of(pi), yei in stop_of(pi)
            for i in noGRIDS
                ya = years_active(i, pi, p)
                ya > 0 && add_to_expression!(e, F_new[pi, i] * (tau(ysi, i) * f * (c_inv(ysi, i) + c_inv(yei, i)) * ya / 4))
            end
            for i in GRIDS
                ya = years_active(i, pi, p)
                ya > 0 && add_to_expression!(e, F_new[pi, i] * (tau(ysi, i) * f * (c_inv(ysi, i) + c_inv(yei, i)) * ya * gridcost(i) / 4))
            end
        end
        con!(c, "investment_computation_CRF", C_inv_phase_CRF[p] - e, :(==))
    end
    for p in PWU0, ys in start_of(p), ye in stop_of(p), i in TECH
        k = af(p, ys) + af(p, ye)
        coef = k * (c_inv(ys, i) + c_inv(ye, i)) / 4 * (i in GRIDS ? gridcost(i) : 1.0)
        con!(c, "investment_computation_tech", C_inv_phase_tech[p, i] - F_new[p, i] * coef, :(==))
    end
    for p in PWU0, ys in start_of(p), ye in stop_of(p), i in TECH
        coef = (c_inv(ys, i) + c_inv(ye, i)) / 2 * (i in GRIDS ? gridcost(i) : 1.0)
        con!(c, "investment_computation_tech_no_actu", C_inv_phase_tech_no_actu[p, i] - F_new[p, i] * coef, :(==))
    end
    for p in PWU0, i in noGRIDS, ys in start_of(p), ye in stop_of(p)                                # [Eq. 22]
        coef = remaining_years(i, p) / lifetime(ys, i) * (1 / ((1 + SDR(ys))^35)) * (c_inv(ys, i) + c_inv(ye, i)) / 2
        con!(c, "investment_return_phase_tech",
             C_inv_return_phase[p, i] - coef * (F_new[p, i] - asum(F_decom[p2, p, i] for p2 in PWU)), :(==))
    end
    for p in PWU0, i in GRIDS, ys in start_of(p), ye in stop_of(p)
        coef = remaining_years(i, p) / lifetime(ys, i) * (1 / ((1 + SDR(ys))^35)) * (c_inv(ys, i) + c_inv(ye, i)) / 2 * gridcost(i)
        con!(c, "investment_return_phase_tech_grid",
             C_inv_return_phase[p, i] - coef * (F_new[p, i] - asum(F_decom[p2, p, i] for p2 in PWU)), :(==))
    end
    for i in noGRIDS
        con!(c, "investment_return", C_inv_return[i] - asum(C_inv_return_phase[p, i] for p in PWU0), :(==))
    end
    for i in GRIDS
        con!(c, "investment_return_grid", C_inv_return[i] - asum(C_inv_return_phase[p, i] for p in PWU0), :(==))
    end

    # ═══════════ Operating costs (:242-263) ═══════════
    opex_terms = asum((C_opex[ys] + C_opex[ye]) / 2 * ((af(p, ys) + af(p, ye)) / 2)
                      for p in PWU for ys in start_of(p) for ye in stop_of(p))
    con!(c, "Opex_tot_cost_calculation", C_tot_opex - C_opex["YEAR_2020"] - t_phase * opex_terms, :(==))   # [Eq. 18]
    for y in uni(YW, YU)                                                                          # [Eq. 20]
        con!(c, "Opex_cost_calculation",
             C_opex[y] - asum(C_maint[y, j] for j in TECH) - asum(C_op[y, i] for i in RES), :(==))
    end
    for p in PWU, ys in start_of(p), ye in stop_of(p), i in TECH
        con!(c, "operation_computation_tech",
             C_op_phase_tech[p, i] - t_phase * ((C_maint[ys, i] + C_maint[ye, i]) / 2 * ((af(p, ys) + af(p, ye)) / 2)), :(==))
    end
    for p in PWU, ys in start_of(p), ye in stop_of(p), i in TECH
        con!(c, "operation_computation_tech_no_actu",
             C_op_phase_tech_no_actu[p, i] - t_phase * ((C_maint[ys, i] + C_maint[ye, i]) / 2), :(==))
    end
    for p in PWU, ys in start_of(p), ye in stop_of(p), i in RES
        con!(c, "operation_computation_res",
             C_op_phase_res[p, i] - t_phase * ((C_op[ys, i] + C_op[ye, i]) / 2 * ((af(p, ys) + af(p, ye)) / 2)), :(==))
    end
    for p in PWU, ys in start_of(p), ye in stop_of(p), i in RES
        con!(c, "operation_computation_res_no_actu",
             C_op_phase_res_no_actu[p, i] - t_phase * ((C_op[ys, i] + C_op[ye, i]) / 2), :(==))
    end

    # ═══════════ Phase limits (:266-276) ═══════════
    for p in uni(PW, ["2015_2020"])
        con!(c, "maxInvestment", C_inv_phase[p], :<=, max_inv_phase(p))
    end
    for p in PW
        total = asum(C_inv_phase_tech_no_actu[p2, i] for p2 in PWU for i in TECH)
        con!(c, "limit_cost_share_phase",
             asum(C_inv_phase_tech_no_actu[p, i] for i in TECH) - max_share_cost_phase() * total, :<=)
    end

    # ═══════════ Additional constraints (:285-352) ═══════════
    for (nm, a, b) in (("NG", "STO_NG", "NG_STO"), ("SNG", "STO_SNG", "SNG_STO"), ("H2", "STO_H2", "H2_STO"),
                       ("DIE", "STO_DIE", "DIE_STO"), ("GASO", "STO_GASO", "GASO_STO"), ("ELEC", "STO_ELEC", "ELEC_STO"),
                       ("CO2", "STO_CO2", "CO2_STO"))
        for y in uni(YU, YW)
            con!(c, "capacity_storage_equal_in_out_" * nm, F_Mult[y, a] - F_Mult[y, b], :(==))
        end
    end
    for y in setdiff(uni(YU, YW), ["YEAR_2020", "YEAR_2025"])
        con!(c, "elec_import", Annual_Res[y, "ELECTRICITY_EHV"], :(==), 33889.0)
    end
    mobtech = Set(tt for mt in MOB_TYPES for tt in iset("TECHNOLOGIES_OF_MOB_TYPE", mt))
    Tdist = [t for t in TECH if !(t in STO) && !(t in INFRA) && !(t in ("HYDRO_DAM", "HYDRO_RIVER")) && !(t in mobtech)]
    for p in PW, t in Tdist
        "STILL_IN_USE" in age(t, p) || continue
        lhs = asum(F_decom[p2, "2015_2020", t] for p2 in PWU if ord[p2] <= ord[p])
        card = count(p2 -> ord[p2] <= ord[p] && "STILL_IN_USE" in age(t, p2), PWU)
        con!(c, "distribution_init_general", lhs - card * 5 / lifetime("YEAR_2020", t) * F_new["2015_2020", t], :>=)
    end
    for p in PW, mt in MOB_TYPES, t in iset("TECHNOLOGIES_OF_MOB_TYPE", mt)
        "STILL_IN_USE" in age(t, p) || continue
        con!(c, "distribution_init", F_decom[p, "2015_2020", t] - 5 / lifetime("YEAR_2020", t) * F_new["2015_2020", t], :(==))
    end
    for (nm, tl, key) in (("private", S.PRIV, "MODELS_OF_TECHNOLOGIES_OF_PRIVATEMOB_ALL_DISTANCES"),
                          ("public", S.PUB, "MODELS_OF_TECHNOLOGIES_OF_PUBLICMOB_ALL_DISTANCES"),
                          ("freight", S.FRE, "MODELS_OF_TECHNOLOGIES_OF_FREIGHTMOB_ALL_DISTANCES"))
        for p in P0, j in tl
            con!(c, "fnew_base_" * nm, F_new[p, j] - asum(F_new[p, i] for i in iset(key, j)), :(==))
        end
        for p in PWU, pb in P0, j in tl
            con!(c, "decom_base_" * nm, F_decom[p, pb, j] - asum(F_decom[p, pb, i] for i in iset(key, j)), :(==))
        end
    end

    # ═══════════ Total cost and emissions (:364-373) ═══════════
    con!(c, "total_cost_transition", TotalTransitionCost - C_tot_capex - C_tot_opex, :(==))           # [Eq. 16]
    con!(c, "max_cost_transition", TotalTransitionCost, :<=, max_cost_budget())
    con!(c, "total_emissions", TotalEmission - asum(TotalGWP[y] for y in YW), :(==))
    con!(c, "max_co2_transition", TotalGWPTransition, :<=, max_co2_budget())

    # ═══════════ PES_store_variables.mod: variables carried between windows ═══════════
    @variable(m, F_up_to[YU, TECH] >= 0)
    @variable(m, F_new_up_to[uni(PU, ["2020_2025"]), TECH] >= 0)
    @variable(m, F_old_up_to[PU, TECH] >= 0)
    @variable(m, F_decom_up_to[PU, uni(PU, ["2015_2020", "2020_2025"]), TECH] >= 0)
    @variable(m, F_used_year_start_next[YEAR_ONE_NEXT, TECH] >= 0)
    @variable(m, Res_up_to[YU, RES] >= 0)
    @variable(m, Res_t_up_to[YU, RES, PERIODS] >= 0)
    for j in TECH, y in YU
        con!(c, "store_F_up_to", F_up_to[y, j] - F_Mult[y, j], :(==))
    end
    for p in uni(PU, ["2020_2025"]), j in TECH
        con!(c, "store_F_new_up_to", F_new_up_to[p, j] - F_new[p, j], :(==))
    end
    for p in PU, j in TECH
        con!(c, "store_F_old_up_to", F_old_up_to[p, j] - F_old[p, j], :(==))
    end
    for pd in PU, pb in uni(PU, ["2015_2020", "2020_2025"]), j in TECH
        con!(c, "store_F_decom_up_to", F_decom_up_to[pd, pb, j] - F_decom[pd, pb, j], :(==))
    end
    for y in YEAR_ONE_NEXT, j in TECH
        con!(c, "store_F_used_year_start_next", F_used_year_start_next[y, j] - F_used_year_start[y, j], :(==))
    end
    for j in RES, y in YU
        con!(c, "store_Res_up_to", Res_up_to[y, j] - Res[y, j], :(==))
    end
    for j in RES, y in YU, t in PERIODS
        con!(c, "store_Res_t_up_to", Res_t_up_to[y, j, t] - Res_t[y, j, t], :(==))
    end

    # ═══════════ PES_scenarios.mod ═══════════
    noINFRA = setdiff(TECH, INFRA)
    @variable(m, Number_Of_Units[YEARS, noINFRA] >= 0)
    ref_size = P("ref_size")
    for y in Y, i in noINFRA
        con!(c, "number_of_units", Number_Of_Units[y, i] - F_Mult[y, i] / ref_size(y, i), :(==))
    end
    for y in Y, t in ("TRAIN_FREIGHT_ELEC_LD", "TRAIN_FREIGHT_ELEC_ELD")
        con!(c, "no_electric_trains", F_Mult[y, t], :(==))
    end
    lio = P("layers_in_out")
    for y in Y
        e = AffExpr(0.0)
        for i in uni(RES, TECH)
            i in STO && continue
            x = lio(y, i, "CO2_C")
            x > 0 && for t in PERIODS
                add_to_expression!(e, F_Mult_t[y, i, t] * (abs(x) * t_op(t)))
            end
        end
        con!(c, "co2_captur_limit_1", e, :<=, ccs_limit(y))
    end

    # ═══════════ Objective (PES_obj_pathway.mod, active objective `obj`) ═══════════
    @objective(m, Min, TotalTransitionCost)

    # ═══════════ `fix` statements of the .dat files (e.g. fix F_new['2025_2030','WIND_ONSHORE'] := 0) ═══════════
    pes_vars = (; F_new, F_decom, F_old, C_inv_phase, C_inv_phase_no_actu, C_inv_phase_tech, C_inv_phase_tech_no_actu,
                C_op_phase_tech, C_op_phase_tech_no_actu, C_op_phase_res, C_op_phase_res_no_actu, C_inv_return,
                C_inv_return_phase, C_opex, C_tot_opex, C_tot_capex, TotalGWPTransition, Delta_change, Res, Res_t,
                F_used_year_start, C_inv_phase_CRF, TotalTransitionCost, TotalEmission, F_up_to, F_new_up_to, F_old_up_to,
                F_decom_up_to, F_used_year_start_next, Res_up_to, Res_t_up_to, Number_Of_Units)
    allvars = merge(v, pes_vars)
    for f in db.fixes
        hasproperty(allvars, Symbol(f.var)) || error("fix: variable '$(f.var)' unknown to the model")
        fix(getproperty(allvars, Symbol(f.var))[f.key...], Float64(f.value); force=true)
    end
    pes_vars
end

"Complete pathway model (static model + PES_*), for one window (the only one in perfect foresight)."
build_pathway_model(db::DataStore) = build_qc_model(db; extend! = add_pes!)

"""
    carry_over(M, db) -> Vector

Myopic mode: values of the solved window `M` to **fix** in the next window. Equivalent of `AmplObject.set_init_sol`
(which writes `fix.mod` from `SET_INIT_SOL` of `PES_store_variables.mod`): `F_up_to`->`F_Mult`, `F_new_up_to`->`F_new`,
`F_decom_up_to`->`F_decom`, `F_old_up_to`->`F_old`, `F_used_year_start_next`->`F_used_year_start`, `Res_up_to`->`Res`,
`Res_t_up_to`->`Res_t`, each on the `*_UP_TO` sets of the solved window. The entries have the form of `db.fixes`.
"""
function carry_over(M, db::DataStore)
    S, v = M.S, M.v
    sset(name) = haskey(db.sets, name) ? strs(db.sets[name]) : String[]
    PU, YEAR_ONE_NEXT = sset("PHASE_UP_TO"), sset("YEAR_ONE_NEXT")
    TECH, RES, PERIODS, YU = S.TECHNOLOGIES, S.RESOURCES, S.PERIODS, S.YEARS_UP_TO
    out = NamedTuple{(:var, :key, :value, :file),Tuple{String,Tuple,Any,String}}[]
    add(name, var, key) = push!(out, (var=name, key=key, value=Float64(value(var[key...])), file="<previous window>"))
    for y in YU, j in TECH;                     add("F_Mult", v.F_Mult, (y, j)); end
    for p in unique(vcat(PU, ["2020_2025"])), j in TECH; add("F_new", v.F_new, (p, j)); end
    for p in PU, j in TECH;                     add("F_old", v.F_old, (p, j)); end
    for pd in PU, pb in unique(vcat(PU, ["2015_2020", "2020_2025"])), j in TECH
        add("F_decom", v.F_decom, (pd, pb, j))
    end
    for y in YEAR_ONE_NEXT, j in TECH;          add("F_used_year_start", v.F_used_year_start, (y, j)); end
    for y in YU, j in RES;                      add("Res", v.Res, (y, j)); end
    for y in YU, j in RES, t in PERIODS;        add("Res_t", v.Res_t, (y, j, t)); end
    out
end

end # module
