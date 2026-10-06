# Console-only coverage report: which techs have usable material-intensity data (vs placeholder zeros, unmapped)
import pandas as pd

from . import canonical
from .mapping import load_mapping

STATUS_ORDER = ['not_mapped', 'not_yet_modeled', 'placeholder_zero', 'integrated']


# DataFrame by energyscope_tech: mapping_type + status (not_mapped / not_yet_modeled / placeholder_zero / integrated)
def build_report(mapping, intensities):
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
