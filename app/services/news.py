"""Crypto-news ingestion from legitimate public RSS feeds (no API key).

The service normalizes every feed item into a small dict, tags articles that
match a tracked asset, de-duplicates by URL and keeps the result in a SQLite
cache. All network work happens inside a short TTL window so the dashboard
never depends on live requests; failures degrade to ``{"news": [], ...}`` and
never raise.
"""

from __future__ import annotations

import re
import threading
import time
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime

import requests

from app.core.config import settings

# Public RSS feeds (name -> feed URL). All are editorial crypto publications;
# the altcoin-heavy ones (CryptoPotato, U.Today) keep per-asset coverage broad
# so every tracked card usually finds a genuinely relevant story.
SOURCES: tuple[tuple[str, str], ...] = (
    ("CoinDesk", "https://www.coindesk.com/arc/outboundfeeds/rss/"),
    ("Cointelegraph", "https://cointelegraph.com/rss"),
    ("Decrypt", "https://decrypt.co/feed"),
    ("The Block", "https://www.theblock.co/rss.xml"),
    ("Bitcoin Magazine", "https://bitcoinmagazine.com/feed"),
    ("CryptoPotato", "https://cryptopotato.com/feed/"),
    ("U.Today", "https://u.today/rss"),
)

NEWS_TTL_SECONDS = 15 * 60
PER_SOURCE_CAP = 20
FEED_TIMEOUT_SECONDS = 8

# Coin id -> extra search aliases. The coin id and its display name are always
# searched as well (e.g. "ethereum" matches "Ethereum", "ETH" matches "eth").
_COIN_ALIASES: dict[str, tuple[str, ...]] = {
    "bitcoin": ("btc",),
    "ethereum": ("eth",),
    "solana": ("sol",),
    "binancecoin": ("binance", "bnb"),
    "dogecoin": ("doge",),
    "ripple": ("xrp",),
    "cardano": ("ada",),
    "litecoin": ("ltc",),
    "polkadot": ("dot",),
    "chainlink": ("link",),
    "matic-network": ("polygon", "matic"),
    "avalanche-2": ("avax",),
}

# Broad market terms keep market-wide crypto news in the general feed even when
# no specific tracked asset is mentioned.
_GENERAL_TERMS: tuple[str, ...] = (
    "crypto", "cryptocurrency", "market", "token", "blockchain", "altcoin",
    "stablecoin", "etf", "sec", "federal reserve", "bitcoin", "ethereum",
    "defi", "halving", "mining", "regulat",
)

_CACHE: list[dict] | None = None
_CACHE_AT: float = 0.0
_FETCH_ERROR: str | None = None

_TAG_RE = re.compile(r"<[^>]+>")
_WS_RE = re.compile(r"\s+")

_SESSION_LOCAL = threading.local()


def _session() -> requests.Session:
    """Per-thread ``requests.Session`` (connection pooling, env-proxy safe)."""
    session = getattr(_SESSION_LOCAL, "session", None)
    if session is None:
        session = requests.Session()
        session.trust_env = False
        session.headers.update({"User-Agent": "Mozilla/5.0 (AI-Market-Intelligence/1.0)"})
        _SESSION_LOCAL.session = session
    return session

_TRACKED_COINS = tuple(settings.tracked_coins)


def _clean_html(text: str | None) -> str:
    if not text:
        return ""
    return _WS_RE.sub(" ", _TAG_RE.sub(" ", text)).strip()


def _parse_date(value: str | None) -> datetime | None:
    if not value:
        return None
    parsed = None
    try:
        parsed = parsedate_to_datetime(value)
    except (TypeError, ValueError):
        parsed = None
    if parsed is None:
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            parsed = None
    if parsed is None:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _node_text(element: ET.Element, tag: str) -> str | None:
    node = element.find(tag)
    if node is None or not node.text:
        return None
    return node.text.strip()


def _extract_image(entry: ET.Element) -> str | None:
    """Best-effort article image from media:content/enclosure/thumbnail or the
    first <img> inside the description. Returns an absolute http(s) URL or None.
    """
    for candidate in entry.findall("content") + entry.findall("enclosure") + entry.findall("thumbnail"):
        url = candidate.get("url")
        if not url or not url.startswith("http"):
            continue
        kind = candidate.get("type", "")
        medium = candidate.get("medium", "")
        if medium and medium != "image":
            continue
        if kind and not kind.startswith("image"):
            continue
        return url
    raw = (_node_text(entry, "description") or _node_text(entry, "content") or "")
    match = re.search(r'<img[^>]+src=["\']?([^"\'>\s]+)', raw)
    if match and match.group(1).startswith("http"):
        return match.group(1)
    return None


def _parse_feed(xml_text: str, source: str) -> list[dict]:
    root = ET.fromstring(xml_text)
    for element in root.iter():
        tag = element.tag
        if isinstance(tag, str) and "}" in tag:
            element.tag = tag.split("}", 1)[1]
    items: list[dict] = []
    if root.tag == "feed":
        entries = root.findall("entry")
    else:
        entries = list(root.iter("item"))
    for entry in entries:
        title = _node_text(entry, "title")
        if not title:
            continue
        link: str | None = None
        link_node = entry.find("link")
        if link_node is not None:
            link = link_node.get("href") or (link_node.text or "").strip() or None
        if not link:
            continue
        published = _parse_date(_node_text(entry, "published")
                                or _node_text(entry, "updated")
                                or _node_text(entry, "pubDate"))
        summary = _clean_html(_node_text(entry, "summary")
                              or _node_text(entry, "content")
                              or _node_text(entry, "description")
                              or _node_text(entry, "encoded"))
        items.append({
            "title": _WS_RE.sub(" ", title).strip(),
            "url": link,
            "source": source,
            "published_at": published.isoformat() if published else None,
            "summary": summary[:300],
            "image": _extract_image(entry),
        })
    return items


def _asset_terms(coin_id: str) -> tuple[str, ...]:
    name = coin_id.replace("-", " ")
    terms = {name, coin_id, *(_COIN_ALIASES.get(coin_id) or ())}
    return tuple(sorted(terms, key=len, reverse=True))


def _compile_terms(terms: tuple[str, ...]) -> re.Pattern:
    pattern = "|".join(re.escape(term) for term in terms)
    return re.compile(rf"\b(?:{pattern})\b", re.IGNORECASE)


_COIN_MATCHERS: dict[str, re.Pattern] = {
    coin: _compile_terms(_asset_terms(coin)) for coin in _TRACKED_COINS
}
_GENERAL_MATCHER = _compile_terms(_GENERAL_TERMS)


def _relevance(text: str) -> list[str]:
    """Return the tracked coins an article mentions (word-boundary match)."""
    return [coin for coin, matcher in _COIN_MATCHERS.items() if matcher.search(text)]


def _fetch_feed(name: str, url: str) -> list[dict]:
    response = _session().get(url, timeout=FEED_TIMEOUT_SECONDS)
    response.raise_for_status()
    try:
        xml_text = response.content.decode("utf-8")
    except UnicodeDecodeError:
        xml_text = response.content.decode("latin-1")
    return _parse_feed(xml_text, name)


def _refresh() -> tuple[list[dict], str | None]:
    """Fetch every feed concurrently, normalize, de-duplicate and return
    recency-sorted items.

    Network errors are per-feed tolerant: one dead feed never blocks the rest.
    """
    global _CACHE, _CACHE_AT, _FETCH_ERROR
    seen: dict[str, dict] = {}
    errors: list[str] = []
    with ThreadPoolExecutor(max_workers=len(SOURCES)) as pool:
        results = list(pool.map(_fetch_feed, (name for name, _ in SOURCES),
                                (url for _, url in SOURCES)))
    for (name, _url), result in zip(SOURCES, results):
        if isinstance(result, Exception):
            errors.append(f"{name}: {result.__class__.__name__}")
            continue
        for item in result[:PER_SOURCE_CAP]:
            key = item["url"].split("#")[0]
            seen.setdefault(key, item)
    articles = list(seen.values())
    for article in articles:
        article["coins"] = _relevance(f"{article['title']} {article['summary']}")
    if articles:
        _CACHE = articles
        _CACHE_AT = time.time()
        _FETCH_ERROR = None
    error_note = "; ".join(errors) if errors else None
    if error_note:
        _FETCH_ERROR = error_note
    _persist(articles)
    return articles, error_note


def _persist(articles: list[dict]) -> None:
    from app.data.database import connection, initialize_database  # local import avoids a cycle

    initialize_database()
    with connection() as conn:
        conn.executemany(
            """INSERT INTO news_articles (url_hash, title, url, source, published_at, summary, coins, image, fetched_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
               ON CONFLICT(url_hash) DO UPDATE SET
                 title=excluded.title, summary=excluded.summary,
                 published_at=excluded.published_at, image=excluded.image,
                 fetched_at=excluded.fetched_at""",
            [
                (
                    _url_hash(article["url"]),
                    article["title"],
                    article["url"],
                    article["source"],
                    article["published_at"],
                    article["summary"],
                    ",".join(article["coins"]),
                    article.get("image"),
                    datetime.now(timezone.utc).isoformat(),
                )
                for article in articles
            ],
        )


def _from_db() -> list[dict]:
    from app.data.database import connection, initialize_database  # local import avoids a cycle

    initialize_database()
    cutoff = (datetime.now(timezone.utc) - timedelta(hours=48)).isoformat()
    with connection() as conn:
        rows = conn.execute(
            """SELECT title, url, source, published_at, summary, coins, image
               FROM news_articles
               WHERE published_at IS NULL OR published_at >= ?
               ORDER BY published_at DESC LIMIT 200""",
            (cutoff,),
        ).fetchall()
    articles = []
    for row in rows:
        article = dict(row)
        article["coins"] = [coin for coin in article["coins"].split(",") if coin]
        articles.append(article)
    return articles


def get_news(limit: int = 30, coin_id: str | None = None) -> dict:
    """Latest normalized news, optionally filtered to one tracked asset.

    Returns a dict with ``news``, ``sources``, ``fetched_at`` and ``error`` so
    the API can always answer 200, even when every feed is unreachable.
    """
    global _CACHE, _CACHE_AT, _FETCH_ERROR
    limit = max(1, min(int(limit or 30), 100))
    if coin_id is not None and coin_id not in _TRACKED_COINS:
        coin_id = None
    if _CACHE is None or time.time() - _CACHE_AT > NEWS_TTL_SECONDS:
        articles, error = _refresh()
    else:
        articles, error = list(_CACHE), _FETCH_ERROR
    if not articles:
        articles = _from_db()
    articles.sort(key=lambda item: item.get("published_at") or "", reverse=True)
    if coin_id:
        articles = [item for item in articles if coin_id in (item.get("coins") or [])]
    return {
        "news": articles[:limit],
        "sources": len(SOURCES),
        "fetched_at": datetime.fromtimestamp(_CACHE_AT, tz=timezone.utc).isoformat() if _CACHE_AT else None,
        "error": error,
    }


def _url_hash(url: str) -> str:
    import hashlib

    return hashlib.sha1(url.rsplit("#", 1)[0].encode("utf-8")).hexdigest()


def _reset_cache() -> None:
    global _CACHE, _CACHE_AT, _FETCH_ERROR
    _CACHE = None
    _CACHE_AT = 0.0
    _FETCH_ERROR = None
