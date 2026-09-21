#!/usr/bin/env python3
"""PostToolUse hook：把執行過的命令分類記帳，供 claim-guard.py 比對。

像行車紀錄器——只記錄，永遠不干預，任何情況都 exit 0。
與 claim-guard.py 必須成對安裝：只裝這支不會有任何效果，只裝那支則永遠攔錯人。

本檔自含所有邏輯，不依賴其他 hook 檔案。
"""

from __future__ import annotations

import json
import re
import sys
import tempfile
import time
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="UTF-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="UTF-8")

LEDGER_DIR = Path(tempfile.gettempdir()) / "bootstrap-ai-project-claim-ledger"
MAX_ENTRIES = 200
COMMAND_CHARS = 160

# 分類順序有意義：先比對 test，再 check，最後 search。
# 一條命令只歸一類，避免 `npm test` 同時算成 check 而讓宣稱過關。
CATEGORY_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    (
        "test",
        re.compile(
            r"\b(pytest|unittest|nose2|npm\s+(run\s+)?test|yarn\s+test|pnpm\s+test|"
            r"vitest|jest|mocha|dotnet\s+test|go\s+test|cargo\s+test|rspec|"
            r"phpunit|gradle\s+test|mvn\s+test|ctest)\b",
            re.IGNORECASE,
        ),
    ),
    (
        "check",
        # --version / -V 不能放進 \b(...)\b：連字號前不存在 word boundary，永遠比對不到。
        re.compile(
            r"\b(lint|ruff|flake8|eslint|mypy|pyright|tsc|clippy|"
            r"build|compile|make|msbuild|validate|check)\b"
            r"|\bgit\s+(status|diff|log)\b"
            r"|--version\b"
            r"|(?<![\w-])-V(?![\w-])",
            re.IGNORECASE,
        ),
    ),
    (
        "search",
        re.compile(
            r"\b(grep|rg|ripgrep|ack|find|fd|ls|dir|Get-ChildItem|Select-String|"
            r"gh\s+(search|api))\b",
            re.IGNORECASE,
        ),
    ),
]

# Grep / Glob 工具本身就是搜尋行為，不必比對命令字串。
TOOL_CATEGORY = {"Grep": "search", "Glob": "search"}


def classify(tool_name: str, command: str) -> str | None:
    direct = TOOL_CATEGORY.get(tool_name)
    if direct:
        return direct
    if not command:
        return None
    for category, pattern in CATEGORY_PATTERNS:
        if pattern.search(command):
            return category
    return None


def ledger_path(session_id: str) -> Path:
    safe = "".join(char for char in session_id if char.isalnum() or char in "-_") or "unknown"
    return LEDGER_DIR / f"{safe}.json"


def load_ledger(path: Path) -> dict[str, list[dict[str, str]]]:
    try:
        data = json.loads(path.read_text(encoding="UTF-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def record(session_id: str, category: str, command: str, tool_name: str) -> None:
    path = ledger_path(session_id)
    ledger = load_ledger(path)
    entries = ledger.setdefault(category, [])
    entries.append(
        {
            "at": time.strftime("%H:%M:%S"),
            "tool": tool_name,
            "command": command[:COMMAND_CHARS],
        }
    )
    del entries[:-MAX_ENTRIES]
    try:
        LEDGER_DIR.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(ledger, ensure_ascii=False), encoding="UTF-8")
    except OSError:
        pass  # 記帳失敗絕不影響工作流程


def main() -> int:
    try:
        event = json.loads(sys.stdin.read() or "{}")
    except (json.JSONDecodeError, OSError):
        return 0

    tool_name = str(event.get("tool_name", ""))
    tool_input = event.get("tool_input") or {}
    command = str(tool_input.get("command") or tool_input.get("pattern") or "")

    category = classify(tool_name, command)
    if category:
        record(str(event.get("session_id", "unknown")), category, command, tool_name)
    return 0


if __name__ == "__main__":
    sys.exit(main())
