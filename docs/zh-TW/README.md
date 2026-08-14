# 繁體中文文件

這個目錄放的是 oh-my-pi **入門文件的繁體中文翻譯**。

> **英文原文永遠是準的。** 上游 [`can1357/oh-my-pi`](https://github.com/can1357/oh-my-pi) 還在活躍開發，這裡的翻譯**不會**自動跟上。每份檔案開頭都標了翻譯基準的 commit，看到內容跟實際行為對不上時，回去讀英文原檔。

翻譯基準：`1c7170e11`（2026-08-14）

## 已翻譯

| 中文版 | 英文原檔 | 內容 |
|---|---|---|
| [`project-overview.md`](project-overview.md) | [`README.md`](../../README.md) | 專案門面：安裝、21 項功能、工具清單、供應商、Rust 原生層、四個進入點 |
| [`contributing.md`](contributing.md) | [`CONTRIBUTING.md`](../../CONTRIBUTING.md) | 貢獻流程、AI 輔助貢獻的界線、PR 要求 |
| [`providers.md`](providers.md) | [`docs/providers.md`](../providers.md) | 供應商如何變成可用、憑證優先順序、環境變數對照、本機引擎、自訂供應商 |
| [`config-usage.md`](config-usage.md) | [`docs/config-usage.md`](../config-usage.md) | 設定根目錄、profile、settings 分層與優先順序、各子系統怎麼用設定 |
| [`skills.md`](skills.md) | [`docs/skills.md`](../skills.md) | Skill 的目錄結構、frontmatter、探索流程與 provider 優先順序、`skill://` |
| [`tree.md`](tree.md) | [`docs/tree.md`](../tree.md) | `/tree` session 樹導覽：按鍵、篩選、選取結果、摘要流程 |
| [`approval-mode.md`](approval-mode.md) | [`docs/approval-mode.md`](../approval-mode.md) | 工具核准的三個輸入、三種模式、安全覆寫、ACP 與子代理 |
| [`agent-hub.md`](agent-hub.md) | [`docs/agent-hub.md`](../agent-hub.md) | 子代理的即時名冊、檢視器、導引與復活 |
| [`vibe-mode.md`](vibe-mode.md) | [`docs/vibe-mode.md`](../vibe-mode.md) | 導演模式：兩種 worker 層級與五個控制工具 |
| [`magic-keywords.md`](magic-keywords.md) | [`docs/magic-keywords.md`](../magic-keywords.md) | `ultrathink`／`orchestrate`／`workflowz` 的效果與比對規則 |

## 本來就是中文、但不在這個目錄的

`docs/` 底下另有五份**原生中文**文件。它們不是翻譯，是這個 fork 自己寫的，所以留在 `docs/` 而不搬進來（`CLAUDE.md` 也用 `@docs/...` 語法匯入它們）：

- [`docs/README.md`](../README.md) —— 全部 82 個 docs 項目的分組索引
- [`docs/ARCHITECTURE.md`](../ARCHITECTURE.md) —— 雙 workspace、相依方向、worker 契約、Rust crate
- [`docs/FEATURES.md`](../FEATURES.md) —— 附來源的能力盤點
- [`docs/DEVELOPMENT.md`](../DEVELOPMENT.md) —— 環境、常用指令、程式碼慣例
- [`docs/TESTING.md`](../TESTING.md) —— 測試拓樸、分桶理由、撰寫契約

## 沒有翻譯的部分

`docs/` 還有 70 幾份英文文件沒翻，這是刻意的：

- **`settings.md`（99 KB）、`environment-variables.md`（96 KB）** —— 設定鍵與預設值的參考表，你要找的是鍵名，翻了反而難查
- **`models.md`** —— 大量模型 ID
- **`tools/`（31 份）、`toolconv/`（11 份）** —— wire format 與 JSON 範例，翻錯就變成錯誤文件
- **`sdk.md`、`rpc.md`** —— 給嵌入者看的，內容以程式碼為主
- **`AGENTS.md`** —— 它是給 AI agent 讀的契約，中文化會讓術語跟程式碼裡的英文識別字對不上

## 翻譯慣例

如果你要補翻或修正：

- **保留原文**：程式碼區塊內容、終端機指令、檔案路徑、變數／函式／型別名、API 與套件名、設定鍵、環境變數、模型 ID、旗標，以及廣為使用的英文術語（commit、merge、build、deploy、fork、PR）
- **台灣用語**：軟體、程式、檔案、資料夾、網路
- **結構不動**：標題層級、表格、清單縮排、HTML 區塊、badge 與圖片 URL
- **連結**：目標有翻譯就用 `./foo.md`，沒有就用 `../foo.md` 指回英文原檔；指向 repo 根的用 `../../`
- **開頭標頭**：每份都要標來源檔與翻譯基準的 commit
