"""Cienki wrapper nad docker-py.

Cała reszta aplikacji rozmawia z Dockerem wyłącznie przez ten moduł, dzięki
czemu logikę da się testować na atrapie (fake) bez prawdziwego demona.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import List, Optional

import docker

_CREATED_RE = re.compile(
    r"^(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2})(?:\.(\d+))?(.*)$"
)


def parse_created(raw: Optional[str]) -> Optional[datetime]:
    """Parsuje pole ``Created`` Dockera (z nanosekundami i ``Z``) na datetime UTC."""
    if not raw:
        return None
    text = str(raw).strip().replace("Z", "+00:00")
    match = _CREATED_RE.match(text)
    if not match:
        return None
    base, frac, tz = match.groups()
    if frac:
        frac = (frac + "000000")[:6]  # ucinamy nanosekundy do mikrosekund
        base = f"{base}.{frac}"
    try:
        dt = datetime.fromisoformat(base + (tz or ""))
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def image_info(image) -> dict:
    """Buduje serializowalny opis obrazu z obiektu docker-py ``Image``."""
    attrs = getattr(image, "attrs", {}) or {}
    created = parse_created(attrs.get("Created"))
    now = datetime.now(timezone.utc)
    age_seconds = (now - created).total_seconds() if created else None
    short_id = (getattr(image, "short_id", "") or "").replace("sha256:", "")
    return {
        "id": image.id,
        "short_id": short_id,
        "tags": list(getattr(image, "tags", []) or []),
        "size": int(attrs.get("Size", 0) or 0),
        "created": created.isoformat() if created else None,
        "age_seconds": age_seconds,
    }


class DockerClient:
    """Operacje na obrazach potrzebne aplikacji."""

    def __init__(self, client=None):
        self.client = client if client is not None else docker.from_env()

    # -- odczyt ---------------------------------------------------------------

    def list_unused_images(self, scope: str = "dangling") -> List[dict]:
        if scope == "all":
            images = self._all_unused_images()
        else:
            images = self.client.images.list(filters={"dangling": True})
        return [image_info(img) for img in images]

    def _all_unused_images(self) -> list:
        """Obrazy, do których nie odwołuje się żaden kontener (running/stopped)."""
        used_ids = set()
        for container in self.client.containers.list(all=True):
            image = getattr(container, "image", None)
            if image is not None and getattr(image, "id", None):
                used_ids.add(image.id)
        return [img for img in self.client.images.list() if img.id not in used_ids]

    def disk_usage(self) -> dict:
        return self.client.df()

    def ping(self) -> bool:
        return bool(self.client.ping())

    # -- zapis ----------------------------------------------------------------

    def remove_image(self, image_id: str, force: bool = False) -> None:
        self.client.images.remove(image=image_id, force=force, noprune=False)

    def prune_build_cache(self) -> dict:
        result = self.client.api.prune_builds()
        return result if isinstance(result, dict) else {}
