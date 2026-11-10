# EnergyScope-Quebec tutorials

All tutorials live here. Each `.ipynb` file opens in Jupyter (JupyterLab, VS Code, etc.);
run the cells one after the other with **Shift + Enter**.

## The four tutorials

|  | **Snapshot** (one year) | **Pathway** (trajectory 2020 to 2050) |
|---|---|---|
| **JuMP: open source**<br>Julia + HiGHS, no license needed | [`03_snapshot_jump_opensource.ipynb`](03_snapshot_jump_opensource.ipynb) | [`04_pathway_jump_opensource.ipynb`](04_pathway_jump_opensource.ipynb) |
| **AMPL: reference version**<br>needs AMPL and a solver license | [`01_snapshot_ampl.ipynb`](01_snapshot_ampl.ipynb) | [`02_pathway_ampl.ipynb`](02_pathway_ampl.ipynb) |

The file names say what each one is: `<model>_<engine>`, with `_opensource` for the license-free version.

* **Snapshot**: the energy system of **one year** (2020, 2025, ..., 2050). Quick (about a minute).
* **Pathway**: the **trajectory** from 2020 to 2050, with investment decisions over time.

## What you need

The tutorials run from a **clone of this repository**, with Python and the project installed (`pip install -e .` at the root of the repository).
The open-source tutorials (03 and 04) also need **`juliacall`** (`pip install juliacall`). It downloads and manages Julia by itself: the first
calculation on a machine is slow (installation and compilation), the next ones are fast.

## Which one should I use?

* **No AMPL license** (partners, students, anyone): the open-source (JuMP) tutorials. Everything runs with free software.
* **AMPL license** (the reference version, the one the model developers modify): the AMPL tutorials.

Both versions of the model give the same total costs, up to the solver tolerance (0.05 % by default).

## Example files (folder `example_files`)

* [`my_changes.dat`](example_files/my_changes.dat): ready-to-use examples of input-data changes (a cheaper technology, a capacity limit, a resource price...) for the open-source tutorials (see tutorials 03 and 04).
* [`myopic_limits.dat`](example_files/myopic_limits.dat): relaxes the limits on the pace of change so that the myopic (rolling-horizon) mode has a feasible
  solution (see tutorial 04, section 8).
* [`my_new_constraints.mod`](example_files/my_new_constraints.mod) and [`my_scenario_params.dat`](example_files/my_scenario_params.dat): examples of the extra files that
  `run_pathway(..., extra_files=[...])` accepts (a new constraint, and an empty file for scenario parameters).
