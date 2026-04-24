# EnergyScope-Québec

A monorepo for the EnergyScope-Québec energy system model and its research extensions.

## Structure

```
energyscope-quebec/
├── shared/
│   ├── model/          # AMPL model files of the shared base EnergyScope-Québec model
│   ├── data/           # AMPL data files of the shared base EnergyScope-Québec model
│   ├── scenarios/      # AMPL files of shared scenarios
│   ├── plots/          # Scripts for shared plotting functions and styles
│   ├── utilities/      # Utility functions and scripts used across projects
│   └── docs/           # Shared methodology notes and references
└── projects/
    ├── front_commun/   # Evaluation of Front Commun's energy transition scenarios
    ├── lca/            # Integration of life-cycle assessment (LCA) metrics
    ├── peaks/          # Modeling of end-use demand peaks
    └── pathway/        # Transition pathway modeling (2020–2050)
```

## Projects

| Project                                  | Description                                                                                                 | Lead                                                |
|------------------------------------------|-------------------------------------------------------------------------------------------------------------|-----------------------------------------------------|
| [`front_commun`](projects/front_commun/) | Evaluation of Front Commun's energy transition scenarios                                                    | [Matthieu Souttre](https://github.com/matthieu-str) |
| [`lca`](projects/lca/)                   | Coupling of the energy system model with LCA metrics via [`mescal`](https://github.com/matthieu-str/mescal) | [Matthieu Souttre](https://github.com/matthieu-str) |
| [`peaks`](projects/peaks/)               | Explicit modeling of end-demand peaks                                                                       | [Julien Pedneault](https://github.com/jpedneault)   |
| [`pathway`](projects/pathway/)           | Multi-period transition pathway modeling from 2020 to 2050                                                  | [Mattia Zimmermann](https://github.com/ma-zimmer)   |

## Shared model

The `shared/model/` directory contains a **versioned snapshot** of the base EnergyScope-Québec AMPL model.

See [`shared/docs/model-versioning.md`](shared/docs/model-versioning.md) for the update protocol.

## Installation

To access the shared models and methods, run the following command in your virtual environment:
```bash
pip install -e .
```

Then, in your python files or notebooks, you can import the shared modules as follows:
```python
from shared.models import energyscope_quebec
```

## Contributing

- Changes to `shared/model/` require approval from all project leads (enforced via CODEOWNERS).
- Changes within a project folder require approval from that project's lead only.
- Please use the appropriate issue template when opening issues.
- Branch naming convention: `<project-or-shared>/<short-description>` (e.g. `lca/biogenic-flows`, `shared/fix-storage-constraint`).

See [`CONTRIBUTING.md`](CONTRIBUTING.md) for details.

## License

Apache License 2.0 — see [`LICENSE`](LICENSE) for the full text.