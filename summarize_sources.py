#!/usr/bin/env python3
"""NotebookLM Source Summarizer and Concatenated PDF Inspector.

Usage:
    python summarize_sources.py [notebook_id_or_title] [options]
"""

import os
import sys
from pathlib import Path

# If running on older Python (< 3.10), try to re-exec with modern Python or uv tool python
if sys.version_info < (3, 10):
    candidate_pythons = [
        str(Path.home() / ".local/share/uv/tools/notebooklm-mcp-cli/bin/python3"),
        str(Path.home() / ".pyenv/shims/python3"),
        "/opt/homebrew/bin/python3",
        "/usr/local/bin/python3",
        "python3.12",
        "python3.11",
        "python3.10",
    ]
    for py in candidate_pythons:
        if Path(py).is_file() and os.access(py, os.X_OK):
            os.execv(py, [py] + sys.argv)

# Ensure local package directory is in sys.path
package_root = Path(__file__).resolve().parent
if str(package_root) not in sys.path:
    sys.path.insert(0, str(package_root))

from notebooklm_source_summarizer.cli import main

if __name__ == "__main__":
    sys.exit(main())
