#!/usr/bin/env python3
"""Build .claude/docs/index.html from the markdown sources. Standard library only.

單一事實來源是 markdown 與各 SKILL.md；本檔只負責呈現。
任何內容抽取失敗都會讓產生器以非 0 退出，不會產出缺角的網頁。
"""

from __future__ import annotations

import argparse
import html
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from lint_skills import parse_frontmatter  # noqa: E402


EXIT_OK = 0
EXIT_INVALID = 3

ROOT = Path(__file__).resolve().parents[2]
CLAUDE_DIR = ROOT / ".claude"
DOCS_DIR = CLAUDE_DIR / "docs"
SKILLS_DIR = CLAUDE_DIR / "skills"
CANONICAL_SKILLS_DIR = ROOT / ".agents" / "skills"
BOOTSTRAP_DIR = CANONICAL_SKILLS_DIR / "bootstrap-ai-project"

WORKFLOW_MD = DOCS_DIR / "development-workflow.md"
WALKTHROUGH_MD = DOCS_DIR / "walkthrough.md"
OUTPUT_HTML = DOCS_DIR / "index.html"

FENCE = re.compile(r"^\s*(?:```|~~~)\s*([A-Za-z0-9_+-]*)\s*$")
HEADING = re.compile(r"^(#{1,6})\s+(.*)$")
UNORDERED = re.compile(r"^(\s*)[-*]\s+(.*)$")
ORDERED = re.compile(r"^(\s*)(\d+)\.\s+(.*)$")
TABLE_DIVIDER = re.compile(r"^\s*\|[\s:|-]+\|\s*$")
INLINE_CODE = re.compile(r"`([^`]+)`")
BOLD = re.compile(r"\*\*([^*]+)\*\*")
LINK = re.compile(r"\[([^\]]+)\]\(([^)]+)\)")
CODE_TOKEN = "\x00CODE{}\x00"


class BuildError(Exception):
    """內容抽取或來源檔缺失。"""


# --------------------------------------------------------------------------
# markdown → HTML
# --------------------------------------------------------------------------


def slugify(text: str) -> str:
    plain = re.sub(r"[`*]", "", text).strip()
    slug = re.sub(r"[^\w一-鿿-]+", "-", plain).strip("-").lower()
    return slug or "section"


def render_inline(text: str) -> str:
    """行內格式。先抽出 code 保護，逸出，再套用其餘格式。"""
    codes: list[str] = []

    def stash(match: re.Match[str]) -> str:
        codes.append(match.group(1))
        return CODE_TOKEN.format(len(codes) - 1)

    text = INLINE_CODE.sub(stash, text)
    text = html.escape(text, quote=False)
    text = BOLD.sub(r"<strong>\1</strong>", text)
    text = LINK.sub(lambda m: _link(m.group(1), m.group(2)), text)
    for index, code in enumerate(codes):
        text = text.replace(
            CODE_TOKEN.format(index), f"<code>{html.escape(code, quote=False)}</code>"
        )
    return text


def _link(label: str, target: str) -> str:
    safe_target = html.escape(target, quote=True)
    external = ' target="_blank" rel="noreferrer"' if "://" in target else ""
    return f'<a href="{safe_target}"{external}>{label}</a>'


def render_markdown(source: str, heading_offset: int = 0) -> tuple[str, list[dict[str, str]]]:
    """轉換 markdown，回傳 (html, 標題清單)。標題清單供導覽使用。"""
    lines = source.splitlines()
    out: list[str] = []
    headings: list[dict[str, str]] = []
    index = 0

    while index < len(lines):
        line = lines[index]

        fence = FENCE.match(line)
        if fence:
            index += 1
            body: list[str] = []
            while index < len(lines) and not FENCE.match(lines[index]):
                body.append(lines[index])
                index += 1
            index += 1  # 收尾的 fence
            code = html.escape("\n".join(body), quote=False)
            out.append(f"<pre><code>{code}</code></pre>")
            continue

        heading = HEADING.match(line)
        if heading:
            level = min(len(heading.group(1)) + heading_offset, 6)
            text = heading.group(2).strip()
            slug = slugify(text)
            out.append(f'<h{level} id="{slug}">{render_inline(text)}</h{level}>')
            headings.append({"level": str(level), "text": text, "slug": slug})
            index += 1
            continue

        if line.strip() in {"---", "***", "___"}:
            out.append("<hr>")
            index += 1
            continue

        if line.lstrip().startswith(">"):
            quote: list[str] = []
            while index < len(lines) and lines[index].lstrip().startswith(">"):
                quote.append(lines[index].lstrip()[1:].lstrip())
                index += 1
            inner, _ = render_markdown("\n".join(quote))
            out.append(f"<blockquote>{inner}</blockquote>")
            continue

        if line.strip().startswith("|"):
            table, index = _consume_table(lines, index)
            if table:
                out.append(table)
                continue

        if UNORDERED.match(line) or ORDERED.match(line):
            block, index = _consume_list(lines, index)
            out.append(block)
            continue

        if not line.strip():
            index += 1
            continue

        paragraph: list[str] = []
        while index < len(lines) and lines[index].strip():
            candidate = lines[index]
            if (
                FENCE.match(candidate)
                or HEADING.match(candidate)
                or candidate.strip().startswith(("|", ">"))
                or UNORDERED.match(candidate)
                or ORDERED.match(candidate)
                or candidate.strip() in {"---", "***", "___"}
            ):
                break
            paragraph.append(candidate.strip())
            index += 1
        if paragraph:
            out.append(f"<p>{render_inline(' '.join(paragraph))}</p>")

    return "\n".join(out), headings


def _split_row(line: str) -> list[str]:
    return [cell.strip() for cell in line.strip().strip("|").split("|")]


def _consume_table(lines: list[str], index: int) -> tuple[str, int]:
    if index + 1 >= len(lines) or not TABLE_DIVIDER.match(lines[index + 1]):
        return "", index
    header = _split_row(lines[index])
    index += 2
    rows: list[list[str]] = []
    while index < len(lines) and lines[index].strip().startswith("|"):
        rows.append(_split_row(lines[index]))
        index += 1

    head = "".join(f"<th>{render_inline(cell)}</th>" for cell in header)
    body = "".join(
        "<tr>" + "".join(f"<td>{render_inline(cell)}</td>" for cell in row) + "</tr>"
        for row in rows
    )
    return (
        f'<div class="table-wrap"><table><thead><tr>{head}</tr></thead>'
        f"<tbody>{body}</tbody></table></div>",
        index,
    )


def _consume_list(lines: list[str], index: int) -> tuple[str, int]:
    """處理清單，以縮排量遞迴出巢狀結構。"""
    first = UNORDERED.match(lines[index]) or ORDERED.match(lines[index])
    assert first is not None
    base_indent = len(first.group(1))
    ordered = ORDERED.match(lines[index]) is not None
    items: list[str] = []

    while index < len(lines):
        line = lines[index]
        match = UNORDERED.match(line) or ORDERED.match(line)
        if not match:
            break
        indent = len(match.group(1))
        if indent < base_indent:
            break
        if indent > base_indent:
            nested, index = _consume_list(lines, index)
            if items:
                items[-1] += nested
            else:
                items.append(nested)
            continue
        content = match.group(match.lastindex or 2)
        items.append(f"<li>{render_inline(content)}")
        index += 1

    tag = "ol" if ordered else "ul"
    body = "".join(item + "</li>" if not item.endswith("</li>") else item for item in items)
    return f"<{tag}>{body}</{tag}>", index


# --------------------------------------------------------------------------
# 內容抽取（fail closed）
# --------------------------------------------------------------------------


def display_path(path: Path) -> str:
    """給人看的路徑。repo 外的路徑（測試用暫存檔）直接回傳絕對路徑，不拋錯。"""
    try:
        return path.relative_to(ROOT).as_posix()
    except ValueError:
        return str(path)


def extract_code_block(path: Path, heading: str, occurrence: int = 1) -> str:
    """抽出指定章節底下第 N 個 fenced code block。找不到就拋錯。"""
    if not path.is_file():
        raise BuildError(f"來源檔不存在：{display_path(path)}")
    lines = path.read_text(encoding="UTF-8").splitlines()

    start = next((i for i, line in enumerate(lines) if line.strip() == heading.strip()), None)
    if start is None:
        raise BuildError(f"{display_path(path)} 找不到章節：{heading}")

    level = len(HEADING.match(heading.strip()).group(1))  # type: ignore[union-attr]
    found = 0
    index = start + 1
    while index < len(lines):
        current = HEADING.match(lines[index])
        if current and len(current.group(1)) <= level:
            break
        if FENCE.match(lines[index]):
            index += 1
            body: list[str] = []
            while index < len(lines) and not FENCE.match(lines[index]):
                body.append(lines[index])
                index += 1
            found += 1
            if found == occurrence:
                return "\n".join(body)
        index += 1

    raise BuildError(
        f"{display_path(path)} 的「{heading}」底下找不到第 {occurrence} 個程式碼區塊"
    )


EXAMPLES = [
    {
        "title": "/grill 的提問格式",
        "note": "每題編號並附上建議答案，你只需要做決策。",
        "path": SKILLS_DIR / "grill" / "SKILL.md",
        "heading": "## 訪談協議",
    },
    {
        "title": "ADR 範本",
        "note": "一份 ADR 可以只有一段話——價值在於記下做過這個決策以及為什麼。",
        "path": SKILLS_DIR / "grill" / "ADR-FORMAT.md",
        "heading": "## 範本",
    },
    {
        "title": "CONTEXT.md 詞彙表格式",
        "note": "同一概念有多種講法時選定一個，其餘列進 _避免_。",
        "path": SKILLS_DIR / "grill" / "CONTEXT-FORMAT.md",
        "heading": "## 結構",
    },
    {
        "title": "TDD 測試命令的 description 格式",
        "note": "只有完全符合這個格式的 allowlist 命令才會被 observer 算成證據。",
        "path": BOOTSTRAP_DIR / "templates" / "rules" / "testing.md",
        "heading": "## 執行測試",
    },
    {
        "title": "每個 Task 的終端摘要",
        "note": "呼叫 spectra task done 之前輸出，狀態只能是四種之一。",
        "path": BOOTSTRAP_DIR / "templates" / "rules" / "testing.md",
        "heading": "## Task 完成前",
    },
    {
        "title": "可觀測性：先寫問題，再加訊號",
        "note": "每個訊號都要對應到其中一題；對應不到就不要加。",
        "path": BOOTSTRAP_DIR / "templates" / "rules" / "engineering.md",
        "heading": "### 先寫問題，再加訊號",
    },
    {
        "title": "資料庫結構的三段式遷移",
        "note": "絕不原地改名，也絕不在同一次部署裡既新增又刪除。",
        "path": DOCS_DIR / "development-workflow.md",
        "heading": "### 汰除舊功能",
    },
]


# --------------------------------------------------------------------------
# Skill 卡片
# --------------------------------------------------------------------------

SKILL_GROUPS = [
    ("專案初始化", "bootstrap", ["bootstrap-ai-project"]),
    ("需求釐清與交接", "compass", ["grill", "first-principles", "handoff"]),
    (
        "Spectra 指令鏈",
        "chain",
        [
            "spectra-propose",
            "spectra-apply",
            "spectra-archive",
            "spectra-ask",
            "spectra-discuss",
            "spectra-ingest",
            "spectra-debug",
            "spectra-audit",
            "spectra-commit",
            "spectra-analyze",
            "spectra-drift",
            "spectra-verify",
        ],
    ),
    (
        "開發角色",
        "code",
        ["implementer", "test-engineer", "doc-writer", "git-commit"],
    ),
    ("專門任務", "wrench", ["vuln-fix", "winform-to-quartz-migration"]),
]

SKILL_SUMMARY = {
    "bootstrap-ai-project": "交易式流程建立 Claude／Codex 雙入口、角色、governance、Hooks 與 Spectra TDD。",
    "grill": "決策樹分輪訪談釐清需求，同步維護 CONTEXT.md 詞彙表與 docs/adr/。",
    "first-principles": "把問題拆回地基事實再由下而上重建；先試著刪除需求本身。",
    "handoff": "把對話濃縮成交接文件，讓新 session 無縫接手。",
    "spectra-propose": "建立含 proposal / design / tasks / spec 的變更提案。",
    "spectra-apply": "依 tasks 實作，內嵌 Red-Green-Refactor。",
    "spectra-archive": "歸檔完成的 change 並同步主規格。",
    "spectra-ask": "查詢 openspec/ 文件回答問題。",
    "spectra-discuss": "針對單一主題聚焦討論並收斂結論。",
    "spectra-ingest": "用外部脈絡更新既有 change。",
    "spectra-debug": "四階段系統化除錯。",
    "spectra-audit": "審查危險預設值、型別混淆與靜默失敗。",
    "spectra-commit": "提交特定 change 相關檔案。",
    "vuln-fix": "保守、最小 diff 的安全弱點修補。",
    "winform-to-quartz-migration": "把舊 WinForm／timer 常駐程式遷移進 .NET 8 Quartz 排程範本。",
}


def collect_skills() -> list[dict[str, str]]:
    skills: list[dict[str, str]] = []
    for directory in sorted(SKILLS_DIR.iterdir()):
        skill_file = directory / "SKILL.md"
        if directory.name == "bootstrap-ai-project":
            skill_file = BOOTSTRAP_DIR / "SKILL.md"
        if not directory.is_dir() or not skill_file.is_file():
            continue
        frontmatter, _ = parse_frontmatter(skill_file.read_text(encoding="UTF-8"))
        name = str(frontmatter.get("name", directory.name))
        summary = SKILL_SUMMARY.get(name)
        if not summary:
            summary = _shorten(str(frontmatter.get("description", "")))
        skills.append(
            {
                "name": name,
                "summary": summary,
                "readonly": "yes" if name.startswith("spectra-") else "no",
            }
        )
    return skills


def _shorten(text: str, limit: int = 120) -> str:
    text = text.strip()
    for stop in ("。", ". "):
        head = text.split(stop, 1)[0]
        if head != text:
            return head + "。"
    return text if len(text) <= limit else text[: limit - 1] + "…"


def group_skills(skills: list[dict[str, str]]) -> list[tuple[str, str, list[dict[str, str]]]]:
    by_name = {skill["name"]: skill for skill in skills}
    grouped: list[tuple[str, str, list[dict[str, str]]]] = []
    assigned: set[str] = set()
    for title, icon, names in SKILL_GROUPS:
        members = [by_name[name] for name in names if name in by_name]
        assigned.update(skill["name"] for skill in members)
        if members:
            grouped.append((title, icon, members))
    leftovers = [skill for skill in skills if skill["name"] not in assigned]
    if leftovers:
        grouped.append(("未分類（請補進 build_docs.py 的 SKILL_GROUPS）", "alert", leftovers))
    return grouped


# --------------------------------------------------------------------------
# 視覺元素
# --------------------------------------------------------------------------

ICONS = {
    "bootstrap": '<path d="M3 7l9-4 9 4-9 4-9-4z"/><path d="M3 12l9 4 9-4"/><path d="M3 17l9 4 9-4"/>',
    "compass": '<circle cx="12" cy="12" r="9"/><path d="M15.5 8.5l-2 5-5 2 2-5 5-2z"/>',
    "chain": '<path d="M10 14a4 4 0 0 0 5.7 0l3-3a4 4 0 1 0-5.7-5.7L11.5 6.8"/>'
    '<path d="M14 10a4 4 0 0 0-5.7 0l-3 3a4 4 0 1 0 5.7 5.7l1.5-1.5"/>',
    "wrench": '<path d="M14.7 6.3a4 4 0 0 0 5 5l-9 9a2.8 2.8 0 0 1-4-4l8-10z"/>',
    "alert": '<path d="M12 4l9 16H3l9-16z"/><path d="M12 10v4"/><path d="M12 17.5v.5"/>',
    "flow": '<circle cx="6" cy="12" r="2.5"/><circle cx="18" cy="6" r="2.5"/>'
    '<circle cx="18" cy="18" r="2.5"/><path d="M8.2 10.8L15.6 7"/><path d="M8.2 13.2L15.6 17"/>',
    "book": '<path d="M4 5.5A2.5 2.5 0 0 1 6.5 3H20v15H6.5A2.5 2.5 0 0 0 4 20.5z"/>',
    "code": '<path d="M9 8l-4 4 4 4"/><path d="M15 8l4 4-4 4"/>',
}


def icon(name: str, size: int = 20) -> str:
    body = ICONS.get(name, ICONS["flow"])
    return (
        f'<svg class="icon" width="{size}" height="{size}" viewBox="0 0 24 24" '
        f'fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" '
        f'stroke-linejoin="round" aria-hidden="true">{body}</svg>'
    )


# 每個節點的 data-stage 必須是 development-workflow.md 某個 H2 的前綴，測試會驗證。
FLOW_NODES = [
    ("階段 0", "/grill", "訪談釐清需求", "optional"),
    ("階段 1", "/spectra-propose", "產出 spec 與 tasks", "ai"),
    ("階段 2", "/spectra-apply", "Red → Green → Refactor", "ai"),
    ("階段 3", "spectra analyze", "完整性驗證", "ai"),
    ("階段 N", "/spectra-archive", "歸檔並同步主規格", "ai"),
    ("發布與汰除", "人主導", "分階段推出與回滾", "human"),
]


def render_flow_svg() -> str:
    width, box_w, box_h, gap = 1180, 168, 92, 34
    top = 78
    nodes: list[str] = []
    for position, (stage, command, detail, kind) in enumerate(FLOW_NODES):
        x = 12 + position * (box_w + gap)
        nodes.append(
            f'<g class="node node--{kind}" data-stage="{html.escape(stage, quote=True)}">'
            f'<rect x="{x}" y="{top}" width="{box_w}" height="{box_h}" rx="12"/>'
            f'<text class="node-stage" x="{x + 16}" y="{top + 27}">{html.escape(stage)}</text>'
            f'<text class="node-cmd" x="{x + 16}" y="{top + 51}">{html.escape(command)}</text>'
            f'<text class="node-detail" x="{x + 16}" y="{top + 73}">{html.escape(detail)}</text>'
            "</g>"
        )
        if position < len(FLOW_NODES) - 1:
            ax = x + box_w
            nodes.append(
                f'<path class="arrow" d="M{ax + 6} {top + box_h / 2} L{ax + gap - 8} '
                f'{top + box_h / 2}" marker-end="url(#arrowhead)"/>'
            )

    checkpoint_one_x = 12 + 1 * (box_w + gap) + box_w / 2
    checkpoint_two_x = 12 + 4 * (box_w + gap) + box_w / 2
    ai_span_end = 12 + 5 * (box_w + gap) - gap / 2

    return f"""
<figure class="flow">
<svg viewBox="0 0 {width} 230" role="img" aria-label="開發流程階段圖">
  <defs>
    <marker id="arrowhead" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="6"
            markerHeight="6" orient="auto"><path d="M0 0 L10 5 L0 10 z"/></marker>
  </defs>
  <text class="checkpoint" x="{checkpoint_one_x}" y="34" text-anchor="middle">ADR 檢查點 ①</text>
  <text class="checkpoint-sub" x="{checkpoint_one_x}" y="52" text-anchor="middle">design 收斂後</text>
  <path class="tick" d="M{checkpoint_one_x} 58 L{checkpoint_one_x} {top - 4}"/>
  <text class="checkpoint" x="{checkpoint_two_x}" y="34" text-anchor="middle">ADR 檢查點 ②</text>
  <text class="checkpoint-sub" x="{checkpoint_two_x}" y="52" text-anchor="middle">歸檔前回收</text>
  <path class="tick" d="M{checkpoint_two_x} 58 L{checkpoint_two_x} {top - 4}"/>
  {"".join(nodes)}
  <path class="span" d="M12 {top + box_h + 22} L{ai_span_end} {top + box_h + 22}"/>
  <text class="span-label" x="{(12 + ai_span_end) / 2}" y="{top + box_h + 42}"
        text-anchor="middle">AI 主導，遇衝突停下來問你</text>
  <path class="span span--human" d="M{ai_span_end + 20} {top + box_h + 22} L{width - 12}
        {top + box_h + 22}"/>
  <text class="span-label span-label--human" x="{(ai_span_end + width) / 2}"
        y="{top + box_h + 42}" text-anchor="middle">你決定</text>
</svg>
<figcaption>階段 0 可跳過；發布通常是數個 change 累積後一起進行。</figcaption>
</figure>
"""


def render_skill_cards(grouped: list[tuple[str, str, list[dict[str, str]]]]) -> str:
    blocks: list[str] = []
    for title, group_icon, members in grouped:
        cards = "".join(
            f'<article class="card{" card--readonly" if skill["readonly"] == "yes" else ""}">'
            f'<h4>{html.escape(("$bootstrap-ai-project / /bootstrap-ai-project") if skill["name"] == "bootstrap-ai-project" else "/" + skill["name"])}</h4>'
            f'<p>{render_inline(skill["summary"])}</p>'
            + (
                '<span class="tag">Spectra CLI 產生．唯讀</span>'
                if skill["readonly"] == "yes"
                else ""
            )
            + "</article>"
            for skill in members
        )
        blocks.append(
            f'<h3 class="group">{icon(group_icon)}{html.escape(title)}'
            f'<span class="count">{len(members)}</span></h3>'
            f'<div class="cards">{cards}</div>'
        )
    return "".join(blocks)


def render_examples() -> str:
    blocks: list[str] = []
    for example in EXAMPLES:
        code = extract_code_block(
            example["path"], example["heading"], int(example.get("occurrence", 1))
        )
        source = display_path(Path(example["path"]))
        blocks.append(
            '<article class="example">'
            f'<h3>{html.escape(example["title"])}</h3>'
            f'<p>{render_inline(example["note"])}</p>'
            f"<pre><code>{html.escape(code, quote=False)}</code></pre>"
            f'<p class="source">來源：<code>{html.escape(source)}</code>'
            f' — 「{html.escape(example["heading"].lstrip("# "))}」</p>'
            "</article>"
        )
    return "".join(blocks)


# --------------------------------------------------------------------------
# 版型
# --------------------------------------------------------------------------

STYLE = """
:root {
  color-scheme: light dark;
  --bg: #fbfbfa; --panel: #ffffff; --ink: #1c1b1a; --muted: #6b6a67;
  --line: #e2e0dc; --accent: #b3502a; --accent-soft: #f3e6df;
  --code-bg: #f4f2ef; --human: #2f6f5e; --human-soft: #e2efea;
  --mono: ui-monospace, "Cascadia Code", "Consolas", "Menlo", monospace;
}
@media (prefers-color-scheme: dark) {
  :root {
    --bg: #141613; --panel: #1b1e1a; --ink: #e8e6e1; --muted: #9c9a94;
    --line: #2e322c; --accent: #e08c62; --accent-soft: #33231b;
    --code-bg: #10120f; --human: #7fc4ae; --human-soft: #1c2b26;
  }
}
* { box-sizing: border-box; }
body {
  margin: 0; background: var(--bg); color: var(--ink);
  font-family: "Noto Sans TC", -apple-system, "Segoe UI", system-ui, sans-serif;
  font-size: 16px; line-height: 1.75; -webkit-font-smoothing: antialiased;
}
.layout { display: grid; grid-template-columns: 262px minmax(0, 1fr); gap: 40px;
  max-width: 1380px; margin: 0 auto; padding: 0 28px 96px; }
nav { position: sticky; top: 0; align-self: start; max-height: 100vh;
  overflow-y: auto; padding: 32px 0; font-size: 14px; }
nav .brand { font-weight: 700; font-size: 17px; letter-spacing: .01em; margin-bottom: 4px; }
nav .brand-sub { color: var(--muted); font-size: 12.5px; margin-bottom: 22px; }
nav a { display: block; padding: 5px 12px; color: var(--muted); text-decoration: none;
  border-left: 2px solid transparent; }
nav a:hover { color: var(--accent); border-left-color: var(--accent); background: var(--accent-soft); }
nav a.lv3 { padding-left: 26px; font-size: 13px; }
nav .nav-group { margin-top: 18px; font-weight: 600; color: var(--ink);
  text-transform: none; font-size: 12.5px; letter-spacing: .06em; padding-left: 12px; }
main { padding-top: 32px; min-width: 0; }
header.page { border-bottom: 1px solid var(--line); padding-bottom: 28px; margin-bottom: 12px; }
header.page h1 { font-size: 34px; line-height: 1.25; margin: 0 0 10px; letter-spacing: -.01em; }
header.page .lede { color: var(--muted); margin: 0 0 18px; max-width: 62ch; }
.generated { font-size: 13px; color: var(--muted); background: var(--code-bg);
  border: 1px solid var(--line); border-radius: 10px; padding: 12px 16px; }
.generated code { background: none; padding: 0; }
h2 { font-size: 25px; margin: 52px 0 14px; padding-top: 8px; letter-spacing: -.005em; }
h3 { font-size: 18.5px; margin: 30px 0 10px; }
h4 { font-size: 15.5px; margin: 20px 0 6px; }
p { margin: 12px 0; }
a { color: var(--accent); }
hr { border: none; border-top: 1px solid var(--line); margin: 40px 0; }
ul, ol { padding-left: 22px; margin: 12px 0; }
li { margin: 5px 0; }
blockquote { margin: 18px 0; padding: 4px 20px; border-left: 3px solid var(--accent);
  background: var(--accent-soft); border-radius: 0 8px 8px 0; }
blockquote p { margin: 10px 0; }
code { font-family: var(--mono); font-size: .875em; background: var(--code-bg);
  padding: 2px 6px; border-radius: 5px; }
pre { background: var(--code-bg); border: 1px solid var(--line); border-radius: 10px;
  padding: 16px 18px; overflow-x: auto; margin: 16px 0; }
pre code { background: none; padding: 0; font-size: 13.5px; line-height: 1.65; }
.table-wrap { overflow-x: auto; margin: 18px 0; border: 1px solid var(--line);
  border-radius: 10px; }
table { border-collapse: collapse; width: 100%; font-size: 14.5px; }
th, td { text-align: left; padding: 10px 14px; border-bottom: 1px solid var(--line);
  vertical-align: top; }
th { background: var(--code-bg); font-weight: 600; white-space: nowrap; }
tr:last-child td { border-bottom: none; }
.flow { margin: 24px 0 8px; padding: 0; overflow-x: auto; }
.flow svg { min-width: 940px; width: 100%; height: auto; }
.flow figcaption { color: var(--muted); font-size: 13.5px; margin-top: 6px; }
.node rect { fill: var(--panel); stroke: var(--line); stroke-width: 1.5; }
.node--ai rect { stroke: var(--accent); }
.node--optional rect { stroke-dasharray: 5 4; }
.node--human rect { stroke: var(--human); fill: var(--human-soft); }
.node-stage { font: 600 15px/1 sans-serif; fill: var(--ink); }
.node-cmd { font: 500 13px/1 var(--mono); fill: var(--accent); }
.node--human .node-cmd { fill: var(--human); }
.node-detail { font: 12.5px/1 sans-serif; fill: var(--muted); }
.arrow { stroke: var(--muted); stroke-width: 1.4; fill: none; }
#arrowhead path { fill: var(--muted); }
.checkpoint { font: 600 12.5px/1 sans-serif; fill: var(--accent); }
.checkpoint-sub { font: 11.5px/1 sans-serif; fill: var(--muted); }
.tick { stroke: var(--accent); stroke-width: 1.2; stroke-dasharray: 3 3; fill: none; }
.span { stroke: var(--accent); stroke-width: 2; fill: none; opacity: .5; }
.span--human { stroke: var(--human); }
.span-label { font: 12.5px/1 sans-serif; fill: var(--accent); }
.span-label--human { fill: var(--human); }
.icon { vertical-align: -3px; margin-right: 8px; color: var(--accent); }
.group { display: flex; align-items: center; margin-top: 34px; }
.group .count { margin-left: 10px; font: 500 12px/1 var(--mono); color: var(--muted);
  border: 1px solid var(--line); border-radius: 20px; padding: 3px 9px; }
.cards { display: grid; gap: 12px; grid-template-columns: repeat(auto-fill, minmax(268px, 1fr)); }
.card { background: var(--panel); border: 1px solid var(--line); border-radius: 11px;
  padding: 14px 16px; }
.card h4 { margin: 0 0 6px; font-family: var(--mono); font-size: 14.5px; color: var(--accent); }
.card p { margin: 0; font-size: 14px; color: var(--muted); line-height: 1.6; }
.card--readonly { border-style: dashed; }
.card .tag { display: inline-block; margin-top: 9px; font-size: 11.5px; color: var(--muted);
  background: var(--code-bg); border-radius: 20px; padding: 2px 9px; }
.example { border: 1px solid var(--line); border-radius: 11px; padding: 4px 18px 14px;
  margin: 18px 0; background: var(--panel); }
.example h3 { margin-top: 16px; }
.example .source { font-size: 12.5px; color: var(--muted); margin: 4px 0 0; }
.section-lede { color: var(--muted); max-width: 66ch; }
@media (max-width: 980px) {
  .layout { grid-template-columns: 1fr; gap: 0; padding: 0 18px 64px; }
  nav { position: static; max-height: none; border-bottom: 1px solid var(--line);
    padding: 20px 0; }
  nav a { display: inline-block; border-left: none; border-bottom: 2px solid transparent; }
  nav a.lv3 { display: none; }
  header.page h1 { font-size: 27px; }
}
"""


def build_nav(sections: list[dict[str, object]]) -> str:
    parts: list[str] = []
    for section in sections:
        parts.append(f'<div class="nav-group">{html.escape(str(section["title"]))}</div>')
        for heading in section["headings"]:  # type: ignore[index]
            level_class = "lv3" if heading["level"] != "2" else ""
            parts.append(
                f'<a class="{level_class}" href="#{heading["slug"]}">'
                f'{html.escape(heading["text"])}</a>'
            )
    return "".join(parts)


def build_page() -> str:
    for source in (WORKFLOW_MD, WALKTHROUGH_MD):
        if not source.is_file():
            raise BuildError(f"來源檔不存在：{display_path(source)}")

    workflow_raw = WORKFLOW_MD.read_text(encoding="UTF-8")
    walkthrough_raw = WALKTHROUGH_MD.read_text(encoding="UTF-8")

    workflow_body, workflow_headings = render_markdown(_drop_title(workflow_raw))
    walkthrough_body, walkthrough_headings = render_markdown(_drop_title(walkthrough_raw))

    skills = collect_skills()
    grouped = group_skills(skills)

    sections = [
        {"title": "實例走查", "headings": [h for h in walkthrough_headings if h["level"] == "2"]},
        {"title": "流程細節", "headings": [h for h in workflow_headings if h["level"] == "2"]},
        {"title": "Skill 目錄", "headings": [{"level": "2", "text": "全部 Skill", "slug": "skills"}]},
        {"title": "格式範例", "headings": [{"level": "2", "text": "格式範例集", "slug": "examples"}]},
    ]

    sources_note = " · ".join(
        f"<code>{path.relative_to(ROOT).as_posix()}</code>"
        for path in (WORKFLOW_MD, WALKTHROUGH_MD)
    )

    return f"""<!doctype html>
<html lang="zh-Hant">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>開發流程與 Skill 說明</title>
<style>{STYLE}</style>
</head>
<body>
<div class="layout">
<nav>
  <div class="brand">開發流程與 Skill</div>
  <div class="brand-sub">SDD + Spectra TDD</div>
  <a href="#overview">流程總覽</a>
  {build_nav(sections)}
</nav>
<main>
<header class="page">
  <h1>開發流程與 Skill 說明</h1>
  <p class="lede">整合 Spectra（SDD）與 TDD 的單一軌道流程，由
    Codex 用 <code>$bootstrap-ai-project</code>、Claude 用 <code>/bootstrap-ai-project</code> 初始化，再由各宿主原生的 <code>spectra-*</code> Skills 驅動。</p>
  <p class="generated">本頁由 <code>.claude/tools/build_docs.py</code> 產生，<strong>請勿手動編輯</strong>。
    內容來源：{sources_note}、各 <code>SKILL.md</code> 與 <code>templates/rules/*.md</code>。
    改完來源後重跑產生器。</p>
</header>

<h2 id="overview">{icon("flow")}流程總覽</h2>
{render_flow_svg()}

<hr>
<h2 id="walkthrough-section">{icon("book")}實例走查</h2>
<p class="section-lede">用一個具體例子走完整條流程，看每一步實際會發生什麼。</p>
{walkthrough_body}

<hr>
<h2 id="workflow-section">{icon("compass")}流程細節與統一規則</h2>
{workflow_body}

<hr>
<h2 id="skills">{icon("chain")}Skill 目錄<span class="count">{len(skills)}</span></h2>
<p class="section-lede">由目錄自動掃描產生，新增或移除 skill 後重跑產生器即會更新。</p>
{render_skill_cards(grouped)}

<hr>
<h2 id="examples">{icon("code")}格式範例集</h2>
<p class="section-lede">全部從既有檔案抽取，來源標在每則下方——抽不到時產生器會直接報錯，
不會產出缺角的頁面。</p>
{render_examples()}
</main>
</div>
</body>
</html>
"""


def _drop_title(markdown: str) -> str:
    """移除來源檔的 H1，頁面自己有標題。"""
    lines = markdown.splitlines()
    if lines and lines[0].startswith("# "):
        return "\n".join(lines[1:])
    return markdown


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="產生 .claude/docs/index.html")
    parser.add_argument("--output", default=str(OUTPUT_HTML))
    parser.add_argument("--check", action="store_true", help="只檢查能否產生，不寫檔")
    args = parser.parse_args(argv)

    try:
        page = build_page()
    except BuildError as error:
        print(f"產生失敗：{error}", file=sys.stderr)
        return EXIT_INVALID

    if args.check:
        print("來源完整，可產生。")
        return EXIT_OK

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(page, encoding="UTF-8")
    print(f"已產生 {output.relative_to(ROOT) if output.is_relative_to(ROOT) else output}"
          f"（{len(page):,} 字元）")
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
