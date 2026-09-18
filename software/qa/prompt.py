"""快速问答 system / user 消息组装。"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

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


def load_user_md(path: Path) -> str:
    """读取 ``USER.md`` 全文；缺文件或读失败当空串。

    参数:
        path: ``var/qa/USER.md`` 路径。

    返回值:
        文件 UTF-8 原文；不截断（注入上限由 :func:`build_system_prompt` 处理）。

    副作用:
        若文件存在则读盘。
    """
    if not path.is_file():
        return ""
    try:
        return path.read_text(encoding="utf-8")
    except OSError:
        return ""


def save_user_md(path: Path, text: str) -> None:
    """把自定义问答助手正文写入 ``USER.md``。

    参数:
        path: 目标路径；父目录不存在时创建。
        text: 要落盘的全文（磁盘可不截断）。

    返回值:
        无。

    副作用:
        覆盖 ``path``；必要时 ``mkdir`` 父目录。

    异常:
        ``OSError``: 写盘失败，由调用方提示，不假装已保存。
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
