#!/usr/bin/env python3
"""Validate the canonical cross-host skill without third-party dependencies."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path


EXIT_OK = 0
EXIT_INVALID = 3
NAME_PATTERN = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
LINK_PATTERN = re.compile(r"\[[^\]]+\]\(([^)]+)\)")
BANNED_TERMS = (
    "t" + "f-",
    "sdd-" + "preflight",
    "Track" + " B",
    "軌道" + " B",
    "Test-" + "First TDD",
)
CLAUDE_FIELDS = {
    "name",
    "description",
    "argument-hint",
    "disable-model-invocation",
    "user-invocable",
    "allowed-tools",
    "model",
    "context",
    "agent",
    "hooks",
}
CODEX_FIELDS = {"name", "description"}
REQUIRED_RESOURCES = (
    "policy/test-observer.json",
    "references/tdd-observability.md",
    "schemas/run-config.schema.json",
    "schemas/role-contract.schema.json",
    "schemas/test-observation.schema.json",
    "schemas/test-observer-config.schema.json",
    "scripts/test_observer.py",
    "scripts/test_observer.mjs",
    "templates/rules/testing.md",
    "templates/test-evidence.md",
    "agents/openai.yaml",
    "roles/implementer.json",
    "roles/test-engineer.json",
    "roles/doc-writer.json",
    "roles/git-commit.json",
)
REQUIRED_OBSERVER_EVENTS = {
    "UserPromptExpansion",
    "UserPromptSubmit",
    "PreToolUse",
    "PostToolUse",
    "PostToolUseFailure",
    "Stop",
    "SessionEnd",
}


def parse_scalar(value: str) -> object:
    value = value.strip()
    if value in {"true", "false"}:
        return value == "true"
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        return value[1:-1]
    return value


def parse_frontmatter(content: str) -> tuple[dict[str, object], str]:
    if not content.startswith("---\n"):
        raise ValueError("SKILL.md 必須以 YAML frontmatter 開始")
    end = content.find("\n---\n", 4)
    if end < 0:
        raise ValueError("SKILL.md frontmatter 缺少結尾 ---")
    frontmatter: dict[str, object] = {}
    for index, raw_line in enumerate(content[4:end].splitlines(), start=2):
        if not raw_line.strip() or raw_line.lstrip().startswith("#"):
            continue
        if raw_line[:1].isspace() or ":" not in raw_line:
            raise ValueError(f"第 {index} 行不是本 validator 支援的純量欄位")
        key, value = raw_line.split(":", 1)
        key = key.strip()
        if key in frontmatter:
            raise ValueError(f"frontmatter 重複欄位：{key}")
        frontmatter[key] = parse_scalar(value)
    return frontmatter, content[end + 5 :]


def validate(skill_dir: Path) -> list[dict[str, str]]:
    errors: list[dict[str, str]] = []
    skill_file = skill_dir / "SKILL.md"
    if not skill_file.is_file():
        return [{"code": "missing-skill", "message": "找不到 SKILL.md"}]

    try:
        content = skill_file.read_text(encoding="UTF-8")
    except UnicodeDecodeError:
        return [{"code": "encoding", "message": "SKILL.md 不是合法 UTF-8"}]

    try:
        frontmatter, body = parse_frontmatter(content)
    except ValueError as error:
        return [{"code": "frontmatter", "message": str(error)}]

    canonical = (skill_dir / "agents" / "openai.yaml").is_file()
    allowed_fields = CODEX_FIELDS if canonical else CLAUDE_FIELDS
    unknown = sorted(set(frontmatter) - allowed_fields)
    if unknown:
        errors.append(
            {
                "code": "unknown-frontmatter",
                "message": f"不支援的 frontmatter 欄位：{', '.join(unknown)}",
            }
        )

    name = frontmatter.get("name")
    if name != skill_dir.name or not isinstance(name, str) or not NAME_PATTERN.fullmatch(name):
        errors.append(
            {
                "code": "name",
                "message": "name 必須是合法 hyphen-case 且等於 Skill 目錄名稱",
            }
        )
    description = frontmatter.get("description")
    if not isinstance(description, str) or not description.strip():
        errors.append({"code": "description", "message": "description 不得為空"})
    if canonical:
        metadata = (skill_dir / "agents" / "openai.yaml").read_text(
            encoding="UTF-8"
        )
        if "allow_implicit_invocation: false" not in metadata:
            errors.append(
                {
                    "code": "manual-only",
                    "message": "Codex openai.yaml 必須停用 implicit invocation",
                }
            )
        if "$bootstrap-ai-project" not in metadata:
            errors.append(
                {
                    "code": "default-prompt",
                    "message": "Codex default_prompt 必須提及 $bootstrap-ai-project",
                }
            )
    else:
        if frontmatter.get("argument-hint") != "[target-path]":
            errors.append(
                {
                    "code": "argument-hint",
                    "message": 'argument-hint 必須是 "[target-path]"',
                }
            )
        if frontmatter.get("disable-model-invocation") is not True:
            errors.append(
                {
                    "code": "manual-only",
                    "message": "disable-model-invocation 必須是 true",
                }
            )
        if "$ARGUMENTS" not in body:
            errors.append(
                {
                    "code": "arguments",
                    "message": "Claude 薄入口 body 必須使用 $ARGUMENTS",
                }
            )

    for link in LINK_PATTERN.findall(body):
        if "://" in link or link.startswith("#"):
            continue
        path_text = link.split("#", 1)[0]
        if path_text and not (skill_dir / path_text).is_file():
            errors.append(
                {
                    "code": "broken-link",
                    "message": f"找不到 SKILL.md 引用檔：{path_text}",
                }
            )

    for relative in REQUIRED_RESOURCES:
        if not (skill_dir / relative).is_file():
            errors.append(
                {
                    "code": "missing-resource",
                    "message": f"缺少必要資源：{relative}",
                }
            )

    for path in sorted(skill_dir.rglob("*")):
        if not path.is_file() or path.suffix.lower() not in {".md", ".json", ".py", ".mjs"}:
            continue
        try:
            text = path.read_text(encoding="UTF-8")
        except UnicodeDecodeError:
            errors.append(
                {
                    "code": "encoding",
                    "message": f"不是合法 UTF-8：{path.relative_to(skill_dir)}",
                }
            )
            continue
        for term in BANNED_TERMS:
            if term in text:
                errors.append(
                    {
                        "code": "banned-term",
                        "message": f"{path.relative_to(skill_dir)} 含禁止殘留詞",
                    }
                )
        if path.suffix.lower() == ".json":
            try:
                document = json.loads(text)
            except json.JSONDecodeError:
                errors.append(
                    {
                        "code": "invalid-json",
                        "message": f"不是合法 JSON：{path.relative_to(skill_dir)}",
                    }
                )
                continue
            relative = path.relative_to(skill_dir).as_posix()
            if relative.startswith("policy/") and (
                not isinstance(document, dict)
                or document.get("schema_version") != 1
            ):
                errors.append(
                    {
                        "code": "policy-schema",
                        "message": f"Policy schema_version 必須為 1：{relative}",
                    }
                )
            if relative.startswith("schemas/") and (
                not isinstance(document, dict)
                or not isinstance(document.get("$schema"), str)
                or "type" not in document
            ):
                errors.append(
                    {
                        "code": "json-schema",
                        "message": f"Schema 缺少 $schema 或 type：{relative}",
                    }
                )

    hook_policy_path = skill_dir / "policy" / "hook-policy.json"
    if hook_policy_path.is_file():
        try:
            hook_policy = json.loads(hook_policy_path.read_text(encoding="UTF-8"))
            configured_events = set(hook_policy.get("matcher_events", [])) | set(
                hook_policy.get("matcher_forbidden_events", [])
            )
            missing_events = sorted(REQUIRED_OBSERVER_EVENTS - configured_events)
            if missing_events:
                errors.append(
                    {
                        "code": "observer-events",
                        "message": "Hook policy 缺少 observer events："
                        + ", ".join(missing_events),
                    }
                )
        except (UnicodeDecodeError, json.JSONDecodeError):
            pass

    marker_checks = {
        "templates/rules/testing.md": "bootstrap-ai-project:tdd-observability",
        "templates/test-evidence.md": "bootstrap-ai-project:tdd-evidence",
    }
    for relative, marker in marker_checks.items():
        path = skill_dir / relative
        if path.is_file():
            try:
                marker_present = marker in path.read_text(encoding="UTF-8")
            except UnicodeDecodeError:
                marker_present = False
            if not marker_present:
                errors.append(
                    {
                        "code": "managed-marker",
                        "message": f"缺少受管 marker：{relative}",
                    }
                )

    role_ids = {"implementer", "test-engineer", "doc-writer", "git-commit"}
    for role_id in sorted(role_ids):
        role_path = skill_dir / "roles" / f"{role_id}.json"
        if not role_path.is_file():
            continue
        try:
            contract = json.loads(role_path.read_text(encoding="UTF-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            continue
        if (
            not isinstance(contract, dict)
            or contract.get("schema_version") != 1
            or contract.get("id") != role_id
            or not isinstance(contract.get("instructions"), str)
            or not contract["instructions"].strip()
        ):
            errors.append(
                {
                    "code": "role-contract",
                    "message": f"Canonical role contract 無效：roles/{role_id}.json",
                }
            )

    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "skill_dir",
        nargs="?",
        default=str(Path(__file__).resolve().parents[1]),
    )
    args = parser.parse_args()
    skill_dir = Path(args.skill_dir).resolve()
    errors = validate(skill_dir)
    result = {
        "errors": errors,
        "skill": str(skill_dir),
        "status": "ok" if not errors else "invalid",
    }
    print(json.dumps(result, ensure_ascii=True, sort_keys=True))
    return EXIT_OK if not errors else EXIT_INVALID


if __name__ == "__main__":
    sys.exit(main())
