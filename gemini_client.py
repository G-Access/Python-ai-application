"""Gemini API の薄いラッパー。

google-genai SDK を直接使うと各ツールが SDK の型に依存してしまうので、
「文字列を渡して文字列（またはストリーム）を受け取る」だけに縛っている。
"""

from __future__ import annotations

import logging
from collections.abc import Iterator

from google import genai
from google.genai import types

from config import BASE_SYSTEM_PROMPT


logger = logging.getLogger(__name__)


class GeminiError(RuntimeError):
    """API 呼び出しに失敗したときに投げる。UI 側でそのまま表示する。

    メッセージは _friendly_message が組み立てた定型文だけを持つ。
    例外の生テキストは画面に出さず、起動したターミナルのログにのみ残す。
    """


_clients: dict[str, genai.Client] = {}

# Gemini 3 系は thinking_level（minimal/low/medium/high）で思考量を指定する。
# 2.5 系は旧来の thinking_budget（トークン数、-1 で動的、0 で無効）。
# 両者は互換性がないので、モデル世代ごとに使い分ける。
_MINIMAL_OK = {"gemini-3.6-flash", "gemini-3.5-flash-lite", "gemini-3.1-flash-lite"}


def _thinking_config(model: str, thinking: bool) -> types.ThinkingConfig:
    if model.startswith("gemini-3"):
        if thinking:
            return types.ThinkingConfig(thinking_level="high")
        # minimal は一部モデルのみ。非対応モデルでは low が最小。
        return types.ThinkingConfig(
            thinking_level="minimal" if model in _MINIMAL_OK else "low"
        )

    # 2.5 系。Pro は思考を完全には切れないため常に動的思考。
    if "pro" in model:
        return types.ThinkingConfig(thinking_budget=-1)
    return types.ThinkingConfig(thinking_budget=-1 if thinking else 0)


def get_client(api_key: str) -> genai.Client:
    """API キーごとにクライアントを使い回す（Streamlit の再実行対策）。"""
    if api_key not in _clients:
        _clients[api_key] = genai.Client(api_key=api_key)
    return _clients[api_key]


def _build_config(
    *,
    system_prompt: str | None,
    temperature: float,
    max_output_tokens: int,
    thinking: bool,
    model: str,
) -> types.GenerateContentConfig:
    system_instruction = BASE_SYSTEM_PROMPT
    if system_prompt:
        system_instruction = f"{BASE_SYSTEM_PROMPT}\n\n---\n\n{system_prompt}"

    # 思考トークンも max_output_tokens を消費するため、
    # 軽い変換タスクでは思考を最小にして本文にトークンを回す。
    return types.GenerateContentConfig(
        system_instruction=system_instruction,
        temperature=temperature,
        max_output_tokens=max_output_tokens,
        thinking_config=_thinking_config(model, thinking),
    )


def stream_text(
    *,
    api_key: str,
    model: str,
    prompt: str,
    system_prompt: str | None = None,
    temperature: float = 0.7,
    max_output_tokens: int = 4096,
    thinking: bool = False,
) -> Iterator[str]:
    """プロンプトを送り、生成テキストを逐次 yield する。"""
    client = get_client(api_key)
    config = _build_config(
        system_prompt=system_prompt,
        temperature=temperature,
        max_output_tokens=max_output_tokens,
        thinking=thinking,
        model=model,
    )
    try:
        for chunk in client.models.generate_content_stream(
            model=model, contents=prompt, config=config
        ):
            if chunk.text:
                yield chunk.text
    except Exception as exc:  # SDK の例外は種類が多いのでまとめて包む
        raise GeminiError(_friendly_message(exc)) from exc


def generate_text(**kwargs) -> str:
    """stream_text をまとめて 1 つの文字列にする。"""
    return "".join(stream_text(**kwargs))


def stream_chat(
    *,
    api_key: str,
    model: str,
    message: str,
    history: list[dict],
    system_prompt: str | None = None,
    temperature: float = 0.7,
    max_output_tokens: int = 4096,
    thinking: bool = False,
) -> Iterator[str]:
    """マルチターンのチャット。history は [{"role": "user"|"assistant", "content": str}]。"""
    client = get_client(api_key)
    config = _build_config(
        system_prompt=system_prompt,
        temperature=temperature,
        max_output_tokens=max_output_tokens,
        thinking=thinking,
        model=model,
    )
    sdk_history = [
        types.Content(
            role="user" if m["role"] == "user" else "model",
            parts=[types.Part(text=m["content"])],
        )
        for m in history
        if m.get("content")
    ]
    try:
        chat = client.chats.create(model=model, config=config, history=sdk_history)
        for chunk in chat.send_message_stream(message):
            if chunk.text:
                yield chunk.text
    except Exception as exc:
        raise GeminiError(_friendly_message(exc)) from exc


def _friendly_message(exc: Exception) -> str:
    """SDK の例外を、画面に出してよい日本語の定型文に変換する。

    生の例外文にはリクエスト先やレスポンス本文の断片が含まれうるため、
    どの分岐にも当たらなかった場合でも素通しはせず、詳細はログにだけ送る。
    """
    text = str(exc)
    lowered = text.lower()
    if "api key" in lowered or "api_key" in lowered or "unauthenticated" in lowered:
        return "API キーが無効です。.env の GEMINI_API_KEY を確認してください。"
    if "quota" in lowered or "resource_exhausted" in lowered or "429" in text:
        return "レート制限・クォータ超過です。少し待つか、軽いモデルに切り替えてください。"
    if "not found" in lowered and "model" in lowered:
        return "指定したモデルが利用できません。別のモデルを選択してください。"
    if "safety" in lowered or "blocked" in lowered:
        return "安全性フィルタにより生成がブロックされました。入力内容を調整してください。"
    logger.warning("Gemini 呼び出しに失敗: %s", text)
    return "生成に失敗しました。時間をおいて再試行してください（詳細は起動中のターミナルに出力しました）。"
