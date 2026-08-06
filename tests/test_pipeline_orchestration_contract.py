#!/usr/bin/env python3

import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ViOTUcluster.pipeline import ViOTUclusterPipeline


class PipelineFixture:
    def __init__(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.root = Path(self.tempdir.name)
        self.input_dir = self.root / "input"
        self.raw_dir = self.root / "raw"
        self.output_dir = self.root / "output"
        self.db_dir = self.root / "db"
        self.script_dir = self.root / "shell-modules"

        self.input_dir.mkdir()
        self.raw_dir.mkdir()
        self.output_dir.mkdir()
        self.db_dir.mkdir()
        self.script_dir.mkdir()
        (self.script_dir / "viral_prediction_module.sh").write_text("#!/usr/bin/env bash\n")

        self.original_script_dir = os.environ.get("ScriptDir")
        os.environ["ScriptDir"] = str(self.script_dir)

    def cleanup(self):
        if self.original_script_dir is None:
            os.environ.pop("ScriptDir", None)
        else:
            os.environ["ScriptDir"] = self.original_script_dir
        self.tempdir.cleanup()

    def make_pipeline(self, database=None):
        return ViOTUclusterPipeline(
            input_dir=str(self.input_dir),
            raw_seq_dir=str(self.raw_dir),
            output_dir=str(self.output_dir),
            database=str(database or self.db_dir),
            threads=8,
            max_prediction_tasks=3,
            tpm_tasks=2,
            assemble_jobs=4,
        )

    def populate_database_structure(self):
        for subdir in ("db", "ViralVerify", "checkv-db-v1.5", "genomad_db"):
            (self.db_dir / subdir).mkdir(exist_ok=True)

    def populate_virsorter_runtime_assets(self):
        virsorter_root = self.db_dir / "db"
        (virsorter_root / "hmm" / "viral").mkdir(parents=True, exist_ok=True)
        (virsorter_root / "group" / "NCLDV").mkdir(parents=True, exist_ok=True)
        (virsorter_root / "hmm" / "viral" / "combined.hmm").write_text("HMMER3/f\n")
        (virsorter_root / "group" / "NCLDV" / "rbs-prodigal-train.db").write_text("stub\n")


class TestPipelineOrchestrationContract(unittest.TestCase):
    def setUp(self):
        self.fx = PipelineFixture()

    def tearDown(self):
        self.fx.cleanup()

    def test_validate_inputs_requires_database_structure(self):
        pipeline = self.fx.make_pipeline()
        self.assertFalse(
            pipeline.validate_inputs(),
            "validate_inputs should fail fast when required database subdirectories are missing",
        )

    def test_validate_inputs_requires_virsorter_runtime_assets(self):
        self.fx.populate_database_structure()
        pipeline = self.fx.make_pipeline()
        self.assertFalse(
            pipeline.validate_inputs(),
            "validate_inputs should fail when VirSorter2 database assets are incomplete",
        )

    def test_validate_inputs_accepts_complete_virsorter_runtime_assets(self):
        self.fx.populate_database_structure()
        self.fx.populate_virsorter_runtime_assets()
        pipeline = self.fx.make_pipeline()
        self.assertTrue(
            pipeline.validate_inputs(),
            "validate_inputs should pass once required VirSorter2 assets are present",
        )

    def test_setup_environment_exports_stage_thread_budget(self):
        self.fx.populate_database_structure()
        pipeline = self.fx.make_pipeline()
        env = pipeline._setup_environment()

        self.assertEqual("8", env.get("THREADS_PER_FILE"))
        self.assertEqual("3", env.get("CROSS_VALIDATION_TASKS"))
        self.assertEqual(sys.executable, env.get("VIOTUCLUSTER_PYTHON"))

    def test_disable_binning_uses_post_cross_validation_fastas(self):
        self.fx.populate_database_structure()
        pipeline = self.fx.make_pipeline()

        filtered_dir = Path(pipeline.filtered_seqs_dir)
        filtered_dir.mkdir(parents=True, exist_ok=True)
        (filtered_dir / "sample1.fasta").write_text(">length_only\nAAAA\n")

        sample_dir = Path(pipeline.output_dir) / "SeprateFile" / "sample1"
        sample_dir.mkdir(parents=True, exist_ok=True)
        (sample_dir / "sample1_filtered.fasta").write_text(">viral_only\nTTTT\n")

        pipeline._prepare_unbinned_from_contigs()

        staged = Path(pipeline.output_dir) / "Summary" / "SeperateRes" / "unbined" / "sample1_unbined.fasta"
        self.assertTrue(staged.exists())
        self.assertEqual(">viral_only\nTTTT\n", staged.read_text())


if __name__ == "__main__":
    unittest.main()
