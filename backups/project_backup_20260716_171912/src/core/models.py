from dataclasses import dataclass, field
from datetime import datetime, date, timezone
from typing import List, Optional, Literal, Dict


Side = Literal["LONG", "SHORT"]


@dataclass
class Position:
    side: Side
    entry_price: float
    qty: float
    stop_loss: float
    take_profit: float
    opened_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    status: Literal["OPEN", "CLOSED"] = "OPEN"
    exit_price: Optional[float] = None
    pnl: float = 0.0


@dataclass
class ExchangeConfig:
    exchange_id: str = "binance"
    api_key: str = ""
    api_secret: str = ""
    testnet: bool = True
    strict_testnet: bool = False
    symbol: str = "BTC/USDT"
    timeframe: str = "1m"


@dataclass
class Portfolio:
    balance: float = 10000.0
    daily_start_balance: float = 10000.0
    daily_date: date = field(default_factory=lambda: datetime.now(timezone.utc).date())
    open_positions: List[Position] = field(default_factory=list)
    closed_positions: List[Position] = field(default_factory=list)
    trading_enabled: bool = True
    risk_profile: str = "balanced"
    risk_profiles: Dict[str, Dict[str, float]] = field(default_factory=dict)

    def reset_daily_if_needed(self):
        today = datetime.now(timezone.utc).date()
        if today != self.daily_date:
            self.daily_date = today
            self.daily_start_balance = self.balance
            self.trading_enabled = True

    def daily_loss_pct(self) -> float:
        if self.daily_start_balance <= 0:
            return 0.0
        dd = max(0.0, self.daily_start_balance - self.balance)
        return dd / self.daily_start_balance

    def risk_conf(self) -> Dict[str, float]:
        return self.risk_profiles[self.risk_profile]
