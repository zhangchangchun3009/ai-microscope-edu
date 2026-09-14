# 教学一体机设置（壳 + 立刻旋转 + 语音配置）

> 状态：按 2026-09-14 审阅意见修订，待再确认  
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
- 打开设置：**隐藏整条工具条**，设置页从右侧占 **半屏**；关掉后回到全屏主页并 **展开显示工具条**。语音浮标始终叠在预览上。

## 1. 目标

工具条点「设置」：工具条收掉，右侧弹出半屏设置页（不是「预览 | 设置 | 工具条」三栏）。教师在半屏里转屏、开关字幕、调音量、改 `USER.md`、改 LLM。关掉设置回到全屏预览，工具条回来。语音浮标一直在预览上，分屏时也能按住说话。211 重启 `edu-app` 后喇叭可用，不必手敲 `amixer`。

## 2. 本刀范围

| 做 | 不做 |
|----|------|
| 设置右栏：隐藏工具条 + 右侧半屏分组表单；提示词/LLM 子页 | 相机 ISP、Wi-Fi、关机、知识库管理、历史「新对话」 |
| 旋转 0/90/180/270：**立刻**改 Qt 层；缺省 90 | linuxfb `rotation=` 重启路径 |
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

### 4.1 打开 / 关闭（与现壳分屏不同）

现壳是「预览 | 右栏 | 工具条」：右栏出来时工具条仍占右缘。**设置不走这条。**

| 状态 | 画面 |
|------|------|
| 默认主页 | 预览铺满；工具条在右缘（展开）；浮标在预览上 |
| 设置打开 | 工具条 **整条隐藏**（含折叠柄）；窗口左右 **1:1**：左预览、右设置；浮标仍在左预览 |
| 设置关闭 | 回到默认主页：预览铺满，工具条 **展开显示**（不恢复打开前的折叠态） |

打开：设置页从右缘滑入到半屏（约 200–300 ms）。linuxfb 若动画掉帧或抢触控，则瞬时出现，不要为动画卡住。关闭：滑出或瞬时收起，然后显示工具条。

半屏相对 **整窗** 1:1（横屏约 960|960），不是「去掉工具条宽度后再对半」。当次允许拖分割条；关掉后丢弃比例，下次打开再 1:1。不能点预览空白关闭（易误触）；只通过设置页头「关闭」。子页「返回」只退一层，不关设置。

融合 / 拼接 / 历史本刀仍占位，**仍用现壳**（工具条留着）。以后若那些页也要藏工具条，另改定，不在本刀偷改。

语音浮标父控件始终是预览，分屏时夹紧到当前预览矩形内。设置开着也能 PTT。

### 4.2 页内

页头：「设置」+「关闭」。两组，触控行高 ≥ 44 px：

| 组 | 行 | 行为 |
|----|----|------|
| 显示 | 字幕 | 开关；立刻显隐底栏并写 yaml |
| 显示 | 屏幕方向 | 四按钮 `0°` `90°` `180°` `270°`；点即转并写 yaml |
| 语音与问答 | 音量 | 滑条 0–100；**松手**写 `amixer` 与 yaml |
| 语音与问答 | 自定义问答助手 | 子页编辑 `USER.md` |
| 语音与问答 | 大模型 | 子页编辑 yaml 的 `llm` 段 |

子页栈深最多两层。融合 / 拼接 / 历史继续占位。

**虚拟键盘：** `QT_IM_MODULE=qtvirtualkeyboard`，默认 **zh_CN 拼音**（全键 + 候选栏），可切英文。`LANG`/`QLocale` 用中文。211 必须装 Qt VirtualKeyboard **以及拼音插件**；验收：在 USER.md 里能拼出「洋葱」。缺插件视为部署失败，不把英文-only 当合格。Mac 无该插件时可用外接键盘，包括中文输入法。

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
| 第一句 TTS 取走合成 | **立刻顶掉** 当前画面（含未读完的 ASR 幕），改为该句的分页 |
| 后续 TTS 句 | 后句整页顶掉前句；该句超长则同样 2 s 切幕 |
| 无 token 级显示 | 切幕不必与喇叭逐字对齐；可接受短暂不同步 |
| 播报结束（队列播完、回空闲） | **立刻隐藏** 整条，不把最后一句留到下一轮 |
| 失败 beep / 新一轮 `start_ptt` | 同样隐藏并取消切幕定时器 |

TTS 到达优先于 ASR 剩余阅读时间。关字幕则永不出现该框；开关不改变语音是否运行。

`VoiceSession` 回调可在工作线程触发，GUI 用排队信号更新：

| 回调 | 何时 |
|------|------|
| `on_asr(text)` | 判定通过且识别非空 |
| `on_assistant_sentence(text)` | 一句被播放器取走去合成（与现分句队列同一批句） |
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
| `app/shell_state.py` | 打开设置则分屏且工具条隐藏；关闭则全屏并展开工具条 |
| `app/settings_page.py` | 分组与子页栈 |
| `app/settings_prompt.py` / `settings_llm.py` | USER.md；LLM 表单（不回显 key） |
| `app/caption_bar.py` | 两行框、2 s 切幕、播完隐藏 |
| `qa/client.py` / `qa/turn.py` | 从 yaml 的 `llm` 段加载；`reload_llm()` |
| `voice/session.py` | 字幕回调 |
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
- 打开 `settings`：`split_open` 且工具条隐藏；`close_right`：全屏且 `strip_expanded` 为真；浮标仍属预览
- USER.md 保存/清空仍截断进 system

211 手测：

1. 点设置：工具条消失，右半是设置、左半是预览，浮标还在预览上能按住说话；点关闭回到全屏且工具条展开。
2. 无 yaml 首启即为 **90° 横屏**；点 0° 立刻竖过来且触点跟手；重启保持。
3. `restart edu-app` 后 PTT 有声，不必手跑 amixer；滑条能改变响度。
4. 开字幕：ASR 出字即显（两行）；回答后句顶前句；播完底栏消失，不留到下一问。
5. USER.md 能用拼音输入汉字。
6. 填 LLM key 保存后 yaml 为 `enc1:`，设置页看不到明文；把该 yaml 拷到另一台（或改测试 serial）下一问 beep，重填后恢复。
7. 改 USER.md 下一问能听出效果。

## 13. 非目标

ISP、配网、关机、知识库、识图、改分句水位、混音器通路进设置、linuxfb 重启旋转、把算法参数合并进 `edu.yaml`、MicroClaw `.secret_key` / `enc2` 格式。
