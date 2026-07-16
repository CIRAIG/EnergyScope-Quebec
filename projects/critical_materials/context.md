# CONTEXT.md — Mémoire CRM / EnergyScope-Québec

> Fichier de référence à garder à jour et à fournir à Claude en début de session
> (ou à laisser dans le repo pour que Claude Code le lise directement).
> Branche : `5-critical-materials` — Dossier projet : `critical_materials`

---

## 1. Sujet du mémoire

Intégration **endogène** des contraintes de matériaux critiques (CRM) et des
**boucles de recyclage dynamique** dans EnergyScope-Québec (modèle LP
d'optimisation de système énergétique, codé en AMPL).

**Gap de recherche identifié** : absence simultanée dans la littérature de
(i) contraintes multi-CRM endogènes dans un LP-ESM établi, et
(ii) boucles de recyclage dynamique alimentant l'offre secondaire à partir
des déploiements passés (concept de *feedstock lag*).

**Périmètre technologique** : génération électrique (~34 technologies) +
mobilité privée (CAR_BEV, CAR_PHEV, CAR_HEV, etc.).

---

## 2. Méthodologie — collecte des intensités matière

- **Unités cibles** : kg/kW ou t/GW.
- **Système de confiance à paliers (tiered confidence)** :
  - Valeur directement sourcée (source primaire fiable)
  - Valeur calculée / proxy (dérivée d'une techno similaire ou d'une mise à l'échelle)
  - Valeur incertaine / à vérifier (flag explicite)

### Sources principales utilisées
| Source | Usage |
|---|---|
| JRC 2013 | Base historique intensités matière, plusieurs technos |
| JRC 2024 | Éoliennes (drivetrain, DD-PMSG vs GB-DFIG) |
| Carrara et al. 2020 (JRC119941) | Comparaison / validation |
| Colucci 2025 (PhD Politecnico di Torino) | Comparaison / validation |
| Liang et al. 2022 | Comparaison / validation |
| Bieuville et al. 2026 (Nature Sustainability, papier du labo CIRAIG) | Référence propre au labo |
| Watari et al. 2018 | Baseline Nd pour BEV (~695 g Nd/véhicule) |
| Månberger & Stenqvist ; Tokimatsu ; World Bank (Hund et al. 2020) | Benchmarking croisé |

---

## 3. Décisions méthodologiques clés (à ne pas re-débattre)

1. **CCGT variants** → mappées à une seule intensité `Foss_NaturalGas`.
   Le CCS ajoute seulement de l'acier en vrac (bulk steel), pas d'autres CRM.
2. **COAL_IGCC et H2_CCGT** (familles) → mappées à leurs archétypes fossiles respectifs.
3. **Cuivre CHP** : utilisation de la valeur CCGT du Tableau 25 du JRC (NEEDS 2008,
   ~1 100 kg Cu/MW) comme proxy. La valeur du Tableau 70 (~44 448 kg/MW) est
   considérée comme une **erreur de transcription/unité** dans le document source.
4. **Mobilité — Nd** : mise à l'échelle par puissance moteur (kW) pour
   CAR_BEV / CAR_PHEV / CAR_HEV, baseline BEV = Watari et al. 2018.
   ⚠️ **Anomalie non résolue** : ratio Nd:Pr observé ~695:1 vs. ratio naturel
   ~3–4:1 → à vérifier dans la source primaire.
5. Tout le stockage batterie est capté via le secteur mobilité —
   `STORAGE_TECH` (AMPL) ne contient que hydro + stockage thermique, pas de Li-ion.

---

## 4. Repères techniques AMPL / EnergyScope-Québec

- Structures clés : `layers_in_out`, `c_p_t`, conventions de signe `RES_WIND_ONSHORE`.
- Identifiants technos notables : `MP_NG_GRID`, `PLANE_SH` (aviation courte distance).
- Pipeline Python en cours de développement : génération de fichiers `.dat` AMPL
  à partir d'inputs Excel (formatage FR — virgule décimale).

### Pipeline `src/mi_pipeline/` (technologies électriques + piles à combustible)

Remplace l'édition manuelle de `technologies_mi_all_years.xlsx` pour le scope
électrique (~35 technos). Calcule les intensités à partir de
`excel_files/Material_intensities_energyscope.xlsx` (MI_Energy + MS_Energy_Disag/Ag)
selon la correspondance définie dans `excel_files/tech_mapping.xlsx` (feuille
`Mapping`), avec interpolation décennale vers les 7 années cibles. Régénère
`technologies_mi_all_years.xlsx` (uniquement les lignes des technos électriques —
le reste est recopié tel quel) et `ampl_files/Material_intensity.dat`.

**Lancer** : `python run_build_mi.py [--scenario baseline]` depuis
`projects/critical_materials/`. Imprime aussi un rapport de couverture
(intégré / placeholder zéro / non mappé / pas encore modélisé).

**Ajouter une technologie électrique** : une ligne dans `tech_mapping.xlsx`
(`energyscope_tech`, `mapping_type` = direct/aggregate/disaggregate/not_mapped,
`subtechs`, `energy_source`/`ms_table` si pondéré, `confidence`, `notes`). Si la
techno n'est pas encore dans `shared/data/QC_data.dat`, la ligne est acceptée
mais ignorée à l'écriture (warning) jusqu'à ce qu'elle soit ajoutée au modèle —
utile pour préremplir (ex. `NEW_WIND_OFFSHORE`).

**Ajouter un matériau** : ajouter la ligne (matériau = index) dans `MI_Energy`
(`Material_intensities_energyscope.xlsx`), puis une entrée dans
`MATERIAL_NAME_TO_CODE` (`sources.py`) et dans `MATERIAL_OUTPUT_ORDER`
(`build_table.py`) — c'est la seule liste qui pilote à la fois l'ordre des
colonnes du tableau final et la ligne `set MATERIALS := ...` du `.dat`.

**Scénarios/overrides** : feuille `Overrides` de `tech_mapping.xlsx`
(`scenario`, `energyscope_tech`, `material`, `override_value`, `reason`) —
`--scenario <nom>` applique les lignes correspondantes par-dessus le mapping de base.

**Décisions incorporées dans `tech_mapping.xlsx`** : CCGT/COAL_IGCC/H2_CCGT
familles → archétypes fossiles (`Foss_NaturalGas`/`Foss_Coal`/`Foss_Hydrogen`),
variantes `_CC`/`_CCS` → archétype + sous-techno `CCS` (constaté : ajoute surtout
du cuivre dans MI_Energy, pas seulement de l'acier comme supposé initialement —
à vérifier/documenter dans le mémoire). PAFC/PEMFC/SOFC volontairement laissés
`not_mapped` (pas de proxy Pt trompeur depuis Alakaline_FC).

---

## 5. Revue de littérature — état d'avancement

**Axes couverts** :
- Définitions CRM et cadres de criticité
- Taxonomie des méthodes d'estimation de la demande matière :
  ex-post simple → model-supported ex-post → soft-linking → hard-linking
- Papiers clés analysés : Burghardt et al., Colucci/Vai, Harpprecht et al.,
  Creutzig et al. 2024, Seck et al., Kullmann et al. (NESTOR),
  Tokimatsu et al., cadre DYNERIO
- Outil `mescal` (pont ESM–LCA) — pertinence pour le cadrage des trade-offs

---

## 6. Anomalies / points ouverts à surveiller

- [ ] Ratio Nd:Pr anormal (~695:1) — vérifier source Watari et al. 2018
- [ ] Valeur cuivre CHP Tableau 70 JRC 2013 — erreur de transcription probable, à documenter formellement dans le mémoire
- [ ] Confusion unités silicium (kg/MW vs t/GW) entre sources — résolue mais à citer comme exemple de piège méthodologique
- [ ] Classification binaire implicite GB-DFIG/DD-PMSG dans World Bank — limite à noter

---

*Dernière mise à jour : à compléter à chaque session importante.*
