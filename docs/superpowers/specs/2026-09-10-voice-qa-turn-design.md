# 语音问答一轮（ASR → 快速问答 → TTS）

> 状态：按 2026-09-10 审阅意见：知识库只留接口；LLM 流式；**先缓存 2～3 句再播**，生产/消费用队列对齐  
> 产品计划：[`../../plans/2026-09-07-ai-camera-closed-loop-plan.md`](../../plans/2026-09-07-ai-camera-closed-loop-plan.md) §4.7 / §4.9  
> UI 总规：[`2026-09-08-edu-kiosk-ui-design.md`](2026-09-08-edu-kiosk-ui-design.md) §4  
> 录音进出：[`2026-09-10-board-voice-io-design.md`](2026-09-10-board-voice-io-design.md)  
> 问答槽对照（只读）：[`../../../../docs/superpowers/specs/2026-08-17-fast-qa-conversation-mode-design.md`](../../../../docs/superpowers/specs/2026-08-17-fast-qa-conversation-mode-design.md)（组消息、超时、流式 + 非流式回退；不抄 WS 时间线）  
> 实现：`software/voice/`、`software/qa/`、`software/app/` 接线  
> 对照（只读）：`sensevoice_asr.py`、`agent_tts_sherpa.py`、`qa_turn.rs`。不抄 `:8098`、`audio_service`、Rust 网关。

ASR / TTS 照搬旧板端。本刀增量：**流式问答 + 分句队列 + 按句 TTS**、忙时浮标禁用。知识库只留注入口，不建 SQLite。

等整段 LLM 再合成会偏慢；切出第一句立刻播又容易切错，模型一顿喇叭就空。本刀折中：**流式进队列，攒够 2～3 句（或流结束）再开播**，之后一句接一句，队列做生产和消费的缓冲。

## 1. 目标

按住浮标说完松开：识别 `last.wav` → 流式收回答并分句入队 → **未播句达到 2～3 句（或生成结束）后开始 TTS**，串行播完。不再回放原声。

211：应在开头两三句就绪后出声，而不是等全文；也不应在第一处句号就开口。失败只 beep。从按住录音到 **队列播完**（或 beep），浮标不可按。

## 2. 本刀范围

| 做 | 不做 |
|----|------|
| SenseVoice；16 kHz 临时 WAV，**不改** `last.wav` | `:8098`、VAD、回放原声 |
| OpenAI 兼容流式 SSE；零工具；关思考；SSE 失败再非流式一次拿全文 | 字幕条（流式文本先不画） |
| 按句入队；**开播水位 2 句**，预取目标 **3 句**；喇叭串行，不叠音 | 切出一句立刻播；多句并行 TTS |
| `var/qa/USER.md` 若存在则截断 1000 字接到 system | 设置页编辑提示词 |
| `KnowledgeRecall.lookup(text) -> str`，本刀恒返回 `""` | SQLite、FTS、导入、触屏知识库 |
| 内存最近 **8** 轮；约 20 分钟无问答则新开一场 | 历史页、磁盘 20 场 |
| 只发文本 | 当前帧 / ROI 识图 |
| 后台线程：ASR、读 SSE、分句、TTS、`aplay` | GUI 线程阻塞 linuxfb |
| 忙碌时浮标 **禁用** 直到空闲 | 只吞事件但浮标仍像能按 |

## 3. 回合与浮标

判定 `ok` 后进入 `turning`（与 `recording` 一样忙碌）：

1. 重采样 → SenseVoice；空文本或失败 → beep → 空闲。
2. 组消息同旧 qa 槽：短 system（生物学 + `{datetime}` + 可选 USER.md）→ 历史 → 本轮 user（KB 块本刀为空）。超时默认 **30 s**（10–600）。流式失败则非流式回退；两种结果都进入同一套分句播放。失败 / 超时且尚无已播句子 → beep，不写 assistant。若已播出部分句子再失败：停队列、不写 assistant（避免半句进历史），浮标恢复。
3. **分句 → 队列（生产）**：token 遇到 `。！？!?` 或换行则切出一句（标点留在句尾）。不要按逗号切。流结束或非流式全文到达后，剩余缓冲非空也入队。
4. **短句合并（减少误切）**：入队前若本句去掉空白和句末标点后 **少于 8 字**，且队列里或后续还能接到下一句，则与下一句拼成一句再入队（例如「好。」+「这是洋葱表皮。」）。流已结束且只剩这一短句，则照播，不再等。
5. **消费（TTS）**：未播句 **≥ 2** 才开始第一句 `aplay`；生成已结束则有一句就播（避免只有一句时卡死）。播放期间尽量让队列里维持 **2～3** 句未播：模型快、TTS 慢时队列可以超过 3（全文都留下，**不丢句**）；TTS 快、模型慢时队列空了就等下一句，允许句间短暂静音，不要把未完成的缓冲拿去合成。一句 Matcha → 22050 → 立体声 `aplay`，**播完再取下一句**。单句失败：beep、丢弃未播句。

6. 队列播完（或按上款失败）后：仅当流/回退 **完整成功** 时把整段 assistant 原文写入历史。空闲，浮标恢复。

`app/`：`is_busy()` 为真则浮标 `setEnabled(False)`。覆盖录音 + ASR + 攒句 + **队列播完**，不是松开就恢复。

关窗 `abort()`：停录或放弃回合（不承诺杀掉 HTTP），停当前 `aplay`，清空未播句，恢复浮标。

实现状态（2026-09-10）：`abort()` 不分相位置位一个 `threading.Event`，回合循环在每次
`synthesize` / `play_pcm` 前检查并收手（返回 `aborted`，不 beep、不写 assistant）；关窗对工作
线程 `join(timeout=PTT_JOIN_TIMEOUT_S)`。**已经交给 `aplay` 的那一句仍会播完**——中断在播进程
需要把 `subprocess.run` 换成 `Popen` + `terminate`，留作后续。自动收尾（300 s / 3 s 无数据）
禁用浮标前必须调 `AiFab.cancel_ptt()`：Qt 不向禁用控件派发 release，否则 PTT 高亮会卡住。

## 4. 模块

| 文件 | 职责 |
|------|------|
| `voice/asr.py` | 16 kHz、`sensevoice_demo`、`Output:`、PTT 尾部清理 |
| `voice/tts.py` | 一句文本→PCM（Matcha 22050 s16le；无 sherpa 则 Mock）。不直接 `aplay` |
| `voice/alsa.py` | `play_pcm(pcm, sample_rate=None)` 覆盖 aplay `-r`，仍先升混立体声 |
| `qa/sentences.py` | 流式增量分句、短句合并、开播水位（纯函数/小队列，便于测） |
| `qa/prompt.py` | system / 可选 KB 前缀 / user |
| `qa/knowledge.py` | `KnowledgeRecall` + `EmptyRecall` |
| `qa/client.py` | SSE 流式；失败则非流式；`enable_thinking=false`；白名单 host 附加 `X-Device-Secret` |
| `qa/session.py` | 8 轮记忆、20 分钟切场 |
| `voice/session.py` | 判定后调度；按句调用 TTS+播放 |
| `app/` | PTT；工作线程；按 busy 禁用浮标 |

配置：ASR/TTS 路径对齐现网。LLM：`var/qa/llm.json` + `EDU_LLM_*`。缺配置 → beep。自建 nginx 网关对照 MicroClaw：请求 URL host 命中白名单时附加 `X-Device-Secret`。不引入 MCP SDK。SSE 可用标准库读 chunk，若实现时过痛再加一个轻量 HTTP 依赖（计划里写明）。

## 5. 错误

过短 / 静音 / 开麦失败 / ASR 空 / 首句都未播出的 LLM 失败 / 某句 TTS 失败：beep，浮标回到可用。忙碌按浮标：无效果。

## 6. 测试

- 重采样；`Output:` 与「，请。」清理
- 分句：`你好。世界！` → 两句；无句号的尾包在结束时成一句；逗号不断句
- 短句合并：「好。」+「这是洋葱。」→ 一句；开播：未结束时 1 句不得 TTS，2 句才允许第一句；流结束后 1 句也要播
- 无 KB 时 user 即原文；假 `lookup` 非空时 user 前有块；USER.md 截断进 system
- 流式 mock 按 token 喂入，断言 TTS 顺序；非流式回退同样走队列
- 超时且零句已播：不写 assistant；busy 时 `start_ptt` 为 False
- 浮标 busy 禁用、空闲启用

211：问一句，应在攒了开头几句后出声，而不是等全文、也不是第一处句号就开口；捂麦 beep；未空闲时浮标按不动。

## 7. 非目标

字幕 UI、识图、SQLite 知识库、设置页、配网关机、门控再调参、多句并行 TTS。
