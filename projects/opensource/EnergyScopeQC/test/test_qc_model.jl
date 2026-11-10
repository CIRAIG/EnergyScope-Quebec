# Static JuMP model (snapshot). No parameter value is checked: only that the model builds, solves, and that
# constraints added by the user are taken into account.
using JuMP, HiGHS
using EnergyScopeQC.QCEsMain

@testset "user constraints (subject to)" begin
    db = parse_load("subject to c1 {y in YEARS}: F[y] >= 2*x + 1; subject to c2: F['a'] = 3;"; derived=Dict{String,Function}())
    @test length(db.constraints) == 2
    @test db.constraints[1].stmt.name == "c1" && db.constraints[1].stmt.op == :>=
    @test db.constraints[2].stmt.op == :(==)
    @test_throws DatSyntaxError parse_load("subject to c3: 1 <= F['a'] <= 2;")      # double relation rejected
    @test_throws DatSyntaxError parse_load("subject to c4: F['a'] 3;")              # no relation
end

@testset "snapshot model: construction, solve, user constraint" begin
    root = repo_root()
    if !all(isfile, vcat(snapshot_files(2020, root), mod_files(root)))
        @info "ES-QC files not found: model test skipped"
    else
        db = load_snapshot(2020)
        # user constraint: a relation on a model variable, written as in a scenario file
        load_dat_string!(db, "subject to test_extra {y in YEARS}: Annual_Prod[y,'HYDRO_RIVER'] >= 0;"; name="<test>")
        load_dat_string!(db, "subject to test_sum {y in YEARS}: sum {i in TECHNOLOGIES} F_Mult[y,i] >= 0;"; name="<test>")
        M = build_qc_model(db)
        @test M.attempted["test_extra"] == 1
        @test M.attempted["test_sum"] == 1
        # unknown technology in a constraint: the message names the bad value and suggests one
        db2 = load_snapshot(2020)
        load_dat_string!(db2, "subject to bad {y in YEARS}: F_Mult[y,'WIND_ONSHOR'] >= 0;"; name="<test>")
        err = try build_qc_model(db2); nothing catch e; e end
        @test err isa DatSyntaxError
        @test occursin("WIND_ONSHOR", err.msg) && occursin("did you mean", err.msg)
        @test num_variables(M.model) > 0
        set_optimizer(M.model, HiGHS.Optimizer); set_silent(M.model)
        optimize!(M.model)
        @test termination_status(M.model) == MOI.OPTIMAL
        @test isfinite(objective_value(M.model))
        # the objective is the sum of the costs
        @test objective_value(M.model) ≈ sum(value(M.v.TotalCost[y]) for y in M.S.YEARS) rtol = 1e-6
    end
end
