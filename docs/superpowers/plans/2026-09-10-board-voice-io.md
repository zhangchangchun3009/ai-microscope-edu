# 板载语音进出（录音回放）Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 按住 AI 浮标用板载麦录音，松开后喇叭回放原声；过短/静音/开麦失败则只播 beep。本计划不接 ASR/TTS。

**Architecture:** `voice/` 无 Qt：WAV 判定、`arecord`/`aplay`、PTT 会话。`MainWindow` 只把 `ptt_changed` 和 200 ms `tick` 接到 `VoiceSession`。回放在 `play_pcm` 内发生；真实 ALSA 可能阻塞数秒到 300 s，回放期间 `start_ptt` 必须返回 False。

**Tech Stack:** Python 3、pytest、板端 `alsa-utils`（`arecord`/`aplay`）。不新增 PyPI 依赖。

## Global Constraints

- 只改 `ai-microscope-edu/`。旧 `microscope/python/audio_service` 只读对照，不启 `audio_service`、不开 `:8098`、不用 VAD。
- 规格：[`docs/superpowers/specs/2026-09-10-board-voice-io-design.md`](../specs/2026-09-10-board-voice-io-design.md)。上限 **300 s**（不是 60 s）。过短 **&lt; 400 ms**，静音峰值 **&lt; 200**。设备默认 `plughw:0,0`，16 kHz 单声道 S16_LE。
- 学生路径不打字、不上字幕条、不接 LLM。
- Mac 用 `/usr/bin/python3 -m pytest`；无 `arecord` 时走 mock。
- 非平凡逻辑先测后写。真 ALSA 只在 211 手测。
- 未经用户明确要求不要 `git commit`。计划步骤里的 commit 一律跳过。
- 回复与源码注释用简体中文。每个对外函数/类有说明（用途、参数、返回值、副作用）。

---

## File map

| 路径 | 职责 |
|------|------|
| `software/voice/config.py` | 采样率、设备名、300 s / 400 ms / 峰值 200 |
| `software/voice/wavutil.py` | PCM↔WAV、峰值、时长、过短/静音、beep |
| `software/voice/alsa.py` | Capture/Playback 协议、mock、`arecord`/`aplay` |
| `software/voice/session.py` | `VoiceSession` |
| `software/voice/__init__.py` | 再导出 `VoiceSession`、`build_audio_io` |
| `software/tests/test_wavutil.py` | WAV 判定 |
| `software/tests/test_voice_session.py` | 会话状态机 |
| `software/app/main_window.py` | 接线 |
| `software/deploy/edu-app.service` | `SupplementaryGroups` 加 `audio` |
| `software/README.md` | 手测与 `audio` 组 |

---

### Task 1: WAV 判定与 beep

**Files:**
- Create: `ai-microscope-edu/software/voice/__init__.py`
- Create: `ai-microscope-edu/software/voice/config.py`
- Create: `ai-microscope-edu/software/voice/wavutil.py`
- Test: `ai-microscope-edu/software/tests/test_wavutil.py`

**Interfaces:**
- Consumes: 无
- Produces: `SAMPLE_RATE=16000`、`CHANNELS=1`、`MAX_RECORD_S=300.0`、`MIN_UTTERANCE_S=0.4`、`SILENCE_PEAK=200`、`pcm_to_wav`、`wav_to_pcm`、`pcm_duration_s`、`pcm_peak`、`classify_utterance` → `"ok" | "too_short" | "silent"`、`make_beep_pcm`

- [ ] **Step 1: Write the failing test**

创建 `ai-microscope-edu/software/tests/test_wavutil.py`：

```python
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
    make_beep_pcm,
    pcm_duration_s,
    pcm_peak,
    pcm_to_wav,
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd ai-microscope-edu/software && PYTHONPATH=. /usr/bin/python3 -m pytest tests/test_wavutil.py -q`

Expected: import error，`voice` 不存在。

- [ ] **Step 3: Write minimal implementation**

`voice/__init__.py`：

```python
"""板载语音：PTT 录音回放（本包不含 ASR/TTS）。"""
```

`voice/config.py`：

```python
"""板载 ALSA 与判定常量。"""

SAMPLE_RATE = 16000
CHANNELS = 1
ALSA_CAPTURE_DEVICE = "plughw:0,0"
ALSA_PLAYBACK_DEVICE = "plughw:0,0"
MAX_RECORD_S = 300.0
MIN_UTTERANCE_S = 0.4
SILENCE_PEAK = 200
NO_DATA_S = 3.0
BEEP_HZ = 880.0
BEEP_S = 0.2
BEEP_AMPLITUDE = 8000
```

`voice/wavutil.py`：标准 44 字节 PCM WAV 头；`classify_utterance` 先过短再静音；`make_beep_pcm` 用 `BEEP_HZ` / `BEEP_S` 正弦。损坏 WAV 时 `wav_to_pcm` 返回 `None`。每个函数写中文说明。

- [ ] **Step 4: Run test to verify it passes**

Run: `cd ai-microscope-edu/software && PYTHONPATH=. /usr/bin/python3 -m pytest tests/test_wavutil.py -q`

Expected: 全过。

- [ ] **Step 5: Commit**

跳过。

---

### Task 2: `VoiceSession` + mock IO

**Files:**
- Create: `ai-microscope-edu/software/voice/alsa.py`（先只放 Protocol + Mock）
- Create: `ai-microscope-edu/software/voice/session.py`
- Test: `ai-microscope-edu/software/tests/test_voice_session.py`

**Interfaces:**
- Consumes: Task 1 的 `classify_utterance`、`make_beep_pcm`、`MAX_RECORD_S`、`NO_DATA_S`、`pcm_to_wav`
- Produces:
  - `AudioCapture.start() -> bool`、`.stop() -> bytes`、`.bytes_captured() -> int`
  - `AudioPlayback.play_pcm(pcm: bytes) -> bool`
  - `MockCapture(pcm: bytes, *, start_ok: bool = True)`
  - `MockPlayback`（`played: list[bytes]`）
  - `VoiceSession(capture, playback, wav_path: Path, *, monotonic=time.monotonic)`
  - `start_ptt() -> bool`、`stop_ptt() -> str`、`tick(now: float | None = None) -> None`、`is_busy() -> bool`
  - `stop_ptt` 返回：`ignored` | `played` | `discarded` | `failed`

- [ ] **Step 1: Write the failing test**

创建 `ai-microscope-edu/software/tests/test_voice_session.py`：

```python
"""PTT 会话：忙碌忽略、300s 截断、失败不回放原声。"""

from __future__ import annotations

import math
import struct
import sys
from pathlib import Path

_SOFTWARE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_SOFTWARE))

from voice.alsa import MockCapture, MockPlayback  # noqa: E402
from voice.config import MAX_RECORD_S, SAMPLE_RATE  # noqa: E402
from voice.session import VoiceSession  # noqa: E402
from voice.wavutil import make_beep_pcm, pcm_to_wav  # noqa: E402


def _tone(seconds: float, amplitude: int = 4000) -> bytes:
    n = int(SAMPLE_RATE * seconds)
    samples = [int(amplitude * math.sin(2 * math.pi * 440 * i / SAMPLE_RATE)) for i in range(n)]
    return struct.pack("<" + "h" * n, *samples)


def _session(tmp_path: Path, pcm: bytes, *, start_ok: bool = True) -> tuple[VoiceSession, MockPlayback]:
    play = MockPlayback()
    sess = VoiceSession(
        MockCapture(pcm, start_ok=start_ok),
        play,
        tmp_path / "last.wav",
        monotonic=lambda: 0.0,
    )
    return sess, play


def test_start_while_busy_is_ignored(tmp_path: Path) -> None:
    sess, play = _session(tmp_path, _tone(0.5))
    assert sess.start_ptt() is True
    assert sess.start_ptt() is False
    assert sess.is_busy() is True
    assert play.played == []


def test_ok_utterance_writes_wav_and_plays_original(tmp_path: Path) -> None:
    pcm = _tone(0.5)
    sess, play = _session(tmp_path, pcm)
    sess.start_ptt()
    assert sess.stop_ptt() == "played"
    assert play.played == [pcm]
    assert (tmp_path / "last.wav").read_bytes() == pcm_to_wav(pcm)


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


def test_max_record_300s_auto_stop(tmp_path: Path) -> None:
    pcm = _tone(0.5)
    play = MockPlayback()
    clock = {"t": 0.0}
    sess = VoiceSession(
        MockCapture(pcm),
        play,
        tmp_path / "last.wav",
        monotonic=lambda: clock["t"],
    )
    sess.start_ptt()
    clock["t"] = MAX_RECORD_S
    sess.tick()
    assert play.played == [pcm]
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


def test_start_during_playback_is_ignored(tmp_path: Path) -> None:
    play = MockPlayback()
    sess = VoiceSession(
        MockCapture(_tone(0.5)),
        play,
        tmp_path / "last.wav",
        monotonic=lambda: 0.0,
    )
    nested = {"started": None}

    def _play(pcm: bytes) -> bool:
        nested["started"] = sess.start_ptt()
        play.played.append(pcm)
        return True

    play.play_pcm = _play  # type: ignore[method-assign]
    sess.start_ptt()
    sess.stop_ptt()
    assert nested["started"] is False
```

`MockCapture.bytes_captured`：录音中返回 `live_bytes`（默认 `len(pcm)`，无数据测例设为 0）；`stop()` 仍返回构造时的 `pcm`。

- [ ] **Step 2: Run test to verify it fails**

Run: `cd ai-microscope-edu/software && PYTHONPATH=. /usr/bin/python3 -m pytest tests/test_voice_session.py -q`

Expected: FAIL，`VoiceSession` 未定义。

- [ ] **Step 3: Write minimal implementation**

`alsa.py` 先实现 Protocol 注释、`MockCapture`、`MockPlayback`（`played: list[bytes]`，`play_pcm` 追加并返回 True）。

`session.py`：`start_ptt` 空闲且 `capture.start()` 成功才进入录音并记下 `t0`；失败则 `playback.play_pcm(make_beep_pcm())` 并保持空闲、返回 False。`stop_ptt` 非录音返回 `ignored`。录音中 `stop` 得到 PCM，`pcm_to_wav` 写入 `wav_path`（父目录 mkdir），`classify_utterance`：`ok` 则播原 PCM 返回 `played`，否则播 beep 返回 `discarded`。空 PCM 当 `failed`（也播 beep）。`tick`：录音且 `now - t0 >= MAX_RECORD_S` 则 `stop_ptt`；录音且 `now - t0 >= NO_DATA_S` 且 `bytes_captured()==0` 则停录当 `failed`。`is_busy`：录音或正在 `play_pcm`。`play_pcm` 前后把相位设为 playing / idle，以便重入 `start_ptt` 看到忙碌。

- [ ] **Step 4: Run test to verify it passes**

Run: `cd ai-microscope-edu/software && PYTHONPATH=. /usr/bin/python3 -m pytest tests/test_wavutil.py tests/test_voice_session.py -q`

Expected: 全过。

- [ ] **Step 5: Commit**

跳过。

---

### Task 3: 真 ALSA 子进程

**Files:**
- Modify: `ai-microscope-edu/software/voice/alsa.py`
- Test: `ai-microscope-edu/software/tests/test_voice_session.py`（可补 `build_audio_io` 在无 arecord 时返回 mock；不必打真设备）

**Interfaces:**
- Consumes: `config.ALSA_*`、`SAMPLE_RATE`、`CHANNELS`
- Produces: `AlsaCapture`、`AlsaPlayback`、`build_audio_io() -> tuple[AudioCapture, AudioPlayback]`

- [ ] **Step 1: Write the failing test**

在 `test_voice_session.py` 追加：

```python
def test_build_audio_io_falls_back_without_arecord(monkeypatch) -> None:
    from voice.alsa import MockCapture, build_audio_io

    monkeypatch.setattr("voice.alsa.shutil.which", lambda _name: None)
    cap, play = build_audio_io()
    assert isinstance(cap, MockCapture)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd ai-microscope-edu/software && PYTHONPATH=. /usr/bin/python3 -m pytest tests/test_voice_session.py::test_build_audio_io_falls_back_without_arecord -q`

Expected: FAIL，`build_audio_io` 未定义。

- [ ] **Step 3: Write ALSA implementation**

对照 `microscope/python/audio_service/audio_capture.py` 与 `audio_playback.py`：

- `AlsaCapture.start`：`arecord -q -D plughw:0,0 -f S16_LE -r 16000 -c 1 -t raw`，stdout 线程累加 PCM，stderr 抽空。`bytes_captured` 为已读字节。`stop`：terminate、join、返回 PCM。
- `AlsaPlayback.play_pcm`：`aplay` 同样格式；`timeout_sec = max(20.0, duration_s + 12.0)`。失败打日志返回 False。
- `build_audio_io`：`arecord` 与 `aplay` 都在 `PATH` 则返回 ALSA 对，否则 mock。

不要按帧 VAD 队列。

- [ ] **Step 4: Run tests**

Run: `cd ai-microscope-edu/software && PYTHONPATH=. /usr/bin/python3 -m pytest tests/test_wavutil.py tests/test_voice_session.py -q`

Expected: 全过。

- [ ] **Step 5: Commit**

跳过。

---

### Task 4: 接到浮标与 systemd

**Files:**
- Modify: `ai-microscope-edu/software/app/main_window.py`
- Modify: `ai-microscope-edu/software/deploy/edu-app.service`
- Modify: `ai-microscope-edu/software/README.md`
- Modify: `ai-microscope-edu/software/voice/__init__.py`

**Interfaces:**
- Consumes: `VoiceSession`、`build_audio_io`
- Produces: 浮标 PTT → 会话；200 ms `QTimer` 调 `tick`

- [ ] **Step 1: Wire MainWindow**

在 `MainWindow.__init__`：`cap, play = build_audio_io()`；`self._voice = VoiceSession(cap, play, Path(__file__).resolve().parents[1] / "var" / "voice" / "last.wav")`。`self._fab.ptt_changed` **额外**连接 `_on_ptt`（保留现有 `set_ptt_active`）：

```python
def _on_ptt(self, active: bool) -> None:
    if active:
        self._voice.start_ptt()
    else:
        self._voice.stop_ptt()
```

`QTimer` interval 200，`timeout` → `self._voice.tick()`。关闭窗口先 `stop_ptt` 以免 arecord 残留。

`voice/__init__.py` 导出 `VoiceSession`、`build_audio_io`。

- [ ] **Step 2: systemd + README**

`edu-app.service`：`SupplementaryGroups=video render input audio`

README 增加：板端 `groups` 含 `audio`，否则 `sudo usermod -aG audio cat` 后重新登录/重启服务。手测：按住说话松开应听到原声；捂麦应只听到 beep。录音上限 300 s。rsync 命令不变。

- [ ] **Step 3: Run unit tests**

Run: `cd ai-microscope-edu/software && PYTHONPATH=. /usr/bin/python3 -m pytest tests/ -q`

Expected: 既有壳层测试 + 新语音测试全过；缺 PySide6 的仍 skip。

- [ ] **Step 4: Commit**

跳过。211 部署等用户说「同步」再 rsync，并确认 `id cat` 含 `audio`。

---

## Spec coverage

| spec | 任务 |
|------|------|
| `plughw:0,0` 16 kHz 单声道 arecord/aplay | Task 3 |
| 不启 audio_service / 不用 VAD | 全局约束 |
| PTT 开录、忙忽略、半双工 | Task 2、4 |
| 300 s 截断仍判定 | Task 2 |
| 过短 400 ms、峰值 200 | Task 1–2 |
| last.wav 覆盖 | Task 2 |
| 失败 beep 200 ms 880 Hz | Task 1–2 |
| 3 s 无数据失败 | Task 2 |
| systemd `audio` 组 | Task 4 |
| Mac mock pytest | Task 1–3 |
| ASR/TTS 不实现 | 无对应任务 |

## 非目标

SenseVoice、Sherpa、字幕、设置页、旋转、相机。
