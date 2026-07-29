# CONTEXT.md

## 1. Sujet du travail

Intégration **endogène** des contraintes de matériaux et des
**boucles de recyclage dynamique** dans EnergyScope-Québec.

**Gap de recherche identifié** : absence simultanée dans la littérature de
(i) contraintes multi-CRM endogènes dans un LP-ESM établi, et
(ii) boucles de recyclage dynamique alimentant l'offre secondaire à partir
des déploiements passés (concept de *feedstock lag*).

---

## 2. Méthodologie — collecte des intensités matière

- **Unités cibles** : kg/kW, t/GW ou g/Vehicle.
- **Système de confiance à paliers (tiered confidence)** :
  - Valeur directement sourcée (source primaire fiable)
  - Valeur calculée / proxy (dérivée d'une techno similaire ou d'une mise à l'échelle)
  - Valeur incertaine / à vérifier (flag explicite)

---

### Pipeline `src/mi_pipeline/` 

Génère `technologies_mi_all_years.xlsx` + `Material_intensity.dat` depuis
`Material_intensities_energyscope.xlsx`. Tout le fichier est externe/lecture
seule, le code n'y écrit jamais.


- Ajouter une techno élec → ligne dans la feuille `Mapping` (+ `QC_data.dat` si
  pas encore modélisée ; sinon prérempli et ignoré à l'écriture avec warning)
- Ajouter un matériau → ligne dans `Materials` + l'intenisté matérielle dans la feuille correspondante
- Scénarios/overrides → feuille `Overrides`, `--scenario <nom>`

Décisions dans la feuille `Mapping` : CCGT/COAL_IGCC/H2_CCGT → archétypes
fossiles (`Foss_NaturalGas`/`Foss_Coal`/`Foss_Hydrogen`), `_CC`/`_CCS` →
archétype + `CCS`.

---

## 3. Résultats

**Axes couverts** :
- Demande en matériau et c'est compris dans `Material_content_year` qui est la demande annuelle par technologie EnergyScope
- Demande en matériau cumulée dans `Material_content_cumulative` qui est la demande annuelle cumulée par technologie EnergyScope
- Quantité de matériau recyclée dans `Recycled_material` qui est la quantité de matériau recyclée par année

---