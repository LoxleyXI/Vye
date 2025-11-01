"""
Color scheme management for Vye editor
"""

import tkinter as tk
from pathlib import Path
from typing import Dict, List, Optional, TYPE_CHECKING

from vye.utils.file_utils import load_json

if TYPE_CHECKING:
    from vye.app import VyeEditor


class ColorScheme:
    """
    Manages color schemes for the editor.

    Loads all themes from JSON files in the themes/ directory.
    """

    # All possible syntax tags that can be colored
    ALL_SYNTAX_TAGS = [
        "keyword", "builtin", "string", "comment", "number", "function", "class",
        "decorator", "search", "tag", "attribute", "selector", "property", "value",
        "boolean", "null", "heading", "bold", "italic", "code", "link", "list",
        "doctype", "color", "entity", "script", "style", "fstring", "regex",
        "operator", "important", "variable", "at-rule", "strikethrough",
        "blockquote", "horizontal_rule", "table", "image"
    ]

    def __init__(self, editor: Optional['VyeEditor'] = None):
        """
        Initialize the color scheme manager.

        Args:
            editor: Reference to the main editor instance

        Raises:
            FileNotFoundError: If themes directory doesn't exist
            ValueError: If no theme files are found
        """
        self.editor = editor
        self.schemes: Dict[str, Dict[str, str]] = {}
        self.current_scheme: Optional[Dict[str, str]] = None
        self.current_scheme_name: Optional[str] = None
        self.load_theme_files()

    def load_theme_files(self) -> None:
        """
        Load all theme files from themes directory.

        Raises:
            FileNotFoundError: If themes directory doesn't exist
            ValueError: If no theme files are found or all themes are invalid
        """
        themes_dir = Path("themes")
        if not themes_dir.exists():
            raise FileNotFoundError(
                f"Themes directory not found: {themes_dir}\n"
                f"Expected color theme JSON files in themes/"
            )

        theme_files = list(themes_dir.glob("*.json"))
        if not theme_files:
            raise ValueError(f"No theme files (*.json) found in {themes_dir}")

        loaded_count = 0
        for theme_file in theme_files:
            theme_data = load_json(str(theme_file))
            if theme_data:
                name = theme_file.stem
                self.schemes[name] = theme_data
                loaded_count += 1
            else:
                print(f"Warning: Failed to load theme {theme_file}")

        if loaded_count == 0:
            raise ValueError(f"All theme files in {themes_dir} are invalid or empty")

    def get_available_themes(self) -> List[str]:
        """
        Get list of available theme names.

        Returns:
            List of theme names
        """
        return list(self.schemes.keys())

    def load_from_file(self, filepath: str) -> Optional[str]:
        """
        Load a color scheme from a JSON file.

        Args:
            filepath: Path to the theme JSON file

        Returns:
            Theme name if successful, None otherwise
        """
        theme_data = load_json(filepath)
        if theme_data:
            name = Path(filepath).stem
            self.schemes[name] = theme_data
            return name
        return None

    def apply_scheme(self, scheme_name: str) -> bool:
        """
        Apply a color scheme to all text widgets.

        Args:
            scheme_name: Name of the scheme to apply

        Returns:
            True if scheme was applied successfully
        """
        if scheme_name not in self.schemes:
            return False

        scheme = self.schemes[scheme_name]
        self.current_scheme = scheme
        self.current_scheme_name = scheme_name

        # Apply to all tabs if editor is available
        if self.editor and hasattr(self.editor, 'tabs'):
            for tab_data in self.editor.tabs.values():
                text_widget = tab_data.get('text')
                if text_widget:
                    self._apply_to_widget(text_widget, scheme)

        return True

    def _apply_to_widget(self, text_widget: tk.Text, scheme: Dict[str, str]) -> None:
        """
        Apply color scheme to a specific text widget.

        Args:
            text_widget: The text widget to apply colors to
            scheme: Color scheme dictionary
        """
        # Apply general colors
        text_widget.config(
            bg=scheme.get("background", "#ffffff"),
            fg=scheme.get("foreground", "#000000"),
            insertbackground=scheme.get("insertbackground", "#000000"),
            insertwidth=scheme.get("insertwidth", "2"),
            selectbackground=scheme.get("selectbackground", "#0078d4"),
            selectforeground=scheme.get("selectforeground", "#ffffff")
        )

        # Apply syntax highlighting colors
        for tag in self.ALL_SYNTAX_TAGS:
            if tag in scheme:
                text_widget.tag_config(tag, foreground=scheme[tag])

    def get_scheme(self, scheme_name: str) -> Optional[Dict[str, str]]:
        """
        Get a color scheme by name.

        Args:
            scheme_name: Name of the scheme

        Returns:
            Color scheme dictionary or None if not found
        """
        return self.schemes.get(scheme_name)

    def add_scheme(self, name: str, scheme: Dict[str, str]) -> None:
        """
        Add a new color scheme programmatically.

        Args:
            name: Name for the new scheme
            scheme: Color scheme dictionary
        """
        self.schemes[name] = scheme
