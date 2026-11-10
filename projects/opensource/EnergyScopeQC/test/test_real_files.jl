# Tests on the real ES-QC .dat files. NO parameter value is checked here: users must be free to change
# them (SDR, i_hurdle, per-technology parameters...). Only structural properties are checked. Values are validated
# (a) on the frozen fixtures (test/fixtures) and (b) by the full comparison with AMPL (tests/, Python side).

using EnergyScopeQC.QCFiles

@testset "real files: structure only" begin
    pw, sn = pathway_files(), snapshot_files(2030)
    if !all(isfile, vcat(pw, sn))
        @info "ES-QC files not found: real-file test skipped"
    else
        defaults = read_param_defaults(mod_files())

        # 1. the whole pathway set is readable: no syntax error, no read before definition
        db = load_dat_files(pw; defaults, derived=derived_sets())
        @test !isempty(db.params) && !isempty(db.sets)

        # 2. the snapshot is readable and contains no PES_* file (the two modes are isolated)
        snap = load_dat_files(sn; defaults, derived=derived_sets())
        @test !isempty(snap.params)
        @test !any(f -> occursin("PES_", basename(f)), values(snap.provenance))

        # 3. no shared state: loading the snapshot twice gives the same result
        snap2 = load_dat_files(sn; defaults, derived=derived_sets())
        @test snap.params == snap2.params && snap.sets == snap2.sets

        # 4. no parameter mixes keys of different arity
        for (name, d) in db.params
            @test length(unique(length.(keys(d)))) == 1
        end
    end
end
