"""Console formatters and visual presenters for notebook source summaries."""

import sys
from typing import Any, Optional
from .models import NotebookSummaryResult, SourceSummary

try:
    from rich.console import Console
    from rich.table import Table
    from rich.panel import Panel
    from rich.tree import Tree
    from rich.text import Text
    from rich.rule import Rule
    from rich.box import ROUNDED, DOUBLE_EDGE
    HAS_RICH = True
except ImportError:
    HAS_RICH = False


def print_console_report(result: NotebookSummaryResult, console: Optional[Any] = None) -> None:
    """Render a structured report of notebook sources and decomposed documents to the terminal."""
    if HAS_RICH:
        _render_rich(result, console)
    else:
        _render_plain(result)


def _render_rich(result: NotebookSummaryResult, custom_console: Optional[Any] = None) -> None:
    from rich.console import Console
    from rich.table import Table
    from rich.panel import Panel
    from rich.tree import Tree
    from rich.text import Text
    from rich.rule import Rule
    from rich.box import ROUNDED

    console = custom_console or Console()

    # Header Panel
    header_text = Text()
    header_text.append(f"📓 {result.notebook_title}\n", style="bold cyan")
    header_text.append(f"ID: {result.notebook_id}\n", style="dim")
    header_text.append(f"Total Sources: {result.source_count}  •  ", style="bold white")
    header_text.append(f"Multi-Document / Concatenated: {result.concatenated_source_count}  •  ", style="bold yellow")
    header_text.append(f"Sub-documents Identified: {result.total_sub_document_count}", style="bold green")

    console.print(Panel(header_text, title="[bold magenta]NotebookLM Source Summary Report[/bold magenta]", box=ROUNDED, border_style="cyan"))
    console.print()

    # Summary Table
    table = Table(title="[bold]Sources Overview[/bold]", box=ROUNDED, border_style="dim")
    table.add_column("#", justify="right", style="dim", width=4)
    table.add_column("Title", style="bold white", min_width=30, max_width=45)
    table.add_column("Type", style="cyan", width=12)
    table.add_column("Multi-Doc?", justify="center", width=11)
    table.add_column("Sub-Docs", justify="right", width=9)
    table.add_column("Keywords", style="italic yellow", min_width=20)

    for i, src in enumerate(result.sources, start=1):
        multi_badge = "[bold green]YES[/bold green]" if src.is_concatenated else "[dim]No[/dim]"
        sub_count = f"[bold green]{len(src.sub_documents)}[/bold green]" if src.sub_documents else "-"
        kws = ", ".join(src.keywords[:3]) if src.keywords else "-"
        table.add_row(str(i), src.title, src.source_type, multi_badge, sub_count, kws)

    console.print(table)
    console.print()

    # Detailed Cards
    console.print(Rule("[bold cyan]Detailed Source Analysis[/bold cyan]", style="cyan"))
    console.print()

    for i, src in enumerate(result.sources, start=1):
        badge = " [bold yellow]📦 CONCATENATED PDF / MULTI-PART[/bold yellow]" if src.is_concatenated else ""
        panel_title = f"[bold white]Source #{i}: {src.title}[/bold white]{badge}"

        details_tree = Tree(panel_title)

        # Meta node
        meta_branch = details_tree.add("[bold cyan]Metadata[/bold cyan]")
        meta_branch.add(f"[dim]Source ID:[/dim] {src.source_id}")
        meta_branch.add(f"[dim]Type:[/dim] {src.source_type}")
        if src.url:
            meta_branch.add(f"[dim]URL:[/dim] {src.url}")
        if src.char_count:
            meta_branch.add(f"[dim]Characters:[/dim] {src.char_count:,}")
        if src.keywords:
            meta_branch.add(f"[dim]Keywords:[/dim] {', '.join(src.keywords)}")

        # Summary node
        summary_branch = details_tree.add("[bold cyan]Overview Summary[/bold cyan]")
        summary_branch.add(Text(src.summary or "(No summary available)", style="white"))

        # Decomposed sub-documents
        if src.is_concatenated and src.sub_documents:
            sub_branch = details_tree.add(f"[bold green]Contained Documents / Sub-Sections ({len(src.sub_documents)})[/bold green]")
            for j, sub in enumerate(src.sub_documents, start=1):
                doc_node = sub_branch.add(f"[bold yellow]{j}. {sub.title}[/bold yellow]")
                if sub.scope:
                    doc_node.add(f"[dim]Scope/Pages:[/dim] {sub.scope}")
                if sub.authors:
                    doc_node.add(f"[dim]Authors:[/dim] {sub.authors}")
                if sub.summary:
                    doc_node.add(f"[white]{sub.summary}[/white]")
                if sub.keywords:
                    doc_node.add(f"[italic dim]Keywords: {', '.join(sub.keywords)}[/italic dim]")

        border_col = "yellow" if src.is_concatenated else "blue"
        console.print(Panel(details_tree, box=ROUNDED, border_style=border_col))
        console.print()


def _render_plain(result: NotebookSummaryResult) -> None:
    """Plain-text fallback when rich is not installed."""
    print("=" * 80)
    print(f"Notebook: {result.notebook_title} ({result.notebook_id})")
    print(f"Sources: {result.source_count} | Concatenated: {result.concatenated_source_count} | Sub-docs: {result.total_sub_document_count}")
    print("=" * 80)
    print()

    for i, src in enumerate(result.sources, start=1):
        print(f"[{i}] {src.title} ({src.source_type})")
        print(f"    ID: {src.source_id}")
        if src.keywords:
            print(f"    Keywords: {', '.join(src.keywords)}")
        print(f"    Summary: {src.summary}")

        if src.is_concatenated:
            print(f"    *** CONCATENATED / MULTI-PART SOURCE (Sub-documents: {len(src.sub_documents)}) ***")
            for j, sub in enumerate(src.sub_documents, start=1):
                scope_str = f" [{sub.scope}]" if sub.scope else ""
                author_str = f" (by {sub.authors})" if sub.authors else ""
                print(f"      {j}. {sub.title}{scope_str}{author_str}")
                if sub.summary:
                    print(f"         {sub.summary}")
        print("-" * 80)
