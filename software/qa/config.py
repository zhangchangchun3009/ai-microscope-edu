"""快速问答常量。"""

USER_MD_MAX_CHARS = 1000
MAX_TURNS = 8
IDLE_NEW_SESSION_S = 20 * 60.0
DEFAULT_LLM_TIMEOUT_S = 30.0
PLAY_START_WATERMARK = 2
SHORT_SENTENCE_CHARS = 8
QA_ROLE_CORE = "你只回答生物学和显微镜观察相关的问题。\n当前时间：{datetime}"
# 对照 microclaw config-default.toml [microscope]；仅白名单 host 附加 X-Device-Secret。
DEFAULT_DEVICE_SECRET = "Microclaw-2026-SuperSecr3t!"
DEFAULT_DEVICE_SECRET_HOSTS = ("www.aiinstrum.com",)
