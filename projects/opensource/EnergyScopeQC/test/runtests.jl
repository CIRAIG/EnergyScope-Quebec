using Test
using EnergyScopeQC.AmplDat

parse_load(txt; derived=Dict{String,Function}(), defaults=Dict{String,Any}()) = begin
    db = DataStore(; derived, defaults)
    tmp = tempname() * ".dat"
    write(tmp, txt)
    try load_dat_files!(db, [tmp]) finally rm(tmp; force=true) end
    db
end

@testset "comments" begin
    @test strip(strip_comments("a # c\nb")) == "a \nb"
    @test occursin("let x", strip_comments("/* \n let y := 1; \n*/ let x := 2;"))
    @test !occursin("let y", strip_comments("/* \n let y := 1; \n*/ let x := 2;"))
    # line numbers are preserved
    @test count(==('\n'), strip_comments("/*\n\n*/\nx")) == 3
    # # and /* inside a string are not comments
    @test occursin("a#b", strip_comments("let p['a#b'] := 1;"))
    @test_throws DatSyntaxError strip_comments("let x := 1;\n/* never closed\nlet y := 2;")
end

@testset "comments: commented-out parameters are not passed on" begin
    db = parse_load("""
        let a := 1;
        /* let b := 2;
           let c := 3; */
        # let d := 4;
        let e := 5; # let f := 6;
        """)
    @test sort(collect(keys(db.params))) == ["a", "e"]
end

@testset "let / sets / param" begin
    db = parse_load("""
        data;
        set YEARS := YEAR_2020 YEAR_2025;
        set PERIODS := 1 2 3;
        set PHASE_START["2020_2025"] := YEAR_2020;
        set YEAR_ONE;
        param n := 7;
        param: l :=
        A 1.5   # comment
        B 2e-3;
        param t : P1 P2 :=
        r1 1 2
        r2 3 .
        ;
        let t_op[1] := 744 ;
        let x['YEAR_2020','AFC'] := 1988.27*1.0 ;
        let co2 := Infinity;
        """)
    @test db.sets["YEARS"] == ["YEAR_2020", "YEAR_2025"]
    @test db.sets["PERIODS"] == [1, 2, 3]
    @test db.isets["PHASE_START"][("2020_2025",)] == ["YEAR_2020"]
    @test db.sets["YEAR_ONE"] == []
    @test getparam(db, "n") == 7.0
    @test getparam(db, "l", ("B",)) == 2e-3
    @test getparam(db, "t", ("r1", "P2")) == 2.0
    @test !haskey(db.params["t"], ("r2", "P2"))       # '.' = missing value
    @test getparam(db, "t_op", (1,)) == 744.0
    @test getparam(db, "x", ("YEAR_2020", "AFC")) ≈ 1988.27
    @test getparam(db, "co2") == Inf
end

@testset "slices [A,*,*]" begin
    db = parse_load("""
        param ya :=
        [AFC, *, *] : 2015_2020 2020_2025 :=
        2015_2020 2.5 5
        2020_2025 0.0 2.5
        [BAT, *, *] : 2015_2020 2020_2025 :=
        2015_2020 1 1
        ;
        """)
    @test getparam(db, "ya", ("AFC", "2015_2020", "2020_2025")) == 5.0
    @test getparam(db, "ya", ("AFC", "2020_2025", "2020_2025")) == 2.5
    @test getparam(db, "ya", ("BAT", "2015_2020", "2015_2020")) == 1.0
end

@testset "for loops / let with domain" begin
    db = parse_load("""
        set YEARS := YEAR_2020 YEAR_2025 YEAR_2030;
        set TECH := A B;
        let c['YEAR_2020','A'] := 4;
        for {i in TECH} { let c['YEAR_2015', i] := 9; }
        for {y in YEARS diff {"YEAR_2020","YEAR_2025"}}{
            let s[y] := 0.5 ;
            for {t in TECH} { let f[y,t] := c['YEAR_2020','A'] * 2; }
        }
        let {y in YEARS} SDR[y] := 0.0285;
        let {y in YEARS, i in TECH} h[y,i] := 0.06;
        fix F['2025_2030','W'] := 0;
        """)
    @test getparam(db, "c", ("YEAR_2015", "B")) == 9.0
    @test !haskey(db.params["s"], ("YEAR_2020",))
    @test getparam(db, "s", ("YEAR_2030",)) == 0.5
    @test getparam(db, "f", ("YEAR_2030", "A")) == 8.0
    @test length(db.params["SDR"]) == 3
    @test length(db.params["h"]) == 6
    @test db.fixes[1].var == "F" && db.fixes[1].key == ("2025_2030", "W")
end

@testset "sum {domain} expression" begin
    pre = "set T := A B C; let c['A'] := 1; let c['B'] := 2; let c['C'] := 3;\n"
    val(expr, name="x") = getparam(parse_load(pre * "let $name := $expr;"), name)
    @test val("sum {t in T} c[t]") == 6.0
    @test val("sum {t in T diff {'A'}} c[t]") == 5.0
    @test val("sum {t in T, u in T} c[t] * c[u]") == 36.0
    @test val("sum {t in T} sum {u in T} c[t] * c[u]") == 36.0
    @test val("1 + sum {t in T} c[t]") == 7.0
    @test val("2 * sum {t in T} c[t]") == 12.0
    @test val("sum {t in T} c[t] + 1") == 9.0           # the operand extends over `+` (AMPL precedence)
    @test val("(sum {t in T} c[t]) + 1") == 7.0
    @test val("sum {t in {'A','C'}} c[t]") == 4.0
    @test val("sum {t in {}} c[t]") == 0.0
    # the summation variable hides a loop variable of the same name only inside the sum
    db = parse_load(pre * "for {t in T} { let w[t] := sum {t in T} c[t]; }")
    @test all(v == 6.0 for v in values(db.params["w"]))
    # in a constraint
    db = parse_load(pre * "subject to s1 {y in T}: sum {t in T} c[t] >= 2;")
    @test length(db.constraints) == 1 && db.constraints[1].stmt.name == "s1"
    @test_throws DatSyntaxError parse_load(pre * "let x := sum {t in T c[t];")      # unclosed brace
end

@testset "derived sets (computed by the .mod)" begin
    txt = "for {i in TECHNOLOGIES} { let lt['Y', i] := 1; }"
    @test_throws DatSyntaxError parse_load(txt)
    db = parse_load(txt; derived=Dict("TECHNOLOGIES" => _ -> ["X", "Y"]))
    @test length(db.params["lt"]) == 2
end

@testset "syntax errors" begin
    @test_throws DatSyntaxError parse_load("let x := 1")                  # no ;
    @test_throws DatSyntaxError parse_load("var x;")                      # unknown statement
    @test_throws DatSyntaxError parse_load("let y := z[1];")              # read before definition
    e = try parse_load("let a := 1;\nlet b := ;\n") catch e; e end
    @test e isa DatSyntaxError && e.line == 2
end

@testset "overwrites between files" begin
    f1 = tempname() * ".dat"; f2 = tempname() * ".dat"
    write(f1, "let a[1] := 1;\nlet b := 5;\n")
    write(f2, "let a[1] := 2;\nlet b := 5;\nlet a[1] := 3;\n")   # 2 then 3 in the same file
    db = load_dat_files([f1, f2])
    @test getparam(db, "a", (1,)) == 3.0
    ow = db.overwrites
    @test length(ow) == 2          # a:1→2 and b:5→5 (unchanged); a:2→3 stays within the same file, not logged
    @test count(o -> o.changed, ow) >= 1
    @test any(o -> o.param == "b" && !o.changed, ow)
    rm(f1); rm(f2)
end

@testset "default values of the .mod" begin
    f = tempname() * ".mod"
    write(f, "param c {YEARS,T} >= 0 default 0; # x
param l {YEARS} default 20;
param z {T};
param k default Infinity;
")
    d = read_param_defaults([f]); rm(f)
    @test d == Dict("c" => 0.0, "l" => 20.0, "k" => Inf)
    db = parse_load("let a['x'] := b['y'];"; defaults=Dict{String,Any}("b" => 7.0))
    @test getparam(db, "a", ("x",)) == 7.0
end

@testset "frozen fixtures (base + scenario)" begin
    fx = joinpath(@__DIR__, "fixtures")
    db = load_dat_files([joinpath(fx, "base.dat"), joinpath(fx, "scenario.dat")])
    @test getparam(db, "SDR", ("YEAR_2020",)) == 0.04            # base: SDR_base * 2 (reference to a scalar)
    @test getparam(db, "SDR", ("YEAR_2030",)) == 0.5             # scenario overwrites base
    @test getparam(db, "i_hurdle", ("YEAR_2030", "WIND")) == 0.09
    @test getparam(db, "i_hurdle", ("YEAR_2030", "PV")) == 0.06
    @test getparam(db, "c_inv", ("YEAR_2020", "WIND")) == 1000.0  # /* */ block of the scenario ignored
    @test getparam(db, "c_inv", ("YEAR_2025", "PV")) == 300.0     # for loop with diff, reads c_inv already defined
    @test getparam(db, "c_inv", ("YEAR_2020", "PV")) == 700.0     # 2020 excluded by diff
    @test !haskey(db.params["c_inv"], ("YEAR_2030", "BATTERY"))   # '.' = missing
    @test getparam(db, "f_max_tab", ("WIND", "YEAR_2025", "YEAR_2020")) == 7.0
    @test length(db.fixes) == 1 && db.fixes[1].var == "F_new"
    @test Set(o.param for o in db.overwrites if o.changed) == Set(["SDR", "i_hurdle", "c_inv"])
end

@testset "user overrides" begin
    fx = joinpath(@__DIR__, "fixtures")
    db = load_dat_files([joinpath(fx, "base.dat")])
    apply_overrides!(db, Dict(
        "SDR" => 0.03,                                                   # broadcast to every year
        "i_hurdle" => Dict(("YEAR_2030", "WIND") => 0.08),              # precise entry
        "c_inv" => Dict(("YEAR_2030", "ELECTROLYSER") => 450.0)))       # new technology
    @test all(v == 0.03 for v in values(db.params["SDR"]))
    @test getparam(db, "i_hurdle", ("YEAR_2030", "WIND")) == 0.08
    @test getparam(db, "i_hurdle", ("YEAR_2025", "WIND")) == 0.06       # the rest is untouched
    @test getparam(db, "c_inv", ("YEAR_2030", "ELECTROLYSER")) == 450.0
    @test any(o -> o.param == "SDR" && o.new_file == "<overrides>", db.overwrites)
    # indexed parameter WITHOUT explicit entry (e.g. i_hurdle in snapshot): the scalar replaces the `default`
    db2 = DataStore(; defaults=Dict{String,Any}("i_hurdle" => 0.04))
    apply_overrides!(db2, Dict("i_hurdle" => 0.08))
    @test getparam(db2, "i_hurdle", ("YEAR_2030", "WIND")) == 0.08
    @test getparam(db2, "i_hurdle", ("YEAR_2020", "PV")) == 0.08
    @test_throws ErrorException apply_overrides!(db, Dict("SDRR" => 0.1))                 # typo
    @test_throws ErrorException apply_overrides!(db, Dict("c_inv" => Dict(("YEAR_2030",) => 1.0)))  # wrong arity
end

@testset "validation of user files (strict)" begin
    modfile = tempname() * ".mod"
    write(modfile, """
        param c_inv {YEARS,TECHNOLOGIES} >= 0 default 0;
        param share {YEARS} default 1;
        param scal default 3;
        param phased {PHASE union {'2015_2020'}, TECHNOLOGIES};
        param total_time := 5;
        """)
    decls = read_param_decls([modfile]); rm(modfile)
    @test decls["c_inv"] == ["YEARS", "TECHNOLOGIES"]
    @test decls["scal"] == String[]
    @test decls["phased"] == [nothing, "TECHNOLOGIES"]

    function strict_load(text; strict=true)
        db = DataStore(; decls, derived=Dict{String,Function}("TECHNOLOGIES" => _ -> ["WIND_ONSHORE", "PV"]))
        load_dat_string!(db, "set YEARS := YEAR_2020 YEAR_2030;"; name="<sets>")
        f = tempname() * ".dat"; write(f, text)
        try load_dat_files!(db, [f]; strict) finally rm(f; force=true) end
        db
    end
    msg(text) = (try strict_load(text); "" catch e; e isa DatSyntaxError ? e.msg : rethrow() end)

    @test getparam(strict_load("let c_inv['YEAR_2020','PV'] := 5;"), "c_inv", ("YEAR_2020", "PV")) == 5.0
    @test getparam(strict_load("let scal := 4;"), "scal") == 4.0
    @test getparam(strict_load("for {y in YEARS, i in TECHNOLOGIES} { let c_inv[y,i] := 1; }"), "c_inv", ("YEAR_2030", "PV")) == 1.0
    @test getparam(strict_load("let c_inv['YEAR_2099','PV'] := 5;"), "c_inv", ("YEAR_2099", "PV")) == 5.0   # time sets are not checked
    m = msg("let c_invv['YEAR_2020','PV'] := 5;")
    @test occursin("unknown parameter 'c_invv'", m) && occursin("did you mean 'c_inv'", m)
    m = msg("let c_inv['YEAR_2020','WIND_ONSHOR'] := 5;")
    @test occursin("'WIND_ONSHOR' is not in TECHNOLOGIES", m) && occursin("did you mean 'WIND_ONSHORE'", m)
    @test occursin("is not in TECHNOLOGIES", msg("let c_inv['YEAR_2020','wind_onshore'] := 5;"))
    @test occursin("expects 2 index", msg("let c_inv['PV'] := 5;"))
    @test occursin("expects 2 index", msg("let c_inv['YEAR_2020','PV','x'] := 5;"))
    @test occursin("expects 0 index", msg("let scal['x'] := 5;"))
    e = try strict_load("# comment\n\nlet c_invv['YEAR_2020','PV'] := 5;"); nothing catch e; e end
    @test e isa DatSyntaxError && e.line == 3
    # the standard data files are not validated: same statements are accepted without `strict`
    @test getparam(strict_load("let c_invv['a'] := 1;"; strict=false), "c_invv", ("a",)) == 1.0
end

@testset "robustness of the reader" begin
    @test getparam(parse_load("﻿# comment\nlet a := 1;\n"), "a") == 1.0                     # byte order mark
    @test getparam(parse_load("# c\r\nlet a := 1;\r\n"), "a") == 1.0                              # CRLF
    e = try parse_load("let a := 1/0;") catch e; e end
    @test e isa DatSyntaxError && occursin("division by zero", e.msg)
    e = try parse_load("let a := 1,5;") catch e; e end
    @test e isa DatSyntaxError && occursin("decimal comma", e.msg)
    e = try parse_load("let a['x'] := 1; let b[“x”] := 2;") catch e; e end
    @test e isa DatSyntaxError && occursin("typographic quotes", e.msg)
end

include("test_real_files.jl")
include("test_qc_model.jl")
include("test_myopic.jl")
