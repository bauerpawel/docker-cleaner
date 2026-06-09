# Docker Cleaner 🧹

> [English](README.md) · **Polski**

Narzędziowy obraz Dockera, który czyści **nieużywane obrazy**. Działa w dwóch trybach przełączanych zmienną `MODE`:

- **`web`** — panel WWW z listą nieużywanych obrazów, ręcznym zaznaczaniem/usuwaniem oraz konfiguracją automatycznego czyszczenia wg harmonogramu.
- **`console`** — bez panelu; demon, który cyklicznie czyści obrazy wg interwału lub crona.

## Uruchomienie z Docker Hub

Obraz jest opublikowany jako [`pbauer/docker-cleaner`](https://hub.docker.com/r/pbauer/docker-cleaner) (multi-arch: `linux/amd64` + `linux/arm64`) — pobierasz i uruchamiasz od razu, bez budowania.

### Panel WWW

```bash
docker run -d --name docker-cleaner \
  -p 8080:8080 \
  -v /var/run/docker.sock:/var/run/docker.sock \
  -v "$(pwd)/data:/data" \
  pbauer/docker-cleaner:latest
```

Otwórz <http://localhost:8080> i ustaw harmonogram oraz zakres czyszczenia z panelu — albo zdefiniuj je z góry zmiennymi środowiskowymi poniżej.

### Tryb konsolowy (harmonogram, bez panelu)

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

### Stack Portainer / docker compose

```yaml
services:
  docker-cleaner:
    image: pbauer/docker-cleaner:latest
    environment:
      MODE: web
      AUTO_CLEAN: "true"           # uruchom harmonogram także w trybie web
      # --- czas czyszczenia (harmonogram) ---
      CLEAN_INTERVAL: 24h          # co 24h, 30m, 7d, 90s …
      # CLEAN_CRON: "0 3 * * *"    # …albo wyrażenie cron (ma pierwszeństwo)
      # --- co czyścić ---
      CLEAN_SCOPE: all             # dangling | all
      CLEAN_BUILD_CACHE: "true"    # czyść też build cache
      MIN_AGE: 168h                # tylko obrazy starsze niż próg
    ports:
      - "8080:8080"
    volumes:
      - /var/run/docker.sock:/var/run/docker.sock
      - /opt/docker-cleaner/data:/data
    restart: unless-stopped
```

**Czas czyszczenia (harmonogram):** `CLEAN_INTERVAL` uruchamia czyszczenie co N czasu (`30m`, `24h`, `7d`, `90s`). Dla stałej pory dnia użyj `CLEAN_CRON` (np. `0 3 * * *` = codziennie o 03:00) — ma pierwszeństwo przed interwałem. Dla crona ustaw `TZ` (np. `Europe/Warsaw`). W trybie `web` harmonogram działa tylko gdy `AUTO_CLEAN=true` (lub po włączeniu w panelu); w trybie `console` jest zawsze aktywny.

**Co czyścić:** `CLEAN_SCOPE` wybiera `dangling` (nieotagowane pozostałości) lub `all` (każdy obraz nieużywany przez żaden kontener). `CLEAN_BUILD_CACHE=true` dodatkowo czyści build cache. `MIN_AGE` chroni świeże obrazy — usuwane są tylko starsze niż próg (`0h` wyłącza ochronę).

> **Windows / Docker Desktop (kontenery Linux):** socket podaj jako `-v //var/run/docker.sock:/var/run/docker.sock` (podwójny ukośnik), a w PowerShell użyj `${PWD}` zamiast `$(pwd)`.

## Budowanie samodzielnie

### Panel WWW

```bash
docker build -t docker-cleaner .

docker run -d --name docker-cleaner \
  -p 8080:8080 \
  -v /var/run/docker.sock:/var/run/docker.sock \
  -v "$(pwd)/data:/data" \
  docker-cleaner
```

Otwórz <http://localhost:8080>.

> **Windows / Docker Desktop (kontenery Linux):** ścieżkę socketu podaj jako `-v //var/run/docker.sock:/var/run/docker.sock` (podwójny ukośnik) i użyj `${PWD}` zamiast `$(pwd)` w PowerShell.

### Tryb konsolowy

```bash
docker run -d --name docker-cleaner-console \
  -e MODE=console \
  -e CLEAN_INTERVAL=24h \
  -e MIN_AGE=168h \
  -v /var/run/docker.sock:/var/run/docker.sock \
  -v "$(pwd)/data:/data" \
  docker-cleaner
```

Albo przez `docker compose`:

```bash
docker compose --profile web up --build        # panel
docker compose --profile console up --build     # tryb konsolowy
```

## Konfiguracja (zmienne środowiskowe)

| Zmienna | Domyślnie | Opis |
|---|---|---|
| `MODE` | `web` | `web` (panel) lub `console` (demon) |
| `WEB_PORT` | `8080` | port panelu WWW |
| `WEB_AUTH_ENABLED` | — | jawny włącznik logowania; gdy nieustawiony, auth włącza się automatycznie po podaniu loginu i hasła |
| `WEB_AUTH_USER` / `WEB_AUTH_PASSWORD` | — | dane do Basic Auth (wymagane, gdy logowanie włączone) |
| `CLEAN_SCOPE` | `dangling` | `dangling` (nieotagowane `<none>`) lub `all` (każdy obraz bez kontenera, jak `docker image prune -a`) |
| `CLEAN_BUILD_CACHE` | `false` | czyść też build cache (`docker builder prune`) |
| `MIN_AGE` | `168h` | usuwaj tylko obrazy **starsze** niż próg (chroni świeżo zbudowane); `0h` = bez progu |
| `AUTO_CLEAN` | `false` (web) / `true` (console) | włącza harmonogram |
| `CLEAN_INTERVAL` | `24h` | interwał czyszczenia, gdy brak crona (`30m`, `24h`, `7d`, `90s`) |
| `CLEAN_CRON` | — | wyrażenie cron (np. `0 3 * * *`); **ma pierwszeństwo** przed interwałem |
| `DATA_DIR` | `/data` | katalog na `settings.json` i `cleanup.log` (zamontuj jako wolumen, aby ustawienia przetrwały restart) |
| `TZ` | `UTC` | strefa czasu dla crona (np. `Europe/Warsaw`) |

W trybie **web** ustawienia zmienione w panelu zapisują się do `DATA_DIR/settings.json` i nadpisują zmienne środowiskowe po restarcie.

## Definicja „nieużywany"

- **`dangling`** — obrazy bez tagów (`<none>:<none>`), zwykle warstwy po przebudowach.
- **`all`** — wszystkie obrazy, do których nie odwołuje się żaden kontener (działający ani zatrzymany).

Wybór jest dostępny zarówno w panelu, jak i przez `CLEAN_SCOPE`.

## API panelu

| Metoda | Ścieżka | Opis |
|---|---|---|
| `GET` | `/` | panel HTML |
| `GET` | `/api/images?scope=dangling\|all` | lista nieużywanych obrazów |
| `POST` | `/api/images/delete` | `{"ids": [...], "force": false}` |
| `POST` | `/api/clean/run` | uruchom czyszczenie teraz wg ustawień |
| `GET` / `PUT` | `/api/settings` | odczyt / zapis ustawień auto-czyszczenia |
| `GET` | `/api/status` | stan, następne uruchomienie, miejsce do odzyskania |
| `GET` | `/healthz` | health check |

## Bezpieczeństwo

Kontener potrzebuje dostępu do socketu Dockera (`/var/run/docker.sock`), co jest równoważne dostępowi roota na hoście — uruchamiaj go tylko w zaufanym środowisku. Panel domyślnie jest otwarty; w sieci współdzielonej włącz Basic Auth (`WEB_AUTH_USER` + `WEB_AUTH_PASSWORD`). Zabezpieczenia przed przypadkowym usunięciem: próg wieku (`MIN_AGE`), ręczne potwierdzenie usunięcia w panelu oraz log operacji w `DATA_DIR/cleanup.log`.

## Rozwój

```bash
pip install -r requirements-dev.txt
pytest
```
