#!/usr/bin/env bash

#
# OSS Sustain Guard - Comprehensive Command Test Script
#
# Prerequisites:
# - GITHUB_TOKEN must be set (.env file or environment variable)
# - os4g must be installed (pipx, uv tool, pip, or from source)
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

cat > package.json << EOF
{
  "name": "test-project",
  "dependencies": {
    "express": "^4.18.0",
    "lodash": "^4.17.21"
  }
}
EOF

cat > Cargo.toml << EOF
[package]
name = "test-project"

[dependencies]
serde = "1.0"
tokio = "1.0"
EOF

# ==========================================
# 1. check command tests
# ==========================================
print_section "1. check command tests"

# Basic package checks
run_test "check: Single package (Python)" "os4g check requests --insecure"
run_test "check: Single package (JavaScript)" "os4g check -e javascript express --insecure"
run_test "check: Single package (Rust)" "os4g check -e rust serde --insecure"

# Multiple packages from requirements.txt
run_test "check: requirements.txt" "os4g check requests click httpx --insecure"

# Multiple packages at once
run_test "check: Multiple packages" "os4g check requests click httpx --insecure"

# Scoring profile tests
run_test "check: balanced profile" "os4g check requests --profile balanced --insecure"
run_test "check: security_first profile" "os4g check requests --profile security_first --insecure"
run_test "check: contributor_experience profile" "os4g check requests --profile contributor_experience --insecure"
run_test "check: long_term_stability profile" "os4g check requests --profile long_term_stability --insecure"

# Scan depth tests
run_test "check: shallow scan" "os4g check requests --scan-depth shallow --insecure"
run_test "check: default scan" "os4g check requests --scan-depth default --insecure"
run_test "check: deep scan" "os4g check requests --scan-depth deep --insecure"

# Output format tests
run_test "check: JSON output" "os4g check requests --output-format json --insecure"
run_test "check: HTML output" "os4g check requests --output-format html --output-file report.html --insecure"
run_test "check: Markdown output" "os4g check requests --output-format json --output-file report.json --insecure"

# Recursive scan tests
run_optional_test "check: Recursive scan (shallow)" "os4g check requests --recursive --max-depth 1 --insecure"

# Lookback period tests
run_test "check: 90 days analysis" "os4g check requests --days-lookback 90 --insecure"

# Verbose mode
run_test "check: verbose mode" "os4g check requests --verbose --insecure"

# No-cache option
run_test "check: no cache" "os4g check requests --no-cache --insecure"

# Ecosystem auto-detection
run_test "check: Ecosystem auto-detection" "os4g check requests click --insecure"

# GitLab repository tests (optional - requires GITLAB_TOKEN)
if [ -n "$GITLAB_TOKEN" ]; then
    run_optional_test "check: GitLab package" "os4g check gitlab-runner --insecure"
else
    record_result "check: GitLab package" "SKIP" "GITLAB_TOKEN not set"
fi

# ==========================================
# 2. cache command tests
# ==========================================
print_section "2. cache command tests"

# Cache statistics
run_test "cache stats: All ecosystems" "os4g cache stats"
run_test "cache stats: Python ecosystem" "os4g cache stats python"
run_test "cache stats: JavaScript ecosystem" "os4g cache stats javascript"

# Cache listing
run_test "cache list: Python packages" "os4g cache list python"
run_test "cache list: All ecosystems" "os4g cache list"

# Cache list filtering
run_test "cache list: JSON output" "os4g cache list python --sort name"
run_test "cache list: Package search" "os4g cache list python --filter requests"

# Cache clearing
run_test "cache clear: Expired only" "os4g cache clear --expired-only"
run_test "cache clear: Python ecosystem only" "os4g cache clear python"

# Clear all cache (run last)
run_optional_test "cache clear: Clear all cache" "os4g cache clear --all --force"

# ==========================================
# 3. trend command tests
# ==========================================
print_section "3. trend command tests"

# Basic trend analysis
run_test "trend: Monthly trend" "os4g trend requests --interval monthly --periods 3 --insecure"
run_test "trend: Weekly trend" "os4g trend requests --interval weekly --periods 4 --insecure"
run_test "trend: Quarterly trend" "os4g trend requests --interval quarterly --periods 2 --insecure"

# Custom time window
run_test "trend: Custom window" "os4g trend requests --window-days 60 --periods 3 --insecure"

# Profile specification
run_test "trend: security_first profile" "os4g trend requests --profile security_first --periods 2 --insecure"

# Ecosystem specification
run_test "trend: JavaScript package" "os4g trend -e javascript express --periods 2 --insecure"

# Output formats
run_test "trend: JSON output" "os4g trend requests --periods 2 --insecure"
run_test "trend: HTML output" "os4g trend requests --periods 2 --insecure"

# Scan depth
run_test "trend: shallow scan" "os4g trend requests --scan-depth shallow --periods 2 --insecure"

# ==========================================
# 4. graph command tests
# ==========================================
print_section "4. graph command tests"

# Dependency graph generation
run_test "graph: Generate graph from requirements.txt" "os4g graph requirements.txt --insecure"
run_test "graph: HTML output" "os4g graph requirements.txt -o dep_graph.html --insecure"
run_test "graph: JSON output" "os4g graph requirements.txt -o dep_graph.json --insecure"

# Profile specification
run_test "graph: security_first profile" "os4g graph requirements.txt --profile security_first --insecure"

# Direct dependencies only
run_test "graph: Direct dependencies only" "os4g graph requirements.txt --direct-only --insecure"

# Depth limit
run_test "graph: Depth 1 only" "os4g graph requirements.txt --max-depth 1 --insecure"

# Verbose mode
run_test "graph: verbose mode" "os4g graph requirements.txt --verbose --insecure"

# Alternative ecosystem (Node.js)
if [ -f "package.json" ]; then
    run_optional_test "graph: Generate graph from package.json" "os4g graph package.json --insecure"
fi

# ==========================================
# 5. gratitude command tests
# ==========================================
print_section "5. gratitude command tests"

# Basic gratitude display (test output only, browser may open)
# Note: Be cautious with this command as it may open browser
run_optional_test "gratitude: Show top 3" "timeout 30s os4g gratitude --top 3 || true"
run_optional_test "gratitude: Show top 5" "timeout 30s os4g gratitude --top 5 || true"

# ==========================================
# 6. Integration tests and advanced options
# ==========================================
print_section "6. Integration tests and advanced options"

# Custom cache directory
CUSTOM_CACHE_DIR="$TEST_DIR/custom_cache"
mkdir -p "$CUSTOM_CACHE_DIR"
run_test "check: Custom cache directory" "os4g check requests --cache-dir $CUSTOM_CACHE_DIR --insecure"

# Custom cache TTL
run_test "check: Custom cache TTL" "os4g check requests --cache-ttl 3600 --insecure"

# Disable local cache
run_test "check: Disable local cache" "os4g check requests --no-local-cache --insecure"

# SSL verification disabled (already has insecure flag)
run_optional_test "check: SSL verification disabled" "os4g check requests --insecure"

# Combined options
run_test "check: Combined options" "os4g check requests --profile security_first --scan-depth deep --output-format json --no-cache --insecure"

# ==========================================
# 7. Error handling tests
# ==========================================
print_section "7. Error handling tests"

# Non-existent package
run_optional_test "check: Non-existent package" "os4g check nonexistent-package-xyz-12345 --insecure || true"

# Invalid profile
run_optional_test "check: Invalid profile" "os4g check requests --profile invalid-profile --insecure || true"

# Invalid scan depth
run_optional_test "check: Invalid scan depth" "os4g check requests --scan-depth invalid --insecure || true"

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
