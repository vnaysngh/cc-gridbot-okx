# Deploy CC Trading Bot to Railway.app

This guide walks you through deploying your trading bot to Railway.app so it runs 24/7 in the cloud.

## Why Railway.app?

- Free tier: $5 credit/month (enough for a lightweight bot)
- Runs 24/7 without your computer
- Easy deployment from GitHub
- Simple environment variable management
- Automatic restarts if bot crashes

---

## Pre-Deployment Checklist

Before deploying, make sure:

- [ ] You've tested the bot in paper mode locally (`PAPER_TRADING = True`)
- [ ] You have your OKX API keys ready (with Trade permission only)
- [ ] Your grid range is up to date in `config.py`
- [ ] You have sufficient balance on OKX (~$40 USDT + ~$40 worth of CC)

---

## Step 1: Create a GitHub Repository

Railway deploys from GitHub, so you need to push your code first.

### 1.1 Initialize Git (if not already done)

```bash
cd /Users/vinaysingh/Downloads/cc_bot
git init
```

### 1.2 Add all files (except .env which is gitignored)

```bash
git add .
git commit -m "Initial commit - CC trading bot"
```

### 1.3 Create a GitHub repository

1. Go to https://github.com/new
2. Name it `cc-trading-bot` (or whatever you prefer)
3. **Make it PRIVATE** (you don't want others seeing your strategy)
4. Don't initialize with README (you already have files)
5. Click "Create repository"

### 1.4 Push to GitHub

```bash
# Replace YOUR_USERNAME with your GitHub username
git remote add origin https://github.com/YOUR_USERNAME/cc-trading-bot.git
git branch -M main
git push -u origin main
```

**CRITICAL:** Verify `.env` is NOT in your GitHub repo. Check: https://github.com/YOUR_USERNAME/cc-trading-bot
If you see `.env` listed, you accidentally committed your API keys. Delete the repo and start over.

---

## Step 2: Deploy to Railway.app

### 2.1 Sign up for Railway

1. Go to https://railway.app
2. Click "Login" → "Login with GitHub"
3. Authorize Railway to access your GitHub

### 2.2 Create a new project

1. Click "New Project"
2. Select "Deploy from GitHub repo"
3. Choose your `cc-trading-bot` repository
4. Railway will detect it's a Python app automatically

### 2.3 Configure environment variables

This is where you add your API keys (they're NOT in GitHub, remember?)

1. Click on your deployed service
2. Go to "Variables" tab
3. Click "Add Variable" and add these one by one:

```
OKX_API_KEY=your_api_key_here
OKX_API_SECRET=your_api_secret_here
OKX_API_PASSPHRASE=your_passphrase_here
```

**Do NOT add** `PAPER_TRADING` as an environment variable - it's already in `config.py`

### 2.4 Verify deployment

1. Go to "Deployments" tab
2. Wait for "Build" and "Deploy" to complete (takes 2-3 minutes)
3. Click on the latest deployment
4. Check "Logs" - you should see your bot starting up

---

## Step 3: Monitor Your Bot

### View live logs

1. In Railway, click your service → "Deployments" → Latest deployment
2. Check "Logs" tab
3. You should see:
   ```
   Grid Bot started (full mode). Press Ctrl+C to stop.
   Current price: $0.1401
   Grid range: $0.1331 – $0.1471
   In range: YES
   Active buys: 5
   Active sells: 5
   ```

### What to watch for

✅ **Good signs:**
- Bot shows "In range: YES"
- Orders are being placed
- No error messages

🔴 **Bad signs:**
- "Insufficient funds" errors → check OKX balance
- "Invalid API key" → check environment variables
- "Price outside grid" → update grid range

---

## Step 4: Update Grid Range (Weekly Maintenance)

When you need to update the grid range:

### 4.1 Update locally

```bash
# Check current price
python3 -c 'from utils.exchange import get_exchange, get_current_price; exchange = get_exchange("okx", authenticated=False); price = get_current_price(exchange, "CC/USDT"); print(f"Current: ${price:.4f} | Lower (-5%): ${price*0.95:.4f} | Upper (+5%): ${price*1.05:.4f}")'

# Edit config.py with new values
# Update GRID_LOWER_PRICE and GRID_UPPER_PRICE
# Update "Last updated" date
```

### 4.2 Push to GitHub

```bash
git add config.py
git commit -m "Update grid range - $(date +%Y-%m-%d)"
git push
```

### 4.3 Railway auto-deploys

- Railway detects the GitHub push
- Automatically rebuilds and redeploys
- Bot restarts with new grid range
- Takes ~2-3 minutes

---

## Step 5: Cost Management

### Railway.app pricing

- **Free tier:** $5 credit/month
- **Your bot usage:** ~$3-4/month (lightweight Python process)
- **What happens if you run out:** Bot stops, Railway emails you

### Monitor usage

1. Railway dashboard → "Usage" tab
2. Check "Estimated cost this month"
3. If approaching $5, consider:
   - Upgrade to Hobby plan ($5/month unlimited)
   - Increase `POLL_INTERVAL_SECONDS` to reduce CPU usage

---

## Troubleshooting

### Bot keeps restarting

**Cause:** Railway thinks it's a web server, not a worker process.

**Fix:** Check that `Procfile` contains:
```
worker: python3 bot.py
```

### "No module named 'ccxt'" error

**Cause:** Dependencies not installed.

**Fix:** Verify `requirements.txt` exists and Railway detected it. Check "Build Logs".

### Bot shows "PAPER TRADING" in logs

**Cause:** You forgot to set `PAPER_TRADING = False` in `config.py`

**Fix:**
```bash
# Edit config.py line 16
PAPER_TRADING = False

git add config.py
git commit -m "Enable live trading"
git push
```

### "Invalid API key" error

**Cause:** Environment variables not set correctly in Railway.

**Fix:**
1. Railway → your service → Variables tab
2. Verify `OKX_API_KEY`, `OKX_API_SECRET`, `OKX_API_PASSPHRASE` are set
3. No quotes, no spaces, exact values from OKX
4. Redeploy: Deployments → ⋮ menu → "Redeploy"

### Can't see my trades on OKX

**Cause:** Either still in paper mode, or API key lacks Trade permission.

**Fix:**
1. Verify `PAPER_TRADING = False` in config.py
2. Check OKX → API Management → your key has "Trade" enabled
3. Check bot logs for "[LIVE]" prefix on orders (not "[PAPER]")

---

## Emergency: Stop the Bot

### Method 1: Pause on Railway (quick)

1. Railway → your service
2. Click "Settings" → "Sleep Service"
3. Bot stops immediately

### Method 2: Delete deployment (permanent)

1. Railway → your service
2. Settings → "Delete Service"
3. Type service name to confirm

### Method 3: Disable API key (safest)

1. Go to OKX → Account → API Management
2. Delete or disable your API key
3. Bot can't place orders even if running

---

## Next Steps

Once deployed and running:

1. **Week 1:** Monitor daily, check profits, verify orders executing correctly
2. **Week 2+:** Check every Monday to update grid range
3. **Monthly:** Review performance, adjust `GRID_ORDER_USDT` if needed
4. **Set alerts:** Use OKX mobile app to get notified of trades

---

## Questions?

- Railway docs: https://docs.railway.app
- Check bot logs in Railway for errors
- Test locally first with `PAPER_TRADING = True` before deploying changes
