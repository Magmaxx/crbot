import logging
from typing import Optional, Dict, Any, List

import requests

logger = logging.getLogger("binance-sentiment")

BINANCE_FAPI_BASE = "https://fapi.binance.com"


def _normalize_symbol(symbol: str) -> str:
    # BTC/USDT -> BTCUSDT
    return symbol.replace("/", "").upper().strip()


def _get(url: str, params: Dict[str, Any]) -> Optional[Any]:
    try:
        r = requests.get(url, params=params, timeout=12)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        logger.warning(f"Binance sentiment request failed: {url} | {e}")
        return None


def _to_float(v, default=0.0) -> float:
    try:
        return float(v)
    except Exception:
        return default


def fetch_binance_futures_sentiment_bias(symbol: str) -> Optional[float]:
    """
    Ücretsiz Binance Futures endpointlerinden sentiment bias üretir.
    Kaynaklar:
      - Global Long/Short Account Ratio
      - Open Interest
      - Taker Buy/Sell Volume
    Dönüş: [-1, +1] veya veri alınamazsa None
    """
    s = _normalize_symbol(symbol)

    # 1) Global long/short ratio
    ls_url = f"{BINANCE_FAPI_BASE}/futures/data/globalLongShortAccountRatio"
    ls = _get(ls_url, {"symbol": s, "period": "5m", "limit": 2})

    # 2) Open interest (anlık)
    oi_url = f"{BINANCE_FAPI_BASE}/fapi/v1/openInterest"
    oi_now = _get(oi_url, {"symbol": s})

    # 3) Open interest history (değişim çıkarımı için)
    oi_hist_url = f"{BINANCE_FAPI_BASE}/futures/data/openInterestHist"
    oi_hist = _get(oi_hist_url, {"symbol": s, "period": "5m", "limit": 2})

    # 4) Taker long/short volume ratio
    taker_url = f"{BINANCE_FAPI_BASE}/futures/data/takerlongshortRatio"
    taker = _get(taker_url, {"symbol": s, "period": "5m", "limit": 2})

    has_any = False
    ls_component = 0.0
    oi_component = 0.0
    taker_component = 0.0

    # ----- Long/Short component -----
    if isinstance(ls, list) and ls:
        row = ls[-1]
        long_acc = _to_float(row.get("longAccount"), 0.0)
        short_acc = _to_float(row.get("shortAccount"), 0.0)
        ratio = _to_float(row.get("longShortRatio"), 1.0)

        if long_acc > 0 and short_acc > 0:
            total = long_acc + short_acc
            ls_component = (long_acc - short_acc) / total
            has_any = True
        elif ratio > 0:
            # ratio 1 = neutral
            ls_component = max(-1.0, min(1.0, (ratio - 1.0) / max(1.0, abs(ratio))))
            has_any = True

    # ----- Open interest change component -----
    # Eğer history varsa delta hesapla, yoksa 0
    if isinstance(oi_hist, list) and len(oi_hist) >= 2:
        prev_oi = _to_float(oi_hist[-2].get("sumOpenInterest"), 0.0)
        curr_oi = _to_float(oi_hist[-1].get("sumOpenInterest"), 0.0)
        if prev_oi > 0:
            delta = (curr_oi - prev_oi) / prev_oi
            oi_component = max(-1.0, min(1.0, delta))
            has_any = True
    elif isinstance(oi_now, dict):
        oi_val = _to_float(oi_now.get("openInterest"), 0.0)
        if oi_val > 0:
            # tek başına yön vermez ama veri var sinyali
            oi_component = 0.0
            has_any = True

    # ----- Taker flow component -----
    if isinstance(taker, list) and taker:
        row = taker[-1]
        buy_vol = _to_float(row.get("buyVol"), 0.0)
        sell_vol = _to_float(row.get("sellVol"), 0.0)
        if buy_vol > 0 or sell_vol > 0:
            total = buy_vol + sell_vol
            if total > 0:
                taker_component = (buy_vol - sell_vol) / total
                has_any = True

    if not has_any:
        return None

    # Ağırlıklar: LS ana, taker ikincil, OI yardımcı
    bias = (0.55 * ls_component) + (0.30 * taker_component) + (0.15 * oi_component)
    return max(-1.0, min(1.0, bias))
