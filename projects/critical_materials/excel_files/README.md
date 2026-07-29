# Material_intensities_energyscope.xlsx

## À quoi sert ce classeur

Ce classeur est l'entrée du code et permet de créer les fichiers `ampl_files/Material_intensity.dat` 
et `technologies_mi_all_years.xlsx`, 
qui contiendront les intensités matérielles des technologies EnergyScope-Québec,  
qui seront donc utilisé par le code pour générer les résultats.
Données sources (littérature) + table de correspondance technologique pour le
pipeline `src/mi_pipeline/`.

Ce classeur est traité comme une **entrée en lecture seule** par le code :
rien dans `src/mi_pipeline/` n'écrit dedans. Toute modification (mapping,
matériaux, données sources) se fait à la main dans Excel, puis on relance le
pipeline pour régénérer les fichiers de sortie.

## Origine des données

La majorité des feuilles proviennent des données supplémentaires publiées par :

> Bieuville, P., Majeau-Bettez, G., de Bortoli, A. (2025). *Metal bottlenecks
> along energy transitions call for technology flexibility and sobriety.*

Voir la feuille `Table of content` pour la description originale de ces
feuilles — ne pas la modifier, elle documente les données publiées telles quelles.

## Feuilles ajoutées pour le pipeline

- **`Materials`** — liste maîtresse des matériaux (nom complet + code court).
  C'est la seule feuille à modifier pour ajouter un matériau : le code
  (`sources.py`/`build_table.py`) lit cette liste. Il faut aussi ajouter la valeur dans la/les feuille(s) `MI_*`
  concernée(s) ci-dessous.
- **`MI_Energy`** — intensité matérielle des sous-technologies électriques
  (t/GW), utilisée via la feuille `Mapping`.
- **`MI_Vehicles`** — intensité matérielle complète par véhicule
  (g/véhicule), par motorisation (ICEV/HEV/PHEV/EV/FCV). Source : Watari et
  al. 2019 / Fishman et al. 2018. Source par défaut du pipeline
  (`vehicle_source='watari'`).
- **`MI_Vehicles_Bieuville_Clean`** — source alternative, reconstruite à
  partir de la carrosserie + batterie (par chimie) + moteur (par type),
  pondérées par le mix de marché de `MS_Battery_Motor_LDV`. Utilisée avec
  `vehicle_source='bieuville'`. FCV n'y est pas couvert : la valeur
  `MI_Vehicles` est utilisée dans les deux cas pour cette motorisation.
- **`MS_Battery_Motor_LDV`** — part de marché par chimie de batterie (par
  année) et par type de moteur (fixe), utilisée uniquement par
  `MI_Vehicles_Bieuville_Clean`.
- **`MI_H2`** — intensité matérielle des 3 technologies d'électrolyse
  (Alcaline/PEM/SOEC), en t/GW.
- **`Mapping`** — table de correspondance entre chacune des ~690 technologies
  EnergyScope-Québec et la/les sous-techno(s) de la littérature ci-dessus.
  `mapping_type` = `direct`/`aggregate`/`disaggregate`/`not_mapped`. C'est
  cette feuille que le pipeline lit réellement pour savoir quoi calculer pour
  chaque techno.
- **`Overrides`** — valeurs forcées manuellement pour un scénario donné,
  appliquées après le calcul, (à retravailler).

Feuille à ignorer : `MI_Vehicles_Bieuville` (version brute non nettoyée,
remplacée par `MI_Vehicles_Bieuville_Clean`) — gardée seulement pour
traçabilité des valeurs d'origine.

## Comment l'utiliser

**Régénérer les fichiers de sortie** — depuis `projects/critical_materials/` :
```bash
python run_build_mi.py
```
ou dans un notebook :
```python
from run_build_mi import main
main()
```

**Ajouter un matériau** — ajouter une ligne dans `Materials` (nom complet +
code court), puis la valeur dans les feuilles `MI_*` où ce matériau a une
donnée. Aucun fichier `.py` à modifier.

**Ajouter ou modifier le mapping d'une technologie** — éditer sa ligne dans
`Mapping` (`mapping_type`, `subtechs`, `energy_source`/`ms_table` si
`aggregate`).

**Comparer les deux sources véhicule** :
```python
main(vehicle_source='watari')      # défaut
main(vehicle_source='bieuville')
```
Les deux écrivent dans les mêmes fichiers de sortie (pas de suffixe) — il
faut relancer `run_pathway_materials` entre les deux pour comparer les
résultats en bout de chaîne (voir `src/run_pathway_materials.py`).

**Scénarios** — feuille `Overrides`, puis `main(scenario='<nom>')`.
