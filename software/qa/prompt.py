"""快速问答 system / user 消息组装。"""

from __future__ import annotations

from datetime import datetime

from qa.config import QA_ROLE_CORE, USER_MD_MAX_CHARS


def build_system_prompt(now: datetime, user_md: str) -> str:
    """组装 system 提示：角色约束、当前时间与可选 USER.md 正文。

    参数:
        now: 用于替换 ``QA_ROLE_CORE`` 中 ``{datetime}`` 的当前时间。
        user_md: ``var/qa/USER.md`` 全文；空白视为未配置。

    返回值:
        发给 LLM 的 system 字符串。

    副作用:
        无。
    """
    core = QA_ROLE_CORE.replace("{datetime}", now.strftime("%Y-%m-%d %H:%M:%S"))
    body = user_md.strip()
    if not body:
        return core
    truncated = body[:USER_MD_MAX_CHARS]
    return f"{core}\n\n{truncated}"


def build_user_message(knowledge: str, user_text: str) -> str:
    """组装本轮 user 消息：可选知识块前缀 + 用户问句。

    参数:
        knowledge: 知识库 lookup 结果；去空白后为空则不加前缀。
        user_text: 用户问句原文（ASR 文本）。

    返回值:
        发给 LLM 的 user 字符串。

    副作用:
        无。
    """
    block = knowledge.strip()
    if not block:
        return user_text
    return f"{block.rstrip()}\n{user_text}"
