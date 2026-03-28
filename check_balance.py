#!/usr/bin/env python3
# check_balance.py - Check OKX account balances

from utils.exchange import get_exchange
import config

def check_balances():
    print("Connecting to OKX...")
    exchange = get_exchange("okx", authenticated=True)

    print("\nFetching balances...")
    balance = exchange.fetch_balance()

    # Get free (available) balances
    usdt_free = balance['free'].get('USDT', 0)
    usdt_total = balance['total'].get('USDT', 0)

    cc_free = balance['free'].get('CC', 0)
    cc_total = balance['total'].get('CC', 0)

    print("\n" + "="*60)
    print("OKX ACCOUNT BALANCES")
    print("="*60)
    print(f"\nUSDT:")
    print(f"  Available: ${usdt_free:.2f}")
    print(f"  Total:     ${usdt_total:.2f}")

    print(f"\nCC:")
    print(f"  Available: {cc_free:.4f} CC")
    print(f"  Total:     {cc_total:.4f} CC")

    # Get current CC price
    from utils.exchange import get_current_price
    cc_price = get_current_price(exchange, "CC/USDT")
    cc_value_usdt = cc_free * cc_price

    print(f"\nCC Value:")
    print(f"  Current CC price: ${cc_price:.4f}")
    print(f"  CC holdings worth: ${cc_value_usdt:.2f} USDT")

    print("\n" + "="*60)
    print("GRID BOT REQUIREMENTS")
    print("="*60)

    # Calculate requirements from config
    from strategies.grid import GridStrategy
    lower_price = cc_price * (1 - config.GRID_LOWER_RANGE_PCT / 100)
    upper_price = cc_price * (1 + config.GRID_UPPER_RANGE_PCT / 100)
    
    strategy = GridStrategy(
        lower_price=lower_price,
        upper_price=upper_price,
        num_levels=config.GRID_NUM_LEVELS,
        order_usdt=config.GRID_ORDER_USDT,
        start_mode=config.GRID_START_MODE,
    )

    # Estimate requirements
    buy_levels = sum(1 for l in strategy.levels if l < cc_price)
    sell_levels = config.GRID_NUM_LEVELS - buy_levels

    usdt_needed = buy_levels * config.GRID_ORDER_USDT
    cc_needed_usdt = sell_levels * config.GRID_ORDER_USDT
    cc_needed_tokens = cc_needed_usdt / cc_price

    print(f"\nFor {config.GRID_START_MODE} mode grid bot:")
    print(f"  Buy orders needed:  {buy_levels}")
    print(f"  Sell orders needed: {sell_levels}")
    print(f"\n  USDT needed:  ${usdt_needed:.2f}")
    print(f"  CC needed:    {cc_needed_tokens:.2f} tokens (${cc_needed_usdt:.2f} worth)")

    print("\n" + "="*60)
    print("STATUS CHECK")
    print("="*60)

    usdt_ok = usdt_free >= usdt_needed
    cc_ok = cc_free >= cc_needed_tokens

    print(f"\n  USDT: {'✅ SUFFICIENT' if usdt_ok else '❌ INSUFFICIENT'}")
    print(f"    Have: ${usdt_free:.2f}")
    print(f"    Need: ${usdt_needed:.2f}")
    if not usdt_ok:
        print(f"    Missing: ${usdt_needed - usdt_free:.2f}")

    print(f"\n  CC: {'✅ SUFFICIENT' if cc_ok else '❌ INSUFFICIENT'}")
    print(f"    Have: {cc_free:.2f} CC")
    print(f"    Need: {cc_needed_tokens:.2f} CC")
    if not cc_ok:
        print(f"    Missing: {cc_needed_tokens - cc_free:.2f} CC (${(cc_needed_tokens - cc_free) * cc_price:.2f} worth)")

    print("\n" + "="*60)

    if usdt_ok and cc_ok:
        print("✅ You have sufficient balance to run the grid bot!")
    else:
        print("❌ INSUFFICIENT BALANCE - Cannot start grid bot")
        print("\nOptions:")
        if not usdt_ok:
            print(f"  1. Deposit ${usdt_needed - usdt_free:.2f} more USDT to OKX")
        if not cc_ok:
            print(f"  2. Deposit {cc_needed_tokens - cc_free:.2f} more CC tokens to OKX")
        print(f"  3. Change to 'buys_only' mode (only needs ${usdt_needed:.2f} USDT)")
        print(f"  4. Reduce GRID_ORDER_USDT in config.py (currently ${config.GRID_ORDER_USDT})")

    print("="*60 + "\n")

if __name__ == "__main__":
    try:
        check_balances()
    except Exception as e:
        print(f"\n❌ Error: {e}")
        print("\nMake sure:")
        print("  1. OKX API keys are set in .env file")
        print("  2. API key has 'Trade' permission enabled")
        print("  3. You're connected to the internet")
