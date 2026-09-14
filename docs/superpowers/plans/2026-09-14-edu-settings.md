# 教学一体机设置 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 设置右栏可改方向/字幕/音量/`USER.md`/LLM；配置进一份 `var/edu.yaml`；密钥按 CPU 序列号 `enc1:` 加密；旋转立刻转；字幕两行切幕播完消失；开机写混音器；分界线手指拖得动。

**Architecture:** 无 Qt 逻辑在 `software/system/`（yaml、序列号、AES-GCM、旋转几何、切幕分页、amixer argv）。`qa/` 从 yaml 的 `llm` 段读配置并 `reload_llm()`。`voice/session.py` 只加字幕回调。`app/` 替换设置占位页、加宽 splitter、旋转宿主、字幕条；现壳「预览 | 右栏 | 工具条」不改交互。

**Tech Stack:** Python 3、pytest、PySide6、`ruamel.yaml`、`cryptography`（AES-256-GCM）。不引入 MCP。

## Global Constraints

- 规格：[`docs/superpowers/specs/2026-09-14-edu-settings-design.md`](../specs/2026-09-14-edu-settings-design.md)。只改 `ai-microscope-edu/`。
- 设置走现壳，不藏工具条、不做半屏滑入。
- 缺省旋转 **90**。密钥界面不回显明文。混音器通路不进 UI。
- 当前验证屏偏小（约 5 寸、高 DPI）：分界线 **32 px**（spec ≥24），设置控件高度 **56 px**（spec ≥44）。工具条圆钮直径本刀不改。
- Mac：`cd ai-microscope-edu/software && PYTHONPATH=. /usr/bin/python3 -m pytest tests/ --ignore=tests/test_ai_fab.py -q`
- 未经用户明确要求不要 `git commit`。下列 Commit 步骤一律跳过。
- 单文件 < 1000 行；入口只调度。回复与注释用简体中文。

---

## File map

| 路径 | 职责 |
|------|------|
| `software/system/device_id.py` | CPU 序列号 / 可注入 |
| `software/system/secret_box.py` | `enc1` AES-GCM |
| `software/system/display.py` | `logical_size`、`map_touch` |
| `software/system/captions.py` | `paginate`、切幕状态 |
| `software/system/mixer.py` | 固定通路 argv、音量映射、`apply_*` |
| `software/system/edu_config.py` | `edu.yaml` 读写真机默认与迁移 |
| `software/qa/client.py` / `turn.py` | yaml + 解密 + `reload_llm` |
| `software/voice/session.py` | `on_asr` / `on_assistant_sentence` / `on_captions_clear` |
| `software/app/rotate_host.py` | 物理全屏 + 立刻旋转 |
| `software/app/settings_page.py` 等 | 设置分组与子页 |
| `software/app/caption_bar.py` | 预览底两行框 |
| `software/app/main_window.py` / `theme.py` | 接线、splitter 32px |
| `software/deploy/edu-mixer.sh`、`edu.yaml.example`、`edu-app.service` | 启动混音器、样例、拼音 IM |
| `software/README.md` | 211 手测，去掉 restart 后手跑 amixer |

---

### Task 1: 设备序列号与 enc1 加解密

**Files:**
- Create: `ai-microscope-edu/software/system/__init__.py`
- Create: `ai-microscope-edu/software/system/device_id.py`
- Create: `ai-microscope-edu/software/system/secret_box.py`
- Modify: `ai-microscope-edu/software/requirements.txt`（加上 `ruamel.yaml>=0.18` 与 `cryptography>=42`）
- Test: `ai-microscope-edu/software/tests/test_secret_box.py`

**Interfaces:**
- Consumes: 无
- Produces:
  - `read_cpu_serial(*, cpuinfo: str | None = None, dt_serial: str | None = None) -> str`
  - `encrypt_secret(plain: str, serial: str) -> str`（`enc1:` + hex）
  - `decrypt_secret(token: str, serial: str) -> str`（非 `enc1:` 当明文；失败抛 `ValueError`）

- [ ] **Step 1: Write the failing test**

创建 `ai-microscope-edu/software/tests/test_secret_box.py`：

```python
"""CPU 序列号派生 AES-GCM；换 serial 不可解。"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

_SOFTWARE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_SOFTWARE))

from system.device_id import read_cpu_serial  # noqa: E402
from system.secret_box import decrypt_secret, encrypt_secret  # noqa: E402


def test_cpuinfo_serial_lowercase() -> None:
    blob = "processor\t: 0\nSerial\t\t: 0123ABCD\n"
    assert read_cpu_serial(cpuinfo=blob, dt_serial=None) == "0123abcd"


def test_dt_serial_wins() -> None:
    assert read_cpu_serial(cpuinfo="Serial: dead", dt_serial="AABB") == "aabb"


def test_missing_falls_back_macos_dev() -> None:
    assert read_cpu_serial(cpuinfo="", dt_serial=None) == "macos-dev"


def test_roundtrip_same_serial() -> None:
    token = encrypt_secret("sk-live", "serial-a")
    assert token.startswith("enc1:")
    assert decrypt_secret(token, "serial-a") == "sk-live"


def test_wrong_serial_raises() -> None:
    token = encrypt_secret("sk-live", "serial-a")
    with pytest.raises(ValueError):
        decrypt_secret(token, "serial-b")


def test_plaintext_passthrough() -> None:
    assert decrypt_secret("sk-plain", "serial-a") == "sk-plain"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd ai-microscope-edu/software && PYTHONPATH=. /usr/bin/python3 -m pytest tests/test_secret_box.py -q`

Expected: FAIL（`system` 未定义或缺 `cryptography`）

- [ ] **Step 3: Write minimal implementation**

`system/__init__.py` 可为模块说明 docstring。

`device_id.py`：`dt_serial` 非空则 `strip().lower()`；否则在 `cpuinfo` 文本里找以 `Serial` 开头的行，取 `:` 后 hex 小写；都没有返回 `"macos-dev"`。运行时（参数都省略）先试读 `/sys/firmware/devicetree/base/serial-number`（去 `\x00`），再读 `/proc/cpuinfo`，失败回退。

`secret_box.py`：

```python
_PREFIX = "enc1:"
_SALT = b"ai-microscope-edu-llm-v1|"

def _key(serial: str) -> bytes:
    return hashlib.sha256(_SALT + serial.encode("utf-8")).digest()

def encrypt_secret(plain: str, serial: str) -> str:
    nonce = os.urandom(12)
    ct = AESGCM(_key(serial)).encrypt(nonce, plain.encode("utf-8"), None)
    return _PREFIX + (nonce + ct).hex()

def decrypt_secret(token: str, serial: str) -> str:
    raw = (token or "").strip()
    if not raw.startswith(_PREFIX):
        return raw
    blob = bytes.fromhex(raw[len(_PREFIX):])
    if len(blob) < 13:
        raise ValueError("enc1 密文过短")
    try:
        return AESGCM(_key(serial)).decrypt(blob[:12], blob[12:], None).decode("utf-8")
    except Exception as exc:
        raise ValueError("enc1 解密失败") from exc
```

每个对外函数写用途/参数/返回值/副作用。`requirements.txt` 增加两行依赖。本机 `python3 -m pip install 'ruamel.yaml>=0.18' 'cryptography>=42'`（若 pytest 缺包）。

- [ ] **Step 4: Run tests**

Run: `cd ai-microscope-edu/software && PYTHONPATH=. /usr/bin/python3 -m pytest tests/test_secret_box.py -q`

Expected: PASS

- [ ] **Step 5: Commit** — 跳过

---

### Task 2: 旋转几何与字幕分页

**Files:**
- Create: `ai-microscope-edu/software/system/display.py`
- Create: `ai-microscope-edu/software/system/captions.py`
- Test: `ai-microscope-edu/software/tests/test_display.py`、`tests/test_captions.py`

**Interfaces:**
- Produces:
  - `PHYSICAL_W, PHYSICAL_H = 1080, 1920`
  - `logical_size(pw: int, ph: int, deg: int) -> tuple[int, int]`
  - `normalize_rotation(deg: object) -> int`（非法 → 90）
  - `map_touch(px: float, py: float, pw: int, ph: int, deg: int) -> tuple[float, float]`
  - `PAGE_HOLD_S = 2.0`
  - `paginate(text: str, max_chars: int) -> list[str]`
  - `CaptionPager`：`show(text, max_chars, now)` / `tick(now)` / `clear()` / `visible_text`

- [ ] **Step 1: Write the failing tests**

`tests/test_display.py`：

```python
from system.display import PHYSICAL_H, PHYSICAL_W, logical_size, map_touch, normalize_rotation

def test_default_and_invalid_are_90() -> None:
    assert normalize_rotation(None) == 90
    assert normalize_rotation(45) == 90
    assert normalize_rotation(90) == 90

def test_logical_size_swaps_on_90_270() -> None:
    assert logical_size(PHYSICAL_W, PHYSICAL_H, 0) == (1080, 1920)
    assert logical_size(PHYSICAL_W, PHYSICAL_H, 90) == (1920, 1080)
    assert logical_size(PHYSICAL_W, PHYSICAL_H, 180) == (1080, 1920)
    assert logical_size(PHYSICAL_W, PHYSICAL_H, 270) == (1920, 1080)

def test_map_touch_center_90() -> None:
    lx, ly = map_touch(540, 960, 1080, 1920, 90)
    assert lx == pytest.approx(960, abs=1)
    assert ly == pytest.approx(540, abs=1)

def test_map_touch_identity_0() -> None:
    assert map_touch(10, 20, 1080, 1920, 0) == (10, 20)
```

`tests/test_captions.py`：短文一页；`max_chars=4` 时 `"abcdefgh"` 两页且每页 ≤4；`CaptionPager.show` 后 `tick(+2)` 翻页；`clear` 后 `visible_text==""`。

- [ ] **Step 2: Run tests — expect FAIL**

`pytest tests/test_display.py tests/test_captions.py -q`

- [ ] **Step 3: Implement**

`logical_size`：`deg = normalize_rotation(deg)`；90/270 返回 `(ph, pw)` 否则 `(pw, ph)`。

`normalize_rotation`：能转 int 且属于 `{0,90,180,270}` 才用，否则 90。

`map_touch`（物理 → 逻辑，顺时针）：

- 0: `(px, py)`
- 90: `(py, pw - px)`
- 180: `(pw - px, ph - py)`
- 270: `(ph - py, px)`

`paginate`：空串 `[]`；`max_chars<=0` 或全文更短则单页；否则按字切，遇空格且回退点 ≥ `max_chars//2` 则在词界切。

`CaptionPager`：`show` 重置页索引与时间戳；`tick` 若 `now - shown_at >= PAGE_HOLD_S` 且还有下一页则 `index+=1`；`clear` 清空。

- [ ] **Step 4: pytest PASS**
- [ ] **Step 5: Commit** — 跳过

---

### Task 3: 混音器命令与音量映射

**Files:**
- Create: `ai-microscope-edu/software/system/mixer.py`
- Test: `ai-microscope-edu/software/tests/test_mixer.py`

**Interfaces:**
- Produces:
  - `volume_pct_to_output(pct: int | float) -> int` → 0–33
  - `DEFAULT_VOLUME_PCT = 73`
  - `fixed_path_commands(card: int = 0) -> list[list[str]]`
  - `volume_commands(output: int, card: int = 0) -> list[list[str]]`
  - `apply_fixed_path(*, runner=...) -> None`
  - `apply_volume(pct: int, *, runner=...) -> None`

- [ ] **Step 1: Failing tests**

```python
def test_volume_map() -> None:
    assert volume_pct_to_output(0) == 0
    assert volume_pct_to_output(73) == 24
    assert volume_pct_to_output(100) == 33
    assert volume_pct_to_output(200) == 33

def test_fixed_path_contains_line2_and_pga() -> None:
    cmds = [" ".join(c) for c in fixed_path_commands()]
    joined = "\n".join(cmds)
    assert "Speaker" in joined and "on" in joined
    assert "Differential Mux" in joined and "Line 2" in joined
    assert "Left Channel" in joined and " 8" in joined
    assert "PCM" in joined

def test_apply_volume_calls_output_1_and_2() -> None:
    ran: list[list[str]] = []
    apply_volume(73, runner=lambda args, **k: ran.append(list(args)))
    flat = " ".join(" ".join(a) for a in ran)
    assert "Output 1" in flat and "Output 2" in flat and "24" in flat
```

`runner` 缺 `amixer` 时 `OSError` 必须吞掉（再写一个 test：`runner` 抛 `OSError`，`apply_fixed_path` 不抛）。

- [ ] **Step 2–4:** 实现 argv：`amixer -c 0 sset Speaker on` 等，与 README 现状一致（spk switch、Line 2、Channel 8、PCM 100%）。`apply_*` 对每条 `runner(cmd, check=False, capture_output=True, timeout=3)`。默认 `runner=subprocess.run`。
- [ ] **Step 5: Commit** — 跳过

---

### Task 4: 一份 edu.yaml

**Files:**
- Create: `ai-microscope-edu/software/system/edu_config.py`
- Create: `ai-microscope-edu/software/deploy/edu.yaml.example`
- Test: `ai-microscope-edu/software/tests/test_edu_config.py`

**Interfaces:**
- Produces:
  - `@dataclass EduSettings`：`v: int`、`rotation_deg: int`、`captions_enabled: bool`、`volume_pct: int`、`llm: dict[str, Any]`
  - `defaults() -> EduSettings`
  - `load_edu(path: Path) -> EduSettings`（缺/坏 → 默认；不半解析）
  - `save_edu(path: Path, settings: EduSettings) -> None`（ruamel，尽量留注释）
  - `patch_edu(path: Path, **fields) -> EduSettings`（读改写）
  - `maybe_migrate_llm_json(yaml_path: Path, json_path: Path, serial: str) -> None`

- [ ] **Step 1: Tests**

- 无文件：`rotation_deg==90`、`volume_pct==73`、`captions_enabled is False`、`llm=={}`
- 坏 yaml：同样回退
- `save` 再 `load` 保持 180° 与 `volume_pct=10`
- 文件里已有 `# keep-me` 注释，只 `patch` 音量后注释仍在（若 ruamel 丢注释则至少未改的 `llm.model` 还在）
- `llm.json` 有三件套、yaml 无 `llm.base_url`：`maybe_migrate_llm_json` 后 yaml 里 `api_key` 以 `enc1:` 开头，json 文件仍在

- [ ] **Step 3: Implement with ruamel.yaml `YAML(typ="rt")`**。`llm` 缺省 `{}`。样例 `deploy/edu.yaml.example` 按 spec §3 写注释，密钥写 `# api_key: enc1:...` 不要写真值。

`patch_edu` 只更新传入的顶层字段（`rotation_deg` / `captions_enabled` / `volume_pct` / `llm`）。

- [ ] **Step 4–5:** pytest PASS；Commit 跳过

---

### Task 5: LLM 从 yaml 加载、解密、reload

**Files:**
- Modify: `ai-microscope-edu/software/qa/client.py`（`load_llm_config`）
- Modify: `ai-microscope-edu/software/qa/turn.py`（yaml 路径 + `reload_llm`）
- Modify: `ai-microscope-edu/software/tests/test_qa_client.py`（json 夹具改 yaml）
- Test: `ai-microscope-edu/software/tests/test_qa_reload.py`

**Interfaces:**
- Consumes: `decrypt_secret`、`read_cpu_serial`、`load_edu`
- Produces:
  - `load_llm_config(path: Path, environ, *, serial: str | None = None) -> LlmConfig | None`
  - `QaService.reload_llm() -> None`（注入的 `config=` 构造则 no-op）

`path`：`edu.yaml` 文件，或含 `edu.yaml` 的目录，或目录 `var/`（读 `edu.yaml`）。**不再**从 `llm.json` 读运行时配置（迁移在 Task 4）。

环境变量规则与现在相同；`EDU_LLM_API_KEY` 出现则不走解密。yaml 里 `enc1:` 用 `serial or read_cpu_serial()` 解密，失败则该 key 当空（整份配置若缺三件套 → `None`）。

- [ ] **Step 1:** 改 `test_load_llm_config_*`：把 `llm.json` 写成 `edu.yaml`：

```yaml
llm:
  base_url: https://json.example.com/v1
  api_key: sk-json
  model: json-model
  timeout_secs: 45
```

`load_llm_config(tmp_path / "edu.yaml", ...)`。空目录仍 `None`。

新增 `test_qa_reload.py`：`QaService(qa_dir=..., config=None)` 先写 yaml 明文 key，`iter_tokens` mock 打到 url A；改 yaml 的 `base_url` 后 `reload_llm()`，再 `iter_tokens` 打到 url B。注入 `config=` 的实例 `reload_llm()` 不改 `_config`。

解密失败：yaml `api_key: enc1:00`，`serial="x"` → `load_llm_config` 返回 `None`（不要把乱码当 Bearer）。

- [ ] **Step 3:** `QaService` 默认 `edu_yaml = software/var/edu.yaml`，`USER.md` 仍 `var/qa/USER.md`。构造未注入 config 时 `load_llm_config(self._edu_yaml, env)`。启动时若 yaml 无 llm 则 `maybe_migrate_llm_json(edu_yaml, qa_dir/"llm.json", serial)` 再 load。

- [ ] **Step 4:** `pytest tests/test_qa_client.py tests/test_qa_reload.py tests/test_qa_prompt.py -q` PASS
- [ ] **Step 5: Commit** — 跳过

---

### Task 6: 会话字幕回调

**Files:**
- Modify: `ai-microscope-edu/software/voice/session.py`
- Modify: `ai-microscope-edu/software/tests/test_voice_session.py`（补回调断言）

**Interfaces:**
- `VoiceSession(..., on_asr=None, on_assistant_sentence=None, on_captions_clear=None)`
- 回调类型 `Callable[[str], None]` / `Callable[[], None]`；允许工作线程调用；内部 `try/except` 打日志，不影响 TTS。

调用点：

| 时机 | 回调 |
|------|------|
| `start_ptt` 成功 | `on_captions_clear()` |
| ASR 非空 | `on_asr(user_text)` |
| `player.submit(sentence)` 前 | `on_assistant_sentence(sentence)` |
| `_beep()` 前（失败/丢弃） | `on_captions_clear()` |
| `_run_turn` 在 `player.close()` 之后（成功或失败都清） | 成功 `played` 也 `on_captions_clear()`（播完即消失） |

成功路径：先句回调，播完再 clear。测试用现有 mock QA/TTS：收 `events` 列表，断言含 `("asr", "...")`、若干 `("sent", ...)`、最后 `("clear",)`。失败 beep 路径只有 clear，无 sent。

- [ ] **Step 4:** `pytest tests/test_voice_session.py tests/test_voice_turn.py -q` PASS
- [ ] **Step 5: Commit** — 跳过

---

### Task 7: 加宽分界线 + 设置页壳

**Files:**
- Modify: `ai-microscope-edu/software/app/theme.py`（handle width 32；设置页 QSS）
- Modify: `ai-microscope-edu/software/app/main_window.py`（`setHandleWidth(32)`；SETTINGS 用真页面）
- Modify: `ai-microscope-edu/software/app/shell_state.py` 仅当需要导出 `SPLIT_HANDLE_PX = 32`（可放 `app/theme.py` 或 `shell_state.py`）
- Create: `ai-microscope-edu/software/app/settings_page.py`
- Modify: `ai-microscope-edu/software/app/stub_pages.py`（SETTINGS 不再用 StubPage）
- Test: `ai-microscope-edu/software/tests/test_shell_state.py`（已有 settings 分屏且 strip 仍展开；保持）

**Interfaces:**
- `SettingsPage(on_close, settings: EduSettings, on_change, parent)` 信号或回调：`rotation_deg`、`captions_enabled`、`volume_pct` 变化；子页入口先做按钮，Task 9 再填编辑器。
- 触控：关闭钮、开关、旋转钮、滑条高度 **56**。分组标题「显示」「语音与问答」。

- [ ] **Step 1:** 在 `test_shell_state.py` 已有 `open_tool("settings")` → `split_open` 且不要藏 strip（`strip_expanded` 保持 True）。无需新状态。可加 `assert SPLIT_HANDLE_PX >= 24`。

- [ ] **Step 3:** `QSplitter.setHandleWidth(32)`；QSS `width: 32px`。`SettingsPage` objectName `settingsPage`，页头「设置」+「关闭」。`QStackedWidget`：首页分组 + 两个占位子页壳（标题+返回），避免后面再拆导航。

音量滑条 `sliderReleased`（及 `editingFinished`）才调用 `on_change(volume_pct=...)`。旋转四钮互斥。字幕 `QCheckBox` 或开关按钮。

`MainWindow._apply` 仍显示工具条。变化写入 `patch_edu` + 立刻副作用留给 Task 8/10（本任务可只改内存回调，`MainWindow` 先 `print`/调 `on_settings_patch`）。

- [ ] **Step 4:** `pytest tests/test_shell_state.py tests/test_icons.py -q` PASS。设置页不强制 Qt 单测。
- [ ] **Step 5: Commit** — 跳过

---

### Task 8: 立刻旋转宿主

**Files:**
- Create: `ai-microscope-edu/software/app/rotate_host.py`
- Modify: `ai-microscope-edu/software/app/main_window.py` 的 `main()`
- Modify: `ai-microscope-edu/software/app/settings_page.py`（旋转钮调用宿主）

**Interfaces:**
- `RotateHost.set_content(widget)` / `apply_rotation(deg: int)`（立刻）
- 首选 `QGraphicsView` + `QGraphicsProxyWidget`：`rotate(deg)` + `fitInView` 铺满物理屏。
- 若代理不接触摸：在 `RotateHost` 重写 `mousePress/Move/ReleaseEvent` 和 `event` 里的 touch，用 `map_touch` 把坐标转给内容（`QCursor`/`QTest` 不作为产品路径）。

`main()`：

```python
ensure_embedded_platform()
apply_theme(app)
cfg = load_edu(edu_yaml_path())
host = RotateHost()
win = MainWindow(edu=cfg)
host.set_content(win)
host.apply_rotation(cfg.rotation_deg)  # 先转再全屏，避免 0° 闪帧
host.showFullScreen()
```

`MainWindow` 不要自己 `showFullScreen`。设置里改角度：`patch_edu` + `host.apply_rotation`。非法角走 `normalize_rotation`。

内容逻辑尺寸 = `logical_size(host.width(), host.height(), deg)`。浮标仍跟预览 `resized`。

- [ ] **Step 4:** `pytest tests/test_display.py -q` PASS。211 手测点 0/90。
- [ ] **Step 5: Commit** — 跳过

---

### Task 9: 字幕条 + USER.md/LLM 子页

**Files:**
- Create: `ai-microscope-edu/software/app/caption_bar.py`
- Create: `ai-microscope-edu/software/app/settings_prompt.py`
- Create: `ai-microscope-edu/software/app/settings_llm.py`
- Modify: `ai-microscope-edu/software/app/preview_pane.py`（底部叠 `CaptionBar`，`WA_TransparentForMouseEvents`）
- Modify: `ai-microscope-edu/software/app/main_window.py`（Qt 信号排队回调）
- Modify: `ai-microscope-edu/software/app/platform.py` 或 `main()`：`QLocale(Chinese)` 当 `QT_IM_MODULE=qtvirtualkeyboard`

**Interfaces:**
- `CaptionBar.set_enabled(bool)` / `show_text(str)` / `clear()`；内部用 `CaptionPager` + 200ms `QTimer` 调 `tick`；`max_chars` 用两行 `QFontMetrics`（宽 / 平均汉字宽 × 2 行，至少 8）。
- `MainWindow` 定义 `asr_caption = Signal(str)` 等，`QueuedConnection` 接条。`VoiceSession` 回调只 `emit`。
- 字幕关：`CaptionBar.hide()`，会话仍跑。
- `settings_prompt.py`：`QTextEdit` + 保存/清空（清空 `QMessageBox` 确认）；读写 `var/qa/USER.md`。
- `settings_llm.py`：字段对齐 spec §8；key/secret 空占位「已加密保存，输入新密钥将覆盖」；保存时空 key 表示保持；写出 `enc1:`；`QaService.reload_llm()`。环境变量若 `in os.environ` 则只读 + 顶栏提示。三件套空拒绝保存。日志与异常字符串禁止包含明文 key。

- [ ] **Step 4:** `pytest tests/test_captions.py tests/test_qa_prompt.py tests/test_qa_reload.py tests/test_voice_session.py -q`
- [ ] **Step 5: Commit** — 跳过

---

### Task 10: 启动混音器、unit、README、样例

**Files:**
- Create: `ai-microscope-edu/software/deploy/edu-mixer.sh`（可执行，仅固定通路 `amixer`，不解析 yaml）
- Modify: `ai-microscope-edu/software/deploy/edu-app.service`
- Modify: `ai-microscope-edu/software/README.md`
- Modify: `ai-microscope-edu/software/app/main_window.py` `main()`：`apply_fixed_path()` + `apply_volume(cfg.volume_pct)`
- Delete or 保留 `deploy/llm.json.example`：README 改为指向 `edu.yaml.example`；可留 json 样例并注明已废弃。

**service 增加：**

```
ExecStartPost=/home/cat/ai-microscope-edu/software/deploy/edu-mixer.sh
Environment=QT_IM_MODULE=qtvirtualkeyboard
Environment=LANG=zh_CN.UTF-8
Environment=QT_VIRTUALKEYBOARD_AVAILABLE_LOCALES=zh_CN,en_US
```

README：

- 重启后 **不要** 再手跑 amixer。
- `var/edu.yaml` 配置；密钥为 `enc1:`。
- 211 安装：venv `pip install -r requirements.txt`；Debian 拼音：`qml6-module-qtquick-virtualkeyboard`（或板上实际包名）+ 拼音插件。验收拼「洋葱」。
- 手测清单抄 spec §12。

`edu-mixer.sh`：与 `fixed_path_commands()` 同一组 `amixer`（Speaker、spk switch、Line 2、Channel 8、PCM）。

- [ ] **Step 4:** 全量 `pytest tests/ --ignore=tests/test_ai_fab.py -q`（现网约 116+ 本刀新用例）
- [ ] **Step 5: Commit** — 跳过

---

## 211 手测（执行者，非 CI）

```bash
rsync -avz --exclude '.venv' --exclude '__pycache__' --exclude 'var' \
  software/ cat@10.198.24.211:/home/cat/ai-microscope-edu/software/
# 板上 venv: pip install -r software/requirements.txt
sudo cp software/deploy/edu-app.service /etc/systemd/system/edu-app.service
sudo cp software/deploy/edu-mixer.sh /home/cat/ai-microscope-edu/software/deploy/
chmod +x .../edu-mixer.sh
sudo systemctl daemon-reload && sudo systemctl restart edu-app
```

1. 点设置：三栏仍在；拖 32px 分界线明显比现在好抓；关闭全屏。
2. 无 yaml 首启横屏 90°；点 0° 立刻竖且触点跟手。
3. restart 后 PTT 有声，不手跑 amixer；滑条松手变响度。
4. 开字幕：ASR 出字；TTS 顶掉；播完消失。
5. USER.md 拼音「洋葱」。
6. 保存 LLM key 后 yaml 为 `enc1:`，页上无明文；错 serial/换板 beep。

**不要部署 235。**

---

## Spec coverage

| spec | 任务 |
|------|------|
| 一份 yaml、注释、默认 90/73/字幕关 | 4 |
| enc1 + CPU serial、不回显 | 1、5、9 |
| 迁移 llm.json | 4、5 |
| 现壳设置页、56px 控件、子页 | 7、9 |
| splitter ≥24（计划 32） | 7 |
| 立刻旋转 + map_touch | 2、8 |
| 字幕两行、2s 切幕、播完 clear | 2、6、9 |
| 混音器启动 + 音量松手 | 3、7、10 |
| USER.md / reload_llm | 5、9 |
| 拼音 VirtualKeyboard | 10 |
| 不藏工具条、不做 ISP/配网/关机 | 全局 |

## 非目标

ISP、Wi-Fi、关机、知识库、藏工具条半屏壳、linuxfb rotation 重启、算法配置并进 yaml、`enc2` / `.secret_key`、git commit。
