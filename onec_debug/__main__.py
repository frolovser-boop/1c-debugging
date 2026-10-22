# -*- coding: utf-8 -*-
try:
    from .cli import main
except (ImportError, ValueError):
    from onec_debug.cli import main

if __name__ == "__main__":
    main()
