# WP Updater

A small, self-hosted, **MainWP-style** dashboard that scans the WordPress sites
you run and reports available **core, plugin, and theme updates** — with a simple
web GUI, scheduled scans, email reports, per-site **auto-update** toggles, and
optional one-click "update all".

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

Everything is configured with environment variables; scheduler and SMTP settings
are also editable live in the **Settings** page.

| Variable | Default | Notes |
|----------|---------|-------|
| `TZ` | `UTC` | Local timezone for the scheduler (e.g. `Europe/Zagreb`) |
| `WPUPDATER_PORT` | `8090` | Port inside the container (map it to any host port) |
| `WPUPDATER_SECRET_KEY` | — | Flask session key; set a long random value |
| `WPUPDATER_USER` / `WPUPDATER_PASSWORD` | empty | Optional HTTP basic auth |
| `WPUPDATER_VERIFY_TLS` | `true` | Set `false` only for self-signed site certs |
| `WPUPDATER_REQUEST_TIMEOUT` | `30` | Per-request timeout (seconds) |
| `WPUPDATER_SCAN_ENABLED` | `true` | Enable the daily automatic scan |
| `WPUPDATER_SCAN_HOUR` / `_MINUTE` | `6` / `0` | Daily scan time (local `TZ`) |
| `SMTP_HOST` … `REPORT_RECIPIENTS` | empty | Email reporting (see `.env.example`) |

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

- **Dashboard cards** per site: pending core/plugin/theme counts, WP/PHP version,
  expandable list of exactly what needs updating.
- **Clickable summary tiles** — Core / Plugin / Theme / Sites-with-updates open the
  **Updates** page on the matching tab; **Failed / partial** opens the **Activity Log**.
- **Scan all now** (with optional "email report after scan") and **per-site scan**.
- **Scheduled daily scan** at a configurable time (Settings page).
- **Email reports** via SMTP — to dashboard recipients and/or each opted-in site's
  admin; optionally only when updates are pending. Includes a **Send test email**.
- **Downloadable report** as HTML (`/report.html`) or Markdown (`/report.md`).
- **Per-site auto-update** checkbox (real WordPress auto-updates, not just a flag).
- **One-click "Update all"** per site, and **per-item updates** — update a single
  plugin, theme, or core on its own with a live "Updating…" indicator. On the
  **Updates** page you can tick checkboxes and **Update selected** to apply them
  **sequentially, one after another**.
- **Edit a site** in place (name, URL, group, optional new API key). The **pencil**
  in the Sites table opens the details drawer **directly in edit mode**.
- **Connector version** column so you can see which sites run the latest connector.
- **Activity log** with status badges, durations, expandable error details and
  **Retry** for failed/partial actions.
- **Dark mode** (persisted), empty states, loading skeletons and toast notifications.

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

**JSON API** (consumed by the SPA, basic-auth protected like the GUI):

| Method | Endpoint | Purpose |
|--------|----------|---------|
| GET    | `/api/state` | full state: sites, available updates, activity log |
| GET / POST | `/api/schedule` | read / change the daily scan time + on-off |
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
     ├─ Scheduler thread → daily scan + email
     └─ Reports (HTML / Markdown)
```

---

## Releasing (maintainers)

Pushing a `vX.Y.Z` tag triggers the **Publish to Docker Hub** GitHub Action, which
builds and pushes a multi-arch image to `mfrankovic/wp-updater` (`:X.Y.Z`,
`:X.Y`, `:latest`). Attach the matching `wp-updater-connector.php` to the GitHub
Release so the Help page link resolves to it.

Requires two repository secrets: `DOCKERHUB_USERNAME` and a `DOCKERHUB_TOKEN`
access token with Read/Write scope.

## License

[MIT](LICENSE)
