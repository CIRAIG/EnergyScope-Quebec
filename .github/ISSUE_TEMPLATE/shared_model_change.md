---
name: Shared model change
about: Propose a change to shared/model/ — requires discussion and approval from all project leads before any code is written
labels: shared-model, needs-discussion
---

## Summary

<!-- One sentence: what changes and why. -->

## Motivation

<!-- What bug does this fix, or what capability does this add? Link to a bug report if applicable. -->

## Proposed change

<!-- Describe the modification to the AMPL model, parameters, or data as precisely as possible. -->

## Impact assessment

<!-- For each project, describe the expected impact on results: -->

| Project        | Expected impact on results | Validation needed |
|----------------|----------------------------|-------------------|
| `front_commun` |                            |                   |
| `lca`          |                            |                   |
| `peaks`        |                            |                   |
| `pathway`      |                            |                   |

## Suggested version bump

- [ ] PATCH — bug fix, no change to results on existing case studies
- [ ] MINOR — new feature or parameter, backward compatible
- [ ] MAJOR — structural change that alters existing results

## Checklist

- [ ] All three project leads have been notified
- [ ] Discussion has reached consensus
- [ ] A branch `shared/<description>` will be created (no code before consensus)
