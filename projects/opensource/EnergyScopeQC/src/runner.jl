"""
    Runner

Complete pathway calculation (perfect foresight or myopic mode): reading the data, solving window by window, writing the
results as TSV. Called from Python through `juliacall` (`shared/julia_pathway.py`, `shared/julia_backend.py`).

    run = open_pathway(gap, outdir; overrides_file, changes, nwindows)
    solve_next!(run)        # solves the next window, writes results_<i>.tsv + done_<i>, returns the solver status

`nwindows == 0`: a single window over the whole horizon (perfect foresight), results in `results.tsv`.
`nwindows == N`: myopic mode, the sets of window i are read from `outdir/seq_<i>.dat` (the `PES_seq_opti.dat` written by
`AmplPreProcessor`); between two windows the past is fixed to the previous solution (`PESMain.carry_over`).

Output (key and element separator = \\x1f):
  META  <name> <value>              status, objective, times
  TABLE <variable> <key> <value>    values of the model variables (empty key for a scalar variable)
  PARAM <parameter> <key> <value>   parameters of the .dat files (explicit entries) + computed parameters (tau, end_uses_input)
  DEFAULT <parameter> <value>       `default` clause of the .mod
  SET   <set> <elements>            simple sets      |  ISET <set> <key> <elements>  indexed sets
"""
module Runner

using ..AmplDat, ..QCFiles, ..QCEsMain, ..PESMain
using JuMP, HiGHS

export PathwayRun, open_pathway, solve_next!, solve_snapshot

const SEP = "\x1f"
const Fix = NamedTuple{(:var, :key, :value, :file),Tuple{String,Tuple,Any,String}}

key_elem(s) = (v = tryparse(Int, s); v === nothing ? String(s) : v)
parse_value(s) = s == "Infinity" ? Inf : parse(Float64, s)
join_key(k) = join(string.(k), SEP)

mutable struct PathwayRun
    base::DataStore                                   # common data, read once
    gap::Float64
    time_limit::Float64                               # HiGHS time limit per window [s]
    outdir::String
    override_lines::Vector{Tuple{String,String,Tuple,Float64}}   # (ALL|ONE|MUL, name, key, value)
    changes::Vector{String}                           # .dat files of modifications
    nwindows::Int
    next::Int                                         # next window (0-based)
    carry::Vector{Fix}                                # past values to fix in the next window
    t_data::Float64
end

"""
    open_pathway(gap, outdir; overrides_file="", changes=String[], nwindows=0, time_limit=3600.0) -> PathwayRun

Reads the common data. `overrides_file`: user overrides, one line `type<TAB>name<TAB>key<TAB>value`
(`ALL`: everywhere, `ONE`: one entry, `MUL`: multiplies the entry), key separated by `\\x1f`.
"""
function open_pathway(gap, outdir; overrides_file="", changes=String[], nwindows=0, time_limit=3600.0)
    lines = read_override_lines(overrides_file)
    t_data = @elapsed base = load_pathway_base()
    PathwayRun(base, Float64(gap), Float64(time_limit), String(outdir), lines, String.(changes), Int(nwindows), 0, Fix[], t_data)
end

"Lines of the overrides file: (type, name, key, value). Missing or empty file: no override."
function read_override_lines(file)
    lines = Tuple{String,String,Tuple,Float64}[]
    if !isempty(file) && isfile(file)
        for line in eachline(file)
            isempty(strip(line)) && continue
            kind, name, key, val = split(line, '\t')
            push!(lines, (String(kind), String(name), kind == "ALL" ? () : Tuple(key_elem.(split(key, SEP))), parse_value(val)))
        end
    end
    lines
end

"Version called from Python (`juliacall`): `changes` = paths separated by newlines."
open_pathway(gap, outdir, overrides_file::AbstractString, changes::AbstractString, nwindows::Integer, time_limit::Real) =
    open_pathway(gap, outdir; overrides_file, changes=filter(!isempty, String.(split(changes, '\n'))), nwindows, time_limit)

resolve_overrides(run::PathwayRun, db) = resolve_overrides(run.override_lines, db)

function resolve_overrides(lines, db)
    overrides = Dict{String,Any}()
    for (kind, name, k, x) in lines
        if kind == "ALL"
            overrides[name] = x
        else
            kind == "MUL" && (x = getparam(db, name, k) * x)
            d = get!(overrides, name, Dict{Tuple,Any}())
            d isa Dict || error("override $name: mix of a scalar value and precise entries")
            d[k] = x
        end
    end
    overrides
end

"Data of one window: common base + window sets + modification files + overrides + carried-over values."
function window_db(run::PathwayRun, seqfile)
    db = deepcopy(run.base)
    seqfile === nothing ? load_dat_string!(db, window_sets_text(db); name="<single window>") : load_dat_files!(db, [seqfile])
    isempty(run.changes) || load_dat_files!(db, run.changes; strict=true)
    isempty(run.override_lines) || apply_overrides!(db, resolve_overrides(run, db))
    append!(db.fixes, run.carry)                      # after the `fix` of the .dat files, as AMPL reads fix.mod last
    db
end

"Builds and solves one window; returns (model, build time, solve time). HiGHS log in `logfile`."
function solve_window(run::PathwayRun, db, logfile)
    t_build = @elapsed M = build_pathway_model(db)
    set_optimizer(M.model, HiGHS.Optimizer)
    # phase 0 options (AMPL: mip:lpsolver=hipo mip:ipmsolver=hipo bar:crossover=off mip:gap=5e-4)
    for (name, val) in ("mip_rel_gap" => run.gap, "mip_lp_solver" => "hipo", "mip_ipm_solver" => "hipo",
                        "run_crossover" => "off", "time_limit" => run.time_limit, "threads" => 0, "log_file" => logfile,
                        "log_to_console" => false)
        set_attribute(M.model, name, val)
    end
    t_solve = @elapsed optimize!(M.model)
    M, t_build, t_solve
end

"Writes the TSV of a solved window."
function write_results(path, M, db, t_data, t_build, t_solve)
    v = M.v
    exported = Pair{String,Any}[]
    for nm in (:F_Mult, :F_Mult_t, :C_inv, :C_maint, :C_op, :TotalGWP, :TotalCost, :GWP_constr, :Annual_Prod, :Monthly_Prod,
               :End_Uses, :Storage_In, :Storage_Out, :F_new, :F_decom, :F_old, :C_inv_phase, :C_inv_phase_no_actu,
               :C_inv_phase_tech, :C_inv_phase_tech_no_actu, :C_op_phase_tech, :C_op_phase_tech_no_actu, :C_op_phase_res,
               :C_op_phase_res_no_actu, :C_inv_return, :C_inv_return_phase, :C_inv_phase_CRF, :C_opex, :C_tot_opex, :C_tot_capex,
               :TotalGWPTransition, :TotalTransitionCost, :Res, :Number_Of_Units)
        push!(exported, string(nm) => getproperty(v, nm))
    end
    for (k, name) in ("NG" => "STO_NG_LEVEL", "CO2" => "STO_CO2_LEVEL", "H2" => "STO_H2_LEVEL", "ELEC" => "STO_ELEC_LEVEL",
                      "DIE" => "STO_DIE_LEVEL", "GASO" => "STO_GASO_LEVEL")
        push!(exported, name => v.LEVEL[k])
    end

    open(path, "w") do io
        println(io, "META\tstatus\t", termination_status(M.model))
        println(io, "META\tt_data\t", t_data); println(io, "META\tt_build\t", t_build)
        println(io, "META\tt_solve\t", t_solve); println(io, "META\tt_solver\t", solve_time(M.model))
        has_values(M.model) || return
        println(io, "META\tobjective\t", repr(objective_value(M.model)))
        for (nm, arr) in exported
            if arr isa VariableRef
                println(io, "TABLE\t", nm, "\t\t", repr(value(arr)))
            else
                for k in Iterators.product(axes(arr)...)
                    println(io, "TABLE\t", nm, "\t", join_key(k), "\t", repr(value(arr[k...])))
                end
            end
        end

        # parameters: explicit entries of the .dat files, then parameters computed by the .mod (tau, end_uses_input)
        for (name, d) in db.params, (k, x) in d
            x isa Number && println(io, "PARAM\t", name, "\t", join_key(k), "\t", repr(Float64(x)))
        end
        S = M.S
        for y in S.YEARS, i in S.TECHNOLOGIES
            h, n = getparam(db, "i_hurdle", (y, i)), getparam(db, "lifetime", (y, i))
            println(io, "PARAM\ttau\t", join_key((y, i)), "\t", repr(h * (1 + h)^n / ((1 + h)^n - 1)))
        end
        for y in S.YEARS, i in db.sets["END_USES_INPUT"]
            println(io, "PARAM\tend_uses_input\t", join_key((y, i)), "\t",
                    repr(sum(getparam(db, "end_uses_demand_year", (y, i, s)) for s in S.SECTORS)))
        end
        for (name, x) in db.defaults
            x isa Number && println(io, "DEFAULT\t", name, "\t", repr(Float64(x)))
        end

        sets = Dict{String,Any}(string(k) => x for (k, x) in db.sets)
        for nm in (:TECHNOLOGIES, :LAYERS, :END_USES_TYPES, :RESOURCES)
            sets[string(nm)] = getfield(S, nm)
        end
        for (nm, x) in sets
            println(io, "SET\t", nm, "\t", join(string.(x), SEP))
        end
        for (nm, d) in db.isets, (k, x) in d
            println(io, "ISET\t", nm, "\t", join_key(k), "\t", join(string.(x), SEP))
        end
    end
end

"""
    solve_next!(run) -> String

Solves the next window and writes its results. Returns the solver status (`"OPTIMAL"`, `"INFEASIBLE"`...).
In myopic mode, the past is carried over in `run.carry`; a window without solution leaves `run.next` unchanged (the computation stops).
"""
function solve_next!(run::PathwayRun)
    i = run.next
    outdir = run.outdir
    if run.nwindows == 0                                       # perfect foresight: one window, results.tsv
        t_db = @elapsed db = window_db(run, nothing)
        M, t_build, t_solve = solve_window(run, db, joinpath(outdir, "highs.log"))
        write_results(joinpath(outdir, "results.tsv"), M, db, run.t_data + t_db, t_build, t_solve)
        run.next = 1
        return string(termination_status(M.model))
    end
    t_win = time()
    t_db = @elapsed db = window_db(run, joinpath(outdir, "seq_$i.dat"))
    M, t_build, t_solve = solve_window(run, db, joinpath(outdir, "highs_$i.log"))
    ok = has_values(M.model)
    ok && (run.carry = carry_over(M, db))
    write_results(joinpath(outdir, "results_$i.tsv"), M, db, i == 0 ? run.t_data + t_db : t_db, t_build, t_solve)
    write(joinpath(outdir, "done_$i"), "")
    status = string(termination_status(M.model))
    println("julia : window ", i + 1, "/", run.nwindows, " ", status, " in ", round(time() - t_win; digits=1), " s")
    flush(stdout)
    ok && (run.next = i + 1)
    status
end

"""
    solve_snapshot(year, gap, outdir; overrides_file="", changes=String[], scenario=true) -> String

Snapshot calculation (one year): reads the data, applies modifications and overrides, solves, writes
`outdir/results.tsv` (same META / TABLE / PARAM / SET / ISET lines as the pathway, for the tables useful to the post-processing
of energyscope). Returns the solver status.
"""
function solve_snapshot(year, gap, outdir; overrides_file="", changes=String[], scenario=true)
    t_data = @elapsed begin
        db = load_snapshot(year; scenario)
        isempty(changes) || load_dat_files!(db, changes; strict=true)
        lines = read_override_lines(overrides_file)
        isempty(lines) || apply_overrides!(db, resolve_overrides(lines, db))
    end
    t_build = @elapsed M = build_qc_model(db)
    set_optimizer(M.model, HiGHS.Optimizer)
    set_attribute(M.model, "mip_rel_gap", Float64(gap))
    set_silent(M.model)
    t_solve = @elapsed optimize!(M.model)

    open(joinpath(outdir, "results.tsv"), "w") do io
        println(io, "META\tstatus\t", termination_status(M.model))
        println(io, "META\tt_data\t", t_data)
        println(io, "META\tt_build\t", t_build)
        println(io, "META\tt_solve\t", t_solve)
        println(io, "META\tt_solver\t", solve_time(M.model))     # HiGHS solver time only
        if has_values(M.model)
            println(io, "META\tobjective\t", repr(objective_value(M.model)))
            tables = ("F_Mult" => M.v.F_Mult, "F_Mult_t" => M.v.F_Mult_t, "Annual_Prod" => M.v.Annual_Prod,
                      "Annual_Res" => M.v.Annual_Res, "TotalCost" => M.v.TotalCost, "TotalGWP" => M.v.TotalGWP,
                      "C_inv" => M.v.C_inv, "C_maint" => M.v.C_maint, "C_op" => M.v.C_op)
            for (nm, arr) in tables, k in Iterators.product(axes(arr)...)
                println(io, "TABLE\t", nm, "\t", join_key(k), "\t", repr(value(arr[k...])))
            end

            # Parameters needed by the energyscope post-processing (same content as parse_result on the AMPL side)
            for y in M.S.YEARS, i in M.S.TECHNOLOGIES
                h, n = getparam(db, "i_hurdle", (y, i)), getparam(db, "lifetime", (y, i))
                println(io, "PARAM\ttau\t", join_key((y, i)), "\t", repr(h * (1 + h)^n / ((1 + h)^n - 1)))
            end
            for t in M.S.PERIODS
                println(io, "PARAM\tt_op\t", t, "\t", repr(getparam(db, "t_op", (t,))))
            end
            for name in ("layers_in_out", "end_uses_demand_year"), (k, v) in db.params[name]
                v isa Number && v != 0 && println(io, "PARAM\t", name, "\t", join_key(k), "\t", repr(Float64(v)))
            end

            # Sets (the sets computed by the .mod come from M.S)
            sets = Dict{String,Any}(string(k) => v for (k, v) in db.sets)
            for nm in (:TECHNOLOGIES, :LAYERS, :END_USES_TYPES, :RESOURCES)
                sets[string(nm)] = getfield(M.S, nm)
            end
            for (nm, v) in sets
                println(io, "SET\t", nm, "\t", join(string.(v), SEP))
            end
            for (nm, d) in db.isets, (k, v) in d
                println(io, "ISET\t", nm, "\t", join_key(k), "\t", join(string.(v), SEP))
            end
        end
    end
    string(termination_status(M.model))
end

"Version called from Python (`juliacall`): `changes` = paths separated by newlines."
solve_snapshot(year::Integer, gap, outdir::AbstractString, overrides_file::AbstractString, changes::AbstractString, scenario::Bool) =
    solve_snapshot(year, gap, outdir; overrides_file, changes=filter(!isempty, String.(split(changes, '\n'))), scenario)

end # module
