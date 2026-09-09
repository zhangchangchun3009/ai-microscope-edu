"""211 板端探测：无桌面环境下 PySide6 能否独占 MIPI 全屏。

这不是教学应用。不接相机、不接配网。失败时看 journalctl -u edu-kiosk-probe。
平台插件由环境变量 QT_QPA_PLATFORM 选择（无桌面时默认 linuxfb）。
"""

from __future__ import annotations

import sys

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QLabel, QVBoxLayout, QWidget

from app.platform import ensure_embedded_platform


def build_window() -> QWidget:
    """构造全屏探测窗：深蓝底 + 白字，确认 Qt 已拿到屏。"""
    win = QWidget()
    win.setObjectName("kioskProbe")
    win.setWindowTitle("edu-kiosk-probe")
    win.setStyleSheet("QWidget#kioskProbe { background: #1a4a7a; }")
    layout = QVBoxLayout(win)
    label = QLabel("PySide6 kiosk 探测\n无桌面全屏 — 211")
    label.setAlignment(Qt.AlignmentFlag.AlignCenter)
    label.setStyleSheet("color: white; font-size: 42px;")
    layout.addWidget(label)
    return win


def main(argv: list[str] | None = None) -> int:
    """启动全屏 Qt 应用，直到进程被 systemd/SSH 停掉。"""
    ensure_embedded_platform()
    app = QApplication(argv if argv is not None else sys.argv)
    win = build_window()
    win.showFullScreen()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
