# Optional: Scheduled Data Refresh

The app currently refreshes data on-demand via the `/api/refresh` endpoint.
For automatic daily updates, you have several options:

## Option 1: External Cron Service (Recommended)

Use a free cron service to hit your refresh endpoint daily:

### cron-job.org (Free)
1. Go to https://cron-job.org
2. Create account
3. Add new cron job:
   - URL: `https://your-app.com/api/refresh`
   - Method: POST
   - Schedule: `0 6 * * *` (6 AM daily)

### GitHub Actions (Free)
Add `.github/workflows/refresh.yml`:

```yaml
name: Refresh Basketball Data

on:
  schedule:
    # Run at 6 AM UTC daily (8 AM Israel time)
    - cron: '0 6 * * *'
  workflow_dispatch:  # Allow manual trigger

jobs:
  refresh:
    runs-on: ubuntu-latest
    steps:
      - name: Trigger refresh
        run: |
          curl -X POST https://your-app.com/api/refresh
          sleep 120  # Wait 2 minutes for scrape
          curl https://your-app.com/api/cache-info
```

### UptimeRobot (Free)
1. Go to https://uptimerobot.com
2. Add new monitor → HTTP(s)
3. URL: `https://your-app.com/api/refresh`
4. Monitoring interval: 24 hours
5. Note: This also acts as uptime monitoring!

---

## Option 2: Built-in Scheduler

Add APScheduler to the app for built-in scheduling.

### Step 1: Add dependency

Add to `requirements.txt`:
```
apscheduler>=3.10.0
```

### Step 2: Update main.py

Add this code after the imports:

```python
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
import os

# Initialize scheduler
scheduler = AsyncIOScheduler()

async def scheduled_refresh():
    """Background task to refresh data."""
    print("[Scheduler] Starting scheduled refresh...")
    try:
        if not data_service.is_scraping():
            data_service.refresh_async()
            print("[Scheduler] Refresh started")
        else:
            print("[Scheduler] Scrape already in progress, skipping")
    except Exception as e:
        print(f"[Scheduler] Error: {e}")
```

Update the lifespan function:

```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    # ... existing startup code ...
    
    # Start scheduler if enabled
    if os.getenv("ENABLE_SCHEDULER", "false").lower() == "true":
        scheduler.add_job(
            scheduled_refresh,
            CronTrigger(hour=6, minute=0),  # 6 AM daily
            id="daily_refresh",
            replace_existing=True
        )
        scheduler.start()
        print("[+] Scheduler started (daily refresh at 6 AM)")
    
    yield  # Application runs here
    
    # Shutdown
    if scheduler.running:
        scheduler.shutdown()
    print("[*] Shutting down...")
```

### Step 3: Enable via environment

Set `ENABLE_SCHEDULER=true` in your deployment platform.

---

## Option 3: Fly.io Machines (Advanced)

Fly.io can run scheduled tasks with their Machines API.

### Create refresh-worker.toml

```toml
app = "ibasketcal-worker"
primary_region = "fra"

[build]
  dockerfile = "Dockerfile"

[[services]]
  internal_port = 8000
  protocol = "tcp"

[processes]
  worker = "python -c \"from src.services.data_service import DataService; DataService().get_data(force_refresh=True)\""
```

### Schedule with fly machines

```bash
# Create a machine that runs once daily
fly machine run . \
  --schedule "0 6 * * *" \
  --command "python -c 'from src.services.data_service import DataService; DataService().get_data(force_refresh=True)'"
```

---

## Recommendation

For most users, **Option 1 (External Cron)** is the simplest:
- No code changes required
- Free services available
- Easy to modify schedule
- Works with any deployment platform

The GitHub Actions approach is particularly nice because:
- It's already integrated with your repo
- You can see refresh history
- Easy to trigger manually
- Sends notifications on failure
