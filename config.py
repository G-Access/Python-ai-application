"""アプリ全体の設定。"""

from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()

APP_TITLE = "AI ライティングツール"
APP_ICON = "✍️"


@dataclass(frozen=True)
class ModelSpec:
    id: str
    label: str
    note: str


# 上から順に「速い ← → 賢い」
MODELS: list[ModelSpec] = [
    ModelSpec("gemini-3.5-flash-lite", "Flash Lite 3.5 (最速・低コスト)", "短文の変換や要約向き"),
    ModelSpec("gemini-3.6-flash", "Flash 3.6 (標準)", "普段使いの推奨モデル"),
    ModelSpec("gemini-3.8-flash", "Flash 3.8 (最新)", "3.6 より高性能かつ低価格。長文記事や難しい推敲向き"),
]

DEFAULT_MODEL = "gemini-3.6-flash"

# 生成テキストの長さプリセット(max_output_tokens)
LENGTH_PRESETS: dict[str, int] = {
    "短め": 1024,
    "標準": 4096,
    "長め": 8192,
    "最長": 16384,
}

# 文体トーン。各ツールで共通利用する。
TONES: list[str] = [
    "丁寧・ビジネス",
    "カジュアル・親しみやすい",
    "フォーマル・硬め",
    "フレンドリーな敬体（です・ます）",
    "常体（だ・である）",
    "情熱的・熱量高め",
    "落ち着いた・淡々",
]

HISTORY_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "history")

# 全ツール共通の土台となる指示。
BASE_SYSTEM_PROMPT = """あなたは日本語のプロのライター兼編集者です。
出力は必ず日本語で、指示された形式・文字数・トーンを厳密に守ってください。

原則:
- 事実が不確かな箇所は断定せず、必要なら「[要確認]」と明示する。
- 冗長な前置き（「承知しました」「以下に示します」など）は書かず、成果物だけを出力する。
- 読み手が誰かを常に意識し、一文を短く、主語と述語を対応させる。
- 指示にない情報を勝手に創作しない。素材が足りない場合は最後に「不足情報」として箇条書きで挙げる。
"""


def get_api_key() -> str | None:
    """環境変数 or Streamlit secrets から API キーを取得する。"""
    key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    if key:
        return key.strip()
    try:
        import streamlit as st

        return str(st.secrets["GEMINI_API_KEY"]).strip()
    except Exception:
        return None
