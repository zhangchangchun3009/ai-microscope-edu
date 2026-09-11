"""TTS：Mock 正弦、Sherpa Matcha 加载字段、float→s16le，无真机模型。"""

from __future__ import annotations

import struct
import sys
import types
from pathlib import Path

_SOFTWARE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_SOFTWARE))

from voice.wavutil import pcm_duration_s  # noqa: E402


def test_mock_tts_nonempty_text_is_about_50ms_at_22050() -> None:
    from voice.tts import TTS_RATE, MockTts

    pcm = MockTts().synthesize("甲")
    duration = pcm_duration_s(pcm, sample_rate=TTS_RATE)
    assert abs(duration - 0.05) <= 0.01
    assert len(pcm) % 2 == 0
    assert pcm_duration_s(pcm, sample_rate=TTS_RATE) > 0


def test_mock_tts_empty_text_returns_empty_bytes() -> None:
    from voice.tts import MockTts

    assert MockTts().synthesize("") == b""


def test_build_tts_returns_mock_when_sherpa_missing(monkeypatch) -> None:
    """Mac 无 sherpa-onnx 时应落到 Mock，而不是在 import 时崩。"""
    monkeypatch.setitem(sys.modules, "sherpa_onnx", None)
    from voice.tts import MockTts, build_tts

    tts = build_tts()
    assert isinstance(tts, MockTts)


def test_float_samples_to_s16le_clamps() -> None:
    from voice.tts import float_samples_to_s16le

    pcm = float_samples_to_s16le([2.0, -2.0, 0.0, 0.5])
    samples = struct.unpack("<hhhh", pcm)
    assert samples[0] == 32767
    assert samples[1] == -32767
    assert samples[2] == 0
    assert samples[3] == int(round(0.5 * 32767))


def test_sherpa_matcha_load_uses_legacy_file_fields(tmp_path: Path, monkeypatch) -> None:
    """对照旧 agent_tts_sherpa._load_matcha 的 Matcha 文件名与字段，不 import microscope。"""
    model_dir = tmp_path / "matcha-icefall-zh-baker"
    model_dir.mkdir()
    acoustic = model_dir / "model-steps-3.onnx"
    lexicon = model_dir / "lexicon.txt"
    tokens = model_dir / "tokens.txt"
    vocoder = tmp_path / "vocos-22khz-univ.onnx"
    for path in (acoustic, lexicon, tokens, vocoder):
        path.write_bytes(b"x")

    captured: dict[str, object] = {}

    class _OfflineTtsMatchaModelConfig:
        def __init__(self, **kwargs: object) -> None:
            captured["matcha"] = kwargs

    class _OfflineTtsModelConfig:
        def __init__(self, **kwargs: object) -> None:
            captured["model"] = kwargs

    class _OfflineTtsConfig:
        def __init__(self, **kwargs: object) -> None:
            captured["tts"] = kwargs

        def validate(self) -> bool:
            return True

    class _OfflineTts:
        def __init__(self, cfg: object) -> None:
            captured["engine_cfg"] = cfg

    stub = types.ModuleType("sherpa_onnx")
    stub.OfflineTtsMatchaModelConfig = _OfflineTtsMatchaModelConfig
    stub.OfflineTtsModelConfig = _OfflineTtsModelConfig
    stub.OfflineTtsConfig = _OfflineTtsConfig
    stub.OfflineTts = _OfflineTts
    monkeypatch.setitem(sys.modules, "sherpa_onnx", stub)
    monkeypatch.setattr("voice.config.TTS_MODEL_DIR", str(model_dir))
    monkeypatch.setattr("voice.config.TTS_VOCODER", str(vocoder))

    from voice.tts import SherpaTts

    SherpaTts()
    matcha = captured["matcha"]
    assert isinstance(matcha, dict)
    assert matcha["acoustic_model"] == str(acoustic)
    assert matcha["vocoder"] == str(vocoder)
    assert matcha["lexicon"] == str(lexicon)
    assert matcha["tokens"] == str(tokens)
    model = captured["model"]
    assert isinstance(model, dict)
    assert "matcha" in model
