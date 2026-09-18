"""教学一体机简单配置：一份 edu.yaml 的读、写、补丁与旧 llm.json 迁移。"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, MutableMapping

from ruamel.yaml import YAML, YAMLError
from ruamel.yaml.comments import CommentedMap

from system.display import normalize_rotation
from system.mixer import DEFAULT_VOLUME_PCT
from system.secret_box import encrypt_secret

# 磁盘为 display / audio / qa / llm 嵌套；patch_edu 只改传入的扁平字段。
DEFAULT_RETAIN_DAYS = 7
DEFAULT_CONTEXT_TURNS = 8
MAX_RETAIN_DAYS = 3650
MAX_CONTEXT_TURNS = 64
_LLM_TRIO = ("base_url", "api_key", "model")
_LLM_SECRETS = ("api_key", "device_secret")
_ENC_PREFIX = "enc1:"


@dataclass
class EduSettings:
    """内存中的扁平设置；落盘为 display / audio / qa / llm 嵌套 YAML。

    属性:
        v: 配置版本，从 1 起。
        rotation_deg: 顺时针旋转角（0/90/180/270）。
        captions_enabled: 字幕总开关。
        volume_pct: 音量百分比（0–100，缺省 73）。
        retain_days: 问答记录保留天数（缺省 7，钳制 1–3650）。
        context_turns: 当前场送给 LLM 的最近轮数（缺省 8，钳制 1–64）。
        llm: 大模型段；缺省空 dict 表示未配置。
    """

    v: int
    rotation_deg: int
    captions_enabled: bool
    volume_pct: int
    retain_days: int
    context_turns: int
    llm: dict[str, Any]


def defaults() -> EduSettings:
    """返回整份缺省设置（缺文件或损坏时的回退值）。

    参数:
        无。

    返回:
        ``rotation_deg=90``、``captions_enabled=False``、``volume_pct=73``、
        ``retain_days=7``、``context_turns=8``、``llm={}``、``v=1`` 的新实例
        （``llm`` 每次新建，避免共享可变对象）。

    副作用:
        无。
    """
    return EduSettings(
        v=1,
        rotation_deg=90,
        captions_enabled=False,
        volume_pct=DEFAULT_VOLUME_PCT,
        retain_days=DEFAULT_RETAIN_DAYS,
        context_turns=DEFAULT_CONTEXT_TURNS,
        llm={},
    )


def edu_yaml_path() -> Path:
    """返回教学一体机配置文件 ``software/var/edu.yaml`` 的绝对路径。

    参数:
        无。

    返回:
        相对本模块定位的 ``var/edu.yaml``（即 ``software/var/edu.yaml``）。

    副作用:
        无；不创建文件或目录。
    """
    return Path(__file__).resolve().parents[1] / "var" / "edu.yaml"


def load_edu(path: Path) -> EduSettings:
    """读取 ``edu.yaml``；缺文件或损坏时整份回退缺省，不半解析。

    参数:
        path: YAML 文件路径。

    返回:
        解析成功的设置；文件不存在、无法解码、YAML 非法、或根不是映射时
        返回 :func:`defaults`（不用损坏文件里碰巧能读到的片段）。

    副作用:
        若 ``path`` 指向存在的文件则读盘。
    """
    data = _try_load_mapping(path)
    if data is None:
        return defaults()
    return _settings_from_nested(data)


def save_edu(path: Path, settings: EduSettings) -> None:
    """把设置写入 YAML（ruamel round-trip）；已有文件尽量保留注释与键序。

    参数:
        path: 目标文件；父目录不存在时会创建。
        settings: 要落盘的扁平设置。

    返回:
        无。

    副作用:
        覆盖 ``path``；必要时 ``mkdir`` 父目录。不加密 ``llm`` 密钥
        （加密由迁移或设置页在写入前完成）。
    """
    yaml = _rt_yaml()
    data = _try_load_mapping(path, yaml)
    if data is None:
        data = CommentedMap()
    _write_settings_into(data, settings)
    _dump(path, yaml, data)


def patch_edu(path: Path, **fields: Any) -> EduSettings:
    """只更新传入的顶层字段后写回，并返回读盘结果。

    参数:
        path: YAML 路径；不存在或损坏时从缺省结构开始写。
        **fields: 仅 ``rotation_deg`` / ``captions_enabled`` / ``volume_pct`` /
            ``llm`` 会被应用；其余关键字忽略。

    返回:
        写回后再 :func:`load_edu` 的设置。

    副作用:
        读改写 ``path``；ruamel round-trip 尽量保留未改键上的注释。
    """
    yaml = _rt_yaml()
    data = _try_load_mapping(path, yaml)
    if data is None:
        data = _nested_from_settings(defaults())
    if "rotation_deg" in fields:
        _ensure_map(data, "display")["rotation_deg"] = fields["rotation_deg"]
    if "captions_enabled" in fields:
        _ensure_map(data, "display")["captions_enabled"] = fields["captions_enabled"]
    if "volume_pct" in fields:
        _ensure_map(data, "audio")["volume_pct"] = fields["volume_pct"]
    if "llm" in fields:
        data["llm"] = fields["llm"]
    _dump(path, yaml, data)
    return load_edu(path)


def maybe_migrate_llm_json(yaml_path: Path, json_path: Path, serial: str) -> None:
    """旧 ``llm.json`` 三件套迁入 yaml，并把密钥写成 ``enc1:``；不删除 json。

    参数:
        yaml_path: ``edu.yaml`` 路径。
        json_path: 旧 ``var/qa/llm.json`` 路径。
        serial: 本机 CPU 序列号，用于 :func:`encrypt_secret`。

    返回:
        无。yaml 已有可用 ``llm.base_url``、json 缺失/损坏、或 json 缺三件套时
        直接返回。

    副作用:
        条件满足时把 json 字段写入 yaml 的 ``llm`` 段（``api_key`` /
        ``device_secret`` 明文会加密）；**不**删除 ``json_path``。
    """
    current = load_edu(yaml_path)
    if str(current.llm.get("base_url") or "").strip():
        return
    if not json_path.is_file():
        return
    try:
        raw = json.loads(json_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return
    if not isinstance(raw, dict):
        return
    if not all(str(raw.get(key) or "").strip() for key in _LLM_TRIO):
        return
    llm: dict[str, Any] = dict(raw)
    for key in _LLM_SECRETS:
        val = llm.get(key)
        if isinstance(val, str) and val.strip() and not val.startswith(_ENC_PREFIX):
            llm[key] = encrypt_secret(val, serial)
    patch_edu(yaml_path, llm=llm)


def _rt_yaml() -> YAML:
    yaml = YAML(typ="rt")
    yaml.preserve_quotes = True
    yaml.width = 4096
    return yaml


def _try_load_mapping(path: Path, yaml: YAML | None = None) -> Any:
    """成功则返回根映射；缺文件/损坏/非映射则 ``None``（调用方整份回退）。"""
    if not path.is_file():
        return None
    loader = yaml if yaml is not None else _rt_yaml()
    try:
        with path.open("r", encoding="utf-8") as fh:
            data = loader.load(fh)
    except (OSError, UnicodeDecodeError, YAMLError):
        return None
    if not isinstance(data, dict):
        return None
    return data


def _settings_from_nested(data: Mapping[str, Any]) -> EduSettings:
    display = data.get("display")
    if not isinstance(display, dict):
        display = {}
    audio = data.get("audio")
    if not isinstance(audio, dict):
        audio = {}
    qa = data.get("qa")
    if not isinstance(qa, dict):
        qa = {}
    llm_raw = data.get("llm")
    llm = dict(llm_raw) if isinstance(llm_raw, dict) else {}

    try:
        version = int(data.get("v", 1))
    except (TypeError, ValueError):
        version = 1

    captions = display.get("captions_enabled", False)
    if not isinstance(captions, bool):
        captions = bool(captions)

    try:
        volume = int(audio.get("volume_pct", DEFAULT_VOLUME_PCT))
    except (TypeError, ValueError):
        volume = DEFAULT_VOLUME_PCT

    retain_days = _clamp_int(
        qa.get("retain_days", DEFAULT_RETAIN_DAYS),
        DEFAULT_RETAIN_DAYS,
        1,
        MAX_RETAIN_DAYS,
    )
    context_turns = _clamp_int(
        qa.get("context_turns", DEFAULT_CONTEXT_TURNS),
        DEFAULT_CONTEXT_TURNS,
        1,
        MAX_CONTEXT_TURNS,
    )

    return EduSettings(
        v=version,
        rotation_deg=normalize_rotation(display.get("rotation_deg", 90)),
        captions_enabled=captions,
        volume_pct=volume,
        retain_days=retain_days,
        context_turns=context_turns,
        llm=llm,
    )


def _clamp_int(raw: Any, default: int, lo: int, hi: int) -> int:
    """仅接受真实 ``int``（不含 ``bool``），再钳制到闭区间 ``[lo, hi]``。

    参数:
        raw: 映射中的原始值；``bool``、``float``、字符串等一律回退 ``default``。
        default: 类型不符时的返回值。
        lo: 下限（小于 ``lo`` 的值会被抬到 ``lo``）。
        hi: 上限。

    返回:
        钳制后的整数。

    副作用:
        无。
    """
    if isinstance(raw, bool) or not isinstance(raw, int):
        return default
    if raw < lo:
        return lo
    if raw > hi:
        return hi
    return raw


def _ensure_map(parent: MutableMapping[str, Any], key: str) -> MutableMapping[str, Any]:
    node = parent.get(key)
    if not isinstance(node, dict):
        parent[key] = CommentedMap()
        node = parent[key]
    return node


def _write_settings_into(data: MutableMapping[str, Any], settings: EduSettings) -> None:
    data["v"] = settings.v
    display = _ensure_map(data, "display")
    display["rotation_deg"] = settings.rotation_deg
    display["captions_enabled"] = settings.captions_enabled
    audio = _ensure_map(data, "audio")
    audio["volume_pct"] = settings.volume_pct
    qa = _ensure_map(data, "qa")
    qa["retain_days"] = settings.retain_days
    qa["context_turns"] = settings.context_turns
    data["llm"] = settings.llm


def _nested_from_settings(settings: EduSettings) -> CommentedMap:
    data = CommentedMap()
    _write_settings_into(data, settings)
    return data


def _dump(path: Path, yaml: YAML, data: MutableMapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        yaml.dump(data, fh)
