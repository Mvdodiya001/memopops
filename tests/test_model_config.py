import io
import json
from urllib import error

import agents.model as model
from agents.model import (
    DEFAULT_LIVE_BASE_URL,
    DEFAULT_LIVE_MODEL,
    LIVE_BASE_ENV,
    LIVE_KEY_ENV,
    LIVE_NAME_ENV,
    OpenAICompatibleModel,
    ScriptedActions,
    generate_content_url,
    text_from_generate_content,
)


def _clear_model_env(monkeypatch) -> None:
    for name in (LIVE_KEY_ENV, LIVE_BASE_ENV, LIVE_NAME_ENV):
        monkeypatch.delenv(name, raising=False)


def test_missing_key_keeps_scripted_replay(monkeypatch, tmp_path):
    _clear_model_env(monkeypatch)
    monkeypatch.setattr(model, "_LOCAL_ENV_PATH", tmp_path / "missing.env")
    actor = ScriptedActions([{"type": "tool", "name": "inspect_memory", "arguments": {}}])

    assert OpenAICompatibleModel.from_env() is None
    assert model.live_credentials_present() is False
    assert actor.next_action({}) == {"type": "tool", "name": "inspect_memory", "arguments": {}}
    assert actor.next_action({}) == {"type": "stop"}


def test_local_key_selects_gemma_generate_content_url(monkeypatch, tmp_path):
    _clear_model_env(monkeypatch)
    env_file = tmp_path / ".env"
    env_file.write_text(
        "MEMOPOPS_MODEL_API_KEY=test-key\n"
        "MEMOPOPS_MODEL_BASE_URL=https://generativelanguage.googleapis.com/v1beta/models/\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(model, "_LOCAL_ENV_PATH", env_file)

    selected = OpenAICompatibleModel.from_env()

    assert selected is not None
    assert selected.mode == "live_model"
    assert selected.supports_tools is False
    assert selected.model_name == DEFAULT_LIVE_MODEL == "gemini-flash-latest"
    assert selected.base_url == DEFAULT_LIVE_BASE_URL
    assert selected.endpoint_url == (
        "https://generativelanguage.googleapis.com/v1beta/models/gemini-flash-latest:generateContent"
    )
    assert "chat/completions" not in selected.endpoint_url
    assert model.live_credentials_present() is True


def test_empty_base_url_uses_native_generate_content(monkeypatch, tmp_path):
    _clear_model_env(monkeypatch)
    monkeypatch.setattr(model, "_LOCAL_ENV_PATH", tmp_path / "missing.env")
    monkeypatch.setenv(LIVE_KEY_ENV, "test-key")

    selected = OpenAICompatibleModel.from_env()

    assert selected is not None
    assert selected.endpoint_url == generate_content_url("", DEFAULT_LIVE_MODEL)


def test_explicit_model_name_is_used(monkeypatch, tmp_path):
    _clear_model_env(monkeypatch)
    monkeypatch.setattr(model, "_LOCAL_ENV_PATH", tmp_path / "missing.env")
    monkeypatch.setenv(LIVE_KEY_ENV, "test-key")
    monkeypatch.setenv(LIVE_NAME_ENV, "other-model")

    selected = OpenAICompatibleModel.from_env()

    assert selected is not None
    assert selected.model_name == "other-model"
    assert selected.endpoint_url.endswith("/other-model:generateContent")


def test_generate_text_posts_native_body_and_parses_parts(monkeypatch, tmp_path):
    _clear_model_env(monkeypatch)
    monkeypatch.setattr(model, "_LOCAL_ENV_PATH", tmp_path / "missing.env")
    monkeypatch.setenv(LIVE_KEY_ENV, "test-key")
    captured: dict[str, object] = {}

    class FakeResponse:
        status = 200

        def read(self) -> bytes:
            return json.dumps(
                {"candidates": [{"content": {"parts": [{"text": "AI learns patterns."}]}}]}
            ).encode("utf-8")

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

    def fake_urlopen(req, timeout=0):
        captured["url"] = req.full_url
        captured["api_key"] = req.get_header("X-goog-api-key")
        captured["authorization"] = req.get_header("Authorization")
        captured["content_type"] = req.get_header("Content-type")
        captured["body"] = json.loads(req.data.decode("utf-8"))
        captured["timeout"] = timeout
        return FakeResponse()

    monkeypatch.setattr(model.request, "urlopen", fake_urlopen)
    selected = OpenAICompatibleModel.from_env()
    assert selected is not None

    text = selected.generate_text("Explain how AI works in a few words", timeout=60)

    assert text == "AI learns patterns."
    assert captured["url"] == selected.endpoint_url
    assert captured["api_key"] == "test-key"
    assert captured["authorization"] is None
    assert captured["content_type"] == "application/json"
    assert captured["timeout"] == 60
    body = captured["body"]
    assert isinstance(body, dict)
    assert body["contents"] == [
        {"role": "user", "parts": [{"text": "Explain how AI works in a few words"}]}
    ]
    assert "tools" not in body
    assert text_from_generate_content(body | {"candidates": [{"content": {"parts": [{"text": "AI learns patterns."}]}}]}) == "AI learns patterns."


def test_non_200_redacts_the_key(monkeypatch, tmp_path):
    _clear_model_env(monkeypatch)
    monkeypatch.setattr(model, "_LOCAL_ENV_PATH", tmp_path / "missing.env")
    monkeypatch.setenv(LIVE_KEY_ENV, "test-key")

    def fake_urlopen(req, timeout=0):
        raise error.HTTPError(
            req.full_url,
            404,
            "Not Found",
            hdrs=None,
            fp=io.BytesIO(b'{"error":{"message":"no such model test-key"}}'),
        )

    monkeypatch.setattr(model.request, "urlopen", fake_urlopen)
    selected = OpenAICompatibleModel.from_env()
    assert selected is not None
    try:
        selected.generate_text("hello")
    except RuntimeError as exc:
        message = str(exc)
    else:
        raise AssertionError("expected HTTP 404 to raise")

    assert "HTTP 404" in message
    assert "test-key" not in message
    assert "[REDACTED]" in message
