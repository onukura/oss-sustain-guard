#!/bin/bash
# release.sh - OSS Sustain Guard release automation script
# Usage: ./release.sh <version>
# Example: ./release.sh 0.15.0

set -e

# Color output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function definitions
log_info() {
    echo -e "${BLUE}ℹ️  $1${NC}"
}

log_success() {
    echo -e "${GREEN}✅ $1${NC}"
}

log_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

log_error() {
    echo -e "${RED}❌ $1${NC}"
}

# Version validation
if [ -z "$1" ]; then
    log_error "Version number required"
    echo "Usage: ./release.sh <version>"
    echo "Example: ./release.sh 0.15.0"
    exit 1
fi

VERSION=$1

# Semantic versioning validation
if ! [[ $VERSION =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
    log_error "Invalid version format: $VERSION"
    echo "Correct format: X.Y.Z (e.g., 0.15.0)"
    exit 1
fi

log_info "Releasing OSS Sustain Guard v${VERSION}"

# Step 1: Verify local environment
log_info "Step 1: Verifying local environment"
if ! git status --porcelain | grep -q ""; then
    log_info "  Checking for uncommitted changes"
    git status --porcelain | head -10
    log_warning "  Found uncommitted changes"
    read -p "  Continue anyway? (y/n) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        log_error "Cancelled"
        exit 1
    fi
fi

# Step 2: Run tests
log_info "Step 2: Running tests"
if ! make test > /dev/null 2>&1; then
    log_error "Tests failed"
    make test
    exit 1
fi
log_success "Tests passed"

# Step 3: Run linter
log_info "Step 3: Running code quality checks"
if ! make lint > /dev/null 2>&1; then
    log_error "Linting failed"
    make lint
    exit 1
fi
log_success "Linting passed"

# Step 4: Build documentation
log_info "Step 4: Building documentation"
if ! make doc-build > /dev/null 2>&1; then
    log_error "Documentation build failed"
    make doc-build
    exit 1
fi
log_success "Documentation build succeeded"

# Step 5: Update pyproject.toml
log_info "Step 5: Updating version in pyproject.toml"
sed -i.bak "s/^version = .*/version = \"${VERSION}\"/" pyproject.toml
rm pyproject.toml.bak
log_success "Version updated to ${VERSION}"

# Step 6: Update CHANGELOG
log_info "Step 6: Updating CHANGELOG.md"
TODAY=$(date +%Y-%m-%d)
CHANGELOG_ENTRY="## v${VERSION} - ${TODAY}

- Added: description of new features
- Fixed: description of bug fixes
- Improved: description of improvements

"

# Insert new entry at the top of CHANGELOG
sed -i.bak "/^## v[0-9]/i\\
$CHANGELOG_ENTRY
" CHANGELOG.md
rm CHANGELOG.md.bak
log_warning "CHANGELOG.md updated (please add descriptions manually)"

# Prompt user to edit CHANGELOG
echo ""
log_info "Please edit CHANGELOG.md to add change descriptions"
read -p "Done editing? (y/n) " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    log_error "Cancelled"
    git checkout pyproject.toml CHANGELOG.md
    exit 1
fi

# Step 7: Commit changes
log_info "Step 7: Committing changes"
git add pyproject.toml CHANGELOG.md
git commit -m "chore: release version ${VERSION}"
log_success "Commit created"

# Step 8: Create Git tag
log_info "Step 8: Creating Git tag"
git tag -s -m "Release version ${VERSION}" "v${VERSION}"
log_success "Tag v${VERSION} created"

# Step 9: Push to remote
log_info "Step 9: Pushing changes and tag to remote"
log_warning "This will start the automated release pipeline"
read -p "Continue? (y/n) " -n 1 -r
echo

if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    log_warning "Cancelled"
    log_info "To push manually:"
    echo "  git push origin main"
    echo "  git push origin v${VERSION}"
    exit 0
fi

git push origin main
git push origin "v${VERSION}"

log_success "Tag pushed!"
echo ""
log_success "✨ Release v${VERSION} preparation complete!"
echo ""

# Generate GitHub Release Notes Template
log_info "Generating GitHub Release Notes template..."
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "📝 GitHub Release Notes Template"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# Extract changelog for this version
CHANGELOG_SECTION=$(sed -n "/^## v${VERSION}/,/^## v[0-9]/p" CHANGELOG.md | sed '$d' | tail -n +2)

cat << RELEASE_NOTES
## What's New in v${VERSION}

${CHANGELOG_SECTION}

## Installation

\`\`\`bash
pip install oss-sustain-guard==${VERSION}
\`\`\`

## Verification

To verify the installation:

\`\`\`bash
os4g --version
os4g check requests
\`\`\`

## PyPI Package

- **Package**: [oss-sustain-guard on PyPI](https://pypi.org/project/oss-sustain-guard/${VERSION}/)
- **Sigstore Signatures**: Available in GitHub Release assets

## What to Do Now

1. ✅ Monitor GitHub Actions: https://github.com/onukura/oss-sustain-guard/actions
2. ✅ Wait for PyPI publication (5-10 minutes)
3. ✅ Copy release notes above to GitHub Releases page
4. ✅ Verify installation: \`pip install oss-sustain-guard==${VERSION}\`
5. ✅ Test functionality: \`os4g check requests\`

RELEASE_NOTES

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
log_info "Copy the template above to: https://github.com/onukura/oss-sustain-guard/releases/tag/v${VERSION}"
echo ""
log_info "Next steps:"
echo "  1. Monitor GitHub Actions progress: https://github.com/onukura/oss-sustain-guard/actions"
echo "  2. Wait for PyPI publication (5-10 minutes)"
echo "  3. Check GitHub Releases page for new release"
