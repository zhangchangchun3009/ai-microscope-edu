# 设备端软件（`ai-microscope-edu/software`）

教学一体机 PySide6 kiosk。Mac 编辑，需要板端显示时 rsync 到 **211**（`cat@10.198.24.211`）。**235 只读对照，不部署。**

## 当前：无桌面教学壳

教学应用以 `python -m app` 启动。系统关闭图形桌面并停用 scandog/mipi-hmi 后，由 Qt 独占 MIPI（DSI-1）。

板端路径：

- 代码：`/home/cat/ai-microscope-edu/software/`
- venv：`/home/cat/ai-microscope-edu/.venv/`（不进 git）
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
