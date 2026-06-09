# Docker Cleaner 🧹

Clean up **unused Docker images** — on demand or on a schedule. A single, lightweight, multi-arch image that runs in either of two modes:

- **`web`** — a web panel that lists unused images so you can select & delete them, and configure scheduled automatic cleanup.
- **`console`** — a headless daemon that periodically cleans images on an interval or cron schedule.

The web panel is bilingual (English / Polish, switcher in the top‑right corner).

## Supported tags

- `latest` — latest build from the `main` branch
- `x.y.z` — released versions (e.g. `1.0.0`)

**Architectures:** `linux/amd64`, `linux/arm64`

## Quick start

### Web panel

```bash
docker run -d --name docker-cleaner \
  -p 8080:8080 \
  -v /var/run/docker.sock:/var/run/docker.sock \
  -v docker-cleaner-data:/data \
  pbauer/docker-cleaner:latest
```

Open <http://localhost:8080>.

### Console mode (scheduled, no panel)

```bash
docker run -d --name docker-cleaner \
  -e MODE=console \
  -e CLEAN_INTERVAL=24h \
  -e CLEAN_SCOPE=all \
  -e MIN_AGE=168h \
  -v /var/run/docker.sock:/var/run/docker.sock \
  pbauer/docker-cleaner:latest
```

### docker compose

```yaml
services:
  docker-cleaner:
    image: pbauer/docker-cleaner:latest
    environment:
      MODE: web
    ports:
      - "8080:8080"
    volumes:
      - /var/run/docker.sock:/var/run/docker.sock
      - docker-cleaner-data:/data
    restart: unless-stopped

volumes:
  docker-cleaner-data:
```

> **Windows / Docker Desktop (Linux containers):** pass the socket as `//var/run/docker.sock:/var/run/docker.sock` (double slash).

## Configuration (environment variables)

| Variable | Default | Description |
|---|---|---|
| `MODE` | `web` | `web` (panel) or `console` (daemon) |
| `WEB_PORT` | `8080` | web panel port |
| `WEB_AUTH_ENABLED` | — | explicit on/off switch for login; if unset, auth turns on once a user + password are set |
| `WEB_AUTH_USER` / `WEB_AUTH_PASSWORD` | — | credentials for Basic Auth (required when login is enabled) |
| `CLEAN_SCOPE` | `dangling` | `dangling` (untagged `<none>`) or `all` (every image not used by any container) |
| `CLEAN_BUILD_CACHE` | `false` | also prune the build cache |
| `MIN_AGE` | `168h` | only remove images **older** than this threshold; `0h` disables the guard |
| `AUTO_CLEAN` | `false` (web) / `true` (console) | enables the scheduler |
| `CLEAN_INTERVAL` | `24h` | cleanup interval when no cron is set (`30m`, `24h`, `7d`, `90s`) |
| `CLEAN_CRON` | — | cron expression (e.g. `0 3 * * *`); **takes precedence** over the interval |
| `DATA_DIR` | `/data` | directory for `settings.json` and `cleanup.log` (mount a volume to persist) |
| `TZ` | `UTC` | time zone for cron (e.g. `Europe/Warsaw`) |

In **web** mode, settings changed in the panel are saved to `DATA_DIR/settings.json` and override the environment variables after a restart.

## What "unused" means

- **`dangling`** — images without tags (`<none>:<none>`), typically leftover layers from rebuilds.
- **`all`** — every image not referenced by any container (running or stopped), like `docker image prune -a`.

## Security

The container needs access to the Docker socket (`/var/run/docker.sock`), which is equivalent to root on the host — run it only in a trusted environment. The panel is open by default; on a shared network enable Basic Auth with `WEB_AUTH_ENABLED=true` + `WEB_AUTH_USER` / `WEB_AUTH_PASSWORD`. Accidental‑deletion guards: the age threshold (`MIN_AGE`), manual delete confirmation in the panel, and an operation log in `DATA_DIR/cleanup.log`.

## Source & issues

Full documentation, source code and issue tracker:
**https://github.com/bauerpawel/docker-cleaner**
