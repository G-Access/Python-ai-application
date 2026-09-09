"""Streamlit x LLM アプリのセキュリティレビュー用・候補地点の洗い出し。

出力するのは「見るべき場所」であって「脆弱性」ではない。
判定は必ずレビューする側がコードを読んで行う。

usage: python recon.py <project-root>
"""

from __future__ import annotations

import argparse
import ast
import re
import sys
from pathlib import Path

SKIP_DIRS = {
    ".git", "__pycache__", ".venv", "venv", "env", "node_modules",
    "site-packages", ".mypy_cache", ".pytest_cache", ".ruff_cache",
    "build", "dist", ".tox",
}

# カテゴリ -> (なぜ見るのか, 正規表現)
PATTERNS: dict[str, tuple[str, str]] = {
    "A: 秘密情報の入口": (
        "キーの読み込み・受け取り。ここを起点に 4 つの出口まで追う。",
        r"getenv|environ\[|environ\.get|st\.secrets|load_dotenv|"
        r"\bapi[_-]?key\b|\bAPI_KEY\b|\bsecret\b|\btoken\b",
    ),
    "A: 秘密情報の直書き疑い": (
        "リテラルに実キーが入っていないか。プレースホルダなら問題ない。",
        r"[\"'](?:sk-[A-Za-z0-9_-]{16,}|sk-ant-[A-Za-z0-9_-]{16,}|"
        r"AIza[A-Za-z0-9_-]{30,}|hf_[A-Za-z0-9]{20,}|gsk_[A-Za-z0-9]{20,})[\"']",
    ),
    "A: エラーの素通し（キー露出経路）": (
        "例外の生文字列が UI へ出ていないか。最後のフォールバックを特に見る。",
        r"st\.exception|st\.error\s*\(\s*(?:str\s*\(|f[\"'])|"
        r"traceback\.|format_exc|print_exc|"
        r"f[\"'][^\"']*\{\s*(?:exc|e|err|error)\b",
    ),
    "C: 出力の HTML 描画": (
        "モデル出力が流れていれば XSS。静的な装飾だけなら問題ない。",
        r"unsafe_allow_html\s*=\s*True|components\.v1\.html|st\.html\s*\(",
    ),
    "C: 出力の描画・書き出し": (
        "Markdown 描画は画像記法による外部通信の経路になりうる（C-2）。",
        r"st\.markdown|st\.write_stream|st\.download_button|st\.code|st\.text\s*\(",
    ),
    "D: 出力の副作用（最優先）": (
        "モデル出力がここに到達するなら深刻度は跳ね上がる。",
        r"\beval\s*\(|\bexec\s*\(|subprocess|os\.system|os\.popen|"
        r"pickle\.loads?|yaml\.load\s*\(|__import__|\bcompile\s*\(",
    ),
    "E: 入力の受け口": (
        "外部由来のデータ。B（プロンプト混入）と E（パス操作）に接続する。",
        r"st\.file_uploader|st\.query_params|experimental_get_query_params|"
        r"requests\.|httpx\.|urllib\.request",
    ),
    "E/F: ファイル操作": (
        "パスにユーザー入力が混ざらないか。保存物に機微情報が入らないか。",
        r"\bopen\s*\(|os\.path\.join|Path\s*\(|shutil\.|\.write_text|\.write_bytes|"
        r"os\.makedirs|to_csv|to_json",
    ),
    "F: ログ出力": (
        "プロンプト・レスポンス全文をログに落としていないか。",
        r"\bprint\s*\(|logger\.|logging\.|\.info\s*\(|\.debug\s*\(",
    ),
    "B/D: LLM 呼び出し": (
        "プロンプトの組み立て元と、戻り値の行き先を両方追う。",
        r"generate_content|chat\.completions|messages\.create|"
        r"system_instruction|system_prompt|\.invoke\s*\(|send_message",
    ),
}


def iter_python_files(root: Path):
    for path in sorted(root.rglob("*.py")):
        rel_parts = path.relative_to(root).parts[:-1]
        # ドットディレクトリ（.claude, .venv など）は対象アプリのコードではない
        if any(p in SKIP_DIRS or p.startswith(".") for p in rel_parts):
            continue
        yield path


def scan_patterns(root: Path, files: list[Path]) -> dict[str, list[str]]:
    compiled = {k: re.compile(v[1]) for k, v in PATTERNS.items()}
    hits: dict[str, list[str]] = {k: [] for k in PATTERNS}
    for path in files:
        try:
            lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
        except OSError:
            continue
        rel = path.relative_to(root).as_posix()
        for n, line in enumerate(lines, 1):
            stripped = line.strip()
            if stripped.startswith("#"):
                continue
            for cat, rx in compiled.items():
                if rx.search(line):
                    hits[cat].append(f"{rel}:{n}: {stripped[:110]}")
    return hits


MUTATING_METHODS = {
    "append", "extend", "insert", "add", "update", "setdefault",
    "pop", "clear", "remove", "discard",
}


def _mutated_names(tree: ast.AST) -> set[str]:
    """ファイル内のどこかで中身を書き換えられている名前を集める。

    定数として置かれただけの dict / list は共有されても害がない。
    実際に書き込まれているものだけが、セッションを越えたデータ混入の経路になる。
    """
    names: set[str] = set()
    for node in ast.walk(tree):
        # x[k] = v  /  del x[k]
        if isinstance(node, (ast.Assign, ast.AugAssign, ast.Delete)):
            targets = node.targets if isinstance(node, (ast.Assign, ast.Delete)) else [node.target]
            for t in targets:
                if isinstance(t, ast.Subscript) and isinstance(t.value, ast.Name):
                    names.add(t.value.id)
        # x.append(...) など
        elif isinstance(node, ast.Call):
            fn = node.func
            if (
                isinstance(fn, ast.Attribute)
                and fn.attr in MUTATING_METHODS
                and isinstance(fn.value, ast.Name)
            ):
                names.add(fn.value.id)
    return names


def scan_shared_state(root: Path, files: list[Path]) -> list[str]:
    """セッションを越えて共有される状態（F-3）を AST で拾う。

    モジュールレベルの可変オブジェクトとキャッシュ付き関数はプロセス全体で共有され、
    公開時に他人のデータが混ざる経路になる。ただし書き換えられていない定数は
    共有されても無害なので、実際に変更されているものだけを挙げる。
    """
    found: list[str] = []
    for path in files:
        try:
            tree = ast.parse(path.read_text(encoding="utf-8", errors="replace"))
        except (OSError, SyntaxError):
            continue
        rel = path.relative_to(root).as_posix()
        mutated = _mutated_names(tree)

        for node in tree.body:
            if isinstance(node, (ast.Assign, ast.AnnAssign)):
                value = node.value
                if isinstance(value, (ast.Dict, ast.List, ast.Set)):
                    targets = node.targets if isinstance(node, ast.Assign) else [node.target]
                    for t in targets:
                        if isinstance(t, ast.Name) and t.id in mutated:
                            kind = type(value).__name__.lower()
                            found.append(
                                f"{rel}:{node.lineno}: モジュールレベルの {kind} `{t.id}`"
                                " が実行中に書き換えられている — 全ユーザーで共有される"
                            )

            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                for dec in node.decorator_list:
                    src = ast.unparse(dec)
                    if any(k in src for k in ("cache_data", "cache_resource", "lru_cache")):
                        found.append(
                            f"{rel}:{node.lineno}: @{src} が付いた `{node.name}`"
                            " — 引数だけで戻り値が決まるか確認"
                        )
    return found


def scan_config(root: Path) -> list[str]:
    """設定ファイルまわり（A-4 / G / H）の事実を集める。判定はしない。"""
    notes: list[str] = []

    gitignore = root / ".gitignore"
    ignored = ""
    if gitignore.exists():
        ignored = gitignore.read_text(encoding="utf-8", errors="replace")
    else:
        notes.append(".gitignore: 無し")

    for name in (".env", ".streamlit/secrets.toml", ".env.local"):
        if (root / name).exists():
            base = name.split("/")[-1]
            covered = base in ignored or name in ignored
            mark = "gitignore 済み" if covered else "★ gitignore されていない"
            notes.append(f"{name}: 存在（{mark}）")

    example = root / ".env.example"
    if example.exists():
        body = example.read_text(encoding="utf-8", errors="replace")
        risky = re.search(r"=\s*(?:sk-|AIza|hf_|gsk_)[A-Za-z0-9_-]{16,}", body)
        notes.append(
            f".env.example: 存在（{'★ 実キーらしき値あり' if risky else 'プレースホルダのみ'}）"
        )

    cfg = root / ".streamlit" / "config.toml"
    if cfg.exists():
        body = cfg.read_text(encoding="utf-8-sig", errors="replace")
        notes.append(".streamlit/config.toml: 存在")
        for key in ("address", "enableXsrfProtection", "enableCORS",
                    "maxUploadSize", "headless"):
            m = re.search(rf"^\s*{key}\s*=\s*(.+)$", body, re.MULTILINE)
            notes.append(f"  {key} = {m.group(1).strip() if m else '（未設定＝既定値）'}")
    else:
        notes.append(
            ".streamlit/config.toml: 無し"
            " → server.address は既定＝全インターフェイス待ち受け（G-2）"
        )

    req = root / "requirements.txt"
    if req.exists():
        lines = [
            ln.strip()
            for ln in req.read_text(encoding="utf-8", errors="replace").splitlines()
            if ln.strip() and not ln.strip().startswith("#")
        ]
        loose = [ln for ln in lines if "==" not in ln]
        notes.append(
            f"requirements.txt: {len(lines)} 件中 {len(loose)} 件がバージョン未固定"
            + (f" → {', '.join(loose[:8])}" if loose else "")
        )

    return notes


def main() -> int:
    ap = argparse.ArgumentParser(description="セキュリティレビュー用の候補地点洗い出し")
    ap.add_argument("root", nargs="?", default=".", help="プロジェクトルート")
    args = ap.parse_args()

    # Windows の既定コンソールは cp932 なので、そのままだと日本語が化ける
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, OSError):
        pass

    root = Path(args.root).resolve()
    if not root.is_dir():
        print(f"ディレクトリが見つからない: {root}", file=sys.stderr)
        return 1

    files = list(iter_python_files(root))
    print(f"# 候補地点の洗い出し: {root}")
    print(f"# Python ファイル {len(files)} 件を走査")
    print("# ここに出るのは『見るべき場所』であり、脆弱性の判定ではない。\n")

    print("=" * 70)
    print("設定ファイルの状況")
    print("=" * 70)
    for note in scan_config(root):
        print(f"  {note}")

    print()
    print("=" * 70)
    print("F-3: セッションを越えて共有される状態")
    print("=" * 70)
    shared = scan_shared_state(root, files)
    for item in shared or ["該当なし"]:
        print(f"  {item}")

    hits = scan_patterns(root, files)
    for cat, (why, _) in PATTERNS.items():
        print()
        print("=" * 70)
        print(f"{cat}  ({len(hits[cat])} 件)")
        print(f"  → {why}")
        print("=" * 70)
        if not hits[cat]:
            print("  該当なし")
            continue
        for line in hits[cat][:40]:
            print(f"  {line}")
        if len(hits[cat]) > 40:
            print(f"  ... 他 {len(hits[cat]) - 40} 件")

    print()
    print("次の手順: checklist.md を読み、各候補を実際にコードで裏取りしてから報告する。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
