"""Data models for NotebookLM Source Summarizer."""

from dataclasses import dataclass, field, asdict
from typing import Any, Optional
import json
from datetime import datetime


@dataclass
class SubDocument:
    """Represents an individual document/paper/section inside a concatenated source."""

    title: str
    summary: str
    scope: Optional[str] = None  # e.g., "Pages 1-15", "Chapter 2", "Section B"
    authors: Optional[str] = None
    keywords: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class SourceSummary:
    """Summary and decomposition information for a single NotebookLM source."""

    source_id: str
    title: str
    source_type: str
    url: Optional[str] = None
    char_count: Optional[int] = None
    status: Optional[int] = None
    summary: str = ""
    keywords: list[str] = field(default_factory=list)
    is_concatenated: bool = False
    concatenation_analysis: Optional[str] = None
    sub_documents: list[SubDocument] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class NotebookSummaryResult:
    """Complete summary results for all sources in a NotebookLM notebook."""

    notebook_id: str
    notebook_title: str
    source_count: int
    generated_at: str = field(default_factory=lambda: datetime.utcnow().isoformat() + "Z")
    sources: list[SourceSummary] = field(default_factory=list)

    @property
    def concatenated_source_count(self) -> int:
        return sum(1 for s in self.sources if s.is_concatenated)

    @property
    def total_sub_document_count(self) -> int:
        return sum(len(s.sub_documents) for s in self.sources)

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["concatenated_source_count"] = self.concatenated_source_count
        data["total_sub_document_count"] = self.total_sub_document_count
        return data

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent, ensure_ascii=False)

    def to_markdown(self) -> str:
        """Render complete results as a GitHub Flavored Markdown report."""
        lines = [
            f"# Notebook Sources & Content Summary: {self.notebook_title}",
            "",
            f"- **Notebook ID:** `{self.notebook_id}`",
            f"- **Total Sources:** {self.source_count}",
            f"- **Concatenated / Multi-part Sources:** {self.concatenated_source_count}",
            f"- **Total Sub-documents Identified:** {self.total_sub_document_count}",
            f"- **Generated At:** {self.generated_at}",
            "",
            "---",
            "",
            "## Summary Table of Sources",
            "",
            "| # | Source Title | Type | Multi-Document? | Sub-Docs | Keywords |",
            "|---|---|---|:---:|:---:|---|",
        ]

        for i, src in enumerate(self.sources, start=1):
            is_concat_str = "Yes" if src.is_concatenated else "No"
            sub_count = str(len(src.sub_documents)) if src.sub_documents else "-"
            kw_str = ", ".join(src.keywords[:4]) if src.keywords else "-"
            # Escape pipes in title
            safe_title = src.title.replace("|", "\\|")
            lines.append(
                f"| {i} | **{safe_title}** | `{src.source_type}` | {is_concat_str} | {sub_count} | {kw_str} |"
            )

        lines.extend(["", "---", "", "## Detailed Source Summaries", ""])

        for i, src in enumerate(self.sources, start=1):
            lines.append(f"### {i}. {src.title}")
            lines.append("")
            lines.append(f"- **Source ID:** `{src.source_id}`")
            lines.append(f"- **Type:** `{src.source_type}`")
            if src.url:
                lines.append(f"- **URL:** [{src.url}]({src.url})")
            if src.char_count:
                lines.append(f"- **Character Count:** {src.char_count:,}")
            if src.keywords:
                lines.append(f"- **Keywords:** {', '.join(f'`{kw}`' for kw in src.keywords)}")

            lines.append("")
            lines.append("#### Overview Summary")
            lines.append(src.summary or "_No summary available._")
            lines.append("")

            if src.is_concatenated:
                lines.append("> [!NOTE]")
                lines.append("> **Concatenated / Composite Document Detected:** This source contains multiple distinct documents, papers, reports, or sections.")
                lines.append("")

                if src.sub_documents:
                    lines.append("#### Contained Documents / Sub-Sections:")
                    lines.append("")
                    for j, doc in enumerate(src.sub_documents, start=1):
                        scope_str = f" _({doc.scope})_" if doc.scope else ""
                        author_str = f" — *Authors: {doc.authors}*" if doc.authors else ""
                        lines.append(f"{j}. **{doc.title}**{scope_str}{author_str}")
                        if doc.summary:
                            lines.append(f"   - **Summary:** {doc.summary}")
                        if doc.keywords:
                            lines.append(f"   - **Keywords:** {', '.join(doc.keywords)}")
                        lines.append("")

                if src.concatenation_analysis:
                    lines.append("<details>")
                    lines.append("<summary>Full Document Decomposition Analysis</summary>")
                    lines.append("")
                    lines.append(src.concatenation_analysis)
                    lines.append("")
                    lines.append("</details>")
                    lines.append("")

            lines.append("---")
            lines.append("")

        return "\n".join(lines)
