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

问答与显示读 `software/var/edu.yaml`（`var/` 已 gitignore）。带注释样例：

```bash
mkdir -p var
cp deploy/edu.yaml.example var/edu.yaml
# 再在设置页或手改 yaml：方向 / 字幕 / 音量 / llm 段
```

密钥字段（`api_key` / `device_secret`）落盘为 `enc1:` 密文，由本机 CPU 序列号派生，换板不可解。设置页不回显明文；空输入表示保持原密文。

`qa.retain_days`（启动时删过期非当前场）与 `qa.context_turns`（送给 LLM 的当前场最近轮数）可选手改 yaml，**重启进程生效**；本刀设置页不加滑条。缺省 7 天 / 8 轮。

旧 `deploy/llm.json.example` 与 `var/qa/llm.json` **已废弃**。启动时若 yaml 尚无可用 `llm` 段且存在旧 json，会迁移一次（不删除 json）；之后只认 yaml。

`USER.md` 仍独立：`var/qa/USER.md`（截断 1000 字接到 system）。

**LLM 环境变量**：只要出现在进程环境就覆盖 yaml `llm` 段的同名字段并在设置页锁定（**没有** `EDU_LLM_TIMEOUT`；超时只认 yaml 的 `timeout_secs`）。当前 `edu-app.service` **不**设置这些变量。

| 变量 | 覆盖 yaml 字段 |
|------|------|
| `EDU_LLM_BASE_URL` | `base_url` |
| `EDU_LLM_API_KEY` | `api_key` |
| `EDU_LLM_MODEL` | `model` |
| `EDU_LLM_DEVICE_SECRET` | 覆盖 `device_secret`；空串禁用该头 |
| `EDU_LLM_DEVICE_SECRET_HOSTS` | 逗号分隔覆盖 `device_secret_hosts` |

**ASR / TTS 环境变量**：不涉及 yaml；缺省指向本应用 `models/`（见 `voice/config.py` 与 `edu-app.service`）。文件不存在时识别为空、TTS 回退 Mock（短正弦，不是人声）。venv 需要 `sherpa-onnx==1.13.2`。

| 变量 | 板上缺省 |
|------|------|
| `EDU_SENSEVOICE_DEMO` | `models/sensevoice/sensevoice_demo`（同目录 `lib/` 为 `$ORIGIN/lib`；还要有 `model/am.mvn`，否则 demo 仍 exit 0 但无 `Output:`） |
| `EDU_SENSEVOICE_MODEL` | `models/sensevoice/sensevoice_f32.rknn` |
| `EDU_SENSEVOICE_TOKENS` | `models/sensevoice/tokens.txt` |
| `EDU_TTS_MODEL_DIR` | `models/matcha-icefall-zh-baker` |
| `EDU_TTS_VOCODER` | `models/vocos-22khz-univ.onnx` |

## 211 安装、同步与手测

在 Mac 仓库的 `ai-microscope-edu/` 下用本文开头「板端路径」一节的 `rsync` 同步（不要重复维护两份命令；**不要 rsync 覆盖 `var/`**）。**235 只读对照，不部署。**

板上 venv 补依赖：

```bash
cd /home/cat/ai-microscope-edu/software
/home/cat/ai-microscope-edu/.venv/bin/pip install -r requirements.txt
```

虚拟键盘走 **PySide6-Addons**（与 Essentials **同版本** 的 Qt VirtualKeyboard，含拼音）。`pip install -r requirements.txt` 会装上。**不要**再 `apt` 装 Debian Qt 6.4 的 `qml6-module-qtquick-virtualkeyboard`：版本对不上，InputPanel 会缺 `libQt6VirtualKeyboardSettings.so.6`。

验收：设置 → 自定义问答助手，点编辑框应弹出内嵌键盘，拼音拼出「洋葱」。

安装 unit 与混音器脚本后重载：

```bash
sudo cp /home/cat/ai-microscope-edu/software/deploy/edu-app.service /etc/systemd/system/edu-app.service
chmod +x /home/cat/ai-microscope-edu/software/deploy/edu-mixer.sh
sudo systemctl daemon-reload && sudo systemctl restart edu-app
```

重启后 **不要** 再手跑 `amixer`。`ExecStartPost` 跑 `deploy/edu-mixer.sh` 写固定通路（Speaker、spk switch、Line 2、Channel 8、PCM）；进程 `main()` 再写通路，并按 `var/edu.yaml` 的 `audio.volume_pct` 写 Output 1/2（缺省 73→24）。Mac 无 `amixer` 时启动仍可用。`TTS_GAIN = 0.5` 不进 UI。

手测清单（规格 §12）：

1. 点设置：左预览右设置，工具条仍在；浮标在预览上能 PTT；手指能拖中间分界线改比例；关闭后全屏。
2. 无 yaml 首启即为 **90° 横屏**；点 0° 立刻竖过来且触点跟手；重启保持。
3. `restart edu-app` 后 PTT 有声，不必手跑 amixer；滑条能改变响度。
4. 设置里字幕 **开/关** 钮：打开后 ASR 出字即显（两行）；回答后句顶前句；播完底栏消失，不留到下一问。
5. USER.md 能用拼音输入汉字，并能切到英文。
6. 填 LLM key 保存后 yaml 为 `enc1:`，设置页看不到明文；把该 yaml 拷到另一台（或改测试 serial）下一问 beep，重填后恢复。
7. 改 USER.md 下一问能听出效果。
8. 问一句后打开「历史」：列表有当前场（旁注「当前」），右侧能看见该轮用户/助手正文。
9. 说「新对话」或点历史页按钮：喇叭「已处于新对话」；列表多一场或标题回到「新对话」。忙碌时点按钮可忽略。
10. 点旧场只能看、不能续聊；再按住说话仍写入带「当前」标记的那一场。库打不开时历史页提示「无法读取」，问答仍走内存轮次。
