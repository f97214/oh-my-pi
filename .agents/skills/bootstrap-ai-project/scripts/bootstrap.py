#!/usr/bin/env python3
"""Deterministic, dependency-free bootstrap-ai-project helper.

The program intentionally keeps its public output small: plans contain hashes and
metadata, never file bodies.  It is designed to be called by the skill, not to
infer product decisions on its own.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
import re
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable


if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="UTF-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="UTF-8")


EXIT_OK, EXIT_BLOCK, EXIT_VALIDATION, EXIT_CONFLICT, EXIT_ARGS, EXIT_INTERNAL = 0, 2, 3, 4, 64, 1
HERE = Path(__file__).resolve().parent
ROOT = HERE.parent


class BootstrapError(Exception):
    def __init__(self, message: str, code: int = EXIT_VALIDATION):
        super().__init__(message)
        self.code = code


def canon(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="UTF-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise BootstrapError("unable to load policy", EXIT_INTERNAL) from exc


POLICY_SOURCE = load_json(ROOT / "policy" / "source-inventory.json")
POLICY_SECRET = load_json(ROOT / "policy" / "secret-rules.json")
POLICY_GITIGNORE = load_json(ROOT / "policy" / "managed-gitignore.json")
POLICY_HOOK = load_json(ROOT / "policy" / "hook-policy.json")
POLICY_TEST = load_json(ROOT / "policy" / "test-bootstrap.json")
POLICY_TEST_OBSERVER = load_json(ROOT / "policy" / "test-observer.json")
ROLE_IDS = ("implementer", "test-engineer", "doc-writer", "git-commit")


def load_role_contracts() -> dict[str, dict[str, Any]]:
    contracts: dict[str, dict[str, Any]] = {}
    required = {
        "schema_version",
        "id",
        "title",
        "description",
        "trigger",
        "capabilities",
        "instructions",
    }
    for role_id in ROLE_IDS:
        contract = load_json(ROOT / "roles" / f"{role_id}.json")
        if not isinstance(contract, dict) or set(contract) != required:
            raise BootstrapError("canonical role contract has invalid fields", EXIT_INTERNAL)
        if contract["schema_version"] != 1 or contract["id"] != role_id:
            raise BootstrapError("canonical role contract identity is invalid", EXIT_INTERNAL)
        if not all(
            isinstance(contract.get(key), str) and contract[key].strip()
            for key in ("title", "description", "trigger", "instructions")
        ):
            raise BootstrapError("canonical role contract text is invalid", EXIT_INTERNAL)
        capabilities = contract.get("capabilities")
        if (
            not isinstance(capabilities, dict)
            or set(capabilities) != {"write", "run_tests", "commit"}
            or not all(isinstance(value, bool) for value in capabilities.values())
        ):
            raise BootstrapError("canonical role capabilities are invalid", EXIT_INTERNAL)
        contracts[role_id] = contract
    return contracts


ROLE_CONTRACTS = load_role_contracts()
POLICY_SHA256 = digest(
    canon(
        {
            "source": POLICY_SOURCE,
            "secret": POLICY_SECRET,
            "gitignore": POLICY_GITIGNORE,
            "hook": POLICY_HOOK,
            "test": POLICY_TEST,
            "test_observer": POLICY_TEST_OBSERVER,
            "roles": ROLE_CONTRACTS,
        }
    ).encode("UTF-8")
)


def target_from(request: dict[str, Any]) -> Path:
    raw = request.get("target")
    if isinstance(raw, dict):
        raw = (
            raw.get("selected_root")
            or raw.get("path")
            or raw.get("repo_root")
            or raw.get("root")
        )
    if not isinstance(raw, str) or not raw.strip():
        raise BootstrapError("request.target is required")
    path = Path(raw).expanduser()
    try:
        resolved = path.resolve(strict=True)
    except OSError as exc:
        raise BootstrapError("target does not exist") from exc
    if not resolved.is_dir() or path.is_symlink():
        raise BootstrapError("target must be a non-symlink directory", EXIT_CONFLICT)
    return resolved


def inside(root: Path, path: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False


def safe_path(root: Path, relative: Any) -> Path:
    if not isinstance(relative, str) or not relative or Path(relative).is_absolute():
        raise BootstrapError("operation path must be a relative non-empty path")
    candidate = (root / relative).resolve(strict=False)
    if not inside(root, candidate):
        raise BootstrapError("operation path escapes target", EXIT_CONFLICT)
    cursor = root
    for part in Path(relative).parts:
        if part in (".", ".."):
            raise BootstrapError("operation path is not normalized", EXIT_CONFLICT)
        cursor = cursor / part
        if cursor.exists() and cursor.is_symlink():
            raise BootstrapError("operation path traverses a symlink", EXIT_CONFLICT)
    return candidate


def is_excluded_file(path: Path) -> bool:
    name = path.name
    if name in POLICY_SOURCE["env_key_only_filenames"]:
        return True
    if name in POLICY_SOURCE["secret_filenames"] or name == ".env" or name.startswith(".env."):
        return True
    return any(name.lower().endswith(s.lower()) for s in POLICY_SOURCE["excluded_suffixes"] + POLICY_SOURCE["private_key_suffixes"])


def is_sensitive_file(path: Path) -> bool:
    """Files which are never read by the scanner, even when explicitly named."""
    name = path.name
    if name in POLICY_SOURCE["env_key_only_filenames"]:
        return False
    return name in POLICY_SOURCE["secret_filenames"] or name == ".env" or name.startswith(".env.") or any(
        name.lower().endswith(s.lower()) for s in POLICY_SOURCE["private_key_suffixes"]
    )


def source_files(root: Path) -> Iterable[Path]:
    excluded = set(POLICY_SOURCE["excluded_directories"])
    maximum = int(POLICY_SOURCE["max_file_bytes"])
    for current, dirs, files in os.walk(root, topdown=True, followlinks=False):
        current_path = Path(current)
        dirs[:] = sorted(d for d in dirs if d not in excluded and not (current_path / d).is_symlink())
        for name in sorted(files):
            path = current_path / name
            try:
                if path.is_symlink() or not path.is_file() or path.stat().st_size > maximum:
                    continue
            except OSError:
                continue
            if is_excluded_file(path):
                continue
            yield path


def git_root(path: Path) -> Path | None:
    for candidate in (path, *path.parents):
        if (candidate / ".git").exists():
            return candidate
    return None


def env_keys(path: Path) -> list[str]:
    keys: list[str] = []
    try:
        for line in path.read_text(encoding="UTF-8", errors="replace").splitlines():
            match = re.match(r"\s*(?:export\s+)?([A-Za-z_][A-Za-z0-9_]*)\s*=", line)
            if match:
                keys.append(match.group(1))
    except OSError:
        pass
    return sorted(set(keys))


def source_manifest(root: Path) -> list[dict[str, Any]]:
    """Describe included and excluded inputs without exposing file contents."""
    excluded_directories = set(POLICY_SOURCE["excluded_directories"])
    excluded_suffixes = tuple(
        suffix.lower() for suffix in POLICY_SOURCE["excluded_suffixes"]
    )
    private_suffixes = tuple(
        suffix.lower() for suffix in POLICY_SOURCE["private_key_suffixes"]
    )
    secret_names = set(POLICY_SOURCE["secret_filenames"])
    env_names = set(POLICY_SOURCE["env_key_only_filenames"])
    maximum = int(POLICY_SOURCE["max_file_bytes"])
    records: list[dict[str, Any]] = []
    for current, dirs, files in os.walk(root, topdown=True, followlinks=False):
        current_path = Path(current)
        retained: list[str] = []
        for name in sorted(dirs):
            path = current_path / name
            relative = path.relative_to(root).as_posix()
            if path.is_symlink():
                records.append(
                    {
                        "path": relative,
                        "kind": "symlink",
                        "included": False,
                        "reason": "symlink",
                    }
                )
            elif name in excluded_directories:
                records.append(
                    {
                        "path": relative,
                        "kind": "directory",
                        "included": False,
                        "reason": "excluded-directory",
                    }
                )
            else:
                retained.append(name)
        dirs[:] = retained
        for name in sorted(files):
            path = current_path / name
            relative = path.relative_to(root).as_posix()
            try:
                stat = path.lstat()
            except OSError:
                records.append(
                    {
                        "path": relative,
                        "kind": "file",
                        "included": False,
                        "reason": "unreadable-metadata",
                    }
                )
                continue
            base = {"path": relative, "kind": "file", "bytes": stat.st_size}
            if path.is_symlink():
                records.append(
                    {
                        **base,
                        "kind": "symlink",
                        "included": False,
                        "reason": "symlink",
                    }
                )
            elif name in env_names:
                records.append(
                    {**base, "included": False, "reason": "env-key-only"}
                )
            elif name in secret_names or name == ".env" or name.startswith(".env."):
                records.append(
                    {**base, "included": False, "reason": "secret-file"}
                )
            elif name.lower().endswith(private_suffixes):
                records.append(
                    {**base, "included": False, "reason": "private-key-file"}
                )
            elif stat.st_size > maximum:
                records.append({**base, "included": False, "reason": "too-large"})
            elif name.lower().endswith(excluded_suffixes):
                records.append(
                    {
                        **base,
                        "included": False,
                        "reason": "binary-or-generated",
                    }
                )
            elif not path.is_file():
                records.append(
                    {**base, "included": False, "reason": "not-regular-file"}
                )
            else:
                try:
                    records.append(
                        {
                            **base,
                            "included": True,
                            "reason": "source",
                            "sha256": digest(path.read_bytes()),
                        }
                    )
                except OSError:
                    records.append(
                        {**base, "included": False, "reason": "unreadable"}
                    )
    return sorted(records, key=lambda item: item["path"])


def snapshot(root: Path) -> str:
    rows = []
    for path in source_files(root):
        try:
            rows.append([path.relative_to(root).as_posix(), digest(path.read_bytes())])
        except OSError:
            continue
    return digest(canon(rows).encode())


def discover(request: dict[str, Any]) -> dict[str, Any]:
    root = target_from(request)
    manifest = source_manifest(root)
    stacks: list[str] = []
    checks = [("dotnet", {"*.sln", "*.csproj"}), ("node", {"package.json"}), ("python", {"pyproject.toml", "requirements.txt", "setup.py"}), ("ruby", {"Gemfile"}), ("go", {"go.mod"}), ("rust", {"Cargo.toml"})]
    all_rel = {p.relative_to(root).as_posix() for p in source_files(root)}
    for stack, hints in checks:
        if any(any(Path(item).match(pattern) for pattern in hints) for item in all_rel):
            stacks.append(stack)
    stacks.sort()
    tests = []
    for stack in stacks:
        framework = POLICY_TEST["frameworks"].get(stack, {}).get("framework")
        if framework:
            tests.append({"stack": stack, "framework": framework, "source": "existing" if any("test" in x.lower() for x in all_rel) else "unavailable"})
    env = []
    for name in POLICY_SOURCE["env_key_only_filenames"]:
        candidate = root / name
        if candidate.is_file() and not candidate.is_symlink():
            env.append({"path": name, "keys": env_keys(candidate)})
    evidence = [{"path": p.relative_to(root).as_posix(), "sha256": digest(p.read_bytes()), "bytes": p.stat().st_size} for p in source_files(root)]
    repo = git_root(root)
    spectra_file = root / ".spectra.yaml"
    spectra = {"present": spectra_file.is_file() and not spectra_file.is_symlink(), "tdd": None, "tdd_status": "absent"}
    if spectra["present"]:
        try:
            tdd_lines = [line for line in spectra_file.read_text(encoding="UTF-8").splitlines() if re.match(r"^\s*tdd\s*:", line)]
            values = [re.match(r"^\s*tdd\s*:\s*(true|false)\s*(?:#.*)?$", line) for line in tdd_lines]
            if len(tdd_lines) == 0:
                spectra["tdd_status"] = "unset"
            elif len(tdd_lines) == 1 and values[0]:
                spectra["tdd"] = values[0].group(1) == "true"
                spectra["tdd_status"] = "enabled" if spectra["tdd"] else "disabled"
            else:
                spectra["tdd_status"] = "invalid"
        except (OSError, UnicodeDecodeError):
            spectra["tdd_status"] = "invalid"
    return {
        "ok": True,
        "target": {"selected_root": str(root), "repo_root": str(repo or root), "kind": "monorepo-target" if repo and repo != root else "single-project", "snapshot_sha256": snapshot(root)},
        "discovery": {"stacks": stacks, "test_profiles": tests, "spectra": spectra, "openspec": {"present": (root / "openspec").exists()}, "environment_examples": env, "evidence": evidence, "source_manifest": manifest},
        "decisions": {
            "mode": "docs-only",
            "hosts": ["claude", "codex"],
            "roles": {role_id: {"surfaces": []} for role_id in ROLE_IDS},
            "git_strategy": "track",
            "spectra_tdd": "skip",
            "dependency_execution": "not-required",
        },
        "derived": {
            "spectra_tdd": {"requested": False, "effective": False},
            "test_profile": {
                "source": "existing"
                if any(item["source"] == "existing" for item in tests)
                else "unavailable"
            },
            "commit_patterns_source": "skill-policy",
            "hosts": ["claude", "codex"],
            "tdd_observability": {
                "requested": False,
                "effective": False,
                "observer_runtime": "unavailable",
                "report_pattern": None,
            },
        },
        "operations": [],
        "results": [],
    }


def quoted(value: str) -> str:
    return json.dumps(value, ensure_ascii=False)


def canonical_role_block(instructions: str) -> str:
    return (
        "<!-- bootstrap-ai-project:canonical-role:start -->\n"
        + instructions.rstrip()
        + "\n<!-- bootstrap-ai-project:canonical-role:end -->\n"
    )


def role_skill_content(contract: dict[str, Any], host: str, marker: str) -> str:
    frontmatter = [
        "---",
        f"name: {contract['id']}",
        f"description: {quoted(contract['description'])}",
    ]
    if host == "claude":
        frontmatter.append("disable-model-invocation: true")
    frontmatter.extend(["---", ""])
    return "\n".join(frontmatter) + f"<!-- {marker} -->\n" + canonical_role_block(contract["instructions"])


def codex_skill_metadata(contract: dict[str, Any], marker: str) -> str:
    role_id = contract["id"]
    return (
        f"# {marker}\n"
        "interface:\n"
        f"  display_name: {quoted(contract['title'])}\n"
        f"  short_description: {quoted(contract['description'])}\n"
        f"  default_prompt: {quoted(f'使用 ${role_id} 執行已明確指定的角色工作流。')}\n\n"
        "policy:\n"
        "  allow_implicit_invocation: false\n"
    )


def claude_agent_content(contract: dict[str, Any], marker: str) -> str:
    return (
        "---\n"
        f"name: {contract['id']}\n"
        f"description: {quoted(contract['description'])}\n"
        "---\n\n"
        f"<!-- {marker} -->\n"
        + canonical_role_block(contract["instructions"])
    )


def codex_agent_content(contract: dict[str, Any], marker: str) -> str:
    instructions = contract["instructions"].rstrip()
    if "'''" in instructions:
        raise BootstrapError("canonical role instructions cannot contain triple apostrophes", EXIT_INTERNAL)
    return (
        f"# {marker}\n"
        f"name = {quoted(contract['id'])}\n"
        f"description = {quoted(contract['description'])}\n"
        "developer_instructions = '''"
        + instructions
        + "\n'''\n"
    )


def render_roles(request: dict[str, Any]) -> dict[str, Any]:
    root = target_from(request)
    decisions = request.get("decisions")
    if not isinstance(decisions, dict):
        raise BootstrapError("request.decisions is required")
    mode = decisions.get("mode")
    if mode not in ("docs-only", "full"):
        raise BootstrapError("decisions.mode must be docs-only or full")
    hosts = decisions.get("hosts")
    if (
        not isinstance(hosts, list)
        or not hosts
        or any(host not in ("claude", "codex") for host in hosts)
        or len(hosts) != len(set(hosts))
    ):
        raise BootstrapError("decisions.hosts must contain unique claude/codex values")
    normalized_hosts = [host for host in ("claude", "codex") if host in hosts]
    roles = decisions.get("roles")
    if not isinstance(roles, dict) or set(roles) != set(ROLE_IDS):
        raise BootstrapError("decisions.roles must define all canonical roles")

    operations: list[dict[str, Any]] = []
    rendered: list[dict[str, str]] = []
    for role_id in ROLE_IDS:
        role_decision = roles[role_id]
        if not isinstance(role_decision, dict) or set(role_decision) != {"surfaces"}:
            raise BootstrapError("each role decision must contain only surfaces")
        surfaces = role_decision["surfaces"]
        if (
            not isinstance(surfaces, list)
            or any(surface not in ("skill", "agent") for surface in surfaces)
            or len(surfaces) != len(set(surfaces))
        ):
            raise BootstrapError("role surfaces must be unique skill/agent values")
        if mode == "docs-only" and surfaces:
            raise BootstrapError("docs-only mode cannot render roles")
        contract = ROLE_CONTRACTS[role_id]
        for surface in ("skill", "agent"):
            if surface not in surfaces:
                continue
            group = f"role:{role_id}:{surface}"
            marker = f"bootstrap-ai-project:{group}:v1"
            for host in normalized_hosts:
                artifacts: list[tuple[str, str, str]] = []
                if surface == "skill" and host == "claude":
                    artifacts.append(("skill", f".claude/skills/{role_id}/SKILL.md", role_skill_content(contract, host, marker)))
                elif surface == "skill" and host == "codex":
                    artifacts.extend(
                        [
                            ("skill", f".agents/skills/{role_id}/SKILL.md", role_skill_content(contract, host, marker)),
                            ("metadata", f".agents/skills/{role_id}/agents/openai.yaml", codex_skill_metadata(contract, marker)),
                        ]
                    )
                elif surface == "agent" and host == "claude":
                    artifacts.append(("agent", f".claude/agents/{role_id}.md", claude_agent_content(contract, marker)))
                elif surface == "agent" and host == "codex":
                    artifacts.append(("agent", f".codex/agents/{role_id}.toml", codex_agent_content(contract, marker)))
                for artifact, path, content in artifacts:
                    operations.append(
                        {
                            "id": f"{group}:{host}:{artifact}",
                            "type": "write",
                            "path": path,
                            "content": content,
                            "atomic_group": group,
                            "managed_marker": marker,
                            "host": host,
                            "role": role_id,
                            "surface": surface,
                            "artifact": artifact,
                        }
                    )
                    rendered.append(
                        {
                            "role": role_id,
                            "surface": surface,
                            "host": host,
                            "artifact": artifact,
                            "path": path,
                            "atomic_group": group,
                        }
                    )
    return {
        "ok": True,
        "target": str(root),
        "hosts": normalized_hosts,
        "roles": rendered,
        "operations": operations,
    }


def compile_rules() -> list[tuple[dict[str, Any], re.Pattern[str]]]:
    result = []
    for rule in POLICY_SECRET["rules"]:
        flags = re.IGNORECASE if "i" in rule.get("flags", "") else 0
        if "m" in rule.get("flags", ""):
            flags |= re.MULTILINE
        result.append((rule, re.compile(rule["pattern"], flags)))
    return result


SECRET_RULES = compile_rules()


def normalized_secret_exceptions(request: dict[str, Any]) -> list[str]:
    raw = request.get("secret_exceptions", request.get("exceptions", []))
    if not isinstance(raw, list) or not all(isinstance(item, str) for item in raw):
        raise BootstrapError("secret_exceptions must be an array of rule ids")
    allowed = {
        rule["id"]
        for rule in POLICY_SECRET["rules"]
        if rule.get("allow_exception") is True
    }
    invalid = sorted(set(raw) - allowed)
    if invalid:
        raise BootstrapError("secret_exceptions contains a forbidden rule id")
    return sorted(set(raw))


def findings_for_text(text: str, label: str, exceptions: set[str]) -> list[dict[str, Any]]:
    findings = []
    for rule, regex in SECRET_RULES:
        for match in regex.finditer(text):
            line = text.count("\n", 0, match.start()) + 1
            permitted = bool(rule.get("allow_exception")) and rule["id"] in exceptions
            findings.append({"path": label, "rule_id": rule["id"], "severity": rule["severity"], "line": line, "blocked": not permitted, "redacted": rule.get("redactor", "[REDACTED]")})
    return findings


def requested_scan_texts(request: dict[str, Any], root: Path) -> list[tuple[str, bytes]]:
    """Return only caller-selected scan input; never inventory the target."""
    entries: list[tuple[str, bytes]] = []
    if "text" in request:
        if not isinstance(request["text"], str):
            raise BootstrapError("request.text must be a string")
        label = request.get("path", "<text>")
        if not isinstance(label, str):
            raise BootstrapError("request.path must be a string")
        entries.append((label, request["text"].encode("UTF-8")))
    if "texts" in request:
        texts = request["texts"]
        if not isinstance(texts, list):
            raise BootstrapError("request.texts must be an array")
        for index, item in enumerate(texts):
            if not isinstance(item, dict) or not isinstance(item.get("path"), str) or not isinstance(item.get("content"), str):
                raise BootstrapError("request.texts entries require path and content strings")
            entries.append((item["path"], item["content"].encode("UTF-8")))
    if "files" in request:
        files = request["files"]
        if not isinstance(files, list) or not all(isinstance(item, str) for item in files):
            raise BootstrapError("request.files must be an array of relative paths")
        for relative in files:
            path = safe_path(root, relative)
            # Explicit selection is not authority to inspect actual credential files.
            if is_sensitive_file(path):
                continue
            try:
                if not path.is_file() or path.is_symlink() or path.stat().st_size > int(POLICY_SOURCE["max_file_bytes"]):
                    continue
                entries.append((path.relative_to(root).as_posix(), path.read_bytes()))
            except OSError:
                continue
    return entries


def scan(request: dict[str, Any], extra: Iterable[tuple[str, bytes]] = (), *, include_request: bool = True) -> tuple[dict[str, Any], int]:
    root = target_from(request)
    exceptions = set(normalized_secret_exceptions(request))
    findings: list[dict[str, Any]] = []
    selected = requested_scan_texts(request, root) if include_request else []
    for label, data in [*selected, *extra]:
        try:
            findings.extend(findings_for_text(data.decode("UTF-8"), label, exceptions))
        except UnicodeDecodeError:
            continue
    findings.sort(key=lambda item: (item["path"], item["line"], item["rule_id"]))
    blocked = any(item["blocked"] for item in findings)
    return {"ok": not blocked, "target": str(root), "findings": findings, "blocked": blocked}, EXIT_BLOCK if blocked else EXIT_OK


def deep_merge(base: Any, patch: Any, *, inside_env: bool = False) -> Any:
    if not isinstance(base, dict) or not isinstance(patch, dict):
        raise BootstrapError("merge_json requires JSON objects")
    result = copy.deepcopy(base)
    for key, incoming in patch.items():
        if key in result and isinstance(result[key], dict) and isinstance(incoming, dict):
            result[key] = deep_merge(result[key], incoming, inside_env=inside_env or key == "env")
        elif key in result and isinstance(result[key], list) and isinstance(incoming, list):
            seen = {canon(x) for x in result[key]}
            result[key].extend(copy.deepcopy(x) for x in incoming if not (canon(x) in seen or seen.add(canon(x))))
        elif inside_env and key in result and not isinstance(result[key], (dict, list)) and not isinstance(incoming, (dict, list)):
            # Existing environment scalar values are user-owned.  merge_json can
            # add missing values but must not silently replace them.
            continue
        else:
            result[key] = copy.deepcopy(incoming)
    return result


def validate_variables(value: Any) -> None:
    if isinstance(value, str):
        for found in re.findall(r"\$\{[^}]*\}", value):
            if found != POLICY_HOOK["allowed_project_variable"]:
                raise BootstrapError("unsupported hook variable")
    elif isinstance(value, list):
        for item in value:
            validate_variables(item)
    elif isinstance(value, dict):
        for item in value.values():
            validate_variables(item)


def validate_hooks(document: Any, relative_path: str | None = None) -> None:
    if not isinstance(document, dict) or "hooks" not in document:
        return
    hooks = document["hooks"]
    if not isinstance(hooks, dict):
        raise BootstrapError("hooks must be an object")
    host = (
        "codex"
        if relative_path == ".codex/hooks.json"
        else "claude"
        if relative_path == ".claude/settings.json"
        else None
    )
    allowed_events = (
        set(POLICY_HOOK["host_events"][host])
        if host
        else set(POLICY_HOOK["matcher_events"])
        | set(POLICY_HOOK["matcher_forbidden_events"])
    )
    forbidden_events = set(POLICY_HOOK["matcher_forbidden_events"])
    allowed_types = set(POLICY_HOOK["allowed_handler_types"])
    for event, groups in hooks.items():
        if event not in allowed_events or not isinstance(groups, list):
            raise BootstrapError("unsupported hook event")
        for group in groups:
            if not isinstance(group, dict):
                raise BootstrapError("invalid hook group")
            matcher = group.get("matcher")
            if matcher is not None and not isinstance(matcher, str):
                raise BootstrapError("hook matcher must be a string")
            if event in forbidden_events and "matcher" in group:
                raise BootstrapError("forbidden hook event cannot have a matcher")
            handlers = group.get("hooks", group.get("handlers"))
            if not isinstance(handlers, list):
                raise BootstrapError("hook group requires handlers")
            for handler in handlers:
                if not isinstance(handler, dict) or handler.get("type") not in allowed_types:
                    raise BootstrapError("unsupported hook handler")
                if handler.get("type") == "command":
                    if not isinstance(handler.get("command"), str):
                        raise BootstrapError("command hook requires command")
                    if relative_path == ".codex/hooks.json":
                        if "args" in handler:
                            raise BootstrapError(
                                "Codex command hooks use one command string, not args"
                            )
                    elif not isinstance(handler.get("args"), list) or not all(
                        isinstance(x, str) for x in handler["args"]
                    ):
                        raise BootstrapError("command hook args must be string array")
                validate_variables(handler)


def validate_test_observer_config(document: Any) -> None:
    required = {
        "schema_version",
        "framework",
        "commands",
        "report_pattern",
        "max_failure_summary_chars",
        "secret_rules",
        "required_report_marker",
        "required_summary_heading",
    }
    if not isinstance(document, dict) or set(document) != required:
        raise BootstrapError("test observer config has unsupported fields")
    if document["schema_version"] != 1:
        raise BootstrapError("unsupported test observer config schema")
    if document["framework"] not in POLICY_TEST_OBSERVER["supported_frameworks"]:
        raise BootstrapError("unsupported test observer framework")
    commands = document["commands"]
    if not isinstance(commands, list) or not commands or len(commands) > 32:
        raise BootstrapError("test observer commands must be a non-empty array")
    seen: set[str] = set()
    forbidden = POLICY_TEST_OBSERVER["command_safety"]["forbidden_fragments"]
    for item in commands:
        if not isinstance(item, dict) or set(item) != {"id", "base"}:
            raise BootstrapError("invalid test observer command")
        ident, base = item["id"], item["base"]
        if (
            not isinstance(ident, str)
            or not re.fullmatch(r"[A-Za-z0-9._-]+", ident)
            or len(ident) > 128
            or ident in seen
            or not isinstance(base, str)
            or not base.strip()
            or len(base) > 4096
            or any(fragment in base for fragment in forbidden)
        ):
            raise BootstrapError("invalid test observer command")
        seen.add(ident)
    if (
        document["report_pattern"] != POLICY_TEST_OBSERVER["report_pattern"]
        or document["required_report_marker"]
        != POLICY_TEST_OBSERVER["required_report_marker"]
        or document["required_summary_heading"]
        != POLICY_TEST_OBSERVER["required_summary_heading"]
    ):
        raise BootstrapError("test observer report contract differs from policy")
    limit = document["max_failure_summary_chars"]
    if not isinstance(limit, int) or isinstance(limit, bool) or not 80 <= limit <= 2000:
        raise BootstrapError("invalid test observer summary limit")
    if document["secret_rules"] != POLICY_SECRET["rules"]:
        raise BootstrapError("test observer secret rules must match skill policy")


def hook_script_references(
    document: Any, relative_path: str | None = None
) -> list[str]:
    references: set[str] = set()
    if not isinstance(document, dict) or not isinstance(document.get("hooks"), dict):
        return []
    prefix = POLICY_HOOK["allowed_project_variable"] + "/"
    for groups in document["hooks"].values():
        if not isinstance(groups, list):
            continue
        for group in groups:
            if not isinstance(group, dict):
                continue
            handlers = group.get("hooks", group.get("handlers", []))
            if not isinstance(handlers, list):
                continue
            for handler in handlers:
                if not isinstance(handler, dict) or handler.get("type") != "command":
                    continue
                if relative_path == ".codex/hooks.json":
                    command = handler.get("command", "")
                    matches = re.findall(
                        r"(?<![A-Za-z0-9_./-])"
                        r"(\.ai/bootstrap-ai-project/[A-Za-z0-9_./-]+"
                        r"\.(?:py|mjs|json))"
                        r"(?![A-Za-z0-9_./-])",
                        command,
                    )
                    if ".ai/bootstrap-ai-project/" in command and not matches:
                        raise BootstrapError(
                            "Codex shared hook paths must be unquoted target-relative paths"
                        )
                    for relative in matches:
                        if ".." in Path(relative).parts:
                            raise BootstrapError(
                                "hook script path is not target-relative"
                            )
                        references.add(relative)
                    continue
                for argument in handler.get("args", []):
                    normalized = argument.replace("\\", "/")
                    is_runtime_file = normalized.lower().endswith(
                        (".ps1", ".sh", ".py", ".mjs")
                    )
                    is_observer_config = (
                        normalized
                        == POLICY_HOOK["allowed_project_variable"]
                        + "/.ai/bootstrap-ai-project/tdd-observer.json"
                    )
                    if not is_runtime_file and not is_observer_config:
                        continue
                    if not normalized.startswith(prefix):
                        raise BootstrapError(
                            "hook script path must use ${CLAUDE_PROJECT_DIR}"
                        )
                    relative = normalized[len(prefix) :]
                    if not relative or relative.startswith("/") or ".." in Path(relative).parts:
                        raise BootstrapError("hook script path is not target-relative")
                    references.add(relative)
    return sorted(references)


def gitignore_content(root: Path, strategy: Any) -> bytes:
    if strategy not in POLICY_GITIGNORE["strategies"]:
        raise BootstrapError("managed_gitignore strategy must be track or ignore")
    path = safe_path(root, ".gitignore")
    if path.exists() and path.is_symlink():
        raise BootstrapError(".gitignore is a symlink", EXIT_CONFLICT)
    current = path.read_text(encoding="UTF-8") if path.exists() else ""
    eol = "\r\n" if "\r\n" in current else "\n"
    start, end = POLICY_GITIGNORE["start_marker"], POLICY_GITIGNORE["end_marker"]
    lines = re.split(r"\r?\n", current) if current else []
    if lines and lines[-1] == "":
        lines.pop()
    starts = [index for index, line in enumerate(lines) if line == start]
    ends = [index for index, line in enumerate(lines) if line == end]
    if (
        (not starts) != (not ends)
        or len(starts) > 1
        or len(ends) > 1
        or (starts and starts[0] > ends[0])
    ):
        raise BootstrapError("managed gitignore markers are malformed", EXIT_CONFLICT)
    block = [start, *POLICY_GITIGNORE["strategies"][strategy], end]
    if not starts:
        result_lines = [*lines, *block]
    else:
        result_lines = [
            *lines[: starts[0]],
            *block,
            *lines[ends[0] + 1 :],
        ]
    return (eol.join(result_lines) + eol).encode("UTF-8")


@dataclass
class Prepared:
    ident: str
    kind: str
    path: Path
    before: bytes | None
    after: bytes
    summary: dict[str, Any]
    atomic_group: str | None
    managed_marker: str | None
    host: str | None


def json_bytes(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode("UTF-8")


def operations_from(request: dict[str, Any]) -> list[Any]:
    ops = request.get("operations")
    if not isinstance(ops, list):
        raise BootstrapError("request.operations must be an array")
    return ops


def validate_hook_scripts(
    root: Path, prepared: list[Prepared], *, check_executable: bool = False
) -> None:
    planned = {item.path: item.after for item in prepared}
    references: set[str] = set()
    for item in prepared:
        if not (item.path.name.endswith(".json") or item.kind == "merge_json"):
            continue
        try:
            document = json.loads(item.after.decode("UTF-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            continue
        references.update(
            hook_script_references(
                document, item.path.relative_to(root).as_posix()
            )
        )
    for relative in sorted(references):
        path = safe_path(root, relative)
        if path in planned:
            data = planned[path]
        elif path.is_file() and not path.is_symlink():
            data = path.read_bytes()
        else:
            raise BootstrapError(f"hook script does not exist: {relative}")
        lower = relative.lower()
        if lower.endswith(".ps1"):
            if not data.startswith(b"\xef\xbb\xbf"):
                raise BootstrapError("PowerShell hook must use UTF-8 BOM")
            try:
                text = data.decode("UTF-8-sig")
            except UnicodeDecodeError as exc:
                raise BootstrapError("PowerShell hook must be valid UTF-8") from exc
            required = POLICY_HOOK["script_validation"]["powershell"][
                "required_tokens"
            ]
            if any(token not in text for token in required):
                raise BootstrapError(
                    "PowerShell hook is missing required encoding prologue"
                )
        elif lower.endswith(".sh"):
            if data.startswith(b"\xef\xbb\xbf") or not data.startswith(b"#!"):
                raise BootstrapError("POSIX hook requires a BOM-less shebang")
            if (
                check_executable
                and os.name != "nt"
                and not os.access(path, os.X_OK)
            ):
                raise BootstrapError("POSIX hook is not executable")
        elif lower.endswith((".py", ".mjs")):
            if data.startswith(b"\xef\xbb\xbf"):
                raise BootstrapError("runtime hook script must not use a UTF-8 BOM")
            try:
                data.decode("UTF-8")
            except UnicodeDecodeError as exc:
                raise BootstrapError("runtime hook script must be valid UTF-8") from exc
        elif lower.endswith(".json"):
            try:
                document = json.loads(data.decode("UTF-8"))
            except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                raise BootstrapError("hook config must be valid UTF-8 JSON") from exc
            if relative.replace("\\", "/") == ".ai/bootstrap-ai-project/tdd-observer.json":
                validate_test_observer_config(document)


def prepare(request: dict[str, Any]) -> tuple[Path, list[Prepared]]:
    root = target_from(request)
    prepared: list[Prepared] = []
    seen: set[Path] = set()
    for index, op in enumerate(operations_from(request)):
        if not isinstance(op, dict):
            raise BootstrapError("operation must be an object")
        kind = op.get("type", op.get("kind"))
        ident = op.get("id", str(index + 1))
        if not isinstance(ident, str) or not ident:
            raise BootstrapError("operation id must be a non-empty string")
        atomic_group = op.get("atomic_group")
        managed_marker = op.get("managed_marker")
        host = op.get("host")
        if atomic_group is not None and (
            not isinstance(atomic_group, str) or not atomic_group
        ):
            raise BootstrapError("atomic_group must be a non-empty string")
        if managed_marker is not None and (
            not isinstance(managed_marker, str) or not managed_marker
        ):
            raise BootstrapError("managed_marker must be a non-empty string")
        if host is not None and host not in ("claude", "codex"):
            raise BootstrapError("operation host must be claude or codex")
        if kind == "managed_gitignore":
            path = safe_path(root, ".gitignore")
            after = gitignore_content(root, op.get("strategy"))
        else:
            path = safe_path(root, op.get("path"))
            if kind == "write":
                if not isinstance(op.get("content"), str):
                    raise BootstrapError("write content must be a string")
                after = op["content"].encode("UTF-8")
            elif kind == "merge_json":
                patch = op.get("patch")
                if not isinstance(patch, dict):
                    raise BootstrapError("merge_json patch must be an object")
                try:
                    base = {} if not path.exists() else json.loads(path.read_text(encoding="UTF-8"))
                except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
                    raise BootstrapError("merge_json target is invalid JSON") from exc
                after = json_bytes(deep_merge(base, patch))
            else:
                raise BootstrapError("unsupported operation type")
        if path in seen:
            raise BootstrapError("multiple operations target the same path", EXIT_CONFLICT)
        if any(path in previous.parents or previous in path.parents for previous in seen):
            raise BootstrapError(
                "operation paths may not overlap as ancestor and descendant",
                EXIT_CONFLICT,
            )
        seen.add(path)
        if path.exists() and path.is_symlink():
            raise BootstrapError("operation target is a symlink", EXIT_CONFLICT)
        before = path.read_bytes() if path.exists() else None
        if path.name.endswith(".json") or kind == "merge_json":
            try:
                document = json.loads(after.decode("UTF-8"))
                relative_path = path.relative_to(root).as_posix()
                validate_hooks(document, relative_path)
                if relative_path == ".ai/bootstrap-ai-project/tdd-observer.json":
                    validate_test_observer_config(document)
            except UnicodeDecodeError as exc:
                raise BootstrapError("JSON output must be UTF-8") from exc
        if kind == "write":
            summary = {
                "bytes": len(after),
                "executable": path.suffix.lower() == ".sh",
                "type": "write",
            }
        elif kind == "managed_gitignore":
            summary = {
                "rules": len(POLICY_GITIGNORE["strategies"][op.get("strategy")]),
                "strategy": op.get("strategy"),
                "type": "managed_gitignore",
            }
        else:
            summary = {
                "bytes": len(after),
                "patch_keys": sorted(op["patch"]),
                "type": "merge_json",
            }
        if atomic_group is not None:
            summary["atomic_group"] = atomic_group
        if host is not None:
            summary["host"] = host
        for metadata_key in ("role", "surface", "artifact"):
            metadata_value = op.get(metadata_key)
            if metadata_value is not None:
                if not isinstance(metadata_value, str) or not metadata_value:
                    raise BootstrapError(
                        f"{metadata_key} must be a non-empty string"
                    )
                summary[metadata_key] = metadata_value
        prepared.append(
            Prepared(
                ident,
                kind,
                path,
                before,
                after,
                summary,
                atomic_group,
                managed_marker,
                host,
            )
        )
    validate_hook_scripts(root, prepared)
    return root, prepared


def plan(request: dict[str, Any]) -> tuple[dict[str, Any], list[Prepared]]:
    root, prepared = prepare(request)
    exceptions = normalized_secret_exceptions(request)
    public: list[dict[str, Any]] = []
    for item in prepared:
        before_hash = digest(item.before) if item.before is not None else None
        after_hash = digest(item.after)
        unmanaged = (
            item.before is not None
            and item.managed_marker is not None
            and item.managed_marker.encode("UTF-8") not in item.before
        )
        action = (
            "conflict"
            if unmanaged
            else (
                "create"
                if item.before is None
                else ("skip" if item.before == item.after else "update")
            )
        )
        operation = {
            "id": item.ident,
            "type": item.kind,
            "path": item.path.relative_to(root).as_posix(),
            "action": action,
            "before_sha256": before_hash,
            "after_sha256": after_hash,
            "preview": item.summary,
        }
        if item.atomic_group is not None:
            operation["atomic_group"] = item.atomic_group
        if item.host is not None:
            operation["host"] = item.host
        public.append(operation)
    conflict_groups = {
        item["atomic_group"]
        for item in public
        if item["action"] == "conflict" and "atomic_group" in item
    }
    for item in public:
        if item.get("atomic_group") in conflict_groups:
            item["action"] = "conflict"
    plan_payload = {
        "schema_version": 2,
        "target": str(root),
        "operations": public,
        "secret_exceptions": exceptions,
        "policy_sha256": POLICY_SHA256,
    }
    return {
        "ok": True,
        "target": str(root),
        "operations": public,
        "policy_sha256": POLICY_SHA256,
        "plan_sha256": digest(canon(plan_payload).encode("UTF-8")),
    }, prepared


def atomic_write(root: Path, path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    checked = safe_path(root, path.relative_to(root).as_posix())
    if checked != path or not inside(root, path.parent.resolve(strict=True)):
        raise BootstrapError("write path changed or escaped target", EXIT_CONFLICT)
    fd, temporary = tempfile.mkstemp(prefix=".bootstrap-", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as out:
            out.write(data)
            out.flush()
            os.fsync(out.fileno())
        os.replace(temporary, path)
    except Exception:
        try:
            os.unlink(temporary)
        except OSError:
            pass
        raise


def apply(request: dict[str, Any], confirmation: str | None) -> tuple[dict[str, Any], int]:
    report, prepared = plan(request)
    root = target_from(request)
    if not isinstance(confirmation, str) or confirmation != report["plan_sha256"]:
        raise BootstrapError("confirmation does not match current plan", EXIT_CONFLICT)
    actions = {item["id"]: item["action"] for item in report["operations"]}
    writable = [
        item for item in prepared if actions[item.ident] in ("create", "update")
    ]
    scan_report, scan_code = scan(
        request,
        ((p.path.relative_to(root).as_posix(), p.after) for p in writable),
        include_request=False,
    )
    if scan_code == EXIT_BLOCK:
        return {
            "ok": False,
            "target": report["target"],
            "plan_sha256": report["plan_sha256"],
            "policy_sha256": report["policy_sha256"],
            "findings": scan_report["findings"],
            "blocked": True,
            "results": [],
        }, EXIT_BLOCK
    for item in writable:
        actual = item.path.read_bytes() if item.path.exists() else None
        if actual != item.before:
            raise BootstrapError("file changed after planning", EXIT_CONFLICT)
    created_directories: set[Path] = set()
    for item in writable:
        cursor = item.path.parent
        while cursor != root and not cursor.exists():
            created_directories.add(cursor)
            cursor = cursor.parent
    written: list[Prepared] = []
    try:
        for item in writable:
            atomic_write(root, item.path, item.after)
            if os.name != "nt" and item.path.suffix.lower() == ".sh":
                item.path.chmod(item.path.stat().st_mode | 0o111)
            written.append(item)
    except Exception as exc:
        rollback = []
        for item in reversed(written):
            try:
                if item.path.exists() and item.path.read_bytes() == item.after:
                    if item.before is None:
                        item.path.unlink()
                    else:
                        atomic_write(root, item.path, item.before)
                    rollback.append(item.ident)
            except OSError:
                pass
        removed_directories = []
        for directory in sorted(
            created_directories, key=lambda value: len(value.parts), reverse=True
        ):
            try:
                directory.rmdir()
                removed_directories.append(directory.relative_to(root).as_posix())
            except OSError:
                pass
        return {"ok": False, "target": report["target"], "plan_sha256": report["plan_sha256"], "policy_sha256": report["policy_sha256"], "results": [{"operation_id": x, "status": "rolled-back"} for x in rollback], "removed_directories": removed_directories, "error": {"message": "write failed", "code": EXIT_INTERNAL}}, EXIT_INTERNAL
    results = [
        {
            "operation_id": item.ident,
            "status": (
                "needs-input"
                if actions[item.ident] == "conflict"
                else ("skipped" if actions[item.ident] == "skip" else "success")
            ),
        }
        for item in prepared
    ]
    has_conflicts = any(action == "conflict" for action in actions.values())
    return {
        "ok": not has_conflicts,
        "target": report["target"],
        "plan_sha256": report["plan_sha256"],
        "policy_sha256": report["policy_sha256"],
        "results": results,
        "findings": scan_report["findings"],
        "blocked": False,
    }, EXIT_CONFLICT if has_conflicts else EXIT_OK


def verify(request: dict[str, Any]) -> tuple[dict[str, Any], int]:
    report, prepared = plan(request)
    root = target_from(request)
    actions = {item["id"]: item["action"] for item in report["operations"]}
    validate_hook_scripts(root, prepared, check_executable=True)
    results = []
    valid = True
    for item in prepared:
        if actions[item.ident] == "conflict":
            results.append(
                {
                    "operation_id": item.ident,
                    "path": item.path.relative_to(root).as_posix(),
                    "expected_sha256": digest(item.after),
                    "actual_sha256": digest(item.before) if item.before is not None else None,
                    "json_and_hooks_valid": None,
                    "status": "needs-input",
                }
            )
            valid = False
            continue
        actual = item.path.read_bytes() if item.path.exists() else None
        matches = actual == item.after
        structure_ok = True
        if actual is not None and (item.path.name.endswith(".json") or item.kind == "merge_json"):
            try:
                document = json.loads(actual.decode("UTF-8"))
                relative_path = item.path.relative_to(root).as_posix()
                validate_hooks(document, relative_path)
                if (
                    relative_path == ".ai/bootstrap-ai-project/tdd-observer.json"
                ):
                    validate_test_observer_config(document)
            except (UnicodeDecodeError, json.JSONDecodeError, BootstrapError):
                structure_ok = False
        matches = matches and structure_ok
        results.append({"operation_id": item.ident, "path": item.path.relative_to(root).as_posix(), "expected_sha256": digest(item.after), "actual_sha256": digest(actual) if actual is not None else None, "json_and_hooks_valid": structure_ok if (item.path.name.endswith(".json") or item.kind == "merge_json") else None, "status": "success" if matches else "failed"})
        valid &= matches
    # Verification scans only the just-computed planned bodies; it does not
    # inventory the repository or inspect credentials merely because they exist.
    scan_report, scan_code = scan(request, ((item.path.relative_to(root).as_posix(), item.after) for item in prepared), include_request=False)
    valid &= scan_code != EXIT_BLOCK
    return {
        "ok": bool(valid),
        "target": str(root),
        "results": results,
        "findings": scan_report["findings"],
        "blocked": scan_code == EXIT_BLOCK,
    }, EXIT_OK if valid else (EXIT_BLOCK if scan_code == EXIT_BLOCK else EXIT_CONFLICT)


def read_request(path: str | None) -> dict[str, Any]:
    try:
        raw = Path(path).read_text(encoding="UTF-8") if path else sys.stdin.read()
        value = json.loads(raw)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise BootstrapError("request must be valid JSON", EXIT_VALIDATION) from exc
    if not isinstance(value, dict):
        raise BootstrapError("request must be a JSON object")
    return value


class CliArgumentParser(argparse.ArgumentParser):
    def error(self, message: str) -> None:
        raise BootstrapError("invalid arguments", EXIT_ARGS)


def main(argv: list[str] | None = None) -> int:
    parser = CliArgumentParser(prog="bootstrap.py")
    parser.add_argument(
        "command",
        choices=["discover", "render-roles", "plan", "scan", "apply", "verify"],
    )
    parser.add_argument("--request")
    parser.add_argument("--confirm")
    args: argparse.Namespace | None = None
    try:
        args = parser.parse_args(argv)
        if args.command == "apply" and not args.confirm:
            raise BootstrapError("apply requires --confirm", EXIT_ARGS)
        request = read_request(args.request)
        if args.command == "discover":
            output, code = discover(request), EXIT_OK
        elif args.command == "render-roles":
            output, code = render_roles(request), EXIT_OK
        elif args.command == "scan":
            output, code = scan(request)
        elif args.command == "plan":
            output, _ = plan(request)
            code = EXIT_OK
        elif args.command == "apply":
            output, code = apply(request, args.confirm)
        else:
            output, code = verify(request)
    except BootstrapError as exc:
        output, code = {"ok": False, "error": {"message": str(exc), "code": exc.code}}, exc.code
    except Exception:
        output, code = {"ok": False, "error": {"message": "internal error", "code": EXIT_INTERNAL}}, EXIT_INTERNAL
    command = args.command if args is not None else None
    output = {"schema_version": 2, "ok": bool(output.get("ok")), "command": command, **output}
    sys.stdout.write(canon(output) + "\n")
    return code


if __name__ == "__main__":
    raise SystemExit(main())
