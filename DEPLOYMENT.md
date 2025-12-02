# iBasketCal Deployment Guide

## Quick Comparison

| Platform         | Free Tier     | Persistent Data | Auto-Sleep  | Est. Cost  |
|------------------|---------------|-----------------|-------------|------------|
| **Railway**      | $5 credit/mo  | ✅ Volume       | No          | Free-$5/mo |
| **Render**       | Yes (limited) | ✅ Disk         | Yes (15min) | Free-$7/mo |
| **Fly.io**       | 3 VMs free    | ✅ Volume       | Yes         | Free-$5/mo |
| **DigitalOcean** | No            | ✅              | No          | $5/mo      |

**Currently using**: **Render**

---

## Option 1: Render (Currently Used) ⭐

Render is similar to Railway with a generous free tier.

### Steps

1. **Go to Render**
   ```
   https://render.com
   ```

2. **Create Web Service**
   - New → Web Service
   - Connect GitHub repo
   - Select `RF555/iBasketCal`

3. **Configure**
   ```
   Name: ibasketcal
   Runtime: Docker
   Plan: Free (or Starter $7/mo for always-on)
   Health Check Path: /health
   ```

4. **Add Disk (Important!)**
   - Go to service settings
   - Disks → Add Disk
   - Name: `basketball-data`
   - Mount Path: `/app/cache`
   - Size: 1 GB

5. **Deploy**
   - Click "Create Web Service"
   - Wait for build (~5 min)

### Notes
- **Free tier sleeps after 15 min inactivity** (first request takes 30-60s to wake)
- Starter plan ($7/mo) stays always-on

---

## Option 2: Railway (Easiest)

Railway offers the simplest deployment with automatic Docker detection.

### Steps

1. **Go to Railway**
   ```
   https://railway.app
   ```

2. **Connect GitHub**
   - Click "New Project"
   - Select "Deploy from GitHub repo"
   - Choose `RF555/iBasketCal`

3. **Configure**
   - Railway auto-detects the Dockerfile
   - Add a volume for persistent data:
     - Go to project settings
     - Click "Add Volume"
     - Mount path: `/app/cache`
     - Size: 1GB

4. **Deploy**
   - Click "Deploy"
   - Wait 3-5 minutes for build
   - Get your URL: `https://ibasketcal-xxx.up.railway.app`

5. **Custom Domain (Optional)**
   - Settings → Domains → Add custom domain

### Config File

Create `railway.toml` in project root:
```toml
[build]
builder = "dockerfile"

[deploy]
healthcheckPath = "/health"
healthcheckTimeout = 100
restartPolicyType = "on_failure"
restartPolicyMaxRetries = 3
```

### Cost
- Free tier: $5 credit/month (enough for this app)
- No credit card required to start

---

## Option 3: Fly.io (Best Performance)

Fly.io runs containers on edge servers worldwide. Frankfurt region is closest to Israel.

### Steps

1. **Install Fly CLI**
   ```bash
   # macOS
   brew install flyctl

   # Linux
   curl -L https://fly.io/install.sh | sh

   # Windows
   powershell -Command "iwr https://fly.io/install.ps1 -useb | iex"
   ```

2. **Login**
   ```bash
   fly auth signup  # or fly auth login
   ```

3. **Create App**
   ```bash
   cd iBasketCal
   fly launch --no-deploy
   # Choose Frankfurt (fra) region
   # Say NO to Postgres/Redis
   ```

4. **Create Volume for Data**
   ```bash
   fly volumes create basketball_data --size 1 --region fra
   ```

5. **Create fly.toml**
   Create `fly.toml` in project root:
   ```toml
   app = "ibasketcal"
   primary_region = "fra"

   [build]

   [http_service]
     internal_port = 8000
     force_https = true
     auto_stop_machines = true
     auto_start_machines = true
     min_machines_running = 0

   [mounts]
     source = "basketball_data"
     destination = "/app/cache"

   [[vm]]
     cpu_kind = "shared"
     cpus = 1
     memory_mb = 512
   ```

6. **Deploy**
   ```bash
   fly deploy
   ```

7. **Check Status**
   ```bash
   fly status
   fly logs
   ```

### Your App URL
```
https://ibasketcal.fly.dev
```

### Useful Commands
```bash
fly logs              # View logs
fly status            # Check app status
fly ssh console       # SSH into container
fly volumes list      # List volumes
fly scale count 1     # Ensure 1 instance
```

---

## Option 4: DigitalOcean App Platform

Simple and reliable, but no free tier.

### Steps

1. **Go to DigitalOcean**
   ```
   https://cloud.digitalocean.com/apps
   ```

2. **Create App**
   - Click "Create App"
   - Choose GitHub as source
   - Select `RF555/iBasketCal`

3. **Configure**
   ```
   Type: Web Service
   Plan: Basic ($5/mo)
   Instance Size: 512 MB RAM
   ```

4. **Environment**
   - No env vars needed

5. **Deploy**
   - Review and create
   - Wait for build

### Config File

DigitalOcean uses the App Platform UI for configuration. Alternatively, create `.do/app.yaml`:
```yaml
name: ibasketcal
services:
  - name: web
    dockerfile_path: Dockerfile
    github:
      repo: RF555/iBasketCal
      branch: main
      deploy_on_push: true
    health_check:
      http_path: /health
    instance_count: 1
    instance_size_slug: basic-xxs
    http_port: 8000
```

---

## Post-Deployment Checklist

After deploying to any platform:

### 1. Test Health Endpoint
```bash
curl https://your-app-url.com/health
```

### 2. Test API
```bash
curl https://your-app-url.com/api/seasons
```

### 3. Initial Data Load
The first request will take 1-2 minutes as it scrapes all data.
```bash
curl https://your-app-url.com/api/cache-info
```

### 4. Test Calendar Feed
```bash
curl "https://your-app-url.com/calendar.ics?team=מכבי" -o test.ics
```

### 5. Subscribe in Google Calendar
```
https://your-app-url.com/calendar.ics?team=YOUR_TEAM
```

---

## Troubleshooting

### Build Fails

**"Playwright install failed"**
- Ensure Dockerfile has all Chromium dependencies
- Try the optimized Dockerfile from this package

**"Out of memory during build"**
- Increase build memory in platform settings
- Railway/Render: Usually auto-scales
- Fly.io: `fly scale memory 1024`

### App Crashes

**"No cache found" then crash**
- Volume not mounted properly
- Check mount path is `/app/cache`

**"Token extraction failed"**
- Widget page may have changed
- Check logs for details
- May need to update scraper

### Slow First Request

This is normal! First request triggers data scrape (~60s).
Subsequent requests are fast (<100ms).

### Data Not Persisting

- Ensure volume/disk is mounted to `/app/cache`
- Check volume exists and is attached
- Fly.io: Run `fly volumes list`

---

## Custom Domain Setup

### Railway
1. Settings → Domains → Custom Domain
2. Add your domain
3. Update DNS: CNAME to Railway URL

### Render
1. Settings → Custom Domains
2. Add domain
3. Update DNS as instructed

### Fly.io
```bash
fly certs create yourdomain.com
# Then update DNS as instructed
```

---

## Updating the App

### Railway/Render
Push to GitHub → Auto-deploys

### Fly.io
```bash
fly deploy
```

### DigitalOcean
Push to GitHub → Auto-deploys (or manual trigger)

---

## Cost Summary

| Usage | Railway | Render | Fly.io | DO |
|-------|---------|--------|--------|-----|
| Low (<1K req/day) | Free | Free* | Free | $5/mo |
| Medium | Free | $7/mo | Free | $5/mo |
| High | $5/mo | $7/mo | $5/mo | $12/mo |

*Render free tier has cold starts (30-60s after idle)

---

## Project Files

```
├── Dockerfile              # Multi-stage build for production
├── docker-compose.yml      # Local development
├── .dockerignore           # Reduce image size
├── render.yaml             # Render config (currently used)
├── .github/workflows/      # GitHub Actions CI (runs tests)
└── DEPLOYMENT.md           # This guide
```

Note: For other platforms (Railway, Fly.io, DigitalOcean), you'll need to create their config files as described above.
