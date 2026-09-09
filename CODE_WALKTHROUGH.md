# フォームを書かずに10個のAIツールを作る

> このアプリには「ブログ記事執筆」「メール返信」「要約」など10個のツールが入っているのに、画面を描くコードは `app.py` の1ファイルしかない。ツール1個あたりのコードは約60行、しかもその中に `st.text_input` は1行も出てこない。どうやってそれが成立しているのかを、実際のコードを追いながら読み解く。

**対象**: `app.py` / `config.py` / `gemini_client.py` / `tools/`
**構成**: Python + Streamlit + google-genai

---

## 01. まず、4つの部品に分かれている

このアプリの構造は、ファイル名を見るだけでほぼ言い当てられる。役割が重なっているファイルが1つもないからだ。

| ファイル | 役割 |
|---|---|
| `app.py` | **画面。** サイドバー、フォーム、結果表示、履歴。全ツールで共通の1本で、個別ツールの知識を持たない |
| `config.py` | **設定。** モデル一覧、長さプリセット、文体トーン、全ツール共通のシステムプロンプト、APIキーの取得 |
| `gemini_client.py` | **API。** google-genai SDK をここに閉じ込め、外には「文字列を渡して文字列（またはストリーム）が返る」関数だけを見せる |
| `tools/*.py` | **ツール定義。** 1ファイル1ツール。入力欄の定義とプロンプトの組み立て方だけを書く |

ポイントは `app.py` と `tools/` の関係だ。ふつうに作ると「ブログ記事のページ」「メールのページ」と画面が10個できてしまう。このアプリは逆で、**画面は1つしかなく、ツールはその画面に流し込むデータでしかない。**

---

## 02. ツールは「クラス」ではなく「データ」

中心にあるのが `tools/base.py` の2つの dataclass、`Field` と `Tool` だ。`Field` は入力欄1個を表す。

```python
@dataclass
class Field:
    key: str            # 入力値を受け取るときの名前
    label: str          # 画面に出るラベル
    type: FieldType = "text"   # text / textarea / select / ...
    options: list[str] = ...   # select・radio の選択肢
    default: Any = None
    required: bool = False
    row: int | None = None     # 同じ番号どうしが横並びになる
```

そして `Tool` は、その `Field` のリストに加えて、「システムプロンプト」「温度」「出力の長さ」、そして `build_prompt` —— **入力値の dict を受け取ってプロンプト文字列を返す関数**を持つ。

ブログ記事ツール（`tools/blog.py`）の全体像はこうなる。定義がそのまま画面になる。

```python
TOOL = Tool(
    key="blog", name="ブログ記事執筆", icon="📝",
    category="つくる",
    system_prompt=SYSTEM,      # SEO重視のライター役の指示
    temperature=0.8,           # 創作寄りなので高め
    default_length="長め",      # 長文なのでトークン枠を広げる
    fields=[
        Field("topic", "テーマ・タイトル案", "text", required=True, ...),
        Field("audience", "想定読者", "text", row=1, ...),   # ←┐ 同じ row=1 なので
        Field("goal",     "記事の狙い", "text", row=1, ...),  # ←┘ 横2列に並ぶ
        Field("material", "盛り込みたい素材", "textarea", height=140, ...),
        Field("meta", "メタディスクリプション案も出す", "checkbox", default=True),
    ],
    build_prompt=build,
)
```

レイアウトの指示すら、ウィジェットではなくデータとして書かれている。

描画側（`app.py` の `render_field`）は、この `type` を見て対応する Streamlit ウィジェットに振り分けるだけの、ほぼ if の羅列だ。

```python
def render_field(tool: Tool, f: Field) -> Any:
    key = f"{tool.key}:{f.key}"        # ツール間でキーが衝突しないよう接頭辞
    label = f.label + (" *" if f.required else "")
    if f.type == "textarea":
        return st.text_area(label, key=key, height=f.height, ...)
    if f.type == "select":
        idx = f.options.index(f.default) if f.default in f.options else 0
        return st.selectbox(label, f.options, index=idx, key=key, ...)
    # ... radio / multiselect / number / checkbox ...
    return st.text_input(label, key=key, ...)   # 既定は text
```

> **⚠️ 落とし穴**
>
> 最後の行に注目。`type` が未知の値だったとき、**警告を出さずに黙って `st.text_input` になる。** タイプミスで `"textarae"` と書いても、エラーではなく「なぜか1行入力欄になっている」という形で現れる。
>
> 横並びも同様で、同じ `row` をまとめるロジックは**リスト上で連続している要素しか見ない。** `row=1` の Field を離して書くと、静かに縦並びに戻る。

---

## 03. プロンプトは f-string で組まない

入力欄の多くは任意入力だ。素直に f-string で書くと、空欄のときプロンプトに「## 想定読者」という見出しだけが取り残される。モデルはそれを見て困る。

そこで `tools/base.py` に2つの小さなヘルパーが置かれている。

```python
def section(label: str, value: Any) -> str:
    """値があるときだけ「## ラベル」ブロックを返す。"""
    if value is None:
        return ""
    if isinstance(value, (list, tuple)):
        value = "、".join(str(v) for v in value if v)   # multiselect 対応
    text = str(value).strip()
    if not text:
        return ""                                       # ← 空欄なら見出しごと消える
    return f"## {label}\n{text}\n"


def compose(*parts: str) -> str:
    return "\n".join(p for p in parts if p).strip()      # 空文字は連結しない
```

この2つのおかげで、ツール側の `build_prompt` は条件分岐なしのフラットな列挙で済む。

```python
def build(v: dict) -> str:
    return compose(
        "以下の条件でブログ記事を執筆してください。",
        section("テーマ", v["topic"]),
        section("想定読者", v.get("audience")),      # 空なら丸ごと消える
        section("必ず含めるキーワード", v.get("keywords")),
        section("目安の文字数", f"{v.get('length')}文字程度"),
        "## 出力形式\n1行目に記事タイトル（# 見出し1）を書き、続けて本文を...",
    )
```

**空欄をプロンプトから消すのは、埋めるのと同じくらい大事な仕事だ。** ここを f-string に戻した瞬間、任意入力欄の数だけ壊れ方が増える。

---

## 04. プロンプトは3枚重ねになっている

モデルに届く指示は、3つの層が積み重なったものだ。どこに何を書くかが層ごとに決まっている。

| 層 | 置き場所 | 内容 |
|---|---|---|
| **共通の土台** | `config.BASE_SYSTEM_PROMPT` | 全ツール共通。「必ず日本語で」「承知しましたなどの前置きを書かない」「不確かなら `[要確認]` と書く」「素材不足なら不足情報として挙げる」 |
| **役割** | 各ツールの `system_prompt` | そのツール固有の職能。ブログなら「H2/H3で構造化」「1段落3文以内」、メールなら「件名→宛名→…の順」「断りはクッション言葉→事実→代替案」 |
| **今回の依頼** | `build_prompt()` の戻り値 | ユーザーがフォームに入れた内容。`section()` で組み立てられた `## 見出し` の集まり |

1層目と2層目は `gemini_client._build_config()` で `---` を挟んで連結され、`system_instruction` としてまとめて渡される。3層目だけが毎回変わる本文（`contents`）になる。

---

## 05. SDKは1ファイルに閉じ込める

`gemini_client.py` の冒頭コメントが設計方針をそのまま書いている —— 「SDK を直接使うと各ツールが SDK の型に依存してしまうので、文字列を渡して文字列（またはストリーム）を受け取るだけに縛っている」。

実際、`from google import genai` と書いてよいのはこのファイルだけだ。ツール側は `google.genai` を知らないので、SDK が破壊的変更を入れても直すのは1ファイルで済む。公開されている関数はたった3つ。

```python
stream_text(...)   -> Iterator[str]   # 1発の生成。逐次 yield
generate_text(...) -> str             # 上をまとめて1つの文字列に
stream_chat(...)   -> Iterator[str]   # 履歴つきマルチターン
```

### エラーも日本語に翻訳して返す

SDK が投げる例外は種類が多く、しかも英語だ。ここではすべてを捕まえて `GeminiError` という1種類に包み直し、`_friendly_message()` で日本語に変換してから返す。`app.py` 側は `except GeminiError as exc: st.error(str(exc))` と書くだけでよくなる。

```python
def _friendly_message(exc: Exception) -> str:
    lowered = str(exc).lower()
    if "api key" in lowered or "unauthenticated" in lowered:
        return "API キーが無効です。.env の GEMINI_API_KEY を確認してください。"
    if "quota" in lowered or "429" in str(exc):
        return "レート制限・クォータ超過です。少し待つか、軽いモデルに切り替えてください。"
    if "safety" in lowered or "blocked" in lowered:
        return "安全性フィルタにより生成がブロックされました。入力内容を調整してください。"
    return f"生成に失敗しました: {exc}"
```

---

## 06. 「熟考モード」は世代ごとに書き方が違う

サイドバーのチェックボックス1つに見えるが、裏側は分岐している。Gemini 3系は `thinking_level`（`minimal`/`low`/`medium`/`high`）、2.5系は `thinking_budget`（トークン数、`-1` で動的、`0` で無効）。**この2つに互換性はない**ので、混ぜると API に弾かれる。

```python
def _thinking_config(model: str, thinking: bool) -> types.ThinkingConfig:
    if model.startswith("gemini-3"):
        if thinking:
            return types.ThinkingConfig(thinking_level="high")
        # minimal は一部モデルのみ。非対応モデルでは low が最小
        return types.ThinkingConfig(
            thinking_level="minimal" if model in _MINIMAL_OK else "low")

    # 2.5系。Pro は思考を完全には切れないため常に動的思考
    if "pro" in model:
        return types.ThinkingConfig(thinking_budget=-1)
    return types.ThinkingConfig(thinking_budget=-1 if thinking else 0)
```

分岐がこの関数1つに集約されているのが肝で、モデルを増やすときに触るのはここだけになる。

> **⚠️ 重要**
>
> **思考トークンも `max_output_tokens` を食う。** 「長文を書かせたら途中でぶつ切りになった」という不具合の原因はほぼこれで、本文を書く前に予算を思考で使い切っている。
>
> だから軽い変換タスクでは思考を最小にして本文にトークンを回し、長文ツールは `Tool.default_length` を `長め` 以上にしておく。`blog.py` が `default_length="長め"` なのはこの理由。

---

## 07. 1回の「生成する」で何が起きるか

ここまでの部品が、ボタン1回でどうつながるか。フォーム送信から画面更新までを追う。

```
[フォーム送信] → [必須チェック] → [プロンプト組立] → [長さ・温度の決定]
 render_form      required         build_prompt        run_generation
                       │                                      │
                       │ 未入力なら st.warning で             │
                       │ 中断し、API は呼ばない                │
                       ↓                                      ↓
                                              ┌───────────────┘
                                              ↓
                      [API 呼び出し] → [逐次表示] → [保存して再実行]
                       stream_text       st.write_stream   session_state + rerun
                       → Iterator[str]
```

エラー時は `GeminiError` を捕まえて `st.error` を出し、状態は書き換えない。再実行後、結果は `session_state` から描き直される。

長さの決め方に、細かいが効いている工夫がある（`app.py:194-196`）。

```python
max_tokens = config.LENGTH_PRESETS[settings["length"]]
if settings["length"] == "標準" and tool.default_length != "標準":
    max_tokens = config.LENGTH_PRESETS[tool.default_length]
```

ユーザーがスライダーを「標準」のまま触っていない場合に限り、ツール側の推奨値を採用する。ユーザーが明示的に選んだときはその選択を尊重する —— **「未設定」と「標準を選んだ」を区別している**わけだ。温度も同じ考え方で、サイドバーの「ツールごとの推奨値を使う」チェックで切り替わる。

---

## 08. Streamlit の「毎回全部再実行」とどう付き合うか

Streamlit はボタンを押すたびにスクリプトを上から丸ごと実行し直す。ローカル変数は毎回消えるので、残したいものは `st.session_state` に置く。このアプリが持っている状態は5つだけだ。

```python
st.session_state.setdefault("current", "blog")   # 表示中のツール
st.session_state.setdefault("results", {})       # tool_key -> 生成結果
st.session_state.setdefault("last_prompt", {})   # tool_key -> 直前のプロンプト
st.session_state.setdefault("history", [])       # 全ツール共通の履歴
st.session_state.setdefault("chat", [])          # チャットの会話履歴
```

`results` がツールごとの dict になっているのが要点で、ブログを生成 → メールに移動 → 戻ってくる、をしてもブログの結果は消えない。

もう1つ、再実行モデルへの対策が `gemini_client.get_client()` にある。毎回 `genai.Client()` を作り直さないよう、APIキーをキーにモジュールレベルの dict にキャッシュしている。

### 「さらに直す」は履歴ではなく再送信

結果の下の「修正して再生成」は、チャットのように会話を続けているわけではない。`last_prompt` に保存しておいた元プロンプトと、今表示している出力と、追加指示を**1本の新しいプロンプトに組み直して投げ直している。**

```python
prompt = (
    f"{st.session_state['last_prompt'].get(tool.key, '')}\n\n---\n\n"
    "## これまでの出力\n" f"{output}\n\n"
    "## 修正指示\n"     f"{refine.strip()}\n\n"
    "上の出力を修正指示に従って書き直し、修正後の完成版のみを出力してください。"
)
```

一方フリーチャット（`render_chat_page`）は本物のマルチターンで、`chat` リストを `stream_chat` に渡している。ここで気が利いているのは失敗時の処理で、`GeminiError` が出たら `st.session_state["chat"].pop()` で**直前に足したユーザー発言を取り消す。** そうしないと、返事のないまま自分の発言だけが履歴に残ってしまう。

---

## 09. ツールを1つ増やすには

ここまで読めば手順は短い。`tools/` にファイルを作り、`TOOL` を定義し、**`tools/__init__.py` の `_MODULES` リストに名前を書き足す。** 以上。

```python
_MODULES = [
    "blog", "email_reply", "summarize", "rewrite", "proofread",
    "notes", "sns", "headline", "brainstorm", "translate",
    "my_new_tool",   # ← ここに足さないと画面に出ない
]

TOOLS = [import_module(f".{name}", __package__).TOOL for name in _MODULES]
TOOLS_BY_KEY = {t.key: t for t in TOOLS}
```

> **⚠️ 落とし穴**
>
> **ディレクトリの自動スキャンはしていない。** ファイルを置いただけでは import されないので、サイドバーに何も起きず、エラーも出ない。
>
> `category` は `つくる` / `整える` / `やりとりする` のいずれかに。それ以外の値でもサイドバーには表示されるが、`CATEGORY_ORDER` に載っていないぶん並び順が末尾に落ちる。

### ツール定義で調整できるつまみ

| 項目 | 効果 | 実例 |
|---|---|---|
| `temperature` | 創造性。低いほど堅実で再現性が高い | ブログ `0.8` / メール `0.5` |
| `default_length` | スライダー未操作時のトークン上限 | 長文ツールは `長め`(8192) 以上 |
| `render_markdown` | `False` なら `st.text` でプレーン表示 | メール本文は装飾が邪魔なので `False` |
| `submit_label` | 送信ボタンの文言 | 「記事を書く」「返信文を作る」 |
| `Field.row` | 同じ番号どうしを横並びに | ただし**リスト上で隣接必須** |

---

## 10. この設計から持ち帰れること

このアプリが小さく保たれている理由は、突き詰めると1つの判断に集約される —— **変わるもの（ツール）と変わらないもの（画面・API）を、ファイル境界で分けたこと。**

- **UIをデータで宣言する。** 入力欄を `Field` のリストとして書き、描画は1箇所に集約する。ツールが10個でも100個でも `app.py` は伸びない。
- **外部SDKは1ファイルに閉じ込める。** 呼び出し側には文字列だけを見せる。SDKの仕様変更で直すのは1ファイル。
- **例外は自前の型に包み、その場で日本語にする。** UI側の `except` は1種類で済む。
- **プロンプトは連結ヘルパーで組む。** 空欄は見出しごと消す。f-string に戻すと任意入力の数だけ壊れ方が増える。
- **設定値の「未設定」と「明示的な選択」を区別する。** ユーザーが触っていないときだけ、こちらの推奨値を出す。
- **モデル世代の差は1つの関数に押し込む。** 増えるのは分岐であって、呼び出し側ではない。

逆に、この設計が受け入れているコストもはっきりしている。`_MODULES` への手動登録、未知の `Field.type` の黙ったフォールバック、`row` の隣接依存 —— どれも「暗黙に失敗する」たぐいの罠だ。小さく保つ代わりに、規約をコードではなくドキュメントで守っている、と読める。

---

読んだファイル: `app.py`（364行） / `config.py` / `gemini_client.py` / `tools/base.py` / `tools/__init__.py` / `tools/blog.py` / `tools/email_reply.py`

起動: `streamlit run app.py` → http://localhost:8501
