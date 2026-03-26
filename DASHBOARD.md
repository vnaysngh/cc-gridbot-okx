# Trading Bot Dashboard

Your bot now has a beautiful web UI for real-time monitoring!

## Features

✨ **Real-Time Monitoring**
- Live price updates every 5 seconds
- Current grid range and status
- Active buy/sell orders count
- Completed cycles tracker

📊 **Visual Charts**
- Real-time price chart with grid levels
- Grid upper/lower bounds displayed
- Last 20 data points shown

💰 **Performance Tracking**
- Realized profit (from completed cycles)
- Unrealized P&L (from open positions)
- Total P&L (combined)
- Color-coded green/red for gains/losses

📋 **Order History**
- Last 10 orders displayed
- Timestamp, side (buy/sell), price, amount
- Color-coded buy (green) and sell (red) orders

---

## Running Locally

### 1. Install Flask dependencies
```bash
pip install flask gunicorn
```

### 2. Run bot + dashboard together
```bash
# Terminal 1: Run the trading bot
python3 bot.py

# Terminal 2: Run the web dashboard
python3 dashboard.py
```

### 3. Open your browser
Go to: http://localhost:8080

You should see the dashboard with live updates!

---

## Running on Railway

When you deploy to Railway, the dashboard is **automatically included**!

### Setup:

1. **Push the new files to GitHub:**
   ```bash
   git add .
   git commit -m "Add web dashboard"
   git push
   ```

2. **Railway will auto-deploy** (2-3 minutes)

3. **Access your dashboard:**
   - Go to Railway → Your service → "Settings"
   - Click "Generate Domain" (if not already done)
   - You'll get a URL like: `https://cc-gridbot-okx-production.up.railway.app`
   - Open that URL in your browser → Dashboard appears!

4. **Set environment variables** (if not already done):
   - Railway → Variables tab
   - Add: `OKX_API_KEY`, `OKX_API_SECRET`, `OKX_API_PASSPHRASE`

---

## How It Works

### Architecture:

```
┌─────────────┐         ┌──────────────┐         ┌──────────────┐
│   bot.py    │ writes  │ bot_state    │  reads  │ dashboard.py │
│ (trading)   │────────>│  .json       │<────────│  (Flask)     │
└─────────────┘         └──────────────┘         └──────────────┘
                                                         │
                                                         ▼
                                                  ┌──────────────┐
                                                  │   Browser    │
                                                  │  (Your UI)   │
                                                  └──────────────┘
```

1. **bot.py** runs your trading strategy and writes state to `bot_state.json` every 5 seconds
2. **dashboard.py** (Flask server) reads `bot_state.json` and serves it via API
3. **Browser** fetches from dashboard API every 5 seconds and updates the UI

### Files Added:

- `dashboard.py` - Flask web server with API endpoints
- `templates/dashboard.html` - Beautiful frontend UI
- `start.sh` - Bash script to run bot + dashboard together
- `bot_state.json` - Shared state file (created automatically)

---

## API Endpoints

Your dashboard exposes these endpoints:

### GET `/`
Main dashboard page (HTML)

### GET `/api/status`
Current bot status, price, grid info, P&L, orders
```json
{
  "status": "running",
  "message": "Grid bot active | Price: $0.1401",
  "current_price": 0.1401,
  "grid_lower": 0.1331,
  "grid_upper": 0.1471,
  "in_range": true,
  "active_buys": 5,
  "active_sells": 5,
  "completed_cycles": 3,
  "total_profit_usdt": 0.2456,
  "unrealized_usdt": 0.0123,
  "recent_orders": [...]
}
```

### GET `/api/health`
Health check for monitoring
```json
{
  "healthy": true,
  "status": "running",
  "last_update": "2026-03-27T10:30:00"
}
```

---

## Customization

### Change refresh rate

Edit `templates/dashboard.html` line 536:
```javascript
setInterval(updateDashboard, 5000); // 5000ms = 5 seconds
```

Change to 10 seconds:
```javascript
setInterval(updateDashboard, 10000);
```

### Change chart history

Edit `templates/dashboard.html` line 368:
```javascript
if (priceChart.data.labels.length > 20) {  // Keep last 20 points
```

Change to 50 points:
```javascript
if (priceChart.data.labels.length > 50) {
```

### Add more metrics

Edit `bot.py` `write_bot_state()` function to add new fields, then read them in the dashboard HTML.

---

## Troubleshooting

### Dashboard shows "Waiting for bot..."

**Cause:** Bot hasn't started or crashed

**Fix:**
- Check Railway logs: Deployments → Latest → Logs
- Look for bot startup message: "Grid Bot started"
- Check for errors in logs

### Dashboard shows old data

**Cause:** Bot stopped writing state file

**Fix:**
- Check bot is still running (Railway logs)
- Check `bot_state.json` exists and is being updated
- Restart deployment: Railway → Redeploy

### Can't access dashboard on Railway

**Cause:** No domain generated

**Fix:**
1. Railway → Your service → Settings
2. Click "Generate Domain"
3. Wait 30 seconds
4. Access the URL provided

### Browser shows "Failed to connect to bot"

**Cause:** Flask server not running

**Fix:**
- Check Railway logs for Flask/gunicorn errors
- Verify `start.sh` has execute permissions
- Check Procfile uses: `web: bash start.sh`

---

## Mobile Access

The dashboard works great on mobile! Just:

1. Get your Railway URL (e.g., `https://cc-gridbot-okx-production.up.railway.app`)
2. Open it on your phone's browser
3. Add to home screen (iOS: Share → Add to Home Screen)
4. Now you have a monitoring app!

---

## Security Notes

⚠️ **The dashboard is PUBLIC by default**

Anyone with your Railway URL can view your dashboard (but not trade or access API keys).

### To secure it:

Add basic authentication by editing `dashboard.py`:

```python
from flask import Flask, request, abort

def check_auth():
    auth = request.authorization
    if not auth or auth.password != 'YOUR_SECURE_PASSWORD':
        abort(401)

@app.before_request
def before_request():
    if request.endpoint != 'api_health':  # Allow health checks
        check_auth()
```

Or use Railway's built-in authentication features.

---

## Next Steps

- Bookmark your Railway dashboard URL
- Check it daily to monitor performance
- Set up mobile notifications (use Railway's webhooks + IFTTT)
- Add more custom metrics as you learn what matters to you

Enjoy your beautiful trading bot dashboard! 🚀
