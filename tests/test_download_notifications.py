from __future__ import annotations

import asyncio
import json
from pathlib import Path

from mcp_server.server import _maybe_register_completion_watch
from mcp_server.notifications import DownloadCompletionNotifier, DownloadWatchStore


class FakeClient:
    def __init__(self, statuses):
        self.statuses = statuses

    async def get_download_status(self, info_hash):
        return self.statuses[info_hash]


class FakeNotifier:
    def __init__(self):
        self.watches = []

    async def register_watch(self, *, info_hash, title, notification_target, requester_id=None):
        watch = {
            "info_hash": info_hash,
            "title": title,
            "notification_target": notification_target,
            "requester_id": requester_id,
        }
        self.watches.append(watch)
        return watch


def test_download_watch_store_deduplicates_by_hash_and_target(tmp_path):
    store = DownloadWatchStore(tmp_path / "watches.json")

    first = store.upsert_watch(
        info_hash="abcdef",
        title="Example Movie",
        notification_target="telegram:12345",
        requester_id="user-a",
    )
    second = store.upsert_watch(
        info_hash="ABCDEF",
        title="Updated Title",
        notification_target="telegram:12345",
        requester_id="user-a",
    )

    assert first["created_at"] == second["created_at"]
    assert second["title"] == "Updated Title"
    assert len(store.pending_watches()) == 1


def test_notifier_sends_one_message_when_download_completes(tmp_path):
    sent: list[tuple[str, str]] = []
    store = DownloadWatchStore(tmp_path / "watches.json")
    client = FakeClient(
        {
            "abcdef": {
                "name": "Example.Movie.2026.1080p.WEB-DL.H.264-GRP",
                "state": "uploading",
                "progress": 1.0,
                "hash": "abcdef",
            }
        }
    )

    async def fake_send(target, message):
        sent.append((target, message))

    notifier = DownloadCompletionNotifier(store=store, client=client, send_message=fake_send)
    store.upsert_watch(
        info_hash="abcdef",
        title="Example Movie",
        notification_target="telegram:12345",
        requester_id="user-a",
    )

    asyncio.run(notifier.poll_once())
    asyncio.run(notifier.poll_once())

    assert sent == [
        (
            "telegram:12345",
            "Download complete: Example Movie\nStatus: 100% complete.",
        )
    ]
    watches = json.loads(Path(tmp_path / "watches.json").read_text())["watches"]
    assert watches[0]["notified_at"] is not None


def test_notifier_keeps_incomplete_download_pending(tmp_path):
    sent: list[tuple[str, str]] = []
    store = DownloadWatchStore(tmp_path / "watches.json")
    client = FakeClient(
        {
            "abcdef": {
                "name": "Example.Movie.2026.1080p.WEB-DL.H.264-GRP",
                "state": "downloading",
                "progress": 0.5,
                "hash": "abcdef",
            }
        }
    )

    async def fake_send(target, message):
        sent.append((target, message))

    notifier = DownloadCompletionNotifier(store=store, client=client, send_message=fake_send)
    store.upsert_watch(
        info_hash="abcdef",
        title="Example Movie",
        notification_target="telegram:12345",
        requester_id="user-a",
    )

    asyncio.run(notifier.poll_once())

    assert sent == []
    assert len(store.pending_watches()) == 1


def test_mcp_wrapper_registers_watch_from_download_status_payload():
    notifier = FakeNotifier()
    payload = {
        "status": "success",
        "action": "auto_download",
        "title": "Example Movie",
        "download_status": {
            "hash": "abcdef1234567890",
            "name": "Example.Movie.2026.1080p.WEB-DL.H.264-GRP",
        },
    }

    asyncio.run(
        _maybe_register_completion_watch(
            notifier,
            payload=payload,
            notification_target="telegram:12345",
            requester_id="user-a",
        )
    )

    assert notifier.watches == [
        {
            "info_hash": "abcdef1234567890",
            "title": "Example Movie",
            "notification_target": "telegram:12345",
            "requester_id": "user-a",
        }
    ]
    assert payload["notification_watch"]["status"] == "watching"
