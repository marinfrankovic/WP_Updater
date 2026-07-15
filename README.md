# WP Updater

A small, self-hosted, **MainWP-style** dashboard that scans the WordPress sites
you run and reports available **core, plugin, and theme updates** — with a simple
web GUI, scheduled scans, email/Telegram reports, per-site **auto-update** toggles,
optional one-click "update all", **WPScan vulnerability flagging**, **post-update
health checks**, **pending-update age tracking**, and an optional **weekly digest**.

No SaaS, no per-site fees, no SSH into the sites required — the dashboard talks to
each site over HTTPS using a per-site API key.

It has two parts:

| Part | What it is | Where it runs |
|------|------------|---------------|
| **Connector** | A single-file mu-plugin exposing a secret-protected REST endpoint | On each WordPress site |
| **Dashboard** | A Flask app (Docker container) that polls each site and shows the GUI | On your own server / Docker host |

> **Heads up:** the update / auto-update endpoints perform privileged actions on
> your sites. Run the dashboard on a trusted network and put it behind HTTP basic
> auth or a reverse proxy (see [Securing the dashboard](#securing-the-dashboard)).

---

## Quick start (Docker Hub image)

The published image builds the React SPA and serves it together with the JSON API
from one container — no Node or build step needed on your side.

```bash
mkdir wp-updater && cd wp-updater

# 1. Create a data directory the container (uid 10001) can write to.
mkdir -p data && sudo chown -R 10001:10001 data

# 2. Run it.
docker run -d --name wp-updater \
  -p 8090:8090 \
  -e TZ=UTC \
  -e WPUPDATER_SECRET_KEY="$(openssl rand -hex 32)" \
  -v "$PWD/data:/data" \
  --restart unless-stopped \
  mfrankovic/wp-updater:latest
```

Open `http://YOUR_HOST:8090`.

Image: [`mfrankovic/wp-updater`](https://hub.docker.com/r/mfrankovic/wp-updater)
(multi-arch: `linux/amd64`, `linux/arm64`).

### Or with Docker Compose

```yaml
# compose.yaml
name: wp-updater
services:
  wp-updater:
    image: mfrankovic/wp-updater:latest
    container_name: wp-updater
    restart: unless-stopped
    ports:
      - "8090:8090"
    environment:
      TZ: UTC
      WPUPDATER_SECRET_KEY: change-me-to-a-long-random-string
      # Optional HTTP basic auth (leave blank to disable):
      WPUPDATER_USER: ""
      WPUPDATER_PASSWORD: ""
    volumes:
      - ./data:/data
```

```bash
mkdir -p data && sudo chown -R 10001:10001 data
docker compose up -d
```

### Application updates

Open **Settings → Application updates** to see the installed dashboard version. Update checks are manual unless you opt in to checking whenever Settings opens; that preference stays in the current browser. The dashboard reads stable GitHub Release metadata but never downloads an image, accesses Docker, or executes commands.

For a Compose deployment using `mfrankovic/wp-updater`, run:

```bash
docker compose pull wp-updater
docker compose up -d --no-deps wp-updater
```

For a local source build such as the included `compose.yaml`, run:

```bash
git pull
docker compose up -d --build wp-updater
```

The Settings card displays both command sets with copy buttons when a newer release exists.

---

## 1. Install the connector on each WordPress site

1. Download `wp-updater-connector.php` from the
   [**Releases page**](https://github.com/marinfrankovic/WP_Updater/releases).
2. Copy it into the site's `wp-content/mu-plugins/` folder (create the
   `mu-plugins` folder if it does not exist). Must-use plugins are always
   active — no activation needed.
3. In WP Admin, open **Settings → WP Updater**.
4. Copy the **Site URL** and the **API key** shown there.

> For maximum safety you can instead hard-code the key in `wp-config.php`:
> `define('WPUPDATER_API_KEY', 'your-long-random-key');`
> The Settings page will then show that fixed key.

The connector exposes (all require the `X-WPUpdater-Key` header):

| Method | Endpoint | Purpose |
|--------|----------|---------|
| GET  | `/wp-json/wpupdater/v1/status` | core/plugin/theme versions + available updates + auto-update state |
| POST | `/wp-json/wpupdater/v1/auto-updates` (`enable=true/false`) | turn WordPress auto-updates on/off for all plugins & themes |
| POST | `/wp-json/wpupdater/v1/update` (`targets=core,plugins,themes`) | apply pending updates |
| GET  | `/wp-json/wpupdater/v1/ping` | health/auth check |

Requires WordPress with a writable filesystem and PHP 7.4+.

---

## 2. Add your sites

In the dashboard click **+ Add site**, then enter each site's **Name**, **URL**,
**API key** (from step 1) and an optional **Group**. The site is scanned
immediately so its row populates right away. To stop monitoring a site, use the
**Remove** action — the trash icon in the Sites table row, or the **Remove**
button in the site details drawer. Removing a site deletes its stored scan
history in WP Updater only; it does not touch the WordPress site itself.

A built-in **Help** page (in the left sidebar) walks through connecting sites,
scanning, deploying updates and editing a site.

---

## Configuration

Everything is configured with environment variables. The scan schedule,
SMTP / email reporting and Telegram notifications can also be configured live
in the **Settings** page (the environment variables below just seed the
initial values).

The **Settings → Schedule** section offers an advanced scheduler — pick
**Hourly**, **Daily**, **Several times a day**, **Weekly**, **Monthly**, or a
**Custom cron** expression. Internally the schedule is stored as a standard
5-field cron string (`scan_cron` setting); the legacy `WPUPDATER_SCAN_HOUR` /
`_MINUTE` values are only used as the initial daily default, so upgrading an
existing install keeps the previous 06:00 daily scan until you change it.
Running a scan more than once a day is the recommended way to catch updates
that are published partway through the day.

| Variable | Default | Notes |
|----------|---------|-------|
| `TZ` | `UTC` | Local timezone for the scheduler (e.g. `Europe/Zagreb`) |
| `WPUPDATER_PORT` | `8090` | Port inside the container (map it to any host port) |
| `WPUPDATER_SECRET_KEY` | — | Flask session key; set a long random value |
| `WPUPDATER_USER` / `WPUPDATER_PASSWORD` | empty | Optional HTTP basic auth |
| `WPUPDATER_VERIFY_TLS` | `true` | Set `false` only for self-signed site certs |
| `WPUPDATER_REQUEST_TIMEOUT` | `30` | Per-request timeout (seconds) |
| `WPUPDATER_SCAN_ENABLED` | `true` | Enable the automatic scheduled scan |
| `WPUPDATER_SCAN_HOUR` / `_MINUTE` | `6` / `0` | Initial daily scan time (local `TZ`); seeds the default cron. Change the cadence in **Settings → Schedule** |
| `SMTP_HOST` … `REPORT_RECIPIENTS` | empty | Email reporting (see `.env.example`) |
| `TELEGRAM_BOT_TOKEN` / `TELEGRAM_CHAT_ID` | empty | Telegram notifications (see `.env.example`) |

Data (SQLite DB + generated reports) is stored in the mounted `/data` volume and
survives container rebuilds.

### Securing the dashboard

The GUI has **no login by default**. Either:

- set `WPUPDATER_USER` / `WPUPDATER_PASSWORD` for HTTP basic auth (this also
  protects the `/api/*` endpoints), **or**
- place it behind your existing reverse proxy / SSO.

Each site uses its own 64-char API key sent in a request header over HTTPS; keep
`WPUPDATER_VERIFY_TLS=true` and rotate keys any time from the site's
**Settings → WP Updater** page.

---

## Features

- **Dashboard overview** — a per-site table with pending core/plugin/theme counts,
  WordPress version, connector version, last scan and status. Opening a site shows a
  details drawer with an expandable list of exactly what needs updating.
- **Clickable summary tiles** — Core / Plugin / Theme / Sites-with-updates open the
  **Updates** page on the matching tab; **Failed / partial** opens the **Activity Log**.
- **Manual scans** — "Scan all" and per-site scan. "Scan all" also sends the
  configured email / Telegram reports just like a scheduled run (honouring the
  "only when updates are pending" setting), so you get a notification right away.
- **Advanced scheduled scans** — choose hourly, daily, several times a day,
  weekly, monthly, or a custom cron expression in the **Settings** page. The
  Settings page shows a human-readable description and the next run time.
- **Automatic email reports** via SMTP, sent after every scheduled or "Scan
  all" run; configurable in the **Settings** page (or via environment
  variables), with an optional "only when updates are pending" mode and a
  **Send test** button.
- **Telegram notifications** sent after every scheduled or "Scan all" run;
  configure the bot token and chat ID in the **Settings** page and send a test
  message.
- Email and Telegram each send **one cumulative message** summarising every
  selected site, and you can choose **per-site** which sites are included from
  the site details drawer.
- **Vulnerability scanning (WPScan)** — optionally cross-references each site's
  installed core, plugin and theme versions against the
  [WPScan](https://wpscan.com/api) vulnerability database and flags
  known-vulnerable versions with a red shield badge on the **Sites** page.
  A **green shield** means the site was scanned and is clean; open a site's
  details drawer to see the last-checked time and, when present, the exact
  findings (title, installed → fixed-in version, CVE IDs). Run a scan on demand
  with **Settings → Security → Scan vulnerabilities now**. Lookups are cached per
  slug (default 24h) to respect the free tier's ~25 requests/day budget.
- **Post-update health check** — after applying updates WP Updater fetches the
  site's public home page and flags it if it returns a 5xx or a WordPress
  "critical error" (a coloured health dot appears on the **Sites** page and a
  Telegram alert is sent). Note: automatic rollback is **not** performed — that
  needs a backup mechanism the connector does not provide — so restore from your
  own backups if a site breaks.
- **Pending-update age** — the **Updates** page shows how long each update has
  been outstanding (e.g. `9d`), and the oldest pending age is tracked per site,
  so long-ignored updates stand out.
- **Weekly digest** — an optional periodic roll-up (email and/or Telegram) with
  pending updates per site, oldest pending age, known vulnerabilities, site
  health and how many updates were applied in the last 7 days. Configure the
  schedule and channels under **Settings → Weekly digest**.
- **HTML / Markdown reports** available at `/report.html` and `/report.md`.
- **Per-site auto-update** checkbox (real WordPress auto-updates, not just a flag).
- **One-click "Update all"** per site, and **per-item updates** — update a single
  plugin, theme, or core on its own with a live "Updating…" indicator. On the
  **Updates** page you can tick checkboxes and **Update selected** to apply them
  **sequentially, one after another**.
- **Edit a site** in place (name, URL, group, optional new API key). The **pencil**
  in the Sites table opens the details drawer **directly in edit mode**.
- **Connector version** column so you can see which sites run the latest connector.
- **Activity log** with status badges, durations, expandable error details and
  **Retry** for failed/partial actions. A failed entry can be marked
  **Resolved** to clear it from the dashboard **Failed / partial** tile while
  keeping the log entry intact; a successful update for a site also clears its
  outstanding errors automatically.
- **Dark mode** (persisted), empty states, loading skeletons and toast notifications.
- **Opt-in application update checks** with installed/latest versions, stable release notes, and copyable commands for published-image or local-source deployments.

The UI is deliberately scoped to **updating WordPress core, plugins and themes
only** — no security scanning, uptime, backups, analytics, SEO, billing or client
management.

---

## Running from source

### Dashboard (Docker, build locally)

```bash
git clone https://github.com/marinfrankovic/WP_Updater.git
cd WP_Updater
cp .env.example .env          # set WPUPDATER_SECRET_KEY, TZ, optional auth + SMTP
mkdir -p data && sudo chown -R 10001:10001 data
docker compose up -d --build  # multi-stage build compiles the SPA, no Node needed
```

`compose.yaml` builds the image locally from the `Dockerfile`. The first build
compiles the React SPA in a Node stage, then ships it inside the Python runtime.

### Frontend dev server

```bash
cd frontend
npm install
npm run dev      # http://127.0.0.1:5174 (proxies /api to http://127.0.0.1:8090)
npm run build    # type-check (tsc -b) + build into ../app/webui
```

Set `VITE_API_TARGET` to point the dev proxy at a remote backend if needed.

Stack: React 19, TypeScript (strict), Vite, `lucide-react` icons, React Context +
`useReducer`, a single tokenised global stylesheet (`src/styles/index.css`).
Domain types in `src/types/index.ts` are the contract between the SPA and the
Flask API. Backend: Flask + gunicorn, stdlib SQLite, an in-process scheduler
thread, no external services.

### Tests

Install the pinned development requirements and run backend tests:

```bash
python -m pip install -r requirements-dev.txt
python -m pytest
```

GitHub Actions runs the Python tests and the production frontend build on pushes to `main` and pull requests.

**JSON API** (consumed by the SPA, basic-auth protected like the GUI):

| Method | Endpoint | Purpose |
|--------|----------|---------|
| GET    | `/api/state` | full state: sites, available updates, activity log |
| GET    | `/api/app-info` | installed dashboard version and update commands; no external request |
| GET    | `/api/app-update` | installed/latest stable release information and update commands |
| GET / POST | `/api/schedule` | read / change the scan schedule (cron) + on-off |
| POST   | `/api/sites` (`name,url,apiKey,group`) | add a site + immediate scan |
| PATCH  | `/api/sites/<id>` (`name,url,group,apiKey`) | edit site (blank apiKey keeps current) |
| DELETE | `/api/sites/<id>` | remove a site and its history |
| POST   | `/api/sites/<id>/scan` | rescan one site |
| POST   | `/api/sites/<id>/auto-update` (`enabled`) | toggle real WordPress auto-updates |
| POST   | `/api/sites/<id>/update` (`scope`) | update core/plugin/theme/all |
| POST   | `/api/sites/<id>/update-item` (`type,slug`) | update a single plugin/theme/core |
| POST   | `/api/scan-all` | rescan every enabled site |
| POST   | `/api/bulk-update` (`siteIds,scope`) | update many sites at once |

---

## How it works

```
┌────────────┐    HTTPS + X-WPUpdater-Key     ┌────────────────────┐
│ Dashboard  │  ───────────────────────────▶  │  WP site connector │
│  (Flask)   │   GET /status                  │   (mu-plugin)      │
│  Docker    │  ◀───────────────────────────  │                    │
└────┬───────┘    JSON: versions + updates     └────────────────────┘
     │
     ├─ SQLite (sites, scans, settings)
     ├─ Scheduler thread → cron-scheduled scan + email/Telegram
     └─ Reports (HTML / Markdown)
```

---

## Releasing (maintainers)

Pushing a `vX.Y.Z` tag triggers the **Publish to Docker Hub** GitHub Action, which
builds and pushes a multi-arch image to `mfrankovic/wp-updater` (`:X.Y.Z`,
`:X.Y`, `:latest`). Attach the matching `wp-updater-connector.php` to the GitHub
Release so the Help page link resolves to it.

Create a GitHub Release for every stable tag. The in-app checker reads GitHub's latest stable release endpoint, so pushing only a tag is not enough to announce an update.

Requires two repository secrets: `DOCKERHUB_USERNAME` and a `DOCKERHUB_TOKEN`
access token with Read/Write scope.

## License

[MIT](LICENSE)
