#!/usr/bin/env python3

import os
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ViOTUcluster import viralprediction


class TestViralverifyResolutionContract(unittest.TestCase):
    def test_module_import_does_not_require_runtime_env(self):
        self.assertTrue(hasattr(viralprediction, "resolve_viralverify_command"))

    def test_resolve_viralverify_command_prefers_explicit_env(self):
        with mock.patch.dict(os.environ, {"VIRALVERIFY_COMMAND": "/opt/viralverify/bin/viralverify"}):
            command = viralprediction.resolve_viralverify_command()
        self.assertEqual(["/opt/viralverify/bin/viralverify"], command)

    def test_resolve_viralverify_command_uses_sidecar_env_when_path_missing(self):
        with tempfile.TemporaryDirectory() as root:
            tool_path = os.path.join(root, "envs", "viralverify", "bin", "viralverify")
            os.makedirs(os.path.dirname(tool_path), exist_ok=True)
            with open(tool_path, "w", encoding="utf-8") as handle:
                handle.write("#!/usr/bin/env bash\n")
            os.chmod(tool_path, 0o755)

            fake_python = os.path.join(root, "envs", "ViOTUcluster", "bin", "python")
            os.makedirs(os.path.dirname(fake_python), exist_ok=True)
            with open(fake_python, "w", encoding="utf-8") as handle:
                handle.write("")

            with mock.patch.dict(os.environ, {}, clear=False):
                with mock.patch("ViOTUcluster.viralprediction.shutil.which", return_value=None):
                    with mock.patch.object(sys, "executable", fake_python):
                        command = viralprediction.resolve_viralverify_command()

        self.assertEqual([os.path.realpath(tool_path)], [os.path.realpath(command[0])])

    def test_resolve_viralverify_command_prefers_sidecar_over_path_hit(self):
        with tempfile.TemporaryDirectory() as root:
            sidecar_tool = os.path.join(root, "envs", "viralverify", "bin", "viralverify")
            os.makedirs(os.path.dirname(sidecar_tool), exist_ok=True)
            with open(sidecar_tool, "w", encoding="utf-8") as handle:
                handle.write("#!/usr/bin/env bash\n")
            os.chmod(sidecar_tool, 0o755)

            fake_python = os.path.join(root, "envs", "ViOTUcluster", "bin", "python")
            os.makedirs(os.path.dirname(fake_python), exist_ok=True)
            with open(fake_python, "w", encoding="utf-8") as handle:
                handle.write("")

            with mock.patch.dict(os.environ, {}, clear=False):
                with mock.patch("ViOTUcluster.viralprediction.shutil.which", return_value="/tmp/repo/ViOTUcluster/viralverify"):
                    with mock.patch.object(sys, "executable", fake_python):
                        command = viralprediction.resolve_viralverify_command()

        self.assertEqual([os.path.realpath(sidecar_tool)], [os.path.realpath(command[0])])

    def test_resolve_viralverify_command_uses_nested_yaml_environment(self):
        with tempfile.TemporaryDirectory() as root:
            nested_tool = os.path.join(
                root,
                "envs",
                "ViOTUcluster",
                "envs",
                "viralverify",
                "bin",
                "viralverify",
            )
            os.makedirs(os.path.dirname(nested_tool), exist_ok=True)
            with open(nested_tool, "w", encoding="utf-8") as handle:
                handle.write("#!/usr/bin/env bash\n")
            os.chmod(nested_tool, 0o755)

            fake_python = os.path.join(root, "envs", "ViOTUcluster", "bin", "python")
            os.makedirs(os.path.dirname(fake_python), exist_ok=True)
            with open(fake_python, "w", encoding="utf-8") as handle:
                handle.write("")

            with mock.patch.dict(os.environ, {}, clear=False):
                with mock.patch("ViOTUcluster.viralprediction.shutil.which", return_value=None):
                    with mock.patch.object(sys, "executable", fake_python):
                        command = viralprediction.resolve_viralverify_command()

        self.assertEqual([os.path.realpath(nested_tool)], [os.path.realpath(command[0])])

    def test_build_viralverify_env_prepends_compat_dir(self):
        env = viralprediction.build_viralverify_env({"PYTHONPATH": "/tmp/existing"})
        compat_dir = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(viralprediction.__file__))),
            "ViOTUcluster",
            "compat",
        )
        self.assertTrue(env["PYTHONPATH"].startswith(compat_dir))
        self.assertIn("/tmp/existing", env["PYTHONPATH"])
