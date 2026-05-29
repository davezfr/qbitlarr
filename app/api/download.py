from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException

from app.config import get_settings
from app.domain.save_paths import validate_save_path_override
from app.exceptions import ConfigurationError, UpstreamServiceError
from app.models import DownloadRequest, DownloadResponse
from app.services.qbittorrent import add_download_to_qbittorrent


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
        save_path = validate_save_path_override(request.save_path, settings)
        download_status = await add_download_to_qbittorrent(request.download_link, settings, save_path=save_path)
        return DownloadResponse(download_status=download_status)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except ConfigurationError as exc:
        logger.error("Configuration error: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    except UpstreamServiceError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
