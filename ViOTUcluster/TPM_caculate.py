import os
import sys

import pandas as pd


def _normalise_column_name(column):
    """Return a stable, case-insensitive representation of a table column."""
    return " ".join(str(column).strip().lower().split())


def _extract_tpm_series(table, source_name):
    """Extract TPM explicitly, or derive it from a CheckM coverage table."""
    if not table.index.is_unique:
        duplicates = table.index[table.index.duplicated()].unique().tolist()
        raise ValueError(
            f"{source_name} contains duplicate feature identifiers: {duplicates[:5]}"
        )

    named_tpm_columns = [
        column
        for column in table.columns
        if _normalise_column_name(column) == "tpm"
        or _normalise_column_name(column).endswith(" tpm")
    ]

    if named_tpm_columns:
        if len(named_tpm_columns) != 1:
            raise ValueError(
                f"{source_name} contains multiple TPM columns: {named_tpm_columns}"
            )
        tpm = pd.to_numeric(table[named_tpm_columns[0]], errors="raise")
    else:
        length_columns = [
            column
            for column in table.columns
            if _normalise_column_name(column) == "sequence length (bp)"
        ]
        mapped_read_columns = [
            column
            for column in table.columns
            if _normalise_column_name(column) == "mapped reads"
            or _normalise_column_name(column).startswith("mapped reads.")
        ]

        if len(length_columns) != 1 or len(mapped_read_columns) != 1:
            raise ValueError(
                f"{source_name} must contain exactly one named TPM column, or one "
                "'Sequence length (bp)' and one 'Mapped reads' column from CheckM"
            )

        lengths = pd.to_numeric(table[length_columns[0]], errors="raise")
        mapped_reads = pd.to_numeric(table[mapped_read_columns[0]], errors="raise")
        if (lengths <= 0).any():
            raise ValueError(f"{source_name} contains non-positive sequence lengths")
        if (mapped_reads < 0).any():
            raise ValueError(f"{source_name} contains negative mapped-read counts")

        reads_per_kilobase = mapped_reads / (lengths / 1000.0)
        rate_sum = reads_per_kilobase.sum()
        if rate_sum > 0:
            tpm = reads_per_kilobase / rate_sum * 1_000_000.0
        else:
            tpm = reads_per_kilobase.astype(float) * 0.0

    if tpm.isna().any():
        raise ValueError(f"{source_name} produced missing TPM values")
    if (tpm < 0).any():
        raise ValueError(f"{source_name} produced negative TPM values")
    return tpm.astype(float)


def merge_tpm_files(input_folder, merged_output_file, index_name="OTU"):
    """
    Merge TPM values from multiple TSV files into a single CSV file.

    Parameters:
    - input_folder (str): Path to the folder containing input TSV files.
    - merged_output_file (str): Path to save the merged TPM CSV file.
    - index_name (str): Name assigned to the index column in the output CSV.
    """
    tsv_files = sorted(
        file_name for file_name in os.listdir(input_folder) if file_name.endswith(".tsv")
    )
    if not tsv_files:
        raise ValueError(f"No TSV files found in {input_folder}")

    tpm_series_list = []
    for file_name in tsv_files:
        file_path = os.path.join(input_folder, file_name)
        table = pd.read_csv(file_path, sep="\t", index_col=0)
        tpm_series = _extract_tpm_series(table, file_name)
        tpm_series.name = os.path.splitext(file_name)[0]
        tpm_series_list.append(tpm_series)

    merged_df = pd.concat(tpm_series_list, axis=1, join="outer")
    if merged_df.isna().any().any():
        missing_by_sample = merged_df.isna().sum()
        missing_by_sample = missing_by_sample[missing_by_sample > 0].to_dict()
        raise ValueError(
            "Coverage tables contain inconsistent feature sets; missing values by sample: "
            f"{missing_by_sample}"
        )

    merged_df = merged_df.sort_index(axis=1)
    merged_df.columns = merged_df.columns.str.replace("_coverage", "", regex=False)
    if not merged_df.columns.is_unique:
        raise ValueError("Sample names are duplicated after removing the '_coverage' suffix")
    merged_df.index.name = index_name

    output_dir = os.path.dirname(os.path.abspath(merged_output_file))
    os.makedirs(output_dir, exist_ok=True)
    temporary_output = f"{merged_output_file}.tmp.{os.getpid()}"
    try:
        merged_df.to_csv(temporary_output, float_format="%.10f")
        os.replace(temporary_output, merged_output_file)
    finally:
        if os.path.exists(temporary_output):
            os.remove(temporary_output)
    print(f"Merged TPM file saved to {merged_output_file}")
    return merged_df


def main():
    """
    Main function to execute the TPM calculation and merging process.
    
    Expects two command-line arguments:
    1. Input folder containing TSV files.
    2. Output CSV file path for the merged TPM data.
    3. (Optional) Index column name for the output CSV (defaults to "OTU").
    """
    if len(sys.argv) not in (3, 4):
        print("Usage: python script.py <input_folder> <merged_output_file> [index_name]")
        sys.exit(1)
    
    input_folder = sys.argv[1]
    merged_output_file = sys.argv[2]
    index_name = sys.argv[3] if len(sys.argv) == 4 else "OTU"
    
    try:
        merge_tpm_files(input_folder, merged_output_file, index_name)
    except Exception as exc:
        print(f"Error merging TPM files: {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
