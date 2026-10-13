# Impact environnemental evite par le recyclage: recycle x (impact primaire - impact secondaire)
import re
from pathlib import Path

import pandas as pd

IMPACTS_DAT = Path(__file__).resolve().parent / 'ampl_files' / 'Material_impacts.dat'
FLOW_KEYS = {'used': 'Used_recycled_material', 'recycled': 'Recycled_material'}


# Impacts primaire/secondaire par matiere (index: code court), lus dans ampl_files/Material_impacts.dat
def load_material_impacts(path=IMPACTS_DAT):
    values = {}
    for name, material, value in re.findall(r"let\s+(impact_primary|impact_secondary)\['(\w+)'\]\s*:=\s*([-+0-9.eE]+)",
                                          Path(path).read_text(encoding='utf-8')):
        values.setdefault(material, {})[name] = float(value)
    return pd.DataFrame.from_dict(values, orient='index', columns=['impact_primary', 'impact_secondary']).rename_axis('material')


# Impact evite [kt eq./an] par (Years, Materials), pour les matieres de Material_impacts.dat.
# basis='used': recycle reellement utilise contre la demande (remplace de la production primaire);
# basis='recycled': recycle total de l'annee, stocke ou non.
def avoided_impact(results_materials, basis='used', impacts=None):
    impacts = load_material_impacts() if impacts is None else impacts
    key = FLOW_KEYS[basis]
    flow = results_materials[key][key].groupby(level=['Years', 'Materials']).sum()
    flow = flow[flow.index.get_level_values('Materials').isin(impacts.index)]
    saving = impacts['impact_primary'] - impacts['impact_secondary']  # kg eq./kg = t eq./t
    return (flow * flow.index.get_level_values('Materials').map(saving)).div(1000).rename('Avoided_impact')


# Cumul sur l'horizon [kt eq.], meme convention que les autres _cumulative: valeurs annuelles x 5 ans
def avoided_impact_cumulative(avoided):
    ordered = avoided.sort_index(level=['Materials', 'Years'])
    return (ordered * 5).groupby(level='Materials').cumsum().rename('Avoided_impact_cumulative')
