# Railway Deployment Guide

## Quick Start (5 minutes)

### Prerequisites
- GitHub account
- Railway.app account (free)
- Discord Bot Token (from Discord Developer Portal)
- Telegram Bot Token (from BotFather)

### Step 1: Push Code to GitHub

```bash
git init
git add .
git commit -m "Initial commit"
git branch -M main
git remote add origin https://github.com/YOUR_USERNAME/castopia-bot.git
git push -u origin main
```

### Step 2: Create Railway Project

1. Go to [railway.app/dashboard](https://railway.app/dashboard)
2. Click **"New Project"** → **"Deploy from GitHub repo"**
3. Select your `castopia-bot` repository
4. Railway will automatically detect Python and install dependencies

### Step 3: Configure Environment Variables

In Railway Dashboard → **Variables**:

```env
DISCORD_BOT_TOKEN=your_discord_token_here
TELEGRAM_BOT_TOKEN=your_telegram_token_here
WIKI_BASE_URL=https://castopia.site
WIKI_USER_AGENT=CastopiaBot/2.0
WIKI_MAX_CONCURRENCY=4
LOG_LEVEL=INFO
```

⚠️ **Important**: Do NOT use `.env` file in Railway. Only use Environment Variables in the Dashboard.

### Step 4: Enable Public Networking (Optional)

If you want to access bot logs or health endpoints:
- Go to Settings → Public Networking → Enable

### Step 5: Deploy!

Railway automatically deploys when you push to main. Check deployment status in Dashboard.

---

## Architecture

Railway will:

1. **Build Phase**:
   - Detect Python 3.12 from `runtime.txt`
   - Install packages from `requirements.txt`
   - Run any build commands from `Procfile`

2. **Run Phase**:
   - Execute both processes from `Procfile`:
     ```
     discord: python dsc/bot.py
     telegram: python tg/bot.py
     ```

3. **Monitoring**:
   - View logs in Dashboard
   - Auto-restart on failure
   - Environment variables injected at runtime

---

## Procfile Explained

```procfile
# Format: <process-type>: <command>

discord: python dsc/bot.py
telegram: python tg/bot.py
```

- `discord` - Discord bot process
- `telegram` - Telegram bot process  
- Both run simultaneously
- Railway restarts either if it crashes

---

## Troubleshooting

### Bot not starting?

Check logs in Railway Dashboard → View Logs

Common issues:

| Error | Solution |
|-------|----------|
| `Configuration error: DISCORD_BOT_TOKEN is missing` | Add `DISCORD_BOT_TOKEN` in Railway Variables |
| `Module not found: discord` | Check `requirements.txt` includes `discord.py>=2.4` |
| `Connection refused` | Bots are working, just no incoming messages yet |

### How to view logs?

```bash
# Option 1: Railway Dashboard
# View → Logs tab (real-time streaming)

# Option 2: Railway CLI
railway logs

# Option 3: SSH into running app
railway shell
```

### Restart bot?

- **Manual**: Railway Dashboard → Redeploy
- **Automatic**: Railway restarts on crash or new deployment

### Update code?

```bash
git commit -am "Fix bug"
git push
# Railway automatically redeploys within 1 minute
```

---

## Free Tier Limits

Railway Free Tier includes:

- ✅ Unlimited projects
- ✅ $5/month usage credits (enough for 2-3 bots 24/7)
- ✅ Unlimited deployments
- ✅ Public networking

Estimate for this bot: **~$3-4/month**

---

## Environment Variables Reference

| Variable | Required | Example | Notes |
|----------|----------|---------|-------|
| `DISCORD_BOT_TOKEN` | ✅ | `MTMz...` | From Discord Developer Portal |
| `TELEGRAM_BOT_TOKEN` | ✅ | `7787...` | From BotFather |
| `WIKI_BASE_URL` | ❌ | `https://castopia.site` | Default: castopia.site |
| `WIKI_USER_AGENT` | ❌ | `CastopiaBot/2.0` | Identifies your bot to wiki |
| `WIKI_MAX_CONCURRENCY` | ❌ | `4` | Max concurrent requests (1-10) |
| `LOG_LEVEL` | ❌ | `INFO` | DEBUG, INFO, WARNING, ERROR |

---

## Monitoring

### Check bot status

```python
# Discord: Try /help command
# Telegram: Try /help command
```

### View metrics

- **Railway Dashboard**: Shows CPU, memory, network usage
- **Logs**: Check for errors or warnings

### Health check (optional)

```bash
railway logs | grep -E "Connected to Gateway|Start polling"
```

---

## Scaling

For multiple wikis or higher load:

1. **Discord Bot**:
   - Uses hybrid commands (prefix + slash)
   - Max load: ~5,000 guilds per bot token

2. **Telegram Bot**:
   - Uses long polling (no scaling needed)
   - Can handle unlimited users

3. **Wiki Client**:
   - Configurable concurrency (1-10)
   - 4-level caching (pages, articles, links, search)

---

## Next Steps

- [ ] Deploy to Railway
- [ ] Test Discord bot: `/help`
- [ ] Test Telegram bot: `/help`
- [ ] Monitor logs for 24 hours
- [ ] Set up GitHub Actions for CI/CD (optional)
- [ ] Add custom monitoring or alerts (optional)

---

## Support

- **GitHub**: Create an issue
- **Discord**: Check bot logs for errors
- **Telegram**: Test with `/help` command
- **Railway**: Check [railway.app/docs](https://railway.app/docs)

