"""文章要約ツール。"""

from __future__ import annotations

from .base import Field, Tool, compose, section

SYSTEM = """あなたは要約の専門家です。

要約ルール:
- 原文にない情報を足さない。推測を書くときは必ず「（推測）」と付ける。
- 数値・固有名詞・日付は原文のまま正確に残す。
- 主張と根拠を区別し、結論を先に置く。
- 原文が矛盾している場合はその旨を指摘する。
"""

STYLES = {
    "3行要約": "全体を3行（各60文字以内）で要約する。",
    "箇条書き": "重要ポイントを5〜8個の箇条書きにする。各項目は1文。",
    "エグゼクティブサマリー": "冒頭に結論1段落、その後に「要点」「背景」「示唆」の3セクションで整理する。",
    "議事録スタイル": "「決定事項」「議論の要点」「ToDo（担当・期限つき）」の3セクションで整理する。",
    "一言で": "1文（80文字以内）に凝縮する。",
    "図解メモ": "階層付き箇条書きで、全体構造が一目で分かるツリー状に整理する。",
}


def build(v: dict) -> str:
    return compose(
        "以下の文章を要約してください。",
        section("原文", v["source"]),
        section("要約スタイル", STYLES.get(v.get("style", ""), "")),
        section("読み手", v.get("audience")),
        section("特に知りたいこと", v.get("focus")),
        ("## 追加出力\n要約の後に「キーワード」として重要語を5個、カンマ区切りで挙げてください。"
         if v.get("keywords") else ""),
        ("## 追加出力\n要約の後に「原文で触れられていない論点」を2〜3個、箇条書きで挙げてください。"
         if v.get("gaps") else ""),
    )


TOOL = Tool(
    key="summarize",
    name="要約",
    icon="🗜️",
    category="整える",
    description="長い文章・議事録・記事を、目的に合った形に圧縮します。",
    system_prompt=SYSTEM,
    temperature=0.3,
    default_length="標準",
    submit_label="要約する",
    fields=[
        Field("source", "要約したい文章", "textarea", required=True, height=300,
              placeholder="記事、議事録、メール、レポートなどを貼り付けてください。"),
        Field("style", "要約スタイル", "select", options=list(STYLES), default="箇条書き", row=1),
        Field("audience", "読み手", "text", row=1, placeholder="例: 忙しい上司"),
        Field("focus", "特に知りたいこと（任意）", "text",
              placeholder="例: コストに関する記述だけを重点的に"),
        Field("keywords", "キーワードも抽出する", "checkbox", default=False, row=2),
        Field("gaps", "抜けている論点も指摘する", "checkbox", default=False, row=2),
    ],
    build_prompt=build,
)
