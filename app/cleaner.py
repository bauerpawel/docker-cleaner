"""Logika czyszczenia obrazów — współdzielona przez tryb web i konsolowy."""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone
from typing import List, Optional

from .config import parse_duration

logger = logging.getLogger("docker_cleaner.cleaner")

CLEANUP_LOG_FILENAME = "cleanup.log"


def select_images_to_remove(images: List[dict], min_age_seconds: int) -> List[dict]:
    """Odfiltrowuje obrazy młodsze niż próg wieku.

    Czysta funkcja — serce logiki, łatwa do przetestowania.
    Gdy ``min_age_seconds <= 0`` próg nie obowiązuje i przechodzą wszystkie obrazy.
    """
    if min_age_seconds <= 0:
        return list(images)
    selected = []
    for img in images:
        age = img.get("age_seconds")
        if age is None or age < min_age_seconds:
            continue
        selected.append(img)
    return selected


def run_cleanup(docker_client, config, data_dir: Optional[str] = None, dry_run: bool = False) -> dict:
    """Wykonuje pełny cykl czyszczenia i zwraca podsumowanie.

    Kroki: lista kandydatów wg scope → filtr wieku → usunięcie (lub policzenie
    przy dry-run) → opcjonalny prune build cache → wpis do logu.
    """
    min_age_seconds = parse_duration(config.min_age)
    images = docker_client.list_unused_images(config.clean_scope)
    candidates = select_images_to_remove(images, min_age_seconds)

    removed: List[dict] = []
    errors: List[dict] = []
    reclaimed = 0

    for img in candidates:
        size = int(img.get("size", 0) or 0)
        if dry_run:
            removed.append(img)
            reclaimed += size
            continue
        try:
            docker_client.remove_image(img["id"], force=False)
            removed.append(img)
            reclaimed += size
        except Exception as exc:  # noqa: BLE001 — raportujemy błąd na obraz, nie przerywamy
            errors.append({"id": img["id"], "error": str(exc)})
            logger.warning("Nie udało się usunąć %s: %s", img.get("short_id", img["id"]), exc)

    cache_reclaimed = 0
    if config.clean_build_cache and not dry_run:
        try:
            result = docker_client.prune_build_cache()
            cache_reclaimed = int(result.get("SpaceReclaimed", 0) or 0)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Czyszczenie build cache nieudane: %s", exc)

    summary = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "scope": config.clean_scope,
        "dry_run": dry_run,
        "removed_count": len(removed),
        "removed": [
            {"id": img["id"], "tags": img.get("tags", []), "size": int(img.get("size", 0) or 0)}
            for img in removed
        ],
        "reclaimed_bytes": reclaimed + cache_reclaimed,
        "build_cache_reclaimed_bytes": cache_reclaimed,
        "errors": errors,
    }

    _append_log(data_dir, summary)
    logger.info(
        "Czyszczenie zakończone: usunięto %d obrazów, odzyskano %.1f MB%s",
        summary["removed_count"],
        summary["reclaimed_bytes"] / 1_000_000,
        " [dry-run]" if dry_run else "",
    )
    return summary


def _append_log(data_dir: Optional[str], summary: dict) -> None:
    """Dopisuje jedną linię JSON do pliku logu czyszczeń."""
    if not data_dir:
        return
    try:
        os.makedirs(data_dir, exist_ok=True)
        path = os.path.join(data_dir, CLEANUP_LOG_FILENAME)
        with open(path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(summary, ensure_ascii=False) + "\n")
    except OSError as exc:
        logger.warning("Nie udało się zapisać logu czyszczenia: %s", exc)
