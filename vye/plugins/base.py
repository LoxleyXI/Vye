"""
Base classes for Vye editor plugins
"""

from abc import ABC, abstractmethod
from typing import Dict, List, Callable, Any, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from vye.app import VyeEditor


class Plugin(ABC):
    """
    Abstract base class for all Vye plugins.

    Plugins extend editor functionality without modifying core code.
    """

    # Plugin metadata
    name: str = "Unnamed Plugin"
    version: str = "0.0.0"
    author: str = "Unknown"
    description: str = "No description provided"

    def __init__(self, editor: 'VyeEditor'):
        """
        Initialize the plugin.

        Args:
            editor: Reference to the main editor instance
        """
        self.editor = editor
        self.enabled = False

    @abstractmethod
    def activate(self) -> bool:
        """
        Activate the plugin.

        This method is called when the plugin is loaded or enabled.
        Perform initialization, register hooks, add menu items, etc.

        Returns:
            True if activation was successful, False otherwise
        """
        pass

    @abstractmethod
    def deactivate(self) -> bool:
        """
        Deactivate the plugin.

        This method is called when the plugin is unloaded or disabled.
        Clean up resources, unregister hooks, remove UI elements, etc.

        Returns:
            True if deactivation was successful, False otherwise
        """
        pass

    def on_error(self, error: Exception) -> None:
        """
        Handle plugin errors.

        Override this method to provide custom error handling.

        Args:
            error: The exception that occurred
        """
        print(f"Error in plugin {self.name}: {error}")


class LanguagePlugin(Plugin):
    """
    Plugin for adding language syntax support.

    Provides syntax highlighting definitions for a specific language.
    """

    # Language metadata
    language_name: str = "unknown"
    file_extensions: List[str] = []

    def __init__(self, editor: 'VyeEditor'):
        super().__init__(editor)
        self.syntax_definition: Dict[str, Any] = {}

    @abstractmethod
    def get_syntax_definition(self) -> Dict[str, Any]:
        """
        Get the syntax definition for this language.

        Returns:
            Dictionary with syntax patterns and configuration
        """
        pass

    def activate(self) -> bool:
        """Register the language syntax with the editor."""
        self.syntax_definition = self.get_syntax_definition()
        # Register with syntax highlighter
        if hasattr(self.editor, 'register_language'):
            self.editor.register_language(self.language_name, self.syntax_definition)
        self.enabled = True
        return True

    def deactivate(self) -> bool:
        """Unregister the language syntax."""
        if hasattr(self.editor, 'unregister_language'):
            self.editor.unregister_language(self.language_name)
        self.enabled = False
        return True


class ThemePlugin(Plugin):
    """
    Plugin for adding color themes.

    Provides color scheme definitions for the editor.
    """

    theme_name: str = "unknown"

    def __init__(self, editor: 'VyeEditor'):
        super().__init__(editor)
        self.theme_data: Dict[str, str] = {}

    @abstractmethod
    def get_theme_data(self) -> Dict[str, str]:
        """
        Get the theme color data.

        Returns:
            Dictionary mapping color names to hex values
        """
        pass

    def activate(self) -> bool:
        """Register the theme with the editor."""
        self.theme_data = self.get_theme_data()
        if hasattr(self.editor, 'color_scheme'):
            self.editor.color_scheme.add_scheme(self.theme_name, self.theme_data)
        self.enabled = True
        return True

    def deactivate(self) -> bool:
        """Unregister the theme."""
        # Themes don't need cleanup
        self.enabled = False
        return True


class CommandPlugin(Plugin):
    """
    Plugin for adding custom Vim commands.

    Extends Vim mode with custom commands and key mappings.
    """

    def __init__(self, editor: 'VyeEditor'):
        super().__init__(editor)
        self.commands: Dict[str, Callable] = {}
        self.keybindings: Dict[str, Callable] = {}

    @abstractmethod
    def get_commands(self) -> Dict[str, Callable]:
        """
        Get custom Vim commands.

        Returns:
            Dictionary mapping command names to handler functions
        """
        pass

    def get_keybindings(self) -> Dict[str, Callable]:
        """
        Get custom key bindings.

        Returns:
            Dictionary mapping key sequences to handler functions
        """
        return {}

    def activate(self) -> bool:
        """Register commands and keybindings."""
        self.commands = self.get_commands()
        self.keybindings = self.get_keybindings()

        # Register commands
        if hasattr(self.editor, 'register_commands'):
            self.editor.register_commands(self.commands)

        # Register keybindings
        if hasattr(self.editor, 'register_keybindings'):
            self.editor.register_keybindings(self.keybindings)

        self.enabled = True
        return True

    def deactivate(self) -> bool:
        """Unregister commands and keybindings."""
        if hasattr(self.editor, 'unregister_commands'):
            for cmd_name in self.commands:
                self.editor.unregister_commands(cmd_name)

        self.enabled = False
        return True


class HookPlugin(Plugin):
    """
    Plugin that responds to editor events.

    Implements event handlers for various editor actions.
    """

    def __init__(self, editor: 'VyeEditor'):
        super().__init__(editor)
        self.registered_hooks: List[str] = []

    def activate(self) -> bool:
        """Register event hooks with the editor."""
        # Register all available hook methods
        hook_methods = [
            'on_file_open', 'on_file_save', 'on_file_close',
            'on_mode_change', 'on_text_change', 'on_selection_change',
            'on_startup', 'on_shutdown'
        ]

        for hook_name in hook_methods:
            if hasattr(self, hook_name):
                handler = getattr(self, hook_name)
                if hasattr(self.editor, 'register_hook'):
                    self.editor.register_hook(hook_name, handler)
                    self.registered_hooks.append(hook_name)

        self.enabled = True
        return True

    def deactivate(self) -> bool:
        """Unregister event hooks."""
        if hasattr(self.editor, 'unregister_hook'):
            for hook_name in self.registered_hooks:
                handler = getattr(self, hook_name)
                self.editor.unregister_hook(hook_name, handler)

        self.registered_hooks.clear()
        self.enabled = False
        return True

    # Hook methods (optional to override)
    def on_file_open(self, filepath: str) -> None:
        """Called when a file is opened."""
        pass

    def on_file_save(self, filepath: str) -> None:
        """Called when a file is saved."""
        pass

    def on_file_close(self, filepath: str) -> None:
        """Called when a file is closed."""
        pass

    def on_mode_change(self, old_mode: str, new_mode: str) -> None:
        """Called when Vim mode changes."""
        pass

    def on_text_change(self, start: str, end: str, text: str) -> None:
        """Called when text is modified."""
        pass

    def on_selection_change(self, start: str, end: str) -> None:
        """Called when text selection changes."""
        pass

    def on_startup(self) -> None:
        """Called when editor starts."""
        pass

    def on_shutdown(self) -> None:
        """Called when editor shuts down."""
        pass
