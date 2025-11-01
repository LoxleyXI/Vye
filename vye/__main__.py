"""
Entry point for running Vye as a module: python -m vye
"""

import sys
from vye.app import main

if __name__ == "__main__":
    sys.exit(main())
