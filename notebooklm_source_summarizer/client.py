"""Client wrapper and authentication management for NotebookLM."""

import glob
import json
import os
import sys
from pathlib import Path
from typing import Any, Optional


def _ensure_notebooklm_tools_available() -> None:
    """Ensure notebooklm_tools is importable by searching known uv/pipx paths if needed."""
    try:
        import notebooklm_tools  # noqa: F401
        return
    except ImportError:
        pass

    # Search uv tool paths
    search_patterns = [
        str(Path.home() / ".local/share/uv/tools/notebooklm-mcp-cli/lib/python*/site-packages"),
        str(Path.home() / ".local/pipx/venvs/notebooklm-mcp-cli/lib/python*/site-packages"),
        "/opt/homebrew/lib/python*/site-packages",
    ]
    for pattern in search_patterns:
        matches = glob.glob(pattern)
        for match in matches:
            if match not in sys.path:
                sys.path.insert(0, match)
                try:
                    import notebooklm_tools  # noqa: F401
                    return
                except ImportError:
                    pass


# Ensure package is discoverable
_ensure_notebooklm_tools_available()


class NotebookLMClientWrapper:
    """High-level wrapper around NotebookLMClient for notebook and source inspection."""

    def __init__(self, profile: Optional[str] = None):
        self.profile = profile
        self._client = None
        self._init_client()

    def _init_client(self) -> None:
        """Initialize the underlying NotebookLMClient using available credentials."""
        _ensure_notebooklm_tools_available()

        try:
            from notebooklm_tools.cli.utils import get_client
            from notebooklm_tools.core.auth import AuthManager, get_cache_path
        except ImportError as e:
            raise RuntimeError(
                f"Could not import notebooklm_tools: {e}. "
                "Please ensure notebooklm-mcp-cli is installed (e.g. `uv tool install notebooklm-mcp-cli` "
                "or `pip install notebooklm-mcp-cli`)."
            ) from e

        # 1. Check environment variable
        if os.environ.get("NOTEBOOKLM_COOKIES"):
            from notebooklm_tools.core.client import NotebookLMClient
            from notebooklm_tools.core.auth import parse_cookies_from_chrome_format
            cookies = parse_cookies_from_chrome_format(os.environ["NOTEBOOKLM_COOKIES"])
            self._client = NotebookLMClient(cookies=cookies)
            return

        # 2. Check profile via AuthManager
        manager = AuthManager(self.profile or "default")
        if not manager.profile_exists():
            # Check if default cache path exists as fallback
            default_cache = get_cache_path()
            if not default_cache.exists():
                raise RuntimeError(
                    f"No active NotebookLM session found for profile '{manager.profile_name}'. "
                    "Please authenticate first by running `nlm login` in your terminal."
                )

        self._client = get_client(self.profile)

    @property
    def client(self) -> Any:
        if self._client is None:
            self._init_client()
        return self._client

    def list_notebooks(self) -> list[dict[str, Any]]:
        """List all notebooks in the user's account, normalized as dicts."""
        try:
            raw_notebooks = self.client.list_notebooks()
            normalized = []
            for nb in raw_notebooks:
                if isinstance(nb, dict):
                    normalized.append(nb)
                else:
                    normalized.append({
                        "id": getattr(nb, "id", ""),
                        "title": getattr(nb, "title", "Untitled"),
                        "source_count": getattr(nb, "source_count", 0),
                        "sources": getattr(nb, "sources", []),
                        "created_at": getattr(nb, "created_at", None),
                        "modified_at": getattr(nb, "modified_at", None),
                        "emoji": getattr(nb, "emoji", None),
                    })
            return normalized
        except Exception as e:
            raise RuntimeError(f"Failed to list notebooks: {e}") from e

    def find_notebook(self, identifier: str) -> dict[str, Any]:
        """Find a notebook by exact ID, title, or fuzzy title substring."""
        notebooks = self.list_notebooks()
        if not notebooks:
            raise ValueError("No notebooks found in your NotebookLM account.")

        clean_id = identifier.strip()

        # 1. Exact ID match
        for nb in notebooks:
            if nb.get("id") == clean_id:
                return nb

        # 2. Exact Title match (case-insensitive)
        for nb in notebooks:
            if nb.get("title", "").strip().lower() == clean_id.lower():
                return nb

        # 3. Substring match
        matches = [
            nb for nb in notebooks
            if clean_id.lower() in nb.get("title", "").lower()
        ]
        if len(matches) == 1:
            return matches[0]
        elif len(matches) > 1:
            # Prefer match with closest length or starts-with
            starts = [nb for nb in matches if nb.get("title", "").lower().startswith(clean_id.lower())]
            if len(starts) == 1:
                return starts[0]
            titles = ", ".join(f"'{nb.get('title')}' ({nb.get('id')})" for nb in matches[:5])
            raise ValueError(
                f"Ambiguous notebook identifier '{identifier}'. Multiple matches found: {titles}"
            )

        raise ValueError(
            f"Notebook '{identifier}' not found. Run with `--list` to view available notebooks."
        )

    def get_notebook_sources(self, notebook_id: str) -> list[dict[str, Any]]:
        """Get all sources belonging to a notebook with their metadata and types."""
        try:
            return self.client.get_notebook_sources_with_types(notebook_id)
        except Exception as e:
            raise RuntimeError(f"Failed to get sources for notebook {notebook_id}: {e}") from e

    def get_source_guide(self, source_id: str) -> dict[str, Any]:
        """Get AI summary and keywords for a source."""
        try:
            guide = self.client.get_source_guide(source_id)
            return {
                "summary": guide.get("summary", "") if guide else "",
                "keywords": guide.get("keywords", []) if guide else [],
            }
        except Exception:
            return {"summary": "", "keywords": []}

    def get_source_fulltext(self, source_id: str) -> dict[str, Any]:
        """Get the indexed full text of a source."""
        try:
            return self.client.get_source_fulltext(source_id)
        except Exception:
            return {"content": "", "title": "", "source_type": "", "char_count": 0}

    def query_source(
        self,
        notebook_id: str,
        query_text: str,
        source_id: str,
        timeout: float = 120.0,
    ) -> str:
        """Query the notebook model focused specifically on one source."""
        try:
            resp = self.client.query(
                notebook_id=notebook_id,
                query_text=query_text,
                source_ids=[source_id],
                timeout=timeout,
            )
            if resp and isinstance(resp, dict):
                return resp.get("answer", "")
            return ""
        except Exception as e:
            return f"[Error querying source: {e}]"
