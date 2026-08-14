#!/usr/bin/env python3
"""Tests for the docs site generator."""

from __future__ import annotations

import re
import sys
import tempfile
import unittest
from html.parser import HTMLParser
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import build_docs  # noqa: E402


VOID_TAGS = {"br", "hr", "img", "meta", "link", "input", "path", "circle", "rect"}


class StructureChecker(HTMLParser):
    """檢查標籤是否平衡，並收集 id 與錨點。"""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.stack: list[str] = []
        self.ids: set[str] = set()
        self.anchors: set[str] = set()
        self.unbalanced: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        mapping = dict(attrs)
        if mapping.get("id"):
            self.ids.add(str(mapping["id"]))
        href = mapping.get("href") or ""
        if href.startswith("#"):
            self.anchors.add(href[1:])
        if tag not in VOID_TAGS:
            self.stack.append(tag)

    def handle_endtag(self, tag: str) -> None:
        if tag in VOID_TAGS:
            return
        if self.stack and self.stack[-1] == tag:
            self.stack.pop()
        elif tag in self.stack:
            while self.stack and self.stack.pop() != tag:
                self.unbalanced.append(tag)
        else:
            self.unbalanced.append(tag)


class MarkdownRenderTests(unittest.TestCase):
    def render(self, source: str) -> str:
        return build_docs.render_markdown(source)[0]

    def test_headings_get_ids(self) -> None:
        html, headings = build_docs.render_markdown("## 階段 2 — 實作\n")
        self.assertIn("<h2 id=", html)
        self.assertEqual(headings[0]["text"], "階段 2 — 實作")

    def test_table_is_wrapped_for_overflow(self) -> None:
        html = self.render("| 欄 | 位 |\n|---|---|\n| a | b |\n")
        self.assertIn('<div class="table-wrap">', html)
        self.assertIn("<th>欄</th>", html)
        self.assertIn("<td>b</td>", html)

    def test_nested_list(self) -> None:
        html = self.render("- 上層\n  - 巢狀\n- 第二項\n")
        self.assertIn("<ul>", html)
        self.assertIn("巢狀", html)
        self.assertEqual(html.count("<ul>"), 2)

    def test_ordered_list(self) -> None:
        self.assertIn("<ol>", self.render("1. 第一\n2. 第二\n"))

    def test_inline_formatting(self) -> None:
        html = self.render("**粗** 與 `code` 與 [連結](https://example.invalid)\n")
        self.assertIn("<strong>粗</strong>", html)
        self.assertIn("<code>code</code>", html)
        self.assertIn('target="_blank"', html)

    def test_code_block_escapes_and_keeps_literal_markdown(self) -> None:
        html = self.render("```\n<tag> & **not bold** `not code`\n```\n")
        self.assertIn("&lt;tag&gt; &amp; **not bold** `not code`", html)
        self.assertNotIn("<strong>", html)

    def test_blockquote(self) -> None:
        self.assertIn("<blockquote>", self.render("> 注意事項\n"))


class ExtractionTests(unittest.TestCase):
    def test_extracts_named_block(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "sample.md"
            path.write_text(
                "## 章節\n\n```\n第一塊\n```\n\n```\n第二塊\n```\n", encoding="UTF-8"
            )
            self.assertEqual(build_docs.extract_code_block(path, "## 章節"), "第一塊")
            self.assertEqual(build_docs.extract_code_block(path, "## 章節", 2), "第二塊")

    def test_missing_heading_raises(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "sample.md"
            path.write_text("## 別的章節\n\n```\n內容\n```\n", encoding="UTF-8")
            with self.assertRaises(build_docs.BuildError):
                build_docs.extract_code_block(path, "## 不存在")

    def test_block_from_later_section_is_not_borrowed(self) -> None:
        """章節內沒有 code block 時不得抓下一節的。"""
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "sample.md"
            path.write_text("## 空章節\n\n文字\n\n## 下一節\n\n```\n不該被抓\n```\n", encoding="UTF-8")
            with self.assertRaises(build_docs.BuildError):
                build_docs.extract_code_block(path, "## 空章節")

    def test_every_configured_example_resolves(self) -> None:
        """EXAMPLES 全部要抽得到——來源章節改名時這裡會失敗。"""
        for example in build_docs.EXAMPLES:
            with self.subTest(example=example["title"]):
                code = build_docs.extract_code_block(example["path"], example["heading"])
                self.assertTrue(code.strip(), f"{example['title']} 抽到空內容")


class SkillCollectionTests(unittest.TestCase):
    def test_all_skills_are_collected_and_grouped(self) -> None:
        skills = build_docs.collect_skills()
        on_disk = {
            directory.name
            for directory in build_docs.SKILLS_DIR.iterdir()
            if (directory / "SKILL.md").is_file()
        }
        self.assertEqual({skill["name"] for skill in skills}, on_disk)

        grouped = build_docs.group_skills(skills)
        self.assertNotIn(
            "未分類",
            "".join(title for title, _, _ in grouped),
            "有 skill 未列入 SKILL_GROUPS",
        )
        flattened = [skill["name"] for _, _, members in grouped for skill in members]
        self.assertEqual(sorted(flattened), sorted(on_disk))

    def test_unknown_skill_lands_in_uncategorised_group(self) -> None:
        extra = [{"name": "brand-new-skill", "summary": "測試用", "readonly": "no"}]
        grouped = build_docs.group_skills(build_docs.collect_skills() + extra)
        titles = [title for title, _, _ in grouped]
        self.assertTrue(any("未分類" in title for title in titles))


class PageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.page = build_docs.build_page()

    def test_page_is_structurally_sound(self) -> None:
        checker = StructureChecker()
        checker.feed(self.page)
        self.assertEqual(checker.unbalanced, [], "HTML 標籤不平衡")
        self.assertEqual(checker.stack, [], f"未關閉的標籤：{checker.stack}")

    def test_every_nav_anchor_has_a_target(self) -> None:
        checker = StructureChecker()
        checker.feed(self.page)
        missing = sorted(checker.anchors - checker.ids)
        self.assertEqual(missing, [], f"導覽連結指向不存在的 id：{missing}")

    def test_contains_every_skill(self) -> None:
        for directory in build_docs.SKILLS_DIR.iterdir():
            if (directory / "SKILL.md").is_file():
                with self.subTest(skill=directory.name):
                    label = (
                        "$bootstrap-ai-project / /bootstrap-ai-project"
                        if directory.name == "bootstrap-ai-project"
                        else f"/{directory.name}"
                    )
                    self.assertIn(f"<h4>{label}</h4>", self.page)

    def test_contains_every_source_h2(self) -> None:
        for source in (build_docs.WORKFLOW_MD, build_docs.WALKTHROUGH_MD):
            text = source.read_text(encoding="UTF-8")
            for heading in re.findall(r"^## (.+)$", text, re.M):
                plain = re.sub(r"[`*]", "", heading).strip()
                with self.subTest(source=source.name, heading=plain):
                    self.assertIn(plain.split("（")[0].strip()[:12], self.page)

    def test_flow_diagram_stages_match_workflow_headings(self) -> None:
        """SVG 節點名稱必須是 development-workflow.md 某個 H2 的前綴。"""
        text = build_docs.WORKFLOW_MD.read_text(encoding="UTF-8")
        h2 = [re.sub(r"[`*]", "", h).strip() for h in re.findall(r"^## (.+)$", text, re.M)]
        for stage in re.findall(r'data-stage="([^"]+)"', self.page):
            with self.subTest(stage=stage):
                self.assertTrue(
                    any(heading.startswith(stage) for heading in h2),
                    f"流程圖的「{stage}」在 development-workflow.md 找不到對應章節",
                )

    def test_no_raw_markdown_outside_code_blocks(self) -> None:
        body = self.page.split("</style>", 1)[1]
        stripped = re.sub(r"<pre>.*?</pre>", "", body, flags=re.S)
        for pattern, label in ((r"\*\*", "粗體標記"), (r"^\s*\|", "表格列"), (r"^#{1,6}\s", "標題")):
            with self.subTest(label=label):
                self.assertEqual(re.findall(pattern, stripped, re.M), [], f"殘留 {label}")

    def test_is_self_contained(self) -> None:
        self.assertNotIn("<script", self.page)
        for pattern in (r'src="https?://', r'<link[^>]+href="https?://', r"@import"):
            with self.subTest(pattern=pattern):
                self.assertEqual(re.findall(pattern, self.page), [])

    def test_supports_both_colour_schemes(self) -> None:
        self.assertIn("prefers-color-scheme: dark", self.page)
        self.assertIn("color-scheme: light dark", self.page)

    def test_tables_can_scroll_horizontally(self) -> None:
        self.assertIn("overflow-x: auto", self.page)
        self.assertEqual(
            self.page.count("<table>"), self.page.count('<div class="table-wrap">')
        )


if __name__ == "__main__":
    unittest.main()
