# Scripts Directory

## Language and Coding Standards
- **Communication**: Always talk in Thai when interacting with users.
- **Code & Technical Assets**: All code, comments, documentation, and technical definitions must be in English.

This directory contains utility scripts for the ABTPro i18n project.

## Available Scripts

### export-docs-to-wiki.sh

Export all project documentation to the GitHub Wiki.

**Usage:**
```bash
./scripts/export-docs-to-wiki.sh
```

**What it does:**
- Clones the GitHub Wiki repository
- Copies all documentation files from `docs/` and `tools/` directories
- Converts file paths to wiki-compatible page names
- Creates a Home page with navigation links
- Creates a sidebar for easy navigation
- Commits and pushes changes to the wiki

**Prerequisites:**
- The GitHub Wiki must be initialized (create at least one page on GitHub)
- Git credentials with push access to the wiki repository

**Note:** The script creates a temporary directory `tmp/ABTPi18n.wiki/` which is automatically cleaned up after execution.

### generate_prisma.sh

Generate Prisma Python client from schema.

**Usage:**
```bash
./scripts/generate_prisma.sh [schema_path]
```

**Arguments:**
- `schema_path` (optional): Path to the Prisma schema file. Defaults to `/app/prisma/schema.prisma`

**What it does:**
- Validates that the schema file exists
- Generates the Prisma Python client
- Reports success or failure

### sync_drive_assets.sh

Sync Google Drive assets and preview integration.

**Usage:**
```bash
./scripts/sync_drive_assets.sh <FOLDER_URL_OR_ID> [assets_dir] [map_config]
```

**Arguments:**
- `FOLDER_URL_OR_ID`: Google Drive folder URL or ID (required)
- `assets_dir`: Output directory for assets (default: `external/drive_assets`)
- `map_config`: Path to mapping configuration (default: `configs/drive_assets.map.yaml`)

**What it does:**
- Downloads assets from Google Drive
- Previews integration with dry-run mode
- Provides instructions for actual integration

**Example:**
```bash
./scripts/sync_drive_assets.sh 'https://drive.google.com/drive/folders/1ABC123?usp=sharing'
./scripts/sync_drive_assets.sh '1ABC123'
```

## Script Conventions

All scripts in this directory follow these conventions:

1. **Shebang**: Use `#!/bin/bash` or `#!/usr/bin/env bash`
2. **Error Handling**: Set `set -e` to exit on errors
3. **Headers**: Include project header with version and author information
4. **Documentation**: Include usage instructions in comments
5. **Output**: Use clear, colored output for better readability
6. **Cleanup**: Clean up temporary files/directories after execution

## Contributing

When adding new scripts:

1. Make the script executable: `chmod +x scripts/your-script.sh`
2. Add appropriate error handling
3. Include usage instructions
4. Update this README with script documentation
5. Test the script thoroughly before committing

### integrate_ecc_repo.sh

Integrate the Everything-Claude-Code (ECC) repository as a local external dependency.

**Usage:**
```bash
./scripts/integrate_ecc_repo.sh
```

**Environment variables:**
- `ECC_REPO_URL`: Git URL to clone/pull (default: `git@github.com:cvsz/everything-claude-code.git`)
- `ECC_TARGET_DIR`: Target directory (default: `external/everything-claude-code`)

**What it does:**
- Clones ECC into `external/everything-claude-code` when missing
- Runs `git pull --ff-only` if the repo is already present
