# ViOTUcluster Bioconda Release TODO

Date: 2026-06-30

- [x] Confirm that `bioconda/viotucluster` does not exist yet.
- [x] Decide package scope: first package covers the validated main workflow only.
- [x] Cut upstream GitHub release `v0.5.7.2`.
- [ ] Bump the coordinated public version to `0.6.0` across the repo and recipe.
- [ ] Update README so `mamba install -c conda-forge -c bioconda viotucluster` is the preferred install path.
- [x] Create a Bioconda recipe draft for `viotucluster`.
- [x] Push recipe branch to a personal fork.
- [x] Open a draft upstream PR to `bioconda/bioconda-recipes`.
- [ ] Run full recipe rendering/build checks in a Linux Bioconda-style environment.
- [ ] Address Bioconda CI review comments, if any.
- [ ] Update upstream default-branch README after the post-merge install changes are merged or released into the default branch.
