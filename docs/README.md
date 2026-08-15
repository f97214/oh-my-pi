# 文件索引

`docs/` 目前有 89 個項目（84 份 markdown、1 份 HTML，加 `skills/`、`tools/`、`toolconv/`、`zh-TW/` 四個子目錄）。本索引依主題分組，讓人與 agent 都能先定位再展開。

專案門面與功能敘述在根目錄 [`README.md`](../README.md)；跨 AI 工具的協作規範在 [`AGENTS.md`](../AGENTS.md)。

來源：`docs/` 目錄列表。

## 使用教學（先看這份）

[`GUIDE.html`](GUIDE.html) —— 給**使用 omp 的人**的繁體中文上手教學：接上模型、第一個 session、核心工作流、核准模式、plan mode、session 管理、模型角色、slash 命令與快捷鍵速查、疑難排解。單一自足 HTML，離線可讀，用瀏覽器開。

這是原創內容不是翻譯，所以放在 `docs/` 根層而非 `zh-TW/`。指令與 flag 取自 `omp --help` 實際輸出，slash 命令逐一對照過原始碼。

## 繁體中文翻譯

[`zh-TW/`](zh-TW/) 有十份入門文件的中文翻譯（含根目錄 `README.md` 與 `CONTRIBUTING.md`）。**英文原文為準** —— 上游還在活躍開發，翻譯不會自動跟上，每份檔案都標了翻譯基準的 commit。清單與未翻譯的部分見 [`zh-TW/README.md`](zh-TW/README.md)。

本檔與下列四份是**原生中文**、不是翻譯，所以留在 `docs/` 而非 `zh-TW/`。

## 本次 bootstrap 新增的四份

| 檔案 | 內容 |
|---|---|
| [`ARCHITECTURE.md`](ARCHITECTURE.md) | monorepo 分層、套件相依方向、Rust 原生層邊界 |
| [`FEATURES.md`](FEATURES.md) | 已確認能力清單，每項附原始碼或設定來源 |
| [`DEVELOPMENT.md`](DEVELOPMENT.md) | 環境需求、建置、常用指令、程式碼慣例 |
| [`TESTING.md`](TESTING.md) | 測試拓樸、命令、分桶策略與已知限制 |

## 入門與整體

- [`tree.md`](tree.md) — 專案結構
- [`porting-from-pi-mono.md`](porting-from-pi-mono.md) — 從上游 pi-mono 移植的差異
- [`user-facing-packages.md`](user-facing-packages.md) — 哪些套件是對外介面

## 設定與環境

- [`settings.md`](settings.md)、[`config-usage.md`](config-usage.md) — 設定鍵與讀取路徑
- [`environment-variables.md`](environment-variables.md) — 環境變數
- [`secrets.md`](secrets.md) — 祕密處理
- [`install-id.md`](install-id.md) — 安裝識別
- [`theme.md`](theme.md)、[`keybindings.md`](keybindings.md) — 外觀與按鍵

## 模型與供應商

- [`models.md`](models.md)、[`providers.md`](providers.md) — 模型目錄與供應商總覽
- [`adding-a-provider.md`](adding-a-provider.md) — 新增供應商的流程
- [`provider-compat-reference.md`](provider-compat-reference.md)、[`provider-quirks.md`](provider-quirks.md)、[`provider-endpoint-constraints.md`](provider-endpoint-constraints.md)、[`provider-streaming-internals.md`](provider-streaming-internals.md) — 相容性與串流細節
- [`local-models.md`](local-models.md) — 本地模型
- [`auth-broker-gateway.md`](auth-broker-gateway.md) — 認證中介
- [`ai-schema-normalize.md`](ai-schema-normalize.md) — schema 正規化
- [`ERRATA-GPT5-HARMONY.md`](ERRATA-GPT5-HARMONY.md) — 已知勘誤
- [`toolconv/`](toolconv/) — 各家 tool-calling 格式轉換（anthropic、gemini、harmony、qwen3、minimax…）

## 工具與執行時期

- [`custom-tools.md`](custom-tools.md)、[`resolve-tool-runtime.md`](resolve-tool-runtime.md)
- [`bash-tool-runtime.md`](bash-tool-runtime.md) — bash 工具與內建 coreutils
- [`notebook-tool-runtime.md`](notebook-tool-runtime.md)、[`python-repl.md`](python-repl.md) — notebook 與 Python 執行
- [`computer-use.md`](computer-use.md) — 桌面控制
- [`lsp-config.md`](lsp-config.md) — LSP 設定
- [`task-agent-discovery.md`](task-agent-discovery.md)、[`agent-hub.md`](agent-hub.md) — 子代理與 Agent Hub
- [`advisor-watchdog.md`](advisor-watchdog.md) — advisor 角色
- [`tools/`](tools/) — 個別工具參考

## Session 與 context

- [`session.md`](session.md)、[`session-tree-plan.md`](session-tree-plan.md)
- [`session-operations-export-share-fork-resume.md`](session-operations-export-share-fork-resume.md)
- [`session-switching-and-recent-listing.md`](session-switching-and-recent-listing.md)
- [`compaction.md`](compaction.md)、[`non-compaction-retry-policy.md`](non-compaction-retry-policy.md)
- [`context-files.md`](context-files.md)、[`system-prompt-customization.md`](system-prompt-customization.md)
- [`memory.md`](memory.md)、[`mnemosyne-memory-backend.md`](mnemosyne-memory-backend.md)
- [`handoff-generation-pipeline.md`](handoff-generation-pipeline.md)
- [`ttsr-injection-lifecycle.md`](ttsr-injection-lifecycle.md) — time-traveling stream rules
- [`rulebook-matching-pipeline.md`](rulebook-matching-pipeline.md)
- [`magic-keywords.md`](magic-keywords.md)、[`vibe-mode.md`](vibe-mode.md)、[`approval-mode.md`](approval-mode.md)

## 擴充與整合

- [`extensions.md`](extensions.md)、[`extension-loading.md`](extension-loading.md)
- [`skills.md`](skills.md)、[`skills/`](skills/) — skill 撰寫與範例
- [`slash-command-internals.md`](slash-command-internals.md)
- [`marketplace.md`](marketplace.md)、[`plugin-manager-installer-plumbing.md`](plugin-manager-installer-plumbing.md)
- [`hooks.md`](hooks.md)
- [`mcp-config.md`](mcp-config.md)、[`mcp-protocol-transports.md`](mcp-protocol-transports.md)、[`mcp-runtime-lifecycle.md`](mcp-runtime-lifecycle.md)、[`mcp-server-tool-authoring.md`](mcp-server-tool-authoring.md)
- [`gemini-manifest-extensions.md`](gemini-manifest-extensions.md)
- [`sdk.md`](sdk.md)、[`rpc.md`](rpc.md) — 嵌入與 stdio 驅動
- [`collab.md`](collab.md) — 即時協作

## TUI

- [`tui.md`](tui.md)、[`tui-core-renderer.md`](tui-core-renderer.md)、[`tui-runtime-internals.md`](tui-runtime-internals.md)

## Rust 原生層

- [`native-crates.md`](native-crates.md) — crate 總覽
- [`natives-architecture.md`](natives-architecture.md)、[`natives-binding-contract.md`](natives-binding-contract.md)
- [`natives-addon-loader-runtime.md`](natives-addon-loader-runtime.md)
- [`natives-build-release-debugging.md`](natives-build-release-debugging.md)
- [`natives-text-search-pipeline.md`](natives-text-search-pipeline.md)、[`natives-shell-pty-process.md`](natives-shell-pty-process.md)、[`natives-media-system-utils.md`](natives-media-system-utils.md)、[`natives-rust-task-cancellation.md`](natives-rust-task-cancellation.md)
- [`porting-to-natives.md`](porting-to-natives.md)
- [`fs-scan-cache-architecture.md`](fs-scan-cache-architecture.md)
- [`blob-artifact-architecture.md`](blob-artifact-architecture.md)
- [`omptype-guide.md`](omptype-guide.md)

## 發布

- [`macos-signing-notarization.md`](macos-signing-notarization.md)
