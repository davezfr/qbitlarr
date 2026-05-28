from __future__ import annotations

import json
import os
import re
import secrets
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from app.models import QuerySnapshot, QuerySnapshotEntry, SearchResult


_QUERY_ID_RE = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9_.-]{0,127}$")


def create_query_id() -> str:
    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    return f"{timestamp}-{secrets.token_urlsafe(6)}"


def utc_now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


class QuerySnapshotStore:
    def __init__(self, root_dir: str | os.PathLike[str]) -> None:
        self.root_dir = Path(root_dir)

    def create(
        self,
        *,
        query_id: str,
        request: dict[str, Any],
        status: str,
        reason: str,
        results: list[SearchResult],
    ) -> QuerySnapshot:
        now = utc_now()
        snapshot = QuerySnapshot(
            query_id=query_id,
            status=status,
            created_at=now,
            updated_at=now,
            request=request,
            snapshots=[
                QuerySnapshotEntry(
                    version=1,
                    reason=reason,
                    created_at=now,
                    results=results,
                )
            ],
        )
        self.write(snapshot)
        return snapshot

    def append(
        self,
        *,
        query_id: str,
        status: str,
        reason: str,
        results: list[SearchResult],
    ) -> QuerySnapshot:
        snapshot = self.read(query_id)
        now = utc_now()
        snapshot.status = status
        snapshot.updated_at = now
        snapshot.snapshots.append(
            QuerySnapshotEntry(
                version=len(snapshot.snapshots) + 1,
                reason=reason,
                created_at=now,
                results=results,
            )
        )
        self.write(snapshot)
        return snapshot

    def read(self, query_id: str) -> QuerySnapshot:
        path = self._path_for(query_id)
        return QuerySnapshot.model_validate_json(path.read_text(encoding="utf-8"))

    def write(self, snapshot: QuerySnapshot) -> None:
        path = self._path_for(snapshot.query_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        temp_path = path.with_name(f".{path.name}.{secrets.token_hex(4)}.tmp")
        temp_path.write_text(
            json.dumps(snapshot.model_dump(mode="json"), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        os.replace(temp_path, path)

    def _path_for(self, query_id: str) -> Path:
        if not _QUERY_ID_RE.fullmatch(query_id):
            raise FileNotFoundError(query_id)
        return self.root_dir / f"{query_id}.json"
