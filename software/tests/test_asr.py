"""SenseVoice ASR：重采样、Output 解析与 demo 调用，无真机模型。"""

from __future__ import annotations

import math
import struct
import subprocess
import sys
from pathlib import Path

_SOFTWARE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_SOFTWARE))

from voice.config import SAMPLE_RATE  # noqa: E402
from voice.wavutil import pcm_duration_s, pcm_to_wav  # noqa: E402


def _tone(seconds: float, amplitude: int = 4000, freq: float = 440.0) -> bytes:
    """生成指定时长的 44100 Hz 单声道正弦 PCM。"""
    n = int(SAMPLE_RATE * seconds)
    samples = [
        int(amplitude * math.sin(2 * math.pi * freq * i / SAMPLE_RATE))
        for i in range(n)
    ]
    return struct.pack("<" + "h" * n, *samples)


def test_resample_44100_sine_to_16k_keeps_duration() -> None:
    from voice.asr import ASR_RATE, resample_pcm

    pcm = _tone(1.0)
    out = resample_pcm(pcm, SAMPLE_RATE, ASR_RATE)
    duration = pcm_duration_s(out, sample_rate=ASR_RATE)
    assert abs(duration - 1.0) <= 0.02


def test_extract_sensevoice_output_text_from_stdout() -> None:
    from voice.asr import extract_sensevoice_output_text

    assert extract_sensevoice_output_text("foo\nOutput: 你好，请。\n") == "你好，请。"


def test_normalize_agent_asr_text_strips_control_and_trail() -> None:
    from voice.asr import normalize_agent_asr_text

    assert normalize_agent_asr_text("<|zh|>你好，请。") == "你好"


def test_default_model_paths_live_under_edu_models_not_old_stack() -> None:
    """运行时缺省必须在本应用 models/，不能再指向旧 microscope 树。"""
    from voice import config as voice_config

    paths = (
        voice_config.SENSEVOICE_DEMO,
        voice_config.SENSEVOICE_MODEL,
        voice_config.SENSEVOICE_TOKENS,
        voice_config.TTS_MODEL_DIR,
        voice_config.TTS_VOCODER,
    )
    for value in paths:
        assert value.startswith("/home/cat/ai-microscope-edu/models/")
        assert not value.startswith("/home/cat/microscope/")


def test_transcribe_wav_returns_empty_when_demo_missing(
    tmp_path: Path, monkeypatch
) -> None:
    from voice.asr import transcribe_wav

    monkeypatch.setattr("voice.config.SENSEVOICE_DEMO", "")
    monkeypatch.setattr("voice.config.SENSEVOICE_MODEL", "")
    monkeypatch.setattr("voice.config.SENSEVOICE_TOKENS", "")
    last = tmp_path / "last.wav"
    last.write_bytes(pcm_to_wav(_tone(0.5)))
    assert transcribe_wav(last) == ""
    assert not (tmp_path / "last_16k.wav").exists()


def test_transcribe_wav_writes_16k_sibling_and_keeps_original(
    tmp_path: Path, monkeypatch
) -> None:
    from voice.asr import ASR_RATE, transcribe_wav

    wav = pcm_to_wav(_tone(0.5))
    last = tmp_path / "last.wav"
    last.write_bytes(wav)
    original = last.read_bytes()

    demo = tmp_path / "sensevoice_demo"
    model = tmp_path / "model.rknn"
    tokens = tmp_path / "tokens.txt"
    demo.write_bytes(b"")
    model.write_bytes(b"")
    tokens.write_bytes(b"")
    monkeypatch.setattr("voice.config.SENSEVOICE_DEMO", str(demo))
    monkeypatch.setattr("voice.config.SENSEVOICE_MODEL", str(model))
    monkeypatch.setattr("voice.config.SENSEVOICE_TOKENS", str(tokens))

    captured: list[list[str]] = []

    def runner(argv: list[str], **_kwargs: object) -> subprocess.CompletedProcess[str]:
        captured.append(list(argv))
        return subprocess.CompletedProcess(
            argv, 0, stdout="Output: 你好，请。\n", stderr=""
        )

    text = transcribe_wav(last, runner=runner)
    assert text == "你好"
    assert last.read_bytes() == original
    assert captured, "应调用 sensevoice_demo"
    argv = captured[0]
    assert "--audio_path" in argv
    audio_path = Path(argv[argv.index("--audio_path") + 1])
    sixteen = tmp_path / "last_16k.wav"
    assert audio_path == sixteen
    assert sixteen.is_file()
    header = sixteen.read_bytes()
    assert struct.unpack_from("<I", header, 24)[0] == ASR_RATE
    assert argv[0] == str(demo)
    assert argv[argv.index("--language") + 1] == "auto"
    assert argv[argv.index("--use-itn") + 1] == "1"
