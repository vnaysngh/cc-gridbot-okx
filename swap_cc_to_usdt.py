#!/usr/bin/env python3
# swap_cc_to_usdt.py - Sell $70 worth of CC to USDT via market order

from utils.exchange import get_exchange, get_current_price

TARGET_USDT = 70.0
SYMBOL = "CC/USDT"

def main():
    exchange = get_exchange("okx", authenticated=True)
    exchange.load_markets()

    price = get_current_price(exchange, SYMBOL)
    cc_amount = TARGET_USDT / price
    cc_amount_str = exchange.amount_to_precision(SYMBOL, cc_amount)
    cc_amount = float(cc_amount_str)

    print(f"Current CC price: ${price:.4f}")
    print(f"Selling {cc_amount} CC (~${cc_amount * price:.2f} USDT)")
    print()

    confirm = input("Confirm market sell? (yes/no): ").strip().lower()
    if confirm != "yes":
        print("Cancelled.")
        return

    order = exchange.create_market_order(SYMBOL, "sell", cc_amount)
    print(f"\n✅ Order placed!")
    print(f"  Order ID: {order['id']}")
    print(f"  Status:   {order.get('status')}")
    print(f"  Filled:   {order.get('filled')} CC")
    print(f"  Cost:     ${order.get('cost', 0):.2f} USDT")

if __name__ == "__main__":
    main()
