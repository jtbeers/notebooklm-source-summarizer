"""NotebookLM Source Summarizer & Concatenated PDF Decomposition Toolkit."""

from .client import NotebookLMClientWrapper
from .formatters import print_console_report
from .models import NotebookSummaryResult, SourceSummary, SubDocument
from .summarizer import NotebookSummarizer

__version__ = "0.1.0"
__all__ = [
    "NotebookLMClientWrapper",
    "NotebookSummarizer",
    "NotebookSummaryResult",
    "SourceSummary",
    "SubDocument",
    "print_console_report",
]
