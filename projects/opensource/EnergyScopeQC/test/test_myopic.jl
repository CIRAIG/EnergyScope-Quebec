# Myopic mode: `carry_over` (values to fix in the next window). Small hand-made model: no value of the
# real .dat files is used, the test is instantaneous.
using JuMP, HiGHS
using EnergyScopeQC.PESMain

@testset "carry_over: variables and sets carried between two windows" begin
    TECH, RES, PERIODS = ["A", "B"], ["R"], [1, 2]
    YU, PU = ["Y1", "Y2"], ["P1"]
    m = Model()
    @variable(m, F_Mult[YU, TECH]); @variable(m, F_new[["P1", "2020_2025"], TECH]); @variable(m, F_old[PU, TECH])
    @variable(m, F_decom[PU, ["P1", "2015_2020", "2020_2025"], TECH]); @variable(m, F_used_year_start[["Y3"], TECH])
    @variable(m, Res[YU, RES]); @variable(m, Res_t[YU, RES, PERIODS])
    v = (; F_Mult, F_new, F_old, F_decom, F_used_year_start, Res, Res_t)

    # a different value per entry, so that a mix-up of variable or index shows
    expected = Dict{Tuple{String,Tuple},Float64}()
    k = 0.0
    for (name, arr) in pairs(v), idx in Iterators.product(axes(arr)...)
        k += 1
        fix(arr[idx...], k; force=true)
        expected[(string(name), idx)] = k
    end
    @objective(m, Min, 0)
    set_optimizer(m, HiGHS.Optimizer); set_silent(m); optimize!(m)

    db = DataStore()
    db.sets["PHASE_UP_TO"] = Any["P1"]
    db.sets["YEAR_ONE_NEXT"] = Any["Y3"]
    M = (; S=(; TECHNOLOGIES=TECH, RESOURCES=RES, PERIODS=PERIODS, YEARS_UP_TO=YU), v)
    out = carry_over(M, db)

    names = Set(f.var for f in out)
    @test names == Set(["F_Mult", "F_new", "F_old", "F_decom", "F_used_year_start", "Res", "Res_t"])  # model names, not *_up_to nor *_next
    n_of(name) = count(f -> f.var == name, out)
    @test n_of("F_Mult") == 4                 # YEARS_UP_TO x TECHNOLOGIES
    @test n_of("F_new") == 4                  # (PHASE_UP_TO union {2020_2025}) x TECHNOLOGIES
    @test n_of("F_old") == 2                  # PHASE_UP_TO x TECHNOLOGIES
    @test n_of("F_decom") == 6                # PHASE_UP_TO x (PHASE_UP_TO union {2015_2020, 2020_2025}) x TECHNOLOGIES
    @test n_of("F_used_year_start") == 2      # YEAR_ONE_NEXT x TECHNOLOGIES
    @test n_of("Res") == 2 && n_of("Res_t") == 4
    @test length(out) == length(expected)
    for f in out
        @test f.value == expected[(f.var, f.key)]    # each entry keeps the value of its own variable
    end
end
