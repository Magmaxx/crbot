import logging
from typing import Tuple, List

import pandas as pd


class FeatureEngineer:
    """
    FeatureEngineer:
    - Pandas-ta ile teknik indikatörleri hesaplar (fallback: manuel)
    - ML modeli için feature set oluşturur
    - Label: sonraki mum yönü (up/down)
    """

    def __init__(self):
        self.logger = logging.getLogger("services.feature_engineer")
        self._pta = None
        try:
            import pandas_ta as pta  # type: ignore
            self._pta = pta
        except Exception:
            self._pta = None
            self.logger.warning("pandas_ta yüklenemedi, fallback hesaplamalar kullanılacak.")

    @staticmethod
    def _manual_rsi(close: pd.Series, period: int = 14) -> pd.Series:
        delta = close.diff()
        gain = delta.clip(lower=0).rolling(period).mean()
        loss = (-delta.clip(upper=0)).rolling(period).mean()
        rs = gain / loss.replace(0, 1e-12)
        return 100 - (100 / (1 + rs))

    def add_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        out = df.copy()

        if self._pta is not None:
            out["ema_20"] = self._pta.ema(out["close"], length=20)
            out["ema_50"] = self._pta.ema(out["close"], length=50)
            out["rsi_14"] = self._pta.rsi(out["close"], length=14)

            atr = self._pta.atr(
                high=out["high"],
                low=out["low"],
                close=out["close"],
                length=14,
            )
            out["atr_14"] = atr
        else:
            out["ema_20"] = out["close"].ewm(span=20, adjust=False).mean()
            out["ema_50"] = out["close"].ewm(span=50, adjust=False).mean()
            out["rsi_14"] = self._manual_rsi(out["close"], period=14)

            tr1 = (out["high"] - out["low"]).abs()
            tr2 = (out["high"] - out["close"].shift(1)).abs()
            tr3 = (out["low"] - out["close"].shift(1)).abs()
            out["atr_14"] = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1).rolling(14).mean()

        out["ret_1"] = out["close"].pct_change(1)
        out["ret_3"] = out["close"].pct_change(3)
        out["ret_5"] = out["close"].pct_change(5)
        out["vol_chg"] = out["volume"].pct_change(1)

        return out

    def build_ml_dataset(
        self,
        df: pd.DataFrame,
        news_sentiment: float,
        long_short_bias: float,
    ) -> Tuple[pd.DataFrame, pd.Series, List[str], pd.DataFrame]:
        feat_df = self.add_indicators(df)

        feat_df["news_sentiment"] = float(news_sentiment)
        feat_df["long_short_bias"] = float(long_short_bias)

        feat_df["target"] = (feat_df["close"].shift(-1) > feat_df["close"]).astype(int)

        feature_cols = [
            "open",
            "high",
            "low",
            "close",
            "volume",
            "ema_20",
            "ema_50",
            "rsi_14",
            "atr_14",
            "ret_1",
            "ret_3",
            "ret_5",
            "vol_chg",
            "news_sentiment",
            "long_short_bias",
        ]

        clean = feat_df.dropna().copy()
        X = clean[feature_cols]
        y = clean["target"].astype(int)
        return X, y, feature_cols, clean
