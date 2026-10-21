# Environmental impacts of the material flows: primary supply, recycling process, and impact avoided by recycling
import re
from pathlib import Path

import pandas as pd

IMPACTS_DAT = Path(__file__).resolve().parent / 'ampl_files' / 'Material_impacts.dat'


# Impacts primaire/secondaire par (matiere, indicateur), lus dans ampl_files/Material_impacts.dat
def load_material_impacts(path=IMPACTS_DAT):
    values = {}
    for name, material, indicator, value in re.findall(
            r"let\s+(impact_primary|impact_secondary)\['(\w+)','(\w+)'\]\s*:=\s*([-+0-9.eE]+)",
            Path(path).read_text(encoding='utf-8')):
        values.setdefault((material, indicator), {})[name] = float(value)
    impacts = pd.DataFrame.from_dict(values, orient='index', columns=['impact_primary', 'impact_secondary'])
    impacts.index = pd.MultiIndex.from_tuples(impacts.index, names=['material', 'indicator'])
    return impacts


# Impacts absolus [kt eq./an] par (Years, Materials, Indicators), annees de transition seulement:
# Imp_prim = approvisionnement primaire (Net_demand = demande brute - recycle utilise) x impact primaire,
# Imp_sec = matiere recyclee x impact du procede de recyclage, Imp_materials_total = somme des deux,
# Imp_no_recycling = reference sans recyclage (meme demande brute, tout en primaire),
# Imp_avoided = Imp_no_recycling - Imp_materials_total (= Imp_prim + Imp_sec + Imp_avoided = Imp_no_recycling).
def absolute_impacts(results_materials, impacts=None):
    impacts = load_material_impacts() if impacts is None else impacts
    primary = results_materials['Net_demand']['Net_demand']
    primary = primary[primary.index.get_level_values('Years') != 'YEAR_2020']
    recycled = results_materials['Recycled_material']['Recycled_material'].groupby(level=['Years', 'Materials']).sum()
    recycled = recycled[recycled.index.get_level_values('Years') != 'YEAR_2020']
    used = results_materials['Used_recycled_material']['Used_recycled_material'].groupby(level=['Years', 'Materials']).sum()
    used = used[used.index.get_level_values('Years') != 'YEAR_2020']

    def weighted(flow, factors, name):
        parts = {}
        for indicator in impacts.index.get_level_values('indicator').unique():
            factor = impacts.xs(indicator, level='indicator')[factors]  # kg eq./kg = t eq./t
            kept = flow[flow.index.get_level_values('Materials').isin(factor.index)]
            parts[indicator] = (kept * kept.index.get_level_values('Materials').map(factor)).div(1000)
        if not parts:
            return pd.Series(dtype=float, name=name, index=pd.MultiIndex.from_arrays([[], [], []], names=['Years', 'Materials', 'Indicators']))
        out = pd.concat(parts, names=['Indicators']).reorder_levels(['Years', 'Materials', 'Indicators']).sort_index()
        return out.rename(name)

    imp_prim = weighted(primary, 'impact_primary', 'Imp_prim')
    imp_sec = weighted(recycled, 'impact_secondary', 'Imp_sec')
    total = imp_prim.add(imp_sec, fill_value=0).rename('Imp_materials_total')
    no_recycling = weighted(primary.add(used, fill_value=0), 'impact_primary', 'Imp_no_recycling')
    avoided = no_recycling.sub(total, fill_value=0).rename('Imp_avoided')
    return {'Imp_prim': imp_prim, 'Imp_sec': imp_sec, 'Imp_materials_total': total, 'Imp_no_recycling': no_recycling,
            'Imp_avoided': avoided}


# Cumul sur l'horizon [kt eq.], meme convention que les autres _cumulative: valeurs annuelles x 5 ans
def cumulative_over_years(series):
    others = [name for name in series.index.names if name != 'Years']
    ordered = series.sort_index(level=others + ['Years'])
    return (ordered * 5).groupby(level=others).cumsum().rename(f'{series.name}_cumulative')

