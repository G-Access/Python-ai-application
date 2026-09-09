"""翻訳ツール。"""

from __future__ import annotations

from .base import Field, Tool, compose, section

SYSTEM = """あなたはプロの翻訳者です。

ルール:
- 直訳ではなく、対象言語のネイティブが自然だと感じる表現にする。
- 固有名詞・数値・単位は正確に保つ。慣例訳がある語は慣例に従う。
- 訳しにくい語やニュアンスが落ちる箇所は、末尾に「訳注」としてまとめる。
- 原文が箇条書き・Markdown ならその構造を保つ。
"""

LANGS = ["日本語", "英語", "中国語（簡体字）", "中国語（繁体字）", "韓国語", "スペイン語",
         "フランス語", "ドイツ語", "ポルトガル語", "ベトナム語", "タイ語"]

REGISTERS = ["ビジネス（フォーマル）", "カジュアル", "技術文書", "マーケティング", "学術・論文"]


def build(v: dict) -> str:
    return compose(
        f"以下の文章を{v.get('target')}に翻訳してください。",
        section("原文", v["source"]),
        section("原文の言語", v.get("source_lang")),
        section("文体レジスター", v.get("register")),
        section("用語指定", v.get("glossary")),
        "## 出力形式\n"
        "### 訳文\n翻訳結果のみ。\n"
        + ("### 逆翻訳\n訳文を原文の言語に訳し戻したもの（意味のズレ確認用）。\n" if v.get("back") else "")
        + "### 訳注\n判断に迷った箇所があれば箇条書きで。なければ「なし」。",
    )


TOOL = Tool(
    key="translate",
    name="翻訳",
    icon="🌐",
    category="やりとりする",
    description="ニュアンスを保った自然な翻訳と、訳注・逆翻訳チェック。",
    system_prompt=SYSTEM,
    temperature=0.3,
    default_length="長め",
    submit_label="翻訳する",
    fields=[
        Field("source", "翻訳したい文章", "textarea", required=True, height=260),
        Field("source_lang", "原文の言語", "select", options=["自動判定"] + LANGS, default="自動判定", row=1),
        Field("target", "翻訳先の言語", "select", options=LANGS, default="英語", row=1),
        Field("register", "文体", "select", options=REGISTERS, default="ビジネス（フォーマル）", row=2),
        Field("back", "逆翻訳チェックを付ける", "checkbox", default=False, row=2),
        Field("glossary", "用語指定（任意）", "text",
              placeholder="例: 「案件」は project と訳す"),
    ],
    build_prompt=build,
)
