"""
esqc_run: run the EnergyScope-Quebec model (snapshot) in two ways and compare them.

    import esqc_run as esqc

    r = esqc.run_snapshot(2030)                                  # Julia/JuMP + HiGHS (open source, default)
    a = esqc.run_snapshot(2030, backend="ampl")                  # AMPL + HiGHS (reference)
    s = esqc.run_snapshot(2030, changes="my_changes.dat")        # with your own changes (a text file)

    esqc.compare_summary(a, r)          # table: cost, difference, timings
    esqc.compare_table(a, r, "F_Mult")  # variable by variable
    esqc.plot_capacities(a, r)          # chart of installed capacities

Plots: pass `result.es` straight to the energyscope library, e.g.
    from energyscope.plots import plot_sankey, plot_eud, plot_resources_use
    plot_sankey(r.es);  plot_eud(r.es);  plot_resources_use(r.es)

How it works
------------
* AMPL backend : exactly the existing tools. `shared.utils.load_snapshot` builds the model, the
  `energyscope` library (`Energyscope`, `postprocessing`) solves it and post-processes it. Same steps as
  `shared.utils.run_model`, except that the solver is HiGHS (run_model is hard-wired to Gurobi).
* Julia backend : JuMP + HiGHS (package `projects/opensource/EnergyScopeQC`). Its results are converted into
  the same `energyscope.result.Result` object, so every existing plot works on both.
* `result.es` is that `Result` object (with `.variables`, `.parameters`, `.sets`, `.postprocessing`).

Changing the data
-----------------
* `changes="my_changes.dat"` (the simple way): a text file in the same syntax as the project's data and scenario
  files (`let c_inv[y,'WIND_ONSHORE'] := 1200;`, `for {...} {...}`, `subject to ...`). It is applied after the
  standard data, identically by both backends, and can hold as many changes as you like.
  A template with commented examples is `tutorials/example_files/my_changes.dat`.
* `overrides={...}` (for programs and tests): the same changes as a Python dictionary, same rules for both backends:
    {"parameter_name": value}                                     a number: replaces the parameter everywhere
    {"c_inv": {("YEAR_2030", "WIND_ONSHORE"): 1200.0}}             one specific entry (year, technology, ...)
    {"c_inv": {("YEAR_2030", "WIND_ONSHORE"): esqc.times(0.7)}}    the current value multiplied by 0.7

Julia runs inside the Python process when `juliacall` is installed (`pip install juliacall`) and stays
in memory between runs; otherwise it is started as a separate program for each run (~30 s of compilation each time).
"""
from __future__ import annotations

import contextlib
import math
import os
import shutil
import sys
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:                  # makes `shared.*` importable from anywhere
    sys.path.insert(0, str(ROOT))

from energyscope.result import Result as EsResult, postprocessing   # noqa: E402
from shared import julia_backend                                      # noqa: E402
from shared.julia_backend import times                               # noqa: E402,F401  (re-exported: esqc.times)
from shared.utils import collapse_temporal_index, load_snapshot       # noqa: E402

PKG = ROOT / "projects" / "opensource" / "EnergyScopeQC"
D = ROOT / "shared" / "data"
YEARS = (2020, 2025, 2030, 2035, 2040, 2045, 2050)
SEP = "\x1f"

#: model variables returned, with the names of their indices
TABLES = {
    "F_Mult": ["year", "technology"],                 # installed capacity [GW]
    "F_Mult_t": ["year", "technology", "period"],     # operation in each month [GW]
    "Annual_Prod": ["year", "technology"],            # annual production [GWh]
    "Annual_Res": ["year", "resource"],               # resources used [GWh]
    "TotalCost": ["year"],                            # annual cost of the system [M$CAD]
    "TotalGWP": ["year"],                             # emissions [ktCO2-eq]
    "C_inv": ["year", "technology"],                  # investment cost [M$CAD]
    "C_maint": ["year", "technology"],                # operation and maintenance cost [M$CAD]
    "C_op": ["year", "resource"],                     # resource cost [M$CAD]
}


@dataclass
class Result:
    backend: str
    year: int
    status: str
    objective: float
    seconds: dict
    tables: dict = field(repr=False)
    es: EsResult = field(repr=False, default=None)          # energyscope Result, post-processed (plots use it)
    overrides: dict = field(default_factory=dict, repr=False)
    label: str = ""
    changes: list = field(default_factory=list, repr=False)

    def table(self, name: str = "F_Mult") -> pd.Series:
        """One model variable, e.g. result.table('F_Mult'). See `esqc.TABLES` for the list."""
        return self.tables[name]

    def capacities(self, min_gw: float = 1e-6) -> pd.Series:
        """Installed capacities [GW] of the technologies that require an investment.

        Technologies with zero investment cost (processes, conversions) have an arbitrary capacity
        (often the upper bound, 10 000): they are left out so that only the real choices are shown.
        """
        cap = self.tables["F_Mult"].droplevel("year")
        inv = self.tables["C_inv"].droplevel("year")
        cap = cap[(cap.abs() > min_gw) & (inv.reindex(cap.index).fillna(0.0) > 1e-9)]
        return cap.sort_values(ascending=False)

    def __repr__(self):
        ov = (f", changes={[Path(c).name for c in self.changes]}" if self.changes else "") +              (f", overrides={list(self.overrides)}" if self.overrides else "")
        return (f"Result '{self.label or self.backend}' ({self.backend}, {self.year}): {self.status}, "
                f"total cost = {self.objective:,.2f} M$CAD, {self.seconds['total']:.0f} s{ov}")


def _status(s) -> str:
    """Same vocabulary for both backends."""
    return {"solved": "optimal", "OPTIMAL": "optimal", "infeasible": "infeasible", "INFEASIBLE": "infeasible"}.get(str(s), str(s))


def _tables_from_raw(raw: EsResult) -> dict:
    """The model variables as pandas Series (index names from TABLES), from an energyscope Result."""
    out = {}
    for name, names in TABLES.items():
        # the value column is not always called `name`: energyscope strips ".val" with rstrip, which turns "C_inv" into "C_in"
        s = raw.variables[name].drop(columns=["Run"], errors="ignore").iloc[:, 0].astype(float)
        s.index = s.index.set_names(names) if s.index.nlevels > 1 else s.index.rename(names[0])
        s.name = name
        out[name] = s
    return out


def _finish(backend, year, status, objective, seconds, raw, overrides, changes=()) -> Result:
    """Common end of both backends: tables + post-processing exactly as shared.utils.run_model does it."""
    tables = _tables_from_raw(raw)
    es = postprocessing(collapse_temporal_index(raw))
    return Result(backend, year, _status(status), objective, seconds, tables, es, overrides, changes=list(changes))


def _check_changes(changes) -> list:
    """List of absolute paths of the change files; clear error if one is missing."""
    if changes is None:
        return []
    paths = [Path(c) for c in ([changes] if isinstance(changes, (str, os.PathLike)) else changes)]
    for p in paths:
        if not p.is_file():
            raise FileNotFoundError(f"changes file not found: {p} (looked in {Path.cwd()})")
    return [p.resolve() for p in paths]


# ───────────────────────────── AMPL (existing tools) ─────────────────────────────

@contextlib.contextmanager
def _keep_snapshot_sets_file():
    """`load_snapshot` rewrites shared/data/QC_set_snapshot.dat for the requested year. Put it back afterwards so
    that running a tutorial never leaves a modified tracked file behind."""
    f = D / "QC_set_snapshot.dat"
    old = f.read_bytes() if f.exists() else None
    try:
        yield
    finally:
        if old is not None:
            f.write_bytes(old)


def _make_energyscope(year: int, gap: float):
    """`Energyscope` object on the snapshot model, with HiGHS (run_model itself is hard-wired to Gurobi)."""
    from amplpy import modules
    from energyscope.energyscope import Energyscope
    modules.load()                                       # makes the free HiGHS solver available to AMPL
    solver_options = {"solver": "highs", "solver_msg": 0, "highs_options": f"outlev=0 mip:gap={gap}"}
    return Energyscope(model=load_snapshot(year), solver_options=solver_options)


def load_ampl_snapshot(year: int, gap: float = 1e-4):
    """AMPL object with the model and the data of snapshot `year` loaded (not solved)."""
    with _keep_snapshot_sets_file():
        es = _make_energyscope(year, gap)
        es._initial_run()                                # reads the .mod and .dat files
    return es.es_model


def _lit(x):
    """Value or index as an AMPL literal."""
    if isinstance(x, str):
        return "Infinity" if x == "Infinity" else "'" + x.replace("'", "") + "'"
    if isinstance(x, float) and math.isinf(x):
        return "Infinity" if x > 0 else "-Infinity"
    return repr(x)


def _apply_overrides_ampl(a, overrides: dict):
    for name, spec in overrides.items():
        try:
            p = a.get_parameter(name)
        except Exception:
            raise KeyError(f"override: unknown parameter '{name}'") from None
        if isinstance(spec, dict):
            for key, val in spec.items():
                key = key if isinstance(key, tuple) else (key,)
                idx = "[" + ",".join(_lit(k) for k in key) + "]"
                rhs = f"{name}{idx} * {val.factor!r}" if isinstance(val, times) else _lit(float(val))
                a.eval(f"let {name}{idx} := {rhs};")
        elif p.indexarity() == 0:
            a.eval(f"let {name} := {_lit(float(spec))};")
        else:                      # a number for an indexed parameter: every entry
            for key in list(p.get_values().to_dict().keys()):
                key = key if isinstance(key, tuple) else (key,)
                a.eval(f"let {name}[{','.join(_lit(k) for k in key)}] := {_lit(float(spec))};")


def _run_ampl(year, gap, overrides, changes) -> Result:
    t0 = time.time()
    with _keep_snapshot_sets_file():
        es = _make_energyscope(year, gap)
        es._initial_run()
    a = es.es_model
    if changes:
        a.eval("model;")                                 # the change files only contain `let` / `subject to`: command mode
        for f in changes:
            a.read(str(f))
    _apply_overrides_ampl(a, overrides)
    a.get_value("_nvars")                                # forces the model instantiation
    t_model = time.time() - t0
    t1 = time.time()
    raw = es.calc()                                      # solves and parses, like run_model
    t_solve = time.time() - t1
    return _finish("ampl", year, a.get_value("solve_result"), float(a.get_objective("obj").value()),
                   {"total": time.time() - t0, "data+model": t_model, "solve": t_solve,
                    "solver": float(a.get_value("_solve_elapsed_time"))}, raw, overrides, changes)


# ───────────────────────────── Julia (shared.julia_backend) ─────────────────────────────

def _run_julia(year, gap, overrides, changes) -> Result:
    raw, info = julia_backend.run_snapshot(year, mip_gap=gap, changes=changes, overrides=overrides)
    return _finish("julia", year, info["status"], info["objective"], info["seconds"], raw, overrides, changes)


# ───────────────────────────── API ─────────────────────────────

def run_snapshot(year: int = 2030, backend: str = "julia", overrides: dict | None = None, gap: float = 1e-4,
                 label: str | None = None, changes=None) -> Result:
    """Solve the model for one year (snapshot).

    backend   : "julia" (JuMP + HiGHS, open source) or "ampl" (AMPL + HiGHS, reference)
    changes   : path (or list of paths) of text file(s) with your changes to the data, e.g. "my_changes.dat"
    overrides : the same kind of changes written as a Python dictionary (see the module header)
    gap       : relative accuracy requested from the solver. 1e-4 (0.01 %) is HiGHS's default and fast; use a
                tighter value (1e-6) to compare two runs very precisely, at the price of a longer solve
    label     : name of the run in tables and charts (default: the backend name)
    """
    if year not in YEARS:
        raise ValueError(f"unknown year {year}; choose among {YEARS}")
    overrides = dict(overrides or {})
    changes = _check_changes(changes)
    if backend == "julia":
        res = _run_julia(year, gap, overrides, changes)
    elif backend == "ampl":
        res = _run_ampl(year, gap, overrides, changes)
    else:
        raise ValueError("backend must be 'julia' or 'ampl'")
    res.label = label or backend
    return res


def _labels(a: Result, b: Result):
    la, lb = a.label or a.backend, b.label or b.backend
    return (la, lb) if la != lb else (la + " (1)", lb + " (2)")


def compare_summary(a: Result, b: Result) -> pd.DataFrame:
    """Summary of two runs: status, total cost, relative difference, timings."""
    rel = abs(a.objective - b.objective) / max(1.0, abs(a.objective))
    rows = {
        "status": (a.status, b.status),
        "total cost [M$CAD]": (f"{a.objective:,.4f}", f"{b.objective:,.4f}"),
        "relative cost difference": ("", f"{rel:.1e}"),
        "total time [s]": (f"{a.seconds['total']:.1f}", f"{b.seconds['total']:.1f}"),
        "  of which HiGHS solver only [s]": (f"{a.seconds['solver']:.2f}", f"{b.seconds['solver']:.2f}"),
        "  of which reading, building, start-up [s]": (f"{a.seconds['total'] - a.seconds['solver']:.1f}",
                                                       f"{b.seconds['total'] - b.seconds['solver']:.1f}"),
    }
    return pd.DataFrame(rows, index=list(_labels(a, b))).T


def compare_table(a: Result, b: Result, name: str = "F_Mult", top: int = 15) -> pd.DataFrame:
    """One variable from both runs side by side, sorted by decreasing difference."""
    la, lb = _labels(a, b)
    df = pd.concat([a.tables[name].rename(la), b.tables[name].rename(lb)], axis=1).fillna(0.0)
    df["difference"] = (df.iloc[:, 0] - df.iloc[:, 1]).abs()
    return df.sort_values("difference", ascending=False).head(top)


def same_objective(a: Result, b: Result, tol: float = 1e-6) -> bool:
    return abs(a.objective - b.objective) / max(1.0, abs(a.objective)) <= tol


def plot_capacities(*results: Result, top: int = 12, title: str | None = None):
    """Installed capacities [GW] of the `top` largest technologies, one color per run."""
    import matplotlib.pyplot as plt
    names = [r.label or r.backend for r in results]
    names = [n if names.count(n) == 1 else f"{n} ({i + 1})" for i, n in enumerate(names)]
    caps = pd.concat([r.capacities().rename(n) for r, n in zip(results, names)], axis=1).fillna(0.0)
    caps = caps.loc[caps.max(axis=1).sort_values(ascending=False).head(top).index].iloc[::-1]
    ax = caps.plot.barh(figsize=(8, 0.45 * len(caps) * max(1, len(results)) + 1.5), width=0.8)
    ax.set_xlabel("installed capacity [GW]")
    ax.set_ylabel("")
    ax.set_title(title or f"Installed capacities, {results[0].year}")
    ax.grid(axis="x", alpha=0.3)
    plt.tight_layout()
    return ax
