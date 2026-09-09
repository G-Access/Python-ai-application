# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```powershell
streamlit run app.py --server.address localhost --server.port 8501   # 起動（http://localhost:8501）
```

- **`--server.address localhost` は毎回つける。** 既定は全インターフェイス待ち受けで同一 LAN から到達できてしまう。
  この指定を `.streamlit/config.toml` に書いてはいけない。同じファイルを Streamlit Community Cloud も読むため、
  クラウド側の待ち受けが壊れてデプロイが起動しなくなる。
- **リント・フォーマット・テストのコマンドは存在しない。** 設定ファイルも dev 依存も意図的に置いていない。導入を勝手に提案しない。
- **git リポジトリ。** リモートは `G-Access/Python-ai-application`（private / `main`）。git 2.55.0 と gh CLI が入っており、gh は認証済み。コミット・push は普通に行える。
- **コミットの識別情報はこのリポジトリのローカル設定にだけ入れてある**（`git config user.name` / `user.email`）。グローバル設定は空なので、`--global` を前提にした手順を書かない。
- 動作確認が必要なときは `streamlit.testing.v1.AppTest` でページを描画させるのが最も速い（tests/ は作らず、一時ディレクトリのスクリプトで実行する）。

## 言語規約

UI 文字列・システムプロンプト・コメント・docstring はすべて日本語で書く。
`config.BASE_SYSTEM_PROMPT` がモデルに日本語出力を強制しているため、プロンプトも日本語で統一する。

## ツールを追加するとき

`tools/` にモジュールを置いて `TOOL` を定義するだけでは**画面に出ない**。
`tools/__init__.py` の `_MODULES` リストにモジュール名を手で追記する必要がある（ディレクトリの自動スキャンはしていない）。

`Tool.category` は `tools/__init__.py` の `CATEGORY_ORDER`（`つくる` / `整える` / `やりとりする`）のいずれかにする。それ以外の値もサイドバーには出るが、順序が末尾に落ちる。

## フォーム描画（app.py）の制約

- `Field.type` は `text` / `textarea` / `select` / `multiselect` / `number` / `checkbox` / `radio` のみ。未知の値は警告なく `st.text_input` にフォールバックする。
- 同じ `row` 番号の Field を横並びにするロジックは、**リスト上で連続している要素しか見ない**。同じ `row` を持つ Field は `fields` 内で必ず隣接させること。
- `Tool.render_markdown=False` は出力を `st.text` で表示する。メール本文など Markdown 装飾が邪魔になる用途に使う。

## Gemini API（gemini_client.py）

- **思考トークンも `max_output_tokens` を消費する。** 出力が途中で切れる不具合の原因はほぼこれ。長文を書かせるツールは `Tool.default_length` を `長め` 以上にする。
- **世代ごとに思考の指定方法が違う。** Gemini 3 系は `thinking_level`（`minimal`/`low`/`medium`/`high`）、2.5 系は `thinking_budget`（トークン数、`-1` で動的、`0` で無効）。互換性がないので混ぜると弾かれる。分岐は `_thinking_config()` に集約してあるので、モデルを追加するときはここだけ直す。
- `minimal` は一部モデルしか受け付けない（`_MINIMAL_OK` の集合を参照）。非対応の 3 系モデルでは `low` が最小。
- モデル ID は推測で書かない。学習データより新しいモデルが出ているので、必ず https://ai.google.dev/gemini-api/docs/models で実在を確認してから `config.MODELS` に追加する。
- **ツールモジュールから `google.genai` を直接 import しない。** SDK 依存は `gemini_client.py` に閉じ込め、ツール側は文字列を渡して文字列を受け取るだけにする。
- SDK の例外はすべて `GeminiError` に包み、`_friendly_message` で日本語のメッセージに変換してから UI に出す。新しいエラー種別を扱うときはここに分岐を足す。

## プロンプトの組み立て

`tools/base.py` の `compose()` と `section()` を使う。`section()` は値が空なら自身を出力しないので、任意入力欄が空でもプロンプトに空の見出しが残らない。この仕組みに乗らず f-string で直接組み立てると、空欄時に壊れたプロンプトが飛ぶ。

## API キー

`config.get_api_key()` が `GEMINI_API_KEY` → `GOOGLE_API_KEY` → `st.secrets` の順で探す。
`.env` は gitignore 済み。キーをコードや README に書かない。

## Windows での起動時の落とし穴

`~/.streamlit/credentials.toml` が無いと、初回起動時にターミナルでメールアドレス入力を求められ、**サーバーが起動しないまま止まる**（ポートが開かない）。
このファイルは既に作成済みだが、作り直す場合は **BOM なし** で書くこと。PowerShell の `Out-File -Encoding utf8` は BOM を付けるため TOML の解析に失敗し、同じ症状が再発する。
