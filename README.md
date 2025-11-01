# Vye

Vye is a free lightweight text editor with modal editing and full cross-platform support.

![Python Version](https://img.shields.io/badge/python-3.7%2B-blue)
![License](https://img.shields.io/badge/license-MIT-green)
![Platform](https://img.shields.io/badge/platform-Windows%20%7C%20Linux%20%7C%20macOS-lightgrey)
![Dependencies](https://img.shields.io/badge/dependencies-none-brightgreen)

[![Vye](https://github.com/LoxleyXI/Vye/blob/main/assets/screenshot.png)](https://github.com/LoxleyXI/Vye)

## Features

- **Vim style modal editing** - NORMAL, INSERT, VISUAL, COMMAND, and REPLACE modes
- **Multi-file tabs** - Edit several files at once
- **Syntax highlighting** - 12 languages (Python, JS, TS, C/C++, Lua, Lisp, Haskell, HTML, CSS, JSON, Markdown, plain text)
- **Multiple themes** - 6 built-in themes, plus load your own
- **Project explorer** - Browse directory trees
- **Image viewer** - Display GIF (built-in) and PNG/JPG (with optional Pillow)
- **Find & replace** - Regex search with saved patterns
- **Macro recording** - Record and replay command sequences
- **Plugin system** - Extend functionality without touching core code

## Vim Commands

Vye supports 50+ Vim commands:

- **Motions**: `h/j/k/l`, `w/b/e`, `0/$`, `gg/G`, `{/}`, `(/)`, `[[/]]`
- **Editing**: `i/a/o/O`, `x/X`, `dd/dw/d$`, `yy/yw/y$`, `p/P`, `c/C/s/S`, `r`
- **Visual**: `v` for character selection
- **Search**: `/` and `?`, `n/N` to navigate
- **Repeat**: `.` for last change, `@` for macros
- **Marks**: `m{a-z}` and `'{a-z}`
- **Commands**: `:w`, `:q`, `:wq`, `:e`, `:s/find/replace/`

## Quick Start

### Requirements

- Python 3.7+
- tkinter (included with most Python installations)

### Installation

```bash
git clone https://github.com/LoxleyXI/Vye.git
cd Vye
python vye.py
```

Optional: Install Pillow for PNG/JPG support:
```bash
pip install Pillow
```

### Basic Usage

1. Launch: `python vye.py`
2. Open a file: `Ctrl+O` or `:e filename`
3. Enter insert mode: `i`
4. Save: `:w` or `Ctrl+S`
5. Quit: `:q` or `:wq`

### Keyboard Shortcuts

| Shortcut | Action |
|----------|--------|
| `Ctrl+N` | New tab |
| `Ctrl+O` | Open file |
| `Ctrl+S` | Save |
| `Ctrl+W` | Close tab |
| `Ctrl+Tab` | Next tab |
| `Ctrl+F` | Find |
| `Ctrl+H` | Find & replace |

## Architecture

Vye is organized into modules:

```
vye/
├── core/          # Vim mode, syntax highlighting, themes
├── plugins/       # Plugin system base classes
├── utils/         # File I/O helpers
└── app.py         # Main editor class
```

Configuration is external:
- `syntax/*.json` - Language definitions
- `themes/*.json` - Color schemes
- `patterns/*.json` - Regex patterns

## Plugin System

Create plugins by extending base classes:

```python
from vye.plugins.base import HookPlugin

class AutoSavePlugin(HookPlugin):
    name = "Auto Save"
    version = "1.0.0"

    def on_text_change(self, start, end, text):
        # Auto-save logic here
        pass
```

Available plugin types:
- **LanguagePlugin** - Add syntax highlighting
- **ThemePlugin** - Add color schemes
- **CommandPlugin** - Add Vim commands
- **HookPlugin** - React to editor events

Event hooks:
- `on_file_open/save/close`
- `on_mode_change`
- `on_text_change`
- `on_selection_change`
- `on_startup/shutdown`

## Adding Languages

Create a JSON file in `syntax/`:

```json
{
  "name": "MyLang",
  "extensions": [".ml"],
  "patterns": {
    "keyword": {
      "pattern": "\\b(if|else|while)\\b",
      "flags": ""
    },
    "string": {
      "pattern": "\"[^\"]*\"",
      "flags": ""
    }
  }
}
```

Add corresponding colors to all themes in `themes/*.json`:

```json
{
  "keyword": "#569cd6",
  "string": "#ce9178"
}
```

Restart Vye and the language will be auto-detected by file extension.

## Testing

```bash
# Install dev dependencies
pip install pytest pytest-cov flake8 black mypy

# Run tests
pytest

# Type check
mypy vye/

# Lint
flake8 vye/
black vye/ --check
```

## Contributing

Pull requests welcome. Please:
- Follow PEP 8
- Add type hints
- Write docstrings
- Test your changes

## License

MIT License - see LICENSE file.

## Roadmap

Future improvements:
- Split windows
- LSP support (as optional plugin)
- More languages
- Session management
- Minimap view
