from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException

from app.config import get_settings
from app.exceptions import ConfigurationError, UpstreamServiceError
from app.models import TorrentStatus
from app.services.qbittorrent import list_downloads_from_qbittorrent


logger = logging.getLogger("qbitlarr-api.downloads")
router = APIRouter()


@router.get(
    "/downloads",
    response_model=list[TorrentStatus],
    operation_id="qbitlarr_list_downloads",
    summary="List qBittorrent downloads",
    tags=["qbitlarr"],
)
async def list_downloads() -> list[TorrentStatus]:
    try:
        settings = get_settings()
        return await list_downloads_from_qbittorrent(settings)
    except ConfigurationError as exc:
        logger.error("Configuration error: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    except UpstreamServiceError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
