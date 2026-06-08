"""Wspólne atrapy dla testów."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import List


def make_image(image_id: str, *, tags=None, size=1000, age_seconds=None) -> dict:
    """Buduje opis obrazu w formacie zwracanym przez DockerClient."""
    created = None
    if age_seconds is not None:
        created = (datetime.now(timezone.utc) - timedelta(seconds=age_seconds)).isoformat()
    return {
        "id": image_id,
        "short_id": image_id[:12],
        "tags": list(tags or []),
        "size": size,
        "created": created,
        "age_seconds": age_seconds,
    }


class FakeDockerClient:
    """Atrapa DockerClient sterowana z testów."""

    def __init__(self, images: List[dict] | None = None, fail_ids=None):
        self._images = {img["id"]: img for img in (images or [])}
        self._fail_ids = set(fail_ids or [])
        self.removed: List[str] = []
        self.build_cache_pruned = False
        self.ping_ok = True

    def list_unused_images(self, scope: str = "dangling") -> List[dict]:
        return list(self._images.values())

    def remove_image(self, image_id: str, force: bool = False) -> None:
        if image_id in self._fail_ids:
            raise RuntimeError("image is being used by stopped container")
        if image_id not in self._images:
            raise RuntimeError("No such image")
        self.removed.append(image_id)
        del self._images[image_id]

    def prune_build_cache(self) -> dict:
        self.build_cache_pruned = True
        return {"SpaceReclaimed": 5000}

    def disk_usage(self) -> dict:
        return {"Images": [{"Size": 1000, "Containers": 0}]}

    def ping(self) -> bool:
        return self.ping_ok
