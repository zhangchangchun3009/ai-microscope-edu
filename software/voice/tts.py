"""一句文本合成单声道 s16le PCM。不直接调用 aplay。"""

from __future__ import annotations

import logging
import math
import struct
from pathlib import Path
from typing import Any, Iterable, Protocol

from voice import config as voice_config
from voice.config import TTS_RATE

_LOG = logging.getLogger(__name__)
_MOCK_S = 0.05
_MOCK_HZ = 440.0
_MOCK_AMPLITUDE = 8000
# 对照 microscope/python/audio_service/agent_tts_sherpa.py _load_matcha，不 import microscope。
_ACOUSTIC_NAME = "model-steps-3.onnx"
_LEXICON_NAME = "lexicon.txt"
_TOKENS_NAME = "tokens.txt"
_DEFAULT_RULE_FST_NAMES = ("phone.fst", "date.fst", "number.fst")

__all__ = [
    "TTS_RATE",
    "MockTts",
    "SherpaTts",
    "TextToSpeech",
    "build_tts",
    "float_samples_to_s16le",
]


class TextToSpeech(Protocol):
    """文本合成端口；会话层按句取 PCM 再交给播放。"""

    def synthesize(self, text: str) -> bytes:
        """把一句文本合成单声道 s16le PCM。

        参数:
            text: 待朗读文本。

        返回:
            16-bit LE 单声道 PCM；空文本返回空字节。

        副作用:
            Sherpa 实现会跑本地 ONNX 推理。
        """
        ...


def float_samples_to_s16le(samples: Iterable[float]) -> bytes:
    """将 Sherpa 浮点样本钳位到 [-1, 1] 再转为 int16 LE PCM。

    参数:
        samples: 约在 [-1, 1] 的单声道浮点样本。超出范围的值钳到 ±1。

    返回:
        16-bit LE 单声道 PCM 字节。

    副作用:
        无。
    """
    out: list[int] = []
    for value in samples:
        clamped = max(-1.0, min(1.0, float(value)))
        out.append(int(max(-32768, min(32767, round(clamped * 32767.0)))))
    if not out:
        return b""
    return struct.pack("<" + "h" * len(out), *out)


class MockTts:
    """无 sherpa 时的测试替身：非空文本合成约 50 ms、22050 Hz 正弦。"""

    def synthesize(self, text: str) -> bytes:
        """对非空文本返回约 0.05 s 的 22050 Hz 正弦 PCM。

        参数:
            text: 待朗读文本；空字符串不合成。

        返回:
            单声道 s16le；空文本为 ``b""``。

        副作用:
            无。
        """
        if not text:
            return b""
        n = max(1, int(round(TTS_RATE * _MOCK_S)))
        samples = [
            int(_MOCK_AMPLITUDE * math.sin(2 * math.pi * _MOCK_HZ * i / TTS_RATE))
            for i in range(n)
        ]
        return struct.pack("<" + "h" * n, *samples)


def _import_sherpa() -> Any | None:
    """尝试导入 sherpa_onnx；未安装时返回 None。"""
    try:
        import sherpa_onnx
    except ImportError:
        return None
    return sherpa_onnx


def _resolve_rule_fsts(model_dir: Path) -> str:
    """在模型目录下探测 phone/date/number.fst，逗号拼接已存在的路径。"""
    found = [
        str(model_dir / name)
        for name in _DEFAULT_RULE_FST_NAMES
        if (model_dir / name).is_file()
    ]
    return ",".join(found)


def _resolve_rule_fars(model_dir: Path, rule_fsts: str) -> str:
    """若没有 rule_fsts 且存在 rule.far，则把它交给 OfflineTtsConfig。"""
    if rule_fsts:
        return ""
    far = model_dir / "rule.far"
    return str(far) if far.is_file() else ""


class SherpaTts:
    """Sherpa-ONNX Matcha-TTS：一句文本 → 22050 Hz 单声道 s16le。

    声学模型默认 ``model-steps-3.onnx``，vocoder 默认 ``vocos-22khz-univ.onnx``，
    字段名与旧 ``OfflineTtsMatchaModelConfig`` 一致。

    副作用:
        构造时加载 ONNX；缺包或缺文件时抛出 ImportError / FileNotFoundError。
    """

    def __init__(self) -> None:
        """加载 Matcha ONNX；缺 sherpa 或缺模型文件时抛错，由 build_tts 回退。

        副作用:
            import sherpa_onnx 并构造 OfflineTts。
        """
        sherpa_onnx = _import_sherpa()
        if sherpa_onnx is None:
            raise ImportError("sherpa-onnx 未安装")
        self._sherpa = sherpa_onnx
        self._speed = 1.0
        self._provider = "cpu"
        self._num_threads = int(voice_config.TTS_NUM_THREADS)
        self._tts = self._load_matcha(sherpa_onnx)

    def _load_matcha(self, sherpa_onnx: Any) -> Any:
        """按旧 Matcha 文件名组装 OfflineTts；缺文件时抛出 FileNotFoundError。"""
        model_dir = Path((voice_config.TTS_MODEL_DIR or "").strip())
        vocoder = Path((voice_config.TTS_VOCODER or "").strip())
        acoustic = model_dir / _ACOUSTIC_NAME
        lexicon = model_dir / _LEXICON_NAME
        tokens = model_dir / _TOKENS_NAME
        for path in (acoustic, vocoder, lexicon, tokens):
            if not path.is_file():
                raise FileNotFoundError(f"sherpa matcha tts 文件缺失: {path}")

        # 旧实现 dict_dir 可空；v1.12.15+ Matcha 内置 G2P，空串即可。
        dict_dir = ""
        rule_fsts = _resolve_rule_fsts(model_dir)
        rule_fars = _resolve_rule_fars(model_dir, rule_fsts)
        matcha_cfg = sherpa_onnx.OfflineTtsMatchaModelConfig(
            acoustic_model=str(acoustic),
            vocoder=str(vocoder),
            lexicon=str(lexicon),
            tokens=str(tokens),
            dict_dir=dict_dir,
        )
        model_cfg = sherpa_onnx.OfflineTtsModelConfig(
            matcha=matcha_cfg,
            provider=self._provider,
            num_threads=self._num_threads,
        )
        tts_cfg = sherpa_onnx.OfflineTtsConfig(
            model=model_cfg,
            rule_fsts=rule_fsts,
            rule_fars=rule_fars,
        )
        if not tts_cfg.validate():
            raise RuntimeError("sherpa matcha OfflineTtsConfig validate 失败")
        _LOG.info(
            "TTS Matcha loaded dir=%s vocoder=%s threads=%s",
            model_dir,
            vocoder,
            self._num_threads,
        )
        return sherpa_onnx.OfflineTts(tts_cfg)

    def synthesize(self, text: str) -> bytes:
        """用已加载的 Matcha 引擎合成一句 PCM。

        参数:
            text: 待朗读文本。

        返回:
            22050 Hz 单声道 s16le；空文本为 ``b""``。

        副作用:
            调用 Sherpa OfflineTts.generate。
        """
        raw = text or ""
        if not raw:
            return b""
        gen_cfg = self._sherpa.GenerationConfig()
        gen_cfg.speed = self._speed
        audio = self._tts.generate(raw, gen_cfg)
        samples = getattr(audio, "samples", None)
        if samples is None:
            raise RuntimeError("sherpa generate 未返回 samples")
        return float_samples_to_s16le(samples)


def build_tts() -> TextToSpeech:
    """构造 TTS 端口：Sherpa 可用则用 Matcha，否则 Mock。

    返回:
        ``SherpaTts`` 或 ``MockTts``。

    副作用:
        尝试 import sherpa_onnx 并加载模型文件；失败只打日志，不抛给调用方。
    """
    try:
        return SherpaTts()
    except (ImportError, FileNotFoundError, OSError, RuntimeError):
        _LOG.warning("Sherpa TTS 不可用，回退 MockTts")
        return MockTts()
