#!/usr/bin/env python
"""
Vye - A flexible and lightweight cross-platform modal text editor

Simple entry point script for running Vye editor.
"""

import sys

# Add current directory to path to allow imports
sys.path.insert(0, '.')

from vye.app import main

if __name__ == "__main__":
    sys.exit(main())
