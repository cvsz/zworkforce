#!/bin/bash
# // ZeaZDev [Scripts Sync Drive Assets] //
# // Project: Auto Bot Trader i18n //
# // Version: 1.0.0 //
# // Author: ZeaZDev Meta-Intelligence (Generated) //
# // --- DO NOT EDIT HEADER --- //

set -e

# Script to sync Google Drive assets and preview integration
# Usage: ./scripts/sync_drive_assets.sh <FOLDER_URL_OR_ID>

if [ -z "$1" ]; then
    echo "Usage: $0 <FOLDER_URL_OR_ID>"
    echo ""
    echo "Example:"
    echo "  $0 'https://drive.google.com/drive/folders/1ABC123?usp=sharing'"
    echo "  $0 '1ABC123'"
    exit 1
fi

FOLDER_ID="$1"
ASSETS_DIR="${2:-external/drive_assets}"
MAP_CONFIG="${3:-configs/drive_assets.map.yaml}"

echo "=== Syncing Google Drive Assets ==="
echo "Folder: $FOLDER_ID"
echo "Output: $ASSETS_DIR"
echo ""

# Step 1: Download from Google Drive
echo "Step 1: Downloading assets from Google Drive..."
python3 tools/drive_sync.py --folder-id "$FOLDER_ID" --output "$ASSETS_DIR"

if [ $? -ne 0 ]; then
    echo "ERROR: Failed to download assets"
    exit 1
fi

echo ""
echo "Step 2: Previewing integration (dry run)..."
python3 tools/integrate_drive_assets.py --assets-dir "$ASSETS_DIR" --map "$MAP_CONFIG" --dry-run

echo ""
echo "=== Sync Complete ==="
echo ""
echo "To actually integrate the assets into the repository, run:"
echo "  python3 tools/integrate_drive_assets.py --assets-dir '$ASSETS_DIR' --map '$MAP_CONFIG'"
echo ""
echo "To load external strategies in your application:"
echo "  from core.strategy_autoload import load_external_strategies"
echo "  loaded = load_external_strategies()"
