from typing import List, Dict, Optional


def orderbook_heatmap_bias(orderbook: Dict, depth: int = 10) -> float:
    """
    Orderbook'tan basit long/short bias skoru üretir.
    Dönüş aralığı: [-1, +1]
    +1 => long baskın, -1 => short baskın
    """
    bids: List[List[float]] = orderbook.get("bids", [])[:depth]
    asks: List[List[float]] = orderbook.get("asks", [])[:depth]

    bid_notional = sum(float(price) * float(amount) for price, amount in bids) if bids else 0.0
    ask_notional = sum(float(price) * float(amount) for price, amount in asks) if asks else 0.0

    total = bid_notional + ask_notional
    if total <= 0:
        return 0.0

    return (bid_notional - ask_notional) / total


def combined_heatmap_bias(
    orderbook: Dict,
    market_sentiment_bias: Optional[float],
    depth: int = 10,
) -> float:
    """
    Binance Futures sentiment primary + orderbook fallback.
    - market_sentiment_bias varsa doğrudan kullan
    - yoksa orderbook bias kullan
    """
    if market_sentiment_bias is not None:
        return max(-1.0, min(1.0, float(market_sentiment_bias)))
    return orderbook_heatmap_bias(orderbook, depth=depth)
