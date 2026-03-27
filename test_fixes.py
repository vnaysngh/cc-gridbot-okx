#!/usr/bin/env python3
# test_fixes.py - Validate all rebalancing fixes

import sys
from pathlib import Path
from rich.console import Console
from rich.table import Table
from rich import box

import config
from strategies.grid import GridStrategy
from utils.state_manager import save_grid_state, load_grid_state, clear_grid_state

console = Console()

def test_state_persistence():
    """Test 1: State persistence"""
    console.print("\n[bold cyan]Test 1: State Persistence[/bold cyan]")

    # Create a strategy
    strategy = GridStrategy(
        lower_price=0.13,
        upper_price=0.15,
        num_levels=10,
        order_usdt=8.0,
        start_mode="full",
        rebalance_threshold=0.75,
    )

    # Simulate some activity
    strategy.state.completed_cycles = 5
    strategy.state.total_profit_usdt = 2.5
    strategy.state.rebalance_count = 1

    # Save state
    state_dict = strategy.to_dict()
    save_grid_state(state_dict, "test_exchange", "TEST/USDT")

    # Load state
    loaded = load_grid_state("test_exchange", "TEST/USDT")

    # Verify
    if loaded:
        restored_strategy = GridStrategy.from_dict(loaded)
        checks = [
            ("Completed cycles", strategy.state.completed_cycles == restored_strategy.state.completed_cycles),
            ("Total profit", strategy.state.total_profit_usdt == restored_strategy.state.total_profit_usdt),
            ("Rebalance count", strategy.state.rebalance_count == restored_strategy.state.rebalance_count),
            ("Grid levels", strategy.num_levels == restored_strategy.num_levels),
            ("Order size", strategy.order_usdt == restored_strategy.order_usdt),
        ]

        all_passed = all(result for _, result in checks)

        table = Table(box=box.SIMPLE, show_header=False)
        for check_name, passed in checks:
            status = "[green]✓[/green]" if passed else "[red]✗[/red]"
            table.add_row(status, check_name)
        console.print(table)

        # Cleanup
        clear_grid_state("test_exchange", "TEST/USDT")

        return all_passed
    else:
        console.print("[red]✗ Failed to load state[/red]")
        return False


def test_grid_serialization():
    """Test 2: Grid serialization with orders"""
    console.print("\n[bold cyan]Test 2: Grid Serialization[/bold cyan]")

    strategy = GridStrategy(
        lower_price=0.13,
        upper_price=0.15,
        num_levels=5,
        order_usdt=10.0,
        start_mode="full",
        rebalance_threshold=0.75,
    )

    # Initialize with a price
    strategy.initialize_orders(0.14)

    # Serialize and deserialize
    state_dict = strategy.to_dict()
    restored = GridStrategy.from_dict(state_dict)

    checks = [
        ("Order count", len(strategy.state.orders) == len(restored.state.orders)),
        ("Initialized flag", strategy.state.initialized == restored.state.initialized),
        ("Lower price", strategy.lower_price == restored.lower_price),
        ("Upper price", strategy.upper_price == restored.upper_price),
    ]

    table = Table(box=box.SIMPLE, show_header=False)
    for check_name, passed in checks:
        status = "[green]✓[/green]" if passed else "[red]✗[/red]"
        table.add_row(status, check_name)
    console.print(table)

    return all(result for _, result in checks)


def test_unrealized_pnl():
    """Test 3: Unrealized P&L calculation"""
    console.print("\n[bold cyan]Test 3: Unrealized P&L Calculation[/bold cyan]")

    strategy = GridStrategy(
        lower_price=0.10,
        upper_price=0.20,
        num_levels=5,
        order_usdt=10.0,
        start_mode="full",
        rebalance_threshold=0.75,
    )

    # Initialize grid
    strategy.initialize_orders(0.15)

    # Get summary at initialization (should have 0 unrealized P&L)
    summary = strategy.status_summary(0.15)

    checks = [
        ("Summary contains unrealized_usdt", "unrealized_usdt" in summary),
        ("Summary contains cc_held", "cc_held" in summary),
        ("Summary contains total_profit_usdt", "total_profit_usdt" in summary),
        ("Current price matches", summary["current_price"] == 0.15),
    ]

    table = Table(box=box.SIMPLE, show_header=False)
    for check_name, passed in checks:
        status = "[green]✓[/green]" if passed else "[red]✗[/red]"
        table.add_row(status, check_name)
    console.print(table)

    return all(result for _, result in checks)


def test_rebalance_logic():
    """Test 4: Rebalance trigger logic"""
    console.print("\n[bold cyan]Test 4: Rebalance Logic[/bold cyan]")

    strategy = GridStrategy(
        lower_price=0.10,
        upper_price=0.20,
        num_levels=10,
        order_usdt=10.0,
        start_mode="buys_only",
        rebalance_threshold=0.75,
    )

    # Initialize within grid range (should create buy orders below)
    strategy.initialize_orders(0.18)

    # Check if rebalance is needed (all buys, no sells = should trigger)
    needs_rebal, buy_count, sell_count = strategy._needs_rebalance()

    # For buys_only mode, we expect all buy orders and no sells
    buy_ratio = buy_count / (buy_count + sell_count) if (buy_count + sell_count) > 0 else 0

    checks = [
        ("Rebalance needed (all buys)", needs_rebal == True),
        ("Has buy orders", buy_count > 0),
        ("Has no sell orders (buys_only mode)", sell_count == 0),
        ("Buy ratio >= threshold", buy_ratio >= 0.75),
    ]

    table = Table(box=box.SIMPLE, show_header=False)
    for check_name, passed in checks:
        status = "[green]✓[/green]" if passed else "[red]✗[/red]"
        table.add_row(status, check_name)
    console.print(table)

    return all(result for _, result in checks)


def test_config_structure():
    """Test 5: Config structure"""
    console.print("\n[bold cyan]Test 5: Config Structure[/bold cyan]")

    checks = [
        ("GRID_REBALANCE_THRESHOLD exists", hasattr(config, "GRID_REBALANCE_THRESHOLD")),
        ("GRID_START_MODE exists", hasattr(config, "GRID_START_MODE")),
        ("GRID_LOWER_PRICE exists", hasattr(config, "GRID_LOWER_PRICE")),
        ("GRID_UPPER_PRICE exists", hasattr(config, "GRID_UPPER_PRICE")),
        ("GRID_NUM_LEVELS exists", hasattr(config, "GRID_NUM_LEVELS")),
        ("GRID_ORDER_USDT exists", hasattr(config, "GRID_ORDER_USDT")),
        ("Rebalance threshold is valid", 0 < config.GRID_REBALANCE_THRESHOLD <= 1.0),
    ]

    table = Table(box=box.SIMPLE, show_header=False)
    for check_name, passed in checks:
        status = "[green]✓[/green]" if passed else "[red]✗[/red]"
        table.add_row(status, check_name)
    console.print(table)

    return all(result for _, result in checks)


def main():
    console.print("[bold]Testing All Rebalancing Fixes[/bold]")
    console.print("=" * 60)

    tests = [
        ("State Persistence", test_state_persistence),
        ("Grid Serialization", test_grid_serialization),
        ("Unrealized P&L", test_unrealized_pnl),
        ("Rebalance Logic", test_rebalance_logic),
        ("Config Structure", test_config_structure),
    ]

    results = []
    for test_name, test_func in tests:
        try:
            passed = test_func()
            results.append((test_name, passed))
        except Exception as e:
            console.print(f"[red]✗ {test_name} raised exception: {e}[/red]")
            results.append((test_name, False))

    # Summary
    console.print("\n[bold]Test Summary[/bold]")
    console.print("=" * 60)

    summary_table = Table(box=box.ROUNDED)
    summary_table.add_column("Test", style="cyan")
    summary_table.add_column("Result", justify="center")

    for test_name, passed in results:
        status = "[green]PASS ✓[/green]" if passed else "[red]FAIL ✗[/red]"
        summary_table.add_row(test_name, status)

    console.print(summary_table)

    total_passed = sum(1 for _, passed in results if passed)
    total_tests = len(results)

    console.print(f"\n[bold]Result: {total_passed}/{total_tests} tests passed[/bold]")

    if total_passed == total_tests:
        console.print("[bold green]✓ All tests passed! Bot fixes validated.[/bold green]")
        return 0
    else:
        console.print("[bold red]✗ Some tests failed. Check implementation.[/bold red]")
        return 1


if __name__ == "__main__":
    sys.exit(main())
