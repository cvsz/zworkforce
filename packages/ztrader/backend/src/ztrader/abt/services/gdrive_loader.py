"""// ZeaZDev [Google Drive Integration Utility] //
// Project: Auto Bot Trader i18n //
// Version: 1.0.0 //
// Author: ZeaZDev Meta-Intelligence (Generated) //
// --- DO NOT EDIT HEADER --- //"""

import json
from logging import getLogger
from pathlib import Path
from typing import Any, Dict, List, Optional

import gdown
import yaml

logger = getLogger(__name__)


class GoogleDriveLoader:
    """
    Utility class for downloading and loading strategy configurations from Google Drive.

    This class handles:
    1. Downloading files/folders from Google Drive using shared links
    2. Parsing strategy configurations (YAML/JSON)
    3. Loading external TradingView strategies and indicators
    """

    def __init__(self, cache_dir: str = "/tmp/gdrive_cache"):
        """
        Initialize Google Drive loader.

        Args:
            cache_dir: Directory to cache downloaded files
        """
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def download_file(self, url: str, output_path: Optional[str] = None) -> str:
        """
        Download a single file from Google Drive.

        Args:
            url: Google Drive file URL (shareable link)
            output_path: Optional path to save the file

        Returns:
            Path to downloaded file

        Example:
            loader = GoogleDriveLoader()
            file_path = loader.download_file(
                "https://drive.google.com/file/d/1abc.../view?usp=sharing"
            )
        """
        try:
            if output_path is None:
                # Generate output path in cache directory
                file_id = self._extract_file_id(url)
                output_path = str(self.cache_dir / f"file_{file_id}")

            logger.info(f"Downloading file from Google Drive: {url}")
            gdown.download(url, output_path, quiet=False, fuzzy=True)
            logger.info(f"File downloaded successfully to: {output_path}")

            return output_path

        except Exception as e:
            logger.error(f"Error downloading file from Google Drive: {str(e)}")
            raise

    def download_folder(
        self, folder_url: str, output_dir: Optional[str] = None, quiet: bool = False
    ) -> str:
        """
        Download entire folder from Google Drive.

        Args:
            folder_url: Google Drive folder URL (shareable link)
            output_dir: Optional directory to save files
            quiet: Suppress download progress output

        Returns:
            Path to downloaded folder

        Example:
            loader = GoogleDriveLoader()
            folder_path = loader.download_folder(
                "https://drive.google.com/drive/folders/1abc..."
            )
        """
        try:
            if output_dir is None:
                folder_id = self._extract_folder_id(folder_url)
                output_dir = str(self.cache_dir / f"folder_{folder_id}")

            # Create output directory
            Path(output_dir).mkdir(parents=True, exist_ok=True)

            logger.info(f"Downloading folder from Google Drive: {folder_url}")
            gdown.download_folder(
                folder_url, output=output_dir, quiet=quiet, use_cookies=False
            )
            logger.info(f"Folder downloaded successfully to: {output_dir}")

            return output_dir

        except Exception as e:
            logger.error(f"Error downloading folder from Google Drive: {str(e)}")
            raise

    def load_strategy_config(self, file_path: str) -> Dict[str, Any]:
        """
        Load strategy configuration from YAML or JSON file.

        Args:
            file_path: Path to configuration file

        Returns:
            Dictionary containing strategy configuration
        """
        try:
            file_path = Path(file_path)

            with open(file_path, "r") as f:
                if file_path.suffix in [".yaml", ".yml"]:
                    config = yaml.safe_load(f)
                elif file_path.suffix == ".json":
                    config = json.load(f)
                else:
                    raise ValueError(f"Unsupported file format: {file_path.suffix}")

            logger.info(f"Loaded strategy config from: {file_path}")
            return config

        except Exception as e:
            logger.error(f"Error loading strategy config: {str(e)}")
            raise

    def load_all_configs(self, folder_path: str) -> List[Dict[str, Any]]:
        """
        Load all strategy configurations from a folder.

        Args:
            folder_path: Path to folder containing config files

        Returns:
            List of strategy configuration dictionaries
        """
        configs = []
        folder = Path(folder_path)

        # Find all YAML and JSON files
        config_files = (
            list(folder.glob("*.yaml"))
            + list(folder.glob("*.yml"))
            + list(folder.glob("*.json"))
        )

        for config_file in config_files:
            try:
                config = self.load_strategy_config(str(config_file))
                config["_source_file"] = str(config_file)
                configs.append(config)
            except Exception as e:
                logger.warning(f"Failed to load config from {config_file}: {str(e)}")
                continue

        logger.info(f"Loaded {len(configs)} configurations from {folder_path}")
        return configs

    def _extract_file_id(self, url: str) -> str:
        """Extract file ID from Google Drive URL."""
        if "/file/d/" in url:
            return url.split("/file/d/")[1].split("/")[0]
        elif "id=" in url:
            return url.split("id=")[1].split("&")[0]
        else:
            raise ValueError(f"Cannot extract file ID from URL: {url}")

    def _extract_folder_id(self, url: str) -> str:
        """Extract folder ID from Google Drive URL."""
        if "/folders/" in url:
            return url.split("/folders/")[1].split("?")[0]
        elif "id=" in url:
            return url.split("id=")[1].split("&")[0]
        else:
            raise ValueError(f"Cannot extract folder ID from URL: {url}")

    def clear_cache(self):
        """Clear the download cache directory."""
        import shutil

        if self.cache_dir.exists():
            shutil.rmtree(self.cache_dir)
            self.cache_dir.mkdir(parents=True, exist_ok=True)
            logger.info("Cache cleared successfully")


# Utility function for easy access
def load_tradingview_strategies_from_gdrive(folder_url: str) -> List[Dict[str, Any]]:
    """
    Convenience function to download and load TradingView strategies from Google Drive.

    Args:
        folder_url: Google Drive folder URL containing strategy configs

    Returns:
        List of strategy configurations

    Example:
        strategies = load_tradingview_strategies_from_gdrive(
            "https://drive.google.com/drive/folders/1YlCnoQSP8MlfJO6c1GySn32joXIzgz3G"
        )
        for strategy in strategies:
            print(f"Strategy: {strategy.get('name')}")
    """
    loader = GoogleDriveLoader()
    folder_path = loader.download_folder(folder_url)
    configs = loader.load_all_configs(folder_path)
    return configs


if __name__ == "__main__":
    # Example usage for testing
    print("Google Drive Loader - Test")

    # Test with the folder from the issue
    folder_url = (
        "https://drive.google.com/drive/u/0/folders/1YlCnoQSP8MlfJO6c1GySn32joXIzgz3G"
    )

    try:
        strategies = load_tradingview_strategies_from_gdrive(folder_url)
        print(f"\nLoaded {len(strategies)} strategies:")
        for strategy in strategies:
            print(
                "  - "
                f"{strategy.get('name', 'Unnamed')} "
                f"from {strategy.get('_source_file')}"
            )
    except Exception as e:
        print(f"Error: {str(e)}")
