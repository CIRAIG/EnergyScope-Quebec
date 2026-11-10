# Open-source version of EnergyScope-Quebec (Julia / JuMP + HiGHS)

This folder contains a port of the ES-QC model that runs **without an AMPL license**: the model is written in
[JuMP](https://jump.dev) (Julia) and solved with the free solver [HiGHS](https://highs.dev). It reads the same data files (`.dat`)
as the AMPL version and returns the same result objects, so the plots and post-processing of the project work unchanged.

The AMPL version remains the reference. Both give the same total costs, up to the solver tolerance.

## What it can do

* **Snapshot**: one year (2020, 2025, ..., 2050), `run_model(load_snapshot(year), backend="julia")`.
* **Pathway**: trajectory 2020 to 2050, perfect foresight or myopic (rolling window), `run_pathway(name, backend="julia")`.
* **Changing input data** (costs, capacity limits, resource prices, extra constraints) from a text file: explained in the tutorials.
* Time limit and MIP gap: `run_pathway(..., mip_gap=..., time_limit=...)`.

## Requirements

* Python environment of the project (`pip install -e ".[julia]"` at the repository root). The extra installs `juliacall`, which downloads
  and manages Julia by itself.
* First calculation on a machine: slow (Julia download, package installation, compilation). The next ones are fast
  (a 2020 snapshot takes a few seconds once Julia is loaded).

## How to run

Start with the tutorials in [`tutorials/`](../../tutorials): `03_snapshot_jump_opensource.ipynb` and `04_pathway_jump_opensource.ipynb`.
Results of Julia pathway runs are written to `projects/opensource/out/<run name>/` (ignored by git).

## Layout

```
EnergyScopeQC/   Julia package: .dat parser (ampl_dat.jl), model (QC_es_main.jl, PES_main.jl), runner (runner.jl), Julia tests (test/)
python/          helper functions used by the tutorials
tests/           Python tests and scripts that compare the port with the AMPL version
MAINTENANCE.md   what to update on the Julia side when the AMPL model changes
```

Julia tests: `julia --project=projects/opensource/EnergyScopeQC projects/opensource/EnergyScopeQC/test/runtests.jl`.
Python tests: `pytest projects/opensource/tests/test_julia_pathway.py`.

## Limitations

* The `.mod` files are re-implemented by hand: a change in the AMPL model must be reflected in Julia (see `MAINTENANCE.md`).
  Users get a warning when the AMPL model changed since the port was last checked.
* Change files support linear constraints only (no `abs`, `if`, `prod`, `min`/`max`, double inequalities), and cannot declare new variables.
* HiGHS is slower and less predictable than Gurobi on the full pathway problem: the same run can take from a few minutes to half an hour.
  The result is the same up to the gap.
