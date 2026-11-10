# Keeping the Julia port up to date with the AMPL model

The AMPL model (`.mod` files and `.dat` data) is the reference. The Julia package `EnergyScopeQC` reads the same `.dat` files
but re-implements the `.mod` files in JuMP. This page lists what to update on the Julia side when something changes in AMPL.

Commands below are run from the repository root. The Julia executable is taken from the environment variable `JULIA`, or `julia` on the PATH.

## Quick table

| You changed in AMPL | Update on the Julia side | Check |
|---|---|---|
| A **value** in an existing `.dat` file | Nothing | none needed |
| A new element in an existing set (e.g. a new technology) in a `.dat` file | Nothing, unless it must belong to a computed set (next row) | `tests/compare_dat_with_ampl.py` |
| The definition of a **computed set** in a `.mod` (`TECHNOLOGIES`, `TECHNOLOGIES_OF_CCUS`) | `technologies()` / `ccus()` in `src/qc_files.jl`, and `build_sets` in `src/QC_es_main.jl` | `tests/compare_snapshot_with_ampl.py` |
| A new **parameter** declared in `QC_es_main.mod` or `PES_main.mod` | Read it with `P("name")` where it is used (`src/QC_es_main.jl` or `src/PES_main.jl`). Its `default` clause is read automatically. A parameter declared in any other `.mod` is not seen: add the file to `mod_files()` in `src/qc_files.jl` | `tests/compare_dat_with_ampl.py` |
| A new **variable** | Declare it in `src/QC_es_main.jl` or `src/PES_main.jl`; add it to the export list in `write_results` (`src/runner.jl`) if Python must read it; add it to the `vars` dictionary at the end of `build_qc_model` if users' `subject to` constraints must see it; regenerate the signature (below) | `tests/compare_snapshot_with_ampl.py`, `tests/compare_pathway_with_ampl.py` |
| A new or modified **constraint** | Edit the same-named constraint in `src/QC_es_main.jl` or `src/PES_main.jl`. Keep the name: instance counts are compared by name | both compare scripts above |
| The **objective** (`QC_objective_function.mod`, `PES_obj_pathway.mod`) | End of `build_qc_model` (snapshot) or `add_pes!` (pathway) | objective values in the compare scripts |
| **Indices** of an existing variable, parameter or set (e.g. `C_inv{YEARS,TECHNOLOGIES}` becomes `C_inv{YEARS,TECHNOLOGIES,X}`) | The Julia code, and regenerate the signature (below) | both compare scripts |
| The **order or list of data files** loaded by `load_snapshot` or `run_pathway` (`shared/utils.py`) | The matching list in `src/qc_files.jl` (`snapshot_files`, `pathway_files_foresight`, `pathway_files`). The order matters: the last file wins | `tests/compare_dat_with_ampl.py` |
| A new data file | Add it to the same lists in `src/qc_files.jl` | `tests/compare_dat_with_ampl.py` |
| The **phases or calendar** (`PHASE`, `2015_2020`, `2020_2025`) | `carry_over` in `src/PES_main.jl` and `window_sets_text` in `src/qc_files.jl` contain phase names | `compare_pathway_with_ampl.py`, `test/test_myopic.jl` |
| **Solver options** in `shared/utils.py` | Julia has its own options: `solve_window` and `solve_snapshot` in `src/runner.jl` | a short run |
| A scenario file using AMPL syntax the parser does not know | A `DatSyntaxError` gives file and line; extend `src/ampl_dat.jl` | `julia --project=projects/opensource/EnergyScopeQC projects/opensource/EnergyScopeQC/test/runtests.jl` |
| Plotting or post-processing in Python | Nothing (they work on the same result objects) | none needed |
| **Any change** in a file of `MODEL_FILES` (`shared/julia_backend.py`: the `.mod` files the port re-implements) | After the rows above are done and the checks pass: record the new state, as explained in the next section | `python projects/opensource/tests/update_port_reference.py` |

## The "Julia version out of date" warning

**Why it exists.** The model exists twice: the AMPL version (the reference, the one you edit) and the Julia version (the free copy
used by partners). Both must describe the same model. If someone edits a `.mod` file and nobody makes the same edit in Julia, the two
versions silently drift apart. The warning is there to avoid that.

**How it works.** `projects/opensource/EnergyScopeQC/data/mod_hashes.json` stores a short code for each of the 6 `.mod` files, computed from
the content of the file (change one letter and the code changes). It was recorded when Julia and AMPL were identical. The code of
each file is recomputed and compared with the stored one:
* on every pull request that touches one of these `.mod` files, GitHub shows a warning (it never blocks the pull request);
* the first time a Julia calculation starts in a Python session, the user sees the warning
  "The AMPL model changed since the Julia version was last checked against it (...)".

**Any edit triggers it, even a comment or a space.**

**What to do when you get the warning**

1. *You only changed a comment, a space or the layout of a `.mod` file.* The model is the same, so Julia needs no change. Go to step 3.
2. *You really changed the model* (a constraint, a parameter, a variable, the objective...). First update the Julia code: find your type of
   change in the table at the top of this page, do what it says, and run the check it lists. Then go to step 3.
3. *Record the new state*, from the root of the repository:

   ```
   python projects/opensource/tests/update_port_reference.py
   ```

   This rewrites `mod_hashes.json`. Commit it in the same pull request as the `.mod` file. The warning is gone.

Run the command only when Julia really matches the new AMPL files: it does not check anything, it only records the current state and
silences the warning. To cover another `.mod` file, add it to `MODEL_FILES` in `shared/julia_backend.py`.

## Regenerating the signature

`projects/opensource/EnergyScopeQC/data/ampl_signature.json` stores, for each variable, parameter and set, the sets that index it.
Python uses it to name the index levels of the result tables exactly as AMPL does.

Regenerate it when a `.mod` declaration changes (new variable, parameter or set, or modified indices). It does **not** change when an element
is added to an existing set.

```
python projects/opensource/tests/dump_ampl_signature.py
```

The script prints where it wrote `ampl_signature.json` (the temporary folder). Copy it to
`projects/opensource/EnergyScopeQC/data/ampl_signature.json`.

## Checks

| Script | What it verifies |
|---|---|
| `python projects/opensource/tests/compare_dat_with_ampl.py` | Every parameter and set read by Julia equals what AMPL loads |
| `python projects/opensource/tests/compare_snapshot_with_ampl.py` | Snapshot: number of variables, number of instances of each constraint, objective, for 2020 to 2050 |
| `python projects/opensource/tests/compare_pathway_with_ampl.py [N_year_opti N_year_overlap window]` | Pathway: same structural comparison, perfect foresight or one myopic window |
| `python projects/opensource/tests/check_port.py` | Julia tests, then the snapshot comparison |
| `python -m pytest projects/opensource/tests/test_julia_pathway.py` | Python side of the Julia backend (fast) |

The comparison scripts need AMPL and amplpy. The AMPL result of the snapshot comparison is cached and recomputed
automatically when an input file changes; `--refresh` forces it.

## Known limits of the Julia port

- The `let` statements of the files given by users (`my_changes.dat`, `extra_files`) are validated against the `param`
  declarations of `QC_es_main.mod` and `PES_main.mod`: unknown parameter, wrong number of indices, or an index that does not
  belong to its set (time sets are not checked) stop the run with the file and line. A parameter declared in another `.mod`
  file must be added to `mod_files()` in `src/qc_files.jl` to be accepted. The standard data files are not validated this way.
- Constraints added by users in data files are supported for linear expressions, including `sum {domain} expression`
  (see the parser documentation in `src/ampl_dat.jl`). Not supported: `abs`, `if`, `prod`, `min`, `max`, double relations
  (`a <= x <= b`), and the declaration of new variables.
- The Julia code is a translation, not generated from the `.mod` files: every change in a `.mod` must be reproduced by hand.
