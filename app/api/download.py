from __future__ import annotations

import logging
from urllib.parse import parse_qs, urlparse

from fastapi import APIRouter, HTTPException

from app.config import get_settings
from app.domain.quality import infer_media_type
from app.domain.save_paths import default_save_path_for_title, validate_save_path_override
from app.domain.torrent_metadata import parse_torrent_name
from app.exceptions import ConfigurationError, UpstreamServiceError
from app.models import DownloadRequest, DownloadResponse
from app.services.qbittorrent import _download_torrent_file, add_download_to_qbittorrent


logger = logging.getLogger("qbitlarr-api.download")
router = APIRouter()


@router.post(
    "/download",
    response_model=DownloadResponse,
    operation_id="qbitlarr_download",
    summary="Queue a torrent or magnet in qBittorrent",
    tags=["qbitlarr"],
)
async def download(request: DownloadRequest) -> DownloadResponse:
    try:
        settings = get_settings()
        save_path = await _resolve_download_save_path(request, settings)
        download_kwargs = {"save_path": save_path}
        if request.user_id:
            download_kwargs["requester_id"] = request.user_id
        download_status = await add_download_to_qbittorrent(
            request.download_link,
            settings,
            **download_kwargs,
        )
        return DownloadResponse(download_status=download_status)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except ConfigurationError as exc:
        logger.error("Configuration error: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    except UpstreamServiceError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


async def _resolve_download_save_path(request: DownloadRequest, settings) -> str | None:
    if request.save_path:
        return validate_save_path_override(request.save_path, settings)

    title = await _download_title_from_link(request.download_link, settings)
    media_type = infer_media_type(title or "")
    return default_save_path_for_title(settings=settings, media_type=media_type, title=title or "")


async def _download_title_from_link(download_link: str, settings) -> str | None:
    parsed = urlparse(download_link)
    if parsed.scheme.lower() in {"http", "https"}:
        return parse_torrent_name(await _download_torrent_file(download_link, settings))

    if parsed.scheme.lower() == "magnet":
        names = parse_qs(parsed.query).get("dn") or []
        return names[0].strip() if names and names[0].strip() else None

    return None
