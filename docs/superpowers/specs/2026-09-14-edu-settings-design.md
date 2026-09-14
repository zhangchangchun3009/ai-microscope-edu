# 教学一体机设置（壳 + 立刻旋转 + 语音配置）

> 状态：待用户审阅（2026-09-14）  
> 产品计划：[`../../plans/2026-09-07-ai-camera-closed-loop-plan.md`](../../plans/2026-09-07-ai-camera-closed-loop-plan.md)  
> UI 总规：[`2026-09-08-edu-kiosk-ui-design.md`](2026-09-08-edu-kiosk-ui-design.md) §8  
> 语音回合：[`2026-09-10-voice-qa-turn-design.md`](2026-09-10-voice-qa-turn-design.md)（本刀补上该 spec 明确不做的字幕条与设置页）  
> 实现：`software/app/`（设置 UI、旋转宿主、字幕条）、`software/system/`（旋转几何、混音器）、已有 `qa/` / `voice/`  
> 对照（只读）：旧 Flutter 设置分组；mipi-hmi 混音器经验。不抄 mipi-hmi 进程，不引入对话面板打字。

**已决：** 屏旋转必须 **立刻转**（画面 + 触点一起）。改 `QT_QPA_PLATFORM` / 内核 fb、再 `systemctl restart` 只允许作为 211 上两种 Qt 接法都失败后的 spec 修订，不进本刀实现。混音器固定通路（spk / Line 2 / PGA）**不进设置 UI**，在服务启动与应用初始化写入。音量大小进设置。

## 1. 目标

工具条「设置」打开现有分屏右栏，从占位页换成可点的分组表单。教师能当场：

1. 把 1080×1920 竖屏 framebuffer 转到安装方向，手指点哪里控件就在哪里；
2. 开关字幕、改喇叭音量、改 `USER.md`、改 `llm.json`。

学生主路径仍是语音，不在设置外打字。211 上重启 `edu-app` 后喇叭仍可用，不必再手敲 `amixer`。

## 2. 本刀范围

| 做 | 不做 |
|----|------|
| 设置右栏：分组列表 + 提示词子页 + LLM 子页；关闭按钮与现壳一致 | 相机 ISP、Wi-Fi、关机、知识库管理、历史「新对话」 |
| 旋转 0/90/180/270：**立刻**改 Qt 层逻辑方向并落盘 | 改 linuxfb `rotation=`、写 unit 后重启才转（本刀不实现这条路径） |
| 字幕总开关，默认关；开则预览底部两行只读条 | 学生改字幕文字、把字幕当输入框 |
| 音量滑条 0–100，立刻写 ALSA Output，落盘 | 设置里出现 Speaker / spk switch / Differential Mux / PGA / PCM |
| 启动时写混音器固定通路 + 已存音量（unit `ExecStartPost` 与 `main()` 各调一次） | 把 `TTS_GAIN` 做成第二个音量旋钮 |
| 编辑 `var/qa/USER.md`；保存后下一轮注入（仍截断 1000 字） | 改领域短提示 `QA_ROLE_CORE` |
| 编辑 `var/qa/llm.json`；保存后 `QaService` 重载，下一轮用新配置 | 把密钥写进 git；在设置里展示环境变量明文 |
| Mac 无 ALSA / 无 VirtualKeyboard：落盘与表单仍可用 | 在 235 部署 |

## 3. 设置壳

右栏 `RightPanel.SETTINGS` 不再用 `StubPage`。页头：「设置」+「关闭」（关分屏，与占位页相同）。

正文可滚动，两组，行高适合十寸触控（控件高度 ≥ 44 px）：

| 组 | 行 | 行为 |
|----|----|------|
| 显示 | 字幕 | 开关；立刻显隐字幕条并写入 `display.json` |
| 显示 | 屏幕方向 | 四个互斥按钮：`0°` `90°` `180°` `270°`；点即转并写入 `display.json` |
| 语音与问答 | 音量 | 横滑条 0–100，旁注当前整数；**松手**时写 `amixer` 与 `audio.json`（滑动中不打子进程） |
| 语音与问答 | 自定义问答助手 | 进入子页编辑 `USER.md` |
| 语音与问答 | 大模型 | 进入子页编辑 `llm.json` |

子页仍在右栏内（栈深最多两层），子页头为标题 +「返回」，不关分屏。融合 / 拼接 / 历史继续占位。

触屏键盘：`edu-app.service` 增加 `QT_IM_MODULE=qtvirtualkeyboard`。多行框、单行框在焦点时弹出。板上未装对应包时输入法为空操作，外接键盘与 Mac 开发仍可编辑；实现计划把 211 安装列为部署步骤，不另做自绘键盘。

## 4. 立刻旋转

物理缓冲保持 **1080×1920**（linuxfb 直写 `/dev/fb0`）。产品安装角度用 Qt 转 **整窗内容**，不改内核、不改 `QT_QPA_PLATFORM`。

| `rotation_deg` | 逻辑画布 | 变换 |
|----------------|----------|------|
| 0 | 1080×1920 | 恒等 |
| 90 | 1920×1080 | 顺时针 90° |
| 180 | 1080×1920 | 180° |
| 270 | 1920×1080 | 顺时针 270°（即逆时针 90°） |

缺省 **0**（与当前未转的教学壳一致）。非法角度回退 0。

**接法（必须立刻、必须带触点）：**

1. **首选** `QGraphicsView` + `QGraphicsProxyWidget` 包住现有 `MainWindow` 内容：`rotate(deg)` 后 `fitInView` 铺满物理屏。Qt 把鼠标/触摸映到代理控件。
2. 若 211 上 linuxfb 触摸穿不透代理：宿主拦截 `QTouchEvent` / `QMouseEvent`，用与画面相同的逆变换送到子窗。纯函数 `map_touch(px, py, physical, deg) -> (lx, ly)` 必须单测。

`main()`：最外层全屏控件是旋转宿主，物理尺寸仍是 framebuffer；内层逻辑宽高随角度变。角度变化后预览 `resized` 会夹紧浮标（预览局部坐标语义不变）。不要为旋转改 `fab.json` 版本规则。

开机：读 `var/ui/display.json` 再 `showFullScreen`，避免先以 0° 闪一帧再跳。设置里改角度：同一进程立刻 `apply`，禁止 `systemctl restart`。

## 5. 字幕

默认 **关**。开：预览 **底部** 一条半透明深色条（约 50% 黑），**不拦截点击**（浮标仍可按）。

| 行 | 内容 | 更新时机 |
|----|------|----------|
| 上 | 本轮 ASR | 识别成功后整句写入；下一轮 `start_ptt` 清空两行 |
| 下 | 本轮回答 | **按句**更新：该句被播放器取走去合成时写入，不按 token 刷 |

关：隐藏整条，主界面除工具条外无问答文字。开关不改变 ASR/LLM/TTS 是否运行。

`VoiceSession` 增加可选回调，**允许在工作线程调用**；`MainWindow` 用 Qt 信号排队到 GUI 线程再改字幕。回调缺省空操作，现有 pytest 不因未注入回调失败。

| 回调 | 何时 |
|------|------|
| `on_asr(text)` | 判定通过且识别非空 |
| `on_assistant_sentence(text)` | 一句进入播放路径时（与现有分句队列同一批句） |
| `on_captions_clear()` | 新一轮开始录音，或本轮失败 beep 回空闲 |

失败 beep：清字幕，不留半句。

## 6. 混音器与音量

ES8388 固定通路与现 README 一致，**写死、不进 UI**：

- Speaker on、spk switch on
- Differential Mux = Line 2
- Left/Right Channel = 8（24 dB）
- PCM = 100%

音量 **只调** `Output 1` 与 `Output 2`（同一整数）。UI 0–100 映射：

```
output = clamp(round(volume_pct * 33 / 100), 0, 33)
```

缺省 `volume_pct = 73` → Output **24**（现状）。0% 为 Output 0（静音），不关 Speaker。`TTS_GAIN = 0.5` 仍只做满幅保护，设置里不出现。

启动顺序：`edu-mixer.sh` 作 `ExecStartPost`（用户 `cat`，已在 `audio` 组）→ `main()` 里再调同一套 Python API（读 `audio.json` 后写 Output，并重写固定通路）。开发机直接 `python -m app` 也走 Python 路径。Mac / `amixer` 不存在：固定通路与音量调用记日志后返回，**仍落盘**。

重启会冲掉混音器：本刀之后 **禁止** 再把「restart 后手跑一串 amixer」当成操作步骤；README 改为指向脚本/服务。

## 7. 自定义问答助手

子页多行编辑，文案「自定义问答助手」。读写 `var/qa/USER.md`（已 gitignore 的 `var/`）。OTA 不得带一份覆盖用户文件的 USER.md。

- 磁盘可长于 1000 字；送模型仍截断（现 `qa/prompt.py`）。
- **保存**：写盘。`QaService` 每轮已读文件，不必 reload；下一轮生效。
- **清空**：确认后再删内容（写成空文件或删除文件，读侧都当未配置）。
- 空内容不加该段（现逻辑）。

## 8. 大模型

子页字段与现 `load_llm_config` 对齐：`base_url`、`api_key`（密码框）、`model`、`timeout_secs`（10–600，缺省 30）、`device_secret`（密码框）、`device_secret_hosts`（逗号分隔）。json 未写 `device_secret_hosts` 时表单展示 `www.aiinstrum.com`；json 里写了空列表则展示空（表示不加网关头）。

保存：校验三件套非空后写 `var/qa/llm.json`，调用 `QaService.reload_llm()`（仅对自行读盘的实例；测试注入的假 config 不被设置页碰到）。进行中的回合不中断，**下一轮**用新配置。三件套空则拒绝保存并提示，不写残缺文件。

`EDU_LLM_BASE_URL` / `EDU_LLM_API_KEY` / `EDU_LLM_MODEL` / `EDU_LLM_DEVICE_SECRET` / `EDU_LLM_DEVICE_SECRET_HOSTS` 只要 **出现在进程环境**（空串也算）：对应表单项只读，页顶一句「该字段由服务环境变量锁定」。当前 `edu-app.service` **不**设这些变量，设置页默认可写。不要在界面回显完整密钥；已存密钥用掩码，再编辑即覆盖写入。

样例仍是 `deploy/llm.json.example`。真密钥只存在板端 `var/`。

## 9. 落盘

| 文件 | 字段 | 损坏/缺文件 |
|------|------|-------------|
| `var/ui/display.json` | `v`、`rotation_deg`、`captions_enabled` | 旋转 0、字幕关 |
| `var/ui/audio.json` | `v`、`volume_pct` | 73 |
| `var/qa/USER.md` | 正文 | 不加该段 |
| `var/qa/llm.json` | 现有字段 | 无配置则回合 beep（与现在相同） |

`v` 从 1 起。损坏、缺字段、非有限数字与浮标 JSON 一样整文件回退默认，不半解析。目录不存在则保存时创建（同 `fab_store`）。

## 10. 模块

| 文件 | 职责 |
|------|------|
| `system/display.py` | 读/写 `display.json`；`logical_size`；`map_touch`（无 Qt） |
| `system/mixer.py` | 固定通路 argv；`volume_pct_to_output`；`apply_fixed_path`；`apply_volume`（子进程 `amixer`，可注入 runner） |
| `deploy/edu-mixer.sh` | 与 Python 相同的固定通路；读 `audio.json` 写 Output；供 `ExecStartPost` |
| `app/rotate_host.py` | 物理全屏宿主 + 变换；启动与设置共用 `apply(deg)` |
| `app/settings_page.py` | 分组列表、子页栈、关闭/返回 |
| `app/settings_prompt.py` | USER.md 编辑 |
| `app/settings_llm.py` | llm.json 表单 |
| `app/caption_bar.py` | 预览底字幕条 |
| `qa/turn.py` | `reload_llm()` 再跑 `load_llm_config` |
| `voice/session.py` | 字幕回调；不在此画 UI |
| `app/main_window.py` / `app/__main__.py` | 宿主、初始化混音器、接线 |
| `deploy/edu-app.service` | `ExecStartPost=` 混音器脚本；`QT_IM_MODULE` |

`app/` 只调度。不要在设置页里内联拼 `amixer` 字符串。

## 11. 错误

- `amixer` 失败：音量 UI 保持用户值并落盘，日志警告；不崩溃。固定通路失败同样只记日志（否则无桌面 kiosk 会起不来）。
- 旋转变换异常：保持上一成功角度，日志警告。
- USER.md / llm.json 写失败：子页提示失败，不装成已保存。
- 字幕回调抛错：会话抓住并记日志，不影响 TTS。

## 12. 测试

先测后实现，不依赖 211：

- `logical_size`：0/180 保持 1080×1920；90/270 为 1920×1080
- `map_touch`：四角在 90° 映射到逻辑四角（允许 1 px 取整误差）
- 坏 `display.json` / `audio.json` 回退默认
- `volume_pct_to_output`：0→0、73→24、100→33
- 固定通路命令含 Line 2、Channel 8、Speaker on；`apply_volume` 对 Output 1/2 调同一值
- `reload_llm` 后 `iter_tokens` 打到新 `base_url`（mock）
- USER.md 保存/清空后 `build_system_prompt` 有/无该段
- 会话：注入回调，ASR 与入队句按序到达；beep 路径会 `on_captions_clear`
- 设置状态：开关字幕、改角度只改 store，不在 pytest 里点 linuxfb

211 手测（本刀验收）：

1. 设置里点 90°，整窗立刻横过来，点工具条/浮标位置与画面一致；再开到 0° 恢复；重启服务方向仍在。
2. `systemctl restart edu-app` 后直接 PTT，喇叭有声，**不必**再手跑 amixer。
3. 音量滑条能听出明显变小/变大。
4. 开字幕：问一句，底栏先出现识别、再按句出现回答；关掉后主界面无问答字。
5. 改 USER.md 保存，下一问能听出提示词起作用；改 llm 错误密钥则下一问 beep，改回后恢复。

## 13. 非目标

ISP 手调、配网红点、关机确认、知识库 HTTP/触屏 CRUD、识图、改分句水位、把混音器通路做成高级设置、linuxfb 重启旋转方案。
