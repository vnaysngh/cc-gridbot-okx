#!/usr/bin/env python3
# dashboard.py — Web UI for monitoring the trading bot

from flask import Flask, render_template, jsonify
from datetime import datetime
import json
import os

app = Flask(__name__)

# Path to shared state file (bot writes, dashboard reads)
# Use the data directory so it can be mounted as a persistent volume in Railway
STATE_FILE = os.path.join(os.path.dirname(__file__), "data", "bot_state.json")


def read_bot_state():
    """Read current bot state from shared JSON file."""
    if not os.path.exists(STATE_FILE):
        return {
            "status": "waiting",
            "message": "Bot not started yet",
            "timestamp": datetime.now().isoformat()
        }

    try:
        with open(STATE_FILE, 'r') as f:
            return json.load(f)
    except Exception as e:
        return {
            "status": "error",
            "message": f"Failed to read state: {str(e)}",
            "timestamp": datetime.now().isoformat()
        }


@app.route('/')
def index():
    """Main dashboard page."""
    return render_template('dashboard.html')


@app.route('/api/status')
def api_status():
    """API endpoint: Current bot status."""
    state = read_bot_state()
    return jsonify(state)


@app.route('/api/orders')
def api_orders():
    """API endpoint: Active and completed orders."""
    state = read_bot_state()
    return jsonify({
        "active_orders": state.get("active_orders", []),
        "completed_orders": state.get("completed_orders", [])
    })


@app.route('/api/performance')
def api_performance():
    """API endpoint: Performance metrics."""
    state = read_bot_state()
    return jsonify({
        "total_profit_usdt": state.get("total_profit_usdt", 0),
        "unrealized_usdt": state.get("unrealized_usdt", 0),
        "completed_cycles": state.get("completed_cycles", 0),
        "uptime_hours": state.get("uptime_hours", 0),
    })


@app.route('/api/health')
def api_health():
    """API endpoint: Health check for monitoring."""
    state = read_bot_state()
    is_healthy = state.get("status") == "running" and \
                 (datetime.now() - datetime.fromisoformat(state.get("timestamp", datetime.now().isoformat()))).seconds < 120

    return jsonify({
        "healthy": is_healthy,
        "status": state.get("status", "unknown"),
        "last_update": state.get("timestamp")
    })


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port, debug=False)
