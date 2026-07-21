"""Coverage report (console-only): which EnergyScope technologies actually have
usable material-intensity data, vs. placeholder zeros, vs. genuinely unmapped.

Material_intensities_energyscope.xlsx (including its Mapping/Overrides sheets)
is external/read-only input -- nothing here writes to it. Colors, the `group`
column, etc. are the user's to maintain by hand in Excel.
"""
import pandas as pd

from . import canonical
from .mapping import load_mapping

STATUS_ORDER = ['not_mapped', 'not_yet_modeled', 'placeholder_zero', 'integrated']


def build_report(mapping, intensities):
    """DataFrame indexed by energyscope_tech: mapping_type, confidence, status.

    status is:
      - 'not_mapped'       if mapping_type == 'not_mapped' (no literature source
                           configured yet -- this covers most non-electricity techs
                           today, e.g. heat/mobility/storage groups)
      - 'not_yet_modeled'  if the tech claims real data (mapping_type != 'not_mapped')
                           but isn't (yet) in QC_data.dat -- mapped here for later,
                           excluded from the actual output files
      - 'placeholder_zero' if mapped but every material/year value is 0
      - 'integrated'       otherwise (at least one nonzero value)
    """
    canonical_techs = set(canonical.all_target_techs())
    rows = []
    for tech, row in mapping.iterrows():
        if row['mapping_type'] == 'not_mapped':
            status = 'not_mapped'
        elif tech not in canonical_techs:
            status = 'not_yet_modeled'
        elif (intensities[tech] == 0).all().all():
            status = 'placeholder_zero'
        else:
            status = 'integrated'
        rows.append({
            'energyscope_tech': tech,
            'mapping_type': row['mapping_type'],
            'confidence': row['confidence'],
            'status': status,
        })
    return pd.DataFrame(rows).set_index('energyscope_tech')


def print_report(report):
    counts = report['status'].value_counts().reindex(STATUS_ORDER, fill_value=0)
    print("Coverage report:")
    for status in STATUS_ORDER:
        print(f"  {status:17s}: {counts[status]}")
    for status in STATUS_ORDER:
        techs = sorted(report.index[report['status'] == status])
        if techs:
            print(f"\n{status} ({len(techs)}):")
            for t in techs:
                print(f"  - {t}")


if __name__ == '__main__':
    from .aggregate import compute_all
    mapping = load_mapping()
    intensities = compute_all()
    report = build_report(mapping, intensities)
    print_report(report)
