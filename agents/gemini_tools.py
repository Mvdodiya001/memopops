"""Gemini native function-calling adapter for bounded agent sessions."""

from __future__ import annotations

import json
import os
import time
from typing import Any, Callable

from agents.model import (
    DEFAULT_LIVE_BASE_URL,
    DEFAULT_LIVE_MODEL,
    LIVE_BASE_ENV,
    LIVE_KEY_ENV,
    LIVE_NAME_ENV,
    MAX_MODEL_CHARS,
    _load_local_model_env,
    generate_content_url,
    post_generate_content,
)


Complete = Callable[[dict[str, Any], float], dict[str, Any]]
Status = Callable[[str], None]

_RETRYABLE_STATUS = ("HTTP 429", "HTTP 500", "HTTP 503")
_BASE_FUNCTIONS = ("inspect_memory", "query_conclusion", "record_decision", "finish")
DEFAULT_REQUEST_TIMEOUT = 10.0
MODEL_TIMEOUT_ENV = "MEMOPOPS_MODEL_TIMEOUT_SECONDS"
RETRY_DELAYS = (0, 2)


def _schema(
    properties: dict[str, dict[str, Any]],
    required: list[str],
) -> dict[str, Any]:
    return {
        "type": "OBJECT",
        "properties": properties,
        "required": required,
    }


def _string(description: str, *, enum: list[str] | None = None) -> dict[str, Any]:
    result: dict[str, Any] = {"type": "STRING", "description": description}
    if enum:
        result["enum"] = enum
    return result


FUNCTION_DECLARATIONS: dict[str, dict[str, Any]] = {
    "inspect_memory": {
        "name": "inspect_memory",
        "description": "Read the accepted memory and current head revision.",
        "parameters": _schema(
            {
                "rationale": _string("One sentence explaining why the read is needed."),
                "revision_id": _string("Optional immutable revision to inspect."),
            },
            ["rationale"],
        ),
    },
    "query_conclusion": {
        "name": "query_conclusion",
        "description": "Ask whether an atom or its negation follows at a revision.",
        "parameters": _schema(
            {
                "rationale": _string("One sentence explaining why this query is needed."),
                "revision_id": _string("Revision returned by inspect_memory."),
                "atom_id": _string("Exact registered atom id returned by inspect_memory."),
                "negated": {"type": "BOOLEAN", "description": "Query NOT atom_id when true."},
                "proof_mode": _string(
                    "Use certificate for decisive release queries; solver for uncertainty checks.",
                    enum=["certificate", "solver"],
                ),
            },
            ["rationale", "revision_id", "atom_id"],
        ),
    },
    "propose_assertion": {
        "name": "propose_assertion",
        "description": "Submit an evidence-backed assertion for service validation.",
        "parameters": _schema(
            {
                "rationale": _string("One sentence explaining why this proposal is needed."),
                "expected_revision_id": _string("Current head returned by inspect_memory."),
                "atom_id": _string("Exact registered atom id returned by inspect_memory."),
                "negated": {"type": "BOOLEAN", "description": "Propose NOT atom_id when true."},
                "reason": _string("Concise reason for the proposed memory."),
                "client_ref": _string("Stable client reference for this observation."),
                "evidence_uri": _string("URI identifying the evidence source."),
                "evidence_excerpt": _string("Short evidence excerpt."),
                "observed_at": _string("RFC3339 UTC timestamp for the observation."),
            },
            [
                "rationale",
                "expected_revision_id",
                "atom_id",
                "negated",
                "reason",
                "client_ref",
                "evidence_uri",
                "evidence_excerpt",
                "observed_at",
            ],
        ),
    },
    "record_decision": {
        "name": "record_decision",
        "description": "Record the decision that follows a revision-bound query result.",
        "parameters": _schema(
            {
                "rationale": _string("One sentence explaining why this choice follows."),
                "expected_revision_id": _string("Revision used by the query."),
                "query_id": _string("Query id returned by query_conclusion."),
                "choice": _string(
                    "Choice implied by the result.",
                    enum=["ship", "hold", "abstain"],
                ),
            },
            ["rationale", "expected_revision_id", "query_id", "choice"],
        ),
    },
    "finish": {
        "name": "finish",
        "description": "Finish after the required memory operation and decision are complete.",
        "parameters": _schema(
            {
                "rationale": _string("One sentence explaining why the task is complete."),
                "summary": _string("One-sentence factual summary of the service outcome."),
            },
            ["rationale", "summary"],
        ),
    },
}


def _formula(atom_id: str, negated: bool) -> dict[str, Any]:
    atom: dict[str, Any] = {"op": "atom", "id": atom_id}
    return {"op": "not", "arg": atom} if negated else atom


def _role_card(role: str, workspace_id: str, goal: str) -> str:
    if role == "writer":
        return (
            f"You are a writer agent for workspace {workspace_id}. You can only call the "
            "provided functions. You may propose memory; you cannot activate it. The service "
            "decides acceptance. First inspect_memory. Then propose_assertion for exactly the "
            "fact in your goal, using a registered atom id and the supplied evidence. Then "
            "finish and state the service outcome. Each call needs a one-sentence rationale. "
            f"Goal: {goal}"
        )
    return (
        f"You are a release reader agent for workspace {workspace_id}. You can only call the "
        "provided functions. Never invent atom ids. First inspect_memory, then "
        "query_conclusion at the returned head, then record_decision: PROVED means ship, "
        "REFUTED means hold, every other result means abstain. If prior decision fields are "
        "present, first record that prior decision at its original revision; after a "
        "REVISION_CONFLICT inspect and query the new head. Then finish. Each call needs a "
        f"one-sentence rationale. Goal: {goal}"
    )


def _response_parts(parsed: dict[str, Any]) -> list[dict[str, Any]]:
    candidates = parsed.get("candidates")
    if not isinstance(candidates, list) or not candidates:
        raise ValueError("model response has no candidates")
    candidate = candidates[0]
    content = candidate.get("content") if isinstance(candidate, dict) else None
    parts = content.get("parts") if isinstance(content, dict) else None
    if not isinstance(parts, list):
        raise ValueError("model response has no content parts")
    return [part for part in parts if isinstance(part, dict)]


class GeminiFunctionCallingModel:
    """Translate Gemini function calls into the existing AgentSession contract."""

    mode = "live_model"
    supports_tools = True

    def __init__(
        self,
        complete: Complete,
        *,
        role: str,
        goal: str,
        workspace_id: str,
        model_name: str = DEFAULT_LIVE_MODEL,
        endpoint_url: str = "",
        prior_decision: dict[str, Any] | None = None,
        sleep: Callable[[float], None] = time.sleep,
        request_timeout: float = DEFAULT_REQUEST_TIMEOUT,
        status: Status | None = None,
    ):
        if role not in {"reader", "writer"}:
            raise ValueError("role must be reader or writer")
        if not 1 <= request_timeout <= 120:
            raise ValueError("request_timeout must be between 1 and 120 seconds")
        self._complete = complete
        self._sleep = sleep
        self._status = status or (lambda _message: None)
        self.request_timeout = request_timeout
        self.role = role
        self.goal = goal
        self.workspace_id = workspace_id
        self.model_name = model_name
        self.endpoint_url = endpoint_url
        self.prior_decision = dict(prior_decision) if prior_decision else None
        self.allowed_names = list(_BASE_FUNCTIONS)
        if role == "writer":
            self.allowed_names.insert(2, "propose_assertion")
        self.contents: list[dict[str, Any]] = []
        self.last_function_name: str | None = None
        self.last_rationale = ""
        self.transcript: list[dict[str, Any]] = []
        self._text_replies = 0

    @classmethod
    def from_env(
        cls,
        role: str,
        goal: str,
        *,
        workspace_id: str,
        prior_decision: dict[str, Any] | None = None,
        request_timeout: float | None = None,
        status: Status | None = None,
    ) -> "GeminiFunctionCallingModel | None":
        _load_local_model_env()
        api_key = os.getenv(LIVE_KEY_ENV)
        if not api_key:
            return None
        model_name = os.getenv(LIVE_NAME_ENV) or DEFAULT_LIVE_MODEL
        base_url = os.getenv(LIVE_BASE_ENV) or DEFAULT_LIVE_BASE_URL
        endpoint_url = generate_content_url(base_url, model_name)
        if request_timeout is None:
            configured_timeout = os.getenv(MODEL_TIMEOUT_ENV)
            try:
                request_timeout = (
                    float(configured_timeout)
                    if configured_timeout
                    else DEFAULT_REQUEST_TIMEOUT
                )
            except ValueError as exc:
                raise ValueError(f"{MODEL_TIMEOUT_ENV} must be a number") from exc

        def complete(payload: dict[str, Any], timeout: float) -> dict[str, Any]:
            return post_generate_content(endpoint_url, api_key, payload, timeout=timeout)

        return cls(
            complete,
            role=role,
            goal=goal,
            workspace_id=workspace_id,
            model_name=model_name,
            endpoint_url=endpoint_url,
            prior_decision=prior_decision,
            request_timeout=request_timeout,
            status=status,
        )

    def _payload(self) -> dict[str, Any]:
        declarations = [FUNCTION_DECLARATIONS[name] for name in self.allowed_names]
        return {
            "systemInstruction": {
                "parts": [{"text": _role_card(self.role, self.workspace_id, self.goal)}]
            },
            "contents": self.contents,
            "tools": [{"functionDeclarations": declarations}],
            "toolConfig": {
                "functionCallingConfig": {
                    "mode": "ANY",
                    "allowedFunctionNames": self.allowed_names,
                }
            },
            "generationConfig": {"temperature": 0},
        }

    def _call(self) -> dict[str, Any]:
        last_error: Exception | None = None
        for attempt, delay in enumerate(RETRY_DELAYS, start=1):
            if delay:
                self._status(f"retrying in {delay}s")
                self._sleep(delay)
            self._status(
                f"request attempt {attempt}/{len(RETRY_DELAYS)} "
                f"(timeout {self.request_timeout:g}s)"
            )
            try:
                response = self._complete(self._payload(), self.request_timeout)
                self._status("response received")
                return response
            except (TimeoutError, OSError, RuntimeError) as exc:
                retryable = not isinstance(exc, RuntimeError) or any(
                    marker in str(exc) for marker in _RETRYABLE_STATUS
                )
                if not retryable or attempt == len(RETRY_DELAYS):
                    self._status(
                        f"request failed after {attempt} attempt(s): "
                        f"{exc.__class__.__name__}"
                    )
                    raise
                self._status(
                    f"attempt {attempt}/{len(RETRY_DELAYS)} failed: "
                    f"{exc.__class__.__name__}"
                )
                last_error = exc
        assert last_error is not None
        raise last_error

    def next_action(self, observation: dict[str, Any]) -> dict[str, Any]:
        safe_observation = dict(observation)
        if not self.contents and self.prior_decision:
            safe_observation.update(
                {
                    "prior_decision_revision_id": self.prior_decision.get("revision_id"),
                    "prior_decision_query_id": self.prior_decision.get("query_id"),
                    "prior_decision_choice": self.prior_decision.get("choice"),
                }
            )
        encoded = json.dumps(safe_observation, sort_keys=True, default=str)
        encoded = encoded[:MAX_MODEL_CHARS]
        if self.last_function_name:
            self.contents.append(
                {
                    "role": "user",
                    "parts": [
                        {
                            "functionResponse": {
                                "name": self.last_function_name,
                                "response": {"event": json.loads(encoded)},
                            }
                        }
                    ],
                }
            )
        else:
            self.contents.append({"role": "user", "parts": [{"text": encoded}]})

        parsed = self._call()
        parts = _response_parts(parsed)
        self.contents.append({"role": "model", "parts": parts})
        function_part = next(
            (part["functionCall"] for part in parts if isinstance(part.get("functionCall"), dict)),
            None,
        )
        if function_part is None:
            text = "".join(
                str(part.get("text", "")) for part in parts if isinstance(part.get("text"), str)
            )[:MAX_MODEL_CHARS]
            self._text_replies += 1
            self.last_function_name = None
            self.transcript.append({"type": "text", "text": text[:2_000]})
            if self._text_replies >= 2:
                return {"type": "stop"}
            return {"type": "text", "content": text}

        self._text_replies = 0
        name = function_part.get("name")
        raw_arguments = function_part.get("args", {})
        arguments = dict(raw_arguments) if isinstance(raw_arguments, dict) else {}
        if not isinstance(name, str) or name not in self.allowed_names:
            return {"type": "stop"}
        rationale = arguments.pop("rationale", "")
        self.last_rationale = str(rationale)[:2_000]
        self.last_function_name = name
        action = self._map_action(name, arguments)
        self.transcript.append(
            {
                "type": "function_call",
                "name": name,
                "rationale": self.last_rationale,
                "arguments": action.get("arguments", {}),
            }
        )
        return action

    def _map_action(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        if name == "finish":
            summary = str(arguments.get("summary", "")).strip()
            if summary:
                self.last_rationale = summary[:2_000]
            return {"type": "stop"}
        if name == "inspect_memory":
            mapped: dict[str, Any] = {}
            revision_id = arguments.get("revision_id")
            if isinstance(revision_id, str) and revision_id:
                mapped["revision_id"] = revision_id
            return {"type": "tool", "name": name, "arguments": mapped}
        if name == "query_conclusion":
            atom_id = str(arguments.get("atom_id", ""))
            return {
                "type": "tool",
                "name": name,
                "arguments": {
                    "revision_id": str(arguments.get("revision_id", "")),
                    "query": _formula(atom_id, bool(arguments.get("negated", False))),
                    "proof_mode": str(arguments.get("proof_mode", "certificate")),
                },
            }
        if name == "propose_assertion":
            atom_id = str(arguments.get("atom_id", ""))
            return {
                "type": "tool",
                "name": name,
                "arguments": {
                    "expected_revision_id": str(arguments.get("expected_revision_id", "")),
                    "atom_id": atom_id,
                    "formula": _formula(atom_id, bool(arguments.get("negated", False))),
                    "reason": str(arguments.get("reason", "")),
                    "client_ref": str(arguments.get("client_ref", "")),
                    "evidence": {
                        "uri": str(arguments.get("evidence_uri", "")),
                        "excerpt": str(arguments.get("evidence_excerpt", "")),
                        "observed_at": str(arguments.get("observed_at", "")),
                    },
                },
            }
        return {
            "type": "tool",
            "name": "record_decision",
            "arguments": {
                "expected_revision_id": str(arguments.get("expected_revision_id", "")),
                "query_id": str(arguments.get("query_id", "")),
                "choice": str(arguments.get("choice", "")),
            },
        }
