# Classeurs Excel du projet matériaux critiques

## À quoi servent ces classeurs

Ces trois classeurs sont les **entrées** du code : les pipelines de `src/` les lisent et génèrent les fichiers
`.dat` de `ampl_files/` que `run_pathway(materials=True)` charge dans le modèle.

Ils sont traités en **lecture seule** par le code : toute modification (données, mapping, matériaux) se fait à
la main dans Excel, puis on relance le script correspondant pour régénérer le `.dat`. Chaque classeur a sa
propre feuille `Table of content` qui décrit toutes ses feuilles.

| Classeur | Pipeline | Script | Fichier généré | Option de `run_pathway` |
|---|---|---|---|---|
| `Material_intensities.xlsx` | `mi_pipeline` | `run_build_mi.py` | `Material_intensity.dat` | toujours chargé avec `materials=True` |
| `Recycling_rates.xlsx` | `rr_pipeline` | `run_build_rr.py` | `Material_recycling.dat` | `materials_recycling=True` |
| `Material_limits.xlsx` | `limits_pipeline` | `run_build_limits.py` | `Material_limits.dat` | `materials_limit=True` |

Les scripts réécrivent les `.dat` suivis par git : relis le diff avant de commiter.

---

# Material_intensities.xlsx

Intensités matérielles des technologies EnergyScope-Québec : données sources (littérature) + table de
correspondance technologique. Sortie : `ampl_files/Material_intensity.dat`.

## Origine des données

La majorité des feuilles viennent des données supplémentaires de :

> Bieuville, P., Majeau-Bettez, G., de Bortoli, A. (2025). *Metal bottlenecks
> along energy transitions call for technology flexibility and sobriety.*

Les feuilles `Table of content`, `MI`, `Legend` et `Ref&Hp` documentent ces données telles que publiées : ne
pas les modifier.

## Feuilles utilisées par le pipeline

- **`Materials`** : liste maîtresse des matériaux (nom complet + code court). C'est la seule feuille à modifier
  pour ajouter un matériau (voir plus bas).
- **`MI_Energy`** : intensité matérielle des sous-technologies électriques (t/GW).
- **`MI_H2`** : intensité matérielle des 3 électrolyseurs (Alcaline/PEM/SOEC), en t/GW.
- **`MI_Vehicles`** : intensité par véhicule (g/véhicule) et par motorisation (ICEV/HEV/PHEV/EV/FCV). Source :
  Watari et al. 2019 / Fishman et al. 2018. Utilisée avec `vehicle_source='watari'`.
- **`MI_Vehicles_2`** : source par défaut (`vehicle_source='bieuville'`), reconstruite à partir de la
  carrosserie + batterie (par chimie) + moteur (par type), pondérées par `MS_Battery_Motor_LDV`. FCV n'y est pas
  couvert : la valeur de `MI_Vehicles` est utilisée dans les deux cas.
- **`MI_Vehicles_Public`** : transport en commun (bus, etc.), en g/véhicule. Toujours utilisée, quelle que soit
  la source des véhicules privés.
- **`MS_Battery_Motor_LDV`** : part de marché par chimie de batterie (par année) et par type de moteur (fixe).
- **`MS_Energy_Disag`** : parts de marché des sous-technologies par décennie, pour les technologies de type
  `aggregate`.
- **`Mapping`** : une ligne par technologie EnergyScope-Québec (710), avec la/les sous-techno(s) de la
  littérature à utiliser. `mapping_type` :
  - `direct` et `disaggregate` : une seule sous-techno ;
  - `aggregate` : plusieurs sous-technos, pondérées par `MS_Energy_Disag` d'après `energy_source` ;
  - `not_mapped` : pas de donnée d'intensité matérielle.

Les unités par véhicule sont converties en t/(pkm/h) par le code, avec la taille de référence des véhicules
(`ref_size`, dans `shared/data/Techs/out_techs.dat`).

## PV et éolien

Les 20 sous-technologies PV et éolien (`PV_ROOF_C_SI`, `WIND_ONSHORE_DD_PMSG`, ...) sont toutes en `direct`. Elles
n'existent dans le modèle que pour `materials=True`, via `ampl_files/Subtechs*`. Les 5 technologies agrégées
(`PV_ROOF`, `PV_GROUND`, `WIND_ONSHORE`, `NEW_WIND_ONSHORE`, `WIND_OFFSHORE`) sont en `not_mapped`.

---

# Recycling_rates.xlsx

Taux de recyclage, coûts et technologies de recyclage. Sorties : `ampl_files/Material_recycling.dat` (taux et
coûts) et `ampl_files/Material_recycling_process.dat` (procédés de recyclage).

## Pour `run_build_rr.py` (`Material_recycling.dat`)

- **`Materials`** : même liste de matériaux que dans `Material_intensities.xlsx`.
- **`RR_Energy`, `RR_Vehicles`, `RR_H2`** : taux de recyclage en fin de vie par matériau et sous-technologie,
  une table par année (2020 à 2050).
- **`RR_Global`** : taux par matériau et par année, utilisé pour les technologies sans mapping spécifique.
- **`Mapping`** : même principe que dans `Material_intensities.xlsx` (710 technologies : 180 `direct`, 530
  `not_mapped`).
- **`Cost_recycling_global`, `Cost_material_global`, `Cost_disposal_global`** : coût de recyclage, coût du
  matériau primaire évité et coût d'enfouissement, par matériau (CAD/t). A developper

## Pour `run_build_rt.py` (`Material_recycling_process.dat`)

- **`Recycling_technologies`** : taux de récupération par matériau et par procédé de recyclage. A developper
- **`Recycling_cost`** : coût de chaque procédé et revenu du matériau récupéré. A developper
- **`Collection_rate`** : part du flux collectée, par technologie et par année. A developper

## Feuilles non lues par les pipelines

`Recycling_rates`, `RR_technology`, `Recycling_objective`, `Legend`, `Ref&Hp`, `Table of content` :
documentation ou données de travail.

---

# Material_limits.xlsx

Plafonds de production annuelle par matériau. Sortie : `ampl_files/Material_limits.dat`
(`limit_material_year`).

- **`Material_limits`** : plafonds en t/an par matériau, tous les 5 ans (2020 à 2050). C'est la seule feuille
  lue par le code (38 matériaux).
- **`Materials`** : liste des matériaux.
- Les autres feuilles (`RoE_Demand`, `MiningCapacity_Calcul`, `Reserves_Resources_RR`,
  `MiningCapacity_Results`, `Calcul_Prod`, `Ref&Hp`) documentent comment les plafonds sont calculés (demande du
  reste de l'économie, capacité minière, réserves) : voir `Table of content`.

Seules les années 2030 à 2050 sont écrites dans le `.dat` : 2020 et 2025 restent à `Infinity` (valeur par
défaut du modèle).

---

# Comment les utiliser

**Régénérer un fichier de sortie** — depuis `projects/critical_materials/` :
```bash
python run_build_mi.py [--vehicle-source watari|bieuville] [--no-dat]
python run_build_rr.py [--no-dat]
python run_build_rt.py [--no-dat]
python run_build_limits.py [--no-dat]
```
ou dans un notebook :
```python
from run_build_mi import main
main()
```
`--no-dat` (ou `write_dat=False`) calcule et affiche le rapport de couverture sans écrire le `.dat`.

**Ajouter un matériau** — ajouter une ligne dans la feuille `Materials` (nom complet + code court) du ou des
classeurs concernés, puis ses valeurs dans les feuilles de données. Aucun fichier `.py` à modifier.

**Modifier le mapping d'une technologie** — éditer sa ligne dans `Mapping` (`mapping_type`, `subtechs`,
`energy_source` pour `aggregate`).

**Comparer les deux sources véhicule** :
```python
main(vehicle_source='bieuville')   # défaut
main(vehicle_source='watari')
```
Les deux écrivent dans le même fichier de sortie (pas de suffixe) : il faut relancer `run_pathway` entre les
deux pour comparer les résultats.

**Lancer le modèle avec ces données** :
```python
run_pathway('mon_run', materials=True, materials_recycling=True, materials_limit=True)
```
