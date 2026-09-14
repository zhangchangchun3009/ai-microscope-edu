"""PCM 与 WAV 互转、时长/峰值分析与 utterance 判定。"""

from __future__ import annotations

import math
import struct
from typing import Literal

try:
    import audioop
except ImportError:  # pragma: no cover — 3.13+ 无 audioop 时走纯 Python。
    audioop = None  # type: ignore[assignment]

from voice.config import (
    BEEP_AMPLITUDE,
    BEEP_HZ,
    BEEP_S,
    CHANNELS,
    ECHO_MAX_GAIN,
    ECHO_TARGET_PEAK,
    GATE_CLOSE_RATIO,
    GATE_FRAME_S,
    GATE_HANG_S,
    GATE_MIN_SPEECH_RATIO,
    GATE_NOISE_PERCENTILE,
    GATE_OPEN_FLOOR,
    GATE_OPEN_RATIO,
    GATE_SKIP_LEAD_S,
    MIN_UTTERANCE_S,
    SAMPLE_RATE,
    SILENCE_PEAK,
)

UtteranceClass = Literal["ok", "too_short", "silent"]

_WAV_HEADER_SIZE = 44
_BYTES_PER_SAMPLE = 2  # int16 mono


def pcm_to_wav(pcm: bytes, sample_rate: int = SAMPLE_RATE, channels: int = CHANNELS) -> bytes:
    """将原始 PCM（int16 LE）封装为标准 44 字节头的 WAV。

    参数:
        pcm: 16-bit 小端单声道 PCM 字节流。
        sample_rate: 采样率（Hz），默认取 config.SAMPLE_RATE。
        channels: 声道数，默认 1。

    返回:
        完整 WAV 文件字节（含 RIFF 头）。

    副作用:
        无。
    """
    data_size = len(pcm)
    byte_rate = sample_rate * channels * _BYTES_PER_SAMPLE
    block_align = channels * _BYTES_PER_SAMPLE
    riff_size = 36 + data_size

    header = struct.pack(
        "<4sI4s4sIHHIIHH4sI",
        b"RIFF",
        riff_size,
        b"WAVE",
        b"fmt ",
        16,  # fmt chunk size
        1,  # PCM
        channels,
        sample_rate,
        byte_rate,
        block_align,
        16,  # bits per sample
        b"data",
        data_size,
    )
    return header + pcm


def wav_to_pcm(wav: bytes) -> bytes | None:
    """从 WAV 字节流提取 PCM 载荷；格式不符或损坏时返回 None。

    参数:
        wav: 完整 WAV 文件字节。

    返回:
        16-bit LE PCM 字节流，或 None（非 RIFF/WAVE、头长度不足、data 越界等）。

    副作用:
        无。
    """
    if len(wav) < _WAV_HEADER_SIZE:
        return None
    if wav[:4] != b"RIFF" or wav[8:12] != b"WAVE":
        return None

    # 标准 PCM WAV：fmt 在偏移 12，data 子块紧跟 44 字节头
    if wav[12:16] != b"fmt ":
        return None
    fmt_size = struct.unpack_from("<I", wav, 16)[0]
    if fmt_size < 16:
        return None

    data_offset = 12 + 8 + fmt_size
    # 对齐到偶数字节（部分 WAV 在 fmt 与 data 间有填充）
    if data_offset > len(wav):
        return None

    # 查找 data 子块（允许 fmt 后有额外 chunk）
    pos = 12
    while pos + 8 <= len(wav):
        chunk_id = wav[pos : pos + 4]
        chunk_size = struct.unpack_from("<I", wav, pos + 4)[0]
        if chunk_id == b"data":
            start = pos + 8
            end = start + chunk_size
            if end > len(wav):
                return None
            return wav[start:end]
        pos += 8 + chunk_size
        if chunk_size % 2:
            pos += 1

    return None


def resample_pcm(pcm: bytes, src_rate: int, dst_rate: int) -> bytes:
    """将 int16 LE 单声道 PCM 线性插值重采样。

    参数:
        pcm: 16-bit 小端单声道 PCM。
        src_rate: 源采样率（Hz）。
        dst_rate: 目标采样率（Hz）。

    返回:
        重采样后的 PCM。空输入或非法采样率返回空字节；源/目标相同则原样返回。

    副作用:
        无。
    """
    if not pcm or src_rate <= 0 or dst_rate <= 0:
        return b""
    n_src = len(pcm) // _BYTES_PER_SAMPLE
    if n_src == 0:
        return b""
    if src_rate == dst_rate:
        return pcm[: n_src * _BYTES_PER_SAMPLE]
    raw = pcm[: n_src * _BYTES_PER_SAMPLE]
    if audioop is not None:
        converted, _state = audioop.ratecv(raw, 2, 1, src_rate, dst_rate, None)
        return converted
    samples = struct.unpack_from("<" + "h" * n_src, pcm)
    n_dst = int(round(n_src * dst_rate / src_rate))
    if n_dst <= 0:
        return b""
    last = n_src - 1
    out: list[int] = []
    for i in range(n_dst):
        src_index = i * src_rate / dst_rate
        left = int(src_index)
        if left >= last:
            out.append(samples[last])
            continue
        frac = src_index - left
        interpolated = samples[left] * (1.0 - frac) + samples[left + 1] * frac
        out.append(int(max(-32768, min(32767, round(interpolated)))))
    return struct.pack("<" + "h" * n_dst, *out)


def scale_pcm(pcm: bytes, gain: float) -> bytes:
    """按线性增益缩放 int16 LE PCM。

    参数:
        pcm: 16-bit 小端 PCM。
        gain: 乘数；1.0 原样返回。小于 0 按 0 处理。

    返回:
        缩放后的 PCM；空输入返回空字节。

    副作用:
        无。
    """
    if not pcm:
        return b""
    if len(pcm) % _BYTES_PER_SAMPLE:
        return pcm
    factor = max(0.0, float(gain))
    if factor == 1.0:
        return pcm
    if audioop is not None:
        return audioop.mul(pcm, 2, factor)
    n = len(pcm) // _BYTES_PER_SAMPLE
    samples = struct.unpack_from("<" + "h" * n, pcm)
    out = [
        int(max(-32768, min(32767, round(value * factor))))
        for value in samples
    ]
    return struct.pack("<" + "h" * n, *out)


def pcm_duration_s(pcm: bytes, sample_rate: int = SAMPLE_RATE, channels: int = CHANNELS) -> float:
    """根据 PCM 字节长度计算时长（秒）。

    参数:
        pcm: 16-bit LE PCM。
        sample_rate: 采样率（Hz）。
        channels: 声道数。

    返回:
        时长（秒）；空 PCM 返回 0.0。

    副作用:
        无。
    """
    if not pcm:
        return 0.0
    n_samples = len(pcm) // (_BYTES_PER_SAMPLE * channels)
    return n_samples / sample_rate


def pcm_peak(pcm: bytes) -> int:
    """返回 PCM 样本绝对值的最大值。

    参数:
        pcm: 16-bit LE PCM。

    返回:
        峰值（0 表示空或全零）；空输入返回 0。

    副作用:
        无。
    """
    if not pcm:
        return 0
    n = len(pcm) // _BYTES_PER_SAMPLE
    if n == 0:
        return 0
    samples = struct.iter_unpack("<h", memoryview(pcm)[: n * _BYTES_PER_SAMPLE])
    return max(abs(sample[0]) for sample in samples)


def classify_utterance(pcm: bytes) -> UtteranceClass:
    """判定录音片段是否可用：先检查过短，再检查静音。

    参数:
        pcm: 16-bit LE 单声道 PCM。

    返回:
        "too_short" — 时长 < MIN_UTTERANCE_S；
        "silent" — 峰值 < SILENCE_PEAK（且时长已达标）；
        "ok" — 其余情况。

    副作用:
        无。
    """
    if pcm_duration_s(pcm) < MIN_UTTERANCE_S:
        return "too_short"
    if pcm_peak(pcm) < SILENCE_PEAK:
        return "silent"
    return "ok"


def amplify_pcm(
    pcm: bytes,
    *,
    target_peak: int = ECHO_TARGET_PEAK,
    max_gain: float = ECHO_MAX_GAIN,
) -> bytes:
    """按峰值放大 PCM，供回放听清安静的板载麦录音。

    参数:
        pcm: 16-bit LE PCM。
        target_peak: 希望达到的绝对值峰值，不超过 32767。
        max_gain: 放大倍数上限，避免把底噪抬成破音。

    返回:
        放大后的 PCM；空输入、峰值已够或增益≤1 时返回原文。

    副作用:
        无。落盘的 last.wav 不应走此函数，以免下一刀 ASR 吃到被抬过的电平。
    """
    if not pcm:
        return pcm
    peak = pcm_peak(pcm)
    if peak <= 0:
        return pcm
    goal = min(int(target_peak), 32767)
    gain = min(goal / float(peak), float(max_gain))
    if gain <= 1.01:
        return pcm
    n = len(pcm) // _BYTES_PER_SAMPLE
    samples = struct.iter_unpack("<h", memoryview(pcm)[: n * _BYTES_PER_SAMPLE])
    out = [
        int(max(-32768, min(32767, round(sample[0] * gain))))
        for sample in samples
    ]
    return struct.pack("<" + "h" * n, *out)


def _percentile(values: list[float], q: float) -> float:
    """返回已排序样本的分位值；空列表返回 0。"""
    if not values:
        return 0.0
    ordered = sorted(values)
    index = int(round(q * (len(ordered) - 1)))
    index = max(0, min(index, len(ordered) - 1))
    return ordered[index]


def _frame_rms(samples: list[int], start: int, end: int) -> float:
    """计算半开区间 [start, end) 的 RMS。"""
    length = end - start
    if length <= 0:
        return 0.0
    total = 0.0
    for index in range(start, end):
        value = samples[index]
        total += value * value
    return math.sqrt(total / length)


def gate_pcm(pcm: bytes) -> bytes:
    """按帧能量做滞后噪声门，压掉桌面传来的打印机/机柜底噪。

    参数:
        pcm: 16-bit LE 单声道 PCM。

    返回:
        与输入等长的 PCM。低于关门阈值的帧置零；人声与底噪分不开时
        返回原文。开头 ``GATE_SKIP_LEAD_S`` 不参与噪声估计（开麦未稳）。

    副作用:
        无。只应作用在回放路径；落盘 last.wav 保持原电平。
    """
    n = len(pcm) // _BYTES_PER_SAMPLE
    if n == 0:
        return pcm
    samples = list(struct.unpack_from("<" + "h" * n, pcm))
    frame_n = max(1, int(SAMPLE_RATE * GATE_FRAME_S))
    skip_n = int(SAMPLE_RATE * GATE_SKIP_LEAD_S)
    hang_frames = max(1, int(round(GATE_HANG_S / GATE_FRAME_S)))

    bounds: list[tuple[int, int]] = []
    start = 0
    while start < n:
        end = min(start + frame_n, n)
        bounds.append((start, end))
        start = end

    rms_list = [_frame_rms(samples, start, end) for start, end in bounds]
    noise_rms = [
        rms
        for (start, _end), rms in zip(bounds, rms_list)
        if start >= skip_n
    ]
    noise = _percentile(noise_rms, GATE_NOISE_PERCENTILE)
    peak_rms = max(rms_list) if rms_list else 0.0
    if noise <= 0.0 or peak_rms < GATE_MIN_SPEECH_RATIO * noise:
        return pcm

    open_th = max(GATE_OPEN_RATIO * noise, GATE_OPEN_FLOOR)
    close_th = GATE_CLOSE_RATIO * noise
    opened = False
    hang_left = 0
    gated = list(samples)
    for (start, end), rms in zip(bounds, rms_list):
        if rms >= open_th:
            opened = True
            hang_left = hang_frames
        elif opened and rms >= close_th:
            hang_left = hang_frames
        elif opened and hang_left > 0:
            hang_left -= 1
        else:
            opened = False
            hang_left = 0
            for index in range(start, end):
                gated[index] = 0
    return struct.pack("<" + "h" * n, *gated)


def upmix_mono_to_stereo(pcm: bytes) -> bytes:
    """把单声道 s16le 复制到左右声道，供 ES8388 按立体声帧播放。

    参数:
        pcm: 16-bit LE 单声道 PCM。

    返回:
        交织后的立体声 PCM（L=R）；空输入返回原文。

    副作用:
        无。板上实测：2 秒单声道用 ``-c 1`` 约 1.1 秒播完；左右复制后
        ``-c 2`` 回到约 2.2 秒，音调不再被抬高一个八度。
    """
    n = len(pcm) // _BYTES_PER_SAMPLE
    if n == 0:
        return pcm
    samples = struct.unpack_from("<" + "h" * n, pcm)
    interleaved = [sample for sample in samples for _ in range(2)]
    return struct.pack("<" + "h" * (n * 2), *interleaved)


def make_beep_pcm() -> bytes:
    """生成短促提示音 PCM（正弦波，参数见 config.BEEP_*）。

    返回:
        16-bit LE 单声道 PCM，时长 BEEP_S 秒。

    副作用:
        无。
    """
    n = int(SAMPLE_RATE * BEEP_S)
    samples = [
        int(BEEP_AMPLITUDE * math.sin(2 * math.pi * BEEP_HZ * i / SAMPLE_RATE))
        for i in range(n)
    ]
    return struct.pack("<" + "h" * n, *samples)
