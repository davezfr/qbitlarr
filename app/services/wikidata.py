from __future__ import annotations

import logging
from typing import Any
from urllib.parse import unquote, urlparse

import httpx

from app.config import Settings
from app.domain.quality import extract_external_movie_id, normalize_user_message


logger = logging.getLogger("qbitlarr-api.wikidata")

WIKIDATA_SPARQL_URL = "https://query.wikidata.org/sparql"
SOURCE_PROPERTY_IDS = {
    "douban": "P4529",
    "allocine": "P1265",
}


async def resolve_external_movie_id(
    user_message: str,
    settings: Settings,
) -> dict[str, str | None] | None:
    source = _detect_external_source(user_message)
    if source is None:
        return None

    external = extract_external_movie_id(user_message)
    if external is None:
        return _unresolved_resolution(source=source, source_id=None)

    payload = await _query_wikidata_imdb(
        property_id=SOURCE_PROPERTY_IDS[source],
        source_id=external["source_id"],
        settings=settings,
    )
    parsed = _parse_imdb_resolution(payload)
    if parsed is None:
        return _unresolved_resolution(source=source, source_id=external["source_id"])

    return {
        "source": source,
        "source_id": external["source_id"],
        "imdb_id": parsed["imdb_id"],
        "wikidata_qid": parsed["wikidata_qid"],
    }


async def _query_wikidata_imdb(
    *,
    property_id: str,
    source_id: str,
    settings: Settings,
) -> dict[str, Any] | None:
    query = (
        "SELECT ?item ?imdb WHERE { "
        f'?item wdt:{property_id} "{source_id}" . '
        "?item wdt:P345 ?imdb . "
        "?item wdt:P31/wdt:P279* wd:Q11424 . "
        "}"
    )
    headers = {
        "Accept": "application/sparql-results+json",
        "User-Agent": "qBitlarr/0.1 (external-movie-resolver)",
    }
    params = {"query": query, "format": "json"}

    try:
        async with httpx.AsyncClient(timeout=settings.request_timeout_seconds) as client:
            response = await client.get(WIKIDATA_SPARQL_URL, params=params, headers=headers)
            response.raise_for_status()
            payload = response.json()
    except httpx.HTTPStatusError as exc:
        logger.warning("Wikidata lookup failed with HTTP %s", exc.response.status_code)
        return None
    except httpx.RequestError as exc:
        logger.warning("Wikidata lookup failed: %s", exc.__class__.__name__)
        return None
    except ValueError:
        logger.warning("Wikidata returned invalid JSON")
        return None

    if not isinstance(payload, dict):
        return None
    return payload


def _parse_imdb_resolution(payload: dict[str, Any] | None) -> dict[str, str] | None:
    if not isinstance(payload, dict):
        return None

    results = payload.get("results")
    if not isinstance(results, dict):
        return None

    bindings = results.get("bindings")
    if not isinstance(bindings, list):
        return None

    matches: set[tuple[str, str]] = set()
    for binding in bindings:
        if not isinstance(binding, dict):
            continue

        imdb = _binding_value(binding.get("imdb"))
        item = _binding_value(binding.get("item"))
        qid = _wikidata_qid(item)
        if imdb and qid:
            matches.add((imdb, qid))

    if len(matches) != 1:
        return None

    imdb_id, wikidata_qid = next(iter(matches))
    return {"imdb_id": imdb_id, "wikidata_qid": wikidata_qid}


def _binding_value(value: Any) -> str | None:
    if not isinstance(value, dict):
        return None
    raw = value.get("value")
    if not isinstance(raw, str):
        return None
    text = raw.strip()
    return text or None


def _wikidata_qid(item_url: str | None) -> str | None:
    if not item_url:
        return None
    candidate = item_url.rstrip("/").rsplit("/", 1)[-1]
    if candidate.startswith("Q") and candidate[1:].isdigit():
        return candidate
    return None


def _detect_external_source(user_message: str) -> str | None:
    normalized = normalize_user_message(user_message)
    if ":" in normalized:
        prefix, _ = normalized.split(":", 1)
        if prefix.strip().casefold() in {"douban", "allocine"}:
            return prefix.strip().casefold()

    parsed = urlparse(normalized)
    host = parsed.netloc.rsplit("@", 1)[-1].split(":", 1)[0].casefold()
    path = unquote(parsed.path)

    if host in {"movie.douban.com", "m.douban.com"} and "/subject/" in path:
        return "douban"
    if host == "allocine.fr" or host.endswith(".allocine.fr"):
        if "/film/" in path or "/series/" in path:
            return "allocine"
    return None


def _unresolved_resolution(*, source: str, source_id: str | None) -> dict[str, str | None]:
    return {
        "source": source,
        "source_id": source_id,
        "imdb_id": None,
        "wikidata_qid": None,
    }
