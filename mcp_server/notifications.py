from __future__ import annotations

import asyncio
import json
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Awaitable, Callable

from app.client import QbitlarrApiClient, get_qbitlarr_client


SendMessage = Callable[[str, str], Awaitable[None]]
COMPLETE_STATES = {"uploading", "stalledUP", "pausedUP", "forcedUP", "queuedUP"}


class DownloadWatchStore:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)

    def upsert_watch(
        self,
        *,
        info_hash: str,
        title: str,
        notification_target: str,
        requester_id: str | None = None,
    ) -> dict[str, Any]:
        normalized_hash = _normalize_hash(info_hash)
        normalized_target = _normalize_target(notification_target)
        payload = self._read()
        now = _now()

        for watch in payload["watches"]:
            if watch["info_hash"] == normalized_hash and watch["notification_target"] == normalized_target:
                watch["title"] = title.strip() or watch["title"]
                watch["requester_id"] = requester_id or watch.get("requester_id")
                watch["updated_at"] = now
                self._write(payload)
                return dict(watch)

        watch = {
            "info_hash": normalized_hash,
            "title": title.strip() or normalized_hash,
            "notification_target": normalized_target,
            "requester_id": requester_id,
            "created_at": now,
            "updated_at": now,
            "notified_at": None,
            "last_error": None,
        }
        payload["watches"].append(watch)
        self._write(payload)
        return dict(watch)

    def pending_watches(self) -> list[dict[str, Any]]:
        return [dict(watch) for watch in self._read()["watches"] if not watch.get("notified_at")]

    def mark_notified(self, *, info_hash: str, notification_target: str) -> None:
        self._update_watch(
            info_hash=info_hash,
            notification_target=notification_target,
            updates={"notified_at": _now(), "last_error": None},
        )

    def mark_error(self, *, info_hash: str, notification_target: str, error: str) -> None:
        self._update_watch(
            info_hash=info_hash,
            notification_target=notification_target,
            updates={"last_error": error[:500], "updated_at": _now()},
        )

    def _update_watch(self, *, info_hash: str, notification_target: str, updates: dict[str, Any]) -> None:
        normalized_hash = _normalize_hash(info_hash)
        normalized_target = _normalize_target(notification_target)
        payload = self._read()
        for watch in payload["watches"]:
            if watch["info_hash"] == normalized_hash and watch["notification_target"] == normalized_target:
                watch.update(updates)
                self._write(payload)
                return

    def _read(self) -> dict[str, Any]:
        if not self.path.exists():
            return {"watches": []}
        try:
            payload = json.loads(self.path.read_text())
        except json.JSONDecodeError:
            return {"watches": []}
        watches = payload.get("watches")
        if not isinstance(watches, list):
            return {"watches": []}
        return {"watches": watches}

    def _write(self, payload: dict[str, Any]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(payload, indent=2, sort_keys=True))


class DownloadCompletionNotifier:
    def __init__(
        self,
        *,
        store: DownloadWatchStore,
        client: QbitlarrApiClient | Any,
        send_message: SendMessage,
        poll_interval_seconds: float = 60.0,
    ) -> None:
        self.store = store
        self.client = client
        self.send_message = send_message
        self.poll_interval_seconds = poll_interval_seconds
        self._task: asyncio.Task | None = None

    @classmethod
    def from_env(cls) -> "DownloadCompletionNotifier":
        return cls(
            store=DownloadWatchStore(default_watch_store_path()),
            client=get_qbitlarr_client(),
            send_message=send_hermes_message,
            poll_interval_seconds=float(os.getenv("QBITLARR_NOTIFICATION_INTERVAL_SECONDS", "60")),
        )

    async def register_watch(
        self,
        *,
        info_hash: str,
        title: str,
        notification_target: str,
        requester_id: str | None = None,
    ) -> dict[str, Any]:
        watch = self.store.upsert_watch(
            info_hash=info_hash,
            title=title,
            notification_target=notification_target,
            requester_id=requester_id,
        )
        self.start()
        return watch

    def start(self) -> None:
        if self._task is None or self._task.done():
            self._task = asyncio.create_task(self._poll_loop())

    async def poll_once(self) -> None:
        for watch in self.store.pending_watches():
            try:
                status = await self.client.get_download_status(watch["info_hash"])
            except Exception as exc:
                self.store.mark_error(
                    info_hash=watch["info_hash"],
                    notification_target=watch["notification_target"],
                    error=str(exc),
                )
                continue

            if not _download_complete(status):
                continue

            await self.send_message(watch["notification_target"], _completion_message(watch, status))
            self.store.mark_notified(
                info_hash=watch["info_hash"],
                notification_target=watch["notification_target"],
            )

    async def _poll_loop(self) -> None:
        while True:
            await self.poll_once()
            await asyncio.sleep(self.poll_interval_seconds)


def default_watch_store_path() -> Path:
    return Path(os.getenv("QBITLARR_NOTIFICATION_WATCHES_PATH", "data/download-notification-watches.json"))


async def send_hermes_message(target: str, message: str) -> None:
    hermes_bin = os.getenv("QBITLARR_HERMES_BIN", "hermes")
    proc = await asyncio.create_subprocess_exec(
        hermes_bin,
        "send",
        "--to",
        target,
        "--quiet",
        message,
    )
    return_code = await proc.wait()
    if return_code != 0:
        raise RuntimeError(f"hermes send failed with exit code {return_code}")


def _download_complete(status: dict[str, Any]) -> bool:
    try:
        progress = float(status.get("progress", 0.0))
    except (TypeError, ValueError):
        progress = 0.0
    return progress >= 1.0 or str(status.get("state", "")) in COMPLETE_STATES


def _completion_message(watch: dict[str, Any], status: dict[str, Any]) -> str:
    title = str(watch.get("title") or status.get("name") or watch["info_hash"]).strip()
    return f"Download complete: {title}\nStatus: 100% complete."


def _normalize_hash(info_hash: str) -> str:
    normalized = info_hash.strip().casefold()
    if not normalized:
        raise ValueError("info_hash must not be empty")
    return normalized


def _normalize_target(notification_target: str) -> str:
    target = notification_target.strip()
    if not target:
        raise ValueError("notification_target must not be empty")
    if "\n" in target or "\r" in target:
        raise ValueError("notification_target must be one line")
    return target


def _now() -> str:
    return datetime.now(UTC).isoformat()
