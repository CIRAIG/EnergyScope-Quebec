"""
Pathway with Julia (JuMP + HiGHS), perfect foresight or myopic: results read by the existing AMPL result code.

``run_pathway(..., backend='julia')`` (see ``shared.utils``) keeps the AMPL routine unchanged: for each window it builds an
object, solves, calls the ``get_*`` methods of ``AmplObject``, and stores the tables with ``AmplCollector``. Here the only
things replaced are the *solve* (done by Julia) and the *access to the solved model* (``JuliaAmplObject`` below reads Julia's
values through a small stand-in for the AMPL object). Every table (``Assets``, ``Year_balance``, ``Cost_breakdown``...) is
therefore computed by the same code as with AMPL, and ``plot_results.py`` works unchanged.

The names and index sets of the variables, parameters and sets come from ``data/ampl_signature.json`` in the Julia package.
That file is generated from a loaded AMPL model by a private script and only changes when the ``.mod`` declarations do.
"""
from __future__ import annotations

import itertools
import json
import os
import re
import shutil
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd

from shared.julia_backend import JULIA_PACKAGE, _SEP, _el, _julia_main, _write_overrides

SIGNATURE_FILE = JULIA_PACKAGE / "data" / "ampl_signature.json"


# ───────────────────────────── running Julia and reading its output ─────────────────────────────

@dataclass
class PathwayData:
    """What Julia wrote for one window (``results_<i>.tsv``): values of the variables, of the parameters, and the sets."""
    meta: dict = field(default_factory=dict)
    tables: dict = field(default_factory=dict)      # variable -> {key tuple: value}
    params: dict = field(default_factory=dict)      # parameter -> {key tuple: value}
    defaults: dict = field(default_factory=dict)    # parameter -> default value
    sets: dict = field(default_factory=dict)        # set -> [elements]
    isets: dict = field(default_factory=dict)       # indexed set -> {key: [elements]}


def _key(text: str) -> tuple:
    return tuple(_el(x) for x in text.split(_SEP) if x != "")


def read_output(path: Path) -> PathwayData:
    d = PathwayData()
    for line in Path(path).read_text(encoding="utf8").splitlines():
        p = line.split("\t")
        kind = p[0]
        if kind == "META":
            d.meta[p[1]] = p[2]
        elif kind == "TABLE":
            d.tables.setdefault(p[1], {})[_key(p[2])] = float(p[3])
        elif kind == "PARAM":
            d.params.setdefault(p[1], {})[_key(p[2])] = float(p[3])
        elif kind == "DEFAULT":
            d.defaults[p[1]] = float(p[2])
        elif kind == "SET":
            d.sets[p[1]] = [_el(x) for x in p[2].split(_SEP) if x != ""]
        elif kind == "ISET":
            k = _key(p[2])
            d.isets.setdefault(p[1], {})[k[0] if len(k) == 1 else k] = [_el(x) for x in p[3].split(_SEP) if x != ""]
    return d


class JuliaSession:
    """The Julia side of a run: all the windows of one ``run_pathway`` call (``EnergyScopeQC.Runner``, through ``juliacall``).

    Julia reads the data once, then for each window builds the model, solves it and writes ``results_<i>.tsv`` (followed by an
    empty ``done_<i>``). Between two windows it fixes the variables of the past to the previous solution (what ``set_init_sol`` /
    ``fix.mod`` do with AMPL), so Python never has to carry the solution over. ``window(i)`` returns what Julia computed for
    window ``i``. The sets of window ``i`` are read from ``seq_<i>.dat``, the file ``AmplPreProcessor`` writes for AMPL
    (``write_windows``).
    """

    def __init__(self, work_dir, n_windows: int, mip_gap: float = 5e-4, changes=(), time_limit: float = 3600.0):
        self.dir, self.n_windows, self.mip_gap, self.time_limit = Path(work_dir), n_windows, mip_gap, time_limit
        self.changes = [str(Path(c)) for c in changes]
        self.overrides: dict = {}
        self._run = None            # the Julia PathwayRun
        self._solved = 0            # windows solved so far
        self.dir.mkdir(parents=True, exist_ok=True)

    def write_windows(self, ampl_pre):
        """Write ``seq_<i>.dat`` for every window with the existing ``AmplPreProcessor`` (same windows as with AMPL)."""
        for i in range(self.n_windows):
            ampl_pre.write_seq_opti(i)
            shutil.copyfile(Path(ampl_pre.mod_path) / "PES_seq_opti.dat", self.dir / f"seq_{i}.dat")
        ampl_pre.year_to_rm = ""

    def start(self):
        """Open the Julia run (once). The overrides must be set before: they are the same for all windows."""
        if self._run is not None:
            return
        ov = self.dir / "overrides.tsv"
        _write_overrides(ov, self.overrides)
        jl = _julia_main()
        self._run = jl.EnergyScopeQC.Runner.open_pathway(self.mip_gap, str(self.dir), str(ov), chr(10).join(self.changes),
                                                          self.n_windows, float(self.time_limit))

    def window(self, i: int) -> PathwayData:
        """Results of window ``i`` (0-based); the windows are solved in order, on first request."""
        self.start()                                                     # no-op once started
        solve = getattr(_julia_main().EnergyScopeQC.Runner, "solve_next!")
        while self._solved <= i:
            t0 = time.time()
            try:
                status = str(solve(self._run))
            except Exception as e:                                       # a Julia error: show it with the Python traceback
                raise RuntimeError(f"Julia failed: {e}") from e
            self._solved += 1
            sys.stdout.write(f"[run_pathway] julia : window {self._solved}/{self.n_windows} {status} "
                             f"in {time.time() - t0:.1f} s" + chr(10))
            sys.stdout.flush()
        return read_output(self.dir / f"results_{i}.tsv")

    def close(self):
        if self._run is not None:
            self._run = None
            _julia_main().GC.gc()        # the last HiGHS model closes its log file when it is collected (else the temp folder cannot be removed)


# ───────────────────────────── stand-in for the AMPL object ─────────────────────────────

def _eval_index(expr: str, sets: dict) -> list:
    """Elements of an AMPL indexing expression such as ``i in STORAGE_TECH`` or ``RESOURCES union TECHNOLOGIES diff STORAGE_TECH``."""
    s = " ".join(expr.split())                          # normalises spaces and line breaks
    s = re.sub(r"^\w+ in ", "", s)                      # "i in X" -> "X"
    tokens = re.findall(r"\{[^}]*\}|[A-Za-z_]\w*", s)
    def operand(tok):
        if tok.startswith("{"):
            return [_el(x.strip().strip("'\"")) for x in tok[1:-1].split(",") if x.strip()]
        return list(sets[tok])
    result = operand(tokens[0])
    for k in range(1, len(tokens), 2):
        op, other = tokens[k], operand(tokens[k + 1])
        if op == "union":
            result += [x for x in other if x not in result]
        elif op == "diff":
            result = [x for x in result if x not in set(other)]
        elif op == "inter":
            result = [x for x in result if x in set(other)]
        else:
            raise ValueError(f"index expression not handled: {expr!r}")
    return result


class _DataFrame:
    def __init__(self, df):
        self._df = df

    def to_pandas(self):
        return self._df.copy()


class _Values:
    def __init__(self, values):
        self._values = values

    def toList(self):
        return list(self._values)


class _Set:
    """Simple set, or set indexed by one or more sets."""
    def __init__(self, values=None, indexed=None):
        self._values, self._indexed = values, indexed

    def instances(self):
        if self._indexed is None:
            return [(None, self)]
        return [(k, _Set(values=v)) for k, v in self._indexed.items()]

    def getValues(self):
        if self._indexed is not None:
            if len(self._indexed) != 1:
                raise RuntimeError("indexed set")
            return _Values(next(iter(self._indexed.values())))
        return _Values(self._values)


class _Entity:
    """A variable or a parameter: ``getIndexingSets``, ``getValues().to_pandas()``, ``value()``."""
    def __init__(self, ampl, kind, name):
        self._ampl, self._kind, self._name = ampl, kind, name
        self._index = ampl.sig["variables" if kind == "var" else "parameters"][name]["index"]

    def getIndexingSets(self):
        return list(self._index)

    def getValues(self):
        return _DataFrame(self._ampl._frame(self._kind, self._name, self._index))

    def value(self):
        return self._ampl._lookup(self._kind, self._name)(())

    def instances(self):
        return [(None, self)]


class _Constraint:
    """Dual values do not exist for a MIP: AMPL returns 0 (see the project notes), so does this."""
    def __getitem__(self, key):
        return self

    def dual(self):
        return 0.0


class _Objective:
    def __init__(self, value):
        self._value = value

    def value(self):
        return self._value


class PathwayAmpl:
    """Minimal stand-in for the ``amplpy.AMPL`` object, serving what ``AmplObject`` reads, from Julia's values."""

    def __init__(self, data: PathwayData | None, signature: dict):
        self.d, self.sig = data, signature

    # --- values ---
    def _lookup(self, kind, name):
        d = self.d
        if kind == "var":
            vals = d.tables.get(name, {})
            return lambda k: vals.get(k, 0.0)
        vals, default = d.params.get(name, {}), d.defaults.get(name)
        return lambda k: vals.get(k, default if default is not None else float("nan"))

    def _frame(self, kind, name, index):
        sets = {**self.d.sets}
        axes = [_eval_index(e, sets) for e in index]
        rows = list(itertools.product(*axes)) if axes else [()]
        get = self._lookup(kind, name)
        col = f"{name}.val" if kind == "var" else name
        values = [get(r) for r in rows]
        if len(axes) > 1:
            idx = pd.MultiIndex.from_tuples(rows, names=[f"index{i}" for i in range(len(axes))])
        elif len(axes) == 1:
            idx = pd.Index([r[0] for r in rows], name="index0")
        else:
            idx = pd.RangeIndex(1)
        return pd.DataFrame({col: values}, index=idx)

    # --- amplpy-like API (the names used by AmplObject) ---
    def getVariable(self, name):
        return _Entity(self, "var", name)

    def getParameter(self, name):
        return _Entity(self, "param", name)

    def getVariables(self):
        if self.d is None:
            return {}
        return {n: _Entity(self, "var", n) for n in self.sig["variables"] if n in self.d.tables}

    def getParameters(self):
        if self.d is None:
            return {}
        return {n: _Entity(self, "param", n) for n in self.sig["parameters"] if n in self.d.params or n in self.d.defaults}

    def getSets(self):
        if self.d is None:
            return []
        out = [(n, _Set(values=v)) for n, v in self.d.sets.items()]
        out += [(n, _Set(indexed=v)) for n, v in self.d.isets.items()]
        return out

    def get_constraint(self, name):
        return _Constraint()

    def get_objective(self, name):
        return _Objective(float(self.d.meta.get("objective", "nan")))


# ───────────────────────────── the AmplObject subclass ─────────────────────────────

def load_signature() -> dict:
    return json.loads(SIGNATURE_FILE.read_text(encoding="utf8"))


def julia_amplobject_class():
    """``JuliaAmplObject``: an ``AmplObject`` whose solve is done by Julia. Imported lazily because ``AmplObject`` lives in
    ``projects/pathway/pylib`` (put on ``sys.path`` by ``shared.utils.run_pathway``)."""
    from ampl_object import AmplObject

    class JuliaAmplObject(AmplObject):
        """The window ``index`` of a ``JuliaSession``, seen as an ``AmplObject``."""

        def __init__(self, session, index, type_model='MO'):
            self._session, self._index = session, index
            self._signature = load_signature()
            super().__init__([], [], [], {}, type_model=type_model, ampl_path=None, working_dir=str(session.dir))

        def set_ampl(self, *args, **kwargs):
            return PathwayAmpl(None, self._signature)       # empty until the solve: filled by run_ampl

        def set_params(self, name, value):
            self._session.overrides[name] = value            # applied by Julia before the solve (same for every window)

        def clean_history(self):                             # AMPL version truncates files of the model folder: nothing to do
            pass

        def set_init_sol(self):                              # Julia fixes the past itself, between two windows
            pass

        def run_ampl(self):
            t0 = time.time()
            self._session.start()
            data = self._session.window(self._index)
            self.t = float(data.meta.get("t_solver", time.time() - t0))
            status = data.meta.get("status", "")
            if "LIMIT" in status:                            # time limit: reported as such, whatever the solution found
                return "limit", 400
            if "objective" not in data.meta:
                return ("infeasible" if "INFEASIBLE" in status else "failure"), 1
            self.ampl = PathwayAmpl(data, self._signature)
            self.vars, self.params = self.ampl.getVariables(), self.ampl.getParameters()
            self.sets = dict()
            self.get_sets()
            return "solved", (0 if status == "OPTIMAL" else 400)

    return JuliaAmplObject


# ───────────────────────────── windows (AmplPreProcessor without AMPL) ─────────────────────────────

class _WindowSource:
    """What ``AmplPreProcessor`` reads from the AMPL object: the sets ``YEARS`` and ``PHASE``, and the model folder.
    The folder is a temporary copy, so the files the AMPL routine rewrites at each window (``PES_seq_opti.dat``,
    ``PES_data_remaining_wnd.dat``) are never touched in the repository."""

    def __init__(self, sets, directory):
        self.sets, self.dir = sets, Path(directory)

    def clean_history(self):
        pass


def window_source(model_dir, tmp_dir) -> _WindowSource:
    """Build the window source from ``EXTRA_INFOS.dat`` and copy ``PES_data_remaining.dat`` into ``tmp_dir``."""
    model_dir = Path(model_dir)
    text = (model_dir / "EXTRA_INFOS.dat").read_text(encoding="utf8")

    def read_set(name):
        m = re.search(rf"set\s+{name}\s*:=\s*([^;]*);", text)
        if m is None:
            raise ValueError(f"set {name} not found in EXTRA_INFOS.dat")
        return m.group(1).split()

    (Path(tmp_dir) / "PES_data_remaining.dat").write_bytes((model_dir / "PES_data_remaining.dat").read_bytes())
    return _WindowSource({"YEARS": read_set("YEARS"), "PHASE": read_set("PHASE")}, tmp_dir)
