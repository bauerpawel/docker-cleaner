# Docker Cleaner 🧹

> **English** · [Polski](README.pl.md)

A Docker utility image that removes **unused Docker images**. It runs in two modes, switched with the `MODE` variable:

- **`web`** — a web panel listing unused images, with manual select/delete and configuration of scheduled automatic cleanup.
- **`console`** — no panel; a daemon that periodically cleans images on an interval or cron schedule.

## Quick start

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
| `WEB_AUTH_USER` / `WEB_AUTH_PASSWORD` | — | set **both** to enable Basic Auth on the panel |
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
