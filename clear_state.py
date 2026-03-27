#!/usr/bin/env python3
# clear_state.py - Clear saved bot state

import config
from utils.state_manager import clear_grid_state

def main():
    print(f"Clearing saved grid state for {config.EXCHANGE_ID} {config.SYMBOL}...")
    clear_grid_state(config.EXCHANGE_ID, config.SYMBOL)
    print("✓ State cleared. Next bot run will start fresh.")

if __name__ == "__main__":
    main()
