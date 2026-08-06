# ViOTUcluster Conda Installation Design

Date: 2026-06-28

## Goal

Replace the prepacked tarball installer with a maintainable Conda-first installation path that:

1. installs the default pipeline from checked-in manifests,
2. keeps the default `ViOTUcluster` and `ViOTUcluster_AllinOne` flow in one main environment,
3. isolates only the truly conflicting optional stack into satellite environments,
4. keeps the runtime contract explicit in docs and dependency checks.

## Root Cause

The current installer exists because the dependency graph is not fully co-installable in one environment.

The key confirmed blocker is `iPhop`, whose current Bioconda package still pins Python 3.8 and TensorFlow 2.7, while `geNomad` requires Python 3.9+ and TensorFlow 2.16+.

That means the right fix is not "put everything into one environment", but "keep one main environment for the default pipeline and isolate the conflicting optional analysis".

## Chosen Approach

Use checked-in Conda environment manifests instead of downloaded tarballs.

- `environment.yml` will define the main `ViOTUcluster` environment.
- The main environment will include the default pipeline tools, including preprocessing (`fastp`, `megahit`/`spades`), prediction, dereplication, abundance, and binning (`vRhyme`, `viralverify`, `virsorter`, `geNomad`, `checkv`, `dRep`, `bwa`, `sambamba`, `coverm`, `blast`, `parallel`).
- Optional advanced analysis will stay split:
  - `DRAM` can stay optional even if it may be co-installable.
  - `iPhop` must stay isolated because of the confirmed solver/runtime conflict.
- Runtime code will prefer commands already available in the active main environment and only fall back to sibling environments where needed for backward compatibility.

## Planned Changes

### 1. Installation Manifests

- Add `environment.yml` for the main environment.
- Add satellite environment manifests for optional components.

### 2. Installer Contract

- Replace the tarball-oriented `setup_ViOTUcluster.sh` with a repo-local Conda bootstrap helper.
- The supported primary install path becomes:
  - clone repo,
  - create main env from `environment.yml`,
  - optionally create satellite envs from checked-in manifests.

### 3. Runtime Alignment

- Keep `viralverify` fallback behavior, but allow the main environment to satisfy it directly.
- Update vRhyme invocation to prefer a command on `PATH` before falling back to the historical sibling env location.
- Keep DRAM/iPhop optional and explicit.

### 4. Validation and Docs

- Update `ViOTUcluster_Check` to match actual runtime commands:
  - check `metaspades.py` rather than `spades.py`,
  - check `vRhyme`,
  - stop claiming `checkm` is required when the main pipeline does not call it directly.
- Rewrite README installation instructions around Conda manifests instead of downloaded tarballs.

## Test Strategy

- Add contract tests for:
  - presence and content of Conda environment manifests,
  - installer script no longer depending on prepacked tarballs,
  - dependency-check script matching the revised runtime contract.
- Re-run the existing shell and orchestration contract tests after the install changes land.
