from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache

from app.domain.quality import (
    DEFAULT_PREFER_CODEC,
    DEFAULT_PREFER_RESOLUTION,
    DEFAULT_PREFER_SOURCE,
    MIN_AUTO_DOWNLOAD_SEEDERS,
    QualityPreferences,
)
from app.exceptions import ConfigurationError


@dataclass(frozen=True)
class Settings:
    prowlarr_url: str
    prowlarr_download_url: str | None
    prowlarr_api_key: str
    qbit_url: str
    qbit_username: str
    qbit_password: str
    request_timeout_seconds: float = 30.0
    query_snapshot_dir: str = "data/query-snapshots"
    prowlarr_primary_indexer_ids: list[int] | None = None
    prowlarr_fallback_indexer_ids: list[int] | None = None
    qbitlarr_api_key: str | None = None
    qbitlarr_save_path_movie: str = "/downloads/movies"
    qbitlarr_save_path_movie_4k: str = "/downloads/movies-4k"
    qbitlarr_save_path_tv: str = "/downloads/tv"
    qbitlarr_extra_save_paths: list[str] | None = None
    prefer_resolution: str = DEFAULT_PREFER_RESOLUTION
    prefer_source: str = DEFAULT_PREFER_SOURCE
    prefer_codec: str = DEFAULT_PREFER_CODEC
    min_seeders: int = MIN_AUTO_DOWNLOAD_SEEDERS
    default_mode: str = "auto"

    @property
    def quality_preferences(self) -> QualityPreferences:
        return QualityPreferences(
            resolution=self.prefer_resolution,
            source=self.prefer_source,
            codec=self.prefer_codec,
            min_seeders=self.min_seeders,
        )

    @classmethod
    def from_env(cls) -> "Settings":
        return cls(
            prowlarr_url=_required_env("PROWLARR_URL").rstrip("/"),
            prowlarr_download_url=_optional_env("PROWLARR_DOWNLOAD_URL"),
            prowlarr_api_key=_required_env("PROWLARR_API_KEY"),
            qbit_url=_required_env("QBIT_URL").rstrip("/"),
            qbit_username=_required_env("QBIT_USERNAME"),
            qbit_password=_required_env("QBIT_PASSWORD"),
            request_timeout_seconds=float(os.getenv("REQUEST_TIMEOUT_SECONDS", "30")),
            query_snapshot_dir=os.getenv("QBITLARR_QUERY_SNAPSHOT_DIR", "data/query-snapshots"),
            prowlarr_primary_indexer_ids=_optional_int_list("PROWLARR_PRIMARY_INDEXER_IDS"),
            prowlarr_fallback_indexer_ids=_optional_int_list("PROWLARR_FALLBACK_INDEXER_IDS"),
            qbitlarr_api_key=_optional_str_env("QBITLARR_API_KEY"),
            qbitlarr_save_path_movie=_env_with_default("QBITLARR_SAVE_PATH_MOVIE", "/downloads/movies"),
            qbitlarr_save_path_movie_4k=_env_with_default("QBITLARR_SAVE_PATH_MOVIE_4K", "/downloads/movies-4k"),
            qbitlarr_save_path_tv=_env_with_default("QBITLARR_SAVE_PATH_TV", "/downloads/tv"),
            qbitlarr_extra_save_paths=_optional_str_list("QBITLARR_EXTRA_SAVE_PATHS"),
            prefer_resolution=_env_with_default("QBITLARR_PREFER_RESOLUTION", DEFAULT_PREFER_RESOLUTION),
            prefer_source=_env_with_default("QBITLARR_PREFER_SOURCE", DEFAULT_PREFER_SOURCE),
            prefer_codec=_env_with_default("QBITLARR_PREFER_CODEC", DEFAULT_PREFER_CODEC),
            min_seeders=int(os.getenv("QBITLARR_MIN_SEEDERS", str(MIN_AUTO_DOWNLOAD_SEEDERS))),
            default_mode=_env_with_default("QBITLARR_DEFAULT_MODE", "auto").lower(),
        )


def _required_env(name: str) -> str:
    value = os.getenv(name)
    if value is None or not value.strip():
        raise ConfigurationError(f"Missing required environment variable: {name}")
    return value.strip()


def _optional_env(name: str) -> str | None:
    value = os.getenv(name)
    if value is None or not value.strip():
        return None
    return value.strip().rstrip("/")


def _optional_str_env(name: str) -> str | None:
    value = os.getenv(name)
    if value is None or not value.strip():
        return None
    return value.strip()


def _env_with_default(name: str, default: str) -> str:
    value = os.getenv(name)
    if value is None or not value.strip():
        return default
    return value.strip()


def _optional_int_list(name: str) -> list[int] | None:
    value = os.getenv(name)
    if value is None or not value.strip():
        return None
    return [int(part.strip()) for part in value.split(",") if part.strip()]


def _optional_str_list(name: str) -> list[str] | None:
    value = os.getenv(name)
    if value is None or not value.strip():
        return None
    return [part.strip() for part in value.split(",") if part.strip()]


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings.from_env()
