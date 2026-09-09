"""アイデア出し・構成案ツール。"""

from __future__ import annotations

from .base import Field, Tool, compose, section

SYSTEM = """あなたは企画会議のファシリテーターです。

ルール:
- 似たアイデアを並べない。角度（対象・切り口・フォーマット・時間軸）を意識的にずらす。
- 各アイデアには「一言説明」と「刺さる相手」を必ず添える。
- 平凡な案と挑戦的な案を混ぜ、最後に「まず1つやるなら」と推しを1つ選ぶ。
"""

KINDS = {
    "ブログのネタ出し": "検索需要と書きやすさの両面から、記事ネタを提案する。",
    "記事の構成案": "H2/H3 レベルの見出し構成を、狙いつきで複数パターン出す。",
    "SNSの投稿ネタ": "1つのテーマから、連投できる切り口を分解して出す。",
    "サービス・商品のアイデア": "課題ベースで解決アイデアを出す。",
    "プレゼンの構成": "聞き手の心の動きに沿ったストーリー構成を出す。",
    "質問リスト作成": "そのテーマについて掘り下げるべき質問を出す。",
}


def build(v: dict) -> str:
    return compose(
        "以下の条件でアイデアを出してください。",
        section("テーマ・お題", v["topic"]),
        section("出したいもの", KINDS.get(v.get("kind", ""), "")),
        section("前提・制約", v.get("constraints")),
        section("ターゲット", v.get("audience")),
        f"## 出力形式\n{v.get('count', 10)}案を箇条書きで。各案は「**案のタイトル** — 一言説明（刺さる相手）」の形。"
        "最後に「### まず1つやるなら」で1案を選び、理由と最初の一歩を3行で書いてください。",
    )


TOOL = Tool(
    key="brainstorm",
    name="アイデア出し・構成案",
    icon="🧠",
    category="つくる",
    description="ネタが出ないときに。切り口をずらしたアイデアを一気に並べます。",
    system_prompt=SYSTEM,
    temperature=1.0,
    default_length="標準",
    submit_label="アイデアを出す",
    fields=[
        Field("topic", "テーマ・お題", "textarea", required=True, height=120,
              placeholder="例: Python初心者向けのブログで、来月書く記事のネタ"),
        Field("kind", "出したいもの", "select", options=list(KINDS), default="ブログのネタ出し", row=1),
        Field("count", "案の数", "number", default=10, row=1),
        Field("audience", "ターゲット", "text", row=2),
        Field("constraints", "前提・制約", "text", row=2,
              placeholder="例: 実装を伴わない読み物にしたい"),
    ],
    build_prompt=build,
)
