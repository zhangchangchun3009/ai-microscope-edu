"""ALSA 混音器 argv 与音量百分比映射。"""

from __future__ import annotations

import os
import shlex
import stat
import sys
from pathlib import Path

_SOFTWARE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_SOFTWARE))

from system.mixer import (  # noqa: E402
    DEFAULT_VOLUME_PCT,
    apply_fixed_path,
    apply_volume,
    fixed_path_commands,
    volume_pct_to_output,
)


def test_volume_map() -> None:
    assert volume_pct_to_output(0) == 0
    assert volume_pct_to_output(73) == 24
    assert volume_pct_to_output(100) == 33
    assert volume_pct_to_output(200) == 33


def test_default_volume_pct() -> None:
    assert DEFAULT_VOLUME_PCT == 73
    assert volume_pct_to_output(DEFAULT_VOLUME_PCT) == 24


def test_fixed_path_contains_line2_and_pga() -> None:
    cmds = [" ".join(c) for c in fixed_path_commands()]
    joined = "\n".join(cmds)
    assert "Speaker" in joined and "on" in joined
    assert "Differential Mux" in joined and "Line 2" in joined
    assert "Left Channel" in joined and " 8" in joined
    assert "PCM" in joined
    assert "Output 1" not in joined and "Output 2" not in joined


def test_apply_volume_calls_output_1_and_2() -> None:
    ran: list[list[str]] = []
    apply_volume(73, runner=lambda args, **k: ran.append(list(args)))
    flat = " ".join(" ".join(a) for a in ran)
    assert "Output 1" in flat and "Output 2" in flat and "24" in flat


def test_apply_fixed_path_swallows_oserror() -> None:
    def boom(*args, **kwargs):
        raise OSError("no amixer")

    apply_fixed_path(runner=boom)


def test_apply_volume_swallows_oserror() -> None:
    def boom(*args, **kwargs):
        raise OSError("no amixer")

    apply_volume(50, runner=boom)


def test_edu_mixer_sh_matches_fixed_path_and_is_executable() -> None:
    """启动脚本与 fixed_path_commands 同一组 amixer，不含 Output 音量。"""
    path = _SOFTWARE / "deploy" / "edu-mixer.sh"
    text = path.read_text(encoding="utf-8")
    lines = [
        shlex.split(raw)
        for raw in text.splitlines()
        if raw.strip().startswith("amixer")
    ]
    expected = fixed_path_commands()
    assert lines == expected
    joined = "\n".join(" ".join(c) for c in lines)
    assert "Output 1" not in joined and "Output 2" not in joined
    mode = path.stat().st_mode
    assert mode & stat.S_IXUSR
    assert os.access(path, os.X_OK)
