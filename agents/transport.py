"""HTTP transports for the memory client. Neither one stores credentials."""

from __future__ import annotations

import asyncio
import json
from typing import Any
from urllib import error, request


class AsgiTransport:
    """Call an in-process FastAPI app. Used by replay tests, not by a browser."""

    def __init__(self, app: Any):
        self.app = app

    def request(
        self,
        method: str,
        path: str,
        body: dict[str, Any] | None,
        token: str,
    ) -> tuple[int, dict[str, Any]]:
        async def send() -> tuple[int, dict[str, Any]]:
            import httpx

            headers = {"Authorization": f"Bearer {token}"}
            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app=self.app),
                base_url="http://testserver",
            ) as client:
                response = await client.request(method, path, json=body, headers=headers)
            try:
                parsed = response.json()
            except ValueError:
                parsed = {"detail": response.text[:500]}
            if not isinstance(parsed, dict):
                parsed = {"detail": parsed}
            return response.status_code, parsed

        return asyncio.run(send())


class UrlTransport:
    """Call a running memory API. The bearer token is sent and not recorded."""

    def __init__(self, base_url: str, timeout_seconds: float = 30):
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds

    def request(
        self,
        method: str,
        path: str,
        body: dict[str, Any] | None,
        token: str,
    ) -> tuple[int, dict[str, Any]]:
        payload = None if body is None else json.dumps(body).encode("utf-8")
        req = request.Request(self.base_url + path, data=payload, method=method)
        req.add_header("Authorization", f"Bearer {token}")
        req.add_header("Accept", "application/json")
        if payload is not None:
            req.add_header("Content-Type", "application/json")
        try:
            with request.urlopen(req, timeout=self.timeout_seconds) as response:
                raw = response.read()
                parsed = json.loads(raw.decode("utf-8")) if raw else {}
                if not isinstance(parsed, dict):
                    parsed = {"detail": parsed}
                return response.status, parsed
        except error.HTTPError as exc:
            raw = exc.read()
            try:
                parsed = json.loads(raw.decode("utf-8")) if raw else {}
            except json.JSONDecodeError:
                parsed = {"detail": raw.decode("utf-8", "replace")[:500]}
            if not isinstance(parsed, dict):
                parsed = {"detail": parsed}
            return exc.code, parsed
