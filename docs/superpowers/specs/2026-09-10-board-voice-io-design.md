# 板载语音进出（PTT 录音回放）

> 状态：与用户对齐（2026-09-10）：第一刀只验板载麦和喇叭；单次上限 **300 s**。ASR / 问答 / TTS 见 [`2026-09-10-voice-qa-turn-design.md`](2026-09-10-voice-qa-turn-design.md)。  
> 产品计划：[`../../plans/2026-09-07-ai-camera-closed-loop-plan.md`](../../plans/2026-09-07-ai-camera-closed-loop-plan.md) §4.9  
> UI 总规：[`2026-09-08-edu-kiosk-ui-design.md`](2026-09-08-edu-kiosk-ui-design.md) §4  
> 实现目录：`software/voice/`（纯逻辑）；`software/app/` 只把浮标 PTT 接到会话  
> 对照（只读）：`microscope/python/audio_service/audio_capture.py`、`audio_playback.py`（`arecord` / `aplay`）；`microscopy-front/lib/services/wav_audio_probe.dart`（静音峰值）；Flutter PTT 定界。不抄 `voice_http`、不启 `audio_service`、不用平板麦。

## 1. 目标

学生按住预览上的 AI 浮标，对着 **LubanCat 板载麦** 说话，松开后喇叭把 **刚才这段录音** 播回去。用来同时证明采和播。

本刀结束后：211 上能闭环听自己的声音。把同一份 WAV 送给 SenseVoice、回答走 Sherpa 的闭环见问答回合 spec，本文件不实现模型。

## 2. 依赖与边界

- 采音、放音都在 **本机 ALSA**，设备 ``hw:0,0``（RK3576 + ES8388），录音 **44100 Hz** 单声道 ``S16_LE``；播放前把单声道左右复制成立体声再 ``aplay -c 2``。该芯片按 I2S 双声道取数，单声道 ``-c 1`` 大约会以 2 倍速播出（尖、快）。不要硬灌 16 kHz。回放原声先做自适应噪声门，再按峰值放大（落盘 WAV 保持原电平，不门控）。
- 实现思路抄 `AlsaSubprocessCapture` / `AlsaSubprocessPlayback`：子进程 `arecord` / `aplay`，stderr 抽空，`aplay` 超时 = 时长 + 12 s（不少于 20 s）。**不**引入流式按帧 + Silero VAD（那是板端本地监控链，Agent/PTT 不用）。
- **不**启动 scandog、`audio_service`、`:8098`。教学进程内库调用。
- **不**做对话面板、字幕条、识图。忙（录音或回放）时忽略新的按住，与总规半双工一致。
- 同一 `plughw:0,0` 不能同时录和播：停录之后再 `aplay`。
- systemd：`edu-app.service` 的 `SupplementaryGroups` 增加 `audio`。`cat` 若不在 `audio` 组，板端补一次。
- Mac 无 ALSA：捕获/播放用 mock，pytest 只测 WAV 与会话状态机。

## 3. 会话状态

`voice/` 提供无 Qt 的 `VoiceSession`。`app/` 订阅浮标 `ptt_changed`：

| 事件 | 行为 |
|------|------|
| `ptt=True` 且空闲 | 开 `arecord`，写 `software/var/voice/last.wav`（覆盖） |
| `ptt=True` 且忙碌 | 忽略 |
| `ptt=False` 或满 **300 s** | 停录；满 300 s 时按已录内容进入判定 |
| 判定通过 | 先噪声门再放大，`aplay` 回放该 WAV 的前 **15 s**（`ECHO_MAX_S`），播完回空闲。录音仍可长达 300 s；全长回放会堵住 linuxfb 主线程，下一刀改 TTS 后不再回放原声。 |
| 判定失败 | 不回放原声；播一发短提示音（§5），回空闲 |

单击浮标仍不弹窗（壳层已有）。PTT 手势阈值（0.35 s / 24 px）不变。

## 4. 判定（抄旧前端，写死数字）

旧 Flutter **没有**单独的最短秒数，只丢空包和静音。一体机再加一条过短，避免刚过 PTT 门槛的按键噪声被回放。

| 条件 | 阈值 | 来源 |
|------|------|------|
| 过短 | PCM 时长 **&lt; 400 ms** | 略长于浮标 PTT 门槛 350 ms |
| 静音 | s16le 绝对值峰值 **&lt; 200** | `WavAudioProbe` 默认，约 −44 dBFS |
| 上限 | **300 s** 到点停录并进入判定 | 用户 2026-09-10 改为 5 分钟，避免课堂讲解被截断 |

WAV 容器：标准 RIFF、PCM fmt=1，与日后 `POST` SenseVoice / 板端 `common/sensevoice_asr.py` 吃的整段文件同形。

回放噪声门（只作用于喇叭，不改 `last.wav`）：20 ms 帧 RMS；丢掉开头 80 ms 再取 25 分位作噪声 \(N\)；开门 \(\max(3.5N,\ 400)\)，关门 \(2.2N\)，保持 120 ms。若整段最大 RMS \(< 4N\) 则跳过，避免把整句切没。常数在 `voice/config.py`，工位底噪变了再调。

## 5. 提示音（本刀不用 TTS 模型）

丢弃或开麦失败时：合成约 200 ms、880 Hz 的 s16le 单声道 beep，播放前同样升成立体声，经同一 `aplay` 设备播放。不依赖 espeak，也不拉 Sherpa。

预览角标可继续显示「说话中」；丢弃不必上字幕（字幕开关仍在设置，本刀不做设置页）。

## 6. 模块划分

| 文件 | 职责 |
|------|------|
| `voice/wavutil.py` | s16le ↔ WAV、峰值、时长、过短/静音判定、回放噪声门 |
| `voice/alsa.py` | `arecord` 起停写成 PCM/WAV；`aplay` 播 WAV 或 raw |
| `voice/session.py` | `VoiceSession`：空闲 / 录音 / 回放；300 s；忙碌忽略 |
| `voice/__init__.py` | 对外：`start_ptt` / `stop_ptt` / `is_busy` |
| `app/` | 组合：浮标 → session；不写 ALSA 细节 |

配置（设备名、采样率）放 `voice/config.py` 常量，需要时再抬到设置页。默认 `hw:0,0`，播放声道数为 2。

问答闭环（不在本 spec 实现）：见 [`2026-09-10-voice-qa-turn-design.md`](2026-09-10-voice-qa-turn-design.md)。

## 7. 错误

| 情况 | 行为 |
|------|------|
| `arecord` / `aplay` 不存在 | 提示音 + 日志；保持空闲 |
| 设备忙或 3 s 无数据 | 停录，当失败 |
| WAV 损坏 | 当失败 |
| 回放中途浮标再按 | 忽略，播完为止 |

## 8. 测试

先测后实现，不依赖板子：

- WAV 封装与峰值 / 时长 / 过短 / 静音 / 噪声门
- `VoiceSession`：忽略忙碌、300 s 截断、失败不调用 play 原声、成功才 play；门控不写入 last.wav
- mock 捕获注入固定 PCM

211 手测：按住说话松开，喇叭回放；捂住麦或空按，只听到 beep、没有原声。不强制 pytest 打真 ALSA。

## 9. 非目标

SenseVoice / Sherpa / espeak 对话、字幕条、USER.md、知识库、相机帧、VAD 长监听、远程平板录音。
