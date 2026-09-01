#!/bin/bash

# Export Documentation to GitHub Wiki
# This script exports all documentation from the repository to the GitHub Wiki
#
# Environment Variables:
#   COPY_ASSETS - Set to 1 to copy image assets referenced in docs (default: 0)
#   DRY_RUN     - Set to 1 to preview operations without cloning/pushing (default: 0)
#
# Usage:
#   ./scripts/export-docs-to-wiki.sh              # Normal operation
#   DRY_RUN=1 ./scripts/export-docs-to-wiki.sh   # Preview mode
#   COPY_ASSETS=1 ./scripts/export-docs-to-wiki.sh # Copy images
#
# Testing:
#   - On macOS: Run script to verify BSD sed compatibility
#   - On Linux: Run script to verify GNU sed compatibility
#   - Test COPY_ASSETS=1 with docs containing image references
#   - Test collision detection by creating conflicting file paths

set -e

REPO_NAME="ABTPi18n"
WIKI_URL="https://github.com/ZeaZDev/${REPO_NAME}.wiki.git"
WIKI_DIR="tmp/${REPO_NAME}.wiki"
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

# Environment variables with defaults
COPY_ASSETS="${COPY_ASSETS:-0}"
DRY_RUN="${DRY_RUN:-0}"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Cross-platform sed in-place editing
# Usage: inplace_sed 's/pattern/replacement/g' file
inplace_sed() {
    local pattern="$1"
    local file="$2"
    
    # Create a temporary file
    local temp_file="${file}.tmp.$$"
    
    # Apply sed and write to temp file
    if sed "$pattern" "$file" > "$temp_file"; then
        mv "$temp_file" "$file"
    else
        rm -f "$temp_file"
        return 1
    fi
}

# Function to convert file path to wiki page name
# Example: docs/guides/SECURITY.md -> guides-SECURITY
convert_to_wiki_name() {
    local filepath="$1"
    # Remove .md extension
    local name="${filepath%.md}"
    # Remove docs/ prefix
    name="${name#docs/}"
    # Remove tools/ prefix
    name="${name#tools/}"
    # Replace / with -
    name="${name//\//-}"
    # Convert to Title Case (capitalize first letter of each word)
    # Keep the original case for acronyms like README, API, etc.
    echo "$name"
}

# Detect naming collisions before processing
# Exit with error if multiple files map to the same wiki name
detect_collisions() {
    local -A wiki_names
    local has_collision=0
    
    echo -e "${GREEN}Checking for naming collisions...${NC}"
    
    # Check all markdown files in docs and tools
    while IFS= read -r file; do
        relative_path="${file#"$REPO_ROOT"/}"
        wiki_name="$(convert_to_wiki_name "$relative_path")"
        
        if [ -n "${wiki_names[$wiki_name]}" ]; then
            echo -e "${RED}ERROR: Naming collision detected!${NC}"
            echo -e "  Wiki name: ${wiki_name}.md"
            echo -e "  File 1: ${wiki_names[$wiki_name]}"
            echo -e "  File 2: ${relative_path}"
            has_collision=1
        else
            wiki_names[$wiki_name]="$relative_path"
        fi
    done < <(find "$REPO_ROOT/docs" "$REPO_ROOT/tools" -name "*.md" -type f 2>/dev/null)
    
    if [ "$has_collision" -eq 1 ]; then
        echo -e "${RED}Cannot proceed due to naming collisions.${NC}"
        echo -e "${YELLOW}Please rename files to avoid conflicts.${NC}"
        exit 1
    fi
    
    echo -e "${GREEN}✓ No naming collisions detected${NC}"
}

# Rewrite markdown links safely - only transform docs/tools internal links
# Preserves external URLs and non-markdown links
# Usage: rewrite_markdown_links file
rewrite_markdown_links() {
    local file="$1"
    local temp_file="${file}.rewrite.$$"
    
    # Use perl for more precise regex replacement
    # Only rewrite markdown links pointing to docs/ or tools/ .md files
    if perl -pe '
        # Match markdown links [text](docs/path/file.md) or [text](tools/path/file.md)
        s{\]\((docs|tools)/([^)]+\.md)\)}{
            my $prefix = $1;
            my $path = $2;
            # Remove .md extension
            $path =~ s/\.md$//;
            # Replace / with -
            $path =~ s{/}{-}g;
            "](" . $path . ")";
        }ge;
    ' "$file" > "$temp_file"; then
        mv "$temp_file" "$file"
    else
        rm -f "$temp_file"
        return 1
    fi
}

# Collect image asset references from a markdown file
# Returns list of image paths (relative to repo root)
# Usage: collect_assets file
collect_assets() {
    local file="$1"
    
    # Find image references: ![alt](docs/path/image.ext) or ![alt](tools/path/image.ext)
    # Use -E for extended regex
    grep -oE '!\[[^]]*\]\((docs|tools)/[^)]*\.(png|jpg|jpeg|gif|svg|webp)\)' "$file" 2>/dev/null | \
        sed 's/!\[[^]]*\](//; s/)$//' || true
}

# Copy assets to wiki repository
# Usage: copy_assets source_file wiki_dir
copy_assets() {
    local source_file="$1"
    local wiki_dir="$2"
    local assets_copied=0
    
    # Collect all asset references
    while IFS= read -r asset_path; do
        [ -z "$asset_path" ] && continue
        
        local full_source="$REPO_ROOT/$asset_path"
        
        if [ ! -f "$full_source" ]; then
            echo -e "${YELLOW}  Warning: Referenced asset not found: $asset_path${NC}"
            continue
        fi
        
        # Preserve directory structure under assets/
        # Example: docs/images/diagram.svg -> assets/docs/images/diagram.svg
        local dest_path="assets/$asset_path"
        local dest_dir
        dest_dir="$(dirname "$dest_path")"
        
        if [ "$DRY_RUN" -eq 1 ]; then
            echo "  [DRY RUN] Would copy: $asset_path -> $dest_path"
        else
            mkdir -p "$wiki_dir/$dest_dir"
            cp "$full_source" "$wiki_dir/$dest_path"
            echo "  Copied asset: $asset_path -> $dest_path"
        fi
        
        assets_copied=$((assets_copied + 1))
    done < <(collect_assets "$source_file")
    
    return 0
}

# Rewrite image paths in markdown to point to assets/ directory
# Usage: rewrite_asset_paths file
rewrite_asset_paths() {
    local file="$1"
    local temp_file="${file}.assets.$$"
    
    # Rewrite image paths: ![alt](docs/path/img.ext) -> ![alt](assets/docs/path/img.ext)
    if perl -pe '
        s{!\[([^]]*)\]\((docs|tools)/([^)]+\.(png|jpg|jpeg|gif|svg|webp))\)}{
            "![" . $1 . "](assets/" . $2 . "/" . $3 . ")";
        }ge;
    ' "$file" > "$temp_file"; then
        mv "$temp_file" "$file"
    else
        rm -f "$temp_file"
        return 1
    fi
}

echo -e "${GREEN}=== Exporting Documentation to Wiki ===${NC}"

if [ "$DRY_RUN" -eq 1 ]; then
    echo -e "${YELLOW}DRY RUN MODE - No changes will be made${NC}"
fi

if [ "$COPY_ASSETS" -eq 1 ]; then
    echo -e "${GREEN}Asset copying enabled${NC}"
fi

# Detect naming collisions before proceeding
detect_collisions

# Clean up old wiki clone if it exists
if [ -d "$WIKI_DIR" ]; then
    echo -e "${YELLOW}Removing old wiki clone...${NC}"
    if [ "$DRY_RUN" -eq 1 ]; then
        echo "[DRY RUN] Would remove: $WIKI_DIR"
    else
        rm -rf "$WIKI_DIR"
    fi
fi

# Create tmp directory if it doesn't exist
if [ "$DRY_RUN" -eq 1 ]; then
    echo "[DRY RUN] Would create tmp directory"
else
    mkdir -p tmp
fi

# Clone the wiki repository
echo -e "${GREEN}Cloning wiki repository...${NC}"
if [ "$DRY_RUN" -eq 1 ]; then
    echo "[DRY RUN] Would clone: $WIKI_URL -> $WIKI_DIR"
    echo -e "${YELLOW}Dry run mode - skipping actual operations${NC}"
    echo ""
    echo "=== Dry Run Summary ==="
    echo ""
    echo "Would process markdown files:"
    find "$REPO_ROOT/docs" "$REPO_ROOT/tools" -name "*.md" -type f 2>/dev/null | while read -r file; do
        relative_path="${file#"$REPO_ROOT"/}"
        wiki_name="$(convert_to_wiki_name "$relative_path")"
        echo "  - $relative_path -> ${wiki_name}.md"
    done
    
    if [ "$COPY_ASSETS" -eq 1 ]; then
        echo ""
        echo "Would copy assets:"
        find "$REPO_ROOT/docs" "$REPO_ROOT/tools" -name "*.md" -type f 2>/dev/null | while read -r file; do
            assets=$(collect_assets "$file")
            if [ -n "$assets" ]; then
                echo "$assets" | while read -r asset; do
                    [ -n "$asset" ] && echo "  - $asset -> assets/$asset"
                done
            fi
        done
    fi
    
    echo ""
    echo "=== End Dry Run ==="
    exit 0
fi

if ! git clone "$WIKI_URL" "$WIKI_DIR" 2>/dev/null; then
    echo -e "${RED}Failed to clone wiki repository.${NC}"
    echo -e "${YELLOW}The wiki might not be initialized yet. Please:${NC}"
    echo "1. Go to https://github.com/ZeaZDev/${REPO_NAME}/wiki"
    echo "2. Click 'Create the first page' to initialize the wiki"
    echo "3. Run this script again"
    exit 1
fi

cd "$WIKI_DIR"

# Function to copy and convert markdown file
copy_doc_file() {
    local src_file="$1"
    local wiki_name
    local dest_file
    
    wiki_name="$(convert_to_wiki_name "$src_file")"
    dest_file="${wiki_name}.md"
    
    echo "  Copying: $src_file -> $dest_file"
    
    # Copy the file
    cp "$REPO_ROOT/$src_file" "$dest_file"
    
    # Rewrite markdown internal links safely
    if ! rewrite_markdown_links "$dest_file"; then
        echo -e "${RED}Error rewriting links in $dest_file${NC}"
        return 1
    fi
    
    # Copy assets if enabled
    if [ "$COPY_ASSETS" -eq 1 ]; then
        copy_assets "$REPO_ROOT/$src_file" "$(pwd)"
        
        # Rewrite asset paths in the destination file
        if ! rewrite_asset_paths "$dest_file"; then
            echo -e "${RED}Error rewriting asset paths in $dest_file${NC}"
            return 1
        fi
    fi
}

# Create Home page with navigation
echo -e "${GREEN}Creating Home page...${NC}"
cat > Home.md << 'EOF'
# ABTPro i18n Wiki

Welcome to the Auto Bot Trader Pro (ABTPro) i18n documentation wiki.

## Quick Navigation

### Getting Started
- [Main README](README) - Project overview and quick start
- [Installation Guide](setup-INSTALLER_PLATFORM_REQUIREMENTS) - Platform requirements
- [GitHub Setup](setup-GITHUB-SETUP) - GitHub configuration
- [Contributing Guide](guides-CONTRIBUTING) - Development setup and workflow

### Core Documentation
- [Security Model](guides-SECURITY) - Encryption and security practices
- [Roadmap](guides-ROADMAP) - Project phases and progress
- [Release Process](guides-RELEASE) - Creating releases

### Integration & Setup
- [TradingView Integration](integrations-TRADINGVIEW_INTEGRATION) - Connect TradingView alerts
- [Google Drive Integration](integration-GOOGLE_DRIVE_INTEGRATION) - Google Drive setup
- [Google Drive Loader Guide](guides-GDRIVE_LOADER_GUIDE) - Using the GDrive loader

### Strategy Development
- [Strategy Guide](strategy-STRATEGY_GUIDE) - Creating trading strategies
- [Strategy Implementation Notes](strategy-STRATEGY_IMPLEMENTATION_NOTES) - Implementation details
- [DR/Failover Strategy](strategy-DR_FAILOVER_STRATEGY) - Disaster recovery

### Tools Documentation
- [Tools README](tools-README) - Tools overview
- [Tools Architecture](tools-ARCHITECTURE) - Architecture documentation
- [Tools Examples](tools-EXAMPLES) - Usage examples
- [Tools Summary](tools-SUMMARY) - Tools summary
- [Screenshot Tool](tools-README_SCREENSHOTS) - Automated screenshot capture

### Phase Documentation

#### Phase 1: Foundation & Security
- [Phase 1 Guide](phases-phase1-PHASE1_GUIDE)
- [Phase 1 Summary](phases-phase1-PHASE1_SUMMARY)
- [Phase 1 Implementation](phases-phase1-PHASE1_IMPLEMENTATION_SUMMARY)

#### Phase 2: Strategy Engine & Risk Management
- [Phase 2 Guide](phases-phase2-PHASE2_GUIDE)
- [Phase 2 Summary](phases-phase2-PHASE2_SUMMARY)
- [Phase 2 Implementation](phases-phase2-PHASE2_IMPLEMENTATION_SUMMARY)

#### Phase 3: i18n Dashboard & Authentication
- [Phase 3 Guide](phases-phase3-PHASE3_GUIDE)
- [Phase 3 Summary](phases-phase3-PHASE3_SUMMARY)
- [Phase 3 Implementation](phases-phase3-PHASE3_IMPLEMENTATION_SUMMARY)

#### Phase 4: Advanced Risk & Monetization
- [Phase 4 Guide](phases-phase4-PHASE4_GUIDE)
- [Phase 4 Summary](phases-phase4-PHASE4_SUMMARY)
- [Phase 4 Implementation](phases-phase4-PHASE4_IMPLEMENTATION_SUMMARY)

#### Phase 5: Compliance & Audit
- [Phase 5 Guide](phases-phase5-PHASE5_GUIDE)
- [Phase 5 Summary](phases-phase5-PHASE5_SUMMARY)
- [Phase 5 Implementation](phases-phase5-PHASE5_IMPLEMENTATION_SUMMARY)
- [Phase 5 Quick Start](phases-phase5-PHASE5_QUICK_START)
- [Phase 5 Migration](phases-phase5-PHASE5_MIGRATION_GUIDE)

#### Phase 6: ML / Intelligence
- [Phase 6 Guide](phases-phase6-PHASE6_GUIDE)
- [Phase 6 Summary](phases-phase6-PHASE6_SUMMARY)
- [Phase 6 Implementation](phases-phase6-PHASE6_IMPLEMENTATION_SUMMARY)
- [Phase 6 Quick Start](phases-phase6-PHASE6_QUICK_START)

### Additional Resources
- [Changelog](CHANGELOG) - Version history
- [TradingView Summary](TRADINGVIEW_SUMMARY) - TradingView integration summary
- [Documentation Index](README-docs) - Complete documentation index

---

**Note:** This wiki is automatically generated from the repository documentation.
To update this wiki, modify the documentation files in the repository and run `scripts/export-docs-to-wiki.sh`.
EOF

# Copy main README
echo -e "${GREEN}Copying main README...${NC}"
cp "$REPO_ROOT/README.md" "README.md"

# Copy CHANGELOG
echo -e "${GREEN}Copying CHANGELOG...${NC}"
cp "$REPO_ROOT/CHANGELOG.md" "CHANGELOG.md"

# Copy all documentation files
echo -e "${GREEN}Copying documentation files...${NC}"

# Find and copy all .md files from docs/ directory
find "$REPO_ROOT/docs" -name "*.md" -type f | while read -r file; do
    relative_path="${file#"$REPO_ROOT"/}"
    copy_doc_file "$relative_path"
done

# Copy tools documentation
echo -e "${GREEN}Copying tools documentation...${NC}"
find "$REPO_ROOT/tools" -name "*.md" -type f | while read -r file; do
    relative_path="${file#"$REPO_ROOT"/}"
    copy_doc_file "$relative_path"
done

# Create a sidebar (if wiki supports it)
echo -e "${GREEN}Creating sidebar...${NC}"
cat > _Sidebar.md << 'EOF'
## Navigation

### Getting Started
- [Home](Home)
- [README](README)
- [Contributing](guides-CONTRIBUTING)

### Guides
- [Security](guides-SECURITY)
- [Roadmap](guides-ROADMAP)
- [Release](guides-RELEASE)

### Setup
- [GitHub Setup](setup-GITHUB-SETUP)
- [Platform Requirements](setup-INSTALLER_PLATFORM_REQUIREMENTS)

### Strategy
- [Strategy Guide](strategy-STRATEGY_GUIDE)
- [DR/Failover](strategy-DR_FAILOVER_STRATEGY)

### Integrations
- [TradingView](integrations-TRADINGVIEW_INTEGRATION)
- [Google Drive](integration-GOOGLE_DRIVE_INTEGRATION)

### Phases
- [Phase 1](phases-phase1-PHASE1_GUIDE)
- [Phase 2](phases-phase2-PHASE2_GUIDE)
- [Phase 3](phases-phase3-PHASE3_GUIDE)
- [Phase 4](phases-phase4-PHASE4_GUIDE)
- [Phase 5](phases-phase5-PHASE5_GUIDE)
- [Phase 6](phases-phase6-PHASE6_GUIDE)
EOF

# Git operations
echo -e "${GREEN}Committing changes to wiki...${NC}"
git add .
if git diff --staged --quiet; then
    echo -e "${YELLOW}No changes to commit${NC}"
else
    git commit -m "Update wiki documentation from repository ($(date '+%Y-%m-%d %H:%M:%S'))"
    echo -e "${GREEN}Pushing changes to wiki...${NC}"
    git push origin master
    echo -e "${GREEN}✓ Wiki updated successfully!${NC}"
fi

# Clean up
cd "$REPO_ROOT"
echo -e "${GREEN}Cleaning up temporary files...${NC}"
rm -rf "$WIKI_DIR"

echo -e "${GREEN}=== Documentation export complete ===${NC}"
echo -e "View the wiki at: https://github.com/ZeaZDev/${REPO_NAME}/wiki"
