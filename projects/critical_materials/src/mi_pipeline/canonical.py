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
ELECTROLYSIS_TECHS = ['ALKALINE_ELECTROLYSIS', 'PEM_ELECTROLYSIS', 'SOEC_ELECTROLYSIS']
STORAGE_TECHS_IN_SCOPE = ['HYDRO_STORAGE']  # the only STORAGE_TECH entry that's an electricity-production asset
PRIVATE_MOB_CATEGORIES = ['MOB_PRIVATE_SD', 'MOB_PRIVATE_MD', 'MOB_PRIVATE_LD', 'MOB_PRIVATE_ELD']
_EXCLUDE_PREFIXES = ('TRAFO_',)   # grid transformers: not a material-intensity-per-GW generation asset
_EXCLUDE_TECHS = {'AN_DIG_SI'}    # anaerobic digestion: not an electricity-production tech

REF_SIZE_PATH = _REPO_ROOT / 'shared' / 'data' / 'Techs' / 'out_techs.dat'
_SIZE_SUFFIX_RE = re.compile(r'_(SD|MD|LD|ELD)$')


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


def electrolysis_techs(path=QC_DATA_PATH):
    """ALKALINE_ELECTROLYSIS/PEM_ELECTROLYSIS/SOEC_ELECTROLYSIS, found under the
    broad INFRASTRUCTURE set in QC_data.dat (alongside H2/NG/SNG storage,
    compression, and other H2-production routes like SMR/ATR/gasification)
    but tracked here as their own material-intensity category, matching the
    MI_H2 sheet -- which only covers electrolyzers, not every H2 route."""
    text = Path(path).read_text(encoding='utf-8')
    infra = set(_parse_plain_set(text, 'INFRASTRUCTURE'))
    return sorted(t for t in ELECTROLYSIS_TECHS if t in infra)


def private_mobility_techs(path=QC_DATA_PATH):
    """The 160 CAR_*/SUV_* private-mobility technology names: 128 size-classed
    ones (SD/MD/LD/ELD, from TECHNOLOGIES_OF_END_USES_TYPE["MOB_PRIVATE_*"]) plus
    the 32 bare-family ones (from TECHNOLOGIES_OF_PRIVATEMOB_ALL_DISTANCES) --
    both are separately unioned into the model's real `set TECHNOLOGIES` (see
    shared/model/QC_es_main.mod), so both count as in-scope."""
    text = Path(path).read_text(encoding='utf-8')
    sets = _parse_indexed_sets(text, 'TECHNOLOGIES_OF_END_USES_TYPE')
    techs = []
    for cat in PRIVATE_MOB_CATEGORIES:
        techs.extend(sets.get(cat, []))
    techs.extend(_parse_plain_set(text, 'TECHNOLOGIES_OF_PRIVATEMOB_ALL_DISTANCES'))
    return sorted(set(techs))


def all_target_techs(path=QC_DATA_PATH):
    """Full scope for this pipeline: electricity production + hydro storage +
    fuel cells + electrolyzers + private mobility."""
    return sorted(set(electricity_techs(path)) | set(storage_techs_in_scope(path))
                  | set(fuel_cell_techs(path)) | set(electrolysis_techs(path))
                  | set(private_mobility_techs(path)))


def family_of(tech):
    """Strip the _SD/_MD/_LD/_ELD size-class suffix, e.g. 'CAR_EV_SD' -> 'CAR_EV'.
    All size classes of a given powertrain share the same vehicle spec (body/
    battery/motor) and the same ref_size -- there's only ever one entry for the
    bare family name in out_techs.dat, not one per size class."""
    return _SIZE_SUFFIX_RE.sub('', tech)


def load_ref_size(path=REF_SIZE_PATH):
    """Parse `let ref_size['YEAR_XXXX','FAMILY'] := value ;` lines from
    shared/data/Techs/out_techs.dat (the file run_pathway_materials.py actually
    feeds to AMPL) into a {(year, family): value} dict. Only bare-family names
    (no size suffix) are ever assigned ref_size in that file."""
    text = Path(path).read_text(encoding='utf-8')
    pattern = re.compile(r"let\s+ref_size\['(YEAR_\d+)','([A-Za-z0-9_]+)'\]\s*:=\s*([0-9.eE+-]+)\s*;")
    return {(year, tech): float(value) for year, tech, value in pattern.findall(text)}


if __name__ == '__main__':
    techs = all_target_techs()
    print(f"{len(techs)} technologies in scope:")
    for t in techs:
        print(' -', t)
