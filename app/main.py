"""Punkt wejścia — wybiera tryb na podstawie zmiennej środowiskowej MODE."""

from __future__ import annotations

import logging
import sys

from .config import Settings, load_runtime_config


def configure_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )


def main() -> None:
    configure_logging()
    settings = Settings()
    runtime = load_runtime_config(settings)
    mode = settings.mode.strip().lower()

    if mode == "console":
        from .console import run_console

        run_console(settings, runtime)
    elif mode == "web":
        from .web.app import run_web

        run_web(settings, runtime)
    else:
        print(
            f"Nieznany MODE={settings.mode!r}. Użyj 'web' lub 'console'.",
            file=sys.stderr,
        )
        sys.exit(2)


if __name__ == "__main__":
    main()
