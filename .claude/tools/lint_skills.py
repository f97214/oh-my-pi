#!/usr/bin/env python3
"""Lint every Claude and Codex skill in this repository. Standard library only."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path


EXIT_OK = 0
EXIT_INVALID = 3

NAME_PATTERN = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
LINK_PATTERN = re.compile(r"\[[^\]]*\]\(([^)]+)\)")
TOP_LEVEL_KEY = re.compile(r"^([A-Za-z0-9_.-]+):(.*)$")
FENCE_PATTERN = re.compile(r"^\s*(```|~~~)")

# Claude Code 官方 frontmatter 欄位。
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

# 本 repo 實際使用的擴充欄位：宿主會忽略，但不視為錯誤。
# disallowedTools 由 Spectra CLI 產生（spectra-ask、spectra-discuss），skill 唯讀，只能接受。
EXTRA_FIELDS = {
    "license",
    "compatibility",
    "metadata",
    "disallowedTools",
}

TEXT_SUFFIXES = {".md", ".json", ".py", ".mjs", ".yaml", ".toml"}

# 具備專屬 validator 的 skill：通用檢查之外再跑一次它自己的 profile。
SKILL_PROFILES = {
    "bootstrap-ai-project": "scripts/validate_skill.py",
}


def parse_frontmatter(content: str) -> tuple[dict[str, object], str]:
    """解析 YAML frontmatter 的頂層鍵。巢狀與多行純量只記錄鍵的存在。"""
    if not content.startswith("---\n"):
        raise ValueError("SKILL.md 必須以 YAML frontmatter 開始")
    end = content.find("\n---\n", 4)
    if end < 0:
        raise ValueError("SKILL.md frontmatter 缺少結尾 ---")

    frontmatter: dict[str, object] = {}
    current_key: str | None = None
    for raw_line in content[4:end].splitlines():
        if not raw_line.strip() or raw_line.lstrip().startswith("#"):
            continue
        if raw_line[:1].isspace() or raw_line.lstrip().startswith("- "):
            # 巢狀欄位或多行純量的續行，歸屬於上一個頂層鍵。
            if current_key is None:
                raise ValueError("frontmatter 以縮排行開始，缺少頂層鍵")
            continue
        match = TOP_LEVEL_KEY.match(raw_line)
        if not match:
            raise ValueError(f"無法解析的 frontmatter 行：{raw_line[:40]}")
        key, value = match.group(1), match.group(2).strip()
        if key in frontmatter:
            raise ValueError(f"frontmatter 重複欄位：{key}")
        frontmatter[key] = parse_scalar(value)
        current_key = key
    return frontmatter, content[end + 5 :]


def parse_scalar(value: str) -> object:
    value = value.strip()
    if value in {"true", "false"}:
        return value == "true"
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        return value[1:-1]
    return value


def links_outside_fences(text: str) -> list[str]:
    """擷取 markdown 連結，略過 fenced code block。

    fence 內的路徑是要輸出到下游專案的範例，不是本 repo 的檔案。
    """
    links: list[str] = []
    in_fence = False
    for line in text.splitlines():
        if FENCE_PATTERN.match(line):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        links.extend(LINK_PATTERN.findall(line))
    return links


def is_external(link: str) -> bool:
    return "://" in link or link.startswith(("#", "mailto:"))


def lint_skill(skill_dir: Path) -> list[dict[str, str]]:
    errors: list[dict[str, str]] = []
    skill_file = skill_dir / "SKILL.md"
    if not skill_file.is_file():
        return [{"code": "missing-skill", "message": "找不到 SKILL.md"}]

    try:
        content = skill_file.read_text(encoding="UTF-8")
    except UnicodeDecodeError:
        return [{"code": "encoding", "message": "SKILL.md 不是合法 UTF-8"}]

    try:
        frontmatter, _ = parse_frontmatter(content)
    except ValueError as error:
        return [{"code": "frontmatter", "message": str(error)}]

    unknown = sorted(set(frontmatter) - CLAUDE_FIELDS - EXTRA_FIELDS)
    if unknown:
        errors.append(
            {
                "code": "unknown-frontmatter",
                "message": f"未知 frontmatter 欄位：{', '.join(unknown)}",
            }
        )

    name = frontmatter.get("name")
    if not isinstance(name, str) or name != skill_dir.name or not NAME_PATTERN.fullmatch(name):
        errors.append(
            {
                "code": "name",
                "message": f"name 必須是合法 hyphen-case 且等於目錄名稱 {skill_dir.name}",
            }
        )

    description = frontmatter.get("description")
    if not isinstance(description, str) or not description.strip():
        errors.append({"code": "description", "message": "description 不得為空"})

    for path in sorted(skill_dir.rglob("*")):
        if not path.is_file() or path.suffix.lower() not in TEXT_SUFFIXES:
            continue
        relative = path.relative_to(skill_dir).as_posix()
        try:
            text = path.read_text(encoding="UTF-8")
        except UnicodeDecodeError:
            errors.append({"code": "encoding", "message": f"不是合法 UTF-8：{relative}"})
            continue
        if path.suffix.lower() == ".json":
            try:
                json.loads(text)
            except json.JSONDecodeError:
                errors.append({"code": "invalid-json", "message": f"不是合法 JSON：{relative}"})
            continue
        if path.suffix.lower() != ".md":
            continue
        if relative.startswith("templates/"):
            # templates/ 底下是要輸出到下游專案的成品，連結指向下游檔案而非 skill 內部檔案。
            continue
        for link in links_outside_fences(text):
            if is_external(link):
                continue
            target = link.split("#", 1)[0].strip()
            if not target:
                continue
            if not (path.parent / target).exists():
                errors.append(
                    {
                        "code": "broken-link",
                        "message": f"{relative} 引用不存在的路徑：{target}",
                    }
                )

    profile = (
        SKILL_PROFILES.get(skill_dir.name)
        if ".agents" in skill_dir.parts
        else None
    )
    if profile:
        validator = skill_dir / profile
        if not validator.is_file():
            errors.append({"code": "missing-profile", "message": f"缺少專屬 validator：{profile}"})
        else:
            completed = subprocess.run(
                [sys.executable, str(validator), str(skill_dir)],
                capture_output=True,
                text=True,
                encoding="UTF-8",
            )
            if completed.returncode != EXIT_OK:
                errors.append(
                    {
                        "code": "profile",
                        "message": f"{profile} 回報問題：{completed.stdout.strip()[:400]}",
                    }
                )

    return errors


def lint_all(skills_root: Path) -> dict[str, list[dict[str, str]]]:
    if not skills_root.is_dir():
        raise SystemExit(f"找不到 skill 目錄：{skills_root}")
    return {
        directory.name: lint_skill(directory)
        for directory in sorted(skills_root.iterdir())
        if directory.is_dir()
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Lint 本 repo 的 Claude／Codex skills")
    parser.add_argument(
        "skills_root",
        nargs="?",
        default=None,
        help="單一 skill 目錄；省略時同時檢查 .claude/skills 與 .agents/skills",
    )
    parser.add_argument("--json", action="store_true", help="輸出 JSON 而非人類可讀格式")
    args = parser.parse_args(argv)

    repository = Path(__file__).resolve().parents[2]
    if args.skills_root:
        results = lint_all(Path(args.skills_root).resolve())
    else:
        roots = (
            ("claude", repository / ".claude" / "skills"),
            ("codex", repository / ".agents" / "skills"),
        )
        results = {}
        for host, root in roots:
            for name, errors in lint_all(root).items():
                results[f"{host}/{name}"] = errors
    failed = {name: errors for name, errors in results.items() if errors}

    if args.json:
        print(
            json.dumps(
                {
                    "skills": len(results),
                    "invalid": sorted(failed),
                    "errors": results,
                    "status": "ok" if not failed else "invalid",
                },
                ensure_ascii=False,
                sort_keys=True,
            )
        )
    else:
        for name in sorted(results):
            errors = results[name]
            if not errors:
                print(f"ok      {name}")
                continue
            print(f"INVALID {name}")
            for error in errors:
                print(f"        [{error['code']}] {error['message']}")
        print(f"\n{len(results)} 個 skill，{len(failed)} 個有問題。")

    return EXIT_OK if not failed else EXIT_INVALID


if __name__ == "__main__":
    sys.exit(main())
