# ViOTUcluster 0.6.0 Release Design

Date: 2026-06-30

## Goal

Promote the current validated Conda-first install line into a new public version
`0.6.0`, and make `mamba install -c conda-forge -c bioconda viotucluster` the
preferred installation path in the user-facing documentation.

## Scope

Apply the version bump and release messaging across both release surfaces:

1. the main `ViOTUcluster` repository,
2. the staged Bioconda recipe branch and PR.

## Chosen Approach

Use one coordinated version:

- bump the upstream package version from `0.5.7.2` to `0.6.0`,
- retarget the Bioconda recipe from `0.5.7.2` to `0.6.0`,
- cut a matching upstream release/tag `v0.6.0`,
- rewrite README installation guidance so that Bioconda/mamba is the default
  recommendation,
- keep the repo-local `environment.yml` path as the fallback/manual install path.

## Documentation Direction

README installation order should become:

1. Preferred: `mamba install -c conda-forge -c bioconda viotucluster`
2. Fallback: clone the repository and create the environment from
   `environment.yml`
3. Optional advanced stacks: DRAM/iPhop remain separate from the default
   Bioconda install story

The README should also state clearly that:

- Bioconda installation covers the validated default main workflow,
- databases still need to be downloaded separately,
- DRAM and iPhop remain optional advanced analysis steps.

## Validation

For this release bump, treat the following as required evidence:

- local repo tests still pass after the version/documentation changes,
- Bioconda recipe still builds on `em`,
- package installation from the locally built channel still exposes
  `ViOTUcluster`, `ViOTUcluster_AllinOne`, and `import ViOTUcluster`.
