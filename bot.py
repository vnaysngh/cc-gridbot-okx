#!/usr/bin/env python3
# bot.py — The live bot. Run: python3 bot.py

import time
import signal
import sys
from datetime import datetime

from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich import box

import config
from utils.exchange import get_exchange, get_current_price, place_order
from utils.logger import setup_logger
from strategies.dca import DCAStrategy
from strategies.grid import GridStrategy

console = Console()
logger = setup_logger("bot")

running = True

def handle_signal(sig, frame):
    global running
    console.print("\n[yellow]Shutting down bot gracefully...[/yellow]")
    running = False

signal.signal(signal.SIGINT, handle_signal)
signal.signal(signal.SIGTERM, handle_signal)


def print_header():
    mode  = "PAPER TRADING" if config.PAPER_TRADING else "LIVE TRADING"
    color = "yellow" if config.PAPER_TRADING else "red"
    console.print(Panel(
        f"[bold]CC Trading Bot[/bold] | Strategy: [cyan]{config.BOT_MODE.upper()}[/cyan] | "
        f"[{color}]{mode}[/{color}] | "
        f"Exchange: [green]{config.EXCHANGE_ID}[/green] | "
        f"Pair: [green]{config.SYMBOL}[/green]",
        box=box.ROUNDED,
    ))


def print_grid_status(strategy: GridStrategy, price: float):
    summary = strategy.status_summary(price)
    in_range = "[green]YES[/green]" if summary["in_range"] else "[red]NO — bot paused[/red]"

    realized   = summary["total_profit_usdt"]
    unrealized = summary["unrealized_usdt"]
    total      = realized + unrealized
    r_color    = "green" if realized   >= 0 else "red"
    u_color    = "green" if unrealized >= 0 else "red"
    t_color    = "green" if total      >= 0 else "red"

    table = Table(box=box.SIMPLE, show_header=False)
    table.add_row("Current price",     f"${summary['current_price']:.4f}")
    table.add_row("Grid range",        f"${summary['lower']:.4f} – ${summary['upper']:.4f}")
    table.add_row("In range",          in_range)
    table.add_row("Active buys",       str(summary["active_buys"]))
    table.add_row("Active sells",      str(summary["active_sells"]))
    table.add_row("Completed cycles",  str(summary["completed_cycles"]))
    table.add_row("Realized profit",   f"[{r_color}]${realized:.4f}[/{r_color}]")
    table.add_row("Unrealized P&L",    f"[{u_color}]${unrealized:.4f}[/{u_color}]")
    table.add_row("Total P&L",         f"[{t_color}]${total:.4f}[/{t_color}]")
    console.print(table)


def print_dca_status(strategy: DCAStrategy, price: float):
    summary = strategy.status_summary(price)
    if not summary["active"]:
        console.print("[dim]DCA: Waiting to start new cycle...[/dim]")
        return
    color = "green" if summary["profit_pct"] >= 0 else "red"
    table = Table(box=box.SIMPLE, show_header=False)
    table.add_row("Current price",  f"${summary['current_price']:.4f}")
    table.add_row("Avg entry",      f"${summary['avg_entry']:.4f}")
    table.add_row("P&L",            f"[{color}]{summary['profit_pct']:+.2f}%[/{color}]")
    table.add_row("USDT invested",  f"${summary['usdt_invested']:.2f}")
    table.add_row("CC held",        f"{summary['cc_held']:.4f}")
    table.add_row("Safety orders",  f"{summary['safety_orders_used']}/{summary['safety_orders_max']}")
    console.print(table)


def run_grid_bot(exchange, strategy: GridStrategy):
    price = get_current_price(exchange, config.SYMBOL)
    initial_orders = strategy.initialize_orders(price)

    logger.info(f"Placing {len(initial_orders)} initial orders...")
    for order in initial_orders:
        place_order(
            exchange=exchange,
            symbol=config.SYMBOL,
            side=order.side,
            amount_usdt=order.usdt,
            order_type="limit",
            price=order.price,
            paper=config.PAPER_TRADING,
        )

    while running:
        try:
            price = get_current_price(exchange, config.SYMBOL)

            if not strategy.is_price_in_range(price):
                logger.warning(
                    f"Price ${price:.4f} outside grid "
                    f"${config.GRID_LOWER_PRICE:.4f}–${config.GRID_UPPER_PRICE:.4f}. "
                    f"Paused. Adjust grid range in config.py if needed."
                )
                print_grid_status(strategy, price)
                time.sleep(config.POLL_INTERVAL_SECONDS)
                continue

            actions = strategy.on_price(price)
            for act in actions:
                if act["action"] == "place_order":
                    place_order(
                        exchange=exchange,
                        symbol=config.SYMBOL,
                        side=act["side"],
                        amount_usdt=act["usdt"],
                        order_type="limit",
                        price=act["price"],
                        paper=config.PAPER_TRADING,
                    )

            print_grid_status(strategy, price)
            console.print(
                f"[dim]Next check in {config.POLL_INTERVAL_SECONDS}s | "
                f"{datetime.now().strftime('%H:%M:%S')}[/dim]"
            )
            time.sleep(config.POLL_INTERVAL_SECONDS)

        except Exception as e:
            logger.error(f"Error in Grid loop: {e}")
            time.sleep(config.POLL_INTERVAL_SECONDS)


def run_dca_bot(exchange, strategy: DCAStrategy):
    while running:
        try:
            price = get_current_price(exchange, config.SYMBOL)
            action = strategy.on_price(price)

            if action and action["action"] in ("buy", "sell"):
                place_order(
                    exchange=exchange,
                    symbol=config.SYMBOL,
                    side=action["action"],
                    amount_usdt=action["usdt"],
                    order_type="market",
                    paper=config.PAPER_TRADING,
                )

            print_dca_status(strategy, price)
            console.print(
                f"[dim]Next check in {config.POLL_INTERVAL_SECONDS}s | "
                f"{datetime.now().strftime('%H:%M:%S')}[/dim]"
            )
            time.sleep(config.POLL_INTERVAL_SECONDS)

        except Exception as e:
            logger.error(f"Error in DCA loop: {e}")
            time.sleep(config.POLL_INTERVAL_SECONDS)


def main():
    print_header()

    exchange = get_exchange(
        config.EXCHANGE_ID,
        authenticated=not config.PAPER_TRADING,
    )

    if config.BOT_MODE == "grid":
        strategy = GridStrategy(
            lower_price=config.GRID_LOWER_PRICE,
            upper_price=config.GRID_UPPER_PRICE,
            num_levels=config.GRID_NUM_LEVELS,
            order_usdt=config.GRID_ORDER_USDT,
            start_mode=config.GRID_START_MODE,
        )
        console.print(
            f"[bold green]Grid Bot started ({config.GRID_START_MODE} mode).[/bold green] "
            f"Press Ctrl+C to stop."
        )
        run_grid_bot(exchange, strategy)

    elif config.BOT_MODE == "dca":
        strategy = DCAStrategy(
            base_order_usdt=config.DCA_BASE_ORDER_USDT,
            safety_order_usdt=config.DCA_SAFETY_ORDER_USDT,
            safety_drop_pct=config.DCA_SAFETY_DROP_PCT,
            max_safety_orders=config.DCA_MAX_SAFETY_ORDERS,
            take_profit_pct=config.DCA_TAKE_PROFIT_PCT,
            stop_loss_pct=config.DCA_STOP_LOSS_PCT,
        )
        console.print("[bold green]DCA Bot started.[/bold green] Press Ctrl+C to stop.")
        run_dca_bot(exchange, strategy)

    else:
        console.print(f"[red]Unknown BOT_MODE: {config.BOT_MODE}[/red]")
        sys.exit(1)

    console.print("[yellow]Bot stopped.[/yellow]")


if __name__ == "__main__":
    main()