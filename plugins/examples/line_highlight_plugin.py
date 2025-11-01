"""
Example Line Highlight Plugin for Vye Editor

Demonstrates theme customization by adding enhanced
current line highlighting.
"""

from vye.plugins.base import HookPlugin


class LineHighlightPlugin(HookPlugin):
    """
    Enhances the current line highlighting with custom colors.

    This plugin demonstrates:
    - Visual customization
    - Mode-aware behavior
    - Tkinter tag manipulation
    """

    name = "Enhanced Line Highlight"
    version = "1.0.0"
    author = "Vye Team"
    description = "Enhanced current line highlighting with mode-aware colors"

    def __init__(self, editor):
        super().__init__(editor)
        self.highlight_colors = {
            "NORMAL": "#2d2d30",
            "INSERT": "#1e3a1e",
            "VISUAL": "#3a1e1e",
            "COMMAND": "#1e1e3a",
            "REPLACE": "#3a3a1e",
        }
        self.current_line_tag = "enhanced_current_line"

    def activate(self) -> bool:
        """Activate the plugin."""
        print(f"[{self.name}] Activated")
        super().activate()  # Register hooks
        self._update_highlight()
        return True

    def deactivate(self) -> bool:
        """Deactivate the plugin and remove highlights."""
        # Remove all enhanced highlights
        if hasattr(self.editor, 'tabs'):
            for tab_data in self.editor.tabs.values():
                text_widget = tab_data.get('text')
                if text_widget:
                    text_widget.tag_remove(self.current_line_tag, "1.0", "end")
        print(f"[{self.name}] Deactivated")
        return super().deactivate()

    def on_mode_change(self, old_mode: str, new_mode: str) -> None:
        """Update highlight color based on Vim mode."""
        self._update_highlight()

    def on_selection_change(self, start: str, end: str) -> None:
        """Update highlight when cursor moves."""
        self._update_highlight()

    def _update_highlight(self) -> None:
        """Apply enhanced line highlighting to current line."""
        if not hasattr(self.editor, 'text'):
            return

        text_widget = self.editor.text

        # Remove old highlight
        text_widget.tag_remove(self.current_line_tag, "1.0", "end")

        # Get current mode
        mode = "NORMAL"
        if hasattr(self.editor, 'vim') and hasattr(self.editor.vim, 'mode'):
            mode = self.editor.vim.mode

        # Get cursor position
        try:
            cursor_line = text_widget.index("insert").split(".")[0]
            start_pos = f"{cursor_line}.0"
            end_pos = f"{cursor_line}.end + 1c"

            # Apply new highlight
            color = self.highlight_colors.get(mode, self.highlight_colors["NORMAL"])
            text_widget.tag_config(self.current_line_tag, background=color)
            text_widget.tag_add(self.current_line_tag, start_pos, end_pos)
        except Exception as e:
            print(f"[{self.name}] Error updating highlight: {e}")
