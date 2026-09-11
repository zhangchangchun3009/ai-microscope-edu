"""板载语音：PTT 采集/播放（``alsa``）、识别（``asr``）、合成（``tts``）与回合编排（``session``）。"""

from voice.alsa import build_audio_io
from voice.session import VoiceSession

__all__ = ["VoiceSession", "build_audio_io"]
