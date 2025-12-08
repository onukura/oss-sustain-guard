#!/bin/bash

set -e

# GitHub Actions action entrypoint script for OSS Sustain Guard

# Parse input environment variables
PACKAGES="${INPUT_PACKAGES}"
ECOSYSTEM="${INPUT_ECOSYSTEM:-auto}"
INCLUDE_LOCK="${INPUT_INCLUDE_LOCK:-false}"
VERBOSE="${INPUT_VERBOSE:-false}"
INSECURE="${INPUT_INSECURE:-false}"
GITHUB_TOKEN="${GITHUB_TOKEN}"

# Build command
CMD="uv run oss-guard check"

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

# Add verbose option
if [ "${VERBOSE}" = "true" ]; then
    CMD="${CMD} --verbose"
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

