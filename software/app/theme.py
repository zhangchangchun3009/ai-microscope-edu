"""教学 kiosk 深色仪器风：石墨底 + 光学青绿点缀。"""

from __future__ import annotations

from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import QApplication, QStyleFactory

from app.shell_state import SPLIT_HANDLE_PX

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
# 设置页触控行高：spec ≥44 px；验证屏偏小，本刀用 56。不改工具条圆钮直径。
SETTINGS_CTRL_H = 56


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
        QWidget#stubPage, QWidget#settingsPage, QWidget#historyPage {{
            background: {PANEL_BG};
        }}
        QLabel#stubTitle, QLabel#settingsTitle, QLabel#historyTitle {{
            color: {TEXT};
            font-size: 22px;
            font-weight: 600;
            letter-spacing: 1px;
        }}
        QLabel#settingsGroup {{
            color: {MUTED};
            font-size: 16px;
            font-weight: 600;
            letter-spacing: 1px;
            padding-top: 8px;
        }}
        QLabel#previewHint {{
            color: {MUTED};
            font-size: 28px;
            letter-spacing: 2px;
        }}
        QWidget#captionBar {{
            background: rgba(11, 16, 22, 200);
            border-radius: 12px;
        }}
        QLabel#captionText {{
            color: {TEXT};
            font-size: 22px;
        }}
        QLabel#settingsBanner {{
            color: {ACCENT};
            font-size: 16px;
        }}
        QLabel#settingsError, QLabel#historyStatus {{
            color: {DANGER};
            font-size: 16px;
        }}
        QWidget#historyPage QListWidget {{
            background: {SURFACE};
            border: 1px solid {LINE};
            border-radius: 12px;
            font-size: 18px;
            outline: none;
        }}
        QWidget#historyPage QListWidget::item {{
            min-height: {SETTINGS_CTRL_H}px;
            padding: 8px 12px;
        }}
        QWidget#historyPage QListWidget::item:selected {{
            background: {ACCENT_DIM};
        }}
        QTextEdit#historyBody {{
            background: {PANEL_BG};
            color: {TEXT};
            border: 1px solid {LINE};
            border-radius: 12px;
            font-size: 22px;
            padding: 8px 12px;
        }}
        QWidget#settingsPage QLineEdit,
        QWidget#settingsPage QTextEdit,
        QWidget#settingsPage QSpinBox {{
            background: {SURFACE};
            color: {TEXT};
            border: 1px solid {LINE};
            border-radius: 12px;
            font-size: 18px;
            padding: 8px 12px;
            min-height: {SETTINGS_CTRL_H}px;
        }}
        QSplitter::handle:horizontal {{
            background: {LINE};
            width: {SPLIT_HANDLE_PX}px;
        }}
        QSplitter::handle:horizontal:hover {{
            background: {ACCENT};
        }}
        QPushButton#ghostBtn, QPushButton#settingsCtrl, QPushButton#settingsNav,
        QPushButton#secretRevealBtn {{
            background: {SURFACE};
            color: {TEXT};
            border: 1px solid {LINE};
            border-radius: 22px;
            font-size: 18px;
            padding: 10px 22px;
        }}
        QPushButton#secretRevealBtn {{
            border-radius: 12px;
            padding: 8px 10px;
            font-size: 16px;
        }}
        QPushButton#ghostBtn:pressed, QPushButton#settingsCtrl:pressed,
        QPushButton#settingsNav:pressed, QPushButton#secretRevealBtn:pressed {{
            background: {ACCENT_DIM};
            border-color: {ACCENT};
        }}
        QPushButton#settingsCtrl:checked, QPushButton#secretRevealBtn:checked {{
            background: {ACCENT_DIM};
            border-color: {ACCENT};
            color: {TEXT};
        }}
        QWidget#settingsPage QPushButton#ghostBtn,
        QPushButton#settingsCtrl, QPushButton#settingsNav {{
            min-height: {SETTINGS_CTRL_H}px;
        }}
        QScrollArea#rightPaneScroll QScrollBar:vertical {{
            width: 28px;
            background: {SURFACE};
            margin: 0;
        }}
        QScrollArea#rightPaneScroll QScrollBar::handle:vertical {{
            background: {MUTED};
            min-height: 48px;
            border-radius: 6px;
        }}
        QScrollArea#rightPaneScroll QScrollBar::add-line:vertical,
        QScrollArea#rightPaneScroll QScrollBar::sub-line:vertical {{
            height: 0;
        }}
        QSlider#settingsVolume {{
            min-height: {SETTINGS_CTRL_H}px;
        }}
        QSlider#settingsVolume::groove:horizontal {{
            height: 10px;
            background: {LINE};
            border-radius: 5px;
        }}
        QSlider#settingsVolume::handle:horizontal {{
            width: 32px;
            height: {SETTINGS_CTRL_H}px;
            margin: -23px 0;
            background: {ACCENT};
            border-radius: 16px;
        }}
        QSlider#settingsVolume::sub-page:horizontal {{
            background: {ACCENT_DIM};
            border-radius: 5px;
        }}
        """
    )
