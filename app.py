"""AI ライティングツール — Streamlit エントリポイント。"""

from __future__ import annotations

import datetime as dt
import re
from collections.abc import Iterator
from typing import Any

import streamlit as st

import config
from gemini_client import GeminiError, stream_chat, stream_text
from tools import CHAT_SYSTEM_PROMPT, TOOLS_BY_KEY, Tool, tools_by_category
from tools.base import Field

st.set_page_config(
    page_title=config.APP_TITLE,
    page_icon=config.APP_ICON,
    layout="wide",
    initial_sidebar_state="expanded",
)

CHAT_KEY = "__chat__"

# Markdown の画像記法は生 HTML がエスケープされていても描画されるため、
# 画面に出た時点で外部へリクエストが飛ぶ。貼り付けた文章に仕込まれた指示で
# モデルに画像記法を出力させる経路を塞ぐ。
_IMG_INLINE = re.compile(r"!\[([^\]]*)\]\([^)]*\)")


def strip_remote_images(text: str) -> str:
    """モデル出力から Markdown の画像記法を取り除く（描画時の外部通信を防ぐ）。"""
    text = _IMG_INLINE.sub(r"[画像: \1]", text)
    # 参照形式（![alt][ref]）などの取りこぼしも画像として描画させない
    return text.replace("![", "[")


def stream_markdown(chunks: Iterator[str]) -> str:
    """ストリームを逐次描画しつつ全文を返す。描画のたびに画像記法を除去する。

    st.write_stream は届いたチャンクをそのまま Markdown 描画してしまうため、
    生成中に画像記法が描画されないよう、蓄積した全文を毎回除去してから描く。
    戻り値は除去前の全文（保存・コピー用にはモデルの出力をそのまま残す）。
    """
    placeholder = st.empty()
    buffer = ""
    for chunk in chunks:
        buffer += chunk
        placeholder.markdown(strip_remote_images(buffer))
    placeholder.markdown(strip_remote_images(buffer))
    return buffer


# --------------------------------------------------------------------------
# 状態
# --------------------------------------------------------------------------
def init_state() -> None:
    st.session_state.setdefault("current", "blog")
    st.session_state.setdefault("results", {})       # tool_key -> 生成結果テキスト
    st.session_state.setdefault("last_prompt", {})   # tool_key -> 直前に送ったプロンプト
    st.session_state.setdefault("history", [])       # 全ツール共通の履歴
    st.session_state.setdefault("chat", [])          # チャットの会話履歴
    st.session_state.setdefault("pending", None)     # 実行待ちの (tool_key, prompt)


def push_history(tool_name: str, output: str) -> None:
    st.session_state["history"].insert(
        0,
        {
            "time": dt.datetime.now().strftime("%m/%d %H:%M"),
            "tool": tool_name,
            "output": output,
        },
    )
    del st.session_state["history"][50:]


# --------------------------------------------------------------------------
# サイドバー
# --------------------------------------------------------------------------
def render_sidebar() -> dict[str, Any]:
    with st.sidebar:
        st.markdown(f"## {config.APP_ICON} {config.APP_TITLE}")

        api_key = config.get_api_key()
        if not api_key:
            st.error("API キーが未設定です")
            api_key = st.text_input(
                "GEMINI_API_KEY", type="password",
                help="`.env` に GEMINI_API_KEY を書いておくと、次回から入力不要です。",
            ).strip()
            st.caption("キーの取得: https://aistudio.google.com/apikey")

        st.divider()
        st.caption("ツール")

        for category, tools in tools_by_category().items():
            st.markdown(f"**{category}**")
            for tool in tools:
                is_current = st.session_state["current"] == tool.key
                if st.button(
                    tool.title,
                    key=f"nav_{tool.key}",
                    use_container_width=True,
                    type="primary" if is_current else "secondary",
                ):
                    st.session_state["current"] = tool.key
                    st.rerun()

        st.markdown("**そのほか**")
        if st.button(
            "💬 フリーチャット",
            key="nav_chat",
            use_container_width=True,
            type="primary" if st.session_state["current"] == CHAT_KEY else "secondary",
        ):
            st.session_state["current"] = CHAT_KEY
            st.rerun()

        st.divider()
        with st.expander("⚙️ 生成設定", expanded=False):
            labels = [m.label for m in config.MODELS]
            default_idx = next(
                (i for i, m in enumerate(config.MODELS) if m.id == config.DEFAULT_MODEL), 1
            )
            picked = st.selectbox("モデル", labels, index=default_idx)
            model = config.MODELS[labels.index(picked)]
            st.caption(model.note)

            length = st.select_slider(
                "出力の長さ上限", options=list(config.LENGTH_PRESETS), value="標準"
            )
            creativity = st.slider(
                "創造性", 0.0, 1.5, 0.7, 0.1,
                help="低いほど堅実で再現性が高く、高いほど発想が飛びます。",
            )
            use_tool_temp = st.checkbox(
                "ツールごとの推奨値を使う", value=True,
                help="外すと上のスライダーの値を全ツールに適用します。",
            )
            thinking = st.checkbox(
                "熟考モード", value=False,
                help="生成前に考えさせます。品質は上がりますが遅くなります（Pro は常時ON）。",
            )

        return {
            "api_key": api_key,
            "model": model.id,
            "length": length,
            "creativity": creativity,
            "use_tool_temp": use_tool_temp,
            "thinking": thinking,
        }


# --------------------------------------------------------------------------
# フォーム描画
# --------------------------------------------------------------------------
def render_field(tool: Tool, f: Field) -> Any:
    key = f"{tool.key}:{f.key}"
    label = f.label + (" *" if f.required else "")
    if f.type == "textarea":
        return st.text_area(label, key=key, height=f.height,
                            placeholder=f.placeholder, help=f.help or None)
    if f.type == "select":
        idx = f.options.index(f.default) if f.default in f.options else 0
        return st.selectbox(label, f.options, index=idx, key=key, help=f.help or None)
    if f.type == "radio":
        idx = f.options.index(f.default) if f.default in f.options else 0
        return st.radio(label, f.options, index=idx, key=key, horizontal=True)
    if f.type == "multiselect":
        return st.multiselect(label, f.options, default=f.default or [], key=key)
    if f.type == "number":
        return st.number_input(label, value=int(f.default or 0), step=1, key=key)
    if f.type == "checkbox":
        return st.checkbox(label, value=bool(f.default), key=key, help=f.help or None)
    return st.text_input(label, key=key, placeholder=f.placeholder, help=f.help or None)


def render_form(tool: Tool) -> dict[str, Any] | None:
    """フォームを描画し、送信されたら入力値の dict を返す。"""
    values: dict[str, Any] = {}
    with st.form(key=f"form_{tool.key}", border=False):
        i = 0
        while i < len(tool.fields):
            f = tool.fields[i]
            if f.row is None:
                values[f.key] = render_field(tool, f)
                i += 1
                continue
            # 同じ row 番号が続く分をまとめて横並びにする
            group = [f]
            while i + len(group) < len(tool.fields) and tool.fields[i + len(group)].row == f.row:
                group.append(tool.fields[i + len(group)])
            for col, gf in zip(st.columns(len(group)), group):
                with col:
                    values[gf.key] = render_field(tool, gf)
            i += len(group)

        submitted = st.form_submit_button(
            f"✨ {tool.submit_label}", type="primary", use_container_width=True
        )

    if not submitted:
        return None

    missing = [f.label for f in tool.fields if f.required and not str(values.get(f.key) or "").strip()]
    if missing:
        st.warning("次の項目は必須です: " + "、".join(missing))
        return None
    return values


# --------------------------------------------------------------------------
# 生成
# --------------------------------------------------------------------------
def run_generation(tool: Tool, prompt: str, settings: dict) -> None:
    if not settings["api_key"]:
        st.error("API キーを設定してください。")
        return

    temperature = tool.temperature if settings["use_tool_temp"] else settings["creativity"]
    max_tokens = config.LENGTH_PRESETS[settings["length"]]
    if settings["length"] == "標準" and tool.default_length != "標準":
        max_tokens = config.LENGTH_PRESETS[tool.default_length]

    try:
        with st.spinner("生成中…"):
            output = stream_markdown(
                stream_text(
                    api_key=settings["api_key"],
                    model=settings["model"],
                    prompt=prompt,
                    system_prompt=tool.system_prompt,
                    temperature=temperature,
                    max_output_tokens=max_tokens,
                    thinking=settings["thinking"],
                )
            )
    except GeminiError as exc:
        st.error(str(exc))
        return

    output = (output or "").strip()
    if not output:
        st.warning("空の応答が返りました。もう一度実行するか、モデルを変えてみてください。")
        return

    st.session_state["results"][tool.key] = output
    st.session_state["last_prompt"][tool.key] = prompt
    push_history(tool.name, output)
    st.rerun()


def render_result(tool: Tool, settings: dict) -> None:
    output = st.session_state["results"].get(tool.key)
    if not output:
        return

    st.divider()
    st.subheader("生成結果")

    tab_view, tab_raw = st.tabs(["表示", "コピー用テキスト"])
    with tab_view:
        if tool.render_markdown:
            st.markdown(strip_remote_images(output))
        else:
            st.text(output)
    with tab_raw:
        st.code(output, language=None, wrap_lines=True)

    col1, col2, _ = st.columns([1, 1, 2])
    stamp = dt.datetime.now().strftime("%Y%m%d_%H%M")
    col1.download_button(
        "⬇️ .md で保存", output, file_name=f"{tool.key}_{stamp}.md",
        mime="text/markdown", use_container_width=True,
    )
    if col2.button("🗑️ 結果をクリア", key=f"clear_{tool.key}", use_container_width=True):
        st.session_state["results"].pop(tool.key, None)
        st.rerun()

    st.markdown("**この結果をさらに直す**")
    refine = st.text_input(
        "追加の指示", key=f"refine_{tool.key}", label_visibility="collapsed",
        placeholder="例: 3割短くして、見出しをもっとキャッチーに",
    )
    if st.button("🔄 修正して再生成", key=f"refine_btn_{tool.key}", disabled=not refine.strip()):
        prompt = (
            f"{st.session_state['last_prompt'].get(tool.key, '')}\n\n"
            "---\n\n"
            "## これまでの出力\n"
            f"{output}\n\n"
            "## 修正指示\n"
            f"{refine.strip()}\n\n"
            "上の出力を修正指示に従って書き直し、修正後の完成版のみを出力してください。"
        )
        run_generation(tool, prompt, settings)


# --------------------------------------------------------------------------
# 画面
# --------------------------------------------------------------------------
def render_tool_page(tool: Tool, settings: dict) -> None:
    st.title(tool.title)
    st.caption(tool.description)

    values = render_form(tool)
    if values is not None:
        run_generation(tool, tool.build_prompt(values), settings)

    render_result(tool, settings)


def render_chat_page(settings: dict) -> None:
    st.title("💬 フリーチャット")
    st.caption("決まった型のないライティング相談に。文脈を覚えたまま何度でもやり取りできます。")

    if st.button("🗑️ 会話をリセット"):
        st.session_state["chat"] = []
        st.rerun()

    for msg in st.session_state["chat"]:
        with st.chat_message(msg["role"]):
            if msg["role"] == "user":
                st.markdown(msg["content"])
            else:
                st.markdown(strip_remote_images(msg["content"]))

    user_input = st.chat_input("書きたいこと・直したいことを入力")
    if not user_input:
        return

    if not settings["api_key"]:
        st.error("API キーを設定してください。")
        return

    history = list(st.session_state["chat"])
    st.session_state["chat"].append({"role": "user", "content": user_input})
    with st.chat_message("user"):
        st.markdown(user_input)

    with st.chat_message("assistant"):
        try:
            reply = stream_markdown(
                stream_chat(
                    api_key=settings["api_key"],
                    model=settings["model"],
                    message=user_input,
                    history=history,
                    system_prompt=CHAT_SYSTEM_PROMPT,
                    temperature=settings["creativity"],
                    max_output_tokens=config.LENGTH_PRESETS[settings["length"]],
                    thinking=settings["thinking"],
                )
            )
        except GeminiError as exc:
            st.error(str(exc))
            st.session_state["chat"].pop()
            return

    st.session_state["chat"].append({"role": "assistant", "content": reply})


def render_history() -> None:
    history = st.session_state["history"]
    if not history:
        return
    with st.sidebar:
        st.divider()
        with st.expander(f"🕘 履歴（{len(history)}）", expanded=False):
            for i, item in enumerate(history[:20]):
                st.caption(f"{item['time']} · {item['tool']}")
                st.text(item["output"][:120] + ("…" if len(item["output"]) > 120 else ""))
                st.download_button(
                    "保存", item["output"], file_name=f"history_{i}.md",
                    key=f"hist_dl_{i}", use_container_width=True,
                )
                st.markdown("---")


def main() -> None:
    init_state()
    settings = render_sidebar()

    current = st.session_state["current"]
    if current == CHAT_KEY:
        render_chat_page(settings)
    else:
        render_tool_page(TOOLS_BY_KEY[current], settings)

    render_history()


if __name__ == "__main__":
    main()
