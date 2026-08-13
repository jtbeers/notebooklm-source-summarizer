"""Module entrypoint for `python -m notebooklm_source_summarizer`."""

import sys
from .cli import main

if __name__ == "__main__":
    sys.exit(main())
