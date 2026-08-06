#!/usr/bin/env python3

import os
import unittest


REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def read_text(*parts):
    with open(os.path.join(REPO_ROOT, *parts), "r", encoding="utf-8") as handle:
        return handle.read()


class TestShellContracts(unittest.TestCase):
    def test_drep_module_uses_min_length_for_bins(self):
        content = read_text("Modules", "drep_module.sh")
        self.assertIn('-l "${MIN_LENGTH}"', content)

    def test_database_download_script_validates_and_presses_virsorter_hmms(self):
        content = read_text("Modules", "ViOTUcluster_download-database")
        self.assertIn('db/hmm/viral/combined.hmm', content)
        self.assertIn('rbs-prodigal-train.db', content)
        self.assertIn('hmmpress -f "$DB_DIR/db/hmm/viral/combined.hmm"', content)
        self.assertIn('combined.hmm.$suffix', content)
        self.assertIn('combined.$suffix', content)

    def test_binning_module_prefers_vrhyme_on_path_with_nested_env_fallback(self):
        content = read_text("Modules", "binning_merge_module.sh")
        self.assertIn("resolve_vrhyme_command()", content)
        self.assertIn("command -v vRhyme", content)
        self.assertIn('${CONDA_PREFIX}/envs/vRhyme/bin/vRhyme', content)
        self.assertNotIn('conda run -p "$CONDA_PREFIX/envs/vRhyme" vRhyme', content)

    def test_dependency_check_covers_runtime_tools(self):
        content = read_text("Modules", "ViOTUcluster_Check")
        for tool_name in ("conda", "viralverify", "sambamba", "coverm", "parallel", "makeblastdb", "blastn"):
            self.assertIn(f'"{tool_name}"', content)

    def test_dependency_check_has_sidecar_viralverify_fallback(self):
        content = read_text("Modules", "ViOTUcluster_Check")
        self.assertIn("../../viralverify/bin/viralverify", content)


if __name__ == "__main__":
    unittest.main()
