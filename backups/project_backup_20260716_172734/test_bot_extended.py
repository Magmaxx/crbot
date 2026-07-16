import queue
import threading
import time
import types

import bot


def _sample_ohlcv(n=220, start=100.0):
    ohlcv = []
    p = start
    for i in range(n):
        high = p + 1.2
        low = p - 1.1
        close = p + (0.2 if i % 3 else -0.05)
        ohlcv.append([i, p, high, low, close, 1000])
        p = close
    return ohlcv


def test_engine_push_state_queue_shapes():
    q = queue.Queue()
    engine = bot.TradingEngine(q)

    signal = {"action": "HOLD", "confidence": 0.5}
    engine._push_state(123.45, signal)

    first = q.get_nowait()
    second = q.get_nowait()

    assert first["type"] == "state"
    assert "price" in first and "signal" in first and "balance" in first
    assert second["type"] == "table"
    assert isinstance(second["rows"], list)


def test_mark_to_market_short_tp_close():
    q = queue.Queue()
    engine = bot.TradingEngine(q)
    pos = engine._open_paper_position("SHORT", entry=100.0, atr_val=1.0)
    assert pos is not None
    assert len(engine.portfolio.open_positions) == 1

    # SHORT TP hit when current price <= take_profit
    engine._mark_to_market(pos.take_profit - 0.01)
    assert len(engine.portfolio.open_positions) == 0
    assert len(engine.portfolio.closed_positions) == 1


def test_can_open_new_position_max_open_limit():
    q = queue.Queue()
    engine = bot.TradingEngine(q)
    engine.set_risk_profile("low")  # max_positions = 2

    p1 = engine._open_paper_position("LONG", 100.0, 1.0)
    p2 = engine._open_paper_position("LONG", 101.0, 1.0)
    assert p1 is not None and p2 is not None
    assert engine._can_open_new_position() is False


def test_build_signal_with_synthetic_data():
    ohlcv = _sample_ohlcv()
    s = bot.build_signal(ohlcv)
    assert s["action"] in ("LONG", "SHORT", "HOLD")
    assert 0 <= s["confidence"] <= 1
    assert s["price"] > 0
    assert "atr" in s and "rsi" in s and "sentiment" in s


def test_engine_start_stop_without_real_exchange(monkeypatch):
    q = queue.Queue()
    engine = bot.TradingEngine(q)

    async def fake_strategy_loop(self):
        # emulate short running loop
        self.running = True
        for _ in range(2):
            if not self.running:
                break
            await bot.asyncio.sleep(0.01)
        self.running = False

    monkeypatch.setattr(bot.TradingEngine, "_strategy_loop", fake_strategy_loop, raising=True)

    engine.start()
    time.sleep(0.05)
    engine.stop()
    time.sleep(0.05)

    assert engine.running is False


def test_app_risk_change_updates_engine(monkeypatch):
    # GUI test light: initialize app then destroy quickly
    app = bot.TradingApp()
    try:
        app.risk_var.set("aggressive")
        app._on_risk_change()
        assert app.engine.portfolio.risk_profile == "aggressive"
    finally:
        app.destroy()


def test_strategy_loop_reconnect_logic_skeleton(monkeypatch):
    q = queue.Queue()
    engine = bot.TradingEngine(q)

    class DummyExchange:
        def __init__(self):
            self.calls = 0

        async def watch_ohlcv(self, symbol, timeframe="1m"):
            self.calls += 1
            if self.calls == 1:
                raise Exception("temporary stream error")
            return _sample_ohlcv(80)

        async def close(self):
            return None

    async def fake_connect(self):
        self.exchange = DummyExchange()
        self.log("dummy connected")

    async def fake_close(self):
        if self.exchange:
            await self.exchange.close()

    monkeypatch.setattr(bot.TradingEngine, "_connect_exchange", fake_connect, raising=True)
    monkeypatch.setattr(bot.TradingEngine, "_close_exchange", fake_close, raising=True)

    async def run_once_with_timeout():
        engine.running = True
        t = threading.Timer(0.2, lambda: setattr(engine, "running", False))
        t.start()
        await engine._strategy_loop()
        t.cancel()

    bot.asyncio.run(run_once_with_timeout())

    # strategy loop should not crash process
    assert True
