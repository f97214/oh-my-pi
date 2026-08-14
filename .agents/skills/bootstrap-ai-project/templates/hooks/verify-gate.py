#!/usr/bin/env python3
"""Session lifecycle hook：追蹤本次工作變更，收工前驗證，結束時清理。

設定檔 .ai/bootstrap-ai-project/verify-gate.json。命令以陣列形式執行，不經 shell、不用 eval。
判定依退出碼，不猜輸出樣式。標準函式庫，無第三方相依。

本檔自含所有邏輯——hook 會被部署到別的專案，少一個相依就少一個失效點。
"""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="UTF-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="UTF-8")

EXIT_OK = 0
EXIT_BLOCK = 2

DEFAULT_MAX_BLOCKS = 3
DEFAULT_TIMEOUT = 300
OUTPUT_LINES = 20
STATE_DIR = Path(tempfile.gettempdir()) / "bootstrap-ai-project-verify-gate"


def safe_session_id(session_id: str) -> str:
    return "".join(char for char in session_id if char.isalnum() or char in "-_") or "unknown"


def load_event() -> dict:
    try:
        return json.loads(sys.stdin.read() or "{}")
    except (json.JSONDecodeError, OSError):
        return {}


def state_file(session_id: str) -> Path:
    return STATE_DIR / f"{safe_session_id(session_id)}.count"


def checkpoint_file(session_id: str, project_dir: Path) -> Path:
    project_key = hashlib.sha256(str(project_dir.resolve(strict=False)).encode("UTF-8")).hexdigest()[:16]
    return STATE_DIR / f"{safe_session_id(session_id)}-{project_key}.json"


def read_block_count(session_id: str) -> int:
    path = state_file(session_id)
    try:
        return int(path.read_text(encoding="UTF-8").strip())
    except (OSError, ValueError):
        return 0


def write_block_count(session_id: str, value: int) -> None:
    try:
        STATE_DIR.mkdir(parents=True, exist_ok=True)
        state_file(session_id).write_text(str(value), encoding="UTF-8")
    except OSError:
        pass  # 計數失效時寧可放行，不要讓 hook 自己變成故障點


def clear_block_count(session_id: str) -> None:
    try:
        state_file(session_id).unlink()
    except OSError:
        pass


def read_checkpoint(session_id: str, project_dir: Path) -> dict | None:
    try:
        value = json.loads(
            checkpoint_file(session_id, project_dir).read_text(encoding="UTF-8")
        )
    except (OSError, json.JSONDecodeError):
        return None
    expected_root = str(project_dir.resolve(strict=False))
    if (
        not isinstance(value, dict)
        or value.get("schema_version") != 1
        or value.get("project_dir") != expected_root
        or not isinstance(value.get("fingerprint"), str)
        or not isinstance(value.get("paths"), list)
        or not all(isinstance(path, str) for path in value["paths"])
        or (value.get("head") is not None and not isinstance(value.get("head"), str))
    ):
        return None
    return value


def write_checkpoint(session_id: str, project_dir: Path, state: dict) -> None:
    path = checkpoint_file(session_id, project_dir)
    temporary = path.with_suffix(f".{os.getpid()}.tmp")
    value = {
        "schema_version": 1,
        "project_dir": str(project_dir.resolve(strict=False)),
        "head": state["head"],
        "fingerprint": state["fingerprint"],
        "paths": state["paths"],
    }
    try:
        STATE_DIR.mkdir(parents=True, exist_ok=True)
        temporary.write_text(
            json.dumps(value, ensure_ascii=False, sort_keys=True),
            encoding="UTF-8",
        )
        os.replace(temporary, path)
    except OSError:
        try:
            temporary.unlink()
        except OSError:
            pass


def clear_checkpoint(session_id: str, project_dir: Path) -> None:
    try:
        checkpoint_file(session_id, project_dir).unlink()
    except OSError:
        pass


def load_config(project_dir: Path) -> dict | None:
    path = project_dir / ".ai" / "bootstrap-ai-project" / "verify-gate.json"
    if not path.is_file():
        return None
    try:
        config = json.loads(path.read_text(encoding="UTF-8"))
    except (json.JSONDecodeError, OSError):
        return None
    return config if isinstance(config, dict) else None


def git_bytes(project_dir: Path, *arguments: str) -> bytes | None:
    try:
        result = subprocess.run(
            ["git", *arguments],
            cwd=str(project_dir),
            capture_output=True,
            timeout=20,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if result.returncode != 0:
        return None
    return result.stdout


def nul_paths(raw: bytes) -> list[str]:
    return [
        value.replace("\\", "/")
        for value in raw.decode("UTF-8", errors="replace").split("\0")
        if value
    ]


def workspace_state(project_dir: Path) -> dict | None:
    """取得 HEAD、工作區 fingerprint 與未提交路徑；非 Git repo 時回傳 None。"""
    status = git_bytes(
        project_dir,
        "status",
        "--porcelain=v1",
        "-z",
        "--untracked-files=all",
    )
    if status is None:
        return None

    head_raw = git_bytes(project_dir, "rev-parse", "--verify", "HEAD")
    head = (
        head_raw.decode("ASCII", errors="replace").strip()
        if head_raw is not None
        else None
    )
    unstaged = git_bytes(
        project_dir, "diff", "--name-only", "--no-renames", "-z", "--"
    )
    staged = git_bytes(
        project_dir,
        "diff",
        "--cached",
        "--name-only",
        "--no-renames",
        "-z",
        "--",
    )
    untracked = git_bytes(
        project_dir,
        "ls-files",
        "--others",
        "--exclude-standard",
        "-z",
    )
    if unstaged is None or staged is None or untracked is None:
        return None

    diff_arguments = (
        ("diff", "--binary", "HEAD", "--")
        if head
        else ("diff", "--binary", "--cached", "--")
    )
    tracked_diff = git_bytes(project_dir, *diff_arguments)
    working_diff = git_bytes(project_dir, "diff", "--binary", "--")
    if tracked_diff is None or working_diff is None:
        return None

    untracked_paths = nul_paths(untracked)
    fingerprint = hashlib.sha256()
    fingerprint.update((head or "<unborn>").encode("ASCII"))
    fingerprint.update(status)
    fingerprint.update(tracked_diff)
    fingerprint.update(working_diff)
    for relative in sorted(untracked_paths):
        fingerprint.update(relative.encode("UTF-8"))
        try:
            stat = (project_dir / Path(relative)).lstat()
        except OSError:
            return None
        fingerprint.update(f"{stat.st_mode}:{stat.st_size}:{stat.st_mtime_ns}".encode("ASCII"))

    paths = sorted(set(nul_paths(unstaged) + nul_paths(staged) + untracked_paths))
    return {
        "head": head,
        "fingerprint": fingerprint.hexdigest(),
        "paths": paths,
    }


def committed_paths(
    project_dir: Path,
    previous_head: str | None,
    current_head: str | None,
) -> list[str] | None:
    if previous_head == current_head:
        return []
    if current_head is None:
        return None
    if previous_head is None:
        raw = git_bytes(project_dir, "ls-tree", "-r", "--name-only", "-z", current_head)
    else:
        raw = git_bytes(
            project_dir,
            "diff",
            "--name-only",
            "--no-renames",
            "-z",
            previous_head,
            current_head,
            "--",
        )
    return None if raw is None else nul_paths(raw)


def changes_since_checkpoint(
    project_dir: Path,
    checkpoint: dict | None,
    current: dict | None,
) -> list[str] | None:
    if checkpoint is None or current is None:
        return None
    if checkpoint["fingerprint"] == current["fingerprint"]:
        return []
    committed = committed_paths(project_dir, checkpoint.get("head"), current.get("head"))
    if committed is None:
        return None
    return sorted(set(current["paths"]) | set(committed))


def changed_paths(project_dir: Path) -> list[str] | None:
    """相容舊呼叫端：回傳目前未提交路徑；無法判斷時回傳 None。"""
    state = workspace_state(project_dir)
    return None if state is None else state["paths"]


def check_applies(check: dict, changed: list[str] | None) -> bool:
    prefixes = check.get("paths")
    if not prefixes:
        return True
    if changed is None:
        return True  # 無從判斷變更時一律跑，不要靜默跳過檢查
    return any(path.startswith(tuple(prefixes)) for path in changed)


def resolve_command(command: list[str]) -> list[str]:
    """把 python 換成目前的直譯器，避免 PATH 上沒有或版本不同。"""
    if command and command[0] in {"python", "python3"}:
        return [sys.executable, *command[1:]]
    return list(command)


def run_check(check: dict, project_dir: Path) -> tuple[bool, str]:
    command = check.get("command")
    if not isinstance(command, list) or not command:
        return True, ""
    env = {**os.environ, "PYTHONUTF8": "1", "PYTHONIOENCODING": "UTF-8"}
    try:
        result = subprocess.run(
            resolve_command(command),
            cwd=str(project_dir),
            capture_output=True,
            text=True,
            encoding="UTF-8",
            errors="replace",
            timeout=int(check.get("timeout", DEFAULT_TIMEOUT)),
            env=env,
        )
    except subprocess.TimeoutExpired:
        return False, f"逾時（{check.get('timeout', DEFAULT_TIMEOUT)} 秒）"
    except (OSError, subprocess.SubprocessError) as error:
        return False, f"無法執行：{error}"
    if result.returncode == 0:
        return True, ""
    output = (result.stdout + result.stderr).strip().splitlines()
    tail = "\n".join(output[-OUTPUT_LINES:]) if output else "（無輸出）"
    return False, f"退出碼 {result.returncode}\n{tail}"


def emit_context(message: str) -> None:
    """exit 0 時 stderr 只進 debug log，要讓宿主看到必須走 additionalContext。"""
    print(
        json.dumps(
            {
                "hookSpecificOutput": {
                    "hookEventName": "Stop",
                    "additionalContext": message,
                }
            },
            ensure_ascii=False,
        )
    )


def allow(event: dict) -> int:
    """Codex Stop 的成功輸出必須是 JSON；Claude 保持無輸出。"""
    if "turn_id" in event:
        print("{}")
    return EXIT_OK


def main() -> int:
    event = load_event()
    session_id = str(event.get("session_id", "unknown"))
    project_dir = Path(
        os.environ.get("CLAUDE_PROJECT_DIR")
        or os.environ.get("CODEX_PROJECT_DIR")
        or event.get("cwd")
        or Path.cwd()
    ).resolve(strict=False)
    hook_event = str(
        event.get("hook_event_name") or event.get("hookEventName") or "Stop"
    )

    if hook_event == "SessionStart":
        if read_checkpoint(session_id, project_dir) is None:
            initial = workspace_state(project_dir)
            if initial is not None:
                write_checkpoint(session_id, project_dir, initial)
        return allow(event)

    if hook_event == "SessionEnd":
        clear_block_count(session_id)
        clear_checkpoint(session_id, project_dir)
        return allow(event)

    if event.get("stop_hook_active") is True:
        return allow(event)

    config = load_config(project_dir)
    if not config:
        return allow(event)

    checks = config.get("checks")
    if not isinstance(checks, list) or not checks:
        return allow(event)

    checkpoint = read_checkpoint(session_id, project_dir)
    current = workspace_state(project_dir)
    changed = changes_since_checkpoint(project_dir, checkpoint, current)
    if config.get("skip_when_clean", True) and changed == []:
        clear_block_count(session_id)
        if current is not None:
            write_checkpoint(session_id, project_dir, current)
        return allow(event)

    failures: list[str] = []
    for check in checks:
        if not isinstance(check, dict) or not check_applies(check, changed):
            continue
        ok, detail = run_check(check, project_dir)
        if not ok:
            name = check.get("name") or " ".join(check.get("command", []))
            shown = " ".join(check.get("command", []))
            failures.append(f"✗ {name}\n  $ {shown}\n  {detail}")

    if not failures:
        clear_block_count(session_id)
        if current is not None:
            write_checkpoint(session_id, project_dir, current)
        return allow(event)

    max_blocks = int(config.get("max_blocks", DEFAULT_MAX_BLOCKS))
    count = read_block_count(session_id) + 1
    write_block_count(session_id, count)
    body = "\n\n".join(failures)

    if count > max_blocks:
        clear_block_count(session_id)
        emit_context(
            f"驗證閘門仍未通過，但已達 {max_blocks} 次上限，本次放行。\n\n{body}\n\n"
            "請如實告訴使用者哪些驗證沒過，不要宣稱已完成。"
        )
        return EXIT_OK

    print(
        f"驗證閘門擋下收工（第 {count}/{max_blocks} 次）\n\n{body}\n\n"
        "修好再結束。若判斷不必修，明確說明理由——不要靜默略過。",
        file=sys.stderr,
    )
    return EXIT_BLOCK


if __name__ == "__main__":
    sys.exit(main())
