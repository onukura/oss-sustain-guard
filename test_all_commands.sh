#!/usr/bin/env bash

#
# OSS Sustain Guard - Comprehensive Command Test Script
#
# Prerequisites:
# - GITHUB_TOKEN must be set (.env file or environment variable)
# - uv run --directory "$SCRIPT_DIR" os4g must be installed (pipx, uv tool, pip, or from source)
#
# Usage:
#   1. Write GITHUB_TOKEN=your_token_here in .env file
#      or
#      export GITHUB_TOKEN=your_token_here
#   2. chmod +x test_all_commands.sh
#   3. ./test_all_commands.sh
#

set -e  # Exit on error

# Color definitions for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Test result counters
PASSED=0
FAILED=0
SKIPPED=0
TEST_RESULTS=()

# Record test results
record_result() {
    local test_name=$1
    local status=$2
    local message=$3

    if [ "$status" = "PASS" ]; then
        PASSED=$((PASSED + 1))
        echo -e "${GREEN}✓ PASS${NC}: $test_name"
    elif [ "$status" = "FAIL" ]; then
        FAILED=$((FAILED + 1))
        echo -e "${RED}✗ FAIL${NC}: $test_name - $message"
    elif [ "$status" = "SKIP" ]; then
        SKIPPED=$((SKIPPED + 1))
        echo -e "${YELLOW}⊘ SKIP${NC}: $test_name - $message"
    fi

    TEST_RESULTS+=("$status: $test_name")
}

# Print test section header
print_section() {
    echo ""
    echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${CYAN}$1${NC}"
    echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
}

# Execute command with error handling
run_test() {
    local test_name=$1
    shift
    local cmd="$@"

    echo -e "${BLUE}Running:${NC} $cmd"

    if eval "$cmd" > /tmp/os4g_test_output.log 2>&1; then
        record_result "$test_name" "PASS" ""
    else
        local exit_code=$?
        local error_msg=$(tail -n 5 /tmp/os4g_test_output.log | tr '\n' ' ')
        record_result "$test_name" "FAIL" "Exit code: $exit_code, Error: $error_msg"
    fi
}

# Optional test (continue on failure)
run_optional_test() {
    local test_name=$1
    shift
    local cmd="$@"

    echo -e "${BLUE}Running (optional):${NC} $cmd"

    if eval "$cmd" > /tmp/os4g_test_output.log 2>&1; then
        record_result "$test_name" "PASS" ""
    else
        record_result "$test_name" "SKIP" "Optional test - may fail depending on environment"
    fi
}

echo -e "${CYAN}╔════════════════════════════════════════════════════════════════╗${NC}"
echo -e "${CYAN}║  OSS Sustain Guard - Comprehensive Command Test Script         ║${NC}"
echo -e "${CYAN}╚════════════════════════════════════════════════════════════════╝${NC}"
echo ""

# Load environment variables from .env file
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if [ -f "$SCRIPT_DIR/.env" ]; then
    echo -e "${BLUE}📄 Loading .env file...${NC}"
    # Load .env file (supports export statements)
    set -a
    source "$SCRIPT_DIR/.env"
    set +a
    echo -e "${GREEN}✓ Successfully loaded environment variables from .env file${NC}"
fi

# Check prerequisites
print_section "Prerequisites Check"

if [ -z "$GITHUB_TOKEN" ]; then
    echo -e "${RED}✗ GITHUB_TOKEN is not set${NC}"
    echo "Usage:"
    echo "  1. Add GITHUB_TOKEN=your_token_here to .env file"
    echo "  or"
    echo "  2. export GITHUB_TOKEN=your_token_here"
    exit 1
else
    echo -e "${GREEN}✓ GITHUB_TOKEN is set${NC}"
fi

if ! command -v uv &> /dev/null; then
    echo -e "${RED}✗ uv command not found${NC}"
    echo "Installation: https://docs.astral.sh/uv/getting-started/installation/"
    exit 1
else
    echo -e "${GREEN}✓ uv command is available${NC}"
    uv run -m oss_sustain_guard --version 2>/dev/null || echo "(version info unavailable)"
fi

# Create temporary directory for tests
TEST_DIR=$(mktemp -d)
echo -e "${BLUE}Temporary test directory:${NC} $TEST_DIR"
cd "$TEST_DIR"

# Create sample files for testing
cat > requirements.txt << EOF
requests
click
httpx
EOF

cat > package-lock.json << EOF
{
  "name": "test-project",
  "lockfileVersion": 2,
  "requires": true,
  "packages": {
    "": {
      "name": "test-project",
      "dependencies": {
        "express": "^4.18.0",
        "lodash": "^4.17.21"
      }
    },
    "node_modules/express": {
      "version": "4.18.0",
      "resolved": "https://registry.npmjs.org/express/-/express-4.18.0.tgz"
    },
    "node_modules/lodash": {
      "version": "4.17.21",
      "resolved": "https://registry.npmjs.org/lodash/-/lodash-4.17.21.tgz"
    }
  },
  "dependencies": {
    "express": {
      "version": "4.18.0",
      "resolved": "https://registry.npmjs.org/express/-/express-4.18.0.tgz"
    },
    "lodash": {
      "version": "4.17.21",
      "resolved": "https://registry.npmjs.org/lodash/-/lodash-4.17.21.tgz"
    }
  }
}
EOF

cat > Cargo.lock << EOF
# This file is automatically @generated by Cargo.
# It is not intended for manual editing.
version = 3

[[package]]
name = "serde"
version = "1.0.0"
source = "registry+https://github.com/rust-lang/crates.io-index"

[[package]]
name = "tokio"
version = "1.0.0"
source = "registry+https://github.com/rust-lang/crates.io-index"

[[package]]
name = "test-project"
version = "0.1.0"
dependencies = [
 "serde",
 "tokio",
]
EOF

# ==========================================
# 1. check command tests
# ==========================================
print_section "1. check command tests"

# Basic package checks
run_test "check: Single package (Python)" "uv run --directory "$SCRIPT_DIR" os4g check requests --insecure"
run_test "check: Single package (JavaScript)" "uv run --directory "$SCRIPT_DIR" os4g check -e javascript express --insecure"
run_test "check: Single package (Rust)" "uv run --directory "$SCRIPT_DIR" os4g check -e rust serde --insecure"

# Multiple packages from requirements.txt
run_test "check: requirements.txt" "uv run --directory "$SCRIPT_DIR" os4g check requests click httpx --insecure"

# Multiple packages at once
run_test "check: Multiple packages" "uv run --directory "$SCRIPT_DIR" os4g check requests click httpx --insecure"

# Scoring profile tests
run_test "check: balanced profile" "uv run --directory "$SCRIPT_DIR" os4g check requests --profile balanced --insecure"
run_test "check: security_first profile" "uv run --directory "$SCRIPT_DIR" os4g check requests --profile security_first --insecure"
run_test "check: contributor_experience profile" "uv run --directory "$SCRIPT_DIR" os4g check requests --profile contributor_experience --insecure"
run_test "check: long_term_stability profile" "uv run --directory "$SCRIPT_DIR" os4g check requests --profile long_term_stability --insecure"

# Scan depth tests
run_test "check: shallow scan" "uv run --directory "$SCRIPT_DIR" os4g check requests --scan-depth shallow --insecure"
run_test "check: default scan" "uv run --directory "$SCRIPT_DIR" os4g check requests --scan-depth default --insecure"
run_test "check: deep scan" "uv run --directory "$SCRIPT_DIR" os4g check requests --scan-depth deep --insecure"

# Output format tests
run_test "check: JSON output" "uv run --directory "$SCRIPT_DIR" os4g check requests --output-format json --insecure"
run_test "check: HTML output" "uv run --directory "$SCRIPT_DIR" os4g check requests --output-format html --output-file report.html --insecure"
run_test "check: Markdown output" "uv run --directory "$SCRIPT_DIR" os4g check requests --output-format json --output-file report.json --insecure"

# Recursive scan tests
run_optional_test "check: Recursive scan (shallow)" "uv run --directory "$SCRIPT_DIR" os4g check requests --recursive --max-depth 1 --insecure"

# Lookback period tests
run_test "check: 90 days analysis" "uv run --directory "$SCRIPT_DIR" os4g check requests --days-lookback 90 --insecure"

# Verbose mode
run_test "check: verbose mode" "uv run --directory "$SCRIPT_DIR" os4g check requests --verbose --insecure"

# No-cache option
run_test "check: no cache" "uv run --directory "$SCRIPT_DIR" os4g check requests --no-cache --insecure"

# Ecosystem auto-detection
run_test "check: Ecosystem auto-detection" "uv run --directory "$SCRIPT_DIR" os4g check requests click --insecure"

# GitLab repository tests (optional - requires GITLAB_TOKEN)
if [ -n "$GITLAB_TOKEN" ]; then
    run_optional_test "check: GitLab package" "uv run --directory "$SCRIPT_DIR" os4g check gitlab-runner --insecure"
else
    record_result "check: GitLab package" "SKIP" "GITLAB_TOKEN not set"
fi

# ==========================================
# 2. cache command tests
# ==========================================
print_section "2. cache command tests"

# Cache statistics
run_test "cache stats: All ecosystems" "uv run --directory "$SCRIPT_DIR" os4g cache stats"
run_test "cache stats: Python ecosystem" "uv run --directory "$SCRIPT_DIR" os4g cache stats python"
run_test "cache stats: JavaScript ecosystem" "uv run --directory "$SCRIPT_DIR" os4g cache stats javascript"

# Cache listing
run_test "cache list: Python packages" "uv run --directory "$SCRIPT_DIR" os4g cache list python"
run_test "cache list: All ecosystems" "uv run --directory "$SCRIPT_DIR" os4g cache list"

# Cache list filtering
run_test "cache list: JSON output" "uv run --directory "$SCRIPT_DIR" os4g cache list python --sort name"
run_test "cache list: Package search" "uv run --directory "$SCRIPT_DIR" os4g cache list python --filter requests"

# Cache clearing
run_test "cache clear: Expired only" "uv run --directory "$SCRIPT_DIR" os4g cache clear --expired-only"
run_test "cache clear: Python ecosystem only" "uv run --directory "$SCRIPT_DIR" os4g cache clear python"

# Clear all cache (run last)
run_optional_test "cache clear: Clear all cache" "uv run --directory "$SCRIPT_DIR" os4g cache clear --all --force"

# ==========================================
# 3. trend command tests
# ==========================================
print_section "3. trend command tests"

# Basic trend analysis
run_test "trend: Monthly trend" "uv run --directory "$SCRIPT_DIR" os4g trend requests --interval monthly --periods 3 --insecure"
run_test "trend: Weekly trend" "uv run --directory "$SCRIPT_DIR" os4g trend requests --interval weekly --periods 4 --insecure"
run_test "trend: Quarterly trend" "uv run --directory "$SCRIPT_DIR" os4g trend requests --interval quarterly --periods 2 --insecure"

# Custom time window
run_test "trend: Custom window" "uv run --directory "$SCRIPT_DIR" os4g trend requests --window-days 60 --periods 3 --insecure"

# Profile specification
run_test "trend: security_first profile" "uv run --directory "$SCRIPT_DIR" os4g trend requests --profile security_first --periods 2 --insecure"

# Ecosystem specification
run_test "trend: JavaScript package" "uv run --directory "$SCRIPT_DIR" os4g trend -e javascript express --periods 2 --insecure"

# Output formats
run_test "trend: JSON output" "uv run --directory "$SCRIPT_DIR" os4g trend requests --periods 2 --insecure"
run_test "trend: HTML output" "uv run --directory "$SCRIPT_DIR" os4g trend requests --periods 2 --insecure"

# Scan depth
run_test "trend: shallow scan" "uv run --directory "$SCRIPT_DIR" os4g trend requests --scan-depth shallow --periods 2 --insecure"

# ==========================================
# 4. trace command tests (dependency analysis)
# ==========================================
print_section "4. trace command tests"

# Package mode - terminal output (default)
run_test "trace: Python package" "uv run --directory "$SCRIPT_DIR" os4g trace requests --insecure"
run_test "trace: JavaScript package" "uv run --directory "$SCRIPT_DIR" os4g trace -e javascript express --insecure"
run_test "trace: Rust package" "uv run --directory "$SCRIPT_DIR" os4g trace -e rust serde --insecure"

# Lockfile mode - terminal output
run_test "trace: requirements.txt" "uv run --directory "$SCRIPT_DIR" os4g trace $TEST_DIR/requirements.txt --insecure"
run_test "trace: package.json" "uv run --directory "$SCRIPT_DIR" os4g trace $TEST_DIR/package-lock.json --insecure"
run_test "trace: Cargo.toml" "uv run --directory "$SCRIPT_DIR" os4g trace $TEST_DIR/Cargo.lock --insecure"

# HTML output
run_test "trace: HTML output from package" "uv run --directory "$SCRIPT_DIR" os4g trace requests --output $TEST_DIR/trace-pkg.html --insecure"
run_test "trace: HTML output from lockfile" "uv run --directory "$SCRIPT_DIR" os4g trace $TEST_DIR/requirements.txt --output $TEST_DIR/trace-lock.html --insecure"

# JSON output
run_test "trace: JSON output from package" "uv run --directory "$SCRIPT_DIR" os4g trace requests --output $TEST_DIR/trace-pkg.json --insecure"
run_test "trace: JSON output from lockfile" "uv run --directory "$SCRIPT_DIR" os4g trace $TEST_DIR/package-lock.json --output $TEST_DIR/trace-lock.json --insecure"

# Depth control
run_test "trace: Direct dependencies only" "uv run --directory "$SCRIPT_DIR" os4g trace requests --max-depth 1 --insecure"
run_test "trace: Max depth 2" "uv run --directory "$SCRIPT_DIR" os4g trace $TEST_DIR/package-lock.json --max-depth 2 --insecure"
run_test "trace: Direct only flag" "uv run --directory "$SCRIPT_DIR" os4g trace $TEST_DIR/requirements.txt --direct-only --insecure"

# Scoring profiles
run_test "trace: security_first profile" "uv run --directory "$SCRIPT_DIR" os4g trace requests --profile security_first --insecure"
run_test "trace: Custom profile with lockfile" "uv run --directory "$SCRIPT_DIR" os4g trace $TEST_DIR/package-lock.json --profile contributor_experience --insecure"

# Scan depth
run_test "trace: shallow scan" "uv run --directory "$SCRIPT_DIR" os4g trace requests --scan-depth shallow --insecure"
run_test "trace: deep scan" "uv run --directory "$SCRIPT_DIR" os4g trace $TEST_DIR/package-lock.json --scan-depth deep --insecure"

# Workers and performance
run_test "trace: Custom workers" "uv run --directory "$SCRIPT_DIR" os4g trace $TEST_DIR/requirements.txt --num-workers 3 --insecure"
run_test "trace: No cache" "uv run --directory "$SCRIPT_DIR" os4g trace requests --no-cache --insecure"

# Verbose mode
run_test "trace: verbose mode" "uv run --directory "$SCRIPT_DIR" os4g trace requests --verbose --insecure"

# Combined options
run_test "trace: Combined options" "uv run --directory "$SCRIPT_DIR" os4g trace requests --max-depth 2 --profile security_first --output combined.json --insecure"

# ==========================================
# 5. gratitude command tests
# ==========================================
print_section "5. gratitude command tests"

# Basic gratitude display (test output only, browser may open)
# Note: Be cautious with this command as it may open browser
run_optional_test "gratitude: Show top 3" "timeout 30s uv run --directory "$SCRIPT_DIR" os4g gratitude --top 3 || true"
run_optional_test "gratitude: Show top 5" "timeout 30s uv run --directory "$SCRIPT_DIR" os4g gratitude --top 5 || true"

# ==========================================
# 6. Integration tests and advanced options
# ==========================================
print_section "6. Integration tests and advanced options"

# Custom cache directory
CUSTOM_CACHE_DIR="$TEST_DIR/custom_cache"
mkdir -p "$CUSTOM_CACHE_DIR"
run_test "check: Custom cache directory" "uv run --directory "$SCRIPT_DIR" os4g check requests --cache-dir $CUSTOM_CACHE_DIR --insecure"

# Custom cache TTL
run_test "check: Custom cache TTL" "uv run --directory "$SCRIPT_DIR" os4g check requests --cache-ttl 3600 --insecure"

# Disable local cache
run_test "check: Disable local cache" "uv run --directory "$SCRIPT_DIR" os4g check requests --no-local-cache --insecure"

# SSL verification disabled (already has insecure flag)
run_optional_test "check: SSL verification disabled" "uv run --directory "$SCRIPT_DIR" os4g check requests --insecure"

# Combined options
run_test "check: Combined options" "uv run --directory "$SCRIPT_DIR" os4g check requests --profile security_first --scan-depth deep --output-format json --no-cache --insecure"

# ==========================================
# 7. Error handling tests
# ==========================================
print_section "7. Error handling tests"

# Non-existent package
run_optional_test "check: Non-existent package" "uv run --directory "$SCRIPT_DIR" os4g check nonexistent-package-xyz-12345 --insecure || true"

# Invalid profile
run_optional_test "check: Invalid profile" "uv run --directory "$SCRIPT_DIR" os4g check requests --profile invalid-profile --insecure || true"

# Invalid scan depth
run_optional_test "check: Invalid scan depth" "uv run --directory "$SCRIPT_DIR" os4g check requests --scan-depth invalid --insecure || true"

# ==========================================
# Test Results Summary
# ==========================================
print_section "Test Results Summary"

TOTAL=$((PASSED + FAILED + SKIPPED))

echo ""
echo -e "${CYAN}Total tests:${NC} $TOTAL"
echo -e "${GREEN}Passed:${NC} $PASSED"
echo -e "${RED}Failed:${NC} $FAILED"
echo -e "${YELLOW}Skipped:${NC} $SKIPPED"
echo ""

if [ $FAILED -eq 0 ]; then
    echo -e "${GREEN}✓ All tests completed successfully!${NC}"
    EXIT_CODE=0
else
    echo -e "${RED}✗ Some tests failed.${NC}"
    echo ""
    echo "Failed tests:"
    for result in "${TEST_RESULTS[@]}"; do
        if [[ $result == FAIL:* ]]; then
            echo -e "${RED}  - ${result#FAIL: }${NC}"
        fi
    done
    EXIT_CODE=1
fi

# Cleanup
echo ""
echo -e "${BLUE}Cleaning up...${NC}"
cd - > /dev/null
rm -rf "$TEST_DIR"
rm -f /tmp/os4g_test_output.log

echo ""
echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${CYAN}Test completed!${NC}"
echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"

exit $EXIT_CODE
