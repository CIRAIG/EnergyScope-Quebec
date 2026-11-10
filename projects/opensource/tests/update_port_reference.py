"""
Records the fingerprints of the AMPL model files in `EnergyScopeQC/data/mod_hashes.json`.

Run it ONLY after the Julia port has been updated and checked against AMPL (see projects/opensource/MAINTENANCE.md):
as long as a model file differs from the recorded fingerprint, `backend='julia'` warns the user that the Julia version may
no longer match the AMPL model.

usage: python projects/opensource/tests/update_port_reference.py
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from shared.julia_backend import FINGERPRINT_FILE, mod_fingerprints

new = mod_fingerprints()
old = json.loads(FINGERPRINT_FILE.read_text(encoding="utf8")) if FINGERPRINT_FILE.exists() else {}
FINGERPRINT_FILE.write_text(json.dumps(new, indent=1, sort_keys=True) + "\n", encoding="utf8")
changed = [f for f in new if old.get(f) != new[f]]
print(f"reference written: {FINGERPRINT_FILE}")
print("changed since the previous reference:", ", ".join(changed) if changed else "none")
