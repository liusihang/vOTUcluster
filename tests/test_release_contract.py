#!/usr/bin/env python3

import ast
from pathlib import Path
import unittest


REPO_ROOT = Path(__file__).resolve().parents[1]
RELEASE_VERSION = "0.7.0"
WORKFLOW = REPO_ROOT / ".github" / "workflows" / "publish-to-pypi.yml"


def setup_version():
    tree = ast.parse((REPO_ROOT / "setup.py").read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        if not isinstance(node.func, ast.Name) or node.func.id != "setup":
            continue
        for keyword in node.keywords:
            if keyword.arg == "version" and isinstance(keyword.value, ast.Constant):
                return keyword.value.value
    raise AssertionError("setup.py does not declare a literal setup(version=...)")


def config_version():
    tree = ast.parse(
        (REPO_ROOT / "ViOTUcluster" / "config.py").read_text(encoding="utf-8")
    )
    for node in tree.body:
        if not isinstance(node, ast.Assign):
            continue
        if any(isinstance(target, ast.Name) and target.id == "VERSION" for target in node.targets):
            if isinstance(node.value, ast.Constant):
                return node.value.value
    raise AssertionError("ViOTUcluster/config.py does not declare a literal VERSION")


class TestReleaseVersionContract(unittest.TestCase):
    def test_release_version_is_synchronized(self):
        self.assertEqual(RELEASE_VERSION, setup_version())
        self.assertEqual(RELEASE_VERSION, config_version())

    def test_generated_python_caches_are_excluded_from_release_artifacts(self):
        manifest = (REPO_ROOT / "MANIFEST.in").read_text(encoding="utf-8")
        setup_source = (REPO_ROOT / "setup.py").read_text(encoding="utf-8")

        self.assertIn("global-exclude *.py[cod]", manifest)
        self.assertIn("exclude_package_data", setup_source)
        self.assertIn('"__pycache__/*"', setup_source)
        self.assertIn('"*/__pycache__/*"', setup_source)


class TestTrustedPublisherWorkflowContract(unittest.TestCase):
    def test_trusted_publisher_workflow_exists(self):
        self.assertTrue(WORKFLOW.is_file(), f"missing workflow: {WORKFLOW}")

    def test_trusted_publisher_workflow_uses_tagged_build_artifacts(self):
        self.assertTrue(WORKFLOW.is_file(), f"missing workflow: {WORKFLOW}")
        workflow = WORKFLOW.read_text(encoding="utf-8")

        expected_fragments = (
            'tags:\n      - "v*"',
            "uses: actions/checkout@v6",
            "uses: actions/setup-python@v6",
            "GITHUB_REF_NAME",
            "from ViOTUcluster.config import VERSION",
            "run: python -m build",
            "run: python -m twine check --strict dist/*",
            "uses: actions/upload-artifact@v5",
            "uses: actions/download-artifact@v6",
            "name: python-package-distributions",
            "needs: build",
            "name: pypi",
            "id-token: write",
            "uses: pypa/gh-action-pypi-publish@release/v1",
        )
        for fragment in expected_fragments:
            with self.subTest(fragment=fragment):
                self.assertIn(fragment, workflow)

        self.assertNotIn("PYPI_TOKEN", workflow)
        self.assertNotIn("secrets.", workflow)


if __name__ == "__main__":
    unittest.main()
