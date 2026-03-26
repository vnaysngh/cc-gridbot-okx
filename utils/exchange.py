# utils/exchange.py
import os
import time
import ccxt
import pandas as pd
from datetime import datetime, timedelta
from dotenv import load_dotenv
from utils.logger import setup_logger

load_dotenv()
logger = setup_logger("exchange")


def get_exchange(exchange_id: str, authenticated: bool = False) -> ccxt.Exchange:
    exchange_class = getattr(ccxt, exchange_id)
    config = {"enableRateLimit": True}

    if authenticated:
        key_map = {
            "kucoin": {
                "apiKey":   os.getenv("KUCOIN_API_KEY"),
                "secret":   os.getenv("KUCOIN_API_SECRET"),
                "password": os.getenv("KUCOIN_API_PASSPHRASE"),
            },
            "okx": {
                "apiKey":   os.getenv("OKX_API_KEY"),
                "secret":   os.getenv("OKX_API_SECRET"),
                "password": os.getenv("OKX_API_PASSPHRASE"),
            },
            "kraken": {
                "apiKey":   os.getenv("KRAKEN_API_KEY"),
                "secret":   os.getenv("KRAKEN_API_SECRET"),
            },
            "bybit": {
                "apiKey":   os.getenv("BYBIT_API_KEY"),
                "secret":   os.getenv("BYBIT_API_SECRET"),
            },
            "gate": {
                "apiKey":   os.getenv("GATE_API_KEY"),
                "secret":   os.getenv("GATE_API_SECRET"),
            },
        }
        keys = key_map.get(exchange_id, {})

        # Debug: Log what we're actually getting from environment
        logger.debug(f"Loading keys for {exchange_id}:")
        logger.debug(f"  OKX_API_KEY: {'SET' if os.getenv('OKX_API_KEY') else 'MISSING'}")
        logger.debug(f"  OKX_API_SECRET: {'SET' if os.getenv('OKX_API_SECRET') else 'MISSING'}")
        logger.debug(f"  OKX_API_PASSPHRASE: {'SET' if os.getenv('OKX_API_PASSPHRASE') else 'MISSING'}")

        if not any(keys.values()):
            raise ValueError(f"No API keys found for {exchange_id}. Check your .env file.")
        config.update({k: v for k, v in keys.items() if v})

    exchange = exchange_class(config)
    logger.debug(f"Connected to {exchange_id} (authenticated={authenticated})")
    return exchange


def fetch_ohlcv(
    exchange_id: str,
    symbol: str,
    timeframe: str = "1h",
    days: int = 365,
) -> pd.DataFrame:
    """
    Fetch ALL available OHLCV candles for a symbol, paginating correctly.

    Stops only when the last fetched candle is within 2 hours of now,
    not when a page has fewer than the limit (which happens on listing day).

    No API key required.
    Returns DataFrame with Open/High/Low/Close/Volume and DatetimeIndex.
    """
    exchange = get_exchange(exchange_id, authenticated=False)

    per_page = 500
    now_ms = int(datetime.utcnow().timestamp() * 1000)
    two_hours_ms = 2 * 60 * 60 * 1000
    since_ms = int((datetime.utcnow() - timedelta(days=days)).timestamp() * 1000)

    logger.info(f"Fetching all available {timeframe} candles for {symbol} from {exchange_id}...")

    all_candles = []
    consecutive_empty = 0

    while since_ms < now_ms:
        candles = []
        for attempt in range(3):
            try:
                candles = exchange.fetch_ohlcv(symbol, timeframe, since=since_ms, limit=per_page)
                break
            except Exception as e:
                if attempt == 2:
                    logger.warning(f"Fetch error: {e}")
                time.sleep(2)

        if not candles:
            # No data — coin likely not listed yet, jump forward 30 days
            consecutive_empty += 1
            if consecutive_empty >= 12:
                logger.debug("No more data available.")
                break
            since_ms += int(timedelta(days=30).total_seconds() * 1000)
            continue

        consecutive_empty = 0

        # Drop duplicates with previous page
        if all_candles:
            candles = [c for c in candles if c[0] > all_candles[-1][0]]

        if not candles:
            break

        all_candles.extend(candles)
        last_candle_ts = all_candles[-1][0]
        since_ms = last_candle_ts + 1

        # Stop only when the last candle is within 2 hours of now
        # NOT when page size < per_page (that happens on listing day with few candles)
        if last_candle_ts >= now_ms - two_hours_ms:
            break

        time.sleep(exchange.rateLimit / 1000)

    if not all_candles:
        logger.error(f"No candle data found for {symbol} on {exchange_id}.")
        return pd.DataFrame()

    df = pd.DataFrame(all_candles, columns=["timestamp", "Open", "High", "Low", "Close", "Volume"])
    df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms")
    df.set_index("timestamp", inplace=True)
    df = df[~df.index.duplicated(keep="last")]
    df.sort_index(inplace=True)

    days_of_data = (df.index[-1] - df.index[0]).days
    logger.info(
        f"Fetched {len(df)} candles | "
        f"{df.index[0].strftime('%Y-%m-%d')} to {df.index[-1].strftime('%Y-%m-%d')} "
        f"({days_of_data} days)"
    )
    return df


def get_current_price(exchange: ccxt.Exchange, symbol: str) -> float:
    ticker = exchange.fetch_ticker(symbol)
    return float(ticker["last"])


def get_balance(exchange: ccxt.Exchange, currency: str = "USDT") -> float:
    balance = exchange.fetch_balance()
    return float(balance["free"].get(currency, 0))


def place_order(
    exchange: ccxt.Exchange,
    symbol: str,
    side: str,
    amount_usdt: float,
    order_type: str = "market",
    price: float = None,
    paper: bool = True,
) -> dict:
    price_now = get_current_price(exchange, symbol)
    amount_cc = amount_usdt / (price if price else price_now)

    if paper:
        fake_order = {
            "id": f"PAPER_{side.upper()}_{int(datetime.utcnow().timestamp())}",
            "symbol": symbol,
            "side": side,
            "type": order_type,
            "amount": amount_cc,
            "price": price if price else price_now,
            "cost": amount_usdt,
            "status": "closed",
            "paper": True,
        }
        logger.info(
            f"[PAPER] {side.upper()} {amount_cc:.4f} CC @ "
            f"${price if price else price_now:.4f} (${amount_usdt:.2f} USDT)"
        )
        return fake_order

    try:
        if order_type == "market":
            order = exchange.create_market_order(symbol, side, amount_cc)
        elif order_type == "limit" and price:
            order = exchange.create_limit_order(symbol, side, amount_cc, price)
        else:
            raise ValueError(f"Unknown order_type: {order_type}")

        logger.info(
            f"[LIVE] {side.upper()} {amount_cc:.4f} CC @ "
            f"${price if price else price_now:.4f} | order_id={order['id']}"
        )
        return order
    except ccxt.InsufficientFunds as e:
        logger.error(f"Insufficient funds: {e}")
        raise
    except ccxt.NetworkError as e:
        logger.error(f"Network error: {e}")
        raise
    except Exception as e:
        logger.error(f"Order error: {e}")
        raise