"""GPU market price fetcher — scrapes eBay sold/completed listings."""

import re
import threading
import time
import urllib.parse
import urllib.request
from typing import Optional

POLL_INTERVAL = 3600   # re-fetch every hour

_PRICE_CACHE: dict[str, Optional[float]] = {}
_LOCK        = threading.Lock()


# ── Name cleaning ─────────────────────────────────────────────────────────────

_STRIP = re.compile(
    r'\b(NVIDIA|AMD|Intel|GeForce|Radeon|Graphics)\b',
    re.IGNORECASE,
)

def _search_query(name: str) -> str:
    """Distil a GPU name down to a tight eBay search string."""
    name = _STRIP.sub('', name).strip()
    # collapse extra whitespace
    name = re.sub(r'\s+', ' ', name)
    # keep at most the first 5 tokens (e.g. "RTX 3080 Ti 10GB" is plenty)
    return ' '.join(name.split()[:5])


# ── eBay scraping ─────────────────────────────────────────────────────────────

_PRICE_RE = re.compile(r'\$([\d,]+(?:\.\d{1,2})?)')

def _fetch_median_sold_price(gpu_name: str) -> Optional[float]:
    """Return median sold price (USD) for gpu_name from eBay, or None."""
    query = _search_query(gpu_name)
    if not query:
        return None

    url = (
        "https://www.ebay.com/sch/i.html?"
        + urllib.parse.urlencode({
            "_nkw":        query,
            "LH_Sold":     "1",
            "LH_Complete": "1",
            "_sacat":      "0",
            "_sop":        "13",   # sort by most-recent
        })
    )
    try:
        req = urllib.request.Request(url, headers={
            "User-Agent": (
                "Mozilla/5.0 (X11; Linux x86_64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0 Safari/537.36"
            ),
            "Accept-Language": "en-US,en;q=0.9",
        })
        with urllib.request.urlopen(req, timeout=15) as resp:
            html = resp.read().decode("utf-8", errors="replace")
    except Exception:
        return None

    # eBay embeds sold prices in <span class="s-item__price"> blocks.
    # Extract that section first to avoid catching shipping / bid prices.
    sections = re.findall(
        r's-item__price[^>]*?>.*?</span>',
        html,
        re.DOTALL,
    )
    raw_text = " ".join(sections) if sections else html

    prices: list[float] = []
    for m in _PRICE_RE.finditer(raw_text):
        try:
            v = float(m.group(1).replace(",", ""))
        except ValueError:
            continue
        if 50.0 <= v <= 6000.0:
            prices.append(v)

    if not prices:
        return None

    prices.sort()
    return prices[len(prices) // 2]   # median


# ── Background poller ─────────────────────────────────────────────────────────

class GpuPricePoller:
    """Daemon thread that refreshes eBay sold prices for a fixed list of GPUs."""

    def __init__(self, gpu_names: list[str]) -> None:
        self._names   = list(dict.fromkeys(gpu_names))   # deduplicate, preserve order
        self._stop    = threading.Event()
        self._thread  = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def _loop(self) -> None:
        while not self._stop.is_set():
            for name in self._names:
                if self._stop.is_set():
                    break
                price = _fetch_median_sold_price(name)
                with _LOCK:
                    _PRICE_CACHE[name] = price
                # small gap between requests to be polite
                self._stop.wait(2.0)
            # wait until next refresh cycle
            self._stop.wait(POLL_INTERVAL)

    def stop(self) -> None:
        self._stop.set()


def get_price(gpu_name: str) -> Optional[float]:
    """Return cached sold price for gpu_name, or None if not yet fetched."""
    with _LOCK:
        return _PRICE_CACHE.get(gpu_name)
