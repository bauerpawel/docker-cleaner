"""Testy logiki czyszczenia — filtry wieku/scope, usuwanie, build cache."""

from __future__ import annotations

from app.cleaner import run_cleanup, select_images_to_remove
from app.config import RuntimeConfig

from .conftest import FakeDockerClient, make_image


# --- select_images_to_remove (czysta funkcja) -------------------------------

def test_select_filters_out_images_younger_than_threshold():
    images = [
        make_image("old", age_seconds=1000),
        make_image("young", age_seconds=10),
    ]
    selected = select_images_to_remove(images, min_age_seconds=100)
    ids = [i["id"] for i in selected]
    assert ids == ["old"]


def test_select_with_zero_threshold_keeps_all():
    images = [make_image("a", age_seconds=1), make_image("b", age_seconds=None)]
    selected = select_images_to_remove(images, min_age_seconds=0)
    assert len(selected) == 2


def test_select_drops_images_with_unknown_age_when_threshold_set():
    images = [make_image("unknown", age_seconds=None)]
    assert select_images_to_remove(images, min_age_seconds=100) == []


# --- run_cleanup ------------------------------------------------------------

def _config(**overrides) -> RuntimeConfig:
    base = dict(
        auto_clean=True,
        clean_scope="dangling",
        clean_build_cache=False,
        min_age="0h",
        clean_interval="24h",
        clean_cron=None,
    )
    base.update(overrides)
    return RuntimeConfig(**base)


def test_run_cleanup_removes_matching_images(tmp_path):
    client = FakeDockerClient(images=[
        make_image("img1", size=2000, age_seconds=10_000),
        make_image("img2", size=3000, age_seconds=10_000),
    ])
    summary = run_cleanup(client, _config(), data_dir=str(tmp_path))

    assert summary["removed_count"] == 2
    assert summary["reclaimed_bytes"] == 5000
    assert set(client.removed) == {"img1", "img2"}


def test_run_cleanup_respects_min_age(tmp_path):
    client = FakeDockerClient(images=[
        make_image("old", size=2000, age_seconds=10_000),
        make_image("fresh", size=3000, age_seconds=5),
    ])
    summary = run_cleanup(client, _config(min_age="1h"), data_dir=str(tmp_path))

    assert summary["removed_count"] == 1
    assert client.removed == ["old"]


def test_run_cleanup_dry_run_removes_nothing(tmp_path):
    client = FakeDockerClient(images=[make_image("img1", size=2000, age_seconds=10_000)])
    summary = run_cleanup(client, _config(), data_dir=str(tmp_path), dry_run=True)

    assert summary["dry_run"] is True
    assert summary["removed_count"] == 1
    assert client.removed == []  # nic faktycznie nie usunięto


def test_run_cleanup_records_errors(tmp_path):
    client = FakeDockerClient(
        images=[make_image("ok", age_seconds=10_000), make_image("bad", age_seconds=10_000)],
        fail_ids=["bad"],
    )
    summary = run_cleanup(client, _config(), data_dir=str(tmp_path))

    assert summary["removed_count"] == 1
    assert client.removed == ["ok"]
    assert len(summary["errors"]) == 1
    assert summary["errors"][0]["id"] == "bad"


def test_run_cleanup_prunes_build_cache_when_enabled(tmp_path):
    client = FakeDockerClient(images=[make_image("img1", size=1000, age_seconds=10_000)])
    summary = run_cleanup(client, _config(clean_build_cache=True), data_dir=str(tmp_path))

    assert client.build_cache_pruned is True
    assert summary["build_cache_reclaimed_bytes"] == 5000
    assert summary["reclaimed_bytes"] == 6000  # 1000 obraz + 5000 cache


def test_run_cleanup_writes_log_line(tmp_path):
    client = FakeDockerClient(images=[make_image("img1", age_seconds=10_000)])
    run_cleanup(client, _config(), data_dir=str(tmp_path))

    log_file = tmp_path / "cleanup.log"
    assert log_file.exists()
    assert log_file.read_text(encoding="utf-8").count("\n") == 1
