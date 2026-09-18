"""从 devicetree 或 cpuinfo 读取 CPU 序列号。"""

from __future__ import annotations

from pathlib import Path

_DT_SERIAL = Path("/sys/firmware/devicetree/base/serial-number")
_CPUINFO = Path("/proc/cpuinfo")


def read_cpu_serial(*, cpuinfo: str | None = None, dt_serial: str | None = None) -> str:
    """返回本机 CPU 序列号的小写 hex 字符串。

    参数:
        cpuinfo: 可选，注入的 /proc/cpuinfo 全文；省略时在运行时读取。
        dt_serial: 可选，注入的 devicetree serial-number；非空时优先于 cpuinfo。

    返回:
        小写 hex 序列号；均不可得时为 ``macos-dev``（开发机回退）。

    副作用:
        参数均省略时会尝试读取 ``/sys/firmware/devicetree/base/serial-number``
        与 ``/proc/cpuinfo``。
    """
    if dt_serial is not None and dt_serial.strip():
        return dt_serial.strip().lower()

    # 注入了 cpuinfo（含空串）时不读运行时文件，保持单测可隔离。
    if cpuinfo is not None:
        serial = _serial_from_cpuinfo(cpuinfo)
        return serial if serial else "macos-dev"

    # 运行时：设备树原文（去 NUL 后非空即小写返回），不得当 cpuinfo 再解析。
    raw_dt = _read_dt_serial()
    if raw_dt:
        return raw_dt.strip().lower()

    serial = _serial_from_cpuinfo(_read_cpuinfo_file() or "")
    return serial if serial else "macos-dev"


def _read_dt_serial() -> str | None:
    try:
        raw = _DT_SERIAL.read_bytes()
    except OSError:
        return None
    s = raw.decode("utf-8", errors="replace").strip("\x00").strip()
    return s if s else None


def _read_cpuinfo_file() -> str | None:
    try:
        return _CPUINFO.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None


def _serial_from_cpuinfo(cpuinfo: str) -> str | None:
    for line in cpuinfo.splitlines():
        stripped = line.strip()
        if not stripped.lower().startswith("serial"):
            continue
        if ":" not in line:
            continue
        _, _, value = line.partition(":")
        hex_part = value.strip()
        if hex_part:
            return hex_part.lower()
    return None
