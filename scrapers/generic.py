"""Generic scraper: fetch the vendor's search page, then let Claude Haiku pull out the offers.

This avoids writing a parser per site. A vendor-specific subclass can override
`fetch()` or `parse()` when a site needs more care (pagination, product sub-pages).
"""

from __future__ import annotations

import logging

import httpx
from selectolax.lexbor import LexborHTMLParser as HTMLParser

from core import llm
from core.config import get_settings
from core.models import Compound
from scrapers.base import RawOffer, ScrapeError, VendorScraper

log = logging.getLogger(__name__)

MAX_PAGE_CHARS = 24_000

OFFER_SCHEMA = {
    "type": "object",
    "properties": {
        "compound_found": {
            "type": "boolean",
            "description": "True only if the page lists the exact target compound (matching CAS or name).",
        },
        "offers": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "pack": {"type": "string", "description": "Pack size exactly as shown, e.g. '5 g', '100mg'"},
                    "price": {"type": ["number", "null"], "description": "Price for that pack, null if not shown"},
                    "currency": {"type": ["string", "null"], "description": "ISO code, e.g. USD, AUD, CNY, JPY, EUR"},
                    "purity": {"type": ["number", "null"], "description": "Purity in percent, e.g. 98"},
                    "in_stock": {"type": ["boolean", "null"]},
                    "quote_only": {"type": "boolean", "description": "True if price is 'inquire' / 'request a quote' / login"},
                    "url": {"type": ["string", "null"], "description": "Product page URL if shown"},
                },
                "required": ["pack", "quote_only"],
            },
        },
    },
    "required": ["compound_found", "offers"],
}


def page_text(html: str) -> str:
    tree = HTMLParser(html)
    for tag in tree.css("script, style, noscript, svg, header, footer, nav"):
        tag.decompose()
    text = tree.body.text(separator="\n") if tree.body else tree.text(separator="\n")
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    return "\n".join(lines)[:MAX_PAGE_CHARS]


class GenericSearchScraper(VendorScraper):
    def search_term(self, compound: Compound) -> str:
        return compound.cas or compound.name or compound.smiles

    def search_url(self, compound: Compound) -> str:
        if not self.info.search_url:
            raise ScrapeError(f"{self.name}: no search URL configured")
        from urllib.parse import quote

        return self.info.search_url.format(q=quote(self.search_term(compound)))

    def fetch(self, url: str) -> str:
        settings = get_settings()
        if self.info.requires_js:
            return self._fetch_with_browser(url, settings.scrape_timeout_s)
        try:
            r = httpx.get(
                url,
                timeout=settings.scrape_timeout_s,
                follow_redirects=True,
                headers={"User-Agent": settings.user_agent, "Accept-Language": "en"},
            )
            r.raise_for_status()
            return r.text
        except httpx.HTTPError as exc:
            raise ScrapeError(f"{self.name}: {exc}") from exc

    def _fetch_with_browser(self, url: str, timeout_s: int) -> str:
        try:
            from playwright.sync_api import sync_playwright
        except ImportError as exc:
            raise ScrapeError(
                f"{self.name} needs a browser: pip install playwright && playwright install chromium"
            ) from exc
        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                page = browser.new_page(user_agent=get_settings().user_agent)
                page.goto(url, timeout=timeout_s * 1000, wait_until="networkidle")
                html = page.content()
                browser.close()
                return html
        except Exception as exc:
            raise ScrapeError(f"{self.name}: browser fetch failed: {exc}") from exc

    def parse(self, html: str, compound: Compound, url: str) -> list[RawOffer]:
        if not get_settings().llm_enabled:
            raise ScrapeError(f"{self.name}: set ANTHROPIC_API_KEY to extract prices from pages")
        prompt = (
            f"You are extracting product offers from a chemical vendor's search results page ({self.name}).\n"
            f"Target compound: name={compound.name!r}, CAS={compound.cas!r}, formula={compound.formula!r}.\n"
            "Only include offers for exactly this compound (not salts, derivatives or kits). "
            "Report every pack size with its price. If prices are hidden behind login or 'inquire', "
            "set quote_only=true and price=null. Do not guess prices.\n\n"
            f"Page URL: {url}\n--- PAGE TEXT ---\n{page_text(html)}"
        )
        data = llm.extract(
            prompt,
            tool_name="record_offers",
            tool_description="Record the offers found on the page for the target compound.",
            input_schema=OFFER_SCHEMA,
        )
        if data is None:
            raise ScrapeError(f"{self.name}: extraction failed")
        if not data.get("compound_found"):
            return []
        return [
            RawOffer(
                pack=o.get("pack"),
                price=o.get("price"),
                currency=o.get("currency"),
                purity=o.get("purity"),
                in_stock=o.get("in_stock"),
                quote_only=bool(o.get("quote_only")),
                url=o.get("url") or url,
            )
            for o in data.get("offers", [])
        ]

    def search(self, compound: Compound) -> list[RawOffer]:
        url = self.search_url(compound)
        html = self.fetch(url)
        return self.parse(html, compound, url)
