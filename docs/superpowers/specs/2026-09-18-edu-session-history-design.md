# 教学一体机会话落盘与历史页

> 状态：已批准（2026-09-18）；实现计划 [`../plans/2026-09-18-edu-session-history.md`](../plans/2026-09-18-edu-session-history.md)  
> 产品计划：[`../../plans/2026-09-07-ai-camera-closed-loop-plan.md`](../../plans/2026-09-07-ai-camera-closed-loop-plan.md)  
> UI 总规：[`2026-09-08-edu-kiosk-ui-design.md`](2026-09-08-edu-kiosk-ui-design.md) §5 / §7  
> 语音回合：[`2026-09-10-voice-qa-turn-design.md`](2026-09-10-voice-qa-turn-design.md)（本刀补磁盘场次与历史页；不改分句水位 / ASR / TTS 通路）  
> YAML：[`2026-09-14-edu-settings-design.md`](2026-09-14-edu-settings-design.md) §3（本刀给 `qa` 段）  
> 实现：`software/qa/`（库、切场、标题）、`software/system/edu_config.py`、`software/app/`（历史右栏）、`software/voice/`（ASR 后拦截）  
> 对照（只读）：总规原先「20 场文件」作废；不抄 microclaw 会话目录、不引入对话输入框。

**已决：**

- SQLite 只存对话场次与轮次。知识库表、HTTP 导入、FTS **本刀不做**。
- 历史页 **只读展示**。旧场不能变回当前场，不能在旧场里续聊。所有语音问答只写入 **当前场**。
- 「新对话」入口：语音 **整句等于** 四句口令之一（主）+ 历史栏大按钮（后备）。**不进设置**。不做语意模糊匹配。
- 语音命中后 **跳过 LLM**，程序切场，TTS 固定句「已处于新对话」。切场 **不** 用 LLM 总结正文。
- 标题：空场为「新对话」；有第一句 user 则截断约 20 字；该场 **第一轮完整成功后** 再 **异步** 一次短 LLM 覆盖；失败保留原标题。不把标题绑进首轮流式正文。
- 保留天数、送给 LLM 的当前场轮数都在 **`edu.yaml` 的 `qa` 段**，缺省 `retain_days: 7`、`context_turns: 8`。本刀设置页不加这两项滑条（手改 yaml 即可）。
- 清理按场的 `updated_at` 删除早于 `retain_days` 且不是当前场的记录。只在 **进程启动时后台线程跑一次**，不在每轮问答里扫库。
- 约 20 分钟无问答仍自动新开（时长本刀不进 yaml）。空当前场则复用，不连建空场。

## 1. 目标

5.5 寸继续开发。学生语音问完能在工具条「历史」里回看本周对话；也能说「新对话」或点按钮开一场新的。发给模型的上下文只带 **当前场最近 `qa.context_turns` 轮**（缺省 8）。

211 点验：历史列表可点、正文只读、新对话钮与语音切场后喇叭说「已处于新对话」。Mac 跑 pytest。

## 2. 本刀范围

| 做 | 不做 |
|----|------|
| `var/qa/sessions.sqlite`：场 + 轮次 | 知识库 SQLite / FTS / 学校导入 HTTP |
| 当前场 id；成功轮次落盘；半句失败不写 | 把旧场设为当前、在历史里续聊 |
| 启动线程按 `retain_days` 删过期非当前场 | 每轮问答扫库；按场数封顶 |
| 历史分屏：列表 + 只读正文 +「新对话」钮 | 历史里打字发送；设置里放新对话 |
| ASR 后四句口令整句拦截 → 切场 → TTS 固定句 | 语意模糊匹配；切场时 LLM 总结正文；首轮流式里夹标题 |
| 第一句作标题，首轮成功后异步补 LLM 标题 | 标题与问答正文同一路 SSE |
| `QaMemory` 轮数上限读 `context_turns`，数据来自当前场 | 把整场未截断送模型 |

## 3. 存储

路径：`software/var/qa/sessions.sqlite`（`var/` 已 gitignore）。标准库 `sqlite3`，`WAL`，进程内一把锁（问答线程、标题线程、清理线程共用）。

```text
sessions (
  id          TEXT PRIMARY KEY,   -- 本机生成的不透明 id，如 ulid/uuid
  title       TEXT NOT NULL,      -- 空场「新对话」
  created_at  REAL NOT NULL,      -- unix 秒
  updated_at  REAL NOT NULL
)
turns (
  id          INTEGER PRIMARY KEY,
  session_id  TEXT NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
  seq         INTEGER NOT NULL,   -- 场内从 1 递增
  user_text   TEXT NOT NULL,
  assistant_text TEXT NOT NULL,
  created_at  REAL NOT NULL,
  UNIQUE(session_id, seq)
)
meta (
  key   TEXT PRIMARY KEY,
  value TEXT NOT NULL
)
-- meta.current_session_id = 当前场 id
```

启动：打开库、建表；若 `current_session_id` 空或指向已删行，则插入一场空「新对话」并写入 meta。然后后台线程：`DELETE` `updated_at < now - retain_days` 且 `id != current` 的 sessions（CASCADE 删 turns）。清理失败只打日志。

`retain_days` / `context_turns` 从 `edu.yaml` 的 `qa` 段读取，非法或缺失用缺省 7 / 8；钳制为整数 **≥ 1**（天数上限 3650，轮次上限 64）。当前场永不因保留规则删除（即使 `updated_at` 很旧：只要仍是 current，就留着；切场之后它才可能在下次启动被删）。本刀 **不** 在设置 UI 里暴露这两项。手改 yaml 后重启进程生效（`QaService` 构造时读一次；本刀不做热重载）。

```yaml
qa:
  retain_days: 7      # 启动线程删 updated_at 更早且非当前场
  context_turns: 8    # 送给 LLM 的当前场最近轮数
```

## 4. 当前场与切场

`QaService` 持有 `current_id` 与 `QaMemory`。

- **写入：** 仅当流式/回退 **完整成功** 后追加一轮到当前场，并 `memory.append_turn`。与语音回合 spec 一致：已播部分再失败不写 assistant。
- **读给 LLM：** `memory.messages()` 最多 `context_turns` 轮，且只含当前场。
- **切场**（20 分钟空闲 / 语音关键字 / 历史钮）同一函数 `start_new_session()`：
  - 当前场 **零轮次** → 复用，不新建。
  - 否则冻结该场（保留在库），新建空场，清空 memory，更新 `current_session_id`。
- 点历史列表 **只改变阅读选中项**，不调用 `start_new_session`，不改 `current_id`。
- 浮标说话始终写入当前场，与历史页正在看哪一场无关。

## 5. 标题

1. 新空场：`title = 「新对话」`。
2. 当前场第一轮写入 user 时：若标题仍是「新对话」，改为 user 去空白后截断 **20 字**（不拆 UTF-8 码点）。
3. 该场 **第一轮** 完整成功后，后台再发一次短 completion（同一 `LlmConfig`、短 timeout、零工具）：输入为本轮 user+assistant 截断，要求只回一行不超过 20 字的标题、不要引号和「标题：」前缀。校验长度后覆盖 `sessions.title`。失败、超时、空串：保持步骤 2。
4. 之后的轮次 **不再** 改标题。
5. 禁止把「请同时输出标题」注入常规问答 system，避免标题进分句 TTS。

## 6. 语音「新对话」

时机：SenseVoice 出非空文本之后、`KnowledgeRecall` / 组 LLM 消息之前。

判定（纯函数，便于单测）：去掉空白与常见标点（。！？,.!?、）后，整句 **必须等于** 口令表之一才命中（教用户说「新对话 / 新会话」；不做包含匹配、不靠 LLM 语意）。

口令表：

- 新对话
- 新会话
- 新建对话
- 新建会话
- 新绘画（SenseVoice 常把「会话」听成「绘画」；教室里这两句没有别的意思）
- 新建绘画

| 句 | 命中 |
|----|------|
| 新对话 | 是 |
| 新会话 | 是 |
| 新建对话 | 是 |
| 新建会话 | 是 |
| 新绘画 | 是 |
| 新建绘画 | 是 |
| 「 新对话。」（仅空白/标点） | 是 |
| 开始新会话 | 否 |
| 新的对话 | 否 |
| 新的对话方式是什么 | 否（走问答；知识库条目可答） |
| 洋葱表皮是什么 | 否 |

命中：不请求 LLM；调用 `start_new_session()`；TTS 合成固定句 **「已处于新对话」**（走现有单句 TTS / `aplay`，不走问答分句队列）。字幕总开着则这条上字幕条。浮标忙碌覆盖到这句播完或 beep。

未命中：走现有问答回合。

按钮「新对话」调用同一 `start_new_session()` 与同一 TTS 句，不另写一套。

## 7. 历史页 UI

工具条「历史」打开现壳分屏。右栏：

- 顶栏：标题「历史」+「新对话」钮 +「关闭」（关闭恢复预览铺满，与设置页一致）。
- 左：会话列表，按 `updated_at` 新→旧。当前场一行带「当前」标记。触控行高与设置页控件同级。
- 右：选中场的只读轮次。每块标题为「用户」或「助手」+ 该轮 `created_at` 的本地时间（`YYYY年MM月DD日 HH:MM:SS`）+ 中文冒号，正文另起。用户块与助手块用不同背景色；正文字号大于设置表单（约 22px）。**禁止划选**；正文常显滚动条。无输入框、无发送。空场显示「还没有问答」。
- 打开历史页时从库刷新列表；语音切场后若历史页开着，刷新列表，阅读选中项可保持原 id（若仍存在）。

浮标仍叠在左侧预览，分屏时也能按住说话。

## 8. 失败

| 情况 | 行为 |
|------|------|
| 库打不开 | 问答仍用内存 `context_turns` 轮（重启丢失）；历史页提示无法读取 |
| 落盘失败 | 本轮不进历史页；memory 仍可有这一轮直到切场/重启 |
| 标题 LLM 失败 | 保留第一句标题 |
| 切场成功、TTS 失败 | 已是新场，beep |
| 启动清理失败 | 日志；不挡开界面 |
| 无 LLM 配置 | 问答与现逻辑一致；切场 TTS 仍可（本地合成）；异步标题跳过 |

## 9. 测试

先测后写（Mac pytest）：

- 空场切场复用；有轮次则新建；20 分钟空闲切场。
- 写入一轮后列表可见；半句失败路径不插入 turns。
- 关键字正误例（§6 口令表，含「新绘画」转义）。
- 按注入的 `retain_days` 清理过期非当前场，保留当前场与窗口内场。
- 标题 20 字截断；异步成功覆盖、失败保持。
- `messages()` 最多 `context_turns` 轮且只含当前场。

历史页布局、linuxfb、TTS「已处于新对话」在 211 点验。

## 10. 非目标

知识库、识图进历史、导出、多用户、设置页滑条改 `retain_days`/`context_turns`、在 235 部署。
