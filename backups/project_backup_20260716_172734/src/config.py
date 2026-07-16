import os
from dataclasses import dataclass
from typing import Dict


RISK_PROFILES: Dict[str, Dict[str, float]] = {
    "low": {"risk_per_trade": 0.005, "daily_max_loss": 0.02, "max_positions": 2},
    "balanced": {"risk_per_trade": 0.01, "daily_max_loss": 0.03, "max_positions": 2},
    "aggressive": {"risk_per_trade": 0.02, "daily_max_loss": 0.05, "max_positions": 3},
}


@dataclass
class AppConfig:
    news_api_key: str = os.getenv("NEWS_API_KEY", "")
    exchange_id: str = os.getenv("EXCHANGE_ID", "binance")
    symbol: str = os.getenv("SYMBOL", "BTC/USDT")
    timeframe: str = os.getenv("TIMEFRAME", "1m")
    initial_balance: float = float(os.getenv("INITIAL_BALANCE", "10000"))
    confidence_threshold: float = float(os.getenv("CONFIDENCE_THRESHOLD", "0.60"))
    rest_fallback_enabled: bool = os.getenv("REST_FALLBACK_ENABLED", "1") == "1"
    strict_testnet_default: bool = os.getenv("STRICT_TESTNET", "0") == "1"
    ccxt_verbose: bool = os.getenv("CCXT_VERBOSE", "0") == "1"
    max_notional_pct: float = float(os.getenv("MAX_NOTIONAL_PCT", "0.25"))
    default_risk_profile: str = os.getenv("DEFAULT_RISK_PROFILE", "balanced")
    default_trade_mode: str = os.getenv("DEFAULT_TRADE_MODE", "LEVERAGED_FUTURES")

    # Execution controls (safe-by-default)
    execution_enabled: bool = os.getenv("EXECUTION_ENABLED", "0") == "1"
    paper_only: bool = os.getenv("PAPER_ONLY", "1") == "1"
    use_testnet: bool = os.getenv("USE_TESTNET", "1") == "1"
    binance_api_key: str = os.getenv("BINANCE_API_KEY", "")
    binance_api_secret: str = os.getenv("BINANCE_API_SECRET", "")
    order_size_pct: float = float(os.getenv("ORDER_SIZE_PCT", "0.01"))

    # UI / Dashboard
    ohlcv_limit: int = int(os.getenv("OHLCV_LIMIT", "300"))
    ui_symbols: tuple = ("BTC/USDT", "ETH/USDT", "BNB/USDT", "SOL/USDT", "XRP/USDT")
    ui_timeframes: tuple = ("1m", "5m", "15m", "1h", "4h")


APP_CONFIG = AppConfig()
