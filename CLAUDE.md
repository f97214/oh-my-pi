# CLAUDE.md

@AGENTS.md

## 專案概述

**oh-my-pi**（binary 名稱 `omp`）— Bun 執行的 TypeScript monorepo，加上提供效能關鍵原生能力的 Rust workspace。它是 [pi-mono](https://github.com/badlogic/pi-mono) 的 fork，重寫為 coding-first 的 agent 介面。

選定目標：`E:\howard\自造工具\oh-my-pi\oh-my-pi`（repo 根目錄）

技術棧：Bun `1.3.14` + TypeScript（`package.json:packageManager`）、Rust `nightly-2026-07-28`（`rust-toolchain.toml`）、Python 3（`python/omp-rpc`、`python/robomp`）。Bun workspace 共 17 個 `packages/*`，Cargo workspace 共 7 個 `crates/*` 加 vendored `brush-core`。

**「agent」的指涉**：使用者說「agent」或問「為什麼 agent 會做 X」，指的是 **`packages/coding-agent` 的實作**，不是目前這個對話中的助理。它是一支 CLI 工具，關於它行為的問題都要回到 `packages/coding-agent/` 的程式碼。

## 常用指令

```bash
bun setup                # 安裝 workspace 相依 + 建置 pi-natives + link CLI
bun dev                  # 從原始碼跑 CLI
bun check                # 型別與 lint 檢查（絕不用 tsc／npx tsc）
bun test                 # TypeScript 測試（= bun scripts/ci-test-ts.ts local）
bun run test:rs          # Rust 測試
bun run test:py          # Python 測試（複合命令，含 &&）
bun run ci:test:smoke    # 冒煙探針，含 omp --smoke-test 的 worker 驗證
bun run build:native     # 改動 Rust crate 或 packages/natives 後必跑
bun run lint / fmt / fix
```

**本機現況**（2026-08-14）：bun `1.3.14`、node、cargo（nightly-2026-07-28）、python `3.14.0`、docker、VS Build Tools 2022 都已就緒，`node_modules/` 也已建立。

但 `bun setup` **卡在第二步**：`bun run build:native` 失敗，所以 `packages/natives/native/` 底下沒有 `.node` addon，`omp` 也沒進 PATH。原因是 `LIB`／`INCLUDE` 為空（工具有裝，只是環境變數沒帶進 shell），與 `cargo check` 撞的 `LNK1104: msvcrt.lib` 同源。修法見 `docs/DEVELOPMENT.md` 的「Windows：先把 MSVC 環境帶進來」。

## Claude Code 專屬規則

- 跨工具共同規範已由上方 `@AGENTS.md` 匯入，避免雙寫漂移。
- `.claude/` 版本控制策略：**團隊追蹤** —— `.claude/`、`.agents/`、`.codex/`、`.ai/` 納入版本控制，全隊共用同一套規範與 hooks。
- **`.claude/skills/spectra-*/` 唯讀** —— 由 Spectra CLI 產生，改了會在升級時消失。
- 未經要求不得 commit。
- 禁止未經授權建立、切換或刪除 Git 分支與 worktree。
- 不讀取或輸出 `.env`、credentials、私鑰與 token 真值。
- CLI 與一般文字檔使用 UTF-8；Windows 上輸出中文出現亂碼時設 `PYTHONUTF8=1` 或修正 console encoding，**不要改檔案編碼**。

### 收工閘門

`.claude/settings.json` 註冊了 `.ai/bootstrap-ai-project/` 下的共用 hook runtime：

- `verify-gate.py`（SessionStart／Stop／SessionEnd）—— 對本 session 的變更跑 `verify-gate.json` 的檢查，只看退出碼，連續三次未過就放行並要求如實告知。
- `claim-ledger.py` + `claim-guard.py`（PostToolUse／Stop）—— 記錄跑過的 test／check／search 類命令，收工時比對訊息裡的宣稱有沒有對應紀錄。

兩者都是**防呆不是防駭**：換個說法就繞得過去，擋的是疏忽。

**已知缺口**：閘門目前**只涵蓋 Python 工具鏈**（skill lint、build_docs、tools 與 bootstrap 測試），**TypeScript 與 Rust 兩側都零覆蓋**：

- TypeScript —— bun 與相依都好了，缺的是**先實際跑過一次**確認跑得完，之後才把 `bun run check:ts` 與 `bun run ci:test:smoke` 加進 `verify-gate.json`（`timeout` 上限 600 秒，完整 `bun test` 塞不進去）。
- Rust —— `cargo check` 在此環境失敗（`LNK1104: 無法開啟檔案 'msvcrt.lib'`），因為 `LIB`／`INCLUDE` 未設定。閘門直接 spawn 命令、**不經 shell**，所以它無法自行 source `vcvars64.bat`。要納入閘門，必須先讓 `LIB`／`INCLUDE` 在 Claude Code 啟動的環境中就已設好，並確認 `cargo check --workspace --all-targets` 真的能跑完再加。

**沒驗證過的命令不要加進閘門** —— 這條是踩過坑寫下來的。

## Spectra / SDD

本 repo 已使用 Spectra（`.spectra.yaml`：`tdd: true`、`parallel_tasks: true`、`locale: tw`）。規格在 `openspec/specs/`，變更提案在 `openspec/changes/` —— 兩者目前都是空的。

可用的 `/spectra-*` skill 與流程見 `AGENTS.md`。工作分級（小改動直接做、中型走到 `design.md` 收斂、大型走完整流程）由使用者決定，AI 不自行降級。

## 詳細文件

- @README.md — 專案門面與快速開始
- @AGENTS.md — 跨工具協作規範與專案慣例
- @docs/README.md — 文件索引（82 個項目）
- @docs/ARCHITECTURE.md — 架構、元件與資料流
- @docs/FEATURES.md — 已確認功能與狀態
- @docs/DEVELOPMENT.md — 開發環境與規範
- @docs/TESTING.md — 測試位置、命令與限制

## 來源

- `package.json`、`bunfig.toml`、`rust-toolchain.toml`、`Cargo.toml`、`biome.json`
- `AGENTS.md`（Development Rules、Testing Guidance、Worker scripts、Generated Files）
- `README.md`、`docs/`（82 個項目）
- `.spectra.yaml`、`.claude/settings.json`、`.codex/hooks.json`、`.ai/bootstrap-ai-project/verify-gate.json`
- `scripts/ci-test-ts.ts`（測試拓樸與分桶理由）
- 環境探測：`Get-Command bun`（無結果）、`Test-Path node_modules`（False）、`cargo 1.99.0-nightly`、`Python 3.14.0`
