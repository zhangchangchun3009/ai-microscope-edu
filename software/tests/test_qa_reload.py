"""QaService 从 edu.yaml 加载 LLM，reload 后改打新 URL；注入 config 则 no-op。"""

from __future__ import annotations

import io
import json
import sys
from pathlib import Path
from unittest.mock import patch

_SOFTWARE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_SOFTWARE))

from qa.client import LlmConfig  # noqa: E402
from qa.turn import QaService  # noqa: E402

_SSE_BODY = (
    b'data: {"choices":[{"delta":{"content":"ok"}}]}\n'
    b"\n"
    b"data: [DONE]\n"
    b"\n"
)


class _FakeResponse:
    """假 HTTP 响应：可读、可按行迭代。"""

    def __init__(self, body: bytes, status: int = 200) -> None:
        self._buf = io.BytesIO(body)
        self.status = status

    def read(self, *args, **kwargs):  # noqa: ANN002, ANN003
        return self._buf.read(*args, **kwargs)

    def __iter__(self):
        return self._buf

    def __enter__(self) -> _FakeResponse:
        return self

    def __exit__(self, *exc) -> bool:  # noqa: ANN002
        return False


def _write_llm_yaml(path: Path, base_url: str, api_key: str = "sk-plain", model: str = "m") -> None:
    path.write_text(
        "llm:\n"
        f"  base_url: {base_url}\n"
        f"  api_key: {api_key}\n"
        f"  model: {model}\n",
        encoding="utf-8",
    )


def _request_url(req: object) -> str:
    getter = getattr(req, "get_full_url", None)
    if callable(getter):
        return str(getter())
    return str(getattr(req, "full_url", req))


def test_reload_llm_switches_base_url(tmp_path: Path) -> None:
    """明文 yaml 先打 url A；改 base_url 后 reload 打 url B。"""
    qa_dir = tmp_path / "qa"
    qa_dir.mkdir()
    yaml_path = tmp_path / "edu.yaml"
    _write_llm_yaml(yaml_path, "https://a.example.com/v1")
    svc = QaService(qa_dir=qa_dir, config=None, environ={}, purge_on_start=False)

    urls: list[str] = []

    def fake_urlopen(req, timeout=None):  # noqa: ANN001, ARG001
        urls.append(_request_url(req))
        return _FakeResponse(_SSE_BODY)

    with patch("qa.client.urllib.request.urlopen", side_effect=fake_urlopen):
        text_a = "".join(svc.iter_tokens("问A"))
    assert text_a == "ok"
    assert urls[0].startswith("https://a.example.com/")

    _write_llm_yaml(yaml_path, "https://b.example.com/v1")
    svc.reload_llm()
    with patch("qa.client.urllib.request.urlopen", side_effect=fake_urlopen):
        text_b = "".join(svc.iter_tokens("问B"))
    assert text_b == "ok"
    assert len(urls) == 2
    assert urls[1].startswith("https://b.example.com/")


def test_reload_llm_noop_when_config_injected(tmp_path: Path) -> None:
    """构造时注入 config= 则 reload_llm 不改 _config。"""
    qa_dir = tmp_path / "qa"
    qa_dir.mkdir()
    injected = LlmConfig(
        base_url="https://injected.example.com/v1",
        api_key="sk-injected",
        model="inj",
        timeout_s=30.0,
    )
    svc = QaService(qa_dir=qa_dir, config=injected, environ={}, purge_on_start=False)
    _write_llm_yaml(tmp_path / "edu.yaml", "https://disk.example.com/v1", api_key="sk-disk")
    svc.reload_llm()
    assert svc._config is injected
    assert svc._config.base_url == "https://injected.example.com/v1"
    assert svc._config.api_key == "sk-injected"


def test_reload_during_iter_tokens_does_not_switch_in_flight_url(tmp_path: Path) -> None:
    """组消息时 reload 不得改本轮已选定的 URL；下一轮才打新地址。"""
    qa_dir = tmp_path / "qa"
    qa_dir.mkdir()
    yaml_path = tmp_path / "edu.yaml"
    _write_llm_yaml(yaml_path, "https://a.example.com/v1")
    svc = QaService(qa_dir=qa_dir, config=None, environ={}, purge_on_start=False)
    _write_llm_yaml(yaml_path, "https://b.example.com/v1")
    urls: list[str] = []
    orig_build = QaService._build_messages

    def build_then_reload(self: QaService, user_text: str) -> list[dict[str, str]]:
        msgs = orig_build(self, user_text)
        self.reload_llm()
        return msgs

    def fake_urlopen(req, timeout=None):  # noqa: ANN001, ARG001
        urls.append(_request_url(req))
        return _FakeResponse(_SSE_BODY)

    with patch.object(QaService, "_build_messages", build_then_reload):
        with patch("qa.client.urllib.request.urlopen", side_effect=fake_urlopen):
            assert "".join(svc.iter_tokens("问A")) == "ok"
    assert urls[0].startswith("https://a.example.com/")

    with patch("qa.client.urllib.request.urlopen", side_effect=fake_urlopen):
        assert "".join(svc.iter_tokens("问B")) == "ok"
    assert urls[1].startswith("https://b.example.com/")


def test_qaservice_default_paths_are_var_edu_yaml_and_user_md() -> None:
    """缺省 edu.yaml 在 software/var/edu.yaml，USER.md 仍在 var/qa。"""
    injected = LlmConfig(
        base_url="https://injected.example.com/v1",
        api_key="sk-injected",
        model="inj",
        timeout_s=30.0,
    )
    software = Path(__file__).resolve().parents[1]
    with patch.object(QaService, "_open_store", return_value=None):
        svc = QaService(config=injected, purge_on_start=False)
    assert svc._edu_yaml == software / "var" / "edu.yaml"
    assert svc._user_md_path == software / "var" / "qa" / "USER.md"


def test_decrypt_fail_enc1_iter_tokens_empty_after_load_and_reload(tmp_path: Path) -> None:
    """yaml ``api_key: enc1:00`` 解密失败则 load/reload 后 ``iter_tokens`` 皆空。"""
    qa_dir = tmp_path / "qa"
    qa_dir.mkdir()
    yaml_path = tmp_path / "edu.yaml"
    yaml_path.write_text(
        "llm:\n"
        "  base_url: https://x.example.com/v1\n"
        "  api_key: enc1:00\n"
        "  model: m\n",
        encoding="utf-8",
    )
    svc = QaService(qa_dir=qa_dir, config=None, environ={}, purge_on_start=False)
    assert svc._config is None
    assert list(svc.iter_tokens("问")) == []
    svc.reload_llm()
    assert svc._config is None
    assert list(svc.iter_tokens("再问")) == []


def test_qaservice_migrates_llm_json_when_yaml_has_no_llm(tmp_path: Path) -> None:
    """启动时 yaml 无 llm 则把 qa_dir/llm.json 迁入后再 load。"""
    qa_dir = tmp_path / "qa"
    qa_dir.mkdir()
    (qa_dir / "llm.json").write_text(
        json.dumps(
            {
                "base_url": "https://migrated.example.com/v1",
                "api_key": "sk-mig",
                "model": "mig-model",
            }
        ),
        encoding="utf-8",
    )
    svc = QaService(qa_dir=qa_dir, config=None, environ={}, purge_on_start=False)
    yaml_path = tmp_path / "edu.yaml"
    assert yaml_path.is_file()
    assert "enc1:" in yaml_path.read_text(encoding="utf-8")
    assert (qa_dir / "llm.json").is_file()
    assert svc._config is not None
    assert svc._config.base_url == "https://migrated.example.com/v1"
    assert svc._config.api_key == "sk-mig"
    assert svc._config.model == "mig-model"
