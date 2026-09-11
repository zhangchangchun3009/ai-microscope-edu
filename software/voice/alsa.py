"""音频采集/播放接口及无需 ALSA 设备的测试替身。"""

from __future__ import annotations

import logging
import shutil
import subprocess
import threading
from typing import Protocol

from voice.config import (
    ALSA_CAPTURE_DEVICE,
    ALSA_PLAYBACK_DEVICE,
    CHANNELS,
    PLAYBACK_CHANNELS,
    SAMPLE_RATE,
)
from voice.wavutil import upmix_mono_to_stereo

_LOG = logging.getLogger(__name__)
_STDERR_TAIL_BYTES = 4096


class AudioCapture(Protocol):
    """音频采集端口，由会话层控制录音生命周期。"""

    def start(self) -> bool:
        """开始采集。

        返回:
            成功启动返回 True，否则返回 False。

        副作用:
            具体实现可启动录音设备或后台采集进程。
        """
        ...

    def stop(self) -> bytes:
        """停止采集并取得完整 PCM。

        返回:
            本次录音的 16-bit LE PCM 字节。

        副作用:
            具体实现会停止录音设备或后台采集进程。
        """
        ...

    def bytes_captured(self) -> int:
        """取得当前录音已采集的字节数。

        返回:
            当前录音已采集的 PCM 字节数。

        副作用:
            无。
        """
        ...


class AudioPlayback(Protocol):
    """音频播放端口，由会话层提交 PCM。"""

    def play_pcm(self, pcm: bytes, sample_rate: int | None = None) -> bool:
        """同步播放 PCM。

        参数:
            pcm: 待播放的 16-bit LE PCM 字节。
            sample_rate: 覆盖 aplay ``-r``；缺省用构造时的采样率。

        返回:
            播放成功返回 True，否则返回 False。

        副作用:
            具体实现可占用音频输出设备直至播放结束。
        """
        ...


class AlsaCapture:
    """通过 arecord 子进程采集整段 raw S16_LE PCM。

    参数:
        device: ALSA 采集设备名。
        sample_rate: 采样率，单位 Hz。
        channels: 声道数。

    副作用:
        start() 会启动 arecord 和两个后台抽流线程；stop() 会终止它们。
    """

    def __init__(
        self,
        device: str = ALSA_CAPTURE_DEVICE,
        sample_rate: int = SAMPLE_RATE,
        channels: int = CHANNELS,
    ) -> None:
        self._device = device
        self._sample_rate = int(sample_rate)
        self._channels = int(channels)
        self._proc: subprocess.Popen[bytes] | None = None
        self._stdout_thread: threading.Thread | None = None
        self._stderr_thread: threading.Thread | None = None
        self._pcm = bytearray()
        self._pcm_lock = threading.Lock()
        self._stderr_tail = bytearray()
        self._stderr_lock = threading.Lock()

    def start(self) -> bool:
        """启动 arecord 并开始后台累积 PCM。

        返回:
            子进程成功启动返回 True，否则返回 False。

        副作用:
            会先停止尚未结束的采集，清空上次 PCM，再启动后台线程。
        """
        self.stop()
        with self._pcm_lock:
            self._pcm.clear()
        with self._stderr_lock:
            self._stderr_tail.clear()
        cmd = [
            "arecord",
            "-q",
            "-D",
            self._device,
            "-f",
            "S16_LE",
            "-r",
            str(self._sample_rate),
            "-c",
            str(self._channels),
            "-t",
            "raw",
        ]
        try:
            proc = subprocess.Popen(
                cmd,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                bufsize=0,
            )
        except (OSError, subprocess.SubprocessError):
            _LOG.exception("启动 arecord 失败 cmd=%s stderr=%s", cmd, self._stderr_text())
            return False

        self._proc = proc
        self._stdout_thread = threading.Thread(
            target=self._read_stdout,
            args=(proc,),
            name="alsa-capture-stdout",
            daemon=True,
        )
        self._stderr_thread = threading.Thread(
            target=self._drain_stderr,
            args=(proc,),
            name="alsa-capture-stderr",
            daemon=True,
        )
        self._stdout_thread.start()
        self._stderr_thread.start()
        exit_code = proc.poll()
        if exit_code is not None:
            self._stdout_thread.join(timeout=0.2)
            self._stderr_thread.join(timeout=0.2)
            _LOG.error(
                "arecord 启动后立即退出 exit_code=%s stderr=%s",
                exit_code,
                self._stderr_text(),
            )
            self._proc = None
            self._stdout_thread = None
            self._stderr_thread = None
            return False
        return True

    def stop(self) -> bytes:
        """停止 arecord、等待抽流线程结束并返回完整 PCM。

        返回:
            本次采集到的 raw S16_LE PCM 字节。

        副作用:
            终止当前 arecord 子进程并回收后台线程。
        """
        proc = self._proc
        died_code: int | None = None
        if proc is not None:
            try:
                died_code = proc.poll()
                if died_code is None:
                    proc.terminate()
                    proc.wait(timeout=2.0)
            except subprocess.TimeoutExpired:
                proc.kill()
                try:
                    proc.wait(timeout=2.0)
                except subprocess.TimeoutExpired:
                    _LOG.warning("arecord 在 kill 后仍未退出 stderr=%s", self._stderr_text())
            except (OSError, subprocess.SubprocessError):
                _LOG.exception("终止 arecord 失败 stderr=%s", self._stderr_text())

        for thread in (self._stdout_thread, self._stderr_thread):
            if thread is not None:
                thread.join(timeout=3.0)
        if died_code not in (None, 0):
            _LOG.error(
                "arecord 在录音期间异常退出 exit_code=%s stderr=%s",
                died_code,
                self._stderr_text(),
            )
        self._proc = None
        self._stdout_thread = None
        self._stderr_thread = None
        with self._pcm_lock:
            return bytes(self._pcm)

    def bytes_captured(self) -> int:
        """取得当前已读取的 PCM 字节数。

        返回:
            stdout 后台线程已经累积的字节数。

        副作用:
            无。
        """
        with self._pcm_lock:
            return len(self._pcm)

    def _read_stdout(self, proc: subprocess.Popen[bytes]) -> None:
        """持续读取 arecord 标准输出并累积 PCM。"""
        if proc.stdout is None:
            return
        try:
            while True:
                chunk = proc.stdout.read(4096)
                if not chunk:
                    return
                with self._pcm_lock:
                    self._pcm.extend(chunk)
        except (OSError, ValueError):
            _LOG.exception("读取 arecord PCM 失败")

    def _drain_stderr(self, proc: subprocess.Popen[bytes]) -> None:
        """持续抽空 arecord 标准错误，并保留小段尾部用于失败诊断。"""
        if proc.stderr is None:
            return
        try:
            while True:
                chunk = proc.stderr.read(4096)
                if not chunk:
                    return
                with self._stderr_lock:
                    self._stderr_tail.extend(chunk)
                    del self._stderr_tail[:-_STDERR_TAIL_BYTES]
        except (OSError, ValueError):
            _LOG.exception("读取 arecord stderr 失败")

    def _stderr_text(self) -> str:
        """返回最近一小段 arecord 标准错误文本。"""
        with self._stderr_lock:
            return bytes(self._stderr_tail).decode(errors="replace").strip()


class AlsaPlayback:
    """通过 aplay 子进程同步播放 raw S16_LE PCM。

    参数:
        device: ALSA 播放设备名。
        sample_rate: 采样率，单位 Hz。
        channels: 播放声道数；ES8388 必须为 2。传入的 PCM 仍是单声道，
            play_pcm 内会左右复制后再交给 aplay。

    副作用:
        play_pcm() 会独占播放设备，直至播放完成或超时。
    """

    def __init__(
        self,
        device: str = ALSA_PLAYBACK_DEVICE,
        sample_rate: int = SAMPLE_RATE,
        channels: int = PLAYBACK_CHANNELS,
    ) -> None:
        self._device = device
        self._sample_rate = int(sample_rate)
        self._channels = int(channels)

    def play_pcm(self, pcm: bytes, sample_rate: int | None = None) -> bool:
        """同步播放一段 raw S16_LE PCM。

        参数:
            pcm: 待播放的单声道 PCM 字节。
            sample_rate: 覆盖 aplay ``-r`` 与超时估算；缺省 ``self._sample_rate``。
                TTS 一句为 22050，回放原声仍用 44100。

        返回:
            播放成功返回 True；启动失败、超时或退出码非零返回 False。

        副作用:
            启动 aplay 子进程，并将升混后的 pcm 写入其标准输入。
        """
        if not pcm:
            return True
        rate = int(sample_rate or self._sample_rate)
        # 会话层始终给出单声道 PCM；芯片按立体声帧取数，这里升混后再播。
        play_pcm = upmix_mono_to_stereo(pcm) if self._channels == 2 else pcm
        cmd = [
            "aplay",
            "-q",
            "-D",
            self._device,
            "-f",
            "S16_LE",
            "-r",
            str(rate),
            "-c",
            str(self._channels),
            "-t",
            "raw",
        ]
        byte_rate = rate * self._channels * 2
        duration_s = len(play_pcm) / float(byte_rate)
        timeout_sec = max(20.0, duration_s + 12.0)
        try:
            result = subprocess.run(
                cmd,
                input=play_pcm,
                capture_output=True,
                timeout=timeout_sec,
            )
        except subprocess.TimeoutExpired:
            _LOG.error("aplay 超时 len=%s cmd=%s", len(pcm), cmd)
            return False
        except (OSError, subprocess.SubprocessError):
            _LOG.exception("启动 aplay 失败 cmd=%s", cmd)
            return False
        if result.returncode != 0:
            stderr = (result.stderr or b"").decode(errors="replace").strip()
            _LOG.error("aplay 退出码=%s stderr=%s", result.returncode, stderr)
            return False
        return True


class MockCapture:
    """可预测的采集测试替身。

    参数:
        pcm: 调用 stop() 时返回的完整 PCM。
        start_ok: start() 是否成功。

    副作用:
        start() 和 stop() 会更新内部录音状态。
    """

    def __init__(self, pcm: bytes, *, start_ok: bool = True) -> None:
        self.pcm = pcm
        self.start_ok = start_ok
        self.live_bytes = len(pcm)
        self._recording = False

    def start(self) -> bool:
        """按配置模拟开始采集。

        返回:
            构造时传入的 start_ok。

        副作用:
            成功时将替身标记为录音中。
        """
        self._recording = self.start_ok
        return self.start_ok

    def stop(self) -> bytes:
        """模拟停止采集并返回预设 PCM。

        返回:
            构造时传入的 pcm，即使当前未录音也保持不变。

        副作用:
            将替身标记为非录音状态。
        """
        self._recording = False
        return self.pcm

    def bytes_captured(self) -> int:
        """返回模拟的实时采集字节数。

        返回:
            录音中返回 live_bytes，否则返回 0。

        副作用:
            无。
        """
        return self.live_bytes if self._recording else 0


class MockPlayback:
    """记录所有播放内容的测试替身。

    副作用:
        play_pcm() 会把 PCM 追加到公开的 played 列表。
    """

    def __init__(self) -> None:
        self.played: list[bytes] = []

    def play_pcm(self, pcm: bytes, sample_rate: int | None = None) -> bool:
        """记录一次模拟播放。

        参数:
            pcm: 待记录的 PCM 字节。
            sample_rate: 与真实播放口对齐的可选采样率，替身忽略其值。

        返回:
            始终返回 True。

        副作用:
            将 pcm 追加到 played。
        """
        self.played.append(pcm)
        return True


def build_audio_io() -> tuple[AudioCapture, AudioPlayback]:
    """按 ALSA 工具可用性构造采集与播放端口。

    返回:
        arecord 与 aplay 都在 PATH 时返回真实 ALSA 实现；否则返回 mock 对。

    副作用:
        仅查询 PATH，不启动音频子进程。
    """
    if shutil.which("arecord") is not None and shutil.which("aplay") is not None:
        return AlsaCapture(), AlsaPlayback()
    _LOG.warning("arecord 或 aplay 不可用，音频输入输出回退到 mock")
    return MockCapture(b"", start_ok=False), MockPlayback()
