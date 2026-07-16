from typing import Optional

from src.core.models import Portfolio, Position, Side


def can_open_new_position(portfolio: Portfolio) -> bool:
    portfolio.reset_daily_if_needed()
    conf = portfolio.risk_conf()

    if not portfolio.trading_enabled:
        return False

    if portfolio.daily_loss_pct() >= conf["daily_max_loss"]:
        portfolio.trading_enabled = False
        return False

    open_count = len([p for p in portfolio.open_positions if p.status == "OPEN"])
    return open_count < int(conf["max_positions"])


def calc_position_size(portfolio: Portfolio, entry: float, stop: float) -> float:
    conf = portfolio.risk_conf()
    risk_amount = portfolio.balance * conf["risk_per_trade"]
    unit_risk = abs(entry - stop)
    if unit_risk <= 0:
        return 0.0
    return max(0.0, risk_amount / unit_risk)


def open_paper_position(
    portfolio: Portfolio,
    side: Side,
    entry: float,
    atr_val: float,
) -> Optional[Position]:
    sl_dist = max(atr_val * 1.2, entry * 0.004)
    tp_dist = sl_dist * 1.8

    if side == "LONG":
        stop = entry - sl_dist
        take = entry + tp_dist
    else:
        stop = entry + sl_dist
        take = entry - tp_dist

    qty = calc_position_size(portfolio, entry, stop)
    if qty <= 0:
        return None

    pos = Position(
        side=side,
        entry_price=entry,
        qty=qty,
        stop_loss=stop,
        take_profit=take,
    )
    portfolio.open_positions.append(pos)
    return pos


def mark_to_market_and_close_if_needed(portfolio: Portfolio, current_price: float):
    for pos in portfolio.open_positions:
        if pos.status != "OPEN":
            continue

        hit_sl = (pos.side == "LONG" and current_price <= pos.stop_loss) or (
            pos.side == "SHORT" and current_price >= pos.stop_loss
        )
        hit_tp = (pos.side == "LONG" and current_price >= pos.take_profit) or (
            pos.side == "SHORT" and current_price <= pos.take_profit
        )

        if hit_sl or hit_tp:
            pos.status = "CLOSED"
            pos.exit_price = current_price
            if pos.side == "LONG":
                pos.pnl = (current_price - pos.entry_price) * pos.qty
            else:
                pos.pnl = (pos.entry_price - current_price) * pos.qty

            portfolio.balance += pos.pnl
            portfolio.closed_positions.append(pos)

    portfolio.open_positions = [p for p in portfolio.open_positions if p.status == "OPEN"]
