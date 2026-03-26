#!/usr/bin/env python3
# cancel_all_orders.py - Cancel all open orders on OKX

from utils.exchange import get_exchange
import config

def cancel_all_orders():
    print("Connecting to OKX...")
    exchange = get_exchange("okx", authenticated=True)

    print(f"Fetching all open orders for {config.SYMBOL}...")
    orders = exchange.fetch_open_orders(config.SYMBOL)

    if not orders:
        print("\n✅ No open orders found. Your balance is already free.")
        return

    print(f"\n Found {len(orders)} open orders:")
    print("="*80)

    for order in orders:
        print(f"  Order ID: {order['id']}")
        print(f"    Side: {order['side'].upper()}")
        print(f"    Price: ${order['price']:.4f}")
        print(f"    Amount: {order['amount']:.4f} CC")
        print(f"    Status: {order['status']}")
        print()

    response = input(f"\n⚠️  Cancel all {len(orders)} orders? (yes/no): ")

    if response.lower() != 'yes':
        print("Cancelled. No orders were cancelled.")
        return

    print("\nCancelling orders...")
    cancelled = 0
    failed = 0

    for order in orders:
        try:
            exchange.cancel_order(order['id'], config.SYMBOL)
            print(f"  ✅ Cancelled order {order['id']}")
            cancelled += 1
        except Exception as e:
            print(f"  ❌ Failed to cancel {order['id']}: {e}")
            failed += 1

    print("\n" + "="*80)
    print(f"Results: {cancelled} cancelled, {failed} failed")
    print("="*80)

    if cancelled > 0:
        print("\n✅ Orders cancelled! Run check_balance.py to see your freed balance.")
    else:
        print("\n⚠️  No orders were cancelled. Check manually on OKX.")

if __name__ == "__main__":
    try:
        cancel_all_orders()
    except Exception as e:
        print(f"\n❌ Error: {e}")
