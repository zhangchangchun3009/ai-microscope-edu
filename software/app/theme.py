"""教学 kiosk 深色仪器风：石墨底 + 光学青绿点缀。"""

from __future__ import annotations

from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import QApplication, QStyleFactory

# 预览区接近光学台面；工具条略亮，避免和黑场标本抢对比。
BG = "#0b1016"
STRIP_BG = "#121922"
PANEL_BG = "#151c24"
SURFACE = "#1c2630"
LINE = "#2c3948"
TEXT = "#e7eef6"
MUTED = "#8d9aab"
ACCENT = "#3ee0c0"
ACCENT_DIM = "#1f6f63"
DANGER = "#ff6b7a"


def apply_theme(app: QApplication) -> None:
    """给整个进程套 Fusion 深色调色板和全局 QSS。

    参数：
        app: 已创建的 QApplication。

    副作用：
        改应用 style、palette、stylesheet。
    """
    app.setStyle(QStyleFactory.create("Fusion"))
    pal = QPalette()
    pal.setColor(QPalette.ColorRole.Window, QColor(BG))
    pal.setColor(QPalette.ColorRole.WindowText, QColor(TEXT))
    pal.setColor(QPalette.ColorRole.Base, QColor(PANEL_BG))
    pal.setColor(QPalette.ColorRole.AlternateBase, QColor(SURFACE))
    pal.setColor(QPalette.ColorRole.Text, QColor(TEXT))
    pal.setColor(QPalette.ColorRole.Button, QColor(SURFACE))
    pal.setColor(QPalette.ColorRole.ButtonText, QColor(TEXT))
    pal.setColor(QPalette.ColorRole.Highlight, QColor(ACCENT_DIM))
    pal.setColor(QPalette.ColorRole.HighlightedText, QColor(TEXT))
    pal.setColor(QPalette.ColorRole.PlaceholderText, QColor(MUTED))
    app.setPalette(pal)
    app.setStyleSheet(
        f"""
        QWidget {{
            color: {TEXT};
            font-family: "Noto Sans CJK SC", "Source Han Sans SC",
                         "PingFang SC", "Microsoft YaHei", sans-serif;
        }}
        QWidget#eduMain {{ background: {BG}; }}
        QWidget#previewPane {{ background: #07090c; }}
        QWidget#toolStrip {{
            background: {STRIP_BG};
            border-left: 1px solid {LINE};
        }}
        QWidget#stubPage {{ background: {PANEL_BG}; }}
        QLabel#stubTitle {{
            color: {TEXT};
            font-size: 22px;
            font-weight: 600;
            letter-spacing: 1px;
        }}
        QLabel#previewHint {{
            color: {MUTED};
            font-size: 28px;
            letter-spacing: 2px;
        }}
        QSplitter::handle:horizontal {{
            background: {LINE};
            width: 8px;
        }}
        QSplitter::handle:horizontal:hover {{
            background: {ACCENT};
        }}
        QPushButton#ghostBtn {{
            background: {SURFACE};
            color: {TEXT};
            border: 1px solid {LINE};
            border-radius: 22px;
            font-size: 18px;
            padding: 10px 22px;
        }}
        QPushButton#ghostBtn:pressed {{
            background: {ACCENT_DIM};
            border-color: {ACCENT};
        }}
        """
    )
