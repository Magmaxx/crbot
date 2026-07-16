import os
import math
import asyncio
import threading
import queue
import logging
import tkinter as tk
from tkinter import ttk
from dataclasses import dataclass, field
from datetime import datetime, date, timezone
from typing import List, Optional, Literal, Dict


import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
try:
    import ccxt.pro as ccxtpro
except Exception:
    import ccxt.async_support as ccxtpro

# =========================
# Configuration
# =========================
NEWS_API_KEY = os.getenv("NEWS_API_KEY", "")
EXCHANGE_ID = os.getenv("EXCHANGE_ID", "binance")
SYMBOL = os.getenv("SYMBOL", "BTC/USDT")
TIMEFRAME = os.getenv("TIMEFRAME", "1m")
INITIAL_BALANCE = float(os.getenv("INITIAL_BALANCE", "10000"))
CONFIDENCE_THRESHOLD = float(os.getenv("CONFIDENCE_THRESHOLD", "0.60"))
REST_FALLBACK_ENABLED = os.getenv("REST_FALLBACK_ENABLED", "1") == "1"
STRICT_TESTNET_DEFAULT = os.getenv("STRICT_TESTNET", "0") == "1"

RISK_PROFILES: Dict[str, Dict[str, float]] = {
    "low": {"risk_per_trade": 0.005, "daily_max_loss": 0.02, "max_positions": 2},
    "balanced": {"risk_per_trade": 0.01, "daily_max_loss": 0.03, "max_positions": 2},
    "aggressive": {"risk_per_trade": 0.02, "daily_max_loss": 0.05, "max_positions": 3},
}
DEFAULT_RISK_PROFILE = "balanced"

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger("ai-trading-gui")

MIN_OHLCV_LENGTH = 60
SHORT_LOOP_SLEEP_SEC = 0.2
REST_LOOP_SLEEP_SEC = 1.0
MAX_RECONNECT_DELAY_SEC = 30
MAX_RECONNECT_EXP = 5


# =========================
# Data Models
# =========================
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
    exchange_id: str = EXCHANGE_ID
    api_key: str = ""
    api_secret: str = ""
    testnet: bool = True
    strict_testnet: bool = STRICT_TESTNET_DEFAULT
    symbol: str = SYMBOL
    timeframe: str = TIMEFRAME


@dataclass
class Portfolio:
    balance: float = INITIAL_BALANCE
    daily_start_balance: float = INITIAL_BALANCE
    daily_date: date = field(default_factory=lambda: datetime.now(timezone.utc).date())
    open_positions: List[Position] = field(default_factory=list)
    closed_positions: List[Position] = field(default_factory=list)
    trading_enabled: bool = True
    risk_profile: str = DEFAULT_RISK_PROFILE

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
        return RISK_PROFILES[self.risk_profile]


# =========================
# Indicator & Signal
# =========================
def ema(values: List[float], period: int) -> float:
    if not values:
        return 0.0
    if len(values) < period:
        return values[-1]
    k = 2 / (period + 1)
    e = values[0]
    for v in values[1:]:
        e = v * k + e * (1 - k)
    return e


def rsi(values: List[float], period: int = 14) -> float:
    if len(values) < period + 1:
        return 50.0
    gains, losses = [], []
    for i in range(-period, 0):
        diff = values[i] - values[i - 1]
        if diff >= 0:
            gains.append(diff)
            losses.append(0.0)
        else:
            gains.append(0.0)
            losses.append(abs(diff))
    avg_gain = sum(gains) / period
    avg_loss = sum(losses) / period
    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))


def atr_from_ohlcv(ohlcv: List[List[float]], period: int = 14) -> float:
    if len(ohlcv) < period + 1:
        close = ohlcv[-1][4] if ohlcv else 1.0
        return max(1.0, close * 0.005)

    highs = [c[2] for c in ohlcv]
    lows = [c[3] for c in ohlcv]
    closes = [c[4] for c in ohlcv]
    trs = []
    for i in range(1, len(closes)):
        tr = max(
            highs[i] - lows[i],
            abs(highs[i] - closes[i - 1]),
            abs(lows[i] - closes[i - 1]),
        )
        trs.append(tr)
    recent = trs[-period:]
    return sum(recent) / len(recent)


def fetch_news_sentiment_score() -> float:
    if not NEWS_API_KEY:
        return 0.0
    try:
        url = "https://newsapi.org/v2/everything"
        params = {
            "q": "bitcoin OR crypto OR ethereum",
            "language": "en",
            "sortBy": "publishedAt",
            "pageSize": 20,
            "apiKey": NEWS_API_KEY,
        }
        r = requests.get(url, params=params, timeout=10)
        r.raise_for_status()
        articles = r.json().get("articles", [])
        text = " ".join(
            ((a.get("title") or "") + " " + (a.get("description") or "")) for a in articles
        ).lower()

        bullish = ["surge", "rally", "adoption", "breakout", "approval", "growth", "bullish"]
        bearish = ["hack", "ban", "lawsuit", "crash", "selloff", "recession", "bearish"]
        bull_score = sum(text.count(w) for w in bullish)
        bear_score = sum(text.count(w) for w in bearish)
        total = bull_score + bear_score
        if total == 0:
            return 0.0
        return (bull_score - bear_score) / total
    except Exception as e:
        logger.warning(f"News sentiment alınamadı: {e}")
        return 0.0


def build_signal(ohlcv: List[List[float]]) -> Dict[str, float]:
    closes = [c[4] for c in ohlcv]
    price = closes[-1]
    ema_fast = ema(closes[-50:], 20)
    ema_slow = ema(closes[-200:], 50)
    rsi_val = rsi(closes, 14)
    atr_val = atr_from_ohlcv(ohlcv, 14)
    sentiment = fetch_news_sentiment_score()

    tech_score = 0.0
    if ema_fast > ema_slow:
        tech_score += 0.35
    else:
        tech_score -= 0.35

    if rsi_val < 35:
        tech_score += 0.25
    elif rsi_val > 65:
        tech_score -= 0.25

    score = tech_score + (0.4 * sentiment)
    confidence_long = 1 / (1 + math.exp(-score))
    confidence_short = 1 - confidence_long

    if confidence_long >= CONFIDENCE_THRESHOLD:
        action = "LONG"
        confidence = confidence_long
    elif confidence_short >= CONFIDENCE_THRESHOLD:
        action = "SHORT"
        confidence = confidence_short
    else:
        action = "HOLD"
        confidence = max(confidence_long, confidence_short)

    return {
        "action": action,
        "confidence": confidence,
        "price": price,
        "atr": atr_val,
        "rsi": rsi_val,
        "sentiment": sentiment,
    }


# =========================
# Core Engine
# =========================
def create_resilient_session() -> requests.Session:
    s = requests.Session()
    retry = Retry(
        total=4,
        connect=4,
        read=4,
        status=4,
        backoff_factor=0.6,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["HEAD", "GET", "OPTIONS"],
        raise_on_status=False,
    )
    adapter = HTTPAdapter(max_retries=retry)
    s.mount("https://", adapter)
    s.mount("http://", adapter)
    return s


class TradingEngine:
    def __init__(self, gui_queue: "queue.Queue[dict]"):
        self.gui_queue = gui_queue
        self.portfolio = Portfolio()
        self.exchange = None
        self.running = False
        self._thread = None
        self._loop = None
        self.exchange_config = ExchangeConfig()
        self._reconnect_attempt = 0
        self.http_session = create_resilient_session()
        self.rest_mode = False
        self._stopping = False
        self._lock = threading.RLock()
        self._loop_ready = threading.Event()
        self._strategy_task = None
        self._max_notional_pct = 0.25

    def log(self, msg: str):
        logger.info(msg)
        self.gui_queue.put({"type": "log", "message": msg})

    def set_risk_profile(self, profile: str):
        profile = (profile or "").strip().lower()
        if profile in RISK_PROFILES:
            prev = self.portfolio.risk_profile
            self.portfolio.risk_profile = profile
            conf = self.portfolio.risk_conf()
            self.log(
                f"Risk profili güncellendi: {prev} -> {profile} | "
                f"risk_per_trade=%{conf['risk_per_trade']*100:.1f} "
                f"daily_max_loss=%{conf['daily_max_loss']*100:.1f} "
                f"max_positions={int(conf['max_positions'])}"
            )

    def start(self):
        with self._lock:
            if self.running:
                return
            if self._thread and self._thread.is_alive():
                self._thread.join(timeout=2.0)

            self._stopping = False
            self.running = True
            self.exchange = None
            self.rest_mode = False
            self._reconnect_attempt = 0
            self._loop_ready.clear()
            self._thread = threading.Thread(target=self._run_async_loop, daemon=True)
            self._thread.start()
            self._loop_ready.wait(timeout=2.0)
            self.log("Trading engine başlatıldı.")

    def stop(self):
        with self._lock:
            if not self.running:
                return
            self.running = False
            self._stopping = True
            self.log("Trading engine durduruluyor...")
            loop = self._loop
            task = self._strategy_task

            if loop and loop.is_running():
                if task and not task.done():
                    loop.call_soon_threadsafe(task.cancel)

            if self._thread and self._thread.is_alive():
                self._thread.join(timeout=3.0)

            self._strategy_task = None
            self._loop = None
            self.log("Trading engine durduruldu.")

    def _run_async_loop(self):
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        self._loop_ready.set()
        self._strategy_task = self._loop.create_task(self._strategy_loop())

        try:
            self._loop.run_until_complete(self._strategy_task)
        except asyncio.CancelledError:
            pass
        finally:
            try:
                pending = asyncio.all_tasks(self._loop)
                for t in pending:
                    t.cancel()
                if pending:
                    self._loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))
            except Exception:
                pass
            finally:
                try:
                    self._loop.run_until_complete(self._close_exchange())
                except Exception:
                    pass
                try:
                    self._loop.close()
                except Exception:
                    pass
            self._loop = None
            self._strategy_task = None

    def update_exchange_config(
        self,
        exchange_id: Optional[str] = None,
        api_key: Optional[str] = None,
        api_secret: Optional[str] = None,
        testnet: Optional[bool] = None,
        strict_testnet: Optional[bool] = None,
        symbol: Optional[str] = None,
        timeframe: Optional[str] = None,
    ):
        if exchange_id is not None:
            self.exchange_config.exchange_id = exchange_id.strip().lower()
        if api_key is not None:
            self.exchange_config.api_key = api_key.strip()
        if api_secret is not None:
            self.exchange_config.api_secret = api_secret.strip()
        if testnet is not None:
            self.exchange_config.testnet = bool(testnet)
        if strict_testnet is not None:
            self.exchange_config.strict_testnet = bool(strict_testnet)
        if symbol is not None:
            self.exchange_config.symbol = symbol.strip().upper().replace("-", "/")
        if timeframe is not None:
            self.exchange_config.timeframe = timeframe.strip()

    async def _connect_exchange(self):
        cfg = self.exchange_config
        if cfg.exchange_id != "binance":
            raise ValueError("Bu sürüm şu an yalnızca binance için yapılandırıldı.")

        options = {
            "enableRateLimit": True,
            "timeout": 20000,
            "options": {
                "defaultType": "spot",
                "adjustForTimeDifference": True,
            },
        }
        if cfg.api_key:
            options["apiKey"] = cfg.api_key
        if cfg.api_secret:
            options["secret"] = cfg.api_secret

        # ccxt.pro yoksa ccxt.async_support fallback kullanılıyor olabilir.
        # Fallback modda watch_ohlcv olmayabilir; o durumda net hata ver.
        self.exchange = ccxtpro.binance(options)
        self.exchange.verbose = bool(os.getenv("CCXT_VERBOSE", "0") == "1")

        # Binance testnet endpointleri özellikle REST tarafında bölgesel/erişimsel olarak sık hata verir.
        # Paper trading için market data zorunlu olduğundan, testnet açıkken bağlantı kurulamazsa
        # otomatik olarak mainnet public market data'ya düşmek daha güvenli.
        if cfg.testnet and hasattr(self.exchange, "set_sandbox_mode"):
            try:
                self.exchange.set_sandbox_mode(True)
            except Exception as e:
                self.log(f"Sandbox mode aktif edilemedi, mainnet public data kullanılacak: {e}")
                cfg.testnet = False

        # Bağlantıyı erken doğrula (exchangeInfo erişimi)
        try:
            await self.exchange.load_markets()
        except Exception as e:
            if cfg.testnet:
                if cfg.strict_testnet:
                    self.log(
                        "Strict testnet aktif: Testnet erişimi başarısız, fallback yapılmadan engine durdurulacak: "
                        f"{type(e).__name__}: {e}"
                    )
                    try:
                        await self.exchange.close()
                    except Exception:
                        pass
                    self.exchange = None
                    self.running = False
                    self._stopping = True
                    return
                self.log(
                    "Testnet erişimi başarısız, mainnet public market data'ya otomatik geçiliyor: "
                    f"{type(e).__name__}: {e}"
                )
                try:
                    await self.exchange.close()
                except Exception:
                    pass

                cfg.testnet = False
                self.exchange = ccxtpro.binance(options)
                self.exchange.verbose = bool(os.getenv("CCXT_VERBOSE", "0") == "1")
                await self.exchange.load_markets()
            else:
                if REST_FALLBACK_ENABLED:
                    self.log(
                        "CCXT market yükleme başarısız. REST fallback moduna geçilecek: "
                        f"{type(e).__name__}: {e}"
                    )
                    try:
                        await self.exchange.close()
                    except Exception:
                        pass
                    self.exchange = None
                    self.rest_mode = True
                    self.log("REST fallback kalıcı mod aktif edildi (CCXT reconnect devre dışı).")
                    return
                raise

        self.log(
            f"CCXT WebSocket bağlandı | exchange={cfg.exchange_id} "
            f"symbol={cfg.symbol} tf={cfg.timeframe} testnet={cfg.testnet}"
        )

    async def _close_exchange(self):
        if not self.exchange:
            return
        try:
            await self.exchange.close()
            self.log("Exchange bağlantısı kapatıldı.")
        except Exception as e:
            self.log(f"Exchange kapatma sırasında uyarı: {type(e).__name__}: {e}")

    def _can_open_new_position(self) -> bool:
        p = self.portfolio
        p.reset_daily_if_needed()
        conf = p.risk_conf()

        if not p.trading_enabled:
            return False

        if p.daily_loss_pct() >= conf["daily_max_loss"]:
            p.trading_enabled = False
            self.log("Günlük max zarar limitine ulaşıldı, işlemler durdu.")
            return False

        open_count = len([x for x in p.open_positions if x.status == "OPEN"])
        return open_count < int(conf["max_positions"])

    def _calc_position_size(self, entry: float, stop: float) -> float:
        conf = self.portfolio.risk_conf()
        risk_amount = self.portfolio.balance * conf["risk_per_trade"]
        unit_risk = abs(entry - stop)
        if unit_risk <= 0:
            return 0.0

        raw_qty = risk_amount / unit_risk
        max_notional = self.portfolio.balance * self._max_notional_pct
        max_qty_by_notional = max_notional / max(entry, 1e-9)
        qty = min(raw_qty, max_qty_by_notional)
        qty = max(0.0, round(qty, 5))
        return qty

    def _open_paper_position(self, side: Side, entry: float, atr_val: float) -> Optional[Position]:
        sl_dist = max(atr_val * 1.2, entry * 0.004)
        tp_dist = sl_dist * 1.8

        if side == "LONG":
            stop = entry - sl_dist
            take = entry + tp_dist
        else:
            stop = entry + sl_dist
            take = entry - tp_dist

        qty = self._calc_position_size(entry, stop)
        if qty <= 0:
            return None

        pos = Position(side=side, entry_price=entry, qty=qty, stop_loss=stop, take_profit=take)
        self.portfolio.open_positions.append(pos)
        return pos

    def _mark_to_market(self, current_price: float):
        p = self.portfolio
        for pos in p.open_positions:
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
                p.balance += pos.pnl
                p.closed_positions.append(pos)
                self.log(f"Pozisyon kapandı: {pos.side} PnL={pos.pnl:.2f}")

        p.open_positions = [x for x in p.open_positions if x.status == "OPEN"]

    def _push_state(self, price: float, signal: Dict[str, float]):
        p = self.portfolio
        self.gui_queue.put(
            {
                "type": "state",
                "price": price,
                "signal": signal["action"],
                "confidence": signal["confidence"],
                "balance": p.balance,
                "open_positions": len(p.open_positions),
                "closed_positions": len(p.closed_positions),
                "daily_loss_pct": p.daily_loss_pct() * 100,
                "risk_profile": p.risk_profile,
            }
        )

        rows = []
        for pos in (p.open_positions + p.closed_positions)[-20:]:
            rows.append(
                (
                    pos.opened_at.strftime("%H:%M:%S"),
                    pos.side,
                    f"{pos.entry_price:.2f}",
                    f"{(pos.exit_price or 0):.2f}",
                    f"{pos.qty:.5f}",
                    f"{pos.pnl:.2f}",
                    pos.status,
                )
            )
        self.gui_queue.put({"type": "table", "rows": rows})

    def _fetch_ohlcv_rest(self, symbol: str, timeframe: str, limit: int = 200):
        tf_map = {
            "1m": "1m", "3m": "3m", "5m": "5m", "15m": "15m",
            "30m": "30m", "1h": "1h", "4h": "4h", "1d": "1d",
        }
        interval = tf_map.get(timeframe, "1m")
        symbol_api = symbol.replace("/", "")
        url = "https://api.binance.com/api/v3/klines"
        params = {"symbol": symbol_api, "interval": interval, "limit": limit}
        r = self.http_session.get(url, params=params, timeout=10)
        r.raise_for_status()
        raw = r.json()
        return [[int(x[0]), float(x[1]), float(x[2]), float(x[3]), float(x[4]), float(x[5])] for x in raw]

    async def _strategy_loop(self):
        try:
            while self.running:
                try:
                    cfg = self.exchange_config

                    if not self.rest_mode and self.exchange is None:
                        await self._connect_exchange()

                    if (not self.rest_mode) and self.exchange is not None:
                        ohlcv = await self.exchange.watch_ohlcv(cfg.symbol, timeframe=cfg.timeframe)
                    else:
                        ohlcv = self._fetch_ohlcv_rest(cfg.symbol, cfg.timeframe)
                        await asyncio.sleep(REST_LOOP_SLEEP_SEC)

                    if not ohlcv or len(ohlcv) < MIN_OHLCV_LENGTH:
                        await asyncio.sleep(SHORT_LOOP_SLEEP_SEC)
                        continue

                    self._handle_market_tick(ohlcv)
                    await asyncio.sleep(SHORT_LOOP_SLEEP_SEC)

                except asyncio.CancelledError:
                    break
                except Exception as e:
                    if not self.running or self._stopping:
                        break
                    await self._handle_strategy_exception(e)
        finally:
            await self._close_exchange()
            self.exchange = None
            self.running = False

    def _handle_market_tick(self, ohlcv: List[List[float]]) -> None:
        self._reconnect_attempt = 0
        current_price = ohlcv[-1][4]
        self._mark_to_market(current_price)
        signal = build_signal(ohlcv)

        if signal["action"] in ("LONG", "SHORT") and self._can_open_new_position():
            pos = self._open_paper_position(signal["action"], signal["price"], signal["atr"])
            if pos:
                self.log(
                    f"[PAPER OPEN] {pos.side} Entry={pos.entry_price:.2f} "
                    f"SL={pos.stop_loss:.2f} TP={pos.take_profit:.2f} Qty={pos.qty:.5f}"
                )

        self._push_state(current_price, signal)

    async def _handle_strategy_exception(self, e: Exception) -> None:
        self._reconnect_attempt += 1
        delay = min(MAX_RECONNECT_DELAY_SEC, 2 ** min(self._reconnect_attempt, MAX_RECONNECT_EXP))
        self.log(
            f"Strategy loop hata: {type(e).__name__}: {e} | "
            f"reconnect {delay}s sonra denenecek (attempt={self._reconnect_attempt})"
        )
        await self._close_exchange()
        self.exchange = None
        await asyncio.sleep(delay)


# =========================
# GUI
# =========================
class TradingApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("AI Trading Bot - Desktop GUI (CCXT WebSocket)")
        self.geometry("1220x760")
        self.minsize(1100, 680)
        self.configure(bg="#0f172a")

        self.gui_queue: "queue.Queue[dict]" = queue.Queue()
        self.engine = TradingEngine(self.gui_queue)

        self.style = ttk.Style()
        self._init_style()
        self._build_layout()
        self._poll_gui_queue()

        self.protocol("WM_DELETE_WINDOW", self._on_close)

    def _init_style(self):
        self.style.theme_use("clam")
        self.style.configure("TFrame", background="#0f172a")
        self.style.configure("Card.TFrame", background="#1e293b")
        self.style.configure("Side.TFrame", background="#111827")
        self.style.configure("TLabel", background="#0f172a", foreground="#e5e7eb", font=("Segoe UI", 10))
        self.style.configure("CardTitle.TLabel", background="#1e293b", foreground="#93c5fd", font=("Segoe UI", 9, "bold"))
        self.style.configure("CardValue.TLabel", background="#1e293b", foreground="#f8fafc", font=("Segoe UI", 17, "bold"))
        self.style.configure("Header.TLabel", background="#0f172a", foreground="#f8fafc", font=("Segoe UI", 15, "bold"))
        self.style.configure("TButton", font=("Segoe UI", 10, "bold"), padding=8)
        self.style.configure("Accent.TButton", background="#2563eb", foreground="#ffffff")
        self.style.map("Accent.TButton", background=[("active", "#1d4ed8")])

    def _build_layout(self):
        root = ttk.Frame(self)
        root.pack(fill="both", expand=True, padx=16, pady=16)

        side = ttk.Frame(root, style="Side.TFrame")
        side.pack(side="left", fill="y", padx=(0, 12))
        side.config(width=230)

        ttk.Label(side, text="AI TRADER", font=("Segoe UI", 16, "bold"), background="#111827", foreground="#60a5fa").pack(
            anchor="w", padx=14, pady=(18, 20)
        )
        ttk.Label(side, text="• Dashboard", background="#111827").pack(anchor="w", padx=16, pady=6)
        ttk.Label(side, text="• Risk Control", background="#111827").pack(anchor="w", padx=16, pady=6)
        ttk.Label(side, text="• Logs", background="#111827").pack(anchor="w", padx=16, pady=6)

        content = ttk.Frame(root)
        content.pack(side="left", fill="both", expand=True)

        topbar = ttk.Frame(content)
        topbar.pack(fill="x")
        ttk.Label(topbar, text="AI Trading Dashboard", style="Header.TLabel").pack(side="left")

        controls = ttk.Frame(topbar)
        controls.pack(side="right")
        self.risk_var = tk.StringVar(value=DEFAULT_RISK_PROFILE)
        ttk.Label(controls, text="Risk:", background="#0f172a").pack(side="left", padx=(0, 6))

        # Combobox bazı Windows temalarında tıklanamayabiliyor.
        # Radiobutton ile kesin tıklanabilir seçim sunuyoruz.
        risk_group = ttk.Frame(controls)
        risk_group.pack(side="left", padx=(0, 10))

        ttk.Radiobutton(
            risk_group,
            text="Low",
            value="low",
            variable=self.risk_var,
            command=self._on_risk_change,
        ).pack(side="left", padx=2)

        ttk.Radiobutton(
            risk_group,
            text="Balanced",
            value="balanced",
            variable=self.risk_var,
            command=self._on_risk_change,
        ).pack(side="left", padx=2)

        ttk.Radiobutton(
            risk_group,
            text="Aggressive",
            value="aggressive",
            variable=self.risk_var,
            command=self._on_risk_change,
        ).pack(side="left", padx=2)

        ttk.Button(controls, text="Start", style="Accent.TButton", command=self._start_engine).pack(side="left", padx=4)
        ttk.Button(controls, text="Stop", command=self._stop_engine).pack(side="left", padx=4)

        self.tabs = ttk.Notebook(content)
        self.tabs.pack(fill="both", expand=True, pady=(12, 0))

        controls.lift()

        self.dashboard_tab = ttk.Frame(self.tabs)
        self.settings_tab = ttk.Frame(self.tabs)
        self.positions_tab = ttk.Frame(self.tabs)
        self.logs_tab = ttk.Frame(self.tabs)

        self.tabs.add(self.dashboard_tab, text="Dashboard")
        self.tabs.add(self.settings_tab, text="Settings")
        self.tabs.add(self.positions_tab, text="Positions")
        self.tabs.add(self.logs_tab, text="Logs")

        cards = ttk.Frame(self.dashboard_tab)
        cards.pack(fill="x", pady=(0, 10))

        self.price_var = tk.StringVar(value="-")
        self.signal_var = tk.StringVar(value="-")
        self.balance_var = tk.StringVar(value=f"{INITIAL_BALANCE:.2f}")
        self.open_var = tk.StringVar(value="0")

        self._card(cards, "Canlı Fiyat", self.price_var).pack(side="left", fill="x", expand=True, padx=(0, 8))
        self._card(cards, "Sinyal", self.signal_var).pack(side="left", fill="x", expand=True, padx=8)
        self._card(cards, "Bakiye", self.balance_var).pack(side="left", fill="x", expand=True, padx=8)
        self._card(cards, "Açık Pozisyon", self.open_var).pack(side="left", fill="x", expand=True, padx=(8, 0))

        positions_wrap = ttk.Frame(self.positions_tab)
        positions_wrap.pack(fill="both", expand=True)

        table_card = ttk.Frame(positions_wrap, style="Card.TFrame")
        table_card.pack(fill="both", expand=True, padx=8, pady=8)
        ttk.Label(table_card, text="İşlem Geçmişi", style="CardTitle.TLabel").pack(anchor="w", padx=12, pady=(10, 6))

        columns = ("time", "side", "entry", "exit", "qty", "pnl", "status")
        self.table = ttk.Treeview(table_card, columns=columns, show="headings", height=16)
        headers = ["Saat", "Yön", "Entry", "Exit", "Qty", "PnL", "Durum"]
        for c, h in zip(columns, headers):
            self.table.heading(c, text=h)
            self.table.column(c, width=90, anchor="center")
        self.table.pack(fill="both", expand=True, padx=10, pady=(0, 10))

        log_wrap = ttk.Frame(self.logs_tab)
        log_wrap.pack(fill="both", expand=True)

        log_card = ttk.Frame(log_wrap, style="Card.TFrame")
        log_card.pack(fill="both", expand=True, padx=8, pady=8)
        ttk.Label(log_card, text="Canlı Log", style="CardTitle.TLabel").pack(anchor="w", padx=12, pady=(10, 6))
        self.log_text = tk.Text(
            log_card,
            height=16,
            bg="#0b1220",
            fg="#d1d5db",
            relief="flat",
            font=("Consolas", 10),
            insertbackground="#ffffff",
        )
        self.log_text.pack(fill="both", expand=True, padx=10, pady=(0, 10))
        self.log_text.configure(state="disabled")

        self._build_settings_tab()

        self.status_var = tk.StringVar(value=self._status_text("Hazır"))
        ttk.Label(content, textvariable=self.status_var).pack(anchor="w", pady=(8, 0))

    def _card(self, parent, title: str, value_var: tk.StringVar):
        card = ttk.Frame(parent, style="Card.TFrame")
        ttk.Label(card, text=title, style="CardTitle.TLabel").pack(anchor="w", padx=12, pady=(10, 2))
        ttk.Label(card, textvariable=value_var, style="CardValue.TLabel").pack(anchor="w", padx=12, pady=(0, 10))
        return card

    def _append_log(self, message: str):
        self.log_text.configure(state="normal")
        self.log_text.insert("end", f"{datetime.now().strftime('%H:%M:%S')} | {message}\n")
        self.log_text.see("end")
        self.log_text.configure(state="disabled")

    def _build_settings_tab(self):
        frm = ttk.Frame(self.settings_tab)
        frm.pack(fill="both", expand=True, padx=12, pady=12)

        self.exchange_var = tk.StringVar(value=self.engine.exchange_config.exchange_id)
        self.symbol_var = tk.StringVar(value=self.engine.exchange_config.symbol)
        self.timeframe_var = tk.StringVar(value=self.engine.exchange_config.timeframe)
        self.testnet_var = tk.BooleanVar(value=self.engine.exchange_config.testnet)
        self.strict_testnet_var = tk.BooleanVar(value=self.engine.exchange_config.strict_testnet)
        self.api_key_var = tk.StringVar(value=self.engine.exchange_config.api_key)
        self.api_secret_var = tk.StringVar(value=self.engine.exchange_config.api_secret)

        ttk.Label(frm, text="Exchange").grid(row=0, column=0, sticky="w", padx=4, pady=6)
        ttk.Combobox(frm, textvariable=self.exchange_var, values=["binance"], state="readonly", width=20).grid(row=0, column=1, sticky="w", padx=4, pady=6)

        ttk.Label(frm, text="Symbol").grid(row=1, column=0, sticky="w", padx=4, pady=6)
        ttk.Entry(frm, textvariable=self.symbol_var, width=24).grid(row=1, column=1, sticky="w", padx=4, pady=6)

        ttk.Label(frm, text="Timeframe").grid(row=2, column=0, sticky="w", padx=4, pady=6)
        ttk.Combobox(frm, textvariable=self.timeframe_var, values=["1m", "3m", "5m", "15m", "1h"], state="readonly", width=20).grid(row=2, column=1, sticky="w", padx=4, pady=6)

        ttk.Checkbutton(frm, text="Testnet (Sandbox)", variable=self.testnet_var).grid(row=3, column=0, columnspan=2, sticky="w", padx=4, pady=6)
        ttk.Checkbutton(frm, text="Strict Testnet (bağlanamazsa fallback yok)", variable=self.strict_testnet_var).grid(row=4, column=0, columnspan=2, sticky="w", padx=4, pady=6)

        ttk.Label(frm, text="API Key").grid(row=5, column=0, sticky="w", padx=4, pady=6)
        ttk.Entry(frm, textvariable=self.api_key_var, width=40).grid(row=5, column=1, sticky="w", padx=4, pady=6)

        ttk.Label(frm, text="API Secret").grid(row=6, column=0, sticky="w", padx=4, pady=6)
        ttk.Entry(frm, textvariable=self.api_secret_var, show="*", width=40).grid(row=6, column=1, sticky="w", padx=4, pady=6)

        ttk.Button(frm, text="Apply Settings", style="Accent.TButton", command=self._apply_settings).grid(row=7, column=0, columnspan=2, sticky="w", padx=4, pady=10)

    def _apply_settings(self):
        was_running = self.engine.running
        if was_running:
            self.engine.stop()
            self._append_log("Settings değişikliği için engine durduruldu.")

        self.engine.update_exchange_config(
            exchange_id=self.exchange_var.get(),
            api_key=self.api_key_var.get(),
            api_secret=self.api_secret_var.get(),
            testnet=self.testnet_var.get(),
            strict_testnet=self.strict_testnet_var.get(),
            symbol=self.symbol_var.get(),
            timeframe=self.timeframe_var.get(),
        )

        self.engine.rest_mode = False
        self.engine._reconnect_attempt = 0
        self._append_log("Settings uygulandı. Yeni ayarlar bir sonraki bağlantıda kullanılacak.")
        self.status_var.set(self._status_text("Ayarlar güncellendi"))

        if was_running:
            self.engine.start()
            self._append_log("Engine yeni ayarlarla yeniden başlatıldı.")

    def _status_text(self, prefix: str) -> str:
        cfg = self.engine.exchange_config
        return (
            f"Durum: {prefix} | Exchange: {cfg.exchange_id} | Symbol: {cfg.symbol} | "
            f"TF: {cfg.timeframe} | Testnet: {cfg.testnet} | Strict: {cfg.strict_testnet} | Risk: {self.engine.portfolio.risk_profile}"
        )

    def _on_risk_change(self, _event=None):
        profile = self.risk_var.get().strip().lower()
        if profile not in RISK_PROFILES:
            return

        was_running = self.engine.running
        self.engine.set_risk_profile(profile)
        self.status_var.set(self._status_text(f"Risk={profile}"))
        self._append_log(f"Risk seçildi (UI): {profile}")

        # Kullanıcı gözlemine göre risk değişiminden sonra akış durabiliyor.
        # Engine çalışıyorsa kontrollü restart ile loop'un canlı kalmasını garanti ediyoruz.
        if was_running:
            self._append_log("Risk değişimi sonrası engine yeniden başlatılıyor...")
            self.engine.stop()
            self.engine.start()
            self._append_log("Engine yeniden başlatıldı, log akışı devam etmeli.")

    def _start_engine(self):
        self.engine.set_risk_profile(self.risk_var.get())
        self.engine.start()
        self.status_var.set(self._status_text("Çalışıyor (WebSocket canlı)"))

    def _stop_engine(self):
        self.engine.stop()
        self.status_var.set(self._status_text("Durduruldu"))

    def _poll_gui_queue(self):
        try:
            while True:
                item = self.gui_queue.get_nowait()
                t = item.get("type")

                if t == "log":
                    self._append_log(item["message"])

                elif t == "state":
                    self.price_var.set(f"{item['price']:.2f}")
                    self.signal_var.set(f"{item['signal']} ({item['confidence']:.2f})")
                    self.balance_var.set(f"{item['balance']:.2f}")
                    self.open_var.set(str(item["open_positions"]))

                elif t == "table":
                    for row in self.table.get_children():
                        self.table.delete(row)
                    for r in item["rows"]:
                        self.table.insert("", "end", values=r)

        except queue.Empty:
            pass

        self.after(200, self._poll_gui_queue)

    def _on_close(self):
        self.engine.stop()
        self.after(150, self.destroy)


def main():
    app = TradingApp()
    app.mainloop()


if __name__ == "__main__":
    main()

