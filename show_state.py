#!/usr/bin/env python3
# show_state.py - Display saved bot state

import json
import config
from utils.state_manager import load_grid_state
from rich.console import Console
from rich.table import Table
from rich import box

console = Console()

def main():
    console.print(f"[bold]Loading grid state for {config.EXCHANGE_ID} {config.SYMBOL}...[/bold]\n")

    state = load_grid_state(config.EXCHANGE_ID, config.SYMBOL)

    if not state:
        console.print("[yellow]No saved state found.[/yellow]")
        return

    # Display summary
    s = state["state"]
    console.print(f"[cyan]Grid Configuration:[/cyan]")
    console.print(f"  Range: ${state['lower_price']:.4f} - ${state['upper_price']:.4f}")
    console.print(f"  Levels: {state['num_levels']}")
    console.print(f"  Order size: ${state['order_usdt']:.2f}")
    console.print(f"  Start mode: {state['start_mode']}")
    console.print(f"  Rebalance threshold: {state['rebalance_threshold']:.0%}\n")

    console.print(f"[cyan]Performance:[/cyan]")
    console.print(f"  Completed cycles: {s['completed_cycles']}")
    console.print(f"  Total profit: ${s['total_profit_usdt']:.4f}")
    console.print(f"  Rebalances: {s['rebalance_count']}\n")

    # Display orders
    orders = s["orders"]
    active_orders = [o for o in orders if not o["filled"]]
    filled_orders = [o for o in orders if o["filled"]]

    console.print(f"[cyan]Active Orders:[/cyan] {len(active_orders)}")
    if active_orders:
        table = Table(box=box.SIMPLE)
        table.add_column("Level", style="dim")
        table.add_column("Side")
        table.add_column("Price", justify="right")
        table.add_column("USDT", justify="right")
        table.add_column("Order ID", style="dim")

        for o in sorted(active_orders, key=lambda x: x["price"]):
            color = "green" if o["side"] == "buy" else "red"
            table.add_row(
                str(o["level"]),
                f"[{color}]{o['side'].upper()}[/{color}]",
                f"${o['price']:.4f}",
                f"${o['usdt']:.2f}",
                (o.get("order_id") or "")[:12] + "..." if o.get("order_id") else "N/A"
            )
        console.print(table)

    console.print(f"\n[cyan]Filled Orders:[/cyan] {len(filled_orders)}")

    # Show raw JSON option
    console.print(f"\n[dim]State file location:[/dim]")
    from pathlib import Path
    state_dir = Path(__file__).parent / "data" / "state"
    safe_symbol = config.SYMBOL.replace("/", "_")
    filepath = state_dir / f"grid_{config.EXCHANGE_ID}_{safe_symbol}.json"
    console.print(f"[dim]{filepath}[/dim]")

if __name__ == "__main__":
    main()
