# AI 教学显微镜（N-117M 一体机）工程约定

本目录是 **2026-09 起的唯一开发线**：永新 N-117M + LubanCat-3BTB，**无电控**，10 寸触屏闭环。完整产品说明见 [`docs/plans/2026-09-07-ai-camera-closed-loop-plan.md`](docs/plans/2026-09-07-ai-camera-closed-loop-plan.md)。触屏壳层与交互见 [`docs/superpowers/specs/2026-09-08-edu-kiosk-ui-design.md`](docs/superpowers/specs/2026-09-08-edu-kiosk-ui-design.md)。

工作区根目录的 `microclaw/`、`microscopy-front/`、`microscope/`、`microscopy_server/` 是 **只读对照**，不要在那些树里加本产品功能。

---

## 1. 系统目标

教室里一台铸铁显微镜 + 臂后计算盒 + 斜置 10 寸屏。学生手拧 XYZ；软件提供预览、语音知识问答、ROI 识图、计数、手动引导的 Z 融合与扫描拼接。

**不是** 平板遥控电控载物台，**不是** MicroClaw 工具循环 Agent。

```
学生 ──触屏/语音──> edu-app（PySide6 kiosk，RK3576）
                      ├── camera：UVC pc-oic678
                      ├── qa：云端 LLM（零工具，快速问答）
                      ├── vision：ROI / 计数 RKNN
                      ├── algo：focus_stack / mosaic
                      └── system：nmcli 配网、关机
```

后期另开：高端电控版；云端教材样本训练。都不在本目录当前迭代里实现。

---

## 2. 目录角色

| 路径 | 角色 | 修改规则 |
|------|------|----------|
| `ai-microscope-edu/software/` | 设备端应用与算法 | **主要开发** |
| `ai-microscope-edu/hardware/` | 相机盒、主板盒、臂夹、屏支架、图档 | **主要开发**（结构）；电机件归档不扩展 |
| `ai-microscope-edu/docs/` | 计划与设计 | 新模块先写职责再写代码 |
| `microclaw/` `microscopy-front/` `microscope/` | 旧教育版 | **只读对照** |
| `microscopy_server/` | 更旧 Pi 栈 | **不要用** |

Mac 只做编辑、交叉拷贝、看 SCAD。真机在鲁班猫上跑；不要假设还有 RP2040。

---

## 3. 该改哪里

- 预览 / 拍照 / ISP → `software/camera/`
- 全屏 UI、导航 → `software/app/`（只调度，不堆算法）
- 手动融合、手动拼接向导 → `software/capture_guide/` + `software/algo/`
- 计数、ROI 叠图 → `software/vision/`
- 问答、会话、识图提示词 → `software/qa/`
- 语音与字幕 → `software/voice/`
- Wi-Fi / 关机 / kiosk 自启 → `software/system/`
- 打印件 → `hardware/n117m/`（新件用新 scad；`05_pulley_split` 等电机件不要继续当本期任务）

对照旧实现时：cam/algo 看 `microscope/`，问答看 MicroClaw 快速问答 spec，配网看 mipi-hmi。**抄算法，不要抄进程拓扑。**

---

## 4. 技术约束

- **语言：** 设备端 Python 3。UI：PySide6 kiosk（Linux 全屏，隐藏桌面）。本期 AI 也用 Python；不引入 microclaw，不引入依赖 tokio/reqwest/hyper 的 MCP SDK。
- **进程：** 以一个教学应用为主；算法用线程或本机 worker。不要恢复 scandog 九服务 + WS 网关。
- **相机：** 禁止周期回写 ISP（IsoLock）；禁止按画面统计改显示增益。设置页手调 + 一键恢复默认。
- **运动：** 无 motion API。融合/拼接只有「提示学生手拧 + 拍照」。
- **问答：** 快速问答模式：零工具、短系统提示、知识库预注入、流式优先。不要技能路由、不要 microscope-cli。
- **交互：** 默认语音进、语音出；字幕可开，开了才强调文字。远程客户端本期不开发。
- **长任务：** job + 查询进度，sync-first。
- **单文件：** 源文件尽量 < 1000 行；入口文件只组合模块。
- **测试：** 非平凡逻辑先测后改；声称完成前在本机或板端跑相关 pytest，并写明命令。纯 UI/GStreamer 在板端点验，注明未自动化的部分。
- **CAD：** 打印件不走 TDD；尺寸以卡尺和 `dims.json` 为准。

---

## 5. 硬件与板端

| 项 | 值 |
|----|-----|
| 光学 | N-117M 三目，机械筒长 160 mm |
| 相机 | pc-oic678（USB `1bcf:28c4`），摄影口无目镜 |
| 主板 | 野火 LubanCat-3BTB RK3576 |
| 屏 | 10 寸 MIPI 触屏（支架方案见计划 §3.4，未定案前不要当已冻结） |
| 音频 | 板载麦 + 双外接喇叭 |
| 电机板 | **无** |
| 照明 | 底座 S-LED 为 DC 5V，**可以从板 5V 引出**（低优先级，见计划 §3.6）。禁止用镜体 5V/10VA 适配器给主板供电 |
| 样机对照 IP（旧栈，仅参考） | 历史上 211 / 235；新镜像以现场为准 |

部署：应用随 systemd 自启全屏。配网、关机走应用内按钮（nmcli / loginctl 或 `systemctl poweroff`，权限用 polkit，不要为 kiosk 开空白 sudo）。

预览视场与标尺：10× 下 1440×1080 大约 580×435 μm（须测微尺标定后写入配置）。不要沿用旧前端 `magnification=20` 的 100 μm 尺。

---

## 6. 给代理的工作方式

1. 先读本文件和 `docs/plans/2026-09-07-ai-camera-closed-loop-plan.md`。
2. 只改 `ai-microscope-edu/`。
3. **本周主线仍是硬件建模与打印件。** 允许在 211 上做无桌面 PySide6 kiosk 探测（`software/` 最小入口）；不要在 235 部署，不要恢复 scandog。完整教学应用等结构总装后再铺。
4. 新模块先在计划或设计里补职责和接口，再写代码。
5. 不要把旧仓库文档里的 Flutter / MicroClaw 网关 / RP2040 当现行约束。
6. 用户未要求时不要 commit、不要改 git config。
7. 回复用简体中文。
