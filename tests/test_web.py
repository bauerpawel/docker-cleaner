"""Testy endpointów panelu WWW (TestClient + atrapa Dockera)."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.config import RuntimeConfig, Settings
from app.docker_client import DockerUnavailableError
from app.web.app import create_app

from .conftest import FakeDockerClient, make_image


class UnavailableClient(FakeDockerClient):
    def list_unused_images(self, scope="dangling"):
        raise DockerUnavailableError("Brak /var/run/docker.sock")


def test_api_images_returns_503_when_docker_unavailable(tmp_path):
    settings = Settings(mode="web", data_dir=str(tmp_path))
    runtime = RuntimeConfig.from_settings(settings)
    app = create_app(settings, runtime, docker_client=UnavailableClient())
    with TestClient(app) as client:
        res = client.get("/api/images")
    assert res.status_code == 503
    assert "docker.sock" in res.json()["detail"]


def build_client(tmp_path, settings_kwargs=None, images=None):
    settings = Settings(mode="web", data_dir=str(tmp_path), **(settings_kwargs or {}))
    runtime = RuntimeConfig.from_settings(settings)
    fake = FakeDockerClient(images=images or [])
    app = create_app(settings, runtime, docker_client=fake)
    return TestClient(app), fake, runtime


def test_healthz_ok(tmp_path):
    client, _fake, _rt = build_client(tmp_path)
    with client:
        res = client.get("/healthz")
    assert res.status_code == 200
    assert res.json()["status"] == "ok"


def test_list_images(tmp_path):
    images = [make_image("a", tags=["x:1"], size=2000), make_image("b", size=1000)]
    client, _fake, _rt = build_client(tmp_path, images=images)
    with client:
        res = client.get("/api/images")
    assert res.status_code == 200
    data = res.json()
    assert data["count"] == 2
    # sortowane malejąco po rozmiarze
    assert data["images"][0]["id"] == "a"


def test_delete_images(tmp_path):
    images = [make_image("a"), make_image("b")]
    client, fake, _rt = build_client(tmp_path, images=images)
    with client:
        res = client.post("/api/images/delete", json={"ids": ["a"]})
    assert res.status_code == 200
    assert res.json()["removed"] == ["a"]
    assert fake.removed == ["a"]


def test_delete_reports_errors(tmp_path):
    images = [make_image("a")]
    settings = Settings(mode="web", data_dir=str(tmp_path))
    runtime = RuntimeConfig.from_settings(settings)
    fake = FakeDockerClient(images=images, fail_ids=["a"])
    app = create_app(settings, runtime, docker_client=fake)
    with TestClient(app) as client:
        res = client.post("/api/images/delete", json={"ids": ["a"]})
    assert res.status_code == 200
    body = res.json()
    assert body["removed"] == []
    assert len(body["errors"]) == 1


def test_get_and_update_settings_persist(tmp_path):
    client, _fake, _rt = build_client(tmp_path)
    with client:
        res = client.get("/api/settings")
        assert res.status_code == 200

        update = {
            "auto_clean": True,
            "clean_scope": "all",
            "clean_build_cache": True,
            "min_age": "48h",
            "clean_interval": "6h",
            "clean_cron": None,
        }
        res = client.put("/api/settings", json=update)
        assert res.status_code == 200
        assert res.json()["saved"] is True
        assert res.json()["next_run"] is not None

        # Po zapisie odczyt zwraca nowe wartości.
        res = client.get("/api/settings")
        assert res.json()["clean_scope"] == "all"

    # Plik settings.json został zapisany w data_dir.
    assert (tmp_path / "settings.json").exists()


def test_update_settings_rejects_bad_cron(tmp_path):
    client, _fake, _rt = build_client(tmp_path)
    with client:
        res = client.put("/api/settings", json={
            "auto_clean": True,
            "clean_scope": "dangling",
            "clean_build_cache": False,
            "min_age": "168h",
            "clean_interval": "24h",
            "clean_cron": "totally invalid",
        })
    assert res.status_code == 400


def test_basic_auth_required_when_configured(tmp_path):
    client, _fake, _rt = build_client(
        tmp_path,
        settings_kwargs={"web_auth_user": "admin", "web_auth_password": "secret"},
    )
    with client:
        res = client.get("/api/images")
        assert res.status_code == 401

        res = client.get("/api/images", auth=("admin", "secret"))
        assert res.status_code == 200

        res = client.get("/api/images", auth=("admin", "wrong"))
        assert res.status_code == 401
