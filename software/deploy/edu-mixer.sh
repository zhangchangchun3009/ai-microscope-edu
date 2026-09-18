#!/bin/sh
# 固定音频通路（Speaker / Mux / PGA / PCM）。不含 Output 音量：
# 音量由 Python 读 var/edu.yaml 再 amixer，本脚本不解析 yaml。
# 单条失败不让 systemd ExecStartPost 拖垮 kiosk（与 apply_fixed_path 的 check=False 一致）。

amixer -c 0 sset Speaker on
amixer -c 0 sset "spk switch" on
amixer -c 0 sset "Differential Mux" "Line 2"
amixer -c 0 sset "Left Channel" 8
amixer -c 0 sset "Right Channel" 8
amixer -c 0 sset PCM 100%
exit 0
