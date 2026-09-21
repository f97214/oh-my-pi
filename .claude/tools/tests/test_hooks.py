#!/usr/bin/env python3
"""Tests for the shared Claude/Codex governance hooks."""

from __future__ import annotations

import importlib.util
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stderr
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[3]
HOOKS = ROOT / ".ai" / "bootstrap-ai-project" / "hooks"
HOOK_TEMPLATES = (
    ROOT / ".agents" / "skills" / "bootstrap-ai-project" / "templates" / "hooks"
)


def load_hook(name: str):
    """hook 檔名有連字號，不能直接 import。"""
    path = HOOKS / f"{name}.py"
    spec = importlib.util.spec_from_file_location(name.replace("-", "_"), path)
    assert spec and spec.loader, f"無法載入 {path}"
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


verify_gate = load_hook("verify-gate")
claim_ledger = load_hook("claim-ledger")
claim_guard = load_hook("claim-guard")


def run_hook(name: str, payload: dict) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(HOOKS / f"{name}.py")],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        encoding="UTF-8",
        errors="replace",
        timeout=120,
    )


class LedgerClassificationTests(unittest.TestCase):
    def test_test_commands_classified_as_test(self) -> None:
        for command in (
            "python -m pytest tests/",
            "npm test",
            "dotnet test MyProject.csproj",
            "go test ./...",
            "cargo test",
            "python -m unittest discover -s tests",
        ):
            with self.subTest(command=command):
                self.assertEqual(claim_ledger.classify("Bash", command), "test")

    def test_check_commands_are_not_test(self) -> None:
        """git status 不能算成測試——原 kit 的漏洞就在這裡。"""
        for command in ("git status --porcelain", "ruff check .", "node --version"):
            with self.subTest(command=command):
                self.assertEqual(claim_ledger.classify("Bash", command), "check")

    def test_search_commands_and_tools(self) -> None:
        self.assertEqual(claim_ledger.classify("Bash", "rg TODO src/"), "search")
        self.assertEqual(claim_ledger.classify("Grep", ""), "search")
        self.assertEqual(claim_ledger.classify("Glob", ""), "search")

    def test_unrelated_command_is_not_recorded(self) -> None:
        self.assertIsNone(claim_ledger.classify("Bash", "echo hello"))

    def test_ledger_never_blocks(self) -> None:
        result = run_hook("claim-ledger", {"session_id": "t", "tool_name": "Bash"})
        self.assertEqual(result.returncode, 0)

    def test_malformed_input_is_survivable(self) -> None:
        result = subprocess.run(
            [sys.executable, str(HOOKS / "claim-ledger.py")],
            input="not json at all",
            capture_output=True,
            text=True,
            timeout=60,
        )
        self.assertEqual(result.returncode, 0)


class ClaimGuardTests(unittest.TestCase):
    def test_test_claim_needs_test_record(self) -> None:
        problems = claim_guard.unsupported_claims("測試全部通過了", {})
        self.assertTrue(problems)
        self.assertIn("測試", problems[0])

    def test_check_record_does_not_satisfy_test_claim(self) -> None:
        """跑過 git status 不代表跑過測試。"""
        ledger = {"check": [{"command": "git status"}]}
        self.assertTrue(claim_guard.unsupported_claims("測試全部通過", ledger))

    def test_test_record_satisfies_test_claim(self) -> None:
        ledger = {"test": [{"command": "python -m unittest"}]}
        self.assertEqual(claim_guard.unsupported_claims("測試全部通過", ledger), [])

    def test_verified_claim_accepts_check_record(self) -> None:
        ledger = {"check": [{"command": "ruff check ."}]}
        self.assertEqual(claim_guard.unsupported_claims("已驗證，lint pass", ledger), [])

    def test_negative_existence_claim_needs_search(self) -> None:
        self.assertTrue(claim_guard.unsupported_claims("這個函式並不存在", {}))
        self.assertEqual(
            claim_guard.unsupported_claims("這個函式並不存在", {"search": [{"command": "rg foo"}]}),
            [],
        )

    def test_neutral_message_passes(self) -> None:
        self.assertEqual(claim_guard.unsupported_claims("我改好了三個檔案。", {}), [])

    def test_blocks_unsupported_claim_end_to_end(self) -> None:
        # block 計數會跨執行累積，不先清掉的話第二次跑就會因達上限而放行。
        session = "claim-test-block"
        claim_guard.clear_block_count(session)
        self.addCleanup(claim_guard.clear_block_count, session)
        result = run_hook(
            "claim-guard",
            {"session_id": session, "last_assistant_message": "測試全部通過"},
        )
        self.assertEqual(result.returncode, 2)
        self.assertIn("宣稱缺乏證據", result.stderr)

    def test_block_count_reaching_limit_releases(self) -> None:
        """達上限後改為放行並以 additionalContext 告知，避免無限迴圈。"""
        session = "claim-test-limit"
        self.addCleanup(claim_guard.clear_block_count, session)
        payload = {"session_id": session, "last_assistant_message": "測試全部通過"}
        claim_guard.clear_block_count(session)
        codes = [run_hook("claim-guard", payload).returncode for _ in range(4)]
        self.assertEqual(codes[:2], [2, 2], "前兩次應該擋下")
        self.assertEqual(codes[2], 0, "第三次超過上限應放行")
        last = run_hook("claim-guard", payload)
        self.assertEqual(last.returncode, 2, "放行後計數重置，下一輪重新開始擋")

    def test_stop_hook_active_short_circuits(self) -> None:
        result = run_hook(
            "claim-guard",
            {
                "session_id": "x",
                "last_assistant_message": "測試全部通過",
                "stop_hook_active": True,
            },
        )
        self.assertEqual(result.returncode, 0)

    def test_codex_success_emits_valid_stop_json(self) -> None:
        result = run_hook(
            "claim-guard",
            {
                "session_id": "codex-claim-success",
                "turn_id": "turn-1",
                "last_assistant_message": "中性訊息",
            },
        )
        self.assertEqual(result.returncode, 0)
        self.assertEqual({}, json.loads(result.stdout))


class VerifyGateTests(unittest.TestCase):
    def setUp(self) -> None:
        self.state_directory = tempfile.TemporaryDirectory()
        previous = verify_gate.STATE_DIR
        verify_gate.STATE_DIR = Path(self.state_directory.name)
        self.addCleanup(self.state_directory.cleanup)
        self.addCleanup(setattr, verify_gate, "STATE_DIR", previous)
        # main() 的 project_dir 優先讀環境變數，才 fallback 到 event["cwd"]。
        # 這些測試靠 cwd 指向臨時 repo 做隔離，所以必須清掉——否則從 hook
        # 內部跑（Claude Code 會設 CLAUDE_PROJECT_DIR）就會改寫到真實 repo
        # 的 checkpoint，讓閘門擋住自己。
        environment = mock.patch.dict(os.environ, {}, clear=False)
        environment.start()
        self.addCleanup(environment.stop)
        for name in ("CLAUDE_PROJECT_DIR", "CODEX_PROJECT_DIR"):
            os.environ.pop(name, None)

    def git(self, root: Path, *arguments: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            ["git", *arguments],
            cwd=root,
            capture_output=True,
            text=True,
            encoding="UTF-8",
            check=True,
            timeout=20,
        )

    def repository(self) -> Path:
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name).resolve()
        self.git(root, "init", "--quiet")
        self.git(root, "config", "user.name", "Verify Gate Test")
        self.git(root, "config", "user.email", "verify-gate@example.invalid")
        source = root / "src" / "value.txt"
        source.parent.mkdir()
        source.write_text("baseline\n", encoding="UTF-8")
        self.git(root, "add", ".")
        self.git(root, "commit", "--quiet", "-m", "baseline")
        return root

    def run_stop(
        self,
        root: Path,
        session: str,
        result: tuple[bool, str],
    ) -> tuple[int, mock.Mock]:
        config = {
            "schema_version": 1,
            "max_blocks": 3,
            "skip_when_clean": True,
            "checks": [{"name": "test", "command": ["python", "-c", "pass"]}],
        }
        runner = mock.Mock(return_value=result)
        event = {
            "hook_event_name": "Stop",
            "session_id": session,
            "cwd": str(root),
        }
        with (
            mock.patch.object(verify_gate, "load_event", return_value=event),
            mock.patch.object(verify_gate, "load_config", return_value=config),
            mock.patch.object(verify_gate, "run_check", runner),
            redirect_stderr(io.StringIO()),
        ):
            code = verify_gate.main()
        return code, runner

    def test_path_scoping(self) -> None:
        check = {"command": ["x"], "paths": ["src/"]}
        self.assertTrue(verify_gate.check_applies(check, ["src/main.py"]))
        self.assertFalse(verify_gate.check_applies(check, ["docs/readme.md"]))

    def test_unscoped_check_always_applies(self) -> None:
        self.assertTrue(verify_gate.check_applies({"command": ["x"]}, ["anything"]))

    def test_unknown_changes_do_not_skip_checks(self) -> None:
        """無法判斷變更時要跑，不能靜默略過。"""
        self.assertTrue(verify_gate.check_applies({"command": ["x"], "paths": ["src/"]}, None))

    def test_python_resolves_to_current_interpreter(self) -> None:
        self.assertEqual(verify_gate.resolve_command(["python", "a.py"]), [sys.executable, "a.py"])
        self.assertEqual(verify_gate.resolve_command(["node", "a.js"]), ["node", "a.js"])

    def test_run_check_uses_exit_code_not_output_pattern(self) -> None:
        ok, _ = verify_gate.run_check(
            {"command": ["python", "-c", "print('error error error')"]}, ROOT
        )
        self.assertTrue(ok, "退出碼 0 就該通過，不因輸出含 error 而失敗")

        failed, detail = verify_gate.run_check(
            {"command": ["python", "-c", "import sys; sys.exit(3)"]}, ROOT
        )
        self.assertFalse(failed)
        self.assertIn("退出碼 3", detail)

    def test_missing_config_allows_stop(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            self.assertIsNone(verify_gate.load_config(Path(tmp)))

    def test_block_count_round_trip(self) -> None:
        session = "verify-gate-unit-test"
        verify_gate.clear_block_count(session)
        self.assertEqual(verify_gate.read_block_count(session), 0)
        verify_gate.write_block_count(session, 2)
        self.assertEqual(verify_gate.read_block_count(session), 2)
        verify_gate.clear_block_count(session)
        self.assertEqual(verify_gate.read_block_count(session), 0)

    def test_clean_checkpoint_skips_checks(self) -> None:
        root = self.repository()
        session = "verify-clean"
        baseline = verify_gate.workspace_state(root)
        self.assertIsNotNone(baseline)
        verify_gate.write_checkpoint(session, root, baseline)

        code, runner = self.run_stop(root, session, (True, ""))

        self.assertEqual(0, code)
        runner.assert_not_called()

    def test_dirty_change_runs_and_success_advances_checkpoint(self) -> None:
        root = self.repository()
        session = "verify-dirty"
        baseline = verify_gate.workspace_state(root)
        assert baseline is not None
        verify_gate.write_checkpoint(session, root, baseline)
        (root / "src" / "value.txt").write_text("changed\n", encoding="UTF-8")

        code, runner = self.run_stop(root, session, (True, ""))

        self.assertEqual(0, code)
        runner.assert_called_once()
        current = verify_gate.workspace_state(root)
        self.assertEqual(
            current["fingerprint"],
            verify_gate.read_checkpoint(session, root)["fingerprint"],
        )

    def test_failure_does_not_advance_checkpoint(self) -> None:
        root = self.repository()
        session = "verify-failure"
        baseline = verify_gate.workspace_state(root)
        assert baseline is not None
        verify_gate.write_checkpoint(session, root, baseline)
        (root / "src" / "value.txt").write_text("broken\n", encoding="UTF-8")

        code, runner = self.run_stop(root, session, (False, "failed"))

        self.assertEqual(2, code)
        runner.assert_called_once()
        self.assertEqual(
            baseline["fingerprint"],
            verify_gate.read_checkpoint(session, root)["fingerprint"],
        )

    def test_committed_change_is_detected_with_clean_worktree(self) -> None:
        root = self.repository()
        baseline = verify_gate.workspace_state(root)
        assert baseline is not None
        (root / "src" / "value.txt").write_text("committed\n", encoding="UTF-8")
        self.git(root, "add", ".")
        self.git(root, "commit", "--quiet", "-m", "change")
        current = verify_gate.workspace_state(root)
        assert current is not None

        self.assertEqual([], current["paths"])
        self.assertEqual(
            ["src/value.txt"],
            verify_gate.changes_since_checkpoint(root, baseline, current),
        )

    def test_unicode_space_rename_uses_unquoted_paths(self) -> None:
        root = self.repository()
        old = root / "src" / "舊 名稱.txt"
        old.write_text("內容\n", encoding="UTF-8")
        self.git(root, "add", ".")
        self.git(root, "commit", "--quiet", "-m", "add unicode")
        baseline = verify_gate.workspace_state(root)
        assert baseline is not None
        new = root / "src" / "新 名稱.txt"
        old.rename(new)
        self.git(root, "add", "-A")
        current = verify_gate.workspace_state(root)
        assert current is not None

        changed = verify_gate.changes_since_checkpoint(root, baseline, current)

        self.assertIsNotNone(changed)
        self.assertIn("src/舊 名稱.txt", changed)
        self.assertIn("src/新 名稱.txt", changed)
        self.assertTrue(all("\\\"" not in path for path in changed))

    def test_missing_or_corrupt_checkpoint_is_unknown(self) -> None:
        root = self.repository()
        current = verify_gate.workspace_state(root)
        self.assertIsNone(
            verify_gate.changes_since_checkpoint(root, None, current)
        )
        path = verify_gate.checkpoint_file("verify-corrupt", root)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("{broken", encoding="UTF-8")
        self.assertIsNone(verify_gate.read_checkpoint("verify-corrupt", root))

    def test_session_start_is_idempotent_and_session_end_cleans_state(self) -> None:
        root = self.repository()
        session = "verify-lifecycle"
        start = {
            "hook_event_name": "SessionStart",
            "session_id": session,
            "cwd": str(root),
        }
        with mock.patch.object(verify_gate, "load_event", return_value=start):
            self.assertEqual(0, verify_gate.main())
        baseline = verify_gate.read_checkpoint(session, root)
        self.assertIsNotNone(baseline)

        (root / "src" / "value.txt").write_text("after start\n", encoding="UTF-8")
        with mock.patch.object(verify_gate, "load_event", return_value=start):
            self.assertEqual(0, verify_gate.main())
        self.assertEqual(
            baseline["fingerprint"],
            verify_gate.read_checkpoint(session, root)["fingerprint"],
        )

        verify_gate.write_block_count(session, 1)
        end = {
            "hook_event_name": "SessionEnd",
            "session_id": session,
            "cwd": str(root),
        }
        with mock.patch.object(verify_gate, "load_event", return_value=end):
            self.assertEqual(0, verify_gate.main())
        self.assertIsNone(verify_gate.read_checkpoint(session, root))
        self.assertEqual(0, verify_gate.read_block_count(session))

    def test_repo_config_matches_schema_essentials(self) -> None:
        config = verify_gate.load_config(ROOT)
        self.assertIsNotNone(
            config, "本 repo 應該有 .ai/bootstrap-ai-project/verify-gate.json"
        )
        assert config is not None
        self.assertEqual(config["schema_version"], 1)
        for check in config["checks"]:
            with self.subTest(check=check["name"]):
                self.assertIsInstance(check["command"], list)
                self.assertTrue(check["command"])

    def test_stop_hook_active_short_circuits(self) -> None:
        result = run_hook("verify-gate", {"session_id": "x", "stop_hook_active": True})
        self.assertEqual(result.returncode, 0)

    def test_codex_success_emits_valid_stop_json(self) -> None:
        result = run_hook(
            "verify-gate",
            {
                "session_id": "codex-verify-success",
                "turn_id": "turn-1",
                "stop_hook_active": True,
            },
        )
        self.assertEqual(result.returncode, 0)
        self.assertEqual({}, json.loads(result.stdout))


class RegistrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.settings = json.loads(
            (ROOT / ".claude" / "settings.json").read_text(encoding="UTF-8")
        )
        cls.codex_hooks = json.loads(
            (ROOT / ".codex" / "hooks.json").read_text(encoding="UTF-8")
        )

    def test_runtime_matches_canonical_templates(self) -> None:
        for name in ("verify-gate.py", "claim-ledger.py", "claim-guard.py"):
            with self.subTest(script=name):
                self.assertEqual(
                    (HOOK_TEMPLATES / name).read_bytes(),
                    (HOOKS / name).read_bytes(),
                )

    def test_stop_hooks_have_no_matcher(self) -> None:
        """hook-policy.json 把 Stop 列為 matcher_forbidden_events。"""
        for entry in self.settings["hooks"]["Stop"]:
            self.assertNotIn("matcher", entry)

    def test_uses_exec_form_not_shell_string(self) -> None:
        for entries in self.settings["hooks"].values():
            for entry in entries:
                for hook in entry["hooks"]:
                    with self.subTest(command=hook["command"]):
                        self.assertIn("args", hook, "必須用 command + args，不可拼 shell 字串")
                        self.assertNotIn(" ", hook["command"])

    def test_registered_scripts_exist(self) -> None:
        for entries in self.settings["hooks"].values():
            for entry in entries:
                for hook in entry["hooks"]:
                    for arg in hook["args"]:
                        if arg.endswith(".py"):
                            path = ROOT / arg.replace("${CLAUDE_PROJECT_DIR}/", "")
                            with self.subTest(script=arg):
                                self.assertTrue(path.is_file(), f"找不到 {path}")

    def test_codex_stop_hooks_have_no_matcher(self) -> None:
        for entry in self.codex_hooks["hooks"]["Stop"]:
            self.assertNotIn("matcher", entry)

    def test_codex_registration_uses_shared_runtime(self) -> None:
        commands = []
        for entries in self.codex_hooks["hooks"].values():
            for entry in entries:
                for hook in entry["hooks"]:
                    command = hook["command"]
                    commands.append(command)
                    relative = command.split(" ", 1)[1]
                    self.assertTrue((ROOT / relative).is_file(), relative)
        self.assertEqual(5, len(commands))

    def test_verify_gate_tracks_session_lifecycle_on_both_hosts(self) -> None:
        expected = {"SessionStart", "Stop", "SessionEnd"}
        for registration, label in (
            (self.settings, "claude"),
            (self.codex_hooks, "codex"),
        ):
            actual = {
                event
                for event, entries in registration["hooks"].items()
                for entry in entries
                for hook in entry["hooks"]
                if hook["command"].endswith("verify-gate.py")
                or any(
                    str(argument).endswith("verify-gate.py")
                    for argument in hook.get("args", [])
                )
            }
            with self.subTest(host=label):
                self.assertEqual(expected, actual)


if __name__ == "__main__":
    unittest.main()
