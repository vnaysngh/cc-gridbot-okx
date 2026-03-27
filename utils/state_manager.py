# utils/state_manager.py
"""
State persistence for bot strategies.
Saves and loads strategy state to/from JSON files.
"""

import json
import os
from pathlib import Path
from typing import Optional
from utils.logger import setup_logger

logger = setup_logger("state_manager")

STATE_DIR = Path(__file__).parent.parent / "data" / "state"


def ensure_state_dir():
    """Create state directory if it doesn't exist."""
    STATE_DIR.mkdir(parents=True, exist_ok=True)


def save_grid_state(state: dict, exchange_id: str, symbol: str):
    """
    Save grid strategy state to JSON file.

    Args:
        state: Dictionary containing grid state data
        exchange_id: Exchange identifier (e.g., "okx")
        symbol: Trading pair (e.g., "CC/USDT")
    """
    ensure_state_dir()

    # Sanitize symbol for filename (replace / with _)
    safe_symbol = symbol.replace("/", "_")
    filename = f"grid_{exchange_id}_{safe_symbol}.json"
    filepath = STATE_DIR / filename

    try:
        with open(filepath, 'w') as f:
            json.dump(state, f, indent=2)
        logger.debug(f"Saved grid state to {filepath}")
    except Exception as e:
        logger.error(f"Failed to save state to {filepath}: {e}")


def load_grid_state(exchange_id: str, symbol: str) -> Optional[dict]:
    """
    Load grid strategy state from JSON file.

    Args:
        exchange_id: Exchange identifier (e.g., "okx")
        symbol: Trading pair (e.g., "CC/USDT")

    Returns:
        Dictionary containing grid state data, or None if not found
    """
    safe_symbol = symbol.replace("/", "_")
    filename = f"grid_{exchange_id}_{safe_symbol}.json"
    filepath = STATE_DIR / filename

    if not filepath.exists():
        logger.debug(f"No saved state found at {filepath}")
        return None

    try:
        with open(filepath, 'r') as f:
            state = json.load(f)
        logger.info(f"Loaded grid state from {filepath}")
        return state
    except Exception as e:
        logger.error(f"Failed to load state from {filepath}: {e}")
        return None


def clear_grid_state(exchange_id: str, symbol: str):
    """
    Delete saved grid state file.

    Args:
        exchange_id: Exchange identifier (e.g., "okx")
        symbol: Trading pair (e.g., "CC/USDT")
    """
    safe_symbol = symbol.replace("/", "_")
    filename = f"grid_{exchange_id}_{safe_symbol}.json"
    filepath = STATE_DIR / filename

    if filepath.exists():
        try:
            os.remove(filepath)
            logger.info(f"Cleared grid state: {filepath}")
        except Exception as e:
            logger.error(f"Failed to clear state {filepath}: {e}")
