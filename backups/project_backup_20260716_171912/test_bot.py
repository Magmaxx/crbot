import queue
import bot


def test_risk_profile_switch():
    engine = bot.TradingEngine(queue.Queue())
    engine.set_risk_profile("low")
    assert engine.portfolio.risk_profile == "low"
    assert engine.portfolio.risk_conf()["risk_per_trade"] == 0.005

    engine.set_risk_profile("balanced")
    assert engine.portfolio.risk_profile == "balanced"
    assert engine.portfolio.risk_conf()["daily_max_loss"] == 0.03

    engine.set_risk_profile("aggressive")
    assert engine.portfolio.risk_profile == "aggressive"
    assert engine.portfolio.risk_conf()["max_positions"] == 3


def test_position_size_positive():
    engine = bot.TradingEngine(queue.Queue())
    engine.set_risk_profile("balanced")
    qty = engine._calc_position_size(entry=100.0, stop=99.0)
    assert qty > 0


def test_open_position_and_mark_to_market_close_tp_long():
    engine = bot.TradingEngine(queue.Queue())
    engine.set_risk_profile("balanced")

    pos = engine._open_paper_position("LONG", entry=100.0, atr_val=1.0)
    assert pos is not None
    assert len(engine.portfolio.open_positions) == 1

    tp_price = pos.take_profit + 0.01
    engine._mark_to_market(tp_price)

    assert len(engine.portfolio.open_positions) == 0
    assert len(engine.portfolio.closed_positions) == 1
    assert engine.portfolio.closed_positions[0].pnl > 0


def test_daily_loss_limit_disables_trading():
    engine = bot.TradingEngine(queue.Queue())
    engine.set_risk_profile("low")

    # low profile daily max loss: 2%
    p = engine.portfolio
    p.daily_start_balance = 10000.0
    p.balance = 9700.0  # %3 loss

    can_open = engine._can_open_new_position()
    assert can_open is False
    assert p.trading_enabled is False


def test_build_signal_shape():
    # synthetic ohlcv: [timestamp, open, high, low, close, volume]
    ohlcv = []
    price = 100.0
    for i in range(220):
        high = price + 1
        low = price - 1
        close = price + (0.1 if i % 2 == 0 else -0.05)
        ohlcv.append([i, price, high, low, close, 1000])
        price = close

    s = bot.build_signal(ohlcv)
    assert "action" in s
    assert "confidence" in s
    assert "price" in s
    assert s["action"] in ("LONG", "SHORT", "HOLD")
    assert 0.0 <= s["confidence"] <= 1.0
