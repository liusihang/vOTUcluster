# ViOTUcluster Conda Install TODO

Date: 2026-06-28

- [x] Replace the prepacked tarball installer with checked-in Conda manifests.
- [x] Define a main `environment.yml` for the default pipeline.
- [x] Split optional DRAM and iPhop into explicit satellite environment manifests.
- [x] Update README installation guidance to match the new Conda-first contract.
- [x] Align dependency checks with the actual runtime commands.
- [ ] Validate `conda env create -f environment.yml` on a Linux host with the target channel configuration.
- [ ] Validate optional `./setup_ViOTUcluster.sh --with-dram --with-iphop` on a Linux host.
- [ ] Decide whether a future Bioconda recipe should target only the main pipeline or expose optional subpackages.
