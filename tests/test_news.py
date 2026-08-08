import pytest
import requests

from app.core.config import Settings
from app.data import database as db_module
from app.services import news as news_module


RSS = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0"><channel><title>Test Feed</title>
<item>
  <title>Bitcoin hits record high as ETFs surge</title>
  <link>https://example.com/rss/bitcoin-record</link>
  <pubDate>Sat, 08 Aug 2026 12:00:00 +0000</pubDate>
  <enclosure url="https://example.com/img/bitcoin.jpg" type="image/jpeg" />
  <description>&lt;p&gt;Bitcoin rallied 4% on record ETF inflows today.&lt;/p&gt;</description>
</item>
<item>
  <title>Ethereum gas fees climb</title>
  <link>https://example.com/rss/eth-fees</link>
  <pubDate>Sat, 08 Aug 2026 11:00:00 +0000</pubDate>
  <description>&lt;img src="https://example.com/img/eth.jpg" /&gt;Ethereum network activity picked up sharply.</description>
</item>
<item>
  <title>Stablecoin adoption grows in emerging markets</title>
  <link>https://example.com/rss/stablecoin</link>
  <pubDate>Sat, 08 Aug 2026 10:00:00 +0000</pubDate>
  <description>A new stablecoin launched on two exchanges.</description>
</item>
<item>
  <title>Solidity developers meet in Berlin</title>
  <link>https://example.com/rss/solidity</link>
  <pubDate>Sat, 08 Aug 2026 09:00:00 +0000</pubDate>
  <description>A meetup for smart contract engineers.</description>
</item>
</channel></rss>
"""

ATOM = """<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom"><title>Atom Test</title>
<entry>
  <title>Solana upgrade passes testnet</title>
  <link href="https://example.com/atom/solana-upgrade"/>
  <updated>2026-08-08T09:30:00Z</updated>
  <summary>Solana's latest upgrade went live on testnet.</summary>
</entry>
</feed>
"""


class _FakeResponse:
    def __init__(self, content: bytes):
        self.content = content

    def raise_for_status(self) -> None:
        return None


@pytest.fixture(autouse=True)
def _isolated(tmp_path, monkeypatch):
    monkeypatch.setattr(db_module, "settings", Settings(database_path=tmp_path / "test_news.db"))
    news_module._reset_cache()
    yield
    news_module._reset_cache()


def _mock_feed(monkeypatch, xml: str):
    def fake_get(url, timeout=None, headers=None):
        return _FakeResponse(xml.encode("utf-8"))

    monkeypatch.setattr(news_module._SESSION, "get", fake_get)


def test_rss_parsing_tags_and_recency_order(monkeypatch) -> None:
    _mock_feed(monkeypatch, RSS)
    payload = news_module.get_news(limit=10)
    assert payload["error"] is None
    titles = [article["title"] for article in payload["news"]]
    assert titles[0] == "Bitcoin hits record high as ETFs surge"  # newest first
    by_title = {article["title"]: article for article in payload["news"]}
    assert "bitcoin" in by_title["Bitcoin hits record high as ETFs surge"]["coins"]
    assert "ethereum" in by_title["Ethereum gas fees climb"]["coins"]
    # stablecoin article matches no specific asset but stays in the general feed
    assert by_title["Stablecoin adoption grows in emerging markets"]["coins"] == []


def test_word_boundary_prevents_short_alias_false_positive(monkeypatch) -> None:
    _mock_feed(monkeypatch, RSS)
    payload = news_module.get_news(limit=10)
    solidity = next(a for a in payload["news"] if a["title"].startswith("Solidity"))
    assert "solana" not in solidity["coins"]


def test_atom_feed_parsing(monkeypatch) -> None:
    _mock_feed(monkeypatch, ATOM)
    payload = news_module.get_news(limit=10)
    assert any(a["title"].startswith("Solana") for a in payload["news"])
    solana = next(a for a in payload["news"] if a["title"].startswith("Solana"))
    assert "solana" in solana["coins"]
    assert solana["url"] == "https://example.com/atom/solana-upgrade"


def test_coin_filter(monkeypatch) -> None:
    _mock_feed(monkeypatch, RSS)
    payload = news_module.get_news(limit=10, coin_id="ethereum")
    assert all("ethereum" in (a.get("coins") or []) for a in payload["news"])


def test_all_feeds_fail_degrades_to_empty(monkeypatch) -> None:
    def failing_get(url, timeout=None, headers=None):
        raise requests.ConnectionError("no network")

    monkeypatch.setattr(news_module._SESSION, "get", failing_get)
    payload = news_module.get_news(limit=10)
    assert payload["news"] == []
    assert payload["error"]


def test_article_images_extracted(monkeypatch) -> None:
    _mock_feed(monkeypatch, RSS)
    payload = news_module.get_news(limit=10)
    by_title = {article["title"]: article for article in payload["news"]}
    # enclosure with type image/jpeg
    assert by_title["Bitcoin hits record high as ETFs surge"]["image"] == "https://example.com/img/bitcoin.jpg"
    # fallback to <img> inside the description
    assert by_title["Ethereum gas fees climb"]["image"] == "https://example.com/img/eth.jpg"


def test_persist_round_trip(monkeypatch) -> None:
    _mock_feed(monkeypatch, RSS)
    news_module.get_news(limit=10)  # triggers _persist into the tmp db
    cached = news_module._from_db()
    assert any(a["title"] == "Bitcoin hits record high as ETFs surge" for a in cached)
    bitcoin_article = next(a for a in cached if a["title"].startswith("Bitcoin"))
    assert "bitcoin" in bitcoin_article["coins"]
