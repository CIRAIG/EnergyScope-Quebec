"""
Fast tests (no solve) of the Julia path of run_pathway: myopic windows, reading of Julia's results, errors.
No data value is checked, only the structure: the .dat files can change without breaking these tests.

usage: python -m pytest projects/opensource/tests/test_julia_pathway.py
"""
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
MODEL = ROOT / "projects" / "pathway" / "model"
for p in (ROOT, ROOT / "projects" / "pathway" / "pylib"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

from ampl_preprocessor import AmplPreProcessor                     # noqa: E402
from shared import julia_backend                                   # noqa: E402
from shared.julia_pathway import JuliaSession, read_output, window_source   # noqa: E402
from shared.utils import PathwayResults, run_pathway                # noqa: E402


def _sets(seq_file):
    """Sets written in a PES_seq_opti.dat: name -> list of elements."""
    return {m[1]: (m[2] or "").split() for m in re.finditer(r"set\s+(\w+)\s*(?::=([^;]*))?;", seq_file.read_text(encoding="utf8"))}


@pytest.mark.parametrize("n_opti, n_overlap", [(30, 0), (10, 0), (10, 5), (20, 5), (5, 0)])
def test_windows_written_for_every_window(tmp_path, n_opti, n_overlap):
    src = window_source(MODEL, tmp_path)
    pre = AmplPreProcessor(src, n_opti, n_overlap)
    session = JuliaSession(tmp_path / "julia", len(pre.years_opti))
    before = (MODEL / "PES_seq_opti.dat").read_bytes()
    session.write_windows(pre)

    assert (MODEL / "PES_seq_opti.dat").read_bytes() == before           # the repository is not touched
    assert pre.year_to_rm == ""                                          # preprocessor state reset
    n = len(pre.years_opti)
    wins = [_sets(tmp_path / "julia" / f"seq_{i}.dat") for i in range(n)]
    all_years = src.sets["YEARS"]
    assert wins[0]["YEARS_WND"][0] == all_years[0] and wins[-1]["YEARS_WND"][-1] == all_years[-1]
    assert wins[0]["YEAR_ONE"] == []                                     # the first window has no past
    assert wins[-1]["YEAR_ONE_NEXT"] == []                               # the last window has no successor
    for i in range(1, n):
        assert wins[i]["YEAR_ONE"] == [wins[i]["YEARS_WND"][0]]          # YEAR_ONE = first year of the window
        assert wins[i - 1]["YEAR_ONE_NEXT"] == wins[i]["YEAR_ONE"]       # ... the one the previous window prepares
    assert wins[-1]["YEARS_UP_TO"] == all_years                          # at the end, the whole horizon is carried over


def test_perfect_foresight_is_one_window(tmp_path):
    pre = AmplPreProcessor(window_source(MODEL, tmp_path), 30, 0)
    assert len(pre.years_opti) == 1


RESULTS = "\n".join([
    "META\tstatus\tOPTIMAL", "META\tobjective\t12.5", "META\tt_solver\t0.5",
    "TABLE\tF_Mult\tYEAR_2020\x1fSOLAR\t3.0",
    "TABLE\tTotalCost\tYEAR_2020\t7.0",
    "PARAM\ttau\tYEAR_2020\x1fSOLAR\t0.1",
    "DEFAULT\tc_p\t1.0",
    "SET\tYEARS\tYEAR_2020\x1fYEAR_2025",
    "ISET\tPHASE_START\t2020_2025\tYEAR_2020",
])


def test_read_output(tmp_path):
    path = tmp_path / "results_0.tsv"
    path.write_text(RESULTS, encoding="utf8")
    d = read_output(path)
    assert d.meta["status"] == "OPTIMAL" and float(d.meta["objective"]) == 12.5
    assert d.tables["F_Mult"][("YEAR_2020", "SOLAR")] == 3.0
    assert d.tables["TotalCost"][("YEAR_2020",)] == 7.0
    assert d.params["tau"][("YEAR_2020", "SOLAR")] == 0.1 and d.defaults["c_p"] == 1.0
    assert d.sets["YEARS"] == ["YEAR_2020", "YEAR_2025"]
    assert d.isets["PHASE_START"]["2020_2025"] == ["YEAR_2020"]


def test_missing_juliacall_gives_a_clear_error(monkeypatch):
    monkeypatch.setitem(sys.modules, "juliacall", None)              # makes `import juliacall` fail
    monkeypatch.setattr(julia_backend, "_JL", None)
    with pytest.raises(ImportError, match="pip install juliacall"):
        julia_backend._julia_main()


def test_run_pathway_rejects_unknown_backend():
    with pytest.raises(ValueError, match="backend"):
        run_pathway("x", backend="gurobi")


def test_run_pathway_rejects_materials_with_julia():
    with pytest.raises(ValueError, match="only available with backend='ampl'"):
        run_pathway("x", backend="julia", materials=True)


@pytest.mark.parametrize("option", [{"mip_gap": 1e-4}, {"time_limit": 100}])
def test_run_pathway_rejects_julia_only_options_with_ampl(option):
    with pytest.raises(ValueError, match="only used by backend='julia'"):
        run_pathway("x", **option)


def test_warning_when_the_ampl_model_changed(tmp_path, monkeypatch):
    reference = tmp_path / "mod_hashes.json"
    monkeypatch.setattr(julia_backend, "FINGERPRINT_FILE", reference)

    import json
    import warnings
    with warnings.catch_warnings():
        warnings.simplefilter("error")                                   # no reference recorded: no warning
        julia_backend._warn_if_port_outdated()
        reference.write_text(json.dumps(julia_backend.mod_fingerprints()))   # reference = current files: no warning
        julia_backend._warn_if_port_outdated()

    outdated = {**julia_backend.mod_fingerprints(), "shared/model/QC_es_main.mod": "0" * 64}
    reference.write_text(json.dumps(outdated))
    with pytest.warns(UserWarning, match="AMPL model changed.*QC_es_main.mod"):
        julia_backend._warn_if_port_outdated()


def test_pathway_results_remembers_its_folder():
    r = PathwayResults({"a": 1}, out_dir="somewhere")
    assert isinstance(r, dict) and r["a"] == 1 and r.out_dir == "somewhere"
