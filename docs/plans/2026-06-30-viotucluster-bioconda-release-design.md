# ViOTUcluster Bioconda Release Design

Date: 2026-06-30

## Goal

Enable a real future user flow of:

```bash
mamba install -c conda-forge -c bioconda viotucluster
```

for the default `ViOTUcluster` / `ViOTUcluster_AllinOne` workflow.

## Current Reality

- The current repository now has a working Conda-first install contract (`environment.yml` plus `setup_ViOTUcluster.sh`).
- The upstream default branch still does not expose that contract in its public README.
- No `bioconda/viotucluster` package exists yet.
- The latest published upstream artifact is still `0.5.7.1`, while the validated install/runtime fixes live on the current `0.5.7.2` code line.

## Release Boundary

Package only the default main workflow in the Bioconda package:

- include the Python CLI package,
- include the main default external runtime stack,
- exclude optional DRAM and iPhop satellite environments from the first Bioconda package.

This keeps the first package aligned with the workflow we have actually validated on `em`.

## Options Considered

### Option A: Full main-workflow Bioconda package

- ship one `viotucluster` Bioconda package,
- declare the validated main runtime in `requirements: run`,
- leave DRAM/iPhop outside the first package.

Pros:
- closest to "install and run" for users,
- matches the repo's new Conda-first contract,
- avoids shipping known-conflicting optional stacks.

Cons:
- heavier runtime dependency set,
- requires careful version pinning for database compatibility.

### Option B: Thin Python-only Bioconda package

- ship only the Python wrapper package,
- force users to install all external tools separately.

Pros:
- easiest recipe to maintain.

Cons:
- not what the user asked for,
- poor install UX,
- likely creates more support burden than it removes.

### Option C: Split package family

- `viotucluster` for the Python layer,
- a second runtime/meta package for the validated default toolchain.

Pros:
- cleaner long-term layering.

Cons:
- too much complexity for the first release,
- more moving parts for review and support.

## Chosen Approach

Choose Option A.

Create one Bioconda package `viotucluster` that installs:

- `python=3.10`,
- `biopython`,
- `pandas`,
- `numpy`,
- `packaging`,
- `fastp`,
- `megahit`,
- `spades`,
- `viralverify`,
- `virsorter=2.2.4`,
- `genomad=1.8.0`,
- `checkv=1.0.3`,
- `drep=3.5.0`,
- `vrhyme`,
- `bwa`,
- `sambamba`,
- `coverm`,
- `blast`,
- `parallel`.

Do not put DRAM or iPhop in the first Bioconda package.

## Source Artifact Strategy

Use a new upstream source artifact for `0.5.7.2`, preferably a GitHub tag/release tarball.

This avoids blocking on PyPI credentials and lets the Bioconda recipe point at an immutable upstream source.

## Recipe Strategy

- create `recipes/viotucluster/meta.yaml` in a Bioconda recipe workspace,
- Linux-only for the first release,
- build with `pip install .`,
- minimal tests:
  - `ViOTUcluster --help`
  - `ViOTUcluster_AllinOne --help`
  - `python -c "import ViOTUcluster"`
- do not run `ViOTUcluster_Check` inside Bioconda tests because the mulled test container is not a Conda shell and should not be required to expose `conda` itself.

## Validation Strategy

1. Validate recipe structure and dependency names locally.
2. Validate recipe rendering/buildability in a Linux Conda environment.
3. Keep runtime validation separate from Bioconda recipe tests:
   the runtime smoke already exists on `em` and remains the truth surface for pipeline behavior.

## Deliverables

- upstream release prep for `0.5.7.2`,
- Bioconda recipe directory for `viotucluster`,
- local validation notes and next submission steps for `bioconda-recipes`.
