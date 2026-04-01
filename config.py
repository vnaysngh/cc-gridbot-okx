# config.py — All your settings live here.
# Edit this file to tune your strategy. You should NOT need to touch any other file.
import os

# ─────────────────────────────────────────────
# EXCHANGE SETTINGS
# ─────────────────────────────────────────────

EXCHANGE_ID = "okx"
SYMBOL = "CC/USDT"
TIMEFRAME = "1h"

# ─────────────────────────────────────────────
# GENERAL BOT SETTINGS
# ─────────────────────────────────────────────

PAPER_TRADING = os.environ.get("PAPER_TRADING", "True").lower() == "true"
                                # True = simulate only, no real orders placed
                                # Set to False only when ready to go live

BOT_MODE = "grid"
POLL_INTERVAL_SECONDS = 60

# ─────────────────────────────────────────────
# GRID STRATEGY SETTINGS
# ─────────────────────────────────────────────
#
# 10-level grid centered on current price
#
# Current price: ~$0.1424 (checked 2026-03-27)
# Lower bound:   $0.1360  (~4.5% below current)
# Upper bound:   $0.1488  (~4.5% above current)
# Levels:        10
# Gap per level: ($0.1488 - $0.1360) / 9 = $0.0014 = ~1.0%
# Orders per side: ~5 buys below + ~4 sells above
# Capital used:  5 x $25 = $125 USDT + 4 x $25 = $100 worth of CC
# Total capital needed: ~$125 USDT + ~$100 worth of CC for full grid
#
# Setup checklist before going live:
#   1. Verify paper mode shows ~4 buys + ~4 sells at startup
#   2. Add OKX API keys to .env file
#   3. Set PAPER_TRADING = False
#   4. Run: python3 bot.py

GRID_LOWER_RANGE_PCT = 4.5      # % below current price to place lowest grid buy
GRID_UPPER_RANGE_PCT = 4.5      # % above current price to place highest grid sell
GRID_NUM_LEVELS  = 10           # 10 levels = ~4 buys + ~4 sells
GRID_ORDER_USDT  = 50.0         # $50 per order (~$200 each side)
GRID_SPACING_TYPE = "linear"    # "linear" or "geometric" (constant profit % per grid step)

GRID_START_MODE = "full"        # "full" = place both buys AND sells at startup
                                # Requires USDT for buys + CC for sells
                                # This is how 3Commas and professional grid bots work

GRID_REBALANCE_THRESHOLD = 0.75  # Rebalance when 75%+ orders are on one side
                                  # e.g. 8 buys + 2 sells triggers rebalance
                                  # Set to 1.0 to disable rebalancing

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