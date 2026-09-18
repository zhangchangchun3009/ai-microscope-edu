# 教学一体机会话落盘与历史页 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 成功问答写入本机 SQLite；历史右栏只读回看；语音关键字与按钮切场并 TTS「已处于新对话」；保留天数与送给 LLM 的轮数从 `edu.yaml` 的 `qa` 段读取，不硬编码。

**Architecture:** `system/edu_config.py` 解析 `qa.retain_days` / `qa.context_turns`。`qa/store.py` 用标准库 sqlite3（WAL + 进程锁）管场次与轮次。`QaService` 持有当前场、按 yaml 截断的 `QaMemory`、启动清库线程与异步标题。`VoiceSession` 在 ASR 后、组 LLM 消息前拦截切场口令；历史页只读，与语音共用同一个 `QaService`。入口层（`main_window` / `turn`）只调度。

**Tech Stack:** Python 3、pytest、stdlib `sqlite3`、PySide6。不引入 MCP、不新增 HTTP 依赖。标题走现有 `qa/client.py` 非流式 POST。

## Global Constraints

- 规格：[`docs/superpowers/specs/2026-09-18-edu-session-history-design.md`](../specs/2026-09-18-edu-session-history-design.md)。只改 `ai-microscope-edu/`。
- YAML 缺省：`retain_days=7`（钳制 1–3650）、`context_turns=8`（钳制 1–64）。设置页 **不加** 这两项滑条。
- 历史页只读；语音只写当前场；不能把旧场改回当前。
- 切场 TTS 固定句「已处于新对话」，不走问答分句队列，不用 LLM 总结正文。
- 20 分钟空闲切场时长仍用 `qa.config.IDLE_NEW_SESSION_S`，本刀不进 yaml。
- 清理只在进程启动时后台线程跑一次；`QaService(..., purge_on_start=False)` 供单测同步调用。
- Mac：`cd ai-microscope-edu/software && PYTHONPATH=. /usr/bin/python3 -m pytest tests/ --ignore=tests/test_ai_fab.py -q`
- 未经用户明确要求不要 `git commit`。下列若出现 Commit 步骤一律跳过。
- 单文件 < 1000 行；对外函数写 docstring（用途、参数、返回、副作用）；回复与注释用简体中文。
- 先写失败测试再写实现。声称完成前必须跑相关 pytest。

---

## File map

| 路径 | 职责 |
|------|------|
| `software/system/edu_config.py` | `EduSettings.retain_days` / `context_turns`；读 `qa` 段并钳制 |
| `software/deploy/edu.yaml.example` | 样例 `qa` 段 |
| `software/qa/utterance.py` | 语音「新对话」关键字纯函数 |
| `software/qa/store.py` | SQLite 场次 / 轮次 / meta / 启动清理 |
| `software/qa/title.py` | 20 字截断、解析 LLM 标题、组短 completion |
| `software/qa/memory.py` | `max_turns` 由调用方注入；空闲清空仍可用 |
| `software/qa/turn.py` | 落盘、切场、hydrate、异步标题、清库线程 |
| `software/qa/client.py` | 标题用的非流式一次 completion（可小函数） |
| `software/qa/config.py` | `IDLE_NEW_SESSION_S` 不变；`MAX_TURNS` 仅作无 yaml 时的记忆缺省，**不是**清库天数 |
| `software/voice/session.py` | ASR 后拦截；`announce_new_session()` 供按钮 |
| `software/app/history_page.py` | 历史分屏：列表 + 只读正文 +「新对话」 |
| `software/app/stub_pages.py` | 去掉 HISTORY 占位 |
| `software/app/main_window.py` | 构造一次 `QaService`，注入语音与历史页 |
| `software/qa/__init__.py` | 导出新符号（按需） |
| `software/README.md` | 211 历史页 / 新对话手测；yaml `qa` 段 |

---

### Task 1: YAML `qa.retain_days` / `qa.context_turns`

**Files:**
- Modify: `ai-microscope-edu/software/system/edu_config.py`
- Modify: `ai-microscope-edu/software/tests/test_edu_config.py`
- Modify: `ai-microscope-edu/software/deploy/edu.yaml.example`

**Interfaces:**
- Consumes: 现有 `load_edu` / `save_edu` / `defaults`
- Produces:
  - `DEFAULT_RETAIN_DAYS = 7`、`DEFAULT_CONTEXT_TURNS = 8`
  - `MAX_RETAIN_DAYS = 3650`、`MAX_CONTEXT_TURNS = 64`
  - `EduSettings.retain_days: int`、`EduSettings.context_turns: int`
  - 解析：缺段 / 非整数 → 缺省；再钳制到闭区间。`0` 或负数 → 下限 1。过大 → 上限。
  - `save_edu` / `_write_settings_into` 写入 `qa:` 嵌套，不丢已有注释键序（ruamel）。
  - `patch_edu` **本刀不必**接受这两字段（无设置 UI）。`patch` 音量后 `load_edu` 仍能读到文件里已有的 `qa`。

- [ ] **Step 1: Write the failing test**

在 `test_edu_config.py` 的 `_assert_full_defaults` 增加：

```python
assert settings.retain_days == 7
assert settings.context_turns == 8
```

并追加：

```python
def test_qa_section_roundtrip_and_clamp(tmp_path: Path) -> None:
    path = tmp_path / "edu.yaml"
    path.write_text(
        "v: 1\n"
        "display:\n"
        "  rotation_deg: 90\n"
        "  captions_enabled: false\n"
        "audio:\n"
        "  volume_pct: 73\n"
        "qa:\n"
        "  retain_days: 0\n"
        "  context_turns: 100\n",
        encoding="utf-8",
    )
    loaded = load_edu(path)
    assert loaded.retain_days == 1
    assert loaded.context_turns == 64

    settings = defaults()
    settings.retain_days = 14
    settings.context_turns = 3
    save_edu(path, settings)
    again = load_edu(path)
    assert again.retain_days == 14
    assert again.context_turns == 3
    text = path.read_text(encoding="utf-8")
    assert "retain_days" in text
    assert "context_turns" in text


def test_qa_missing_or_garbage_uses_defaults(tmp_path: Path) -> None:
    path = tmp_path / "edu.yaml"
    path.write_text(
        "v: 1\n"
        "qa:\n"
        "  retain_days: nope\n"
        "  context_turns: []\n",
        encoding="utf-8",
    )
    loaded = load_edu(path)
    assert loaded.retain_days == 7
    assert loaded.context_turns == 8
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd ai-microscope-edu/software && PYTHONPATH=. /usr/bin/python3 -m pytest tests/test_edu_config.py -q
```

预期：`EduSettings` 无新字段，AttributeError 或断言失败。

- [ ] **Step 3: Implement**

`EduSettings` 增加两字段；`defaults()` 填 7/8。`_settings_from_nested` 读 `data["qa"]` 映射，用小函数 `_clamp_int(raw, default, lo, hi)`。`_write_settings_into` 写 `qa.retain_days` / `qa.context_turns`。

`edu.yaml.example` 在 `audio` 与 `llm` 之间加入：

```yaml
qa:
  retain_days: 7      # 启动时删 updated_at 更早且非当前场；不进设置页
  context_turns: 8    # 送给 LLM 的当前场最近轮数
```

- [ ] **Step 4: Re-run tests**

同上命令，应全绿。

- [ ] **Step 5: Skip commit**

---

### Task 2: 语音切场关键字纯函数

**Files:**
- Create: `ai-microscope-edu/software/qa/utterance.py`
- Create: `ai-microscope-edu/software/tests/test_qa_utterance.py`

**Interfaces:**
- Produces: `is_new_session_utterance(text: str) -> bool`
- 规则（与更新后 spec §6 一致）：去掉空白与 `。！？,.!?、` 后，整句 **必须等于** `新对话` / `新会话` / `新建对话` / `新建会话` 之一。不做包含匹配、不加「是什么」启发式。

- [ ] **Step 1: Write the failing test**

```python
"""语音「新对话」口令判定。"""

from __future__ import annotations

import sys
from pathlib import Path

_SOFTWARE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_SOFTWARE))

from qa.utterance import is_new_session_utterance  # noqa: E402


def test_new_session_exact_phrases() -> None:
    assert is_new_session_utterance("新对话") is True
    assert is_new_session_utterance("新会话") is True
    assert is_new_session_utterance("新建对话") is True
    assert is_new_session_utterance("新建会话") is True
    assert is_new_session_utterance("  新对话。") is True
    assert is_new_session_utterance("开始新会话") is False
    assert is_new_session_utterance("新的对话") is False
    assert is_new_session_utterance("新的对话方式是什么") is False
    assert is_new_session_utterance("洋葱表皮是什么") is False
    assert is_new_session_utterance("") is False
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd ai-microscope-edu/software && PYTHONPATH=. /usr/bin/python3 -m pytest tests/test_qa_utterance.py -q
```

- [ ] **Step 3: Implement `qa/utterance.py`**

对外函数写完整 docstring。不要在此文件做 TTS / 切场。

- [ ] **Step 4: Re-run tests** — 应通过。

- [ ] **Step 5: Skip commit**

---

### Task 3: SessionStore（SQLite）

**Files:**
- Create: `ai-microscope-edu/software/qa/store.py`
- Create: `ai-microscope-edu/software/tests/test_qa_store.py`

**Interfaces:**
- Consumes: 无 Qt、无 LLM
- Produces: `SessionStore(path: Path, *, clock: Callable[[], float] | None = None)`
  - `ensure_schema()` / 构造时建表；`PRAGMA journal_mode=WAL`；`PRAGMA foreign_keys=ON`
  - 进程内 `threading.Lock` 包住所有 SQL
  - `ensure_current() -> str`：meta 无 id 或行已删则插入空场 `title=「新对话」`
  - `current_id() -> str`
  - `start_new_session() -> str`：当前场 **0 轮**则返回原 id；否则新 uuid hex，更新 meta
  - `append_turn(user, assistant) -> int`：写入当前场，`seq` 从 1 递增，刷新 `updated_at`；若标题仍是「新对话」，改为 `clip_title(user, 20)`（可先在本文件做截断，Task 4 再抽到 `title.py`，避免循环依赖——推荐本任务就放 `qa/title.py` 的 `clip_title` 纯函数）
  - `list_sessions() -> list[SessionRecord]`：按 `updated_at` 降序；含 `id/title/created_at/updated_at/turn_count`
  - `list_turns(session_id) -> list[TurnRecord]`
  - `update_title(session_id, title) -> None`
  - `hydrate_turns(session_id, *, limit: int) -> list[tuple[str, str]]`：按 seq 升序的最后 `limit` 轮
  - `purge_expired(*, retain_days: int, now: float | None = None) -> int`：`DELETE` `updated_at < now - retain_days*86400` **且** `id != current`；返回删除场次数；`retain_days` 由调用方传入，本模块不读 yaml
  - 打开失败：构造可抛 `OSError`；`QaService` 在下一任务捕获

表结构严格按 spec §3。id 用 `uuid.uuid4().hex`。

- [ ] **Step 1: Write the failing test**

`test_qa_store.py` 至少覆盖：

1. 空库 `ensure_current` 一场「新对话」；`start_new_session` 空场复用同一 id。
2. `append_turn` 后 `start_new_session` 得到新 id；旧场仍在 `list_sessions`。
3. 第一轮 user 把标题从「新对话」改成截断 20 字（含多字节汉字，不要按字节切）。
4. `purge_expired(retain_days=7)`：`updated_at` 在 8 天前的非当前场删除（CASCADE 无 turns）；当前场即使很旧也保留；3 天前的场保留。
5. `hydrate_turns(limit=2)` 只返回最后两轮。

注入 `clock` 以便写死 `updated_at`。

- [ ] **Step 2: Run test to verify it fails**

```bash
cd ai-microscope-edu/software && PYTHONPATH=. /usr/bin/python3 -m pytest tests/test_qa_store.py -q
```

- [ ] **Step 3: Implement `qa/store.py`（及 `clip_title`）**

`clip_title(text: str, max_chars: int = 20) -> str`：`strip` 后按 Unicode 码点切片，空则「新对话」。

每个对外方法 docstring。单文件保持远小于 1000 行。

- [ ] **Step 4: Re-run tests** — 应通过。

- [ ] **Step 5: Skip commit**

---

### Task 4: QaMemory 注入轮数 + QaService 落盘 / 空闲切场 / hydrate

**Files:**
- Modify: `ai-microscope-edu/software/qa/memory.py`
- Modify: `ai-microscope-edu/software/qa/turn.py`
- Modify: `ai-microscope-edu/software/tests/test_qa_prompt.py`
- Create: `ai-microscope-edu/software/tests/test_qa_session_persist.py`
- Modify: `ai-microscope-edu/software/qa/__init__.py`（按需导出）

**Interfaces:**
- `QaMemory(clock=..., *, max_turns: int | None = None)`：`max_turns` 缺省仍用 `qa.config.MAX_TURNS`（=8），**仅**作为未注入时的记忆上限。运行时 `QaService` 必须传入 yaml 的 `context_turns`。
- `QaService` 新增：
  - `qa_dir` 仍默认 `software/var/qa`；库文件 `qa_dir / "sessions.sqlite"`
  - `edu_yaml` 已有；构造时 `load_edu` 取 `retain_days` / `context_turns`（注入 `config=` 时 **仍然**读 yaml 的 qa 段；yaml 缺失则缺省 7/8）
  - `store: SessionStore | None` 可注入；缺省打开上述路径，失败则 `_store=None`（问答走内存，不抛到 GUI）
  - `purge_on_start: bool = True`：为 True 且 store 可用时，`threading.Thread(daemon=True)` 调 `purge_expired(retain_days=...)`，异常只打 log
  - `start_new_session() -> str | None`：无 store 则清空 memory 并返回 `None`；有 store 则委托 `store.start_new_session()`，成功后 `memory` 换成空的同 `max_turns`
  - `append_turn`：先 `_maybe_idle_rotate()`，再 store 写入（失败 log，memory 仍写），再 `memory.append_turn`。store 第一轮且成功时调度标题线程（Task 5 若未做完可先 noop，但本任务测试不依赖 LLM 标题）
  - `iter_tokens`：**组消息前** `_maybe_idle_rotate()`，避免 20 分钟后仍把旧场轮次送给模型
  - `_maybe_idle_rotate()`：若 memory 有轮次且 `clock - last_activity >= IDLE_NEW_SESSION_S`，调用 `start_new_session()`（有内容才会新建）
  - 构造成功打开 store 后：`hydrate_turns(current, limit=context_turns)` 填入 memory
  - `list_sessions` / `list_turns` / `current_session_id`：给历史页；无 store 返回空

空闲切场必须进 SQLite，不能只 `QaMemory.touch()` 清内存。`memory.touch()` 可保留给旧测试；`QaService` 不要只靠它落盘。

- [ ] **Step 1: Write failing tests**

扩展 `test_qa_prompt.py`：

```python
def test_qa_memory_respects_max_turns() -> None:
    mem = QaMemory(max_turns=2)
    mem.append_turn("u1", "a1")
    mem.append_turn("u2", "a2")
    mem.append_turn("u3", "a3")
    msgs = mem.messages()
    assert [m["content"] for m in msgs if m["role"] == "user"] == ["u2", "u3"]
```

`test_qa_session_persist.py`：

```python
def test_append_then_list_and_idle_rotates(tmp_path: Path) -> None:
    clock = {"t": 0.0}
    yaml_path = tmp_path / "edu.yaml"
    yaml_path.write_text("v: 1\nqa:\n  retain_days: 7\n  context_turns: 2\n", encoding="utf-8")
    from qa.memory import QaMemory
    from qa.turn import QaService

    svc = QaService(
        qa_dir=tmp_path,
        environ={},
        memory=QaMemory(clock=lambda: clock["t"], max_turns=2),
        config=None,  # 无 llm 亦可落盘
        purge_on_start=False,
    )
    # 若构造仍从父目录读 yaml，本任务应让 QaService 读 qa_dir.parent/edu.yaml
    # 已有约定：qa_dir 非默认时 edu.yaml = qa_dir.parent / "edu.yaml"
    svc.append_turn("第一问", "第一答")
    svc.append_turn("第二问", "第二答")
    svc.append_turn("第三问", "第三答")
    users = [m["content"] for m in svc.memory.messages() if m["role"] == "user"]
    assert users == ["第二问", "第三问"]  # context_turns=2
    sessions = svc.list_sessions()
    assert len(sessions) == 1
    assert sessions[0].turn_count == 3

    clock["t"] = 20 * 60 + 1
    svc.iter_tokens("新问题")  # 无配置应空迭代，但必须已切场
    assert svc.current_session_id() != sessions[0].id
    assert svc.memory.messages() == []


def test_empty_start_new_session_reuses(tmp_path: Path) -> None:
    svc = QaService(qa_dir=tmp_path, environ={}, config=None, purge_on_start=False)
    first = svc.current_session_id()
    assert svc.start_new_session() == first
    svc.append_turn("u", "a")
    second = svc.start_new_session()
    assert second != first
```

若现有 `QaService` 在 `qa_dir=tmp_path` 时把 `edu.yaml` 指到 `tmp_path.parent / edu.yaml`：测试应把 yaml 放在 **qa_dir 的父目录**，或本任务把「qa 段」改为 `load_edu(self._edu_yaml)`（已存在）。保持现约定，不要改 LLM 路径语义。

`test_qa_reload.py` 等现有用例应继续绿：给 `QaService(qa_dir=..., purge_on_start=False)` 即可避免启动线程。实现时对所有 `QaService(` 测试补 `purge_on_start=False` 或接受 daemon（daemon 在 pytest 结束即死，但会抢同一文件——**单测一律 False**）。

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd ai-microscope-edu/software && PYTHONPATH=. /usr/bin/python3 -m pytest tests/test_qa_prompt.py tests/test_qa_session_persist.py tests/test_qa_reload.py -q
```

- [ ] **Step 3: Implement**

`memory.append_turn` 用 `self._max_turns` 替代直接读 `MAX_TURNS`。

`QaService.__init__` 打开 store、hydrate、可选 purge 线程。

注意：`test_two_default_turns_keep_qa_memory`（`tests/test_voice_session.py`）懒创建 `QaService()` 会写默认 `var/qa`。本任务后改为该测试显式 `qa=QaService(qa_dir=tmp_path, config=cfg, purge_on_start=False)`，**仍断言只构建一次 TTS**；记忆断言不变。不要让 CI/开发机默认库被测试轮次污染。

- [ ] **Step 4: Re-run** 上述 pytest 以及：

```bash
PYTHONPATH=. /usr/bin/python3 -m pytest tests/test_voice_session.py tests/test_voice_turn.py tests/test_qa_reload.py -q
```

- [ ] **Step 5: Skip commit**

---

### Task 5: 异步 LLM 标题

**Files:**
- Create: `ai-microscope-edu/software/qa/title.py`（若 Task 3 已放 `clip_title`，本任务补 generate）
- Modify: `ai-microscope-edu/software/qa/client.py`（非流式一次）
- Modify: `ai-microscope-edu/software/qa/turn.py`
- Create: `ai-microscope-edu/software/tests/test_qa_title.py`

**Interfaces:**
- `parse_llm_title(raw: str) -> str | None`：去空白、去包裹引号、去掉前缀「标题：」/「标题:」；空或全标点 → `None`；再 `clip_title(..., 20)`
- `build_title_messages(user: str, assistant: str) -> list[dict]`：system 要求只回一行 ≤20 字标题；user/assistant 各截断约 200 字
- `complete_once(config, messages, *, timeout_s: float) -> str`：只走 `stream=false`，失败返回 `""` 不抛给 UI（可包 `QaClientError` 为虚）
- `QaService.append_turn`：若本场写入后 `seq==1` 且 `_config` 非空，daemon 线程：`complete_once` → `parse_llm_title` → `store.update_title`；失败保持第一句标题
- **禁止**改问答 system / 把标题塞进 `iter_tokens`

- [ ] **Step 1: Write the failing test**

```python
def test_parse_llm_title_strips_prefix_and_quotes() -> None:
    from qa.title import parse_llm_title
    assert parse_llm_title('标题：洋葱表皮') == "洋葱表皮"
    assert parse_llm_title('"细胞壁"') == "细胞壁"
    assert parse_llm_title("   ") is None


def test_first_turn_schedules_title_override(tmp_path: Path, monkeypatch) -> None:
    from qa.client import LlmConfig
    from qa.turn import QaService

    cfg = LlmConfig(
        base_url="https://api.example.com/v1",
        api_key="sk",
        model="qwen-plus",
        timeout_s=30.0,
    )
    monkeypatch.setattr("qa.title.complete_once", lambda *_a, **_k: "洋葱切片观察")
    svc = QaService(
        qa_dir=tmp_path, environ={}, config=cfg, purge_on_start=False
    )
    svc.append_turn("这是什么标本", "这是洋葱表皮。")
    # 等标题线程
    import time
    for _ in range(50):
        sessions = svc.list_sessions()
        if sessions and sessions[0].title == "洋葱切片观察":
            break
        time.sleep(0.02)
    assert svc.list_sessions()[0].title == "洋葱切片观察"


def test_title_failure_keeps_user_clip(tmp_path: Path, monkeypatch) -> None:
    from qa.client import LlmConfig
    from qa.turn import QaService

    cfg = LlmConfig(
        base_url="https://api.example.com/v1",
        api_key="sk",
        model="qwen-plus",
        timeout_s=30.0,
    )
    monkeypatch.setattr("qa.title.complete_once", lambda *_a, **_k: "")
    svc = QaService(qa_dir=tmp_path, environ={}, config=cfg, purge_on_start=False)
    svc.append_turn("这是什么标本呀同学们", "答")
    import time
    time.sleep(0.05)
    title = svc.list_sessions()[0].title
    assert title.startswith("这是什么标本")
    assert title != "新对话"
```

- [ ] **Step 2: Run to verify fail**

```bash
cd ai-microscope-edu/software && PYTHONPATH=. /usr/bin/python3 -m pytest tests/test_qa_title.py -q
```

- [ ] **Step 3: Implement**

标题 HTTP timeout 用 `min(config.timeout_s, 15)`。无配置则不启动线程。

- [ ] **Step 4: Re-run `test_qa_title.py` + Task 4 相关测试**

- [ ] **Step 5: Skip commit**

---

### Task 6: VoiceSession 拦截口令 + 按钮同一 TTS

**Files:**
- Modify: `ai-microscope-edu/software/voice/session.py`
- Modify: `ai-microscope-edu/software/tests/test_voice_turn.py`
- Modify: `ai-microscope-edu/software/tests/test_voice_session.py`（`_ScriptQa` 补 `start_new_session`）

**Interfaces:**
- `QaPort` 增加 `start_new_session(self) -> object`
- `_run_turn`：ASR 非空之后、`on_asr` **之前**，若 `is_new_session_utterance(user_text)`：
  1. `qa.start_new_session()`
  2. `_speak_fixed("已处于新对话")`：单次 TTS + `play_pcm`，走 `on_assistant_sentence`（字幕），**不**走 `SentenceSplitter` / `SentencePlayer` 水位
  3. 成功 `"played"`；TTS 失败 beep `"failed"`；**不** `iter_tokens`、**不** `append_turn`
- `announce_new_session() -> StopResult`：`is_busy()` 则 `"ignored"`；否则 `turning` → 同上切场+固定句 → `idle`。历史钮走这条，与口令同一句。
- `_ScriptQa.start_new_session` 记一次调用即可。

- [ ] **Step 1: Write the failing test**

在 `test_voice_turn.py`：

```python
def test_new_session_utterance_skips_llm_and_speaks_fixed(tmp_path: Path) -> None:
    qa = _ScriptQa(["不该出现"])
    tts = _Tts()
    sess, play = _make_session(
        tmp_path, asr=lambda _p: "新对话", qa=qa, tts=tts
    )
    sess.start_ptt()
    assert sess.stop_ptt() == "played"
    assert qa.turns == []
    assert getattr(qa, "new_sessions", 1) >= 1
    assert tts.sentences == ["已处于新对话"]
    assert any(b.startswith(b"TTS:") for b in play.played)


def test_normal_question_still_hits_llm(tmp_path: Path) -> None:
    qa = _ScriptQa(["这是洋葱表皮。"])
    tts = _Tts()
    sess, _play = _make_session(
        tmp_path, asr=lambda _p: "洋葱表皮是什么", qa=qa, tts=tts
    )
    sess.start_ptt()
    assert sess.stop_ptt() == "played"
    assert qa.turns
    assert "已处于新对话" not in tts.sentences
```

`_ScriptQa` 增加 `new_sessions = 0` 与 `start_new_session`。

- [ ] **Step 2: Run to verify fail**

```bash
cd ai-microscope-edu/software && PYTHONPATH=. /usr/bin/python3 -m pytest tests/test_voice_turn.py -q
```

- [ ] **Step 3: Implement intercept + `_speak_fixed` + `announce_new_session`**

忙碌覆盖仍含这句播完（已在 `turning`）。关窗 `abort` 仍置位 cancel：固定句合成前检查 cancel。

- [ ] **Step 4: Re-run** `test_voice_turn.py` `test_voice_session.py`

- [ ] **Step 5: Skip commit**

---

### Task 7: 历史页 + MainWindow 接线 + 启动清库

**Files:**
- Create: `ai-microscope-edu/software/app/history_page.py`
- Create: `ai-microscope-edu/software/tests/test_history_page.py`
- Modify: `ai-microscope-edu/software/app/stub_pages.py`（HISTORY 不再占位）
- Modify: `ai-microscope-edu/software/app/main_window.py`
- Modify: `ai-microscope-edu/software/tests/test_main_window_voice.py`
- Modify: `ai-microscope-edu/software/README.md`

**Interfaces:**
- `HistoryPage(on_close, qa, on_new_session, parent=None)`
  - 顶栏：「历史」+「新对话」(`SETTINGS_CTRL_H`) +「关闭」
  - 左 `QListWidget`：标题；当前场后缀或旁注「当前」；行高与设置页同级
  - 右只读区：用户/助手交替；空场文案「还没有问答」；无输入框
  - `reload(keep_selected_id=None)`：从 `qa.list_sessions()` 刷新；点行只改阅读选中，**不** `start_new_session`
  - 「新对话」调用 `on_new_session`（由主窗丢到语音工作线程 `announce_new_session`），不要在 GUI 线程 TTS
- `MainWindow(..., qa: QaService | None = None)`：缺省 `QaService()`（生产要启动清库线程）；注入 `VoiceSession(..., qa=self._qa)`；`HISTORY` 用 `HistoryPage`
- 打开历史工具条时 `history.reload()`；语音切场后若右栏是历史，再 `reload(keep_selected_id=...)`（可在 `announce` 结束的 `_ptt_finished` 里若当前面板是 HISTORY 则刷新）
- `_reload_llm` 改为 `self._qa.reload_llm()`，不要再 `getattr(self._voice, "_qa")`
- `test_main_window_voice._make_window`：`MainWindow(qa=_DummyQa())`，避免写真实 sqlite。Dummy 提供 `reload_llm` / `list_sessions`→`[]` / `list_turns`→`[]` / `current_session_id`→`None` / `start_new_session`
- 库打不开：历史页显示「无法读取」；问答仍内存轮次（已在 Task 4）

历史页纯 Qt 测试（`QT_QPA_PLATFORM=offscreen`，`importorskip("PySide6")`）：用内存假 qa 填两场，点第一行断言正文含助手句；点「新对话」断言回调次数；点列表 **不**调用 `start_new_session`。

- [ ] **Step 1: Write failing tests**（`test_history_page.py` + 给 `_make_window` 预留 `qa=`）

- [ ] **Step 2: Run to verify fail**

```bash
cd ai-microscope-edu/software && PYTHONPATH=. /usr/bin/python3 -m pytest tests/test_history_page.py tests/test_main_window_voice.py -q
```

- [ ] **Step 3: Implement UI and wiring**

对照 `settings_page.py` 页头与 `theme.SETTINGS_CTRL_H`。`stub_pages` 只留 FUSION/STITCH。

README「LLM 与语音模型配置」补一句：可选手改 `qa.retain_days` / `qa.context_turns`，重启生效。板载手测：

- 问一句后打开「历史」，列表有当前场，右侧能看见该轮
- 说「新对话」或点按钮，喇叭「已处于新对话」，列表多一场或标题回到「新对话」
- 点旧场只能看，再说话仍进带「当前」标记的那一场

- [ ] **Step 4: Run full software pytest（忽略 fab 同现约定）**

```bash
cd ai-microscope-edu/software && PYTHONPATH=. /usr/bin/python3 -m pytest tests/ --ignore=tests/test_ai_fab.py -q
```

- [ ] **Step 5: Skip commit**

---

## 启动清库线程（并入 Task 4 / 7，不单开刀）

`QaService(purge_on_start=True)` 默认开 daemon：`store.purge_expired(retain_days=self._retain_days)`。失败 `logging.exception`。`MainWindow` 生产路径不要传 `False`。单测全部 `False`，另写：

```python
def test_purge_on_start_deletes_old_non_current(tmp_path: Path) -> None:
    # 先用 purge_on_start=False 插入一场 updated_at=8 天前的非当前场
    # 再构造第二个 QaService(purge_on_start=True)，join 清理线程或轮询
    # 断言旧场消失、当前场仍在
```

放进 `test_qa_session_persist.py`。

---

## 现有测试必改清单

| 文件 | 改什么 |
|------|--------|
| `test_edu_config.py` | 缺省含 7/8 |
| `test_qa_prompt.py` | `max_turns=2`；空闲测试仍可测 `QaMemory.touch` |
| `test_qa_reload.py` | `purge_on_start=False` |
| `test_voice_turn.py` | `_ScriptQa.start_new_session`；口令用例 |
| `test_voice_session.py` | 懒创建测试注入 `qa_dir=tmp_path`；`_ScriptQa` 同左 |
| `test_main_window_voice.py` | `MainWindow(qa=dummy)` |
| `test_qa_store.py` / `test_qa_utterance.py` / `test_qa_title.py` / `test_qa_session_persist.py` / `test_history_page.py` | 新建 |

`qa.config.MAX_TURNS` **保留**为 8，仅给裸 `QaMemory()` 用。清库天数与送模轮数 **禁止**再写死 7/8 在 `store`/`turn` 业务分支里（缺省常量只允许出现在 `edu_config`）。

---

## 非目标（本计划不做）

知识库 SQLite/FTS、识图进历史、导出、多用户、设置页滑条、热重载 `qa` 段、把空闲分钟数写进 yaml、235 部署、10.1 寸屏。

---

## 计划自检

- 规格每一条已决都有任务：SQLite、只读历史、语音+按钮切场、异步标题、yaml 天数与轮次、启动线程清理、20 分钟空闲切场进库、失败表。
- 类型：`retain_days`/`context_turns` 为钳制后的 `int`；会话 id 为 `str`。
- 命名：`SessionStore`、`start_new_session`、`is_new_session_utterance`、`announce_new_session`、`HistoryPage` 与 spec 一致。
- 入口：`QaService` / `MainWindow` / `VoiceSession._run_turn` 只组合；SQL 在 `store.py`，口令在 `utterance.py`，标题在 `title.py`。
- 测试：无「启动应用看一眼」作为唯一验收；Qt 布局在 211 点验，README 已写手测。
- 一致性：历史钮与口令同一 `start_new_session` + 同一 TTS 句；`context_turns` 同时约束 memory 与 hydrate。
- 占位符：无 TBD。
- Commit 步骤已按仓库惯例跳过。
