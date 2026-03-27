#!/bin/bash
# start.sh - Run trading bot and Web Dashboard

# Run the trading bot in the background
echo "Starting CC Trading Bot..."
python3 bot.py &

# Run the dashboard in the foreground, binding to the Railway $PORT
echo "Starting Web Dashboard..."
exec gunicorn --bind 0.0.0.0:$PORT dashboard:app
