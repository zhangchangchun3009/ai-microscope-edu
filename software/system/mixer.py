"""RK3576 教学机 ALSA 混音器：固定通路 argv 与音量 Output 映射。"""

from __future__ import annotations

import subprocess
from collections.abc import Callable

DEFAULT_VOLUME_PCT: int = 73

_OUTPUT_MAX = 33


def volume_pct_to_output(pct: int | float) -> int:
    """将 UI 音量百分比映射为 ALSA Output 控件值（0–33）。

    参数:
        pct: 0–100 的音量百分比（可超出范围，会夹紧）。

    返回:
        四舍五入并夹紧后的 Output 数值。
    """
    raw = round(pct * _OUTPUT_MAX / 100)
    return max(0, min(_OUTPUT_MAX, int(raw)))


def _amixer_sset(card: int, control: str, *values: str | int) -> list[str]:
    cmd = ["amixer", "-c", str(card), "sset", control]
    cmd.extend(str(v) for v in values)
    return cmd


def fixed_path_commands(card: int = 0) -> list[list[str]]:
    """固定音频通路 amixer 命令（不含 Output 音量）。

    参数:
        card: ALSA 声卡索引，默认 0。

    返回:
        每条命令一个 argv 列表，顺序与 README 手测一致。
    """
    return [
        _amixer_sset(card, "Speaker", "on"),
        _amixer_sset(card, "spk switch", "on"),
        _amixer_sset(card, "Differential Mux", "Line 2"),
        _amixer_sset(card, "Left Channel", 8),
        _amixer_sset(card, "Right Channel", 8),
        _amixer_sset(card, "PCM", "100%"),
    ]


def volume_commands(output: int, card: int = 0) -> list[list[str]]:
    """设置 Output 1/2 音量的 amixer 命令。

    参数:
        output: ALSA Output 控件值（通常 0–33）。
        card: ALSA 声卡索引，默认 0。

    返回:
        Output 1 与 Output 2 各一条 argv。
    """
    return [
        _amixer_sset(card, "Output 1", output),
        _amixer_sset(card, "Output 2", output),
    ]


def _run_commands(
    commands: list[list[str]],
    *,
    runner: Callable[..., object] | None = None,
) -> None:
    run = runner if runner is not None else subprocess.run
    for cmd in commands:
        try:
            run(cmd, check=False, capture_output=True, timeout=3)
        except OSError:
            pass


def apply_fixed_path(*, runner: Callable[..., object] | None = None) -> None:
    """在设备上写入固定混音器通路。

    参数:
        runner: 可注入的子进程调用（默认 subprocess.run）。

    副作用:
        对每条 fixed_path_commands 执行 amixer；缺 amixer 时吞掉 OSError。
    """
    _run_commands(fixed_path_commands(), runner=runner)


def apply_volume(pct: int, *, runner: Callable[..., object] | None = None) -> None:
    """按 UI 音量百分比写入 Output 1/2。

    参数:
        pct: 0–100 音量百分比。
        runner: 可注入的子进程调用（默认 subprocess.run）。

    副作用:
        对每条 volume_commands 执行 amixer；缺 amixer 时吞掉 OSError。
    """
    output = volume_pct_to_output(pct)
    _run_commands(volume_commands(output), runner=runner)
