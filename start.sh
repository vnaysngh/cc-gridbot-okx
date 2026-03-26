#!/bin/bash
# start.sh - Run both bot and dashboard

# Start the trading bot in the background
python3 bot.py &
BOT_PID=$!

# Start the web dashboard
gunicorn --bind 0.0.0.0:$PORT --workers 1 --threads 2 --timeout 120 dashboard:app &
DASHBOARD_PID=$!

# Wait for both processes
wait $BOT_PID $DASHBOARD_PID
