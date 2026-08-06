#!/usr/bin/env python3

import os
import shlex
import stat
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import pandas as pd


REPO_ROOT = Path(__file__).resolve().parents[1]
SUMMARY_MODULE = REPO_ROOT / "Modules" / "summary_module.sh"


class TestSummaryAbundanceIntegration(unittest.TestCase):
    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.test_root = Path(self.temporary_directory.name)
        self.output_dir = self.test_root / "output"
        self.raw_reads = self.test_root / "reads"
        self.fake_bin = self.test_root / "bin"
        self.contig_file = self.test_root / "sample1.fasta"
        self.checkm_log = self.test_root / "checkm.log"

        (self.output_dir / "Summary" / "vOTU" / "vOTU_CheckRes").mkdir(
            parents=True
        )
        (self.output_dir / "Summary" / "dRepRes").mkdir(parents=True)
        (self.output_dir / "Summary" / "temp").mkdir(parents=True)
        (self.output_dir / "Log").mkdir(parents=True)
        self.raw_reads.mkdir()
        self.fake_bin.mkdir()

        self.votu_fasta = self.output_dir / "Summary" / "vOTU" / "vOTU.fasta"
        self.votu_fasta.write_text(
            ">vOTU1\n" + "A" * 1000 + "\n>vOTU2\n" + "C" * 2000 + "\n",
            encoding="utf-8",
        )
        (self.output_dir / "Summary" / "vOTU" / "vOTU_CheckRes" / "quality_summary.tsv").write_text(
            "already checked\n", encoding="utf-8"
        )
        (self.output_dir / "Summary" / "vOTU" / "vOTU.Taxonomy.csv").write_text(
            "already annotated\n", encoding="utf-8"
        )
        self.contig_file.write_text(">sample1_contig\nACGT\n", encoding="utf-8")
        (self.raw_reads / "sample1_R1.fastq").write_text(
            "@r1/1\nACGT\n+\nIIII\n", encoding="utf-8"
        )
        (self.raw_reads / "sample1_R2.fastq").write_text(
            "@r1/2\nTGCA\n+\nIIII\n", encoding="utf-8"
        )

        self._write_executable(
            "bwa",
            r'''#!/usr/bin/env bash
set -euo pipefail
case "${1:-}" in
  index)
    shift
    prefix=""
    while [ "$#" -gt 0 ]; do
      case "$1" in
        -p) prefix=$2; shift 2 ;;
        -b) shift 2 ;;
        *) shift ;;
      esac
    done
    for extension in amb ann bwt pac sa; do
      : > "${prefix}.${extension}"
    done
    ;;
  mem)
    printf '@HD\tVN:1.6\tSO:unsorted\n'
    ;;
  *)
    exit 2
    ;;
esac
''',
        )
        self._write_executable(
            "sambamba",
            r'''#!/usr/bin/env bash
set -euo pipefail
command_name=$1
shift
case "$command_name" in
  view)
    cat
    ;;
  sort)
    output=""
    while [ "$#" -gt 0 ]; do
      case "$1" in
        -o) output=$2; shift 2 ;;
        -t) shift 2 ;;
        *) shift ;;
      esac
    done
    cat > "$output"
    ;;
  index)
    bam_file=${!#}
    : > "${bam_file}.bai"
    ;;
  *)
    exit 2
    ;;
esac
''',
        )
        self._write_executable(
            "checkm",
            r'''#!/usr/bin/env bash
set -euo pipefail
printf '%s\n' "$*" >> "$CHECKM_TEST_LOG"
[ "$1" = "coverage" ]
output_file=${@: -2:1}
printf 'Sequence Id\tBin Id\tSequence length (bp)\tBam Id\tCoverage\tMapped reads\n' > "$output_file"
printf 'vOTU1\tvOTU\t1000\tsample1\t1.0\t10\n' >> "$output_file"
printf 'vOTU2\tvOTU\t2000\tsample1\t0.0\t0\n' >> "$output_file"
''',
        )
        self._write_executable(
            "parallel",
            r'''#!/usr/bin/env bash
set -euo pipefail
[ "$1" = "-j" ]
shift 2
function_name=$1
shift
[ "$1" = ":::" ]
shift
for argument in "$@"; do
  "$function_name" "$argument"
done
''',
        )

        self.environment = os.environ.copy()
        self.environment.update(
            {
                "OUTPUT_DIR": str(self.output_dir),
                "RAW_SEQ_DIR": str(self.raw_reads),
                "THREADS": "1",
                "FILES": str(self.contig_file),
                "TPM_tasks": "1",
                "VIOTUCLUSTER_PYTHON": sys.executable,
                "DATABASE": str(self.test_root / "database"),
                "CHECKM_TEST_LOG": str(self.checkm_log),
                "PATH": str(self.fake_bin) + os.pathsep + os.environ.get("PATH", ""),
                "PYTHONPATH": str(REPO_ROOT),
            }
        )

    def tearDown(self):
        self.temporary_directory.cleanup()

    def _write_executable(self, name, content):
        path = self.fake_bin / name
        path.write_text(content, encoding="utf-8")
        path.chmod(path.stat().st_mode | stat.S_IXUSR)

    def _run_summary(self, **environment_overrides):
        environment = self.environment.copy()
        environment.update(environment_overrides)
        result = subprocess.run(
            ["bash", str(SUMMARY_MODULE)],
            cwd=str(REPO_ROOT),
            env=environment,
            text=True,
            capture_output=True,
            timeout=30,
        )
        if result.returncode != 0:
            self.fail(
                "summary_module.sh failed\n"
                f"stdout:\n{result.stdout}\n"
                f"stderr:\n{result.stderr}"
            )
        return result

    def _checkm_calls(self):
        if not self.checkm_log.exists():
            return []
        return self.checkm_log.read_text(encoding="utf-8").splitlines()

    def test_legacy_checkm_filters_tpm_and_cache_invalidation(self):
        self._run_summary()

        abundance_file = self.output_dir / "Summary" / "vOTU" / "vOTU.Abundance.csv"
        abundance = pd.read_csv(abundance_file, index_col=0)
        self.assertEqual(abundance.columns.tolist(), ["sample1"])
        self.assertEqual(abundance.loc["vOTU1", "sample1"], 1_000_000.0)
        self.assertEqual(abundance.loc["vOTU2", "sample1"], 0.0)

        first_call = shlex.split(self._checkm_calls()[0])
        self.assertEqual(first_call[0], "coverage")
        self.assertEqual(first_call[first_call.index("-a") + 1], "0.98")
        self.assertEqual(first_call[first_call.index("-e") + 1], "0.02")
        self.assertEqual(first_call[first_call.index("-m") + 1], "20")
        self.assertNotIn("-r", first_call)

        self._run_summary()
        self.assertEqual(len(self._checkm_calls()), 1, "unchanged inputs should hit cache")

        with self.votu_fasta.open("a", encoding="utf-8") as handle:
            handle.write("\n")
        self._run_summary()
        self.assertEqual(
            len(self._checkm_calls()), 2, "catalog changes must invalidate coverage"
        )

        stale_coverage = (
            self.output_dir
            / "Summary"
            / "SeperateRes"
            / "Coverage"
            / "removed_sample_coverage.tsv"
        )
        stale_coverage.write_text(
            "Contig\tTPM\nvOTU1\t10\nvOTU2\t20\n", encoding="utf-8"
        )
        self._run_summary(CHECKM_MIN_QC="25")
        self.assertEqual(
            len(self._checkm_calls()), 3, "CheckM parameter changes must invalidate coverage"
        )
        last_call = shlex.split(self._checkm_calls()[-1])
        self.assertEqual(last_call[last_call.index("-m") + 1], "25")
        abundance = pd.read_csv(abundance_file, index_col=0)
        self.assertEqual(
            abundance.columns.tolist(),
            ["sample1"],
            "coverage left by a removed sample must not reappear in abundance",
        )

        with (self.raw_reads / "sample1_R1.fastq").open("a", encoding="utf-8") as handle:
            handle.write("@r2/1\nAAAA\n+\nIIII\n")
        self._run_summary(CHECKM_MIN_QC="25")
        self.assertEqual(
            len(self._checkm_calls()), 4, "read changes must invalidate alignment and coverage"
        )


if __name__ == "__main__":
    unittest.main()
