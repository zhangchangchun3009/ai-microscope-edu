"""句队列：合成与 aplay 重叠，取消后不再合成。"""

from __future__ import annotations

import sys
import threading
import time
from pathlib import Path

_SOFTWARE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_SOFTWARE))

from voice.alsa import MockPlayback  # noqa: E402
from voice.pipeline import SentencePlayer  # noqa: E402


class _Tts:
    """记录合成顺序；可选在指定句上阻塞到事件。"""

    def __init__(self) -> None:
        self.sentences: list[str] = []
        self.lock = threading.Lock()

    def synthesize(self, text: str) -> bytes:
        with self.lock:
            self.sentences.append(text)
        return b"\0\0" * 8


def test_player_synthesizes_next_sentence_while_playing() -> None:
    """播放第一句时第二句应已合成进预取队列，而不是播完再合成。"""
    tts = _Tts()
    second_ready = []

    class _Play(MockPlayback):
        def play_pcm(self, pcm: bytes, sample_rate: int | None = None) -> bool:
            if not self.played:
                deadline = time.monotonic() + 1.0
                while "第二句。" not in tts.sentences and time.monotonic() < deadline:
                    time.sleep(0.005)
                second_ready.append("第二句。" in tts.sentences)
            return super().play_pcm(pcm, sample_rate=sample_rate)

    play = _Play()
    cancel = threading.Event()
    player = SentencePlayer(tts, play, cancel, gain=1.0, prefetch=3)
    player.submit("第一句。")
    player.submit("第二句。")
    result = player.close()
    assert result == "played"
    assert second_ready == [True]
    assert tts.sentences == ["第一句。", "第二句。"]
    assert len(play.played) == 2


def test_player_abort_during_first_synth_skips_play() -> None:
    cancel = threading.Event()
    tts = _Tts()

    def _synth(text: str) -> bytes:
        pcm = _Tts.synthesize(tts, text)
        cancel.set()
        return pcm

    tts.synthesize = _synth  # type: ignore[method-assign]
    play = MockPlayback()
    player = SentencePlayer(tts, play, cancel, gain=1.0)
    player.submit("第一句。")
    player.submit("第二句。")
    result = player.close()
    assert result == "aborted"
    assert len(tts.sentences) == 1
    assert play.played == []
