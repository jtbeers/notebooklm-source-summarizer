# NotebookLM Source Summarizer & PDF Decomposer 📚🔍

[![Python](https://img.shields.io/badge/Python-3.10%2B-blue.svg)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![NotebookLM](https://img.shields.io/badge/NotebookLM-Powered-purple.svg)](https://notebooklm.google.com/)

A powerful Python tool and library that inspects **Google NotebookLM** notebooks, lists all included sources with metadata, generates executive summaries, and **automatically decomposes concatenated PDF files or multi-document bundles** into structured sub-documents.

---

## Key Features

- 📑 **Comprehensive Source Listing:** Retrieve all sources in any notebook with types (`pdf`, `docx`, `web/url`, `drive_doc`, `text`), status, and character counts.
- 💡 **AI-Generated Source Summaries:** Automatically fetch high-level executive summaries and key topic keywords for each source.
- 📦 **Concatenated PDF & Multi-Document Decomposition:** Detects composite documents, compiled conference proceedings, bundled research papers, or statutory annual reports, and isolates each embedded sub-document with:
  - Document / Section Title
  - Scope (page range or section indicator)
  - Authors & Organization
  - Dedicated 2-3 sentence summary
  - Sub-topic keywords
- 🖥️ **Rich Terminal Interface:** Displays elegant progress bars, styled tables, badges, and hierarchical tree views.
- 📄 **Markdown & JSON Export:** Output formatted GitHub Flavored Markdown reports (or machine-readable JSON) directly to disk or automatically into `~/Documents/agy-reports/`.
- ⚡ **Concurrent Processing:** Threaded worker pool for rapid analysis of notebooks containing dozens or hundreds of sources.
- 🎯 **Fuzzy Notebook Discovery:** Pass a Notebook UUID, exact title, partial title substring, or use the interactive picker.

---

## Installation

### 1. Prerequisites
Ensure you have authenticated with NotebookLM using the `nlm` CLI:
```bash
nlm login
```

### 2. Install Dependencies
```bash
cd /Users/jtbeers/Code/notebooklm-source-summarizer
pip install -r requirements.txt
```
Or install in editable development mode:
```bash
pip install -e .
```

---

## Quick Start

### 1. Interactive Selection
Run without arguments to view and select from your available notebooks:
```bash
python summarize_sources.py
```

### 2. Summarize by Title or ID
```bash
python summarize_sources.py "ABN AMRO annual reports 2010-2025"
```
Or by notebook UUID:
```bash
python summarize_sources.py 0e75af01-e199-4651-9a65-01d276527611
```

### 3. Automatically Save Report
Export a timestamped markdown report directly to `~/Documents/agy-reports/`:
```bash
python summarize_sources.py "Mainframe Roadmap" --save-report
```

### 4. Export Custom Markdown or JSON
```bash
# Save to specific markdown file
python summarize_sources.py "Future IT Horizons" -o report.md

# Output JSON
python summarize_sources.py "Future IT Horizons" --json -o summary.json
```

### 5. Fast Mode (Skip Deep PDF Decomposition)
To quickly retrieve existing source summaries without querying NotebookLM for internal PDF decomposition:
```bash
python summarize_sources.py "My Research Notebook" --no-pdf-deep-dive
```

---

## CLI Reference

```
usage: summarize_sources.py [-h] [--list] [--output OUTPUT] [--save-report]
                            [--json] [--no-pdf-deep-dive] [--profile PROFILE]
                            [--concurrency CONCURRENCY] [--quiet]
                            [notebook]

Positional Arguments:
  notebook                 Notebook ID, exact title, or title substring.

Options:
  -h, --help               Show this help message and exit.
  -l, --list               List all available notebooks and exit.
  -o, --output OUTPUT      Path to save the generated report (.md or .json).
  --save-report            Automatically save a timestamped markdown report to ~/Documents/agy-reports/.
  -j, --json               Output results in JSON format.
  --no-pdf-deep-dive       Skip deep decomposition of concatenated PDFs (faster).
  -p, --profile PROFILE    NotebookLM profile name to use (default: 'default').
  -c, --concurrency CONCURRENCY
                           Number of concurrent workers (default: 4).
  -q, --quiet              Suppress intermediate progress messages.
```

---

## Programmatic Python Usage

You can also use `notebooklm_source_summarizer` directly in your Python code:

```python
from notebooklm_source_summarizer import NotebookSummarizer, NotebookLMClientWrapper

# Initialize client
client = NotebookLMClientWrapper()

# Summarize a notebook
summarizer = NotebookSummarizer(client=client)
result = summarizer.summarize_notebook(
    notebook_identifier="ABN AMRO annual reports 2010-2025",
    detect_concatenated_pdfs=True,
    max_workers=4
)

# Access structured data
print(f"Notebook: {result.notebook_title} ({result.source_count} sources)")
for src in result.sources:
    print(f"\nSource: {src.title} [{src.source_type}]")
    print(f"Summary: {src.summary}")
    if src.is_concatenated:
        print(f"Concatenated PDF with {len(src.sub_documents)} sub-documents:")
        for doc in src.sub_documents:
            print(f"  - {doc.title} ({doc.scope}): {doc.summary}")

# Export Markdown or JSON
md_content = result.to_markdown()
json_content = result.to_json()
```

---

## Architecture

```
notebooklm-source-summarizer/
├── summarize_sources.py              # CLI entry point
├── pyproject.toml                    # Package metadata & CLI registration
├── requirements.txt                  # Dependencies
├── README.md                         # Documentation
└── notebooklm_source_summarizer/
    ├── __init__.py                   # Package exports
    ├── __main__.py                   # `python -m notebooklm_source_summarizer`
    ├── cli.py                        # CLI parsing, options, interactive menu
    ├── client.py                     # NotebookLM connection & auth wrapper
    ├── models.py                     # Dataclasses (SubDocument, SourceSummary, NotebookSummaryResult)
    ├── summarizer.py                 # Core summarization & PDF decomposition logic
    └── formatters.py                 # Rich console presentation and text fallbacks
```

---

## License

MIT License. See [LICENSE](LICENSE) for details.
