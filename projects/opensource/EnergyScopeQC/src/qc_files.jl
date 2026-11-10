"""
Data files of ES-QC and the sets computed by the `.mod`.

The lists reproduce the loading order of `run_pathway` (shared/utils.py:267-291), `.mod` files excluded
(the `.mod` files contain no data; their `default` clauses are read by `read_param_defaults`).
"""
module QCFiles

using ..AmplDat

export repo_root, pathway_files, pathway_files_foresight, window_sets_text, load_pathway, load_pathway_base, snapshot_files, snapshot_sets_text, load_snapshot, mod_files, derived_sets

"Repository root of ES-QC (this package is in projects/opensource/EnergyScopeQC)."
repo_root() = normpath(joinpath(@__DIR__, "..", "..", "..", ".."))

function pathway_files(root=repo_root())
    m = joinpath(root, "projects", "pathway", "model"); d = joinpath(root, "shared", "data")
    [joinpath(m, "EXTRA_INFOS.dat"), joinpath(d, "QC_data.dat"),
     joinpath(d, "EUD", "out_eud.dat"), joinpath(d, "Techs", "out_techs.dat"), joinpath(d, "Shares", "out_shares.dat"),
     joinpath(m, "PES_data_pathway.dat"), joinpath(m, "PES_data_decom_allowed_2020.dat"),
     joinpath(m, "PES_data_years_active.dat"), joinpath(m, "PES_seq_opti.dat"),
     joinpath(m, "PES_data_set_AGE_2020.dat"), joinpath(m, "PES_data_remaining_wnd.dat")]
end

"""
Pathway files for **perfect foresight** (a single window over the whole horizon). Same order as `run_pathway`, except:
`PES_seq_opti.dat` (window sets) is replaced by `window_sets_text`, computed in memory, and `remaining_years`
is read from `PES_data_remaining.dat` (all phases): `run_pathway` rewrites these files at every run, so their content
on disk depends on the last calculation.
"""
function pathway_files_foresight(root=repo_root())
    m = joinpath(root, "projects", "pathway", "model"); d = joinpath(root, "shared", "data")
    [joinpath(m, "EXTRA_INFOS.dat"), joinpath(d, "QC_data.dat"),
     joinpath(d, "EUD", "out_eud.dat"), joinpath(d, "Techs", "out_techs.dat"), joinpath(d, "Shares", "out_shares.dat"),
     joinpath(m, "PES_data_pathway.dat"), joinpath(m, "PES_data_decom_allowed_2020.dat"),
     joinpath(m, "PES_data_years_active.dat"), joinpath(m, "PES_data_set_AGE_2020.dat"),
     joinpath(m, "PES_data_remaining.dat")]
end

"""
Sets of the single window (equivalent of `AmplPreProcessor.write_seq_opti(0)` with `N_year_opti=30`, no overlap):
all years but `YEAR_2015`, all phases but `2015_2020`, `YEAR_ONE` and `YEAR_ONE_NEXT` empty.
"""
function window_sets_text(db::DataStore)
    years = [string(y) for y in db.sets["YEARS"] if string(y) != "YEAR_2015"]
    phases = [string(p) for p in db.sets["PHASE"] if string(p) != "2015_2020"]
    "set YEARS_WND := $(join(years, ' ')); set PHASE_WND := $(join(phases, ' ')); " *
    "set YEARS_UP_TO := $(join(years, ' ')); set PHASE_UP_TO := $(join(phases, ' ')); " *
    "set YEAR_ONE; set YEAR_ONE_NEXT;"
end

"""
    load_pathway(; root, derived) -> DataStore

Pathway data for perfect foresight: files of `pathway_files_foresight`, then the window sets.
"""
function load_pathway(; root=repo_root(), derived=derived_sets())
    db = load_pathway_base(; root, derived)
    load_dat_string!(db, window_sets_text(db); name="<single window>")
    db
end

"""
    load_pathway_base(; root, derived) -> DataStore

Pathway data **without the window sets** (`YEARS_WND`, `PHASE_UP_TO`, `YEAR_ONE`...). Read once, then
copied (`deepcopy`) for each window of the myopic mode, which loads its own sets file (`PES_seq_opti.dat`).
`remaining_years` contains all phases: AMPL only keeps those of the window, but the values are the same.
"""
function load_pathway_base(; root=repo_root(), derived=derived_sets())
    db = DataStore(; defaults=read_param_defaults(mod_files(root)), decls=read_param_decls(mod_files(root)), derived)
    load_dat_files!(db, pathway_files_foresight(root))
    db
end

"""
Files of a snapshot run (shared/utils.py `load_snapshot`): the set of years reduced to `year`, then the
data of the year. For 2050 with `scenario=true`, the generic scenario is added last.
"""
function snapshot_files(year, root=repo_root(); scenario=true)
    d = joinpath(root, "shared", "data")
    files = [joinpath(d, "QC_data.dat"), joinpath(d, "Techs", "QC_techs_$year.dat"),
             joinpath(d, "Shares", "QC_shares_$year.dat"), joinpath(d, "EUD", "QC_eud_$year.dat")]
    year == 2050 && scenario && push!(files, joinpath(root, "shared", "scenarios", "QC_generic_scenario_2050.dat"))
    files
end

"""
`QC_set_snapshot.dat` is rewritten by `load_snapshot` at every call; the same content is generated here in memory
(without touching the file) and loaded before the others.
"""
snapshot_sets_text(year) =
    "set YEARS := YEAR_$year; set YEAR_ONE := ; set YEARS_WND := YEAR_$year; set YEARS_UP_TO := YEAR_$year;"

"""
    load_snapshot(year; scenario=true, root) -> DataStore

Data of a snapshot run: year sets reduced to `year`, then the files of the year, with the `default` clauses
of the `.mod` files. Equivalent of `load_snapshot` (shared/utils.py) on the data side.
"""
function load_snapshot(year; scenario=true, root=repo_root(), derived=derived_sets())
    db = DataStore(; defaults=read_param_defaults(mod_files(root)), decls=read_param_decls(mod_files(root)), derived)
    load_dat_string!(db, snapshot_sets_text(year); name="<snapshot sets $year>")
    load_dat_files!(db, snapshot_files(year, root; scenario))
end

"`.mod` files that declare the parameters (and their `default`)."
mod_files(root=repo_root()) = [joinpath(root, "shared", "model", "QC_es_main.mod"),
                               joinpath(root, "projects", "pathway", "model", "PES_main.mod")]

# QC_es_main.mod:52 and :70
ccus(db) = unique!(vcat(getset(db, "TECHNOLOGIES_OF_CC"), getset(db, "TECHNOLOGIES_OF_CCS"), getset(db, "TECHNOLOGIES_OF_CCU")))
function technologies(db)
    s = db.sets
    end_uses_types = unique!(Any[x for c in s["END_USES_CATEGORIES"] for x in db.isets["END_USES_TYPES_OF_CATEGORY"][(c,)]])
    from_types = Any[j for i in end_uses_types for j in db.isets["TECHNOLOGIES_OF_END_USES_TYPE"][(i,)]]
    unique!(vcat(from_types, s["STORAGE_TECH"], s["INFRASTRUCTURE"], getset(db, "TECHNOLOGIES_OF_CCUS"),
                 s["TECHNOLOGIES_OF_IND"], s["TECHNOLOGIES_OF_PRIVATEMOB_ALL_DISTANCES"],
                 s["TECHNOLOGIES_OF_PUBLICMOB_ALL_DISTANCES"], s["TECHNOLOGIES_OF_FREIGHTMOB_ALL_DISTANCES"]))
end
derived_sets() = Dict{String,Function}("TECHNOLOGIES" => technologies, "TECHNOLOGIES_OF_CCUS" => ccus)

end
