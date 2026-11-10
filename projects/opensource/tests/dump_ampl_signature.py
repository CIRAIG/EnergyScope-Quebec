"""Dumps the signature of the AMPL pathway model (without solving): indexing sets of every variable, parameter and set.

Run it again whenever a declaration changes in a .mod file (new variable, parameter or set, or modified indices), then copy the
result (`ampl_signature.json` in the temporary folder) to `EnergyScopeQC/data/ampl_signature.json`.
Adding an element to an existing set (for example a new technology) does not change the signature."""
import importlib.util, json, os, sys, tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
spec = importlib.util.spec_from_file_location("cmp", ROOT / "projects" / "opensource" / "tests" / "compare_pathway_with_ampl.py")
cmp = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cmp)

from amplpy import AMPL

with tempfile.TemporaryDirectory() as td:
    tmp = Path(td)
    empty_fix = tmp / "fix.mod"; empty_fix.write_text("", encoding="utf8")
    M, D, SM = cmp.M, cmp.D, cmp.SM
    mod_1 = [SM / "QC_es_main.mod", M / "PES_main.mod", M / "PES_obj_pathway.mod", M / "PES_store_variables.mod"]
    dats = [M / "PES_data_years_active.dat", cmp.window_file(tmp), M / "PES_data_set_AGE_2020.dat", M / "PES_data_remaining.dat"]
    mod_2 = [M / "EXTRA_INFOS.dat", D / "QC_data.dat", M / "PES_scenarios.mod", D / "EUD" / "out_eud.dat",
             D / "Techs" / "out_techs.dat", D / "Shares" / "out_shares.dat", M / "PES_data_pathway.dat",
             M / "PES_data_decom_allowed_2020.dat", empty_fix]
    a = AMPL()
    os.chdir(M)
    for f in mod_1: a.read(str(f))
    for f in dats: a.read_data(str(f))
    for f in mod_2: a.read(str(f))
    a.get_value("_nvars")

    sig = {"variables": {}, "parameters": {}, "sets": {}}
    for name, v in a.get_variables():
        sig["variables"][name] = {"index": list(v.get_indexing_sets())}
    for name, p in a.get_parameters():
        try:
            n = p.num_instances()
        except Exception:
            n = -1
        sig["parameters"][name] = {"index": list(p.get_indexing_sets()), "n": n}
    for name, s_ in a.get_sets():
        try:
            inst = s_.num_instances()
        except Exception:
            inst = -1
        sig["sets"][name] = {"index": list(s_.get_indexing_sets()), "n_instances": inst}
    out = Path(os.environ["TEMP"]) / "ampl_signature.json"
    out.write_text(json.dumps(sig, indent=1, ensure_ascii=False), encoding="utf8")
    print("signature written:", out, "|", {k: len(v) for k, v in sig.items()})
