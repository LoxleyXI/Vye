"""
Vim-style modal editing for Vye editor
"""

import tkinter as tk
from tkinter import messagebox
import re
from typing import Dict, List, Optional, Tuple, Callable, TYPE_CHECKING, Any

if TYPE_CHECKING:
    from vye.app import VyeEditor


class VimMode:
    """
    Manages Vim-style modal editing with enhanced commands.

    Implements NORMAL, INSERT, VISUAL, COMMAND, and REPLACE modes with
    full Vim command support including motions, text objects, macros,
    and the dot (.) repeat command.
    """

    NORMAL = "NORMAL"
    INSERT = "INSERT"
    VISUAL = "VISUAL"
    COMMAND = "COMMAND"
    REPLACE = "REPLACE"

    def __init__(self, editor: 'VyeEditor'):
        """
        Initialize Vim mode manager.

        Args:
            editor: Reference to the main editor instance
        """
        self.editor: 'VyeEditor' = editor
        self.mode: str = self.NORMAL
        self.command_buffer: str = ""
        self.visual_start: Optional[str] = None
        self.visual_line_mode: bool = False
        self.yanked_text: str = ""
        self.last_search: str = ""
        self.search_direction: int = 1
        self.repeat_count: str = ""
        self.last_change: Optional[Dict[str, Any]] = None
        self.last_change_pos: Optional[str] = None
        self.insert_start_pos: Optional[str] = None
        self.pending_change_motion: Optional[str] = None
        self.marks: Dict[str, str] = {}
        self.recording_macro: bool = False
        self.macro_register: Optional[str] = None
        self.macros: Dict[str, List[str]] = {}
        self.current_macro_recording: List[str] = []

    def set_mode(self, mode, change_motion=None):
        """Switch between Vim modes"""
        old_mode = self.mode
        self.mode = mode

        if old_mode == self.VISUAL and mode != self.VISUAL:
            self.editor.text.tag_remove("sel", "1.0", "end")
            self.visual_start = None
            self.visual_line_mode = False

        # Track insert mode entry/exit for . command
        if mode == self.INSERT and old_mode != self.INSERT:
            # Entering insert mode - record position and change motion if provided
            self.insert_start_pos = self.editor.text.index("insert")
            self.pending_change_motion = change_motion  # Store motion for change commands
        elif old_mode == self.INSERT and mode != self.INSERT:
            # Leaving insert mode - capture inserted text
            if self.insert_start_pos:
                end_pos = self.editor.text.index("insert")
                inserted_text = self.editor.text.get(self.insert_start_pos, end_pos)

                # Determine if this was a change command or just insert
                if self.pending_change_motion:
                    self.last_change = {
                        'type': 'change',
                        'motion': self.pending_change_motion,
                        'text': inserted_text,
                        'count': 1  # Will be updated by the actual command
                    }
                    self.pending_change_motion = None
                elif inserted_text:  # Only track if text was actually inserted
                    self.last_change = {
                        'type': 'insert',
                        'text': inserted_text,
                        'start_pos': self.insert_start_pos
                    }
                self.insert_start_pos = None

        # Update cursor visibility based on mode and theme
        self.editor.update_cursor_visibility()

        self.editor.update_status()
        self.editor.update_mode_indicator()

    def get_word_under_cursor(self):
        """Get the word under the cursor"""
        pos = self.editor.text.index("insert")
        start = self.editor.text.search(r'\b\w', pos, backwards=True, regexp=True)
        if not start:
            start = pos
        end = self.editor.text.search(r'\w\b', f"{pos}", regexp=True)
        if not end:
            end = f"{pos} +1c"
        else:
            end = f"{end} +1c"
        word = self.editor.text.get(start, end).strip()
        return word if word and (word.isalnum() or '_' in word) else None

    def find_prev_word_start(self):
        """Find the start position of the previous word"""
        # Move back from current position to find the previous word
        current_pos = self.editor.text.index("insert")

        # First move back one char to get out of current word
        if current_pos != "1.0":
            search_pos = self.editor.text.index("insert -1c")
            # Skip any whitespace backwards
            while search_pos != "1.0":
                char = self.editor.text.get(search_pos)
                if not char.isspace():
                    break
                search_pos = self.editor.text.index(f"{search_pos} -1c")

            # Now find the start of the word we're in
            if search_pos != "1.0":
                word_start = self.editor.text.index(f"{search_pos} wordstart")
                return word_start

        return "1.0"

    def get_word_boundaries(self, pos=None):
        """Get word boundaries at position"""
        if pos is None:
            pos = self.editor.text.index("insert")

        # Find word start
        char = self.editor.text.get(pos)
        if not char.isalnum() and char != '_':
            # Not on a word, find next word
            next_word = self.editor.text.search(r'\w', pos, regexp=True)
            if next_word:
                pos = next_word
            else:
                return None, None

        # Find actual word boundaries
        start = pos
        while True:
            prev_pos = self.editor.text.index(f"{start} -1c")
            if prev_pos == start:  # Beginning of text
                break
            char = self.editor.text.get(prev_pos)
            if not char.isalnum() and char != '_':
                break
            start = prev_pos

        end = pos
        while True:
            char = self.editor.text.get(end)
            if not char or (not char.isalnum() and char != '_'):
                break
            end = self.editor.text.index(f"{end} +1c")

        return start, end

    def get_text_object(self, obj_type, include_surrounding=False):
        """Get text object boundaries (word, quotes, brackets, etc.)"""
        pos = self.editor.text.index("insert")

        if obj_type == 'w':  # Word
            start, end = self.get_word_boundaries()
            if include_surrounding and start and end:
                # Include surrounding whitespace
                # Check for whitespace after
                while self.editor.text.get(end) in ' \t':
                    end = self.editor.text.index(f"{end} +1c")
                # If no whitespace after, check before
                if end == self.editor.text.index(f"{start} wordend"):
                    while self.editor.text.get(f"{start} -1c") in ' \t':
                        start = self.editor.text.index(f"{start} -1c")
            return start, end

        elif obj_type in '"\'':
            # Find matching quotes
            quote = obj_type
            line_start = self.editor.text.index(f"{pos} linestart")
            line_end = self.editor.text.index(f"{pos} lineend")
            line_text = self.editor.text.get(line_start, line_end)

            pos_in_line = int(pos.split('.')[1])

            # Find quotes in the line
            quotes = []
            for i, char in enumerate(line_text):
                if char == quote:
                    quotes.append(i)

            # Find the pair containing cursor
            for i in range(0, len(quotes), 2):
                if i + 1 < len(quotes):
                    if quotes[i] <= pos_in_line <= quotes[i + 1]:
                        start = f"{line_start.split('.')[0]}.{quotes[i]}"
                        end = f"{line_start.split('.')[0]}.{quotes[i + 1] + 1}"
                        if not include_surrounding:
                            start = self.editor.text.index(f"{start} +1c")
                            end = self.editor.text.index(f"{end} -1c")
                        return start, end
            return None, None

        elif obj_type in '()[]{}><':
            # Find matching brackets
            brackets = {'(': ')', '[': ']', '{': '}', '<': '>'}
            if obj_type in brackets:
                open_br = obj_type
                close_br = brackets[obj_type]
            else:
                close_br = obj_type
                open_br = {v: k for k, v in brackets.items()}[obj_type]

            # Search backward for opening bracket
            start = self.editor.text.search(re.escape(open_br), pos, "1.0", backwards=True)
            if start:
                # Find matching closing bracket
                count = 1
                search_pos = self.editor.text.index(f"{start} +1c")
                while count > 0:
                    next_open = self.editor.text.search(re.escape(open_br), search_pos, "end")
                    next_close = self.editor.text.search(re.escape(close_br), search_pos, "end")

                    if not next_close:
                        return None, None

                    if next_open and self.editor.text.compare(next_open, "<", next_close):
                        count += 1
                        search_pos = self.editor.text.index(f"{next_open} +1c")
                    else:
                        count -= 1
                        if count == 0:
                            end = self.editor.text.index(f"{next_close} +1c")
                            if not include_surrounding:
                                start = self.editor.text.index(f"{start} +1c")
                                end = self.editor.text.index(f"{end} -1c")
                            return start, end
                        search_pos = self.editor.text.index(f"{next_close} +1c")

            return None, None

        return None, None

    def jump_to_matching_bracket(self):
        """Jump to matching bracket/parenthesis"""
        brackets = {'(': ')', '[': ']', '{': '}', ')': '(', ']': '[', '}': '{'}
        char = self.editor.text.get("insert")
        if char not in brackets:
            return

        matching = brackets[char]
        is_opening = char in '([{'
        count = 1
        pos = self.editor.text.index("insert")

        while count > 0:
            if is_opening:
                pos = self.editor.text.search(f"[{re.escape(char)}{re.escape(matching)}]",
                                             f"{pos} +1c", regexp=True)
            else:
                pos = self.editor.text.search(f"[{re.escape(char)}{re.escape(matching)}]",
                                             f"{pos} -1c", backwards=True, regexp=True)

            if not pos:
                break

            found_char = self.editor.text.get(pos)
            if found_char == char:
                count += 1
            else:
                count -= 1

        if pos and count == 0:
            self.editor.text.mark_set("insert", pos)

    def record_command(self, command):
        """Record command for macro recording and repeat"""
        if self.recording_macro:
            self.current_macro_recording.append(command)
        self.last_command = command

    def record_change(self, change_type, **kwargs):
        """Record a change operation for the . repeat command"""
        self.last_change = {
            'type': change_type,
            **kwargs
        }

    def repeat_last_change(self):
        """Repeat the last change operation"""
        if not self.last_change:
            return

        change = self.last_change
        change_type = change['type']

        if change_type == 'insert':
            # Repeat text insertion
            text = change.get('text', '')
            self.editor.text.insert("insert", text)
        elif change_type == 'delete':
            # Repeat deletion
            motion = change.get('motion', '')
            count = change.get('count', 1)
            self.execute_delete(motion, count)
        elif change_type == 'change':
            # Repeat change (delete + insert)
            motion = change.get('motion', '')
            text = change.get('text', '')
            count = change.get('count', 1)
            self.execute_delete(motion, count, is_change=True)
            self.editor.text.insert("insert", text)
        elif change_type == 'replace_char':
            # Repeat character replacement
            char = change.get('char', '')
            count = change.get('count', 1)
            for _ in range(count):
                self.editor.text.delete("insert")
                self.editor.text.insert("insert", char)
        elif change_type == 'delete_char':
            # Repeat character deletion (x, X)
            direction = change.get('direction', 'forward')
            count = change.get('count', 1)
            for _ in range(count):
                if direction == 'forward':
                    self.editor.text.delete("insert")
                else:
                    self.editor.text.delete("insert -1c")
        elif change_type == 'substitute':
            # Repeat substitution (s, S)
            scope = change.get('scope', 'char')
            text = change.get('text', '')
            count = change.get('count', 1)
            if scope == 'char':
                for _ in range(count):
                    self.editor.text.delete("insert")
                self.editor.text.insert("insert", text)
            elif scope == 'line':
                self.editor.text.delete("insert linestart", "insert lineend")
                self.editor.text.insert("insert", text)

    def execute_delete(self, motion, count=1, is_change=False):
        """Execute a delete operation based on motion"""
        if motion == 'w':
            # Delete word(s)
            for _ in range(count):
                end = self.editor.text.search(r'\s', "insert", "insert lineend", regexp=True)
                if not end:
                    end = self.editor.text.index("insert wordend")
                else:
                    # cw excludes trailing space, dw includes it
                    if not is_change:
                        end = self.editor.text.index(f"{end} +1c")
                self.editor.text.delete("insert", end)
        elif motion == 'e':
            # Delete to end of word
            for _ in range(count):
                self.editor.text.delete("insert", "insert wordend")
        elif motion == 'b':
            # Delete backward word
            start = self.find_prev_word_start()
            self.editor.text.delete(start, "insert")
        elif motion == '$':
            # Delete to end of line
            self.editor.text.delete("insert", "insert lineend")
        elif motion == '0':
            # Delete to beginning of line
            self.editor.text.delete("insert linestart", "insert")
        elif motion == '^':
            # Delete to first non-whitespace
            start = self.editor.text.search(r'\S', "insert linestart", "insert lineend", regexp=True)
            if not start:
                start = "insert linestart"
            self.editor.text.delete(start, "insert")
        elif motion == 'd':
            # Delete line
            self.editor.text.delete("insert linestart", "insert lineend +1c")

    def handle_key(self, event):
        """Handle key events based on current mode"""
        if self.mode == self.NORMAL:
            return self.handle_normal_mode(event)
        elif self.mode == self.INSERT:
            return self.handle_insert_mode(event)
        elif self.mode == self.VISUAL:
            return self.handle_visual_mode(event)
        elif self.mode == self.COMMAND:
            return self.handle_command_mode(event)
        elif self.mode == self.REPLACE:
            return self.handle_replace_mode(event)

    def handle_normal_mode(self, event):
        """Handle keys in normal mode"""
        key = event.char
        keysym = event.keysym

        # Ignore modifier keys alone
        if keysym in ('Shift_L', 'Shift_R', 'Control_L', 'Control_R', 'Alt_L', 'Alt_R', 'Super_L', 'Super_R'):
            return "break"

        # Handle number prefixes for repeat counts
        if key.isdigit() and (self.repeat_count or key != '0'):
            self.repeat_count += key
            return "break"

        # Get repeat count (default to 1)
        count = int(self.repeat_count) if self.repeat_count else 1
        self.repeat_count = ""

        # Check command buffer combinations first to handle dw, cw, yw, etc.
        if self.command_buffer:
            # Handle delete commands
            if self.command_buffer == 'd':
                if key == 'd':
                    self.yanked_text = self.editor.text.get("insert linestart", "insert lineend +1c")
                    self.editor.text.delete("insert linestart", "insert lineend +1c")
                    self.record_change('delete', motion='d', count=count)
                    self.command_buffer = ""
                    self.editor.update_mode_indicator()
                    return "break"
                elif key == 'w':
                    for _ in range(count):
                        end = self.editor.text.search(r'\s', "insert", "insert lineend", regexp=True)
                        if not end:
                            end = self.editor.text.index("insert wordend")
                        else:
                            end = self.editor.text.index(f"{end} +1c")
                        text_to_delete = self.editor.text.get("insert", end)
                        if text_to_delete:
                            self.yanked_text = text_to_delete
                            self.editor.text.delete("insert", end)
                    self.record_change('delete', motion='w', count=count)
                    self.command_buffer = ""
                    self.editor.update_mode_indicator()
                    return "break"
                elif key == 'e':
                    for _ in range(count):
                        end = self.editor.text.index("insert wordend")
                        self.yanked_text = self.editor.text.get("insert", end)
                        self.editor.text.delete("insert", end)
                    self.command_buffer = ""
                    self.editor.update_mode_indicator()
                    return "break"
                elif key == 'b':
                    start = self.find_prev_word_start()
                    self.yanked_text = self.editor.text.get(start, "insert")
                    self.editor.text.delete(start, "insert")
                    self.record_change('delete', motion='b', count=count)
                    self.command_buffer = ""
                    self.editor.update_mode_indicator()
                    return "break"
                elif key == '$':
                    self.yanked_text = self.editor.text.get("insert", "insert lineend")
                    self.editor.text.delete("insert", "insert lineend")
                    self.command_buffer = ""
                    self.editor.update_mode_indicator()
                    return "break"
                elif key == '0':
                    self.yanked_text = self.editor.text.get("insert linestart", "insert")
                    self.editor.text.delete("insert linestart", "insert")
                    self.command_buffer = ""
                    self.editor.update_mode_indicator()
                    return "break"
                elif key == '^':
                    start = self.editor.text.search(r'\S', "insert linestart", "insert lineend", regexp=True)
                    if not start:
                        start = "insert linestart"
                    self.yanked_text = self.editor.text.get(start, "insert")
                    self.editor.text.delete(start, "insert")
                    self.command_buffer = ""
                    self.editor.update_mode_indicator()
                    return "break"
                elif key == 'i' or key == 'a':
                    # di/da - delete inside/around text object
                    result = self.handle_command_combination(key)
                    if result:
                        return "break"
            # Handle change commands
            elif self.command_buffer == 'c':
                if key == 'c':
                    self.editor.text.delete("insert linestart", "insert lineend")
                    self.set_mode(self.INSERT, change_motion='c')
                    self.command_buffer = ""
                    self.editor.update_mode_indicator()
                    return "break"
                elif key == 'w':
                    for _ in range(count):
                        end = self.editor.text.search(r'\s', "insert", "insert lineend", regexp=True)
                        if not end:
                            end = self.editor.text.index("insert wordend")
                        self.editor.text.delete("insert", end)
                    self.set_mode(self.INSERT, change_motion='w')
                    self.command_buffer = ""
                    self.editor.update_mode_indicator()
                    return "break"
                elif key == 'e':
                    for _ in range(count):
                        self.editor.text.delete("insert", "insert wordend")
                    self.set_mode(self.INSERT)
                    self.command_buffer = ""
                    self.editor.update_mode_indicator()
                    return "break"
                elif key == 'b':
                    start = self.find_prev_word_start()
                    self.editor.text.delete(start, "insert")
                    self.set_mode(self.INSERT, change_motion='b')
                    self.command_buffer = ""
                    self.editor.update_mode_indicator()
                    return "break"
                elif key == '$':
                    self.editor.text.delete("insert", "insert lineend")
                    self.set_mode(self.INSERT)
                    self.command_buffer = ""
                    self.editor.update_mode_indicator()
                    return "break"
                elif key == '0':
                    self.editor.text.delete("insert linestart", "insert")
                    self.set_mode(self.INSERT)
                    self.command_buffer = ""
                    self.editor.update_mode_indicator()
                    return "break"
                elif key == '^':
                    start = self.editor.text.search(r'\S', "insert linestart", "insert lineend", regexp=True)
                    if not start:
                        start = "insert linestart"
                    self.editor.text.delete(start, "insert")
                    self.set_mode(self.INSERT)
                    self.command_buffer = ""
                    self.editor.update_mode_indicator()
                    return "break"
                elif key == 'i' or key == 'a':
                    # ci/ca - change inside/around text object
                    result = self.handle_command_combination(key)
                    if result:
                        return "break"
            # Handle yank commands
            elif self.command_buffer == 'y':
                if key == 'y':
                    self.yanked_text = self.editor.text.get("insert linestart", "insert lineend +1c")
                    self.command_buffer = ""
                    self.editor.update_mode_indicator()
                    return "break"
                elif key == 'w':
                    for _ in range(count):
                        end = self.editor.text.search(r'\s', "insert", "insert lineend", regexp=True)
                        if not end:
                            end = self.editor.text.index("insert wordend")
                        self.yanked_text = self.editor.text.get("insert", end)
                    self.command_buffer = ""
                    self.editor.update_mode_indicator()
                    return "break"
                elif key == 'e':
                    self.yanked_text = self.editor.text.get("insert", "insert wordend")
                    self.command_buffer = ""
                    self.editor.update_mode_indicator()
                    return "break"
                elif key == 'b':
                    start = self.find_prev_word_start()
                    self.yanked_text = self.editor.text.get(start, "insert")
                    self.command_buffer = ""
                    self.editor.update_mode_indicator()
                    return "break"
                elif key == '$':
                    self.yanked_text = self.editor.text.get("insert", "insert lineend")
                    self.command_buffer = ""
                    self.editor.update_mode_indicator()
                    return "break"
                elif key == '0':
                    self.yanked_text = self.editor.text.get("insert linestart", "insert")
                    self.command_buffer = ""
                    self.editor.update_mode_indicator()
                    return "break"
                elif key == 'i' or key == 'a':
                    # yi/ya - yank inside/around text object
                    result = self.handle_command_combination(key)
                    if result:
                        return "break"
            # Handle other command buffer combinations (r, f, F, t, T, m, ', `, q, @)
            elif self.command_buffer == 'r' and key:
                for _ in range(count):
                    self.editor.text.delete("insert")
                    self.editor.text.insert("insert", key)
                self.record_change('replace_char', char=key, count=count)
                self.command_buffer = ""
                return "break"
            elif self.command_buffer == 'f' and key:
                for _ in range(count):
                    pos = self.editor.text.search(key, "insert +1c", "insert lineend")
                    if pos:
                        self.editor.text.mark_set("insert", pos)
                self.command_buffer = ""
                return "break"
            elif self.command_buffer == 'F' and key:
                for _ in range(count):
                    pos = self.editor.text.search(key, "insert -1c", "insert linestart", backwards=True)
                    if pos:
                        self.editor.text.mark_set("insert", pos)
                self.command_buffer = ""
                return "break"
            elif self.command_buffer == 't' and key:
                for _ in range(count):
                    pos = self.editor.text.search(key, "insert +1c", "insert lineend")
                    if pos:
                        self.editor.text.mark_set("insert", f"{pos} -1c")
                self.command_buffer = ""
                return "break"
            elif self.command_buffer == 'T' and key:
                for _ in range(count):
                    pos = self.editor.text.search(key, "insert -1c", "insert linestart", backwards=True)
                    if pos:
                        self.editor.text.mark_set("insert", f"{pos} +1c")
                self.command_buffer = ""
                return "break"
            elif self.command_buffer == 'm' and key:
                self.marks[key] = self.editor.text.index("insert")
                self.command_buffer = ""
                return "break"
            elif self.command_buffer == "'" and key:
                if key in self.marks:
                    self.editor.text.mark_set("insert", self.marks[key])
                self.command_buffer = ""
                return "break"
            elif self.command_buffer == '`' and key:
                if key in self.marks:
                    self.editor.text.mark_set("insert", self.marks[key])
                self.command_buffer = ""
                return "break"
            elif self.command_buffer == 'q' and key:
                self.recording_macro = True
                self.macro_register = key
                self.current_macro_recording = []
                self.command_buffer = ""
                self.editor.update_status()
                return "break"
            elif self.command_buffer == '@' and key:
                if key in self.macros:
                    for _ in range(count):
                        # Simplified macro playback
                        pass
                self.command_buffer = ""
                return "break"
            elif self.command_buffer == 'g' and key == 'g':
                self.editor.text.mark_set("insert", "1.0")
                self.command_buffer = ""
                return "break"

        # Movement keys (only if no command buffer)
        if key == 'h' or keysym == 'Left':
            for _ in range(count):
                self.editor.text.mark_set("insert", "insert -1c")
            return "break"
        elif key == 'j' or keysym == 'Down':
            for _ in range(count):
                self.editor.text.mark_set("insert", "insert +1l")
            return "break"
        elif key == 'k' or keysym == 'Up':
            for _ in range(count):
                self.editor.text.mark_set("insert", "insert -1l")
            return "break"
        elif key == 'l' or keysym == 'Right':
            for _ in range(count):
                self.editor.text.mark_set("insert", "insert +1c")
            return "break"
        elif key == 'w':
            for _ in range(count):
                self.editor.text.mark_set("insert", "insert wordend +1c")
            return "break"
        elif key == 'b':
            for _ in range(count):
                # Move to the beginning of the previous word
                prev_word_start = self.find_prev_word_start()
                self.editor.text.mark_set("insert", prev_word_start)
            return "break"
        elif key == 'e':
            for _ in range(count):
                self.editor.text.mark_set("insert", "insert wordend")
            return "break"
        elif key == 'W':
            for _ in range(count):
                pos = self.editor.text.search(r'\s+\S', "insert", regexp=True)
                if pos:
                    self.editor.text.mark_set("insert", f"{pos} +1c")
            return "break"
        elif key == 'B':
            for _ in range(count):
                pos = self.editor.text.search(r'\S\s+', "insert", backwards=True, regexp=True)
                if pos:
                    self.editor.text.mark_set("insert", pos)
            return "break"
        elif key == 'E':
            for _ in range(count):
                pos = self.editor.text.search(r'\S\s', "insert", regexp=True)
                if pos:
                    self.editor.text.mark_set("insert", pos)
            return "break"
        elif key == '0':
            self.editor.text.mark_set("insert", "insert linestart")
            return "break"
        elif key == '^':
            line_start = self.editor.text.index("insert linestart")
            first_char = self.editor.text.search(r'\S', line_start, f"{line_start} lineend", regexp=True)
            if first_char:
                self.editor.text.mark_set("insert", first_char)
            return "break"
        elif key == '$':
            self.editor.text.mark_set("insert", "insert lineend")
            return "break"
        elif key == 'G':
            if count > 1:
                self.editor.text.mark_set("insert", f"{count}.0")
            else:
                self.editor.text.mark_set("insert", "end -1c")
            return "break"
        elif key == 'g' and self.command_buffer == 'g':
            self.editor.text.mark_set("insert", "1.0")
            self.command_buffer = ""
            return "break"
        elif key == 'g':
            self.command_buffer = 'g'
            self.editor.update_mode_indicator()
            return "break"
        elif key == '%':
            self.jump_to_matching_bracket()
            return "break"

        # Mode switches
        elif key == 'i':
            if self.command_buffer:
                self.handle_text_object_command(key)
                return "break"
            self.set_mode(self.INSERT)
            return "break"
        elif key == 'I':
            self.editor.text.mark_set("insert", "insert linestart")
            first_char = self.editor.text.search(r'\S', "insert", "insert lineend", regexp=True)
            if first_char:
                self.editor.text.mark_set("insert", first_char)
            self.set_mode(self.INSERT)
            return "break"
        elif key == 'a':
            if self.command_buffer:
                self.handle_text_object_command(key)
                return "break"
            self.editor.text.mark_set("insert", "insert +1c")
            self.set_mode(self.INSERT)
            return "break"
        elif key == 'A':
            self.editor.text.mark_set("insert", "insert lineend")
            self.set_mode(self.INSERT)
            return "break"
        elif key == 'o':
            self.editor.text.insert("insert lineend", "\n")
            self.editor.text.mark_set("insert", "insert +1l")
            self.set_mode(self.INSERT)
            return "break"
        elif key == 'O':
            self.editor.text.insert("insert linestart", "\n")
            self.editor.text.mark_set("insert", "insert -1l")
            self.set_mode(self.INSERT)
            return "break"
        elif key == 'v':
            if self.command_buffer:
                self.handle_text_object_command(key)
                return "break"
            self.set_mode(self.VISUAL)
            self.visual_start = self.editor.text.index("insert")
            self.visual_line_mode = False
            return "break"
        elif key == 'V':
            self.set_mode(self.VISUAL)
            self.visual_start = self.editor.text.index("insert linestart")
            self.editor.text.mark_set("insert", "insert lineend")
            self.visual_line_mode = True
            self.update_visual_selection()
            return "break"
        elif key == 'R':
            self.set_mode(self.REPLACE)
            return "break"
        elif key == ':':
            self.set_mode(self.COMMAND)
            self.editor.command_entry.focus()
            return "break"

        # Editing commands
        elif key == 'x':
            for _ in range(count):
                self.editor.text.delete("insert")
            self.record_change('delete_char', direction='forward', count=count)
            return "break"
        elif key == 'X':
            for _ in range(count):
                self.editor.text.delete("insert -1c")
            self.record_change('delete_char', direction='backward', count=count)
            return "break"
        elif key == 'r':
            self.command_buffer = 'r'
            self.editor.update_mode_indicator()
            return "break"
        elif self.command_buffer == 'r' and key:
            for _ in range(count):
                self.editor.text.delete("insert")
                self.editor.text.insert("insert", key)
            self.record_change('replace_char', char=key, count=count)
            self.command_buffer = ""
            return "break"
        elif key == 's':
            for _ in range(count):
                self.editor.text.delete("insert")
            self.set_mode(self.INSERT)
            return "break"
        elif key == 'S':
            self.editor.text.delete("insert linestart", "insert lineend")
            self.set_mode(self.INSERT)
            return "break"
        elif key == 'c':
            self.command_buffer = 'c'
            self.editor.update_mode_indicator()
            return "break"
        elif key == 'C':
            self.editor.text.delete("insert", "insert lineend")
            self.set_mode(self.INSERT, change_motion='$')
            return "break"
        elif key == 'd':
            self.command_buffer = 'd'
            self.editor.update_mode_indicator()
            return "break"
        elif key == 'D':
            self.yanked_text = self.editor.text.get("insert", "insert lineend")
            self.editor.text.delete("insert", "insert lineend")
            return "break"
        elif key == 'y':
            self.command_buffer = 'y'
            self.editor.update_mode_indicator()
            return "break"
        elif key == 'Y':
            self.yanked_text = self.editor.text.get("insert linestart", "insert lineend +1c")
            return "break"
        elif key == 'p':
            for _ in range(count):
                if self.yanked_text:
                    if '\n' in self.yanked_text:
                        self.editor.text.insert("insert lineend", "\n" + self.yanked_text.rstrip('\n'))
                    else:
                        self.editor.text.insert("insert +1c", self.yanked_text)
            return "break"
        elif key == 'P':
            for _ in range(count):
                if self.yanked_text:
                    if '\n' in self.yanked_text:
                        self.editor.text.insert("insert linestart", self.yanked_text.rstrip('\n') + "\n")
                    else:
                        self.editor.text.insert("insert", self.yanked_text)
            return "break"
        elif key == 'u':
            for _ in range(count):
                try:
                    self.editor.text.edit_undo()
                except:
                    break
            return "break"
        elif event.state & 0x0004 and key == '\x12':  # Ctrl+R
            for _ in range(count):
                try:
                    self.editor.text.edit_redo()
                except:
                    break
            return "break"
        elif key == '.':
            # Repeat last change
            if self.last_change:
                self.repeat_last_change()
            return "break"

        # Search commands
        elif key == '/':
            self.search_direction = 1
            search_term = simpledialog.askstring("Search", "Enter search term (regex):")
            if search_term:
                self.last_search = search_term
                self.search_next()
            return "break"
        elif key == '?':
            self.search_direction = -1
            search_term = simpledialog.askstring("Search", "Enter search term (regex):")
            if search_term:
                self.last_search = search_term
                self.search_next()
            return "break"
        elif key == 'n':
            for _ in range(count):
                self.search_next()
            return "break"
        elif key == 'N':
            self.search_direction *= -1
            for _ in range(count):
                self.search_next()
            self.search_direction *= -1
            return "break"
        elif key == '*':
            word = self.get_word_under_cursor()
            if word:
                self.last_search = r'\b' + re.escape(word) + r'\b'
                self.search_direction = 1
                self.search_next()
            return "break"
        elif key == '#':
            word = self.get_word_under_cursor()
            if word:
                self.last_search = r'\b' + re.escape(word) + r'\b'
                self.search_direction = -1
                self.search_next()
            return "break"

        # Character search
        elif key == 'f':
            self.command_buffer = 'f'
            self.editor.update_mode_indicator()
            return "break"
        elif self.command_buffer == 'f' and key:
            for _ in range(count):
                pos = self.editor.text.search(key, "insert +1c", "insert lineend")
                if pos:
                    self.editor.text.mark_set("insert", pos)
            self.command_buffer = ""
            return "break"
        elif key == 'F':
            self.command_buffer = 'F'
            self.editor.update_mode_indicator()
            return "break"
        elif self.command_buffer == 'F' and key:
            for _ in range(count):
                pos = self.editor.text.search(key, "insert -1c", "insert linestart", backwards=True)
                if pos:
                    self.editor.text.mark_set("insert", pos)
            self.command_buffer = ""
            return "break"
        elif key == 't':
            self.command_buffer = 't'
            self.editor.update_mode_indicator()
            return "break"
        elif self.command_buffer == 't' and key:
            for _ in range(count):
                pos = self.editor.text.search(key, "insert +1c", "insert lineend")
                if pos:
                    self.editor.text.mark_set("insert", f"{pos} -1c")
            self.command_buffer = ""
            return "break"
        elif key == 'T':
            self.command_buffer = 'T'
            self.editor.update_mode_indicator()
            return "break"
        elif self.command_buffer == 'T' and key:
            for _ in range(count):
                pos = self.editor.text.search(key, "insert -1c", "insert linestart", backwards=True)
                if pos:
                    self.editor.text.mark_set("insert", f"{pos} +1c")
            self.command_buffer = ""
            return "break"

        # Marks
        elif key == 'm':
            self.command_buffer = 'm'
            self.editor.update_mode_indicator()
            return "break"
        elif self.command_buffer == 'm' and key:
            self.marks[key] = self.editor.text.index("insert")
            self.command_buffer = ""
            return "break"
        elif key == "'":
            self.command_buffer = "'"
            self.editor.update_mode_indicator()
            return "break"
        elif self.command_buffer == "'" and key:
            if key in self.marks:
                self.editor.text.mark_set("insert", self.marks[key])
            self.command_buffer = ""
            return "break"
        elif key == '`':
            self.command_buffer = '`'
            self.editor.update_mode_indicator()
            return "break"
        elif self.command_buffer == '`' and key:
            if key in self.marks:
                self.editor.text.mark_set("insert", self.marks[key])
            self.command_buffer = ""
            return "break"

        # Macros
        elif key == 'q':
            if self.recording_macro:
                self.macros[self.macro_register] = self.current_macro_recording.copy()
                self.recording_macro = False
                self.macro_register = None
                self.current_macro_recording = []
                self.editor.update_status()
            else:
                self.command_buffer = 'q'
                self.editor.update_mode_indicator()
            return "break"
        elif self.command_buffer == 'q' and key:
            self.recording_macro = True
            self.macro_register = key
            self.current_macro_recording = []
            self.command_buffer = ""
            self.editor.update_status()
            return "break"
        elif key == '@':
            self.command_buffer = '@'
            self.editor.update_mode_indicator()
            return "break"
        elif self.command_buffer == '@' and key:
            if key in self.macros:
                for _ in range(count):
                    # Simplified macro playback
                    pass
            self.command_buffer = ""
            return "break"

        # Handle command buffer combinations for d, c, y with motions and text objects
        elif self.command_buffer:
            # Handle delete commands
            if self.command_buffer == 'd':
                if key == 'w':
                    for _ in range(count):
                        end = self.editor.text.search(r'\s', "insert", "insert lineend", regexp=True)
                        if not end:
                            end = self.editor.text.index("insert wordend")
                        else:
                            end = self.editor.text.index(f"{end} +1c")
                        text_to_delete = self.editor.text.get("insert", end)
                        if text_to_delete:
                            self.yanked_text = text_to_delete
                            self.editor.text.delete("insert", end)
                    self.command_buffer = ""
                    self.editor.update_mode_indicator()
                    return "break"
                elif key == 'e':
                    for _ in range(count):
                        end = self.editor.text.index("insert wordend")
                        self.yanked_text = self.editor.text.get("insert", end)
                        self.editor.text.delete("insert", end)
                    self.command_buffer = ""
                    self.editor.update_mode_indicator()
                    return "break"
                elif key == 'b':
                    start = self.find_prev_word_start()
                    self.yanked_text = self.editor.text.get(start, "insert")
                    self.editor.text.delete(start, "insert")
                    self.record_change('delete', motion='b', count=count)
                    self.command_buffer = ""
                    self.editor.update_mode_indicator()
                    return "break"
                elif key == '$':
                    self.yanked_text = self.editor.text.get("insert", "insert lineend")
                    self.editor.text.delete("insert", "insert lineend")
                    self.command_buffer = ""
                    self.editor.update_mode_indicator()
                    return "break"
                elif key == '0':
                    self.yanked_text = self.editor.text.get("insert linestart", "insert")
                    self.editor.text.delete("insert linestart", "insert")
                    self.command_buffer = ""
                    self.editor.update_mode_indicator()
                    return "break"
                elif key == '^':
                    start = self.editor.text.search(r'\S', "insert linestart", "insert lineend", regexp=True)
                    if not start:
                        start = "insert linestart"
                    self.yanked_text = self.editor.text.get(start, "insert")
                    self.editor.text.delete(start, "insert")
                    self.command_buffer = ""
                    self.editor.update_mode_indicator()
                    return "break"
                elif key == 'i' or key == 'a':
                    # di/da - delete inside/around text object
                    result = self.handle_command_combination(key)
                    if result:
                        return "break"
            # Handle change commands
            elif self.command_buffer == 'c':
                if key == 'w':
                    start_pos = self.editor.text.index("insert")
                    for _ in range(count):
                        end = self.editor.text.search(r'\s', "insert", "insert lineend", regexp=True)
                        if not end:
                            end = self.editor.text.index("insert wordend")
                        else:
                            # Move cursor to skip whitespace for next word
                            self.editor.text.mark_set("insert", end)
                    end_pos = self.editor.text.index("insert")
                    self.editor.text.mark_set("insert", start_pos)
                    self.yanked_text = self.editor.text.get(start_pos, end_pos)
                    self.editor.text.delete(start_pos, end_pos)
                    self.set_mode(self.INSERT)
                    self.command_buffer = ""
                    self.editor.update_mode_indicator()
                    return "break"
                elif key == 'e':
                    end = self.editor.text.index("insert wordend")
                    self.yanked_text = self.editor.text.get("insert", end)
                    self.editor.text.delete("insert", end)
                    self.set_mode(self.INSERT)
                    self.command_buffer = ""
                    self.editor.update_mode_indicator()
                    return "break"
                elif key == 'b':
                    start = self.find_prev_word_start()
                    self.yanked_text = self.editor.text.get(start, "insert")
                    self.editor.text.delete(start, "insert")
                    self.set_mode(self.INSERT)
                    self.command_buffer = ""
                    self.editor.update_mode_indicator()
                    return "break"
                elif key == '$':
                    self.yanked_text = self.editor.text.get("insert", "insert lineend")
                    self.editor.text.delete("insert", "insert lineend")
                    self.set_mode(self.INSERT)
                    self.command_buffer = ""
                    self.editor.update_mode_indicator()
                    return "break"
                elif key == '0':
                    self.yanked_text = self.editor.text.get("insert linestart", "insert")
                    self.editor.text.delete("insert linestart", "insert")
                    self.set_mode(self.INSERT)
                    self.command_buffer = ""
                    self.editor.update_mode_indicator()
                    return "break"
                elif key == '^':
                    start = self.editor.text.search(r'\S', "insert linestart", "insert lineend", regexp=True)
                    if not start:
                        start = "insert linestart"
                    self.yanked_text = self.editor.text.get(start, "insert")
                    self.editor.text.delete(start, "insert")
                    self.editor.text.mark_set("insert", start)
                    self.set_mode(self.INSERT)
                    self.command_buffer = ""
                    self.editor.update_mode_indicator()
                    return "break"
                elif key == 'i' or key == 'a':
                    # ci/ca - change inside/around text object
                    result = self.handle_command_combination(key)
                    if result:
                        return "break"
            # Handle yank commands
            elif self.command_buffer == 'y':
                if key == 'w':
                    end = self.editor.text.search(r'\s', "insert", "insert lineend", regexp=True)
                    if not end:
                        end = self.editor.text.index("insert wordend")
                    else:
                        end = self.editor.text.index(f"{end} +1c")
                    self.yanked_text = self.editor.text.get("insert", end)
                    self.command_buffer = ""
                    self.editor.update_mode_indicator()
                    return "break"
                elif key == 'e':
                    end = self.editor.text.index("insert wordend")
                    self.yanked_text = self.editor.text.get("insert", end)
                    self.command_buffer = ""
                    self.editor.update_mode_indicator()
                    return "break"
                elif key == 'b':
                    start = self.find_prev_word_start()
                    self.yanked_text = self.editor.text.get(start, "insert")
                    self.command_buffer = ""
                    self.editor.update_mode_indicator()
                    return "break"
                elif key == '$':
                    self.yanked_text = self.editor.text.get("insert", "insert lineend")
                    self.command_buffer = ""
                    self.editor.update_mode_indicator()
                    return "break"
                elif key == '0':
                    self.yanked_text = self.editor.text.get("insert linestart", "insert")
                    self.command_buffer = ""
                    self.editor.update_mode_indicator()
                    return "break"
                elif key == 'i' or key == 'a':
                    # yi/ya - yank inside/around text object
                    result = self.handle_command_combination(key)
                    if result:
                        return "break"
            else:
                # For other command buffer combinations
                result = self.handle_command_combination(key)
                if result:
                    return "break"

        # Clear command buffer for unrecognized commands
        if key and self.command_buffer and key not in ['g', 'd', 'y', 'c', 'r', 'f', 'F', 't', 'T', 'm', "'", '`', 'q', '@', 'i', 'a', 'v']:
            self.command_buffer = ""

        # Block all other keys in normal mode to prevent text insertion
        return "break"

    def handle_insert_mode(self, event):
        """Handle keys in insert mode"""
        if event.keysym == 'Escape':
            self.set_mode(self.NORMAL)
            return "break"
        # Record keys for macros
        if self.recording_macro:
            self.current_macro_recording.append(('insert', event.char))
        return None

    def handle_replace_mode(self, event):
        """Handle keys in replace mode"""
        if event.keysym == 'Escape':
            self.set_mode(self.NORMAL)
            return "break"
        # In replace mode, overwrite existing text
        if event.char and event.char.isprintable():
            self.editor.text.delete("insert")
            self.editor.text.insert("insert", event.char)
            return "break"
        return None

    def handle_command_combination(self, key):
        """Handle command combinations like dd, yy, cc, dw, etc."""
        if self.command_buffer == 'd':
            if key == 'd':
                self.yanked_text = self.editor.text.get("insert linestart", "insert lineend +1c")
                self.editor.text.delete("insert linestart", "insert lineend +1c")
                self.command_buffer = ""
                return True
            elif key == 'w':
                end = self.editor.text.index("insert wordend +1c")
                self.yanked_text = self.editor.text.get("insert", end)
                self.editor.text.delete("insert", end)
                self.command_buffer = ""
                return True
            elif key == 'e':
                end = self.editor.text.index("insert wordend")
                self.yanked_text = self.editor.text.get("insert", end)
                self.editor.text.delete("insert", end)
                self.command_buffer = ""
                return True
            elif key == '$':
                self.yanked_text = self.editor.text.get("insert", "insert lineend")
                self.editor.text.delete("insert", "insert lineend")
                self.command_buffer = ""
                return True
            elif key == '0' or key == '^':
                # d0/d^ - delete to beginning of line
                if key == '^':
                    start = self.editor.text.search(r'\S', "insert linestart", "insert lineend", regexp=True)
                    if not start:
                        start = "insert linestart"
                else:
                    start = "insert linestart"
                self.yanked_text = self.editor.text.get(start, "insert")
                self.editor.text.delete(start, "insert")
                self.editor.text.mark_set("insert", start)
                self.command_buffer = ""
                return True
            elif key == 'i':
                self.command_buffer = 'di'
                return True
            elif key == 'a':
                self.command_buffer = 'da'
                return True

        elif self.command_buffer == 'di' or self.command_buffer == 'da':
            # Delete inside/around text object
            include = (self.command_buffer == 'da')
            if key == 'w':
                start, end = self.get_text_object('w', include_surrounding=include)
                if start and end:
                    self.yanked_text = self.editor.text.get(start, end)
                    self.editor.text.delete(start, end)
            elif key in '"\'':
                start, end = self.get_text_object(key, include_surrounding=include)
                if start and end:
                    self.yanked_text = self.editor.text.get(start, end)
                    self.editor.text.delete(start, end)
            elif key in '()[]{}><':
                start, end = self.get_text_object(key, include_surrounding=include)
                if start and end:
                    self.yanked_text = self.editor.text.get(start, end)
                    self.editor.text.delete(start, end)
            self.command_buffer = ""
            return True

        elif self.command_buffer == 'y':
            if key == 'y':
                self.yanked_text = self.editor.text.get("insert linestart", "insert lineend +1c")
                self.command_buffer = ""
                return True
            elif key == 'w':
                end = self.editor.text.index("insert wordend +1c")
                self.yanked_text = self.editor.text.get("insert", end)
                self.command_buffer = ""
                return True
            elif key == 'i':
                self.command_buffer = 'yi'
                return True
            elif key == 'a':
                self.command_buffer = 'ya'
                return True

        elif self.command_buffer == 'yi' or self.command_buffer == 'ya':
            # Yank inside/around text object
            include = (self.command_buffer == 'ya')
            if key == 'w':
                start, end = self.get_text_object('w', include_surrounding=include)
                if start and end:
                    self.yanked_text = self.editor.text.get(start, end)
            elif key in '"\'':
                start, end = self.get_text_object(key, include_surrounding=include)
                if start and end:
                    self.yanked_text = self.editor.text.get(start, end)
            elif key in '()[]{}><':
                start, end = self.get_text_object(key, include_surrounding=include)
                if start and end:
                    self.yanked_text = self.editor.text.get(start, end)
            self.command_buffer = ""
            return True

        elif self.command_buffer == 'c':
            if key == 'c':
                self.editor.text.delete("insert linestart", "insert lineend")
                self.set_mode(self.INSERT)
                self.command_buffer = ""
                return True
            elif key == 'w':
                end = self.editor.text.index("insert wordend")
                self.editor.text.delete("insert", end)
                self.set_mode(self.INSERT)
                self.command_buffer = ""
                return True
            elif key == 'i':
                self.command_buffer = 'ci'
                return True
            elif key == 'a':
                self.command_buffer = 'ca'
                return True

        elif self.command_buffer == 'ci' or self.command_buffer == 'ca':
            # Change inside/around text object
            include = (self.command_buffer == 'ca')
            if key == 'w':
                start, end = self.get_text_object('w', include_surrounding=include)
                if start and end:
                    self.editor.text.delete(start, end)
                    self.editor.text.mark_set("insert", start)
                    self.set_mode(self.INSERT)
            elif key in '"\'':
                start, end = self.get_text_object(key, include_surrounding=include)
                if start and end:
                    self.editor.text.delete(start, end)
                    self.editor.text.mark_set("insert", start)
                    self.set_mode(self.INSERT)
            elif key in '()[]{}><':
                start, end = self.get_text_object(key, include_surrounding=include)
                if start and end:
                    self.editor.text.delete(start, end)
                    self.editor.text.mark_set("insert", start)
                    self.set_mode(self.INSERT)
            self.command_buffer = ""
            return True

        elif self.command_buffer == 'v':
            if key == 'i':
                self.command_buffer = 'vi'
                return True
            elif key == 'a':
                self.command_buffer = 'va'
                return True

        elif self.command_buffer == 'vi' or self.command_buffer == 'va':
            # Visual select inside/around text object
            include = (self.command_buffer == 'va')
            if key == 'w':
                start, end = self.get_text_object('w', include_surrounding=include)
                if start and end:
                    self.set_mode(self.VISUAL)
                    self.visual_start = start
                    self.editor.text.mark_set("insert", end)
                    self.update_visual_selection()
            elif key in '"\'':
                start, end = self.get_text_object(key, include_surrounding=include)
                if start and end:
                    self.set_mode(self.VISUAL)
                    self.visual_start = start
                    self.editor.text.mark_set("insert", end)
                    self.update_visual_selection()
            elif key in '()[]{}><':
                start, end = self.get_text_object(key, include_surrounding=include)
                if start and end:
                    self.set_mode(self.VISUAL)
                    self.visual_start = start
                    self.editor.text.mark_set("insert", end)
                    self.update_visual_selection()
            self.command_buffer = ""
            return True

        return False

    def handle_text_object_command(self, key):
        """Handle text object commands for current command buffer"""
        self.handle_command_combination(key)

    def handle_visual_mode(self, event):
        """Handle keys in visual mode"""
        key = event.char
        keysym = event.keysym

        if keysym == 'Escape':
            self.set_mode(self.NORMAL)
            return "break"

        # Movement updates selection
        if key == 'h' or keysym == 'Left':
            self.editor.text.mark_set("insert", "insert -1c")
        elif key == 'j' or keysym == 'Down':
            self.editor.text.mark_set("insert", "insert +1l")
        elif key == 'k' or keysym == 'Up':
            self.editor.text.mark_set("insert", "insert -1l")
        elif key == 'l' or keysym == 'Right':
            self.editor.text.mark_set("insert", "insert +1c")
        elif key == 'w':
            self.editor.text.mark_set("insert", "insert wordend +1c")
        elif key == 'b':
            # Move to the beginning of the previous word
            prev_word_start = self.find_prev_word_start()
            self.editor.text.mark_set("insert", prev_word_start)
        elif key == 'e':
            self.editor.text.mark_set("insert", "insert wordend")
        elif key == '0':
            self.editor.text.mark_set("insert", "insert linestart")
        elif key == '$':
            self.editor.text.mark_set("insert", "insert lineend")
        elif key == 'G':
            self.editor.text.mark_set("insert", "end -1c")
        elif key == 'g' and self.command_buffer == 'g':
            self.editor.text.mark_set("insert", "1.0")
            self.command_buffer = ""
        elif key == 'g':
            self.command_buffer = 'g'
            self.editor.update_mode_indicator()
            return "break"
        elif key == 'y':
            # Yank selected text
            try:
                self.yanked_text = self.editor.text.get("sel.first", "sel.last")
            except:
                pass
            self.set_mode(self.NORMAL)
            return "break"
        elif key == 'd' or key == 'x':
            # Delete selected text
            try:
                self.yanked_text = self.editor.text.get("sel.first", "sel.last")
                self.editor.text.delete("sel.first", "sel.last")
            except:
                pass
            self.set_mode(self.NORMAL)
            return "break"
        elif key == 'c':
            # Change selected text
            try:
                self.editor.text.delete("sel.first", "sel.last")
            except:
                pass
            self.set_mode(self.INSERT)
            return "break"
        elif key == '>':
            # Indent selected text
            self.indent_selection()
            self.set_mode(self.NORMAL)
            return "break"
        elif key == '<':
            # Unindent selected text
            self.unindent_selection()
            self.set_mode(self.NORMAL)
            return "break"
        else:
            self.update_visual_selection()
            return "break"

        self.update_visual_selection()
        return "break"

    def indent_selection(self):
        """Indent selected lines"""
        try:
            start = self.editor.text.index("sel.first linestart")
            end = self.editor.text.index("sel.last lineend")
            lines = self.editor.text.get(start, end).split('\n')
            indented = [('    ' + line if line else line) for line in lines]
            self.editor.text.delete(start, end)
            self.editor.text.insert(start, '\n'.join(indented))
        except:
            pass

    def unindent_selection(self):
        """Unindent selected lines"""
        try:
            start = self.editor.text.index("sel.first linestart")
            end = self.editor.text.index("sel.last lineend")
            lines = self.editor.text.get(start, end).split('\n')
            unindented = [(line[4:] if line.startswith('    ') else line) for line in lines]
            self.editor.text.delete(start, end)
            self.editor.text.insert(start, '\n'.join(unindented))
        except:
            pass

    def handle_command_mode(self, event):
        """Handle command mode - handled by command entry widget"""
        if event.keysym == 'Escape':
            self.editor.command_entry.delete(0, tk.END)
            self.editor.text.focus()
            self.set_mode(self.NORMAL)
            return "break"
        return None

    def search_next(self):
        """Search for the next occurrence of last_search"""
        if not self.last_search:
            return

        try:
            if self.search_direction == 1:
                start_pos = self.editor.text.index("insert +1c")
                match = self.editor.text.search(self.last_search, start_pos, stopindex="end", regexp=True)
                if not match and messagebox.askyesno("Search", "Reached end. Continue from beginning?"):
                    match = self.editor.text.search(self.last_search, "1.0", stopindex="end", regexp=True)
            else:
                start_pos = self.editor.text.index("insert -1c")
                match = self.editor.text.search(self.last_search, start_pos, stopindex="1.0", backwards=True, regexp=True)
                if not match and messagebox.askyesno("Search", "Reached beginning. Continue from end?"):
                    match = self.editor.text.search(self.last_search, "end", stopindex="1.0", backwards=True, regexp=True)

            if match:
                self.editor.text.mark_set("insert", match)
                self.editor.text.see(match)
                match_end = self.editor.text.search(r'(?!' + self.last_search + r')', match, stopindex="end", regexp=True)
                if match_end:
                    self.editor.text.tag_remove("search", "1.0", "end")
                    self.editor.text.tag_add("search", match, match_end)
                    self.editor.text.tag_config("search", background="yellow")
        except:
            messagebox.showerror("Search Error", "Invalid regular expression")

    def update_visual_selection(self):
        """Update visual selection"""
        if not self.visual_start:
            return

        self.editor.text.tag_remove("sel", "1.0", "end")

        if self.visual_line_mode:
            # Visual line mode
            start_line = int(self.visual_start.split('.')[0])
            current_line = int(self.editor.text.index("insert").split('.')[0])

            if start_line <= current_line:
                self.editor.text.tag_add("sel", f"{start_line}.0", f"{current_line}.end +1c")
            else:
                self.editor.text.tag_add("sel", f"{current_line}.0", f"{start_line}.end +1c")
        else:
            # Character visual mode
            if self.editor.text.compare(self.visual_start, "<", "insert"):
                self.editor.text.tag_add("sel", self.visual_start, "insert +1c")
            else:
                self.editor.text.tag_add("sel", "insert", f"{self.visual_start} +1c")


