"""ツール定義の共通クラス。

各ツールは「入力フォームの定義」と「プロンプトの組み立て方」だけを書けばよく、
UI の描画は app.py が Field の型を見て自動で行う。
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any, Literal

FieldType = Literal["text", "textarea", "select", "multiselect", "number", "checkbox", "radio"]


@dataclass
class Field:
    key: str
    label: str
    type: FieldType = "text"
    options: list[str] = field(default_factory=list)
    default: Any = None
    placeholder: str = ""
    help: str = ""
    height: int = 160
    required: bool = False
    # 横並びにしたいときのカラム番号（同じ値のフィールドが同じ行に並ぶ）
    row: int | None = None


@dataclass
class Tool:
    key: str
    name: str
    icon: str
    description: str
    category: str
    system_prompt: str
    fields: list[Field]
    build_prompt: Callable[[dict[str, Any]], str]
    temperature: float = 0.7
    default_length: str = "標準"
    submit_label: str = "生成する"
    # 出力を Markdown として描画するか（False なら等幅のプレーン表示）
    render_markdown: bool = True

    @property
    def title(self) -> str:
        return f"{self.icon} {self.name}"


def section(label: str, value: Any) -> str:
    """値があるときだけ「## ラベル」ブロックを返すヘルパー。"""
    if value is None:
        return ""
    if isinstance(value, (list, tuple)):
        value = "、".join(str(v) for v in value if v)
    text = str(value).strip()
    if not text:
        return ""
    return f"## {label}\n{text}\n"


def compose(*parts: str) -> str:
    return "\n".join(p for p in parts if p).strip()
