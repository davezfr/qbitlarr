import asyncio
import json

import httpx
import pytest

from app.client import QbitlarrApiClient, QbitlarrApiError, get_qbitlarr_client


def test_qbitlarr_api_client_search_posts_expected_payload():
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(
            200,
            json=[
                {
                    "title": "Ubuntu ISO",
                    "download_link": "https://example.test/ubuntu.torrent",
                    "size": 123,
                    "seeders": 10,
                    "leechers": 1,
                    "indexer": "Indexer A",
                }
            ],
        )

    client = QbitlarrApiClient(
        api_url="http://qbitlarr.test",
        api_key="secret-key",
        transport=httpx.MockTransport(handler),
    )

    results = asyncio.run(
        client.search(
            identifier="imdb:tt0045877",
            query="ubuntu",
            categories=[2000],
            indexer_ids=[10, 11],
        )
    )

    assert results[0]["title"] == "Ubuntu ISO"
    assert requests[0].method == "POST"
    assert requests[0].url == "http://qbitlarr.test/search"
    assert requests[0].headers["X-API-Key"] == "secret-key"
    assert json.loads(requests[0].content) == {
        "identifier": "imdb:tt0045877",
        "query": "ubuntu",
        "categories": [2000],
        "indexer_ids": [10, 11],
    }


def test_qbitlarr_api_client_download_posts_expected_payload():
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, json={"status": "success", "message": "Download queued"})

    client = QbitlarrApiClient(
        api_url="http://qbitlarr.test/",
        transport=httpx.MockTransport(handler),
    )

    response = asyncio.run(client.download("magnet:?xt=urn:btih:abcdef", save_path="/media/Kids"))

    assert response == {"status": "success", "message": "Download queued"}
    assert requests[0].method == "POST"
    assert requests[0].url == "http://qbitlarr.test/download"
    assert json.loads(requests[0].content) == {
        "download_link": "magnet:?xt=urn:btih:abcdef",
        "save_path": "/media/Kids",
    }


def test_qbitlarr_api_client_handle_posts_expected_payload():
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(
            200,
            json={
                "status": "success",
                "action": "auto_download",
                "title": "The Hitch-Hiker (1953)",
                "quality": "1080p WEB-DL H.264",
                "message": "Started auto-downloading The Hitch-Hiker (1953) in 1080p WEB-DL H.264...",
            },
        )

    client = QbitlarrApiClient(
        api_url="http://qbitlarr.test/",
        transport=httpx.MockTransport(handler),
    )

    response = asyncio.run(client.handle("tt0045877", user_id="friend-a", save_path="/media/Kids"))

    assert response["action"] == "auto_download"
    assert requests[0].method == "POST"
    assert requests[0].url == "http://qbitlarr.test/handle"
    assert json.loads(requests[0].content) == {
        "user_message": "tt0045877",
        "user_id": "friend-a",
        "save_path": "/media/Kids",
        "mode": None,
    }


def test_get_qbitlarr_client_default_timeout_allows_slow_verified_imdb_flow(monkeypatch):
    monkeypatch.delenv("QBITLARR_API_TIMEOUT_SECONDS", raising=False)
    monkeypatch.delenv("QBITLARR_API_URL", raising=False)

    client = get_qbitlarr_client()

    assert client.timeout == 90.0


def test_qbitlarr_api_client_health_gets_health_endpoint():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "GET"
        assert request.url == "http://qbitlarr.test/health"
        return httpx.Response(200, json={"status": "ok", "service": "qBitlarr API"})

    client = QbitlarrApiClient(
        api_url="http://qbitlarr.test",
        transport=httpx.MockTransport(handler),
    )

    response = asyncio.run(client.health())

    assert response == {"status": "ok", "service": "qBitlarr API"}


def test_qbitlarr_api_client_deep_health_adds_query_parameter():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "GET"
        assert request.url == "http://qbitlarr.test/health?deep=true"
        return httpx.Response(
            200,
            json={
                "status": "ok",
                "service": "qBitlarr API",
                "dependencies": {
                    "prowlarr": {"status": "ok"},
                    "qbittorrent": {"status": "ok"},
                },
            },
        )

    client = QbitlarrApiClient(
        api_url="http://qbitlarr.test",
        transport=httpx.MockTransport(handler),
    )

    response = asyncio.run(client.health(deep=True))

    assert response["dependencies"]["prowlarr"]["status"] == "ok"


def test_qbitlarr_api_client_list_downloads_gets_downloads_endpoint():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "GET"
        assert request.url == "http://qbitlarr.test/downloads"
        return httpx.Response(
            200,
            json=[
                {
                    "name": "Ubuntu 24.04",
                    "state": "downloading",
                    "progress": 0.42,
                    "size": 1234567,
                    "seeds": 10,
                    "hash": "abcdef1234567890",
                }
            ],
        )

    client = QbitlarrApiClient(
        api_url="http://qbitlarr.test",
        transport=httpx.MockTransport(handler),
    )

    results = asyncio.run(client.list_downloads())

    assert results[0]["name"] == "Ubuntu 24.04"
    assert results[0]["state"] == "downloading"
    assert results[0]["progress"] == 0.42


def test_qbitlarr_api_client_get_download_status_gets_targeted_download_endpoint():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "GET"
        assert request.url == "http://qbitlarr.test/downloads/abcdef1234567890"
        return httpx.Response(
            200,
            json={
                "name": "Ubuntu 24.04",
                "state": "downloading",
                "progress": 0.42,
                "size": 1234567,
                "seeds": 10,
                "hash": "abcdef1234567890",
            },
        )

    client = QbitlarrApiClient(
        api_url="http://qbitlarr.test",
        transport=httpx.MockTransport(handler),
    )

    result = asyncio.run(client.get_download_status("abcdef1234567890"))

    assert result["hash"] == "abcdef1234567890"
    assert result["state"] == "downloading"


def test_qbitlarr_api_client_list_prowlarr_indexers_gets_indexer_endpoint():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "GET"
        assert request.url == "http://qbitlarr.test/prowlarr/indexers"
        return httpx.Response(
            200,
            json=[
                {
                    "id": 10,
                    "name": "Trusted Indexer",
                    "enabled": True,
                    "protocol": "torrent",
                }
            ],
        )

    client = QbitlarrApiClient(
        api_url="http://qbitlarr.test",
        transport=httpx.MockTransport(handler),
    )

    results = asyncio.run(client.list_prowlarr_indexers())

    assert results == [
        {
            "id": 10,
            "name": "Trusted Indexer",
            "enabled": True,
            "protocol": "torrent",
        }
    ]


def test_qbitlarr_api_client_get_query_snapshot_gets_query_endpoint():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "GET"
        assert request.url == "http://qbitlarr.test/queries/query-123"
        return httpx.Response(
            200,
            json={
                "query_id": "query-123",
                "status": "fallback_ready",
                "created_at": "2026-05-27T12:00:00Z",
                "updated_at": "2026-05-27T12:00:40Z",
                "request": {"input": "Rare Movie"},
                "snapshots": [
                    {
                        "version": 1,
                        "reason": "primary_no_results",
                        "created_at": "2026-05-27T12:00:30Z",
                        "results": [],
                    },
                    {
                        "version": 2,
                        "reason": "fallback_results_ready",
                        "created_at": "2026-05-27T12:00:40Z",
                        "results": [
                            {
                                "title": "Rare.Movie.1080p.WEB-DL.H.264-GRP",
                                "download_link": "https://example.test/rare.torrent",
                                "seeders": 12,
                                "indexer": "Fallback Indexer",
                            }
                        ],
                    },
                ],
            },
        )

    client = QbitlarrApiClient(
        api_url="http://qbitlarr.test",
        transport=httpx.MockTransport(handler),
    )

    snapshot = asyncio.run(client.get_query_snapshot("query-123"))

    assert snapshot["status"] == "fallback_ready"
    assert snapshot["snapshots"][-1]["results"][0]["indexer"] == "Fallback Indexer"


def test_qbitlarr_api_client_raises_clean_error_for_qbitlarr_failures():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(502, json={"detail": "Prowlarr is unreachable"})

    client = QbitlarrApiClient(
        api_url="http://qbitlarr.test",
        transport=httpx.MockTransport(handler),
    )

    with pytest.raises(QbitlarrApiError) as exc_info:
        asyncio.run(client.search(query="ubuntu"))

    assert exc_info.value.status_code == 502
    assert str(exc_info.value) == "Prowlarr is unreachable"
