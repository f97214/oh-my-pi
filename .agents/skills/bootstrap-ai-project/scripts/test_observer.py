#!/usr/bin/env python3
"""A deliberately passive TDD observer for Claude Code hooks.

The program only interprets the JSON supplied by a hook.  In particular, it
does not invoke a shell, Spectra, or a test runner.  The small state file is
kept in the OS temporary directory so a project checkout is never modified.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import tempfile
from pathlib import Path
from typing import Any


SLUG = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")
KEY = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")
SUPPORTED_FRAMEWORKS = {"vitest", "jest", "pytest", "xunit", "go", "rspec", "cargo"}
REPORT_PATTERN = "openspec/changes/{change_name}/test-evidence.md"
REPORT_MARKER = "<!-- bootstrap-ai-project:tdd-evidence -->"
SUMMARY_HEADING = "## TDD 測試摘要"
CASE_NAME_LIMIT = 300
TASK_STATUSES = ("proven", "tested-not-proven", "failed", "incomplete")
UNRESOLVED_PLACEHOLDER = re.compile(
    r"<[A-Za-z][A-Za-z0-9 /_.:-]{0,100}>|"
    r"\{\{[^}\r\n]{1,100}\}\}|"
    r"\$\{[^}\r\n]{1,100}\}"
)
MANDATORY_SECRET_PATTERNS = (
    re.compile(
        r"-----BEGIN (?:RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----[\s\S]*?"
        r"(?:-----END (?:RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----|$)",
        re.I,
    ),
    re.compile(r"\b(?:AKIA|ASIA)[A-Z0-9]{16}\b"),
    re.compile(r"\b(?:ghp|gho|ghu|ghs|ghr)_[A-Za-z0-9]{36,255}\b"),
    re.compile(r"\beyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\b"),
    re.compile(
        r"^\s*(?:api[_-]?key|secret|token|password|passwd)\s*[:=]\s*[\"']?([^\s\"'#]{12,})",
        re.I | re.M,
    ),
)
FORBIDDEN_SHELL = re.compile(
    r"[;&|><()]|[\r\n]|`|\$|[*?#{}!]|(?:%[A-Za-z_][A-Za-z0-9_]*%)"
)


class ObserverError(Exception):
    pass


def compact(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def object_from_stdin() -> dict[str, Any]:
    try:
        value = json.loads(sys.stdin.read())
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise ObserverError("invalid hook JSON") from exc
    if not isinstance(value, dict):
        raise ObserverError("hook JSON must be an object")
    return value


def config_from(path: str) -> dict[str, Any]:
    try:
        value = json.loads(Path(path).read_text(encoding="UTF-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ObserverError("invalid observer config") from exc
    required = (
        "schema_version", "framework", "commands", "report_pattern",
        "max_failure_summary_chars", "secret_rules", "required_report_marker",
        "required_summary_heading",
    )
    if (
        not isinstance(value, dict)
        or set(value) != set(required)
        or value.get("schema_version") != 1
    ):
        raise ObserverError("unsupported observer config")
    if value["framework"] not in SUPPORTED_FRAMEWORKS:
        raise ObserverError("incomplete observer config")
    if not isinstance(value["commands"], list) or not value["commands"]:
        raise ObserverError("invalid command allowlist")
    if (
        not isinstance(value["max_failure_summary_chars"], int)
        or isinstance(value["max_failure_summary_chars"], bool)
        or not 80 <= value["max_failure_summary_chars"] <= 2000
    ):
        raise ObserverError("invalid summary limit")
    if (
        value["report_pattern"] != REPORT_PATTERN
        or value["required_report_marker"] != REPORT_MARKER
        or value["required_summary_heading"] != SUMMARY_HEADING
    ):
        raise ObserverError("invalid observer config")
    seen: set[str] = set()
    for item in value["commands"]:
        if (
            not isinstance(item, dict)
            or set(item) != {"id", "base"}
            or not isinstance(item.get("id"), str)
            or not KEY.fullmatch(item["id"])
            or item["id"] in seen
        ):
            raise ObserverError("invalid command allowlist")
        if not isinstance(item.get("base"), str) or not safe_tokens(item["base"]):
            raise ObserverError("invalid command allowlist")
        seen.add(item["id"])
    compile_secret_rules(value["secret_rules"])
    return value


def compile_secret_rules(raw: Any) -> list[re.Pattern[str]]:
    if isinstance(raw, dict):
        raw = raw.get("rules", [])
    if not isinstance(raw, list):
        raise ObserverError("invalid secret rules")
    patterns: list[re.Pattern[str]] = list(MANDATORY_SECRET_PATTERNS)
    for rule in raw:
        if isinstance(rule, dict) and isinstance(rule.get("id"), str) and isinstance(rule.get("pattern"), str):
            pattern, flags_text = rule["pattern"], rule.get("flags", "")
            if not isinstance(flags_text, str):
                raise ObserverError("invalid secret rules")
        else:
            raise ObserverError("invalid secret rules")
        flags = (re.IGNORECASE if "i" in flags_text else 0) | (re.MULTILINE if "m" in flags_text else 0)
        try:
            patterns.append(re.compile(pattern, flags))
        except re.error as exc:
            raise ObserverError("invalid secret rules") from exc
    return patterns


def redact(text: str, rules: list[re.Pattern[str]]) -> tuple[str, bool]:
    changed = False
    for rule in rules:
        text, count = rule.subn("[REDACTED]", text)
        changed = changed or count > 0
    return text, changed


def redact_value(value: Any, rules: list[re.Pattern[str]]) -> tuple[Any, bool]:
    """Redact every string that can leave this process or reach state."""
    if isinstance(value, str):
        return redact(value, rules)
    if isinstance(value, list):
        changed = False
        result = []
        for item in value:
            clean, did_change = redact_value(item, rules)
            result.append(clean)
            changed = changed or did_change
        return result, changed
    if isinstance(value, dict):
        changed = False
        result: dict[str, Any] = {}
        for key, item in value.items():
            clean, did_change = redact_value(item, rules)
            result[key] = clean
            changed = changed or did_change
        return result, changed
    return value, False


def event_name(event: dict[str, Any]) -> str:
    value = event.get(
        "hook_event_name",
        event.get("hookEventName", event.get("event", event.get("name", ""))),
    )
    return value if isinstance(value, str) else ""


def nested(event: dict[str, Any], *names: str) -> Any:
    for name in names:
        if name in event:
            return event[name]
    tool_input = event.get("tool_input")
    if isinstance(tool_input, dict):
        for name in names:
            if name in tool_input:
                return tool_input[name]
    return None


def safe_tokens(command: str) -> list[str] | None:
    if not command or len(command) > 4096 or FORBIDDEN_SHELL.search(command):
        return None
    tokens: list[str] = []
    token = ""
    quote: str | None = None
    escaped = False
    for char in command.strip():
        if escaped:
            token += char
            escaped = False
            continue
        if char == "\\" and quote != "'":
            # In Bash double quotes, backslash is literal unless it escapes a
            # shell-sensitive character.  This preserves quoted Windows paths.
            if quote == '"':
                token += char
            else:
                escaped = True
            continue
        if char in {"'", '"'}:
            if quote is None:
                quote = char
            elif quote == char:
                quote = None
            else:
                token += char
            continue
        if char.isspace() and quote is None:
            if token:
                tokens.append(token)
                token = ""
            continue
        token += char
    if quote is not None or escaped:
        return None
    if token:
        tokens.append(token)
    if not tokens or any(
        not token or any(ord(char) < 32 for char in token) for token in tokens
    ):
        return None
    return tokens


def safe_selector(token: str) -> bool:
    normalized = token.replace("\\", "/")
    if len(token) > 512 or normalized.startswith(("/", "~")):
        return False
    if re.match(r"^[A-Za-z]:/", normalized):
        return False
    return ".." not in normalized.split("/")


def allowed_command(command: Any, config: dict[str, Any]) -> tuple[str, str] | None:
    if not isinstance(command, str):
        return None
    tokens = safe_tokens(command)
    if tokens is None:
        return None
    for item in config["commands"]:
        base = safe_tokens(item["base"])
        assert base is not None
        if tokens[: len(base)] != base:
            continue
        tail = tokens[len(base) :]
        # Selectors remain inert argv-like tokens.  Multiple selectors are
        # useful for runner flags and paths, but an unbounded suffix would turn
        # this observer into a permissive shell parser.
        if len(tail) <= 16 and all(safe_selector(token) for token in tail):
            return item["id"], command.strip()
    return None


def description_phase(value: Any) -> tuple[str, str | None, str | None]:
    if not isinstance(value, str):
        return "unclassified", None, None
    match = re.fullmatch(r"TDD (Red|Green|Refactor): task=([A-Za-z0-9][A-Za-z0-9._-]{0,127}); evidence=([A-Za-z0-9][A-Za-z0-9._-]{0,127})", value)
    if not match:
        return "unclassified", None, None
    return match.group(1).lower(), match.group(2), match.group(3)


def strings_in(value: Any) -> list[str]:
    """Extract only conventional output fields, never arbitrary hook JSON."""
    if isinstance(value, str):
        return [value]
    if not isinstance(value, dict):
        return []
    result: list[str] = []
    for key in ("stdout", "stderr", "output", "message", "error", "tool_error"):
        item = value.get(key)
        if isinstance(item, str):
            result.append(item)
    return result


def output_text(event: dict[str, Any]) -> str:
    values: list[str] = []
    for key in ("tool_response", "tool_result", "response", "error", "tool_error"):
        values.extend(strings_in(event.get(key)))
    # Some hook runtimes place stdout/stderr directly on the event.
    values.extend(strings_in(event))
    return "\n".join(dict.fromkeys(values))


def was_interrupted(event: dict[str, Any]) -> bool:
    if event.get("is_interrupt") is True:
        return True
    for key in ("tool_response", "tool_result", "response"):
        value = event.get(key)
        if isinstance(value, dict) and value.get("interrupted") is True:
            return True
    return False


def post_tool_failed(event: dict[str, Any], output: str) -> bool:
    if event_name(event) == "PostToolUseFailure":
        return True
    containers = [event]
    for key in ("tool_response", "tool_result", "response"):
        value = event.get(key)
        if isinstance(value, dict):
            containers.append(value)
            metadata = value.get("metadata")
            if isinstance(metadata, dict):
                containers.append(metadata)
    for container in containers:
        value = container.get("exit_code", container.get("exitCode"))
        if isinstance(value, int) and not isinstance(value, bool):
            return value != 0
    match = re.search(
        r"\b(?:exit(?:ed)?(?:\s+with)?\s+code|exit_code)\s*[:=]?\s*(-?\d+)\b",
        output,
        re.IGNORECASE,
    )
    return bool(match and int(match.group(1)) != 0)


def count_match(text: str, patterns: list[str]) -> tuple[int | None, int | None, int | None, int | None]:
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE | re.MULTILINE)
        if match:
            values = [int(item) if item is not None else None for item in match.groups()]
            return tuple((values + [None] * 4)[:4])  # passed, failed, skipped, total
    return None, None, None, None


def parse_counts(framework: str, text: str) -> tuple[int | None, int | None, int | None, int | None]:
    patterns = {
        "pytest": [r"(\d+)\s+passed(?:,\s*(\d+)\s+failed)?(?:,\s*(\d+)\s+skipped)?", r"(\d+)\s+passed,\s*(\d+)\s+failed(?:,\s*(\d+)\s+skipped)?"],
        "xunit": [r"Failed:\s*(\d+),\s*Passed:\s*(\d+),\s*Skipped:\s*(\d+),\s*Total:\s*(\d+)"],
        "vitest": [r"Tests\s+(?:(\d+)\s+passed)(?:\s*\|\s*(\d+)\s+failed)?(?:\s*\|\s*(\d+)\s+skipped)?\s*\((\d+)\)", r"Tests\s+(?:(\d+)\s+failed)\s*\|\s*(\d+)\s+passed\s*\((\d+)\)"],
        "jest": [r"Tests:\s*(?:(\d+)\s+passed)(?:,\s*(\d+)\s+failed)?(?:,\s*(\d+)\s+skipped)?(?:,\s*(\d+)\s+total)?"],
        "rspec": [r"(\d+)\s+examples?,\s*(\d+)\s+failures?"],
        "cargo": [r"test result:.*?(\d+)\s+passed;\s*(\d+)\s+failed;\s*(\d+)\s+ignored"],
    }
    key = framework.lower()
    if key in {"vitest", "jest"}:
        summary = re.search(r"^\s*Tests:?\s+(.+)$", text, re.I | re.M)
        if summary:
            line = summary.group(1)
            values: dict[str, int | None] = {}
            for label in ("passed", "failed", "skipped", "total"):
                match = re.search(r"(\d+)\s+" + label + r"\b", line, re.I)
                values[label] = int(match.group(1)) if match else None
            if values["total"] is None:
                total_match = re.search(r"\((\d+)\)", line)
                values["total"] = int(total_match.group(1)) if total_match else None
            if any(values[label] is not None for label in ("passed", "failed", "skipped")):
                return (
                    values["passed"],
                    values["failed"],
                    values["skipped"],
                    values["total"],
                )
    if key == "pytest":
        # pytest can print a failure-only summary (``1 failed in ...``), so
        # do not require the optional passed portion to be present first.
        found: dict[str, int | None] = {}
        for label in ("passed", "failed", "skipped"):
            match = re.search(r"(\d+)\s+" + label + r"\b", text, re.I)
            found[label] = int(match.group(1)) if match else None
        if any(value is not None for value in found.values()):
            total = sum(value for value in found.values() if value is not None)
            return found["passed"], found["failed"], found["skipped"], total
    raw = count_match(text, patterns.get(key, []))
    # xUnit reports failed first; vitest failure-first pattern likewise.
    if key == "xunit" and raw[0] is not None:
        return raw[1], raw[0], raw[2], raw[3]
    if key == "vitest" and raw[0] is not None and re.search(r"Tests\s+\d+\s+failed", text, re.I):
        return raw[1], raw[0], None, raw[2]
    if key == "rspec" and raw[0] is not None:
        return raw[0] - raw[1], raw[1], None, raw[0]
    if key == "cargo" and raw[0] is not None:
        return raw[0], raw[1], raw[2], raw[0] + raw[1] + raw[2]
    if key == "go":
        passed = len(re.findall(r"^--- PASS:", text, re.M))
        failed = len(re.findall(r"^--- FAIL:", text, re.M))
        return (passed or None), (failed or None), None, (passed + failed or None)
    return raw


def parse_cases(framework: str, text: str) -> list[dict[str, str]]:
    cases: list[dict[str, str]] = []
    patterns = [
        (r"^(?:FAILED\s+)([^\s]+)", "failed"),  # pytest
        (r"^--- (PASS|FAIL):\s+(.+?)(?:\s+\(|$)", None),  # go
        (r"^\s*[✓✔]\s+(.+)$", "passed"),
        (r"^\s*[×✕]\s+(.+)$", "failed"),
        (r"^\s*\d+\)\s+(.+)$", "failed"),  # rspec failure listing
    ]
    for line in text.splitlines():
        for pattern, status in patterns:
            match = re.match(pattern, line)
            if not match:
                continue
            if status is None:
                status, name = ("passed" if match.group(1) == "PASS" else "failed"), match.group(2)
            else:
                name = match.group(1)
            name = name.strip()[:CASE_NAME_LIMIT]
            if name:
                cases.append({"name": name, "status": status})
            break
    unique = {(item["name"], item["status"]): item for item in cases}
    return [unique[key] for key in sorted(unique)]


def failure_kind(text: str, status: str) -> str | None:
    if status == "passed":
        return None
    rules = (
        ("compile", r"\b(compil(?:e|ation)|build failed|(?:TS|CS)\d{3,5}|error\s+(?:[A-Z]+\d+|\[E\d+\]))"),
        (
            "infrastructure",
            r"\b(module not found|cannot find module|no module named|"
            r"missing (?:module|dependency|package)|command not found|"
            r"not recognized|dependency|configuration error|invalid config(?:uration)?|"
            r"failed to load config(?:uration)?|permission denied|access denied|"
            r"setup failed|collection error)",
        ),
        ("timeout", r"\b(timeout|timed out|time limit|deadline exceeded)"),
        (
            "assertion",
            r"\b(?:assert(?:ion)?(?:error| failed|[.:])|"
            r"assert\s+.+?(?:==|!=|===|>=|<=)|"
            r"expected .* (?:to|but)|but got|mismatch)",
        ),
    )
    for name, pattern in rules:
        if re.search(pattern, text, re.IGNORECASE):
            return name
    return "unknown" if status in ("failed", "interrupted") else None


def duration(event: dict[str, Any]) -> int | None:
    value = nested(event, "duration_ms", "durationMs")
    return value if isinstance(value, int) and value >= 0 else None


def observation(event: dict[str, Any], config: dict[str, Any], root: Path, rules: list[re.Pattern[str]]) -> dict[str, Any] | None:
    name = event_name(event)
    if name not in ("PostToolUse", "PostToolUseFailure") or nested(event, "tool_name", "toolName") != "Bash":
        return None
    allowed = allowed_command(nested(event, "command"), config)
    if allowed is None:
        return None
    command_id, command = allowed
    phase, task_id, evidence_key = description_phase(nested(event, "description"))
    raw = output_text(event)
    cleaned, was_redacted = redact(raw, rules)
    status = "failed" if post_tool_failed(event, raw) else "passed"
    if was_interrupted(event) or re.search(
        r"\b(interrupted|cancelled|canceled)\b", cleaned, re.IGNORECASE
    ):
        status = "interrupted"
    passed, failed, skipped, total = parse_counts(config["framework"], cleaned)
    if status == "passed" and passed is not None and failed is None:
        failed = 0
    summary: str | None = None
    if status != "passed":
        summary = cleaned.strip()
        limit = config["max_failure_summary_chars"]
        if len(summary) > limit:
            summary = summary[:limit]
    cwd = nested(event, "cwd")
    if not isinstance(cwd, str) or not cwd:
        cwd = str(root)
    result = {
        "schema_version": 1, "kind": "test-observation", "observed": True,
        "event": name, "phase": phase, "task_id": task_id, "evidence_key": evidence_key,
        "framework": config["framework"], "command_id": command_id, "command": command,
        "cwd": cwd, "duration_ms": duration(event), "status": status,
        "failure_kind": failure_kind(cleaned, status),
        "counts": {"passed": passed, "failed": failed, "skipped": skipped, "total": total},
        "cases": parse_cases(config["framework"], cleaned), "failure_summary": summary,
        "redacted": was_redacted, "raw_output_stored": False,
    }
    result, extra_redaction = redact_value(result, rules)
    result["redacted"] = was_redacted or extra_redaction
    return result


def state_path(session_id: Any, root: Path) -> Path | None:
    if not isinstance(session_id, str) or not session_id:
        return None
    material = session_id + "\0" + str(root)
    return Path(tempfile.gettempdir()) / ("bootstrap-ai-project-tdd-observer-" + hashlib.sha256(material.encode("UTF-8")).hexdigest() + ".json")


def load_state(path: Path | None) -> dict[str, Any] | None:
    if path is None or not path.is_file() or path.is_symlink():
        return None
    try:
        value = json.loads(path.read_text(encoding="UTF-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return None
    return value if isinstance(value, dict) and value.get("schema_version") == 1 else None


def save_state(path: Path | None, state: dict[str, Any]) -> None:
    if path is None:
        return
    temporary = path.with_suffix(".tmp")
    try:
        temporary.write_text(compact(state), encoding="UTF-8")
        if os.name != "nt":
            os.chmod(temporary, 0o600)
        os.replace(temporary, path)
    except OSError:
        try:
            temporary.unlink(missing_ok=True)
        except OSError:
            pass


def delete_state(path: Path | None) -> None:
    if path is not None:
        try:
            path.unlink(missing_ok=True)
        except OSError:
            pass


def change_from_apply(command: Any) -> str | None:
    if not isinstance(command, str):
        return None
    tokens = safe_tokens(command)
    if tokens is None or len(tokens) != 6:
        return None
    if tokens[:3] != ["spectra", "instructions", "apply"] or tokens[3] != "--change" or tokens[5] != "--json":
        return None
    return tokens[4] if SLUG.fullmatch(tokens[4]) else None


def prompt_invocation(event: dict[str, Any]) -> tuple[bool, str | None]:
    if event.get("command_name") == "spectra-apply":
        value = event.get("command_args", event.get("arguments"))
        if isinstance(value, list) and len(value) == 1:
            value = value[0]
        return True, value if isinstance(value, str) and SLUG.fullmatch(value) else None
    value = event.get("prompt", event.get("user_prompt", event.get("userPrompt")))
    if not isinstance(value, str):
        return False, None
    match = re.fullmatch(r"\s*[$/]spectra-apply(?:\s+([^\s]+))?\s*", value)
    if not match:
        return False, None
    change = match.group(1)
    return True, change if isinstance(change, str) and SLUG.fullmatch(change) else None


def initial_state(change: str | None) -> dict[str, Any]:
    return {"schema_version": 1, "change": change, "observations": [], "reminder_sent": False}


def state_observation(obs: dict[str, Any]) -> dict[str, Any]:
    # This explicit copy is a guardrail against a future parser accidentally
    # adding raw stdout/stderr fields to durable state.
    return {key: obs[key] for key in obs if key not in {"raw_output", "stdout", "stderr"}}


def context_output(event: str, message: str) -> dict[str, Any]:
    return {
        "hookSpecificOutput": {
            "hookEventName": event,
            "additionalContext": message,
        }
    }


def required_evidence(state: dict[str, Any], root: Path, config: dict[str, Any]) -> list[str]:
    missing: list[str] = []
    change = state.get("change")
    if not isinstance(change, str) or not SLUG.fullmatch(change):
        return ["a valid Spectra change"]
    report = root / "openspec" / "changes" / change / "test-evidence.md"
    try:
        body = report.read_text(encoding="UTF-8")
    except (OSError, UnicodeDecodeError):
        return ["test-evidence.md"]
    if config["required_report_marker"] not in body:
        missing.append("required report marker")
    visible_body = re.sub(r"<!--.*?-->", "", body, flags=re.DOTALL)
    if UNRESOLVED_PLACEHOLDER.search(visible_body):
        missing.append("unresolved report placeholders")
    observations = [
        item for item in state.get("observations", []) if isinstance(item, dict)
    ]
    if observations and "hook-observed" not in body:
        missing.append("hook-observed source")
    for obs in observations:
        if obs.get("phase") == "unclassified" or not isinstance(
            obs.get("evidence_key"), str
        ):
            continue
        evidence_key = obs["evidence_key"]
        if "<!-- evidence:" + evidence_key + " -->" not in body:
            missing.append("evidence:" + evidence_key)
        task_id = obs.get("task_id")
        if isinstance(task_id, str):
            task_line = re.compile(
                r"^.*(?<![A-Za-z0-9._-])"
                + re.escape(task_id)
                + r"(?![A-Za-z0-9._-]).*(?:"
                + "|".join(re.escape(status) for status in TASK_STATUSES)
                + r").*$",
                re.I | re.M,
            )
            if not task_line.search(body):
                missing.append("task:" + task_id)
        command_id = obs.get("command_id")
        command = obs.get("command")
        if (
            isinstance(command_id, str)
            and isinstance(command, str)
        ):
            phase = str(obs.get("phase", "")).capitalize()
            evidence_line = re.compile(
                r"^.*(?<![A-Za-z])"
                + re.escape(phase)
                + r"(?![A-Za-z]).*(?<![A-Za-z0-9._-])"
                + re.escape(str(task_id))
                + r"(?![A-Za-z0-9._-]).*(?<![A-Za-z0-9._-])"
                + re.escape(command_id)
                + r"(?![A-Za-z0-9._-]).*"
                + re.escape(command)
                + r".*hook-observed.*$",
                re.I | re.M,
            )
            if not evidence_line.search(body):
                missing.append("evidence details:" + evidence_key)
        relevant_cases = [
            item
            for item in obs.get("cases", [])
            if isinstance(item, dict)
            and item.get("status") in {"failed", "skipped"}
            and isinstance(item.get("name"), str)
        ]
        if relevant_cases and any(
            item["name"] not in body
            and item["name"].replace("\\", "\\\\").replace("|", "\\|") not in body
            for item in relevant_cases
        ):
            missing.append("failed/skipped cases")
    return missing


def required_terminal_evidence(
    state: dict[str, Any], message: Any, config: dict[str, Any]
) -> list[str]:
    if not isinstance(message, str):
        return ["required summary heading", "task summary details"]
    missing: list[str] = []
    if config["required_summary_heading"] not in message:
        missing.append("required summary heading")
    task_ids = {
        obs["task_id"]
        for obs in state.get("observations", [])
        if isinstance(obs, dict)
        and obs.get("phase") != "unclassified"
        and isinstance(obs.get("task_id"), str)
    }
    if any(task_id not in message for task_id in task_ids) or (
        task_ids and not any(status in message for status in TASK_STATUSES)
    ):
        missing.append("task summary details")
    change = state.get("change")
    if isinstance(change, str):
        report_path = f"openspec/changes/{change}/test-evidence.md"
        if report_path not in message:
            missing.append("report path")
    return missing


def handle(event: dict[str, Any], config: dict[str, Any], root: Path, parse_only: bool) -> dict[str, Any]:
    rules = compile_secret_rules(config["secret_rules"])
    name = event_name(event)
    if parse_only:
        obs = observation(event, config, root, rules)
        return obs if obs is not None else {}
    path = state_path(event.get("session_id"), root)
    if name in ("UserPromptExpansion", "UserPromptSubmit"):
        invoked, change = prompt_invocation(event)
        if invoked:
            save_state(path, initial_state(change))
            return context_output(
                name,
                "TDD observer initialized; apply Spectra instructions before recording test evidence.",
            )
        return {}
    if name == "PreToolUse" and nested(event, "tool_name", "toolName") == "Bash":
        change = change_from_apply(nested(event, "command"))
        if change is not None:
            state = load_state(path) or initial_state(change)
            state["change"] = change
            save_state(path, state)
        return {}
    if name in ("PostToolUse", "PostToolUseFailure"):
        state = load_state(path)
        obs = observation(event, config, root, rules)
        if state is None or obs is None:
            return {}
        observations = state.get("observations")
        if not isinstance(observations, list):
            observations = []
        observations.append(state_observation(obs))
        state["observations"] = observations
        save_state(path, state)
        return context_output(name, "TDD_OBSERVATION " + compact(obs))
    if name == "Stop":
        state = load_state(path)
        if state is None:
            return {}
        missing = required_evidence(state, root, config)
        missing.extend(
            required_terminal_evidence(
                state, event.get("last_assistant_message"), config
            )
        )
        if not missing:
            delete_state(path)
            return {}
        if not state.get("reminder_sent"):
            state["reminder_sent"] = True
            save_state(path, state)
            return context_output(
                name,
                "TDD evidence is incomplete: "
                + ", ".join(sorted(set(missing)))
                + ".",
            )
        delete_state(path)
        return {"systemMessage": "TDD evidence remained incomplete; allowing stop. Missing: " + ", ".join(sorted(set(missing))) + "."}
    if name == "SessionEnd":
        delete_state(path)
    return {}


class ArgumentParser(argparse.ArgumentParser):
    def error(self, message: str) -> None:
        raise ObserverError("invalid arguments")


def main(argv: list[str] | None = None) -> int:
    if hasattr(sys.stdin, "reconfigure"):
        sys.stdin.reconfigure(encoding="UTF-8")
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="UTF-8")
    parser = ArgumentParser(prog="test_observer.py")
    parser.add_argument("--config", required=True)
    parser.add_argument("--project-root", required=True)
    parser.add_argument("--parse-only", action="store_true")
    try:
        args = parser.parse_args(argv)
        root = Path(args.project_root).resolve(strict=False)
        output = handle(object_from_stdin(), config_from(args.config), root, args.parse_only)
    except ObserverError:
        output = {}
    except Exception:
        output = {}
    sys.stdout.write(compact(output) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
