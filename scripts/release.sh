#!/bin/bash

# Ansible Collection Release Script
# Usage: ./scripts/release.sh [major|minor|patch|version]
# Example: ./scripts/release.sh minor
# Example: ./scripts/release.sh 1.2.3

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
COLLECTION_ROOT="$(dirname "$SCRIPT_DIR")"
GALAXY_FILE="$COLLECTION_ROOT/galaxy.yml"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to print colored output
log() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

error() {
    echo -e "${RED}[ERROR]${NC} $1"
    exit 1
}

success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

# Check if we're in a git repository
if ! git rev-parse --git-dir > /dev/null 2>&1; then
    error "Not in a git repository"
fi

# Check if working directory is clean
if [[ -n $(git status --porcelain) ]]; then
    error "Working directory is not clean. Please commit or stash changes first."
fi

# Check if galaxy.yml exists
if [[ ! -f "$GALAXY_FILE" ]]; then
    error "galaxy.yml not found at $GALAXY_FILE"
fi

# Get current version from galaxy.yml
CURRENT_VERSION=$(grep "^version:" "$GALAXY_FILE" | sed 's/version: //')
log "Current version: $CURRENT_VERSION"

# Function to increment version
increment_version() {
    local version=$1
    local increment_type=$2
    
    IFS='.' read -ra VERSION_PARTS <<< "$version"
    local major=${VERSION_PARTS[0]}
    local minor=${VERSION_PARTS[1]}
    local patch=${VERSION_PARTS[2]}
    
    case $increment_type in
        "major")
            major=$((major + 1))
            minor=0
            patch=0
            ;;
        "minor")
            minor=$((minor + 1))
            patch=0
            ;;
        "patch")
            patch=$((patch + 1))
            ;;
        *)
            error "Invalid increment type: $increment_type"
            ;;
    esac
    
    echo "$major.$minor.$patch"
}

# Function to validate semantic version
validate_version() {
    local version=$1
    if [[ ! $version =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
        error "Invalid version format: $version. Must be X.Y.Z"
    fi
}

# Determine new version
if [[ $# -eq 0 ]]; then
    echo "Usage: $0 [major|minor|patch|X.Y.Z]"
    echo ""
    echo "Current version: $CURRENT_VERSION"
    echo ""
    echo "Options:"
    echo "  major  - Increment major version (X.0.0)"
    echo "  minor  - Increment minor version (0.X.0)"
    echo "  patch  - Increment patch version (0.0.X)"
    echo "  X.Y.Z  - Set specific version"
    exit 1
fi

INCREMENT_TYPE=$1

case $INCREMENT_TYPE in
    "major"|"minor"|"patch")
        NEW_VERSION=$(increment_version "$CURRENT_VERSION" "$INCREMENT_TYPE")
        ;;
    *)
        NEW_VERSION=$INCREMENT_TYPE
        validate_version "$NEW_VERSION"
        ;;
esac

log "New version will be: $NEW_VERSION"

# Check if tag already exists
if git tag -l | grep -q "^v$NEW_VERSION$"; then
    error "Tag v$NEW_VERSION already exists"
fi

# Confirm before proceeding
read -p "Continue with release v$NEW_VERSION? (y/N): " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    warn "Release cancelled"
    exit 0
fi

# Update galaxy.yml
log "Updating galaxy.yml with version $NEW_VERSION"
if command -v gsed > /dev/null; then
    # macOS with GNU sed
    gsed -i "s/^version:.*/version: $NEW_VERSION/" "$GALAXY_FILE"
elif sed --version 2>/dev/null | grep -q GNU; then
    # GNU sed
    sed -i "s/^version:.*/version: $NEW_VERSION/" "$GALAXY_FILE"
else
    # BSD sed (macOS default)
    sed -i '' "s/^version:.*/version: $NEW_VERSION/" "$GALAXY_FILE"
fi

# Verify the change
UPDATED_VERSION=$(grep "^version:" "$GALAXY_FILE" | sed 's/version: //')
if [[ "$UPDATED_VERSION" != "$NEW_VERSION" ]]; then
    error "Failed to update version in galaxy.yml"
fi

# Stage the galaxy.yml change
log "Staging galaxy.yml changes"
git add "$GALAXY_FILE"

# Commit the version update
log "Committing version update"
git commit -m "Bump version to $NEW_VERSION"

# Create and push tag
log "Creating tag v$NEW_VERSION"
git tag "v$NEW_VERSION"

log "Pushing changes and tag to origin"
git push origin main
git push origin "v$NEW_VERSION"

success "Release v$NEW_VERSION completed successfully!"
log "GitHub Actions will now build and create the release automatically"
log "Monitor the progress at: https://github.com/$(git config --get remote.origin.url | sed 's/.*github.com[:/]\(.*\)\.git/\1/')/actions"