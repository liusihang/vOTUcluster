#!/usr/bin/env python3

import os
from pathlib import Path
import subprocess
import tempfile
import unittest


REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def read_text(*parts):
    with open(os.path.join(REPO_ROOT, *parts), "r", encoding="utf-8") as handle:
        return handle.read()


class TestShellContracts(unittest.TestCase):
    def run_vrhyme_command(self, path_vrhyme=False, nested_vrhyme=False, sidecar_vrhyme=False):
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            path_bin = temp_path / "path-bin"
            path_bin.mkdir()
            conda_prefix = temp_path / "ViOTUcluster"
            nested_bin = conda_prefix / "envs" / "vRhyme" / "bin"
            nested_bin.mkdir(parents=True)
            sidecar_bin = temp_path / "vRhyme" / "bin"
            sidecar_bin.mkdir(parents=True)
            command_log = temp_path / "commands.log"

            if path_vrhyme:
                path_command = path_bin / "vRhyme"
                path_command.write_text(
                    "#!/bin/bash\n"
                    "printf 'path:%s\\n' \"$*\" >> \"$VRHYME_TEST_LOG\"\n",
                    encoding="utf-8",
                )
                path_command.chmod(0o755)
            if nested_vrhyme:
                nested_command = nested_bin / "vRhyme"
                nested_command.write_text(
                    "#!/bin/bash\n"
                    "printf 'managed:%s path=%s\\n' \"$*\" \"$PATH\" >> \"$VRHYME_TEST_LOG\"\n",
                    encoding="utf-8",
                )
                nested_command.chmod(0o755)
            if sidecar_vrhyme:
                sidecar_command = sidecar_bin / "vRhyme"
                sidecar_command.write_text(
                    "#!/bin/bash\n"
                    "printf 'managed:%s path=%s\\n' \"$*\" \"$PATH\" >> \"$VRHYME_TEST_LOG\"\n",
                    encoding="utf-8",
                )
                sidecar_command.chmod(0o755)

            probe = temp_path / "probe.sh"
            probe.write_text(
                f'source "{Path(REPO_ROOT) / "Modules" / "binning_merge_module.sh"}"\n'
                "run_vrhyme --probe\n",
                encoding="utf-8",
            )
            environment = dict(os.environ)
            environment.update(
                {
                    "CONDA_PREFIX": str(conda_prefix),
                    "FILES": "",
                    "PATH": str(path_bin),
                    "VRHYME_TEST_LOG": str(command_log),
                }
            )
            completed = subprocess.run(
                ["/bin/bash", str(probe)],
                env=environment,
                capture_output=True,
                text=True,
            )
            logged_commands = command_log.read_text(encoding="utf-8").splitlines() if command_log.exists() else []
            return completed, logged_commands, conda_prefix

    def test_vrhyme_runner_prefers_main_environment_path(self):
        completed, logged_commands, _ = self.run_vrhyme_command(path_vrhyme=True, nested_vrhyme=True)

        self.assertEqual(0, completed.returncode, completed.stderr)
        self.assertEqual(["path:--probe"], logged_commands)

    def test_vrhyme_runner_resolves_nested_yaml_environment(self):
        completed, logged_commands, conda_prefix = self.run_vrhyme_command(nested_vrhyme=True)

        self.assertEqual(0, completed.returncode, completed.stderr)
        self.assertEqual(
            [f"managed:--probe path={conda_prefix}/envs/vRhyme/bin:{conda_prefix.parent}/path-bin"],
            logged_commands,
        )

    def test_vrhyme_runner_resolves_legacy_sidecar_environment(self):
        completed, logged_commands, conda_prefix = self.run_vrhyme_command(sidecar_vrhyme=True)

        self.assertEqual(0, completed.returncode, completed.stderr)
        self.assertEqual(
            [f"managed:--probe path={conda_prefix.parent}/vRhyme/bin:{conda_prefix.parent}/path-bin"],
            logged_commands,
        )

    def test_vrhyme_fallback_is_environment_manager_neutral(self):
        content = read_text("Modules", "binning_merge_module.sh")

        self.assertNotIn("conda run", content)
        self.assertIn('PATH="$managed_prefix/bin:$PATH"', content)

    def test_drep_module_uses_min_length_for_bins(self):
        content = read_text("Modules", "drep_module.sh")
        self.assertIn('-l "${MIN_LENGTH}"', content)

    def test_dependency_check_covers_runtime_tools(self):
        content = read_text("Modules", "ViOTUcluster_Check")
        for tool_name in ("viralverify", "sambamba", "parallel", "makeblastdb", "blastn"):
            self.assertIn(f'"{tool_name}"', content)

    def test_dependency_check_does_not_require_an_environment_manager(self):
        content = read_text("Modules", "ViOTUcluster_Check")
        dependency_block = content.split("dependencies=(", 1)[1].split(")", 1)[0]
        self.assertNotIn('"conda"', dependency_block)

    def test_dependency_check_omits_optional_dram_tools(self):
        content = read_text("Modules", "ViOTUcluster_Check")
        dependency_block = content.split("dependencies=(", 1)[1].split(")", 1)[0]
        self.assertNotIn('"coverm"', dependency_block)

    def test_dependency_check_has_sidecar_viralverify_fallback(self):
        content = read_text("Modules", "ViOTUcluster_Check")
        self.assertIn("../../viralverify/bin/viralverify", content)

    def test_dependency_check_has_nested_yaml_viralverify_fallback(self):
        content = read_text("Modules", "ViOTUcluster_Check")
        self.assertIn("../envs/viralverify/bin/viralverify", content)

    def test_dependency_check_versions_the_checkm_command(self):
        content = read_text("Modules", "ViOTUcluster_Check")
        self.assertIn('[checkm]="1.2.2"', content)

    def test_dependency_check_requires_checkm_to_start(self):
        content = read_text("Modules", "ViOTUcluster_Check")
        self.assertIn('if [ "$1" = "checkm" ] && ! checkm -h', content)

    def test_dependency_check_uses_distribution_metadata_for_packaged_versions(self):
        content = read_text("Modules", "ViOTUcluster_Check")
        self.assertIn('distribution_version "genomad"', content)
        self.assertIn('distribution_version "checkm-genome"', content)

    def test_dependency_check_has_no_dead_python_version_expectations(self):
        content = read_text("Modules", "ViOTUcluster_Check")

        self.assertNotIn("[scikit-learn]", content)
        self.assertNotIn("[numpy]", content)

    def test_dependency_check_covers_vrhyme(self):
        content = read_text("Modules", "ViOTUcluster_Check")
        self.assertIn('"vRhyme"', content)
        self.assertIn("../../vRhyme/bin/vRhyme", content)

    def test_dependency_check_fails_when_required_commands_are_missing(self):
        content = read_text("Modules", "ViOTUcluster_Check")
        self.assertRegex(content, r"for missing_dep[\s\S]+done\s+exit 1\s+fi")

    def test_packaged_mini_reads_match_test_command_input(self):
        content = read_text("Modules", "ViOTUcluster_Test")

        self.assertIn('READS_DIR="$VI_TEST_BASE_DIR/Raw/CleanReads"', content)
        self.assertIn('-r "$READS_DIR"', content)

    def test_test_command_captures_pipeline_output_and_exit_code(self):
        content = read_text("Modules", "ViOTUcluster_Test")

        self.assertIn('| tee "$LOG_FILE"', content)
        self.assertIn('COMMAND_EXIT_CODE=${PIPESTATUS[0]}', content)
        self.assertIn('SUCCESS_MESSAGE="All basic analysis completed successfully"', content)


if __name__ == "__main__":
    unittest.main()
