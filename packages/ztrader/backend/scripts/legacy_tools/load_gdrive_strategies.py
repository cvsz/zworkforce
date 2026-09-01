#!/usr/bin/env python3
"""// ZeaZDev [Google Drive Strategy Loader CLI] //
// Project: Auto Bot Trader i18n //
// Version: 1.0.0 //
// Author: ZeaZDev Meta-Intelligence (Generated) //
// --- DO NOT EDIT HEADER --- //"""

import argparse
import sys
from pathlib import Path

# Add backend to Python path
sys.path.insert(0, str(Path(__file__).parent.parent / "apps" / "backend"))

from src.services.gdrive_loader import (
    GoogleDriveLoader,
)


def main():
    parser = argparse.ArgumentParser(
        description="Load TradingView strategies from Google Drive"
    )
    parser.add_argument("url", help="Google Drive folder URL")
    parser.add_argument(
        "-o", "--output", help="Output directory for downloaded files", default=None
    )
    parser.add_argument(
        "-c",
        "--clear-cache",
        help="Clear download cache before downloading",
        action="store_true",
    )
    parser.add_argument("-v", "--verbose", help="Verbose output", action="store_true")

    args = parser.parse_args()

    try:
        loader = GoogleDriveLoader()

        if args.clear_cache:
            print("Clearing cache...")
            loader.clear_cache()

        print(f"Downloading from: {args.url}")
        print("-" * 60)

        # Download folder
        folder_path = loader.download_folder(
            args.url, args.output, quiet=not args.verbose
        )
        print(f"✓ Downloaded to: {folder_path}")

        # Load configurations
        configs = loader.load_all_configs(folder_path)
        print(f"✓ Loaded {len(configs)} strategy configurations")
        print("-" * 60)

        # Display summary
        for i, config in enumerate(configs, 1):
            print(f"\n{i}. {config.get('name', 'Unnamed Strategy')}")
            print(f"   Description: {config.get('description', 'N/A')}")
            print(f"   Type: {config.get('type', 'N/A')}")
            print(f"   Source: {config.get('_source_file', 'N/A')}")

            if "symbols" in config:
                symbols_preview = ", ".join(config["symbols"][:3])
                if len(config["symbols"]) > 3:
                    symbols_preview = symbols_preview + "..."
                print(f"   Symbols: {symbols_preview}")

            if "parameters" in config:
                print(f"   Parameters: {len(config['parameters'])} defined")

        print("\n" + "=" * 60)
        success_msg = (
            f"✓ Successfully loaded {len(configs)} strategies from Google Drive"
        )
        print(success_msg)

    except Exception as e:
        print(f"✗ Error: {str(e)}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
