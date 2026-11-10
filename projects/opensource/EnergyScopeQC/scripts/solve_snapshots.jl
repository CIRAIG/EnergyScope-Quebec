# Builds and solves the JuMP snapshot model for several years in ONE Julia process
# (compilation is paid once); writes one TSV per year in the output folder.
# usage: julia --project=. scripts/solve_snapshots.jl output_folder gap year [year ...]
using EnergyScopeQC.AmplDat, EnergyScopeQC.QCFiles, EnergyScopeQC.QCEsMain
using JuMP, HiGHS
outdir, gap = ARGS[1], parse(Float64, ARGS[2])
for year in parse.(Int, ARGS[3:end])
    db = load_snapshot(year)
    M = build_qc_model(db)
    set_optimizer(M.model, HiGHS.Optimizer)
    set_attribute(M.model, "mip_rel_gap", gap)
    set_silent(M.model)
    optimize!(M.model)
    open(joinpath(outdir, "jl_$year.tsv"), "w") do io
        println(io, "STATUS\t", termination_status(M.model))
        println(io, "OBJECTIVE\t", repr(objective_value(M.model)))
        println(io, "NVARS\t", num_variables(M.model))
        for (n, k) in sort(collect(M.attempted)); println(io, "CON\t", n, "\t", k); end
    end
    println("julia: ", year, " done"); flush(stdout)
end
