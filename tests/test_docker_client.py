"""Testy parsowania metadanych obrazu z formatu docker-py."""

from __future__ import annotations

from datetime import datetime, timezone

import docker
import pytest

from app.docker_client import DockerClient, DockerUnavailableError, image_info, parse_created


def test_client_is_lazy_and_reports_unavailable(monkeypatch):
    def boom(*_a, **_k):
        raise docker.errors.DockerException("no socket")

    monkeypatch.setattr(docker, "from_env", boom)
    client = DockerClient()          # konstrukcja nie łączy się — nie rzuca
    assert client.ping() is False    # ping łyka błąd
    with pytest.raises(DockerUnavailableError):
        _ = client.client            # dostęp do klienta daje czytelny błąd


def test_parse_created_handles_nanoseconds_and_z():
    dt = parse_created("2024-01-15T10:20:30.123456789Z")
    assert dt == datetime(2024, 1, 15, 10, 20, 30, 123456, tzinfo=timezone.utc)


def test_parse_created_without_fraction():
    dt = parse_created("2024-01-15T10:20:30Z")
    assert dt.tzinfo is not None
    assert dt.year == 2024


def test_parse_created_none():
    assert parse_created(None) is None
    assert parse_created("") is None


class _FakeImage:
    def __init__(self, image_id, tags, attrs):
        self.id = image_id
        self.short_id = "sha256:" + image_id[:12]
        self.tags = tags
        self.attrs = attrs


def test_image_info_shape():
    img = _FakeImage(
        "abcdef1234567890",
        ["repo:tag"],
        {"Created": "2024-01-15T10:20:30Z", "Size": 12345},
    )
    info = image_info(img)
    assert info["id"] == "abcdef1234567890"
    assert info["short_id"] == "abcdef123456"
    assert info["tags"] == ["repo:tag"]
    assert info["size"] == 12345
    assert info["age_seconds"] is not None and info["age_seconds"] > 0
