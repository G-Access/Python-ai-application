"""タイトル・キャッチコピー案の作成ツール。"""

from __future__ import annotations

from .base import Field, Tool, compose, section

SYSTEM = """あなたはコピーライターです。

ルール:
- 案ごとに切り口（数字・逆説・問いかけ・ベネフィット・恐怖訴求・共感 など）を必ず変える。
- 誇大表現と根拠のない断定は使わない。
- 各案に「なぜ効くか」を1行で添える。
- 指定文字数を1文字でも超えない。
"""

KINDS = {
    "ブログ記事タイトル": "検索意図を満たしつつクリックされる形。32文字以内を目安。",
    "YouTube 動画タイトル": "サムネと合わせて機能する形。30文字以内。",
    "商品キャッチコピー": "短く記憶に残る形。20文字以内。",
    "メール件名": "開封されるが釣りにならない形。25文字以内。",
    "プレゼン資料のタイトル": "内容を1行で言い切る形。",
    "本・note のタイトル": "書店で目に留まる形。サブタイトル案も添える。",
}


def build(v: dict) -> str:
    return compose(
        "以下の条件でタイトル・キャッチコピー案を作成してください。",
        section("対象の内容", v["content"]),
        section("種類と制約", KINDS.get(v.get("kind", ""), "")),
        section("ターゲット", v.get("audience")),
        section("入れたいキーワード", v.get("keywords")),
        section("避けたい表現", v.get("ng")),
        f"## 出力形式\n{v.get('count', 10)}案を表形式（No / 案 / 文字数 / 切り口 / 効く理由）で出し、"
        "最後に「おすすめ3案」とその理由を書いてください。",
    )


TOOL = Tool(
    key="headline",
    name="タイトル・コピー案",
    icon="💡",
    category="つくる",
    description="記事タイトル、件名、キャッチコピーを切り口を変えて量産します。",
    system_prompt=SYSTEM,
    temperature=1.0,
    default_length="標準",
    submit_label="案を出す",
    fields=[
        Field("content", "対象の内容", "textarea", required=True, height=160,
              placeholder="記事の概要、商品の特徴、伝えたいことなど。"),
        Field("kind", "種類", "select", options=list(KINDS), default="ブログ記事タイトル", row=1),
        Field("count", "案の数", "number", default=10, row=1),
        Field("audience", "ターゲット", "text", row=2),
        Field("keywords", "入れたいキーワード", "text", row=2),
        Field("ng", "避けたい表現", "text", placeholder="例: 「絶対」「最強」は使わない"),
    ],
    build_prompt=build,
)
