# Contributing to EnergyScope-Québec

Thank you for contributing! This document explains the workflow for this monorepo.

## Repository layout

This is a **monorepo** containing a shared base model and several research projects. The key rule is:

- `shared/model/` — changes here affect all projects and require **unanimous review**.
- `projects/<name>/` — changes here affect only one project and require **that project lead's review**.

## Branch naming

Always prefix your branch with the affected scope:

```
shared/<short-description>       # e.g. shared/fix-storage-constraint
front_commun/<short-description> # e.g. front_commun/update-scenarios
lca/<short-description>          # e.g. lca/biogenic-flows
peaks/<short-description>        # e.g. peaks/hourly-demand-disaggregation
pathway/<short-description>      # e.g. pathway/2035-milestone
```

## Workflow for shared model changes

Changes to `shared/model/` are the most sensitive because they affect all projects. Follow this process:

1. **Open an issue** using the *Shared model change* template before writing any code.
2. Discuss the change with all project leads and reach agreement.
3. Create a branch `shared/<description>` and make the minimal necessary change.
4. Open a PR. All project leads must approve before merging.
5. After merging, **bump the model version** in `shared/model/VERSION` following semantic versioning:
   - `PATCH` (e.g. `1.0.0` → `1.0.1`): bug fix with no change to model outputs on existing case studies.
   - `MINOR` (e.g. `1.0.0` → `1.1.0`): new feature or parameter, backward compatible.
   - `MAJOR` (e.g. `1.0.0` → `2.0.0`): structural change that alters existing results.
6. Each project lead decides **independently** when to update their project to the new snapshot (see below).

## Workflow for project-specific changes

1. Create a branch `<project>/<description>` from `main`.
2. Make changes within `projects/<project>/` only.
3. Open a PR; the project lead reviews and merges.
4. Do not modify files outside your project folder in project branches.

## Updating a project to a new shared model snapshot

When the shared model is updated and you want to incorporate the changes into your project:

1. Review the changelog entry in `shared/docs/model-versioning.md`.
2. Copy the relevant updated files from `shared/model/` into your project's model directory.
3. Re-run your validation cases to confirm expected behavior.
4. Update the `SHARED_MODEL_VERSION` field in your project's `README.md`.
5. Commit with message: `chore: update to shared model vX.Y.Z`.

## Commit messages

Use [Conventional Commits](https://www.conventionalcommits.org/) style:

```
feat(lca): add biogenic carbon flows to LCA metrics
fix(shared): correct storage constraint formulation
docs(pathway): update parameter assumptions for 2035 milestone
chore(peaks): update to shared model v1.2.0
```

## Code style

- **AMPL**: 2-space indentation, one constraint per block, commented units on all parameters.
- **Python**: follow PEP 8, use type hints, docstrings on all public functions.
- Keep data files in CSV or JSON; avoid binary formats in version control.
