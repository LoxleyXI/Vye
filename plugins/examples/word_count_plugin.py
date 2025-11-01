"""
Example Word Count Plugin for Vye Editor

Demonstrates UI extension by adding a word count
to the status bar.
"""

from vye.plugins.base import Plugin


class WordCountPlugin(Plugin):
    """
    Displays word and character count in the status bar.

    This plugin demonstrates:
    - UI extension
    - Text analysis
    - Real-time updates
    """

    name = "Word Count"
    version = "1.0.0"
    author = "Vye Team"
    description = "Displays word and character count in status bar"

    def __init__(self, editor):
        super().__init__(editor)
        self.update_delay = 500  # milliseconds
        self.timer_id = None

    def activate(self) -> bool:
        """Activate the plugin and add UI elements."""
        print(f"[{self.name}] Activated")

        # Schedule regular updates
        self._schedule_update()

        self.enabled = True
        return True

    def deactivate(self) -> bool:
        """Deactivate the plugin and remove UI elements."""
        if self.timer_id:
            try:
                self.editor.root.after_cancel(self.timer_id)
            except:
                pass

        print(f"[{self.name}] Deactivated")
        self.enabled = False
        return True

    def _schedule_update(self) -> None:
        """Schedule the next update."""
        if self.enabled:
            self._update_count()
            self.timer_id = self.editor.root.after(
                self.update_delay,
                self._schedule_update
            )

    def _update_count(self) -> None:
        """Update word and character counts."""
        if not hasattr(self.editor, 'text'):
            return

        try:
            # Get text content
            content = self.editor.text.get("1.0", "end-1c")

            # Count words and characters
            words = len(content.split())
            chars = len(content)
            chars_no_spaces = len(content.replace(" ", "").replace("\n", "").replace("\t", ""))

            # Update status bar
            count_text = f" | Words: {words} | Chars: {chars} ({chars_no_spaces} no spaces)"

            # If editor has a status bar, update it
            if hasattr(self.editor, 'status_label'):
                current_text = self.editor.status_label.cget("text")
                # Remove old count if present
                if " | Words:" in current_text:
                    current_text = current_text.split(" | Words:")[0]
                self.editor.status_label.config(text=current_text + count_text)

        except Exception as e:
            print(f"[{self.name}] Error updating count: {e}")
