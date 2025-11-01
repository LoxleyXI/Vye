"""
Regex pattern management for Vye editor
"""

import os
from pathlib import Path
from typing import Dict, List, Optional, TYPE_CHECKING

from vye.utils.file_utils import load_json, save_json, ensure_dir_exists

if TYPE_CHECKING:
    from vye.app import VyeEditor


class RegexManager:
    """
    Manages saved regex patterns for quick access and reuse.

    Loads patterns from patterns/regex_patterns.json. If not found, loads
    from patterns/default_patterns.json and creates a working copy.
    """

    def __init__(self, editor: Optional['VyeEditor'] = None):
        """
        Initialize the regex manager.

        Args:
            editor: Reference to the main editor instance (optional for standalone use)

        Raises:
            FileNotFoundError: If neither regex_patterns.json nor default_patterns.json exist
        """
        self.editor = editor
        self.patterns: List[Dict[str, str]] = []
        self.patterns_file = "patterns/regex_patterns.json"
        self.default_patterns_file = "patterns/default_patterns.json"
        self.load_patterns()

    def load_patterns(self) -> None:
        """
        Load regex patterns from configuration files.

        First tries to load from patterns/regex_patterns.json (user patterns).
        If not found, loads from patterns/default_patterns.json and creates
        a working copy at patterns/regex_patterns.json.

        Raises:
            FileNotFoundError: If no pattern configuration files are found
        """
        patterns_dir = Path("patterns")
        ensure_dir_exists(str(patterns_dir))

        # Try to load user patterns
        if os.path.exists(self.patterns_file):
            loaded_patterns = load_json(self.patterns_file)
            if not loaded_patterns:
                raise ValueError(f"Invalid or empty patterns file: {self.patterns_file}")
            self.patterns = loaded_patterns
        # Try to load default patterns
        elif os.path.exists(self.default_patterns_file):
            loaded_patterns = load_json(self.default_patterns_file)
            if not loaded_patterns:
                raise ValueError(f"Invalid or empty patterns file: {self.default_patterns_file}")
            self.patterns = loaded_patterns
            # Create working copy
            self.save_patterns()
        else:
            raise FileNotFoundError(
                f"No pattern configuration found. Expected either:\n"
                f"  - {self.patterns_file}\n"
                f"  - {self.default_patterns_file}"
            )

    def save_patterns(self) -> bool:
        """
        Save regex patterns to file.

        Returns:
            True if save was successful, False otherwise
        """
        ensure_dir_exists("patterns")
        return save_json(self.patterns_file, self.patterns)

    def add_pattern(self, name: str, pattern: str) -> bool:
        """
        Add a new regex pattern.

        Args:
            name: Display name for the pattern
            pattern: Regex pattern string

        Returns:
            True if pattern was added and saved successfully
        """
        self.patterns.append({"name": name, "pattern": pattern})
        return self.save_patterns()

    def delete_pattern(self, index: int) -> bool:
        """
        Delete a regex pattern by index.

        Args:
            index: Index of the pattern to delete

        Returns:
            True if pattern was deleted and saved successfully
        """
        if 0 <= index < len(self.patterns):
            del self.patterns[index]
            return self.save_patterns()
        return False

    def get_pattern(self, index: int) -> Optional[str]:
        """
        Get a regex pattern by index.

        Args:
            index: Index of the pattern

        Returns:
            The regex pattern string or None if index is invalid
        """
        if 0 <= index < len(self.patterns):
            return self.patterns[index]["pattern"]
        return None

    def get_pattern_by_name(self, name: str) -> Optional[str]:
        """
        Get a regex pattern by name.

        Args:
            name: Name of the pattern

        Returns:
            The regex pattern string or None if not found
        """
        for pattern in self.patterns:
            if pattern["name"] == name:
                return pattern["pattern"]
        return None

    def get_all_patterns(self) -> List[Dict[str, str]]:
        """
        Get all regex patterns.

        Returns:
            List of pattern dictionaries with 'name' and 'pattern' keys
        """
        return self.patterns.copy()
