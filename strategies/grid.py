# strategies/grid.py
"""
Grid Trading Bot Strategy
--------------------------
Two startup modes:

  full (default, recommended for live trading):
    - Places buy orders below current price AND sell orders above it at startup
    - Requires USDT for buys + CC inventory for sells
    - Active on both sides immediately — captures moves up AND down
    - This is how 3Commas and all professional grid bots work

  buys_only:
    - Places ONLY buy orders below current price at startup
    - No CC needed upfront — starts with USDT only
    - Only makes money if price drops first, then bounces back up
    - Not recommended for live trading
"""

from dataclasses import dataclass, field
from typing import Optional
import numpy as np
from utils.logger import setup_logger

logger = setup_logger("grid_strategy")


@dataclass
class GridOrder:
    level: int
    side: str           # "buy" or "sell"
    price: float
    usdt: float
    filled: bool = False
    is_initial_sell: bool = False   # True = placed at startup, not from a buy fill
    order_id: Optional[str] = None


@dataclass
class GridState:
    orders: list = field(default_factory=list)
    completed_cycles: int = 0
    total_profit_usdt: float = 0.0
    initialized: bool = False


class GridStrategy:
    def __init__(
        self,
        lower_price: float,
        upper_price: float,
        num_levels: int,
        order_usdt: float,
        start_mode: str = "full",
    ):
        if lower_price >= upper_price:
            raise ValueError("lower_price must be less than upper_price")
        if num_levels < 2:
            raise ValueError("num_levels must be at least 2")
        if start_mode not in ("buys_only", "full"):
            raise ValueError("start_mode must be 'buys_only' or 'full'")

        self.lower_price = lower_price
        self.upper_price = upper_price
        self.num_levels = num_levels
        self.order_usdt = order_usdt
        self.start_mode = start_mode
        self.state = GridState()

        self.levels = list(np.linspace(lower_price, upper_price, num_levels))
        self.grid_spacing = self.levels[1] - self.levels[0]

        buy_levels  = sum(1 for l in self.levels if l < (lower_price + upper_price) / 2)
        sell_levels = num_levels - buy_levels
        usdt_needed = buy_levels * order_usdt
        cc_needed_usdt = sell_levels * order_usdt

        logger.info(
            f"Grid initialized: {num_levels} levels | "
            f"${lower_price:.4f} -> ${upper_price:.4f} | "
            f"spacing ${self.grid_spacing:.4f} | "
            f"${order_usdt:.2f} per order | "
            f"mode: {start_mode}"
        )
        if start_mode == "full":
            logger.info(
                f"Capital needed: ~${usdt_needed:.0f} USDT + "
                f"~${cc_needed_usdt:.0f} worth of CC "
                f"(~{cc_needed_usdt / ((lower_price + upper_price) / 2):.0f} CC tokens)"
            )
        else:
            logger.info(f"Capital needed: ~${usdt_needed:.0f} USDT only")

    def initialize_orders(self, current_price: float) -> list:
        """
        Called once at startup. Returns list of orders to place.

        full mode:
          - Buy orders at every level BELOW current price
          - Sell orders at every level ABOVE current price
          - Active immediately on both sides

        buys_only mode:
          - Buy orders only below current price
          - Sells placed automatically as buys fill
        """
        s = self.state
        s.orders = []

        for i, level_price in enumerate(self.levels):
            if abs(level_price - current_price) < self.grid_spacing * 0.1:
                # Skip levels too close to current price — exchange would reject
                continue

            if level_price < current_price:
                order = GridOrder(
                    level=i,
                    side="buy",
                    price=level_price,
                    usdt=self.order_usdt,
                )
                s.orders.append(order)

            elif level_price > current_price:
                if self.start_mode == "full":
                    order = GridOrder(
                        level=i,
                        side="sell",
                        price=level_price,
                        usdt=self.order_usdt,
                        is_initial_sell=True,
                    )
                    s.orders.append(order)
                # buys_only: skip sells at startup

        s.initialized = True

        buy_count  = sum(1 for o in s.orders if o.side == "buy")
        sell_count = sum(1 for o in s.orders if o.side == "sell")

        if self.start_mode == "full":
            logger.info(
                f"Startup: {buy_count} buys below ${current_price:.4f} | "
                f"{sell_count} sells above | "
                f"USDT needed: ~${buy_count * self.order_usdt:.0f} | "
                f"CC needed: ~${sell_count * self.order_usdt:.0f} worth"
            )
        else:
            logger.info(
                f"Startup (buys_only): {buy_count} buys below ${current_price:.4f} | "
                f"sells will appear as buys fill"
            )

        return s.orders

    def on_price(self, price: float) -> list:
        """
        Called every poll cycle with the latest price.
        Returns list of new orders to place.
        """
        s = self.state

        if not s.initialized:
            return self.initialize_orders(price)

        actions = []

        for order in s.orders:
            if order.filled:
                continue

            filled = False
            if order.side == "buy"  and price <= order.price:
                filled = True
            elif order.side == "sell" and price >= order.price:
                filled = True

            if not filled:
                continue

            order.filled = True
            logger.info(
                f"Grid order filled: {order.side.upper()} "
                f"level {order.level} @ ${order.price:.4f}"
            )

            if order.side == "buy":
                # Buy filled -> place sell one level up
                next_level = order.level + 1
                if next_level < len(self.levels):
                    sell_price = self.levels[next_level]
                    expected_profit = (sell_price - order.price) / order.price * self.order_usdt

                    new_order = GridOrder(
                        level=next_level,
                        side="sell",
                        price=sell_price,
                        usdt=self.order_usdt,
                        is_initial_sell=False,
                    )
                    s.orders.append(new_order)
                    actions.append({
                        "action": "place_order",
                        "side": "sell",
                        "price": sell_price,
                        "usdt": self.order_usdt,
                        "level": next_level,
                        "expected_profit": expected_profit,
                    })
                    logger.debug(
                        f"New SELL: level {next_level} @ ${sell_price:.4f} | "
                        f"expected profit ${expected_profit:.4f}"
                    )

            elif order.side == "sell":
                # Sell filled -> place buy one level down + record profit
                prev_level = order.level - 1
                if prev_level >= 0:
                    buy_price = self.levels[prev_level]

                    if order.is_initial_sell:
                        # Initial sell: profit = spread between this sell and the level below
                        # (we "bought" CC at market before bot started, treat as bought one level down)
                        profit = (order.price - buy_price) / buy_price * self.order_usdt
                    else:
                        # Normal sell: profit = spread between this sell and its paired buy
                        profit = (order.price - buy_price) / buy_price * self.order_usdt

                    s.completed_cycles += 1
                    s.total_profit_usdt += profit

                    new_order = GridOrder(
                        level=prev_level,
                        side="buy",
                        price=buy_price,
                        usdt=self.order_usdt,
                    )
                    s.orders.append(new_order)
                    actions.append({
                        "action": "place_order",
                        "side": "buy",
                        "price": buy_price,
                        "usdt": self.order_usdt,
                        "level": prev_level,
                        "realized_profit": profit,
                    })
                    logger.info(
                        f"Cycle complete! Profit ${profit:.4f} | "
                        f"total cycles {s.completed_cycles} | "
                        f"total profit ${s.total_profit_usdt:.4f}"
                    )

        return actions

    def is_price_in_range(self, price: float) -> bool:
        return self.lower_price <= price <= self.upper_price

    def status_summary(self, price: float) -> dict:
        s = self.state
        active_orders = [o for o in s.orders if not o.filled]
        active_buys   = sum(1 for o in active_orders if o.side == "buy")
        active_sells  = sum(1 for o in active_orders if o.side == "sell")

        # Estimate unrealized P&L
        # CC held = sum of all filled buys that haven't been sold yet
        filled_buys  = [o for o in s.orders if o.filled and o.side == "buy"]
        filled_sells = [o for o in s.orders if o.filled and o.side == "sell"]
        cc_held = sum(o.usdt / o.price for o in filled_buys) - \
                  sum(o.usdt / o.price for o in filled_sells if not o.is_initial_sell)
        unrealized = cc_held * price - sum(o.usdt for o in filled_buys) + \
                     sum(o.usdt for o in filled_sells if not o.is_initial_sell)

        return {
            "current_price":      price,
            "in_range":           self.is_price_in_range(price),
            "lower":              self.lower_price,
            "upper":              self.upper_price,
            "active_buys":        active_buys,
            "active_sells":       active_sells,
            "completed_cycles":   s.completed_cycles,
            "total_profit_usdt":  s.total_profit_usdt,
            "unrealized_usdt":    unrealized,
            "start_mode":         self.start_mode,
        }