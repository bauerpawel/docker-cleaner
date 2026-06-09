# Docker Cleaner 🧹

> **English** · [Polski](README.pl.md)

A Docker utility image that removes **unused Docker images**. It runs in two modes, switched with the `MODE` variable:

- **`web`** — a web panel listing unused images, with manual select/delete and configuration of scheduled automatic cleanup.
- **`console`** — no panel; a daemon that periodically cleans images on an interval or cron schedule.

## Run from Docker Hub

The image is published at [`pbauer/docker-cleaner`](https://hub.docker.com/r/pbauer/docker-cleaner) (multi-arch: `linux/amd64` + `linux/arm64`) — pull and run it directly, no build needed.

The fastest way is the included ready-to-run [`docker-compose.hub.yml`](docker-compose.hub.yml):

```bash
docker compose -f docker-compose.hub.yml up -d
```

### Web panel

```bash
docker run -d --name docker-cleaner \
  -p 8080:8080 \
  -v /var/run/docker.sock:/var/run/docker.sock \
  -v "$(pwd)/data:/data" \
  pbauer/docker-cleaner:latest
```

Open <http://localhost:8080> and set the schedule and what to clean from the panel — or preset them with the environment variables below.

### Console mode (scheduled, no panel)

```bash
docker run -d --name docker-cleaner \
  -e MODE=console \
  -e CLEAN_INTERVAL=24h \
  -e CLEAN_SCOPE=all \
  -e MIN_AGE=168h \
  -e CLEAN_BUILD_CACHE=true \
  -v /var/run/docker.sock:/var/run/docker.sock \
  pbauer/docker-cleaner:latest
```

### Portainer / docker compose stack

```yaml
services:
  docker-cleaner:
    image: pbauer/docker-cleaner:latest
    environment:
      MODE: web
      AUTO_CLEAN: "true"           # run the schedule in web mode too
      # --- cleaning time (schedule) ---
      CLEAN_INTERVAL: 24h          # every 24h, 30m, 7d, 90s …
      # CLEAN_CRON: "0 3 * * *"    # …or a cron expression (takes precedence)
      # --- what to clean ---
      CLEAN_SCOPE: all             # dangling | all
      CLEAN_BUILD_CACHE: "true"    # also prune build cache
      MIN_AGE: 168h                # only images older than this
    ports:
      - "8080:8080"
    volumes:
      - /var/run/docker.sock:/var/run/docker.sock
      - /opt/docker-cleaner/data:/data
    restart: unless-stopped
```

**Cleaning time (schedule):** `CLEAN_INTERVAL` runs cleanup every N time (`30m`, `24h`, `7d`, `90s`). For a fixed time of day use `CLEAN_CRON` (e.g. `0 3 * * *` = daily at 03:00) — it takes precedence over the interval. Set `TZ` (e.g. `Europe/Warsaw`) for cron. In `web` mode the schedule runs only when `AUTO_CLEAN=true` (or after you enable it in the panel); in `console` mode it is always on.

**What to clean:** `CLEAN_SCOPE` selects `dangling` (untagged leftovers) or `all` (every image not used by any container). `CLEAN_BUILD_CACHE=true` additionally prunes the build cache. `MIN_AGE` protects fresh images — only ones older than the threshold are removed (`0h` disables the guard).

> **Windows / Docker Desktop (Linux containers):** pass the socket as `-v //var/run/docker.sock:/var/run/docker.sock` (double slash) and use `${PWD}` instead of `$(pwd)` in PowerShell.

## Build it yourself

### Web panel

```bash
docker build -t docker-cleaner .

docker run -d --name docker-cleaner \
  -p 8080:8080 \
  -v /var/run/docker.sock:/var/run/docker.sock \
  -v "$(pwd)/data:/data" \
  docker-cleaner
```

Open <http://localhost:8080>.

> **Windows / Docker Desktop (Linux containers):** pass the socket path as `-v //var/run/docker.sock:/var/run/docker.sock` (double slash) and use `${PWD}` instead of `$(pwd)` in PowerShell.

### Console mode

```bash
docker run -d --name docker-cleaner-console \
  -e MODE=console \
  -e CLEAN_INTERVAL=24h \
  -e MIN_AGE=168h \
  -v /var/run/docker.sock:/var/run/docker.sock \
  -v "$(pwd)/data:/data" \
  docker-cleaner
```

Or via `docker compose`:

```bash
docker compose --profile web up --build        # panel
docker compose --profile console up --build     # console mode
```

## Configuration (environment variables)

| Variable | Default | Description |
|---|---|---|
| `MODE` | `web` | `web` (panel) or `console` (daemon) |
| `WEB_PORT` | `8080` | web panel port |
| `WEB_AUTH_ENABLED` | — | explicit on/off switch for login; if unset, auth turns on automatically once a user + password are set |
| `WEB_AUTH_USER` / `WEB_AUTH_PASSWORD` | — | credentials for Basic Auth (required when login is enabled) |
| `CLEAN_SCOPE` | `dangling` | `dangling` (untagged `<none>`) or `all` (any image with no container, like `docker image prune -a`) |
| `CLEAN_BUILD_CACHE` | `false` | also prune build cache (`docker builder prune`) |
| `MIN_AGE` | `168h` | only remove images **older** than this threshold (protects freshly built ones); `0h` = no threshold |
| `AUTO_CLEAN` | `false` (web) / `true` (console) | enables the scheduler |
| `CLEAN_INTERVAL` | `24h` | cleanup interval when no cron is set (`30m`, `24h`, `7d`, `90s`) |
| `CLEAN_CRON` | — | cron expression (e.g. `0 3 * * *`); **takes precedence** over the interval |
| `DATA_DIR` | `/data` | directory for `settings.json` and `cleanup.log` (mount as a volume so settings survive restarts) |
| `TZ` | `UTC` | time zone for cron (e.g. `Europe/Warsaw`) |

In **web** mode, settings changed in the panel are saved to `DATA_DIR/settings.json` and override the environment variables after a restart.

## What "unused" means

- **`dangling`** — images without tags (`<none>:<none>`), typically leftover layers from rebuilds.
- **`all`** — every image not referenced by any container (running or stopped).

The choice is available both in the panel and via `CLEAN_SCOPE`.

## Panel API

| Method | Path | Description |
|---|---|---|
| `GET` | `/` | HTML panel |
| `GET` | `/api/images?scope=dangling\|all` | list of unused images |
| `POST` | `/api/images/delete` | `{"ids": [...], "force": false}` |
| `POST` | `/api/clean/run` | run cleanup now using current settings |
| `GET` / `PUT` | `/api/settings` | read / write auto-cleanup settings |
| `GET` | `/api/status` | status, next run, reclaimable space |
| `GET` | `/healthz` | health check |

## Security

The container needs access to the Docker socket (`/var/run/docker.sock`), which is equivalent to root access on the host — run it only in a trusted environment. The panel is open by default; on a shared network enable Basic Auth (`WEB_AUTH_USER` + `WEB_AUTH_PASSWORD`). Guards against accidental deletion: the age threshold (`MIN_AGE`), manual delete confirmation in the panel, and an operation log in `DATA_DIR/cleanup.log`.

## Development

```bash
pip install -r requirements-dev.txt
pytest
```
