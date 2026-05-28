from __future__ import annotations

import asyncio
import hashlib
from types import SimpleNamespace

from app.services.qbittorrent import _TORRENT_FILE_CACHE, add_download_to_qbittorrent


class FakeQbittorrentClient:
    calls: list[dict] = []
    existing_hashes: list[str] = []
    hashes_after_add: list[str] = []
    add_result = "Ok."

    def __init__(self, *, host, username, password):
        self.host = host
        self.username = username
        self.password = password

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return None

    def auth_log_in(self):
        return None

    def torrents_add(self, **kwargs):
        self.calls.append(kwargs)
        self.existing_hashes = list(self.hashes_after_add)
        return self.add_result

    def torrents_info(self):
        return [_fake_torrent(value) for value in self.existing_hashes]


INFO_DICT = b"d4:name4:Teste"
INFO_HASH = hashlib.sha1(INFO_DICT).hexdigest()
TORRENT_CONTENT = b"d8:announce15:https://tracker4:info" + INFO_DICT + b"e"


def _fake_torrent(hash_value=INFO_HASH):
    return SimpleNamespace(
        hash=hash_value,
        name="Test",
        state="downloading",
        progress=0.25,
        size=1_000_000_000,
        num_seeds=7,
        dlspeed=2_000_000,
        eta=600,
    )


class FakeTorrentResponse:
    content = TORRENT_CONTENT
    headers = {"content-type": "application/x-bittorrent"}

    def raise_for_status(self):
        return None


class FakeAsyncClient:
    fetched_urls: list[str] = []

    def __init__(self, **kwargs):
        self.kwargs = kwargs

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return None

    async def get(self, url):
        self.fetched_urls.append(url)
        return FakeTorrentResponse()


def _settings():
    return SimpleNamespace(
        prowlarr_url="http://prowlarr.test",
        prowlarr_download_url=None,
        prowlarr_api_key="secret",
        qbit_url="http://qbit.test",
        qbit_username="user",
        qbit_password="pass",
        request_timeout_seconds=30,
    )


def _reset_fakes():
    FakeQbittorrentClient.calls = []
    FakeQbittorrentClient.existing_hashes = []
    FakeQbittorrentClient.hashes_after_add = []
    FakeQbittorrentClient.add_result = "Ok."
    FakeAsyncClient.fetched_urls = []
    _TORRENT_FILE_CACHE.clear()


def test_add_download_uploads_http_torrent_content(monkeypatch):
    _reset_fakes()
    monkeypatch.setattr("app.services.qbittorrent.qbittorrentapi.Client", FakeQbittorrentClient)
    monkeypatch.setattr("app.services.qbittorrent.httpx.AsyncClient", FakeAsyncClient)

    asyncio.run(
        add_download_to_qbittorrent(
            "http://prowlarr.test/1/download?link=abc",
            _settings(),
            save_path="/downloads/movies/",
        )
    )

    assert FakeAsyncClient.fetched_urls == ["http://prowlarr.test/1/download?link=abc&apikey=secret"]
    assert FakeQbittorrentClient.calls == [
        {
            "torrent_files": TORRENT_CONTENT,
            "save_path": "/downloads/movies/",
        }
    ]


def test_add_download_passes_magnets_as_urls(monkeypatch):
    _reset_fakes()
    monkeypatch.setattr("app.services.qbittorrent.qbittorrentapi.Client", FakeQbittorrentClient)
    monkeypatch.setattr("app.services.qbittorrent.httpx.AsyncClient", FakeAsyncClient)

    asyncio.run(add_download_to_qbittorrent("magnet:?xt=urn:btih:abcdef", _settings()))

    assert FakeAsyncClient.fetched_urls == []
    assert FakeQbittorrentClient.calls == [
        {
            "urls": "magnet:?xt=urn:btih:abcdef",
            "save_path": None,
        }
    ]


def test_add_download_skips_qbittorrent_add_when_torrent_already_exists(monkeypatch):
    _reset_fakes()
    FakeQbittorrentClient.existing_hashes = [INFO_HASH.upper()]
    monkeypatch.setattr("app.services.qbittorrent.qbittorrentapi.Client", FakeQbittorrentClient)
    monkeypatch.setattr("app.services.qbittorrent.httpx.AsyncClient", FakeAsyncClient)

    asyncio.run(add_download_to_qbittorrent("http://prowlarr.test/1/download?link=abc", _settings()))

    assert FakeAsyncClient.fetched_urls == ["http://prowlarr.test/1/download?link=abc&apikey=secret"]
    assert FakeQbittorrentClient.calls == []


def test_add_download_treats_duplicate_result_as_success_when_torrent_exists_after_add(monkeypatch):
    _reset_fakes()
    FakeQbittorrentClient.hashes_after_add = [INFO_HASH]
    FakeQbittorrentClient.add_result = "Fails."
    monkeypatch.setattr("app.services.qbittorrent.qbittorrentapi.Client", FakeQbittorrentClient)
    monkeypatch.setattr("app.services.qbittorrent.httpx.AsyncClient", FakeAsyncClient)

    asyncio.run(
        add_download_to_qbittorrent(
            "http://prowlarr.test/1/download?link=abc",
            _settings(),
            save_path="/downloads/movies/",
        )
    )

    assert FakeQbittorrentClient.calls == [
        {
            "torrent_files": TORRENT_CONTENT,
            "save_path": "/downloads/movies/",
        }
    ]


def test_add_download_does_not_duplicate_existing_prowlarr_api_key(monkeypatch):
    _reset_fakes()
    monkeypatch.setattr("app.services.qbittorrent.qbittorrentapi.Client", FakeQbittorrentClient)
    monkeypatch.setattr("app.services.qbittorrent.httpx.AsyncClient", FakeAsyncClient)

    asyncio.run(add_download_to_qbittorrent("http://prowlarr.test/1/download?link=abc&apikey=already", _settings()))

    assert FakeAsyncClient.fetched_urls == ["http://prowlarr.test/1/download?link=abc&apikey=already"]


def test_add_download_returns_qbittorrent_status_for_added_torrent(monkeypatch):
    _reset_fakes()
    FakeQbittorrentClient.hashes_after_add = [INFO_HASH]
    monkeypatch.setattr("app.services.qbittorrent.qbittorrentapi.Client", FakeQbittorrentClient)
    monkeypatch.setattr("app.services.qbittorrent.httpx.AsyncClient", FakeAsyncClient)

    status = asyncio.run(add_download_to_qbittorrent("http://prowlarr.test/1/download?link=abc", _settings()))

    assert status is not None
    assert status.hash == INFO_HASH
    assert status.name == "Test"
    assert status.progress == 0.25
    assert status.download_speed == 2_000_000
    assert status.eta == 600
