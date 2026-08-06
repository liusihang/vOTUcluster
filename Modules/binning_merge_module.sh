#!/usr/bin/env bash

# Enable error handling: exit the script if any command fails
set -e
trap 'echo "[❌] An error occurred. Exiting..."; exit 1;' ERR

: "${SAMBAMBA_SAVE_INTERMEDIATE:=false}"
VIOTUCLUSTER_PYTHON=${VIOTUCLUSTER_PYTHON:-python}

resolve_vrhyme_command() {
  if [ -n "${VRHYME_COMMAND:-}" ]; then
    printf '%s\n' "$VRHYME_COMMAND"
    return 0
  fi

  if command -v vRhyme >/dev/null 2>&1; then
    command -v vRhyme
    return 0
  fi

  if [ -n "${CONDA_PREFIX:-}" ] && [ -x "${CONDA_PREFIX}/envs/vRhyme/bin/vRhyme" ]; then
    printf '%s\n' "${CONDA_PREFIX}/envs/vRhyme/bin/vRhyme"
    return 0
  fi

  return 1
}

VRHYME_BIN="$(resolve_vrhyme_command)" || {
  echo "[❌] Error: vRhyme was not found on PATH and no nested sidecar env exists at \$CONDA_PREFIX/envs/vRhyme/bin/vRhyme."
  exit 1
}

# Perform Binning analysis
for FILE in $FILES; do
  echo "[🔄] Processing $FILE"

  BASENAME=$(basename "$FILE" .fa)
  BASENAME=${BASENAME%.fasta}
  OUT_DIR="$OUTPUT_DIR/SeprateFile/${BASENAME}"

  # Match files with BASENAME_R1* pattern
  Read1=$(find "${RAW_SEQ_DIR}" -maxdepth 1 -type f -name "${BASENAME}_R1*" | head -n 1)
  Read2=$(find "${RAW_SEQ_DIR}" -maxdepth 1 -type f -name "${BASENAME}_R2*" | head -n 1)

  if [ -z "$Read1" ] || [ -z "$Read2" ]; then
    echo "[❌] Error: Paired-end files for $BASENAME not found in the expected formats."
    exit 1
  fi

  #echo "Using Read1: $Read1"
  #echo "Using Read2: $Read2"

  # Create Binning directory
  echo "[📂] Creating Binning directory..."
  mkdir -p "$OUT_DIR/Binning"

  # Check and generate BAM file
  if [ ! -f "$OUT_DIR/Binning/alignment.sorted.bam" ]; then
    echo "[🔄] Indexing reference for ${BASENAME}..."
    bwa index -p "$OUT_DIR/Binning/assembly_index" "$OUT_DIR/${BASENAME}_filtered.fasta" >> "${OUTPUT_DIR}/Log/Binning_merge.log" 2>&1

    echo "[🔄] Running alignment and sorting for ${BASENAME}..."
    if [ "$SAMBAMBA_SAVE_INTERMEDIATE" = true ]; then
      INTERMEDIATE_BAM="$OUT_DIR/Binning/alignment.unsorted.bam"
      echo "[💾] Storing intermediate BAM for ${BASENAME} to avoid sambamba piping limits..." >> "${OUTPUT_DIR}/Log/Binning_merge.log"
      rm -f "$INTERMEDIATE_BAM"
      bwa mem -t "${THREADS}" "$OUT_DIR/Binning/assembly_index" "$Read1" "$Read2" 2>> "${OUTPUT_DIR}/Log/Binning_merge.log" | \
        sambamba view -S -f bam -t "${THREADS}" -o "$INTERMEDIATE_BAM" /dev/stdin 2>> "${OUTPUT_DIR}/Log/Binning_merge.log"
      sambamba sort -t "${THREADS}" -o "$OUT_DIR/Binning/alignment.sorted.bam" "$INTERMEDIATE_BAM" 2>> "${OUTPUT_DIR}/Log/Binning_merge.log"
    else
      bwa mem -t "${THREADS}" "$OUT_DIR/Binning/assembly_index" "$Read1" "$Read2" 2>> "${OUTPUT_DIR}/Log/Binning_merge.log" | \
        sambamba view -S -f bam -t "${THREADS}" /dev/stdin 2>> "${OUTPUT_DIR}/Log/Binning_merge.log" | \
        sambamba sort -t "${THREADS}" -o "$OUT_DIR/Binning/alignment.sorted.bam" /dev/stdin 2>> "${OUTPUT_DIR}/Log/Binning_merge.log"
    fi

    sambamba index -t "${THREADS}" "$OUT_DIR/Binning/alignment.sorted.bam" 2>> "${OUTPUT_DIR}/Log/Binning_merge.log"
  else
    echo "[⏭️] Alignment already completed for ${BASENAME}. Skipping..." >> "${OUTPUT_DIR}/Log/Binning_merge.log"
  fi

  VRHYME_DIR="$OUT_DIR/Binning/vRhyme_results_${BASENAME}_filtered"
  LOG_FILE="$VRHYME_DIR/log_vRhyme_${BASENAME}_filtered.log"

  # Check if vRhyme results already exist and are complete
  if [ -f "$LOG_FILE" ] && grep -q "Writing finalized bin sequences to individual fasta files" "$LOG_FILE"; then
    echo "[⏭️] vRhyme results for $BASENAME already exist. Skipping vRhyme run."
  else
    echo "[🔄] Running vRhyme for $BASENAME..."
    #source "$(conda info --base)/etc/profile.d/conda.sh"
    #conda activate vRhyme

    # Remove existing vRhyme results directory
    if [ -d "$VRHYME_DIR" ]; then
      echo "[📂] Deleting existing vRhyme results directory: $VRHYME_DIR"
      rm -rf "$VRHYME_DIR"
    fi

    "$VRHYME_BIN" -i "$OUT_DIR/${BASENAME}_filtered.fasta" \
                  -b "$OUT_DIR/Binning/alignment.sorted.bam" \
                  -t "${THREADS_PER_FILE}" \
                  -o "$VRHYME_DIR"

    #conda deactivate
  fi

  # Determine if reassembly is needed
  if [ "$REASSEMBLE" = true ]; then
    echo "[🔄] Starting reassembly for $BASENAME..."
    ALL_BINS_FA="$OUT_DIR/Binning/summary_bins_contigs.fa"
    cat "$VRHYME_DIR/vRhyme_best_bins_fasta/"*.fasta > "$ALL_BINS_FA"

    mkdir -p "$OUT_DIR/Binning/reads_for_reassembly"

    bwa index -p "$OUT_DIR/Binning/all_bins_index" "$ALL_BINS_FA"
    bwa mem -t "${THREADS}" "$OUT_DIR/Binning/all_bins_index" "$Read1" "$Read2" | "$VIOTUCLUSTER_PYTHON" -m ViOTUcluster.filter_reads_for_bin_reassembly "$VRHYME_DIR/vRhyme_best_bins_fasta" "$OUT_DIR/Binning/reads_for_reassembly" "$STRICT_MAX" "$PERMISSIVE_MAX"

    for FASTQ_FILE in "$OUT_DIR/Binning/reads_for_reassembly/"*_1.fastq; do
      BIN_BASENAME=$(basename "$FASTQ_FILE" _1.fastq)
      OriginalBin=${BIN_BASENAME%%.*}
      EXTRACTED_DIR="$OUT_DIR/Binning/reassembled_bins"

      mkdir -p "$EXTRACTED_DIR/${BIN_BASENAME}_tmp"

      spades.py -t "${THREADS}" --tmp "$EXTRACTED_DIR/${BIN_BASENAME}_tmp" --careful --untrusted-contigs "$VRHYME_DIR/vRhyme_best_bins_fasta/${OriginalBin}.fasta" \
                -1 "$OUT_DIR/Binning/reads_for_reassembly/${BIN_BASENAME}_1.fastq" \
                -2 "$OUT_DIR/Binning/reads_for_reassembly/${BIN_BASENAME}_2.fastq" \
                -o "$OUT_DIR/Binning/reassembile/${BIN_BASENAME}"

      mkdir -p "$EXTRACTED_DIR"
      cp "$OUT_DIR/Binning/reassembile/${BIN_BASENAME}/contigs.fasta" "$EXTRACTED_DIR/${BIN_BASENAME}.fasta"
    done

    mkdir -p "$OUT_DIR/Binning/Summary"
    "$VIOTUCLUSTER_PYTHON" -m ViOTUcluster.concat_fasta_sequences "$EXTRACTED_DIR" "$OUT_DIR/Binning/Summary/tempsummary.fasta"
  fi

  # Create bins directory
  echo "[📂] Creating final bins directory..."
  mkdir -p "${OUTPUT_DIR}/Summary/SeperateRes/bins"

  # Define unbined output file path
  UNBINNED_FASTA="$OUTPUT_DIR/Summary/SeperateRes/unbined/${BASENAME}_unbined.fasta"

  # Skip steps if unbined fasta already exists
  if [ -f "$UNBINNED_FASTA" ]; then
    echo "[⏭️] All processing steps already completed for $FILE, skipping..."
  else
    # Rename and copy vRhyme results
    echo "[🔄] Organizing vRhyme output for $BASENAME..."
    for vRhymeFILE in "$VRHYME_DIR/vRhyme_best_bins_fasta/"*.fasta; do
      NEW_NAME=$(basename "$vRhymeFILE" | sed "s/^vRhyme_/${BASENAME}_/")
      NEW_PATH="$OUT_DIR/Binning/Summary/FinalFasta/Bestbins/$NEW_NAME"
      
      mkdir -p "${OUT_DIR}/Binning/Summary/FinalFasta/Bestbins"
      
      cp "$vRhymeFILE" "$NEW_PATH"
      cp "$NEW_PATH" "${OUTPUT_DIR}/Summary/SeperateRes/bins"
    done

    # Merge bins and unbined sequences
    echo "[🔄] Merging bins and generating unbined sequences..."
    "$VIOTUCLUSTER_PYTHON" -m ViOTUcluster.Mergebins -i "$VRHYME_DIR/vRhyme_best_bins_fasta" -o "${OUTPUT_DIR}/Summary/SeperateRes/bins/${BASENAME}_bins.fasta"

    # Generate unbined sequences
    mkdir -p "$OUTPUT_DIR/Summary/SeperateRes/unbined"
    "$VIOTUCLUSTER_PYTHON" -m ViOTUcluster.unbined -i "$VRHYME_DIR/vRhyme_best_bins_fasta" -r "$OUT_DIR/${BASENAME}_filtered.fasta" -o "$UNBINNED_FASTA"

    # Combine bins and unbined sequences
    cat "${OUTPUT_DIR}/Summary/SeperateRes/bins/${BASENAME}_bins.fasta" "${OUTPUT_DIR}/Summary/SeperateRes/unbined/${BASENAME}_unbined.fasta" > "${OUTPUT_DIR}/Summary/SeperateRes/${BASENAME}_viralseqs.fasta"
    rm -f "${OUTPUT_DIR}/Summary/SeperateRes/bins/${BASENAME}_bins.fasta"
    echo "[✅] Rebinning and reassembly complete for $FILE"
  fi
done
