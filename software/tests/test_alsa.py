"""ALSA 子进程适配器的无设备单元测试。"""

from __future__ import annotations

import io
import subprocess
import sys
import threading
from pathlib import Path

_SOFTWARE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_SOFTWARE))

from voice.alsa import AlsaCapture, AlsaPlayback, build_audio_io
from voice.config import (
    ALSA_CAPTURE_DEVICE,
    ALSA_PLAYBACK_DEVICE,
    CHANNELS,
    PLAYBACK_CHANNELS,
    SAMPLE_RATE,
)
from voice.wavutil import upmix_mono_to_stereo


class _CaptureProcess:
    """提供固定 stdout 的 arecord 子进程测试替身。"""

    def __init__(self, pcm: bytes) -> None:
        self.stdout = io.BytesIO(pcm)
        self.stderr = io.BytesIO()
        self.killed = False
        self.terminated = False

    def terminate(self) -> None:
        """记录 terminate 调用。"""
        self.terminated = True

    def kill(self) -> None:
        """记录 kill 调用。"""
        self.killed = True

    def wait(self, timeout: float | None = None) -> int:
        """模拟子进程立即退出。"""
        return 0

    def poll(self) -> int | None:
        """模拟仍在运行的子进程。"""
        return None


def test_capture_uses_configured_arecord_argv_and_accumulates_pcm(monkeypatch) -> None:
    pcm = b"\x01\x02\x03\x04"
    process = _CaptureProcess(pcm)
    stdout_drained = threading.Event()
    original_read = process.stdout.read

    def _read(size: int = -1) -> bytes:
        chunk = original_read(size)
        if not chunk:
            stdout_drained.set()
        return chunk

    process.stdout.read = _read  # type: ignore[method-assign]
    popen_calls: list[tuple[list[str], dict[str, object]]] = []

    def _popen(argv: list[str], **kwargs: object) -> _CaptureProcess:
        popen_calls.append((argv, kwargs))
        return process

    monkeypatch.setattr("voice.alsa.subprocess.Popen", _popen)

    capture = AlsaCapture()
    assert capture.start() is True
    assert stdout_drained.wait(timeout=1.0)
    assert capture.bytes_captured() == len(pcm)
    assert capture.stop() == pcm
    assert popen_calls[0][0] == [
        "arecord",
        "-q",
        "-D",
        ALSA_CAPTURE_DEVICE,
        "-f",
        "S16_LE",
        "-r",
        str(SAMPLE_RATE),
        "-c",
        str(CHANNELS),
        "-t",
        "raw",
    ]


def test_playback_upmixes_mono_and_uses_stereo_aplay(monkeypatch) -> None:
    pcm = b"\0" * (SAMPLE_RATE * 2 * 10)
    run_calls: list[tuple[list[str], dict[str, object]]] = []

    def _run(argv: list[str], **kwargs: object) -> subprocess.CompletedProcess[bytes]:
        run_calls.append((argv, kwargs))
        return subprocess.CompletedProcess(argv, 0, b"", b"")

    monkeypatch.setattr("voice.alsa.subprocess.run", _run)

    assert AlsaPlayback().play_pcm(pcm) is True
    argv, kwargs = run_calls[0]
    assert argv == [
        "aplay",
        "-q",
        "-D",
        ALSA_PLAYBACK_DEVICE,
        "-f",
        "S16_LE",
        "-r",
        str(SAMPLE_RATE),
        "-c",
        str(PLAYBACK_CHANNELS),
        "-t",
        "raw",
    ]
    assert kwargs["input"] == upmix_mono_to_stereo(pcm)
    assert kwargs["timeout"] == max(20.0, 10.0 + 12.0)


def test_playback_overrides_aplay_rate_and_keeps_stereo_upmix(monkeypatch) -> None:
    """TTS 一句是 22050；覆盖 -r 后仍须左右复制，超时按覆盖采样率计。"""
    tts_rate = 22050
    pcm = b"\0" * (tts_rate * 2 * 10)
    run_calls: list[tuple[list[str], dict[str, object]]] = []

    def _run(argv: list[str], **kwargs: object) -> subprocess.CompletedProcess[bytes]:
        run_calls.append((argv, kwargs))
        return subprocess.CompletedProcess(argv, 0, b"", b"")

    monkeypatch.setattr("voice.alsa.subprocess.run", _run)

    assert AlsaPlayback().play_pcm(pcm, sample_rate=tts_rate) is True
    argv, kwargs = run_calls[0]
    assert argv[argv.index("-r") + 1] == "22050"
    assert argv[argv.index("-c") + 1] == str(PLAYBACK_CHANNELS)
    assert kwargs["input"] == upmix_mono_to_stereo(pcm)
    assert kwargs["timeout"] == max(20.0, 10.0 + 12.0)


def test_build_audio_io_uses_alsa_when_both_tools_exist(monkeypatch) -> None:
    monkeypatch.setattr("voice.alsa.shutil.which", lambda name: f"/usr/bin/{name}")

    capture, playback = build_audio_io()

    assert isinstance(capture, AlsaCapture)
    assert isinstance(playback, AlsaPlayback)


def test_capture_stop_swallows_timeout_after_kill(monkeypatch) -> None:
    class _HungProcess(_CaptureProcess):
        def wait(self, timeout: float | None = None) -> int:
            raise subprocess.TimeoutExpired("arecord", timeout)

    process = _HungProcess(b"")
    monkeypatch.setattr("voice.alsa.subprocess.Popen", lambda *_args, **_kwargs: process)
    capture = AlsaCapture()
    assert capture.start() is True

    assert capture.stop() == b""
    assert process.terminated is True
    assert process.killed is True


def test_capture_logs_stderr_when_arecord_dies_immediately(monkeypatch, caplog) -> None:
    class _DeadProcess(_CaptureProcess):
        def __init__(self) -> None:
            super().__init__(b"")
            self.stderr = io.BytesIO(b"arecord: audio open error: Device or resource busy\n")

        def poll(self) -> int | None:
            return 1

    process = _DeadProcess()
    monkeypatch.setattr("voice.alsa.subprocess.Popen", lambda *_args, **_kwargs: process)

    capture = AlsaCapture()

    assert capture.start() is False
    assert "Device or resource busy" in caplog.text
