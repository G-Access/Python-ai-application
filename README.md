# ✍️ AI ライティングツール

Python + Streamlit + Gemini API で作った、個人用のライティング支援ツール集。
ブログ執筆・メール返信・要約など、よく使う「書く仕事」を 1 つのアプリにまとめています。
データベース・ログイン認証はなし。ローカルで起動してすぐ使えます。

## 搭載ツール

| カテゴリ | ツール | できること |
| --- | --- | --- |
| つくる | 📝 ブログ記事執筆 | テーマ・読者像・キーワードから、構成付きの記事を丸ごと執筆 |
| つくる | 📣 SNS投稿 | X / Instagram / LinkedIn など媒体別に、切り口の違う投稿案を複数生成 |
| つくる | 💡 タイトル・コピー案 | 記事タイトル、メール件名、キャッチコピーを切り口別に量産 |
| つくる | 🧠 アイデア出し・構成案 | ネタ出し、見出し構成、質問リストなどのブレスト |
| 整える | 🗜️ 要約 | 3行 / 箇条書き / エグゼクティブサマリーなど、目的別に圧縮 |
| 整える | 🔁 リライト・文体変換 | 内容は変えずに、分かりやすく・短く・別のトーンへ |
| 整える | 🔍 校正・推敲 | 誤字脱字から論理の飛躍まで、指摘理由と修正版つき |
| 整える | 🗒️ メモ清書・議事録 | 走り書きや文字起こしを、そのまま渡せる文書に |
| やりとりする | ✉️ メール返信 | 受け取ったメールを貼るだけで、送れる形の返信文を作成 |
| やりとりする | 🌐 翻訳 | ニュアンスを保った翻訳＋訳注・逆翻訳チェック |
| そのほか | 💬 フリーチャット | 型のない相談用。文脈を保ったまま何往復でも |

共通機能:

- **ストリーミング表示** — 生成中のテキストが逐次流れます
- **追加指示で再生成** — 出力後に「3割短く」などと指示して直せます
- **モデル切り替え** — Gemini 3.5 Flash Lite / 3.6 Flash / 3.8 Flash をサイドバーで選択
- **熟考モード** — 思考量を `high` に上げて品質を稼ぐ（OFF 時は最小に抑えて速度優先）
- **Markdown 保存** — 結果を `.md` でダウンロード
- **履歴** — 直近 50 件をサイドバーから見返し・保存

## セットアップ

```powershell
# 1. 依存パッケージをインストール
pip install -r requirements.txt

# 2. API キーを設定
copy .env.example .env
# .env を開いて GEMINI_API_KEY に自分のキーを貼る
```

API キーは [Google AI Studio](https://aistudio.google.com/apikey) で無料発行できます。
`.env` を用意しなくても、起動後にサイドバーから直接入力しても動きます（その場合はセッション限り）。

## 起動

```powershell
streamlit run app.py
```

ブラウザで `http://localhost:8501` が開きます。

## ファイル構成

```
├── app.py              # Streamlit の画面。フォームは Field 定義から自動生成
├── config.py           # モデル一覧、長さプリセット、共通システムプロンプト
├── gemini_client.py    # Gemini API ラッパー（ストリーミング・エラー整形）
└── tools/
    ├── __init__.py     # ツールのレジストリ
    ├── base.py         # Tool / Field の定義とプロンプト組み立てヘルパー
    └── blog.py, email_reply.py, summarize.py, rewrite.py, proofread.py,
        notes.py, sns.py, headline.py, brainstorm.py, translate.py
```

## ツールを追加する

`tools/` に 1 ファイル足すだけで、UI もナビゲーションも自動で増えます。

```python
# tools/my_tool.py
from .base import Field, Tool, compose, section

SYSTEM = """（このツール専用のシステムプロンプト）"""

def build(v: dict) -> str:
    return compose(
        "以下の条件で〜してください。",
        section("入力", v["source"]),
        section("オプション", v.get("mode")),
    )

TOOL = Tool(
    key="my_tool",
    name="ツール名",
    icon="🛠️",
    category="つくる",           # つくる / 整える / やりとりする
    description="一言説明",
    system_prompt=SYSTEM,
    temperature=0.7,
    fields=[
        Field("source", "入力", "textarea", required=True, height=200),
        Field("mode", "モード", "select", options=["A", "B"], default="A"),
    ],
    build_prompt=build,
)
```

最後に `tools/__init__.py` の `_MODULES` に `"my_tool"` を追記すれば完了です。

`Field` の `type` は `text` / `textarea` / `select` / `multiselect` / `number` / `checkbox` / `radio`。
同じ `row` 番号を指定したフィールドは横並びになります。

## メモ

- `.env` と `history/` は `.gitignore` 済みです。API キーをコミットしないよう注意してください。
- 出力が途中で切れる場合は、サイドバーの「出力の長さ上限」を上げてください。
- 熟考モードは思考トークンも上限を消費します。長文を書かせるときは上限を「長め」以上に。
