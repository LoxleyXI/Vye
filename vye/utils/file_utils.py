"""
File utility functions for Vye editor
"""

import json
import os
from pathlib import Path
from typing import Any, Dict, Optional


def get_config_dir() -> Path:
    """
    Get the configuration directory for Vye.

    Returns:
        Path to the configuration directory
    """
    # Use the current directory for now (later could use ~/.config/vye or AppData)
    return Path(__file__).parent.parent.parent


def load_json(file_path: str, default: Optional[Any] = None) -> Any:
    """
    Load JSON data from a file with error handling.

    Args:
        file_path: Path to the JSON file
        default: Default value to return if file doesn't exist or is invalid

    Returns:
        Parsed JSON data or default value
    """
    try:
        if os.path.exists(file_path):
            with open(file_path, 'r', encoding='utf-8') as f:
                return json.load(f)
    except (json.JSONDecodeError, IOError) as e:
        print(f"Warning: Could not load {file_path}: {e}")
    return default if default is not None else {}


def save_json(file_path: str, data: Any, indent: int = 2) -> bool:
    """
    Save data to a JSON file with error handling.

    Args:
        file_path: Path to save the JSON file
        data: Data to serialize
        indent: Indentation level for pretty printing

    Returns:
        True if successful, False otherwise
    """
    try:
        # Ensure directory exists
        os.makedirs(os.path.dirname(file_path), exist_ok=True)

        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=indent)
        return True
    except (IOError, TypeError) as e:
        print(f"Error: Could not save {file_path}: {e}")
        return False


def ensure_dir_exists(dir_path: str) -> bool:
    """
    Ensure a directory exists, creating it if necessary.

    Args:
        dir_path: Path to the directory

    Returns:
        True if directory exists or was created successfully
    """
    try:
        os.makedirs(dir_path, exist_ok=True)
        return True
    except OSError as e:
        print(f"Error: Could not create directory {dir_path}: {e}")
        return False
