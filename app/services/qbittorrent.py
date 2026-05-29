from __future__ import annotations

import asyncio
import hashlib
import logging
import re
from collections import OrderedDict
from dataclasses import dataclass
from urllib.parse import parse_qs, parse_qsl, urlencode, urlparse, urlunparse

import httpx
import qbittorrentapi

from app.config import Settings
from app.domain.torrent_metadata import parse_torrent_info_hash
from app.exceptions import UpstreamServiceError
from app.models import TorrentStatus


logger = logging.getLogger("qbitlarr-api.qbittorrent")
_TORRENT_FILE_CACHE_MAX_ENTRIES = 200
_TORRENT_FILE_CACHE: OrderedDict[str, bytes] = OrderedDict()
_REQUESTER_TAG_PREFIX = "requester."
_REQUESTER_TAG_MAX_LENGTH = 64


@dataclass(frozen=True)
class TorrentAddPayload:
    kwargs: dict
    info_hash: str | None = None


async def add_download_to_qbittorrent(
    download_link: str,
    settings: Settings,
    *,
    save_path: str | None = None,
    requester_id: str | None = None,
) -> TorrentStatus | None:
    payload = await _build_torrent_add_payload(download_link, settings)
    requester_tag = _requester_tag_for_user(requester_id)

    def add_download_sync() -> tuple[str, TorrentStatus | None]:
        with qbittorrentapi.Client(
            host=settings.qbit_url,
            username=settings.qbit_username,
            password=settings.qbit_password,
        ) as qbit_client:
            qbit_client.auth_log_in()
            if payload.info_hash and _torrent_exists(qbit_client, payload.info_hash):
                _apply_requester_tag(qbit_client, payload.info_hash, requester_tag)
                _apply_retention_policy(qbit_client, payload.info_hash, settings)
                logger.info("qBittorrent already has torrent hash=%s", payload.info_hash)
                return "Ok.", _get_torrent_status(qbit_client, payload.info_hash)

            add_kwargs = dict(payload.kwargs)
            if requester_tag:
                add_kwargs["tags"] = requester_tag

            result = qbit_client.torrents_add(**add_kwargs, save_path=save_path)
            if str(result).strip().lower() != "ok." and payload.info_hash and _torrent_exists(
                qbit_client,
                payload.info_hash,
            ):
                _apply_requester_tag(qbit_client, payload.info_hash, requester_tag)
                _apply_retention_policy(qbit_client, payload.info_hash, settings)
                logger.info("qBittorrent add result was non-OK but torrent hash=%s exists", payload.info_hash)
                return "Ok.", _get_torrent_status(qbit_client, payload.info_hash)
            if payload.info_hash:
                _apply_requester_tag(qbit_client, payload.info_hash, requester_tag)
                _apply_retention_policy(qbit_client, payload.info_hash, settings)
            return str(result), _get_torrent_status(qbit_client, payload.info_hash)

    try:
        result, status = await asyncio.to_thread(add_download_sync)
    except qbittorrentapi.LoginFailed as exc:
        logger.warning("qBittorrent login failed")
        raise UpstreamServiceError("qBittorrent login failed") from exc
    except qbittorrentapi.APIConnectionError as exc:
        logger.warning("qBittorrent request failed: %s", exc.__class__.__name__)
        raise UpstreamServiceError("qBittorrent is unreachable") from exc
    except qbittorrentapi.APIError as exc:
        logger.warning("qBittorrent API error: %s", exc.__class__.__name__)
        raise UpstreamServiceError("qBittorrent rejected the download") from exc

    if result.strip().lower() != "ok.":
        logger.warning("qBittorrent returned an unexpected add result")
        raise UpstreamServiceError("qBittorrent returned an unexpected response")

    logger.info("qBittorrent accepted download mode=%s save_path=%s", _add_mode(payload.kwargs), save_path or "default")
    return status


async def _build_torrent_add_payload(download_link: str, settings: Settings) -> TorrentAddPayload:
    if _should_upload_torrent_file(download_link):
        content = await _download_torrent_file(download_link, settings)
        return TorrentAddPayload(
            kwargs={"torrent_files": content},
            info_hash=parse_torrent_info_hash(content),
        )

    return TorrentAddPayload(
        kwargs={"urls": download_link},
        info_hash=_info_hash_from_magnet(download_link),
    )


def _should_upload_torrent_file(download_link: str) -> bool:
    return urlparse(download_link).scheme.lower() in {"http", "https"}


async def _download_torrent_file(download_link: str, settings: Settings) -> bytes:
    fetch_url = _download_url_with_prowlarr_api_key(download_link, settings)
    if fetch_url in _TORRENT_FILE_CACHE:
        _TORRENT_FILE_CACHE.move_to_end(fetch_url)
        return _TORRENT_FILE_CACHE[fetch_url]

    try:
        async with httpx.AsyncClient(timeout=settings.request_timeout_seconds, follow_redirects=True) as client:
            response = await client.get(fetch_url)
            response.raise_for_status()
    except httpx.HTTPError as exc:
        logger.warning("Torrent file fetch failed: %s", exc.__class__.__name__)
        raise UpstreamServiceError("Torrent file is unreachable") from exc

    content_type = response.headers.get("content-type", "").casefold()
    if "html" in content_type:
        logger.warning("Torrent file URL returned HTML content")
        raise UpstreamServiceError("Torrent URL returned HTML instead of torrent data")
    if not response.content:
        logger.warning("Torrent file URL returned an empty response")
        raise UpstreamServiceError("Torrent file response was empty")

    _cache_torrent_file(fetch_url, response.content)
    return response.content


def _cache_torrent_file(fetch_url: str, content: bytes) -> None:
    _TORRENT_FILE_CACHE[fetch_url] = content
    _TORRENT_FILE_CACHE.move_to_end(fetch_url)
    while len(_TORRENT_FILE_CACHE) > _TORRENT_FILE_CACHE_MAX_ENTRIES:
        _TORRENT_FILE_CACHE.popitem(last=False)


def _download_url_with_prowlarr_api_key(download_link: str, settings: Settings) -> str:
    parsed = urlparse(download_link)
    if parsed.scheme.lower() not in {"http", "https"}:
        return download_link
    if not _is_prowlarr_download_link(parsed, settings):
        return download_link

    api_key = getattr(settings, "prowlarr_api_key", None)
    if not api_key:
        return download_link

    query_pairs = parse_qsl(parsed.query, keep_blank_values=True)
    if any(key.lower() == "apikey" for key, _ in query_pairs):
        return download_link

    query_pairs.append(("apikey", api_key))
    return urlunparse(parsed._replace(query=urlencode(query_pairs)))


def _is_prowlarr_download_link(parsed, settings: Settings) -> bool:
    prowlarr_urls = [
        getattr(settings, "prowlarr_url", None),
        getattr(settings, "prowlarr_download_url", None),
    ]
    prowlarr_netlocs = {urlparse(url).netloc for url in prowlarr_urls if isinstance(url, str) and url.strip()}
    return parsed.netloc in prowlarr_netlocs and (
        parsed.path.startswith("/api/")
        or parsed.path.endswith("/download")
        or "/download/" in parsed.path
    )


def _info_hash_from_magnet(download_link: str) -> str | None:
    parsed = urlparse(download_link)
    if parsed.scheme.lower() != "magnet":
        return None

    for value in parse_qs(parsed.query).get("xt", []):
        if value.casefold().startswith("urn:btih:"):
            return value.rsplit(":", 1)[-1]

    return None


def _torrent_exists(qbit_client, info_hash: str) -> bool:
    return _get_torrent_status(qbit_client, info_hash) is not None


def _get_torrent_status(qbit_client, info_hash: str | None, *, tag: str | None = None) -> TorrentStatus | None:
    if not info_hash:
        return None

    target = info_hash.casefold()
    for torrent in _list_torrents(qbit_client, torrent_hashes=info_hash, tag=tag):
        if str(torrent.hash).casefold() == target:
            return _torrent_status_from_client_torrent(torrent)
    return None


def _torrent_status_from_client_torrent(torrent) -> TorrentStatus:
    return TorrentStatus(
        name=torrent.name,
        state=torrent.state,
        progress=round(torrent.progress, 4),
        size=torrent.size,
        seeds=torrent.num_seeds,
        hash=torrent.hash,
        download_speed=_optional_int(getattr(torrent, "dlspeed", None)),
        eta=_optional_int(getattr(torrent, "eta", None)),
    )


def _optional_int(value) -> int | None:
    if value is None:
        return None
    return int(value)


def _add_mode(add_kwargs: dict) -> str:
    if "torrent_files" in add_kwargs:
        return "file"
    if str(add_kwargs.get("urls", "")).startswith("magnet:"):
        return "magnet"
    return "url"


def _list_torrents(qbit_client, *, torrent_hashes: str | None = None, tag: str | None = None):
    kwargs = {}
    if torrent_hashes:
        kwargs["torrent_hashes"] = torrent_hashes
    if tag:
        kwargs["tag"] = tag
    return qbit_client.torrents_info(**kwargs)


def _apply_requester_tag(qbit_client, info_hash: str, requester_tag: str | None) -> None:
    if not requester_tag:
        return
    qbit_client.torrents_add_tags(tags=requester_tag, torrent_hashes=info_hash)


def _apply_retention_policy(qbit_client, info_hash: str, settings: Settings) -> None:
    if not getattr(settings, "retention_enabled", False):
        return

    ratio_limit = getattr(settings, "retention_ratio_limit", None)
    seeding_time_limit = getattr(settings, "retention_seeding_time_limit_minutes", None)
    if ratio_limit is None and seeding_time_limit is None:
        return

    try:
        qbit_client.torrents_set_share_limits(
            ratio_limit=ratio_limit,
            seeding_time_limit=seeding_time_limit,
            share_limit_action=getattr(settings, "retention_action", "Remove"),
            torrent_hashes=info_hash,
        )
    except qbittorrentapi.APIError as exc:
        logger.warning(
            "Could not apply retention policy for torrent hash=%s: %s",
            info_hash,
            exc.__class__.__name__,
        )


def _requester_tag_for_user(requester_id: str | None) -> str | None:
    if requester_id is None:
        return None

    normalized = requester_id.strip().casefold()
    if not normalized:
        return None

    sanitized = re.sub(r"[^a-z0-9._-]+", "-", normalized).strip("-._")
    if not sanitized:
        sanitized = hashlib.sha1(normalized.encode("utf-8")).hexdigest()[:12]

    tag = f"{_REQUESTER_TAG_PREFIX}{sanitized}"
    if len(tag) <= _REQUESTER_TAG_MAX_LENGTH:
        return tag

    digest = hashlib.sha1(normalized.encode("utf-8")).hexdigest()[:12]
    suffix_budget = _REQUESTER_TAG_MAX_LENGTH - len(_REQUESTER_TAG_PREFIX) - len(digest) - 1
    trimmed = sanitized[: max(suffix_budget, 1)].rstrip("-._")
    return f"{_REQUESTER_TAG_PREFIX}{trimmed}-{digest}"


async def list_downloads_from_qbittorrent(
    settings: Settings,
    requester_id: str | None = None,
) -> list[TorrentStatus]:
    requester_tag = _requester_tag_for_user(requester_id)

    def list_sync() -> list[TorrentStatus]:
        with qbittorrentapi.Client(
            host=settings.qbit_url,
            username=settings.qbit_username,
            password=settings.qbit_password,
        ) as qbit_client:
            qbit_client.auth_log_in()
            return [_torrent_status_from_client_torrent(t) for t in _list_torrents(qbit_client, tag=requester_tag)]

    try:
        return await asyncio.to_thread(list_sync)
    except qbittorrentapi.LoginFailed as exc:
        logger.warning("qBittorrent login failed")
        raise UpstreamServiceError("qBittorrent login failed") from exc
    except qbittorrentapi.APIConnectionError as exc:
        logger.warning("qBittorrent request failed: %s", exc.__class__.__name__)
        raise UpstreamServiceError("qBittorrent is unreachable") from exc
    except qbittorrentapi.APIError as exc:
        logger.warning("qBittorrent API error: %s", exc.__class__.__name__)
        raise UpstreamServiceError("qBittorrent API error") from exc


async def get_download_status_from_qbittorrent(
    settings: Settings,
    info_hash: str,
    requester_id: str | None = None,
) -> TorrentStatus | None:
    requester_tag = _requester_tag_for_user(requester_id)

    def get_status_sync() -> TorrentStatus | None:
        with qbittorrentapi.Client(
            host=settings.qbit_url,
            username=settings.qbit_username,
            password=settings.qbit_password,
        ) as qbit_client:
            qbit_client.auth_log_in()
            return _get_torrent_status(qbit_client, info_hash, tag=requester_tag)

    try:
        return await asyncio.to_thread(get_status_sync)
    except qbittorrentapi.LoginFailed as exc:
        logger.warning("qBittorrent login failed")
        raise UpstreamServiceError("qBittorrent login failed") from exc
    except qbittorrentapi.APIConnectionError as exc:
        logger.warning("qBittorrent request failed: %s", exc.__class__.__name__)
        raise UpstreamServiceError("qBittorrent is unreachable") from exc
    except qbittorrentapi.APIError as exc:
        logger.warning("qBittorrent API error: %s", exc.__class__.__name__)
        raise UpstreamServiceError("qBittorrent API error") from exc


async def tag_download_for_requester(
    settings: Settings,
    info_hash: str,
    requester_id: str | None,
) -> str | None:
    requester_tag = _requester_tag_for_user(requester_id)
    if not requester_tag:
        return None

    def tag_sync() -> None:
        with qbittorrentapi.Client(
            host=settings.qbit_url,
            username=settings.qbit_username,
            password=settings.qbit_password,
        ) as qbit_client:
            qbit_client.auth_log_in()
            _apply_requester_tag(qbit_client, info_hash, requester_tag)

    try:
        await asyncio.to_thread(tag_sync)
    except qbittorrentapi.LoginFailed as exc:
        logger.warning("qBittorrent login failed")
        raise UpstreamServiceError("qBittorrent login failed") from exc
    except qbittorrentapi.APIConnectionError as exc:
        logger.warning("qBittorrent request failed: %s", exc.__class__.__name__)
        raise UpstreamServiceError("qBittorrent is unreachable") from exc
    except qbittorrentapi.APIError as exc:
        logger.warning("qBittorrent API error: %s", exc.__class__.__name__)
        raise UpstreamServiceError("qBittorrent API error") from exc
    return requester_tag


async def check_qbittorrent_health(settings: Settings) -> dict[str, str]:
    def check_sync() -> None:
        with qbittorrentapi.Client(
            host=settings.qbit_url,
            username=settings.qbit_username,
            password=settings.qbit_password,
        ) as qbit_client:
            qbit_client.auth_log_in()

    try:
        await asyncio.to_thread(check_sync)
    except qbittorrentapi.LoginFailed:
        return {"status": "error", "detail": "qBittorrent login failed"}
    except qbittorrentapi.APIConnectionError:
        return {"status": "error", "detail": "qBittorrent is unreachable"}
    except qbittorrentapi.APIError:
        return {"status": "error", "detail": "qBittorrent API error"}
    return {"status": "ok"}
