"""Konfiguracja aplikacji.

Dwie warstwy:
  * ``Settings``      — niezmienne ustawienia z env (tryb, port, auth, ścieżki),
  * ``RuntimeConfig`` — zmienny podzbiór konfiguracji czyszczenia, który można
                        modyfikować z panelu WWW i zapisać trwale do
                        ``DATA_DIR/settings.json``.
"""

from __future__ import annotations

import json
import os
import re
from typing import Literal, Optional

from croniter import croniter
from pydantic import BaseModel
from pydantic_settings import BaseSettings, SettingsConfigDict

SETTINGS_FILENAME = "settings.json"

_DURATION_UNITS = {"s": 1, "m": 60, "h": 3600, "d": 86400}
_DURATION_RE = re.compile(r"^\s*(\d+)\s*([smhd]?)\s*$", re.IGNORECASE)


def parse_duration(value: str | int) -> int:
    """Zamienia zapis typu ``24h``/``30m``/``7d``/``90s``/``120`` na sekundy.

    Sama liczba (bez jednostki) jest traktowana jako sekundy.
    """
    text = str(value).strip().lower()
    match = _DURATION_RE.match(text)
    if not match:
        raise ValueError(f"Nieprawidłowy czas: {value!r} (użyj np. 24h, 30m, 7d, 90s)")
    number, unit = match.groups()
    return int(number) * _DURATION_UNITS.get(unit or "s", 1)


class Settings(BaseSettings):
    """Ustawienia wczytywane ze zmiennych środowiskowych."""

    model_config = SettingsConfigDict(env_file=None, extra="ignore", case_sensitive=False)

    mode: str = "web"
    web_port: int = 8080
    web_auth_enabled: Optional[bool] = None
    web_auth_user: Optional[str] = None
    web_auth_password: Optional[str] = None

    clean_scope: Literal["dangling", "all"] = "dangling"
    clean_build_cache: bool = False
    min_age: str = "168h"
    auto_clean: Optional[bool] = None
    clean_interval: str = "24h"
    clean_cron: Optional[str] = None

    data_dir: str = "/data"
    tz: str = "UTC"

    @property
    def has_auth_credentials(self) -> bool:
        return bool(self.web_auth_user and self.web_auth_password)

    @property
    def auth_required(self) -> bool:
        """Czy logowanie ma być wymagane.

        Jawny ``WEB_AUTH_ENABLED`` ma pierwszeństwo; gdy nieustawiony — auth
        włącza się automatycznie po podaniu loginu i hasła (zachowanie domyślne).
        """
        if self.web_auth_enabled is not None:
            return self.web_auth_enabled
        return self.has_auth_credentials

    @property
    def auth_enabled(self) -> bool:
        """Czy logowanie jest faktycznie egzekwowane (wymaga też danych)."""
        return self.auth_required and self.has_auth_credentials

    @property
    def auth_misconfigured(self) -> bool:
        """Auth zażądany jawnie, ale bez kompletu login+hasło."""
        return self.auth_required and not self.has_auth_credentials

    @property
    def settings_path(self) -> str:
        return os.path.join(self.data_dir, SETTINGS_FILENAME)


class RuntimeConfig(BaseModel):
    """Zmienny podzbiór konfiguracji czyszczenia (edytowalny z panelu)."""

    auto_clean: bool = False
    clean_scope: Literal["dangling", "all"] = "dangling"
    clean_build_cache: bool = False
    min_age: str = "168h"
    clean_interval: str = "24h"
    clean_cron: Optional[str] = None

    @classmethod
    def from_settings(cls, settings: "Settings") -> "RuntimeConfig":
        auto_clean = settings.auto_clean
        if auto_clean is None:
            # W trybie konsolowym czyszczenie cykliczne ma sens domyślnie.
            auto_clean = settings.mode.lower() == "console"
        cron = settings.clean_cron or None
        return cls(
            auto_clean=auto_clean,
            clean_scope=settings.clean_scope,
            clean_build_cache=settings.clean_build_cache,
            min_age=settings.min_age,
            clean_interval=settings.clean_interval,
            clean_cron=cron,
        )


def validate_runtime(config: "RuntimeConfig | object") -> Optional[str]:
    """Zwraca komunikat błędu lub ``None`` gdy konfiguracja jest poprawna."""
    try:
        parse_duration(config.min_age)
    except ValueError as exc:
        return f"min_age: {exc}"
    try:
        parse_duration(config.clean_interval)
    except ValueError as exc:
        return f"clean_interval: {exc}"
    if getattr(config, "clean_cron", None):
        if not croniter.is_valid(config.clean_cron):
            return f"clean_cron: nieprawidłowe wyrażenie cron {config.clean_cron!r}"
    return None


def load_runtime_config(settings: "Settings") -> "RuntimeConfig":
    """Buduje konfigurację z env i nadpisuje ją wartościami z settings.json."""
    config = RuntimeConfig.from_settings(settings)
    path = settings.settings_path
    if os.path.isfile(path):
        try:
            with open(path, "r", encoding="utf-8") as fh:
                data = json.load(fh)
            stored = {k: v for k, v in data.items() if k in RuntimeConfig.model_fields}
            config = config.model_copy(update=stored)
        except (json.JSONDecodeError, OSError):
            # Uszkodzony plik nie powinien blokować startu — używamy env.
            pass
    return config


def save_runtime_config(settings: "Settings", config: "RuntimeConfig") -> None:
    """Zapisuje zmienny podzbiór konfiguracji do settings.json."""
    os.makedirs(settings.data_dir, exist_ok=True)
    with open(settings.settings_path, "w", encoding="utf-8") as fh:
        json.dump(config.model_dump(), fh, indent=2, ensure_ascii=False)
