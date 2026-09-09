"""校正・推敲ツール。"""

from __future__ import annotations

from .base import Field, Tool, compose, section

SYSTEM = """あなたは出版社の校閲者です。

ルール:
- 事実の書き換えはしない。表現・表記・構成のみを扱う。
- 指摘は必ず「該当箇所の引用 → 問題 → 修正案」の3点セットで書く。
- 好みの問題と明確な誤りを区別し、誤りを先に挙げる。
- 直す必要がない箇所は挙げない。指摘がなければ「重大な指摘なし」と書く。
"""

CHECKS = [
    "誤字脱字・変換ミス",
    "文法・係り受けの誤り",
    "表記ゆれ（送り仮名・英数字・カタカナ）",
    "冗長表現・重複",
    "二重敬語・敬語の誤り",
    "曖昧な指示語・主語の欠落",
    "読みやすさ（一文の長さ・リズム）",
    "論理の飛躍・根拠不足",
    "差別的・炎上リスクのある表現",
]


def build(v: dict) -> str:
    return compose(
        "以下の文章を校正・推敲してください。",
        section("対象の文章", v["source"]),
        section("重点的にチェックする観点", v.get("checks")),
        section("文章の用途", v.get("purpose")),
        "## 出力形式\n"
        "### 1. 修正版\n修正を反映した全文をそのまま出力する。\n"
        "### 2. 指摘一覧\n表形式（元の表現 / 問題 / 修正後 / 理由）で列挙する。\n"
        "### 3. 総評\n文章全体の良い点と、次に書くときの改善点を3行以内で。",
    )


TOOL = Tool(
    key="proofread",
    name="校正・推敲",
    icon="🔍",
    category="整える",
    description="誤字脱字から論理の飛躍まで、指摘理由つきで直します。",
    system_prompt=SYSTEM,
    temperature=0.2,
    default_length="長め",
    submit_label="校正する",
    fields=[
        Field("source", "校正したい文章", "textarea", required=True, height=300),
        Field("checks", "チェック観点", "multiselect", options=CHECKS,
              default=["誤字脱字・変換ミス", "文法・係り受けの誤り", "冗長表現・重複", "読みやすさ（一文の長さ・リズム）"]),
        Field("purpose", "文章の用途", "text", placeholder="例: 社外向けのプレスリリース"),
    ],
    build_prompt=build,
)
