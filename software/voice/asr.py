"""SenseVoice ASR：44100→16 kHz 重采样、demo 调用与 Output 解析。"""

from __future__ import annotations

import logging
import re
import subprocess
from pathlib import Path
from typing import Callable

from voice import config as voice_config
from voice.config import ASR_RATE, ASR_TIMEOUT_S, SAMPLE_RATE
from voice.wavutil import pcm_to_wav, resample_pcm, wav_to_pcm

_LOG = logging.getLogger(__name__)
_OUTPUT_PREFIX = "Output:"
_LAST_16K_NAME = "last_16k.wav"
# 对照 microscope/python/common/sensevoice_asr.py，不 import microscope。
_CONTROL_TOKEN_RE = re.compile(r"<\|[^|]+?\|>")
_AGENT_TRAIL_JUNK_RE = re.compile(r"(?:[，,]\s*)?请\s*[。！？!?…\.]*\s*$")
_AGENT_TRAIL_PUNCT_RE = re.compile(r"[，,。.!！?？、…]+\s*$")

Runner = Callable[..., subprocess.CompletedProcess[str]]

__all__ = [
    "ASR_RATE",
    "extract_sensevoice_output_text",
    "normalize_agent_asr_text",
    "resample_pcm",
    "transcribe_wav",
]


def extract_sensevoice_output_text(stdout_text: str) -> str | None:
    """从 demo 标准输出中解析 ``Output:`` 行文本。

    参数:
        stdout_text: sensevoice_demo 的完整 stdout。

    返回:
        第一条 ``Output:`` 行冒号后的去空白文本；没有该行则 ``None``。

    副作用:
        无。
    """
    for line in stdout_text.splitlines():
        if line.startswith(_OUTPUT_PREFIX):
            return line.split(_OUTPUT_PREFIX, 1)[1].strip()
    return None


def normalize_asr_text(raw_text: str) -> str:
    """去掉 SenseVoice 控制标记并规整空白。

    参数:
        raw_text: demo 原始识别文本。

    返回:
        去掉 ``<|…|>`` 后压缩空白的字符串。

    副作用:
        无。
    """
    text = _CONTROL_TOKEN_RE.sub("", raw_text).strip()
    return re.sub(r"\s+", " ", text)


def normalize_agent_asr_text(raw_text: str) -> str:
    """PTT 专用：去掉控制标记与尾部 ITN/幻听垃圾。

    参数:
        raw_text: demo 原始识别文本，例如 ``<|zh|>你好，请。``。

    返回:
        主干文本。典型误识别「你好，请。」「拍一张照，。」只留命令词。

    副作用:
        无。
    """
    text = normalize_asr_text(raw_text)
    text = _AGENT_TRAIL_JUNK_RE.sub("", text)
    text = _AGENT_TRAIL_PUNCT_RE.sub("", text)
    return text.strip()


def transcribe_wav(
    path: Path,
    *,
    runner: Runner = subprocess.run,
) -> str:
    """识别一段 WAV：重采样后调用 sensevoice_demo，失败返回空串。

    参数:
        path: 原始录音 WAV（通常为 ``last.wav``，44100 Hz）。不改此文件。
        runner: 子进程入口，默认 ``subprocess.run``，测试可注入。

    返回:
        清理后的识别文本。demo/模型/tokens 缺路径或缺文件、非零退出、
        无 ``Output:``、空文本或任何异常时返回 ``""``（会话层据此 beep）。

    副作用:
        在 ``path`` 同目录写入 ``last_16k.wav``（仅在配置齐全且 WAV 可读时）。
        不修改 ``path`` 原文件字节。
    """
    try:
        return _transcribe_wav(path, runner=runner)
    except Exception:
        _LOG.exception("ASR 失败 path=%s", path)
        return ""


def _transcribe_wav(path: Path, *, runner: Runner) -> str:
    """``transcribe_wav`` 的内部实现；异常由调用方吞掉。"""
    demo = (voice_config.SENSEVOICE_DEMO or "").strip()
    model = (voice_config.SENSEVOICE_MODEL or "").strip()
    tokens = (voice_config.SENSEVOICE_TOKENS or "").strip()
    if not demo or not model or not tokens:
        return ""
    demo_path = Path(demo)
    model_path = Path(model)
    tokens_path = Path(tokens)
    if not demo_path.is_file() or not model_path.is_file() or not tokens_path.is_file():
        return ""
    if not path.is_file():
        return ""
    wav = path.read_bytes()
    pcm = wav_to_pcm(wav)
    if pcm is None:
        return ""
    pcm_16k = resample_pcm(pcm, SAMPLE_RATE, ASR_RATE)
    out_path = path.parent / _LAST_16K_NAME
    out_path.write_bytes(pcm_to_wav(pcm_16k, sample_rate=ASR_RATE))
    cmd = [
        str(demo_path),
        "-m",
        str(model_path),
        "--tokens",
        str(tokens_path),
        "--audio_path",
        str(out_path),
        "--language",
        "auto",
        "--use-itn",
        "1",
    ]
    ret = runner(
        cmd,
        check=False,
        capture_output=True,
        text=True,
        timeout=ASR_TIMEOUT_S,
        cwd=str(demo_path.resolve().parent),
    )
    if getattr(ret, "returncode", 1) != 0:
        return ""
    raw = extract_sensevoice_output_text(getattr(ret, "stdout", "") or "")
    if raw is None:
        return ""
    text = normalize_agent_asr_text(raw)
    if not text or text.lower() == "no speech detected":
        return ""
    return text
