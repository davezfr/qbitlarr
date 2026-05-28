from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException

from app.config import get_settings
from app.exceptions import ConfigurationError
from app.models import QuerySnapshot
from app.services.query_snapshots import QuerySnapshotStore


logger = logging.getLogger("qbitlarr-api.query-snapshots")
router = APIRouter()


@router.get(
    "/queries/{query_id}",
    response_model=QuerySnapshot,
    operation_id="qbitlarr_get_query_snapshot",
    summary="Get a saved qBitlarr query snapshot",
    description="Return the stored search snapshot document for a previous qbitlarr_handle query_id.",
    tags=["qbitlarr"],
)
async def get_query_snapshot(query_id: str) -> QuerySnapshot:
    try:
        settings = get_settings()
        return QuerySnapshotStore(settings.query_snapshot_dir).read(query_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Query snapshot not found") from exc
    except ConfigurationError as exc:
        logger.error("Configuration error: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc)) from exc
