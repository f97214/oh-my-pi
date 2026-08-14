#!/usr/bin/env python3
"""Claude/Codex role renderer parity and atomic-group tests."""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
import tomllib
import unittest
from pathlib import Path
from typing import Any


SKILL = Path(__file__).resolve().parents[1]
PYTHON_CLI = SKILL / "scripts" / "bootstrap.py"
NODE_CLI = SKILL / "scripts" / "bootstrap.mjs"
ROLE_IDS = ("implementer", "test-engineer", "doc-writer", "git-commit")


def run_cli(
    runtime: str,
    command: str,
    request: dict[str, Any],
    *,
    confirm: str | None = None,
) -> tuple[int, dict[str, Any], str]:
    executable = sys.executable if runtime == "python" else shutil.which("node")
    if not executable:
        raise unittest.SkipTest("Node.js 不可用")
    script = PYTHON_CLI if runtime == "python" else NODE_CLI
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".json", encoding="UTF-8", delete=False
    ) as request_file:
        json.dump(request, request_file, ensure_ascii=False)
        request_path = Path(request_file.name)
    try:
        argv = [str(executable), str(script), command, "--request", str(request_path)]
        if confirm is not None:
            argv.extend(["--confirm", confirm])
        completed = subprocess.run(
            argv,
            capture_output=True,
            text=True,
            encoding="UTF-8",
            timeout=20,
            check=False,
        )
        return completed.returncode, json.loads(completed.stdout), completed.stderr
    finally:
        request_path.unlink(missing_ok=True)


def role_decisions(
    hosts: list[str], selected: dict[str, list[str]], *, mode: str = "full"
) -> dict[str, Any]:
    return {
        "mode": mode,
        "hosts": hosts,
        "roles": {
            role_id: {"surfaces": selected.get(role_id, [])}
            for role_id in ROLE_IDS
        },
    }


def canonical_markdown_body(content: str) -> str:
    start = "<!-- bootstrap-ai-project:canonical-role:start -->\n"
    end = "<!-- bootstrap-ai-project:canonical-role:end -->"
    return content.split(start, 1)[1].split(end, 1)[0]


class RoleRendererTests(unittest.TestCase):
    maxDiff = None

    def render(
        self, runtime: str, target: Path, decisions: dict[str, Any]
    ) -> tuple[int, dict[str, Any], str]:
        return run_cli(
            runtime,
            "render-roles",
            {"target": str(target), "decisions": decisions},
        )

    def test_discover_and_schema_use_run_config_v2_defaults(self) -> None:
        schema = json.loads(
            (SKILL / "schemas" / "run-config.schema.json").read_text(
                encoding="UTF-8"
            )
        )
        self.assertEqual(2, schema["properties"]["schema_version"]["const"])
        self.assertTrue(
            {"hosts", "roles"}.issubset(
                schema["properties"]["decisions"]["required"]
            )
        )
        with tempfile.TemporaryDirectory() as directory:
            outputs = []
            for runtime in ("python", "node"):
                code, output, stderr = run_cli(
                    runtime, "discover", {"target": directory}
                )
                self.assertEqual(0, code, stderr)
                self.assertEqual(2, output["schema_version"])
                self.assertEqual(["claude", "codex"], output["decisions"]["hosts"])
                self.assertEqual(
                    {
                        role_id: {"surfaces": []}
                        for role_id in ROLE_IDS
                    },
                    output["decisions"]["roles"],
                )
                outputs.append(output)
            self.assertEqual(outputs[0], outputs[1])

    def test_target_object_aliases_have_identical_canonical_paths(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            expected = str(Path(directory).resolve())
            for field in ("selected_root", "path", "repo_root", "root"):
                outputs = []
                for runtime in ("python", "node"):
                    code, output, stderr = run_cli(
                        runtime,
                        "discover",
                        {"target": {field: directory}},
                    )
                    self.assertEqual(0, code, stderr)
                    self.assertEqual(expected, output["target"]["selected_root"])
                    self.assertEqual(expected, output["target"]["repo_root"])
                    outputs.append(output)
                self.assertEqual(outputs[0], outputs[1])

    def test_python_node_parity_for_host_and_surface_matrix(self) -> None:
        matrices = [
            role_decisions(["claude"], {"doc-writer": ["skill"]}),
            role_decisions(["codex"], {"doc-writer": ["agent"]}),
            role_decisions(
                ["codex", "claude"],
                {
                    "implementer": ["agent"],
                    "test-engineer": ["skill", "agent"],
                    "doc-writer": ["skill"],
                    "git-commit": ["skill", "agent"],
                },
            ),
            role_decisions(["claude", "codex"], {}),
        ]
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory)
            for decisions in matrices:
                outputs = []
                for runtime in ("python", "node"):
                    code, output, stderr = self.render(runtime, target, decisions)
                    self.assertEqual(0, code, stderr)
                    self.assertEqual(2, output["schema_version"])
                    outputs.append(output)
                self.assertEqual(outputs[0], outputs[1])

    def test_generated_native_entries_embed_canonical_instructions(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory)
            decisions = role_decisions(
                ["claude", "codex"],
                {role_id: ["skill", "agent"] for role_id in ROLE_IDS},
            )
            code, rendered, stderr = self.render("python", target, decisions)
            self.assertEqual(0, code, stderr)
            request = {"target": str(target), "operations": rendered["operations"]}
            code, planned, stderr = run_cli("python", "plan", request)
            self.assertEqual(0, code, stderr)
            code, applied, stderr = run_cli(
                "python", "apply", request, confirm=planned["plan_sha256"]
            )
            self.assertEqual(0, code, stderr)
            self.assertTrue(applied["ok"])

            for role_id in ROLE_IDS:
                contract = json.loads(
                    (SKILL / "roles" / f"{role_id}.json").read_text(encoding="UTF-8")
                )
                canonical = contract["instructions"].rstrip() + "\n"
                markdown_paths = (
                    target / ".agents" / "skills" / role_id / "SKILL.md",
                    target / ".claude" / "skills" / role_id / "SKILL.md",
                    target / ".claude" / "agents" / f"{role_id}.md",
                )
                for path in markdown_paths:
                    body = path.read_text(encoding="UTF-8")
                    self.assertEqual(canonical, canonical_markdown_body(body))
                codex_agent = tomllib.loads(
                    (target / ".codex" / "agents" / f"{role_id}.toml").read_text(
                        encoding="UTF-8"
                    )
                )
                self.assertEqual(
                    {"name", "description", "developer_instructions"},
                    set(codex_agent),
                )
                self.assertEqual(canonical, codex_agent["developer_instructions"])
                codex_skill_yaml = (
                    target
                    / ".agents"
                    / "skills"
                    / role_id
                    / "agents"
                    / "openai.yaml"
                ).read_text(encoding="UTF-8")
                self.assertIn("allow_implicit_invocation: false", codex_skill_yaml)
                self.assertIn(f"${role_id}", codex_skill_yaml)
                claude_skill = (
                    target / ".claude" / "skills" / role_id / "SKILL.md"
                ).read_text(encoding="UTF-8")
                self.assertIn("disable-model-invocation: true", claude_skill)

    def test_custom_file_conflicts_are_atomic_per_role_surface(self) -> None:
        decisions = role_decisions(
            ["claude", "codex"], {"doc-writer": ["skill", "agent"]}
        )
        for runtime in ("python", "node"):
            with self.subTest(runtime=runtime), tempfile.TemporaryDirectory() as directory:
                target = Path(directory)
                custom = target / ".agents" / "skills" / "doc-writer" / "SKILL.md"
                custom.parent.mkdir(parents=True)
                custom.write_text("custom Codex skill\n", encoding="UTF-8")
                code, rendered, stderr = self.render(runtime, target, decisions)
                self.assertEqual(0, code, stderr)
                request = {"target": str(target), "operations": rendered["operations"]}
                code, planned, stderr = run_cli(runtime, "plan", request)
                self.assertEqual(0, code, stderr)
                skill_group = [
                    operation
                    for operation in planned["operations"]
                    if operation.get("atomic_group") == "role:doc-writer:skill"
                ]
                self.assertTrue(skill_group)
                self.assertEqual({"conflict"}, {item["action"] for item in skill_group})
                self.assertEqual(
                    {"doc-writer"},
                    {item["preview"]["role"] for item in skill_group},
                )
                self.assertEqual(
                    {"skill"},
                    {item["preview"]["surface"] for item in skill_group},
                )
                agent_group = [
                    operation
                    for operation in planned["operations"]
                    if operation.get("atomic_group") == "role:doc-writer:agent"
                ]
                self.assertEqual({"create"}, {item["action"] for item in agent_group})

                code, applied, stderr = run_cli(
                    runtime, "apply", request, confirm=planned["plan_sha256"]
                )
                self.assertEqual(4, code, stderr)
                self.assertFalse(applied["ok"])
                self.assertEqual("custom Codex skill\n", custom.read_text(encoding="UTF-8"))
                self.assertFalse(
                    (target / ".claude" / "skills" / "doc-writer" / "SKILL.md").exists()
                )
                self.assertTrue((target / ".claude" / "agents" / "doc-writer.md").exists())
                self.assertTrue((target / ".codex" / "agents" / "doc-writer.toml").exists())

    def test_docs_only_rejects_role_surfaces(self) -> None:
        decisions = role_decisions(
            ["claude", "codex"], {"doc-writer": ["skill"]}, mode="docs-only"
        )
        with tempfile.TemporaryDirectory() as directory:
            for runtime in ("python", "node"):
                code, output, _ = self.render(runtime, Path(directory), decisions)
                self.assertEqual(3, code)
                self.assertFalse(output["ok"])


if __name__ == "__main__":
    unittest.main()
