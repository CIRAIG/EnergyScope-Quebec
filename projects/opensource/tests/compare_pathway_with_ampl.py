"""
Structure of the pathway model, JuMP against AMPL (perfect foresight, a single window).

Compares the number of variables and the number of instances of EACH constraint, name by name. The AMPL model is loaded the way
`AmplObject.set_ampl` does for `run_pathway`: models (`mod_1`), then the window `.dat` files, then the `mod_2` files (`let`...).
The two files that `run_pathway` rewrites at every run (`PES_seq_opti.dat`, `PES_data_remaining_wnd.dat`) are replaced by
temporary files: NO file tracked by git is modified.

usage: python compare_pathway_with_ampl.py [N_year_opti N_year_overlap window]
Without argument: single window (perfect foresight). With arguments: window number `window` (0, 1, ...) of the myopic mode,
whose sets are written by AmplPreProcessor (as for run_pathway) and read by AMPL and by Julia.
Exit code 1 if any difference.
Julia executable: environment variable JULIA, or `julia` on the PATH.
"""
import os, re, shutil, subprocess, sys, tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
M = ROOT / "projects" / "pathway" / "model"
D = ROOT / "shared" / "data"
SM = ROOT / "shared" / "model"
PKG = ROOT / "projects" / "opensource" / "EnergyScopeQC"
JULIA = os.environ.get("JULIA") or shutil.which("julia")
if JULIA is None:
    sys.exit("Julia not found. Set the JULIA environment variable to the path of julia.exe, or add julia to the PATH.")


def window_file(tmp, spec=None):
    """PES_seq_opti.dat of the single window: all years but 2015, all phases but 2015_2020.
    With `spec = (N_year_opti, overlap, k)`: window k of the myopic mode, written by AmplPreProcessor."""
    if spec is not None:
        sys.path[:0] = [str(ROOT), str(ROOT / "projects" / "pathway" / "pylib")]
        from shared.julia_pathway import window_source
        from ampl_preprocessor import AmplPreProcessor
        pre = AmplPreProcessor(window_source(M, tmp), spec[0], spec[1])
        print(f"windows: {pre.years_opti}", flush=True)
        pre.write_seq_opti(spec[2])
        return tmp / "PES_seq_opti.dat"
    extra = (M / "EXTRA_INFOS.dat").read_text(encoding="utf8")
    years = re.search(r"set\s+YEARS\s*:=\s*([^;]*);", extra)[1].split()
    phases = re.search(r"set\s+PHASE\s*:=\s*([^;]*);", extra)[1].split()
    years = [y for y in years if y != "YEAR_2015"]
    phases = [p for p in phases if p != "2015_2020"]
    f = tmp / "PES_seq_opti.dat"
    f.write_text(f"set YEARS_WND := {' '.join(years)} ;\nset PHASE_WND := {' '.join(phases)} ;\n"
                 f"set YEARS_UP_TO := {' '.join(years)} ;\nset PHASE_UP_TO := {' '.join(phases)} ;\n"
                 "set YEAR_ONE;\nset YEAR_ONE_NEXT;\n", encoding="utf8")
    return f


def ampl_side(tmp, spec=None):
    from amplpy import AMPL
    empty_fix = tmp / "fix.mod"
    empty_fix.write_text("", encoding="utf8")
    mod_1 = [SM / "QC_es_main.mod", M / "PES_main.mod", M / "PES_obj_pathway.mod", M / "PES_store_variables.mod"]
    dats = [M / "PES_data_years_active.dat", window_file(tmp, spec), M / "PES_data_set_AGE_2020.dat", M / "PES_data_remaining.dat"]
    mod_2 = [M / "EXTRA_INFOS.dat", D / "QC_data.dat", M / "PES_scenarios.mod", D / "EUD" / "out_eud.dat",
             D / "Techs" / "out_techs.dat", D / "Shares" / "out_shares.dat", M / "PES_data_pathway.dat",
             M / "PES_data_decom_allowed_2020.dat", empty_fix]
    a = AMPL()
    os.chdir(M)
    for f in mod_1:
        a.read(str(f))
    for f in dats:
        a.read_data(str(f))
    for f in mod_2:
        a.read(str(f))
    nvars = int(a.get_value("_nvars"))            # forces the instantiation
    out = a.get_output("for {i in 1.._ncons} printf '%s\\n', _conname[i];")
    cons = {}
    for line in out.splitlines():
        line = line.strip()
        if line:
            base = line.split("[")[0]
            cons[base] = cons.get(base, 0) + 1
    return nvars, int(a.get_value("_ncons")), cons


def julia_side(tmp, spec=None):
    out = tmp / "jl_counts.tsv"
    cmd = [JULIA, f"--project={PKG}", str(PKG / "scripts" / "dump_pathway_counts.jl"), str(out)]
    if spec is not None:
        cmd.append(str(tmp / "PES_seq_opti.dat"))        # written by ampl_side (same file on both sides)
    subprocess.run(cmd, check=True)
    nvars, cons = 0, {}
    for line in out.read_text(encoding="utf8").splitlines():
        p = line.split("\t")
        if p[0] == "NVARS":
            nvars = int(p[1])
        else:
            cons[p[1]] = int(p[2])
    return nvars, cons


def main():
    spec = tuple(int(a) for a in sys.argv[1:4]) if len(sys.argv) >= 4 else None
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        print("AMPL: loading the pathway model...", flush=True)
        a_nvars, a_ncons, a_cons = ampl_side(tmp, spec)
        print(f"AMPL: {a_nvars} variables, {a_ncons} constraints, {len(a_cons)} families", flush=True)
        print("Julia: building...", flush=True)
        j_nvars, j_cons = julia_side(tmp, spec)
    bad = 0
    if a_nvars != j_nvars:
        print(f"  variables: AMPL={a_nvars} JuMP={j_nvars}"); bad += 1
    for n in sorted(set(a_cons) | set(j_cons)):
        x, y = a_cons.get(n, 0), j_cons.get(n, 0)
        if x != y:
            print(f"  constraint {n:40s} AMPL={x:>8} JuMP={y:>8}"); bad += 1
    print(f"variables: AMPL={a_nvars} JuMP={j_nvars} | constraint families: AMPL={len(a_cons)} JuMP={len(j_cons)} | differences: {bad}")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
