# Builds the JuMP pathway model (perfect foresight) and writes the number of instances of each constraint.
# usage: julia --project=. scripts/dump_pathway_counts.jl output.tsv [PES_seq_opti.dat of a myopic window]
# TSV output: NVARS <n> | CON <name> <instances> <omitted>
using EnergyScopeQC.AmplDat, EnergyScopeQC.QCFiles, EnergyScopeQC.QCEsMain, EnergyScopeQC.PESMain
using JuMP

if length(ARGS) >= 2
    db = load_pathway_base(); load_dat_files!(db, [ARGS[2]])
else
    db = load_pathway()
end
M = build_pathway_model(db)
open(ARGS[1], "w") do io
    println(io, "NVARS\t", num_variables(M.model))
    for (n, k) in sort(collect(M.attempted)); println(io, "CON\t", n, "\t", k, "\t", get(M.trivial, n, 0)); end
end
println("julia: ", num_variables(M.model), " variables, ", length(M.attempted), " constraint families")
