# Shared model versioning

The shared base model follows [Semantic Versioning](https://semver.org/): `MAJOR.MINOR.PATCH`.

| Increment | Meaning                                                | Example trigger                                         |
|-----------|--------------------------------------------------------|---------------------------------------------------------|
| `PATCH`   | Bug fix; no change to results on existing case studies | Correcting a unit conversion, fixing a typo in a set    |
| `MINOR`   | New feature or parameter; backward compatible          | Adding a new technology, new optional constraint        |
| `MAJOR`   | Structural change that alters existing results         | Reformulating an objective term, changing normalisation |

The current version is always stored in `shared/VERSION`.

---

## Changelog

### v1.0.0 — Initial release
*Date: 2026-04-24*

Initial snapshot of the shared EnergyScope-Québec base model, migrated from the individual project repositories.

---

## Update protocol

See [`CONTRIBUTING.md`](../../CONTRIBUTING.md) for the full workflow. In short:

1. Raise a *Shared model change* issue and get consensus.
2. Merge the PR with all three leads' approval.
3. Bump `VERSION` and add an entry to this changelog.
4. Each project updates independently at a time of their choosing.
