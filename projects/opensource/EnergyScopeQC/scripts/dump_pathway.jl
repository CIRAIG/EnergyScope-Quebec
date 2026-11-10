# Writes every parameter and set read by the parser to a TSV file, for comparison with AMPL.
# usage: julia --project=. scripts/dump_pathway.jl output.tsv
using EnergyScopeQC.AmplDat, EnergyScopeQC.QCFiles
out = ARGS[1]
db = load_dat_files(pathway_files(); defaults=read_param_defaults(mod_files()), derived=derived_sets())
fmt(x) = x isa AbstractFloat ? string(x) : string(x)
open(out, "w") do io
    for n in sort(collect(keys(db.params))), (k, v) in db.params[n]
        println(io, "P\t", n, "\t", join(fmt.(k), "\x1f"), "\t", v isa AbstractString ? v : repr(v))
    end
    for n in sort(collect(keys(db.sets))); v = db.sets[n]
        println(io, "S\t", n, "\t", join(fmt.(v), "\x1f"), "\t")
    end
    for n in sort(collect(keys(db.isets))), (k, v) in db.isets[n]
        println(io, "I\t", n, "\t", join(fmt.(k), "\x1f"), "\t", join(fmt.(v), "\x1f"))
    end
end
println("written: ", out, " (", length(db.params), " parameters)")
