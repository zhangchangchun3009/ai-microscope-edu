"""语音回合编排：水位、空识别、部分 TTS 失败与 QaService。"""

from __future__ import annotations

import math
import struct
import sys
from collections.abc import Iterator
from pathlib import Path

_SOFTWARE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_SOFTWARE))

from qa.sentences import ready_to_play  # noqa: E402
from voice.alsa import MockCapture, MockPlayback  # noqa: E402
from voice.config import SAMPLE_RATE  # noqa: E402
from voice.session import VoiceSession  # noqa: E402
from voice.wavutil import make_beep_pcm  # noqa: E402


def _tone(seconds: float, amplitude: int = 4000) -> bytes:
    n = int(SAMPLE_RATE * seconds)
    samples = [int(amplitude * math.sin(2 * math.pi * 440 * i / SAMPLE_RATE)) for i in range(n)]
    return struct.pack("<" + "h" * n, *samples)


class _ScriptQa:
    """可在产出过程中观察播放次数的问答替身。"""

    def __init__(self, tokens: list[str], on_after_first=None) -> None:
        self._tokens = list(tokens)
        self._on_after_first = on_after_first
        self.turns: list[tuple[str, str]] = []
        self.new_sessions = 0

    def iter_tokens(self, user_text: str) -> Iterator[str]:
        """按列表产出 token；第一段之后可回调。"""
        del user_text
        for i, token in enumerate(self._tokens):
            yield token
            if i == 0 and self._on_after_first is not None:
                self._on_after_first()

    def append_turn(self, user: str, assistant: str) -> None:
        """记录成功写入的记忆。"""
        self.turns.append((user, assistant))

    def start_new_session(self) -> None:
        """记一次切场调用。"""
        self.new_sessions += 1


class _Tts:
    """把句子原样编码成伪 PCM。"""

    def __init__(self) -> None:
        self.sentences: list[str] = []

    def synthesize(self, text: str) -> bytes:
        """记录并返回伪 PCM。"""
        self.sentences.append(text)
        return b"TTS:" + text.encode("utf-8")


def _make_session(
    tmp_path: Path,
    *,
    asr,
    qa,
    tts,
    playback: MockPlayback | None = None,
) -> tuple[VoiceSession, MockPlayback]:
    play = playback if playback is not None else MockPlayback()
    sess = VoiceSession(
        MockCapture(_tone(0.5)),
        play,
        tmp_path / "last.wav",
        monotonic=lambda: 0.0,
        asr=asr,
        qa=qa,
        tts=tts,
    )
    return sess, play


def test_ready_to_play_watermark_is_two_until_done() -> None:
    assert ready_to_play(1, False) is False
    assert ready_to_play(3, True) is True


def test_watermark_holds_playback_until_enough_sentences(tmp_path: Path) -> None:
    play = MockPlayback()
    seen_after_first: list[int] = []

    def _after_first() -> None:
        seen_after_first.append(len(play.played))

    qa = _ScriptQa(["好。", "这是洋葱。", "第三句。"], on_after_first=_after_first)
    tts = _Tts()
    sess, play = _make_session(
        tmp_path,
        asr=lambda _p: "问细胞壁",
        qa=qa,
        tts=tts,
        playback=play,
    )
    sess.start_ptt()
    assert sess.stop_ptt() == "played"
    assert seen_after_first == [0]
    assert len(play.played) >= 1
    assert tts.sentences


def test_asr_empty_beeps_not_tts(tmp_path: Path) -> None:
    tts = _Tts()
    qa = _ScriptQa(["不该走到问答。"])
    sess, play = _make_session(
        tmp_path,
        asr=lambda _p: "",
        qa=qa,
        tts=tts,
    )
    sess.start_ptt()
    assert sess.stop_ptt() == "failed"
    assert play.played == [make_beep_pcm()]
    assert tts.sentences == []
    assert qa.turns == []


def test_empty_qa_tokens_beep_and_skip_memory(tmp_path: Path) -> None:
    tts = _Tts()
    qa = _ScriptQa([])
    sess, play = _make_session(
        tmp_path,
        asr=lambda _p: "这是什么",
        qa=qa,
        tts=tts,
    )
    sess.start_ptt()
    assert sess.stop_ptt() == "failed"
    assert play.played == [make_beep_pcm()]
    assert qa.turns == []


def test_tts_play_failure_beeps_and_does_not_append(tmp_path: Path) -> None:
    class _FailPlay(MockPlayback):
        def play_pcm(self, pcm: bytes, sample_rate: int | None = None) -> bool:
            self.played.append(pcm)
            return False

    qa = _ScriptQa(["这是洋葱表皮细胞。细胞膜清晰可见了。"])
    tts = _Tts()
    play = _FailPlay()
    sess, _ = _make_session(
        tmp_path,
        asr=lambda _p: "看一下",
        qa=qa,
        tts=tts,
        playback=play,
    )
    sess.start_ptt()
    assert sess.stop_ptt() == "failed"
    assert play.played[-1] == make_beep_pcm()
    assert qa.turns == []


def test_abort_during_turn_stops_queue_without_beep(tmp_path: Path) -> None:
    """回合中 abort 后不再合成新句、不 beep、不写记忆（关窗要能有界退出）。"""

    class _AbortingTts(_Tts):
        def synthesize(self, text: str) -> bytes:
            pcm = super().synthesize(text)
            sess.abort()
            return pcm

    qa = _ScriptQa(["第一句。", "第二句。", "第三句。", "第四句。"])
    tts = _AbortingTts()
    sess, play = _make_session(
        tmp_path,
        asr=lambda _p: "讲讲细胞",
        qa=qa,
        tts=tts,
    )
    sess.start_ptt()

    assert sess.stop_ptt() == "aborted"
    assert len(tts.sentences) == 1
    assert play.played == []
    assert qa.turns == []
    assert sess.is_busy() is False


def test_abort_flag_cleared_for_next_turn(tmp_path: Path) -> None:
    """上一轮的取消标志不得残留，否则下一轮开口就被吞掉。"""
    qa = _ScriptQa(["这是洋葱表皮细胞。细胞壁清晰可见。"])
    tts = _Tts()
    sess, play = _make_session(
        tmp_path,
        asr=lambda _p: "这是什么",
        qa=qa,
        tts=tts,
    )
    sess.abort()

    sess.start_ptt()
    assert sess.stop_ptt() == "played"
    assert tts.sentences
    assert play.played


def test_qa_service_without_llm_yields_nothing(tmp_path: Path) -> None:
    from qa.turn import QaService

    svc = QaService(qa_dir=tmp_path, environ={}, purge_on_start=False)
    assert list(svc.iter_tokens("细胞膜是什么")) == []


def test_qa_service_append_turn_keeps_memory(tmp_path: Path) -> None:
    from qa.turn import QaService

    svc = QaService(qa_dir=tmp_path, environ={}, purge_on_start=False)
    svc.append_turn("问", "答")
    assert svc.memory.messages() == [
        {"role": "user", "content": "问"},
        {"role": "assistant", "content": "答"},
    ]


def test_new_session_utterance_skips_llm_and_speaks_fixed(tmp_path: Path) -> None:
    qa = _ScriptQa(["不该出现"])
    tts = _Tts()
    sess, play = _make_session(
        tmp_path, asr=lambda _p: "新对话", qa=qa, tts=tts
    )
    sess.start_ptt()
    assert sess.stop_ptt() == "played"
    assert qa.turns == []
    assert getattr(qa, "new_sessions", 1) >= 1
    assert tts.sentences == ["已处于新对话"]
    assert play.played
    assert make_beep_pcm() not in play.played


def test_normal_question_still_hits_llm(tmp_path: Path) -> None:
    qa = _ScriptQa(["这是洋葱表皮。"])
    tts = _Tts()
    sess, _play = _make_session(
        tmp_path, asr=lambda _p: "洋葱表皮是什么", qa=qa, tts=tts
    )
    sess.start_ptt()
    assert sess.stop_ptt() == "played"
    assert qa.turns
    assert "已处于新对话" not in tts.sentences


def test_new_session_utterance_skips_on_asr_and_captions_fixed(
    tmp_path: Path,
) -> None:
    """口令在 on_asr 之前拦截：用户字幕不出现，固定句走上字幕。"""
    events: list[tuple] = []
    qa = _ScriptQa(["不该出现"])
    tts = _Tts()
    play = MockPlayback()
    sess = VoiceSession(
        MockCapture(_tone(0.5)),
        play,
        tmp_path / "last.wav",
        monotonic=lambda: 0.0,
        asr=lambda _p: "  新会话。",
        qa=qa,
        tts=tts,
        on_asr=lambda text: events.append(("asr", text)),
        on_assistant_sentence=lambda text, *_a: events.append(("sent", text)),
        on_captions_clear=lambda: events.append(("clear",)),
    )
    sess.start_ptt()
    assert sess.stop_ptt() == "played"
    assert qa.new_sessions == 1
    assert qa.turns == []
    assert not any(item[0] == "asr" for item in events)
    assert ("sent", "已处于新对话") in events


def test_new_session_tts_fail_beeps_without_llm(tmp_path: Path) -> None:
    """切场成功但 TTS 失败：beep、不走 LLM、不写记忆。"""

    class _FailTts:
        def synthesize(self, text: str) -> bytes:
            raise RuntimeError("tts boom")

    qa = _ScriptQa(["不该出现"])
    sess, play = _make_session(
        tmp_path, asr=lambda _p: "新建对话", qa=qa, tts=_FailTts()
    )
    sess.start_ptt()
    assert sess.stop_ptt() == "failed"
    assert qa.new_sessions == 1
    assert qa.turns == []
    assert play.played[-1] == make_beep_pcm()


def test_new_session_abort_before_fixed_tts_skips_speak(tmp_path: Path) -> None:
    """固定句合成前若已 abort，则不 TTS、不 beep。"""

    class _AbortingQa(_ScriptQa):
        def start_new_session(self) -> None:
            super().start_new_session()
            sess.abort()

    qa = _AbortingQa(["不该出现"])
    tts = _Tts()
    sess, play = _make_session(
        tmp_path, asr=lambda _p: "新建会话", qa=qa, tts=tts
    )
    sess.start_ptt()
    assert sess.stop_ptt() == "aborted"
    assert qa.new_sessions == 1
    assert tts.sentences == []
    assert play.played == []
    assert qa.turns == []
