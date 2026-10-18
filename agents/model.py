"""Model adapters. Scripted replay is the default; live calls need an explicit key."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Callable
from urllib import error, request


LIVE_KEY_ENV = "MEMOPOPS_MODEL_API_KEY"
LIVE_BASE_ENV = "MEMOPOPS_MODEL_BASE_URL"
LIVE_NAME_ENV = "MEMOPOPS_MODEL_NAME"
# Gemini Flash on the native generateContent API.
DEFAULT_LIVE_MODEL = "gemini-flash-latest"
DEFAULT_LIVE_BASE_URL = "https://generativelanguage.googleapis.com/v1beta/models"
_LOCAL_ENV_PATH = Path(".env")
_MODEL_ENV_KEYS = {LIVE_KEY_ENV, LIVE_BASE_ENV, LIVE_NAME_ENV}
MAX_MODEL_CHARS = 8_000


def _load_local_model_env() -> None:
    """Fill unset model settings from the gitignored .env file. Never print values."""
    path = _LOCAL_ENV_PATH
    if not path.is_file():
        return
    for line in path.read_text(encoding="utf-8-sig").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        key = key.strip()
        if key not in _MODEL_ENV_KEYS:
            continue
        os.environ.setdefault(key, value.strip().strip("\"'"))


def live_credentials_present() -> bool:
    _load_local_model_env()
    return bool(os.getenv(LIVE_KEY_ENV))


def generate_content_url(base_url: str | None, model_name: str) -> str:
    """Build a native generateContent URL. Never append /chat/completions."""
    raw = (base_url or "").strip().rstrip("/")
    if raw.endswith(":generateContent"):
        return raw
    if not raw or raw.endswith("/openai"):
        root = DEFAULT_LIVE_BASE_URL
    else:
        root = raw
    model_id = model_name.strip().removeprefix("models/")
    if root.endswith("/" + model_id):
        return f"{root}:generateContent"
    return f"{root}/{model_id}:generateContent"


def contents_from_messages(messages: list[dict[str, Any]]) -> dict[str, Any]:
    """Map chat messages onto Gemini contents. System text is a system instruction."""
    system_parts: list[str] = []
    contents: list[dict[str, Any]] = []
    for message in messages:
        text = str(message.get("content") or "")
        role = str(message.get("role") or "user")
        if role == "system":
            if text:
                system_parts.append(text)
            continue
        contents.append(
            {
                "role": "model" if role == "assistant" else "user",
                "parts": [{"text": text}],
            }
        )
    if not contents:
        contents.append({"role": "user", "parts": [{"text": ""}]})
    payload: dict[str, Any] = {"contents": contents}
    if system_parts:
        payload["systemInstruction"] = {"parts": [{"text": "\n".join(system_parts)}]}
    return payload


def text_from_generate_content(parsed: dict[str, Any]) -> str:
    """Read candidates[0].content.parts[].text. This response has no tool calls."""
    candidates = parsed.get("candidates")
    if not isinstance(candidates, list) or not candidates or not isinstance(candidates[0], dict):
        raise ValueError("model response has no candidates")
    content = candidates[0].get("content")
    parts = content.get("parts") if isinstance(content, dict) else None
    if not isinstance(parts, list):
        raise ValueError("model response has no content parts")
    texts = [
        part["text"]
        for part in parts
        if isinstance(part, dict) and isinstance(part.get("text"), str)
    ]
    if not texts:
        raise ValueError("model response has no text")
    return "".join(texts)


def _redact_secret(text: str, secret: str) -> str:
    if secret:
        return text.replace(secret, "[REDACTED]")
    return text


def post_generate_content(
    url: str,
    api_key: str,
    payload: dict[str, Any],
    *,
    timeout: float = 60,
) -> dict[str, Any]:
    """POST generateContent with X-goog-api-key. Raise a short error on non-200."""
    req = request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        method="POST",
    )
    req.add_header("X-goog-api-key", api_key)
    req.add_header("Content-Type", "application/json")
    try:
        with request.urlopen(req, timeout=timeout) as response:
            parsed = json.loads(response.read().decode("utf-8"))
    except error.HTTPError as exc:
        body = _redact_secret(exc.read().decode("utf-8", errors="replace")[:500], api_key)
        raise RuntimeError(f"model request failed: HTTP {exc.code}: {body}") from exc
    if not isinstance(parsed, dict):
        raise ValueError("model response must be an object")
    return parsed


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
    """Live generateContent client. The name is kept for existing imports.

    Replies are plain text. This client does not send function tools and does not
    invent tool calls from the model's prose.
    """

    def __init__(
        self,
        complete: Callable[..., dict[str, Any]],
        *,
        model_name: str,
        base_url: str,
        endpoint_url: str,
    ):
        self._complete = complete
        self.model_name = model_name
        self.base_url = base_url.rstrip("/")
        self.endpoint_url = endpoint_url
        self.mode = "live_model"
        self.supports_tools = False

    @classmethod
    def from_env(cls) -> "OpenAICompatibleModel | None":
        _load_local_model_env()
        api_key = os.getenv(LIVE_KEY_ENV)
        if not api_key:
            return None
        base_url = os.getenv(LIVE_BASE_ENV) or DEFAULT_LIVE_BASE_URL
        model_name = os.getenv(LIVE_NAME_ENV) or DEFAULT_LIVE_MODEL
        endpoint_url = generate_content_url(base_url, model_name)

        def complete(messages: list[dict[str, Any]], timeout: float = 60) -> dict[str, Any]:
            return post_generate_content(
                endpoint_url,
                api_key,
                contents_from_messages(messages),
                timeout=timeout,
            )

        return cls(
            complete,
            model_name=model_name,
            base_url=base_url,
            endpoint_url=endpoint_url,
        )

    def generate_text(self, prompt: str, *, timeout: float = 60) -> str:
        parsed = self._complete([{"role": "user", "content": prompt}], timeout=timeout)
        return text_from_generate_content(parsed)[:MAX_MODEL_CHARS]

    def next_action(self, observation: dict[str, Any]) -> dict[str, Any]:
        encoded = json.dumps(observation, sort_keys=True, default=str)
        if len(encoded) > MAX_MODEL_CHARS:
            encoded = encoded[:MAX_MODEL_CHARS]
        parsed = self._complete(
            [
                {
                    "role": "system",
                    "content": (
                        "Answer in plain text. Do not claim to have called a tool. "
                        "Do not request shell, Cypher, or web access."
                    ),
                },
                {"role": "user", "content": encoded},
            ]
        )
        return {
            "type": "text",
            "content": text_from_generate_content(parsed)[:MAX_MODEL_CHARS],
        }
