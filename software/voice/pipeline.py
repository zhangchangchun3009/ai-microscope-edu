"""问答播报管线：合成线程与 aplay 线程重叠，避免句间空等。"""

from __future__ import annotations

import logging
import queue
import threading
from collections.abc import Callable
from typing import Literal

from voice.alsa import AudioPlayback
from voice.config import TTS_GAIN, TTS_PCM_PREFETCH, TTS_RATE
from voice.tts import TextToSpeech
from voice.wavutil import scale_pcm

_LOG = logging.getLogger(__name__)
PlayStatus = Literal["played", "failed", "aborted"]
_SENTINEL = None
_JOIN_S = 120.0


class SentencePlayer:
    """文本句入队后，后台合成 PCM，同时另一线程串行 aplay。

    参数:
        tts: 一句文本 → PCM。
        playback: 播放端口。
        cancel: 跨线程取消标志；置位后不再合成新句、不再取下一句播放。
        sample_rate: 交给 aplay 前的 PCM 采样率（Matcha 为 22050）。
        gain: 合成后线性增益，1.0 为原电平。
        prefetch: 未播 PCM 队列上限，让合成领先播放 2～3 句。
        on_play_start: 某句即将 aplay 时回调 ``(text, duration_s)``；可在播放线程调用。

    副作用:
        构造即启动守护线程；``close()`` 等待两线程结束。
    """

    def __init__(
        self,
        tts: TextToSpeech,
        playback: AudioPlayback,
        cancel: threading.Event,
        *,
        sample_rate: int = TTS_RATE,
        gain: float = TTS_GAIN,
        prefetch: int = TTS_PCM_PREFETCH,
        on_play_start: Callable[[str, float], None] | None = None,
    ) -> None:
        self._tts = tts
        self._playback = playback
        self._cancel = cancel
        self._sample_rate = int(sample_rate)
        self._gain = float(gain)
        self._on_play_start = on_play_start
        self._text_q: queue.Queue[str | None] = queue.Queue()
        # (句文本, PCM)；结束标记仍为 None。
        self._pcm_q: queue.Queue[tuple[str, bytes] | None] = queue.Queue(
            maxsize=max(1, int(prefetch))
        )
        self._played = 0
        self._failed = False
        self._synth_t = threading.Thread(
            target=self._synth_loop, name="edu-tts-synth", daemon=True
        )
        self._play_t = threading.Thread(
            target=self._play_loop, name="edu-tts-play", daemon=True
        )
        self._synth_t.start()
        self._play_t.start()

    def submit(self, sentence: str) -> None:
        """把一句待朗读文本交给合成线程。

        参数:
            sentence: 已分好的一句；空串忽略。

        返回:
            无。

        副作用:
            入队；队列满时阻塞（背压，避免堆无限 PCM）。
        """
        text = (sentence or "").strip()
        if not text or self._cancel.is_set() or self._failed:
            return
        self._text_q.put(text)

    def close(self) -> PlayStatus:
        """声明没有更多句子，等待合成与播放结束。

        返回:
            played 至少播完一句；aborted 若取消；failed 若合成/播放出错或零句。

        副作用:
            向队列投入结束标记并 join 工作线程。
        """
        self._text_q.put(_SENTINEL)
        self._synth_t.join(timeout=_JOIN_S)
        self._play_t.join(timeout=_JOIN_S)
        if self._cancel.is_set():
            return "aborted"
        if self._failed or self._played == 0:
            return "failed"
        return "played"

    def _synth_loop(self) -> None:
        """从文本队列取句，合成后放入 PCM 队列。"""
        try:
            while True:
                if self._cancel.is_set() or self._failed:
                    return
                item = self._text_q.get()
                if item is _SENTINEL:
                    return
                if self._cancel.is_set() or self._failed:
                    return
                try:
                    pcm = self._tts.synthesize(item)
                except Exception:
                    _LOG.exception("TTS 合成失败")
                    self._failed = True
                    return
                if self._cancel.is_set():
                    return
                if not pcm:
                    continue
                if self._gain != 1.0:
                    pcm = scale_pcm(pcm, self._gain)
                try:
                    self._pcm_q.put((item, pcm), timeout=_JOIN_S)
                except queue.Full:
                    self._failed = True
                    return
        finally:
            try:
                self._pcm_q.put(_SENTINEL, timeout=_JOIN_S)
            except queue.Full:
                pass

    def _play_loop(self) -> None:
        """从 PCM 队列取句并串行播放；取消后仍排空队列直到结束标记。"""
        while True:
            item = self._pcm_q.get()
            if item is _SENTINEL:
                return
            if self._cancel.is_set() or self._failed:
                continue
            text, pcm = item
            duration_s = pcm_duration_s(pcm, self._sample_rate)
            self._emit_play_start(text, duration_s)
            if not self._playback.play_pcm(pcm, sample_rate=self._sample_rate):
                _LOG.error("TTS 播放失败")
                self._failed = True
                continue
            self._played += 1

    def _emit_play_start(self, text: str, duration_s: float) -> None:
        """通知字幕：该句即将开口。异常只记日志。"""
        cb = self._on_play_start
        if cb is None:
            return
        try:
            cb(text, duration_s)
        except Exception:
            _LOG.exception("on_play_start 失败")


def pcm_duration_s(pcm: bytes, sample_rate: int) -> float:
    """单声道 s16le PCM 的时长（秒）。

    参数:
        pcm: 16-bit LE 单声道字节。
        sample_rate: 采样率。

    返回:
        秒；空数据或非法采样率为 0。
    """
    if not pcm or sample_rate <= 0:
        return 0.0
    return len(pcm) / (2.0 * float(sample_rate))
