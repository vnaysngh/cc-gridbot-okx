# Dashboard Quick Start

## What You Just Got

✅ **Beautiful web dashboard** with real-time monitoring
✅ **Live price charts** showing grid levels
✅ **P&L tracking** (realized + unrealized profits)
✅ **Order history** with timestamps
✅ **Auto-updates** every 5 seconds
✅ **Works on mobile** - responsive design

---

## Access Your Dashboard

### On Railway (after deployment):

1. **Wait for Railway to finish deploying** (2-3 minutes)
   - Railway will auto-detect the changes and redeploy

2. **Generate a public URL:**
   - Go to Railway dashboard
   - Click your service (cc-gridbot-okx)
   - Click "Settings" tab
   - Click "Generate Domain" button
   - You'll get a URL like: `https://cc-gridbot-okx-production-abc123.up.railway.app`

3. **Open the URL in your browser:**
   - Dashboard loads immediately
   - Shows real-time bot status
   - Updates every 5 seconds automatically

4. **Bookmark it** for easy access!

---

## What You'll See

### Dashboard Sections:

**1. Status Banner (Top)**
- Bot status: Running / Error / Waiting
- Current message from bot
- Last update timestamp

**2. Metrics Cards**
- **Current Status:** Price, Grid Range, In Range check
- **Performance:** Realized profit, Unrealized P&L, Total P&L
- **Activity:** Active buys/sells, Completed cycles

**3. Price Chart**
- Real-time price line (blue)
- Grid upper bound (red dashed)
- Grid lower bound (green dashed)
- Last 20 data points shown

**4. Recent Orders Table**
- Last 10 orders
- Timestamp, Side (Buy/Sell), Price, Amount
- Color-coded: Green = Buy, Red = Sell

---

## Important: Railway Config Change

**The Procfile changed from `worker` to `web`:**

**Old Procfile:**
```
worker: python3 bot.py
```

**New Procfile:**
```
web: bash start.sh
```

**Why?**
- `worker` = no public URL, runs in background
- `web` = gets a public URL, can serve HTTP traffic
- `start.sh` runs BOTH bot + dashboard together

Railway will detect this change and automatically:
1. Assign a port (stored in `$PORT` environment variable)
2. Expose that port to the internet
3. Generate a public domain for you

---

## Verify Dashboard is Working

### Check Railway Logs:

1. Railway → Your service → Deployments → Latest
2. Look for these log lines:

```
✅ Starting bot:
Grid Bot started (full mode)...

✅ Starting dashboard:
[INFO] Starting gunicorn 21.2.0
[INFO] Listening at: http://0.0.0.0:8080
```

If you see both, the dashboard is live!

### Check Bot State File:

The bot creates `bot_state.json` with current status. In Railway logs, you should see:
```
Writing bot state to bot_state.json...
```

### Test the API:

Once you have your Railway URL, test the API directly:
```
https://your-railway-url.up.railway.app/api/status
```

Should return JSON with bot status.

---

## Mobile Setup

### Add to Home Screen (iOS):

1. Open your Railway URL in Safari
2. Tap the Share button (square with arrow)
3. Scroll down and tap "Add to Home Screen"
4. Name it "CC Bot"
5. Tap "Add"

Now you have a native-looking app icon!

### Add to Home Screen (Android):

1. Open your Railway URL in Chrome
2. Tap the three-dot menu (top right)
3. Tap "Add to Home screen"
4. Name it "CC Bot"
5. Tap "Add"

---

## Troubleshooting

### "Failed to connect to bot"

**Cause:** Bot not running or crashed

**Fix:**
1. Check Railway logs for errors
2. Verify environment variables are set (OKX_API_KEY, etc.)
3. Manually redeploy: Railway → Deployments → "Redeploy"

### Dashboard loads but shows "Waiting for bot..."

**Cause:** Bot hasn't written state file yet (first run)

**Fix:** Wait 30 seconds for bot to initialize and write first state

### No charts showing

**Cause:** Not enough data yet

**Fix:** Wait 2-3 minutes for bot to collect price data

### Railway logs show "Port already in use"

**Cause:** Multiple instances running (shouldn't happen)

**Fix:** Railway → Settings → Restart

---

## What's Next?

Now that you have a dashboard:

1. **Monitor daily** - Check profits, active orders
2. **Watch for errors** - Red status banner = something's wrong
3. **Track performance** - See which grid levels trade most
4. **Adjust grid range** - Use dashboard data to optimize weekly

Read **DASHBOARD.md** for advanced customization options!

---

## Summary of Changes

**Files added:**
- `dashboard.py` - Flask web server
- `templates/dashboard.html` - Frontend UI
- `start.sh` - Script to run bot + dashboard
- `DASHBOARD.md` - Full documentation

**Files modified:**
- `bot.py` - Now writes state to JSON file
- `Procfile` - Changed from `worker` to `web`
- `requirements.txt` - Added Flask and gunicorn

**Total cost on Railway:** Still ~$3-4/month (dashboard uses minimal resources)

Enjoy your new dashboard! 🎉
