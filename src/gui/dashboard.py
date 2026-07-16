import logging
import hashlib
import os
import sys
from typing import Tuple
from datetime import datetime, date, timezone

# Ensure project root is available for `from src...` imports when run via Streamlit script path.
_CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = os.path.abspath(os.path.join(_CURRENT_DIR, "..", ".."))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from streamlit_autorefresh import st_autorefresh

from src.config import APP_CONFIG
from src.services.data_fetcher import DataFetcher
from src.services.feature_engineer import FeatureEngineer
from src.services.ml_predictor import MLPredictor
from src.services.trading_engine import TradingEngine
from src.utils.logging_setup import setup_logging


def _build_candle_figure(df: pd.DataFrame) -> go.Figure:
    fig = go.Figure()

    fig.add_trace(
        go.Candlestick(
            x=df["datetime"],
            open=df["open"],
            high=df["high"],
            low=df["low"],
            close=df["close"],
            name="Price",
        )
    )

    if "ema_20" in df.columns:
        fig.add_trace(go.Scatter(x=df["datetime"], y=df["ema_20"], mode="lines", name="EMA 20"))
    if "ema_50" in df.columns:
        fig.add_trace(go.Scatter(x=df["datetime"], y=df["ema_50"], mode="lines", name="EMA 50"))

    fig.update_layout(
        template="plotly_dark",
        height=520,
        xaxis_rangeslider_visible=False,
        margin=dict(l=10, r=10, t=30, b=10),
        legend=dict(orientation="h"),
    )
    return fig


def _gauge(value: float, title: str) -> go.Figure:
    v = max(-1.0, min(1.0, float(value)))
    fig = go.Figure(
        go.Indicator(
            mode="gauge+number",
            value=v,
            title={"text": title},
            gauge={
                "axis": {"range": [-1, 1]},
                "bar": {"color": "#00cc96"},
                "steps": [
                    {"range": [-1, -0.2], "color": "#5e1f1f"},
                    {"range": [-0.2, 0.2], "color": "#3f3f3f"},
                    {"range": [0.2, 1], "color": "#1f5e2f"},
                ],
            },
        )
    )
    fig.update_layout(
        template="plotly_dark",
        height=280,
        margin=dict(l=10, r=10, t=80, b=20),
    )
    return fig


@st.cache_resource
def _init_services() -> Tuple[DataFetcher, FeatureEngineer, MLPredictor, TradingEngine]:
    fetcher = DataFetcher(
        exchange_id=APP_CONFIG.exchange_id,
        symbol=APP_CONFIG.symbol,
        timeframe=APP_CONFIG.timeframe,
        news_api_key=APP_CONFIG.news_api_key,
        ohlcv_limit=APP_CONFIG.ohlcv_limit,
    )
    fe = FeatureEngineer()
    ml = MLPredictor()
    te = TradingEngine(
        initial_balance=APP_CONFIG.initial_balance,
        risk_profile=APP_CONFIG.default_risk_profile,
        trade_mode=getattr(APP_CONFIG, "default_trade_mode", "LEVERAGED_FUTURES"),
    )
    return fetcher, fe, ml, te


def _dataset_signature(df: pd.DataFrame) -> str:
    if df.empty:
        return "empty"
    tail = df.tail(120)[["datetime", "open", "high", "low", "close", "volume"]].copy()
    sig = tail.to_json(date_format="iso", orient="split")
    return hashlib.md5(sig.encode("utf-8")).hexdigest()


def run_dashboard():
    setup_logging()
    logger = logging.getLogger("gui.dashboard")

    st.set_page_config(page_title="AI Trading Dashboard", layout="wide")
    st.title("AI Quant Trading Dashboard (Paper Mode)")

    if "last_bundle" not in st.session_state:
        st.session_state["last_bundle"] = None
    if "last_clean" not in st.session_state:
        st.session_state["last_clean"] = None
    if "last_pred" not in st.session_state:
        st.session_state["last_pred"] = {"direction": "HOLD", "prob_up": 0.5, "prob_down": 0.5, "backend": "none"}
    if "last_data_sig" not in st.session_state:
        st.session_state["last_data_sig"] = None
    if "last_trained_sig" not in st.session_state:
        st.session_state["last_trained_sig"] = None
    if "last_prediction_sig" not in st.session_state:
        st.session_state["last_prediction_sig"] = None

    fetcher, fe, ml, te = _init_services()

    with st.sidebar:
        st.header("Kontrol Paneli")
        symbol = st.selectbox("Coin", APP_CONFIG.ui_symbols, index=APP_CONFIG.ui_symbols.index(APP_CONFIG.symbol) if APP_CONFIG.symbol in APP_CONFIG.ui_symbols else 0)
        timeframe = st.selectbox("Zaman Aralığı", APP_CONFIG.ui_timeframes, index=APP_CONFIG.ui_timeframes.index(APP_CONFIG.timeframe) if APP_CONFIG.timeframe in APP_CONFIG.ui_timeframes else 0)
        risk_profile = st.selectbox("Risk Profili", ["low", "balanced", "aggressive"], index=["low", "balanced", "aggressive"].index(APP_CONFIG.default_risk_profile) if APP_CONFIG.default_risk_profile in ["low", "balanced", "aggressive"] else 1)
        trade_mode = st.selectbox(
            "İşlem Modu",
            ["SCALP_SPOT", "LEVERAGED_FUTURES"],
            index=0 if getattr(APP_CONFIG, "default_trade_mode", "LEVERAGED_FUTURES") == "SCALP_SPOT" else 1,
        )
        auto_refresh = st.toggle("Auto Refresh (10s)", value=True)
        run_once = st.button("Veriyi Güncelle")

        st.markdown("---")
        reset_confirm = st.checkbox("Reset Paper State onayı", value=False)
        reset_state_btn = st.button("Reset Paper State", type="secondary", disabled=not reset_confirm)

    fetcher.set_market(symbol=symbol, timeframe=timeframe)
    te.set_risk_profile(risk_profile=risk_profile)
    te.set_trade_mode(trade_mode=trade_mode)

    if reset_state_btn and reset_confirm:
        if hasattr(te, "reset_paper_state"):
            te.reset_paper_state()
            st.session_state["last_bundle"] = None
            st.session_state["last_clean"] = None
            st.session_state["last_pred"] = {"direction": "HOLD", "prob_up": 0.5, "prob_down": 0.5, "backend": "none"}
            st.session_state["last_data_sig"] = None
            st.session_state["last_trained_sig"] = None
            st.session_state["last_prediction_sig"] = None
            st.success("Paper state sıfırlandı.")
        else:
            # Backward-compatible fallback for cached/older TradingEngine instances
            current_risk = te.portfolio.risk_profile
            te.portfolio = te.portfolio.__class__(
                balance=float(getattr(te, "initial_balance", APP_CONFIG.initial_balance)),
                daily_start_balance=float(getattr(te, "initial_balance", APP_CONFIG.initial_balance)),
                risk_profile=current_risk,
                risk_profiles=te.portfolio.risk_profiles,
            )
            te.trade_history = []
            st.session_state["last_bundle"] = None
            st.session_state["last_clean"] = None
            st.session_state["last_pred"] = {"direction": "HOLD", "prob_up": 0.5, "prob_down": 0.5, "backend": "none"}
            st.session_state["last_data_sig"] = None
            st.session_state["last_trained_sig"] = None
            st.session_state["last_prediction_sig"] = None
            st.warning("Eski cache instance bulundu; uyumlu fallback ile paper state sıfırlandı.")

    auto_tick = 0
    if auto_refresh:
        auto_tick = st_autorefresh(interval=10000, key="dashboard_refresh_10s")

    controls_changed = (
        st.session_state.get("_last_symbol") != symbol
        or st.session_state.get("_last_timeframe") != timeframe
        or st.session_state.get("_last_risk_profile") != risk_profile
        or st.session_state.get("_last_trade_mode") != trade_mode
    )

    should_run = run_once or controls_changed or (auto_refresh and auto_tick > 0)

    st.session_state["_last_symbol"] = symbol
    st.session_state["_last_timeframe"] = timeframe
    st.session_state["_last_risk_profile"] = risk_profile
    st.session_state["_last_trade_mode"] = trade_mode

    if should_run:
        bundle = fetcher.fetch_all()
        df = bundle["ohlcv"]

        if not df.empty:
            data_sig = _dataset_signature(df)
            market_changed = st.session_state.get("last_data_sig") != data_sig

            X, y, feature_cols, clean = fe.build_ml_dataset(
                df=df,
                news_sentiment=bundle["news_sentiment"],
                long_short_bias=bundle["long_short_bias"],
            )

            if len(X) > 60:
                if market_changed or st.session_state.get("last_trained_sig") != data_sig:
                    ml.train(X.iloc[:-1], y.iloc[:-1])
                    st.session_state["last_trained_sig"] = data_sig

                if market_changed or st.session_state.get("last_prediction_sig") != data_sig:
                    pred = ml.predict_next(X.iloc[[-1]])
                    st.session_state["last_pred"] = pred
                    st.session_state["last_prediction_sig"] = data_sig
                else:
                    pred = st.session_state.get("last_pred")
            else:
                pred = {"direction": "HOLD", "prob_up": 0.5, "prob_down": 0.5, "backend": "none"}
                st.session_state["last_pred"] = pred
                st.session_state["last_prediction_sig"] = data_sig

            current_price = float(clean["close"].iloc[-1])
            current_atr = float(clean["atr_14"].iloc[-1]) if "atr_14" in clean.columns else max(1.0, current_price * 0.005)
            confidence = max(pred.get("prob_up", 0.5), pred.get("prob_down", 0.5))

            te.on_price_tick(current_price)
            te.maybe_open_trade(
                direction=pred["direction"],
                price=current_price,
                atr_val=current_atr,
                confidence=confidence,
            )

            st.session_state["last_data_sig"] = data_sig
            st.session_state["last_bundle"] = bundle
            st.session_state["last_clean"] = clean

            logger.info(
                "UI update | symbol=%s timeframe=%s dir=%s up=%.3f down=%.3f changed=%s",
                symbol,
                timeframe,
                pred["direction"],
                pred["prob_up"],
                pred["prob_down"],
                market_changed,
            )
        else:
            st.warning("OHLCV verisi bu turda alınamadı, son başarılı veri gösteriliyor.")

    bundle = st.session_state.get("last_bundle")
    clean = st.session_state.get("last_clean")
    pred = st.session_state.get("last_pred")

    if bundle is None or clean is None:
        st.info("Veri bekleniyor. 'Veriyi Güncelle' ile ilk yüklemeyi yapabilir veya Auto Refresh açabilirsiniz.")
        return

    st.subheader(f"{symbol} | {timeframe}")
    fig = _build_candle_figure(clean.tail(180))
    st.plotly_chart(fig, width="stretch")

    c1, c2 = st.columns(2)
    with c1:
        st.plotly_chart(_gauge(bundle["news_sentiment"], "Sentiment (News)"), width="stretch")
    with c2:
        st.plotly_chart(_gauge(bundle["long_short_bias"], "Long/Short Bias (Binance Futures)"), width="stretch")

    st.markdown("### Model Yön Tahmini (Next Candle)")
    p1, p2, p3, p4 = st.columns(4)
    p1.metric("Direction", pred["direction"])
    p2.metric("Prob Up", f"{pred['prob_up']:.2%}")
    p3.metric("Prob Down", f"{pred['prob_down']:.2%}")
    p4.metric("Model", pred.get("backend", "unknown"))

    snap = te.snapshot()
    s1, s2, s3, s4, s5 = st.columns(5)
    s1.metric("Balance", f"{snap['balance']:.2f} USDT")
    s2.metric("Open Positions", f"{snap['open_positions']}")
    s3.metric("Closed Positions", f"{snap['closed_positions']}")
    s4.metric("Daily Loss %", f"{snap['daily_loss_pct']:.2%}")
    s5.metric("Trade Mode", f"{snap['trade_mode']}")

    st.markdown("### Risk Paneli")
    risk_conf = te.portfolio.risk_conf()
    daily_limit = float(risk_conf.get("daily_max_loss", 0.0))
    daily_used = float(snap.get("daily_loss_pct", 0.0))
    usage_ratio = (daily_used / daily_limit) if daily_limit > 0 else 0.0
    usage_ratio = max(0.0, min(1.0, usage_ratio))

    max_pos = int(risk_conf.get("max_positions", 0))
    open_pos = int(snap.get("open_positions", 0))
    capacity_left = max(0, max_pos - open_pos)

    r1, r2, r3, r4 = st.columns(4)
    r1.metric("Risk/Trade", f"{float(risk_conf.get('risk_per_trade', 0.0)):.2%}")
    r2.metric("Daily Max Loss", f"{daily_limit:.2%}")
    r3.metric("Daily Loss Usage", f"{daily_used:.2%}")
    r4.metric("Open Capacity", f"{open_pos}/{max_pos} (left {capacity_left})")

    st.progress(usage_ratio, text=f"Günlük kayıp limiti kullanım oranı: {usage_ratio:.0%}")

    st.markdown("#### Risk Uyarıları")
    if usage_ratio >= 1.0:
        st.error("🔴 Günlük kayıp limiti aşıldı: trade akışı risk motoru tarafından durdurulabilir.")
    elif usage_ratio >= 0.8:
        st.warning("🟠 Günlük kayıp limiti %80+ seviyesinde.")
    else:
        st.success("🟢 Günlük kayıp limiti güvenli aralıkta.")

    if max_pos > 0 and open_pos >= max_pos:
        st.error("🔴 Açık pozisyon kapasitesi dolu.")
    elif max_pos > 0 and open_pos >= max(1, int(max_pos * 0.8)):
        st.warning("🟠 Açık pozisyon kapasitesi %80+ dolu.")
    else:
        st.success("🟢 Açık pozisyon kapasitesi uygun.")

    if not bool(snap.get("trading_enabled", True)):
        st.error("🔴 Trading engine pasif durumda.")
    else:
        st.info("ℹ️ Trading engine aktif durumda.")

    if bool(snap.get("execution_enabled", False)) and not bool(snap.get("paper_only", True)) and not bool(snap.get("use_testnet", True)):
        st.warning("🟠 Canlı market execution aktif (paper_only=0, use_testnet=0).")

    status_df = pd.DataFrame(
        [
            {"field": "risk_profile", "value": snap.get("risk_profile")},
            {"field": "trade_mode", "value": snap.get("trade_mode")},
            {"field": "trading_enabled", "value": snap.get("trading_enabled")},
            {"field": "execution_enabled", "value": snap.get("execution_enabled")},
            {"field": "paper_only", "value": snap.get("paper_only")},
            {"field": "use_testnet", "value": snap.get("use_testnet")},
        ]
    )
    status_df["field"] = status_df["field"].astype(str)
    status_df["value"] = status_df["value"].astype(str)
    st.dataframe(status_df, width="stretch", hide_index=True)

    st.markdown("### Son İşlem Geçmişi")

    full_history_df = pd.DataFrame(te.trade_history)

    if not full_history_df.empty:
        pnl_series = pd.to_numeric(full_history_df.get("pnl", pd.Series(dtype=float)), errors="coerce").fillna(0.0)
        total_net_pnl = float(pnl_series.sum())

        close_df = full_history_df[full_history_df.get("event", "").astype(str) == "CLOSE"].copy()
        if not close_df.empty:
            close_df["_time_dt"] = pd.to_datetime(close_df.get("time"), errors="coerce", utc=True)
            close_df["_pnl"] = pd.to_numeric(close_df.get("pnl"), errors="coerce").fillna(0.0)

            now_utc = pd.Timestamp.utcnow()
            day_cut = now_utc - pd.Timedelta(days=1)
            week_cut = now_utc - pd.Timedelta(days=7)

            day_df = close_df[close_df["_time_dt"] >= day_cut]
            week_df = close_df[close_df["_time_dt"] >= week_cut]

            day_win_rate = float((day_df["_pnl"] > 0).mean()) if len(day_df) > 0 else 0.0
            week_win_rate = float((week_df["_pnl"] > 0).mean()) if len(week_df) > 0 else 0.0
            close_count = int(len(close_df))
        else:
            day_win_rate = 0.0
            week_win_rate = 0.0
            close_count = 0

        p1, p2, p3, p4 = st.columns(4)
        p1.metric("Toplam Net PnL", f"{total_net_pnl:.2f} USDT")
        p2.metric("24s Win Rate", f"{day_win_rate:.2%}")
        p3.metric("7g Win Rate", f"{week_win_rate:.2%}")
        p4.metric("Closed Trades", f"{close_count}")

    if full_history_df.empty:
        st.info("Henüz işlem yok.")
    else:
        with st.expander("Filtreler ve CSV Export", expanded=True):
            col_f1, col_f2, col_f3 = st.columns(3)
            with col_f1:
                event_opts = ["ALL"] + sorted(full_history_df["event"].dropna().astype(str).unique().tolist())
                event_filter = st.selectbox("Event", event_opts, index=0)
            with col_f2:
                side_opts = ["ALL"] + sorted(full_history_df["side"].dropna().astype(str).unique().tolist())
                side_filter = st.selectbox("Side", side_opts, index=0)
            with col_f3:
                mode_opts = ["ALL"] + sorted(full_history_df["trade_mode"].dropna().astype(str).unique().tolist())
                mode_filter = st.selectbox("Trade Mode", mode_opts, index=0)

            col_f4, col_f5 = st.columns(2)
            with col_f4:
                default_start = date.today()
                start_date = st.date_input("Start Date", value=default_start)
            with col_f5:
                end_date = st.date_input("End Date", value=date.today())

        filtered_df = full_history_df.copy()
        if event_filter != "ALL":
            filtered_df = filtered_df[filtered_df["event"].astype(str) == event_filter]
        if side_filter != "ALL":
            filtered_df = filtered_df[filtered_df["side"].astype(str) == side_filter]
        if mode_filter != "ALL":
            filtered_df = filtered_df[filtered_df["trade_mode"].astype(str) == mode_filter]

        if "time" in filtered_df.columns:
            filtered_df["_time_dt"] = pd.to_datetime(filtered_df["time"], errors="coerce", utc=True)
            start_dt = pd.Timestamp(datetime.combine(start_date, datetime.min.time()), tz="UTC")
            end_dt = pd.Timestamp(datetime.combine(end_date, datetime.max.time()), tz="UTC")
            filtered_df = filtered_df[
                (filtered_df["_time_dt"].isna()) | ((filtered_df["_time_dt"] >= start_dt) & (filtered_df["_time_dt"] <= end_dt))
            ].drop(columns=["_time_dt"], errors="ignore")

        st.caption(f"Filtrelenmiş kayıt: {len(filtered_df)} / Toplam: {len(full_history_df)}")
        display_df = filtered_df.tail(200).copy()
        for col in display_df.columns:
            if display_df[col].dtype == "object":
                display_df[col] = display_df[col].astype(str)
        st.dataframe(display_df, width="stretch")

        csv_data = filtered_df.to_csv(index=False).encode("utf-8")
        st.download_button(
            "CSV İndir (Filtrelenmiş)",
            data=csv_data,
            file_name=f"trade_history_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}.csv",
            mime="text/csv",
        )


if __name__ == "__main__":
    run_dashboard()
