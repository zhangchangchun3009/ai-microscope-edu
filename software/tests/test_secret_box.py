"""CPU 序列号派生 AES-GCM；换 serial 不可解。"""

from __future__ import annotations

import hashlib
import sys
from pathlib import Path

import pytest
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

_SOFTWARE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_SOFTWARE))

from system.device_id import read_cpu_serial  # noqa: E402
from system.secret_box import decrypt_secret, encrypt_secret  # noqa: E402

_PREFIX = "enc1:"
_SALT = b"ai-microscope-edu-llm-v1|"
_NONCE_LEN = 12
_TAG_LEN = 16


def test_cpuinfo_serial_lowercase() -> None:
    blob = "processor\t: 0\nSerial\t\t: 0123ABCD\n"
    assert read_cpu_serial(cpuinfo=blob, dt_serial=None) == "0123abcd"


def test_dt_serial_wins() -> None:
    assert read_cpu_serial(cpuinfo="Serial: dead", dt_serial="AABB") == "aabb"


def test_missing_falls_back_macos_dev() -> None:
    assert read_cpu_serial(cpuinfo="", dt_serial=None) == "macos-dev"


def test_roundtrip_same_serial() -> None:
    token = encrypt_secret("sk-live", "serial-a")
    assert token.startswith("enc1:")
    assert decrypt_secret(token, "serial-a") == "sk-live"


def test_roundtrip_empty_plaintext() -> None:
    serial = "serial-a"
    assert decrypt_secret(encrypt_secret("", serial), serial) == ""


def test_wrong_serial_raises() -> None:
    token = encrypt_secret("sk-live", "serial-a")
    with pytest.raises(ValueError):
        decrypt_secret(token, "serial-b")


def test_plaintext_passthrough() -> None:
    assert decrypt_secret("sk-plain", "serial-a") == "sk-plain"


def test_runtime_dt_serial_lowercase(monkeypatch: pytest.MonkeyPatch) -> None:
    """运行时设备树原文（无 Serial: 行）应直接小写返回，不得当 cpuinfo 解析。"""
    monkeypatch.setattr("system.device_id._read_dt_serial", lambda: "AABBCCDD")
    monkeypatch.setattr("system.device_id._read_cpuinfo_file", lambda: "Serial: dead")
    assert read_cpu_serial() == "aabbccdd"


def test_runtime_cpuinfo_when_dt_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    """无设备树时运行时仍解析 /proc/cpuinfo 的 Serial 行。"""
    monkeypatch.setattr("system.device_id._read_dt_serial", lambda: None)
    monkeypatch.setattr(
        "system.device_id._read_cpuinfo_file",
        lambda: "processor\t: 0\nSerial\t\t: 0123ABCD\n",
    )
    assert read_cpu_serial() == "0123abcd"


def test_enc1_layout_nonce_tag_ciphertext() -> None:
    """enc1 hex 为 nonce(12) ‖ tag(16) ‖ ciphertext，按规格顺序可用 AESGCM 解开。"""
    serial = "serial-a"
    token = encrypt_secret("sk-live", serial)
    assert token.startswith(_PREFIX)
    blob = bytes.fromhex(token[len(_PREFIX) :])
    nonce = blob[:_NONCE_LEN]
    tag = blob[_NONCE_LEN : _NONCE_LEN + _TAG_LEN]
    ciphertext = blob[_NONCE_LEN + _TAG_LEN :]
    assert len(nonce) == _NONCE_LEN
    assert len(tag) == _TAG_LEN
    assert len(ciphertext) >= 1
    key = hashlib.sha256(_SALT + serial.encode("utf-8")).digest()
    plain = AESGCM(key).decrypt(nonce, ciphertext + tag, None)
    assert plain == b"sk-live"
