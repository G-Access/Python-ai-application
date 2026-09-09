"""メモ・箇条書きを整った文章に起こすツール。"""

from __future__ import annotations

from .base import Field, Tool, compose, section

SYSTEM = """あなたは口述メモを清書する編集者です。

ルール:
- メモに書かれていない事実を作らない。話の順序は読みやすさのために入れ替えてよい。
- 主語が省略されたメモは、文脈から補って明示する。補ったものが不確かなら「[要確認]」を付ける。
- 「えー」「あの」などのフィラー、言い直しは削る。
- 意味が取れない断片は捨てず、末尾に「解読できなかったメモ」として原文のまま残す。
"""

FORMATS = {
    "議事録": "「日時・参加者」「決定事項」「議論の要点」「ToDo（担当・期限）」「次回」の構成で整える。",
    "報告書": "「結論」「経緯」「詳細」「今後の対応」の構成で整える。",
    "説明文・文章化": "箇条書きを、つながりのある読みやすい文章（段落）に起こす。",
    "手順書・マニュアル": "番号付きの手順に整理し、各手順に前提と注意点を添える。",
    "FAQ": "想定される質問と回答の対に整理する。",
    "そのまま整形": "構成は変えず、誤字・口語・重複だけを整えて読める形にする。",
}


def build(v: dict) -> str:
    return compose(
        "以下のメモを清書してください。",
        section("メモ・下書き", v["source"]),
        section("仕上げる形式", FORMATS.get(v.get("format", ""), "")),
        section("読み手", v.get("audience")),
        section("補足情報", v.get("context")),
        "## 出力形式\n清書した文書を Markdown で出力してください。",
    )


TOOL = Tool(
    key="notes",
    name="メモ清書・議事録",
    icon="🗒️",
    category="整える",
    description="走り書きのメモや箇条書きを、そのまま渡せる文書に起こします。",
    system_prompt=SYSTEM,
    temperature=0.4,
    default_length="長め",
    submit_label="清書する",
    fields=[
        Field("source", "メモ・下書き", "textarea", required=True, height=300,
              placeholder="箇条書き、走り書き、文字起こしをそのまま貼り付けてください。"),
        Field("format", "仕上げる形式", "select", options=list(FORMATS), default="議事録", row=1),
        Field("audience", "読み手", "text", row=1, placeholder="例: 参加していなかったチーム全員"),
        Field("context", "補足情報（任意）", "textarea", height=100,
              placeholder="日時、参加者、プロジェクト名など、メモに書き漏らした情報。"),
    ],
    build_prompt=build,
)
