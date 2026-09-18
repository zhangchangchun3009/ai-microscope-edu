"""基于设备 serial 派生密钥的 AES-GCM 密文封装（enc1）。"""

from __future__ import annotations

import hashlib
import os

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

_PREFIX = "enc1:"
_SALT = b"ai-microscope-edu-llm-v1|"
_NONCE_LEN = 12
_TAG_LEN = 16
# AESGCM.encrypt 返回 ciphertext ‖ tag；落盘规格为 nonce ‖ tag ‖ ciphertext。
_MIN_BLOB = _NONCE_LEN + _TAG_LEN


def _key(serial: str) -> bytes:
    return hashlib.sha256(_SALT + serial.encode("utf-8")).digest()


def encrypt_secret(plain: str, serial: str) -> str:
    """用设备 serial 派生密钥，将明文加密为 ``enc1:`` + hex 令牌。

    参数:
        plain: UTF-8 明文（如 LLM API key）。
        serial: 设备序列号，须与解密时一致。

    返回:
        以 ``enc1:`` 为前缀的 hex 字符串（nonce ‖ tag ‖ ciphertext）。

    副作用:
        调用 ``os.urandom`` 生成随机 nonce。
    """
    nonce = os.urandom(_NONCE_LEN)
    packed = AESGCM(_key(serial)).encrypt(nonce, plain.encode("utf-8"), None)
    ciphertext, tag = packed[:-_TAG_LEN], packed[-_TAG_LEN:]
    return _PREFIX + (nonce + tag + ciphertext).hex()


def decrypt_secret(token: str, serial: str) -> str:
    """解密 ``enc1:`` 令牌；非 enc1 前缀当明文透传。

    参数:
        token: ``enc1:`` 密文或明文 API key。
        serial: 设备序列号，须与加密时一致。

    返回:
        解密或透传后的 UTF-8 字符串。

    副作用:
        无。

    异常:
        ValueError: 密文过短或 AES-GCM 校验/解密失败。
    """
    raw = (token or "").strip()
    if not raw.startswith(_PREFIX):
        return raw
    blob = bytes.fromhex(raw[len(_PREFIX) :])
    if len(blob) < _MIN_BLOB:
        raise ValueError("enc1 密文过短")
    nonce = blob[:_NONCE_LEN]
    tag = blob[_NONCE_LEN : _NONCE_LEN + _TAG_LEN]
    ciphertext = blob[_NONCE_LEN + _TAG_LEN :]
    try:
        return AESGCM(_key(serial)).decrypt(nonce, ciphertext + tag, None).decode("utf-8")
    except Exception as exc:
        raise ValueError("enc1 解密失败") from exc
