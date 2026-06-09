"""Testy konfiguracji — parsowanie czasu, scalanie env + settings.json."""

from __future__ import annotations

import pytest

from app.config import (
    RuntimeConfig,
    Settings,
    load_runtime_config,
    parse_duration,
    save_runtime_config,
    validate_runtime,
)


@pytest.mark.parametrize(
    "value,expected",
    [
        ("90s", 90),
        ("30m", 1800),
        ("24h", 86400),
        ("7d", 604800),
        ("120", 120),  # bez jednostki = sekundy
        ("  2h ", 7200),
    ],
)
def test_parse_duration(value, expected):
    assert parse_duration(value) == expected


def test_parse_duration_invalid():
    with pytest.raises(ValueError):
        parse_duration("abc")


def test_runtime_from_settings_console_defaults_auto_clean_true():
    settings = Settings(mode="console", data_dir="/tmp/x")
    runtime = RuntimeConfig.from_settings(settings)
    assert runtime.auto_clean is True


def test_runtime_from_settings_web_defaults_auto_clean_false():
    settings = Settings(mode="web", data_dir="/tmp/x")
    runtime = RuntimeConfig.from_settings(settings)
    assert runtime.auto_clean is False


def test_explicit_auto_clean_env_overrides_mode_default():
    settings = Settings(mode="console", auto_clean=False, data_dir="/tmp/x")
    assert RuntimeConfig.from_settings(settings).auto_clean is False


def test_save_and_load_runtime_roundtrip(tmp_path):
    settings = Settings(mode="web", data_dir=str(tmp_path))
    config = RuntimeConfig.from_settings(settings)
    config.auto_clean = True
    config.clean_scope = "all"
    config.clean_interval = "12h"
    save_runtime_config(settings, config)

    # Nowy odczyt powinien odtworzyć zapisane wartości (nadpisując env).
    loaded = load_runtime_config(settings)
    assert loaded.auto_clean is True
    assert loaded.clean_scope == "all"
    assert loaded.clean_interval == "12h"


def test_load_runtime_uses_env_when_no_file(tmp_path):
    settings = Settings(mode="web", clean_scope="all", data_dir=str(tmp_path))
    loaded = load_runtime_config(settings)
    assert loaded.clean_scope == "all"


def test_validate_runtime_accepts_valid_cron():
    config = RuntimeConfig(clean_cron="0 3 * * *")
    assert validate_runtime(config) is None


def test_validate_runtime_rejects_bad_cron():
    config = RuntimeConfig(clean_cron="not a cron")
    assert validate_runtime(config) is not None


def test_validate_runtime_rejects_bad_interval():
    config = RuntimeConfig(clean_interval="soon")
    assert validate_runtime(config) is not None


# --- logowanie do panelu (WEB_AUTH_ENABLED) ---------------------------------

def test_auth_auto_enabled_when_credentials_present():
    s = Settings(mode="web", web_auth_user="a", web_auth_password="b", data_dir="/tmp/x")
    assert s.auth_enabled is True
    assert s.auth_misconfigured is False


def test_auth_off_when_no_credentials_and_no_toggle():
    s = Settings(mode="web", data_dir="/tmp/x")
    assert s.auth_required is False
    assert s.auth_enabled is False


def test_toggle_false_overrides_credentials():
    s = Settings(
        mode="web", web_auth_enabled=False,
        web_auth_user="a", web_auth_password="b", data_dir="/tmp/x",
    )
    assert s.auth_required is False
    assert s.auth_enabled is False


def test_toggle_true_without_credentials_is_misconfigured():
    s = Settings(mode="web", web_auth_enabled=True, data_dir="/tmp/x")
    assert s.auth_required is True
    assert s.auth_enabled is False
    assert s.auth_misconfigured is True
