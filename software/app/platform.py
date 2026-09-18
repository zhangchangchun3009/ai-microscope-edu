"""无桌面时的 Qt 平台插件。211 上必须 linuxfb，eglfs_kms 会 ABRT。"""

from __future__ import annotations

import os

# 语言切换只保留简中、繁中、英文；其它 VirtualKeyboard 插件不进菜单。
VK_LOCALES = ("zh_CN", "zh_TW", "en_US")


def ensure_embedded_platform() -> None:
    """已有 DISPLAY/WAYLAND 或已设 QT_QPA_PLATFORM 时不改。"""
    if os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY"):
        return
    os.environ.setdefault("QT_QPA_PLATFORM", "linuxfb:fb=/dev/fb0")


def apply_virtual_keyboard_locale() -> None:
    """``QT_IM_MODULE=qtvirtualkeyboard`` 时默认简体中文拼音。

    须在创建 ``QApplication`` 之前调用。未设置该模块时为空操作。
    同时关掉顶层 Desktop InputPanel；linuxfb 下启用软件 Qt Quick 后端，
    以便把 ``InputPanel`` 嵌进主窗。

    参数:
        无。

    返回:
        无。

    副作用:
        设置 ``QLocale`` 为简体中文；可能写入 ``QT_VIRTUALKEYBOARD_*``
        与 ``QT_QUICK_BACKEND``。
    """
    if os.environ.get("QT_IM_MODULE") != "qtvirtualkeyboard":
        return
    os.environ.setdefault("QT_VIRTUALKEYBOARD_DESKTOP_DISABLE", "1")
    os.environ.setdefault(
        "QT_VIRTUALKEYBOARD_AVAILABLE_LOCALES",
        ",".join(VK_LOCALES),
    )
    # linuxfb 没有 EGL；内嵌 InputPanel 走软件场景图。
    if not os.environ.get("DISPLAY") and not os.environ.get("WAYLAND_DISPLAY"):
        os.environ.setdefault("QT_QUICK_BACKEND", "software")
    from PySide6.QtCore import QLocale

    QLocale.setDefault(QLocale(QLocale.Language.Chinese, QLocale.Country.China))
