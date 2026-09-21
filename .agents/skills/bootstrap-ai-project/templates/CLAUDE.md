# CLAUDE.md

@AGENTS.md

## 專案概述

{PROJECT_NAME} — {TECH_STACK_SUMMARY}

選定目標：`{SELECTED_TARGET}`

## 常用指令

{CONFIRMED_COMMANDS_OR_UNCONFIRMED}

## Claude Code 專屬規則

- 跨工具共同規範已由上方 `@AGENTS.md` 匯入，避免雙寫漂移。
- `.claude/` 版本控制策略：{CLAUDE_VCS_POLICY}
- 禁止未經授權建立、切換或刪除 Git 分支與 worktree。
- 不讀取或輸出 `.env`、credentials、私鑰與 token 真值。
- CLI 與一般文字檔使用 UTF-8；遇到亂碼先修正 console encoding。

{SPECTRA_SECTION_ONLY_WHEN_DISCOVERED_OR_EFFECTIVE}

## 詳細文件

- @README.md — 專案門面與快速開始
- @AGENTS.md — 跨工具協作規範與專案慣例
- @docs/README.md — 文件索引
- @docs/ARCHITECTURE.md — 架構、元件與資料流
- @docs/FEATURES.md — 已確認功能與狀態
- @docs/DEVELOPMENT.md — 開發環境與規範
- @docs/TESTING.md — 測試位置、命令與限制
{ADR_AND_CONTEXT_LINES_ONLY_WHEN_FILES_EXIST}

## 來源

{PROJECT_CONVENTION_EVIDENCE}
