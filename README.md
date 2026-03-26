# CC Trading Bot — DCA & Grid Strategies with Backtester

A personal trading bot for CC/USDT on KuCoin (or any exchange listing CC).
Includes a backtester so you can find good parameters before risking real money.

---

## Setup (do this once)

### 1. Install Python dependencies
```bash
pip install ccxt pandas backtesting python-dotenv rich tabulate
```

### 2. Copy the example env file and add your keys
```bash
cp .env.example .env
```
Then open `.env` and paste your exchange API key and secret.
**Never commit .env to git. Never share it.**

To get API keys on KuCoin:
- Go to KuCoin → Account → API Management → Create API
- Enable: General + Trade permissions
- Disable: Withdraw (never give a bot withdrawal permission)

### 3. Edit config.py to set your strategy parameters
Open `config.py` — every setting is documented there.

---

## Running the backtester first (always do this before live trading)

```bash
python backtester.py
```

This will:
- Download the last 6 months of CC/USDT hourly candles from KuCoin (free, no API key needed)
- Run both your DCA and Grid strategies against that real history
- Print a full report: profit, number of trades, win rate, max drawdown, Sharpe ratio
- Save an interactive HTML chart you can open in your browser

Tweak the parameters in `config.py` and re-run until you're happy with the results.

---

## Running the live bot (paper trading mode by default)

```bash
python bot.py
```

By default `PAPER_TRADING = True` in config.py — the bot will simulate trades
using real live prices but place NO real orders. Watch it for a day or two first.

When you're confident, set `PAPER_TRADING = False` in config.py to go live.

---

## Files

```
cc_bot/
├── config.py          ← All your strategy settings. Edit this.
├── bot.py             ← The live bot. Run this.
├── backtester.py      ← The backtester. Run this first.
├── strategies/
│   ├── dca.py         ← DCA bot logic
│   └── grid.py        ← Grid bot logic
├── utils/
│   ├── exchange.py    ← Exchange connection helpers
│   └── logger.py      ← Logging setup
├── .env.example       ← Copy to .env and fill in your keys
├── .env               ← Your real keys (never share this)
└── logs/              ← Bot activity logs saved here
```

---

## Important warnings

- Start with small amounts ($50–100) even after backtesting
- CC is thinly traded — large orders will move the price against you
- Grid bots lose money when price breaks outside your grid range — set it wide
- DCA bots can accumulate large losing positions in a sustained downtrend
- Past backtest performance does NOT guarantee future results
- Never invest more than you can afford to lose completely
