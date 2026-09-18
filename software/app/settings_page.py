"""设置右栏：分组首页 + USER.md / LLM 子页栈。"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QButtonGroup,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSlider,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from app.settings_llm import LlmSettingsPage
from app.settings_prompt import PromptSettingsPage
from app.theme import SETTINGS_CTRL_H
from system.display import normalize_rotation
from system.edu_config import EduSettings

_ROTATION_DEGS = (0, 90, 180, 270)
_PAGE_HOME = 0
_PAGE_PROMPT = 1
_PAGE_LLM = 2
_SAVE_FAIL = "无法保存设置，请重试。"


def captions_toggle_text(enabled: bool) -> str:
    """字幕开关按钮上的文字：开或关。

    参数:
        enabled: 当前是否打开字幕。

    返回:
        ``开`` 或 ``关``。
    """
    return "开" if enabled else "关"


def should_commit_volume(
    *,
    slider_down: bool,
    from_release: bool,
    value: int,
    committed: int,
) -> bool:
    """判断这次滑条事件是否应写出 ``volume_pct``。

    参数:
        slider_down: 手柄是否按住（``QSlider.isSliderDown()``）。
        from_release: 是否来自 ``sliderReleased``。
        value: 当前滑条百分比。
        committed: 上次已提交的百分比。

    返回:
        应调用 ``on_change(volume_pct=...)`` 时为 True。拖动中的
        ``valueChanged`` 为 False；点槽位等非拖动改值、以及松手为 True。
        ``value == committed`` 时一律 False，避免拖动结束重复写。

    副作用:
        无。
    """
    if int(value) == int(committed):
        return False
    if from_release:
        return True
    return not slider_down


class SettingsPage(QWidget):
    """设置分屏右栏：显示 / 语音与问答，含子页编辑器。"""

    def __init__(
        self,
        on_close: Callable[[], None],
        settings: EduSettings,
        on_change: Callable[..., bool] | Callable[..., None],
        parent: QWidget | None = None,
        *,
        user_md_path: Path | None = None,
        edu_path: Path | None = None,
        reload_llm: Callable[[], None] | None = None,
        environ: Mapping[str, str] | None = None,
        serial: str | None = None,
    ) -> None:
        """组装设置页壳并绑定当前设置。

        参数:
            on_close: 页头「关闭」时退出分屏。
            settings: 当前内存设置；本页会就地改对应字段。
            on_change: 字段变化回调，关键字为 ``rotation_deg`` /
                ``captions_enabled`` / ``volume_pct``。可返回 ``False`` 表示
                写盘失败；``None`` 与其它真值都当成功。音量在松手或非拖动
                改值时触发，拖动预览只改百分比文案。
            parent: 父控件。
            user_md_path: 自定义问答助手文件；缺省 ``var/qa/USER.md``。
            edu_path: ``edu.yaml``；缺省软件 var 路径。
            reload_llm: 保存 LLM 段后刷新运行中的问答配置。
            environ: 覆盖 LLM 环境变量；缺省进程环境。
            serial: 密钥加解密序列号；缺省读本机。

        返回:
            无。

        副作用:
            构建控件树。用户改动先经 ``on_change`` 写盘，成功后才改
            ``settings``；失败则页内提示并回滚首页控件。
        """
        super().__init__(parent)
        self.setObjectName("settingsPage")
        # QWidget 子类默认不绘 QSS background，与 CaptionBar 同一问题。
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self._settings = settings
        self._on_change = on_change
        self._stack = QStackedWidget(self)
        self._stack.addWidget(self._build_home(on_close))
        self._stack.addWidget(
            PromptSettingsPage(self._go_home, path=user_md_path, parent=self)
        )
        self._stack.addWidget(
            LlmSettingsPage(
                self._go_home,
                edu_path=edu_path,
                reload_llm=reload_llm,
                environ=environ,
                serial=serial,
                parent=self,
            )
        )
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        root.addWidget(self._stack)

    def _build_home(self, on_close: Callable[[], None]) -> QWidget:
        """首页：页头 +「显示」+「语音与问答」。"""
        home = QWidget(self)
        layout = QVBoxLayout(home)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(12)
        layout.addLayout(self._header("设置", "关闭", on_close))
        self._save_error = QLabel("")
        self._save_error.setObjectName("settingsError")
        self._save_error.setWordWrap(True)
        self._save_error.hide()
        layout.addWidget(self._save_error)
        layout.addWidget(self._group_label("显示"))
        layout.addWidget(self._captions_row())
        layout.addWidget(self._rotation_row())
        layout.addWidget(self._group_label("语音与问答"))
        layout.addWidget(self._volume_row())
        layout.addWidget(
            self._nav_button("自定义问答助手", lambda: self._stack.setCurrentIndex(_PAGE_PROMPT))
        )
        layout.addWidget(self._nav_button("大模型", lambda: self._stack.setCurrentIndex(_PAGE_LLM)))
        return home

    def _header(
        self,
        title: str,
        action: str,
        on_action: Callable[[], None],
    ) -> QHBoxLayout:
        """页头标题与触控按钮（关闭或返回）。"""
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

    def _group_label(self, text: str) -> QLabel:
        """分组标题。"""
        label = QLabel(text)
        label.setObjectName("settingsGroup")
        return label

    def _captions_row(self) -> QWidget:
        """字幕开/关按钮，高度与方向钮相同。"""
        wrap = QWidget(self)
        row = QHBoxLayout(wrap)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(12)
        caption = QLabel("字幕")
        caption.setObjectName("settingsGroup")
        btn = QPushButton(captions_toggle_text(bool(self._settings.captions_enabled)))
        btn.setObjectName("settingsCtrl")
        btn.setCheckable(True)
        btn.setFixedHeight(SETTINGS_CTRL_H)
        btn.setChecked(bool(self._settings.captions_enabled))
        btn.toggled.connect(self._on_captions)
        self._captions = btn
        row.addWidget(caption, 0)
        row.addWidget(btn, 1)
        return wrap

    def _rotation_row(self) -> QWidget:
        """四个互斥方向钮：0° / 90° / 180° / 270°。"""
        wrap = QWidget(self)
        row = QHBoxLayout(wrap)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(8)
        self._rot_group = QButtonGroup(wrap)
        self._rot_group.setExclusive(True)
        self._rot_buttons: dict[int, QPushButton] = {}
        current = normalize_rotation(self._settings.rotation_deg)
        for deg in _ROTATION_DEGS:
            btn = QPushButton(f"{deg}°")
            btn.setObjectName("settingsCtrl")
            btn.setCheckable(True)
            btn.setFixedHeight(SETTINGS_CTRL_H)
            btn.setChecked(deg == current)
            self._rot_group.addButton(btn, deg)
            self._rot_buttons[deg] = btn
            row.addWidget(btn, 1)
        self._rot_group.idClicked.connect(self._on_rotation)
        return wrap

    def _volume_row(self) -> QWidget:
        """音量滑条 0–100；松手或点槽位写出，拖动中只改文案。"""
        wrap = QWidget(self)
        row = QHBoxLayout(wrap)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(12)
        caption = QLabel("音量")
        caption.setObjectName("settingsGroup")
        slider = QSlider(Qt.Orientation.Horizontal)
        slider.setObjectName("settingsVolume")
        slider.setRange(0, 100)
        slider.setValue(int(self._settings.volume_pct))
        slider.setMinimumHeight(SETTINGS_CTRL_H)
        slider.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        value = QLabel(f"{int(self._settings.volume_pct)}%")
        value.setMinimumWidth(56)
        value.setAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignRight)
        slider.valueChanged.connect(self._on_volume_preview)
        slider.sliderReleased.connect(self._on_volume_released)
        self._volume = slider
        self._volume_value = value
        row.addWidget(caption, 0)
        row.addWidget(slider, 1)
        row.addWidget(value, 0)
        return wrap

    def _nav_button(self, title: str, on_click: Callable[[], None]) -> QPushButton:
        """进入提示词 / LLM 子页的整行按钮。"""
        btn = QPushButton(title)
        btn.setObjectName("settingsNav")
        btn.setMinimumHeight(SETTINGS_CTRL_H)
        btn.clicked.connect(on_click)
        return btn

    def _go_home(self) -> None:
        """子页「返回」只退回设置首页，不关分屏。"""
        self._stack.setCurrentIndex(_PAGE_HOME)

    def _emit(self, **fields: Any) -> None:
        """先让外壳写盘；成功才改内存设置。失败则页内报错并回滚控件。

        参数:
            **fields: 要提交的顶层字段。

        返回:
            无。

        副作用:
            调用 ``on_change``（应先 ``patch_edu``）。返回 False 或抛
            ``OSError`` 时不 ``setattr``，并把对应控件恢复为提交前的值。
        """
        previous = {key: getattr(self._settings, key) for key in fields}
        try:
            ok = self._on_change(**fields)
        except OSError:
            ok = False
        if ok is False:
            self._show_save_error()
            self._restore_widgets(previous)
            return
        self._save_error.hide()
        self._save_error.clear()
        for key, value in fields.items():
            setattr(self._settings, key, value)

    def _show_save_error(self) -> None:
        """在首页显示写盘失败提示（非模态）。"""
        self._save_error.setText(_SAVE_FAIL)
        self._save_error.show()

    def _restore_widgets(self, previous: Mapping[str, Any]) -> None:
        """把已改动的首页控件恢复为 ``previous`` 中的旧值，避免信号重入。"""
        if "captions_enabled" in previous:
            self._captions.blockSignals(True)
            self._captions.setChecked(bool(previous["captions_enabled"]))
            self._captions.setText(captions_toggle_text(bool(previous["captions_enabled"])))
            self._captions.blockSignals(False)
        if "rotation_deg" in previous:
            deg = int(previous["rotation_deg"])
            btn = self._rot_buttons.get(deg)
            if btn is not None:
                self._rot_group.blockSignals(True)
                btn.setChecked(True)
                self._rot_group.blockSignals(False)
        if "volume_pct" in previous:
            pct = int(previous["volume_pct"])
            self._volume.blockSignals(True)
            self._volume.setValue(pct)
            self._volume.blockSignals(False)
            self._volume_value.setText(f"{pct}%")

    def _on_captions(self, checked: bool) -> None:
        """字幕开关变化。"""
        self._captions.setText(captions_toggle_text(bool(checked)))
        self._emit(captions_enabled=bool(checked))

    def _on_rotation(self, deg: int) -> None:
        """互斥方向钮被点选；yaml 由外壳写入，RotateHost 经 on_settings_patch 立刻转。"""
        self._emit(rotation_deg=int(deg))

    def _on_volume_preview(self, value: int) -> None:
        """更新百分比文案；非拖动改值时提交。"""
        pct = int(value)
        self._volume_value.setText(f"{pct}%")
        self._maybe_commit_volume(
            value=pct,
            slider_down=bool(self._volume.isSliderDown()),
            from_release=False,
        )

    def _on_volume_released(self) -> None:
        """拖动松手后提交当前值（若尚未因点槽位写过）。"""
        self._maybe_commit_volume(
            value=int(self._volume.value()),
            slider_down=False,
            from_release=True,
        )

    def _maybe_commit_volume(
        self,
        *,
        value: int,
        slider_down: bool,
        from_release: bool,
    ) -> None:
        """按 :func:`should_commit_volume` 决定是否写出音量。"""
        if not should_commit_volume(
            slider_down=slider_down,
            from_release=from_release,
            value=value,
            committed=int(self._settings.volume_pct),
        ):
            return
        self._emit(volume_pct=int(value))
