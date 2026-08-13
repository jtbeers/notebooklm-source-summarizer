"""Command-line interface for NotebookLM Source Summarizer."""

import argparse
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

from .client import NotebookLMClientWrapper
from .formatters import print_console_report
from .models import NotebookSummaryResult
from .summarizer import NotebookSummarizer

try:
    from rich.console import Console
    from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn
    from rich.table import Table
    from rich.panel import Panel
    from rich.tree import Tree
    from rich.text import Text
    from rich.rule import Rule
    from rich.prompt import Prompt
    HAS_RICH = True
except ImportError:
    HAS_RICH = False


def get_reports_directory() -> Path:
    """Get the preferred reports directory according to workspace preferences."""
    reports_dir = Path.home() / "Documents" / "agy-reports"
    reports_dir.mkdir(parents=True, exist_ok=True)
    return reports_dir


def interactive_select_notebook(client: NotebookLMClientWrapper) -> str:
    """Interactively list notebooks and allow the user to select one."""
    notebooks = client.list_notebooks()
    if not notebooks:
        print("No notebooks found in your NotebookLM account.")
        sys.exit(1)

    print("\nAvailable NotebookLM Notebooks:")
    print("-" * 60)
    for idx, nb in enumerate(notebooks, start=1):
        title = nb.get("title", "Untitled")
        nb_id = nb.get("id", "")
        count = nb.get("source_count", 0)
        print(f"[{idx:2d}] {title:<40} (Sources: {count:2d})  ID: {nb_id}")
    print("-" * 60)

    while True:
        try:
            choice = input(f"\nSelect a notebook [1-{len(notebooks)}] or enter ID/Search: ").strip()
            if not choice:
                continue
            if choice.isdigit():
                num = int(choice)
                if 1 <= num <= len(notebooks):
                    return notebooks[num - 1]["id"]
                print(f"Please enter a number between 1 and {len(notebooks)}.")
                continue
            # Try fuzzy match
            match = client.find_notebook(choice)
            return match["id"]
        except (KeyboardInterrupt, EOFError):
            print("\nAborted by user.")
            sys.exit(0)
        except Exception as e:
            print(f"Error: {e}")


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="List and summarize all sources in a NotebookLM notebook, decomposing concatenated PDFs.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Summarize a notebook by exact ID or title
  python summarize_sources.py "ABN AMRO annual reports 2010-2025"

  # Interactively select a notebook from your account
  python summarize_sources.py

  # Save markdown report to Documents/agy-reports/
  python summarize_sources.py "Mainframe Roadmap" --save-report

  # Export JSON output
  python summarize_sources.py "Future IT Horizons" --json -o future_it.json

  # List all available notebooks
  python summarize_sources.py --list
        """,
    )

    parser.add_argument(
        "notebook",
        nargs="?",
        default=None,
        help="Notebook ID, exact title, or title substring to search for.",
    )
    parser.add_argument(
        "--list", "-l",
        action="store_true",
        help="List all available notebooks and exit.",
    )
    parser.add_argument(
        "--output", "-o",
        type=str,
        default=None,
        help="Path to save the generated report (Markdown or JSON depending on flags).",
    )
    parser.add_argument(
        "--save-report",
        action="store_true",
        help="Automatically save a timestamped markdown report to ~/Documents/agy-reports/.",
    )
    parser.add_argument(
        "--json", "-j",
        action="store_true",
        help="Output results in JSON format.",
    )
    parser.add_argument(
        "--no-pdf-deep-dive",
        action="store_true",
        help="Skip deep decomposition of concatenated PDFs (faster, only basic summaries).",
    )
    parser.add_argument(
        "--profile", "-p",
        type=str,
        default=None,
        help="NotebookLM profile name to use (default: 'default').",
    )
    parser.add_argument(
        "--concurrency", "-c",
        type=int,
        default=4,
        help="Number of concurrent workers for analyzing sources (default: 4).",
    )
    parser.add_argument(
        "--quiet", "-q",
        action="store_true",
        help="Suppress intermediate progress messages.",
    )

    args = parser.parse_args(argv)

    try:
        client = NotebookLMClientWrapper(profile=args.profile)
    except Exception as e:
        print(f"Authentication / Initialization Error: {e}", file=sys.stderr)
        return 1

    if args.list:
        try:
            notebooks = client.list_notebooks()
            if HAS_RICH and not args.quiet:
                console = Console()
                table = Table(title="NotebookLM Notebooks", box=None)
                table.add_column("#", style="dim", width=4)
                table.add_column("Title", style="bold cyan")
                table.add_column("Sources", justify="right", style="green")
                table.add_column("Notebook ID", style="dim")
                for i, nb in enumerate(notebooks, start=1):
                    table.add_row(
                        str(i),
                        nb.get("title", "Untitled"),
                        str(nb.get("source_count", 0)),
                        nb.get("id", ""),
                    )
                console.print(table)
            else:
                for i, nb in enumerate(notebooks, start=1):
                    print(f"[{i:2d}] {nb.get('title', 'Untitled')} (ID: {nb.get('id', '')}, Sources: {nb.get('source_count', 0)})")
            return 0
        except Exception as e:
            print(f"Error listing notebooks: {e}", file=sys.stderr)
            return 1

    notebook_identifier = args.notebook
    if not notebook_identifier:
        notebook_identifier = interactive_select_notebook(client)

    summarizer = NotebookSummarizer(client=client, profile=args.profile)

    # Progress tracking
    if HAS_RICH and not args.quiet and not args.json:
        console = Console()
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TaskProgressColumn(),
            console=console,
        ) as progress:
            task = progress.add_task("[cyan]Initializing...", total=1)

            def _progress_cb(desc: str, completed: int, total: int) -> None:
                progress.update(task, description=f"[cyan]{desc}", completed=completed, total=max(1, total))

            result = summarizer.summarize_notebook(
                notebook_identifier=notebook_identifier,
                detect_concatenated_pdfs=not args.no_pdf_deep_dive,
                max_workers=args.concurrency,
                progress_callback=_progress_cb,
            )
    else:
        def _plain_progress(desc: str, completed: int, total: int) -> None:
            if not args.quiet and not args.json:
                print(f"[*] {desc}")

        result = summarizer.summarize_notebook(
            notebook_identifier=notebook_identifier,
            detect_concatenated_pdfs=not args.no_pdf_deep_dive,
            max_workers=args.concurrency,
            progress_callback=_plain_progress,
        )

    # Handle outputs
    if args.json:
        json_str = result.to_json(indent=2)
        if args.output:
            Path(args.output).write_text(json_str, encoding="utf-8")
            if not args.quiet:
                print(f"JSON results saved to {args.output}")
        else:
            print(json_str)
    else:
        print_console_report(result)

        if args.output:
            out_path = Path(args.output)
            out_path.write_text(result.to_markdown(), encoding="utf-8")
            print(f"\nReport saved to: {out_path.resolve()}")

    if args.save_report:
        reports_dir = get_reports_directory()
        safe_title = "".join(c if c.isalnum() or c in ("-", "_") else "_" for c in result.notebook_title)[:40]
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        report_file = reports_dir / f"notebook_summary_{safe_title}_{timestamp}.md"
        report_file.write_text(result.to_markdown(), encoding="utf-8")
        print(f"\n[Saved to AGY Reports Directory]: {report_file.resolve()}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
