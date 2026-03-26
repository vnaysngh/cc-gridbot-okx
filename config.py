# config.py — All your settings live here.
# Edit this file to tune your strategy. You should NOT need to touch any other file.

# ─────────────────────────────────────────────
# EXCHANGE SETTINGS
# ─────────────────────────────────────────────

EXCHANGE_ID = "okx"
SYMBOL = "CC/USDT"
TIMEFRAME = "1h"

# ─────────────────────────────────────────────
# GENERAL BOT SETTINGS
# ─────────────────────────────────────────────

PAPER_TRADING = False            # True = simulate only, no real orders placed
                                # Set to False only when ready to go live

BOT_MODE = "grid"
POLL_INTERVAL_SECONDS = 60

# ─────────────────────────────────────────────
# GRID STRATEGY SETTINGS
# ─────────────────────────────────────────────
#
# GRID RANGE UPDATE STRATEGY:
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# When to update:
#   • URGENT: When price breaks >50% outside your range (bot pauses automatically)
#   • ROUTINE: Once per week on Monday morning (or Sunday evening)
#   • OPTIONAL: After major news/events that shift price levels
#
# How to choose range width:
#   • Volatile periods: ±5-7% (catches most swings, lower profit/trade)
#   • Stable periods:   ±3-5% (higher profit/trade, more risk of breakout)
#   • For CC (volatile): Start with ±5% and adjust based on observation
#
# How to set the range:
#   1. Check current price (run bot in paper mode or check exchange)
#   2. Set GRID_LOWER_PRICE = current_price * 0.95  (5% below)
#   3. Set GRID_UPPER_PRICE = current_price * 1.05  (5% above)
#   4. Update "Last updated" date below
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#
# Last updated: 2026-03-27
# Current price: ~$0.1401
# Lower bound:   $0.1331  (~5.0% below current)
# Upper bound:   $0.1471  (~5.0% above current)
# Levels:        10
# Gap per level: ($0.1471 - $0.1331) / 9 = $0.0156 = ~1.1% per level
# Orders per side: ~5 buys below + ~5 sells above
# Capital used:  5 x $8 = $40 USDT + 5 x $8 = $40 worth of CC
# Profit per cycle: ~1.1% * $8 = $0.088 per completed buy-sell cycle
#
# Setup checklist before going live:
#   1. Verify paper mode shows ~5 buys + ~5 sells at startup
#   2. Add OKX API keys to .env file
#   3. Set PAPER_TRADING = False
#   4. Run: python3 bot.py

GRID_LOWER_PRICE = 0.1331       # 5.0% below $0.1401 — updated 2026-03-27
GRID_UPPER_PRICE = 0.1471       # 5.0% above $0.1401 — updated 2026-03-27
GRID_NUM_LEVELS  = 10           # 10 levels = ~5 buys + ~5 sells
GRID_ORDER_USDT  = 8.0          # $8 per order (uses $40 USDT + $40 worth CC, leaves ~$6 buffer)

GRID_START_MODE = "full"        # "full" = place both buys AND sells at startup
                                # Requires USDT for buys + CC for sells
                                # This is how 3Commas and professional grid bots work

# ─────────────────────────────────────────────
# DCA STRATEGY SETTINGS
# ─────────────────────────────────────────────

DCA_BASE_ORDER_USDT   = 50.0
DCA_SAFETY_ORDER_USDT = 30.0
DCA_SAFETY_DROP_PCT   = 3.0
DCA_MAX_SAFETY_ORDERS = 5
DCA_TAKE_PROFIT_PCT   = 2.5
DCA_STOP_LOSS_PCT     = 15.0

# ─────────────────────────────────────────────
# BACKTESTER SETTINGS
# ─────────────────────────────────────────────

BACKTEST_EXCHANGE        = "kucoin"   # Most CC history available
BACKTEST_DAYS            = 365        # Fetches all available (~136 days for CC)
BACKTEST_INITIAL_CAPITAL = 500
BACKTEST_COMMISSION      = 0.001      # 0.1% KuCoin (OKX is 0.08%, close enough)

DCA_SWEEP = {
    "safety_drop_pct":   [2.0, 3.0, 5.0],
    "take_profit_pct":   [1.5, 2.5, 4.0],
    "max_safety_orders": [3, 5],
}

GRID_SWEEP = {
    "num_levels":       [20, 25, 30],
    "lower_multiplier": [0.85, 0.90, 0.92],
    "upper_multiplier": [1.08, 1.10, 1.15],
}