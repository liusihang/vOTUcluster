#!/usr/bin/env python3

import os
from pathlib import Path
import re
import subprocess
import tempfile
import unittest

import yaml


REPO_ROOT = Path(__file__).resolve().parents[1]
ENVIRONMENT_DIR = REPO_ROOT / "environments"
INSTALLER = REPO_ROOT / "setup_ViOTUcluster_yaml.sh"


def load_environment(filename):
    with (ENVIRONMENT_DIR / filename).open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def conda_dependency_names(specification):
    names = set()
    for dependency in specification["dependencies"]:
        if isinstance(dependency, str):
            names.add(re.split(r"[<>=!~ \[]", dependency, maxsplit=1)[0].lower())
    return names


def pip_dependencies(specification):
    for dependency in specification["dependencies"]:
        if isinstance(dependency, dict) and "pip" in dependency:
            return dependency["pip"]
    return []


class TestYamlEnvironmentContracts(unittest.TestCase):
    def test_yaml_install_assets_are_in_source_distribution(self):
        manifest = (REPO_ROOT / "MANIFEST.in").read_text(encoding="utf-8")
        self.assertIn("include setup_ViOTUcluster_yaml.sh", manifest)
        self.assertIn("recursive-include environments *.yml", manifest)
        self.assertIn("recursive-include test *.fastq.gz", manifest)

    def test_installer_stages_bundled_mini_reads(self):
        installer = INSTALLER.read_text(encoding="utf-8")
        self.assertIn("ViTest/Raw/CleanReads", installer)
        self.assertIn('"$SCRIPT_DIR"/test/*.fastq.gz', installer)

    def test_main_environment_declares_runtime_commands(self):
        specification = load_environment("viotucluster.yml")

        self.assertEqual(["conda-forge", "bioconda", "nodefaults"], specification["channels"])
        required = {
            "python",
            "pip",
            "biopython",
            "pandas",
            "packaging",
            "fastp",
            "megahit",
            "spades",
            "genomad",
            "checkv",
            "drep",
            "checkm-genome",
            "bwa",
            "sambamba",
            "coverm",
            "parallel",
            "blast",
            "samtools",
            "pyhmmer",
            "prodigal",
            "screed",
            "ruamel.yaml",
            "snakemake",
            "click",
            "numpy",
            "scikit-learn",
            "imbalanced-learn",
            "seaborn",
            "conda-package-handling",
        }
        self.assertTrue(required.issubset(conda_dependency_names(specification)))

        custom_virsorter = [
            dependency
            for dependency in pip_dependencies(specification)
            if "liusihang/VirSorter2-pyhmmerAcc" in dependency
        ]
        self.assertEqual(1, len(custom_virsorter))
        self.assertRegex(custom_virsorter[0], r"@75e9b70143040243d0975c038b6caf3c416ee2e9$")

    def test_subenvironment_specs_match_runtime_layout(self):
        expected = {
            "vrhyme.yml": {"python", "samtools", "mash", "mummer", "mmseqs2", "prodigal", "bowtie2", "bwa", "scikit-learn", "vrhyme", "numpy"},
            "viralverify.yml": {"python", "viralverify", "pyhmmer", "prodigal"},
            "dram.yml": {"python", "pandas", "scikit-bio", "prodigal", "mmseqs2", "hmmer", "trnascan-se", "barrnap", "parallel", "pip"},
            "iphop.yml": {"python", "iphop"},
        }

        for filename, required in expected.items():
            with self.subTest(filename=filename):
                specification = load_environment(filename)
                self.assertEqual(["conda-forge", "bioconda", "nodefaults"], specification["channels"])
                self.assertTrue(required.issubset(conda_dependency_names(specification)))

        dram_pip = pip_dependencies(load_environment("dram.yml"))
        self.assertIn("DRAM-bio==1.5.0", dram_pip)
        self.assertIn(
            "setuptools<82",
            load_environment("dram.yml")["dependencies"],
        )

    def test_cpu_environment_specs_add_only_verified_tensorflow_builds(self):
        expected = (
            (
                "viotucluster.yml",
                "viotucluster-cpu.yml",
                "tensorflow=2.11.1=cpu_py38h66f0ec1_0",
            ),
            (
                "iphop.yml",
                "iphop-cpu.yml",
                "tensorflow=2.7.0=cpu_py38h66f0ec1_0",
            ),
        )

        for default_filename, cpu_filename, tensorflow_pin in expected:
            with self.subTest(cpu_filename=cpu_filename):
                cpu_path = ENVIRONMENT_DIR / cpu_filename
                self.assertTrue(cpu_path.is_file(), f"missing CPU environment file: {cpu_path}")
                default_specification = load_environment(default_filename)
                cpu_specification = load_environment(cpu_filename)
                self.assertEqual(default_specification["channels"], cpu_specification["channels"])
                cpu_dependencies = list(cpu_specification["dependencies"])
                self.assertIn(tensorflow_pin, cpu_dependencies)
                cpu_dependencies.remove(tensorflow_pin)
                self.assertEqual(default_specification["dependencies"], cpu_dependencies)

    def test_readme_documents_cpu_option(self):
        readme = (REPO_ROOT / "README.md").read_text(encoding="utf-8")

        self.assertIn("--cpu", readme)
        self.assertIn("CPU-only", readme)
        self.assertIn("CONDA_OVERRIDE_CUDA", readme)
        self.assertIn("mamba", readme)
        self.assertIn("TensorFlow 2.11.1", readme)
        self.assertIn("TensorFlow 2.7.0", readme)
        self.assertIn("9.19 GiB", readme)
        self.assertIn("15.72 GiB", readme)


class TestYamlInstallerContract(unittest.TestCase):
    def test_dependency_check_receives_the_conda_runtime_path(self):
        installer = INSTALLER.read_text(encoding="utf-8")

        self.assertIn("CONDA_RUNTIME_BIN", installer)
        self.assertIn(
            'PATH="$INSTALL_PREFIX/bin:$CONDA_RUNTIME_BIN:$PATH"',
            installer,
        )

    def run_installer(
        self,
        *arguments,
        prefix_exists=False,
        with_checkm_data=False,
        manager_name="fake-manager",
    ):
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            install_prefix = temp_path / "ViOTUcluster"
            if prefix_exists:
                install_prefix.mkdir()

            command_log = temp_path / "manager.log"
            fake_manager = temp_path / manager_name
            fake_manager.write_text(
                "#!/usr/bin/env bash\n"
                "printf 'CUDA_SET=%s CUDA_VALUE=%s CHECKM_DATA_DIR=%s args=%s\\n' "
                "\"${CONDA_OVERRIDE_CUDA+x}\" \"${CONDA_OVERRIDE_CUDA-<unset>}\" "
                "\"${CHECKM_DATA_DIR:-}\" \"$*\" >> \"$VIOTUCLUSTER_MANAGER_LOG\"\n",
                encoding="utf-8",
            )
            fake_manager.chmod(0o755)

            environment = dict(os.environ)
            environment["VIOTUCLUSTER_ENV_MANAGER"] = str(fake_manager)
            environment["VIOTUCLUSTER_MANAGER_LOG"] = str(command_log)

            checkm_data_dir = None
            installer_arguments = ["--prefix", str(install_prefix), *arguments]
            if with_checkm_data:
                checkm_data_dir = temp_path / "checkm_data"
                marker = checkm_data_dir / "genome_tree" / "genome_tree.derep.txt"
                marker.parent.mkdir(parents=True)
                marker.write_text("complete\n", encoding="utf-8")
                installer_arguments.extend(["--checkm-data-dir", str(checkm_data_dir)])

            completed = subprocess.run(
                ["bash", str(INSTALLER), *installer_arguments],
                cwd=REPO_ROOT,
                env=environment,
                capture_output=True,
                text=True,
            )
            logged_commands = command_log.read_text(encoding="utf-8").splitlines() if command_log.exists() else []
            return completed, logged_commands, install_prefix, checkm_data_dir

    def test_dry_run_creates_main_and_four_subenvironment_commands(self):
        completed, logged_commands, install_prefix, _ = self.run_installer("--dry-run")

        self.assertEqual(0, completed.returncode, completed.stderr)
        self.assertEqual(5, len(logged_commands))
        expected_prefixes = [
            install_prefix,
            install_prefix / "envs" / "vRhyme",
            install_prefix / "envs" / "viralverify",
            install_prefix / "envs" / "DRAM",
            install_prefix / "envs" / "iPhop",
        ]
        for target_prefix in expected_prefixes:
            self.assertTrue(any(f"--prefix {target_prefix}" in command for command in logged_commands))
        self.assertTrue(all("--dry-run" in command for command in logged_commands))
        self.assertIn("environments/viotucluster.yml", logged_commands[0])
        self.assertIn("environments/iphop.yml", logged_commands[-1])
        self.assertTrue(
            all("CUDA_SET= CUDA_VALUE=<unset>" in command for command in logged_commands)
        )

    def test_existing_prefix_is_rejected_before_manager_runs(self):
        completed, logged_commands, _, _ = self.run_installer(prefix_exists=True)

        self.assertNotEqual(0, completed.returncode)
        self.assertIn("already exists", completed.stderr)
        self.assertEqual([], logged_commands)

    def test_checkm_data_directory_is_forwarded_to_environment_creation(self):
        completed, logged_commands, _, checkm_data_dir = self.run_installer(
            "--dry-run",
            with_checkm_data=True,
        )

        self.assertEqual(0, completed.returncode, completed.stderr)
        self.assertEqual(5, len(logged_commands))
        self.assertTrue(
            all(f"CHECKM_DATA_DIR={checkm_data_dir}" in command for command in logged_commands)
        )

    def test_cpu_dry_run_selects_cpu_specs_and_hides_cuda(self):
        completed, logged_commands, _, _ = self.run_installer(
            "--dry-run",
            "--cpu",
            manager_name="mamba",
        )

        self.assertEqual(0, completed.returncode, completed.stderr)
        self.assertEqual(5, len(logged_commands))
        self.assertIn("environments/viotucluster-cpu.yml", logged_commands[0])
        self.assertIn("environments/iphop-cpu.yml", logged_commands[-1])
        self.assertTrue(all("CUDA_SET=x CUDA_VALUE=" in command for command in logged_commands))

    def test_cpu_mode_rejects_non_mamba_manager(self):
        completed, logged_commands, _, _ = self.run_installer(
            "--dry-run",
            "--cpu",
            manager_name="conda",
        )

        self.assertNotEqual(0, completed.returncode)
        self.assertIn("--cpu requires mamba", completed.stderr)
        self.assertEqual([], logged_commands)


if __name__ == "__main__":
    unittest.main()
