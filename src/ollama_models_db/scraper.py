from __future__ import annotations

import logging
import re
import time
from datetime import datetime, timezone
from typing import Optional

import httpx
from bs4 import BeautifulSoup, Tag

from .models import ModelEntry, ModelTag

logger = logging.getLogger(__name__)

SEARCH_URL = "https://ollama.com/search"
LIBRARY_URL = "https://ollama.com/library"

_relative_time_re = re.compile(
    r"(?:about\s+)?(\d+)\s*(second|minute|hour|day|week|month|year)s?\s*ago",
    re.IGNORECASE,
)


def _parse_relative_time(text: str) -> Optional[datetime]:
    m = _relative_time_re.search(text.strip())
    if not m:
        return None
    n = int(m.group(1))
    unit = m.group(2).lower()
    now = datetime.now(timezone.utc)
    if unit == "second":
        delta = n
    elif unit == "minute":
        delta = n * 60
    elif unit == "hour":
        delta = n * 3600
    elif unit == "day":
        delta = n * 86400
    elif unit == "week":
        delta = n * 604800
    elif unit == "month":
        delta = n * 2592000
    elif unit == "year":
        delta = n * 31536000
    else:
        return None
    return datetime.fromtimestamp(now.timestamp() - delta, tz=timezone.utc)


def _parse_pull_count(text: str) -> int:
    text = text.strip().upper()
    text = text.replace(",", "")
    if text.endswith("K"):
        return int(float(text[:-1]) * 1000)
    if text.endswith("M"):
        return int(float(text[:-1]) * 1_000_000)
    if text.endswith("B"):
        return int(float(text[:-1]) * 1_000_000_000)
    return int(text) if text else 0


def _parse_size_gb(text: str) -> Optional[float]:
    text = text.strip().upper()
    m = re.search(r"([\d.]+)\s*GB", text)
    if m:
        return float(m.group(1))
    m = re.search(r"([\d.]+)\s*MB", text)
    if m:
        return float(m.group(1)) / 1024
    return None


def _parse_context_window(text: str) -> Optional[int]:
    m = re.search(r"(\d+)\s*[Kk]", text)
    if m:
        return int(m.group(1)) * 1024
    return None


class Scraper:
    def __init__(self, client: Optional[httpx.Client] = None):
        self.client = client or httpx.Client(
            follow_redirects=True,
            timeout=30,
            headers={
                "User-Agent": (
                    "Mozilla/5.0 (compatible; ollama-models-db/0.1; "
                    "+https://github.com/robbiec/ollama-models-db)"
                ),
            },
        )

    def search_models(
        self, query: Optional[str] = None, delay: float = 1.0
    ) -> list[ModelEntry]:
        models: list[ModelEntry] = []
        page = 1

        while True:
            url = f"{SEARCH_URL}?page={page}"
            if query:
                url += f"&q={query}"

            logger.info("Fetching search page %s", url)
            resp = self.client.get(
                url,
                headers={"HX-Request": "true"},
            )
            resp.raise_for_status()
            soup = BeautifulSoup(resp.text, "lxml")

            items = soup.select("li[x-test-model]")
            if not items:
                logger.info("No more models found on page %d", page)
                break

            for item in items:
                entry = self._parse_search_item(item)
                if entry:
                    models.append(entry)

            page += 1
            if delay:
                time.sleep(delay)

        return models

    def _parse_search_item(self, item: Tag) -> Optional[ModelEntry]:
        title_span = item.select_one("[x-test-search-response-title]")
        if not title_span:
            return None
        name = title_span.get_text(strip=True)

        link = item.find("a")
        href = link.get("href", "") if link else ""
        url = f"https://ollama.com{href}" if href.startswith("/") else href

        desc_p = item.select_one("p.max-w-lg")
        description = desc_p.get_text(strip=True) if desc_p else ""

        pull_span = item.select_one("[x-test-pull-count]")
        pull_count = _parse_pull_count(pull_span.get_text(strip=True)) if pull_span else 0

        tag_span = item.select_one("[x-test-tag-count]")
        tag_count = int(tag_span.get_text(strip=True)) if tag_span else 0

        updated_span = item.select_one("[x-test-updated]")
        updated_text = updated_span.get_text(strip=True) if updated_span else ""
        updated_ts = _parse_relative_time(updated_text) if updated_text else None

        caps: list[str] = []
        for cap in item.select("[x-test-capability]"):
            caps.append(cap.get_text(strip=True))

        sizes: list[str] = []
        for sz in item.select("[x-test-size]"):
            sizes.append(sz.get_text(strip=True))

        cloud_badge = item.select_one(
            "span.inline-flex.items-center.rounded-md.bg-cyan-50"
        )
        is_cloud = cloud_badge is not None

        return ModelEntry(
            name=name,
            description=description,
            url=url,
            pull_count=pull_count,
            tag_count=tag_count,
            updated_text=updated_text,
            updated_timestamp=updated_ts,
            capabilities=caps,
            sizes=sizes,
            is_cloud=is_cloud,
        )

    def model_tags(self, model_name: str, delay: float = 0.5) -> list[ModelTag]:
        url = f"{LIBRARY_URL}/{model_name}"
        logger.info("Fetching model page %s", url)
        resp = self.client.get(url)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "lxml")

        models_section = soup.find(
            "section",
            class_="flex flex-1 flex-col",
        )
        if not models_section:
            logger.warning("No models section found for %s", model_name)
            if delay:
                time.sleep(delay)
            return []

        container = models_section.select_one(
            "div.min-w-full.divide-y.divide-gray-200"
        )
        if not container:
            logger.warning("No tag container found for %s", model_name)
            if delay:
                time.sleep(delay)
            return []

        tags: list[ModelTag] = []
        seen: set[str] = set()

        # First row is the header; skip it
        rows = container.find_all("div", recursive=False)
        for row in rows[1:]:
            link = row.select_one("a[href*=':']")
            if not link:
                continue

            href = link.get("href", "")
            tag_name = href.split(":", 1)[1] if ":" in href else "latest"
            if tag_name in seen or tag_name == "latest":
                continue
            seen.add(tag_name)

            is_latest = bool(row.select_one(".border-blue-500"))
            is_mlx = bool(row.select_one(".border-neutral-600"))

            size_el = row.select_one("[x-test-model-tag-size]")
            size_gb = _parse_size_gb(size_el.get_text(strip=True)) if size_el else None

            cols = row.select("p.col-span-2")
            context_window = None
            modalities: list[str] = []
            if len(cols) >= 3:
                context_window = _parse_context_window(
                    cols[1].get_text(strip=True)
                )
                mod_text = cols[2].get_text(strip=True)
                modalities = [m.strip() for m in mod_text.split(",") if m.strip()]

            tags.append(
                ModelTag(
                    model_name=model_name,
                    tag=tag_name,
                    size_gb=size_gb,
                    context_window=context_window,
                    modalities=modalities,
                    is_latest=is_latest,
                    is_mlx=is_mlx,
                )
            )

        if delay:
            time.sleep(delay)
        return tags
