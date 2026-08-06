#!/usr/bin/env bash

set -euo pipefail

VIOTUCLUSTER_ENV_NAME="ViOTUcluster"
INSTALL_PREFIX=""
WITH_DRAM=false
WITH_IPHOP=false
USE_CHINA_HINT=false

echo_msg() {
    echo "$@"
}

show_help() {
    cat <<EOF
Usage: $0 [options]

This helper must be run from a ViOTUcluster repository checkout. It creates the
main Conda environment from environment.yml and can optionally create the DRAM
and iPhop satellite environments under <main-env>/envs/.

Options:
  -p, --prefix, --install-path <path>  Install the main environment at <path>/ViOTUcluster.
  --with-dram                          Create the optional DRAM satellite environment.
  --with-iphop                         Create the optional iPhop satellite environment.
  --all-optional                       Create both optional satellite environments.
  --china                              Show a reminder to configure local Conda mirrors before install.
  -h, --help                           Show this help message.
EOF
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        -p|--prefix|--install-path)
            if [[ -z "${2:-}" || "${2:-}" == -* ]]; then
                echo_msg "Error: Argument for $1 is missing or looks like another option."
                show_help
                exit 1
            fi
            INSTALL_PREFIX="$2"
            shift 2
            ;;
        --with-dram)
            WITH_DRAM=true
            shift
            ;;
        --with-iphop)
            WITH_IPHOP=true
            shift
            ;;
        --all-optional)
            WITH_DRAM=true
            WITH_IPHOP=true
            shift
            ;;
        --china)
            USE_CHINA_HINT=true
            shift
            ;;
        -h|--help)
            show_help
            exit 0
            ;;
        *)
            echo_msg "Error: Unrecognized argument: $1"
            show_help
            exit 1
            ;;
    esac
done

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$SCRIPT_DIR"
MAIN_ENV_FILE="$REPO_ROOT/environment.yml"
DRAM_ENV_FILE="$REPO_ROOT/environments/dram.yml"
IPHOP_ENV_FILE="$REPO_ROOT/environments/iphop.yml"

if [[ ! -f "$MAIN_ENV_FILE" ]]; then
    echo_msg "Error: environment.yml not found next to $0."
    echo_msg "Clone the ViOTUcluster repository first, then run this helper from that checkout."
    exit 1
fi

if [[ "$USE_CHINA_HINT" == true ]]; then
    echo_msg "Reminder: this script uses your existing Conda channel configuration."
    echo_msg "If you need a mainland mirror, configure Conda mirrors first, then rerun this helper."
fi

CONDA_BASE="$(conda info --base 2>/dev/null)" || {
    echo_msg "Error: Conda not found. Please install Conda first."
    exit 1
}

if [[ ! -f "$CONDA_BASE/etc/profile.d/conda.sh" ]]; then
    echo_msg "Error: Conda initialization script not found at $CONDA_BASE/etc/profile.d/conda.sh"
    exit 1
fi

. "$CONDA_BASE/etc/profile.d/conda.sh"

SOLVER="conda"
if command -v mamba >/dev/null 2>&1; then
    SOLVER="mamba"
fi

if [[ -n "$INSTALL_PREFIX" ]]; then
    mkdir -p "$INSTALL_PREFIX"
    INSTALL_PREFIX_ABS="$(cd "$INSTALL_PREFIX" && pwd)"
    MAIN_ENV_ROOT="$INSTALL_PREFIX_ABS/$VIOTUCLUSTER_ENV_NAME"
    ACTIVATE_HINT="conda activate $MAIN_ENV_ROOT"
else
    MAIN_ENV_ROOT="$CONDA_BASE/envs/$VIOTUCLUSTER_ENV_NAME"
    ACTIVATE_HINT="conda activate $VIOTUCLUSTER_ENV_NAME"
fi

create_or_update_env() {
    local manifest_path="$1"
    shift

    if [[ -d "$1/conda-meta" ]]; then
        echo_msg "[🔄] Updating environment at $1 from $(basename "$manifest_path")..."
        "$SOLVER" env update -p "$1" -f "$manifest_path" --prune
    else
        echo_msg "[🔄] Creating environment at $1 from $(basename "$manifest_path")..."
        "$SOLVER" env create -p "$1" -f "$manifest_path" -y
    fi
}

create_or_update_env "$MAIN_ENV_FILE" "$MAIN_ENV_ROOT"

echo_msg "[🔄] Refreshing ViOTUcluster package install in the main environment..."
(
    cd "$REPO_ROOT"
    conda run -p "$MAIN_ENV_ROOT" python -m pip install --no-deps --upgrade .
)

mkdir -p "$MAIN_ENV_ROOT/envs"

if [[ "$WITH_DRAM" == true ]]; then
    create_or_update_env "$DRAM_ENV_FILE" "$MAIN_ENV_ROOT/envs/DRAM"
fi

if [[ "$WITH_IPHOP" == true ]]; then
    create_or_update_env "$IPHOP_ENV_FILE" "$MAIN_ENV_ROOT/envs/iPhop"
fi

echo_msg "[✅] ViOTUcluster Conda setup complete."
echo_msg "Main environment: $MAIN_ENV_ROOT"
if [[ "$WITH_DRAM" == true ]]; then
    echo_msg "Optional DRAM environment: $MAIN_ENV_ROOT/envs/DRAM"
fi
if [[ "$WITH_IPHOP" == true ]]; then
    echo_msg "Optional iPhop environment: $MAIN_ENV_ROOT/envs/iPhop"
fi
echo_msg "Next step: $ACTIVATE_HINT"
