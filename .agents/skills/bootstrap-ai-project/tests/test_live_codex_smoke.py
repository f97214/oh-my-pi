#!/usr/bin/env python3
"""Codex 原生 Skill／自訂 Agent 的 opt-in live smoke tests。

這組測試會使用目前登入的 Codex CLI 與模型額度，因此預設跳過。
執行方式：

    $env:RUN_CODEX_LIVE_TESTS = "1"
    $env:CODEX_CLI = "<codex.exe absolute path>"  # PATH 不可用時才需要
    python -X utf8 -m unittest test_live_codex_smoke.py

具名 Agent 測試另會消耗一個子代理，且受 CLI／帳戶當下的
multi-agent runtime 影響；需再設定 `RUN_CODEX_AGENT_LIVE_TESTS=1`。
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from typing import Any

from test_role_rendering import role_decisions, run_cli


LIVE_ENABLED = os.environ.get("RUN_CODEX_LIVE_TESTS") == "1"
AGENT_LIVE_ENABLED = os.environ.get("RUN_CODEX_AGENT_LIVE_TESTS") == "1"
CODEX_CLI = os.environ.get("CODEX_CLI") or shutil.which("codex")


def install_role_entries(target: Path) -> None:
    decisions = role_decisions(
        ["claude", "codex"],
        {
            "doc-writer": ["skill", "agent"],
            "git-commit": ["skill"],
        },
    )
    code, rendered, stderr = run_cli(
        "python",
        "render-roles",
        {"target": str(target), "decisions": decisions},
    )
    if code != 0:
        raise AssertionError(stderr or rendered)
    request: dict[str, Any] = {
        "target": str(target),
        "operations": rendered["operations"],
    }
    code, planned, stderr = run_cli("python", "plan", request)
    if code != 0:
        raise AssertionError(stderr or planned)
    code, applied, stderr = run_cli(
        "python", "apply", request, confirm=planned["plan_sha256"]
    )
    if code != 0 or not applied["ok"]:
        raise AssertionError(stderr or applied)


@unittest.skipUnless(LIVE_ENABLED, "需設定 RUN_CODEX_LIVE_TESTS=1")
class CodexLiveSmokeTests(unittest.TestCase):
    def setUp(self) -> None:
        if not CODEX_CLI:
            self.skipTest("Codex CLI 不可用")
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.target = Path(self.temporary_directory.name).resolve()
        subprocess.run(
            ["git", "init", "--quiet", str(self.target)],
            check=True,
            capture_output=True,
            timeout=20,
        )
        install_role_entries(self.target)

    def tearDown(self) -> None:
        self.temporary_directory.cleanup()

    def run_codex(self, prompt: str, *, json_events: bool = False) -> subprocess.CompletedProcess[str]:
        project_key = self.target.as_posix().replace('"', '\\"')
        argv = [
            str(CODEX_CLI),
            "exec",
            "--ephemeral",
            "--sandbox",
            "read-only",
            "--disable",
            "hooks",
            "--ignore-rules",
            "-C",
            str(self.target),
            "-c",
            f'projects."{project_key}".trust_level="trusted"',
        ]
        if os.environ.get("CODEX_LIVE_MULTI_AGENT_V2") == "1":
            argv.extend(["--enable", "multi_agent_v2"])
        if json_events:
            argv.append("--json")
        argv.append(prompt)
        return subprocess.run(
            argv,
            capture_output=True,
            text=True,
            encoding="UTF-8",
            timeout=180,
            check=False,
        )

    def test_explicit_doc_writer_skill_is_loaded(self) -> None:
        completed = self.run_codex(
            "$doc-writer 不要執行工具或修改檔案。"
            "只讀取本 Skill 內嵌的角色契約，回覆「輸出與驗證證據」"
            "編號 3 的代碼識別字，不得加其他文字。"
        )
        self.assertEqual(0, completed.returncode, completed.stderr)
        self.assertIn("source_mapping", completed.stdout)

    @unittest.skipUnless(
        AGENT_LIVE_ENABLED, "需另設定 RUN_CODEX_AGENT_LIVE_TESTS=1"
    )
    def test_named_doc_writer_agent_is_actually_spawned(self) -> None:
        completed = self.run_codex(
            "立刻呼叫 spawn_agent 工具，agent_type 必須設為 doc-writer；"
            "不要先搜尋或讀取角色檔案，主代理也不得自行回答。"
            "要求子代理只回覆其角色契約輸出證據的第一個代碼識別字，"
            "等待子代理完成後，最後你也只回覆該識別字。",
            json_events=True,
        )
        self.assertEqual(0, completed.returncode, completed.stderr)
        events = [json.loads(line) for line in completed.stdout.splitlines() if line.strip()]
        serialized = json.dumps(events, ensure_ascii=False)
        if os.environ.get("CODEX_LIVE_DEBUG") == "1":
            print(serialized)
        self.assertIn("status", serialized)
        self.assertIn("doc-writer", serialized)
        self.assertIn('"tool": "spawn_agent"', serialized)


if __name__ == "__main__":
    unittest.main()
