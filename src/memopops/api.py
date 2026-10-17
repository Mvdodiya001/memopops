"""HTTP boundary for authenticated, revision-bound memory queries."""

from __future__ import annotations

from contextlib import asynccontextmanager
from hashlib import sha256
import hmac
import json
import os
from time import monotonic
from typing import Any, Literal, Protocol
from uuid import uuid4

from fastapi import Depends, FastAPI, HTTPException
from fastapi.responses import JSONResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, ConfigDict, Field

from memopops.formula import SEMANTICS_VERSION, formula_hash, formula_to_json, parse_formula
from memopops.solver import classify
from memopops.store import (
    FalkorSnapshotStore,
    IdempotencyConflictError,
    SnapshotIntegrityError,
    SnapshotNotFoundError,
)


class SnapshotReader(Protocol):
    def ping(self) -> bool: ...
    def close(self) -> None: ...
    def load_snapshot(self, workspace_id: str, revision_id: str) -> Any: ...
    def current_head(self, workspace_id: str) -> str | None: ...
    def persist_query_result(
        self,
        workspace_id: str,
        revision_id: str,
        idempotency_key: str,
        request_hash: str,
        result_payload: dict[str, Any],
    ) -> dict[str, Any]: ...


class QueryRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    revision_id: str = Field(min_length=1, max_length=128)
    idempotency_key: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
    query: dict[str, Any]
    # Solver-only stays explicit until the independent certificate lane is integrated.
    proof_mode: Literal["solver"] = "solver"


class RequestBodyLimitMiddleware:
    """Bound bytes and JSON nesting before decoding or model validation."""

    @staticmethod
    def _exceeds_json_depth(body: bytes, max_depth: int = 32) -> bool:
        depth = 0
        in_string = False
        escaped = False
        for byte in body:
            if in_string:
                if escaped:
                    escaped = False
                elif byte == 0x5C:
                    escaped = True
                elif byte == 0x22:
                    in_string = False
                continue
            if byte == 0x22:
                in_string = True
            elif byte in (0x7B, 0x5B):
                depth += 1
                if depth > max_depth:
                    return True
            elif byte in (0x7D, 0x5D):
                depth -= 1
        return False

    def __init__(self, app, max_bytes: int = 65_536):
        self.app = app
        self.max_bytes = max_bytes

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        body = bytearray()
        while True:
            message = await receive()
            if message["type"] == "http.disconnect":
                return
            body.extend(message.get("body", b""))
            if len(body) > self.max_bytes:
                response = JSONResponse(status_code=413, content={"detail": "Request body exceeds 64 KiB"})
                await response(scope, receive, send)
                return
            if not message.get("more_body", False):
                break
        if self._exceeds_json_depth(body):
            response = JSONResponse(status_code=422, content={"detail": "JSON nesting exceeds 32 levels"})
            await response(scope, receive, send)
            return
        replayed = False

        async def replay_receive():
            nonlocal replayed
            if not replayed:
                replayed = True
                return {"type": "http.request", "body": bytes(body), "more_body": False}
            return {"type": "http.request", "body": b"", "more_body": False}

        await self.app(scope, replay_receive, send)


def _request_hash(revision_id: str, query_digest: str, proof_mode: str) -> str:
    payload = json.dumps(
        {"revision_id": revision_id, "query_hash": query_digest, "proof_mode": proof_mode},
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    ).encode("utf-8")
    return sha256(payload).hexdigest()


def create_app(store: SnapshotReader | None = None) -> FastAPI:
    memory_store = store or FalkorSnapshotStore.from_env()
    bearer = HTTPBearer(auto_error=False)

    @asynccontextmanager
    async def lifespan(_app: FastAPI):
        yield
        memory_store.close()

    app = FastAPI(title="Memopops Memory API", version="0.1.0", lifespan=lifespan)
    app.state.memory_store = memory_store
    app.add_middleware(RequestBodyLimitMiddleware, max_bytes=65_536)

    def authenticate(
        credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
    ) -> dict[str, str]:
        if credentials is None or credentials.scheme.lower() != "bearer":
            raise HTTPException(status_code=401, detail="Bearer authentication required")
        try:
            configured = json.loads(os.getenv("MEMOPOPS_AUTH_TOKENS", "{}"))
        except json.JSONDecodeError as exc:
            raise HTTPException(status_code=503, detail="Authentication is misconfigured") from exc
        if not isinstance(configured, dict):
            raise HTTPException(status_code=503, detail="Authentication is misconfigured")
        for token, principal in configured.items():
            if isinstance(token, str) and hmac.compare_digest(token, credentials.credentials):
                if not isinstance(principal, dict):
                    break
                workspace_id = principal.get("workspace_id")
                role = principal.get("role")
                if isinstance(workspace_id, str) and role in {"reader", "writer", "operator"}:
                    return {"workspace_id": workspace_id, "role": role}
                break
        raise HTTPException(status_code=401, detail="Invalid bearer token")

    def authorize_workspace(workspace_id: str, principal: dict[str, str]) -> None:
        if not hmac.compare_digest(principal["workspace_id"], workspace_id):
            raise HTTPException(status_code=404, detail="Workspace not found")

    @app.get("/api/v1/health/live")
    def live() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/api/v1/health/ready")
    def ready() -> dict[str, str]:
        try:
            if not memory_store.ping():
                raise RuntimeError("database ping returned false")
        except Exception as exc:
            raise HTTPException(status_code=503, detail="Memory database is unavailable") from exc
        return {"status": "ready"}

    @app.post("/api/v1/workspaces/{workspace_id}/queries")
    def query_memory(
        workspace_id: str,
        request: QueryRequest,
        principal: dict[str, str] = Depends(authenticate),
    ) -> dict[str, Any]:
        authorize_workspace(workspace_id, principal)
        load_started = monotonic()
        try:
            snapshot = memory_store.load_snapshot(workspace_id, request.revision_id)
        except SnapshotNotFoundError as exc:
            raise HTTPException(status_code=404, detail="Revision not found") from exc
        except SnapshotIntegrityError as exc:
            raise HTTPException(
                status_code=500, detail="Stored memory failed integrity verification"
            ) from exc
        except Exception as exc:
            raise HTTPException(status_code=503, detail="Memory snapshot is unavailable") from exc
        load_ms = int((monotonic() - load_started) * 1_000)

        try:
            formula = parse_formula(request.query, snapshot.atom_ids)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

        query_digest = formula_hash(formula)
        request_digest = _request_hash(request.revision_id, query_digest, request.proof_mode)
        solve_started = monotonic()
        evaluation = classify(snapshot.formulas, formula, timeout_ms=3_000)
        solve_ms = int((monotonic() - solve_started) * 1_000)

        try:
            head = memory_store.current_head(workspace_id)
        except Exception as exc:
            raise HTTPException(status_code=503, detail="Workspace head is unavailable") from exc
        result_payload: dict[str, Any] = {
            "query_id": str(uuid4()),
            "workspace_id": workspace_id,
            "revision_id": snapshot.revision_id,
            "head_revision_observed": head,
            "freshness": "CURRENT_AS_OF_READ" if head == snapshot.revision_id else "HISTORICAL",
            "semantics_version": SEMANTICS_VERSION,
            "knowledge_hash": snapshot.knowledge_hash,
            "query_hash": query_digest,
            "result": evaluation.result.value,
            "proof_status": "NOT_REQUESTED",
            "witnesses_verified": False,
            "certificate_id": None,
            "support_assertion_ids": [],
            "explanation": f"The Boolean query result is {evaluation.result.value} at the requested revision.",
            "solver": {
                "name": "z3",
                "version": evaluation.solver_version,
                "reason_unknown": evaluation.reason_unknown,
            },
            "timings_ms": {"load": load_ms, "solve": solve_ms},
            "witnesses": evaluation.witnesses,
        }
        try:
            return memory_store.persist_query_result(
                workspace_id,
                request.revision_id,
                request.idempotency_key,
                request_digest,
                result_payload,
            )
        except IdempotencyConflictError as exc:
            raise HTTPException(status_code=409, detail="Idempotency key was used for another request") from exc
        except SnapshotNotFoundError as exc:
            raise HTTPException(status_code=404, detail="Revision not found") from exc
        except Exception as exc:
            raise HTTPException(status_code=503, detail="Query result could not be persisted") from exc

    return app


app = create_app()
