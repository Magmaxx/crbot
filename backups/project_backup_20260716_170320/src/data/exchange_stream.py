from typing import Any, List, Dict

import ccxt.pro as ccxtpro


class ExchangeStream:
    """
    CCXT Pro ile WebSocket veri akışı (OHLCV + Orderbook).
    """

    def __init__(self, exchange_id: str, symbol: str, timeframe: str, ccxt_verbose: bool = False):
        self.exchange_id = exchange_id
        self.symbol = symbol
        self.timeframe = timeframe
        self.ccxt_verbose = ccxt_verbose
        self.exchange: Any = None

    async def connect(self):
        if self.exchange_id != "binance":
            raise ValueError("Bu sürüm yalnızca binance exchange_id destekler.")

        self.exchange = ccxtpro.binance(
            {
                "enableRateLimit": True,
                "timeout": 20000,
                "options": {
                    "defaultType": "spot",
                    "adjustForTimeDifference": True,
                },
            }
        )
        self.exchange.verbose = self.ccxt_verbose

    async def close(self):
        if self.exchange:
            await self.exchange.close()
            self.exchange = None

    async def watch_ohlcv(self) -> List[List[float]]:
        return await self.exchange.watch_ohlcv(self.symbol, timeframe=self.timeframe)

    async def watch_order_book(self, limit: int = 20) -> Dict:
        return await self.exchange.watch_order_book(self.symbol, limit=limit)
