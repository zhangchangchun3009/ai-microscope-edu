"""PTT 会话：忙碌忽略、300s 截断、判定后走 ASR→问答→TTS。"""

from __future__ import annotations

import math
import struct
import sys
from pathlib import Path
from typing import Iterator

_SOFTWARE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_SOFTWARE))

from voice.alsa import MockCapture, MockPlayback  # noqa: E402
from voice.config import MAX_RECORD_S, SAMPLE_RATE, TTS_RATE  # noqa: E402
from voice.session import VoiceSession  # noqa: E402
from voice.wavutil import amplify_pcm, gate_pcm, make_beep_pcm, pcm_to_wav  # noqa: E402


def _tone(seconds: float, amplitude: int = 4000) -> bytes:
    n = int(SAMPLE_RATE * seconds)
    samples = [int(amplitude * math.sin(2 * math.pi * 440 * i / SAMPLE_RATE)) for i in range(n)]
    return struct.pack("<" + "h" * n, *samples)


class _ScriptQa:
    """按预设 token 流回答，并记录写入记忆的回合。"""

    def __init__(self, tokens: list[str] | str) -> None:
        if isinstance(tokens, str):
            self._tokens = [tokens]
        else:
            self._tokens = list(tokens)
        self.turns: list[tuple[str, str]] = []

    def iter_tokens(self, user_text: str) -> Iterator[str]:
        """逐段产出助手文本。"""
        del user_text
        yield from self._tokens

    def append_turn(self, user: str, assistant: str) -> None:
        """记录成功回合。"""
        self.turns.append((user, assistant))


class _RecordingTts:
    """记录合成句子并返回可辨认 PCM。"""

    def __init__(self) -> None:
        self.sentences: list[str] = []

    def synthesize(self, text: str) -> bytes:
        """记下句子并返回以 TTS: 为前缀的伪 PCM。"""
        self.sentences.append(text)
        return b"TTS:" + text.encode("utf-8")


def _session(
    tmp_path: Path,
    pcm: bytes,
    *,
    start_ok: bool = True,
    asr=None,
    qa=None,
    tts=None,
) -> tuple[VoiceSession, MockPlayback]:
    play = MockPlayback()
    extra: dict[str, object] = {}
    if asr is not None:
        extra["asr"] = asr
    if qa is not None:
        extra["qa"] = qa
    if tts is not None:
        extra["tts"] = tts
    sess = VoiceSession(
        MockCapture(pcm, start_ok=start_ok),
        play,
        tmp_path / "last.wav",
        monotonic=lambda: 0.0,
        **extra,
    )
    return sess, play


def _ok_ports(
    asr_text: str = "这是洋葱。还有细胞壁。",
    qa_tokens: list[str] | str | None = None,
) -> tuple[object, _ScriptQa, _RecordingTts]:
    tokens: list[str] | str = asr_text if qa_tokens is None else qa_tokens
    return (lambda _path: asr_text, _ScriptQa(tokens), _RecordingTts())


def test_start_while_busy_is_ignored(tmp_path: Path) -> None:
    sess, play = _session(tmp_path, _tone(0.5))
    assert sess.start_ptt() is True
    assert sess.start_ptt() is False
    assert sess.is_busy() is True
    assert sess.input_enabled() is True
    assert play.played == []


def test_ok_utterance_writes_wav_and_plays_tts(tmp_path: Path) -> None:
    pcm = _tone(0.5)
    asr, qa, tts = _ok_ports()
    sess, play = _session(tmp_path, pcm, asr=asr, qa=qa, tts=tts)
    sess.start_ptt()
    assert sess.stop_ptt() == "played"
    assert (tmp_path / "last.wav").read_bytes() == pcm_to_wav(pcm)
    assert play.played != [amplify_pcm(gate_pcm(pcm))]
    assert amplify_pcm(gate_pcm(pcm)) not in play.played
    assert tts.sentences == ["这是洋葱。还有细胞壁。"]
    assert qa.turns == [("这是洋葱。还有细胞壁。", "这是洋葱。还有细胞壁。")]


def test_session_does_not_echo_gated_original(tmp_path: Path) -> None:
    """门控不再用于回放原声；落盘仍是原电平，给 ASR。"""
    noise = _tone(0.8, amplitude=300)
    speech = _tone(0.5, amplitude=8000)
    pcm = noise + speech
    asr, qa, tts = _ok_ports()
    sess, play = _session(tmp_path, pcm, asr=asr, qa=qa, tts=tts)
    sess.start_ptt()
    assert sess.stop_ptt() == "played"
    assert (tmp_path / "last.wav").read_bytes() == pcm_to_wav(pcm)
    assert amplify_pcm(gate_pcm(pcm)) not in play.played
    assert tts.sentences


def test_abort_stops_recording_without_playback(tmp_path: Path) -> None:
    sess, play = _session(tmp_path, _tone(0.5))
    sess.start_ptt()

    sess.abort()

    assert sess.is_busy() is False
    assert play.played == []


def test_stop_exception_returns_failed_and_restores_idle(tmp_path: Path) -> None:
    class _FailingCapture(MockCapture):
        def stop(self) -> bytes:
            raise RuntimeError("capture failed")

    play = MockPlayback()
    sess = VoiceSession(
        _FailingCapture(_tone(0.5)),
        play,
        tmp_path / "last.wav",
        monotonic=lambda: 0.0,
    )
    sess.start_ptt()

    assert sess.stop_ptt() == "failed"
    assert sess.is_busy() is False
    assert play.played == [make_beep_pcm()]


def test_silent_plays_beep_not_original(tmp_path: Path) -> None:
    n = int(SAMPLE_RATE * 0.5)
    silent = struct.pack("<" + "h" * n, *([0] * n))
    sess, play = _session(tmp_path, silent)
    sess.start_ptt()
    assert sess.stop_ptt() == "discarded"
    assert play.played == [make_beep_pcm()]


def test_capture_start_failure_beeps(tmp_path: Path) -> None:
    sess, play = _session(tmp_path, _tone(0.5), start_ok=False)
    assert sess.start_ptt() is False
    assert sess.stop_ptt() == "ignored"
    assert play.played == [make_beep_pcm()]
    assert sess.is_busy() is False


def test_would_auto_stop_only_compares_clock_and_bytes(tmp_path: Path) -> None:
    """would_auto_stop 只看相位/时钟/字节，不得收尾或播音。"""
    from voice.config import NO_DATA_S

    play = MockPlayback()
    cap = MockCapture(_tone(0.5))
    clock = {"t": 0.0}
    sess = VoiceSession(
        cap,
        play,
        tmp_path / "last.wav",
        monotonic=lambda: clock["t"],
    )
    assert sess.would_auto_stop() is False
    sess.start_ptt()
    clock["t"] = NO_DATA_S - 0.1
    assert sess.would_auto_stop() is False
    clock["t"] = NO_DATA_S
    assert sess.would_auto_stop() is False
    cap.live_bytes = 0
    assert sess.would_auto_stop() is True
    assert sess.is_busy() is True
    assert play.played == []
    cap.live_bytes = 8
    clock["t"] = MAX_RECORD_S
    assert sess.would_auto_stop() is True
    assert sess.is_busy() is True
    assert play.played == []


def test_max_record_300s_auto_stop(tmp_path: Path) -> None:
    pcm = _tone(0.5)
    asr, qa, tts = _ok_ports()
    play = MockPlayback()
    clock = {"t": 0.0}
    sess = VoiceSession(
        MockCapture(pcm),
        play,
        tmp_path / "last.wav",
        monotonic=lambda: clock["t"],
        asr=asr,
        qa=qa,
        tts=tts,
    )
    sess.start_ptt()
    clock["t"] = MAX_RECORD_S
    sess.tick()
    assert tts.sentences
    assert amplify_pcm(pcm) not in play.played
    assert sess.is_busy() is False


def test_no_data_after_3s_fails(tmp_path: Path) -> None:
    play = MockPlayback()
    cap = MockCapture(b"", start_ok=True)
    cap.live_bytes = 0
    clock = {"t": 0.0}
    sess = VoiceSession(cap, play, tmp_path / "last.wav", monotonic=lambda: clock["t"])
    sess.start_ptt()
    clock["t"] = 3.0
    sess.tick()
    assert play.played == [make_beep_pcm()]
    assert sess.is_busy() is False


def test_start_during_turning_is_ignored(tmp_path: Path) -> None:
    play = MockPlayback()
    nested: dict[str, object] = {}
    asr_text = "这是洋葱。还有细胞壁。"

    class _Tts:
        def synthesize(self, text: str) -> bytes:
            nested["started"] = sess.start_ptt()
            nested["busy"] = sess.is_busy()
            nested["input_enabled"] = sess.input_enabled()
            return b"TTS:" + text.encode("utf-8")

    sess = VoiceSession(
        MockCapture(_tone(0.5)),
        play,
        tmp_path / "last.wav",
        monotonic=lambda: 0.0,
        asr=lambda _p: asr_text,
        qa=_ScriptQa(asr_text),
        tts=_Tts(),
    )
    sess.start_ptt()
    sess.stop_ptt()
    assert nested["started"] is False
    assert nested["busy"] is True
    assert nested["input_enabled"] is False


def test_input_enabled_false_only_while_turning(tmp_path: Path) -> None:
    asr, qa, tts = _ok_ports()
    sess, _play = _session(tmp_path, _tone(0.5), asr=asr, qa=qa, tts=tts)
    assert sess.input_enabled() is True
    sess.start_ptt()
    assert sess.is_busy() is True
    assert sess.input_enabled() is True
    sess.stop_ptt()
    assert sess.is_busy() is False
    assert sess.input_enabled() is True


def test_build_audio_io_falls_back_without_arecord(monkeypatch) -> None:
    from voice.alsa import MockCapture, MockPlayback, build_audio_io

    monkeypatch.setattr("voice.alsa.shutil.which", lambda _name: None)
    cap, play = build_audio_io()
    assert isinstance(cap, MockCapture)
    assert cap.start() is False
    assert isinstance(play, MockPlayback)


def test_two_default_turns_keep_qa_memory(tmp_path: Path, monkeypatch) -> None:
    """qa/tts 缺省时只懒创建一次；第二轮记忆仍含第一轮 user。"""
    from qa.client import LlmConfig
    from qa.turn import QaService

    cfg = LlmConfig(
        base_url="https://api.example.com/v1",
        api_key="sk-test",
        model="qwen-plus",
        timeout_s=30.0,
    )
    monkeypatch.setattr("qa.turn.load_llm_config", lambda *_a, **_k: cfg)

    def _fake_tokens(_config, _messages):
        yield "这是洋葱表皮。"

    monkeypatch.setattr("qa.turn.iter_chat_tokens", _fake_tokens)
    tts_builds: list[_RecordingTts] = []

    def _fake_build_tts() -> _RecordingTts:
        tts = _RecordingTts()
        tts_builds.append(tts)
        return tts

    monkeypatch.setattr("voice.session.build_tts", _fake_build_tts)
    questions = iter(["第一问细胞", "第二问细胞核"])
    sess, _play = _session(tmp_path, _tone(0.5), asr=lambda _p: next(questions))

    sess.start_ptt()
    assert sess.stop_ptt() == "played"
    sess.start_ptt()
    assert sess.stop_ptt() == "played"

    assert isinstance(sess._qa, QaService)
    users = [m["content"] for m in sess._qa.memory.messages() if m["role"] == "user"]
    assert "第一问细胞" in users
    assert users[0] == "第一问细胞"
    assert len(tts_builds) == 1


def test_tts_playback_uses_tts_rate(tmp_path: Path) -> None:
    pcm = _tone(0.5)
    asr, qa, tts = _ok_ports()
    sess, play = _session(tmp_path, pcm, asr=asr, qa=qa, tts=tts)
    rates: list[int | None] = []
    original = play.play_pcm

    def _play(pcm_bytes: bytes, sample_rate: int | None = None) -> bool:
        rates.append(sample_rate)
        return original(pcm_bytes, sample_rate=sample_rate)

    play.play_pcm = _play  # type: ignore[method-assign]
    sess.start_ptt()
    sess.stop_ptt()
    assert TTS_RATE in rates
