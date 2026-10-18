"""Small client for the published workspace, memory, query, and revision routes."""

from __future__ import annotations

from typing import Any, Protocol


class MemoryTransport(Protocol):
    def request(
        self,
        method: str,
        path: str,
        body: dict[str, Any] | None,
        token: str,
    ) -> tuple[int, dict[str, Any]]: ...


class MemoryClient:
    def __init__(self, transport: MemoryTransport, token: str, workspace_id: str):
        self.transport = transport
        self.token = token
        self.workspace_id = workspace_id

    def _request(
        self, method: str, path: str, body: dict[str, Any] | None = None
    ) -> tuple[int, dict[str, Any]]:
        last_error: Exception | None = None
        for _attempt in range(2):
            try:
                return self.transport.request(method, path, body, self.token)
            except OSError as exc:
                last_error = exc
        assert last_error is not None
        raise last_error

    def workspace(self) -> tuple[int, dict[str, Any]]:
        return self._request("GET", f"/api/v1/workspaces/{self.workspace_id}")

    def memory(self, revision_id: str | None = None) -> tuple[int, dict[str, Any]]:
        path = f"/api/v1/workspaces/{self.workspace_id}/memory"
        if revision_id:
            path += f"?revision_id={revision_id}"
        return self._request("GET", path)

    def revisions(self) -> tuple[int, dict[str, Any]]:
        return self._request("GET", f"/api/v1/workspaces/{self.workspace_id}/revisions")

    def proposals(self) -> tuple[int, dict[str, Any]]:
        return self._request(
            "GET",
            f"/api/v1/workspaces/{self.workspace_id}/proposals?status=QUARANTINED",
        )

    def impact(self, revision_id: str) -> tuple[int, dict[str, Any]]:
        return self._request(
            "GET",
            f"/api/v1/workspaces/{self.workspace_id}/impact?revision={revision_id}&limit=50",
        )

    def query_result(self, query_id: str) -> tuple[int, dict[str, Any]]:
        return self._request(
            "GET", f"/api/v1/workspaces/{self.workspace_id}/queries/{query_id}"
        )

    def certificate(self, query_id: str) -> tuple[int, dict[str, Any]]:
        return self._request(
            "GET",
            f"/api/v1/workspaces/{self.workspace_id}/queries/{query_id}/certificate",
        )

    def submit_query(self, body: dict[str, Any]) -> tuple[int, dict[str, Any]]:
        return self._request(
            "POST", f"/api/v1/workspaces/{self.workspace_id}/queries", body
        )

    def submit_revision(self, body: dict[str, Any]) -> tuple[int, dict[str, Any]]:
        return self._request(
            "POST", f"/api/v1/workspaces/{self.workspace_id}/revisions", body
        )

    def submit_decision(self, body: dict[str, Any]) -> tuple[int, dict[str, Any]]:
        return self._request(
            "POST", f"/api/v1/workspaces/{self.workspace_id}/decisions", body
        )
