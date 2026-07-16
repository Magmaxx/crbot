from dataclasses import dataclass
from typing import Optional, Dict, Any

import ccxt


@dataclass
class ExecutionResult:
    ok: bool
    mode: str
    details: Dict[str, Any]


class SpotExecutionAdapter:
    """
    Spot execution adapter.
    Iteration-1: safe-by-default (paper_only=True)
    """

    def __init__(
        self,
        exchange_id: str,
        api_key: str = "",
        api_secret: str = "",
        testnet: bool = True,
        paper_only: bool = True,
    ):
        self.exchange_id = exchange_id
        self.api_key = api_key
        self.api_secret = api_secret
        self.testnet = testnet
        self.paper_only = paper_only
        self.exchange: Optional[Any] = None

    def connect(self):
        if self.exchange_id != "binance":
            raise ValueError("Iteration-1 spot adapter currently supports only binance.")
        self.exchange = ccxt.binance(
            {
                "apiKey": self.api_key,
                "secret": self.api_secret,
                "enableRateLimit": True,
            }
        )
        if self.testnet:
            self.exchange.set_sandbox_mode(True)

    def create_order(self, symbol: str, side: str, amount: float, order_type: str = "market") -> ExecutionResult:
        if self.paper_only:
            return ExecutionResult(
                ok=True,
                mode="paper",
                details={
                    "symbol": symbol,
                    "side": side,
                    "amount": amount,
                    "type": order_type,
                    "info": "Paper mode enabled, real order not sent.",
                },
            )

        if not self.exchange:
            self.connect()

        order = self.exchange.create_order(symbol, order_type, side, amount)
        return ExecutionResult(ok=True, mode="live", details={"order": order})


class FuturesExecutionAdapter:
    """
    Futures execution adapter.
    Iteration-1: safe-by-default (paper_only=True)
    """

    def __init__(
        self,
        exchange_id: str,
        api_key: str = "",
        api_secret: str = "",
        testnet: bool = True,
        paper_only: bool = True,
    ):
        self.exchange_id = exchange_id
        self.api_key = api_key
        self.api_secret = api_secret
        self.testnet = testnet
        self.paper_only = paper_only
        self.exchange: Optional[Any] = None

    def connect(self):
        if self.exchange_id != "binance":
            raise ValueError("Iteration-1 futures adapter currently supports only binance.")

        self.exchange = ccxt.binance(
            {
                "apiKey": self.api_key,
                "secret": self.api_secret,
                "enableRateLimit": True,
                "options": {"defaultType": "future"},
            }
        )
        if self.testnet:
            self.exchange.set_sandbox_mode(True)

    def create_order(
        self,
        symbol: str,
        side: str,
        amount: float,
        order_type: str = "market",
        params: Optional[Dict[str, Any]] = None,
    ) -> ExecutionResult:
        if self.paper_only:
            return ExecutionResult(
                ok=True,
                mode="paper",
                details={
                    "symbol": symbol,
                    "side": side,
                    "amount": amount,
                    "type": order_type,
                    "params": params or {},
                    "info": "Paper mode enabled, real futures order not sent.",
                },
            )

        if not self.exchange:
            self.connect()

        order = self.exchange.create_order(symbol, order_type, side, amount, None, params or {})
        return ExecutionResult(ok=True, mode="live", details={"order": order})
