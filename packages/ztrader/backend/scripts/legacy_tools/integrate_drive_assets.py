"""// ZeaZDev [Tools Integrate Drive Assets] //
// Project: Auto Bot Trader i18n //
// Version: 1.0.0 //
// Author: ZeaZDev Meta-Intelligence (Generated) //
// --- DO NOT EDIT HEADER --- //"""

import argparse
import logging
import shutil
import sys
from pathlib import Path
from typing import Any, Dict, List, Tuple

try:
    import yaml
except ImportError:
    print(
        "ERROR: pyyaml is not installed. Please run: pip install pyyaml",
        file=sys.stderr,
    )
    sys.exit(1)

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def load_mapping_config(config_path: str) -> Dict[str, Any]:
    """
    Load YAML mapping configuration.

    Args:
        config_path: Path to YAML configuration file

    Returns:
        Parsed configuration dictionary

    Raises:
        FileNotFoundError: If config file doesn't exist
        yaml.YAMLError: If config file is invalid
    """
    config_file = Path(config_path)

    if not config_file.exists():
        raise FileNotFoundError(f"Mapping config file not found: {config_path}")

    with open(config_file, "r") as f:
        config = yaml.safe_load(f)

    if not config or "rules" not in config:
        raise ValueError("Invalid mapping config: must contain 'rules' key")

    return config


def match_files(assets_dir: Path, patterns: List[str]) -> List[Path]:
    """
    Find files matching glob patterns in assets directory.

    Args:
        assets_dir: Root directory containing assets
        patterns: List of glob patterns (e.g., ["**/*.json", "strategies/**/*.py"])

    Returns:
        List of matching file paths
    """
    matched_files = []

    for pattern in patterns:
        # Use rglob for recursive patterns, glob for non-recursive
        if "**" in pattern:
            matches = list(assets_dir.glob(pattern))
        else:
            matches = list(assets_dir.glob(pattern))

        matched_files.extend([f for f in matches if f.is_file()])

    # Remove duplicates while preserving order
    seen = set()
    unique_files = []
    for f in matched_files:
        if f not in seen:
            seen.add(f)
            unique_files.append(f)

    return unique_files


def compute_destination(
    source_file: Path,
    assets_dir: Path,
    dest_dir: str,
    keep_tree: bool,
    strip_prefix: str,
) -> Path:
    """
    Compute destination path for a source file.

    Args:
        source_file: Source file path
        assets_dir: Root assets directory
        dest_dir: Destination directory in repo
        keep_tree: Whether to preserve directory structure
        strip_prefix: Prefix to strip from source path

    Returns:
        Computed destination path
    """
    dest_base = Path(dest_dir)

    if keep_tree:
        # Preserve directory structure relative to assets_dir
        relative_path = source_file.relative_to(assets_dir)

        # Strip prefix if specified
        if strip_prefix:
            prefix_parts = Path(strip_prefix).parts
            relative_parts = relative_path.parts

            # Remove matching prefix parts
            if relative_parts[: len(prefix_parts)] == prefix_parts:
                relative_path = Path(*relative_parts[len(prefix_parts) :])

        dest_path = dest_base / relative_path
    else:
        # Just use filename
        dest_path = dest_base / source_file.name

    return dest_path


def integrate_assets(
    assets_dir: str, mapping_config: str, dry_run: bool = False
) -> Tuple[int, int]:
    """
    Integrate downloaded assets into repository structure based on mapping config.

    Args:
        assets_dir: Directory containing downloaded assets
        mapping_config: Path to YAML mapping configuration
        dry_run: If True, only show what would be done without copying

    Returns:
        Tuple of (files_processed, files_copied)
    """
    assets_path = Path(assets_dir)

    if not assets_path.exists():
        logger.error(f"Assets directory '{assets_dir}' does not exist")
        return 0, 0

    # Load mapping configuration
    try:
        config = load_mapping_config(mapping_config)
    except Exception as e:
        logger.error(f"Failed to load mapping config: {e}")
        return 0, 0

    rules = config.get("rules", [])
    logger.info(f"Loaded {len(rules)} mapping rules from '{mapping_config}'")

    if dry_run:
        logger.info("DRY RUN MODE - No files will be copied")

    files_processed = 0
    files_copied = 0

    # Process each rule
    for idx, rule in enumerate(rules, 1):
        patterns = rule.get("patterns", [])
        dest_dir = rule.get("dest", "")
        keep_tree = rule.get("keep_tree", True)
        strip_prefix = rule.get("strip_prefix", "")

        if not patterns or not dest_dir:
            logger.warning(f"Rule {idx}: Missing 'patterns' or 'dest', skipping")
            continue

        pattern_info = f"Rule {idx}: Processing patterns {patterns} -> {dest_dir}"
        logger.info(pattern_info)

        # Find matching files
        matched_files = match_files(assets_path, patterns)
        logger.info(f"  Found {len(matched_files)} matching files")

        # Process each matched file
        for source_file in matched_files:
            files_processed += 1

            # Compute destination
            dest_file = compute_destination(
                source_file, assets_path, dest_dir, keep_tree, strip_prefix
            )

            # Log action
            action = "Would copy" if dry_run else "Copying"
            action_line = (
                f"  {action}: {source_file.relative_to(assets_path)} -> {dest_file}"
            )
            logger.info(action_line)

            if not dry_run:
                # Create destination directory
                dest_file.parent.mkdir(parents=True, exist_ok=True)

                # Copy file
                try:
                    shutil.copy2(source_file, dest_file)
                    files_copied += 1
                except Exception as e:
                    logger.error(f"  Failed to copy {source_file}: {e}")

    logger.info(
        "Integration complete: %s files processed, %s files copied",
        files_processed,
        files_copied,
    )

    return files_processed, files_copied


def main():
    """Main entry point for integrate_drive_assets tool."""
    parser = argparse.ArgumentParser(
        description="Integrate Google Drive assets into ABTPi18n repository structure",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Dry run to see what would be done
  python tools/integrate_drive_assets.py --dry-run

  # Actually copy files
  python tools/integrate_drive_assets.py

  # Use custom paths
  python tools/integrate_drive_assets.py --assets-dir external/my_assets \
    --map configs/my_map.yaml

Configuration:
  Edit configs/drive_assets.map.yaml to define mapping rules.
  Each rule specifies glob patterns and destination paths.
        """,
    )

    parser.add_argument(
        "--assets-dir",
        default="external/drive_assets",
        help="Directory containing downloaded assets (default: external/drive_assets)",
    )

    parser.add_argument(
        "--map",
        default="configs/drive_assets.map.yaml",
        help="YAML mapping configuration file (default: configs/drive_assets.map.yaml)",
    )

    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be done without actually copying files",
    )

    parser.add_argument("--verbose", action="store_true", help="Enable verbose logging")

    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    files_processed, files_copied = integrate_assets(
        args.assets_dir, args.map, args.dry_run
    )

    if files_processed > 0:
        logger.info("Integration completed successfully")
        sys.exit(0)
    else:
        logger.warning("No files were processed")
        sys.exit(0)


if __name__ == "__main__":
    main()
