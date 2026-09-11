"""OpenAI 兼容聊天客户端：SSE 流式优先，失败则非流式回退。"""

from __future__ import annotations

import http.client
import json
import urllib.error
import urllib.request
from collections.abc import Iterator, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from qa.config import (
    DEFAULT_DEVICE_SECRET,
    DEFAULT_DEVICE_SECRET_HOSTS,
    DEFAULT_LLM_TIMEOUT_S,
)


class QaClientError(Exception):
    """问答客户端失败：缺配置、超时或 HTTP 错误。"""


@dataclass(frozen=True)
class LlmConfig:
    """OpenAI 兼容 ``/chat/completions`` 的连接配置。

    属性:
        base_url: API 根地址，或已含 ``chat/completions`` 的完整 URL。
        api_key: Bearer 令牌。
        model: 模型名。
        timeout_s: ``urllib`` 单次请求超时秒数。
        device_secret: 自建 nginx 网关暗号；空串表示不带头。
        device_secret_hosts: 附加 ``X-Device-Secret`` 的 hostname 白名单
            （小写，不含 scheme/port）。
    """

    base_url: str
    api_key: str
    model: str
    timeout_s: float
    device_secret: str = ""
    device_secret_hosts: tuple[str, ...] = ()


def load_llm_config(path: Path, environ: Mapping[str, str]) -> LlmConfig | None:
    """从 json 文件与环境变量组装 LLM 配置。

    参数:
        path: ``llm.json`` 路径，或存放该文件的目录。
        environ: 环境映射；``EDU_LLM_BASE_URL`` / ``EDU_LLM_API_KEY`` /
            ``EDU_LLM_MODEL`` 覆盖 json 同名字段。``EDU_LLM_DEVICE_SECRET`` /
            ``EDU_LLM_DEVICE_SECRET_HOSTS``（逗号分隔）覆盖网关暗号与白名单。

    返回值:
        三件套（base_url、api_key、model）均非空时返回配置；否则 ``None``。
        超时取 json 的 ``timeout_secs``（或 ``timeout_s``），缺省
        ``DEFAULT_LLM_TIMEOUT_S``。未写 ``device_secret`` 时用 MicroClaw
        缺省暗号；json 里显式空串则禁用该头。

    副作用:
        若 ``path`` 指向存在的文件则读盘。
    """
    data: dict[str, Any] = {}
    file_path = path / "llm.json" if path.is_dir() else path
    if file_path.is_file():
        try:
            loaded = json.loads(file_path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError):
            loaded = None
        if isinstance(loaded, dict):
            data = loaded

    base_url = str(environ.get("EDU_LLM_BASE_URL") or data.get("base_url") or "").strip()
    api_key = str(environ.get("EDU_LLM_API_KEY") or data.get("api_key") or "").strip()
    model = str(environ.get("EDU_LLM_MODEL") or data.get("model") or "").strip()
    timeout_raw = data.get("timeout_secs", data.get("timeout_s", DEFAULT_LLM_TIMEOUT_S))
    try:
        timeout_s = float(timeout_raw)
    except (TypeError, ValueError):
        timeout_s = DEFAULT_LLM_TIMEOUT_S

    if not base_url or not api_key or not model:
        return None
    return LlmConfig(
        base_url=base_url,
        api_key=api_key,
        model=model,
        timeout_s=timeout_s,
        device_secret=_read_device_secret(data, environ),
        device_secret_hosts=_read_device_secret_hosts(data, environ),
    )


def iter_chat_tokens(
    config: LlmConfig | None,
    messages: list[dict[str, str]],
) -> Iterator[str]:
    """流式拉取助手文本；SSE 在产出任何 token 前失败则再发一次非流式请求。

    参数:
        config: ``load_llm_config`` 的结果；``None`` 或缺字段视为无配置。
        messages: OpenAI 风格 ``role`` / ``content`` 列表。

    返回值:
        增量 token 迭代器。非流式回退时可能一次 yield 全文。

    副作用:
        向 ``{base_url}/chat/completions`` 发 POST（``enable_thinking`` 恒为
        false）。请求 URL 的 host 命中白名单时附加 ``X-Device-Secret``
        （对照 microclaw ``DeviceGatewayAuth``）。仅当流式尚未 yield 任何
        token 时才会再 POST ``stream=false``。

    异常:
        ``QaClientError``：无配置、超时、HTTP 错误，流式已产出 token 后失败，
        或回退请求也失败。
    """
    if config is None or not _config_ready(config):
        raise QaClientError("缺少 LLM 配置")

    url = _completions_url(config.base_url)
    yielded_any = False
    try:
        with _post_chat(config, url, messages, stream=True) as resp:
            for token in _iter_sse(resp):
                yielded_any = True
                yield token
        return
    except QaClientError:
        raise
    except (
        OSError,
        TimeoutError,
        urllib.error.URLError,
        json.JSONDecodeError,
        KeyError,
        IndexError,
        TypeError,
        ValueError,
        http.client.HTTPException,
    ) as exc:
        # 已产出 token 后再失败不得回退全文，否则会与已 yield 的增量重复。
        if yielded_any:
            raise QaClientError(str(exc)) from exc
        # 零 token 时流式失败（含超时 / HTTPError / IncompleteRead）改走非流式一次。

    try:
        with _post_chat(config, url, messages, stream=False) as resp:
            yield from _iter_nonstream(resp)
    except QaClientError:
        raise
    except Exception as exc:
        raise QaClientError(str(exc)) from exc


def _config_ready(config: LlmConfig) -> bool:
    """三件套均非空才可发请求。"""
    return bool(config.base_url.strip() and config.api_key.strip() and config.model.strip())


def _completions_url(base_url: str) -> str:
    """拼出 chat/completions URL，避免重复追加路径。"""
    base = base_url.rstrip("/")
    if base.endswith("chat/completions"):
        return base
    return f"{base}/chat/completions"


def _post_chat(
    config: LlmConfig,
    url: str,
    messages: list[dict[str, str]],
    *,
    stream: bool,
) -> Any:
    """构造并发送 JSON POST。必须 ``import urllib.request`` 以便单测 patch。"""
    payload = {
        "model": config.model,
        "messages": messages,
        "stream": stream,
        "enable_thinking": False,
    }
    headers = {
        "Authorization": f"Bearer {config.api_key}",
        "Content-Type": "application/json",
    }
    headers.update(_device_gateway_headers(config, url))
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers=headers,
        method="POST",
    )
    return urllib.request.urlopen(req, timeout=config.timeout_s)


def _read_device_secret(data: Mapping[str, Any], environ: Mapping[str, str]) -> str:
    """环境变量优先，其次 json；都未写则用 MicroClaw 缺省暗号。"""
    if "EDU_LLM_DEVICE_SECRET" in environ:
        return str(environ.get("EDU_LLM_DEVICE_SECRET") or "").strip()
    if "device_secret" in data:
        return str(data.get("device_secret") or "").strip()
    return DEFAULT_DEVICE_SECRET


def _read_device_secret_hosts(
    data: Mapping[str, Any],
    environ: Mapping[str, str],
) -> tuple[str, ...]:
    """环境变量或 json 覆盖白名单；未写则 ``www.aiinstrum.com``。"""
    if "EDU_LLM_DEVICE_SECRET_HOSTS" in environ:
        return _split_hosts(str(environ.get("EDU_LLM_DEVICE_SECRET_HOSTS") or ""))
    if "device_secret_hosts" in data:
        raw = data.get("device_secret_hosts")
        if isinstance(raw, str):
            return _split_hosts(raw)
        if isinstance(raw, list):
            return tuple(
                str(item).strip().lower() for item in raw if str(item).strip()
            )
        return ()
    return tuple(host.lower() for host in DEFAULT_DEVICE_SECRET_HOSTS)


def _split_hosts(raw: str) -> tuple[str, ...]:
    """把逗号分隔的 host 列表规范成小写 tuple。"""
    return tuple(part.strip().lower() for part in raw.split(",") if part.strip())


def _device_gateway_headers(config: LlmConfig, url: str) -> dict[str, str]:
    """host 命中白名单且暗号非空时返回 ``X-Device-Secret``。"""
    secret = (config.device_secret or "").strip()
    if not secret:
        return {}
    hosts: Sequence[str] = tuple(
        str(host).strip().lower()
        for host in config.device_secret_hosts
        if str(host).strip()
    )
    if not hosts:
        return {}
    hostname = (urlparse(url).hostname or "").lower()
    if hostname not in hosts:
        return {}
    return {"X-Device-Secret": secret}


def _iter_sse(resp: Any) -> Iterator[str]:
    """按行解析 ``data:`` SSE，遇到 ``[DONE]`` 结束。"""
    for raw in resp:
        line = raw.decode("utf-8") if isinstance(raw, (bytes, bytearray)) else str(raw)
        line = line.rstrip("\r\n")
        if not line.startswith("data:"):
            continue
        payload = line[len("data:") :].strip()
        if payload == "[DONE]":
            return
        if not payload:
            continue
        obj = json.loads(payload)
        content = (obj["choices"][0].get("delta") or {}).get("content")
        if content:
            yield str(content)


def _iter_nonstream(resp: Any) -> Iterator[str]:
    """读取完整 JSON，yield ``choices[0].message.content``。"""
    raw = resp.read()
    text = raw.decode("utf-8") if isinstance(raw, (bytes, bytearray)) else str(raw)
    obj = json.loads(text)
    content = obj["choices"][0]["message"]["content"]
    if content:
        yield str(content)
