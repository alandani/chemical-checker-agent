"""Literature search through the Valency MCP server (Streamable HTTP, JSON-RPC).

Used as evidence only: when a compound has no recorded route, show papers that may describe its synthesis.
Every failure returns an empty list with a warning, so the pipeline carries on without it.
"""

from __future__ import annotations

import json
import logging
from typing import Any

import httpx

from core.config import get_settings
from core.models import Paper

log = logging.getLogger(__name__)

PROTOCOL_VERSION = "2025-11-25"
SEARCH_TOOL = "semantic_search_papers"


class ValencyError(RuntimeError):
    pass


def _body(resp: httpx.Response) -> dict:
    """The server may answer with plain JSON or a Server-Sent Events stream holding one JSON-RPC message."""
    if "text/event-stream" in resp.headers.get("content-type", ""):
        for line in resp.text.splitlines():
            if line.startswith("data:") and line[5:].strip():
                return json.loads(line[5:])
        raise ValencyError("Empty event stream from Valency")
    return resp.json() if resp.content else {}


class ValencyClient:
    def __init__(self, token: str, url: str, timeout: float = 20, transport: httpx.BaseTransport | None = None):
        self._url = url
        self._http = httpx.Client(timeout=timeout, transport=transport)
        self._headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
        }
        self._id = 0
        self._ready = False

    def close(self) -> None:
        self._http.close()

    def _post(self, payload: dict) -> httpx.Response:
        resp = self._http.post(self._url, headers=self._headers, json=payload)
        resp.raise_for_status()
        return resp

    def _initialize(self) -> None:
        resp = self._post(
            {
                "jsonrpc": "2.0",
                "id": self._next_id(),
                "method": "initialize",
                "params": {
                    "protocolVersion": PROTOCOL_VERSION,
                    "capabilities": {},
                    "clientInfo": {"name": "chempinski", "version": "0.1"},
                },
            }
        )
        msg = _body(resp)
        if "error" in msg:
            raise ValencyError(msg["error"].get("message", "initialize failed"))
        version = (msg.get("result") or {}).get("protocolVersion", PROTOCOL_VERSION)
        self._headers["MCP-Protocol-Version"] = version
        if sid := resp.headers.get("Mcp-Session-Id"):
            self._headers["Mcp-Session-Id"] = sid
        self._post({"jsonrpc": "2.0", "method": "notifications/initialized"})
        self._ready = True

    def _next_id(self) -> int:
        self._id += 1
        return self._id

    def call_tool(self, name: str, arguments: dict[str, Any]) -> Any:
        if not self._ready:
            self._initialize()
        msg = _body(
            self._post(
                {
                    "jsonrpc": "2.0",
                    "id": self._next_id(),
                    "method": "tools/call",
                    "params": {"name": name, "arguments": arguments},
                }
            )
        )
        if "error" in msg:
            raise ValencyError(msg["error"].get("message", f"{name} failed"))
        result = msg.get("result") or {}
        text = "".join(b.get("text", "") for b in result.get("content", []) if b.get("type") == "text")
        if result.get("isError"):
            raise ValencyError(text or f"{name} failed")
        try:
            return json.loads(text)
        except ValueError:
            return text


# ---------------- parsing ----------------

def _first(d: dict, *keys: str) -> Any:
    for k in keys:
        if d.get(k):
            return d[k]
    return None


def _year(value: Any) -> int | None:
    try:
        return int(str(value)[:4])
    except (TypeError, ValueError):
        return None


def parse_papers(data: Any) -> list[Paper]:
    """Tolerant of the exact response shape: a list, or a dict wrapping one under a common key."""
    if isinstance(data, dict):
        data = _first(data, "papers", "results", "items", "data") or []
    papers: list[Paper] = []
    for item in data if isinstance(data, list) else []:
        if not isinstance(item, dict) or not (title := _first(item, "title")):
            continue
        authors = _first(item, "authors") or []
        if isinstance(authors, str):
            authors = [a.strip() for a in authors.split(",") if a.strip()]
        authors = [a if isinstance(a, str) else str(a.get("name", "")) for a in authors]
        doi = _first(item, "doi")
        url = _first(item, "url", "link", "pdf_url") or (f"https://doi.org/{doi}" if doi else None)
        papers.append(
            Paper(
                title=" ".join(str(title).split()),
                authors=[a for a in authors if a][:6],
                year=_year(_first(item, "year", "published", "publication_date", "date", "created")),
                venue=_first(item, "venue", "journal"),
                doi=doi,
                url=url,
                abstract=_first(item, "abstract", "summary"),
            )
        )
    return papers


# ---------------- public API ----------------

def find_synthesis_papers(name: str, limit: int | None = None) -> tuple[list[Paper], str | None]:
    """Papers likely to describe a synthesis of `name`. Returns (papers, warning)."""
    settings = get_settings()
    if not settings.literature_enabled:
        return [], None
    limit = limit or settings.literature_max_papers
    client = ValencyClient(settings.valency_token, settings.valency_url, timeout=settings.http_timeout_s)
    try:
        data = client.call_tool(SEARCH_TOOL, {"query": f"synthesis of {name}", "limit": limit})
        return parse_papers(data)[:limit], None
    except Exception as exc:  # network, auth, protocol
        log.warning("Valency search failed: %s", exc)
        return [], "Literature search is unavailable right now."
    finally:
        client.close()
