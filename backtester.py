#!/usr/bin/env python3
# backtester.py — Run this BEFORE running the live bot.
#
# Usage:
#   python backtester.py
#
# What it does:
#   1. Downloads real CC/USDT historical price data (free, no API key needed)
#   2. Simulates your DCA and Grid strategies against that history
#   3. Sweeps all parameter combinations from config.py
#   4. Prints a ranked table showing which settings performed best
#   5. Saves an interactive HTML chart you can open in your browser

import itertools
import warnings
warnings.filterwarnings("ignore")

import numpy as np
import pandas as pd
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.progress import track
from rich import box
from backtesting import Backtest, Strategy
from backtesting.lib import crossover

import config
from utils.exchange import fetch_ohlcv
from utils.logger import setup_logger

console = Console()
logger = setup_logger("backtester")


# ══════════════════════════════════════════════════════════════════════════════
# DCA BACKTEST STRATEGY (backtesting.py wrapper)
# ══════════════════════════════════════════════════════════════════════════════

class DCABacktest(Strategy):
    # These become tunable parameters in the sweep
    safety_drop_pct   = config.DCA_SAFETY_DROP_PCT
    take_profit_pct   = config.DCA_TAKE_PROFIT_PCT
    max_safety_orders = config.DCA_MAX_SAFETY_ORDERS
    base_order_usdt   = config.DCA_BASE_ORDER_USDT
    safety_order_usdt = config.DCA_SAFETY_ORDER_USDT

    def init(self):
        self.last_buy_price = None
        self.safety_count = 0
        self.in_position = False
        self.avg_entry = None
        self.total_spent = 0.0
        self.total_cc = 0.0

    def next(self):
        price = self.data.Close[-1]

        if not self.in_position:
            # Open new cycle with base order
            size = self.base_order_usdt / price
            cost = size * price
            if size > 0 and self.equity >= cost:
                self.buy(size=size)
                self.last_buy_price = price
                self.safety_count = 0
                self.in_position = True
                self.total_spent = size * price
                self.total_cc = size
                self.avg_entry = price
            return

        # Update average entry
        if self.position.size > 0:
            self.avg_entry = (self.position.size * price) / self.position.size

        # Check take profit
        if self.avg_entry and price >= self.avg_entry * (1 + self.take_profit_pct / 100):
            self.position.close()
            self.in_position = False
            self.last_buy_price = None
            self.safety_count = 0
            return

        # Check safety order
        if (self.last_buy_price and
                self.safety_count < self.max_safety_orders and
                price <= self.last_buy_price * (1 - self.safety_drop_pct / 100)):
            size = self.safety_order_usdt / price
            cost = size * price
            if size > 0 and self.equity >= cost:
                self.buy(size=size)
                self.last_buy_price = price
                self.safety_count += 1


# ══════════════════════════════════════════════════════════════════════════════
# GRID BACKTEST (custom simulation — backtesting.py isn't ideal for grid)
# ══════════════════════════════════════════════════════════════════════════════

def simulate_grid(
    df: pd.DataFrame,
    initial_capital: float,
    order_usdt: float,
    num_levels: int,
    lower_multiplier: float,
    upper_multiplier: float,
    commission: float,
) -> dict:
    """
    Pure Python grid simulation over a price DataFrame.
    Returns performance metrics dict.
    """
    first_price = df["Close"].iloc[0]
    lower = first_price * lower_multiplier
    upper = first_price * upper_multiplier

    if lower >= upper:
        return None

    levels = list(np.linspace(lower, upper, num_levels))
    spacing = levels[1] - levels[0]

    capital = initial_capital
    cc_held = 0.0
    completed_cycles = 0
    total_commission = 0.0
    trades = []

    # Initial buy orders below first price
    for lvl in levels:
        if lvl < first_price:
            cost = order_usdt * (1 + commission)
            if capital >= cost:
                amount = order_usdt / lvl
                capital -= cost
                cc_held += amount
                trades.append({"type": "buy", "price": lvl})

    # Track pending sell orders: {level_index: sell_price}
    pending_sells = set()
    for i, lvl in enumerate(levels):
        if lvl > first_price:
            pending_sells.add(i)

    equity_curve = []

    for i, row in df.iterrows():
        price = row["Close"]
        low = row["Low"]
        high = row["High"]

        # Check if any pending buy orders fill (price dropped to level)
        for idx, lvl in enumerate(levels):
            if lvl not in pending_sells and low <= lvl:
                cost = order_usdt * (1 + commission)
                if capital >= cost:
                    amount = order_usdt / lvl
                    capital -= cost
                    cc_held += amount
                    total_commission += order_usdt * commission
                    trades.append({"type": "buy", "price": lvl})
                    # Schedule sell one level up
                    if idx + 1 < num_levels:
                        pending_sells.add(idx + 1)

        # Check if any pending sell orders fill (price rose to level)
        filled_sells = set()
        for idx in list(pending_sells):
            sell_price = levels[idx]
            if high >= sell_price:
                amount = order_usdt / (sell_price - spacing)  # approx cc amount
                if cc_held >= amount:
                    proceeds = amount * sell_price * (1 - commission)
                    capital += proceeds
                    cc_held -= amount
                    total_commission += amount * sell_price * commission
                    completed_cycles += 1
                    trades.append({"type": "sell", "price": sell_price})
                    filled_sells.add(idx)
                    # Schedule buy one level down
                    if idx - 1 >= 0:
                        pass  # Will be picked up next bar

        pending_sells -= filled_sells

        # Mark-to-market equity
        equity_curve.append(capital + cc_held * price)

    final_price = df["Close"].iloc[-1]
    final_equity = capital + cc_held * final_price
    total_return_pct = ((final_equity - initial_capital) / initial_capital) * 100

    # Sharpe ratio (annualised)
    if len(equity_curve) > 1:
        returns = pd.Series(equity_curve).pct_change().dropna()
        sharpe = (returns.mean() / returns.std() * np.sqrt(len(df))) if returns.std() > 0 else 0
    else:
        sharpe = 0

    # Max drawdown
    eq = pd.Series(equity_curve)
    roll_max = eq.cummax()
    drawdown = (eq - roll_max) / roll_max
    max_drawdown = drawdown.min() * 100

    return {
        "strategy": "Grid",
        "num_levels": num_levels,
        "lower_mult": lower_multiplier,
        "upper_mult": upper_multiplier,
        "lower_price": round(lower, 4),
        "upper_price": round(upper, 4),
        "final_equity": round(final_equity, 2),
        "return_pct": round(total_return_pct, 2),
        "completed_cycles": completed_cycles,
        "num_trades": len(trades),
        "max_drawdown_pct": round(max_drawdown, 2),
        "sharpe": round(sharpe, 3),
        "commission_paid": round(total_commission, 2),
    }


# ══════════════════════════════════════════════════════════════════════════════
# PARAMETER SWEEP HELPERS
# ══════════════════════════════════════════════════════════════════════════════

def sweep_dca(df: pd.DataFrame) -> list:
    """Run DCA backtest for all parameter combinations in config.DCA_SWEEP."""
    results = []
    sweep = config.DCA_SWEEP
    combos = list(itertools.product(
        sweep["safety_drop_pct"],
        sweep["take_profit_pct"],
        sweep["max_safety_orders"],
    ))

    console.print(f"\n[cyan]Running DCA sweep: {len(combos)} combinations...[/cyan]")

    for drop, tp, max_so in track(combos, description="DCA sweep"):
        try:
            bt = Backtest(
                df,
                DCABacktest,
                cash=config.BACKTEST_INITIAL_CAPITAL,
                commission=config.BACKTEST_COMMISSION,
                exclusive_orders=True,
            )
            stats = bt.run(
                safety_drop_pct=drop,
                take_profit_pct=tp,
                max_safety_orders=max_so,
            )
            results.append({
                "strategy": "DCA",
                "safety_drop_pct": drop,
                "take_profit_pct": tp,
                "max_safety_orders": max_so,
                "return_pct": round(stats["Return [%]"], 2),
                "max_drawdown_pct": round(stats["Max. Drawdown [%]"], 2),
                "num_trades": stats["# Trades"],
                "win_rate": round(stats["Win Rate [%]"], 1),
                "sharpe": round(stats.get("Sharpe Ratio", 0) or 0, 3),
                "final_equity": round(stats["Equity Final [$]"], 2),
            })
        except Exception as e:
            logger.debug(f"DCA combo ({drop}, {tp}, {max_so}) failed: {e}")

    return results


def sweep_grid(df: pd.DataFrame) -> list:
    """Run Grid simulation for all parameter combinations in config.GRID_SWEEP."""
    results = []
    sweep = config.GRID_SWEEP
    combos = list(itertools.product(
        sweep["num_levels"],
        sweep["lower_multiplier"],
        sweep["upper_multiplier"],
    ))

    console.print(f"\n[cyan]Running Grid sweep: {len(combos)} combinations...[/cyan]")

    for levels, lower_m, upper_m in track(combos, description="Grid sweep"):
        if lower_m >= upper_m:
            continue
        result = simulate_grid(
            df=df,
            initial_capital=config.BACKTEST_INITIAL_CAPITAL,
            order_usdt=config.GRID_ORDER_USDT,
            num_levels=levels,
            lower_multiplier=lower_m,
            upper_multiplier=upper_m,
            commission=config.BACKTEST_COMMISSION,
        )
        if result:
            results.append(result)

    return results


# ══════════════════════════════════════════════════════════════════════════════
# RESULTS DISPLAY
# ══════════════════════════════════════════════════════════════════════════════

def print_results_table(results: list, strategy: str, top_n: int = 10):
    if not results:
        console.print(f"[red]No {strategy} results to show.[/red]")
        return

    # Sort by return_pct descending
    sorted_results = sorted(results, key=lambda x: x["return_pct"], reverse=True)[:top_n]

    title = f"Top {min(top_n, len(sorted_results))} {strategy} Configurations"
    table = Table(title=title, box=box.ROUNDED, show_lines=True)

    if strategy == "DCA":
        table.add_column("Rank", style="dim", width=5)
        table.add_column("Drop %", justify="right")
        table.add_column("TP %", justify="right")
        table.add_column("Max SO", justify="right")
        table.add_column("Return %", justify="right", style="bold")
        table.add_column("Max DD %", justify="right")
        table.add_column("Trades", justify="right")
        table.add_column("Win %", justify="right")
        table.add_column("Sharpe", justify="right")
        table.add_column("Final $", justify="right")

        for i, r in enumerate(sorted_results, 1):
            ret_color = "green" if r["return_pct"] > 0 else "red"
            table.add_row(
                str(i),
                f"{r['safety_drop_pct']}%",
                f"{r['take_profit_pct']}%",
                str(r["max_safety_orders"]),
                f"[{ret_color}]{r['return_pct']:+.2f}%[/{ret_color}]",
                f"{r['max_drawdown_pct']:.2f}%",
                str(r["num_trades"]),
                f"{r['win_rate']:.1f}%",
                f"{r['sharpe']:.3f}",
                f"${r['final_equity']:.2f}",
            )

    elif strategy == "Grid":
        table.add_column("Rank", style="dim", width=5)
        table.add_column("Levels", justify="right")
        table.add_column("Lower", justify="right")
        table.add_column("Upper", justify="right")
        table.add_column("Range $", justify="right")
        table.add_column("Return %", justify="right", style="bold")
        table.add_column("Max DD %", justify="right")
        table.add_column("Cycles", justify="right")
        table.add_column("Sharpe", justify="right")
        table.add_column("Final $", justify="right")

        for i, r in enumerate(sorted_results, 1):
            ret_color = "green" if r["return_pct"] > 0 else "red"
            table.add_row(
                str(i),
                str(r["num_levels"]),
                f"{r['lower_mult']:.2f}x",
                f"{r['upper_mult']:.2f}x",
                f"${r['lower_price']}–${r['upper_price']}",
                f"[{ret_color}]{r['return_pct']:+.2f}%[/{ret_color}]",
                f"{r['max_drawdown_pct']:.2f}%",
                str(r["completed_cycles"]),
                f"{r['sharpe']:.3f}",
                f"${r['final_equity']:.2f}",
            )

    console.print(table)
    console.print()


def print_best_settings(dca_results: list, grid_results: list):
    """Print the single best settings for each strategy to copy into config.py."""
    console.print(Panel("[bold]Best settings to copy into config.py[/bold]", box=box.ROUNDED))

    if dca_results:
        best = max(dca_results, key=lambda x: x["return_pct"])
        console.print("[bold cyan]DCA Strategy:[/bold cyan]")
        console.print(f"  DCA_SAFETY_DROP_PCT    = {best['safety_drop_pct']}")
        console.print(f"  DCA_TAKE_PROFIT_PCT    = {best['take_profit_pct']}")
        console.print(f"  DCA_MAX_SAFETY_ORDERS  = {best['max_safety_orders']}")
        console.print(f"  → Backtest return: [green]{best['return_pct']:+.2f}%[/green] | "
                      f"Max drawdown: {best['max_drawdown_pct']:.2f}% | "
                      f"Sharpe: {best['sharpe']:.3f}")
        console.print()

    if grid_results:
        best = max(grid_results, key=lambda x: x["return_pct"])
        console.print("[bold cyan]Grid Strategy:[/bold cyan]")
        console.print(f"  GRID_LOWER_RANGE_PCT   = {round((1 - best['lower_mult']) * 100, 2)}  "
                      f"[dim](= {best['lower_mult']:.2f}x of entry price)[/dim]")
        console.print(f"  GRID_UPPER_RANGE_PCT   = {round((best['upper_mult'] - 1) * 100, 2)}  "
                      f"[dim](= {best['upper_mult']:.2f}x of entry price)[/dim]")
        console.print(f"  GRID_NUM_LEVELS        = {best['num_levels']}")
        console.print(f"  → Backtest return: [green]{best['return_pct']:+.2f}%[/green] | "
                      f"Max drawdown: {best['max_drawdown_pct']:.2f}% | "
                      f"Cycles: {best['completed_cycles']}")
        console.print()

    console.print("[yellow]⚠ Reminder: past performance does not guarantee future results.[/yellow]")
    console.print("[yellow]  Always start with small amounts and paper trading first.[/yellow]")


def save_dca_chart(df: pd.DataFrame, best_params: dict):
    """Save an interactive HTML chart for the best DCA configuration."""
    try:
        bt = Backtest(
            df,
            DCABacktest,
            cash=config.BACKTEST_INITIAL_CAPITAL,
            commission=config.BACKTEST_COMMISSION,
            exclusive_orders=True,
        )
        bt.run(**best_params)
        bt.plot(filename="backtest_dca_chart.html", open_browser=False)
        console.print("[green]DCA chart saved: backtest_dca_chart.html[/green]")
    except Exception as e:
        logger.debug(f"Could not save DCA chart: {e}")


# ══════════════════════════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════════════════════════

def main():
    console.print(Panel(
        f"[bold]CC Bot Backtester[/bold] | "
        f"{config.EXCHANGE_ID} | {config.SYMBOL} | "
        f"{config.BACKTEST_DAYS} days | "
        f"Capital: ${config.BACKTEST_INITIAL_CAPITAL}",
        box=box.ROUNDED,
    ))

    # 1. Fetch historical data
    df = fetch_ohlcv(
        exchange_id=config.EXCHANGE_ID,
        symbol=config.SYMBOL,
        timeframe=config.TIMEFRAME,
        days=config.BACKTEST_DAYS,
    )

    if df.empty:
        console.print("[red]No data fetched. Check your exchange and symbol settings.[/red]")
        return

    console.print(
        f"\nPrice range in dataset: "
        f"[cyan]${df['Low'].min():.4f}[/cyan] – "
        f"[cyan]${df['High'].max():.4f}[/cyan] | "
        f"Current: [bold]${df['Close'].iloc[-1]:.4f}[/bold]\n"
    )

    # 2. Run sweeps
    dca_results = sweep_dca(df)
    grid_results = sweep_grid(df)

    # 3. Print result tables
    print_results_table(dca_results, "DCA", top_n=10)
    print_results_table(grid_results, "Grid", top_n=10)

    # 4. Print the winner settings
    print_best_settings(dca_results, grid_results)

    # 5. Save interactive chart for best DCA config
    if dca_results:
        best_dca = max(dca_results, key=lambda x: x["return_pct"])
        save_dca_chart(df, {
            "safety_drop_pct":   best_dca["safety_drop_pct"],
            "take_profit_pct":   best_dca["take_profit_pct"],
            "max_safety_orders": best_dca["max_safety_orders"],
        })


if __name__ == "__main__":
    main()