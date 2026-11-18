"""Website extraction service.

Asynchronously fetches website HTML using HTTPX with SSRF protection,
anti-DNS-rebinding safeguards, response streaming limits, and parses
clean, structured content using BeautifulSoup.
"""

import asyncio
from datetime import datetime, timezone
import logging
import re
from typing import Dict, List, Optional, Set, Tuple
from urllib.parse import urljoin, urlparse, urlsplit

from bs4 import BeautifulSoup, Tag
from httpcore._backends.anyio import AnyIOBackend
import httpx

from app.config import Settings, get_settings
from app.schemas import ExtractedContent, ExtractedHeading, ExtractedLink
from app.utils import validators
from app.utils.validators import (
    SSRFSecurityError,
    URLValidationError,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Custom Exceptions
# ---------------------------------------------------------------------------

class WebsiteExtractionError(Exception):
    """Base exception for website extraction failures."""

    def __init__(self, message: str, status_code: int = 502, error_code: str = "EXTRACTION_FAILED"):
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.error_code = error_code


class ConnectionTimeoutError(WebsiteExtractionError):
    """Raised when a website request times out."""

    def __init__(self, message: str = "The target website took too long to respond."):
        super().__init__(message, status_code=504, error_code="GATEWAY_TIMEOUT")


class UpstreamConnectionError(WebsiteExtractionError):
    """Raised when connection to target website fails."""

    def __init__(self, message: str = "Failed to establish connection to target website."):
        super().__init__(message, status_code=502, error_code="UPSTREAM_CONNECT_ERROR")


class ResponseTooLargeError(WebsiteExtractionError):
    """Raised when response body exceeds maximum permitted size."""

    def __init__(self, max_bytes: int):
        super().__init__(
            f"The target webpage response exceeded the maximum allowed size ({max_bytes // (1024 * 1024)} MB).",
            status_code=413,
            error_code="PAYLOAD_TOO_LARGE",
        )


class UnsupportedContentTypeError(WebsiteExtractionError):
    """Raised when target URL does not return HTML."""

    def __init__(self, content_type: str):
        super().__init__(
            f"Target URL returned unsupported Content-Type '{content_type}'. Only HTML pages can be analyzed.",
            status_code=422,
            error_code="UNSUPPORTED_CONTENT_TYPE",
        )


class HTTPStatusExtractionError(WebsiteExtractionError):
    """Raised when upstream server returns an HTTP error status."""

    def __init__(self, status_code: int, status_message: str):
        super().__init__(
            f"Target website returned HTTP error: {status_code} ({status_message}).",
            status_code=502 if status_code >= 500 else 400,
            error_code=f"UPSTREAM_HTTP_{status_code}",
        )


class RedirectLimitExceededError(WebsiteExtractionError):
    """Raised when website exceeds maximum allowed redirects."""

    def __init__(self, max_redirects: int):
        super().__init__(
            f"Target website exceeded maximum redirect limit of {max_redirects} redirects.",
            status_code=502,
            error_code="TOO_MANY_REDIRECTS",
        )


# ---------------------------------------------------------------------------
# SSRF-Safe Network Backend (Mitigates DNS Rebinding)
# ---------------------------------------------------------------------------

class SSRFSafeBackend(AnyIOBackend):
    """Custom HTTPCore network backend preventing SSRF & DNS rebinding.

    Inspects DNS resolution at the exact moment of socket creation and connects
    directly to a verified safe public IP address.
    """

    async def connect_tcp(
        self,
        host: str,
        port: int,
        timeout: Optional[float] = None,
        local_address: Optional[str] = None,
        socket_options=None,
    ):
        # Resolve hostname and verify ALL returned IPs against SSRF restrictions
        safe_ips = await validators.resolve_and_validate_host(host, port)
        if not safe_ips:
            raise SSRFSecurityError(
                f"No safe public IP addresses available for host '{host}'."
            )

        # Pin the TCP connection to the first verified public IP
        pinned_ip = safe_ips[0]
        logger.debug("SSRFSafeBackend connecting to host=%s pinned_ip=%s port=%d", host, pinned_ip, port)

        # Connect directly to pinned IP address
        return await super().connect_tcp(
            host=pinned_ip,
            port=port,
            timeout=timeout,
            local_address=local_address,
            socket_options=socket_options,
        )


# ---------------------------------------------------------------------------
# Website Extractor Class
# ---------------------------------------------------------------------------

class WebsiteExtractor:
    """Production website HTML extractor and sanitizer."""

    def __init__(self, settings: Optional[Settings] = None):
        self.settings = settings or get_settings()

    def _build_transport(self) -> httpx.AsyncHTTPTransport:
        """Create an HTTPX transport with SSRF-safe connection pooling."""
        backend = SSRFSafeBackend()
        transport = httpx.AsyncHTTPTransport(
            verify=True,
            http1=True,
            http2=False,
            retries=0,
        )
        # Inject the custom network backend into httpcore's connection pool
        transport._pool._network_backend = backend
        return transport

    async def fetch_html(self, initial_url: str) -> Tuple[str, str, int]:
        """Fetch HTML content asynchronously with redirect tracking and size enforcement.

        Returns:
            Tuple of (raw_html, final_url, total_bytes_downloaded)
        """
        current_url, host, port = validators.validate_url(initial_url)
        redirect_count = 0
        transport = self._build_transport()

        timeout_config = httpx.Timeout(
            timeout=self.settings.REQUEST_TIMEOUT_SECONDS,
            connect=self.settings.CONNECT_TIMEOUT_SECONDS,
            read=self.settings.READ_TIMEOUT_SECONDS,
            write=5.0,
        )

        headers = {
            "User-Agent": self.settings.USER_AGENT,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
            "Accept-Encoding": "gzip, deflate",
            "Connection": "close",
        }

        async with httpx.AsyncClient(
            transport=transport,
            timeout=timeout_config,
            follow_redirects=False,
            verify=True,
        ) as client:
            while True:
                # 1. Pre-validate URL syntax and hostname
                current_url, host, port = validators.validate_url(current_url)

                # 2. Pre-validate DNS resolution against SSRF before making the request
                await validators.resolve_and_validate_host(host, port)

                try:
                    request = client.build_request("GET", current_url, headers=headers)
                    response = await client.send(request, stream=True)
                except httpx.ConnectTimeout as e:
                    logger.warning("Connection timeout fetching %s: %s", current_url, e)
                    raise ConnectionTimeoutError() from e
                except httpx.ReadTimeout as e:
                    logger.warning("Read timeout fetching %s: %s", current_url, e)
                    raise ConnectionTimeoutError() from e
                except (httpx.ConnectError, httpx.NetworkError) as e:
                    logger.warning("Network connection error fetching %s: %s", current_url, e)
                    raise UpstreamConnectionError(f"Could not connect to {current_url}: {e}") from e
                except (SSRFSecurityError, URLValidationError):
                    raise
                except Exception as e:
                    logger.error("Unexpected error fetching %s: %s", current_url, e, exc_info=True)
                    raise WebsiteExtractionError(f"Failed to fetch website: {e}") from e

                # Handle HTTP redirects (301, 302, 303, 307, 308)
                if response.is_redirect:
                    await response.aclose()
                    redirect_count += 1
                    if redirect_count > self.settings.MAX_REDIRECTS:
                        raise RedirectLimitExceededError(self.settings.MAX_REDIRECTS)

                    location = response.headers.get("location")
                    if not location:
                        raise WebsiteExtractionError(
                            "Received redirect status without a Location header.",
                            status_code=502,
                        )

                    next_url = urljoin(current_url, location)
                    logger.info("Following redirect %d: %s -> %s", redirect_count, current_url, next_url)
                    current_url, _, _ = validators.validate_url(next_url)
                    continue

                # Handle HTTP error status codes (4xx, 5xx)
                if response.is_error:
                    await response.aclose()
                    status_text = response.reason_phrase or "Error"
                    logger.warning("Upstream returned HTTP %d for %s", response.status_code, current_url)
                    raise HTTPStatusExtractionError(response.status_code, status_text)

                # Validate Content-Type
                content_type = response.headers.get("content-type", "").lower()
                if not any(t in content_type for t in ("text/html", "application/xhtml+xml", "text/plain")):
                    await response.aclose()
                    raise UnsupportedContentTypeError(content_type or "unknown")

                # Stream response bytes with strict size limit
                chunks: List[bytes] = []
                total_bytes = 0

                try:
                    async for chunk in response.aiter_bytes():
                        total_bytes += len(chunk)
                        if total_bytes > self.settings.MAX_RESPONSE_SIZE_BYTES:
                            await response.aclose()
                            raise ResponseTooLargeError(self.settings.MAX_RESPONSE_SIZE_BYTES)
                        chunks.append(chunk)
                finally:
                    await response.aclose()

                raw_bytes = b"".join(chunks)

                # Determine character encoding
                encoding = response.encoding or "utf-8"
                try:
                    html_text = raw_bytes.decode(encoding, errors="replace")
                except (LookupError, UnicodeDecodeError):
                    html_text = raw_bytes.decode("utf-8", errors="replace")

                return html_text, str(response.url), total_bytes

    def parse_html(self, raw_html: str, base_url: str, raw_size_bytes: int) -> ExtractedContent:
        """Parse raw HTML with BeautifulSoup and extract clean, structured business data."""
        # Prefer lxml parser for speed and resilience, fallback to html.parser
        try:
            soup = BeautifulSoup(raw_html, "lxml")
        except Exception:
            soup = BeautifulSoup(raw_html, "html.parser")

        # 1. Extract Page Title
        title = ""
        if soup.title and soup.title.string:
            title = soup.title.get_text(strip=True)
        if not title:
            # Fallback to OpenGraph / Twitter meta title
            og_title = soup.find("meta", property="og:title") or soup.find("meta", attrs={"name": "twitter:title"})
            if og_title and og_title.get("content"):
                title = og_title["content"].strip()
        if not title:
            h1_first = soup.find("h1")
            if h1_first:
                title = h1_first.get_text(strip=True)
        title = self._clean_whitespace(title) or "Untitled Website"

        # 2. Extract Meta Description
        meta_desc = ""
        meta_tag = (
            soup.find("meta", attrs={"name": re.compile(r"^description$", re.I)})
            or soup.find("meta", property="og:description")
            or soup.find("meta", attrs={"name": "twitter:description"})
        )
        if meta_tag and meta_tag.get("content"):
            meta_desc = self._clean_whitespace(meta_tag["content"])

        # 3. Extract Links before decomposing navigation elements
        links = self._extract_links(soup, base_url)

        # 4. Extract Services / Offerings
        services = self._extract_services(soup)

        # 5. Extract Headings
        headings, heading_items = self._extract_headings(soup)

        # 6. Sanitize DOM tree: remove scripts, styles, boilerplate, and clutter
        self._sanitize_soup(soup)

        # 7. Extract Meaningful Paragraphs
        paragraphs = self._extract_paragraphs(soup)

        # 8. Assemble Clean Text Summary for LLM Context
        clean_text_summary = self._build_clean_summary(
            url=base_url,
            title=title,
            meta_description=meta_desc,
            headings=heading_items,
            services=services,
            paragraphs=paragraphs,
            links=links,
        )

        word_count = len(clean_text_summary.split())
        char_count = len(clean_text_summary)

        return ExtractedContent(
            url=base_url,
            title=title,
            meta_description=meta_desc or None,
            headings=headings,
            heading_items=heading_items,
            paragraphs=paragraphs,
            services=services,
            links=links,
            clean_text_summary=clean_text_summary,
            word_count=word_count,
            character_count=char_count,
            raw_html_size_bytes=raw_size_bytes,
            extracted_at=datetime.now(timezone.utc),
        )

    def _sanitize_soup(self, soup: BeautifulSoup) -> None:
        """Decompose unwanted tags and boilerplate clutter."""
        # Non-content and executable tags to completely remove
        tags_to_decompose = [
            "script", "style", "noscript", "iframe", "svg", "canvas",
            "audio", "video", "template", "form", "select", "option",
            "input", "button", "picture", "source", "embed", "object"
        ]
        for tag_name in tags_to_decompose:
            for element in soup.find_all(tag_name):
                element.decompose()

        # Boilerplate containers to remove (headers, footers, cookie banners, navigation menus)
        boilerplate_tags = ["header", "footer", "nav"]
        for b_tag in boilerplate_tags:
            for element in soup.find_all(b_tag):
                element.decompose()

        # Elements with boilerplate class names or IDs
        boilerplate_pattern = re.compile(
            r"(cookie|consent|banner|newsletter|modal|popup|sidebar|social-share|advertisement|ad-container|widget)",
            re.I,
        )
        for element in soup.find_all(attrs={"class": boilerplate_pattern}):
            # Don't decompose if it looks like main service or content
            class_str = " ".join(element.get("class", []))
            if not re.search(r"(service|feature|solution|product)", class_str, re.I):
                element.decompose()

        for element in soup.find_all(attrs={"id": boilerplate_pattern}):
            id_str = str(element.get("id", ""))
            if not re.search(r"(service|feature|solution|product)", id_str, re.I):
                element.decompose()

    def _extract_headings(self, soup: BeautifulSoup) -> Tuple[Dict[str, List[str]], List[ExtractedHeading]]:
        """Extract structured and sequential headings (h1 - h6)."""
        headings: Dict[str, List[str]] = {}
        heading_items: List[ExtractedHeading] = []
        seen_texts: Set[str] = set()

        for tag in soup.find_all(["h1", "h2", "h3", "h4", "h5", "h6"]):
            text = self._clean_whitespace(tag.get_text(strip=True))
            if not text or len(text) < 2 or text.lower() in seen_texts:
                continue

            seen_texts.add(text.lower())
            level = tag.name.lower()

            if level not in headings:
                headings[level] = []

            if len(headings[level]) < self.settings.MAX_HEADINGS:
                headings[level].append(text)

            if len(heading_items) < self.settings.MAX_HEADINGS:
                heading_items.append(ExtractedHeading(level=level, text=text))

        return headings, heading_items

    def _extract_services(self, soup: BeautifulSoup) -> List[str]:
        """Extract visible service offerings, product features, or capabilities."""
        services: List[str] = []
        seen_services: Set[str] = set()

        # Keyword pattern targeting service/product sections
        service_pattern = re.compile(
            r"(service|solution|feature|offering|product|capability|what-we-do)",
            re.I,
        )

        # 1. Look for targeted containers with relevant class or id
        candidate_containers = soup.find_all(
            ["section", "div", "article"],
            attrs={"class": service_pattern},
        ) + soup.find_all(
            ["section", "div", "article"],
            attrs={"id": service_pattern},
        )

        for container in candidate_containers:
            # Extract cards, items, subheadings, or bullet points within the container
            items = container.find_all(["h3", "h4", "li", "strong"])
            for item in items:
                text = self._clean_whitespace(item.get_text(strip=True))
                # Validate length and filter common noise
                if 4 <= len(text) <= 120 and text.lower() not in seen_services:
                    if not re.search(r"(learn more|read more|contact us|click here|all rights)", text, re.I):
                        seen_services.add(text.lower())
                        services.append(text)
                        if len(services) >= self.settings.MAX_SERVICES:
                            return services

        # 2. Look for headings with "Services", "What We Do", "Our Solutions"
        service_headings = soup.find_all(
            ["h1", "h2", "h3"],
            string=re.compile(r"(services|what we do|our solutions|features|capabilities)", re.I),
        )
        for heading in service_headings:
            parent = heading.find_parent(["section", "div"])
            if parent:
                for card in parent.find_all(["h3", "h4", "li"]):
                    text = self._clean_whitespace(card.get_text(strip=True))
                    if 4 <= len(text) <= 120 and text.lower() not in seen_services:
                        seen_services.add(text.lower())
                        services.append(text)
                        if len(services) >= self.settings.MAX_SERVICES:
                            return services

        return services

    def _extract_paragraphs(self, soup: BeautifulSoup) -> List[str]:
        """Extract meaningful, clean paragraphs from the page content."""
        paragraphs: List[str] = []
        seen_texts: Set[str] = set()

        for p in soup.find_all("p"):
            text = self._clean_whitespace(p.get_text(strip=True))
            # Filter trivial snippets, disclaimers, and boilerplate
            if len(text) < 25:
                continue
            if re.search(r"(all rights reserved|copyright ©|cookie policy|terms of service|privacy policy)", text, re.I):
                continue

            normalized = text.lower()
            if normalized in seen_texts:
                continue

            seen_texts.add(normalized)
            paragraphs.append(text)

            if len(paragraphs) >= self.settings.MAX_PARAGRAPHS:
                break

        return paragraphs

    def _extract_links(self, soup: BeautifulSoup, base_url: str) -> List[ExtractedLink]:
        """Extract and categorize relevant hyperlinks."""
        links: List[ExtractedLink] = []
        seen_urls: Set[str] = set()
        base_domain = urlparse(base_url).netloc.lower()

        for a in soup.find_all("a", href=True):
            raw_href = a.get("href", "").strip()
            if not raw_href or raw_href.startswith(("#", "javascript:", "mailto:", "tel:")):
                continue

            resolved_url = urljoin(base_url, raw_href)
            parsed_resolved = urlsplit(resolved_url)

            if parsed_resolved.scheme.lower() not in ("http", "https"):
                continue

            # Strip fragments for deduplication
            clean_url = f"{parsed_resolved.scheme}://{parsed_resolved.netloc}{parsed_resolved.path}"
            if parsed_resolved.query:
                clean_url += f"?{parsed_resolved.query}"

            if clean_url in seen_urls:
                continue
            seen_urls.add(clean_url)

            anchor_text = self._clean_whitespace(a.get_text(strip=True))
            if not anchor_text:
                anchor_text = clean_url

            link_domain = parsed_resolved.netloc.lower()
            is_internal = (link_domain == base_domain) or link_domain.endswith(f".{base_domain}")

            links.append(
                ExtractedLink(
                    text=anchor_text[:100],
                    url=clean_url,
                    is_internal=is_internal,
                )
            )

            if len(links) >= self.settings.MAX_LINKS:
                break

        return links

    def _build_clean_summary(
        self,
        url: str,
        title: str,
        meta_description: str,
        headings: List[ExtractedHeading],
        services: List[str],
        paragraphs: List[str],
        links: List[ExtractedLink],
    ) -> str:
        """Assemble structured, concise plain text formatted for LLM business analysis."""
        lines: List[str] = []

        lines.append(f"# Website Analysis Data for {url}")
        lines.append(f"**Title:** {title}")
        if meta_description:
            lines.append(f"**Meta Description:** {meta_description}")
        lines.append("")

        if headings:
            lines.append("## Key Headings:")
            for h in headings[:25]:
                lines.append(f"- [{h.level.upper()}] {h.text}")
            lines.append("")

        if services:
            lines.append("## Identified Services / Offerings:")
            for s in services[:20]:
                lines.append(f"- {s}")
            lines.append("")

        if paragraphs:
            lines.append("## Main Content:")
            for p in paragraphs[:30]:
                lines.append(f"{p}\n")

        if links:
            internal_links = [l for l in links if l.is_internal][:15]
            if internal_links:
                lines.append("## Key Navigation & Internal Links:")
                for l in internal_links:
                    lines.append(f"- {l.text}: {l.url}")
                lines.append("")

        full_text = "\n".join(lines).strip()

        # Enforce maximum character limit for LLM prompt optimization
        max_len = self.settings.MAX_EXTRACTED_CONTENT_LENGTH
        if len(full_text) > max_len:
            # Truncate at nearest sentence or word boundary
            truncated = full_text[:max_len]
            last_period = truncated.rfind(".")
            if last_period > max_len * 0.8:
                truncated = truncated[:last_period + 1]
            full_text = truncated + "\n\n[Content truncated for optimal LLM context size]"

        return full_text

    @staticmethod
    def _clean_whitespace(text: str) -> str:
        """Collapse multiple whitespace characters and newlines into single spaces."""
        if not text:
            return ""
        return " ".join(text.split()).strip()


async def extract_website_content(url: str, settings: Optional[Settings] = None) -> ExtractedContent:
    """Convenience function to fetch and parse a website."""
    extractor = WebsiteExtractor(settings)
    raw_html, final_url, raw_bytes = await extractor.fetch_html(url)
    return extractor.parse_html(raw_html, final_url, raw_bytes)
