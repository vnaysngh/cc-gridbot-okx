# strategies/dca.py
"""
DCA (Dollar Cost Averaging) Bot Strategy
-----------------------------------------
Logic:
  1. Place a base buy at startup
  2. If price drops safety_drop_pct% from the last buy → buy again (safety order)
  3. Repeat up to max_safety_orders times
  4. When average entry price is profitable by take_profit_pct% → sell all
  5. If price falls stop_loss_pct% below average entry → sell all and reset
  6. After a full sell cycle → restart from step 1
"""

from dataclasses import dataclass, field
from typing import Optional
from utils.logger import setup_logger

logger = setup_logger("dca_strategy")


@dataclass
class DCAState:
    """Holds the current state of one DCA cycle."""
    active: bool = False
    fills: list = field(default_factory=list)   # list of {"price": float, "usdt": float}
    safety_orders_placed: int = 0

    @property
    def total_usdt_spent(self) -> float:
        return sum(f["usdt"] for f in self.fills)

    @property
    def total_cc_held(self) -> float:
        return sum(f["usdt"] / f["price"] for f in self.fills)

    @property
    def average_entry(self) -> Optional[float]:
        if not self.fills or self.total_cc_held == 0:
            return None
        return self.total_usdt_spent / self.total_cc_held

    @property
    def last_buy_price(self) -> Optional[float]:
        return self.fills[-1]["price"] if self.fills else None

    def reset(self):
        self.active = False
        self.fills = []
        self.safety_orders_placed = 0


class DCAStrategy:
    def __init__(
        self,
        base_order_usdt: float,
        safety_order_usdt: float,
        safety_drop_pct: float,
        max_safety_orders: int,
        take_profit_pct: float,
        stop_loss_pct: float,
    ):
        self.base_order_usdt = base_order_usdt
        self.safety_order_usdt = safety_order_usdt
        self.safety_drop_pct = safety_drop_pct
        self.max_safety_orders = max_safety_orders
        self.take_profit_pct = take_profit_pct
        self.stop_loss_pct = stop_loss_pct
        self.state = DCAState()

    def on_price(self, price: float) -> Optional[dict]:
        """
        Called every poll cycle with the latest price.
        Returns an action dict or None.

        Action dict: {"action": "buy"|"sell"|"none", "usdt": float, "reason": str}
        """
        s = self.state

        # ── Not in a cycle yet → open with base order ──────────────────────
        if not s.active:
            logger.info(f"Starting new DCA cycle. Base buy @ ${price:.4f}")
            s.active = True
            s.fills.append({"price": price, "usdt": self.base_order_usdt})
            return {
                "action": "buy",
                "usdt": self.base_order_usdt,
                "reason": "base_order",
                "price": price,
            }

        avg = s.average_entry
        last_buy = s.last_buy_price

        # ── Check take profit ───────────────────────────────────────────────
        profit_pct = ((price - avg) / avg) * 100
        if profit_pct >= self.take_profit_pct:
            logger.info(
                f"Take profit hit: {profit_pct:.2f}% profit | "
                f"avg entry ${avg:.4f} | current ${price:.4f}"
            )
            usdt_value = s.total_cc_held * price
            s.reset()
            return {
                "action": "sell",
                "usdt": usdt_value,
                "reason": "take_profit",
                "price": price,
                "profit_pct": profit_pct,
            }

        # ── Check stop loss ─────────────────────────────────────────────────
        if self.stop_loss_pct > 0:
            loss_pct = ((avg - price) / avg) * 100
            if loss_pct >= self.stop_loss_pct:
                logger.warning(
                    f"Stop loss triggered: {loss_pct:.2f}% loss | "
                    f"avg entry ${avg:.4f} | current ${price:.4f}"
                )
                usdt_value = s.total_cc_held * price
                s.reset()
                return {
                    "action": "sell",
                    "usdt": usdt_value,
                    "reason": "stop_loss",
                    "price": price,
                    "loss_pct": loss_pct,
                }

        # ── Check safety order ──────────────────────────────────────────────
        if s.safety_orders_placed < self.max_safety_orders:
            drop_from_last = ((last_buy - price) / last_buy) * 100
            if drop_from_last >= self.safety_drop_pct:
                s.safety_orders_placed += 1
                s.fills.append({"price": price, "usdt": self.safety_order_usdt})
                logger.info(
                    f"Safety order #{s.safety_orders_placed} | "
                    f"dropped {drop_from_last:.2f}% from last buy | "
                    f"new avg entry ${s.average_entry:.4f}"
                )
                return {
                    "action": "buy",
                    "usdt": self.safety_order_usdt,
                    "reason": f"safety_order_{s.safety_orders_placed}",
                    "price": price,
                }

        # ── Nothing to do ───────────────────────────────────────────────────
        logger.debug(
            f"Price ${price:.4f} | avg entry ${avg:.4f} | "
            f"P&L {profit_pct:+.2f}% | "
            f"safety orders used {s.safety_orders_placed}/{self.max_safety_orders}"
        )
        return {"action": "none", "price": price}

    def status_summary(self, price: float) -> dict:
        """Return a dict summarising current cycle state for display."""
        s = self.state
        if not s.active or not s.average_entry:
            return {"active": False}
        profit_pct = ((price - s.average_entry) / s.average_entry) * 100
        return {
            "active": True,
            "current_price": price,
            "avg_entry": s.average_entry,
            "profit_pct": profit_pct,
            "usdt_invested": s.total_usdt_spent,
            "cc_held": s.total_cc_held,
            "safety_orders_used": s.safety_orders_placed,
            "safety_orders_max": self.max_safety_orders,
        }