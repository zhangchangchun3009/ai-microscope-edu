# 设备端软件（`ai-microscope-edu/software`）

教学一体机 PySide6 kiosk。Mac 编辑，需要板端显示时 rsync 到 **211**（`cat@10.198.24.211`）。**235 只读对照，不部署。**

## 当前：无桌面教学壳

教学应用以 `python -m app` 启动。系统关闭图形桌面并停用 scandog/mipi-hmi 后，由 Qt 独占 MIPI（DSI-1）。

板端路径：

- 代码：`/home/cat/ai-microscope-edu/software/`
- venv：`/home/cat/ai-microscope-edu/.venv/`（不进 git）
- 语音模型：`/home/cat/ai-microscope-edu/models/`（不进 git；运行时不要再指向 `/home/cat/microscope/`）
- 服务：`edu-app.service`

```bash
rsync -avz --exclude '.venv' --exclude '__pycache__' --exclude 'var' \
  software/ cat@10.198.24.211:/home/cat/ai-microscope-edu/software/
ssh cat@10.198.24.211 'sudo cp /home/cat/ai-microscope-edu/software/deploy/edu-app.service /etc/systemd/system/edu-app.service && sudo systemctl disable --now edu-kiosk-probe && sudo systemctl daemon-reload && sudo systemctl enable --now edu-app && journalctl -u edu-app -n 30 --no-pager'
```

确认教学壳与旧服务状态：

```bash
ssh cat@10.198.24.211 'systemctl is-active edu-app; systemctl is-enabled edu-kiosk-probe; systemctl is-enabled scandog'
```

当前 unit 使用 `linuxfb`（直写 `/dev/fb0`）。`eglfs_kms` 在 Mesa 上会因缺少 `EGL_EXT_device_base` 而 ABRT；接通硬件加速时再验证 Mali GBM（`/usr/lib/aarch64-linux-gnu/mali` + `libmali.so`）。

板端应显示深色预览「等待相机」、右侧圆形图标工具条，以及预览右侧居中的麦克风浮标。若仍停在左上角，删掉板端 `software/var/ui/fab.json` 后重启服务。`kiosk_probe` 仍保留用于诊断，但不再作为默认 systemd 入口。

## 板载语音点验

PTT 闭环是 **ASR → 快速问答 → TTS**，不再回放自己的原声。

`groups` 输出必须包含 `audio`，否则把 kiosk 用户加入音频组，并重新登录或重启服务：

```bash
groups
sudo usermod -aG audio cat
sudo systemctl restart edu-app
```

手测：

- 按住麦克风浮标问一句生物学相关问题，松开后应听到 **TTS 回答**（攒够开头两三句后出声，不是等全文，也不是第一处句号就开口）。
- 捂住麦克风录音再松开：只听到提示音（beep），没有原声、没有回答。
- 松开后到喇叭播完（或 beep）之前，浮标灰色、按不动；录音过程中仍可抬手结束。
- 单次录音上限 300 秒。失败（过短 / 静音 / 缺 LLM / ASR 空）只 beep。

## LLM 与语音模型配置

问答读 `software/var/qa/llm.json`（目录已 gitignore）。样例：

```bash
mkdir -p var/qa
cp deploy/llm.json.example var/qa/llm.json
# 再改 base_url / api_key / model；timeout_secs 缺省 30
```

字段：`base_url`、`api_key`、`model`、`timeout_secs`。三件套缺一则本轮 beep。可选 `device_secret` / `device_secret_hosts`（对照 MicroClaw：仅白名单 host 附加 `X-Device-Secret`；未写则用与 `config-default.toml` 相同的缺省）。可选 `var/qa/USER.md`（截断 1000 字接到 system）。

**LLM 环境变量**：只有这三个会覆盖 `llm.json` 的同名字段（**没有** `EDU_LLM_TIMEOUT`；超时只认 json 的 `timeout_secs` / `timeout_s`）：

| 变量 | 覆盖 json 字段 |
|------|------|
| `EDU_LLM_BASE_URL` | `base_url` |
| `EDU_LLM_API_KEY` | `api_key` |
| `EDU_LLM_MODEL` | `model` |
| `EDU_LLM_DEVICE_SECRET` | 覆盖 `device_secret`；空串禁用该头 |
| `EDU_LLM_DEVICE_SECRET_HOSTS` | 逗号分隔覆盖 `device_secret_hosts` |

**ASR / TTS 环境变量**：不涉及 `llm.json`；缺省指向本应用 `models/`（见 `voice/config.py` 与 `edu-app.service`）。文件不存在时识别为空、TTS 回退 Mock（短正弦，不是人声）。venv 需要 `sherpa-onnx==1.13.2`。

| 变量 | 板上缺省 |
|------|------|
| `EDU_SENSEVOICE_DEMO` | `models/sensevoice/sensevoice_demo`（同目录 `lib/` 为 `$ORIGIN/lib`；还要有 `model/am.mvn`，否则 demo 仍 exit 0 但无 `Output:`） |
| `EDU_SENSEVOICE_MODEL` | `models/sensevoice/sensevoice_f32.rknn` |
| `EDU_SENSEVOICE_TOKENS` | `models/sensevoice/tokens.txt` |
| `EDU_TTS_MODEL_DIR` | `models/matcha-icefall-zh-baker` |
| `EDU_TTS_VOCODER` | `models/vocos-22khz-univ.onnx` |

## 211 同步与手测

在 Mac 仓库的 `ai-microscope-edu/` 下用本文开头「板端路径」一节的 `rsync` 同步（不要重复维护两份命令）。

板上：放入 `var/qa/llm.json`（不要 rsync 覆盖 var）。ASR/TTS 已指向本应用 `models/`，不必再引用旧 `microscope/`。重启后重设混音器（spk / Line 2 / PGA 24dB / Output 拉满）：

```bash
sudo systemctl restart edu-app
amixer -c 0 sset Speaker on
amixer -c 0 sset "spk switch" on
amixer -c 0 sset "Differential Mux" "Line 2"
amixer -c 0 sset "Left Channel" 8
amixer -c 0 sset "Right Channel" 8
amixer -c 0 sset "Output 1" 33
amixer -c 0 sset "Output 2" 33
amixer -c 0 sset PCM 100%
```

重启会冲掉混音器，必须在 `restart` **之后**再跑 `amixer`。
