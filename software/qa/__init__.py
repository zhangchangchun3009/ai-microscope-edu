"""快速问答：分句、prompt、记忆与 LLM 客户端。"""

from qa.client import LlmConfig, QaClientError, iter_chat_tokens, load_llm_config
from qa.turn import QaService
from qa.config import (
    DEFAULT_LLM_TIMEOUT_S,
    IDLE_NEW_SESSION_S,
    MAX_TURNS,
    PLAY_START_WATERMARK,
    QA_ROLE_CORE,
    SHORT_SENTENCE_CHARS,
    USER_MD_MAX_CHARS,
)
from qa.knowledge import EmptyRecall, KnowledgeRecall
from qa.memory import QaMemory
from qa.prompt import build_system_prompt, build_user_message
from qa.sentences import SentenceSplitter, merge_short_sentences, ready_to_play

__all__ = [
    "DEFAULT_LLM_TIMEOUT_S",
    "EmptyRecall",
    "IDLE_NEW_SESSION_S",
    "KnowledgeRecall",
    "LlmConfig",
    "MAX_TURNS",
    "PLAY_START_WATERMARK",
    "QA_ROLE_CORE",
    "QaClientError",
    "QaMemory",
    "QaService",
    "SHORT_SENTENCE_CHARS",
    "SentenceSplitter",
    "USER_MD_MAX_CHARS",
    "build_system_prompt",
    "build_user_message",
    "iter_chat_tokens",
    "load_llm_config",
    "merge_short_sentences",
    "ready_to_play",
]
