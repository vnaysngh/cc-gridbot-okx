#!/usr/bin/env python3
# cancel_all_auto.py - Auto-cancel all open orders (no prompt)

from utils.exchange import get_exchange
import config

exchange = get_exchange("okx", authenticated=True)
print(f"Fetching open orders for {config.SYMBOL}...")

orders = exchange.fetch_open_orders(config.SYMBOL)

if not orders:
    print("✅ No open orders found.")
else:
    print(f"Found {len(orders)} orders. Cancelling...")
    for order in orders:
        try:
            exchange.cancel_order(order['id'], config.SYMBOL)
            print(f"  ✅ Cancelled {order['side']} @ ${order['price']:.4f}")
        except Exception as e:
            print(f"  ❌ Failed: {e}")

print("\n✅ Done! Run check_balance.py to verify.")
