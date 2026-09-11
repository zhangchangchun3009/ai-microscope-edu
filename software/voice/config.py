"""板载 ALSA 与判定常量。"""

import os

# ES8388 在 hw:0,0 上请求 48000 会回落到 44100；16 kHz 直出 hw 会把语音播成杂音。
# 录音保持单声道 44100。播放必须升成立体声：该芯片按 I2S 双声道取数，
# 单声道 raw 用 -c 1 大约会以 2 倍速播完，听起来尖且快。
SAMPLE_RATE = 44100
# SenseVoice 只要 16 kHz；不要把 ALSA 采/播改成这个速率。
ASR_RATE = 16000
# Matcha 原生 22050。一句 PCM 交给 aplay 时覆盖 -r，不要把采集改成这个。
TTS_RATE = 22050
CHANNELS = 1
PLAYBACK_CHANNELS = 2
ECHO_TARGET_PEAK = 12000
ECHO_MAX_GAIN = 24.0
ALSA_CAPTURE_DEVICE = "hw:0,0"
ALSA_PLAYBACK_DEVICE = "hw:0,0"
MAX_RECORD_S = 300.0
ECHO_MAX_S = 15.0
MIN_UTTERANCE_S = 0.4
SILENCE_PEAK = 200
NO_DATA_S = 3.0
BEEP_HZ = 880.0
BEEP_S = 0.2
BEEP_AMPLITUDE = 8000
# 回放噪声门：按本段 20ms 帧能量自适应。阈值可随后再调。
GATE_FRAME_S = 0.02
GATE_SKIP_LEAD_S = 0.08
GATE_NOISE_PERCENTILE = 0.25
GATE_OPEN_RATIO = 3.5
GATE_CLOSE_RATIO = 2.2
GATE_OPEN_FLOOR = 400.0
GATE_MIN_SPEECH_RATIO = 4.0
GATE_HANG_S = 0.12

# 板上模型只放本应用目录，运行时不要再指向 /home/cat/microscope/（旧树可能被删）。
# Mac 上这些文件不存在：ASR 返回 ""，TTS 回退 MockTts。可用 EDU_* 覆盖。
# sensevoice_demo 的 cwd 是其父目录，还必须有 model/am.mvn（CMVN），缺了会识别为空。
_MODELS_ROOT = "/home/cat/ai-microscope-edu/models"
SENSEVOICE_DEMO = os.environ.get(
    "EDU_SENSEVOICE_DEMO",
    f"{_MODELS_ROOT}/sensevoice/sensevoice_demo",
)
SENSEVOICE_MODEL = os.environ.get(
    "EDU_SENSEVOICE_MODEL",
    f"{_MODELS_ROOT}/sensevoice/sensevoice_f32.rknn",
)
SENSEVOICE_TOKENS = os.environ.get(
    "EDU_SENSEVOICE_TOKENS",
    f"{_MODELS_ROOT}/sensevoice/tokens.txt",
)
ASR_TIMEOUT_S = 30.0

# Matcha-TTS zh-baker。对照旧 agent_tts_sherpa 文件名，不 import microscope。
# 覆盖：EDU_TTS_MODEL_DIR（含 model-steps-3.onnx / lexicon.txt / tokens.txt）、
# EDU_TTS_VOCODER（vocos-22khz-univ.onnx）。
TTS_MODEL_DIR = os.environ.get(
    "EDU_TTS_MODEL_DIR",
    f"{_MODELS_ROOT}/matcha-icefall-zh-baker",
)
TTS_VOCODER = os.environ.get(
    "EDU_TTS_VOCODER",
    f"{_MODELS_ROOT}/vocos-22khz-univ.onnx",
)
