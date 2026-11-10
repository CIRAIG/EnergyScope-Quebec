"""
Julia backend of the EnergyScope-Quebec model (open source: JuMP + HiGHS, no AMPL and no license needed).

It runs the Julia package ``projects/opensource/EnergyScopeQC`` and converts what it computes into the same
``energyscope.result.Result`` object that the AMPL route produces (``energyscope.result.parse_result``). Everything that
consumes a ``Result`` (``postprocessing``, ``energyscope.plots``, ``shared.plotting``) therefore works unchanged.

Normally you do not call this module directly: use the ``backend`` argument of ``shared.utils.run_model``::

    from shared.utils import load_snapshot, run_model
    result = run_model(load_snapshot(2030), backend="julia")

Julia runs inside the Python process (package ``juliacall``, required: ``pip install juliacall``) and stays in memory between
calculations.
"""
from __future__ import annotations

import hashlib
import json
import math
import tempfile
import time
import warnings
from dataclasses import dataclass
from pathlib import Path

import pandas as pd
from energyscope.result import Result

_ROOT = Path(__file__).resolve().parents[1]
JULIA_PACKAGE = _ROOT / "projects" / "opensource" / "EnergyScopeQC"
_SEP = "\x1f"

# AMPL model files that the Julia package re-implements; their fingerprints are recorded in data/mod_hashes.json
# when the port was last checked against AMPL (projects/opensource/MAINTENANCE.md).
MODEL_FILES = ("shared/model/QC_es_main.mod", "shared/model/QC_objective_function.mod",
               "projects/pathway/model/PES_main.mod", "projects/pathway/model/PES_store_variables.mod",
               "projects/pathway/model/PES_scenarios.mod", "projects/pathway/model/PES_obj_pathway.mod")
FINGERPRINT_FILE = JULIA_PACKAGE / "data" / "mod_hashes.json"


def mod_fingerprints() -> dict:
    """SHA-256 of each AMPL model file in ``MODEL_FILES`` (line endings and trailing blank lines ignored)."""
    out = {}
    for rel in MODEL_FILES:
        text = (_ROOT / rel).read_text(encoding="utf8", errors="replace").replace("\r\n", "\n").rstrip()
        out[rel] = hashlib.sha256(text.encode("utf8")).hexdigest()
    return out


def _warn_if_port_outdated():
    """Warn when an AMPL model file differs from the version the Julia port was last checked against."""
    try:
        reference = json.loads(FINGERPRINT_FILE.read_text(encoding="utf8"))
        current = mod_fingerprints()
    except (OSError, ValueError):
        return                                                    # no reference recorded: nothing to compare with
    changed = [f for f, h in current.items() if reference.get(f) != h]
    if changed:
        warnings.warn("The AMPL model changed since the Julia version was last checked against it ("
                      + ", ".join(Path(f).name for f in changed) + "): results with backend='julia' may no longer match "
                      "the AMPL model. See projects/opensource/MAINTENANCE.md.", UserWarning, stacklevel=3)


@dataclass(frozen=True)
class times:
    """Current value multiplied by ``factor`` (e.g. ``times(0.7)`` = -30 %). Used in ``overrides``."""
    factor: float


_JL = None


def _julia_main():
    """The ``juliacall`` Julia session of this Python process, with ``EnergyScopeQC`` loaded (started once, kept in memory).

    ``juliacall`` manages its own Julia (it downloads one the first time, 1.10 to 1.11 at the time of writing); set the
    environment variable ``PYTHON_JULIAPKG_EXE`` before the first use to make it use another installed Julia."""
    global _JL
    if _JL is None:
        try:
            from juliacall import Main as jl
        except ImportError as e:
            raise ImportError("The Julia backend needs the package juliacall: pip install juliacall") from e
        jl.seval("import Pkg")
        jl.seval(f'Pkg.activate(raw"{JULIA_PACKAGE}"; io=devnull)')
        jl.seval("Pkg.instantiate()")                              # first run on a machine: installs JuMP, HiGHS... (a few minutes)
        jl.seval("using EnergyScopeQC")
        _JL = jl
        _warn_if_port_outdated()
    return _JL


def _jl_value(v) -> str:
    return "Infinity" if (isinstance(v, float) and math.isinf(v)) else repr(float(v))


def _write_overrides(path: Path, overrides: dict):
    lines = []
    for name, spec in (overrides or {}).items():
        if isinstance(spec, dict):
            for key, val in spec.items():
                key = key if isinstance(key, tuple) else (key,)
                kind, v = ("MUL", val.factor) if isinstance(val, times) else ("ONE", val)
                lines.append(f"{kind}\t{name}\t{_SEP.join(str(k) for k in key)}\t{_jl_value(v)}")
        else:
            lines.append(f"ALL\t{name}\t\t{_jl_value(spec)}")
    path.write_text("\n".join(lines) + "\n", encoding="utf8")


def _el(x: str):
    """A key element read from a file: integer if it is only digits (months), else text.
    (Not ``int(x)``: Python accepts "2020_2025" as 20202025, but that is a phase name.)"""
    return int(x) if x.isascii() and x.isdigit() else x


def _frame(name: str, items: list, one_d_name: str) -> pd.DataFrame:
    """DataFrame in the layout ``parse_result`` gives for an AMPL variable or parameter."""
    keys = [tuple(_el(k) for k in key) for key, _ in items]
    if len(keys[0]) == 1:
        idx = pd.Index([k[0] for k in keys], name=one_d_name)
    else:
        idx = pd.MultiIndex.from_tuples(keys, names=[f"index{i}" for i in range(len(keys[0]))])
    df = pd.DataFrame({name: [v for _, v in items]}, index=idx)
    df["Run"] = 0
    return df


def _raw_result(meta, tables, params, sets, isets) -> Result:
    """``Result`` (as ``parse_result`` would give it) from the values written by the Julia script."""
    return Result(
        objectives={"obj": pd.DataFrame({"obj": [float(meta.get("objective", "nan"))]})},
        variables={n: _frame(n, items, "index0") for n, items in tables.items() if items},
        parameters={n: _frame(n, items, "index") for n, items in params.items() if items},
        sets={**{n: pd.DataFrame({n: items}) for n, items in sets.items()},
              **{n: {k: v for k, v in d.items()} for n, d in isets.items()}},
    )


_NOISE = 1e-6  # interior-point solutions carry ~1e-9 residuals on unused technologies; AMPL+Gurobi gives exact zeros


def _clean(x: float) -> float:
    return 0.0 if abs(x) < _NOISE else x


def _read_results(path: Path):
    meta, tables, params, sets, isets = {}, {}, {}, {}, {}
    for line in path.read_text(encoding="utf8").splitlines():
        parts = line.split("\t")
        kind = parts[0]
        if kind == "META":
            meta[parts[1]] = parts[2]
        elif kind == "TABLE":
            tables.setdefault(parts[1], []).append((tuple(parts[2].split(_SEP)), _clean(float(parts[3]))))
        elif kind == "PARAM":
            params.setdefault(parts[1], []).append((tuple(parts[2].split(_SEP)), float(parts[3])))
        elif kind == "SET":
            sets[parts[1]] = [x for x in parts[2].split(_SEP) if x != ""]
        elif kind == "ISET":
            isets.setdefault(parts[1], {})[parts[2].split(_SEP)[0]] = [x for x in parts[3].split(_SEP) if x != ""]
    return meta, tables, params, sets, isets


def run_snapshot(year: int, *, mip_gap: float = 1e-4, changes=(), overrides: dict | None = None,
                 scenario: bool = True):
    """Solve the snapshot of ``year`` with Julia (JuMP + HiGHS).

    Parameters
    ----------
    year      : 2020, 2025, ..., 2050
    mip_gap   : relative accuracy requested from HiGHS (1e-4 is HiGHS's default)
    changes   : text file(s) with changes to the data (``let ...;``), applied after the standard data
    overrides : the same kind of changes as a Python dictionary (see ``times``)
    scenario  : for 2050, include the generic scenario file (as ``load_snapshot`` does)

    Returns
    -------
    (result, info) : ``result`` is the ``Result`` before ``collapse_temporal_index`` / ``postprocessing`` (the year
    dimension is still there); ``info`` holds ``status``, ``objective`` and ``seconds`` (timings).
    """
    t0 = time.time()
    with tempfile.TemporaryDirectory() as wd:
        wd = Path(wd)
        ov = wd / "overrides.tsv"
        _write_overrides(ov, overrides)
        try:
            _julia_main().EnergyScopeQC.Runner.solve_snapshot(int(year), float(mip_gap), str(wd), str(ov),
                                                              "\n".join(str(Path(c)) for c in changes), bool(scenario))
        except Exception as e:                          # a Julia error: show it with the Python traceback
            raise RuntimeError(f"Julia failed: {e}") from e
        meta, tables, params, sets, isets = _read_results(wd / "results.tsv")
    if "objective" not in meta:
        status = meta.get("status", "")
        hint = (" The model has no feasible solution: look for a capacity limit (f_max) below f_min or below what is needed, "
                "a constraint added in your changes file, or a negative cost.") if "INFEASIBLE" in status else ""
        raise ValueError(f"No optimal solution found (Julia status: {status}).{hint}")
    info = {
        "status": meta["status"],
        "objective": float(meta["objective"]),
        "seconds": {"total": time.time() - t0, "data+model": float(meta["t_data"]) + float(meta["t_build"]),
                    "solve": float(meta["t_solve"]), "solver": float(meta["t_solver"])},
    }
    return _raw_result(meta, tables, params, sets, isets), info
