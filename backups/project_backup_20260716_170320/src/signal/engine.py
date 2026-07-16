import math
from typing import Dict, List

from src.analytics.indicators import ema, rsi, atr_from_ohlcv


def build_signal(
    ohlcv: List[List[float]],
    sentiment_score: float,
    heatmap_bias: float,
    confidence_threshold: float = 0.60,
) -> Dict[str, float]:
    """
    AI-ready hybrid signal:
    - Teknik skor (EMA + RSI)
    - Haber sentiment
    - Orderbook heatmap bias
    """
    closes = [c[4] for c in ohlcv]
    price = closes[-1]

    ema_fast = ema(closes[-50:], 20)
    ema_slow = ema(closes[-200:], 50)
    rsi_val = rsi(closes, 14)
    atr_val = atr_from_ohlcv(ohlcv, 14)

    tech_score = 0.0

    # Trend etkisi
    if ema_fast > ema_slow:
        tech_score += 0.35
    else:
        tech_score -= 0.35

    # Momentum etkisi
    if rsi_val < 35:
        tech_score += 0.25
    elif rsi_val > 65:
        tech_score -= 0.25

    # Hibrit skor
    score = (0.5 * tech_score) + (0.3 * sentiment_score) + (0.2 * heatmap_bias)

    confidence_long = 1 / (1 + math.exp(-score))
    confidence_short = 1 - confidence_long

    if confidence_long >= confidence_threshold:
        action = "LONG"
        confidence = confidence_long
    elif confidence_short >= confidence_threshold:
        action = "SHORT"
        confidence = confidence_short
    else:
        action = "HOLD"
        confidence = max(confidence_long, confidence_short)

    return {
        "action": action,
        "confidence": confidence,
        "price": price,
        "atr": atr_val,
        "rsi": rsi_val,
        "sentiment": sentiment_score,
        "heatmap": heatmap_bias,
        "score": score,
    }
