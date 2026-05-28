from __future__ import annotations

import asyncio
import logging
import os
from typing import Any

from mcp.server.fastmcp import FastMCP

from app.client import get_qbitlarr_client


logging.basicConfig(level=os.getenv("LOG_LEVEL", "WARNING").upper())
logger = logging.getLogger("qbitlarr-mcp")

def create_mcp_server() -> FastMCP:
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
            save_path: Optional qBittorrent save path override, such as
                "/media/Kids". Leave unset to use qBitlarr's configured defaults.
            mode: Optional output mode. "auto" (default for IMDb input) picks
                and queues the best release; "manual" always returns a ranked
                list without downloading; "confirm" returns the top pick and
                alternatives without queueing — use this when the user wants
                to review before committing. Leave unset to use the server
                default (QBITLARR_DEFAULT_MODE).
        """
        return await get_qbitlarr_client().handle(
            user_message=user_message,
            user_id=user_id,
            save_path=save_path,
            mode=mode,
        )

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
    async def qbitlarr_download(download_link: str, save_path: str | None = None) -> dict[str, Any]:
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
        """
        return await get_qbitlarr_client().download(download_link, save_path=save_path)

    @mcp.tool()
    async def qbitlarr_list_downloads() -> list[dict[str, Any]]:
        """List all torrents currently tracked by qBittorrent.

        Returns each torrent's name, state, progress (0.0–1.0), size in bytes,
        number of seeds, and info hash. Call this after qbitlarr_download to confirm
        the torrent was accepted and to monitor its progress.

        Common state values: downloading, uploading (seeding), stalledDL,
        stalledUP, pausedDL, pausedUP, metaDL (fetching metadata), checkingDL.
        """
        return await get_qbitlarr_client().list_downloads()

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
