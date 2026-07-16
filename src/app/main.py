import asyncio
import logging

from src.config import APP_CONFIG
from src.services.data_fetcher import DataFetcher
from src.services.feature_engineer import FeatureEngineer
from src.services.ml_predictor import MLPredictor
from src.services.trading_engine import TradingEngine
from src.utils.logging_setup import setup_logging

logger = logging.getLogger("app-main")


class TradingOrchestrator:
    """
    OOP orchestrator:
    - DataFetcher: market + sentiment verisi
    - FeatureEngineer: indikatör + ML feature
    - MLPredictor: yön tahmini
    - TradingEngine: risk yönetimi + paper trade
    """

    def __init__(self):
        self.config = APP_CONFIG
        self._running = False

        self.fetcher = DataFetcher(
            exchange_id=self.config.exchange_id,
            symbol=self.config.symbol,
            timeframe=self.config.timeframe,
            news_api_key=self.config.news_api_key,
            ohlcv_limit=self.config.ohlcv_limit,
        )
        self.feature_engineer = FeatureEngineer()
        self.ml_predictor = MLPredictor()
        self.trading_engine = TradingEngine(
            initial_balance=self.config.initial_balance,
            risk_profile=self.config.default_risk_profile,
            trade_mode=getattr(self.config, "default_trade_mode", "LEVERAGED_FUTURES"),
            exchange_id=self.config.exchange_id,
            api_key=self.config.binance_api_key,
            api_secret=self.config.binance_api_secret,
            execution_enabled=self.config.execution_enabled,
            paper_only=self.config.paper_only,
            use_testnet=self.config.use_testnet,
            order_size_pct=self.config.order_size_pct,
            symbol=self.config.symbol,
        )

    async def _setup(self):
        setup_logging()
        logger.info("TradingOrchestrator setup tamamlandı.")

    async def _teardown(self):
        logger.info("TradingOrchestrator teardown tamamlandı.")

    async def run(self):
        self._running = True
        await self._setup()
        logger.info("TradingOrchestrator started.")

        try:
            while self._running:
                bundle = self.fetcher.fetch_all()
                df = bundle["ohlcv"]

                if df.empty or len(df) < 80:
                    await asyncio.sleep(0.5)
                    continue

                X, y, _, clean = self.feature_engineer.build_ml_dataset(
                    df=df,
                    news_sentiment=bundle["news_sentiment"],
                    long_short_bias=bundle["long_short_bias"],
                )

                if len(X) < 60:
                    await asyncio.sleep(0.5)
                    continue

                train_X = X.iloc[:-1]
                train_y = y.iloc[:-1]
                latest_X = X.iloc[[-1]]

                self.ml_predictor.train(train_X, train_y)
                pred = self.ml_predictor.predict_next(latest_X)

                current_price = float(clean["close"].iloc[-1])
                atr_val = float(clean["atr_14"].iloc[-1]) if "atr_14" in clean.columns else max(1.0, current_price * 0.005)

                self.trading_engine.on_price_tick(current_price)

                confidence = max(float(pred.get("prob_up", 0.5)), float(pred.get("prob_down", 0.5)))
                self.trading_engine.maybe_open_trade(
                    direction=pred["direction"],
                    price=current_price,
                    atr_val=atr_val,
                    confidence=confidence,
                )

                snap = self.trading_engine.snapshot()
                logger.info(
                    "pred=%s up=%.3f down=%.3f backend=%s mode=%s exec_enabled=%s paper_only=%s testnet=%s price=%.2f news=%.3f ls=%.3f balance=%.2f open=%d closed=%d",
                    pred["direction"],
                    float(pred.get("prob_up", 0.5)),
                    float(pred.get("prob_down", 0.5)),
                    pred.get("backend", "unknown"),
                    str(snap.get("trade_mode", "LEVERAGED_FUTURES")),
                    str(snap.get("execution_enabled", False)),
                    str(snap.get("paper_only", True)),
                    str(snap.get("use_testnet", True)),
                    current_price,
                    float(bundle["news_sentiment"]),
                    float(bundle["long_short_bias"]),
                    float(snap["balance"]),
                    int(snap["open_positions"]),
                    int(snap["closed_positions"]),
                )

                await asyncio.sleep(1.0)
        finally:
            await self._teardown()
            logger.info("TradingOrchestrator stopped.")

    def stop(self):
        self._running = False
