"""Tryb konsolowy: demon czyszczący obrazy wg harmonogramu, bez panelu WWW."""

from __future__ import annotations

import logging
import signal
import threading

from .cleaner import run_cleanup
from .docker_client import DockerClient
from .scheduler import CleanupScheduler

logger = logging.getLogger("docker_cleaner.console")


def run_console(settings, runtime, docker_client=None) -> None:
    client = docker_client if docker_client is not None else DockerClient()

    # W trybie konsolowym czyszczenie cykliczne jest sensem działania.
    runtime.auto_clean = True

    logger.info(
        "Tryb konsolowy uruchomiony. scope=%s, min_age=%s, %s, build_cache=%s",
        runtime.clean_scope,
        runtime.min_age,
        f"cron={runtime.clean_cron}" if runtime.clean_cron else f"interwał={runtime.clean_interval}",
        runtime.clean_build_cache,
    )

    def job() -> None:
        run_cleanup(client, runtime, data_dir=settings.data_dir)

    # Pierwsze czyszczenie od razu po starcie — natychmiastowa informacja zwrotna.
    job()

    scheduler = CleanupScheduler(job, timezone=settings.tz)
    scheduler.start(runtime)
    logger.info("Następne czyszczenie: %s", scheduler.next_run())

    stop = threading.Event()

    def handle_signal(signum, _frame):
        logger.info("Otrzymano sygnał %s — zamykanie.", signum)
        stop.set()

    signal.signal(signal.SIGTERM, handle_signal)
    signal.signal(signal.SIGINT, handle_signal)

    try:
        while not stop.wait(1.0):
            pass
    finally:
        scheduler.shutdown()
        logger.info("Zatrzymano.")
