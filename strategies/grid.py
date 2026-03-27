# strategies/grid.py
"""
Grid Trading Bot Strategy with Auto-Rebalancing
-------------------------------------------------
Places buy orders below current price and sell orders above.
When the grid becomes too lopsided (too many buys, too few sells
or vice versa), it automatically recenters the grid around the
current price so you always have active orders on both sides.

Startup modes:
  full (recommended): places both buys and sells at startup.
                      Requires USDT + CC inventory.
  buys_only:          places only buys at startup.
                      Only needs USDT.
"""

from dataclasses import dataclass, field, asdict
from typing import Optional
import numpy as np
from utils.logger import setup_logger

logger = setup_logger("grid_strategy")


@dataclass
class GridOrder:
    level: int
    side: str
    price: float
    usdt: float
    filled: bool = False
    is_initial_sell: bool = False
    order_id: Optional[str] = None
    amount_filled: float = 0.0


@dataclass
class GridState:
    orders: list = field(default_factory=list)
    completed_cycles: int = 0
    total_profit_usdt: float = 0.0
    initialized: bool = False
    rebalance_count: int = 0


class GridStrategy:
    def __init__(
        self,
        lower_price: float,
        upper_price: float,
        num_levels: int,
        order_usdt: float,
        start_mode: str = "full",
        rebalance_threshold: float = 0.75,
        spacing_type: str = "linear",
    ):
        """
        rebalance_threshold: if buy ratio exceeds this (e.g. 0.75 = 75% buys),
                             recentre the grid around current price.
                             Set to 1.0 to disable rebalancing.
        """
        if lower_price >= upper_price:
            raise ValueError("lower_price must be less than upper_price")
        if num_levels < 2:
            raise ValueError("num_levels must be at least 2")

        self.initial_lower = lower_price
        self.initial_upper = upper_price
        self.lower_price = lower_price
        self.upper_price = upper_price
        self.num_levels = num_levels
        self.order_usdt = order_usdt
        self.start_mode = start_mode
        self.rebalance_threshold = rebalance_threshold
        self.spacing_type = spacing_type

        # Grid range width as a ratio — preserved when recentering
        self.range_ratio = (upper_price - lower_price) / lower_price

        self.state = GridState()
        self.levels = self._compute_levels(lower_price, upper_price)
        self.grid_spacing = self.levels[1] - self.levels[0]

        logger.info(
            f"Grid initialized: {num_levels} levels | "
            f"${lower_price:.4f} -> ${upper_price:.4f} | "
            f"spacing ${self.grid_spacing:.4f} | "
            f"${order_usdt:.2f}/order | mode: {start_mode} | "
            f"rebalance threshold: {rebalance_threshold:.0%}"
        )

    def _compute_levels(self, lower: float, upper: float) -> list:
        if self.spacing_type == "geometric":
            return list(np.geomspace(lower, upper, self.num_levels))
        return list(np.linspace(lower, upper, self.num_levels))

    def _needs_rebalance(self) -> tuple:
        """
        Check if the active order ratio is too lopsided.
        Returns (needs_rebalance, buy_count, sell_count).
        """
        active = [o for o in self.state.orders if not o.filled]
        if len(active) < 2:
            return False, 0, 0

        buys  = sum(1 for o in active if o.side == "buy")
        sells = sum(1 for o in active if o.side == "sell")
        total = buys + sells

        buy_ratio  = buys / total
        sell_ratio = sells / total

        too_many_buys  = buy_ratio  >= self.rebalance_threshold
        too_many_sells = sell_ratio >= self.rebalance_threshold

        return (too_many_buys or too_many_sells), buys, sells

    def _recenter_grid(self, current_price: float) -> list:
        """
        Reset the grid centered on current price, preserving the
        original range width. Returns new orders to place.
        """
        half_range = (self.upper_price - self.lower_price) / 2
        new_lower = max(current_price - half_range, 0.0001)
        new_upper = current_price + half_range

        self.lower_price = round(new_lower, 6)
        self.upper_price = round(new_upper, 6)
        self.levels = self._compute_levels(self.lower_price, self.upper_price)
        self.grid_spacing = self.levels[1] - self.levels[0]

        # Cancel all unfilled orders (caller will cancel on exchange)
        cancelled = [o for o in self.state.orders if not o.filled]
        for o in cancelled:
            o.filled = True  # Mark as done so we don't process them again

        self.state.rebalance_count += 1
        logger.info(
            f"Grid rebalanced #{self.state.rebalance_count}: "
            f"new range ${self.lower_price:.4f} – ${self.upper_price:.4f} | "
            f"centered on ${current_price:.4f}"
        )

        # Place fresh orders centered on current price
        new_orders = self.initialize_orders(current_price)
        return new_orders, cancelled

    def initialize_orders(self, current_price: float) -> list:
        """Place initial orders. Returns list of GridOrder objects."""
        s = self.state
        new_orders = []

        for i, level_price in enumerate(self.levels):
            # Skip levels too close to current price
            if abs(level_price - current_price) < self.grid_spacing * 0.1:
                continue

            if level_price < current_price:
                order = GridOrder(
                    level=i,
                    side="buy",
                    price=level_price,
                    usdt=self.order_usdt,
                )
                s.orders.append(order)
                new_orders.append(order)

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
                    new_orders.append(order)

        s.initialized = True

        buy_count  = sum(1 for o in new_orders if o.side == "buy")
        sell_count = sum(1 for o in new_orders if o.side == "sell")
        logger.info(
            f"Orders placed: {buy_count} buys below ${current_price:.4f} | "
            f"{sell_count} sells above"
        )
        return new_orders

    def on_price(self, price: float) -> dict:
        """
        Called every poll cycle with the latest price.
        Returns a dict:
          {
            "new_orders":      [list of GridOrder to place],
            "cancel_orders":   [list of GridOrder to cancel on exchange],
            "rebalanced":      bool,
          }
        """
        s = self.state

        if not s.initialized:
            new_orders = self.initialize_orders(price)
            return {"new_orders": new_orders, "cancel_orders": [], "rebalanced": False}

        # Check if rebalance needed BEFORE processing fills
        needs_rebal, buy_count, sell_count = self._needs_rebalance()
        if needs_rebal:
            logger.warning(
                f"Grid lopsided: {buy_count} buys / {sell_count} sells — rebalancing..."
            )
            new_orders, cancelled = self._recenter_grid(price)
            return {"new_orders": new_orders, "cancel_orders": cancelled, "rebalanced": True}

        # Process fills
        new_orders = []
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
                f"Filled: {order.side.upper()} level {order.level} @ ${order.price:.4f}"
            )

            if order.side == "buy":
                # Buy filled → place sell one level up
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
                    new_orders.append(new_order)
                    logger.debug(
                        f"New SELL: level {next_level} @ ${sell_price:.4f} | "
                        f"expected profit ${expected_profit:.4f}"
                    )

            elif order.side == "sell":
                # Sell filled → place buy one level down + record profit
                prev_level = order.level - 1
                if prev_level >= 0:
                    buy_price = self.levels[prev_level]
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
                    new_orders.append(new_order)
                    logger.info(
                        f"Cycle complete! Profit ${profit:.4f} | "
                        f"total cycles {s.completed_cycles} | "
                        f"total profit ${s.total_profit_usdt:.4f}"
                    )

        return {"new_orders": new_orders, "cancel_orders": [], "rebalanced": False}

    def is_price_in_range(self, price: float) -> bool:
        return self.lower_price <= price <= self.upper_price

    def status_summary(self, price: float) -> dict:
        s = self.state
        active  = [o for o in s.orders if not o.filled]
        a_buys  = sum(1 for o in active if o.side == "buy")
        a_sells = sum(1 for o in active if o.side == "sell")

        # Calculate inventory from filled trades
        # - Buys that filled: we acquired CC, spent USDT
        # - Sells that filled (excluding initial sells): we sold CC, got USDT
        # - Initial sells don't count as they represent initial inventory
        filled_buys  = [o for o in s.orders if o.filled and o.side == "buy"]
        filled_sells = [o for o in s.orders if o.filled and o.side == "sell"
                        and not o.is_initial_sell]
                        
        partial_buys  = [o for o in active if o.side == "buy" and o.amount_filled > 0]
        partial_sells = [o for o in active if o.side == "sell" and o.amount_filled > 0 and not o.is_initial_sell]

        # CC inventory = (bought - sold)
        cc_bought = sum(o.usdt / o.price for o in filled_buys) + sum(o.amount_filled for o in partial_buys)
        cc_sold = sum(o.usdt / o.price for o in filled_sells) + sum(o.amount_filled for o in partial_sells)
        cc_held = cc_bought - cc_sold

        # USDT flows: negative for buys (spent), positive for sells (received)
        usdt_spent = sum(o.usdt for o in filled_buys) + sum(o.amount_filled * o.price for o in partial_buys)
        usdt_received = sum(o.usdt for o in filled_sells) + sum(o.amount_filled * o.price for o in partial_sells)

        # Unrealized P&L = current value of CC held - net USDT spent
        # If we hold CC worth more than we spent (net), that's profit
        unrealized = (cc_held * price) - (usdt_spent - usdt_received)

        return {
            "current_price":     price,
            "in_range":          self.is_price_in_range(price),
            "lower":             self.lower_price,
            "upper":             self.upper_price,
            "active_buys":       a_buys,
            "active_sells":      a_sells,
            "completed_cycles":  s.completed_cycles,
            "total_profit_usdt": s.total_profit_usdt,
            "unrealized_usdt":   unrealized,
            "cc_held":           cc_held,
            "rebalance_count":   s.rebalance_count,
            "start_mode":        self.start_mode,
        }

    def to_dict(self) -> dict:
        """Serialize strategy state to dict for persistence."""
        return {
            "initial_lower": self.initial_lower,
            "initial_upper": self.initial_upper,
            "lower_price": self.lower_price,
            "upper_price": self.upper_price,
            "num_levels": self.num_levels,
            "order_usdt": self.order_usdt,
            "start_mode": self.start_mode,
            "rebalance_threshold": self.rebalance_threshold,
            "spacing_type": self.spacing_type,
            "range_ratio": self.range_ratio,
            "grid_spacing": self.grid_spacing,
            "levels": self.levels,
            "state": {
                "orders": [asdict(o) for o in self.state.orders],
                "completed_cycles": self.state.completed_cycles,
                "total_profit_usdt": self.state.total_profit_usdt,
                "initialized": self.state.initialized,
                "rebalance_count": self.state.rebalance_count,
            }
        }

    @classmethod
    def from_dict(cls, data: dict) -> "GridStrategy":
        """Restore strategy from serialized dict."""
        strategy = cls(
            lower_price=data["initial_lower"],
            upper_price=data["initial_upper"],
            num_levels=data["num_levels"],
            order_usdt=data["order_usdt"],
            start_mode=data["start_mode"],
            rebalance_threshold=data["rebalance_threshold"],
            spacing_type=data.get("spacing_type", "linear"),
        )

        # Restore adjusted grid boundaries
        strategy.lower_price = data["lower_price"]
        strategy.upper_price = data["upper_price"]
        strategy.range_ratio = data["range_ratio"]
        strategy.grid_spacing = data["grid_spacing"]
        strategy.levels = data["levels"]

        # Restore state
        state_data = data["state"]
        strategy.state = GridState(
            orders=[GridOrder(**o) for o in state_data["orders"]],
            completed_cycles=state_data["completed_cycles"],
            total_profit_usdt=state_data["total_profit_usdt"],
            initialized=state_data["initialized"],
            rebalance_count=state_data["rebalance_count"],
        )

        logger.info(
            f"Restored grid state: {state_data['completed_cycles']} cycles | "
            f"${state_data['total_profit_usdt']:.4f} profit | "
            f"{len([o for o in strategy.state.orders if not o.filled])} active orders"
        )
        return strategy