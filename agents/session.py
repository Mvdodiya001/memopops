"""Bounded agent session. Decisions are local receipts checked against the live head."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any
from uuid import uuid4

from agents.client import MemoryClient
from memopops.formula import FormulaValidationError, formula_atoms, parse_formula


MAX_STEPS = 6
MAX_ARGUMENT_CHARS = 4_000
_KEY_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
_SECRET_KEYS = {
    "token",
    "authorization",
    "api_key",
    "password",
    "secret",
    "bearer",
    "credentials",
}
_READER_TOOLS = {"inspect_memory", "query_conclusion", "record_decision"}
_WRITER_TOOLS = _READER_TOOLS | {"propose_assertion"}
_CHOICE_FOR_RESULT = {
    "PROVED": "ship",
    "REFUTED": "hold",
    "UNKNOWN": "abstain",
    "INCONSISTENT_MEMORY": "abstain",
    "SOLVER_UNKNOWN": "abstain",
}


def redact(value: Any, token: str) -> Any:
    """Drop credential fields and any copy of the bearer token."""
    if isinstance(value, dict):
        cleaned = {}
        for key, item in value.items():
            if str(key).lower() in _SECRET_KEYS:
                continue
            cleaned[str(key)] = redact(item, token)
        return cleaned
    if isinstance(value, list):
        return [redact(item, token) for item in value]
    if isinstance(value, str):
        if token:
            value = value.replace(token, "[redacted]")
        if len(value) > 2_000:
            return value[:2_000]
        return value
    if isinstance(value, (int, float, bool)) or value is None:
        return value
    return str(value)[:500]


class AgentSession:
    def __init__(
        self,
        *,
        client: MemoryClient,
        model: Any,
        role: str,
        workspace_id: str,
        mode: str,
        journal_path: Path,
        session_id: str | None = None,
    ):
        if role not in {"reader", "writer", "operator"}:
            raise ValueError("role must be reader, writer, or operator")
        if mode not in {"scripted_replay", "live_model"}:
            raise ValueError("mode must be scripted_replay or live_model")
        self.client = client
        self.model = model
        self.role = role
        self.workspace_id = workspace_id
        self.mode = mode
        self.journal_path = Path(journal_path)
        self.session_id = session_id or uuid4().hex
        self.events: list[dict[str, Any]] = []
        self.decisions: list[dict[str, Any]] = []
        self.executed_steps = 0

    @classmethod
    def resume(
        cls,
        path: Path,
        *,
        client: MemoryClient,
        model: Any,
        role: str,
        mode: str,
    ) -> "AgentSession":
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            raise ValueError("journal must be an object")
        if any(key in data for key in _SECRET_KEYS):
            raise ValueError("journal must not carry credentials")
        if data.get("role") != role or data.get("workspace_id") != client.workspace_id:
            raise ValueError("journal identity does not match this client")
        session = cls(
            client=client,
            model=model,
            role=role,
            workspace_id=client.workspace_id,
            mode=mode,
            journal_path=path,
            session_id=str(data["session_id"]),
        )
        session.events = list(data.get("events", []))
        session.decisions = list(data.get("decisions", []))
        return session

    def current_decision(self) -> dict[str, Any] | None:
        current = [item for item in self.decisions if item.get("status") == "current"]
        return current[-1] if current else None

    def run(self) -> dict[str, Any]:
        observation: dict[str, Any] = {
            "type": "start",
            "workspace_id": self.workspace_id,
            "role": self.role,
            "mode": self.mode,
        }
        prior = self.current_decision()
        if prior:
            observation["prior_decision_revision_id"] = prior["revision_id"]
        stopped = "model_stop"
        while True:
            action = self.model.next_action(observation)
            if not isinstance(action, dict) or action.get("type") in (None, "stop"):
                break
            if self.executed_steps >= MAX_STEPS:
                self._record(
                    {
                        "outcome": "budget_exceeded",
                        "tool": action.get("name"),
                        "detail": f"tool steps are capped at {MAX_STEPS}",
                    }
                )
                stopped = "budget"
                break
            self.executed_steps += 1
            observation = self._handle(action)
        self.save()
        return self.snapshot(stopped_reason=stopped)

    def snapshot(self, stopped_reason: str) -> dict[str, Any]:
        return {
            "session_id": self.session_id,
            "role": self.role,
            "mode": self.mode,
            "workspace_id": self.workspace_id,
            "stopped_reason": stopped_reason,
            "executed_steps": self.executed_steps,
            "events": self.events,
            "decisions": self.decisions,
        }

    def save(self) -> None:
        payload = {
            "session_id": self.session_id,
            "workspace_id": self.workspace_id,
            "role": self.role,
            "mode": self.mode,
            "events": self.events,
            "decisions": self.decisions,
        }
        self.journal_path.parent.mkdir(parents=True, exist_ok=True)
        self.journal_path.write_text(
            json.dumps(redact(payload, self.client.token), indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )

    def _handle(self, action: dict[str, Any]) -> dict[str, Any]:
        if action.get("type") == "text":
            return self._record(
                {
                    "outcome": "ignored_text",
                    "tool": None,
                    "detail": "text is not a tool call and was not executed",
                }
            )
        if action.get("type") != "tool":
            return self._record(
                {"outcome": "rejected", "tool": None, "detail": "action type is not allowed"}
            )
        name = action.get("name")
        arguments = action.get("arguments", {})
        if not isinstance(name, str) or name not in _WRITER_TOOLS:
            return self._record(
                {
                    "outcome": "tool_not_allowed",
                    "tool": name if isinstance(name, str) else None,
                    "detail": "only inspect_memory, query_conclusion, propose_assertion, and record_decision are available",
                }
            )
        if self.role == "reader" and name not in _READER_TOOLS:
            return self._record(
                {
                    "outcome": "tool_not_allowed",
                    "tool": name,
                    "detail": "reader cannot propose or activate premises",
                }
            )
        if not isinstance(arguments, dict):
            return self._record(
                {"outcome": "rejected", "tool": name, "detail": "arguments must be an object"}
            )
        encoded = json.dumps(arguments, sort_keys=True, default=str)
        if len(encoded) > MAX_ARGUMENT_CHARS:
            return self._record(
                {
                    "outcome": "rejected",
                    "tool": name,
                    "detail": "arguments exceed 4000 characters",
                }
            )
        try:
            if name == "inspect_memory":
                result = self._inspect(arguments)
            elif name == "query_conclusion":
                result = self._query(arguments)
            elif name == "propose_assertion":
                result = self._propose(arguments)
            else:
                result = self._decide(arguments)
        except OSError as exc:
            result = {"outcome": "error", "tool": name, "detail": f"transport failed: {exc.__class__.__name__}"}
        return self._record(result)

    def _record(self, result: dict[str, Any]) -> dict[str, Any]:
        event = redact(
            {
                "event_id": f"e{len(self.events) + 1}",
                "session_id": self.session_id,
                "actor_role": self.role,
                "mode": self.mode,
                **result,
            },
            self.client.token,
        )
        self.events.append(event)
        self.save()
        return event

    def _inspect(self, arguments: dict[str, Any]) -> dict[str, Any]:
        allowed = {"revision_id"}
        if set(arguments) - allowed:
            return {"outcome": "rejected", "tool": "inspect_memory", "detail": "unexpected arguments"}
        status, workspace = self.client.workspace()
        if status != 200:
            return _http_error("inspect_memory", status, workspace)
        revision_id = arguments.get("revision_id") or workspace.get("head_revision_id")
        if not isinstance(revision_id, str):
            return {"outcome": "error", "tool": "inspect_memory", "detail": "workspace has no head revision"}
        memory_status, memory = self.client.memory(revision_id)
        if memory_status != 200:
            return _http_error("inspect_memory", memory_status, memory)
        assertions = [
            {"id": item["id"], "formula": item["formula"]}
            for item in memory.get("assertions", [])
            if isinstance(item, dict) and "id" in item and "formula" in item
        ]
        return {
            "outcome": "ok",
            "tool": "inspect_memory",
            "revision_id": memory.get("revision_id"),
            "head_revision_id": workspace.get("head_revision_id"),
            "role": workspace.get("role"),
            "atom_ids": memory.get("atom_ids", []),
            "assertions": assertions,
        }

    def _query(self, arguments: dict[str, Any]) -> dict[str, Any]:
        allowed = {"revision_id", "query", "proof_mode", "idempotency_key"}
        if set(arguments) - allowed:
            return {"outcome": "rejected", "tool": "query_conclusion", "detail": "unexpected arguments"}
        revision_id = arguments.get("revision_id")
        query = arguments.get("query")
        if not isinstance(revision_id, str) or not isinstance(query, dict):
            return {
                "outcome": "pending_review",
                "tool": "query_conclusion",
                "detail": "query requires a revision id and a Boolean AST",
            }
        proof_mode = arguments.get("proof_mode", "certificate")
        if not isinstance(proof_mode, str) or proof_mode not in {"certificate", "solver"}:
            return {"outcome": "rejected", "tool": "query_conclusion", "detail": "unknown proof mode"}
        key = arguments.get("idempotency_key") or f"q{self.executed_steps}{self.session_id[:8]}"
        if not isinstance(key, str) or _KEY_PATTERN.fullmatch(key) is None:
            return {"outcome": "rejected", "tool": "query_conclusion", "detail": "invalid idempotency key"}
        status, body = self.client.submit_query(
            {
                "revision_id": revision_id,
                "idempotency_key": key,
                "query": query,
                "proof_mode": proof_mode,
            }
        )
        if status != 200:
            if status == 422:
                return {
                    "outcome": "pending_review",
                    "tool": "query_conclusion",
                    "status_code": status,
                    "detail": body.get("detail", "query was rejected"),
                }
            return _http_error("query_conclusion", status, body)
        return {
            "outcome": "ok",
            "tool": "query_conclusion",
            "query_id": body.get("query_id"),
            "revision_id": body.get("revision_id"),
            "head_revision_id": body.get("head_revision_observed"),
            "result": body.get("result"),
            "proof_status": body.get("proof_status"),
            "freshness": body.get("freshness"),
            "support_assertion_ids": body.get("support_assertion_ids", []),
        }

    def _propose(self, arguments: dict[str, Any]) -> dict[str, Any]:
        allowed = {
            "expected_revision_id",
            "atom_id",
            "formula",
            "reason",
            "client_ref",
            "evidence",
        }
        if set(arguments) - allowed:
            return {"outcome": "rejected", "tool": "propose_assertion", "detail": "unexpected arguments"}
        pending = _pending_proposal(arguments, self.client)
        if pending is not None:
            return pending
        key = f"p{self.executed_steps}{self.session_id[:8]}"
        status, body = self.client.submit_revision(
            {
                "expected_revision": arguments["expected_revision_id"],
                "idempotency_key": key,
                "reason": arguments["reason"],
                "acceptance": "human_confirmed",
                "mutations": [
                    {
                        "op": "add",
                        "assertion": {
                            "client_ref": arguments["client_ref"],
                            "formula": arguments["formula"],
                            "evidence": [arguments["evidence"]],
                        },
                    }
                ],
            }
        )
        base = {"tool": "propose_assertion", "status_code": status}
        if status == 403:
            return {**base, "outcome": "rejected", "detail": body.get("detail")}
        if status == 409:
            return {
                **base,
                "outcome": "conflict",
                "detail": body.get("detail"),
                "head_revision_id": _detail_head(body),
            }
        if status in {200, 201} and body.get("status") == "QUARANTINED":
            return {
                **base,
                "outcome": "quarantined",
                "proposal_id": body.get("proposal_id"),
                "base_revision_id": body.get("base_revision_id"),
            }
        if status == 201 and body.get("status") == "COMMITTED":
            return {**base, "outcome": "committed", "revision_id": body.get("revision_id")}
        return {**base, "outcome": "error", "detail": body.get("detail")}

    def _decide(self, arguments: dict[str, Any]) -> dict[str, Any]:
        allowed = {"expected_revision_id", "query_id", "choice"}
        if set(arguments) - allowed or set(allowed) - set(arguments):
            return {"outcome": "rejected", "tool": "record_decision", "detail": "unexpected arguments"}
        expected = arguments["expected_revision_id"]
        query_id = arguments["query_id"]
        choice = arguments["choice"]
        if not isinstance(expected, str) or not isinstance(query_id, str):
            return {"outcome": "rejected", "tool": "record_decision", "detail": "ids must be strings"}
        if not isinstance(choice, str) or choice not in {"ship", "hold", "abstain"}:
            return {"outcome": "rejected", "tool": "record_decision", "detail": "choice must be ship, hold, or abstain"}
        status, workspace = self.client.workspace()
        if status != 200:
            return _http_error("record_decision", status, workspace)
        head = workspace.get("head_revision_id")
        if head != expected:
            return {
                "outcome": "conflict",
                "tool": "record_decision",
                "code": "REVISION_CONFLICT",
                "expected_revision_id": expected,
                "head_revision_id": head,
                "detail": "head advanced; reread memory before recording a current decision",
            }
        query_status, query = self.client.query_result(query_id)
        if query_status != 200:
            return _http_error("record_decision", query_status, query)
        if query.get("revision_id") != expected:
            return {
                "outcome": "rejected",
                "tool": "record_decision",
                "detail": "query is not bound to the expected revision",
            }
        result = query.get("result")
        proof_status = query.get("proof_status")
        expected_choice = _CHOICE_FOR_RESULT.get(str(result))
        if choice != expected_choice:
            return {
                "outcome": "rejected",
                "tool": "record_decision",
                "detail": f"choice {choice} does not follow result {result}",
            }
        if choice in {"ship", "hold"} and proof_status not in {"VERIFIED", "NOT_REQUESTED"}:
            return {
                "outcome": "rejected",
                "tool": "record_decision",
                "detail": "a decisive choice needs a verified certificate or an explicit solver-only result",
            }
        if choice == "abstain":
            local = _local_decision(expected, query_id, choice, result, proof_status)
            self._mark_current(local)
            return {"outcome": "ok", "tool": "record_decision", **local, "persisted": False}

        outcome = "PROCEED" if choice == "ship" else "BLOCK"
        rationale = {
            "ship": "Query is PROVED at the requested revision.",
            "hold": "Query is REFUTED at the requested revision.",
        }[choice]
        key = f"d{self.executed_steps}{self.session_id[:8]}"
        api_status, api_body = self.client.submit_decision(
            {
                "expected_revision": expected,
                "query_id": query_id,
                "idempotency_key": key,
                "outcome": outcome,
                "rationale": rationale,
            }
        )
        if api_status == 409:
            detail = api_body.get("detail")
            if isinstance(detail, dict) and detail.get("code") == "REVISION_CONFLICT":
                return {
                    "outcome": "conflict",
                    "tool": "record_decision",
                    "code": "REVISION_CONFLICT",
                    "expected_revision_id": expected,
                    "head_revision_id": detail.get("actual_revision"),
                    "detail": "head advanced; reread memory before recording a current decision",
                }
            return _http_error("record_decision", api_status, api_body)
        if api_status not in {200, 201}:
            return _http_error("record_decision", api_status, api_body)

        local = _local_decision(expected, query_id, choice, result, proof_status)
        local["decision_id"] = api_body.get("decision_id", local["decision_id"])
        local["outcome"] = api_body.get("outcome", outcome)
        local["persisted"] = True
        self._mark_current(local)
        return {"outcome": "ok", "tool": "record_decision", **local}

    def _mark_current(self, decision: dict[str, Any]) -> None:
        for item in self.decisions:
            if item.get("status") == "current":
                item["status"] = "historical"
        self.decisions.append(decision)


def _local_decision(
    revision_id: str,
    query_id: str,
    choice: str,
    result: Any,
    proof_status: Any,
) -> dict[str, Any]:
    return {
        "decision_id": f"d{uuid4().hex[:12]}",
        "revision_id": revision_id,
        "query_id": query_id,
        "choice": choice,
        "result": result,
        "proof_status": proof_status,
        "proof_verified": proof_status == "VERIFIED",
        "status": "current",
    }


def _pending_proposal(arguments: dict[str, Any], client: MemoryClient) -> dict[str, Any] | None:
    required = {"expected_revision_id", "atom_id", "formula", "reason", "client_ref", "evidence"}
    if set(arguments) != required:
        return {"outcome": "rejected", "tool": "propose_assertion", "detail": "missing proposal fields"}
    if not isinstance(arguments["atom_id"], str) or not arguments["atom_id"]:
        return {
            "outcome": "pending_review",
            "tool": "propose_assertion",
            "detail": "explicit atom mapping is required",
        }
    formula = arguments["formula"]
    if not isinstance(formula, dict):
        return {
            "outcome": "pending_review",
            "tool": "propose_assertion",
            "detail": "formula must be a Boolean AST with an explicit atom id",
        }
    evidence = arguments["evidence"]
    if not isinstance(evidence, dict) or set(evidence) != {"uri", "excerpt", "observed_at"}:
        return {"outcome": "rejected", "tool": "propose_assertion", "detail": "evidence is incomplete"}
    if not all(isinstance(arguments[key], str) and arguments[key].strip() for key in ("reason", "client_ref", "expected_revision_id")):
        return {"outcome": "rejected", "tool": "propose_assertion", "detail": "proposal text fields must be nonempty strings"}
    status, memory = client.memory(arguments["expected_revision_id"])
    if status != 200:
        return _http_error("propose_assertion", status, memory)
    registered = set(memory.get("atom_ids", []))
    try:
        parsed = parse_formula(formula, registered)
    except FormulaValidationError as exc:
        detail = str(exc)
        if "unregistered atom" in detail:
            detail = "explicit atom mapping does not match a registered atom"
        return {"outcome": "pending_review", "tool": "propose_assertion", "detail": detail}
    if arguments["atom_id"] not in formula_atoms(parsed):
        return {
            "outcome": "pending_review",
            "tool": "propose_assertion",
            "detail": "atom mapping does not match the formula",
        }
    return None


def _http_error(tool: str, status: int, body: dict[str, Any]) -> dict[str, Any]:
    outcome = "conflict" if status == 409 else "rejected" if status in {401, 403, 422} else "error"
    return {
        "outcome": outcome,
        "tool": tool,
        "status_code": status,
        "detail": body.get("detail"),
    }


def _detail_head(body: dict[str, Any]) -> str | None:
    detail = body.get("detail")
    if isinstance(detail, dict):
        actual = detail.get("actual_revision")
        return actual if isinstance(actual, str) else None
    return None
