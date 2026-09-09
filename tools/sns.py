"""SNS 投稿文の作成ツール。"""

from __future__ import annotations

from .base import Field, Tool, compose, section

SYSTEM = """あなたはSNS運用のプロです。

ルール:
- 最初の1〜2行（プレビューで見える範囲）で必ず手を止めさせる。
- 煽りすぎ・誇大表現・誤解を招く断定は使わない。
- 絵文字は指定があるときだけ、意味のある位置に最小限。
- 各案は明確に切り口を変える（切り口が被ったら作り直す）。
"""

PLATFORMS = {
    "X（Twitter）": "全角140文字以内。改行を使って読みやすく。ハッシュタグは最大2個。",
    "X（長文ポスト）": "500〜800文字。1行1メッセージで改行を多用。",
    "Instagram": "冒頭2行でフックを作り、その後に本文。末尾にハッシュタグを10〜15個まとめる。",
    "LinkedIn": "ビジネス文脈。実体験と学びを軸に、300〜500文字。ハッシュタグは3個。",
    "Facebook": "やや長め（300文字前後）で、語りかける口調。",
    "note / ブログ告知": "記事へ誘導する告知文。記事の価値を3点で示し、最後にリンク誘導。",
}


def build(v: dict) -> str:
    return compose(
        "以下の条件でSNS投稿文を作成してください。",
        section("伝えたい内容・元ネタ", v["content"]),
        section("プラットフォームの制約", PLATFORMS.get(v.get("platform", ""), "")),
        section("投稿の目的", v.get("goal")),
        section("ターゲット", v.get("audience")),
        section("絵文字", "適度に使う" if v.get("emoji") else "使わない"),
        f"## 出力形式\n切り口の異なる案を{v.get('count', 3)}つ出してください。"
        "各案は「### 案N（切り口の一言説明）」の見出しの下に、投稿本文をそのまま貼れる形で書き、"
        "末尾に想定文字数を添えてください。",
    )


TOOL = Tool(
    key="sns",
    name="SNS投稿",
    icon="📣",
    category="つくる",
    description="X・Instagram・LinkedIn など、媒体に合わせた投稿文を複数案作ります。",
    system_prompt=SYSTEM,
    temperature=0.9,
    default_length="標準",
    submit_label="投稿案を作る",
    fields=[
        Field("content", "伝えたい内容・元ネタ", "textarea", required=True, height=180,
              placeholder="記事のURL要約、実績、気づき、告知したいことなど。"),
        Field("platform", "プラットフォーム", "select", options=list(PLATFORMS),
              default="X（Twitter）", row=1),
        Field("count", "案の数", "number", default=3, row=1),
        Field("goal", "目的", "text", row=2, placeholder="例: 記事へのクリックを増やす"),
        Field("audience", "ターゲット", "text", row=2, placeholder="例: 20〜30代の個人開発者"),
        Field("emoji", "絵文字を使う", "checkbox", default=False),
    ],
    build_prompt=build,
)
