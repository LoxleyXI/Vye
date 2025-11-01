"""
Main Vye editor application
"""

import tkinter as tk
from tkinter import ttk, filedialog, messagebox, simpledialog
import json
import re
import os
from pathlib import Path
from typing import Dict, List, Tuple, Optional, Any
import sys

from vye.core.vim_mode import VimMode
from vye.core.syntax import SyntaxHighlighter
from vye.core.themes import ColorScheme
from vye.core.regex_mgr import RegexManager
from vye.plugins.loader import PluginLoader
from vye.utils.file_utils import load_json, save_json, ensure_dir_exists

class VyeEditor:
    """
    Main Vye editor application.

    A flexible and lightweight cross-platform modal text editor with
    Vim-style editing, syntax highlighting, and extensible plugin system.
    """

    def __init__(self, root: tk.Tk):
        """
        Initialize the Vye editor.

        Args:
            root: The Tkinter root window
        """
        self.root = root
        self.root.title("Vye")
        self.root.geometry("1200x800")

        # Set window icon
        try:
            icon_path = Path(__file__).parent.parent / "assets" / "icon.png"
            if icon_path.exists():
                icon = tk.PhotoImage(file=str(icon_path))
                self.root.iconphoto(True, icon)
        except Exception:
            pass

        # Tab management
        self.tabs = {}  # Dictionary to store tab data
        self.current_tab = None
        self.tab_counter = 0

        # Whitespace visibility
        self.show_whitespace = True  # Default to showing whitespace

        # Indentation settings
        self.tabs_to_spaces = True  # Default to converting tabs to spaces
        self.tab_size = 4  # Default tab size

        # Recent files list (max 10)
        self.recent_files = []
        self.max_recent_files = 10
        self.load_recent_files()

        # Project view
        self.project_root = None
        self.show_project_view = False

        # GUI Theme settings
        self.gui_themes = {
            "dark": {
                "bg": "#2b2b2b",
                "fg": "#ffffff",
                "select_bg": "#404040",
                "tab_bg": "#1e1e1e",
                "active_tab_bg": "#404040",  # More contrast for selected tab
                "menu_bg": "#2b2b2b",
                "menu_fg": "#ffffff",
                "menu_active_bg": "#404040",
                "menu_select_color": "#ffffff",  # White checkmark background for visibility
                "scrollbar_bg": "#3c3c3c",
                "scrollbar_fg": "#606060",
                "line_num_bg": "#1e1e1e",
                "line_num_fg": "#a0a0a0",  # Lighter text for better visibility
                "border_color": "#1e1e1e",  # Dark border color
                "whitespace_fg": "#333333",  # Very subtle whitespace color
                "current_line_bg": "#323232"  # Slightly lighter background for current line
            },
            "light": {
                "bg": "#f5f5f5",
                "fg": "#000000",
                "select_bg": "#e0e0e0",
                "tab_bg": "#e8e8e8",
                "active_tab_bg": "#ffffff",
                "menu_bg": "#f0f0f0",
                "menu_fg": "#000000",
                "menu_active_bg": "#d0d0d0",
                "menu_select_color": "#ffffff",  # White checkmark background
                "scrollbar_bg": "#e0e0e0",
                "scrollbar_fg": "#a0a0a0",
                "line_num_bg": "#f0f0f0",
                "line_num_fg": "#808080",
                "border_color": "#d0d0d0",  # Light border color
                "whitespace_fg": "#e0e0e0",  # Very subtle whitespace color
                "current_line_bg": "#f8f8f8"  # Slightly lighter background for current line
            }
        }
        self.current_gui_theme = "dark"

        # Apply default GUI theme BEFORE creating UI
        self.setup_gui_theme_style()

        # Setup UI first (creates notebook)
        self.setup_ui()

        # Setup shared components
        self.setup_regex_manager()
        self.setup_color_schemes()

        # Populate menus
        self.populate_syntax_menu()
        self.populate_theme_menu()
        self.populate_gui_theme_menu()
        self.populate_regex_menu()

        # Create initial tab
        self.new_tab()

        # Apply GUI theme to configure colors
        self.apply_gui_theme("dark")

        # Apply default color scheme
        self.color_scheme.apply_scheme("dark")

    def setup_gui_theme_style(self):
        """Setup initial GUI theme style"""
        theme = self.gui_themes[self.current_gui_theme]
        style = ttk.Style()

        # Set the theme base
        try:
            if self.current_gui_theme == "dark":
                style.theme_use('clam')  # Better for dark themes
            else:
                style.theme_use('default')
        except:
            pass

        # Configure notebook (tabs) style
        style.configure('TNotebook',
                       background=theme['bg'],
                       borderwidth=0,
                       highlightthickness=0,
                       tabmargins=0)
        style.configure('TNotebook.Tab',
                       background=theme['tab_bg'],
                       foreground=theme['fg'],
                       padding=[12, 8],
                       borderwidth=0,
                       focuscolor='none')
        style.map('TNotebook.Tab',
                 background=[('selected', theme['active_tab_bg'])],
                 foreground=[('selected', theme['fg'])])  # Removed expand to keep same size

        # Configure frames
        style.configure('TFrame',
                       background=theme['bg'],
                       borderwidth=0)

        # Configure treeview for project explorer
        style.configure('Treeview',
                       background=theme['bg'],
                       foreground=theme['fg'],
                       fieldbackground=theme['bg'],
                       borderwidth=0)
        style.map('Treeview',
                 background=[('selected', theme['active_tab_bg'])],
                 foreground=[('selected', theme['fg'])])
        style.configure('Treeview.Heading',
                       background=theme['tab_bg'],
                       foreground=theme['fg'],
                       borderwidth=0)

        # Configure scrollbars with better contrast
        style.configure('Vertical.TScrollbar',
                       background=theme['scrollbar_bg'],
                       darkcolor=theme['scrollbar_fg'],
                       lightcolor=theme['scrollbar_bg'],
                       troughcolor=theme['bg'],
                       bordercolor=theme['bg'],
                       arrowcolor=theme['fg'],
                       borderwidth=0,
                       relief='flat')
        style.configure('Horizontal.TScrollbar',
                       background=theme['scrollbar_bg'],
                       darkcolor=theme['scrollbar_fg'],
                       lightcolor=theme['scrollbar_bg'],
                       troughcolor=theme['bg'],
                       bordercolor=theme['bg'],
                       arrowcolor=theme['fg'],
                       borderwidth=0,
                       relief='flat')

        # Map scrollbar states
        style.map('Vertical.TScrollbar',
                 background=[('active', theme['scrollbar_fg']),
                           ('pressed', theme['select_bg'])])
        style.map('Horizontal.TScrollbar',
                 background=[('active', theme['scrollbar_fg']),
                           ('pressed', theme['select_bg'])])

    def setup_ui(self):
        """Setup the user interface"""
        # Configure menu colors based on theme
        theme = self.gui_themes[self.current_gui_theme]

        # Menu bar
        menubar = tk.Menu(self.root,
                         bg=theme['menu_bg'],
                         fg=theme['menu_fg'],
                         activebackground=theme['menu_active_bg'],
                         activeforeground=theme['menu_fg'],
                         borderwidth=0,
                         activeborderwidth=0,
                         relief='flat')
        self.root.config(menu=menubar)

        # File menu
        file_menu = tk.Menu(menubar, tearoff=0,
                           bg=theme['menu_bg'], fg=theme['menu_fg'],
                           activebackground=theme['menu_active_bg'],
                           activeforeground=theme['menu_fg'],
                           borderwidth=0, activeborderwidth=0, relief='flat')
        menubar.add_cascade(label="File", menu=file_menu)
        file_menu.add_command(label="New", command=self.new_file, accelerator="Ctrl+N")
        file_menu.add_command(label="Open", command=self.open_file, accelerator="Ctrl+O")
        file_menu.add_command(label="Open Directory", command=self.open_directory)
        file_menu.add_separator()

        # Recent files submenu
        self.recent_menu = tk.Menu(file_menu, tearoff=0,
                                  bg=theme['menu_bg'], fg=theme['menu_fg'],
                                  activebackground=theme['menu_active_bg'],
                                  activeforeground=theme['menu_fg'],
                                  borderwidth=0, activeborderwidth=0, relief='flat')
        file_menu.add_cascade(label="Recent Files", menu=self.recent_menu)
        self.update_recent_files_menu()

        file_menu.add_separator()
        file_menu.add_command(label="Save", command=self.save_file, accelerator="Ctrl+S")
        file_menu.add_command(label="Save As", command=self.save_as_file)
        file_menu.add_separator()
        file_menu.add_command(label="Exit", command=self.quit_editor)

        # Edit menu
        edit_menu = tk.Menu(menubar, tearoff=0,
                           bg=theme['menu_bg'], fg=theme['menu_fg'],
                           activebackground=theme['menu_active_bg'],
                           activeforeground=theme['menu_fg'],
                           borderwidth=0, activeborderwidth=0, relief='flat')
        menubar.add_cascade(label="Edit", menu=edit_menu)
        edit_menu.add_command(label="Undo", command=self.undo, accelerator="Ctrl+Z")
        edit_menu.add_command(label="Redo", command=self.redo, accelerator="Ctrl+Y")
        edit_menu.add_separator()
        edit_menu.add_command(label="Find", command=self.find_dialog, accelerator="Ctrl+F")
        edit_menu.add_command(label="Replace", command=self.replace_dialog, accelerator="Ctrl+H")

        # Syntax menu
        self.syntax_menu = tk.Menu(menubar, tearoff=0,
                                  bg=theme['menu_bg'], fg=theme['menu_fg'],
                                  activebackground=theme['menu_active_bg'],
                                  activeforeground=theme['menu_fg'],
                           borderwidth=0, activeborderwidth=0, relief='flat')
        menubar.add_cascade(label="Syntax", menu=self.syntax_menu)

        # Regex menu
        self.regex_menu = tk.Menu(menubar, tearoff=0,
                                 bg=theme['menu_bg'], fg=theme['menu_fg'],
                                 activebackground=theme['menu_active_bg'],
                                 activeforeground=theme['menu_fg'],
                           borderwidth=0, activeborderwidth=0, relief='flat')
        menubar.add_cascade(label="Regex", menu=self.regex_menu)

        # View menu
        view_menu = tk.Menu(menubar, tearoff=0,
                           bg=theme['menu_bg'], fg=theme['menu_fg'],
                           activebackground=theme['menu_active_bg'],
                           activeforeground=theme['menu_fg'],
                           borderwidth=0, activeborderwidth=0, relief='flat')
        menubar.add_cascade(label="View", menu=view_menu)
        # Create BooleanVars for checkbuttons
        self.show_line_numbers_var = tk.BooleanVar(value=True)
        self.show_whitespace_var = tk.BooleanVar(value=self.show_whitespace)

        view_menu.add_checkbutton(label="Show Line Numbers", variable=self.show_line_numbers_var,
                                  command=self.toggle_line_numbers,
                                  selectcolor=theme.get('menu_select_color', '#ffffff'))
        view_menu.add_checkbutton(label="Show Whitespace", variable=self.show_whitespace_var,
                                  command=self.toggle_whitespace,
                                  selectcolor=theme.get('menu_select_color', '#ffffff'))
        view_menu.add_separator()

        # Indentation settings
        self.tabs_to_spaces_var = tk.BooleanVar(value=self.tabs_to_spaces)
        view_menu.add_checkbutton(label="Convert Tabs to Spaces", variable=self.tabs_to_spaces_var,
                                  command=self.toggle_tabs_to_spaces,
                                  selectcolor=theme.get('menu_select_color', '#ffffff'))

        # Tab size submenu
        tab_size_menu = tk.Menu(view_menu, tearoff=0,
                               bg=theme['menu_bg'], fg=theme['menu_fg'],
                               activebackground=theme['menu_active_bg'],
                               activeforeground=theme['menu_fg'],
                               borderwidth=0, activeborderwidth=0, relief='flat')
        view_menu.add_cascade(label="Tab Size", menu=tab_size_menu)

        # Tab size options with radio buttons
        self.tab_size_var = tk.IntVar(value=self.tab_size)
        for size in [2, 4, 8]:
            tab_size_menu.add_radiobutton(label=f"{size} spaces",
                                         variable=self.tab_size_var,
                                         value=size,
                                         command=lambda s=size: self.set_tab_size(s))
        view_menu.add_separator()

        # Theme submenu
        self.theme_menu = tk.Menu(view_menu, tearoff=0,
                                 bg=theme['menu_bg'], fg=theme['menu_fg'],
                                 activebackground=theme['menu_active_bg'],
                                 activeforeground=theme['menu_fg'],
                           borderwidth=0, activeborderwidth=0, relief='flat')
        view_menu.add_cascade(label="Editor Theme", menu=self.theme_menu)

        # GUI Theme submenu
        self.gui_theme_menu = tk.Menu(view_menu, tearoff=0,
                                      bg=theme['menu_bg'], fg=theme['menu_fg'],
                                      activebackground=theme['menu_active_bg'],
                                      activeforeground=theme['menu_fg'],
                           borderwidth=0, activeborderwidth=0, relief='flat')
        view_menu.add_cascade(label="GUI Theme", menu=self.gui_theme_menu)

        # Main container with paned window for project view
        self.main_paned = tk.PanedWindow(self.root, orient=tk.HORIZONTAL,
                                         bg=theme.get('bg', '#2b2b2b'),
                                         sashwidth=4)
        self.main_paned.pack(fill=tk.BOTH, expand=True)

        # Project view panel (left side)
        self.project_frame = tk.Frame(self.main_paned, bg=theme.get('bg'))
        self.setup_project_view()

        # Main frame for editor (right side)
        self.editor_area = ttk.Frame(self.main_paned)

        # Add frames to paned window (project explorer on left if visible)
        if self.show_project_view:
            self.main_paned.add(self.project_frame, minsize=150, width=180)
        self.main_paned.add(self.editor_area, minsize=400)

        # Notebook widget for tabs
        self.notebook = ttk.Notebook(self.editor_area)
        self.notebook.pack(fill=tk.BOTH, expand=True)
        self.notebook.bind("<<NotebookTabChanged>>", self.on_tab_changed)

        # Enable tab closing with middle click
        self.notebook.bind("<Button-2>", self.on_tab_middle_click)

        # Add keyboard shortcuts for tab navigation
        self.root.bind("<Control-Tab>", lambda e: self.next_tab())
        self.root.bind("<Control-Shift-Tab>", lambda e: self.prev_tab())
        self.root.bind("<Control-t>", lambda e: self.new_tab())
        self.root.bind("<Control-w>", lambda e: self.close_current_tab())
        self.root.bind("<Alt-Key>", self.on_alt_number)  # Alt+1, Alt+2, etc. for tab switching

        # Status bar frame
        status_frame = tk.Frame(self.root, bg="#2d2d2d", height=28)
        status_frame.pack(side=tk.BOTTOM, fill=tk.X)
        status_frame.pack_propagate(False)

        # Mode indicator with colored background
        self.mode_frame = tk.Frame(status_frame, width=110, bg="#4a9eff")
        self.mode_frame.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 1))

        self.mode_label = tk.Label(self.mode_frame, text="NORMAL", fg="white", bg="#4a9eff",
                                   font=("Consolas", 10, "bold"), padx=12)
        self.mode_label.pack(expand=True)

        # Command entry (for Vim command mode)
        self.command_entry = tk.Entry(status_frame, bg="#3d3d3d", fg="white",
                                      insertbackground="white", bd=0,
                                      font=("Consolas", 10))
        self.command_entry.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=6, pady=3)
        self.command_entry.bind('<Return>', self.execute_command)

        # File path indicator
        self.file_path_label = tk.Label(status_frame, text="",
                                        fg="#888888", bg="#2d2d2d", font=("Consolas", 9), padx=8)
        self.file_path_label.pack(side=tk.LEFT, padx=4)

        # Syntax indicator
        self.syntax_label = tk.Label(status_frame, text="Plain Text",
                                     fg="#a0a0a0", bg="#2d2d2d", font=("Consolas", 9), padx=8)
        self.syntax_label.pack(side=tk.RIGHT, padx=4)

        # Status info (line and column)
        self.status_label = tk.Label(status_frame, text="Line 1, Col 1",
                                     fg="#a0a0a0", bg="#2d2d2d", font=("Consolas", 9), padx=8)
        self.status_label.pack(side=tk.RIGHT, padx=8)


    def setup_regex_manager(self):
        """Setup regex pattern manager"""
        self.regex_manager = RegexManager(self)

    def setup_color_schemes(self):
        """Setup color scheme manager"""
        self.color_scheme = ColorScheme(self)

    # Properties for current tab components
    @property
    def text(self):
        """Get current tab's text widget"""
        if self.current_tab and self.current_tab in self.tabs:
            return self.tabs[self.current_tab]['text']
        return None

    @property
    def vim(self):
        """Get current tab's vim mode"""
        if self.current_tab and self.current_tab in self.tabs:
            return self.tabs[self.current_tab]['vim']
        return None

    @property
    def highlighter(self):
        """Get current tab's syntax highlighter"""
        if self.current_tab and self.current_tab in self.tabs:
            return self.tabs[self.current_tab]['highlighter']
        return None

    @property
    def line_numbers(self):
        """Get current tab's line numbers widget"""
        if self.current_tab and self.current_tab in self.tabs:
            return self.tabs[self.current_tab]['line_numbers']
        return None

    @property
    def current_file(self):
        """Get current tab's file path"""
        if self.current_tab and self.current_tab in self.tabs:
            return self.tabs[self.current_tab]['file_path']
        return None

    @current_file.setter
    def current_file(self, value):
        """Set current tab's file path"""
        if self.current_tab and self.current_tab in self.tabs:
            self.tabs[self.current_tab]['file_path'] = value
            self.update_tab_title()

    @property
    def modified(self):
        """Get current tab's modified status"""
        if self.current_tab and self.current_tab in self.tabs:
            return self.tabs[self.current_tab]['modified']
        return False

    @modified.setter
    def modified(self, value):
        """Set current tab's modified status"""
        if self.current_tab and self.current_tab in self.tabs:
            self.tabs[self.current_tab]['modified'] = value
            self.update_tab_title()

    @property
    def show_line_numbers(self):
        """Get current tab's line numbers visibility"""
        if self.current_tab and self.current_tab in self.tabs:
            return self.tabs[self.current_tab].get('show_line_numbers', True)
        return True

    @show_line_numbers.setter
    def show_line_numbers(self, value):
        """Set current tab's line numbers visibility"""
        if self.current_tab and self.current_tab in self.tabs:
            self.tabs[self.current_tab]['show_line_numbers'] = value

    def setup_bindings(self):
        """Setup keyboard bindings"""
        self.root.bind('<Control-n>', lambda e: self.new_file())
        self.root.bind('<Control-o>', lambda e: self.open_file())
        self.root.bind('<Control-s>', lambda e: self.save_file())
        self.root.bind('<Control-z>', lambda e: self.undo())
        self.root.bind('<Control-y>', lambda e: self.redo())
        self.root.bind('<Control-f>', lambda e: self.find_dialog())
        self.root.bind('<Control-h>', lambda e: self.replace_dialog())

    # Tab management methods
    def new_tab(self, file_path=None):
        """Create a new tab"""
        self.tab_counter += 1
        tab_id = f"tab_{self.tab_counter}"

        # Create tab frame
        tab_frame = ttk.Frame(self.notebook)

        # Create tab content
        tab_data = self.create_tab_content(tab_frame, file_path)
        tab_data['frame'] = tab_frame
        tab_data['file_path'] = file_path
        tab_data['modified'] = False

        # Store tab data
        self.tabs[tab_id] = tab_data

        # Add tab to notebook
        title = self.get_tab_title(file_path, False)
        self.notebook.add(tab_frame, text=title)

        # Select the new tab
        self.notebook.select(tab_frame)
        self.current_tab = tab_id

        # Load file if specified
        if file_path and os.path.exists(file_path):
            self.load_file_content(file_path)

        return tab_id

    def create_tab_content(self, parent, file_path=None):
        """Create content for a tab"""
        # Main frame for tab
        main_frame = ttk.Frame(parent)
        main_frame.pack(fill=tk.BOTH, expand=True)

        # Text frame with line numbers
        text_frame = ttk.Frame(main_frame)
        text_frame.pack(fill=tk.BOTH, expand=True)

        # Line numbers
        gui_theme = self.gui_themes.get(self.current_gui_theme, self.gui_themes['dark'])
        line_numbers = tk.Text(text_frame, width=5, padx=3, takefocus=0,
                              state='disabled', wrap='none',
                              bg=gui_theme['line_num_bg'],
                              fg=gui_theme['line_num_fg'],
                              borderwidth=0,
                              highlightthickness=0,
                              relief='flat',
                              font=('Consolas', 10) if sys.platform == 'win32' else ('Monaco', 10) if sys.platform == 'darwin' else ('Monospace', 10))
        line_numbers.pack(side=tk.LEFT, fill=tk.Y)

        # Separator between line numbers and text
        separator = tk.Frame(text_frame, width=1,
                            bg=gui_theme.get('border_color', '#333333'))
        separator.pack(side=tk.LEFT, fill=tk.Y)

        # Main text widget
        text_widget = tk.Text(text_frame, wrap='none', undo=True, maxundo=-1,
                             borderwidth=0,
                             highlightthickness=0,
                             relief='flat',
                             font=('Consolas', 11) if sys.platform == 'win32' else ('Monaco', 11) if sys.platform == 'darwin' else ('Monospace', 11))
        text_widget.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # Scrollbars
        y_scrollbar = ttk.Scrollbar(text_frame, orient=tk.VERTICAL, command=text_widget.yview)
        y_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        text_widget.config(yscrollcommand=y_scrollbar.set)

        x_scrollbar = ttk.Scrollbar(main_frame, orient=tk.HORIZONTAL, command=text_widget.xview)
        x_scrollbar.pack(side=tk.BOTTOM, fill=tk.X)
        text_widget.config(xscrollcommand=x_scrollbar.set)

        # Bind Control shortcuts FIRST (before vim) to ensure they work
        text_widget.bind('<Control-n>', lambda e: (self.new_file(), "break")[1])
        text_widget.bind('<Control-o>', lambda e: (self.open_file(), "break")[1])
        text_widget.bind('<Control-s>', lambda e: (self.save_file(), "break")[1])
        text_widget.bind('<Control-f>', lambda e: (self.find_dialog(), "break")[1])
        text_widget.bind('<Control-h>', lambda e: (self.replace_dialog(), "break")[1])
        text_widget.bind('<Control-z>', lambda e: (self.undo(), "break")[1])
        text_widget.bind('<Control-y>', lambda e: (self.redo(), "break")[1])
        text_widget.bind('<Control-t>', lambda e: (self.new_tab(), "break")[1])
        text_widget.bind('<Control-w>', lambda e: (self.close_current_tab(), "break")[1])

        # Standard text editing shortcuts
        text_widget.bind('<Control-a>', lambda e: (text_widget.tag_add("sel", "1.0", "end"), "break")[1])
        text_widget.bind('<Control-x>', lambda e: (text_widget.event_generate("<<Cut>>"), "break")[1])
        text_widget.bind('<Control-c>', lambda e: (text_widget.event_generate("<<Copy>>"), "break")[1])
        text_widget.bind('<Control-v>', lambda e: (text_widget.event_generate("<<Paste>>"), "break")[1])

        # Setup vim mode for this tab
        vim = VimMode(self)
        text_widget.bind('<Key>', vim.handle_key)

        # Bind Tab and Shift+Tab for indentation (higher priority than vim)
        text_widget.bind('<Tab>', lambda e: self.handle_tab(e))
        text_widget.bind('<Shift-Tab>', lambda e: self.handle_shift_tab(e))

        # Setup syntax highlighter for this tab
        highlighter = SyntaxHighlighter(text_widget, self)
        text_widget.bind('<KeyRelease>', lambda e: self.on_key_release(e))

        # Bind text modified event
        text_widget.bind('<<Modified>>', lambda e: self.on_text_modified(e))
        text_widget.bind('<Configure>', lambda e: self.update_line_numbers())

        # Bind cursor movement events for current line highlighting
        text_widget.bind('<ButtonRelease-1>', lambda e: self.update_status())
        text_widget.bind('<KeyRelease-Up>', lambda e: self.update_status())
        text_widget.bind('<KeyRelease-Down>', lambda e: self.update_status())
        text_widget.bind('<KeyRelease-Left>', lambda e: self.update_status())
        text_widget.bind('<KeyRelease-Right>', lambda e: self.update_status())

        # Apply color scheme to new tab
        if hasattr(self, 'color_scheme') and self.color_scheme.current_scheme_name:
            # Apply general colors
            text_widget.config(
                bg=self.color_scheme.current_scheme.get("background", "#ffffff"),
                fg=self.color_scheme.current_scheme.get("foreground", "#000000"),
                insertbackground=self.color_scheme.current_scheme.get("insertbackground", "#000000"),
                insertwidth=self.color_scheme.current_scheme.get("insertwidth", "2"),
                selectbackground=self.color_scheme.current_scheme.get("selectbackground", "#0078d4"),
                selectforeground=self.color_scheme.current_scheme.get("selectforeground", "#ffffff")
            )
            # Apply syntax tag colors
            for tag in self.color_scheme.ALL_SYNTAX_TAGS:
                if tag in self.color_scheme.current_scheme:
                    text_widget.tag_config(tag, foreground=self.color_scheme.current_scheme[tag])

        return {
            'text': text_widget,
            'line_numbers': line_numbers,
            'vim': vim,
            'highlighter': highlighter,
            'show_line_numbers': True
        }

    def close_tab(self, tab_id=None):
        """Close a tab"""
        if tab_id is None:
            tab_id = self.current_tab

        if not tab_id or tab_id not in self.tabs:
            return

        # Check if file is modified
        if self.tabs[tab_id]['modified']:
            file_name = self.get_tab_title(self.tabs[tab_id]['file_path'], False)
            result = messagebox.askyesnocancel(
                "Save Changes",
                f"Do you want to save changes to {file_name}?"
            )
            if result is True:
                # Save the file
                old_tab = self.current_tab
                self.current_tab = tab_id
                self.save_file()
                self.current_tab = old_tab
            elif result is None:
                # Cancel closing
                return

        # Remove tab from notebook
        tab_frame = self.tabs[tab_id]['frame']
        self.notebook.forget(tab_frame)

        # Remove from tabs dictionary
        del self.tabs[tab_id]

        # If no tabs left, create a new one
        if not self.tabs:
            self.new_tab()

    def close_current_tab(self):
        """Close the current tab"""
        self.close_tab(self.current_tab)

    def on_tab_changed(self, event):
        """Handle tab selection change"""
        selected_tab = self.notebook.select()
        if not selected_tab:
            return

        # Find the tab_id for the selected tab
        for tab_id, tab_data in self.tabs.items():
            if str(tab_data['frame']) == str(selected_tab):
                self.current_tab = tab_id
                self.update_status()
                self.update_mode_indicator()
                break

    def on_tab_middle_click(self, event):
        """Handle middle click on tab to close it"""
        # Get the tab that was clicked
        clicked_tab = self.notebook.tk.call(self.notebook._w, "identify", "tab", event.x, event.y)
        if clicked_tab:
            # Find the tab_id for the clicked tab
            tab_frames = [self.tabs[tid]['frame'] for tid in self.tabs]
            if 0 <= int(clicked_tab) < len(tab_frames):
                clicked_frame = tab_frames[int(clicked_tab)]
                for tab_id, tab_data in self.tabs.items():
                    if tab_data['frame'] == clicked_frame:
                        self.close_tab(tab_id)
                        break

    def next_tab(self):
        """Switch to next tab"""
        tabs = self.notebook.tabs()
        if not tabs:
            return
        current_index = self.notebook.index("current")
        next_index = (current_index + 1) % len(tabs)
        self.notebook.select(tabs[next_index])

    def prev_tab(self):
        """Switch to previous tab"""
        tabs = self.notebook.tabs()
        if not tabs:
            return
        current_index = self.notebook.index("current")
        prev_index = (current_index - 1) % len(tabs)
        self.notebook.select(tabs[prev_index])

    def on_alt_number(self, event):
        """Switch to tab by number (Alt+1, Alt+2, etc.)"""
        if event.char.isdigit():
            tab_num = int(event.char)
            tabs = self.notebook.tabs()
            if 0 < tab_num <= len(tabs):
                self.notebook.select(tabs[tab_num - 1])

    def get_tab_title(self, file_path, modified):
        """Get tab title for a file"""
        if file_path:
            title = os.path.basename(file_path)
        else:
            title = "Untitled"

        if modified:
            title = "*" + title

        return title

    def update_tab_title(self):
        """Update current tab's title"""
        if not self.current_tab or self.current_tab not in self.tabs:
            return

        tab_data = self.tabs[self.current_tab]
        title = self.get_tab_title(tab_data['file_path'], tab_data['modified'])

        # Find tab index
        tab_frame = tab_data['frame']
        tabs = self.notebook.tabs()
        for i, tab in enumerate(tabs):
            if str(tab) == str(tab_frame):
                self.notebook.tab(i, text=title)
                break

        # Update window title as well
        self.update_window_title()

    def update_window_title(self):
        """Update the window title to show current file"""
        if self.current_file:
            filename = os.path.basename(self.current_file)
            modified = " *" if self.modified else ""
            self.root.title(f"Vye - {filename}{modified}")

            # Update file path in status bar
            if hasattr(self, 'file_path_label'):
                # Show relative path if reasonable length, otherwise just filename
                if len(self.current_file) < 60:
                    self.file_path_label.config(text=self.current_file)
                else:
                    # Show .../<last two dirs>/filename
                    parts = Path(self.current_file).parts
                    if len(parts) > 2:
                        short_path = ".../" + "/".join(parts[-2:])
                        self.file_path_label.config(text=short_path)
                    else:
                        self.file_path_label.config(text=filename)
        else:
            self.root.title("Vye")
            if hasattr(self, 'file_path_label'):
                self.file_path_label.config(text="")

    def populate_syntax_menu(self):
        """Populate syntax menu with available languages"""
        # Clear existing menu items
        self.syntax_menu.delete(0, tk.END)

        # Create a variable to track current syntax
        if not hasattr(self, 'current_syntax_var'):
            self.current_syntax_var = tk.StringVar()
            self.current_syntax_var.set("auto")

        self.syntax_menu.add_radiobutton(
            label="Auto Detect",
            variable=self.current_syntax_var,
            value="auto",
            command=self.auto_detect_syntax
        )
        self.syntax_menu.add_separator()

        # Get available languages from SyntaxHighlighter class
        temp_highlighter = SyntaxHighlighter(None)
        languages = sorted(temp_highlighter.get_available_languages())

        for lang in languages:
            # Get the display name from the syntax definition
            if lang in temp_highlighter.syntax_definitions:
                display_name = temp_highlighter.syntax_definitions[lang].get("name", lang)
            else:
                display_name = lang

            self.syntax_menu.add_radiobutton(
                label=display_name,
                variable=self.current_syntax_var,
                value=lang,
                command=lambda l=lang: self.set_syntax(l)
            )

    def populate_gui_theme_menu(self):
        """Populate GUI theme menu"""
        # Clear existing menu items
        self.gui_theme_menu.delete(0, tk.END)

        # Create a variable to track current GUI theme
        if not hasattr(self, 'current_gui_theme_var'):
            self.current_gui_theme_var = tk.StringVar()
            self.current_gui_theme_var.set(self.current_gui_theme)

        # Add GUI theme options
        for theme_name in self.gui_themes.keys():
            self.gui_theme_menu.add_radiobutton(
                label=theme_name.title(),
                variable=self.current_gui_theme_var,
                value=theme_name,
                command=lambda t=theme_name: self.apply_gui_theme(t)
            )

    def apply_gui_theme(self, theme_name):
        """Apply GUI theme to interface elements"""
        if theme_name not in self.gui_themes:
            return

        theme = self.gui_themes[theme_name]
        self.current_gui_theme = theme_name

        # Configure ttk style
        style = ttk.Style()

        # Set the appropriate base theme
        try:
            if theme_name == "dark":
                style.theme_use('clam')
            else:
                style.theme_use('default')
        except:
            pass

        # Configure notebook (tabs)
        style.configure('TNotebook',
                       background=theme['bg'],
                       borderwidth=0,
                       highlightthickness=0,
                       tabmargins=0)
        style.configure('TNotebook.Tab',
                       background=theme['tab_bg'],
                       foreground=theme['fg'],
                       padding=[12, 8],
                       borderwidth=0,
                       focuscolor='none')
        style.map('TNotebook.Tab',
                 background=[('selected', theme['active_tab_bg'])],
                 foreground=[('selected', theme['fg'])])  # Removed expand to keep same size

        # Configure frames
        style.configure('TFrame',
                       background=theme['bg'],
                       borderwidth=0)

        # Configure scrollbars
        style.configure('Vertical.TScrollbar',
                       background=theme['scrollbar_bg'],
                       darkcolor=theme['scrollbar_fg'],
                       lightcolor=theme['scrollbar_bg'],
                       troughcolor=theme['bg'],
                       bordercolor=theme['bg'],
                       arrowcolor=theme['fg'],
                       borderwidth=0,
                       relief='flat')
        style.configure('Horizontal.TScrollbar',
                       background=theme['scrollbar_bg'],
                       darkcolor=theme['scrollbar_fg'],
                       lightcolor=theme['scrollbar_bg'],
                       troughcolor=theme['bg'],
                       bordercolor=theme['bg'],
                       arrowcolor=theme['fg'],
                       borderwidth=0,
                       relief='flat')

        # Map scrollbar states
        style.map('Vertical.TScrollbar',
                 background=[('active', theme['scrollbar_fg']),
                           ('pressed', theme['select_bg'])])
        style.map('Horizontal.TScrollbar',
                 background=[('active', theme['scrollbar_fg']),
                           ('pressed', theme['select_bg'])])

        # Update line numbers for all tabs
        for tab_data in self.tabs.values():
            if 'line_numbers' in tab_data:
                tab_data['line_numbers'].config(
                    bg=theme['line_num_bg'],
                    fg=theme['line_num_fg']
                )

        # Update status bar
        if hasattr(self, 'mode_frame'):
            # Keep mode frame colored based on mode
            pass  # Mode frame color is handled by mode changes

        # Update status bar background
        status_frame = self.mode_frame.master
        if status_frame:
            status_frame.config(bg=theme['bg'])
            # Update other status bar elements
            for widget in status_frame.winfo_children():
                if isinstance(widget, tk.Label) and widget != self.mode_label:
                    widget.config(bg=theme['bg'], fg=theme['fg'])
                elif isinstance(widget, tk.Entry):
                    widget.config(bg=theme['select_bg'], fg=theme['fg'])

        # Update menus (this is limited in tkinter)
        self.root.option_add('*Menu.background', theme['menu_bg'])
        self.root.option_add('*Menu.foreground', theme['menu_fg'])
        self.root.option_add('*Menu.activeBackground', theme['menu_active_bg'])
        self.root.option_add('*Menu.activeForeground', theme['menu_fg'])

    def populate_theme_menu(self):
        """Populate theme menu with available themes"""
        # Clear existing menu items
        self.theme_menu.delete(0, tk.END)

        # Create a variable to track current theme
        if not hasattr(self, 'current_theme_var'):
            self.current_theme_var = tk.StringVar()
            self.current_theme_var.set("dark")  # Default theme

        themes = sorted(self.color_scheme.get_available_themes())
        for theme in themes:
            self.theme_menu.add_radiobutton(
                label=theme.title(),
                variable=self.current_theme_var,
                value=theme,
                command=lambda t=theme: self.change_color_scheme(t)
            )
        self.theme_menu.add_separator()
        self.theme_menu.add_command(label="Load from file...", command=self.load_color_scheme_file)

    def populate_regex_menu(self):
        """Populate regex menu"""
        self.regex_menu.add_command(label="Manage Patterns", command=self.manage_regex_patterns)
        self.regex_menu.add_command(label="Quick Search", command=self.quick_regex_search)
        self.regex_menu.add_separator()
        self.update_regex_menu()

    def set_syntax(self, language):
        """Manually set syntax highlighting language"""
        if self.highlighter.setup_language(language):
            self.highlighter.highlight()
            self.syntax_label.config(text=language.title())
            # Update the menu checkmark
            if hasattr(self, 'current_syntax_var'):
                self.current_syntax_var.set(language)
        else:
            self.syntax_label.config(text="Plain Text")
            if hasattr(self, 'current_syntax_var'):
                self.current_syntax_var.set("plaintext")

    def auto_detect_syntax(self):
        """Auto-detect syntax from file extension"""
        if hasattr(self, 'current_syntax_var'):
            self.current_syntax_var.set("auto")

        if self.current_file:
            language = self.highlighter.detect_language(self.current_file)
            if language:
                self.highlighter.setup_language(language)
                self.highlighter.highlight()
                self.syntax_label.config(text=language.title())
            else:
                self.syntax_label.config(text="Plain Text")
        else:
            self.syntax_label.config(text="Plain Text")

    def on_key_release(self, event):
        """Handle key release events"""
        # Update syntax highlighting for current line
        if self.current_file and self.highlighter.current_language:
            line = self.text.index("insert").split('.')[0]
            self.highlighter.highlight_line(line)

    def on_text_modified(self, event):
        """Handle text modification events"""
        self.modified = True
        self.update_line_numbers()
        self.update_status()

    def update_line_numbers(self, event=None):
        """Update line numbers display"""
        if not self.show_line_numbers:
            return

        self.line_numbers.config(state='normal')
        self.line_numbers.delete('1.0', 'end')

        line_count = int(self.text.index('end-1c').split('.')[0])
        line_numbers_string = '\n'.join(str(i) for i in range(1, line_count + 1))
        self.line_numbers.insert('1.0', line_numbers_string)
        self.line_numbers.config(state='disabled')

    def toggle_line_numbers(self):
        """Toggle line numbers display"""
        self.show_line_numbers = not self.show_line_numbers
        if self.show_line_numbers:
            self.line_numbers.pack(side=tk.LEFT, fill=tk.Y, before=self.text)
            self.update_line_numbers()
        else:
            self.line_numbers.pack_forget()

    def toggle_whitespace(self):
        """Toggle whitespace visibility"""
        self.show_whitespace = not self.show_whitespace
        # Refresh highlighting for all tabs
        for tab_id in self.tabs:
            highlighter = self.tabs[tab_id]['highlighter']
            if highlighter:
                # Re-highlight to apply/remove whitespace
                highlighter.highlight("1.0", "end")

    def toggle_tabs_to_spaces(self):
        """Toggle tabs to spaces conversion"""
        self.tabs_to_spaces = self.tabs_to_spaces_var.get()

    def set_tab_size(self, size):
        """Set the tab size"""
        self.tab_size = size
        # Update tab stops for all text widgets
        for tab_id in self.tabs:
            text_widget = self.tabs[tab_id]['text']
            # Set tab width in characters
            font = text_widget.cget("font")
            tab_width = self.tab_size * 7  # Approximate pixel width per character
            text_widget.config(tabs=(tab_width,))

    def handle_tab(self, event):
        """Handle Tab key press for indentation"""
        if not self.text:
            return "break"

        # Check if there's a selection
        try:
            sel_start = self.text.index("sel.first")
            sel_end = self.text.index("sel.last")
            has_selection = True
        except:
            has_selection = False

        if has_selection:
            # Indent selected lines
            start_line = int(sel_start.split('.')[0])
            end_line = int(sel_end.split('.')[0])

            for line_num in range(start_line, end_line + 1):
                if self.tabs_to_spaces:
                    self.text.insert(f"{line_num}.0", " " * self.tab_size)
                else:
                    self.text.insert(f"{line_num}.0", "\t")

            # Maintain selection
            self.text.tag_add("sel", f"{start_line}.0", f"{end_line}.end")
        else:
            # Insert tab or spaces at cursor position
            if self.tabs_to_spaces:
                # Calculate how many spaces to add to reach next tab stop
                cursor_pos = self.text.index("insert")
                col = int(cursor_pos.split('.')[1])
                spaces_to_add = self.tab_size - (col % self.tab_size)
                self.text.insert("insert", " " * spaces_to_add)
            else:
                self.text.insert("insert", "\t")

        # Update highlighting and whitespace visualization
        if self.highlighter:
            if has_selection:
                # Re-highlight all affected lines
                self.highlighter.highlight(f"{start_line}.0", f"{end_line}.end")
            else:
                # Re-highlight current line
                cursor_pos = self.text.index("insert")
                line_num = cursor_pos.split('.')[0]
                self.highlighter.highlight(f"{line_num}.0", f"{line_num}.end")

        return "break"  # Prevent default tab behavior

    def handle_shift_tab(self, event):
        """Handle Shift+Tab key press for unindentation"""
        if not self.text:
            return "break"

        # Check if there's a selection
        try:
            sel_start = self.text.index("sel.first")
            sel_end = self.text.index("sel.last")
            has_selection = True
        except:
            has_selection = False

        if has_selection:
            # Unindent selected lines
            start_line = int(sel_start.split('.')[0])
            end_line = int(sel_end.split('.')[0])

            for line_num in range(start_line, end_line + 1):
                line_start = f"{line_num}.0"
                line_text = self.text.get(line_start, f"{line_num}.end")

                # Remove leading tab or spaces
                if line_text.startswith("\t"):
                    self.text.delete(line_start, f"{line_num}.1")
                elif line_text.startswith(" "):
                    # Remove up to tab_size spaces
                    spaces_to_remove = 0
                    for i in range(min(self.tab_size, len(line_text))):
                        if line_text[i] == ' ':
                            spaces_to_remove += 1
                        else:
                            break
                    if spaces_to_remove > 0:
                        self.text.delete(line_start, f"{line_num}.{spaces_to_remove}")

            # Maintain selection
            self.text.tag_add("sel", f"{start_line}.0", f"{end_line}.end")
        else:
            # Remove indentation from current line
            cursor_pos = self.text.index("insert")
            line_num = cursor_pos.split('.')[0]
            line_start = f"{line_num}.0"
            line_text = self.text.get(line_start, f"{line_num}.end")

            # Remove leading tab or spaces
            if line_text.startswith("\t"):
                self.text.delete(line_start, f"{line_num}.1")
            elif line_text.startswith(" "):
                # Remove up to tab_size spaces
                spaces_to_remove = 0
                for i in range(min(self.tab_size, len(line_text))):
                    if line_text[i] == ' ':
                        spaces_to_remove += 1
                    else:
                        break
                if spaces_to_remove > 0:
                    self.text.delete(line_start, f"{line_num}.{spaces_to_remove}")

        # Update highlighting and whitespace visualization
        if self.highlighter:
            if has_selection:
                # Re-highlight all affected lines
                self.highlighter.highlight(f"{start_line}.0", f"{end_line}.end")
            else:
                # Re-highlight current line
                cursor_pos = self.text.index("insert")
                line_num = cursor_pos.split('.')[0]
                self.highlighter.highlight(f"{line_num}.0", f"{line_num}.end")

        return "break"  # Prevent default shift+tab behavior

    def apply_whitespace_to_text(self, text_widget, start="1.0", end="end"):
        """Apply visual whitespace indicators with indentation levels and trailing spaces"""
        # Remove existing whitespace and indentation tags
        for tag in text_widget.tag_names():
            if tag.startswith(("whitespace_", "indent_", "trailing_")):
                text_widget.tag_remove(tag, start, end)

        if not self.show_whitespace:
            return

        # Get the GUI theme
        theme = self.gui_themes[self.current_gui_theme]

        # Define colors for different indentation levels (progressive greys with more contrast)
        if self.current_gui_theme == "dark":
            indent_colors = [
                "#303030",  # Level 1 - subtle but visible
                "#383838",  # Level 2
                "#404040",  # Level 3
                "#484848",  # Level 4
                "#505050",  # Level 5
                "#585858",  # Level 6+
            ]
            trailing_color = "#5a2020"  # Red tint for trailing spaces
        else:
            indent_colors = [
                "#f0f0f0",  # Level 1 - subtle but visible
                "#e8e8e8",  # Level 2
                "#e0e0e0",  # Level 3
                "#d8d8d8",  # Level 4
                "#d0d0d0",  # Level 5
                "#c8c8c8",  # Level 6+
            ]
            trailing_color = "#ffb0b0"  # Light red for trailing spaces

        # Process each line
        content = text_widget.get(start, end)
        lines = content.split('\n')

        # Get the actual starting line number
        start_line_num = int(start.split('.')[0]) if '.' in str(start) else 1

        for i, line in enumerate(lines):
            if not line:
                continue

            # Calculate actual line number in the document
            actual_line_num = start_line_num + i

            # Find leading whitespace
            leading_spaces = len(line) - len(line.lstrip(' \t'))

            # Calculate indentation level
            if leading_spaces > 0:
                # Apply indentation highlighting for leading spaces/tabs
                for col in range(leading_spaces):
                    char = line[col]
                    indent_level = col // self.tab_size  # Calculate indent level
                    color_idx = min(indent_level, len(indent_colors) - 1)
                    indent_color = indent_colors[color_idx]

                    pos = f"{actual_line_num}.{col}"
                    next_pos = f"{actual_line_num}.{col + 1}"

                    if char == ' ' or char == '\t':
                        tag_name = f"indent_{actual_line_num}_{col}"
                        text_widget.tag_add(tag_name, pos, next_pos)
                        text_widget.tag_config(tag_name,
                                              background=indent_color,
                                              borderwidth=0)

            # Find and highlight trailing whitespace
            stripped_line = line.rstrip(' \t')
            if len(stripped_line) < len(line):
                # There are trailing spaces
                trailing_start = len(stripped_line)
                for col in range(trailing_start, len(line)):
                    pos = f"{actual_line_num}.{col}"
                    next_pos = f"{actual_line_num}.{col + 1}"
                    tag_name = f"trailing_{actual_line_num}_{col}"
                    text_widget.tag_add(tag_name, pos, next_pos)
                    text_widget.tag_config(tag_name,
                                          background=trailing_color,
                                          borderwidth=0)

    def highlight_current_line(self):
        """Highlight the line where the cursor is"""
        if not self.text:
            return

        # Remove previous current line highlighting
        self.text.tag_remove("current_line", "1.0", "end")

        # Get current cursor position
        cursor_pos = self.text.index("insert")
        line_num = cursor_pos.split('.')[0]

        # Get GUI theme color for current line
        theme = self.gui_themes[self.current_gui_theme]
        current_line_bg = theme.get('current_line_bg', '#323232')

        # Configure and apply the current line tag
        self.text.tag_config("current_line",
                            background=current_line_bg)
        self.text.tag_add("current_line",
                         f"{line_num}.0",
                         f"{line_num}.end+1c")

        # Make sure current line tag has lower priority than syntax highlighting
        self.text.tag_lower("current_line")

    def update_status(self):
        """Update status bar"""
        pos = self.text.index("insert")
        line, col = pos.split('.')
        status_text = f"Line {line}, Col {int(col) + 1}"

        # Add macro recording indicator
        if self.vim.recording_macro:
            status_text += f" | Recording @{self.vim.macro_register}"

        self.status_label.config(text=status_text)

        # Update current line highlighting
        self.highlight_current_line()

    def update_mode_indicator(self):
        """Update the mode indicator with appropriate color"""
        mode = self.vim.mode
        mode_colors = {
            "NORMAL": "#4a9eff",  # Blue
            "INSERT": "#4fc74f",  # Green
            "VISUAL": "#ff9f40",  # Orange
            "COMMAND": "#ff4444", # Red
            "REPLACE": "#ff44ff"  # Magenta
        }

        color = mode_colors.get(mode, "#4a9eff")
        self.mode_frame.config(bg=color)

        # Show command buffer in mode label if present
        mode_text = mode
        if mode == "NORMAL" and self.vim.command_buffer:
            mode_text = f"{mode} [{self.vim.command_buffer}]"
        elif mode == "NORMAL" and self.vim.repeat_count:
            mode_text = f"{mode} [{self.vim.repeat_count}]"

        self.mode_label.config(text=mode_text, bg=color)

    def update_cursor_visibility(self):
        """Update cursor visibility based on theme and mode"""
        if not self.color_scheme.current_scheme_name:
            return

        scheme = self.color_scheme.current_scheme
        mode = self.vim.mode

        # Get background color for contrast
        bg_color = scheme.get("background", "#ffffff")

        # Determine if background is dark or light
        # Convert hex to RGB and calculate luminance
        bg_rgb = tuple(int(bg_color[i:i+2], 16) for i in (1, 3, 5))
        luminance = (0.299 * bg_rgb[0] + 0.587 * bg_rgb[1] + 0.114 * bg_rgb[2]) / 255

        # Set cursor color based on background luminance and mode
        if luminance < 0.5:  # Dark background
            if mode == self.vim.INSERT:
                cursor_color = "#00ff00"  # Bright green for insert
                cursor_width = 2
            elif mode == self.vim.REPLACE:
                cursor_color = "#ff8800"  # Orange for replace
                cursor_width = 4
            elif mode == self.vim.VISUAL:
                cursor_color = "#ffff00"  # Yellow for visual
                cursor_width = 2
            else:  # NORMAL or COMMAND
                cursor_color = "#ffffff"  # White for normal
                cursor_width = 2
        else:  # Light background
            if mode == self.vim.INSERT:
                cursor_color = "#008800"  # Dark green for insert
                cursor_width = 2
            elif mode == self.vim.REPLACE:
                cursor_color = "#cc4400"  # Dark orange for replace
                cursor_width = 4
            elif mode == self.vim.VISUAL:
                cursor_color = "#cc8800"  # Dark yellow for visual
                cursor_width = 2
            else:  # NORMAL or COMMAND
                cursor_color = "#000000"  # Black for normal
                cursor_width = 2

        self.text.config(insertbackground=cursor_color, insertwidth=cursor_width)

    def execute_command(self, event):
        """Execute Vim command"""
        command = self.command_entry.get()
        self.command_entry.delete(0, tk.END)

        if command == 'q':
            self.quit_editor()
        elif command == 'q!':
            self.root.quit()
        elif command == 'w':
            self.save_file()
        elif command == 'wq' or command == 'x':
            self.save_file()
            self.quit_editor()
        elif command.startswith('e '):
            filename = command[2:].strip()
            self.open_file(filename)
        elif command.startswith('s/'):
            # Substitute command
            parts = command.split('/')
            if len(parts) >= 3:
                pattern = parts[1]
                replacement = parts[2] if len(parts) > 2 else ''
                flags = parts[3] if len(parts) > 3 else ''
                self.substitute(pattern, replacement, 'g' in flags)
        elif command.startswith('set syntax='):
            # Set syntax highlighting
            lang = command.split('=')[1].strip()
            self.set_syntax(lang)
        elif command == 'syntax on':
            self.auto_detect_syntax()
        elif command == 'syntax off':
            self.highlighter.current_language = None
            self.highlighter.patterns = {}
            self.syntax_label.config(text="Plain Text")
            # Clear all syntax highlighting
            for tag in self.highlighter.patterns.keys():
                self.text.tag_remove(tag, "1.0", "end")

        self.text.focus()
        self.vim.set_mode(VimMode.NORMAL)

    def substitute(self, pattern, replacement, global_replace=False):
        """Perform regex substitution"""
        try:
            text_content = self.text.get("1.0", "end-1c")
            if global_replace:
                new_content = re.sub(pattern, replacement, text_content)
            else:
                new_content = re.sub(pattern, replacement, text_content, count=1)
            self.text.delete("1.0", "end")
            self.text.insert("1.0", new_content)
        except Exception as e:
            messagebox.showerror("Substitution Error", str(e))

    def new_file(self):
        """Create a new file in a new tab"""
        self.new_tab()

    def open_file(self, filename=None):
        """Open a file in a new tab or existing tab"""
        if not filename:
            filename = filedialog.askopenfilename(
                defaultextension=".txt",
                filetypes=[("All Files", "*.*"), ("Text Files", "*.txt"), ("Python Files", "*.py"),
                          ("JavaScript Files", "*.js"), ("HTML Files", "*.html"), ("CSS Files", "*.css"),
                          ("JSON Files", "*.json"), ("Markdown Files", "*.md")]
            )

        if filename:
            # Check if file is already open in a tab
            for tab_id, tab_data in self.tabs.items():
                if tab_data['file_path'] == filename:
                    # Select the existing tab
                    self.notebook.select(tab_data['frame'])
                    return

            # Check if current tab is unmodified "Untitled" and can be replaced
            if (self.current_tab and
                self.current_tab in self.tabs and
                not self.tabs[self.current_tab]['file_path'] and
                not self.tabs[self.current_tab]['modified'] and
                self.text.get("1.0", "end-1c").strip() == ""):
                # Reuse the current untitled tab
                self.load_file_content(filename)
                self.tabs[self.current_tab]['file_path'] = filename
                # Update tab title
                title = self.get_tab_title(filename, False)
                self.notebook.tab(self.tabs[self.current_tab]['frame'], text=title)
                # Add to recent files
                self.add_to_recent_files(filename)
            else:
                # Create new tab with the file
                self.new_tab(filename)

    def load_file_content(self, filename):
        """Load file content into current tab"""
        if not self.text:
            return

        # Check if it's an image file
        image_extensions = {'.png', '.jpg', '.jpeg', '.gif', '.bmp', '.ppm', '.pgm'}
        file_ext = os.path.splitext(filename)[1].lower()

        if file_ext in image_extensions:
            self._load_image_file(filename)
            return

        try:
            with open(filename, 'r', encoding='utf-8') as f:
                content = f.read()
            self.text.delete("1.0", "end")
            self.text.insert("1.0", content)
            self.text.edit_modified(False)  # Reset the text widget's modified flag
            self.current_file = filename
            self.modified = False

            # Auto-detect and apply syntax highlighting
            language = self.highlighter.detect_language(filename)
            if language:
                self.highlighter.setup_language(language)
                # Force immediate highlight of entire document
                self.highlighter.highlight_all()
                self.syntax_label.config(text=language.title())
                # Update menu if in auto mode
                if hasattr(self, 'current_syntax_var') and self.current_syntax_var.get() == "auto":
                    pass  # Keep it as auto
                elif hasattr(self, 'current_syntax_var'):
                    self.current_syntax_var.set(language)
            else:
                self.syntax_label.config(text="Plain Text")
                if hasattr(self, 'current_syntax_var') and self.current_syntax_var.get() == "auto":
                    pass  # Keep it as auto

            self.update_line_numbers()
            self.update_tab_title()

            # Apply colors after highlighting
            if hasattr(self, 'color_scheme') and self.color_scheme.current_scheme_name:
                self.color_scheme.apply_scheme(self.color_scheme.current_scheme_name)
        except UnicodeDecodeError:
            # Binary file that's not an image
            self._load_binary_file(filename)
        except Exception as e:
            messagebox.showerror("Error", f"Failed to open file: {e}")

    def _load_image_file(self, filename):
        """Load and display an image file (uses Pillow if available)"""
        try:
            self.text.delete("1.0", "end")
            self.text.config(state='normal')

            # Clear any existing images
            if hasattr(self, '_image_refs'):
                self._image_refs.clear()
            else:
                self._image_refs = []

            # Try to use Pillow if available (optional dependency)
            try:
                from PIL import Image, ImageTk
                pil_available = True
            except ImportError:
                pil_available = False

            if pil_available:
                # Use Pillow for enhanced format support (PNG, JPG, etc.)
                try:
                    image = Image.open(filename)
                    width, height = image.size
                    mode = image.mode

                    # Resize if too large (max 1200x800)
                    max_width = 1200
                    max_height = 800
                    if width > max_width or height > max_height:
                        ratio = min(max_width / width, max_height / height)
                        new_width = int(width * ratio)
                        new_height = int(height * ratio)
                        image = image.resize((new_width, new_height), Image.Resampling.LANCZOS)
                        width, height = new_width, new_height

                    photo = ImageTk.PhotoImage(image)

                    # Display image info
                    info_text = f"Image: {os.path.basename(filename)}\n"
                    info_text += f"Format: {image.format}\n"
                    info_text += f"Size: {width} x {height} pixels\n"
                    info_text += f"Mode: {mode}\n\n"
                    self.text.insert("1.0", info_text)

                    # Insert image
                    self.text.image_create("end", image=photo)
                    self._image_refs.append(photo)
                except Exception as e:
                    # Pillow failed, show error
                    self.text.insert("1.0", f"Image File: {os.path.basename(filename)}\n\n")
                    self.text.insert("end", f"Error loading image: {e}\n\n")
                    self.text.insert("end", f"File path: {filename}")
            else:
                # Fallback to Tkinter PhotoImage (GIF, PGM, PPM only)
                try:
                    photo = tk.PhotoImage(file=filename)

                    info_text = f"Image: {os.path.basename(filename)}\n"
                    info_text += f"Size: {photo.width()} x {photo.height()} pixels\n\n"
                    self.text.insert("1.0", info_text)

                    self.text.image_create("end", image=photo)
                    self._image_refs.append(photo)

                except tk.TclError:
                    # Image format not supported
                    file_size = os.path.getsize(filename)
                    if file_size < 1024:
                        size_str = f"{file_size} bytes"
                    elif file_size < 1024 * 1024:
                        size_str = f"{file_size / 1024:.2f} KB"
                    else:
                        size_str = f"{file_size / (1024 * 1024):.2f} MB"

                    ext = os.path.splitext(filename)[1].upper()
                    self.text.insert("1.0", f"Image File: {os.path.basename(filename)}\n\n")
                    self.text.insert("end", f"Format: {ext[1:] if ext else 'Unknown'}\n")
                    self.text.insert("end", f"Size: {size_str}\n\n")
                    self.text.insert("end", "Tkinter supports GIF, PGM, and PPM formats only.\n")
                    self.text.insert("end", f"To view {ext[1:]} images, install Pillow:\n")
                    self.text.insert("end", "  pip install Pillow\n\n")
                    self.text.insert("end", f"File path: {filename}")

            self.current_file = filename
            self.modified = False
            self.text.edit_modified(False)
            self.syntax_label.config(text="Image")
            self.update_tab_title()

        except Exception as e:
            messagebox.showerror("Error", f"Failed to load image: {e}")

    def _load_binary_file(self, filename):
        """Handle binary files that cannot be displayed as text"""
        self.text.delete("1.0", "end")
        self.text.config(state='normal')

        # Get file info
        file_size = os.path.getsize(filename)
        file_ext = os.path.splitext(filename)[1].upper()

        # Format file size
        if file_size < 1024:
            size_str = f"{file_size} bytes"
        elif file_size < 1024 * 1024:
            size_str = f"{file_size / 1024:.2f} KB"
        else:
            size_str = f"{file_size / (1024 * 1024):.2f} MB"

        # Display info
        info_text = f"Binary File: {os.path.basename(filename)}\n\n"
        info_text += f"Type: {file_ext[1:] if file_ext else 'Unknown'}\n"
        info_text += f"Size: {size_str}\n\n"
        info_text += "This file contains binary data and cannot be displayed as text.\n\n"
        info_text += "Common binary file types:\n"
        info_text += "  - Executables (.exe, .dll, .so)\n"
        info_text += "  - Archives (.zip, .tar, .gz)\n"
        info_text += "  - Databases (.db, .sqlite)\n"
        info_text += "  - Compiled files (.pyc, .class, .o)\n"
        info_text += "  - Media files (audio, video)\n\n"
        info_text += f"Full path: {filename}"

        self.text.insert("1.0", info_text)
        self.current_file = filename
        self.modified = False
        self.text.edit_modified(False)
        self.syntax_label.config(text="Binary")
        self.update_tab_title()

    def save_file(self):
        """Save the current file"""
        if not self.current_file:
            self.save_as_file()
        else:
            try:
                content = self.text.get("1.0", "end-1c")
                with open(self.current_file, 'w') as f:
                    f.write(content)
                self.modified = False
                messagebox.showinfo("Saved", f"File saved: {os.path.basename(self.current_file)}")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to save file: {e}")

    def save_as_file(self):
        """Save the file with a new name"""
        filename = filedialog.asksaveasfilename(
            defaultextension=".txt",
            filetypes=[("All Files", "*.*"), ("Text Files", "*.txt"), ("Python Files", "*.py"),
                      ("JavaScript Files", "*.js"), ("HTML Files", "*.html"), ("CSS Files", "*.css"),
                      ("JSON Files", "*.json"), ("Markdown Files", "*.md")]
        )

        if filename:
            self.current_file = filename
            self.save_file()
            self.update_window_title()

            # Update syntax highlighting for new file type
            language = self.highlighter.detect_language(filename)
            if language:
                self.highlighter.setup_language(language)
                self.highlighter.highlight()
                self.syntax_label.config(text=language.title())
                # Update menu if in auto mode
                if hasattr(self, 'current_syntax_var') and self.current_syntax_var.get() == "auto":
                    pass  # Keep it as auto
                elif hasattr(self, 'current_syntax_var'):
                    self.current_syntax_var.set(language)

    def undo(self):
        """Undo last action"""
        try:
            self.text.edit_undo()
        except:
            pass

    def redo(self):
        """Redo last undone action"""
        try:
            self.text.edit_redo()
        except:
            pass

    def find_dialog(self):
        """Open find dialog"""
        search_term = simpledialog.askstring("Find", "Enter search term (regex):")
        if search_term:
            self.vim.last_search = search_term
            self.vim.search_direction = 1
            self.vim.search_next()

    def replace_dialog(self):
        """Open replace dialog"""
        find_term = simpledialog.askstring("Find and Replace", "Find (regex):")
        if find_term:
            replace_term = simpledialog.askstring("Find and Replace", "Replace with:")
            if replace_term is not None:
                self.substitute(find_term, replace_term, True)

    def manage_regex_patterns(self):
        """Open regex pattern manager dialog"""
        dialog = tk.Toplevel(self.root)
        dialog.title("Manage Regex Patterns")
        dialog.geometry("600x400")

        # Pattern list
        listbox = tk.Listbox(dialog)
        listbox.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        for pattern in self.regex_manager.patterns:
            listbox.insert(tk.END, f"{pattern['name']}: {pattern['pattern']}")

        # Buttons
        button_frame = ttk.Frame(dialog)
        button_frame.pack(fill=tk.X, padx=10, pady=5)

        def add_pattern():
            name = simpledialog.askstring("Add Pattern", "Pattern name:")
            if name:
                pattern = simpledialog.askstring("Add Pattern", "Regex pattern:")
                if pattern:
                    self.regex_manager.add_pattern(name, pattern)
                    listbox.insert(tk.END, f"{name}: {pattern}")
                    self.update_regex_menu()

        def delete_pattern():
            selection = listbox.curselection()
            if selection:
                index = selection[0]
                listbox.delete(index)
                self.regex_manager.delete_pattern(index)
                self.update_regex_menu()

        ttk.Button(button_frame, text="Add", command=add_pattern).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Delete", command=delete_pattern).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Close", command=dialog.destroy).pack(side=tk.RIGHT, padx=5)

    def quick_regex_search(self):
        """Quick search using saved regex patterns"""
        dialog = tk.Toplevel(self.root)
        dialog.title("Quick Regex Search")
        dialog.geometry("400x300")

        listbox = tk.Listbox(dialog)
        listbox.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        for pattern in self.regex_manager.patterns:
            listbox.insert(tk.END, pattern['name'])

        def use_pattern():
            selection = listbox.curselection()
            if selection:
                index = selection[0]
                pattern = self.regex_manager.get_pattern(index)
                if pattern:
                    self.vim.last_search = pattern
                    self.vim.search_direction = 1
                    self.vim.search_next()
                    dialog.destroy()

        ttk.Button(dialog, text="Search", command=use_pattern).pack(pady=5)

    def update_regex_menu(self):
        """Update regex menu with saved patterns"""
        # Clear existing pattern items
        self.regex_menu.delete(3, tk.END)

        # Add separator if patterns exist
        if self.regex_manager.patterns:
            self.regex_menu.add_separator()

        # Add saved patterns
        for i, pattern in enumerate(self.regex_manager.patterns):
            self.regex_menu.add_command(
                label=pattern['name'],
                command=lambda p=pattern['pattern']: self.use_regex_pattern(p)
            )

    def use_regex_pattern(self, pattern):
        """Use a regex pattern for search"""
        self.vim.last_search = pattern
        self.vim.search_direction = 1
        self.vim.search_next()

    def change_color_scheme(self, scheme_name):
        """Change the color scheme"""
        if self.color_scheme.apply_scheme(scheme_name):
            # Update the menu checkmark
            if hasattr(self, 'current_theme_var'):
                self.current_theme_var.set(scheme_name)
            # Reapply syntax highlighting with new colors
            if self.highlighter.current_language:
                self.highlighter.highlight()
            # Update cursor visibility for new theme
            self.update_cursor_visibility()

    def load_color_scheme_file(self):
        """Load a color scheme from file"""
        filename = filedialog.askopenfilename(
            defaultextension=".json",
            filetypes=[("JSON Files", "*.json"), ("All Files", "*.*")]
        )

        if filename:
            scheme_name = self.color_scheme.load_from_file(filename)
            if scheme_name:
                self.change_color_scheme(scheme_name)
                messagebox.showinfo("Success", f"Loaded color scheme: {scheme_name}")
                # Refresh theme menu and update checkmark
                if hasattr(self, 'current_theme_var'):
                    self.current_theme_var.set(scheme_name)
                self.populate_theme_menu()

    def quit_editor(self):
        """Quit the editor"""
        if self.modified:
            response = messagebox.askyesnocancel("Save Changes", "Do you want to save changes?")
            if response is None:
                return
            elif response:
                self.save_file()

        self.root.quit()


    # Project view and recent files methods
    def setup_project_view(self):
        """Setup the project/directory tree view"""
        # Get the current theme
        theme = self.gui_themes[self.current_gui_theme]

        # Close button at the top
        close_frame = tk.Frame(self.project_frame, bg=theme.get('bg'), height=20)
        close_frame.pack(fill=tk.X, padx=5, pady=(5, 0))
        close_frame.pack_propagate(False)

        close_btn = tk.Button(close_frame, text="✕", command=self.close_project_view,
                            bd=0, padx=5, font=("Consolas", 10),
                            bg=theme.get('bg'), fg=theme.get('fg'),
                            activebackground=theme.get('active_tab_bg'))
        close_btn.pack(side=tk.RIGHT)

        # Create treeview directly without scrollbars initially
        self.project_tree = ttk.Treeview(self.project_frame, show="tree")
        self.project_tree.pack(fill=tk.BOTH, expand=True, padx=5, pady=(0, 5))

        # Bind double-click to open files
        self.project_tree.bind("<Double-Button-1>", self.on_tree_double_click)
        # Also bind Enter key to open files
        self.project_tree.bind("<Return>", self.on_tree_double_click)

    def open_directory(self):
        """Open a directory as a project"""
        from tkinter import filedialog
        directory = filedialog.askdirectory(title="Select Project Directory")

        if directory:
            self.project_root = directory
            self.load_project_tree(directory)
            self.show_project_panel()

    def load_project_tree(self, directory):
        """Load directory structure into tree view"""
        # Clear existing tree
        for item in self.project_tree.get_children():
            self.project_tree.delete(item)

        # Add root directory
        root_name = os.path.basename(directory)
        root_id = self.project_tree.insert("", "end", text=root_name, open=True,
                                          tags=("directory",))

        # Load directory contents
        self.populate_tree(root_id, directory)

    def populate_tree(self, parent_id, path):
        """Recursively populate tree with files and directories"""
        try:
            items = []
            for item in os.listdir(path):
                if item.startswith('.'):  # Skip hidden files
                    continue
                item_path = os.path.join(path, item)
                items.append((item, item_path, os.path.isdir(item_path)))

            # Sort: directories first, then files
            items.sort(key=lambda x: (not x[2], x[0].lower()))

            for item_name, item_path, is_dir in items:
                if is_dir:
                    # Add directory
                    dir_id = self.project_tree.insert(parent_id, "end",
                                                     text=item_name,
                                                     tags=("directory",))
                    # Add dummy child to show expand arrow
                    self.project_tree.insert(dir_id, "end", text="", tags=("dummy",))
                else:
                    # Add file
                    self.project_tree.insert(parent_id, "end",
                                           text=item_name,
                                           tags=("file", item_path))
        except PermissionError:
            pass

        # Bind tree expand event (only once)
        if not hasattr(self, '_tree_expand_bound'):
            self.project_tree.bind("<<TreeviewOpen>>", self.on_tree_expand)
            self._tree_expand_bound = True

    def on_tree_expand(self, event):
        """Handle tree node expansion"""
        item_id = self.project_tree.focus()
        children = self.project_tree.get_children(item_id)

        # Check if has dummy child
        if len(children) == 1 and self.project_tree.item(children[0])["tags"][0] == "dummy":
            # Remove dummy
            self.project_tree.delete(children[0])

            # Get full path
            path_parts = []
            current = item_id
            while current:
                path_parts.insert(0, self.project_tree.item(current)["text"])
                current = self.project_tree.parent(current)

            full_path = os.path.join(self.project_root, *path_parts[1:])
            self.populate_tree(item_id, full_path)

    def on_tree_double_click(self, event):
        """Handle double-click on tree item"""
        item_id = self.project_tree.focus()
        if not item_id:
            return

        tags = self.project_tree.item(item_id)["tags"]
        if "file" in tags and len(tags) > 1:
            file_path = tags[1]
            self.open_file_path(file_path)

    def show_project_panel(self):
        """Show the project panel"""
        if not self.show_project_view:
            self.show_project_view = True
            # Clear and re-add in correct order (project on left, editor on right)
            for widget in self.main_paned.panes():
                self.main_paned.forget(widget)
            self.main_paned.add(self.project_frame, minsize=150, width=180)
            self.main_paned.add(self.editor_area)

    def close_project_view(self):
        """Close the project view panel"""
        if self.show_project_view:
            self.show_project_view = False
            self.main_paned.forget(self.project_frame)
            self.project_root = None

    def load_recent_files(self):
        """Load recent files list from file"""
        try:
            import json
            if os.path.exists("recent_files.json"):
                with open("recent_files.json", "r") as f:
                    self.recent_files = json.load(f)
                # Filter out non-existent files
                self.recent_files = [f for f in self.recent_files if os.path.exists(f)]
        except:
            self.recent_files = []

    def save_recent_files(self):
        """Save recent files list to file"""
        try:
            import json
            with open("recent_files.json", "w") as f:
                json.dump(self.recent_files[:self.max_recent_files], f, indent=2)
        except:
            pass

    def add_to_recent_files(self, file_path):
        """Add a file to recent files list"""
        if file_path in self.recent_files:
            self.recent_files.remove(file_path)
        self.recent_files.insert(0, file_path)
        self.recent_files = self.recent_files[:self.max_recent_files]
        self.update_recent_files_menu()

    def update_recent_files_menu(self):
        """Update the recent files menu"""
        if not hasattr(self, 'recent_menu'):
            return

        theme = self.gui_themes[self.current_gui_theme]
        self.recent_menu.delete(0, tk.END)

        if not self.recent_files:
            self.recent_menu.add_command(label="(No recent files)", state="disabled")
        else:
            for i, file_path in enumerate(self.recent_files, 1):
                file_name = os.path.basename(file_path)
                self.recent_menu.add_command(
                    label=f"{i}. {file_name}",
                    command=lambda p=file_path: self.open_file_path(p)
                )

            self.recent_menu.add_separator()
            self.recent_menu.add_command(label="Clear Recent Files",
                                        command=self.clear_recent_files)

    def clear_recent_files(self):
        """Clear the recent files list"""
        self.recent_files = []
        self.update_recent_files_menu()
        self.save_recent_files()

    def open_file_path(self, file_path):
        """Open a specific file path"""
        if not os.path.exists(file_path):
            from tkinter import messagebox
            messagebox.showerror("Error", f"File not found: {file_path}")
            return

        # Check if file is already open in a tab
        for tab_id, tab_data in self.tabs.items():
            if tab_data['file_path'] == file_path:
                # Select the existing tab
                self.notebook.select(tab_data['frame'])
                return

        # Check if current tab is unmodified "Untitled" and can be replaced
        if (self.current_tab and
            self.current_tab in self.tabs and
            not self.tabs[self.current_tab]['file_path'] and
            not self.tabs[self.current_tab]['modified'] and
            self.text.get("1.0", "end-1c").strip() == ""):
            # Reuse the current untitled tab
            self.tabs[self.current_tab]['file_path'] = file_path
            self.load_file_content(file_path)
            # Update tab title
            title = self.get_tab_title(file_path, False)
            self.notebook.tab(self.tabs[self.current_tab]['frame'], text=title)
            # Add to recent files
            self.add_to_recent_files(file_path)
        else:
            # Create new tab and load file
            self.new_tab(file_path)
            # Add to recent files
            self.add_to_recent_files(file_path)


def main() -> int:
    """
    Main entry point for Vye editor.

    Returns:
        Exit code (0 for success)
    """
    try:
        root = tk.Tk()
        editor = VyeEditor(root)
        root.mainloop()
        return 0
    except Exception as e:
        print(f"Fatal error: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())