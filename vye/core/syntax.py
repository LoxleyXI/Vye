"""
Syntax highlighting engine for Vye editor
"""

import re
import tkinter as tk
from pathlib import Path
from typing import Dict, List, Optional, Union, TYPE_CHECKING

from vye.utils.file_utils import load_json

if TYPE_CHECKING:
    from vye.app import VyeEditor


class SyntaxHighlighter:
    """
    Handles syntax highlighting with external JSON definition files.

    Supports multiple programming languages through JSON-based syntax
    definitions, with regex patterns for different token types.
    """

    def __init__(self, text_widget: tk.Text, editor: Optional['VyeEditor'] = None):
        """
        Initialize the syntax highlighter.

        Args:
            text_widget: The Tkinter text widget to highlight
            editor: Reference to the main editor instance
        """
        self.text = text_widget
        self.editor = editor
        self.patterns: Dict[str, Union[str, Dict]] = {}
        self.current_language: Optional[str] = None
        self.syntax_definitions: Dict[str, Dict] = {}
        self.load_syntax_definitions()

    def load_syntax_definitions(self) -> None:
        """Load all syntax definition files from syntax directory."""
        syntax_dir = Path("syntax")
        if not syntax_dir.exists():
            return

        for syntax_file in syntax_dir.glob("*.json"):
            definition = load_json(str(syntax_file))
            if definition:
                lang_name = definition.get("name", syntax_file.stem)
                self.syntax_definitions[lang_name.lower()] = definition

    def get_available_languages(self) -> List[str]:
        """
        Get list of available language syntaxes.

        Returns:
            List of supported language names
        """
        return list(self.syntax_definitions.keys())

    def setup_language(self, language: str) -> bool:
        """
        Setup patterns for a specific language.

        Args:
            language: Name of the language to set up

        Returns:
            True if language was found and loaded successfully
        """
        language = language.lower()
        if language not in self.syntax_definitions:
            self.current_language = None
            self.patterns = {}
            return False

        self.current_language = language
        definition = self.syntax_definitions[language]
        self.patterns = {}

        # Convert patterns from definition format
        for tag, pattern_info in definition.get("patterns", {}).items():
            if isinstance(pattern_info, dict):
                self.patterns[tag] = pattern_info
            else:
                self.patterns[tag] = str(pattern_info)

        return True

    def detect_language(self, filename: str) -> Optional[str]:
        """
        Detect language from file extension.

        Args:
            filename: Name of the file (can include path)

        Returns:
            Detected language name or None if not recognized
        """
        if not filename:
            return None

        ext = Path(filename).suffix.lower()

        # Check all syntax definitions for matching extensions
        for lang_name, definition in self.syntax_definitions.items():
            extensions = definition.get("extensions", [])
            if ext in extensions:
                return lang_name

        return None

    def highlight_all(self) -> None:
        """Apply syntax highlighting to entire document."""
        self.highlight("1.0", "end")

    def highlight(self, start: str = "1.0", end: str = "end") -> None:
        """
        Apply syntax highlighting to a range of text.

        Args:
            start: Start position in Tkinter text index format
            end: End position in Tkinter text index format
        """
        if not self.patterns:
            return

        # Remove existing tags
        for tag in self.patterns.keys():
            self.text.tag_remove(tag, start, end)

        text_content = self.text.get(start, end)

        # Apply highlighting for each pattern
        for tag, pattern in self.patterns.items():
            if not pattern:
                continue

            try:
                # Extract pattern details
                pattern_str = pattern
                group = 0
                flags = re.MULTILINE

                if isinstance(pattern, dict):
                    pattern_str = pattern.get("pattern", "")
                    group = pattern.get("group", 0)
                    flag_str = pattern.get("flags", "")
                    if 'm' in flag_str:
                        flags = re.MULTILINE
                    if 'i' in flag_str:
                        flags |= re.IGNORECASE

                # Find and tag all matches
                for match in re.finditer(str(pattern_str), text_content, flags):
                    if group and match.groups():
                        match_start = match.start(group)
                        match_end = match.end(group)
                    else:
                        match_start = match.start()
                        match_end = match.end()

                    start_idx = self.text.index(f"{start} +{match_start}c")
                    end_idx = self.text.index(f"{start} +{match_end}c")

                    self.text.tag_add(tag, start_idx, end_idx)
            except (re.error, Exception) as e:
                print(f"Error highlighting {tag}: {e}")

        # Apply whitespace display after syntax highlighting
        if self.editor and hasattr(self.editor, 'show_whitespace') and self.editor.show_whitespace:
            if hasattr(self.editor, 'apply_whitespace_to_text'):
                self.editor.apply_whitespace_to_text(self.text, start, end)

    def highlight_line(self, line_num: int) -> None:
        """
        Highlight a specific line.

        Args:
            line_num: Line number to highlight (1-indexed)
        """
        start = f"{line_num}.0"
        end = f"{line_num}.end"
        self.highlight(start, end)

    def set_language(self, language: str) -> bool:
        """
        Set the language and re-highlight the entire document.

        Args:
            language: Name of the language to use

        Returns:
            True if language was set successfully
        """
        if self.setup_language(language):
            self.highlight_all()
            return True
        return False
