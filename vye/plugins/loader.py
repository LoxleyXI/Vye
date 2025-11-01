"""
Plugin discovery and loading system for Vye editor
"""

import importlib.util
import os
import sys
from pathlib import Path
from typing import Dict, List, Optional, Type, TYPE_CHECKING

from vye.plugins.base import Plugin

if TYPE_CHECKING:
    from vye.app import VyeEditor


class PluginLoader:
    """
    Discovers and loads plugins from the plugins directory.

    Supports both built-in plugins and user plugins, with error handling
    and dependency management.
    """

    def __init__(self, editor: 'VyeEditor', plugins_dir: str = "plugins"):
        """
        Initialize the plugin loader.

        Args:
            editor: Reference to the main editor instance
            plugins_dir: Directory to search for plugins
        """
        self.editor = editor
        self.plugins_dir = Path(plugins_dir)
        self.loaded_plugins: Dict[str, Plugin] = {}
        self.failed_plugins: Dict[str, str] = {}

    def discover_plugins(self) -> List[Path]:
        """
        Discover plugin files in the plugins directory.

        Returns:
            List of paths to plugin Python files
        """
        if not self.plugins_dir.exists():
            print(f"Plugins directory not found: {self.plugins_dir}")
            return []

        plugin_files = []

        # Search for Python files
        for path in self.plugins_dir.rglob("*.py"):
            # Skip __init__.py and __pycache__
            if path.name == "__init__.py" or "__pycache__" in str(path):
                continue
            plugin_files.append(path)

        return plugin_files

    def load_plugin_from_file(self, filepath: Path) -> Optional[Plugin]:
        """
        Load a plugin from a Python file.

        Args:
            filepath: Path to the plugin file

        Returns:
            Loaded plugin instance or None if loading failed
        """
        try:
            # Create module name from file path
            module_name = f"vye_plugin_{filepath.stem}"

            # Load the module
            spec = importlib.util.spec_from_file_location(module_name, filepath)
            if spec is None or spec.loader is None:
                raise ImportError(f"Could not load spec from {filepath}")

            module = importlib.util.module_from_spec(spec)
            sys.modules[module_name] = module
            spec.loader.exec_module(module)

            # Find Plugin subclasses in the module
            plugin_class = None
            for attr_name in dir(module):
                attr = getattr(module, attr_name)
                if (isinstance(attr, type) and
                    issubclass(attr, Plugin) and
                    attr is not Plugin):
                    plugin_class = attr
                    break

            if plugin_class is None:
                raise ValueError(f"No Plugin subclass found in {filepath}")

            # Instantiate the plugin
            plugin = plugin_class(self.editor)
            return plugin

        except Exception as e:
            error_msg = f"Failed to load {filepath.name}: {str(e)}"
            print(error_msg)
            self.failed_plugins[filepath.name] = error_msg
            return None

    def load_all_plugins(self) -> int:
        """
        Discover and load all plugins.

        Returns:
            Number of successfully loaded plugins
        """
        plugin_files = self.discover_plugins()
        loaded_count = 0

        for plugin_file in plugin_files:
            plugin = self.load_plugin_from_file(plugin_file)
            if plugin:
                try:
                    if plugin.activate():
                        self.loaded_plugins[plugin.name] = plugin
                        loaded_count += 1
                        print(f"Loaded plugin: {plugin.name} v{plugin.version}")
                    else:
                        error_msg = f"Plugin {plugin.name} failed to activate"
                        print(error_msg)
                        self.failed_plugins[plugin.name] = error_msg
                except Exception as e:
                    error_msg = f"Error activating {plugin.name}: {str(e)}"
                    print(error_msg)
                    self.failed_plugins[plugin.name] = error_msg

        if loaded_count > 0:
            print(f"\nLoaded {loaded_count} plugin(s) successfully")
        if self.failed_plugins:
            print(f"Failed to load {len(self.failed_plugins)} plugin(s)")

        return loaded_count

    def reload_plugin(self, plugin_name: str) -> bool:
        """
        Reload a specific plugin.

        Args:
            plugin_name: Name of the plugin to reload

        Returns:
            True if reload was successful
        """
        if plugin_name not in self.loaded_plugins:
            return False

        # Deactivate old plugin
        old_plugin = self.loaded_plugins[plugin_name]
        try:
            old_plugin.deactivate()
        except Exception as e:
            print(f"Error deactivating {plugin_name}: {e}")

        # Find and reload the plugin file
        plugin_files = self.discover_plugins()
        for plugin_file in plugin_files:
            plugin = self.load_plugin_from_file(plugin_file)
            if plugin and plugin.name == plugin_name:
                try:
                    if plugin.activate():
                        self.loaded_plugins[plugin_name] = plugin
                        print(f"Reloaded plugin: {plugin_name}")
                        return True
                except Exception as e:
                    print(f"Error activating {plugin_name}: {e}")
                    return False

        return False

    def unload_plugin(self, plugin_name: str) -> bool:
        """
        Unload a specific plugin.

        Args:
            plugin_name: Name of the plugin to unload

        Returns:
            True if unload was successful
        """
        if plugin_name not in self.loaded_plugins:
            return False

        plugin = self.loaded_plugins[plugin_name]
        try:
            plugin.deactivate()
            del self.loaded_plugins[plugin_name]
            print(f"Unloaded plugin: {plugin_name}")
            return True
        except Exception as e:
            print(f"Error unloading {plugin_name}: {e}")
            return False

    def get_loaded_plugins(self) -> List[Plugin]:
        """
        Get list of loaded plugins.

        Returns:
            List of loaded plugin instances
        """
        return list(self.loaded_plugins.values())

    def get_plugin(self, plugin_name: str) -> Optional[Plugin]:
        """
        Get a specific plugin by name.

        Args:
            plugin_name: Name of the plugin

        Returns:
            Plugin instance or None if not found
        """
        return self.loaded_plugins.get(plugin_name)

    def get_failed_plugins(self) -> Dict[str, str]:
        """
        Get information about failed plugins.

        Returns:
            Dictionary mapping plugin names to error messages
        """
        return self.failed_plugins.copy()
