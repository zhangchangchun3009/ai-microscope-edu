# 教学一体机设置（壳 + 立刻旋转 + 语音配置）

> 状态：已批准（2026-09-14）；实现计划 [`../plans/2026-09-14-edu-settings.md`](../plans/2026-09-14-edu-settings.md)  
> 产品计划：[`../../plans/2026-09-07-ai-camera-closed-loop-plan.md`](../../plans/2026-09-07-ai-camera-closed-loop-plan.md)  
> UI 总规：[`2026-09-08-edu-kiosk-ui-design.md`](2026-09-08-edu-kiosk-ui-design.md) §4 / §8  
> 语音回合：[`2026-09-10-voice-qa-turn-design.md`](2026-09-10-voice-qa-turn-design.md)  
> 实现：`software/app/`（设置 UI、旋转宿主、字幕条）、`software/system/`（yaml、旋转几何、混音器、设备绑定加密）、已有 `qa/` / `voice/`  
> 对照（只读）：MicroClaw `enc2` + `.secret_key`（**不照抄**）；`microclaw/src/push/device_id.rs` 的 CPU Serial 读法。不引入 `~/.zeroclaw/`。

**已决：**

- 屏旋转必须 **立刻转**（画面 + 触点一起）。改 linuxfb 再重启不进本刀。
- 混音器固定通路不进设置 UI；音量进设置。
- 简单配置（方向、字幕开关、音量、LLM）**一份 YAML**；不要 JSON（不能写注释、手改不直观）。
- 缺省方向 **90° 横屏**。
- 字幕：一块最多两行的底栏；ASR 出字即显；TTS 后句顶前句；超长切幕；播完自己消失。
- 虚拟键盘必须能 **拼音打中文**。
- `api_key` / `device_secret` 用 **本机 CPU 序列号派生** 加解密，换板不可解，界面永不回显明文。
- 设置走 **现有壳**：预览 | 右栏 | 工具条。本刀把分界线做成手指拖得动（现 handle 太窄，板上等于没做）。

## 1. 目标

工具条点「设置」走现壳分屏：左预览、右设置、最右工具条仍在。教师在右栏转屏、开关字幕、调音量、改 `USER.md`、改 LLM。「关闭」后预览铺满。语音浮标一直在预览上。本刀补上 **可拖分界线**（手指能改左右比例）。211 重启 `edu-app` 后喇叭可用，不必手敲 `amixer`。

## 2. 本刀范围

| 做 | 不做 |
|----|------|
| 设置右栏走现壳 + 分组表单；提示词/LLM 子页；分界线可拖 | 相机 ISP、Wi-Fi、关机、知识库管理、历史「新对话」 |
| 旋转 0/90/180/270：**立刻**改 Qt 层；缺省 90 | linuxfb `rotation=` 重启；另做藏工具条半屏壳 |
| 字幕总开关默认关；开则底部最多两行只读框 + 切幕 | 学生改字幕、token 级逐字、上行 ASR / 下行 TTS 两行分栏 |
| 音量滑条 0–100，松手写 ALSA Output | 设置里出现 Speaker / Mux / PGA / PCM |
| 启动写混音器固定通路 + yaml 音量 | 把 `TTS_GAIN` 做成第二旋钮 |
| 编辑 `var/qa/USER.md`（仍独立 Markdown） | 把长文提示词塞进 yaml |
| `var/edu.yaml` 管显示/音量/LLM；密钥 `enc1:` 落盘 | 明文 key、把 yaml 拷到另一台板仍能用 |
| 触屏键盘：Qt VirtualKeyboard **中文拼音** | 自绘键盘、英文-only 就算过关 |
| 旧 `var/qa/llm.json` 若 yaml 尚无 LLM 段则迁移一次 | 继续双写 json；算法侧配置（融合/拼接/计数）并进这份 yaml |
| Mac 无 ALSA / 无 Serial：落盘与表单仍可用 | 在 235 部署 |

## 3. 一份 YAML

路径：`software/var/edu.yaml`（`var/` 已 gitignore）。样例带注释：`software/deploy/edu.yaml.example`。手改与 UI 保存都走同一文件。

用 **ruamel.yaml** 读写，尽量保留已有注释和键序。缺依赖或损坏则按 §9 整文件回退默认，不半解析。

```yaml
# 教学一体机简单配置。融合 / 拼接 / 计数等算法参数仍用各自文件，不写这里。
v: 1
display:
  rotation_deg: 90   # 物理 fb 1080×1920；90 = 逻辑横屏 1920×1080
  captions_enabled: false
audio:
  volume_pct: 73     # 映射 ALSA Output 0–33，73→24
qa:
  retain_days: 7      # 启动时删 updated_at 更早且非当前场；不进设置页
  context_turns: 8    # 送给 LLM 的当前场最近轮数
llm:
  base_url: https://www.aiinstrum.com/api-micro-llm/v1
  model: qwen-plus
  timeout_secs: 30
  # 下列密文由本机 CPU 序列号派生，换设备必须重填
  api_key: enc1:...
  device_secret: enc1:...
  device_secret_hosts:
    - www.aiinstrum.com
```

浮标 `var/ui/fab.json`、录音 `var/voice/last.wav`、`USER.md` **不**进这份 yaml。日后算法配置保持独立文件。

设置页改任一字段：读入 → 改对应键 → 写回（密钥见 §8）。`QaService.reload_llm()` 在保存 LLM 段后调用。

迁移：启动时若 `edu.yaml` 没有可用的 `llm` 段，且存在旧 `var/qa/llm.json`，则读 json、把密钥按本机加密写入 yaml，**不删除** json（以免回滚），但之后只认 yaml。

`edu-mixer.sh` 只写固定通路；音量由 Python 读 yaml 再 `amixer`（shell 不解析 yaml）。

## 4. 设置壳

### 4.1 打开 / 关闭（沿用现壳）

试过现 UI 后，设置 **继续用**「预览 | 右栏 | 工具条」，不要藏工具条、不要另做从右侧滑入的半屏。融合 / 拼接 / 历史占位页同一套。

| 状态 | 画面 |
|------|------|
| 默认主页 | 预览铺满；工具条在右缘；浮标在预览上 |
| 设置打开 | 左预览、右设置、最右工具条；默认左右 **1:1**（相对 splitter 区域，不含工具条宽度） |
| 设置关闭 | 右栏隐藏，预览铺满；工具条保持打开前的展开/折叠 |

关闭只点设置页头「关闭」（或子页返回后再关）。子页「返回」只退一层。点预览不关设置。浮标父控件始终是预览，分屏时夹紧到当前预览矩形，开着设置也能 PTT。

**分界线可拖：** 总规 §5 已要求，壳里已有 `QSplitter` 和 `SPLIT_MIN/MAX`（0.25–0.75），但 handle 只有 8 px，十寸触屏基本抓不住。本刀把分界线做成 **手指拖得动**：

- handle 命中宽度 ≥ **24 px**，颜色沿用现 QSS（`QSplitter::handle`）
- 拖动写入 `ShellState.split_ratio` 并夹紧；松开后比例留在内存，再开右栏仍用该比例（不写 yaml）
- linuxfb 上触摸应能拖；若系统只把触摸当鼠标，handle 仍要够宽

### 4.2 页内

页头：「设置」+「关闭」。两组，触控行高 ≥ 44 px：

| 组 | 行 | 行为 |
|----|----|------|
| 显示 | 字幕 | 与方向钮同高的 **开/关** 按钮（不用勾选框）；立刻显隐底栏并写 yaml |
| 显示 | 屏幕方向 | 四按钮 `0°` `90°` `180°` `270°`；点即转并写 yaml |
| 语音与问答 | 音量 | 滑条 0–100；**松手**写 `amixer` 与 yaml |
| 语音与问答 | 自定义问答助手 | 子页编辑 `USER.md` |
| 语音与问答 | 大模型 | 子页编辑 yaml 的 `llm` 段 |

子页栈深最多两层。融合 / 拼接 / 历史继续占位。

**虚拟键盘：** `QT_IM_MODULE=qtvirtualkeyboard`，默认 **zh_CN 拼音**（全键 + 候选栏），语言切换只保留 **简中 / 繁中 / 英文**（`VirtualKeyboardSettings.activeLocales` + `QT_VIRTUALKEYBOARD_AVAILABLE_LOCALES`）。`LANG`/`QLocale` 用简体中文。**禁止**走独立顶层 Desktop InputPanel（linuxfb + `RotateHost` 调不出）。改为 `QT_VIRTUALKEYBOARD_DESKTOP_DISABLE=1`，把 `InputPanel` 嵌进 `MainWindow` 底边（随内容一起旋转）。`InputPanel` 作为 `QQuickWidget` 根对象，视口跟着内容高度（含候选栏），避免最下一排被压扁。点键盘不得抢走编辑框焦点。**右栏始终可纵向滚动**（常显粗滚动条，触屏可拖）；键盘弹出时在内容下方垫一块与键盘等高的空白，把焦点/光标滚到键盘上方，不压缩设置页布局。linuxfb 用 `QT_QUICK_BACKEND=software`。板上须装与 Essentials **同版本** 的 `PySide6-Addons`（提供 `libQt6VirtualKeyboard*.so`）；Debian Qt 6.4 的 VirtualKeyboard 包不要混用。`edu-app.service` 把 `LD_LIBRARY_PATH` 指到 venv 的 `PySide6/Qt/lib`。验收：在 USER.md 里能拼出「洋葱」，并能切到英文。Mac 无该插件时可用外接键盘。

## 5. 立刻旋转

物理缓冲仍是 **1080×1920**。Qt 转整窗内容。

| `rotation_deg` | 逻辑画布 | 变换 |
|----------------|----------|------|
| 0 | 1080×1920 | 恒等 |
| 90 | 1920×1080 | 顺时针 90° |
| 180 | 1080×1920 | 180° |
| 270 | 1920×1080 | 顺时针 270° |

**缺省 90**（产品横装）。非法角度回退 **90**，不是 0。开机先读 yaml 再全屏，避免先以 0° 闪一帧。

接法不变：首选 `QGraphicsView` + `QGraphicsProxyWidget`；linuxfb 触摸穿不透则宿主逆变换。`map_touch` 必须单测。浮标仍是预览局部坐标，不改 `fab.json` 版本规则。

## 6. 字幕

默认 **关**。开：预览底部 **一块** 半透明深色只读框，最多 **两行**，不拦截点击。不是「上行用户 / 下行回答」分栏。

**分页（切幕）：** 按当前条宽度与字体度量，贪心装满两行（中文按字、英文尽量按词）得到若干幕。一幕显示长度记为 `max_chars`（UI 用 `QFontMetrics` 算，纯函数测试注入整数）。十寸横屏两行通常够一整句；分页是长句安全网。

| 阶段 | 行为 |
|------|------|
| ASR 成功 | 立刻把识别全文分页显示。多幕则每幕停留 **2 s** 再下一幕 |
| TTS | **句级跟读**：某句 **开始 aplay** 才上字幕（不是入合成队列时）。水位仍可提前合成多句，但字幕不得把未播的句闪完。 |
| 后续 TTS 句 | 下一句开口才顶掉前句 |
| 一句超长 | 按该句 PCM 时长均分各幕；最后一幕留到这句播完。不做逐字卡拉 OK |
| 播报结束（队列播完、回空闲） | **立刻隐藏** 整条，不把最后一句留到下一轮 |
| 失败 beep / 新一轮 `start_ptt` | 同样隐藏并取消切幕定时器 |

TTS 开口优先于 ASR 剩余阅读时间。关字幕则永不出现该框；开关不改变语音是否运行。

`VoiceSession` 回调可在工作线程触发，GUI 用排队信号更新：

| 回调 | 何时 |
|------|------|
| `on_asr(text)` | 判定通过且识别非空 |
| `on_assistant_sentence(text, duration_s)` | 该句 **开始播放**（`play_pcm` 之前），不是 `submit` 入队时 |
| `on_captions_clear()` | 回合成功播完、失败 beep、或新一轮开始录音 |

## 7. 混音器与音量

固定通路写死、不进 UI（与现 README 相同）：Speaker / spk switch on，Differential Mux = Line 2，Left/Right Channel = 8，PCM = 100%。

音量只调 Output 1 与 Output 2：`output = clamp(round(volume_pct * 33 / 100), 0, 33)`。缺省 `volume_pct = 73` → 24。0% 为 Output 0，不关 Speaker。`TTS_GAIN = 0.5` 不进 UI。

`ExecStartPost` 跑固定通路脚本；`main()` 再写通路 + yaml 音量。无 `amixer`（Mac）只记日志，yaml 仍保存。禁止再把「restart 后手跑 amixer」写进操作步骤。

## 8. 大模型与设备绑定密钥

字段与现 `load_llm_config` 对齐：`base_url`、`model`、`timeout_secs`（10–600，缺省 30）、`api_key`、`device_secret`、`device_secret_hosts`（列表；缺省 `www.aiinstrum.com`；显式空列表表示不加网关头）。

**设备 ID：** 与旧 OTA 同数据源，只用于派生加密密钥：优先设备树 `serial-number`，否则 `/proc/cpuinfo` 的 `Serial:`（小写 hex）。都没有时（Mac）用稳定回退 `macos-dev`，**不要**把板端密文拿到 Mac 上当可解密。单测注入假序列号。

**算法：** `key = SHA256(b"ai-microscope-edu-llm-v1|" + serial)`（32 字节）。AES-256-GCM 加密，`nonce` 12 字节随机。落盘 `enc1:` + hex(`nonce ‖ tag ‖ ciphertext`)。不把随机密钥另存文件（有意区别于 MicroClaw `enc2` + `~/.zeroclaw/.secret_key`：yaml 单独拷到另一台 RK 板必然失败）。

明文（迁移来的旧 json、或教师新输入）在 **下一次写入 yaml 前** 加密。读盘：`enc1:` 用本机 serial 解密；失败则该密钥视为缺失（本轮 beep），设置页提示「密钥无法在本机解密，请重新输入」，**绝不**把错误解密结果当 Bearer。非 `enc1:` 前缀当明文，保存时改写成 `enc1:`。

**界面永不回显明文：** 已保存时输入框空、占位「已加密保存，输入新密钥将覆盖」；不填表示保持原密文。日志禁止打印 key。yaml 样例里只写 `enc1:` 占位或注释，不写真密钥。

保存：三件套（url / 解密后的 key / model）非空才写 LLM 段并 `reload_llm()`；进行中的回合不中断。环境变量 `EDU_LLM_*` 只要出现在进程环境则对应项只读并提示锁定；当前 unit **不**设这些变量。

`USER.md` 仍按 §总规 8.1：独立文件、截断 1000 字、保存后下一轮生效、清空要确认。

## 9. 落盘与缺省

| 位置 | 缺省 / 损坏时 |
|------|----------------|
| `display.rotation_deg` | **90** |
| `display.captions_enabled` | false |
| `audio.volume_pct` | 73 |
| `llm.*` | 无配置 → 回合 beep |
| `var/qa/USER.md` | 不加该段 |

`v` 从 1 起。目录不存在则保存时创建。

## 10. 模块

| 文件 | 职责 |
|------|------|
| `system/edu_config.py` | 读/写 `edu.yaml`（ruamel）；缺省与校验 |
| `system/device_id.py` | 读 CPU 序列号 / 可注入 |
| `system/secret_box.py` | `enc1` 加解密（无 Qt） |
| `system/display.py` | `logical_size`、`map_touch` |
| `system/mixer.py` | 固定通路、`volume_pct_to_output`、`apply_*` |
| `system/captions.py` | `paginate(text, max_chars) -> list[str]` |
| `deploy/edu-mixer.sh` | 仅固定通路 |
| `deploy/edu.yaml.example` | 带注释样例 |
| `app/rotate_host.py` | 物理全屏宿主 |
| `app/shell_state.py` | 现有分屏状态；`set_split_ratio` 夹紧 0.25–0.75（本刀不改语义） |
| `app/settings_page.py` | 分组与子页栈 |
| `app/settings_prompt.py` / `settings_llm.py` | USER.md；LLM 表单（不回显 key） |
| `app/caption_bar.py` | 两行框、2 s 切幕、播完隐藏 |
| `qa/client.py` / `qa/turn.py` | 从 yaml 的 `llm` 段加载；`reload_llm()` |
| `voice/session.py` | 字幕回调 |
| `app/main_window.py` | 宿主、混音器初始化、右栏接线、加宽可拖分界线、字幕接线 |
| `deploy/edu-app.service` | `ExecStartPost`；`QT_IM_MODULE`；中文 locale |

venv 增加 `ruamel.yaml`、`cryptography`（AES-GCM）。不要在设置页拼 `amixer`。

## 11. 错误

- `amixer` / 固定通路失败：日志警告，不崩溃，yaml 仍保存用户值。
- 旋转变换异常：保持上一成功角度。
- yaml / USER.md 写失败：界面提示，不装成已保存。
- 解密失败：当无 key，不把乱码送出网。
- 字幕回调抛错：会话抓住，不影响 TTS。

## 12. 测试

不依赖 211：

- `logical_size`：90/270 → 1920×1080；0/180 → 1080×1920；缺文件默认 90
- `map_touch`：90° 四角（1 px 误差）
- `volume_pct_to_output`：0→0、73→24、100→33
- 固定通路含 Line 2、Channel 8
- yaml 缺段回退；保存音量不丢 LLM 段注释（至少不丢未改键）
- 同一 serial 加解密往返；换 serial 解密失败
- 无 `enc1:` 前缀当明文，保存后变为 `enc1:`
- `paginate`：短文一幕；超 `max_chars` 多幕且每幕不超过上限
- `reload_llm` 后 mock 打到新 `base_url`；解密失败则 `iter_tokens` 空
- 会话回调：ASR、入队句、播完/beep/`start_ptt` 会 clear
- 打开 `settings`：`split_open`、工具条仍显示；`close_right` 后右栏关、预览铺满
- `set_split_ratio` 夹紧到 [0.25, 0.75]
- USER.md 保存/清空仍截断进 system

211 手测：

1. 点设置：左预览右设置，工具条仍在；浮标在预览上能 PTT；手指能拖中间分界线改比例；关闭后全屏。
2. 无 yaml 首启即为 **90° 横屏**；点 0° 立刻竖过来且触点跟手；重启保持。
3. `restart edu-app` 后 PTT 有声，不必手跑 amixer；滑条能改变响度。
4. 开字幕：ASR 出字即显（两行）；回答后句顶前句；播完底栏消失，不留到下一问。
5. USER.md 能用拼音输入汉字。
6. 填 LLM key 保存后 yaml 为 `enc1:`，设置页看不到明文；把该 yaml 拷到另一台（或改测试 serial）下一问 beep，重填后恢复。
7. 改 USER.md 下一问能听出效果。

## 13. 非目标

ISP、配网、关机、知识库、识图、改分句水位、混音器通路进设置、linuxfb 重启旋转、藏工具条再滑出半屏设置、把算法参数合并进 `edu.yaml`、MicroClaw `.secret_key` / `enc2` 格式。
