"""Load and validate the Mapping/Overrides sheets in
Material_intensities_energyscope.xlsx -- the hand-edited matching table between
EnergyScope technologies and the literature sub-technologies in that same
workbook's MI_Energy/MS_Energy_Disag/MS_Energy_Ag sheets.

The whole file (including these two sheets) is treated as external/read-only:
the pipeline never writes to it. Colors and any other bookkeeping are the
user's to maintain by hand in Excel.
"""
import pandas as pd

from . import canonical
from .sources import SOURCE_XLSX

MAPPING_XLSX = SOURCE_XLSX

VALID_MAPPING_TYPES = {'direct', 'aggregate', 'disaggregate', 'not_mapped'}
VALID_CONFIDENCE = {'sourced', 'proxy', 'uncertain', ''}


def load_mapping(path=MAPPING_XLSX):
    """Return the Mapping sheet as a DataFrame indexed by energyscope_tech, with
    `subtechs` parsed into a list of MI_Energy column names."""
    df = pd.read_excel(path, sheet_name='Mapping', dtype=str).fillna('')
    df['subtechs'] = df['subtechs'].apply(lambda s: [t.strip() for t in s.split(',') if t.strip()])
    df = df.set_index('energyscope_tech', drop=False)
    return df


def load_overrides(path=MAPPING_XLSX, scenario='baseline'):
    """Return Overrides rows for the given scenario (empty DataFrame for 'baseline'
    or a scenario name with no matching rows)."""
    df = pd.read_excel(path, sheet_name='Overrides', dtype=str)
    df = df[df['scenario'] == scenario].copy()
    if not df.empty:
        df['override_value'] = pd.to_numeric(df['override_value'])
    return df


def validate_mapping(df, path=MAPPING_XLSX):
    """Cross-check the mapping table against the canonical EnergyScope tech list and
    basic schema rules. Raises ValueError listing every hard problem found (not just
    the first), since this is meant to catch hand-editing mistakes in the Mapping sheet.

    A tech present in the Mapping sheet but not (yet) in QC_data.dat is only a
    warning, not an error -- it lets you pre-fill the mapping for a planned/future
    EnergyScope technology before it's added to the model. build_table.py skips
    these when writing output rows.
    """
    problems = []

    canonical_techs = set(canonical.all_target_techs())
    mapped_techs = set(df.index)
    missing = canonical_techs - mapped_techs
    if missing:
        problems.append(f"Techs in scope but missing from {path.name}: {sorted(missing)}")

    # Only techs that actually claim real data (mapping_type != 'not_mapped') need
    # to exist in QC_data.dat -- a not_mapped row for e.g. a heat/mobility tech the
    # Mapping sheet doesn't yet cover computation for is expected and silent.
    claims_real_data = df.index[df['mapping_type'] != 'not_mapped']
    not_yet_modeled = set(claims_real_data) - canonical_techs
    if not_yet_modeled:
        print(f"[mapping] Note: {sorted(not_yet_modeled)} are in {path.name} but not yet in "
              f"QC_data.dat -- pre-filled for later, skipped when writing output.")

    bad_types = set(df['mapping_type']) - VALID_MAPPING_TYPES
    if bad_types:
        problems.append(f"Invalid mapping_type value(s): {sorted(bad_types)} (expected one of {VALID_MAPPING_TYPES})")

    bad_confidence = set(df['confidence']) - VALID_CONFIDENCE
    if bad_confidence:
        problems.append(f"Invalid confidence value(s): {sorted(bad_confidence)} (expected one of {VALID_CONFIDENCE - {''}})")

    for tech, row in df.iterrows():
        if row['mapping_type'] in ('direct', 'aggregate', 'disaggregate') and not row['subtechs']:
            problems.append(f"{tech}: mapping_type='{row['mapping_type']}' but 'subtechs' is empty")
        if row['mapping_type'] == 'direct' and len(row['subtechs']) != 1:
            problems.append(f"{tech}: mapping_type='direct' expects exactly 1 subtech, got {row['subtechs']}")

    if problems:
        raise ValueError(f"{path.name}'s Mapping sheet validation failed:\n- " + "\n- ".join(problems))


if __name__ == '__main__':
    mapping = load_mapping()
    validate_mapping(mapping)
    print(f"OK: {len(mapping)} techs loaded and validated from {MAPPING_XLSX.name}")
    print(mapping['mapping_type'].value_counts())
