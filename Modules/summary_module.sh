#!/usr/bin/env bash
set -Eeuo pipefail

VIOTUCLUSTER_PYTHON=${VIOTUCLUSTER_PYTHON:-python}
# Merge all
echo "[🔄] Merging final sequences..."

# Define the path for the quality_summary.tsv file
QUALITY_SUMMARY="$OUTPUT_DIR/Summary/vOTU/vOTU_CheckRes/quality_summary.tsv"

# Define paths for input FASTA files
DREP_VIRAL_FASTA="$OUTPUT_DIR/Summary/dRepRes/DrepViralcontigs.fasta"
DREP_BINS_FASTA="$OUTPUT_DIR/Summary/dRepRes/DrepBins.fasta"

# Check if quality_summary.tsv already exists
if [ -f "$QUALITY_SUMMARY" ]; then
  echo "[✅] quality_summary.tsv already exists, skipping vOTU merging and CheckV analysis."
else
  # Create vOTU directory
  echo "[📁] Creating vOTU directory..."
  mkdir -p "$OUTPUT_DIR/Summary/vOTU"

  # Rename DrepViralcontigs.fasta file
  echo "[🔄] Renaming sequences..."
  "$VIOTUCLUSTER_PYTHON" -m ViOTUcluster.Rename -i "$DREP_VIRAL_FASTA"

  # Merge DrepViralcontigs.fasta and DrepBins.fasta into vOTU.fasta
  echo "[🔄] Merging FASTA files..."
  cat "$DREP_VIRAL_FASTA" "$DREP_BINS_FASTA" > "$OUTPUT_DIR/Summary/vOTU/vOTU.fasta"

  # Run CheckV analysis
  echo "[🔄] Running CheckV analysis..."
  checkv end_to_end "$OUTPUT_DIR/Summary/vOTU/vOTU.fasta" "$OUTPUT_DIR/Summary/vOTU/vOTU_CheckRes" -t "${THREADS}" -d "$DATABASE/checkv-db-v1.5"
  if [ $? -ne 0 ]; then
    echo "[❌] Error: CheckV analysis failed."
    exit 1
  fi

  echo "[✅] CheckV analysis completed successfully."
fi

# Define the path for vOTU.Abundance.csv
ABUNDANCE_CSV="$OUTPUT_DIR/Summary/vOTU/vOTU.Abundance.csv"
ABUNDANCE_CACHE_FILE="${ABUNDANCE_CSV}.cache-key"
ABUNDANCE_CACHE_SCHEMA="checkm-tpm-v1"
COVERAGE_CACHE_SCHEMA="checkm-coverage-v1"
CHECKM_MIN_ALIGN=${CHECKM_MIN_ALIGN:-0.98}
CHECKM_MAX_EDIT_DIST=${CHECKM_MAX_EDIT_DIST:-0.02}
CHECKM_MIN_QC=${CHECKM_MIN_QC:-20}
VOTU_FASTA="$OUTPUT_DIR/Summary/vOTU/vOTU.fasta"
TPM_TEMP_DIR="$OUTPUT_DIR/Summary/Viralcontigs/TPMTemp"
INDEX_PREFIX="$TPM_TEMP_DIR/TempIndex"
CHECKM_REFERENCE_DIR="$TPM_TEMP_DIR/CheckMReference"
COVERAGE_DIR="$OUTPUT_DIR/Summary/SeperateRes/Coverage"
CURRENT_COVERAGE_DIR="$TPM_TEMP_DIR/CurrentCoverage"

hash_lines() {
  sha256sum | awk '{print $1}'
}

file_signature() {
  stat -Lc '%n|%s|%y' -- "$1"
}

tool_signature() {
  local executable
  if ! executable=$(command -v "$1"); then
    echo "[❌] Error: Required command '$1' is not available." >&2
    return 1
  fi
  file_signature "$executable"
}

cache_matches() {
  local data_file=$1
  local cache_file=$2
  local expected_key=$3
  [ -f "$data_file" ] && [ -f "$cache_file" ] && \
    [ "$(tr -d '\r\n' < "$cache_file")" = "$expected_key" ]
}

write_cache_key() {
  local cache_file=$1
  local cache_key=$2
  local temporary_cache="${cache_file}.tmp.$$"
  printf '%s\n' "$cache_key" > "$temporary_cache"
  mv -f -- "$temporary_cache" "$cache_file"
}

sample_basename() {
  local name
  name=$(basename "$1")
  case "$name" in
    *.fasta) name=${name%.fasta} ;;
    *.fna) name=${name%.fna} ;;
    *.fa) name=${name%.fa} ;;
  esac
  printf '%s\n' "$name"
}

find_unique_read() {
  local basename=$1
  local mate=$2
  local first_match=""
  local second_match=""
  first_match=$(find "$RAW_SEQ_DIR" -type f -name "${basename}_${mate}*" -print | LC_ALL=C sort | sed -n '1p')
  second_match=$(find "$RAW_SEQ_DIR" -type f -name "${basename}_${mate}*" -print | LC_ALL=C sort | sed -n '2p')
  if [ -z "$first_match" ]; then
    echo "[❌] Error: ${mate} file not found for $basename." >&2
    return 1
  fi
  if [ -n "$second_match" ]; then
    echo "[❌] Error: Multiple ${mate} files found for $basename; refusing an arbitrary first match." >&2
    return 1
  fi
  printf '%s\n' "$first_match"
}

sample_alignment_cache_key() {
  local basename=$1
  local read1=$2
  local read2=$3
  {
    printf 'schema=bwa-v1\n'
    printf 'sample=%s\n' "$basename"
    printf 'catalog_sha256=%s\n' "$CATALOG_SHA"
    printf 'read1=%s\n' "$(file_signature "$read1")"
    printf 'read2=%s\n' "$(file_signature "$read2")"
    printf 'bwa=%s\n' "$BWA_SIGNATURE"
    printf 'sambamba=%s\n' "$SAMBAMBA_SIGNATURE"
  } | hash_lines
}

sample_coverage_cache_key() {
  local alignment_key=$1
  {
    printf 'schema=%s\n' "$COVERAGE_CACHE_SCHEMA"
    printf 'alignment_key=%s\n' "$alignment_key"
    printf 'checkm=%s\n' "$CHECKM_SIGNATURE"
    printf 'min_align=%s\n' "$CHECKM_MIN_ALIGN"
    printf 'max_edit_dist=%s\n' "$CHECKM_MAX_EDIT_DIST"
    printf 'min_qc=%s\n' "$CHECKM_MIN_QC"
    printf 'proper_pairs_only=true\n'
  } | hash_lines
}

build_abundance_cache_key() {
  local file
  local basename
  local read1
  local read2
  local -a sample_records=()
  {
    printf 'schema=%s\n' "$ABUNDANCE_CACHE_SCHEMA"
    printf 'catalog_sha256=%s\n' "$CATALOG_SHA"
    printf 'bwa=%s\n' "$BWA_SIGNATURE"
    printf 'sambamba=%s\n' "$SAMBAMBA_SIGNATURE"
    printf 'checkm=%s\n' "$CHECKM_SIGNATURE"
    printf 'min_align=%s\n' "$CHECKM_MIN_ALIGN"
    printf 'max_edit_dist=%s\n' "$CHECKM_MAX_EDIT_DIST"
    printf 'min_qc=%s\n' "$CHECKM_MIN_QC"
    printf 'proper_pairs_only=true\n'
    printf 'tpm_implementation_sha256=%s\n' "$TPM_IMPLEMENTATION_SHA"
    for file in "${FILE_ARRAY[@]}"; do
      basename=$(sample_basename "$file")
      read1=$(find_unique_read "$basename" R1)
      read2=$(find_unique_read "$basename" R2)
      sample_records+=("sample=${basename}|read1=$(file_signature "$read1")|read2=$(file_signature "$read2")")
    done
    printf '%s\n' "${sample_records[@]}" | LC_ALL=C sort
  } | hash_lines
}

ensure_bwa_index() {
  local index_key
  local index_cache_file="${INDEX_PREFIX}.cache-key"
  local complete=true
  local extension
  index_key=$({
    printf 'schema=bwa-index-v1\n'
    printf 'catalog_sha256=%s\n' "$CATALOG_SHA"
    printf 'bwa=%s\n' "$BWA_SIGNATURE"
  } | hash_lines)

  for extension in amb ann bwt pac sa; do
    if [ ! -f "${INDEX_PREFIX}.${extension}" ]; then
      complete=false
      break
    fi
  done

  if [ "$complete" = true ] && cache_matches "${INDEX_PREFIX}.sa" "$index_cache_file" "$index_key"; then
    echo "[✅] BWA index cache matches the current vOTU catalog."
    return 0
  fi

  echo "[🔄] Building BWA index for the current vOTU catalog..."
  rm -f -- "${INDEX_PREFIX}.amb" "${INDEX_PREFIX}.ann" "${INDEX_PREFIX}.bwt" \
    "${INDEX_PREFIX}.pac" "${INDEX_PREFIX}.sa" "$index_cache_file"
  bwa index -b "100000000" -p "$INDEX_PREFIX" "$VOTU_FASTA"
  for extension in amb ann bwt pac sa; do
    if [ ! -f "${INDEX_PREFIX}.${extension}" ]; then
      echo "[❌] Error: BWA index is incomplete; missing ${INDEX_PREFIX}.${extension}." >&2
      return 1
    fi
  done
  write_cache_key "$index_cache_file" "$index_key"
}

process_sample_bam() {
  set -o pipefail
  local file=$1
  local basename
  local read1
  local read2
  local alignment_key
  local coverage_key
  local bam_file
  local bam_index
  local bam_cache_file
  local bam_temporary
  local coverage_file
  local coverage_cache_file
  local coverage_temporary

  basename=$(sample_basename "$file")
  read1=$(find_unique_read "$basename" R1) || return 1
  read2=$(find_unique_read "$basename" R2) || return 1
  alignment_key=$(sample_alignment_cache_key "$basename" "$read1" "$read2")
  coverage_key=$(sample_coverage_cache_key "$alignment_key")
  coverage_file="$COVERAGE_DIR/${basename}_coverage.tsv"
  coverage_cache_file="${coverage_file}.cache-key"
  if cache_matches "$coverage_file" "$coverage_cache_file" "$coverage_key"; then
    echo "[✅] CheckM coverage cache matches current inputs and parameters for ${basename}."
    return 0
  fi

  bam_file="$TPM_TEMP_DIR/${basename}_sorted_gene.bam"
  bam_index="${bam_file}.bai"
  bam_cache_file="${bam_file}.cache-key"
  if ! cache_matches "$bam_file" "$bam_cache_file" "$alignment_key" || [ ! -f "$bam_index" ]; then
    echo "[🔄] Aligning reads for ${basename}; BAM cache is absent or stale..."
    rm -f -- "$bam_file" "$bam_index" "$bam_cache_file"
    bam_temporary="${bam_file}.tmp.$$"
    if ! bwa mem -t "$THREADS" "$INDEX_PREFIX" "$read1" "$read2" 2>> "$OUTPUT_DIR/Log/Summary.log" | \
      sambamba view -S -f bam -t "$THREADS" /dev/stdin | \
      sambamba sort -t "$THREADS" -o "$bam_temporary" /dev/stdin; then
      rm -f -- "$bam_temporary"
      echo "[❌] Error: Alignment pipeline failed for $basename." >&2
      return 1
    fi
    mv -f -- "$bam_temporary" "$bam_file"
    if ! sambamba index -t "$THREADS" "$bam_file"; then
      rm -f -- "$bam_file" "$bam_index"
      echo "[❌] Error: Failed to index BAM for $basename." >&2
      return 1
    fi
    write_cache_key "$bam_cache_file" "$alignment_key"
  else
    echo "[✅] BAM cache matches current catalog and reads for ${basename}."
  fi

  echo "[🔄] Calculating strict CheckM coverage for ${basename}..."
  rm -f -- "$coverage_file" "$coverage_cache_file"
  coverage_temporary="${coverage_file}.tmp.$$.tsv"
  if ! checkm coverage -x fasta -a "$CHECKM_MIN_ALIGN" -e "$CHECKM_MAX_EDIT_DIST" \
    -m "$CHECKM_MIN_QC" -t "$THREADS" --quiet "$CHECKM_REFERENCE_DIR" \
    "$coverage_temporary" "$bam_file"; then
    rm -f -- "$coverage_temporary"
    echo "[❌] Error: CheckM coverage failed for $basename." >&2
    return 1
  fi
  mv -f -- "$coverage_temporary" "$coverage_file"
  write_cache_key "$coverage_cache_file" "$coverage_key"
  echo "[✅] Strict CheckM coverage completed for ${basename}."
}

read -r -a FILE_ARRAY <<< "$FILES"
if [ "${#FILE_ARRAY[@]}" -eq 0 ]; then
  echo "[❌] Error: No samples were supplied for abundance calculation." >&2
  exit 1
fi

SAMPLE_BASENAMES=()
for file in "${FILE_ARRAY[@]}"; do
  basename=$(sample_basename "$file")
  for existing_basename in "${SAMPLE_BASENAMES[@]}"; do
    if [ "$basename" = "$existing_basename" ]; then
      echo "[❌] Error: Duplicate sample name after removing FASTA extension: $basename" >&2
      exit 1
    fi
  done
  SAMPLE_BASENAMES+=("$basename")
done

CATALOG_SHA=$(sha256sum "$VOTU_FASTA" | awk '{print $1}')
BWA_SIGNATURE=$(tool_signature bwa)
SAMBAMBA_SIGNATURE=$(tool_signature sambamba)
CHECKM_SIGNATURE=$(tool_signature checkm)
TPM_IMPLEMENTATION_PATH=$("$VIOTUCLUSTER_PYTHON" -c \
  'import inspect; import ViOTUcluster.TPM_caculate as module; print(inspect.getsourcefile(module))')
if [ ! -f "$TPM_IMPLEMENTATION_PATH" ]; then
  echo "[❌] Error: Cannot locate the TPM implementation: $TPM_IMPLEMENTATION_PATH" >&2
  exit 1
fi
TPM_IMPLEMENTATION_SHA=$(sha256sum "$TPM_IMPLEMENTATION_PATH" | awk '{print $1}')
ABUNDANCE_EXPECTED_KEY=$(build_abundance_cache_key)

if cache_matches "$ABUNDANCE_CSV" "$ABUNDANCE_CACHE_FILE" "$ABUNDANCE_EXPECTED_KEY"; then
  echo "[✅] vOTU abundance cache matches current catalog, reads, tools, and CheckM parameters."
else
  if [ -f "$ABUNDANCE_CSV" ] || [ -f "$ABUNDANCE_CACHE_FILE" ]; then
    echo "[♻️] vOTU abundance cache is stale; recalculating."
  fi
  rm -f -- "$ABUNDANCE_CSV" "$ABUNDANCE_CACHE_FILE"
  mkdir -p "$TPM_TEMP_DIR" "$CHECKM_REFERENCE_DIR" "$COVERAGE_DIR"
  rm -f -- "$CHECKM_REFERENCE_DIR/vOTU.fasta"
  ln -s "$VOTU_FASTA" "$CHECKM_REFERENCE_DIR/vOTU.fasta"

  ensure_bwa_index

  export -f hash_lines file_signature cache_matches write_cache_key sample_basename
  export -f find_unique_read sample_alignment_cache_key sample_coverage_cache_key process_sample_bam
  export OUTPUT_DIR RAW_SEQ_DIR THREADS TPM_TEMP_DIR INDEX_PREFIX CHECKM_REFERENCE_DIR COVERAGE_DIR
  export CATALOG_SHA BWA_SIGNATURE SAMBAMBA_SIGNATURE CHECKM_SIGNATURE COVERAGE_CACHE_SCHEMA
  export CHECKM_MIN_ALIGN CHECKM_MAX_EDIT_DIST CHECKM_MIN_QC

  TPM_tasks=${TPM_tasks:-4}
  echo "[🔄] Processing ${#FILE_ARRAY[@]} samples with parallel (max ${TPM_tasks} concurrent jobs)..."
  parallel -j "$TPM_tasks" process_sample_bam ::: "${FILE_ARRAY[@]}"

  rm -rf -- "$CURRENT_COVERAGE_DIR"
  mkdir -p "$CURRENT_COVERAGE_DIR"
  for basename in "${SAMPLE_BASENAMES[@]}"; do
    coverage_file="$COVERAGE_DIR/${basename}_coverage.tsv"
    if [ ! -f "$coverage_file" ]; then
      echo "[❌] Error: Expected coverage table is missing: $coverage_file" >&2
      exit 1
    fi
    ln -s "$(readlink -f -- "$coverage_file")" "$CURRENT_COVERAGE_DIR/${basename}_coverage.tsv"
  done

  "$VIOTUCLUSTER_PYTHON" -m ViOTUcluster.TPM_caculate "$CURRENT_COVERAGE_DIR" "$ABUNDANCE_CSV"
  write_cache_key "$ABUNDANCE_CACHE_FILE" "$ABUNDANCE_EXPECTED_KEY"
  echo "[✅] Strict CheckM TPM calculation completed successfully."
fi

# Define the path for vOTU.Taxonomy.csv
TAXONOMY_CSV="$OUTPUT_DIR/Summary/vOTU/vOTU.Taxonomy.csv"

# Check if vOTU.Taxonomy.csv already exists
if [ -f "$TAXONOMY_CSV" ]; then
  echo "[✅] vOTU.Taxonomy.csv already exists, skipping Taxonomy prediction."
else
  echo "[🔬] Starting taxonomy prediction..."
  genomad annotate "$OUTPUT_DIR/Summary/vOTU/vOTU.fasta" "$OUTPUT_DIR/Summary/vOTU/TaxAnnotate" $DATABASE/genomad_db -t "$THREADS"
  "$VIOTUCLUSTER_PYTHON" -m ViOTUcluster.format_taxonomy "$OUTPUT_DIR/Summary/vOTU/TaxAnnotate/vOTU_annotate/vOTU_taxonomy.tsv" "$TAXONOMY_CSV" "$ABUNDANCE_CSV"
  echo "[✅] Taxonomy prediction completed successfully."
fi

rm -rf -- "$OUTPUT_DIR/Summary/temp"
rm -rf -- "$OUTPUT_DIR/Summary/dRepRes"
rm -rf -- "$OUTPUT_DIR/Summary/Viralcontigs"

echo "[✅] All files processed and combined successfully."
