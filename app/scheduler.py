"""Harmonogram czyszczenia oparty o APScheduler (interwał lub cron)."""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Callable, Optional
from zoneinfo import ZoneInfo

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

from .config import parse_duration

logger = logging.getLogger("docker_cleaner.scheduler")

JOB_ID = "cleanup"


def _resolve_timezone(name: str) -> ZoneInfo:
    try:
        return ZoneInfo(name)
    except Exception:  # noqa: BLE001 — nieznana strefa nie powinna blokować startu
        logger.warning("Nieznana strefa czasu %r, używam UTC", name)
        return ZoneInfo("UTC")


class CleanupScheduler:
    """Opakowuje pojedyncze zadanie czyszczenia w harmonogram APScheduler."""

    def __init__(self, job_func: Callable[[], object], timezone: str = "UTC"):
        self._tz = _resolve_timezone(timezone)
        self._scheduler = BackgroundScheduler(timezone=self._tz)
        self._job_func = job_func

    def _build_trigger(self, config):
        if getattr(config, "clean_cron", None):
            return CronTrigger.from_crontab(config.clean_cron, timezone=self._tz)
        seconds = parse_duration(config.clean_interval)
        return IntervalTrigger(seconds=seconds, timezone=self._tz)

    def start(self, config) -> None:
        if not self._scheduler.running:
            self._scheduler.start()
        self.apply(config)

    def apply(self, config) -> None:
        """Dodaje, aktualizuje lub usuwa zadanie zależnie od ``auto_clean``."""
        existing = self._scheduler.get_job(JOB_ID)
        if getattr(config, "auto_clean", False):
            trigger = self._build_trigger(config)
            self._scheduler.add_job(
                self._job_func, trigger=trigger, id=JOB_ID, replace_existing=True
            )
            logger.info(
                "Zaplanowano czyszczenie (%s)",
                config.clean_cron if getattr(config, "clean_cron", None) else f"co {config.clean_interval}",
            )
        elif existing is not None:
            self._scheduler.remove_job(JOB_ID)
            logger.info("Automatyczne czyszczenie wyłączone")

    def next_run(self) -> Optional[datetime]:
        job = self._scheduler.get_job(JOB_ID)
        return job.next_run_time if job else None

    def shutdown(self) -> None:
        if self._scheduler.running:
            self._scheduler.shutdown(wait=False)
