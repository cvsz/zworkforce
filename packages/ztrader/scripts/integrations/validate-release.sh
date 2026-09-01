#!/bin/bash
# Validation script for release workflow
# This script validates the release setup without actually creating a release

set -e

echo "🔍 Validating Release Setup..."
echo ""

# Check for required files
echo "✓ Checking required files..."
required_files=(
    ".github/workflows/release.yml"
    "CHANGELOG.md"
    "docs/guides/RELEASE.md"
    "release.sh"
)

for file in "${required_files[@]}"; do
    if [ -f "$file" ]; then
        echo "  ✓ $file exists"
    else
        echo "  ✗ $file missing"
        exit 1
    fi
done

echo ""
echo "✓ Checking workflow syntax..."
if command -v yamllint &> /dev/null; then
    # yamllint considers line-length as "error" but it's just a style issue
    # Only fail on actual syntax errors
    if python3 -c "import yaml; yaml.safe_load(open('.github/workflows/release.yml'))" 2>/dev/null; then
        echo "  ✓ Workflow YAML syntax is valid"
    else
        echo "  ✗ Workflow has YAML syntax errors"
        python3 -c "import yaml; yaml.safe_load(open('.github/workflows/release.yml'))"
        exit 1
    fi
else
    echo "  ⚠ YAML parser not available, skipping syntax check"
fi

echo ""
echo "✓ Checking Dockerfiles..."
dockerfiles=(
    "apps/frontend/Dockerfile"
    "apps/backend/Dockerfile"
)

for dockerfile in "${dockerfiles[@]}"; do
    if [ -f "$dockerfile" ]; then
        echo "  ✓ $dockerfile exists"
    else
        echo "  ✗ $dockerfile missing"
        exit 1
    fi
done

echo ""
echo "✓ Checking CHANGELOG.md format..."
if grep -q "## \[1.0.0\]" CHANGELOG.md; then
    echo "  ✓ CHANGELOG.md contains version 1.0.0"
else
    echo "  ✗ CHANGELOG.md missing version 1.0.0"
    exit 1
fi

echo ""
echo "✓ Checking release script..."
if [ -x "release.sh" ]; then
    echo "  ✓ release.sh is executable"
else
    echo "  ✗ release.sh is not executable"
    exit 1
fi

echo ""
echo "✓ Checking git status..."
if [ -d ".git" ]; then
    echo "  ✓ Git repository initialized"
    CURRENT_BRANCH=$(git rev-parse --abbrev-ref HEAD)
    echo "  ℹ Current branch: $CURRENT_BRANCH"
else
    echo "  ✗ Not a git repository"
    exit 1
fi

echo ""
echo "✅ All validations passed!"
echo ""
echo "📋 Next steps to create a release:"
echo "  1. Merge this PR to main branch"
echo "  2. Checkout main branch: git checkout main"
echo "  3. Pull latest changes: git pull origin main"
echo "  4. Run release script: ./release.sh 1.0.0"
echo ""
echo "The GitHub Actions workflow will then:"
echo "  • Create a GitHub release"
echo "  • Build Docker images (frontend, backend)"
echo "  • Publish images to ghcr.io"
