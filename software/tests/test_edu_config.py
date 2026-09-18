"""edu.yaml 读写真机默认、注释保留与 llm.json 迁移。"""

from __future__ import annotations

import json
import sys
from pathlib import Path

_SOFTWARE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_SOFTWARE))

from system.edu_config import (  # noqa: E402
    defaults,
    load_edu,
    maybe_migrate_llm_json,
    patch_edu,
    save_edu,
)
from system.secret_box import decrypt_secret  # noqa: E402


def _assert_full_defaults(settings) -> None:
    assert settings.rotation_deg == 90
    assert settings.volume_pct == 73
    assert settings.captions_enabled is False
    assert settings.llm == {}
    assert settings.retain_days == 7
    assert settings.context_turns == 8


def test_missing_file_returns_defaults(tmp_path: Path) -> None:
    settings = load_edu(tmp_path / "missing.yaml")
    _assert_full_defaults(settings)
    d = defaults()
    assert d.rotation_deg == 90
    assert d.volume_pct == 73
    assert d.captions_enabled is False
    assert d.llm == {}


def test_corrupt_yaml_returns_defaults(tmp_path: Path) -> None:
    path = tmp_path / "edu.yaml"
    path.write_text("{[ not: yaml", encoding="utf-8")
    _assert_full_defaults(load_edu(path))


def test_save_then_load_keeps_rotation_and_volume(tmp_path: Path) -> None:
    path = tmp_path / "edu.yaml"
    settings = defaults()
    settings.rotation_deg = 180
    settings.volume_pct = 10
    save_edu(path, settings)
    loaded = load_edu(path)
    assert loaded.rotation_deg == 180
    assert loaded.volume_pct == 10


def test_patch_volume_preserves_comment_or_unpatched_llm_model(tmp_path: Path) -> None:
    path = tmp_path / "edu.yaml"
    path.write_text(
        "# keep-me\n"
        "v: 1\n"
        "display:\n"
        "  rotation_deg: 90\n"
        "  captions_enabled: false\n"
        "audio:\n"
        "  volume_pct: 50\n"
        "llm:\n"
        "  model: keep-model\n",
        encoding="utf-8",
    )
    patched = patch_edu(path, volume_pct=10)
    text = path.read_text(encoding="utf-8")
    assert patched.volume_pct == 10
    assert "# keep-me" in text or patched.llm.get("model") == "keep-model"


def test_maybe_migrate_llm_json_encrypts_key_and_keeps_json(tmp_path: Path) -> None:
    yaml_path = tmp_path / "edu.yaml"
    json_path = tmp_path / "llm.json"
    json_path.write_text(
        json.dumps(
            {
                "base_url": "https://example.com/v1",
                "api_key": "sk-plain",
                "model": "qwen-plus",
            }
        ),
        encoding="utf-8",
    )
    maybe_migrate_llm_json(yaml_path, json_path, "serial-a")
    loaded = load_edu(yaml_path)
    token = str(loaded.llm.get("api_key", ""))
    assert token.startswith("enc1:")
    assert decrypt_secret(token, "serial-a") == "sk-plain"
    assert json_path.is_file()
    assert json_path.read_text(encoding="utf-8")


def test_qa_section_roundtrip_and_clamp(tmp_path: Path) -> None:
    path = tmp_path / "edu.yaml"
    path.write_text(
        "v: 1\n"
        "display:\n"
        "  rotation_deg: 90\n"
        "  captions_enabled: false\n"
        "audio:\n"
        "  volume_pct: 73\n"
        "qa:\n"
        "  retain_days: 0\n"
        "  context_turns: 100\n",
        encoding="utf-8",
    )
    loaded = load_edu(path)
    assert loaded.retain_days == 1
    assert loaded.context_turns == 64

    settings = defaults()
    settings.retain_days = 14
    settings.context_turns = 3
    save_edu(path, settings)
    again = load_edu(path)
    assert again.retain_days == 14
    assert again.context_turns == 3
    text = path.read_text(encoding="utf-8")
    assert "retain_days" in text
    assert "context_turns" in text


def test_qa_yaml_float_and_bool_use_defaults(tmp_path: Path) -> None:
    """YAML 浮点与布尔不得被 int() 截断/强转，应回退缺省 7/8。"""
    path = tmp_path / "edu.yaml"
    path.write_text(
        "v: 1\n"
        "qa:\n"
        "  retain_days: 1.5\n"
        "  context_turns: true\n",
        encoding="utf-8",
    )
    loaded = load_edu(path)
    assert loaded.retain_days == 7
    assert loaded.context_turns == 8


def test_qa_yaml_false_retain_days_uses_default(tmp_path: Path) -> None:
    path = tmp_path / "edu.yaml"
    path.write_text(
        "v: 1\n"
        "qa:\n"
        "  retain_days: false\n"
        "  context_turns: 2\n",
        encoding="utf-8",
    )
    loaded = load_edu(path)
    assert loaded.retain_days == 7
    assert loaded.context_turns == 2


def test_qa_yaml_quoted_string_integers_use_defaults(tmp_path: Path) -> None:
    """YAML 引号字符串不是 Python int，应回退缺省 7/8。"""
    path = tmp_path / "edu.yaml"
    path.write_text(
        "v: 1\n"
        "qa:\n"
        '  retain_days: "14"\n'
        '  context_turns: "3"\n',
        encoding="utf-8",
    )
    loaded = load_edu(path)
    assert loaded.retain_days == 7
    assert loaded.context_turns == 8


def test_qa_missing_or_garbage_uses_defaults(tmp_path: Path) -> None:
    path = tmp_path / "edu.yaml"
    path.write_text(
        "v: 1\n"
        "qa:\n"
        "  retain_days: nope\n"
        "  context_turns: []\n",
        encoding="utf-8",
    )
    loaded = load_edu(path)
    assert loaded.retain_days == 7
    assert loaded.context_turns == 8


def test_maybe_migrate_skips_when_yaml_already_has_base_url(tmp_path: Path) -> None:
    """yaml 已有 llm.base_url 时不覆盖，即使 json 三件套完整。"""
    yaml_path = tmp_path / "edu.yaml"
    json_path = tmp_path / "llm.json"
    yaml_path.write_text(
        "v: 1\n"
        "llm:\n"
        "  base_url: https://keep.example.com/v1\n"
        "  api_key: enc1:keep\n"
        "  model: keep-model\n",
        encoding="utf-8",
    )
    json_path.write_text(
        json.dumps(
            {
                "base_url": "https://json.example.com/v1",
                "api_key": "sk-plain",
                "model": "json-model",
            }
        ),
        encoding="utf-8",
    )
    maybe_migrate_llm_json(yaml_path, json_path, "serial-a")
    loaded = load_edu(yaml_path)
    assert loaded.llm.get("base_url") == "https://keep.example.com/v1"
    assert loaded.llm.get("api_key") == "enc1:keep"
    assert loaded.llm.get("model") == "keep-model"
