"""无桌面时的 Qt 平台插件。211 上必须 linuxfb，eglfs_kms 会 ABRT。"""

from __future__ import annotations

import os


def ensure_embedded_platform() -> None:
    """已有 DISPLAY/WAYLAND 或已设 QT_QPA_PLATFORM 时不改。"""
    if os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY"):
        return
    os.environ.setdefault("QT_QPA_PLATFORM", "linuxfb:fb=/dev/fb0")
