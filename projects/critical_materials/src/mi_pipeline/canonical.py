"""Canonical EnergyScope technology lists for the material-intensity pipeline.

Parsed directly from shared/data/QC_data.dat (the authoritative EnergyScope-Quebec
data file) rather than hand-maintained, so the pipeline stays in sync if the model's
technology sets ever change.
"""
import re
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[4]  # .../EnergyScope-Quebec
QC_DATA_PATH = _REPO_ROOT / 'shared' / 'data' / 'QC_data.dat'

ELECTRICITY_CATEGORIES = ['ELECTRICITY_LV', 'ELECTRICITY_MV', 'ELECTRICITY_HV', 'ELECTRICITY_EHV']
FUEL_CELL_TECHS = ['AFC', 'PAFC', 'PEMFC', 'SOFC']
STORAGE_TECHS_IN_SCOPE = ['HYDRO_STORAGE']  # the only STORAGE_TECH entry that's an electricity-production asset
_EXCLUDE_PREFIXES = ('TRAFO_',)   # grid transformers: not a material-intensity-per-GW generation asset
_EXCLUDE_TECHS = {'AN_DIG_SI'}    # anaerobic digestion: not an electricity-production tech


def _parse_indexed_sets(text, set_name):
    """Parse every `set {set_name}["KEY"] := tok tok ... ;` block, across line wraps."""
    pattern = re.compile(
        rf'set\s+{re.escape(set_name)}\s*\[\s*"([^"]+)"\s*\]\s*:=\s*(.*?);',
        re.DOTALL,
    )
    return {key: body.split() for key, body in pattern.findall(text)}


def _parse_plain_set(text, set_name):
    """Parse a single `set {set_name} := tok tok ... ;` block (commented-out lines
    starting with '#' are ignored)."""
    pattern = re.compile(
        rf'^set\s+{re.escape(set_name)}\s*:=\s*(.*?);',
        re.DOTALL | re.MULTILINE,
    )
    match = pattern.search(text)
    return match.group(1).split() if match else []


def electricity_techs(path=QC_DATA_PATH):
    """The ES electricity-production technology names (LV/MV/HV/EHV), excluding
    grid transformers (TRAFO_*) and non-generation techs (AN_DIG_SI)."""
    text = Path(path).read_text(encoding='utf-8')
    sets = _parse_indexed_sets(text, 'TECHNOLOGIES_OF_END_USES_TYPE')
    techs = []
    for cat in ELECTRICITY_CATEGORIES:
        for tok in sets.get(cat, []):
            if tok.startswith(_EXCLUDE_PREFIXES) or tok in _EXCLUDE_TECHS:
                continue
            techs.append(tok)
    return sorted(set(techs))


def storage_techs_in_scope(path=QC_DATA_PATH):
    """HYDRO_STORAGE only: the electricity-relevant entry of STORAGE_TECH
    (DHN/DEC thermal storage are out of scope for this pipeline)."""
    text = Path(path).read_text(encoding='utf-8')
    storage = set(_parse_plain_set(text, 'STORAGE_TECH'))
    return sorted(t for t in STORAGE_TECHS_IN_SCOPE if t in storage)


def fuel_cell_techs(path=QC_DATA_PATH):
    """AFC/PAFC/PEMFC/SOFC, found under HEAT_LOW_T_DECEN in QC_data.dat but tracked
    here as material-intensity technologies alongside electricity production."""
    text = Path(path).read_text(encoding='utf-8')
    sets = _parse_indexed_sets(text, 'TECHNOLOGIES_OF_END_USES_TYPE')
    heat = sets.get('HEAT_LOW_T_DECEN', [])
    return sorted(t for t in FUEL_CELL_TECHS if t in heat)


def all_target_techs(path=QC_DATA_PATH):
    """Full V1 scope for this pipeline: electricity production + hydro storage + fuel cells."""
    return sorted(set(electricity_techs(path)) | set(storage_techs_in_scope(path)) | set(fuel_cell_techs(path)))


if __name__ == '__main__':
    techs = all_target_techs()
    print(f"{len(techs)} technologies in scope:")
    for t in techs:
        print(' -', t)
