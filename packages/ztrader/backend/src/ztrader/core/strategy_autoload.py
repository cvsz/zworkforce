"""// ZeaZDev [Core Strategy Autoload] //
// Project: Auto Bot Trader i18n //
// Version: 1.0.0 //
// Author: ZeaZDev Meta-Intelligence (Generated) //
// --- DO NOT EDIT HEADER --- //"""

import importlib
import importlib.util
import logging
import sys
from pathlib import Path

from ztrader.core.strategy_base import Strategy
from ztrader.core.strategy_registry import StrategyRegistry

logger = logging.getLogger(__name__)


def load_external_strategies(external_dir: str = "strategies/external") -> list[str]:
    """
    Dynamically import and register Strategy subclasses from external directory.

    This function scans the specified directory for Python files, imports them,
    and registers any Strategy subclasses found with the StrategyRegistry.

    Args:
        external_dir: Path to directory containing external strategy modules
                     (relative to project root or absolute)

    Returns:
        List of strategy names that were successfully loaded and registered

    Notes:
        - Only imports .py files (ignores __init__.py and files starting with _)
        - Strategies can either:
          1. Call StrategyRegistry.register() at import time, or
          2. Define Strategy subclass with 'name' attribute for auto-registration
        - Errors during import are logged but don't stop the process
        - Use caution: external code is untrusted - consider sandboxing in production

    Example:
        >>> loaded = load_external_strategies()
        >>> print(f"Loaded strategies: {loaded}")
        Loaded strategies: ['CUSTOM_MA', 'EXTERNAL_MOMENTUM']
    """
    external_path = Path(external_dir)

    if not external_path.exists():
        logger.warning(f"External strategies directory '{external_dir}' does not exist")
        return []

    if not external_path.is_dir():
        logger.warning(f"External strategies path '{external_dir}' is not a directory")
        return []

    loaded_strategies = []
    initial_strategies = set(StrategyRegistry.list_names())

    # Find all Python files in the external directory
    python_files = list(external_path.glob("*.py"))
    python_files = [f for f in python_files if not f.name.startswith("_")]

    for py_file in python_files:
        module_name = f"external_strategy_{py_file.stem}"

        try:
            # Import the module dynamically
            spec = importlib.util.spec_from_file_location(module_name, py_file)
            if spec is None or spec.loader is None:
                logger.warning(f"Could not load spec for {py_file}")
                continue

            module = importlib.util.module_from_spec(spec)
            sys.modules[module_name] = module
            spec.loader.exec_module(module)

            # Find Strategy subclasses in the module
            for attr_name in dir(module):
                attr = getattr(module, attr_name)

                # Check if it's a Strategy subclass (but not Strategy itself)
                if (
                    isinstance(attr, type)
                    and issubclass(attr, Strategy)
                    and attr is not Strategy
                    and hasattr(attr, "name")
                ):
                    # Register unless module already self-registered.
                    if attr.name not in StrategyRegistry.list_names():
                        StrategyRegistry.register(attr)
                        logger.info(
                            "Auto-registered strategy '%s' from %s",
                            attr.name,
                            py_file.name,
                        )

        except Exception as e:
            logger.error(
                f"Error loading external strategy from {py_file}: {e}", exc_info=True
            )
            continue

    # Determine which strategies were newly loaded
    final_strategies = set(StrategyRegistry.list_names())
    newly_loaded = final_strategies - initial_strategies
    loaded_strategies = sorted(newly_loaded)

    if loaded_strategies:
        count = len(loaded_strategies)
        names = ", ".join(loaded_strategies)
        logger.info(f"Successfully loaded {count} external strategies")
        logger.debug(f"Loaded strategy names: {names}")
    else:
        logger.info(f"No new external strategies loaded from '{external_dir}'")

    return loaded_strategies
