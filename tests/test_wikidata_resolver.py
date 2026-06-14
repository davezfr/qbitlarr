from __future__ import annotations

import asyncio
from types import SimpleNamespace

from app.domain.quality import extract_external_movie_id
from app.services.wikidata import resolve_external_movie_id


class FakeWikidataResponse:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self._payload


class FakeAsyncClient:
    requests: list[dict] = []
    payload = {"results": {"bindings": []}}

    def __init__(self, **kwargs):
        self.kwargs = kwargs

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return None

    async def get(self, url, *, params=None, headers=None):
        self.requests.append({"url": url, "params": params, "headers": headers})
        return FakeWikidataResponse(self.payload)


def _settings():
    return SimpleNamespace(request_timeout_seconds=30)


def _reset_fakes():
    FakeAsyncClient.requests = []
    FakeAsyncClient.payload = {"results": {"bindings": []}}


def test_extract_external_movie_id_from_douban_subject_url():
    assert extract_external_movie_id("https://movie.douban.com/subject/1292052/") == {
        "source": "douban",
        "source_id": "1292052",
    }


def test_extract_external_movie_id_from_allocine_film_url():
    assert extract_external_movie_id("https://www.allocine.fr/film/fichefilm_gen_cfilm=25801.html") == {
        "source": "allocine",
        "source_id": "25801",
    }


def test_extract_external_movie_id_accepts_prefixed_ids():
    assert extract_external_movie_id("douban:1292052") == {
        "source": "douban",
        "source_id": "1292052",
    }
    assert extract_external_movie_id("allocine:25801") == {
        "source": "allocine",
        "source_id": "25801",
    }


def test_resolve_external_movie_id_maps_douban_to_imdb_via_wikidata(monkeypatch):
    _reset_fakes()
    FakeAsyncClient.payload = {
        "results": {
            "bindings": [
                {
                    "item": {"value": "http://www.wikidata.org/entity/Q172241"},
                    "imdb": {"value": "tt0111161"},
                }
            ]
        }
    }

    monkeypatch.setattr("app.services.wikidata.httpx.AsyncClient", FakeAsyncClient)

    result = asyncio.run(resolve_external_movie_id("https://movie.douban.com/subject/1292052/", _settings()))

    assert result == {
        "source": "douban",
        "source_id": "1292052",
        "imdb_id": "tt0111161",
        "wikidata_qid": "Q172241",
    }
    assert FakeAsyncClient.requests
    assert "wd:Q11424" in FakeAsyncClient.requests[0]["params"]["query"]


def test_resolve_external_movie_id_returns_unresolved_for_known_allocine_input_without_match(monkeypatch):
    _reset_fakes()
    monkeypatch.setattr("app.services.wikidata.httpx.AsyncClient", FakeAsyncClient)

    result = asyncio.run(
        resolve_external_movie_id("https://www.allocine.fr/film/fichefilm_gen_cfilm=25801.html", _settings())
    )

    assert result == {
        "source": "allocine",
        "source_id": "25801",
        "imdb_id": None,
        "wikidata_qid": None,
    }


def test_resolve_external_movie_id_returns_unresolved_for_known_allocine_series_url():
    result = asyncio.run(
        resolve_external_movie_id("https://www.allocine.fr/series/ficheserie_gen_cserie=543.html", _settings())
    )

    assert result == {
        "source": "allocine",
        "source_id": None,
        "imdb_id": None,
        "wikidata_qid": None,
    }


def test_resolve_external_movie_id_returns_none_for_non_external_input():
    assert asyncio.run(resolve_external_movie_id("The Hitch-Hiker", _settings())) is None
