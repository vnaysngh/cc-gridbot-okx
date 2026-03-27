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


def load_markets_once(exchange: ccxt.Exchange):
    if not exchange.markets:
        try:
            exchange.load_markets()
            logger.debug(f"Loaded markets for {exchange.id}")
        except Exception as e:
            logger.error(f"Failed to load markets for {exchange.id}: {e}")


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
    load_markets_once(exchange)
    
    price_now = get_current_price(exchange, symbol)
    order_price = price if price else price_now
    amount_cc = amount_usdt / order_price
    
    # Format to exchange precision requirements
    formatted_amount = amount_cc
    formatted_price = order_price
    
    if exchange.markets and symbol in exchange.markets:
        try:
            formatted_amount_str = exchange.amount_to_precision(symbol, amount_cc)
            formatted_amount = float(formatted_amount_str)
            formatted_price_str = exchange.price_to_precision(symbol, order_price)
            formatted_price = float(formatted_price_str)
        except Exception as e:
            logger.warning(f"Failed to convert precision for {symbol}: {e}")

    if paper:
        fake_order = {
            "id": f"PAPER_{side.upper()}_{int(datetime.utcnow().timestamp())}",
            "symbol": symbol,
            "side": side,
            "type": order_type,
            "amount": formatted_amount,
            "price": formatted_price,
            "cost": formatted_amount * formatted_price,
            "status": "closed",
            "paper": True,
        }
        logger.info(
            f"[PAPER] {side.upper()} {formatted_amount} CC @ "
            f"${formatted_price} (${formatted_amount * formatted_price:.2f} USDT)"
        )
        return fake_order

    try:
        if order_type == "market":
            order = exchange.create_market_order(symbol, side, formatted_amount)
        elif order_type == "limit" and price:
            order = exchange.create_limit_order(symbol, side, formatted_amount, formatted_price)
        else:
            raise ValueError(f"Unknown order_type: {order_type}")

        logger.info(
            f"[LIVE] {side.upper()} {formatted_amount} CC @ "
            f"${formatted_price} | order_id={order['id']}"
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


def cancel_order(
    exchange,
    symbol: str,
    order_id: str,
    paper: bool = True,
) -> bool:
    if paper:
        logger.info(f"[PAPER] CANCEL order {order_id}")
        return True
    try:
        exchange.cancel_order(order_id, symbol)
        logger.info(f"[LIVE] Cancelled order {order_id}")
        return True
    except Exception as e:
        logger.warning(f"Could not cancel order {order_id}: {e}")
        return False


def fetch_open_orders(exchange: ccxt.Exchange, symbol: str) -> list:
    """
    Fetch all open orders for a symbol from the exchange.

    Returns list of order dicts with keys: id, side, price, amount, status
    """
    try:
        orders = exchange.fetch_open_orders(symbol)
        logger.debug(f"Fetched {len(orders)} open orders for {symbol}")
        return orders
    except Exception as e:
        logger.error(f"Failed to fetch open orders: {e}")
        return []


def check_order_status(exchange: ccxt.Exchange, symbol: str, order_id: str) -> dict:
    """
    Check the status of a specific order.

    Returns dict with keys: status, filled, remaining, price
    Returns None if order not found or error occurs.
    """
    try:
        order = exchange.fetch_order(order_id, symbol)
        return {
            "status": order.get("status"),
            "filled": float(order.get("filled", 0)),
            "remaining": float(order.get("remaining", 0)),
            "price": float(order.get("price", 0)),
            "amount": float(order.get("amount", 0)),
        }
    except Exception as e:
        logger.warning(f"Failed to fetch order {order_id}: {e}")
        return None


def sync_grid_with_exchange(exchange: ccxt.Exchange, symbol: str, grid_strategy) -> int:
    """
    Sync grid strategy state with actual exchange orders.

    - Fetches open orders from exchange
    - Matches them with internal grid orders by price
    - Updates order_id for matched orders
    - Checks for partial fills
    - Marks unmatched internal orders as filled (likely executed while bot was offline)

    Returns number of orders synced.
    """
    if not grid_strategy.state.initialized:
        logger.debug("Grid not initialized yet, skipping sync")
        return 0

    try:
        exchange_orders = fetch_open_orders(exchange, symbol)

        # Build map of exchange orders by (side, price) and by order_id
        exchange_map_by_price = {}
        exchange_map_by_id = {}

        for eo in exchange_orders:
            key = (eo['side'], round(float(eo['price']), 6))
            exchange_map_by_price[key] = eo
            exchange_map_by_id[eo['id']] = eo

        synced_count = 0
        filled_count = 0
        partial_fill_count = 0

        # Match internal orders with exchange orders
        for order in grid_strategy.state.orders:
            if order.filled:
                continue

            # Try matching by order_id first (most reliable)
            if order.order_id and order.order_id in exchange_map_by_id:
                eo = exchange_map_by_id[order.order_id]

                # Check for partial fills
                last_amount_filled = order.amount_filled
                order.amount_filled = float(eo.get('filled', 0))
                filled_pct = float(eo.get('filled', 0)) / float(eo.get('amount', 1))
                if 0 < filled_pct < 1.0:
                    partial_fill_count += 1
                    if order.amount_filled > last_amount_filled:
                        logger.warning(
                            f"Partial fill detected/updated: {order.side} @ ${order.price:.4f} "
                            f"({filled_pct:.1%} filled) - treating as open"
                        )

                synced_count += 1
                continue

            # Fallback to matching by price
            key = (order.side, round(order.price, 6))

            if key in exchange_map_by_price:
                # Order exists on exchange - update ID
                eo = exchange_map_by_price[key]
                order.order_id = eo['id']
                synced_count += 1
                logger.debug(f"Synced {order.side} @ ${order.price:.4f} -> {eo['id']}")

                # Check for partial fills
                order.amount_filled = float(eo.get('filled', 0))
                filled_pct = float(eo.get('filled', 0)) / float(eo.get('amount', 1))
                if 0 < filled_pct < 1.0:
                    partial_fill_count += 1
                    logger.warning(
                        f"Partial fill detected: {order.side} @ ${order.price:.4f} "
                        f"({filled_pct:.1%} filled) - treating as open"
                    )
            else:
                # Order doesn't exist on exchange - likely filled while offline
                order.filled = True
                filled_count += 1
                logger.info(f"Marked {order.side} @ ${order.price:.4f} as filled (not on exchange)")

        logger.info(
            f"Exchange sync complete: {synced_count} orders synced, "
            f"{filled_count} marked as filled, {partial_fill_count} partial fills, "
            f"{len(exchange_orders)} on exchange"
        )
        return synced_count

    except Exception as e:
        logger.error(f"Failed to sync with exchange: {e}")
        return 0