"""
Full check of the Julia port, to run before a commit:
  1. Julia tests (parser, fixtures, overrides, structure of the real files, snapshot model);
  2. JuMP / AMPL parity on the snapshot (AMPL references are cached if the inputs have not changed).

usage: python check_port.py [--refresh]      (--refresh: run AMPL again, full comparison)
Exit code 0 if everything passes.
Julia executable: environment variable JULIA, or `julia` on the PATH.
"""
import os, shutil, subprocess, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
JULIA = os.environ.get("JULIA") or shutil.which("julia")
if JULIA is None:
    sys.exit("Julia not found. Set the JULIA environment variable to the path of julia.exe, or add julia to the PATH.")
PKG = HERE.parent / "EnergyScopeQC"


def step(title, cmd):
    print(f"\n=== {title} ===", flush=True)
    r = subprocess.run(cmd)
    if r.returncode != 0:
        print(f"FAILED: {title}", flush=True)
        sys.exit(r.returncode)


def main():
    step("Julia tests", [JULIA, f"--project={PKG}", str(PKG / "test" / "runtests.jl")])
    step("JuMP / AMPL parity (snapshot)", [sys.executable, "-u", str(HERE / "compare_snapshot_with_ampl.py")] + sys.argv[1:])
    print("\nJulia port: all checks passed.", flush=True)


if __name__ == "__main__":
    main()
