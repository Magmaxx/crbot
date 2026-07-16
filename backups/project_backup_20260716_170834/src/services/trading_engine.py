import logging
from typing import Dict, Any, List
from datetime import datetime, timezone

from src.config import RISK_PROFILES
from src.core.models import Portfolio
from src.execution.adapters import SpotExecutionAdapter, FuturesExecutionAdapter
from src.risk.manager import can_open_new_position, open_paper_position, mark_to_market_and_close_if_needed


class TradingEngine:
    """
    TradingEngine:
    - Risk profile yönetimi (low/balanced/aggressive)
    - Trade modu yönetimi (SCALP_SPOT / LEVERAGED_FUTURES)
    - Paper trade açma/kapama
    - İşlem geçmişi takibi
    """

    VALID_TRADE_MODES = ("SCALP_SPOT", "LEVERAGED_FUTURES")

    def __init__(
        self,
        initial_balance: float = 10000.0,
        risk_profile: str = "balanced",
        trade_mode: str = "LEVERAGED_FUTURES",
        exchange_id: str = "binance",
        api_key: str = "",
        api_secret: str = "",
        execution_enabled: bool = False,
        paper_only: bool = True,
        use_testnet: bool = True,
        order_size_pct: float = 0.01,
        symbol: str = "BTC/USDT",
    ):
        self.logger = logging.getLogger("services.trading_engine")
        if risk_profile not in RISK_PROFILES:
            risk_profile = "balanced"

        self.initial_balance = float(initial_balance)
        self.portfolio = Portfolio(
            balance=self.initial_balance,
            daily_start_balance=self.initial_balance,
            risk_profile=risk_profile,
            risk_profiles=RISK_PROFILES,
        )
        self.trade_history: List[Dict[str, Any]] = []
        self.trade_mode = "LEVERAGED_FUTURES"
        self.set_trade_mode(trade_mode)

        self.exchange_id = exchange_id
        self.api_key = api_key
        self.api_secret = api_secret
        self.execution_enabled = execution_enabled
        self.paper_only = paper_only
        self.use_testnet = use_testnet
        self.order_size_pct = max(0.0, min(1.0, order_size_pct))
        self.symbol = symbol

        self.spot_adapter = SpotExecutionAdapter(
            exchange_id=self.exchange_id,
            api_key=self.api_key,
            api_secret=self.api_secret,
            testnet=self.use_testnet,
            paper_only=self.paper_only,
        )
        self.futures_adapter = FuturesExecutionAdapter(
            exchange_id=self.exchange_id,
            api_key=self.api_key,
            api_secret=self.api_secret,
            testnet=self.use_testnet,
            paper_only=self.paper_only,
        )

    def set_risk_profile(self, risk_profile: str):
        if risk_profile in RISK_PROFILES:
            self.portfolio.risk_profile = risk_profile

    def set_trade_mode(self, trade_mode: str):
        if trade_mode in self.VALID_TRADE_MODES:
            self.trade_mode = trade_mode

    def on_price_tick(self, current_price: float):
        before_closed = len(self.portfolio.closed_positions)
        mark_to_market_and_close_if_needed(self.portfolio, current_price)
        after_closed = len(self.portfolio.closed_positions)

        if after_closed > before_closed:
            for pos in self.portfolio.closed_positions[before_closed:]:
                self.trade_history.append(
                    {
                        "time": datetime.now(timezone.utc).isoformat(),
                        "event": "CLOSE",
                        "side": pos.side,
                        "entry": pos.entry_price,
                        "exit": pos.exit_price,
                        "qty": pos.qty,
                        "pnl": pos.pnl,
                        "balance": self.portfolio.balance,
                        "trade_mode": self.trade_mode,
                    }
                )

    def maybe_open_trade(self, direction: str, price: float, atr_val: float, confidence: float):
        if direction not in ("LONG", "SHORT"):
            return None

        # SCALP_SPOT kuralı: spot modda SHORT açılmaz (ignore -> HOLD davranışı)
        if self.trade_mode == "SCALP_SPOT" and direction == "SHORT":
            self.logger.info("SCALP_SPOT mode: SHORT signal ignored (treated as HOLD).")
            return None
        if confidence < 0.55:
            return None
        if not can_open_new_position(self.portfolio):
            return None

        pos = open_paper_position(
            portfolio=self.portfolio,
            side=direction,
            entry=price,
            atr_val=atr_val,
        )
        if pos:
            exec_result = self._execute_order(side=direction, price=price)

            self.trade_history.append(
                {
                    "time": datetime.now(timezone.utc).isoformat(),
                    "event": "OPEN",
                    "side": pos.side,
                    "entry": pos.entry_price,
                    "exit": None,
                    "qty": pos.qty,
                    "pnl": 0.0,
                    "balance": self.portfolio.balance,
                    "trade_mode": self.trade_mode,
                    "execution_mode": exec_result["mode"],
                    "execution_ok": exec_result["ok"],
                }
            )
            self.logger.info(
                "OPEN mode=%s exec_mode=%s side=%s entry=%.2f sl=%.2f tp=%.2f qty=%.6f",
                self.trade_mode,
                exec_result["mode"],
                pos.side,
                pos.entry_price,
                pos.stop_loss,
                pos.take_profit,
                pos.qty,
            )
        return pos

    def _execute_order(self, side: str, price: float) -> Dict[str, Any]:
        if not self.execution_enabled:
            return {"ok": True, "mode": "disabled", "details": {"reason": "EXECUTION_ENABLED=0"}}

        if self.paper_only:
            return {"ok": True, "mode": "paper", "details": {"reason": "PAPER_ONLY=1"}}

        notional = max(0.0, self.portfolio.balance * self.order_size_pct)
        amount = (notional / price) if price > 0 else 0.0
        if amount <= 0:
            return {"ok": False, "mode": "invalid-size", "details": {"notional": notional, "price": price}}

        ccxt_side = "buy" if side == "LONG" else "sell"

        try:
            if self.trade_mode == "SCALP_SPOT":
                res = self.spot_adapter.create_order(
                    symbol=self.symbol,
                    side=ccxt_side,
                    amount=amount,
                    order_type="market",
                )
            else:
                res = self.futures_adapter.create_order(
                    symbol=self.symbol,
                    side=ccxt_side,
                    amount=amount,
                    order_type="market",
                    params={},
                )
            return {"ok": res.ok, "mode": res.mode, "details": res.details}
        except Exception as e:
            self.logger.exception("Order execution failed | mode=%s side=%s err=%s", self.trade_mode, side, e)
            return {"ok": False, "mode": "error", "details": {"error": str(e)}}

    def reset_paper_state(self):
        current_risk = self.portfolio.risk_profile
        self.portfolio = Portfolio(
            balance=self.initial_balance,
            daily_start_balance=self.initial_balance,
            risk_profile=current_risk,
            risk_profiles=RISK_PROFILES,
        )
        self.trade_history = []
        self.logger.info("Paper state reset completed | balance=%.2f risk_profile=%s", self.initial_balance, current_risk)

    def snapshot(self) -> Dict[str, Any]:
        return {
            "balance": self.portfolio.balance,
            "risk_profile": self.portfolio.risk_profile,
            "open_positions": len(self.portfolio.open_positions),
            "closed_positions": len(self.portfolio.closed_positions),
            "daily_loss_pct": self.portfolio.daily_loss_pct(),
            "trading_enabled": self.portfolio.trading_enabled,
            "trade_mode": self.trade_mode,
            "execution_enabled": self.execution_enabled,
            "paper_only": self.paper_only,
            "use_testnet": self.use_testnet,
        }
