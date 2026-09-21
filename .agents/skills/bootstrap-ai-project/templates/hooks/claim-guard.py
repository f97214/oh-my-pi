#!/usr/bin/env python3
"""Stop hook：宣稱做過某事，本 session 就要有對應類別的命令紀錄。

與 claim-ledger.py 成對安裝。帳本由那支寫，這支只讀。

這是防呆不是防駭——換個說法（「已經沒問題了」）就繞得過去，而且只比對
類別、不驗證宣稱與那筆紀錄是否真的對應。它擋的是疏忽：沒跑測試卻順口
說「測試通過」。要更嚴謹的證據鏈請用 Spectra TDD 的 test-observer。

本檔自含所有邏輯，不依賴其他 hook 檔案。
"""

from __future__ import annotations

import json
import os
import re
import sys
import tempfile
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="UTF-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="UTF-8")

EXIT_OK = 0
EXIT_BLOCK = 2

LEDGER_DIR = Path(tempfile.gettempdir()) / "bootstrap-ai-project-claim-ledger"
STATE_DIR = Path(tempfile.gettempdir()) / "bootstrap-ai-project-claim-guard"
DEFAULT_MAX_BLOCKS = 2

# 每條規則：宣稱樣式 → 可接受的帳本類別（滿足其一即可）。
RULES: list[tuple[str, re.Pattern[str], tuple[str, ...]]] = [
    (
        "測試通過",
        re.compile(
            r"(測試(全部)?(都)?(通過|成功)|全部通過|all\s+tests?\s+pass|"
            r"tests?\s+(are\s+)?passing|test\s+suite\s+passe)",
            re.IGNORECASE,
        ),
        ("test",),
    ),
    (
        "已驗證／已確認",
        re.compile(
            r"(驗證通過|已驗證|實測通過|確認無誤|檢查過了|"
            r"\bverified\b|\bconfirmed\s+(that|it)|lint\s+pass)",
            re.IGNORECASE,
        ),
        ("test", "check"),
    ),
    (
        "不存在／找不到",
        re.compile(
            r"(找不到任何|查無|並不存在|沒有任何.{0,8}(檔案|定義|實作|引用)|"
            r"there\s+(is|are)\s+no\b|does\s+not\s+exist|no\s+such\s+file|"
            r"couldn'?t\s+find)",
            re.IGNORECASE,
        ),
        ("search",),
    ),
]

CATEGORY_LABEL = {
    "test": "測試類命令",
    "check": "檢查／建置類命令",
    "search": "搜尋類操作",
}


def safe_name(session_id: str) -> str:
    return "".join(c for c in session_id if c.isalnum() or c in "-_") or "unknown"


def load_ledger(session_id: str) -> dict[str, list]:
    path = LEDGER_DIR / f"{safe_name(session_id)}.json"
    try:
        data = json.loads(path.read_text(encoding="UTF-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def read_block_count(session_id: str) -> int:
    try:
        return int((STATE_DIR / f"{safe_name(session_id)}.count").read_text(encoding="UTF-8"))
    except (OSError, ValueError):
        return 0


def write_block_count(session_id: str, value: int) -> None:
    try:
        STATE_DIR.mkdir(parents=True, exist_ok=True)
        (STATE_DIR / f"{safe_name(session_id)}.count").write_text(str(value), encoding="UTF-8")
    except OSError:
        pass


def clear_block_count(session_id: str) -> None:
    try:
        (STATE_DIR / f"{safe_name(session_id)}.count").unlink()
    except OSError:
        pass


def unsupported_claims(message: str, ledger: dict[str, list]) -> list[str]:
    """回傳缺乏對應紀錄的宣稱說明。"""
    problems: list[str] = []
    for label, pattern, categories in RULES:
        if not pattern.search(message):
            continue
        if any(ledger.get(category) for category in categories):
            continue
        wanted = "或".join(CATEGORY_LABEL[category] for category in categories)
        problems.append(f"· 訊息裡出現「{label}」的說法，但本 session 沒有任何{wanted}的紀錄。")
    return problems


def allow(event: dict) -> int:
    """Codex Stop 的成功輸出必須是 JSON；Claude 保持無輸出。"""
    if "turn_id" in event:
        print("{}")
    return EXIT_OK


def main() -> int:
    try:
        event = json.loads(sys.stdin.read() or "{}")
    except (json.JSONDecodeError, OSError):
        return EXIT_OK

    if event.get("stop_hook_active") is True:
        return allow(event)

    session_id = str(event.get("session_id", "unknown"))
    message = str(event.get("last_assistant_message") or "")
    if not message:
        return allow(event)

    problems = unsupported_claims(message, load_ledger(session_id))
    if not problems:
        clear_block_count(session_id)
        return allow(event)

    max_blocks = int(os.environ.get("CLAIM_GUARD_MAX_BLOCKS", DEFAULT_MAX_BLOCKS))
    count = read_block_count(session_id) + 1
    write_block_count(session_id, count)
    body = "\n".join(problems)

    if count > max_blocks:
        clear_block_count(session_id)
        print(
            json.dumps(
                {
                    "hookSpecificOutput": {
                        "hookEventName": "Stop",
                        "additionalContext": (
                            f"宣稱證據檢查仍未通過，已達 {max_blocks} 次上限，本次放行。\n"
                            f"{body}\n請確認回覆內容如實反映實際做過的事。"
                        ),
                    }
                },
                ensure_ascii=False,
            )
        )
        return EXIT_OK

    print(
        f"宣稱缺乏證據（第 {count}/{max_blocks} 次）\n\n{body}\n\n"
        "兩條路：實際執行該做的命令再回報，或把話改成如實描述"
        "（例如「未執行」「無法驗證」）。不要只是換句話說繞過這個檢查。",
        file=sys.stderr,
    )
    return EXIT_BLOCK


if __name__ == "__main__":
    sys.exit(main())
