"""语音包公开接口回归测试。"""

from __future__ import annotations

import sys
from pathlib import Path

_SOFTWARE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_SOFTWARE))


def test_voice_package_exports_session_and_audio_factory() -> None:
    """voice 包应直接导出主窗所需的两个接口。"""
    from voice import VoiceSession, build_audio_io

    assert VoiceSession.__name__ == "VoiceSession"
    assert callable(build_audio_io)
