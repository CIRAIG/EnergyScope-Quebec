"""
    QCEsMain

Julia/JuMP translation of `shared/model/QC_es_main.mod` (static part of the model, shared by the
snapshot mode and the pathway). One section per block of the `.mod`, same constraint and variable names;
the `.mod` line number is given in a comment for review.

Convention: `YEARS_WND diff YEAR_ONE` is called `Y`, `YEARS_UP_TO union YEARS_WND` is called `YC`
(the AMPL constraints are posed on one or the other).

Not translated: the commented-out blocks of the `.mod` (taxes), and the variables that appear in
no constraint (`C_tax_tech`, `C_tax_res`, `CC_tax_reduction`, `STO`), which have no effect on the solution.
"""
module QCEsMain

using JuMP
using ..AmplDat

export QCModel, build_qc_model, constraint_counts, Ctx, con!, triv!, Par, par, strs, build_sets

strs(v) = String[string(x) for x in v]

# ───────────── parameters: access `p(y, i, ...)` with the `default` clause of the .mod ─────────────

struct Par
    name::String
    d::Dict{Tuple,Any}
    default::Any            # nothing = no default declared
end
function (p::Par)(k...)
    v = get(p.d, k, p.default)
    v === nothing && error("parameter $(p.name)$k: no value in the .dat files and no `default` in the .mod")
    v
end
par(db::DataStore, name) = Par(name, get(db.params, name, Dict{Tuple,Any}()), get(db.defaults, name, nothing))

# ───────────── sets ─────────────

function build_sets(db::DataStore)
    s(name) = haskey(db.sets, name) ? strs(db.sets[name]) : String[]
    iset(name, k) = haskey(db.isets, name) ? strs(get(db.isets[name], (k,), Any[])) : String[]
    uni(args...) = unique!(vcat(args...))
    PERIODS = Int[x for x in db.sets["PERIODS"]]

    CATS = s("END_USES_CATEGORIES")
    EUT = uni([iset("END_USES_TYPES_OF_CATEGORY", c) for c in CATS]...)               # :31
    RES = s("RESOURCES")
    STO = s("STORAGE_TECH")
    CCUS = uni(s("TECHNOLOGIES_OF_CC"), s("TECHNOLOGIES_OF_CCS"), s("TECHNOLOGIES_OF_CCU"))   # :52
    PRIV, PUB, FRE = s("TECHNOLOGIES_OF_PRIVATEMOB_ALL_DISTANCES"), s("TECHNOLOGIES_OF_PUBLICMOB_ALL_DISTANCES"),
                     s("TECHNOLOGIES_OF_FREIGHTMOB_ALL_DISTANCES")
    TECH = uni([iset("TECHNOLOGIES_OF_END_USES_TYPE", i) for i in EUT]..., STO, s("INFRASTRUCTURE"), CCUS,
               s("TECHNOLOGIES_OF_IND"), PRIV, PUB, FRE)                                  # :70
    LAYERS = uni(setdiff(RES, s("EXPORT")), EUT)                                          # :69
    TECH_OF_CAT = Dict(c => uni([iset("TECHNOLOGIES_OF_END_USES_TYPE", j) for j in iset("END_USES_TYPES_OF_CATEGORY", c)]...)
                       for c in CATS)                                                      # :71
    suvs(type) = intersect(uni([iset("MODELS_OF_TECHNOLOGIES_OF_PRIVATEMOB_ALL_DISTANCES", j) for j in s("SUVS")]...),
                           iset("TECHNOLOGIES_OF_MOB_TYPE", type))                         # :103-106
    YWND, Y1, YUP = s("YEARS_WND"), s("YEAR_ONE"), s("YEARS_UP_TO")
    (; YEARS=s("YEARS"), YEAR_ONE=Y1, YEARS_WND=YWND, YEARS_UP_TO=YUP,
       Y=setdiff(YWND, Y1), YC=uni(YUP, YWND),
       PERIODS, SECTORS=s("SECTORS"), END_USES_CATEGORIES=CATS, END_USES_TYPES=EUT, RESOURCES=RES,
       STORAGE_TECH=STO, TECHNOLOGIES=TECH, LAYERS, CO2_CATEGORY=s("CO2_CATEGORY"),
       RT=uni(RES, TECH), RT_noSTO=setdiff(uni(RES, TECH), STO), TECH_noSTO=setdiff(TECH, STO),
       RENEW=s("RENEW"), PV_TECH=s("PV_TECH"), BIO_PRODUCT=s("BIO_PRODUCT"), TECHNOLOGIES_OF_CCS=s("TECHNOLOGIES_OF_CCS"),
       GRIDS=s("GRIDS"), ELECTRICITY_LAYERS=s("ELECTRICITY_LAYERS"), H2_LAYERS=s("H2_LAYERS"), NG_LAYERS=s("NG_LAYERS"),
       SNG_LAYERS=s("SNG_LAYERS"), SCHOOLBUSES=s("SCHOOLBUSES"), MOBILITY_TYPE=s("MOBILITY_TYPE"),
       PRIV, PUB, FRE, TECH_OF_CAT,
       SUVS_SD=suvs("MOB_PRIVATE_ROAD_SD"), SUVS_MD=suvs("MOB_PRIVATE_ROAD_MD"),
       SUVS_LD=suvs("MOB_PRIVATE_ROAD_LD"), SUVS_ELD=suvs("MOB_PRIVATE_ROAD_ELD"),
       MARITIME_BULK=s("MODELS_OF_TECHNOLOGIES_MARITIME_BULK_CARRIER"),
       MARITIME_CONT=s("MODELS_OF_TECHNOLOGIES_MARITIME_CONTAINER"),
       MARITIME_OIL=s("MODELS_OF_TECHNOLOGIES_MARITIME_OIL_TANKER"),
       iset)
end

# ───────────── model wrapper ─────────────

struct QCModel
    model::Model
    S::Any                          # sets
    v::Any                          # variables (NamedTuple)
    attempted::Dict{String,Int}     # instances of each constraint (like AMPL's `card(constraint)`)
    trivial::Dict{String,Int}       # instances without variable or with infinite bound (omitted, as in AMPL)
end
constraint_counts(M::QCModel) = M.attempted

mutable struct Ctx
    m::Model
    att::Dict{String,Int}
    triv::Dict{String,Int}
end

"Counts one trivial constraint instance (omitted, as AMPL does)."
triv!(c::Ctx, name) = (c.att[name] = get(c.att, name, 0) + 1; c.triv[name] = get(c.triv, name, 0) + 1; nothing)

"Adds `lhs <sense> rhs`; omits (and counts) constraints without variable or with infinite bound."
function con!(c::Ctx, name::String, lhs, sense::Symbol, rhs=0.0)
    c.att[name] = get(c.att, name, 0) + 1
    if rhs isa Real && isinf(rhs)
        ((sense == :<= && rhs > 0) || (sense == :>= && rhs < 0)) && (c.triv[name] = get(c.triv, name, 0) + 1; return nothing)
        error("constraint $name infeasible: bound $sense $rhs")
    end
    e = lhs - rhs
    if e isa Real || (e isa AffExpr && (drop_zeros!(e); isempty(e.terms)))
        k = e isa Real ? e : e.constant
        ok = sense == :(==) ? abs(k) <= 1e-9 : sense == :<= ? k <= 1e-9 : k >= -1e-9
        ok || error("constraint $name has no variable and is violated: $k $sense 0")
        c.triv[name] = get(c.triv, name, 0) + 1
        return nothing
    end
    sense == :(==) ? @constraint(c.m, e == 0) : sense == :<= ? @constraint(c.m, e <= 0) : @constraint(c.m, e >= 0)
    nothing
end

# ───────────── construction ─────────────

"""
    build_qc_model(db::DataStore) -> QCModel

Builds the JuMP model from the data read by `AmplDat`. Does not solve.

`extend!` (optional): function `extend!(c, db, S, v) -> NamedTuple` called once the static model is built. It adds
variables and constraints (the pathway model: `PES_main.mod` & co) and **sets the objective**; it returns its variables,
which are merged into `v`. Without `extend!`, the objective is the snapshot one (`QC_objective_function.mod`).
"""
function build_qc_model(db::DataStore; extend! = nothing)
    S = build_sets(db)
    (; YEARS, Y, YC, PERIODS, SECTORS, END_USES_TYPES, RESOURCES, STORAGE_TECH, TECHNOLOGIES, LAYERS, CO2_CATEGORY,
       RT, RT_noSTO, TECH_noSTO, GRIDS) = S
    TECH = TECHNOLOGIES; STO = STORAGE_TECH; RES = RESOURCES; EUT = END_USES_TYPES
    iset = S.iset
    P(name) = par(db, name)

    # --- parameters (QC_es_main.mod:113-244) ---
    demand, t_op = P("end_uses_demand_year"), P("t_op")
    total_time = sum(t_op(t) for t in PERIODS)                                              # :180
    eui_cache = Dict{Tuple{String,String},Float64}()
    eui(y, i) = get!(eui_cache, (y, i)) do; sum(demand(y, i, s) for s in SECTORS); end      # :114
    lighting_month, heating_month, elec_export_month, cooling_month = P("lighting_month"), P("heating_month"), P("elec_export_month"), P("cooling_month")
    lio, c_inv, c_maint, lifetime = P("layers_in_out"), P("c_inv"), P("c_maint"), P("lifetime")
    f_max, f_min, fmax_perc, fmin_perc = P("f_max"), P("f_min"), P("fmax_perc"), P("fmin_perc")
    fmax_perc_mob, fmin_perc_mob, c_p_t, c_p = P("fmax_perc_mob"), P("fmin_perc_mob"), P("c_p_t"), P("c_p")
    i_hurdle, gwp_constr_p, trl = P("i_hurdle"), P("gwp_constr"), P("trl")
    c_op, avail, gwp_e = P("c_op"), P("avail"), P("gwp_e")
    f_grid_ext, l_grid_ext, n_stations, k_security = P("f_grid_ext"), P("l_grid_ext"), P("n_stations"), P("k_security")
    eff_in, eff_out, loss_coeff = P("storage_eff_in"), P("storage_eff_out"), P("loss_coeff")
    peak_dhn_factor, co2_limit, co2_limit_max, sng_min = P("peak_dhn_factor"), P("co2_limit"), P("co2_limit_max"), P("sng_min")
    renew, trl_min, trl_max, bio_ratio = P("renew"), P("trl_min"), P("trl_max"), P("bio_ratio")
    out_max, out_min, reno_max, reno_min = P("out_max"), P("out_min"), P("reno_max"), P("reno_min")
    tau(y, i) = (h = i_hurdle(y, i); n = lifetime(y, i);
                 (h > 0 && n > 0) || error("annuity factor undefined for ($y, $i): i_hurdle = $h and lifetime = $n must both be positive ",
                                           "(use a small i_hurdle such as 0.0001 to approximate 0 %)");
                 h * (1 + h)^n / ((1 + h)^n - 1))   # :203

    m = Model()
    c = Ctx(m, Dict{String,Int}(), Dict{String,Int}())

    # --- variables (:254-317) ---
    @variable(m, End_Uses[YEARS, LAYERS, PERIODS] >= 0)
    @variable(m, F_Mult[YEARS, TECH] >= 0)
    @variable(m, F_Mult_t[YEARS, RT, PERIODS] >= 0)
    @variable(m, C_inv[YEARS, TECH] >= 0)
    @variable(m, C_maint[YEARS, TECH] >= 0)
    @variable(m, C_op[YEARS, RES] >= 0)
    @variable(m, Storage_In[YEARS, STO, LAYERS, PERIODS] >= 0)
    @variable(m, Storage_Out[YEARS, STO, LAYERS, PERIODS] >= 0)
    @variable(m, Share_Mobility_Public[type in ("SD", "MD", "LD", "ELD"), y in YEARS])
    for type in ("SD", "MD", "LD", "ELD"), y in YEARS
        set_lower_bound(Share_Mobility_Public[type, y], P("share_mobility_public_min_" * lowercase(type))(y))
        set_upper_bound(Share_Mobility_Public[type, y], P("share_mobility_public_max_" * lowercase(type))(y))
    end
    @variable(m, Share_Heat_Dhn[YEARS])
    for y in YEARS
        set_lower_bound(Share_Heat_Dhn[y], P("share_heat_dhn_min")(y)); set_upper_bound(Share_Heat_Dhn[y], P("share_heat_dhn_max")(y))
    end
    @variable(m, Y_Solar_Backup[YEARS, TECH], Bin)
    @variable(m, Losses[YEARS, EUT, PERIODS] >= 0)
    @variable(m, GWP_constr[YEARS, TECH] >= 0)
    @variable(m, TotalGWP[YEARS])
    @variable(m, TotalCost[YEARS] >= 0)
    @variable(m, Monthly_Prod[YEARS, TECH, PERIODS])
    @variable(m, Annual_Prod[YEARS, TECH_noSTO])
    @variable(m, Annual_Res[YEARS, RES])
    @variable(m, GWP[YEARS, CO2_CATEGORY, PERIODS])
    @variable(m, Total_emission[YEARS, PERIODS])
    @variable(m, C_inv_grid_help[YEARS, GRIDS] >= 0)
    DECEN = setdiff(iset("TECHNOLOGIES_OF_END_USES_TYPE", "HEAT_LOW_T_DECEN"), ["DEC_SOLAR"])
    @variable(m, X_Solar_Backup_Aux[YEARS, DECEN, PERIODS] >= 0)                            # :528
    @variable(m, Y_Sto_In[YEARS, STO, PERIODS], Bin)                                        # :576
    @variable(m, Y_Sto_Out[YEARS, STO, PERIODS], Bin)
    @variable(m, Max_Heat_Demand_DHN[YEARS] >= 0)                                           # :686
    @variable(m, Share_Public_Schoolbus_SD[YEARS])                                          # :1298
    for y in YEARS
        set_lower_bound(Share_Public_Schoolbus_SD[y], P("share_public_schoolbus_min_sd")(y))
        set_upper_bound(Share_Public_Schoolbus_SD[y], P("share_public_schoolbus_max_sd")(y))
    end

    # Seasonal storages: same pattern for NG, CO2, H2, ELEC, DIE, GASO (:937-1180)
    # (key, input tech, output tech, layer, suffix, capacity_factor name, balance name t>1, balance name t=1, level bounds)
    kinds = [("NG", "NG_STO", "STO_NG", "NG_S", "", "capacity_factor_Sto_ng", "ng_storage", "ng_balance", (0.0, Inf)),
             ("CO2", "CO2_STO", "STO_CO2", "CO2_CS", "_co2", "capacity_factor_Sto_co2", "co2_storage", "co2_balance", (0.0, Inf)),
             ("H2", "H2_STO", "STO_H2", "H2_S", "_h2", "capacity_factor_Sto_h2", "h2_storage", "h2_balance", (0.0, Inf)),
             ("ELEC", "ELEC_STO", "STO_ELEC", "ELEC_S", "_elec", "capacity_factor_Sto_elec", "elec_storage", "elec_balance", (0.0, 0.0)),
             ("DIE", "DIE_STO", "STO_DIE", "DIESEL_S", "_DIE", "capacity_factor_Sto_DIE", "DIE_storage", "DIE_balance", (0.0, Inf)),
             ("GASO", "GASO_STO", "STO_GASO", "GASOLINE_S", "_GASO", "capacity_factor_Sto_GASO", "GASO_storage", "GASO_balance", (0.0, Inf))]
    LEVEL, BIN_IN, BIN_OUT, HELP_IN, HELP_OUT = Dict(), Dict(), Dict(), Dict(), Dict()
    for (k, _, _, _, _, _, _, _, (lo, hi)) in kinds
        LEVEL[k] = @variable(m, [YEARS, PERIODS], lower_bound = lo, base_name = "STO_$(k)_LEVEL")
        isfinite(hi) && for y in YEARS, t in PERIODS; set_upper_bound(LEVEL[k][y, t], hi); end
        BIN_IN[k] = @variable(m, [YEARS, PERIODS], Bin, base_name = "STO_IN_$k")
        BIN_OUT[k] = @variable(m, [YEARS, PERIODS], Bin, base_name = "STO_OUT_$k")
        HELP_IN[k] = @variable(m, [YEARS, PERIODS], lower_bound = 0, base_name = "HELP_STO_$k")
        HELP_OUT[k] = @variable(m, [YEARS, PERIODS], lower_bound = 0, base_name = "HELP_STO_OUT_$k")
    end

    # --- reused formula parts ---
    sum_in(y, i, t) = sum((Storage_In[y, i, l, t] * eff_in(y, i, l) for l in LAYERS if eff_in(y, i, l) > 0); init=AffExpr(0.0))
    sum_out(y, i, t) = sum((Storage_Out[y, i, l, t] / eff_out(y, i, l) for l in LAYERS if eff_out(y, i, l) > 0); init=AffExpr(0.0))
    # non-zero (technology/resource, coefficient) pairs of layers_in_out for a layer, per year
    lio_by = Dict{Tuple{String,String},Vector{Tuple{String,Float64}}}()
    inRTnS = Set(RT_noSTO)
    for ((y, i, l), v) in db.params["layers_in_out"]
        (v == 0 || !(i in inRTnS)) && continue
        push!(get!(lio_by, (string(y), string(l)), Tuple{String,Float64}[]), (string(i), Float64(v)))
    end
    lio_list(y, l) = get(lio_by, (y, l), Tuple{String,Float64}[])
    lio_sum(y, l, t; cond=(v -> true), over=nothing) =
        sum((v * F_Mult_t[y, i, t] for (i, v) in lio_list(y, l) if cond(v) && (over === nothing || i in over)); init=AffExpr(0.0))

    # ═══════════ End-use demand (:323-446) ═══════════
    for y in Y, l in LAYERS, t in PERIODS
        D = eui; tm = total_time
        rhs = if l == "ELECTRICITY_LV"
            D(y, l) / tm + D(y, "LIGHTING") * lighting_month(t) / t_op(t) + D(y, "HEAT_LOW_T_SC") * cooling_month(t) / t_op(t) + Losses[y, l, t]
        elseif l == "ELECTRICITY_MV" || l == "ELECTRICITY_HV"
            D(y, l) / tm + Losses[y, l, t]
        elseif l == "ELECTRICITY_EHV"
            D(y, l) / tm + D(y, "ELECTRICITY_EHV_EXPORT") * elec_export_month(t) / t_op(t) + Losses[y, l, t]
        elseif l == "HEAT_LOW_T_DHN"
            (D(y, "HEAT_LOW_T_HW") / tm + D(y, "HEAT_LOW_T_SH") * heating_month(t) / t_op(t)) * Share_Heat_Dhn[y] + Losses[y, l, t]
        elseif l == "HEAT_LOW_T_DECEN"
            (D(y, "HEAT_LOW_T_HW") / tm + D(y, "HEAT_LOW_T_SH") * heating_month(t) / t_op(t)) * (1 - Share_Heat_Dhn[y])
        elseif l in ("MOB_PUBLIC_SD", "MOB_PUBLIC_MD", "MOB_PUBLIC_LD", "MOB_PUBLIC_ELD")
            ty = l[12:end]; D(y, "MOBILITY_PASSENGER_" * ty) / tm * Share_Mobility_Public[ty, y]
        elseif l in ("MOB_PRIVATE_SD", "MOB_PRIVATE_MD", "MOB_PRIVATE_LD", "MOB_PRIVATE_ELD")
            ty = l[13:end]; D(y, "MOBILITY_PASSENGER_" * ty) / tm * (1 - Share_Mobility_Public[ty, y])
        elseif l in ("MOB_FREIGHT_SD", "MOB_FREIGHT_MD", "MOB_FREIGHT_LD", "MOB_FREIGHT_ELD")
            D(y, "MOBILITY_FREIGHT_" * l[13:end]) / tm
        elseif l in ("HEAT_HIGH_T", "METHANOL", "PHENOL", "ACETIC_ACID", "ACETONE", "PE", "PET", "PVC", "PP", "PS",
                     "ALUMINUM", "PAPER", "CEMENT", "STEEL", "FOOD")
            D(y, l) / tm
        else
            0.0
        end
        con!(c, "end_uses_t", End_Uses[y, l, t], :(==), rhs)
    end

    # ═══════════ Layer balance (:457-483) ═══════════
    excluded = ("H2_S", "NG_S", "CO2_CS", "HEAT_WASTE", "ELEC_S", "DIESEL_S", "GASOLINE_S")
    for y in Y, l in setdiff(unique(vcat(LAYERS, CO2_CATEGORY)), excluded), t in PERIODS
        e = if l == "CO2_A" || l == "CO2_S" || l == "CO2_E"
            lio_sum(y, l, t) - GWP[y, l, t]
        elseif l == "CO2_EE"
            sum((F_Mult_t[y, i, t] * gwp_e(y, i, t) for i in RES); init=AffExpr(0.0)) - GWP[y, l, t]
        elseif l == "CO2_C"
            lio_sum(y, l, t)
        else
            lio_sum(y, l, t) + sum((Storage_Out[y, j, l, t] - Storage_In[y, j, l, t] for j in STO); init=AffExpr(0.0)) - End_Uses[y, l, t]
        end
        con!(c, "layer_balance", e, :(==))
    end
    for y in Y, t in PERIODS
        con!(c, "co2_caputrable", GWP[y, "CO2_A", t], :>=)
        con!(c, "co2_imp", GWP[y, "CO2_EE", t], :>=)
    end

    # ═══════════ Multiplication factors (:498-546) ═══════════
    for y in Y, i in TECH                                                          # size_limit :498 (variable bounds)
        c.att["size_limit"] = get(c.att, "size_limit", 0) + 1
        f_min(y, i) > f_max(y, i) &&
            error("capacity limits of ($y, $i): f_min = $(f_min(y, i)) is above f_max = $(f_max(y, i)), the model would be infeasible")
        f_min(y, i) > 0 && set_lower_bound(F_Mult[y, i], f_min(y, i))
        isfinite(f_max(y, i)) && set_upper_bound(F_Mult[y, i], f_max(y, i))
        c.triv["size_limit"] = get(c.triv, "size_limit", 0) + 1
    end
    no_cf = ("H2_STO", "NG_STO", "CO2_STO", "ELEC_STO", "GASO_STO", "DIE_STO")
    for y in Y, i in setdiff(TECH, no_cf), t in PERIODS
        con!(c, "capacity_factor_t", F_Mult_t[y, i, t] - F_Mult[y, i] * c_p_t(y, i, t), :<=)       # :502
    end
    for y in Y, (k, i, _, _, _, nm) in kinds, t in PERIODS
        con!(c, nm, LEVEL[k][y, t] - F_Mult[y, i], :<=)                                              # :508-513, 1055, 1102, 1145
    end
    for y in Y, i in TECH                                                                           # :516
        con!(c, "capacity_factor", sum(F_Mult_t[y, i, t] * t_op(t) for t in PERIODS) - F_Mult[y, i] * c_p(y, i) * total_time, :<=)
    end
    for y in Y, i in DECEN, t in PERIODS                                                            # :530-542
        coef = (eui(y, "HEAT_LOW_T_HW") / total_time + eui(y, "HEAT_LOW_T_SH") * heating_month(t) / t_op(t)) /
               (eui(y, "HEAT_LOW_T_HW") + eui(y, "HEAT_LOW_T_SH"))
        con!(c, "op_strategy_decen_1_linear",
             F_Mult_t[y, i, t] + X_Solar_Backup_Aux[y, i, t] - sum(F_Mult_t[y, i, t2] * t_op(t2) for t2 in PERIODS) * coef, :>=)
        con!(c, "op_strategy_decen_1_linear_1", X_Solar_Backup_Aux[y, i, t] - f_max(y, "DEC_SOLAR") * Y_Solar_Backup[y, i], :<=)
        con!(c, "op_strategy_decen_1_linear_2", X_Solar_Backup_Aux[y, i, t] - F_Mult_t[y, "DEC_SOLAR", t], :<=)
        con!(c, "op_strategy_decen_1_linear_3",
             X_Solar_Backup_Aux[y, i, t] - F_Mult_t[y, "DEC_SOLAR", t] + (1 - Y_Solar_Backup[y, i]) * f_max(y, "DEC_SOLAR"), :>=)
    end
    for y in Y
        con!(c, "op_strategy_decen_2", sum(Y_Solar_Backup[y, i] for i in TECH), :<=, 1.0)           # :545
    end

    # ═══════════ Resources (:552) ═══════════
    for y in Y, i in RES
        con!(c, "resource_availability", sum(F_Mult_t[y, i, t] * t_op(t) for t in PERIODS), :<=, avail(y, i))
    end

    # ═══════════ Storage (:560-608) ═══════════
    for y in Y, i in STO, l in LAYERS, t in PERIODS                                                # :560-564
        for (nm, var, eff) in (("storage_layer_in", Storage_In, eff_in), ("storage_layer_out", Storage_Out, eff_out))
            k = ceil(eff(y, i, l)) - 1                  # 0 if the storage/layer pair is compatible, -1 otherwise
            k == 0 ? triv!(c, nm) : con!(c, nm, var[y, i, l, t] * k, :(==))
        end
    end
    for y in Y, i in STO, t in PERIODS
        con!(c, "storage_no_transfer_1", sum_in(y, i, t) * t_op(t) - Y_Sto_In[y, i, t] * f_max(y, i), :<=)    # :582
        con!(c, "storage_no_transfer_2", sum_out(y, i, t) * t_op(t) - Y_Sto_Out[y, i, t] * f_max(y, i), :<=)  # :585
        con!(c, "storage_no_transfer_3", Y_Sto_In[y, i, t] + Y_Sto_Out[y, i, t], :<=, 1.0)                    # :588
        prev = t == 1 ? length(PERIODS) : t - 1                                                               # :602
        con!(c, "storage_level", F_Mult_t[y, i, t] - F_Mult_t[y, i, prev] - (sum_in(y, i, t) - sum_out(y, i, t)) * t_op(t), :(==))
    end

    # ═══════════ Losses (:611) ═══════════
    for y in Y, i in EUT, t in PERIODS
        con!(c, "network_losses", Losses[y, i, t] - lio_sum(y, i, t; cond=(v -> v > 0)) * loss_coeff(y, i), :(==))
    end

    # ═══════════ Min/max shares (:618-630) ═══════════
    for y in Y, i in EUT, j in iset("TECHNOLOGIES_OF_END_USES_TYPE", i)
        tot = sum(F_Mult_t[y, j2, t2] * t_op(t2) for j2 in iset("TECHNOLOGIES_OF_END_USES_TYPE", i) for t2 in PERIODS)
        mine = sum(F_Mult_t[y, j, t] * t_op(t) for t in PERIODS)
        con!(c, "f_max_perc", mine - fmax_perc(y, j) * tot, :<=)
        con!(c, "f_min_perc", mine - fmin_perc(y, j) * tot, :>=)
    end
    for y in Y, i in S.MOBILITY_TYPE, j in iset("TECHNOLOGIES_OF_MOB_TYPE", i)
        tot = sum(F_Mult_t[y, j2, t2] * t_op(t2) for j2 in iset("TECHNOLOGIES_OF_MOB_TYPE", i) for t2 in PERIODS)
        mine = sum(F_Mult_t[y, j, t] * t_op(t) for t in PERIODS)
        con!(c, "f_max_perc_mob", mine - fmax_perc_mob(y, j) * tot, :<=)
        con!(c, "f_min_perc_mob", mine - fmin_perc_mob(y, j) * tot, :>=)
    end

    # ═══════════ Hydro dams (:635, :639) ═══════════
    for y in Y
        con!(c, "storage_level_hydro_dams",
             F_Mult[y, "HYDRO_STORAGE"] * (f_max(y, "NEW_HYDRO_DAM") - f_min(y, "NEW_HYDRO_DAM")) -
             (f_min(y, "HYDRO_STORAGE") + (f_max(y, "HYDRO_STORAGE") - f_min(y, "HYDRO_STORAGE")) * (F_Mult[y, "NEW_HYDRO_DAM"] - f_min(y, "NEW_HYDRO_DAM"))), :<=)
    end
    for y in Y, t in PERIODS
        con!(c, "hydro_dams_shift", Storage_In[y, "HYDRO_STORAGE", "ELECTRICITY_EHV", t] - (F_Mult_t[y, "HYDRO_DAM", t] + F_Mult_t[y, "NEW_HYDRO_DAM", t]), :<=)
    end

    # ═══════════ District heating (:682-693) ═══════════
    DHN = iset("TECHNOLOGIES_OF_END_USES_TYPE", "HEAT_LOW_T_DHN")
    for y in Y
        con!(c, "extra_dhn", F_Mult[y, "DHN"] - sum(F_Mult[y, j] for j in setdiff(DHN, ["DHN_RENOVATION"])), :(==))
    end
    for y in Y, t in PERIODS
        con!(c, "max_dhn_heat_demand", Max_Heat_Demand_DHN[y] - End_Uses[y, "HEAT_LOW_T_DHN", t], :>=)
    end
    for y in Y
        con!(c, "peak_dhn", sum(F_Mult[y, j] for j in DHN) - peak_dhn_factor() * Max_Heat_Demand_DHN[y], :>=)
    end

    # ═══════════ Mobility (:706-744) ═══════════
    MOBCATS = ["MOBILITY_PASSENGER_SD", "MOBILITY_PASSENGER_MD", "MOBILITY_PASSENGER_LD", "MOBILITY_PASSENGER_ELD",
               "MOBILITY_FREIGHT_SD", "MOBILITY_FREIGHT_MD", "MOBILITY_FREIGHT_LD", "MOBILITY_FREIGHT_ELD"]
    MOBTECH = unique!(vcat([S.TECH_OF_CAT[x] for x in MOBCATS]...))
    for y in Y, i in MOBTECH, t in PERIODS
        con!(c, "op_strategy_mob_private", F_Mult_t[y, i, t] - sum(F_Mult_t[y, i, t2] * t_op(t2) / total_time for t2 in PERIODS), :>=)
    end
    for (nm, TL, key) in (("private", S.PRIV, "MODELS_OF_TECHNOLOGIES_OF_PRIVATEMOB_ALL_DISTANCES"),
                          ("public", S.PUB, "MODELS_OF_TECHNOLOGIES_OF_PUBLICMOB_ALL_DISTANCES"),
                          ("freight", S.FRE, "MODELS_OF_TECHNOLOGIES_OF_FREIGHTMOB_ALL_DISTANCES"))
        for y in Y, i in TL, j in iset(key, i)
            con!(c, "capacity_factor_mob_models_" * nm,
                 sum(F_Mult_t[y, j, t] * t_op(t) for t in PERIODS) - F_Mult[y, j] * c_p(y, i) * total_time, :<=)
        end
        for y in Y, j in TL, t in PERIODS
            con!(c, nm * "mob_use_pertech1", F_Mult_t[y, j, t] - sum(F_Mult_t[y, i, t] for i in iset(key, j)), :(==))
        end
        for y in Y, j in TL
            con!(c, nm * "mob_installed_pertech1", F_Mult[y, j] - sum(F_Mult[y, i] for i in iset(key, j)), :(==))
        end
    end

    # ═══════════ Grids (:761-765) ═══════════
    for y in Y, t in PERIODS, g in GRIDS
        con!(c, "grid_power1", F_Mult[y, g] - F_Mult_t[y, g, t], :>=)
    end
    techset_ns = Set(TECH_noSTO)
    GL = unique(vcat(S.ELECTRICITY_LAYERS, S.H2_LAYERS, S.NG_LAYERS))
    for y in Y, t in PERIODS, l in GL, g in iset("GRIDS_OF_LAYERS", l)
        con!(c, "grid_power2", F_Mult_t[y, g, t] - lio_sum(y, l, t; cond=(v -> v > 0), over=techset_ns) - F_Mult_t[y, l, t], :>=)
    end

    # ═══════════ Renewables (:774) ═══════════
    for y in Y
        con!(c, "renw_penetratino",
             sum(F_Mult_t[y, i, t] * t_op(t) for i in S.RENEW for t in PERIODS) -
             renew() * sum(F_Mult_t[y, ii, tt] * t_op(tt) for ii in setdiff(RES, S.BIO_PRODUCT) for tt in PERIODS), :>=)
    end

    # ═══════════ Costs (:793-837) ═══════════
    NOREN = setdiff(TECH, ["DHN_RENOVATION", "DEC_RENOVATION"], GRIDS)
    for y in YC, i in NOREN
        con!(c, "investment_cost_calc_1", C_inv[y, i] - c_inv(y, i) * F_Mult[y, i], :(==))
    end
    for y in YC
        con!(c, "investment_cost_calc_3", C_inv[y, "DHN_RENOVATION"] - c_inv(y, "DHN_RENOVATION") * sum(F_Mult_t[y, "DHN_RENOVATION", t] * t_op(t) for t in PERIODS), :(==))
    end
    for y in YC, i in GRIDS
        con!(c, "investment_cost_calc_4",
             C_inv[y, i] - (F_Mult[y, i] - f_grid_ext(i)) * c_inv(y, i) * l_grid_ext(i) * k_security(i) / n_stations(i) - C_inv_grid_help[y, i], :(==))
    end
    for y in YC, t in PERIODS
        con!(c, "op_strategy_renovation", F_Mult_t[y, "DHN_RENOVATION", t] - sum(F_Mult_t[y, "DHN_RENOVATION", t2] * t_op(t2) / total_time for t2 in PERIODS), :>=)
    end
    for y in YC
        con!(c, "investment_cost_calc_5", C_inv[y, "DEC_RENOVATION"] - c_inv(y, "DEC_RENOVATION") * sum(F_Mult_t[y, "DEC_RENOVATION", t] * t_op(t) for t in PERIODS), :(==))
    end
    for y in YC, t in PERIODS
        con!(c, "op_strategy_renovation_2", F_Mult_t[y, "DEC_RENOVATION", t] - sum(F_Mult_t[y, "DEC_RENOVATION", t2] * t_op(t2) / total_time for t2 in PERIODS), :>=)
    end
    for y in YC, i in TECH
        con!(c, "main_cost_calc", C_maint[y, i] - c_maint(y, i) * F_Mult[y, i], :(==))
    end
    for y in YC, i in RES
        con!(c, "op_cost_calc", C_op[y, i] - sum(c_op(y, i, t) * F_Mult_t[y, i, t] * t_op(t) for t in PERIODS), :(==))
    end
    for y in Y
        con!(c, "totalcost_cal",
             TotalCost[y] - sum(tau(y, i) * C_inv[y, i] + C_maint[y, i] for i in TECH) - sum(C_op[y, j] for j in RES), :(==))
    end

    # ═══════════ Emissions and output variables (:843-880) ═══════════
    for y in YC, i in TECH
        con!(c, "gwp_constr_calc", GWP_constr[y, i] - gwp_constr_p(y, i) * F_Mult[y, i] / lifetime(y, i), :(==))
    end
    for y in YC, i in TECH_noSTO, t in PERIODS
        con!(c, "production", Monthly_Prod[y, i, t] - F_Mult_t[y, i, t] * t_op(t), :(==))
    end
    for y in YC, i in TECH_noSTO
        con!(c, "production2", Annual_Prod[y, i] - sum(Monthly_Prod[y, i, t] for t in PERIODS), :(==))
    end
    for y in YC, r in RES
        con!(c, "res_import", Annual_Res[y, r] - sum(F_Mult_t[y, r, t] * t_op(t) for t in PERIODS), :(==))
    end
    for y in YC, i in STO, t in PERIODS
        con!(c, "storage", Monthly_Prod[y, i, t] -
             sum(((Storage_In[y, i, l, t] * eff_in(y, i, l) - Storage_Out[y, i, l, t] / eff_out(y, i, l)) for l in LAYERS if eff_out(y, i, l) > 0); init=AffExpr(0.0)) * t_op(t), :(==))
    end
    for y in YC, t in PERIODS
        con!(c, "total_emission", Total_emission[y, t] -
             (GWP[y, "CO2_A", t] + GWP[y, "CO2_E", t] - lio(y, "ELECTRICITY_EHV", "CO2_E") * F_Mult_t[y, "ELECTRICITY_EHV", t]) * t_op(t), :(==))
    end
    for y in YC
        con!(c, "co2_emission", sum(Total_emission[y, t] for t in PERIODS), :<=, co2_limit())
        con!(c, "co2_emission2", sum(Total_emission[y, t] for t in PERIODS), :>=, co2_limit_max())
        con!(c, "co2", TotalGWP[y] - sum(Total_emission[y, t] for t in PERIODS), :(==))
    end
    techset = Set(TECH_noSTO)
    for y in YC, sng in S.SNG_LAYERS                                                              # :879
        e = AffExpr(0.0)
        for (i, v) in lio_list(y, sng), t in PERIODS
            v > 0 && i in techset && add_to_expression!(e, v, Monthly_Prod[y, i, t])
        end
        con!(c, "sng_max", e, :>=, sng_min())
    end

    # ═══════════ Forced use (:882-917) ═══════════
    for y in Y, i in S.PV_TECH, t in PERIODS
        con!(c, "pv_full_utilization", F_Mult_t[y, i, t] - F_Mult[y, i] * c_p_t(y, i, t), :(==))
    end
    for (nm, tech) in (("solarthermal_full_utilization", "DEC_SOLAR"), ("wind_onshore_full_utilization", "WIND_ONSHORE"),
                       ("new_wind_onshore_full_utilization", "NEW_WIND_ONSHORE"), ("wind_offshore_full_utilization", "WIND_OFFSHORE"),
                       ("hydro_river_full_utilization", "HYDRO_RIVER"), ("new_hydro_river_full_utilization", "NEW_HYDRO_RIVER"))
        for y in Y, t in PERIODS
            con!(c, nm, F_Mult_t[y, tech, t] - F_Mult[y, tech] * c_p_t(y, tech, t), :(==))
        end
    end

    # ═══════════ TRL and biomass (:928, :931) ═══════════
    for y in Y, i in TECH
        (trl(y, i) > trl_max() || trl(y, i) < trl_min()) && con!(c, "trl_choice", F_Mult[y, i], :(==))
    end
    for y in Y
        rhs = bio_ratio() == 0 ? 0.0 : bio_ratio() * (avail(y, "WOOD") + avail(y, "WET_BIOMASS"))
        con!(c, "bio_peneration", sum((F_Mult_t[y, "WOOD", t] + F_Mult_t[y, "WET_BIOMASS", t]) * t_op(t) for t in PERIODS), :>=, rhs)
    end

    # ═══════════ Seasonal storages NG, CO2, H2, ELEC, DIE, GASO (:937-1180) ═══════════
    for (k, sin, sout, layer, suf, _, nm_storage, nm_balance, _) in kinds
        for y in Y
            for t in PERIODS
                flux = lio(y, sin, layer) * F_Mult_t[y, sin, t] * t_op(t) + lio(y, sout, layer) * F_Mult_t[y, sout, t] * t_op(t)
                if t > 1
                    con!(c, nm_storage, LEVEL[k][y, t] - LEVEL[k][y, t-1] - flux, :(==))
                else
                    con!(c, nm_balance, LEVEL[k][y, 1] - LEVEL[k][y, length(PERIODS)] - flux, :(==))
                end
            end
            for t in PERIODS
                con!(c, "bi_choice" * suf, BIN_IN[k][y, t] + BIN_OUT[k][y, t], :<=, 1.0)
                con!(c, "in_chocie" * suf, F_Mult_t[y, sin, t] - HELP_IN[k][y, t], :<=)
                con!(c, "aux_1" * suf, HELP_IN[k][y, t] - f_max(y, sin) * BIN_IN[k][y, t], :<=)
                con!(c, "aux_2" * suf, HELP_IN[k][y, t] - F_Mult_t[y, sin, t], :<=)
                con!(c, "aux_3" * suf, HELP_IN[k][y, t] - F_Mult_t[y, sin, t] + (1 - BIN_IN[k][y, t]) * f_max(y, sin), :>=)
                con!(c, "out_chocie" * suf, F_Mult_t[y, sout, t] - HELP_OUT[k][y, t], :<=)
                con!(c, "aux_1_out" * suf, HELP_OUT[k][y, t] - f_max(y, sout) * BIN_OUT[k][y, t], :<=)
                con!(c, "aux_2_out" * suf, HELP_OUT[k][y, t] - F_Mult_t[y, sout, t], :<=)
                con!(c, "aux_3_out" * suf, HELP_OUT[k][y, t] - F_Mult_t[y, sout, t] + (1 - BIN_OUT[k][y, t]) * f_max(y, sout), :>=)
            end
        end
    end
    for y in Y, t in PERIODS
        con!(c, "hydro_dams_shift3", F_Mult_t[y, "ELEC_STO", t] - (F_Mult_t[y, "HYDRO_DAM", t] + F_Mult_t[y, "NEW_HYDRO_DAM", t]), :<=)   # :1095
    end

    # ═══════════ Min/max production, CCU, renovation (:1186-1210) ═══════════
    for y in Y, i in TECH_noSTO
        con!(c, "prod_max", Annual_Prod[y, i], :<=, out_max(y, i))
        con!(c, "prod_min", Annual_Prod[y, i], :>=, out_min(y, i))
    end
    ccu_techs = setdiff(TECH_noSTO, S.TECHNOLOGIES_OF_CCS, ["CO2_STO"])
    for y in Y, t in PERIODS
        con!(c, "ccu", sum((-Annual_Prod[y, i] * lio(y, i, "CO2_C") for i in ccu_techs if lio(y, i, "CO2_C") < 0); init=AffExpr(0.0)) - LEVEL["CO2"][y, t], :>=)
    end
    for y in Y
        con!(c, "renovation_max", Annual_Prod[y, "DHN_RENOVATION"] + Annual_Prod[y, "DEC_RENOVATION"], :<=, reno_max())
        con!(c, "renovation_min", Annual_Prod[y, "DHN_RENOVATION"] + Annual_Prod[y, "DEC_RENOVATION"], :>=, reno_min())
    end

    # ═══════════ Mobility shares (:1231-1320) ═══════════
    function share_limits!(base, mobtype, minp, maxp, demand_type, share)
        for y in Y
            prod = sum(Annual_Prod[y, i] for i in iset("TECHNOLOGIES_OF_MOB_TYPE", mobtype))
            d = sum(demand(y, demand_type, s) for s in SECTORS)
            ref = share === nothing ? d : d * Share_Mobility_Public[share, y]
            con!(c, base * "_1", prod - P(minp)(y) * ref, :>=)
            con!(c, base * "_2", prod - P(maxp)(y) * ref, :<=)
        end
    end
    for ty in ("sd", "md", "ld", "eld")
        share_limits!("share_public_rail_$ty", "MOB_PUBLIC_RAIL_" * uppercase(ty), "share_public_rail_min_$ty", "share_public_rail_max_$ty",
                      "MOBILITY_PASSENGER_" * uppercase(ty), uppercase(ty))
    end
    for ty in ("ld", "eld")
        share_limits!("share_public_air_$ty", "MOB_PUBLIC_AIR_" * uppercase(ty), "share_public_air_min_$ty", "share_public_air_max_$ty",
                      "MOBILITY_PASSENGER_" * uppercase(ty), uppercase(ty))
        share_limits!("share_freight_rail_$ty", "MOB_FREIGHT_RAIL_" * uppercase(ty), "share_freight_rail_min_$ty", "share_freight_rail_max_$ty",
                      "MOBILITY_FREIGHT_" * uppercase(ty), nothing)
    end
    share_limits!("share_freight_air_eld", "MOB_FREIGHT_AIR_ELD", "share_freight_air_min_eld", "share_freight_air_max_eld", "MOBILITY_FREIGHT_ELD", nothing)
    share_limits!("share_freight_maritime_eld", "MOB_FREIGHT_MARITIME_ELD", "share_freight_maritime_min_eld", "share_freight_maritime_max_eld", "MOBILITY_FREIGHT_ELD", nothing)

    MAR = iset("TECHNOLOGIES_OF_MOB_TYPE", "MOB_FREIGHT_MARITIME_ELD")
    for y in Y, (nm, models, p) in (("f_min_perc_container", S.MARITIME_CONT, "share_freight_maritime_container"),
                                    ("f_min_perc_bulk_carrier", S.MARITIME_BULK, "share_freight_maritime_bulk_carrier"),
                                    ("f_min_perc_oil_tanker", S.MARITIME_OIL, "share_freight_maritime_oil_tanker"))
        con!(c, nm, sum(F_Mult_t[y, j, t] * t_op(t) for t in PERIODS for j in models) -
                    P(p)(y) * sum(F_Mult_t[y, j, t] * t_op(t) for j in MAR for t in PERIODS), :>=)
    end

    # Schoolbus (:1293-1300). The quotient by a variable (Share_Mobility_Public_SD) is linear only if the
    # share is fixed (min == max): AMPL then fixes it in presolve. Same here, otherwise a clear error.
    for y in Y
        d = sum(demand(y, "MOBILITY_PASSENGER_SD", s) for s in SECTORS)
        prod = sum(Annual_Prod[y, i] for i in S.SCHOOLBUSES)
        con!(c, "share_public_schoolbus_sd_1", prod - P("share_public_schoolbus_min_sd")(y) * d * Share_Mobility_Public["SD", y], :>=)
        con!(c, "share_public_schoolbus_sd_2", prod - P("share_public_schoolbus_max_sd")(y) * d * Share_Mobility_Public["SD", y], :<=)
        lo, hi = P("share_mobility_public_min_sd")(y), P("share_mobility_public_max_sd")(y)
        lo == hi || error("share_public_schoolbus_sd_3 is non-linear (quotient by Share_Mobility_Public_SD[$y]): " *
                          "requires share_mobility_public_min_sd == max_sd, here $lo ≠ $hi")
        con!(c, "share_public_schoolbus_sd_3", Share_Public_Schoolbus_SD[y] - prod / (d * lo), :(==))
    end
    for ty in ("sd", "md", "ld", "eld"), y in Y
        suv = getfield(S, Symbol("SUVS_" * uppercase(ty)))
        tot = sum(Annual_Prod[y, j] for j in iset("TECHNOLOGIES_OF_MOB_TYPE", "MOB_PRIVATE_ROAD_" * uppercase(ty)))
        mine = sum(Annual_Prod[y, i] for i in suv)
        con!(c, "share_private_suv_$(ty)_1", mine - P("share_private_suv_min_$ty")(y) * tot, :>=)
        con!(c, "share_private_suv_$(ty)_2", mine - P("share_private_suv_max_$ty")(y) * tot, :<=)
    end

    v0 = (; End_Uses, F_Mult, F_Mult_t, C_inv, C_maint, C_op, Storage_In, Storage_Out, Share_Mobility_Public, Share_Heat_Dhn,
          Y_Solar_Backup, Losses, GWP_constr, TotalGWP, TotalCost, Monthly_Prod, Annual_Prod, Annual_Res, GWP, Total_emission,
          C_inv_grid_help, X_Solar_Backup_Aux, Y_Sto_In, Y_Sto_Out, Max_Heat_Demand_DHN, Share_Public_Schoolbus_SD,
          LEVEL, BIN_IN, BIN_OUT, HELP_IN, HELP_OUT)

    # ═══════════ Extension (pathway model) ═══════════
    extra = extend! === nothing ? NamedTuple() : extend!(c, db, S, v0)

    # ═══════════ Constraints added by the user in scenario .dat files (`subject to ...`) ═══════════
    vars = Dict{String,Any}("End_Uses" => End_Uses, "F_Mult" => F_Mult, "F_Mult_t" => F_Mult_t, "C_inv" => C_inv,
        "C_maint" => C_maint, "C_op" => C_op, "Storage_In" => Storage_In, "Storage_Out" => Storage_Out,
        "Share_Heat_Dhn" => Share_Heat_Dhn, "Losses" => Losses, "GWP_constr" => GWP_constr, "TotalGWP" => TotalGWP,
        "TotalCost" => TotalCost, "Monthly_Prod" => Monthly_Prod, "Annual_Prod" => Annual_Prod, "Annual_Res" => Annual_Res,
        "GWP" => GWP, "Total_emission" => Total_emission, "Y_Solar_Backup" => Y_Solar_Backup,
        "Max_Heat_Demand_DHN" => Max_Heat_Demand_DHN, "Share_Public_Schoolbus_SD" => Share_Public_Schoolbus_SD)
    for ty in ("SD", "MD", "LD", "ELD")
        vars["Share_Mobility_Public_$ty"] = y -> Share_Mobility_Public[ty, y]
    end
    for (k, x) in pairs(extra)
        vars[String(k)] = x                       # pathway variables, also visible to the user's `subject to`
    end
    for cs in db.constraints
        st = cs.stmt
        foreach_domain(db, st.dom, cs.file, st.line) do env
            l = AmplDat.evaluate(st.lhs, env, db, cs.file, st.line, vars)
            r = AmplDat.evaluate(st.rhs, env, db, cs.file, st.line, vars)
            con!(c, st.name, l, st.op, r)
        end
    end

    # ═══════════ Snapshot objective function (QC_objective_function.mod) ═══════════
    extend! === nothing && @objective(m, Min, sum(TotalCost[y] for y in YEARS))

    v = merge(v0, extra)
    QCModel(m, S, v, c.att, c.triv)
end

end # module
