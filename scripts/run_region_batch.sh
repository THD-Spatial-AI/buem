#!/usr/bin/env bash
#
# Run every building of one region through buem's thermal model on a Linux
# host, writing per-building results to a single Parquet file.
#
# Sized for a whole community (Loenen is ~3,100 residential buildings) on a
# multi-core server rather than a laptop: the run takes tens of minutes, is
# resumable, and detaches from the terminal so an SSH session can drop
# without killing it.
#
# Usage
#   scripts/run_region_batch.sh [DATA_DIR] [OUTPUT] [WORKERS]
#
#   DATA_DIR  CsvBuildingSource region directory
#             (default: src/buem/data/buildings/netherlands)
#   OUTPUT    Parquet path         (default: results/<region>.parquet)
#   WORKERS   Worker processes     (default: all cores minus two)
#
# Environment
#   WEATHER_DATA_DIR  Required. Root of the processed provider archives
#                     (the NetCDF output of `weather run --provider ...`).
#                     Never point this at a copy inside the buem checkout --
#                     the archives are 1-2 GB per provider-month and belong
#                     wherever the weather pipeline produced them.
#   CONDA_ENV         Conda environment to activate (default: buem_env).
#                     Skipped entirely if already inside the right env.
#   COUNTRY           TABULA country code for archetype matching
#                     (default: NL — every CsvBuildingSource region today).
#
# Re-running the same command resumes: building ids already in OUTPUT are
# skipped and their rows preserved, so an interrupted run continues rather
# than restarting.
set -euo pipefail

DATA_DIR="${1:-src/buem/data/buildings/netherlands}"
REGION_NAME="$(basename "${DATA_DIR}")"
OUTPUT="${2:-results/${REGION_NAME}.parquet}"
CONDA_ENV="${CONDA_ENV:-buem_env}"
COUNTRY="${COUNTRY:-NL}"

if [[ -z "${WEATHER_DATA_DIR:-}" ]]; then
    echo "ERROR: WEATHER_DATA_DIR is not set." >&2
    echo "Point it at the processed provider archives, e.g." >&2
    echo "  export WEATHER_DATA_DIR=/data/soma/weather/data" >&2
    exit 1
fi
if [[ ! -d "${WEATHER_DATA_DIR}" ]]; then
    echo "ERROR: WEATHER_DATA_DIR=${WEATHER_DATA_DIR} is not a directory." >&2
    exit 1
fi
if [[ ! -d "${DATA_DIR}" ]]; then
    echo "ERROR: region directory ${DATA_DIR} not found (run from the repo root)." >&2
    exit 1
fi

# Default to leaving two cores for the OS and for the parent process that
# collects results and writes Parquet.
if [[ -n "${3:-}" ]]; then
    WORKERS="$3"
else
    CORES="$(nproc 2>/dev/null || echo 4)"
    WORKERS="$(( CORES > 3 ? CORES - 2 : 1 ))"
fi

if [[ "${CONDA_DEFAULT_ENV:-}" != "${CONDA_ENV}" ]]; then
    # shellcheck disable=SC1091
    source "$(conda info --base)/etc/profile.d/conda.sh"
    conda activate "${CONDA_ENV}"
fi

# Each worker's linear algebra is single-building and small; letting BLAS
# spawn its own thread pool inside every worker oversubscribes the cores and
# slows the whole run down.
export OMP_NUM_THREADS=1
export OPENBLAS_NUM_THREADS=1
export MKL_NUM_THREADS=1

mkdir -p "$(dirname "${OUTPUT}")" logs
LOG="logs/batch_${REGION_NAME}_$(date +%Y%m%d_%H%M%S).log"

echo "Region:  ${DATA_DIR}"
echo "Output:  ${OUTPUT}"
echo "Workers: ${WORKERS}"
echo "Log:     ${LOG}"

nohup python -m buem.analysis.batch \
    --source csv \
    --data-dir "${DATA_DIR}" \
    --country "${COUNTRY}" \
    --residential-only \
    --resume \
    --workers "${WORKERS}" \
    --flush-every 100 \
    --output "${OUTPUT}" \
    > "${LOG}" 2>&1 &

echo "Started as PID $!. Follow with: tail -f ${LOG}"
