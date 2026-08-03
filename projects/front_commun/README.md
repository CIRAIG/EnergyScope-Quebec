# Scénarios de transition énergétique — Front commun pour la transition énergétique du Québec

> **🌐 Accéder à l'application : [ciraig.github.io/scenarios-front-commun](https://ciraig.github.io/scenarios-front-commun/)**

Tableau de bord interactif présentant les résultats de modélisation des scénarios de transition énergétique développés dans le cadre du [Front commun pour la transition énergétique du Québec](https://www.pourlatransitionenergetique.org/).

---

## À propos

Les scénarios combinent deux outils de modélisation complémentaires :

- **[EnergyScope-Québec](https://github.com/CIRAIG/EnergyScope-Quebec)** — modélisation du système énergétique québécois à l'horizon 2050
- **[mescal](https://mescal.readthedocs.io/en/latest/)** — couplage avec l'analyse du cycle de vie (ACV) via le framework Brightway

Les résultats couvrent le mix énergétique, les coûts système, les impacts environnementaux (santé humaine, qualité des écosystèmes, changement climatique) et les flux de carbone pour chaque scénario.

## Scénarios

| Identifiant       | Description                                       | Contrainte |
|-------------------|---------------------------------------------------|------------|
| `actuel`          | État du système en 2023                           | Référence  |
| `brut`            | Croissance non contrainte                         | —          |
| `brut_nz`         | Croissance non contrainte                         | Net-Zéro   |
| `acc_verte`       | Accélération verte                                | —          |
| `acc_verte_nz`    | Accélération verte                                | Net-Zéro   |
| `sobre`           | Sobriété énergétique                              | —          |
| `sobre_nz`        | Sobriété énergétique                              | Net-Zéro   |
| `sobre_lim_cc_nz` | Sobriété + CCS limité                             | Net-Zéro   |
| `energyscope_nz`  | Optimum EnergyScope (Canada's Energy Future 2023) | Net-Zéro   |

## Structure du dépôt

```
├── 01_Notebooks/     # Script pour créer les fichiers AMPL des scénarios, faire tourner le modèle, et générer les graphes
├── 02_AMPL_files/    # Fichiers AMPL (un par scénario + un fichier de scénario commun)
├── 03_Results/       # Graphes Plotly et résultats complets au format pickle
└── README.md
```
> **Dépot Github de l'application web : [https://github.com/CIRAIG/scenarios-front-commun](https://github.com/CIRAIG/scenarios-front-commun)**

## Auteurs

| Auteur·e             | Contributions                                        |
|----------------------|------------------------------------------------------|
| **Matthieu Souttre** | Conception du site, Modélisation, Résultats, Analyse |
| **Titouan Greffe**   | Résultats, Analyse                                   |
| **Éric Pineault**    | Narratifs                                            |
| **Cécile Bulle**     | Supervision                                          |

---

*Développé au [CIRAIG](https://ciraig.org/), Polytechnique Montréal.*