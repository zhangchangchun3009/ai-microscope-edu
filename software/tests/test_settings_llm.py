"""LLM 设置表单：三件套校验、空密钥保持、enc1 写出、环境变量锁定。"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

_SOFTWARE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_SOFTWARE))

from app.settings_llm import (  # noqa: E402
    KEY_KEEP_PLACEHOLDER,
    LlmFormInput,
    build_llm_section,
    clamp_timeout_secs,
    locked_llm_fields,
)
from system.secret_box import decrypt_secret, encrypt_secret  # noqa: E402

_SECRET = "sk-SECRET-do-not-echo"


def _form(**overrides: object) -> LlmFormInput:
    kwargs: dict[str, object] = {
        "base_url": "https://api.example.com/v1",
        "model": "qwen-plus",
        "timeout_secs": 30,
        "api_key": "sk-new",
        "device_secret": "",
        "device_secret_hosts": "www.aiinstrum.com",
    }
    kwargs.update(overrides)
    return LlmFormInput(**kwargs)  # type: ignore[arg-type]


def test_key_placeholder_verbatim() -> None:
    assert KEY_KEEP_PLACEHOLDER == "已加密保存，输入新密钥将覆盖"


def test_timeout_clamped_to_10_600_default_30() -> None:
    assert clamp_timeout_secs(5) == 10
    assert clamp_timeout_secs(10) == 10
    assert clamp_timeout_secs(30) == 30
    assert clamp_timeout_secs(600) == 600
    assert clamp_timeout_secs(999) == 600
    assert clamp_timeout_secs("x") == 30
    assert clamp_timeout_secs(None) == 30


def test_empty_form_url_refuses_even_if_yaml_has_url() -> None:
    result = build_llm_section(
        _form(base_url=""),
        existing={"base_url": "https://old.example/v1", "api_key": "sk", "model": "m"},
        serial="s",
    )
    assert result.ok is False
    result = build_llm_section(_form(base_url="  ", api_key="sk-x"), existing={}, serial="s")
    assert result.ok is False
    assert result.llm is None
    assert "sk-x" not in result.error


def test_refuse_empty_key_without_existing() -> None:
    result = build_llm_section(_form(api_key=""), existing={"model": "m"}, serial="s")
    assert result.ok is False
    assert result.llm is None


def test_new_key_written_as_enc1_not_plaintext() -> None:
    result = build_llm_section(_form(api_key=_SECRET), existing={}, serial="serial-a")
    assert result.ok is True
    assert result.llm is not None
    token = str(result.llm["api_key"])
    assert token.startswith("enc1:")
    assert _SECRET not in token
    assert _SECRET not in str(result.llm)
    assert decrypt_secret(token, "serial-a") == _SECRET


def test_empty_key_keeps_existing_enc1() -> None:
    token = encrypt_secret("sk-live", "serial-a")
    result = build_llm_section(
        _form(api_key=""),
        existing={"base_url": "https://old.example/v1", "api_key": token, "model": "old"},
        serial="serial-a",
    )
    assert result.ok is True
    assert result.llm is not None
    assert result.llm["api_key"] == token


def test_empty_key_reencrypts_legacy_plaintext() -> None:
    result = build_llm_section(
        _form(api_key=""),
        existing={
            "base_url": "https://old.example/v1",
            "api_key": "sk-plain",
            "model": "old",
        },
        serial="serial-a",
    )
    assert result.ok is True
    assert result.llm is not None
    token = str(result.llm["api_key"])
    assert token.startswith("enc1:")
    assert decrypt_secret(token, "serial-a") == "sk-plain"


def test_decrypt_fail_without_new_key_refuses() -> None:
    result = build_llm_section(
        _form(api_key=""),
        existing={"api_key": "enc1:00", "base_url": "https://x", "model": "m"},
        serial="serial-a",
    )
    assert result.ok is False
    assert "enc1:00" not in result.error


def test_empty_hosts_keeps_existing_list() -> None:
    """保存后栏空；再保存其它字段时不得把网关地址写成空列表。"""
    result = build_llm_section(
        _form(device_secret_hosts="  "),
        existing={
            "base_url": "https://old.example/v1",
            "api_key": "sk",
            "model": "m",
            "device_secret_hosts": ["gateway.example.com"],
        },
        serial="s",
    )
    assert result.ok is True
    assert result.llm is not None
    assert result.llm["device_secret_hosts"] == ["gateway.example.com"]


def test_empty_hosts_without_existing_uses_default() -> None:
    from qa.config import DEFAULT_DEVICE_SECRET_HOSTS

    result = build_llm_section(_form(device_secret_hosts=""), existing={}, serial="s")
    assert result.ok is True
    assert result.llm is not None
    assert result.llm["device_secret_hosts"] == list(DEFAULT_DEVICE_SECRET_HOSTS)


def test_reveal_button_is_icon_only(qapp) -> None:
    """眼睛钮无文字，开/闭两枚图标都有效。"""
    del qapp
    from app.settings_llm import make_eye_icon, reveal_button_caption

    assert reveal_button_caption(revealed=False) == ""
    assert reveal_button_caption(revealed=True) == ""
    opened = make_eye_icon(revealed=False)
    hidden = make_eye_icon(revealed=True)
    assert opened is not None
    assert hidden is not None
    assert not opened.isNull()
    assert not hidden.isNull()


def test_timeout_written_clamped() -> None:
    result = build_llm_section(_form(timeout_secs=3), existing={}, serial="s")
    assert result.ok is True
    assert result.llm is not None
    assert result.llm["timeout_secs"] == 10


def test_locked_fields_from_environ() -> None:
    assert locked_llm_fields({}) == frozenset()
    locked = locked_llm_fields(
        {
            "EDU_LLM_BASE_URL": "https://env.example/v1",
            "EDU_LLM_API_KEY": "sk-env",
            "EDU_LLM_MODEL": "env-model",
            "EDU_LLM_DEVICE_SECRET": "sec",
            "EDU_LLM_DEVICE_SECRET_HOSTS": "h",
        }
    )
    assert locked == frozenset(
        {"base_url", "api_key", "model", "device_secret", "device_secret_hosts"}
    )


def test_env_locked_key_ignores_form_and_keeps_existing() -> None:
    token = encrypt_secret("sk-disk", "serial-a")
    result = build_llm_section(
        _form(api_key="sk-should-ignore"),
        existing={"api_key": token, "base_url": "https://disk.example/v1", "model": "disk"},
        serial="serial-a",
        environ={"EDU_LLM_API_KEY": "sk-env"},
    )
    assert result.ok is True
    assert result.llm is not None
    assert result.llm["api_key"] == token
    assert "sk-should-ignore" not in str(result.llm)
    assert "sk-env" not in str(result.llm)


@pytest.fixture
def qapp():
    """进程内唯一 QApplication（offscreen）。"""
    pytest.importorskip("PySide6")
    from PySide6.QtWidgets import QApplication

    return QApplication.instance() or QApplication([])


def test_llm_save_oserror_shows_banner_without_modal(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    qapp,
) -> None:
    """LLM 写盘 OSError 用页内横幅，不得 QMessageBox.exec。"""
    del qapp
    from PySide6.QtWidgets import QMessageBox

    from app.settings_llm import LlmSettingsPage
    from system.edu_config import patch_edu

    path = tmp_path / "edu.yaml"
    patch_edu(
        path,
        llm={
            "base_url": "https://api.example.com/v1",
            "api_key": "sk-keep",
            "model": "qwen-plus",
        },
    )
    execs: list[str] = []
    monkeypatch.setattr(QMessageBox, "exec", lambda *a, **k: execs.append("exec") or 0)
    monkeypatch.setattr(QMessageBox, "warning", lambda *a, **k: execs.append("warn"))

    def boom(*_args: object, **_kwargs: object) -> None:
        raise OSError("disk full")

    monkeypatch.setattr("app.settings_llm.patch_edu", boom)
    page = LlmSettingsPage(on_back=lambda: None, edu_path=path, serial="serial-a")
    page._on_save()
    assert execs == []
    assert not page._banner.isHidden()
    assert "无法写入" in page._banner.text()


def test_llm_trio_refuse_shows_banner_without_modal(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    qapp,
) -> None:
    """缺三件套时页内提示，不弹模态框。"""
    del qapp
    from PySide6.QtWidgets import QMessageBox

    from app.settings_llm import LlmSettingsPage

    execs: list[str] = []
    monkeypatch.setattr(QMessageBox, "exec", lambda *a, **k: execs.append("exec") or 0)
    monkeypatch.setattr(QMessageBox, "warning", lambda *a, **k: execs.append("warn"))
    path = tmp_path / "edu.yaml"
    page = LlmSettingsPage(on_back=lambda: None, edu_path=path, serial="serial-a")
    page._base_url.setText("")
    page._model.setText("")
    page._api_key.setText("")
    page._on_save()
    assert execs == []
    assert not page._banner.isHidden()
    assert page._banner.text()


def test_llm_page_labels_and_secrets_blank_after_fill(
    tmp_path: Path,
    qapp,
) -> None:
    """网关口令保存后不回显；网关地址明文；密钥用眼睛图标切明文。"""
    del qapp
    from PySide6.QtWidgets import QFormLayout, QLineEdit, QScrollArea

    from app.settings_llm import LlmSettingsPage
    from system.edu_config import patch_edu
    from system.secret_box import encrypt_secret

    path = tmp_path / "edu.yaml"
    patch_edu(
        path,
        llm={
            "base_url": "https://api.example.com/v1",
            "api_key": encrypt_secret("sk-keep", "serial-a"),
            "model": "qwen-plus",
            "device_secret": encrypt_secret("gw-keep", "serial-a"),
            "device_secret_hosts": ["www.aiinstrum.com"],
        },
    )
    page = LlmSettingsPage(on_back=lambda: None, edu_path=path, serial="serial-a")
    form = page.findChild(QFormLayout)
    labels = [
        form.itemAt(i, QFormLayout.ItemRole.LabelRole).widget().text()
        for i in range(form.rowCount())
        if form.itemAt(i, QFormLayout.ItemRole.LabelRole) is not None
    ]
    assert "API 网关口令" in labels
    assert "API 网关地址" in labels
    assert "设备暗号" not in labels
    assert "暗号主机" not in labels
    assert page._device_secret.text() == ""
    assert page._hosts.text() == "www.aiinstrum.com"
    assert page._device_secret.echoMode() == QLineEdit.EchoMode.Password
    assert page._hosts.echoMode() == QLineEdit.EchoMode.Normal
    assert page.findChildren(QScrollArea) == []
    assert page._reveal_secret.text() == ""
    assert not page._reveal_secret.icon().isNull()
    page._reveal_secret.setChecked(True)
    assert page._device_secret.echoMode() == QLineEdit.EchoMode.Normal
    page._fill_from_disk()
    assert page._device_secret.text() == ""
    assert page._hosts.text() == "www.aiinstrum.com"
    assert page._reveal_secret.isChecked() is False
    assert page._device_secret.echoMode() == QLineEdit.EchoMode.Password


def test_llm_page_discards_unsaved_on_reshow(
    tmp_path: Path,
    qapp,
) -> None:
    """未保存就离开再进入，输入框回到 yaml，不把草稿留下来。"""
    from PySide6.QtWidgets import QLineEdit

    from app.settings_llm import LlmSettingsPage
    from system.edu_config import patch_edu
    from system.secret_box import encrypt_secret

    path = tmp_path / "edu.yaml"
    patch_edu(
        path,
        llm={
            "base_url": "https://api.example.com/v1",
            "api_key": encrypt_secret("sk-keep", "serial-a"),
            "model": "qwen-plus",
            "device_secret_hosts": ["www.aiinstrum.com"],
        },
    )
    page = LlmSettingsPage(on_back=lambda: None, edu_path=path, serial="serial-a")
    page.show()
    qapp.processEvents()
    page._base_url.setText("https://draft.example/v1")
    page._api_key.setText("sk-draft")
    page._hosts.setText("draft.example")
    page.hide()
    qapp.processEvents()
    page.show()
    qapp.processEvents()
    assert page._base_url.text() == "https://api.example.com/v1"
    assert page._api_key.text() == ""
    assert page._api_key.echoMode() == QLineEdit.EchoMode.Password
    assert page._hosts.text() == "www.aiinstrum.com"
