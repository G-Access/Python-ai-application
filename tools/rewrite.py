"""リライト・文体変換ツール。"""

from __future__ import annotations

from config import TONES

from .base import Field, Tool, compose, section

SYSTEM = """あなたはリライトの専門家です。

ルール:
- 元の文章の情報・意図・事実関係を一切変えずに、表現だけを作り替える。
- 削るべきは修飾語と重複であり、情報ではない。情報を落とす場合は最後に明示する。
- 指定された長さの目安を守る。
"""

GOALS = {
    "分かりやすくする": "専門用語をかみ砕き、一文を短くし、具体例を補って平易にする。",
    "短くする": "情報量を保ったまま、指定の割合まで圧縮する。",
    "長く厚くする": "根拠・具体例・補足を足して説得力を厚くする。ただし水増しの言い回しは禁止。",
    "文体を変える": "内容はそのままに、指定トーンに合わせて書き直す。",
    "説得力を上げる": "主張→根拠→具体例→結論の型に組み替え、読者の反論を先回りして潰す。",
    "小学生にも分かるように": "難語をすべて言い換え、比喩を使って説明する。",
}


def build(v: dict) -> str:
    return compose(
        "以下の文章をリライトしてください。",
        section("元の文章", v["source"]),
        section("リライトの目的", GOALS.get(v.get("goal", ""), "")),
        section("目標トーン", v.get("tone")),
        section("長さの目安", v.get("ratio")),
        section("追加の指示", v.get("extra")),
        "## 出力形式\nリライト後の文章のみを出力し、その後に「変更のポイント」を3点、箇条書きで添えてください。",
    )


TOOL = Tool(
    key="rewrite",
    name="リライト・文体変換",
    icon="🔁",
    category="整える",
    description="内容は変えずに、分かりやすく・短く・別のトーンに書き直します。",
    system_prompt=SYSTEM,
    temperature=0.6,
    default_length="標準",
    submit_label="リライトする",
    fields=[
        Field("source", "元の文章", "textarea", required=True, height=260),
        Field("goal", "リライトの目的", "select", options=list(GOALS), default="分かりやすくする", row=1),
        Field("tone", "目標トーン", "select", options=["元のまま"] + TONES, default="元のまま", row=1),
        Field("ratio", "長さの目安", "select",
              options=["元の50%程度", "元の70%程度", "元と同じくらい", "元の1.5倍", "元の2倍"],
              default="元と同じくらい", row=2),
        Field("extra", "追加の指示（任意）", "text", row=2,
              placeholder="例: 「弊社」を「当社」に統一"),
    ],
    build_prompt=build,
)
