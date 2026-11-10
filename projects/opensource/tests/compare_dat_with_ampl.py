"""
Compare what the Julia parser (ampl_dat.jl) reads with what AMPL loads, for the pathway data files.
No value is hard-coded: the comparison follows the .dat files.

usage: python compare_dat_with_ampl.py [julia_dump.tsv]
  - without argument, runs Julia (scripts/dump_pathway.jl) to produce the dump.
Output: summary and first differences; exit code 1 if any difference.
Julia executable: environment variable JULIA, or `julia` on the PATH.
"""
import math, os, shutil, subprocess, sys, tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
JULIA = os.environ.get("JULIA") or shutil.which("julia")
if JULIA is None:
    sys.exit("Julia not found. Set the JULIA environment variable to the path of julia.exe, or add julia to the PATH.")
PKG = ROOT / "projects" / "opensource" / "EnergyScopeQC"
SEP = "\x1f"
M = ROOT / "projects" / "pathway" / "model"; D = ROOT / "shared" / "data"


def norm(x):
    """Key/value normalised as text: 1.0 -> '1', 'abc' -> 'abc'."""
    if isinstance(x, (int, float)) and not isinstance(x, bool):
        return str(int(x)) if float(x).is_integer() else repr(float(x))
    s = str(x)
    try:
        f = float(s)
        return str(int(f)) if f.is_integer() and "." not in s.replace("e", "") and "inf" not in s.lower() else s
    except ValueError:
        return s


def load_julia(path):
    P, S, I = {}, {}, {}
    for line in open(path, encoding="utf8"):
        t, name, key, val = line.rstrip("\n").split("\t")
        parts = [norm(k) for k in key.split(SEP) if k != ""]
        if t == "P":
            P.setdefault(name, {})[tuple(parts)] = float(val) if _isnum(val) else val
        elif t == "S":
            S[name] = set(parts)
        else:
            I.setdefault(name, {})[tuple(parts)] = {norm(v) for v in val.split(SEP) if v != ""}
    return P, S, I


def _isnum(v):
    try: float(v); return True
    except ValueError: return False


def load_ampl():
    from amplpy import AMPL
    a = AMPL()
    os.chdir(M)
    mod1 = [ROOT / "shared" / "model" / "QC_es_main.mod", M / "PES_main.mod", M / "PES_obj_pathway.mod", M / "PES_store_variables.mod"]
    mod2 = [M / "EXTRA_INFOS.dat", D / "QC_data.dat", M / "PES_scenarios.mod", D / "EUD" / "out_eud.dat",
            D / "Techs" / "out_techs.dat", D / "Shares" / "out_shares.dat", M / "PES_data_pathway.dat",
            M / "PES_data_decom_allowed_2020.dat"]
    dats = [M / "PES_data_years_active.dat", M / "PES_seq_opti.dat", M / "PES_data_set_AGE_2020.dat", M / "PES_data_remaining_wnd.dat"]
    for f in mod1 + mod2:
        a.read(str(f))
    for f in dats:
        a.read_data(str(f))
    return a


def ampl_param(a, name):
    p = a.get_parameter(name)
    if p.indexarity() == 0:
        return {(): p.value()}
    df = p.get_values().to_pandas()
    out = {}
    for idx, row in df.iterrows():
        idx = idx if isinstance(idx, tuple) else (idx,)
        out[tuple(norm(i) for i in idx)] = row.iloc[0]
    return out


def close(x, y):
    if isinstance(x, str) or isinstance(y, str):
        return str(x) == str(y)
    if math.isinf(x) or math.isinf(y):
        return x == y
    return math.isclose(x, y, rel_tol=1e-12, abs_tol=1e-15)


def main():
    dump = sys.argv[1] if len(sys.argv) > 1 else None
    if dump is None:
        dump = os.path.join(tempfile.gettempdir(), "jl_dump.tsv")
        subprocess.run([JULIA, f"--project={PKG}", str(PKG / "scripts" / "dump_pathway.jl"), dump], check=True)
    P, S, I = load_julia(dump)
    a = load_ampl()

    bad, n_cmp = [], 0
    for name, jd in sorted(P.items()):
        try:
            ad = ampl_param(a, name)
        except Exception as e:
            bad.append(f"[parameter missing in AMPL] {name} ({len(jd)} Julia values): {str(e)[:60]}")
            continue
        for k, jv in jd.items():
            n_cmp += 1
            if k not in ad:
                bad.append(f"[key missing in AMPL] {name}{k} = {jv}")
            elif not close(ad[k], jv):
                bad.append(f"[different value] {name}{k}: Julia={jv} AMPL={ad[k]}")
        # entries not read by Julia: AMPL must hold one common default value there
        extra = {v for k, v in ad.items() if k not in jd}
        if len(extra) > 1:
            bad.append(f"[AMPL has non-uniform values outside Julia] {name}: {sorted(map(str, extra))[:4]}")
    n_sets = 0
    for name, js in sorted(S.items()):
        try:
            av = {norm(x) for x in a.get_set(name).get_values().to_list()}
        except Exception:
            continue                      # derived set, not declared or not comparable
        n_sets += 1
        if av != js:
            bad.append(f"[different set] {name}: only in Julia={sorted(js-av)[:3]} only in AMPL={sorted(av-js)[:3]}")
    print(f"compared: {n_cmp} parameter values ({len(P)} parameters), {n_sets} sets")
    print(f"differences: {len(bad)}")
    for b in bad[:40]:
        print("  ", b)
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
