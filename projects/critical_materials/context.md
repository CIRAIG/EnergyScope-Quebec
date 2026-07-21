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

### Pipeline `src/mi_pipeline/` (technos élec + piles à combustible)

Génère `technologies_mi_all_years.xlsx` + `Material_intensity.dat` depuis
`Material_intensities_energyscope.xlsx` — MI_Energy + MS_Energy_Disag/Ag pour
les données source, feuilles `Mapping`/`Overrides` (dans ce même classeur) pour
la correspondance techno ↔ sous-techno. Tout le fichier est externe/lecture
seule, le code n'y écrit jamais (couleurs et colonne `group` gérées à la main).
Interpolation décennale → 7 années ES. Remplace l'édition manuelle pour le
scope élec (~35 technos) ; le reste du tableau (mobilité, chauffage...) reste
recopié tel quel.

`python run_build_mi.py [--scenario baseline]`, depuis `critical_materials/`.
Sort aussi un rapport de couverture (intégré / placeholder / non mappé / pas
encore modélisé), console seulement.

- Ajouter une techno élec → ligne dans la feuille `Mapping` (+ `QC_data.dat` si
  pas encore modélisée ; sinon prérempli et ignoré à l'écriture avec warning)
- Ajouter un matériau → ligne dans `MI_Energy` + `MATERIAL_NAME_TO_CODE`
  (`sources.py`) + `MATERIAL_OUTPUT_ORDER` (`build_table.py`)
- Scénarios/overrides → feuille `Overrides`, `--scenario <nom>`

Décisions dans la feuille `Mapping` : CCGT/COAL_IGCC/H2_CCGT → archétypes
fossiles (`Foss_NaturalGas`/`Foss_Coal`/`Foss_Hydrogen`), `_CC`/`_CCS` →
archétype + `CCS` (ajoute surtout du cuivre dans MI_Energy, pas de l'acier
comme supposé au départ — à vérifier). PAFC/PEMFC/SOFC non mappés (pas de
proxy Pt depuis Alkaline_FC).

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
