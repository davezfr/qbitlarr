from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException, Query

from app.config import get_settings
from app.exceptions import ConfigurationError, UpstreamServiceError
from app.models import TorrentStatus, normalize_optional_user_id
from app.services.qbittorrent import get_download_status_from_qbittorrent, list_downloads_from_qbittorrent


logger = logging.getLogger("qbitlarr-api.downloads")
router = APIRouter()


@router.get(
    "/downloads",
    response_model=list[TorrentStatus],
    operation_id="qbitlarr_list_downloads",
    summary="List qBittorrent downloads",
    tags=["qbitlarr"],
)
async def list_downloads(
    user_id: str | None = Query(
        default=None,
        description="Optional requester identifier. When set, only torrents tagged for that requester are returned.",
    ),
) -> list[TorrentStatus]:
    try:
        settings = get_settings()
        return await list_downloads_from_qbittorrent(settings, requester_id=normalize_optional_user_id(user_id))
    except ConfigurationError as exc:
        logger.error("Configuration error: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    except UpstreamServiceError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.get(
    "/downloads/{info_hash}",
    response_model=TorrentStatus,
    operation_id="qbitlarr_get_download_status",
    summary="Get one qBittorrent download by info hash",
    tags=["qbitlarr"],
)
async def get_download_status(
    info_hash: str,
    user_id: str | None = Query(
        default=None,
        description="Optional requester identifier. When set, the torrent must be tagged for that requester.",
    ),
) -> TorrentStatus:
    try:
        settings = get_settings()
        status = await get_download_status_from_qbittorrent(
            settings,
            info_hash,
            requester_id=normalize_optional_user_id(user_id),
        )
        if status is None:
            raise HTTPException(status_code=404, detail="Download not found")
        return status
    except ConfigurationError as exc:
        logger.error("Configuration error: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    except UpstreamServiceError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
