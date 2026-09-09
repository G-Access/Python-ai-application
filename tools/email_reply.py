"""メール返信文の作成ツール。"""

from __future__ import annotations

from .base import Field, Tool, compose, section

SYSTEM = """あなたは日本のビジネスメールに精通したアシスタントです。

執筆ルール:
- 件名（Re: を含む形）→ 宛名 → 挨拶 → 本文 → 結び → 署名欄の順で構成する。
- 相手のメールの要求事項を漏れなく拾い、それぞれに明確に回答する。
- 断りや謝罪では、クッション言葉 → 事実 → 代替案 の順で書く。
- 曖昧な期日表現（「なるべく早く」等）は避け、具体的に書く。
- 署名は「（署名）」のプレースホルダにする。
- 複数案を求められた場合のみ複数出し、それ以外は1案に絞る。
"""

PURPOSES = [
    "お礼・承諾",
    "依頼・お願い",
    "お断り",
    "謝罪・お詫び",
    "日程調整",
    "質問への回答",
    "催促・リマインド",
    "その他（意図欄に記載）",
]

FORMALITY = ["社外・初対面（最も丁寧）", "社外・取引先（標準）", "社内・上司", "社内・同僚（ややカジュアル）"]


def build(v: dict) -> str:
    return compose(
        "以下のメールへの返信文を作成してください。",
        section("受け取ったメール", v["received"]),
        section("返信の目的", v.get("purpose")),
        section("必ず伝えたい内容", v.get("points")),
        section("相手との関係・丁寧さ", v.get("formality")),
        section("差出人（自分）の名前・所属", v.get("sender")),
        section("長さの希望", v.get("length_hint")),
        "## 出力形式\n件名から署名まで、そのままコピーして送れる完成形で出力してください。"
        + ("\n加えて、末尾に「別案（トーン違い）」として2案目を簡潔に添えてください。" if v.get("alt") else ""),
    )


TOOL = Tool(
    key="email",
    name="メール返信",
    icon="✉️",
    category="やりとりする",
    description="受け取ったメールを貼るだけで、そのまま送れる返信文を作ります。",
    system_prompt=SYSTEM,
    temperature=0.5,
    default_length="標準",
    submit_label="返信文を作る",
    render_markdown=False,
    fields=[
        Field("received", "受け取ったメール本文", "textarea", required=True, height=220,
              placeholder="メールをそのまま貼り付けてください。"),
        Field("purpose", "返信の目的", "select", options=PURPOSES, default="質問への回答", row=1),
        Field("formality", "丁寧さ", "select", options=FORMALITY, default="社外・取引先（標準）", row=1),
        Field("points", "必ず伝えたい内容", "textarea", height=120, required=True,
              placeholder="例: 来週水曜は不可。木・金の午後なら可能。資料は明日送る。"),
        Field("sender", "自分の名前・所属", "text", row=2, placeholder="例: 株式会社◯◯ 田中"),
        Field("length_hint", "長さ", "select", options=["簡潔に（5行程度）", "標準", "丁寧に厚く"],
              default="標準", row=2),
        Field("alt", "トーン違いの別案も出す", "checkbox", default=False),
    ],
    build_prompt=build,
)
