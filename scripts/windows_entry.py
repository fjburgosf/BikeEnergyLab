"""Shared Windows entrypoint: GUI on double-click, CLI with arguments."""

import sys

from bikeenergylab.cli import main

if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:] or ["gui"]))
