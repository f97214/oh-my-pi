# Apply：專案文件

## 目錄

- [文件集合](#文件集合)
- [生成原則](#生成原則)
- [README 三態](#readme-三態)
- [AGENTS 與 CLAUDE](#agents-與-claude)
- [機密與編碼](#機密與編碼)

## 文件集合

| 檔案 | 職責 |
|---|---|
| `README.md` | 專案門面、快速開始、最常用命令 |
| `AGENTS.md` | 跨 AI 工具的單一協作規範 |
| `CLAUDE.md` | Claude Code 薄入口，引用 AGENTS 與必要 Claude 專屬資訊 |
| `docs/README.md` | 文件索引 |
| `docs/ARCHITECTURE.md` | 元件、資料流、外部邊界與來源 |
| `docs/FEATURES.md` | 實際存在的能力與狀態 |
| `docs/DEVELOPMENT.md` | 環境、建置、設定鍵名與開發流程 |
| `docs/TESTING.md` | 現有測試位置、框架、指令與限制 |
| `docs/adr/README.md` | 架構決策紀錄索引（條件式，見下） |

沒有足夠內容時保留章節並標記「未確認」，不要產生空泛教科書文字。

`docs/adr/README.md` 只在 target 已存在 `docs/adr/` 且其中有 ADR 時建立或更新，欄位為編號、標題、狀態、來源。沒有任何 ADR 時不建立空索引，也不建立 `docs/adr/` 目錄——索引隨第一份 ADR 出現才有意義。既有索引有自訂內容時不覆蓋，只提出合併預覽。

## 生成原則

- 專案名稱、技術棧與命令先由 discovery 證據決定，再由使用者確認衝突。
- 深讀原始碼後才寫架構與功能文件。
- 每個重要段落附「來源」清單；無證據的推測標示「未確認」。
- 指令只有在 manifest、script、CI 或使用者確認中出現才可寫成正式命令。
- 不留下模板 placeholder 或條件標記。

## README 三態

1. 不存在：建立。
2. 明確框架樣板：在 Preview 說明判定證據；取得確認後才替換。
3. 自訂內容：不覆蓋。提出新增區段的合併預覽；無安全插入點則 skip。

## AGENTS 與 CLAUDE

- 使用 `templates/AGENTS.md` 與 `templates/CLAUDE.md` 作為結構，不直接複製未展開 placeholder。
- AGENTS 是跨工具單一事實來源；CLAUDE 必須以獨立的 `@AGENTS.md` 匯入，不重複長篇規則。
- 不建立 `CODEX.md`；Codex 直接讀 `AGENTS.md`。
- 文件模式且專案未使用 Spectra/OpenSpec 時，兩者不得提及相關檔案或命令。
- 專案本來已使用 Spectra 時，可據實記錄並附來源，但不得寫成本次新啟用。
- 預設不產生 Copilot 轉接檔；既有 `.github/copilot-instructions.md` 不修改、不刪除。

兩份模板的 `{ADR_AND_CONTEXT_LINES_ONLY_WHEN_FILES_EXIST}` 依 discovery 結果逐行展開，檔案不存在時整行不輸出；兩者皆不存在時整個 placeholder 連同該行一併刪除，不留空行或未展開標記：

| 條件 | `CLAUDE.md` 詳細文件 | `AGENTS.md` 專案慣例 |
|---|---|---|
| `docs/adr/` 存在且有 ADR | `- @docs/adr/README.md — 架構決策紀錄索引` | `- **架構決策：** 見 docs/adr/`（輸出時寫成指向 `docs/adr/` 的連結） |
| `CONTEXT.md` 存在 | `- @CONTEXT.md — 專案詞彙表` | `- **詞彙表：** 見 CONTEXT.md`（輸出時寫成指向 `CONTEXT.md` 的連結） |

不得為了讓連結成立而建立這些檔案；本次 bootstrap 也不撰寫 ADR 或詞彙表內容。

## 機密與編碼

- 永遠不讀真實 `.env`；設定文件只列鍵名、用途與取得方式，不列值。
- 所有生成內容在 plan 前與 apply 後各掃描一次。
- 可安全遮蔽的內容使用 `[REDACTED]`；不可安全遮蔽時阻擋整份檔案寫入。
- 高熵字串只回報「需要確認」，不得自動判定為安全或祕密。
- 文件統一 UTF-8；不要為了修編碼覆寫無法可靠解碼的既有自訂檔。
- 摘要必須說明：掃描是第二層防護，不保證偵測所有機密。
