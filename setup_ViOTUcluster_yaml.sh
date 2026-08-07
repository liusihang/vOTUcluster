#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
ENVIRONMENT_DIR="$SCRIPT_DIR/environments"
DEFAULT_ENV_NAME=ViOTUcluster

INSTALL_PREFIX=""
ENV_NAME="$DEFAULT_ENV_NAME"
NAME_WAS_SET=false
DRY_RUN=false
CHECKM_DATA_ROOT=""
CONDA_RUNTIME_BIN=""

show_help() {
    cat <<'EOF'
Usage: setup_ViOTUcluster_yaml.sh [options]

Create ViOTUcluster from reproducible Conda YAML specifications.

Options:
  -n, --name NAME       Install under <conda-base>/envs/NAME.
  -p, --prefix PATH     Install the main environment at PATH.
      --dry-run         Solve all five YAML files without creating environments.
      --checkm-data-dir PATH
                        Reuse an extracted CheckM data directory instead of
                        downloading it during the CheckM post-link step.
  -h, --help            Show this help message.

The installer creates these prefixes:
  <main-prefix>
  <main-prefix>/envs/vRhyme
  <main-prefix>/envs/viralverify
  <main-prefix>/envs/DRAM
  <main-prefix>/envs/iPhop

Database downloads are intentionally separate from environment installation.
EOF
}

die() {
    printf 'Error: %s\n' "$*" >&2
    exit 1
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        -n|--name)
            [[ $# -ge 2 ]] || die "missing value for $1"
            [[ -z "$INSTALL_PREFIX" ]] || die "--name and --prefix cannot be used together"
            ENV_NAME=$2
            NAME_WAS_SET=true
            shift 2
            ;;
        -p|--prefix)
            [[ $# -ge 2 ]] || die "missing value for $1"
            [[ "$NAME_WAS_SET" = false ]] || die "--name and --prefix cannot be used together"
            INSTALL_PREFIX=$2
            shift 2
            ;;
        --dry-run)
            DRY_RUN=true
            shift
            ;;
        --checkm-data-dir)
            [[ $# -ge 2 ]] || die "missing value for $1"
            CHECKM_DATA_ROOT=$2
            shift 2
            ;;
        -h|--help)
            show_help
            exit 0
            ;;
        *)
            die "unknown option: $1"
            ;;
    esac
done

ENV_MANAGER=${VIOTUCLUSTER_ENV_MANAGER:-}
if [[ -z "$ENV_MANAGER" ]]; then
    if command -v mamba >/dev/null 2>&1; then
        ENV_MANAGER=$(command -v mamba)
    elif command -v conda >/dev/null 2>&1; then
        ENV_MANAGER=$(command -v conda)
    else
        die "neither mamba nor conda is available"
    fi
elif [[ "$ENV_MANAGER" == */* ]]; then
    [[ -x "$ENV_MANAGER" ]] || die "environment manager is not executable: $ENV_MANAGER"
elif ! command -v "$ENV_MANAGER" >/dev/null 2>&1; then
    die "environment manager is not available: $ENV_MANAGER"
fi

if [[ -z "$INSTALL_PREFIX" ]]; then
    command -v conda >/dev/null 2>&1 || die "conda is required to resolve --name installations"
    CONDA_BASE=$(conda info --base 2>/dev/null) || die "could not determine the Conda base directory"
    [[ -n "$CONDA_BASE" ]] || die "Conda returned an empty base directory"
    INSTALL_PREFIX="$CONDA_BASE/envs/$ENV_NAME"
elif [[ "$INSTALL_PREFIX" != /* ]]; then
    INSTALL_PREFIX="$PWD/$INSTALL_PREFIX"
fi

if [[ -n "$CHECKM_DATA_ROOT" && "$CHECKM_DATA_ROOT" != /* ]]; then
    CHECKM_DATA_ROOT="$PWD/$CHECKM_DATA_ROOT"
fi
if [[ -n "$CHECKM_DATA_ROOT" ]]; then
    CHECKM_MARKER="$CHECKM_DATA_ROOT/genome_tree/genome_tree.derep.txt"
    [[ -r "$CHECKM_MARKER" ]] || die "invalid CheckM data directory; missing readable marker: $CHECKM_MARKER"
fi

[[ ! -e "$INSTALL_PREFIX" ]] || die "installation prefix already exists: $INSTALL_PREFIX"

for environment_file in viotucluster.yml vrhyme.yml viralverify.yml dram.yml iphop.yml; do
    [[ -f "$ENVIRONMENT_DIR/$environment_file" ]] || die "missing environment file: $ENVIRONMENT_DIR/$environment_file"
done

if [[ "$DRY_RUN" = false ]]; then
    if [[ "$ENV_MANAGER" == */* ]]; then
        ENV_MANAGER_PATH="$ENV_MANAGER"
    else
        ENV_MANAGER_PATH=$(command -v "$ENV_MANAGER")
    fi
    ENV_MANAGER_BIN=$(cd "$(dirname "$ENV_MANAGER_PATH")" && pwd)
    CONDA_RUNTIME_CANDIDATES=(
        "${CONDA_EXE:-}"
        "$(type -P conda 2>/dev/null || true)"
        "$ENV_MANAGER_BIN/conda"
        "$ENV_MANAGER_BIN/../condabin/conda"
    )
    for candidate in "${CONDA_RUNTIME_CANDIDATES[@]}"; do
        if [[ -n "$candidate" && -x "$candidate" ]]; then
            CONDA_RUNTIME_BIN=$(cd "$(dirname "$candidate")" && pwd)
            break
        fi
    done
    [[ -n "$CONDA_RUNTIME_BIN" ]] || die "a conda executable is required at runtime but was not found beside the environment manager"
fi

create_environment() {
    local label=$1
    local environment_file=$2
    local target_prefix=$3
    local command_args=(
        env create
        --yes
        --file "$ENVIRONMENT_DIR/$environment_file"
        --prefix "$target_prefix"
    )

    if [[ "$DRY_RUN" = true ]]; then
        command_args+=(--dry-run)
    fi

    printf 'Creating %s environment at %s\n' "$label" "$target_prefix"
    if [[ -n "$CHECKM_DATA_ROOT" ]]; then
        CHECKM_DATA_DIR="$CHECKM_DATA_ROOT" \
            CONDA_CHANNEL_PRIORITY=strict \
            "$ENV_MANAGER" "${command_args[@]}"
    else
        CONDA_CHANNEL_PRIORITY=strict "$ENV_MANAGER" "${command_args[@]}"
    fi
}

create_environment ViOTUcluster viotucluster.yml "$INSTALL_PREFIX"
create_environment vRhyme vrhyme.yml "$INSTALL_PREFIX/envs/vRhyme"
create_environment viralverify viralverify.yml "$INSTALL_PREFIX/envs/viralverify"
create_environment DRAM dram.yml "$INSTALL_PREFIX/envs/DRAM"
create_environment iPhop iphop.yml "$INSTALL_PREFIX/envs/iPhop"

if [[ "$DRY_RUN" = true ]]; then
    printf '%s\n' 'All environment specifications solved successfully.'
    exit 0
fi

"$INSTALL_PREFIX/bin/python" -m pip install --no-deps "$SCRIPT_DIR"

MINI_READS_DIR="$INSTALL_PREFIX/ViTest/Raw/CleanReads"
mkdir -p "$MINI_READS_DIR"
cp "$SCRIPT_DIR"/test/*.fastq.gz "$MINI_READS_DIR/"

required_subenvironment_commands=(
    "envs/vRhyme/bin/vRhyme"
    "envs/viralverify/bin/viralverify"
    "envs/DRAM/bin/DRAM-v.py"
    "envs/iPhop/bin/iphop"
)
for relative_command in "${required_subenvironment_commands[@]}"; do
    [[ -x "$INSTALL_PREFIX/$relative_command" ]] || die "required command is missing: $INSTALL_PREFIX/$relative_command"
done

PATH="$INSTALL_PREFIX/bin:$CONDA_RUNTIME_BIN:$PATH" "$INSTALL_PREFIX/bin/ViOTUcluster_Check"

printf '%s\n' 'ViOTUcluster YAML installation completed.'
printf 'Activate with: conda activate %s\n' "$INSTALL_PREFIX"
printf '%s\n' 'Install databases separately with ViOTUcluster_download-database.'
