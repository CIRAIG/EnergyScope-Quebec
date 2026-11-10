"""
Static parity of AMPL and JuMP for the snapshot, with the same solver (HiGHS) on both sides.

For each year:
  1. number of variables;
  2. number of instances of EACH constraint (name by name, like AMPL's `card(constraint)`);
  3. objective value (relative tolerance `--tol`, 1e-6 by default).

No value is hard-coded: the test follows the .dat files. Years go from 2020 to 2050 (2050 includes the
generic scenario, which contains `subject to` constraints).

Cache: the AMPL result only depends on the input files (.mod, .dat, scenario). It is kept in
`ampl_reference_snapshot.json` together with a hash of these files. If the hash is unchanged, AMPL is not
run again (a few minutes instead of ~10); if a .dat or .mod changes, it is recomputed automatically.
`--refresh` forces the full comparison.

usage: python compare_snapshot_with_ampl.py [--years 2020 2030] [--tol 1e-6] [--refresh]
Exit code 1 if any difference.
Julia executable: environment variable JULIA, or `julia` on the PATH.
"""
import argparse, hashlib, json, os, shutil, subprocess, sys, tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
JULIA = os.environ.get("JULIA") or shutil.which("julia")
if JULIA is None:
    sys.exit("Julia not found. Set the JULIA environment variable to the path of julia.exe, or add julia to the PATH.")
PKG = ROOT / "projects" / "opensource" / "EnergyScopeQC"
D = ROOT / "shared" / "data"
M = ROOT / "shared" / "model"


def julia_all(years, gap, workdir):
    """One Julia process for all years (compilation is paid once)."""
    subprocess.run([JULIA, f"--project={PKG}", str(PKG / "scripts" / "solve_snapshots.jl"), str(workdir), str(gap)]
                   + [str(y) for y in years], check=True)
    out = {}
    for y in years:
        res = {"cons": {}}
        for line in (Path(workdir) / f"jl_{y}.tsv").read_text(encoding="utf8").splitlines():
            parts = line.split("\t")
            if parts[0] == "STATUS": res["status"] = parts[1]
            elif parts[0] == "OBJECTIVE": res["obj"] = float(parts[1])
            elif parts[0] == "NVARS": res["nvars"] = int(parts[1])
            elif parts[0] == "CON": res["cons"][parts[1]] = int(parts[2])
        out[y] = res
    return out


def ampl_side(year, gap):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "python"))
    import esqc_run                                     # AMPL loading shared with the notebooks (single source)
    a = esqc_run.load_ampl_snapshot(year)
    nvars = int(a.get_value("_nvars"))     # also forces the model instantiation
    # A single AMPL command (calling num_instances() one constraint at a time makes amplpy crash intermittently).
    out = a.get_output("for {i in 1.._ncons} printf '%s\\n', _conname[i];")
    cons = {}
    for line in out.splitlines():
        line = line.strip()
        if line:
            base = line.split("[")[0]
            cons[base] = cons.get(base, 0) + 1
    a.option["solver"] = "highs"
    a.option["highs_options"] = f"outlev=0 mip:gap={gap}"      # same relative tolerance as JuMP (mip_rel_gap)
    a.solve()
    return {"nvars": nvars, "cons": cons, "obj": float(a.get_objective("obj").value()),
            "status": a.get_value("solve_result")}


CACHE = Path(__file__).resolve().parent / "ampl_reference_snapshot.json"


def input_files(year):
    """Everything the AMPL result depends on for one year: model, data, scenario."""
    files = [M / "QC_es_main.mod", M / "QC_objective_function.mod", D / "QC_data.dat",
             D / "Techs" / f"QC_techs_{year}.dat", D / "Shares" / f"QC_shares_{year}.dat", D / "EUD" / f"QC_eud_{year}.dat"]
    if year == 2050:
        files.append(ROOT / "shared" / "scenarios" / "QC_generic_scenario_2050.dat")
    return files


def inputs_hash(year, gap):
    h = hashlib.sha256()
    h.update(f"v1|{year}|{gap}".encode())
    for f in input_files(year):
        h.update(f.name.encode()); h.update(f.read_bytes())
    return h.hexdigest()


def ampl_reference(year, gap, refresh):
    """AMPL result for the year: read from the cache if the input files are unchanged, otherwise recomputed."""
    cache = json.loads(CACHE.read_text(encoding="utf8")) if CACHE.exists() else {}
    key, h = str(year), inputs_hash(year, gap)
    if not refresh and cache.get(key, {}).get("hash") == h:
        return cache[key]["result"], True
    res = ampl_side(year, gap)
    cache[key] = {"hash": h, "result": res}
    CACHE.write_text(json.dumps(cache, indent=1, sort_keys=True), encoding="utf8")
    return res, False


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--years", type=int, nargs="*", default=[2020, 2025, 2030, 2035, 2040, 2045, 2050])
    ap.add_argument("--tol", type=float, default=1e-6, help="relative tolerance on the objective")
    ap.add_argument("--gap", type=float, default=1e-7, help="relative MIP gap imposed on both solvers")
    ap.add_argument("--refresh", action="store_true", help="run AMPL even if the cache is up to date (full comparison)")
    args = ap.parse_args()
    bad = 0
    with tempfile.TemporaryDirectory() as wd:
        J = julia_all(args.years, args.gap, wd)
        for y in args.years:
            j = J[y]
            a, from_cache = ampl_reference(y, args.gap, args.refresh)
            problems = []
            if j["nvars"] != a["nvars"]:
                problems.append(f"variables: AMPL={a['nvars']} JuMP={j['nvars']}")
            for n in sorted(set(a["cons"]) | set(j["cons"])):
                x, z = a["cons"].get(n, 0), j["cons"].get(n, 0)
                if x != z:
                    problems.append(f"constraint {n}: AMPL={x} JuMP={z}")
            rel = abs(j["obj"] - a["obj"]) / max(1.0, abs(a["obj"]))
            if rel > args.tol:
                problems.append(f"objective: AMPL={a['obj']!r} JuMP={j['obj']!r} (relative difference {rel:.2e})")
            print(f"{y}  AMPL {a['status']:7s} {a['obj']:.8f} | JuMP {j['status']:8s} {j['obj']:.8f} | relative difference {rel:.1e}"
                  f" | {len(a['cons'])} constraints | {'OK' if not problems else 'DIFFERENCE'}"
                  f" | AMPL {'(cached)' if from_cache else '(recomputed)'}", flush=True)
            for p in problems:
                print("     ", p)
            bad += bool(problems)
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
