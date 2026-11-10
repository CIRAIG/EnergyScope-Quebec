"""
Prints a GitHub warning when an AMPL model file differs from the version the Julia port was last checked against.

Standard library only (used by .github/workflows/julia-port-outdated.yml). Never fails: it only informs.
The list of files and the fingerprint rule are those of `shared/julia_backend.py` (MODEL_FILES, mod_fingerprints).

usage: python projects/opensource/tests/check_mod_hashes.py
"""
import ast
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
REFERENCE = ROOT / "projects" / "opensource" / "EnergyScopeQC" / "data" / "mod_hashes.json"


def model_files() -> tuple:
    tree = ast.parse((ROOT / "shared" / "julia_backend.py").read_text(encoding="utf8"))
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(getattr(t, "id", None) == "MODEL_FILES" for t in node.targets):
            return ast.literal_eval(node.value)
    sys.exit("MODEL_FILES not found in shared/julia_backend.py")


def fingerprint(rel: str) -> str:
    text = (ROOT / rel).read_text(encoding="utf8", errors="replace").replace("\r\n", "\n").rstrip()
    return hashlib.sha256(text.encode("utf8")).hexdigest()


reference = json.loads(REFERENCE.read_text(encoding="utf8"))
changed = [f for f in model_files() if reference.get(f) != fingerprint(f)]

if changed:
    names = ", ".join(Path(f).name for f in changed)
    print(f"::warning title=Julia port may be out of date::The AMPL model changed ({names}) since the Julia version was last "
          "checked against it. See projects/opensource/MAINTENANCE.md.")
else:
    print("Julia port reference is up to date.")
