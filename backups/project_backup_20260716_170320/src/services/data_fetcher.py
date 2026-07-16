import logging
from typing import Dict, Any, List, Optional

import ccxt
import pandas as pd

from src.data.news_feed import fetch_news_sentiment_score
from src.data.binance_sentiment import fetch_binance_futures_sentiment_bias


class DataFetcher:
    """
    DataFetcher:
    - CCXT üzerinden OHLCV verisi toplar
    - Haber sentiment skoru çeker
    - Binance Futures long/short sentiment bias üretir
    """

    def __init__(
        self,
        exchange_id: str = "binance",
        symbol: str = "BTC/USDT",
        timeframe: str = "1m",
        news_api_key: str = "",
        ohlcv_limit: int = 300,
    ):
        self.logger = logging.getLogger("services.data_fetcher")
        self.exchange_id = exchange_id
        self.symbol = symbol
        self.timeframe = timeframe
        self.news_api_key = news_api_key
        self.ohlcv_limit = ohlcv_limit

        self.exchange = self._build_exchange()

    def _build_exchange(self):
        if self.exchange_id != "binance":
            raise ValueError("Bu sürüm yalnızca binance exchange_id destekler.")
        return ccxt.binance({"enableRateLimit": True})

    def set_market(self, symbol: str, timeframe: str):
        self.symbol = symbol
        self.timeframe = timeframe

    def fetch_ohlcv_df(self) -> pd.DataFrame:
        """
        OHLCV verisini pandas DataFrame olarak döndürür.
        """
        raw: List[List[float]] = self.exchange.fetch_ohlcv(
            self.symbol, timeframe=self.timeframe, limit=self.ohlcv_limit
        )
        if not raw:
            return pd.DataFrame(columns=["timestamp", "open", "high", "low", "close", "volume"])

        df = pd.DataFrame(raw, columns=["timestamp", "open", "high", "low", "close", "volume"])
        df["datetime"] = pd.to_datetime(df["timestamp"], unit="ms", utc=True)
        return df

    def fetch_sentiment_bundle(self) -> Dict[str, float]:
        """
        Haber sentiment + Binance futures sentiment.
        """
        news_score = fetch_news_sentiment_score(self.news_api_key)
        futures_bias = fetch_binance_futures_sentiment_bias(self.symbol)

        return {
            "news_sentiment": float(news_score),
            "long_short_bias": float(futures_bias) if futures_bias is not None else 0.0,
        }

    def fetch_all(self) -> Dict[str, Any]:
        """
        Dashboard ve model için tek noktadan veri toplama.
        """
        df = self.fetch_ohlcv_df()
        sentiment = self.fetch_sentiment_bundle()

        return {
            "symbol": self.symbol,
            "timeframe": self.timeframe,
            "ohlcv": df,
            "news_sentiment": sentiment["news_sentiment"],
            "long_short_bias": sentiment["long_short_bias"],
        }
