from __future__ import annotations

import asyncio
import logging
import os
from typing import Any

from mcp.server.fastmcp import FastMCP

from app.client import get_qbitlarr_client
from mcp_server.notifications import DownloadCompletionNotifier


logging.basicConfig(level=os.getenv("LOG_LEVEL", "WARNING").upper())
logger = logging.getLogger("qbitlarr-mcp")

def create_mcp_server() -> FastMCP:
    notifier = DownloadCompletionNotifier.from_env()
    mcp = FastMCP(
        "qbitlarr",
        instructions=(
            "Search torrent indexers via Prowlarr and manage qBittorrent downloads. "
            "Use this only for media the user is allowed to access. "
            "Default workflow: call qbitlarr_handle with a user's IMDb ID, IMDb URL, or title. "
            "For IMDb IDs and IMDb URLs, qBitlarr auto-selects a 1080p release by default and queues it. "
            "For keywords, qBitlarr returns a friendly numbered candidate list. "
            "qbitlarr_handle returns query_id when a saved query snapshot is available. "
            "Use qbitlarr_search and qbitlarr_download only when manual control is needed. "
            "Use qbitlarr_list_prowlarr_indexers to discover indexer IDs for configuration."
        ),
    )

    @mcp.tool()
    async def qbitlarr_handle(
        user_message: str,
        user_id: str | None = None,
        save_path: str | None = None,
        mode: str | None = None,
        notification_target: str | None = None,
    ) -> dict[str, Any]:
        """Main qBitlarr tool for normal users.

        Pass a raw user request such as "tt0045877",
        "https://www.imdb.com/title/tt0045877/", "The Hitch-Hiker", or
        "Example Show S03". If the message contains an IMDb ID or IMDb URL, qBitlarr
        searches Prowlarr, applies quality/seed rules, and queues the selected
        result in qBittorrent. If the message is a keyword search or no safe
        automatic match is found, qBitlarr returns a friendly numbered list with
        download_link values for manual selection.

        On auto_download responses, an "alternatives" list is included with the
        top runner-ups, so the user can be offered "or did you mean..." without
        a second tool call.

        Args:
            user_message: IMDb ID, IMDb URL, title, season phrase, or plain
                search terms. qBitlarr recommends 1080p by default. Include "4K",
                "2160p", "UHD", "720p", "480p", or "Remux" only when the
                user explicitly asks for that quality.
            user_id: Optional caller identifier for logs and multi-user context.
                When serving multiple people through one qBittorrent instance,
                pass a stable chat/user ID so future status checks can be scoped
                to that requester's tagged torrents.
            save_path: Optional qBittorrent save path override, such as
                "/media/Kids". Leave unset to use qBitlarr's configured defaults.
            mode: Optional output mode. "auto" (default for IMDb input) picks
                and queues the best release; "manual" always returns a ranked
                list without downloading; "confirm" returns the top pick and
                alternatives without queueing — use this when the user wants
                to review before committing. Leave unset to use the server
                default (QBITLARR_DEFAULT_MODE).
            notification_target: Optional Hermes send target, such as
                "telegram:28568871". When set and the response includes a
                torrent hash, qBitlarr will send that target a one-time
                completion notification when the torrent reaches 100%. When
                omitted, qBitlarr reuses user_id if it already looks like a
                Hermes send target.
        """
        payload = await get_qbitlarr_client().handle(
            user_message=user_message,
            user_id=user_id,
            save_path=save_path,
            mode=mode,
        )
        await _maybe_register_completion_watch(
            notifier,
            payload=payload,
            notification_target=notification_target,
            requester_id=user_id,
        )
        return payload

    @mcp.tool()
    async def qbitlarr_get_query_snapshot(query_id: str) -> dict[str, Any]:
        """Return the saved search snapshot document for a previous qbitlarr_handle query_id.

        Use this only when the user asks for more alternatives from the same
        query. The snapshot may include a later fallback pass from slower
        fallback indexers. Do not expose raw download_link values unless
        the user explicitly asks to queue or inspect a specific result.
        """
        return await get_qbitlarr_client().get_query_snapshot(query_id)

    @mcp.tool()
    async def qbitlarr_search(
        identifier: str | None = None,
        query: str | None = None,
        categories: list[int] | None = None,
        indexer_ids: list[int] | None = None,
    ) -> list[dict[str, Any]]:
        """Search torrent indexers via Prowlarr and return ranked results.

        Manual workflow helper. Prefer qbitlarr_handle for normal user requests.
        Call this to discover candidates, then pass the chosen result's
        download_link to qbitlarr_download.

        Args:
            identifier: Typed media ID or IMDb URL for precise matching. Supported prefixes:
                imdb:tt0045877, tmdb:123456, tvdb:123456, tvmaze:123456,
                trakt:1234, douban:1234567. A bare IMDb ID (tt0045877) also works.
            query: Free-text keywords, e.g. "The General 1926 BluRay 1080p".
                Combine with identifier for best results.
            categories: Optional Prowlarr category IDs, such as 2000 for movies
                or 5000 for TV. Leave unset for qBitlarr defaults.
            indexer_ids: Optional Prowlarr indexer IDs. Use
                qbitlarr_list_prowlarr_indexers to discover them.

        At least one argument is required. Returns up to 20 results. Each result
        contains title, download_link (pass to qbitlarr_download), size (bytes),
        seeders, leechers, indexer, protocol (torrent/usenet), publish_date,
        and info_hash.
        """
        return await get_qbitlarr_client().search(
            identifier=identifier,
            query=query,
            categories=categories,
            indexer_ids=indexer_ids,
        )

    @mcp.tool()
    async def qbitlarr_download(
        download_link: str,
        save_path: str | None = None,
        notification_target: str | None = None,
        requester_id: str | None = None,
    ) -> dict[str, Any]:
        """Queue a torrent or magnet link in qBittorrent.

        Pass a download_link from qbitlarr_search results. Accepted schemes:
        http, https (direct .torrent file), magnet, bc (BitComet).

        Returns {"status": "success", "message": "Download queued"} on success.
        Call qbitlarr_list_downloads afterward to confirm the torrent is active.

        Args:
            download_link: A download_link value returned by qbitlarr_search.
            save_path: Optional qBittorrent save path override, such as
                "/media/Kids". Leave unset to use qBitlarr's inferred default
                media path.
            notification_target: Optional Hermes send target, such as
                "telegram:28568871". When set and qBitlarr can identify the
                torrent hash, the requester gets a one-time completion notice.
                When omitted, qBitlarr reuses requester_id if it already
                looks like a Hermes send target.
            requester_id: Optional stable user identifier. When set, qBitlarr
                tags the torrent for requester-scoped status queries and stores
                the same identifier with the completion watch.
        """
        payload = await get_qbitlarr_client().download(
            download_link,
            save_path=save_path,
            user_id=requester_id,
        )
        await _maybe_register_completion_watch(
            notifier,
            payload=payload,
            notification_target=notification_target,
            requester_id=requester_id,
        )
        return payload

    @mcp.tool()
    async def qbitlarr_list_downloads(requester_id: str | None = None) -> list[dict[str, Any]]:
        """List all torrents currently tracked by qBittorrent.

        Returns each torrent's name, state, progress (0.0–1.0), size in bytes,
        number of seeds, and info hash. Call this after qbitlarr_download to confirm
        the torrent was accepted and to monitor its progress.

        When requester_id is set, only torrents tagged for that requester are
        returned. Use a stable chat/user identifier here for multi-user bots.

        Common state values: downloading, uploading (seeding), stalledDL,
        stalledUP, pausedDL, pausedUP, metaDL (fetching metadata), checkingDL.
        """
        return await get_qbitlarr_client().list_downloads(user_id=requester_id)

    @mcp.tool()
    async def qbitlarr_get_download_status(info_hash: str, requester_id: str | None = None) -> dict[str, Any]:
        """Read one qBittorrent torrent by info hash.

        Prefer this over qbitlarr_list_downloads when you already have the
        exact torrent hash from a previous qbitlarr_handle auto-download
        response and want a reliable follow-up status check. When requester_id
        is set, the torrent must already be tagged for that requester.
        """
        return await get_qbitlarr_client().get_download_status(info_hash, user_id=requester_id)

    @mcp.tool()
    async def qbitlarr_watch_download(
        info_hash: str,
        notification_target: str,
        title: str | None = None,
        requester_id: str | None = None,
    ) -> dict[str, Any]:
        """Send a one-time completion notification for a torrent hash.

        Use this when a user asks to be notified when a specific torrent
        finishes. notification_target must be a Hermes send target such as
        "telegram:28568871" so the notification goes back to the requesting
        chat/user.
        """
        watch = await notifier.register_watch(
            info_hash=info_hash,
            title=title or info_hash,
            notification_target=notification_target,
            requester_id=requester_id,
        )
        return {"status": "watching", "watch": watch}

    @mcp.tool()
    async def qbitlarr_health(deep: bool = False) -> dict[str, Any]:
        """Check whether the qBitlarr API is reachable.

        Returns {"status": "ok", "service": "qBitlarr API"} when the API is
        reachable. Set deep=true to also check Prowlarr and qBittorrent.

        Args:
            deep: When true, also check Prowlarr and qBittorrent readiness.
        """
        return await get_qbitlarr_client().health(deep=deep)

    @mcp.tool()
    async def qbitlarr_list_prowlarr_indexers() -> list[dict[str, Any]]:
        """List configured Prowlarr indexers and their numeric IDs.

        Use this when setting PROWLARR_PRIMARY_INDEXER_IDS or
        PROWLARR_FALLBACK_INDEXER_IDS. Each item includes id, name, enabled,
        and protocol when Prowlarr provides those fields.
        """
        return await get_qbitlarr_client().list_prowlarr_indexers()

    return mcp


async def _maybe_register_completion_watch(
    notifier: DownloadCompletionNotifier,
    *,
    payload: dict[str, Any],
    notification_target: str | None,
    requester_id: str | None,
) -> None:
    resolved_target = _resolve_notification_target(notification_target, requester_id)
    if not resolved_target:
        return

    download_status = payload.get("download_status")
    if not isinstance(download_status, dict):
        return

    info_hash = download_status.get("hash")
    if not isinstance(info_hash, str) or not info_hash.strip():
        return

    title = _string_value(payload.get("title")) or _string_value(download_status.get("name")) or info_hash
    watch = await notifier.register_watch(
        info_hash=info_hash,
        title=title,
        notification_target=resolved_target,
        requester_id=requester_id,
    )
    _add_completion_notice_to_message(payload)
    payload["notification_watch"] = {"status": "watching", "watch": watch}


def _string_value(value: Any) -> str | None:
    if isinstance(value, str) and value.strip():
        return value.strip()
    return None


def _add_completion_notice_to_message(payload: dict[str, Any]) -> None:
    message = _string_value(payload.get("message"))
    if not message:
        return
    if "notified when it finishes" in message.casefold():
        return

    status_hint = "You can ask for a status update any time."
    completion_hint = "You'll be notified when it finishes."
    if message.endswith(status_hint):
        prefix = message[: -len(status_hint)].rstrip()
        payload["message"] = f"{prefix} {completion_hint} {status_hint}".strip()
        return

    payload["message"] = f"{message} {completion_hint}"


def _resolve_notification_target(
    notification_target: str | None,
    requester_id: str | None,
) -> str | None:
    explicit_target = _string_value(notification_target)
    if explicit_target:
        return explicit_target

    requester_target = _string_value(requester_id)
    if _looks_like_hermes_target(requester_target):
        return requester_target

    return None


def _looks_like_hermes_target(value: str | None) -> bool:
    if not value:
        return False

    platform, separator, target_ref = value.partition(":")
    if not separator or not target_ref.strip():
        return False

    return all(char.isalnum() or char in {"_", "-"} for char in platform)


async def run_mcp_server() -> None:
    server = create_mcp_server()
    await server.run_stdio_async()


def main() -> None:
    try:
        asyncio.run(run_mcp_server())
    except KeyboardInterrupt:
        logger.info("qBitlarr MCP server stopped")


if __name__ == "__main__":
    main()
