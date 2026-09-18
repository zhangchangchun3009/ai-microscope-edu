"""快速问答 LLM 客户端：SSE 流式、非流式回退与配置加载，无真网。"""

from __future__ import annotations

import io
import json
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

_SOFTWARE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_SOFTWARE))

from qa.client import (  # noqa: E402
    LlmConfig,
    QaClientError,
    iter_chat_tokens,
    load_llm_config,
)
from qa.config import DEFAULT_LLM_TIMEOUT_S  # noqa: E402

_MESSAGES = [{"role": "user", "content": "你好"}]
_SSE_BODY = (
    b'data: {"choices":[{"delta":{"content":"\xe4\xbd\xa0"}}]}\n'
    b"\n"
    b'data: {"choices":[{"delta":{"content":"\xe5\xa5\xbd\xe3\x80\x82"}}]}\n'
    b"\n"
    b"data: [DONE]\n"
    b"\n"
)
_NONSTREAM_BODY = json.dumps(
    {"choices": [{"message": {"content": "整段回答。"}}]},
    ensure_ascii=False,
).encode("utf-8")


class _FakeResponse:
    """假 HTTP 响应：可读、可按行迭代、带 status。"""

    def __init__(self, body: bytes, status: int = 200) -> None:
        self._buf = io.BytesIO(body)
        self.status = status

    def read(self, *args, **kwargs):  # noqa: ANN002, ANN003
        return self._buf.read(*args, **kwargs)

    def readline(self, *args, **kwargs):  # noqa: ANN002, ANN003
        return self._buf.readline(*args, **kwargs)

    def __iter__(self):
        return self._buf

    def __enter__(self) -> _FakeResponse:
        return self

    def __exit__(self, *exc) -> bool:  # noqa: ANN002
        return False


def _cfg(**overrides: object) -> LlmConfig:
    kwargs: dict[str, object] = {
        "base_url": str(overrides.get("base_url", "https://api.example.com/v1")),
        "api_key": str(overrides.get("api_key", "sk-test")),
        "model": str(overrides.get("model", "qwen-plus")),
        "timeout_s": float(overrides.get("timeout_s", DEFAULT_LLM_TIMEOUT_S)),
    }
    if "device_secret" in overrides:
        kwargs["device_secret"] = str(overrides["device_secret"])
    if "device_secret_hosts" in overrides:
        hosts = overrides["device_secret_hosts"]
        kwargs["device_secret_hosts"] = tuple(hosts)  # type: ignore[arg-type]
    return LlmConfig(**kwargs)  # type: ignore[arg-type]


def _header_map(req: object) -> dict[str, str]:
    items = req.header_items()  # type: ignore[attr-defined]
    return {str(key).lower(): str(value) for key, value in items}


def _request_json(req) -> dict:
    raw = req.data if hasattr(req, "data") else req
    if isinstance(raw, bytes):
        return json.loads(raw.decode("utf-8"))
    return json.loads(raw)


def test_iter_chat_tokens_falls_back_to_non_stream() -> None:
    calls: list = []

    def fake_urlopen(req, timeout=None):  # noqa: ANN001
        calls.append((req, timeout))
        if len(calls) == 1:
            raise OSError("stream broken")
        return _FakeResponse(_NONSTREAM_BODY, status=200)

    with patch("qa.client.urllib.request.urlopen", side_effect=fake_urlopen):
        text = "".join(iter_chat_tokens(_cfg(), _MESSAGES))

    assert text == "整段回答。"
    assert len(calls) == 2
    first_body = _request_json(calls[0][0])
    second_body = _request_json(calls[1][0])
    assert first_body["stream"] is True
    assert second_body["stream"] is False
    assert first_body["enable_thinking"] is False
    assert second_body["enable_thinking"] is False
    assert calls[0][1] == DEFAULT_LLM_TIMEOUT_S
    assert calls[1][1] == DEFAULT_LLM_TIMEOUT_S


def test_iter_chat_tokens_parses_sse_and_disables_thinking() -> None:
    calls: list = []

    def fake_urlopen(req, timeout=None):  # noqa: ANN001
        calls.append((req, timeout))
        return _FakeResponse(_SSE_BODY, status=200)

    with patch("qa.client.urllib.request.urlopen", side_effect=fake_urlopen):
        text = "".join(iter_chat_tokens(_cfg(), _MESSAGES))

    assert text == "你好。"
    assert len(calls) == 1
    body = _request_json(calls[0][0])
    assert body["enable_thinking"] is False
    assert body["stream"] is True
    assert body["messages"] == _MESSAGES


_EDU_LLM_YAML = (
    "llm:\n"
    "  base_url: https://json.example.com/v1\n"
    "  api_key: sk-json\n"
    "  model: json-model\n"
    "  timeout_secs: 45\n"
)


def _write_edu_yaml(path: Path, body: str = _EDU_LLM_YAML) -> Path:
    path.write_text(body, encoding="utf-8")
    return path


def test_load_llm_config_empty_dir_returns_none(tmp_path: Path) -> None:
    assert load_llm_config(tmp_path / "edu.yaml", {}) is None
    assert load_llm_config(tmp_path, {}) is None


def test_load_llm_config_from_env_trio(tmp_path: Path) -> None:
    cfg = load_llm_config(
        tmp_path / "edu.yaml",
        {
            "EDU_LLM_BASE_URL": "https://api.example.com/v1",
            "EDU_LLM_API_KEY": "sk-env",
            "EDU_LLM_MODEL": "qwen-plus",
        },
    )
    assert cfg is not None
    assert cfg.base_url == "https://api.example.com/v1"
    assert cfg.api_key == "sk-env"
    assert cfg.model == "qwen-plus"
    assert cfg.timeout_s == DEFAULT_LLM_TIMEOUT_S


def test_load_llm_config_env_overrides_yaml(tmp_path: Path) -> None:
    path = _write_edu_yaml(tmp_path / "edu.yaml")
    cfg = load_llm_config(
        path,
        {
            "EDU_LLM_BASE_URL": "https://env.example.com/v1",
            "EDU_LLM_API_KEY": "sk-env",
            "EDU_LLM_MODEL": "env-model",
        },
    )
    assert cfg is not None
    assert cfg.base_url == "https://env.example.com/v1"
    assert cfg.api_key == "sk-env"
    assert cfg.model == "env-model"
    assert cfg.timeout_s == 45.0


def test_load_llm_config_from_dir_or_var(tmp_path: Path) -> None:
    """目录含 edu.yaml，或名为 var 的目录，都读其中的 yaml。"""
    _write_edu_yaml(tmp_path / "edu.yaml")
    from_dir = load_llm_config(tmp_path, {})
    assert from_dir is not None
    assert from_dir.api_key == "sk-json"
    assert from_dir.base_url == "https://json.example.com/v1"

    var_dir = tmp_path / "var"
    var_dir.mkdir()
    _write_edu_yaml(var_dir / "edu.yaml")
    from_var = load_llm_config(var_dir, {})
    assert from_var is not None
    assert from_var.model == "json-model"


def test_load_llm_config_decrypt_failure_returns_none(tmp_path: Path) -> None:
    """enc1 解密失败时该 key 当空，缺三件套则整份 None，不得把乱码当 Bearer。"""
    path = _write_edu_yaml(
        tmp_path / "edu.yaml",
        "llm:\n"
        "  base_url: https://json.example.com/v1\n"
        "  api_key: enc1:00\n"
        "  model: json-model\n",
    )
    assert load_llm_config(path, {}, serial="x") is None


def test_load_llm_config_decrypts_enc1_api_key(tmp_path: Path) -> None:
    from system.secret_box import encrypt_secret

    token = encrypt_secret("sk-live", "serial-a")
    path = _write_edu_yaml(
        tmp_path / "edu.yaml",
        "llm:\n"
        "  base_url: https://json.example.com/v1\n"
        f"  api_key: {token}\n"
        "  model: json-model\n",
    )
    cfg = load_llm_config(path, {}, serial="serial-a")
    assert cfg is not None
    assert cfg.api_key == "sk-live"


def test_load_llm_config_env_api_key_skips_yaml_decrypt(tmp_path: Path) -> None:
    """进程环境出现 EDU_LLM_API_KEY 时不解密 yaml 里的 enc1。"""
    path = _write_edu_yaml(
        tmp_path / "edu.yaml",
        "llm:\n"
        "  base_url: https://json.example.com/v1\n"
        "  api_key: enc1:00\n"
        "  model: json-model\n",
    )
    cfg = load_llm_config(
        path,
        {"EDU_LLM_API_KEY": "sk-env"},
        serial="x",
    )
    assert cfg is not None
    assert cfg.api_key == "sk-env"


def test_iter_chat_tokens_timeout_raises() -> None:
    def fake_urlopen(req, timeout=None):  # noqa: ANN001, ARG001
        raise TimeoutError("timed out")

    with patch("qa.client.urllib.request.urlopen", side_effect=fake_urlopen):
        with pytest.raises(QaClientError):
            "".join(iter_chat_tokens(_cfg(), _MESSAGES))


def test_iter_chat_tokens_http_error_raises() -> None:
    import urllib.error

    def fake_urlopen(req, timeout=None):  # noqa: ANN001, ARG001
        raise urllib.error.HTTPError(
            "https://api.example.com/v1/chat/completions",
            502,
            "Bad Gateway",
            hdrs=None,
            fp=io.BytesIO(b""),
        )

    with patch("qa.client.urllib.request.urlopen", side_effect=fake_urlopen):
        with pytest.raises(QaClientError):
            "".join(iter_chat_tokens(_cfg(), _MESSAGES))


def test_iter_chat_tokens_missing_config_raises() -> None:
    with pytest.raises(QaClientError):
        "".join(iter_chat_tokens(None, _MESSAGES))  # type: ignore[arg-type]


def test_iter_chat_tokens_no_fallback_after_partial_sse() -> None:
    """SSE 已产出 token 后再失败时不得非流式回退，以免拼接重复全文。"""
    partial = b'data: {"choices":[{"delta":{"content":"\xe4\xbd\xa0"}}]}\n\n'

    class _PartialThenFail(_FakeResponse):
        def __iter__(self):
            yield from io.BytesIO(partial)
            raise OSError("stream broken after tokens")

    calls: list = []

    def fake_urlopen(req, timeout=None):  # noqa: ANN001
        calls.append((req, timeout))
        if len(calls) == 1:
            return _PartialThenFail(partial, status=200)
        return _FakeResponse(_NONSTREAM_BODY, status=200)

    tokens: list[str] = []
    with patch("qa.client.urllib.request.urlopen", side_effect=fake_urlopen):
        with pytest.raises(QaClientError):
            for token in iter_chat_tokens(_cfg(), _MESSAGES):
                tokens.append(token)

    assert tokens == ["你"]
    assert len(calls) == 1
    assert _request_json(calls[0][0])["stream"] is True


def test_iter_chat_tokens_incomplete_read_on_stream_wraps() -> None:
    """流式路径的 IncompleteRead 按 OSError 同样规则处理，不得未包装冒出。"""
    import http.client

    calls: list = []

    def fake_urlopen(req, timeout=None):  # noqa: ANN001
        calls.append((req, timeout))
        raise http.client.IncompleteRead(b"partial")

    with patch("qa.client.urllib.request.urlopen", side_effect=fake_urlopen):
        with pytest.raises(QaClientError) as info:
            "".join(iter_chat_tokens(_cfg(), _MESSAGES))

    assert not isinstance(info.value, http.client.IncompleteRead)
    assert isinstance(info.value, QaClientError)
    # 零 token 时允许回退；两次均 IncompleteRead 则包装为 QaClientError。
    assert len(calls) == 2
    assert _request_json(calls[0][0])["stream"] is True
    assert _request_json(calls[1][0])["stream"] is False


def test_load_llm_config_defaults_device_gateway_like_microclaw(tmp_path: Path) -> None:
    """未写 device_secret 时用 MicroClaw 缺省暗号，仅白名单 host 会带头。"""
    from qa.config import DEFAULT_DEVICE_SECRET, DEFAULT_DEVICE_SECRET_HOSTS

    path = _write_edu_yaml(
        tmp_path / "edu.yaml",
        "llm:\n"
        "  base_url: https://www.aiinstrum.com/api-micro-llm/v1\n"
        "  api_key: sk-json\n"
        "  model: qwen-plus\n",
    )
    cfg = load_llm_config(path, {})
    assert cfg is not None
    assert cfg.device_secret == DEFAULT_DEVICE_SECRET
    assert tuple(cfg.device_secret_hosts) == tuple(DEFAULT_DEVICE_SECRET_HOSTS)


def test_load_llm_config_empty_device_secret_disables_header(tmp_path: Path) -> None:
    path = _write_edu_yaml(
        tmp_path / "edu.yaml",
        "llm:\n"
        "  base_url: https://www.aiinstrum.com/v1\n"
        "  api_key: sk-json\n"
        "  model: qwen-plus\n"
        '  device_secret: ""\n',
    )
    cfg = load_llm_config(path, {})
    assert cfg is not None
    assert cfg.device_secret == ""


def test_iter_chat_tokens_sends_x_device_secret_for_allowlisted_host() -> None:
    """对照 microclaw DeviceGatewayAuth：host 命中白名单才附加 X-Device-Secret。"""
    cfg = _cfg(
        base_url="https://www.aiinstrum.com/api-micro-llm/v1",
        device_secret="Microclaw-2026-SuperSecr3t!",
        device_secret_hosts=("www.aiinstrum.com",),
    )
    calls: list = []

    def fake_urlopen(req, timeout=None):  # noqa: ANN001
        calls.append(req)
        return _FakeResponse(_SSE_BODY, status=200)

    with patch("qa.client.urllib.request.urlopen", side_effect=fake_urlopen):
        text = "".join(iter_chat_tokens(cfg, _MESSAGES))

    assert text == "你好。"
    headers = _header_map(calls[0])
    assert headers["x-device-secret"] == "Microclaw-2026-SuperSecr3t!"
    assert headers["authorization"] == "Bearer sk-test"


def test_iter_chat_tokens_skips_x_device_secret_for_other_host() -> None:
    cfg = _cfg(
        base_url="https://api.example.com/v1",
        device_secret="Microclaw-2026-SuperSecr3t!",
        device_secret_hosts=("www.aiinstrum.com",),
    )
    calls: list = []

    def fake_urlopen(req, timeout=None):  # noqa: ANN001
        calls.append(req)
        return _FakeResponse(_SSE_BODY, status=200)

    with patch("qa.client.urllib.request.urlopen", side_effect=fake_urlopen):
        "".join(iter_chat_tokens(cfg, _MESSAGES))

    headers = _header_map(calls[0])
    assert "x-device-secret" not in headers
