from __future__ import annotations

from typing import Literal
from urllib.parse import urlparse

from pydantic import BaseModel, Field, field_validator


SUPPORTED_DOWNLOAD_SCHEMES = {"http", "https", "magnet", "bc"}


def normalize_download_link(download_link: str) -> str:
    link = download_link.strip()
    if not link:
        raise ValueError("download_link must not be empty")

    scheme = urlparse(link).scheme.lower()
    if scheme not in SUPPORTED_DOWNLOAD_SCHEMES:
        raise ValueError("download_link must use http, https, magnet, or bc scheme")

    return link


def normalize_optional_save_path(save_path: str | None) -> str | None:
    if save_path is None:
        return None
    path = save_path.strip()
    return path or None


class SearchRequest(BaseModel):
    identifier: str | None = Field(default=None, description="Optional media ID")
    query: str | None = Field(default=None, description="Optional search keywords")
    categories: list[int] | None = Field(default=None, description="Optional Prowlarr category IDs")
    indexer_ids: list[int] | None = Field(default=None, description="Optional Prowlarr indexer IDs")


class SearchResult(BaseModel):
    title: str
    download_link: str
    size: int | None = None
    seeders: int | None = None
    leechers: int | None = None
    grabs: int | None = None
    indexer: str | None = None
    protocol: str | None = None
    publish_date: str | None = None
    info_hash: str | None = None


class DownloadRequest(BaseModel):
    download_link: str
    save_path: str | None = Field(default=None, description="Optional qBittorrent save path override")

    @field_validator("download_link")
    @classmethod
    def validate_download_link(cls, value: str) -> str:
        return normalize_download_link(value)

    @field_validator("save_path")
    @classmethod
    def validate_save_path(cls, value: str | None) -> str | None:
        return normalize_optional_save_path(value)


class DownloadResponse(BaseModel):
    status: Literal["success"] = "success"
    message: str = "Download queued"


HandleMode = Literal["auto", "manual", "confirm"]


class HandleRequest(BaseModel):
    user_message: str = Field(description="Natural-language title, IMDb ID, IMDb URL, or search phrase")
    user_id: str | None = Field(default=None, description="Optional caller/user identifier")
    save_path: str | None = Field(default=None, description="Optional qBittorrent save path override")
    mode: HandleMode | None = Field(
        default=None,
        description=(
            "Output mode. 'auto' (default) downloads the best release when confident; "
            "'manual' always returns ranked results without downloading; "
            "'confirm' returns the top pick plus alternatives without downloading. "
            "When omitted, the server uses QBITLARR_DEFAULT_MODE."
        ),
    )

    @field_validator("user_message")
    @classmethod
    def validate_user_message(cls, value: str) -> str:
        message = value.strip()
        if not message:
            raise ValueError("user_message must not be empty")
        return message

    @field_validator("user_id")
    @classmethod
    def validate_user_id(cls, value: str | None) -> str | None:
        if value is None:
            return None
        user_id = value.strip()
        return user_id or None

    @field_validator("save_path")
    @classmethod
    def validate_save_path(cls, value: str | None) -> str | None:
        return normalize_optional_save_path(value)

    @field_validator("mode", mode="before")
    @classmethod
    def validate_mode(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip().lower()
        if not normalized:
            return None
        if normalized not in ("auto", "manual", "confirm"):
            raise ValueError("mode must be 'auto', 'manual', or 'confirm'")
        return normalized


class ManualSearchResult(BaseModel):
    index: int
    title: str
    quality: str
    seeders: int | None = None
    size: int | None = None
    download_link: str


class HandleResponse(BaseModel):
    status: Literal["success", "not_found"]
    action: Literal["auto_download", "show_results", "confirm"]
    message: str
    query_id: str | None = None
    snapshot_status: str | None = None
    title: str | None = None
    quality: str | None = None
    results: list[ManualSearchResult] | None = None
    alternatives: list[ManualSearchResult] | None = Field(
        default=None,
        description=(
            "Ranked runner-up releases. Populated on auto_download and confirm actions "
            "so callers can offer alternatives without a second query lookup."
        ),
    )


class QuerySnapshotEntry(BaseModel):
    version: int
    reason: str
    created_at: str
    results: list[SearchResult]


class QuerySnapshot(BaseModel):
    query_id: str
    status: str
    created_at: str
    updated_at: str
    request: dict
    snapshots: list[QuerySnapshotEntry]


class TorrentStatus(BaseModel):
    name: str
    state: str
    progress: float
    size: int
    seeds: int
    hash: str
    download_speed: int | None = None
    eta: int | None = None


class ProwlarrIndexer(BaseModel):
    id: int
    name: str | None = None
    enabled: bool | None = None
    protocol: str | None = None
