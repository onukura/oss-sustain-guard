#!/bin/bash

set -e

# GitHub Actions action entrypoint script for OSS Sustain Guard

# Parse input environment variables
PACKAGES="${INPUT_PACKAGES}"
ECOSYSTEM="${INPUT_ECOSYSTEM:-auto}"
INCLUDE_LOCK="${INPUT_INCLUDE_LOCK:-false}"
OUTPUT_STYLE="${INPUT_OUTPUT_STYLE:-normal}"
VERBOSE="${INPUT_VERBOSE:-false}"
PROFILE="${INPUT_PROFILE:-balanced}"
ROOT_DIR="${INPUT_ROOT_DIR:-.}"
MANIFEST="${INPUT_MANIFEST}"
RECURSIVE="${INPUT_RECURSIVE:-false}"
INSECURE="${INPUT_INSECURE:-false}"
GITHUB_TOKEN="${GITHUB_TOKEN}"

# Build command
CMD="uv run os4g check"

# Add packages (if specified)
if [ -n "${PACKAGES}" ]; then
    CMD="${CMD} ${PACKAGES}"
fi

# Add ecosystem option if not auto
if [ "${ECOSYSTEM}" != "auto" ]; then
    CMD="${CMD} --ecosystem ${ECOSYSTEM}"
fi

# Add lockfile detection option
if [ "${INCLUDE_LOCK}" = "true" ]; then
    CMD="${CMD} --include-lock"
fi

# Add output style option
if [ "${OUTPUT_STYLE}" != "normal" ]; then
    CMD="${CMD} -o ${OUTPUT_STYLE}"
fi

# Add verbose logging option
if [ "${VERBOSE}" = "true" ]; then
    CMD="${CMD} -v"
fi

# Add profile option
if [ "${PROFILE}" != "balanced" ]; then
    CMD="${CMD} --profile ${PROFILE}"
fi

# Add root directory option
if [ "${ROOT_DIR}" != "." ]; then
    CMD="${CMD} --root-dir ${ROOT_DIR}"
fi

# Add manifest file option
if [ -n "${MANIFEST}" ]; then
    CMD="${CMD} --manifest ${MANIFEST}"
fi

# Add recursive scanning option
if [ "${RECURSIVE}" = "true" ]; then
    CMD="${CMD} --recursive"
fi

# Add insecure SSL option
if [ "${INSECURE}" = "true" ]; then
    CMD="${CMD} --insecure"
fi

# Execute analysis
echo "🔍 Running OSS Sustain Guard analysis..."
echo "Command: ${CMD}"
echo ""

eval "${CMD}"

# Set output
echo "summary=✅ Analysis complete" >> "${GITHUB_OUTPUT}"
