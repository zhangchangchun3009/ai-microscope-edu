"""按住说话（PTT）录音会话编排：判定后走 ASR → 问答 → 句队列 TTS。"""

from __future__ import annotations

import logging
import threading
import time
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Literal, Optional, Protocol

from qa.config import SHORT_SENTENCE_CHARS
from qa.sentences import SentenceSplitter, merge_short_sentences, ready_to_play
from qa.turn import QaService
from voice.alsa import AudioCapture, AudioPlayback
from voice.asr import transcribe_wav
from voice.config import MAX_RECORD_S, NO_DATA_S, TTS_GAIN
from voice.pipeline import SentencePlayer
from voice.tts import TextToSpeech, build_tts
from voice.wavutil import classify_utterance, make_beep_pcm, pcm_to_wav

StopResult = Literal["ignored", "played", "discarded", "failed", "aborted"]
_LOG = logging.getLogger(__name__)
_STRIP_CHARS = " \t\n\r。！？!?.,，"


class QaPort(Protocol):
    """问答端口：流式 token 与成功后写记忆。"""

    def iter_tokens(self, user_text: str) -> Iterator[str]:
        """按用户问句产出助手增量文本。"""
        ...

    def append_turn(self, user: str, assistant: str) -> None:
        """写入一轮完整问答。"""
        ...


def _is_short(text: str) -> bool:
    """句末标点与空白不计，有效字数是否低于短句阈值。"""
    return len(text.strip().strip(_STRIP_CHARS)) < SHORT_SENTENCE_CHARS


class VoiceSession:
    """协调一次 PTT 采集、有效性判定、识别、问答与按句播报。

    参数:
        capture: 音频采集端口。
        playback: 音频播放端口。
        wav_path: 最近一次录音写入的 WAV 路径。
        monotonic: 单调时钟函数，默认使用 time.monotonic。
        asr: 识别函数；缺省 ``transcribe_wav``。
        qa: 问答端口；缺省首轮懒创建 ``QaService`` 并复用其 ``QaMemory``。
        tts: 语音合成端口；缺省首轮懒创建 ``build_tts()`` 并复用。

    副作用:
        可启动或停止采集、写入 WAV，并同步播放提示音或 TTS PCM。
    """

    def __init__(
        self,
        capture: AudioCapture,
        playback: AudioPlayback,
        wav_path: Path,
        *,
        monotonic: Callable[[], float] = time.monotonic,
        asr: Callable[[Path], str] | None = None,
        qa: QaPort | None = None,
        tts: TextToSpeech | None = None,
    ) -> None:
        self._capture = capture
        self._playback = playback
        self._wav_path = wav_path
        self._monotonic = monotonic
        self._asr = transcribe_wav if asr is None else asr
        # 缺省时在首轮懒创建并挂到实例上；每回合 new 会丢掉 8 轮记忆、重载 Matcha。
        self._qa = qa
        self._tts = tts
        self._tts_lock = threading.Lock()
        self._phase = "idle"
        self._started_at = 0.0
        # 跨线程取消标志：GUI 线程 abort() 置位，工作线程的回合循环据此提前收手。
        self._cancel = threading.Event()
        if tts is None:
            threading.Thread(
                target=self._warmup_tts,
                name="edu-tts-warmup",
                daemon=True,
            ).start()

    def start_ptt(self) -> bool:
        """空闲时开始一段 PTT 录音。

        返回:
            成功进入录音状态返回 True；忙碌或采集启动失败返回 False。

        副作用:
            启动采集、清除上一次的取消标志；启动失败时播放提示音。
        """
        if self.is_busy():
            return False
        self._cancel.clear()
        if not self._capture.start():
            self._beep()
            return False
        self._phase = "recording"
        self._started_at = self._monotonic()
        return True

    def stop_ptt(self) -> StopResult:
        """停止当前 PTT 录音并处理结果。

        返回:
            ignored 表示当前未录音；played 表示问答 TTS 已播完；
            discarded 表示无效语音已丢弃并提示；failed 表示空录音、
            识别失败、问答失败或播放失败；aborted 表示回合中被
            ``abort()`` 取消（无提示音、未写记忆）。

        副作用:
            停止采集、写入最近 WAV，并播放 TTS 或提示音。
        """
        if self._phase != "recording":
            return "ignored"
        return self._finish_recording()

    def abort(self) -> None:
        """中止当前录音或回合，且不播放任何声音。

        返回:
            无。

        副作用:
            任何相位都会置位取消标志：回合中的 ``_run_turn`` 会在下一次
            synthesize / play_pcm 之前收手（不 beep、不写记忆），关窗因此
            不必等整段回答播完。已经交给 ``aplay`` 的那一句仍会播完
            （中断在播的进程需要 Popen，属后续改动）。
            录音中还会停止采集并丢弃结果；无论停止是否异常都会恢复空闲。
        """
        self._cancel.set()
        if self._phase != "recording":
            return
        try:
            self._capture.stop()
        except Exception:
            _LOG.exception("中止 PTT 录音时停止采集失败")
        finally:
            self._phase = "idle"

    def would_auto_stop(self, now: Optional[float] = None) -> bool:
        """廉价判定录音是否已达自动收尾条件。

        参数:
            now: 单调时钟值；省略时读取 monotonic。

        返回:
            正在录音且达到 300 秒上限，或满 3 秒仍无数据时返回 True。

        副作用:
            无。只比较时钟与已采集字节数，不停止采集、不跑 ASR。
        """
        if self._phase != "recording":
            return False
        current = self._monotonic() if now is None else now
        elapsed = current - self._started_at
        if elapsed >= MAX_RECORD_S:
            return True
        return elapsed >= NO_DATA_S and self._capture.bytes_captured() == 0

    def tick(self, now: Optional[float] = None) -> None:
        """检查录音超时和持续无数据条件。

        参数:
            now: 用于本次检查的单调时钟值；省略时读取 monotonic。

        返回:
            无。

        副作用:
            达到 300 秒时自动正常收尾；达到 3 秒仍无数据时停止并
            播放失败提示音。未超时则为空操作。
        """
        if not self.would_auto_stop(now):
            return
        current = self._monotonic() if now is None else now
        elapsed = current - self._started_at
        if elapsed >= MAX_RECORD_S:
            self._finish_recording()
        elif elapsed >= NO_DATA_S and self._capture.bytes_captured() == 0:
            self._finish_recording(force_failed=True)

    def is_busy(self) -> bool:
        """判断会话是否占用采集或回合链路。

        返回:
            正在录音或问答播报时返回 True，否则返回 False。

        副作用:
            无。
        """
        return self._phase in ("recording", "turning")

    def input_enabled(self) -> bool:
        """浮标是否仍应接受按住/松开。

        返回:
            回合中（``turning``）返回 False；录音中返回 True，以便松开结束 PTT。

        副作用:
            无。
        """
        return self._phase != "turning"

    def _finish_recording(self, *, force_failed: bool = False) -> StopResult:
        try:
            pcm = self._capture.stop()
            self._wav_path.parent.mkdir(parents=True, exist_ok=True)
            self._wav_path.write_bytes(pcm_to_wav(pcm))
            if not pcm or force_failed:
                self._beep()
                return "failed"

            if classify_utterance(pcm) != "ok":
                played = self._beep()
                return "discarded" if played else "failed"

            self._phase = "turning"
            return self._run_turn()
        except Exception:
            _LOG.exception("PTT 录音收尾失败")
            try:
                self._beep()
            except Exception:
                _LOG.exception("PTT 录音收尾失败后播放提示音失败")
            return "failed"
        finally:
            self._phase = "idle"

    def _ensure_qa(self) -> QaPort:
        """返回本会话复用的问答端口；缺省时只构造一次 ``QaService``。

        返回:
            注入的端口，或首次懒创建后缓存的 ``QaService``。

        副作用:
            首次缺省调用会构造 ``QaService`` 并写入 ``self._qa``。
        """
        if self._qa is None:
            self._qa = QaService()
        return self._qa

    def _ensure_tts(self) -> TextToSpeech:
        """返回本会话复用的 TTS；缺省时只调用一次 ``build_tts()``。

        返回:
            注入的 TTS，或首次懒创建后缓存的实例。

        副作用:
            首次缺省调用会 ``build_tts()`` 并写入 ``self._tts``。
        """
        with self._tts_lock:
            if self._tts is None:
                self._tts = build_tts()
            return self._tts

    def _warmup_tts(self) -> None:
        """应用启动后预加载 Matcha，避免第一轮开口卡在模型加载。"""
        try:
            self._ensure_tts()
        except Exception:
            _LOG.exception("TTS 预热失败")

    def _run_turn(self) -> StopResult:
        """识别 → 流式分句入队 → 水位到达后按句 TTS。全程成功才写记忆。

        取消（``abort()``）在每次合成/播放前检查，命中即返回 ``aborted``：
        不 beep、不写记忆，让关窗路径有界退出。
        """
        if self._cancel.is_set():
            return "aborted"
        user_text = (self._asr(self._wav_path) or "").strip()
        if not user_text:
            self._beep()
            return "failed"

        qa = self._ensure_qa()
        tts = self._ensure_tts()
        splitter = SentenceSplitter()
        pending: list[str] = []
        queue: list[str] = []
        started = False
        submitted = 0
        assistant_parts: list[str] = []
        player = SentencePlayer(tts, self._playback, self._cancel, gain=TTS_GAIN)

        def ingest(parts: list[str], *, producer_done: bool) -> None:
            """合并短句后入队；流未结束时末尾短句留下一拍，等下一句。"""
            pending.extend(parts)
            if not pending:
                return
            merged = merge_short_sentences(pending, producer_done=producer_done)
            if producer_done:
                queue.extend(merged)
                pending.clear()
                return
            if merged and _is_short(merged[-1]):
                queue.extend(merged[:-1])
                pending[:] = [merged[-1]]
            else:
                queue.extend(merged)
                pending.clear()

        def flush_to_player(*, producer_done: bool) -> None:
            """水位够了才把句子交给合成线程；之后随到随交，不再等播完。"""
            nonlocal started, submitted
            if not started:
                if not ready_to_play(len(queue), producer_done):
                    return
                started = True
            while submitted < len(queue):
                player.submit(queue[submitted])
                submitted += 1

        stream_error = False
        try:
            for token in qa.iter_tokens(user_text):
                if self._cancel.is_set():
                    break
                assistant_parts.append(token)
                ingest(splitter.push(token), producer_done=False)
                flush_to_player(producer_done=False)
            else:
                ingest(splitter.finish(), producer_done=True)
                flush_to_player(producer_done=True)
        except Exception:
            _LOG.exception("问答流失败")
            self._cancel.set()
            stream_error = True

        status = player.close()
        if self._cancel.is_set() and not stream_error:
            return "aborted"
        if stream_error or status != "played":
            if status != "aborted":
                self._beep()
            return "aborted" if status == "aborted" else "failed"

        qa.append_turn(user_text, "".join(assistant_parts))
        return "played"

    def _beep(self) -> bool:
        """播放失败提示音，不改变会话相位。"""
        return self._playback.play_pcm(make_beep_pcm())
