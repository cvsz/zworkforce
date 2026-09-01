#!/bin/bash
# Release Script - Creates and pushes a new version tag
# Usage: ./release.sh <version>
# Example: ./release.sh 1.0.0

set -e

if [ -z "$1" ]; then
    echo "Error: Version number required"
    echo "Usage: ./release.sh <version>"
    echo "Example: ./release.sh 1.0.0"
    exit 1
fi

VERSION=$1
TAG="v${VERSION}"

# Verify we're on main branch
CURRENT_BRANCH=$(git rev-parse --abbrev-ref HEAD)
if [ "$CURRENT_BRANCH" != "main" ]; then
    echo "Warning: Not on main branch (current: $CURRENT_BRANCH)"
    read -p "Continue anyway? (y/N) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

# Check if CHANGELOG.md has been updated
if ! grep -q "\[$VERSION\]" CHANGELOG.md; then
    echo "Warning: CHANGELOG.md doesn't contain version [$VERSION]"
    read -p "Continue anyway? (y/N) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

# Ensure working directory is clean
if ! git diff-index --quiet HEAD --; then
    echo "Error: Working directory is not clean"
    echo "Please commit or stash your changes first"
    exit 1
fi

# Create annotated tag
echo "Creating tag $TAG..."
git tag -a "$TAG" -m "Release version $VERSION"

# Show the tag
git show "$TAG" --no-patch

# Push the tag
echo ""
read -p "Push tag $TAG to origin? (y/N) " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo "Pushing tag to origin..."
    git push origin "$TAG"
    echo ""
    echo "✅ Tag pushed successfully!"
    echo "🚀 GitHub Actions workflow will now:"
    echo "   1. Create a GitHub release"
    echo "   2. Build Docker images"
    echo "   3. Publish to GitHub Container Registry"
    echo ""
    echo "Monitor the workflow at:"
    echo "https://github.com/$(git remote get-url origin | sed 's/.*github.com[:/]\(.*\)\.git/\1/')/actions"
else
    echo "Tag created locally but not pushed"
    echo "To push manually: git push origin $TAG"
fi
