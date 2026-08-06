#!/usr/bin/env python3

import os
import sys
import tempfile
import unittest

import pandas as pd


REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO_ROOT)

from ViOTUcluster.TPM_caculate import merge_tpm_files


class TestTpmCalculate(unittest.TestCase):
    def test_selects_named_tpm_column_instead_of_first_data_column(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            input_file = os.path.join(temporary_directory, "sample_coverage.tsv")
            output_file = os.path.join(temporary_directory, "abundance.csv")
            pd.DataFrame(
                {
                    "Contig": ["vOTU1", "vOTU2"],
                    "Count": [100, 200],
                    "sample.bam TPM": [12.5, 87.5],
                    "Covered Fraction": [0.9, 0.8],
                }
            ).to_csv(input_file, sep="\t", index=False)

            result = merge_tpm_files(temporary_directory, output_file)

            self.assertEqual(result.columns.tolist(), ["sample"])
            self.assertEqual(result["sample"].tolist(), [12.5, 87.5])

    def test_rejects_ambiguous_tpm_columns(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            input_file = os.path.join(temporary_directory, "sample_coverage.tsv")
            output_file = os.path.join(temporary_directory, "abundance.csv")
            pd.DataFrame(
                {
                    "Contig": ["vOTU1"],
                    "TPM": [1.0],
                    "sample TPM": [2.0],
                }
            ).to_csv(input_file, sep="\t", index=False)

            with self.assertRaisesRegex(ValueError, "multiple TPM columns"):
                merge_tpm_files(temporary_directory, output_file)

            self.assertFalse(os.path.exists(output_file))

    def test_calculates_tpm_from_checkm_mapped_reads_and_lengths(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            input_file = os.path.join(temporary_directory, "sample_coverage.tsv")
            output_file = os.path.join(temporary_directory, "abundance.csv")
            pd.DataFrame(
                {
                    "Sequence Id": ["vOTU1", "vOTU2"],
                    "Bin Id": ["vOTU", "vOTU"],
                    "Sequence length (bp)": [1000, 2000],
                    "Bam Id": ["sample", "sample"],
                    "Coverage": [7.0, 5.0],
                    "Mapped reads": [10, 10],
                }
            ).to_csv(input_file, sep="\t", index=False)

            result = merge_tpm_files(temporary_directory, output_file)

            self.assertAlmostEqual(result.loc["vOTU1", "sample"], 666666.6666667)
            self.assertAlmostEqual(result.loc["vOTU2", "sample"], 333333.3333333)
            self.assertAlmostEqual(result["sample"].sum(), 1_000_000.0)

    def test_all_zero_checkm_counts_produce_zero_tpm(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            input_file = os.path.join(temporary_directory, "sample_coverage.tsv")
            output_file = os.path.join(temporary_directory, "abundance.csv")
            pd.DataFrame(
                {
                    "Sequence Id": ["vOTU1", "vOTU2"],
                    "Bin Id": ["vOTU", "vOTU"],
                    "Sequence length (bp)": [1000, 2000],
                    "Bam Id": ["sample", "sample"],
                    "Coverage": [0.0, 0.0],
                    "Mapped reads": [0, 0],
                }
            ).to_csv(input_file, sep="\t", index=False)

            result = merge_tpm_files(temporary_directory, output_file)

            self.assertEqual(result["sample"].tolist(), [0.0, 0.0])

    def test_rejects_inconsistent_votu_sets_between_samples(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            output_file = os.path.join(temporary_directory, "abundance.csv")
            pd.DataFrame(
                {"Contig": ["vOTU1", "vOTU2"], "TPM": [1.0, 2.0]}
            ).to_csv(
                os.path.join(temporary_directory, "sample1_coverage.tsv"),
                sep="\t",
                index=False,
            )
            pd.DataFrame({"Contig": ["vOTU1"], "TPM": [3.0]}).to_csv(
                os.path.join(temporary_directory, "sample2_coverage.tsv"),
                sep="\t",
                index=False,
            )

            with self.assertRaisesRegex(ValueError, "inconsistent feature sets"):
                merge_tpm_files(temporary_directory, output_file)


if __name__ == "__main__":
    unittest.main()
