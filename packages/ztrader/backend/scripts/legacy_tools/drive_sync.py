"""// ZeaZDev [Tools Google Drive Sync] //
// Project: Auto Bot Trader i18n //
// Version: 1.0.0 //
// Author: ZeaZDev Meta-Intelligence (Generated) //
// --- DO NOT EDIT HEADER --- //"""

import argparse
import logging
import re
import sys
from pathlib import Path

try:
    import gdown
except ImportError:
    print(
        "ERROR: gdown is not installed. Please run: pip install gdown", file=sys.stderr
    )
    sys.exit(1)

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def extract_folder_id(url_or_id: str) -> str:
    """
    Extract Google Drive folder ID from URL or return as-is if already an ID.

    Args:
        url_or_id: Google Drive folder URL or folder ID

    Returns:
        Folder ID string

    Examples:
        >>> extract_folder_id("https://drive.google.com/drive/folders/1ABC123?usp=sharing")
        '1ABC123'
        >>> extract_folder_id("1ABC123")
        '1ABC123'
    """
    # Check if it's already just an ID (alphanumeric, underscore, hyphen)
    if re.match(r"^[a-zA-Z0-9_-]+$", url_or_id):
        return url_or_id

    # Try to extract from various Google Drive URL formats
    patterns = [
        r"folders/([a-zA-Z0-9_-]+)",
        r"id=([a-zA-Z0-9_-]+)",
    ]

    for pattern in patterns:
        match = re.search(pattern, url_or_id)
        if match:
            return match.group(1)

    # If no pattern matched, return as-is and let gdown handle it
    logger.warning(f"Could not extract folder ID from '{url_or_id}', using as-is")
    return url_or_id


def download_drive_folder(
    folder_id: str, output_dir: str = "external/drive_assets"
) -> bool:
    """
    Download a Google Drive folder and its contents.

    Args:
        folder_id: Google Drive folder ID or URL
        output_dir: Local directory to download files into

    Returns:
        True if download succeeded, False otherwise

    Notes:
        - Folder must be shared as "Anyone with the link can view"
        - Creates output_dir if it doesn't exist
        - Downloads all files and subdirectories recursively
    """
    folder_id = extract_folder_id(folder_id)
    output_path = Path(output_dir)

    logger.info(f"Downloading Google Drive folder '{folder_id}' to '{output_dir}'")

    # Create output directory if it doesn't exist
    output_path.mkdir(parents=True, exist_ok=True)

    try:
        # Use gdown to download the folder
        # Note: gdown.download_folder requires the folder to be publicly shared
        url = f"https://drive.google.com/drive/folders/{folder_id}"

        logger.info(f"Attempting to download from: {url}")
        logger.info("Note: Folder must be shared as 'Anyone with the link can view'")

        # Download the folder
        gdown.download_folder(
            url, output=str(output_path), quiet=False, remaining_ok=True
        )

        logger.info(f"Successfully downloaded folder to '{output_dir}'")
        return True

    except Exception as e:
        logger.error(f"Failed to download Google Drive folder: {e}", exc_info=True)
        logger.error(
            "Make sure the folder is shared as 'Anyone with the link can view'"
        )
        return False


def main():
    """Main entry point for drive_sync tool."""
    parser = argparse.ArgumentParser(
        description="Download Google Drive folder contents for ABTPi18n integration",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python tools/drive_sync.py --folder-id "1ABC123XYZ"
  python tools/drive_sync.py --folder-id "https://drive.google.com/drive/folders/1ABC123?usp=sharing"
  python tools/drive_sync.py --folder-id "1ABC123" --output external/my_assets

Prerequisites:
  - Folder must be shared as "Anyone with the link can view"
  - Install gdown: pip install gdown
        """,
    )

    parser.add_argument(
        "--folder-id", required=True, help="Google Drive folder URL or folder ID"
    )

    parser.add_argument(
        "--output",
        default="external/drive_assets",
        help="Output directory for downloaded files (default: external/drive_assets)",
    )

    parser.add_argument("--verbose", action="store_true", help="Enable verbose logging")

    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    success = download_drive_folder(args.folder_id, args.output)

    if success:
        logger.info("Download completed successfully")
        sys.exit(0)
    else:
        logger.error("Download failed")
        sys.exit(1)


if __name__ == "__main__":
    main()
