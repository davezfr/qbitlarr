from __future__ import annotations

import os
from typing import Any

import httpx


DEFAULT_QBITLARR_API_URL = "http://127.0.0.1:8000"


class QbitlarrApiError(RuntimeError):
    def __init__(self, message: str, *, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code


class QbitlarrApiClient:
    def __init__(
        self,
        api_url: str,
        *,
        api_key: str | None = None,
        timeout: float = 30.0,
        transport: httpx.AsyncBaseTransport | httpx.BaseTransport | None = None,
    ) -> None:
        self.api_url = api_url.rstrip("/")
        self.api_key = api_key.strip() if api_key and api_key.strip() else None
        self.timeout = timeout
        self.transport = transport

    async def search(
        self,
        *,
        identifier: str | None = None,
        query: str | None = None,
        categories: list[int] | None = None,
        indexer_ids: list[int] | None = None,
    ) -> list[dict[str, Any]]:
        response = await self._request(
            "POST",
            "/search",
            json={
                "identifier": identifier,
                "query": query,
                "categories": categories,
                "indexer_ids": indexer_ids,
            },
        )
        if not isinstance(response, list):
            raise QbitlarrApiError("qBitlarr API returned an unexpected search response")
        return response

    async def download(self, download_link: str, save_path: str | None = None) -> dict[str, Any]:
        response = await self._request(
            "POST",
            "/download",
            json={"download_link": download_link, "save_path": save_path},
        )
        if not isinstance(response, dict):
            raise QbitlarrApiError("qBitlarr API returned an unexpected download response")
        return response

    async def handle(
        self,
        user_message: str,
        user_id: str | None = None,
        save_path: str | None = None,
        mode: str | None = None,
    ) -> dict[str, Any]:
        response = await self._request(
            "POST",
            "/handle",
            json={
                "user_message": user_message,
                "user_id": user_id,
                "save_path": save_path,
                "mode": mode,
            },
        )
        if not isinstance(response, dict):
            raise QbitlarrApiError("qBitlarr API returned an unexpected handle response")
        return response

    async def health(self, *, deep: bool = False) -> dict[str, Any]:
        kwargs: dict[str, Any] = {}
        if deep:
            kwargs["params"] = {"deep": "true"}
        response = await self._request("GET", "/health", **kwargs)
        if not isinstance(response, dict):
            raise QbitlarrApiError("qBitlarr API returned an unexpected health response")
        return response

    async def list_downloads(self) -> list[dict[str, Any]]:
        response = await self._request("GET", "/downloads")
        if not isinstance(response, list):
            raise QbitlarrApiError("qBitlarr API returned an unexpected downloads response")
        return response

    async def get_download_status(self, info_hash: str) -> dict[str, Any]:
        response = await self._request("GET", f"/downloads/{info_hash}")
        if not isinstance(response, dict):
            raise QbitlarrApiError("qBitlarr API returned an unexpected download status response")
        return response

    async def get_query_snapshot(self, query_id: str) -> dict[str, Any]:
        response = await self._request("GET", f"/queries/{query_id}")
        if not isinstance(response, dict):
            raise QbitlarrApiError("qBitlarr API returned an unexpected query snapshot response")
        return response

    async def list_prowlarr_indexers(self) -> list[dict[str, Any]]:
        response = await self._request("GET", "/prowlarr/indexers")
        if not isinstance(response, list):
            raise QbitlarrApiError("qBitlarr API returned an unexpected Prowlarr indexer response")
        return response

    async def _request(self, method: str, path: str, **kwargs: Any) -> Any:
        headers = dict(kwargs.pop("headers", {}) or {})
        if self.api_key:
            headers["X-API-Key"] = self.api_key
        async with httpx.AsyncClient(
            base_url=self.api_url,
            timeout=self.timeout,
            transport=self.transport,
        ) as client:
            try:
                response = await client.request(method, path, headers=headers, **kwargs)
                response.raise_for_status()
            except httpx.HTTPStatusError as exc:
                raise QbitlarrApiError(
                    _extract_error_detail(exc.response),
                    status_code=exc.response.status_code,
                ) from exc
            except httpx.RequestError as exc:
                raise QbitlarrApiError(f"qBitlarr API is unreachable: {exc.__class__.__name__}") from exc

        try:
            return response.json()
        except ValueError as exc:
            raise QbitlarrApiError("qBitlarr API returned invalid JSON") from exc


def get_qbitlarr_client() -> QbitlarrApiClient:
    return QbitlarrApiClient(
        api_url=os.getenv("QBITLARR_API_URL", DEFAULT_QBITLARR_API_URL),
        api_key=os.getenv("QBITLARR_API_KEY"),
        timeout=float(os.getenv("QBITLARR_API_TIMEOUT_SECONDS", "90")),
    )


def _extract_error_detail(response: httpx.Response) -> str:
    try:
        payload = response.json()
    except ValueError:
        return f"qBitlarr API returned HTTP {response.status_code}"

    if isinstance(payload, dict):
        detail = payload.get("detail")
        if isinstance(detail, str) and detail.strip():
            return detail.strip()

    return f"qBitlarr API returned HTTP {response.status_code}"
