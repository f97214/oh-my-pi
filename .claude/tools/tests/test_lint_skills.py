#!/usr/bin/env python3
"""Tests for the repository-wide skill linter."""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import lint_skills  # noqa: E402


CLEAN_SKILL = """---
name: sample-skill
description: 一個乾淨的範例 skill。
argument-hint: "[題目]"
license: MIT
metadata:
  adaptedFrom: "https://example.invalid/skills"
  sourcePaths:
    - skills/sample/SKILL.md
---

# Sample

細節見 [REFERENCE.md](./REFERENCE.md)。
"""


def codes(errors: list[dict[str, str]]) -> set[str]:
    return {error["code"] for error in errors}


class LintSkillsTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.addCleanup(self._tmp.cleanup)

    def make_skill(self, name: str, skill_md: str, **extra: str) -> Path:
        skill_dir = self.root / name
        skill_dir.mkdir(parents=True)
        (skill_dir / "SKILL.md").write_text(skill_md, encoding="UTF-8")
        for relative, content in extra.items():
            path = skill_dir / relative.replace("__", "/")
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="UTF-8")
        return skill_dir

    def test_clean_skill_passes(self) -> None:
        skill = self.make_skill("sample-skill", CLEAN_SKILL, **{"REFERENCE.md": "# Reference\n"})
        self.assertEqual(lint_skills.lint_skill(skill), [])

    def test_nested_and_multiline_frontmatter_is_accepted(self) -> None:
        """metadata 巢狀與 >- 多行 description 是本 repo 既有寫法，不得誤判。"""
        skill_md = """---
name: folded-skill
description: >-
  這個 description 使用折疊純量，
  跨越多行。
metadata:
  sourceCommit: "abc123"
---

# Folded
"""
        skill = self.make_skill("folded-skill", skill_md)
        self.assertEqual(lint_skills.lint_skill(skill), [])

    def test_broken_link_is_reported(self) -> None:
        skill = self.make_skill("sample-skill", CLEAN_SKILL)
        self.assertIn("broken-link", codes(lint_skills.lint_skill(skill)))

    def test_links_inside_fences_are_ignored(self) -> None:
        """fence 內是要輸出到下游專案的範例路徑，不是 skill 內部連結。"""
        skill_md = CLEAN_SKILL.replace(
            "細節見 [REFERENCE.md](./REFERENCE.md)。",
            "```md\n- [Ordering](./src/ordering/CONTEXT.md) — 範例\n```\n",
        )
        skill = self.make_skill("sample-skill", skill_md)
        self.assertEqual(lint_skills.lint_skill(skill), [])

    def test_links_under_templates_are_ignored(self) -> None:
        """templates/ 是輸出成品，連結指向下游專案的檔案。"""
        skill = self.make_skill(
            "sample-skill",
            CLEAN_SKILL,
            **{
                "REFERENCE.md": "# Reference\n",
                "templates__AGENTS.md": "見 [架構](docs/ARCHITECTURE.md)\n",
            },
        )
        self.assertEqual(lint_skills.lint_skill(skill), [])

    def test_name_must_match_directory(self) -> None:
        skill = self.make_skill(
            "other-name", CLEAN_SKILL, **{"REFERENCE.md": "# Reference\n"}
        )
        self.assertIn("name", codes(lint_skills.lint_skill(skill)))

    def test_missing_frontmatter_is_reported(self) -> None:
        skill = self.make_skill("sample-skill", "# 沒有 frontmatter\n")
        self.assertIn("frontmatter", codes(lint_skills.lint_skill(skill)))

    def test_invalid_json_is_reported(self) -> None:
        skill = self.make_skill(
            "sample-skill",
            CLEAN_SKILL,
            **{"REFERENCE.md": "# Reference\n", "policy__broken.json": "{not json}"},
        )
        self.assertIn("invalid-json", codes(lint_skills.lint_skill(skill)))

    def test_real_repository_skills_are_clean(self) -> None:
        """本 repo 目前所有 skill 都必須通過 lint。"""
        skills_root = Path(__file__).resolve().parents[2] / "skills"
        results = lint_skills.lint_all(skills_root)
        self.assertTrue(results, "找不到任何 skill")
        self.assertEqual({name: errors for name, errors in results.items() if errors}, {})


if __name__ == "__main__":
    unittest.main()
