"""WAV 封装与过短/静音判定，无 ALSA。"""

from __future__ import annotations

import math
import struct
import sys
from pathlib import Path

_SOFTWARE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_SOFTWARE))

from voice.config import MIN_UTTERANCE_S, SAMPLE_RATE, SILENCE_PEAK  # noqa: E402
from voice.wavutil import (  # noqa: E402
    classify_utterance,
    gate_pcm,
    make_beep_pcm,
    pcm_duration_s,
    pcm_peak,
    pcm_to_wav,
    upmix_mono_to_stereo,
    wav_to_pcm,
)


def _tone(seconds: float, amplitude: int = 4000, freq: float = 440.0) -> bytes:
    n = int(SAMPLE_RATE * seconds)
    samples = [
        int(amplitude * math.sin(2 * math.pi * freq * i / SAMPLE_RATE))
        for i in range(n)
    ]
    return struct.pack("<" + "h" * n, *samples)


def test_wav_roundtrip_preserves_pcm() -> None:
    pcm = _tone(0.5)
    wav = pcm_to_wav(pcm)
    assert wav[:4] == b"RIFF"
    assert wav_to_pcm(wav) == pcm


def test_too_short_under_400ms() -> None:
    pcm = _tone(MIN_UTTERANCE_S - 0.05, amplitude=4000)
    assert pcm_duration_s(pcm) < MIN_UTTERANCE_S
    assert classify_utterance(pcm) == "too_short"


def test_silence_peak_under_200() -> None:
    n = int(SAMPLE_RATE * 0.5)
    pcm = struct.pack("<" + "h" * n, *([SILENCE_PEAK - 1] * n))
    assert pcm_peak(pcm) < SILENCE_PEAK
    assert classify_utterance(pcm) == "silent"


def test_ok_speech_like_tone() -> None:
    assert classify_utterance(_tone(0.5, amplitude=4000)) == "ok"


def test_beep_is_audible_and_short() -> None:
    beep = make_beep_pcm()
    assert pcm_duration_s(beep) == 0.2
    assert pcm_peak(beep) >= SILENCE_PEAK


def test_upmix_mono_to_stereo_duplicates_each_frame() -> None:
    """ES8388 播放必须按立体声帧送数，左右复制后时长不变。"""
    pcm = struct.pack("<hh", 100, -100)
    out = upmix_mono_to_stereo(pcm)
    assert out == struct.pack("<hhhh", 100, 100, -100, -100)
    assert pcm_duration_s(out, channels=2) == pcm_duration_s(pcm, channels=1)


def test_amplify_pcm_raises_quiet_peak_without_clipping() -> None:
    """回放增益应抬升安静录音，且不超过目标峰值。"""
    from voice.wavutil import amplify_pcm

    quiet = _tone(0.2, amplitude=500)
    loud = amplify_pcm(quiet, target_peak=12000, max_gain=40.0)
    assert pcm_peak(loud) >= 11000
    assert pcm_peak(loud) <= 12000
    assert pcm_duration_s(loud) == pcm_duration_s(quiet)


def _peak_between(pcm: bytes, start_s: float, end_s: float) -> int:
    start = int(start_s * SAMPLE_RATE) * 2
    end = int(end_s * SAMPLE_RATE) * 2
    return pcm_peak(pcm[start:end])


def test_gate_zeros_leading_desk_noise_keeps_speech() -> None:
    """打印机一类底噪远低于人声时，回放应切掉前段、保住说话。"""
    noise = _tone(0.8, amplitude=300, freq=120.0)
    speech = _tone(0.5, amplitude=8000, freq=440.0)
    pcm = noise + speech
    gated = gate_pcm(pcm)
    assert pcm_duration_s(gated) == pcm_duration_s(pcm)
    assert _peak_between(gated, 0.15, 0.55) < 80
    assert _peak_between(gated, 0.85, 1.20) >= 6000


def test_gate_leaves_inseparable_clip_unchanged() -> None:
    """底噪和峰值分不开时不要乱切，避免整句被静音。"""
    pcm = _tone(0.8, amplitude=400, freq=120.0)
    assert gate_pcm(pcm) == pcm
