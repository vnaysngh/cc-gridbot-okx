#!/usr/bin/env python3
# bot.py — Run: python3 bot.py

import time
import signal
import sys
from datetime import datetime

from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich import box

import config
from utils.exchange import (
    get_exchange, get_current_price, place_order, cancel_order,
    sync_grid_with_exchange
)
from utils.logger import setup_logger
from utils.state_manager import save_grid_state, load_grid_state
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
    in_range = "[green]YES[/green]" if summary["in_range"] else "[red]NO — rebalance pending[/red]"

    realized   = summary["total_profit_usdt"]
    unrealized = summary["unrealized_usdt"]
    total      = realized + unrealized
    r_color = "green" if realized   >= 0 else "red"
    u_color = "green" if unrealized >= 0 else "red"
    t_color = "green" if total      >= 0 else "red"

    table = Table(box=box.SIMPLE, show_header=False)
    table.add_row("Current price",    f"${summary['current_price']:.4f}")
    table.add_row("Grid range",       f"${summary['lower']:.4f} – ${summary['upper']:.4f}")
    table.add_row("In range",         in_range)
    table.add_row("Active buys",      str(summary["active_buys"]))
    table.add_row("Active sells",     str(summary["active_sells"]))
    table.add_row("Completed cycles", str(summary["completed_cycles"]))
    table.add_row("Rebalances",       str(summary["rebalance_count"]))
    table.add_row("Realized profit",  f"[{r_color}]${realized:.4f}[/{r_color}]")
    table.add_row("Unrealized P&L",   f"[{u_color}]${unrealized:.4f}[/{u_color}]")
    table.add_row("Total P&L",        f"[{t_color}]${total:.4f}[/{t_color}]")
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
    # Initialize grid only if not already initialized (from loaded state)
    price = get_current_price(exchange, config.SYMBOL)

    if not strategy.state.initialized:
        initial_orders = strategy.initialize_orders(price)
        logger.info(f"Placing {len(initial_orders)} initial orders...")
        for order in initial_orders:
            try:
                order_response = place_order(
                    exchange=exchange,
                    symbol=config.SYMBOL,
                    side=order.side,
                    amount_usdt=order.usdt,
                    order_type="limit",
                    price=order.price,
                    paper=config.PAPER_TRADING,
                )
                if order_response and order_response.get("id"):
                    order.order_id = order_response["id"]
            except Exception as e:
                logger.error(f"Failed to place initial {order.side} order at ${order.price:.4f}: {e}")
    else:
        logger.info("Grid already initialized from saved state")
        # Sync with exchange to update order IDs and detect fills
        if not config.PAPER_TRADING:
            sync_grid_with_exchange(exchange, config.SYMBOL, strategy)

        # If sync wiped all active orders (e.g. stale state from old grid),
        # reset and reinitialize a fresh grid
        active = [o for o in strategy.state.orders if not o.filled]
        if not active:
            logger.info("No active orders after sync — reinitializing fresh grid")
            strategy.state.initialized = False
            strategy.state.orders = []
            initial_orders = strategy.initialize_orders(price)
            logger.info(f"Placing {len(initial_orders)} initial orders...")
            for order in initial_orders:
                try:
                    order_response = place_order(
                        exchange=exchange,
                        symbol=config.SYMBOL,
                        side=order.side,
                        amount_usdt=order.usdt,
                        order_type="limit",
                        price=order.price,
                        paper=config.PAPER_TRADING,
                    )
                    if order_response and order_response.get("id"):
                        order.order_id = order_response["id"]
                except Exception as e:
                    logger.error(f"Failed to place initial {order.side} order at ${order.price:.4f}: {e}")

    # Save state after initialization
    save_grid_state(strategy.to_dict(), config.EXCHANGE_ID, config.SYMBOL)

    while running:
        try:
            price = get_current_price(exchange, config.SYMBOL)
            result = strategy.on_price(price)

            # Handle rebalance — cancel old orders, place new ones
            if result["rebalanced"]:
                cancel_count = sum(1 for o in result['cancel_orders'] if o.order_id)
                console.print(
                    f"[yellow]Grid rebalanced — cancelling {cancel_count} old orders and "
                    f"placing {len(result['new_orders'])} new orders[/yellow]"
                )

                # Step 1: Cancel all old orders
                cancelled_successfully = 0
                for order in result["cancel_orders"]:
                    if order.order_id:
                        success = cancel_order(
                            exchange=exchange,
                            symbol=config.SYMBOL,
                            order_id=order.order_id,
                            paper=config.PAPER_TRADING,
                        )
                        if success:
                            cancelled_successfully += 1

                if not config.PAPER_TRADING:
                    if cancelled_successfully < cancel_count:
                        logger.warning(
                            f"Only cancelled {cancelled_successfully}/{cancel_count} orders during rebalance"
                        )
                    else:
                        logger.info(f"Successfully cancelled all {cancel_count} orders")

                # Step 2: Place new orders
                placed_successfully = 0
                for order in result["new_orders"]:
                    try:
                        order_response = place_order(
                            exchange=exchange,
                            symbol=config.SYMBOL,
                            side=order.side,
                            amount_usdt=order.usdt,
                            order_type="limit",
                            price=order.price,
                            paper=config.PAPER_TRADING,
                        )
                        if order_response and order_response.get("id"):
                            order.order_id = order_response["id"]
                            placed_successfully += 1
                    except Exception as e:
                        logger.error(f"Failed to place {order.side} order at ${order.price:.4f}: {e}")

                # Step 3: Verify rebalance success
                if not config.PAPER_TRADING:
                    if placed_successfully < len(result["new_orders"]):
                        logger.error(
                            f"Rebalance incomplete: only placed {placed_successfully}/{len(result['new_orders'])} new orders"
                        )
                        console.print(
                            f"[red]⚠ Rebalance partially failed - check logs[/red]"
                        )
                    else:
                        console.print(
                            f"[green]✓ Rebalance successful: {cancelled_successfully} cancelled, "
                            f"{placed_successfully} placed[/green]"
                        )

            # Place any new orders from normal grid operation
            elif result["new_orders"]:
                for order in result["new_orders"]:
                    try:
                        order_response = place_order(
                            exchange=exchange,
                            symbol=config.SYMBOL,
                            side=order.side,
                            amount_usdt=order.usdt,
                            order_type="limit",
                            price=order.price,
                            paper=config.PAPER_TRADING,
                        )
                        if order_response and order_response.get("id"):
                            order.order_id = order_response["id"]
                    except Exception as e:
                        logger.error(f"Failed to place {order.side} order at ${order.price:.4f}: {e}")

            # Save state after each cycle
            save_grid_state(strategy.to_dict(), config.EXCHANGE_ID, config.SYMBOL)

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
        # Try to load saved state first
        saved_state = load_grid_state(config.EXCHANGE_ID, config.SYMBOL)

        if saved_state:
            console.print("[yellow]Restoring grid from saved state...[/yellow]")
            strategy = GridStrategy.from_dict(saved_state)
        else:
            console.print("[yellow]Starting fresh grid...[/yellow]")
            strategy = GridStrategy(
                lower_price=config.GRID_LOWER_PRICE,
                upper_price=config.GRID_UPPER_PRICE,
                num_levels=config.GRID_NUM_LEVELS,
                order_usdt=config.GRID_ORDER_USDT,
                start_mode=config.GRID_START_MODE,
                rebalance_threshold=config.GRID_REBALANCE_THRESHOLD,
                spacing_type=getattr(config, "GRID_SPACING_TYPE", "linear"),
            )

        console.print(
            f"[bold green]Grid Bot started ({strategy.start_mode} mode).[/bold green] "
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