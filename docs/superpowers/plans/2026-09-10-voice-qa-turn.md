# 语音问答一轮 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 按住浮标说完后：SenseVoice 识别 `last.wav`，流式快速问答，分句入队（开播水位 2、预取 3），串行 TTS 播完；失败只 beep。不再回放原声。

**Architecture:** `qa/` 无 Qt：分句队列、prompt、空知识库、SSE 客户端、8 轮记忆。`voice/asr.py` / `voice/tts.py` 对照旧板端子进程/Sherpa。`VoiceSession` 在判定 ok 后跑回合（测试里同步；主窗把 `stop_ptt` 放到工作线程以免冻 linuxfb）。浮标在 **松开之后到队列播完** 禁用（按住期间保持可收抬手，否则 Qt 会丢 `mouseRelease`）。

**Tech Stack:** Python 3、pytest、板端 `sensevoice_demo` + `sherpa-onnx` Matcha、标准库 `urllib` 读 SSE。不引入 MCP / rmcp。

## Global Constraints

- 只改 `ai-microscope-edu/`。不改 `microclaw/`、`microscope/` 源码；不 import `microscope` 包。
- 规格：[`docs/superpowers/specs/2026-09-10-voice-qa-turn-design.md`](../specs/2026-09-10-voice-qa-turn-design.md)。
- 不启 `audio_service`、不开 `:8098`、不用 VAD、不建 SQLite 知识库、不画字幕、不送预览图。
- `last.wav` 保持 44100 单声道原电平；送给 SenseVoice 的是临时 16 kHz 文件。
- 学生不打字。回复与源码注释用简体中文。对外函数/类写用途、参数、返回值、副作用。
- Mac：`cd ai-microscope-edu/software && PYTHONPATH=. /usr/bin/python3 -m pytest tests/ -q`
- 未经用户明确要求不要 `git commit`。下列 Commit 步骤一律跳过。
- 单文件 < 1000 行；入口只调度。

---

## File map

| 路径 | 职责 |
|------|------|
| `software/qa/__init__.py` | 再导出本刀需要的类型 |
| `software/qa/sentences.py` | 增量分句、短句合并、开播水位 |
| `software/qa/knowledge.py` | `KnowledgeRecall` + `EmptyRecall` |
| `software/qa/prompt.py` | system / KB 前缀 / user |
| `software/qa/memory.py` | 8 轮 + 20 分钟切场 |
| `software/qa/client.py` | SSE + 非流式回退 |
| `software/qa/config.py` | USER.md 路径、轮次、超时、水位常数 |
| `software/voice/asr.py` | 重采样 + `sensevoice_demo` |
| `software/voice/tts.py` | 一句文本 → PCM（Matcha / mock） |
| `software/voice/session.py` | 去掉回放原声，接 ASR→QA→队列 TTS |
| `software/voice/alsa.py` | `play_pcm(..., sample_rate=)` 给 22050 |
| `software/app/main_window.py` | 工作线程跑 `stop_ptt`；按 busy 禁用浮标 |
| `software/app/ai_fab.py` | 禁用态绘制 |
| `software/tests/test_sentences.py` 等 | 各任务单测 |
| `software/README.md` | 211 手测与 `llm.json` |

对照（只读）：`microscope/python/common/sensevoice_asr.py`、`audio_service/agent_tts_sherpa.py`。

---

### Task 1: 分句、短句合并、开播水位

**Files:**
- Create: `ai-microscope-edu/software/qa/__init__.py`
- Create: `ai-microscope-edu/software/qa/config.py`
- Create: `ai-microscope-edu/software/qa/sentences.py`
- Test: `ai-microscope-edu/software/tests/test_sentences.py`

**Interfaces:**
- Consumes: 无
- Produces:
  - `PLAY_START_WATERMARK = 2`
  - `SHORT_SENTENCE_CHARS = 8`
  - `SentenceSplitter.push(chunk: str) -> list[str]` / `finish() -> list[str]`
  - `merge_short_sentences(parts: list[str], *, producer_done: bool, min_chars: int = 8) -> list[str]`
  - `ready_to_play(queued: int, producer_done: bool, watermark: int = 2) -> bool`

- [ ] **Step 1: Write the failing test**

创建 `ai-microscope-edu/software/tests/test_sentences.py`：

```python
"""流式分句、短句合并与开播水位，无网络。"""

from __future__ import annotations

import sys
from pathlib import Path

_SOFTWARE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_SOFTWARE))

from qa.sentences import (  # noqa: E402
    SentenceSplitter,
    merge_short_sentences,
    ready_to_play,
)


def test_split_on_full_stop_keeps_punct() -> None:
    sp = SentenceSplitter()
    assert sp.push("你好。世界！") == ["你好。"]
    assert sp.finish() == ["世界！"]


def test_comma_does_not_split() -> None:
    sp = SentenceSplitter()
    assert sp.push("细胞壁，细胞膜") == []
    assert sp.finish() == ["细胞壁，细胞膜"]


def test_newline_splits() -> None:
    sp = SentenceSplitter()
    assert sp.push("甲\n乙") == ["甲"]
    assert sp.finish() == ["乙"]


def test_merge_short_with_following_sentence() -> None:
    out = merge_short_sentences(["好。", "这是洋葱。"], producer_done=False)
    assert out == ["好。这是洋葱。"]


def test_short_alone_when_producer_done_is_kept() -> None:
    assert merge_short_sentences(["好。"], producer_done=True) == ["好。"]


def test_ready_to_play_waits_for_two_until_done() -> None:
    assert ready_to_play(1, False) is False
    assert ready_to_play(2, False) is True
    assert ready_to_play(1, True) is True
    assert ready_to_play(0, True) is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd ai-microscope-edu/software && PYTHONPATH=. /usr/bin/python3 -m pytest tests/test_sentences.py -q`

Expected: FAIL collecting or import error（还没有 `qa.sentences`）

- [ ] **Step 3: Write minimal implementation**

`qa/config.py`：

```python
"""快速问答常量。"""

USER_MD_MAX_CHARS = 1000
MAX_TURNS = 8
IDLE_NEW_SESSION_S = 20 * 60.0
DEFAULT_LLM_TIMEOUT_S = 30.0
PLAY_START_WATERMARK = 2
SHORT_SENTENCE_CHARS = 8
QA_ROLE_CORE = "你只回答生物学和显微镜观察相关的问题。\n当前时间：{datetime}"
```

`qa/sentences.py`：句末切分字符集合 `。！？!?` 以及 `\n`；`push` 把切出的完整句 return，尾巴留在 `_buf`。`merge_short_sentences` 从左到右：若当前句去掉空白和 `。！？!?.,` 后长度 `< min_chars` 且后面还有元素，则与下一句拼接；`producer_done` 且无下一句则保留。`ready_to_play`：`queued <= 0` 为 False；`producer_done` 时 `queued >= 1`；否则 `queued >= watermark`。

`qa/__init__.py` 可先空或再导出上述符号。

- [ ] **Step 4: Run tests**

Run: `cd ai-microscope-edu/software && PYTHONPATH=. /usr/bin/python3 -m pytest tests/test_sentences.py -q`

Expected: PASS

- [ ] **Step 5: Commit** — 跳过

---

### Task 2: prompt、空知识库、8 轮记忆

**Files:**
- Create: `ai-microscope-edu/software/qa/knowledge.py`
- Create: `ai-microscope-edu/software/qa/prompt.py`
- Create: `ai-microscope-edu/software/qa/memory.py`
- Test: `ai-microscope-edu/software/tests/test_qa_prompt.py`

**Interfaces:**
- Consumes: `qa.config.QA_ROLE_CORE`、`USER_MD_MAX_CHARS`、`MAX_TURNS`、`IDLE_NEW_SESSION_S`
- Produces:
  - `KnowledgeRecall.lookup(self, text: str) -> str`
  - `EmptyRecall.lookup` 恒 `""`
  - `build_system_prompt(now: datetime, user_md: str) -> str`
  - `build_user_message(knowledge: str, user_text: str) -> str`
  - `QaMemory.append_turn(user: str, assistant: str)`；`messages() -> list[dict[str, str]]`（`role`/`content`）；`touch(now)` 若空闲超过 20 分钟则清空再记

- [ ] **Step 1: Write the failing test**

`tests/test_qa_prompt.py`：`EmptyRecall` 时 `build_user_message` 等于原文；假 `lookup` 非空时前缀+原文；`build_system_prompt` 含 `2026-09-10 19:00:00` 且 USER.md 截到 1000 字。记忆：注入 `monotonic` 时钟，append 9 轮后第一条 user 是 `u1`、共 16 条 message；`clock["t"] = 20*60+1` 后 `touch()` 清空。

- [ ] **Step 2: Run to see fail**

`pytest tests/test_qa_prompt.py -q` → import fail

- [ ] **Step 3: Implement**

`knowledge.py`：`Protocol` + `EmptyRecall`。

`prompt.py`：`build_system_prompt` 用 `QA_ROLE_CORE.replace("{datetime}", now.strftime("%Y-%m-%d %H:%M:%S"))`，非空 `user_md` 截断 `USER_MD_MAX_CHARS` 后追加 `\n\n` + 正文。`build_user_message`：knowledge 去空白后若空则返回 `user_text`，否则 `f"{knowledge.rstrip()}\n{user_text}"`。

`memory.py`：内部 `list[tuple[str,str]]`，`append_turn` 先 `touch()` 再追加，只留最后 `MAX_TURNS` 轮。`messages()` 展开为 user/assistant dict。`touch()`：若已有内容且 `now - last_activity >= IDLE_NEW_SESSION_S` 则清空；然后更新 `last_activity`。

- [ ] **Step 4: pytest tests/test_qa_prompt.py -q** → PASS

- [ ] **Step 5: Commit** — 跳过

---

### Task 3: 非流式回退 + SSE 流式客户端

**Files:**
- Create: `ai-microscope-edu/software/qa/client.py`
- Test: `ai-microscope-edu/software/tests/test_qa_client.py`

**Interfaces:**
- Consumes: `qa.config.DEFAULT_LLM_TIMEOUT_S`
- Produces:
  - `LlmConfig(base_url: str, api_key: str, model: str, timeout_s: float)`
  - `load_llm_config(path: Path, environ: Mapping[str, str]) -> LlmConfig | None`（`EDU_LLM_BASE_URL` / `EDU_LLM_API_KEY` / `EDU_LLM_MODEL` 覆盖 json）
  - `iter_chat_tokens(config, messages: list[dict[str, str]]) -> Iterator[str]`：先 POST `stream=true`，解析 `data:` JSON 的 `choices[0].delta.content`；`data: [DONE]` 结束。失败则再 POST `stream=false`，yield 完整 `choices[0].message.content`（一次或按字符都行，测例按 join 断言）。请求 JSON 含 `"enable_thinking": false`。超时 / HTTP 错 / 无配置：抛 `QaClientError`

- [ ] **Step 1: Failing tests**

用 `unittest.mock.patch("qa.client.urllib.request.urlopen", ...)`。第一次 urlopen 抛 `OSError`，第二次返回 `io.BytesIO` 包一层有 `.read()` 和 `status=200` 的假响应，body 为 `{"choices":[{"message":{"content":"整段回答。"}}]}`，断言 `"".join(iter_chat_tokens(...)) == "整段回答。"`。

另一测例：第一次 urlopen 返回 SSE：

```
data: {"choices":[{"delta":{"content":"你"}}]}

data: {"choices":[{"delta":{"content":"好。"}}]}

data: [DONE]

```

断言 join == `"你好。"`。请求体 `json.loads` 后 `enable_thinking is False`。

`load_llm_config`：空文件目录返回 None；环境变量三件套可组成 config。

- [ ] **Step 2: pytest tests/test_qa_client.py -q** → FAIL

- [ ] **Step 3: Implement `client.py`**

`POST {base_url}/chat/completions`（若 `base_url` 已含该路径则不要重复拼接：若 `base_url.rstrip("/").endswith("chat/completions")` 则原样，否则 `rstrip("/") + "/chat/completions"`）。Header `Authorization: Bearer {api_key}`、`Content-Type: application/json`。`timeout` 用 `urllib` 的 `timeout=`。读 SSE：按行，`line.startswith("data:")` 后 strip，`[DONE]` 停止，否则 `json.loads` 取 delta。非流式：`json.loads(body)`。不要新增 PyPI 依赖。

- [ ] **Step 4: pytest … PASS**

- [ ] **Step 5: Commit** — 跳过

---

### Task 4: ASR 重采样与 demo 解析

**Files:**
- Create: `ai-microscope-edu/software/voice/asr.py`
- Modify: `ai-microscope-edu/software/voice/config.py`（ASR 路径常量）
- Test: `ai-microscope-edu/software/tests/test_asr.py`

**Interfaces:**
- Consumes: `voice.wavutil.pcm_to_wav` / `wav_to_pcm`；`SAMPLE_RATE=44100`
- Produces:
  - `ASR_RATE = 16000`
  - `resample_pcm(pcm: bytes, src_rate: int, dst_rate: int) -> bytes`（线性插值 int16）
  - `extract_sensevoice_output_text(stdout: str) -> str | None`
  - `normalize_agent_asr_text(raw: str) -> str`（对照旧 `sensevoice_asr.py` 的控制标记与「，请。」尾巴）
  - `transcribe_wav(path: Path, *, runner=subprocess.run) -> str`：读 wav，不改原文件；写同目录 `last_16k.wav` 临时文件；调用 `sensevoice_demo -m … --audio_path … --language auto --use-itn 1`；解析 Output。demo 不存在或 rc≠0 或空文本：返回 `""` 或抛错——**统一返回 `""`** 好让会话 beep，不要把异常漏到 GUI。配置缺文件同样 `""`。

对照 argv 与 `Output:` 解析抄 `microscope/python/common/sensevoice_asr.py`，把正则拷进 `voice/asr.py`，不要 import microscope。

默认路径（板 211 现网，可用环境变量 `EDU_SENSEVOICE_DEMO` 等覆盖）：

- demo: `/opt/sensevoice/sensevoice_demo` 若计划执行时发现 211 实际路径不同，以板上 `which` / 旧 yaml 为准，写进 `voice/config.py` 注释。先在 Task 4 用常量 `SENSEVOICE_DEMO`、`SENSEVOICE_MODEL`、`SENSEVOICE_TOKENS`，缺省为空字符串；空则 `transcribe_wav` 返回 `""`（Mac）。

- [ ] **Step 1: Tests**

- 1 秒 44100 正弦 → 16000 后 `pcm_duration_s(..., sample_rate=16000)` 约 1.0（允许 ±20 ms）
- `extract_sensevoice_output_text("foo\nOutput: 你好，请。\n") == "你好，请。"`
- `normalize_agent_asr_text("<|zh|>你好，请。") == "你好"`
- monkeypatch runner：断言 argv 含 `--audio_path` 且指向 `last_16k.wav`，原 `last.wav` 字节不变

- [ ] **Step 2–4:** 实现线性重采样（逐目标下标 `src_index = i * src_rate / dst_rate` 取最近邻或线性）。写 16k wav 后 `runner`。pytest PASS

- [ ] **Step 5: Commit** — 跳过

---

### Task 5: TTS 一句 PCM + aplay 采样率

**Files:**
- Create: `ai-microscope-edu/software/voice/tts.py`
- Modify: `ai-microscope-edu/software/voice/alsa.py`（`play_pcm` 增加 `sample_rate: int | None = None`，默认 `self._sample_rate`）
- Modify: `ai-microscope-edu/software/tests/test_alsa.py`（断言可覆盖 `-r`）
- Test: `ai-microscope-edu/software/tests/test_tts.py`

**Interfaces:**
- Consumes: `upmix_mono_to_stereo`；Matcha 默认 22050
- Produces:
  - `TTS_RATE = 22050`
  - `TextToSpeech.synthesize(self, text: str) -> bytes`（单声道 s16le）
  - `MockTts`：对非空文本返回约 0.05 s 的 22050 正弦，空文本 `b""`
  - `SherpaTts`：try `import sherpa_onnx`，按旧 `agent_tts_sherpa.py` 的 Matcha 文件名加载；失败则调用方改用 Mock（`build_tts() -> TextToSpeech`）
  - `AlsaPlayback.play_pcm(pcm, sample_rate: int | None = None)` 把 `-r` 设成该值再升混

- [ ] **Step 1: Tests**

`test_tts.py`：`MockTts().synthesize("甲")` 时长约 0.05；空字符串空 bytes。

`test_alsa.py` 增加：`play_pcm(pcm, sample_rate=22050)` 时 argv `-r` 为 `"22050"`。

- [ ] **Step 3:** `play_pcm` 开头 `rate = int(sample_rate or self._sample_rate)`，timeout 用这个 rate。`tts.py` 的 Sherpa 加载逻辑从只读旧文件抄 `OfflineTtsMatchaModelConfig` 字段（acoustic `model-steps-3.onnx`、vocoder `vocos-22khz-univ.onnx`、lexicon/tokens）。`synthesize` 把引擎 float 转 int16（clamp）。Mac 无 sherpa → `build_tts` 返回 `MockTts`。

- [ ] **Step 4:** pytest `tests/test_tts.py tests/test_alsa.py -q` PASS

- [ ] **Step 5: Commit** — 跳过

---

### Task 6: VoiceSession 去掉回放原声，接回合

**Files:**
- Modify: `ai-microscope-edu/software/voice/session.py`
- Modify: `ai-microscope-edu/software/tests/test_voice_session.py`
- Create: `ai-microscope-edu/software/tests/test_voice_turn.py`（回合编排）

**Interfaces:**
- Consumes: Task 1–5
- Produces: `VoiceSession(..., *, asr: Callable[[Path], str] | None, complete: Callable[..., str] | None)` 过重则拆：
  - `AsrPort.transcribe(path: Path) -> str`
  - `QaPort.iter_tokens(user_text: str) -> Iterator[str]`（内部组 prompt、记忆、客户端）
  - `TtsPort.synthesize(text: str) -> bytes`
  - 判定 `ok` 后：`turning`；`asr` 空 → beep、idle、`failed`；否则把 token 送进 `SentenceSplitter`，`merge_short_sentences` 后入 list 队列；`ready_to_play` 为真后按序 `synthesize` + `playback.play_pcm(pcm, sample_rate=TTS_RATE)`；生产者结束再把剩余播完。全程成功才 `memory.append_turn`。不再调用 `amplify_pcm` / `gate_pcm` 回放原声。
  - `is_busy`：`recording` 或 `turning`

构造默认：`asr=None` 时用 `transcribe_wav`；测试注入 mock。

`QaPort` 做成 `qa/turn.py` 里的 `QaService`：持有 `QaMemory`、`EmptyRecall`、读 `var/qa/USER.md`、`iter_chat_tokens`。缺 LLM 配置时 `iter_tokens` 立刻结束（空），会话当失败 beep。

- [ ] **Step 1: Update / add tests**

原 `test_ok_utterance_writes_wav_and_plays_original`：**改为** 注入 `asr=lambda p: "这是洋葱。还有细胞壁。"`、`tts` 记录句子、`playback` 记录播放次数。断言 `last.wav` 仍是原始 pcm 的 wav；`play.played` 不是 `amplify_pcm(gate_pcm(...))`；TTS 句子为合并后的列表。

`test_echo_gates_noise_but_wav_keeps_original`：**删除或改成**「门控不再用于回放原声」。门控函数可留在 wavutil 给以后，本刀会话不调用。

新增：mock token 流 `"好。这是洋葱。第三句。"`，`producer_done` 前只推第一句时 `playback` 次数仍为 0（水位）；三句都到齐后 playback ≥ 1。可用同步 `QaPort`：`iter_tokens` yield 整段，splitter 一次切出三句，`ready_to_play(3, True)` 为真。

ASR 返回 `""`：beep，`played` 为 beep 不是 TTS。

busy：`start_ptt` 后在 `turning` 中再 `start_ptt` 为 False——在 mock tts 的 `synthesize` 里回调 `start_ptt`。

- [ ] **Step 3: 改 `session.py`**

`_finish_recording`：写 wav + classify 与现在相同；`ok` 后 `_phase = "turning"`，调用 `_run_turn()`（可同步，主窗线程化）。`_run_turn` 实现队列循环。`finally` 回到 idle。

播放 TTS 失败：beep、break、不 `append_turn`。

- [ ] **Step 4:** `pytest tests/test_voice_session.py tests/test_voice_turn.py -q` PASS；全量 `tests/ -q` 也要绿（改掉依赖回放原声的断言）

- [ ] **Step 5: Commit** — 跳过

---

### Task 7: 主窗工作线程 + 浮标禁用

**Files:**
- Modify: `ai-microscope-edu/software/app/main_window.py`
- Modify: `ai-microscope-edu/software/app/ai_fab.py`（`paintEvent`：`not self.isEnabled()` 时用灰色填充，不进 PTT 色）
- Modify: `ai-microscope-edu/software/tests/test_main_window_voice.py`

**Interfaces:**
- Consumes: `VoiceSession.is_busy`、`stop_ptt`
- Produces: 松开 PTT 后 `QThread`/`threading.Thread` 调用 `stop_ptt`；结束用 `QMetaObject`/`Signal` 回主线程 `fab.setEnabled(True)`。`start_ptt` 成功后不要 `setEnabled(False)`（必须能抬手）。`stop` 一开始（进入 turning 前也可）`setEnabled(False)`。`abort`/关窗 `wait` 线程。

- [ ] **Step 1: Tests**

扩展 `_VoiceSession`：加 `is_busy` 属性。断言 `ptt_changed True` 后浮标仍 `isEnabled()`；`False` 后若测试里同步 stop，可在 mock `stop_ptt` 里检查当时 fab 已禁用——更简单：给 MainWindow 加 `_sync_fab_enabled()`：`self._fab.setEnabled(not self._voice.is_busy() or self._voice._phase == "recording")` 不要测私有 phase。

公开 `VoiceSession.phase` 或 `def allows_ptt_release(self) -> bool`。更干净：`def fab_should_enable(self) -> bool: return self._phase == "idle"` **不行**，录音中也要 enable。

**规则写成：** `fab_enabled = phase in ("idle", "recording")`。测：构造后 True；mock phase 做不到。改为会话方法 `def input_enabled(self) -> bool: return self._phase != "turning"`。

测试：`start_ptt` 后 `input_enabled` True；进入 turning 的 mock：在 `stop_ptt` 里设 busy turning 再返回，主窗 disable。

`test_main_window_wires_…` 给 `_VoiceSession` 增加 `input_enabled = True`，`stop_ptt` 里设 `input_enabled = False` 再 True（模拟回合瞬间）。主窗在 start 后 `_apply_fab_input()`：`self._fab.setEnabled(self._voice.input_enabled())`。stop 后先 disable 再开线程，线程结束 enable。

测例断言：emit True 后 `window._fab.isEnabled()` is True；手动 `window._set_turning_ui(True)` 后 False。把 `_set_turning_ui` 做成小方法便于测。

- [ ] **Step 3:** `_on_ptt(False)`：`self._fab.setEnabled(False)`，`threading.Thread(target=self._stop_ptt_worker, daemon=True).start()`。worker：`result = self._voice.stop_ptt()`，然后 `QTimer.singleShot(0, lambda: self._fab.setEnabled(self._voice.input_enabled()))`（必须在主线程改控件）。`QThread` 与 Qt 更亲，也可用 `QObject` 信号。

禁止在 GUI 线程里直接跑 ASR。

- [ ] **Step 4:** `pytest tests/test_main_window_voice.py tests/test_voice_session.py -q` PASS

- [ ] **Step 5: Commit** — 跳过

---

### Task 8: 配置样例、README、211 手测说明

**Files:**
- Create: `ai-microscope-edu/software/deploy/llm.json.example`
- Modify: `ai-microscope-edu/software/README.md`
- Modify: `ai-microscope-edu/software/voice/config.py` 注释写明 211 上 SenseVoice / Matcha 的实际路径（执行本任务时 **ssh 211 查一次** 再写入，不要猜）

**Interfaces:** 无代码接口。`llm.json` 字段：`base_url`、`api_key`、`model`、`timeout_secs`。复制到板 `software/var/qa/llm.json`（var 已 gitignore）。

- [ ] **Step 1:** README「板载语音点验」改为：问一句应听到 TTS；捂麦 beep；松开后到播完浮标按不动；不再要求听到自己的原声。

- [ ] **Step 2:** 全量 `PYTHONPATH=. /usr/bin/python3 -m pytest tests/ -q`

Expected: 既有测试 + 本计划新测试全绿（PySide6 skip 照旧）

- [ ] **Step 3:** Commit — 跳过

211（执行本计划的人，非本文件自动跑）：

```bash
rsync -avz --exclude '.venv' --exclude '__pycache__' --exclude 'var' \
  software/ cat@10.198.24.211:/home/cat/ai-microscope-edu/software/
# 放入 var/qa/llm.json；确认 sensevoice_demo 与 Matcha 模型
sudo systemctl restart edu-app
# 重启后重设混音器（spk / Line 2 / PGA 24dB / Output 拉满）
```

---

## Spec coverage

| spec | 任务 |
|------|------|
| SenseVoice、16 kHz 临时文件、不改 last.wav | 4、6 |
| SSE + 非流式回退、关思考 | 3 |
| 开播水位 2、预取 3、短句 8 字合并、串行 TTS | 1、6 |
| USER.md 1000 字、EmptyRecall | 2 |
| 8 轮、20 分钟切场 | 2 |
| 只文本、无字幕无 SQLite | 全局 |
| 后台线程、linuxfb | 7 |
| 浮标 turning 禁用、录音中可抬手 | 7 |
| TTS 22050 + 立体声 aplay | 5 |
| 失败 beep、不写半截历史 | 6 |

## 非目标

字幕 UI、ROI 识图、SQLite 知识库、设置页、配网关机、门控调参、多句并行 TTS、git commit。
