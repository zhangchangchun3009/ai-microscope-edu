"""大模型子页：yaml ``llm`` 段表单；密钥不回显明文。"""

from __future__ import annotations

import logging
import os
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from app.theme import SETTINGS_CTRL_H
from qa.config import DEFAULT_DEVICE_SECRET_HOSTS, DEFAULT_LLM_TIMEOUT_S
from system.device_id import read_cpu_serial
from system.edu_config import edu_yaml_path, load_edu, patch_edu
from system.secret_box import decrypt_secret, encrypt_secret

_LOG = logging.getLogger(__name__)

KEY_KEEP_PLACEHOLDER = "已加密保存，输入新密钥将覆盖"
_TIMEOUT_MIN = 10
_TIMEOUT_MAX = 600
_TIMEOUT_DEFAULT = int(DEFAULT_LLM_TIMEOUT_S)
_ENV_TO_FIELD = {
    "EDU_LLM_BASE_URL": "base_url",
    "EDU_LLM_API_KEY": "api_key",
    "EDU_LLM_MODEL": "model",
    "EDU_LLM_DEVICE_SECRET": "device_secret",
    "EDU_LLM_DEVICE_SECRET_HOSTS": "device_secret_hosts",
}
_TRIO_REFUSE = "请填写接口地址、密钥和模型。"
_DECRYPT_HINT = "密钥无法在本机解密，请重新输入"
_ENV_BANNER = "部分字段由环境变量 EDU_LLM_* 锁定，无法在此修改。"


@dataclass(frozen=True)
class LlmFormInput:
    """设置页提交的 LLM 表单值（密钥栏空表示保持原密文）。"""

    base_url: str
    model: str
    timeout_secs: object
    api_key: str
    device_secret: str
    device_secret_hosts: str


@dataclass(frozen=True)
class LlmFormResult:
    """表单校验与加密结果；``error`` 不得包含明文密钥。"""

    ok: bool
    llm: dict[str, Any] | None
    error: str = ""


def locked_llm_fields(environ: Mapping[str, str]) -> frozenset[str]:
    """返回已出现在进程环境中的 ``EDU_LLM_*`` 对应表单字段名。

    参数:
        environ: 环境映射；只看键是否存在，不看值。

    返回:
        ``base_url`` / ``api_key`` / ``model`` / ``device_secret`` /
        ``device_secret_hosts`` 的冻结集合。

    副作用:
        无。
    """
    return frozenset(
        field for env_name, field in _ENV_TO_FIELD.items() if env_name in environ
    )


def clamp_timeout_secs(raw: object) -> int:
    """把超时夹到 10–600 秒；非法值回退 30。

    参数:
        raw: 表单或 yaml 中的超时（秒）。

    返回:
        夹紧后的整数秒。

    副作用:
        无。
    """
    try:
        value = int(raw)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return _TIMEOUT_DEFAULT
    return max(_TIMEOUT_MIN, min(_TIMEOUT_MAX, value))


def parse_host_list(text: str) -> list[str]:
    """把逗号或换行分隔的 host 文本解析成列表；空串得到空列表。

    参数:
        text: 教师输入的白名单。

    返回:
        去空白后的 host 列表；显式空表示不加网关头。

    副作用:
        无。
    """
    parts = [item.strip() for item in text.replace("\n", ",").split(",")]
    return [item for item in parts if item]


def build_llm_section(
    form: LlmFormInput,
    *,
    existing: Mapping[str, Any],
    serial: str,
    environ: Mapping[str, str] | None = None,
) -> LlmFormResult:
    """根据表单与已有 yaml 组装可写入的 ``llm`` 段。

    参数:
        form: 界面字段；``api_key`` / ``device_secret`` 空表示保持。
        existing: 当前 yaml 的 ``llm`` 映射。
        serial: 本机 CPU 序列号，用于 ``enc1:``。
        environ: 用于判定 ``EDU_LLM_*`` 锁定；缺省空映射。

    返回:
        三件套（url / 解密后的 key / model）均非空时 ``ok`` 且 ``llm``
        含 ``enc1:`` 密钥；否则 ``ok=False`` 且 ``error`` 无明文。

    副作用:
        可能调用 :func:`encrypt_secret`（随机 nonce）。
    """
    env = environ if environ is not None else {}
    locked = locked_llm_fields(env)
    url = _effective_url(form.base_url, existing, env, locked)
    model = _effective_model(form.model, existing, env, locked)
    key_plain = _effective_plain_secret(
        form.api_key,
        existing.get("api_key"),
        serial,
        env,
        env_name="EDU_LLM_API_KEY",
        locked_field="api_key",
        locked=locked,
    )
    if not url or not model or not key_plain:
        return LlmFormResult(ok=False, llm=None, error=_TRIO_REFUSE)

    api_token = _token_for_save(
        form.api_key,
        existing.get("api_key"),
        serial,
        locked="api_key" in locked,
    )
    secret_token = _token_for_save(
        form.device_secret,
        existing.get("device_secret"),
        serial,
        locked="device_secret" in locked,
    )
    hosts = _hosts_for_save(form.device_secret_hosts, existing, locked)

    llm: dict[str, Any] = dict(existing)
    llm["base_url"] = _field_to_write(
        form.base_url.strip(),
        str(existing.get("base_url") or "").strip(),
        locked="base_url" in locked,
    )
    llm["model"] = _field_to_write(
        form.model.strip(),
        str(existing.get("model") or "").strip(),
        locked="model" in locked,
    )
    llm["timeout_secs"] = clamp_timeout_secs(form.timeout_secs)
    if api_token:
        llm["api_key"] = api_token
    if secret_token:
        llm["device_secret"] = secret_token
    elif "device_secret" not in existing or not str(
        existing.get("device_secret") or ""
    ).strip():
        llm.pop("device_secret", None)
    llm["device_secret_hosts"] = hosts
    return LlmFormResult(ok=True, llm=llm, error="")


def _field_to_write(form_value: str, existing_value: str, *, locked: bool) -> str:
    return existing_value if locked else form_value


def _effective_url(
    form_url: str,
    existing: Mapping[str, Any],
    env: Mapping[str, str],
    locked: frozenset[str],
) -> str:
    del existing, locked
    if "EDU_LLM_BASE_URL" in env:
        return str(env.get("EDU_LLM_BASE_URL") or "").strip()
    return form_url.strip()


def _effective_model(
    form_model: str,
    existing: Mapping[str, Any],
    env: Mapping[str, str],
    locked: frozenset[str],
) -> str:
    del existing, locked
    if "EDU_LLM_MODEL" in env:
        return str(env.get("EDU_LLM_MODEL") or "").strip()
    return form_model.strip()


def _effective_plain_secret(
    form_value: str,
    existing_token: object,
    serial: str,
    env: Mapping[str, str],
    *,
    env_name: str,
    locked_field: str,
    locked: frozenset[str],
) -> str:
    if env_name in env:
        return str(env.get(env_name) or "").strip()
    if locked_field in locked:
        return _decrypt_or_empty(existing_token, serial)
    new = form_value.strip()
    if new:
        return new
    return _decrypt_or_empty(existing_token, serial)


def _decrypt_or_empty(token: object, serial: str) -> str:
    raw = str(token or "").strip()
    if not raw:
        return ""
    try:
        return decrypt_secret(raw, serial).strip()
    except ValueError:
        return ""


def _token_for_save(
    form_value: str,
    existing_token: object,
    serial: str,
    *,
    locked: bool,
) -> str:
    existing = str(existing_token or "").strip()
    if locked:
        return _reencrypt_if_plain(existing, serial)
    new = form_value.strip()
    if new:
        return encrypt_secret(new, serial)
    return _reencrypt_if_plain(existing, serial)


def _reencrypt_if_plain(existing: str, serial: str) -> str:
    if not existing:
        return ""
    if existing.startswith("enc1:"):
        return existing
    return encrypt_secret(existing, serial)


def _hosts_for_save(
    form_text: str,
    existing: Mapping[str, Any],
    locked: frozenset[str],
) -> list[str]:
    if "device_secret_hosts" in locked:
        raw = existing.get("device_secret_hosts")
        if isinstance(raw, list):
            return [str(item).strip() for item in raw if str(item).strip()]
        if isinstance(raw, str):
            return parse_host_list(raw)
        if "device_secret_hosts" not in existing:
            return list(DEFAULT_DEVICE_SECRET_HOSTS)
        return []
    return parse_host_list(form_text)


def _hosts_for_display(existing: Mapping[str, Any]) -> str:
    if "device_secret_hosts" not in existing:
        return ",".join(DEFAULT_DEVICE_SECRET_HOSTS)
    raw = existing.get("device_secret_hosts")
    if isinstance(raw, list):
        return ", ".join(str(item).strip() for item in raw if str(item).strip())
    if isinstance(raw, str):
        return raw.strip()
    return ""


def _secret_undecryptable(token: object, serial: str) -> bool:
    raw = str(token or "").strip()
    if not raw.startswith("enc1:"):
        return False
    try:
        decrypt_secret(raw, serial)
    except ValueError:
        return True
    return False


class LlmSettingsPage(QWidget):
    """设置栈中的大模型连接表单。"""

    def __init__(
        self,
        on_back: Callable[[], None],
        *,
        edu_path: Path | None = None,
        reload_llm: Callable[[], None] | None = None,
        environ: Mapping[str, str] | None = None,
        serial: str | None = None,
        parent: QWidget | None = None,
    ) -> None:
        """组装 LLM 字段；密钥栏空且带占位，不回显明文。

        参数:
            on_back: 页头「返回」。
            edu_path: ``edu.yaml``；缺省 :func:`edu_yaml_path`。
            reload_llm: 保存成功后调用（通常 ``QaService.reload_llm``）；
                进行中的回合由问答层快照配置，不会被打断。
            environ: 覆盖 ``os.environ`` 以便测试；缺省进程环境。
            serial: 加解密用序列号；缺省读本机。
            parent: 父控件。

        返回:
            无。

        副作用:
            读 ``edu.yaml`` 填非密钥字段。
        """
        super().__init__(parent)
        self.setObjectName("settingsLlmPage")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self._edu_path = edu_path if edu_path is not None else edu_yaml_path()
        self._reload_llm = reload_llm
        self._environ: Mapping[str, str] = (
            environ if environ is not None else os.environ
        )
        self._serial = serial if serial is not None else read_cpu_serial()
        self._banner = QLabel(self)
        self._banner.setObjectName("settingsBanner")
        self._banner.setWordWrap(True)
        self._base_url = QLineEdit(self)
        self._model = QLineEdit(self)
        self._timeout = QSpinBox(self)
        self._timeout.setRange(_TIMEOUT_MIN, _TIMEOUT_MAX)
        self._timeout.setValue(_TIMEOUT_DEFAULT)
        self._timeout.setMinimumHeight(SETTINGS_CTRL_H)
        self._api_key = self._secret_edit()
        self._device_secret = self._secret_edit()
        self._hosts = QLineEdit(self)
        for widget in (self._base_url, self._model, self._hosts):
            widget.setMinimumHeight(SETTINGS_CTRL_H)
        self._fill_from_disk()

        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        inner = QWidget()
        form = QFormLayout(inner)
        form.setContentsMargins(0, 0, 0, 0)
        form.setSpacing(12)
        form.addRow("接口地址", self._base_url)
        form.addRow("模型", self._model)
        form.addRow("超时（秒）", self._timeout)
        form.addRow("API 密钥", self._api_key)
        form.addRow("设备暗号", self._device_secret)
        form.addRow("暗号主机", self._hosts)
        scroll.setWidget(inner)

        save_btn = QPushButton("保存")
        save_btn.setObjectName("settingsNav")
        save_btn.setMinimumHeight(SETTINGS_CTRL_H)
        save_btn.clicked.connect(self._on_save)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(12)
        layout.addLayout(self._header("大模型", "返回", on_back))
        layout.addWidget(self._banner)
        layout.addWidget(scroll, 1)
        layout.addWidget(save_btn)

    def _secret_edit(self) -> QLineEdit:
        """空栏 + 占位 + 密码回显，避免露出明文。"""
        edit = QLineEdit(self)
        edit.setEchoMode(QLineEdit.EchoMode.Password)
        edit.setPlaceholderText(KEY_KEEP_PLACEHOLDER)
        edit.setMinimumHeight(SETTINGS_CTRL_H)
        return edit

    def _header(
        self,
        title: str,
        action: str,
        on_action: Callable[[], None],
    ) -> QHBoxLayout:
        """页头标题与返回钮。"""
        row = QHBoxLayout()
        label = QLabel(title)
        label.setObjectName("settingsTitle")
        label.setAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft)
        btn = QPushButton(action)
        btn.setObjectName("ghostBtn")
        btn.setFixedHeight(SETTINGS_CTRL_H)
        btn.clicked.connect(on_action)
        row.addWidget(label, 1)
        row.addWidget(btn, 0)
        return row

    def _fill_from_disk(self) -> None:
        """用 yaml 填非密钥字段；密钥栏保持空。"""
        llm = dict(load_edu(self._edu_path).llm)
        locked = locked_llm_fields(self._environ)
        self._base_url.setText(str(llm.get("base_url") or "").strip())
        self._model.setText(str(llm.get("model") or "").strip())
        self._timeout.setValue(clamp_timeout_secs(llm.get("timeout_secs", _TIMEOUT_DEFAULT)))
        self._api_key.setText("")
        self._device_secret.setText("")
        self._hosts.setText(_hosts_for_display(llm))
        if "EDU_LLM_BASE_URL" in self._environ:
            self._base_url.setText(str(self._environ.get("EDU_LLM_BASE_URL") or ""))
        if "EDU_LLM_MODEL" in self._environ:
            self._model.setText(str(self._environ.get("EDU_LLM_MODEL") or ""))
        if "EDU_LLM_DEVICE_SECRET_HOSTS" in self._environ:
            self._hosts.setText(str(self._environ.get("EDU_LLM_DEVICE_SECRET_HOSTS") or ""))
        self._base_url.setReadOnly("base_url" in locked)
        self._model.setReadOnly("model" in locked)
        self._api_key.setReadOnly("api_key" in locked)
        self._device_secret.setReadOnly("device_secret" in locked)
        self._hosts.setReadOnly("device_secret_hosts" in locked)
        banners: list[str] = []
        if locked:
            banners.append(_ENV_BANNER)
        if _secret_undecryptable(llm.get("api_key"), self._serial) or _secret_undecryptable(
            llm.get("device_secret"), self._serial
        ):
            banners.append(_DECRYPT_HINT)
        self._banner.setObjectName("settingsBanner")
        self._banner.setText("\n".join(banners))
        self._banner.setVisible(bool(banners))

    def _show_error(self, message: str) -> None:
        """用页内横幅显示错误，避免嵌套代理上的模态框冻死 kiosk。"""
        self._banner.setObjectName("settingsError")
        self._banner.setText(message)
        self._banner.setVisible(True)

    def _on_save(self) -> None:
        """校验三件套、写出 enc1，并 reload；异常文案不含明文。"""
        existing = dict(load_edu(self._edu_path).llm)
        form = LlmFormInput(
            base_url=self._base_url.text(),
            model=self._model.text(),
            timeout_secs=self._timeout.value(),
            api_key=self._api_key.text(),
            device_secret=self._device_secret.text(),
            device_secret_hosts=self._hosts.text(),
        )
        result = build_llm_section(
            form,
            existing=existing,
            serial=self._serial,
            environ=self._environ,
        )
        if not result.ok or result.llm is None:
            self._show_error(result.error or _TRIO_REFUSE)
            return
        try:
            patch_edu(self._edu_path, llm=result.llm)
        except OSError:
            _LOG.exception("保存 LLM 配置失败")
            self._show_error("无法写入大模型配置。")
            return
        except Exception:
            _LOG.exception("保存 LLM 配置失败")
            self._show_error("无法写入大模型配置。")
            return
        if self._reload_llm is not None:
            try:
                self._reload_llm()
            except Exception:
                _LOG.exception("reload_llm 失败")
        self._api_key.setText("")
        self._device_secret.setText("")
        self._fill_from_disk()
