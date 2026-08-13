"""Core summarization and concatenated PDF / multi-document decomposition engine."""

import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Callable, Optional

from .client import NotebookLMClientWrapper
from .models import NotebookSummaryResult, SourceSummary, SubDocument


def parse_sub_documents_from_text(text: str) -> tuple[bool, list[SubDocument], str]:
    """Parse AI response to detect if source is concatenated and extract structured sub-documents.

    Returns:
        (is_concatenated, list_of_sub_documents, raw_analysis_text)
    """
    if not text or "[Error" in text:
        return False, [], text

    lower = text.lower()

    # Heuristic checks for single document vs composite/concatenated
    is_explicit_single = (
        "status: single_document" in lower
        or "is a single, unified document" in lower
        or "is a single continuous document" in lower
        or "serves entirely as a singular" in lower
        or "there are no indications of separate independent publications or standalone documents merged" in lower
    )

    is_explicit_concat = (
        "status: concatenated" in lower
        or "composite, concatenated" in lower
        or "concatenated collection" in lower
        or "merged these previously separate documents" in lower
        or "collection of multiple" in lower
        or "bundle of" in lower
        or "distinct documents and sub-sections" in lower
        or "consists of multiple independent" in lower
    )

    # If explicitly single and no concat markers, treat as single document
    if is_explicit_single and not is_explicit_concat:
        return False, [], text

    # Extract sub-documents based on bulleted or numbered items
    sub_docs: list[SubDocument] = []

    # Pattern for items like:
    # * **Chapter 1: ...** or 1. **Title** or ### 1. Title
    # followed by Scope, Summary, Authors, etc.
    item_blocks = re.split(r"\n(?=(?:(?:\*|\-|\d+\.)\s+\*\*|###?\s+))", text)

    for block in item_blocks:
        block = block.strip()
        if not block:
            continue

        # Look for title
        title_match = re.search(r"^(?:(?:\*|\-|\d+\.)\s+)?(?:\*\*)?(?:###?\s+)?([^\*\n:]+)(?:\*\*)?", block)
        if not title_match:
            continue

        candidate_title = title_match.group(1).strip()
        # Clean title of common prefixes
        candidate_title = re.sub(r"^(?:Title|Document Title|Section Title|Document|Chapter|Paper)\s*:\s*", "", candidate_title, flags=re.IGNORECASE)

        # Filter out introductory meta-sentences from being treated as sub-documents
        lower_title = candidate_title.lower()
        if (
            len(candidate_title) < 4
            or lower_title.endswith(":")
            or lower_title.endswith("as follows")
            or "structured as follows" in lower_title
            or "sub-sections contained within" in lower_title
            or "publication are structured" in lower_title
            or lower_title in ("the", "note", "status", "overview", "introduction")
        ):
            continue

        # Ignore non-title header blocks (like introductory sentences)
        if len(candidate_title) > 140 or "publication" in candidate_title.lower() and len(block) > 500:
            # Check if this block has strong sub-fields
            if not any(k in block.lower() for k in ["scope:", "summary:", "key focus", "author"]):
                continue

        # Extract scope (page range, chapter, etc.)
        scope = None
        scope_match = re.search(r"(?:Scope|Pages?|Location)\s*:\s*([^\n\*]+)", block, re.IGNORECASE)
        if scope_match:
            scope = scope_match.group(1).strip().strip("[]*")

        # Extract authors
        authors = None
        author_match = re.search(r"(?:Authors?|Organization|By)\s*:\s*([^\n\*]+)", block, re.IGNORECASE)
        if author_match:
            authors = author_match.group(1).strip().strip("[]*")

        # Extract summary
        summary = ""
        summary_match = re.search(r"(?:Key Focus\s*/\s*Summary|Summary|Focus)\s*:\s*([^\n]+(?:\n[^\n\*#]+)*)", block, re.IGNORECASE)
        if summary_match:
            summary = summary_match.group(1).strip().strip("[]*")
        else:
            # If no explicit Summary: label, extract following text paragraphs
            lines = [ln.strip() for ln in block.split("\n")[1:] if ln.strip() and not ln.startswith("*   **Scope") and not ln.startswith("- **Scope")]
            if lines:
                summary = " ".join(lines)

        # Extract keywords
        keywords = []
        kw_match = re.search(r"(?:Keywords?|Key Topics?|Topics?)\s*:\s*([^\n\*]+)", block, re.IGNORECASE)
        if kw_match:
            raw_kws = kw_match.group(1).strip().strip("[]*")
            keywords = [k.strip() for k in raw_kws.split(",") if k.strip()]

        # Clean citation marks like [1], [2, 3] from extracted text
        candidate_title = re.sub(r"\s*\[[\d,\s\-]+\]", "", candidate_title).strip("*").strip()
        if scope:
            scope = re.sub(r"\s*\[[\d,\s\-]+\]", "", scope).strip()
        if authors:
            authors = re.sub(r"\s*\[[\d,\s\-]+\]", "", authors).strip()
        if summary:
            summary = re.sub(r"\s*\[[\d,\s\-]+\]", "", summary).strip()

        if candidate_title and (summary or scope or authors):
            sub_docs.append(SubDocument(
                title=candidate_title,
                summary=summary,
                scope=scope,
                authors=authors,
                keywords=keywords,
            ))

    is_concat = len(sub_docs) > 1 or is_explicit_concat
    return is_concat, sub_docs, text


class NotebookSummarizer:
    """Orchestrates source listing, summarization, and multi-document decomposition."""

    def __init__(self, client: Optional[NotebookLMClientWrapper] = None, profile: Optional[str] = None):
        self.client = client or NotebookLMClientWrapper(profile=profile)

    def summarize_single_source(
        self,
        notebook_id: str,
        source_meta: dict,
        detect_concatenated_pdfs: bool = True,
    ) -> SourceSummary:
        """Process and summarize a single source, running deep decomposition if applicable."""
        source_id = source_meta.get("id", "")
        title = source_meta.get("title", "Untitled Source")
        source_type = source_meta.get("type", "unknown")
        url = source_meta.get("url")
        status = source_meta.get("status")

        # 1. Fetch standard AI guide (summary + keywords)
        guide = self.client.get_source_guide(source_id)
        summary_text = guide.get("summary", "")
        keywords = guide.get("keywords", [])

        # Fetch character count / metadata if available
        char_count = None
        try:
            fulltext_meta = self.client.get_source_fulltext(source_id)
            if fulltext_meta:
                char_count = fulltext_meta.get("char_count")
                if not source_type or source_type == "unknown":
                    source_type = fulltext_meta.get("source_type", source_type)
        except Exception:
            pass

        # 2. Check if deep PDF / concatenated document inspection is requested
        is_concatenated = False
        sub_documents: list[SubDocument] = []
        raw_decomposition = None

        is_potential_composite = (
            source_type.lower() in ("pdf", "uploaded_file", "file")
            or title.lower().endswith(".pdf")
            or any(term in title.lower() for term in ["report", "review", "proceedings", "collection", "bundle", "vol", "annual"])
            or (char_count and char_count > 30000)
        )

        if detect_concatenated_pdfs and is_potential_composite:
            decomposition_prompt = (
                f"Analyze the source '{title}' thoroughly.\n\n"
                "1. Determine whether this source is a single standalone document or a composite / concatenated multi-part publication "
                "(e.g., merged research papers, combined reports, distinct articles, statutory financial disclosures, or independent sections).\n"
                "2. If it is a composite / concatenated document containing multiple distinct documents or parts, list each distinct document/sub-section contained within it, including:\n"
                "   - Document / Section Title\n"
                "   - Authors / Organization (if identified)\n"
                "   - Scope / Page or Section indicators if available\n"
                "   - Key Focus / Summary (2-3 sentences)\n"
                "   - Keywords / Key Topics\n"
                "3. If it is a single standalone document with no merged sub-publications, clearly state 'STATUS: SINGLE_DOCUMENT' and describe its major sections."
            )

            raw_decomposition = self.client.query_source(
                notebook_id=notebook_id,
                query_text=decomposition_prompt,
                source_id=source_id,
                timeout=120.0,
            )

            is_concatenated, sub_documents, _ = parse_sub_documents_from_text(raw_decomposition)

        # If guide summary is empty, fallback to decomposition or prompt
        if not summary_text and raw_decomposition:
            summary_text = raw_decomposition[:500] + ("..." if len(raw_decomposition) > 500 else "")

        return SourceSummary(
            source_id=source_id,
            title=title,
            source_type=source_type,
            url=url,
            char_count=char_count,
            status=status,
            summary=summary_text,
            keywords=keywords,
            is_concatenated=is_concatenated,
            concatenation_analysis=raw_decomposition if is_concatenated else None,
            sub_documents=sub_documents,
        )

    def summarize_notebook(
        self,
        notebook_identifier: str,
        detect_concatenated_pdfs: bool = True,
        max_workers: int = 4,
        progress_callback: Optional[Callable[[str, int, int], None]] = None,
    ) -> NotebookSummaryResult:
        """Summarize all sources in a NotebookLM notebook.

        Args:
            notebook_identifier: Notebook UUID or Title / search term.
            detect_concatenated_pdfs: Whether to run deep multi-document decomposition.
            max_workers: Max concurrent threads for source querying.
            progress_callback: Callback fn(stage_description, completed, total).

        Returns:
            NotebookSummaryResult containing all summaries and sub-document decompositions.
        """
        # Resolve notebook
        nb_meta = self.client.find_notebook(notebook_identifier)
        notebook_id = nb_meta.get("id", "")
        notebook_title = nb_meta.get("title", "Untitled Notebook")

        if progress_callback:
            progress_callback(f"Retrieving sources for '{notebook_title}'...", 0, 0)

        raw_sources = self.client.get_notebook_sources(notebook_id)
        total_sources = len(raw_sources)

        if total_sources == 0:
            return NotebookSummaryResult(
                notebook_id=notebook_id,
                notebook_title=notebook_title,
                source_count=0,
                sources=[],
            )

        summarized_sources: list[SourceSummary] = [None] * total_sources  # type: ignore

        if progress_callback:
            progress_callback(f"Summarizing {total_sources} sources...", 0, total_sources)

        # Worker function for threading
        def _worker(idx: int, src: dict) -> tuple[int, SourceSummary]:
            summary = self.summarize_single_source(
                notebook_id=notebook_id,
                source_meta=src,
                detect_concatenated_pdfs=detect_concatenated_pdfs,
            )
            return idx, summary

        completed_count = 0
        with ThreadPoolExecutor(max_workers=max(1, min(max_workers, total_sources))) as executor:
            future_to_idx = {
                executor.submit(_worker, i, src): i
                for i, src in enumerate(raw_sources)
            }

            for future in as_completed(future_to_idx):
                idx, source_summary = future.result()
                summarized_sources[idx] = source_summary
                completed_count += 1
                if progress_callback:
                    progress_callback(
                        f"Processed {completed_count}/{total_sources}: {source_summary.title[:30]}",
                        completed_count,
                        total_sources,
                    )

        return NotebookSummaryResult(
            notebook_id=notebook_id,
            notebook_title=notebook_title,
            source_count=total_sources,
            sources=summarized_sources,
        )
