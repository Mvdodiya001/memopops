"""Model adapters. Scripted replay is the default; live calls need explicit credentials."""

from __future__ import annotations

import json
import os
from typing import Any, Callable
from urllib import request


LIVE_KEY_ENV = "MEMOPOPS_MODEL_API_KEY"
LIVE_BASE_ENV = "MEMOPOPS_MODEL_BASE_URL"
LIVE_NAME_ENV = "MEMOPOPS_MODEL_NAME"
MAX_MODEL_CHARS = 8_000

TOOL_SPEC = [
    {
        "name": "inspect_memory",
        "description": "Read the workspace head and accepted assertions.",
        "parameters": {"type": "object", "properties": {"revision_id": {"type": "string"}}},
    },
    {
        "name": "query_conclusion",
        "description": "Ask what follows from one revision.",
        "parameters": {"type": "object"},
    },
    {
        "name": "propose_assertion",
        "description": "Propose an assertion. The service decides whether it is accepted.",
        "parameters": {"type": "object"},
    },
    {
        "name": "record_decision",
        "description": "Record a decision bound to a query revision.",
        "parameters": {"type": "object"},
    },
]


def live_credentials_present() -> bool:
    return bool(os.getenv(LIVE_KEY_ENV) and os.getenv(LIVE_BASE_ENV))


class ScriptedActions:
    """Return a fixed list of actions. Callables receive the latest observation."""

    def __init__(self, actions: list[dict[str, Any] | Callable[[dict[str, Any]], dict[str, Any]]]):
        self.actions = list(actions)
        self.index = 0

    def next_action(self, observation: dict[str, Any]) -> dict[str, Any]:
        if self.index >= len(self.actions):
            return {"type": "stop"}
        action = self.actions[self.index]
        self.index += 1
        if callable(action):
            return action(observation)
        return action


class OpenAICompatibleModel:
    """Optional adapter. Construct it only when a credential and base URL exist."""

    def __init__(self, complete: Callable[[list[dict[str, Any]]], dict[str, Any]]):
        self._complete = complete
        self.mode = "live_model"

    @classmethod
    def from_env(cls) -> "OpenAICompatibleModel | None":
        api_key = os.getenv(LIVE_KEY_ENV)
        base_url = os.getenv(LIVE_BASE_ENV)
        if not api_key or not base_url:
            return None
        model_name = os.getenv(LIVE_NAME_ENV, "gpt-4.1-mini")

        def complete(messages: list[dict[str, Any]]) -> dict[str, Any]:
            payload = json.dumps(
                {
                    "model": model_name,
                    "messages": messages,
                    "tools": [
                        {"type": "function", "function": spec} for spec in TOOL_SPEC
                    ],
                    "tool_choice": "auto",
                }
            ).encode("utf-8")
            req = request.Request(
                base_url.rstrip("/") + "/chat/completions",
                data=payload,
                method="POST",
            )
            req.add_header("Authorization", f"Bearer {api_key}")
            req.add_header("Content-Type", "application/json")
            with request.urlopen(req, timeout=30) as response:
                parsed = json.loads(response.read().decode("utf-8"))
            if not isinstance(parsed, dict):
                raise ValueError("model response must be an object")
            return parsed

        return cls(complete)

    def next_action(self, observation: dict[str, Any]) -> dict[str, Any]:
        encoded = json.dumps(observation, sort_keys=True, default=str)
        if len(encoded) > MAX_MODEL_CHARS:
            encoded = encoded[:MAX_MODEL_CHARS]
        parsed = self._complete(
            [
                {
                    "role": "system",
                    "content": (
                        "Use only inspect_memory, query_conclusion, propose_assertion, "
                        "and record_decision. Do not request shell, Cypher, or web access."
                    ),
                },
                {"role": "user", "content": encoded},
            ]
        )
        message = parsed.get("choices", [{}])[0].get("message", {})
        tool_calls = message.get("tool_calls") or []
        if not tool_calls:
            return {"type": "text", "content": str(message.get("content") or "")[:MAX_MODEL_CHARS]}
        call = tool_calls[0].get("function", {})
        arguments = call.get("arguments", "{}")
        if isinstance(arguments, str):
            if len(arguments) > MAX_MODEL_CHARS:
                return {"type": "text", "content": "tool arguments exceeded the output budget"}
            try:
                arguments = json.loads(arguments)
            except json.JSONDecodeError:
                return {"type": "text", "content": "tool arguments were not valid JSON"}
        if not isinstance(arguments, dict):
            return {"type": "text", "content": "tool arguments must be an object"}
        return {"type": "tool", "name": str(call.get("name") or ""), "arguments": arguments}
