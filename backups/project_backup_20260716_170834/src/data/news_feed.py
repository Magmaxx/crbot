import requests
from typing import List


BULLISH_WORDS: List[str] = ["surge", "rally", "adoption", "breakout", "approval", "growth", "bullish"]
BEARISH_WORDS: List[str] = ["hack", "ban", "lawsuit", "crash", "selloff", "recession", "bearish"]


def fetch_news_sentiment_score(news_api_key: str) -> float:
    """
    Basit keyword sentiment.
    Sonuç aralığı: [-1, +1]
    """
    if not news_api_key:
        return 0.0

    try:
        url = "https://newsapi.org/v2/everything"
        params = {
            "q": "bitcoin OR crypto OR ethereum",
            "language": "en",
            "sortBy": "publishedAt",
            "pageSize": 30,
            "apiKey": news_api_key,
        }
        r = requests.get(url, params=params, timeout=12)
        r.raise_for_status()
        articles = r.json().get("articles", [])

        text = " ".join(
            ((a.get("title") or "") + " " + (a.get("description") or ""))
            for a in articles
        ).lower()

        bull = sum(text.count(w) for w in BULLISH_WORDS)
        bear = sum(text.count(w) for w in BEARISH_WORDS)
        total = bull + bear
        if total == 0:
            return 0.0

        return (bull - bear) / total
    except Exception:
        return 0.0
