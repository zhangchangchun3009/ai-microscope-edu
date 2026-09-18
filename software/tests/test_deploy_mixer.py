"""启动混音器脚本、systemd unit、README 与 yaml 样例。"""

from __future__ import annotations

import sys
from pathlib import Path

_SOFTWARE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_SOFTWARE))


def test_edu_app_service_mixer_im_and_keeps_linuxfb() -> None:
    """ExecStartPost 跑固定通路；拼音 IM / 中文 locale；保留 linuxfb 与模型路径。"""
    text = (_SOFTWARE / "deploy" / "edu-app.service").read_text(encoding="utf-8")
    assert (
        "ExecStartPost=/home/cat/ai-microscope-edu/software/deploy/edu-mixer.sh"
        in text
    )
    assert "Environment=QT_IM_MODULE=qtvirtualkeyboard" in text
    assert "Environment=QT_VIRTUALKEYBOARD_DESKTOP_DISABLE=1" in text
    assert "Environment=QT_QUICK_BACKEND=software" in text
    assert "LD_LIBRARY_PATH=" in text and "PySide6/Qt/lib" in text
    assert "Environment=LANG=zh_CN.UTF-8" in text
    assert "Environment=QT_VIRTUALKEYBOARD_AVAILABLE_LOCALES=zh_CN,zh_TW,en_US" in text
    assert "QT_QPA_PLATFORM=linuxfb:fb=/dev/fb0" in text
    assert "EDU_SENSEVOICE_DEMO=" in text
    assert "EDU_TTS_MODEL_DIR=" in text
    assert "SupplementaryGroups=video render input audio" in text


def test_requirements_pins_addons_with_essentials() -> None:
    """VirtualKeyboard 在 Addons；与 Essentials 钉同一 6.8.0.2，避开 glibc 2.39。"""
    text = (_SOFTWARE / "requirements.txt").read_text(encoding="utf-8")
    assert "PySide6-Essentials==6.8.0.2" in text
    assert "PySide6-Addons==6.8.0.2" in text


def test_readme_points_to_yaml_not_hand_amixer() -> None:
    """配置走 var/edu.yaml；重启后不要手跑 amixer；211 装 venv 与拼音。"""
    text = (_SOFTWARE / "README.md").read_text(encoding="utf-8")
    assert "必须在 `restart` **之后**再跑 `amixer`" not in text
    assert "var/edu.yaml" in text
    assert "edu.yaml.example" in text
    assert "enc1:" in text
    assert "pip install -r requirements.txt" in text
    assert "PySide6-Addons" in text
    assert "不要" in text and "Debian Qt 6.4" in text
    assert "洋葱" in text
    assert "llm.json.example" in text  # 可留，须标明废弃
    assert "废弃" in text or "已废弃" in text


def test_readme_hand_test_covers_spec_12() -> None:
    """手测清单覆盖设置规格 §12。"""
    text = (_SOFTWARE / "README.md").read_text(encoding="utf-8")
    assert "90°" in text
    assert "不必手跑 amixer" in text or "不手跑 amixer" in text
    assert "enc1:" in text
    assert "拼音" in text
    assert "USER.md" in text


def test_edu_yaml_example_exists_with_defaults() -> None:
    """样例带缺省 90/73/字幕关，密钥只写 enc1: 占位。"""
    text = (_SOFTWARE / "deploy" / "edu.yaml.example").read_text(encoding="utf-8")
    assert "rotation_deg: 90" in text
    assert "volume_pct: 73" in text
    assert "captions_enabled: false" in text
    assert "enc1:" in text
    assert "sk-" not in text
