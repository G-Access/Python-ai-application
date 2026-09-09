"""ツールレジストリ。

新しいツールを足すときは、tools/ に TOOL を定義したモジュールを作って
下の _MODULES に名前を並べるだけでよい。UI は自動で生成される。
"""

from __future__ import annotations

from importlib import import_module

from .base import Field, Tool

_MODULES = [
    "blog",
    "email_reply",
    "summarize",
    "rewrite",
    "proofread",
    "notes",
    "sns",
    "headline",
    "brainstorm",
    "translate",
]

TOOLS: list[Tool] = [import_module(f".{name}", __package__).TOOL for name in _MODULES]
TOOLS_BY_KEY: dict[str, Tool] = {t.key: t for t in TOOLS}

# サイドバーでのカテゴリ表示順
CATEGORY_ORDER = ["つくる", "整える", "やりとりする"]

CHAT_SYSTEM_PROMPT = """あなたは書き手に伴走するライティングパートナーです。

振る舞い:
- 相談されたら、まず何を書きたいのかを1〜2問で確認してから書く。ただし既に十分な情報があれば確認せず書く。
- 文章を求められたら、講釈ではなく成果物を出す。
- 直しを頼まれたら、直した全文と「何を変えたか」を簡潔に示す。
- 分からないこと・裏取りが必要なことは、そう言う。
"""


def tools_by_category() -> dict[str, list[Tool]]:
    grouped: dict[str, list[Tool]] = {c: [] for c in CATEGORY_ORDER}
    for tool in TOOLS:
        grouped.setdefault(tool.category, []).append(tool)
    return {k: v for k, v in grouped.items() if v}


__all__ = ["TOOLS", "TOOLS_BY_KEY", "Tool", "Field", "tools_by_category", "CHAT_SYSTEM_PROMPT"]
