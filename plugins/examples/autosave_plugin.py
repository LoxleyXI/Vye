"""
Example Auto-Save Plugin for Vye Editor

Demonstrates the HookPlugin system by automatically saving files
after a period of inactivity.
"""

import time
from typing import Optional
from vye.plugins.base import HookPlugin


class AutoSavePlugin(HookPlugin):
    """
    Automatically saves files after a period of inactivity.

    This plugin demonstrates:
    - Event hook integration
    - Timer-based actions
    - State tracking
    """

    name = "Auto-Save"
    version = "1.0.0"
    author = "Vye Team"
    description = "Automatically saves files after 30 seconds of inactivity"

    def __init__(self, editor):
        super().__init__(editor)
        self.last_change_time: Optional[float] = None
        self.autosave_delay = 30  # seconds
        self.timer_id: Optional[str] = None
        self.modified = False

    def activate(self) -> bool:
        """Activate the plugin and start monitoring."""
        print(f"[{self.name}] Activated - Auto-save delay: {self.autosave_delay}s")
        super().activate()  # Register hooks
        return True

    def deactivate(self) -> bool:
        """Deactivate the plugin and stop timers."""
        if self.timer_id:
            try:
                self.editor.root.after_cancel(self.timer_id)
            except:
                pass
        print(f"[{self.name}] Deactivated")
        return super().deactivate()

    def on_text_change(self, start: str, end: str, text: str) -> None:
        """Called when text is modified."""
        self.last_change_time = time.time()
        self.modified = True

        # Cancel existing timer and start new one
        if self.timer_id:
            try:
                self.editor.root.after_cancel(self.timer_id)
            except:
                pass

        # Schedule auto-save
        self.timer_id = self.editor.root.after(
            self.autosave_delay * 1000,
            self._auto_save
        )

    def _auto_save(self) -> None:
        """Perform the auto-save operation."""
        if not self.modified:
            return

        # Check if enough time has passed
        if self.last_change_time:
            elapsed = time.time() - self.last_change_time
            if elapsed >= self.autosave_delay:
                # Get current file path
                if hasattr(self.editor, 'current_file_path') and self.editor.current_file_path:
                    try:
                        # Save the file
                        if hasattr(self.editor, 'save_file'):
                            self.editor.save_file()
                            print(f"[{self.name}] Auto-saved: {self.editor.current_file_path}")
                            self.modified = False
                    except Exception as e:
                        print(f"[{self.name}] Error during auto-save: {e}")

    def on_file_save(self, filepath: str) -> None:
        """Called when file is manually saved."""
        self.modified = False
        self.last_change_time = None

    def on_file_close(self, filepath: str) -> None:
        """Called when file is closed."""
        self.modified = False
        self.last_change_time = None
        if self.timer_id:
            try:
                self.editor.root.after_cancel(self.timer_id)
            except:
                pass
