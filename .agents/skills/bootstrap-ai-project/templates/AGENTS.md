# AGENTS.md

本檔是此 repository 的跨 AI 工具協作規範單一事實來源。工具專屬入口只引用本檔，不複製整套規則。

## 1. 開工前必讀與確認

### 必讀清單

存在就讀，不存在就跳過，不要為此建立空檔：

| 讀什麼 | 什麼時候 |
|---|---|
| `docs/ARCHITECTURE.md`、`docs/DEVELOPMENT.md` | 動到架構、分層或新增模組之前 |
| `docs/TESTING.md` | 動測試之前 |
| `CONTEXT.md`（或 `CONTEXT-MAP.md` 定位到的詞彙表） | 建立提案或開始實作之前 |
| `docs/adr/README.md` | 建立提案或開始實作之前；需要細節時才展開個別 ADR |

**知識索引、摘要層或快取的輸出不取代這份清單**，不論用的是哪一種工具。這些文件是契約，回答「可不可以這樣做」；程式碼與測試回答「現在是什麼樣」。從 source 投影出來的東西導不出禁令——已經被否決的做法、不准用的詞、不能跨的界線，都不存在於程式碼裡。

文件與程式碼衝突時停止並回報，不自行選邊。

### 動手前先確認

- 明確列出假設、限制與驗收標準。
- 有多種合理解讀時先說明差異，不要默默選擇。
- repository 證據互相衝突時指出來源並要求決定。
- 能以較小變更完成時，優先選擇較小範圍。

## 2. 維持簡單

- 不實作未要求的功能。
- 不為單次用途建立抽象層。
- 不擴張設定、錯誤處理或相容範圍。
- 優先沿用既有依賴與慣例。

## 3. 精準修改

- 只改與任務相關的檔案。
- 不順手重構鄰近程式碼。
- 保留使用者既有變更與 repository 風格。
- 只清理由本次變更新增的未使用內容。

## 4. 以驗證為終點

- 先定義可觀察的成功條件。
- 修 bug 時先建立可重現證據。
- 依變更風險執行最小充分測試。
- 無法執行的驗證要明確標示，不能寫成已通過。

## 5. 確定性工作交給程式

- 文字整理、摘要與非結構化判讀可使用模型。
- 路由、狀態碼、重試、格式合併與安全阻擋使用程式。
- 不能用提示詞取代可測試的型別與條件判斷。

## 6. 跨 Agent 治理

- 主代理保留需求、規劃、架構、公開介面、整合、驗證與最終輸出所有權。
- Skill 在目前主線程執行；Agent 使用隔離上下文，完成後只向主代理回報。
- Worker 只執行明確契約，不重新解讀最終目標、不擴張範圍、不建立子代理。
- 同一 checkout 同時只允許一個 writer；唯讀 Agent 才可平行。
- 主代理必須回讀 Agent 實際修改的檔案與 diff，並核對測試、建置或 lint 的命令與退出碼。
- Agent 資訊不足、範圍衝突或需要架構／跨模組決策時，回報 `blocked`，不得自行猜測。
- `git-commit` 只有在使用者明確要求時可執行；不得由模型自行判斷工作完成後提交。

## 7. Git 工作流

### AI 的界線

- 不建立、切換、刪除分支或 worktree。
- 若任務需要分支操作，停止並請使用者處理或授權。
- 提交只能在使用者目前所在分支進行。
- 不對共用分支 force push，不繞過 hook。

分支策略（要不要開 feature branch、什麼時候合併）是人的決定；本節只約束 AI 不自行動手。

### 提交紀律

- 一個 commit 只做一件邏輯上的事。
- 訊息說明**為什麼**，不只是做了什麼——未來讀 log 的人缺的是理由。
- 格式化與行為變更分開提交；重構與新功能分開提交。
- 提交前：`git diff --staged` 逐項確認內容、掃過有無祕密、跑測試與 lint。

### 變更大小

| 規模 | 判斷 |
|---|---|
| 約 100 行 | 好審查、好回退 |
| 約 300 行 | 單一邏輯變更的上限 |
| 逼近 1000 行 | 必須拆開 |

這組門檻**針對應用程式碼**。文件、模板與規範類變更改以「一個主題」為單位判斷——一份規範拆成三次提交只會讓歷史更難讀。

### 版本與變更紀錄

只在程式碼有外部消費者時適用：

- 採 `MAJOR.MINOR.PATCH`：破壞相容為 MAJOR、可回溯相容的新增為 MINOR、修錯為 PATCH。
- **不確定算不算破壞性變更時，就當它是。**
- 版本由 tag 推導，不手改散落各處的版本字串；tag 建立後不可變。
- 變更紀錄在改動當下就寫，依 新增／變更／修正／汰除／移除／安全 分組。它是給使用者看的，不是 commit log 的傾印。

## 8. 機密與敏感資料

- 不讀取或輸出 `.env`、私鑰、credentials 或 token 真值。
- 文件只記錄設定鍵名、用途與取得方式。
- 不把 diff、log 或例外中的 credential 複製到文件、commit message 或回覆。
- 自動掃描只是第二層防護，仍需人工確認。

## 9. UTF-8

- 一般文字檔使用 UTF-8 without BOM。
- Windows PowerShell 5.1 的 `.ps1` 可使用 UTF-8 BOM。
- 遇到亂碼先修正 console/tooling encoding，不把正確 UTF-8 轉成 Big5、CP950 或其他 legacy code page。

## 專案慣例

- **專案：** {PROJECT_NAME}
- **選定目標：** `{SELECTED_TARGET}`
- **技術棧：** {TECH_STACK_WITH_SOURCES}
- **建置指令：** `{BUILD_COMMAND_OR_UNCONFIRMED}`
- **測試指令：** `{TEST_COMMAND_OR_UNCONFIRMED}`
- **Lint 指令：** `{LINT_COMMAND_OR_UNCONFIRMED}`
- **架構：** 見 [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md)
- **開發流程：** 見 [`docs/DEVELOPMENT.md`](docs/DEVELOPMENT.md)
{ADR_AND_CONTEXT_LINES_ONLY_WHEN_FILES_EXIST}

{SPECTRA_SECTION_ONLY_WHEN_DISCOVERED_OR_EFFECTIVE}

## 工具專屬說明

- Claude Code 透過 `CLAUDE.md` 的 `@AGENTS.md` 引用本檔；`.claude/` 設定只對 Claude schema 生效。
- OpenAI Codex 與支援 AGENTS.md 的工具直接讀取本檔。
- Codex Skills 位於 `.agents/skills/`，自訂 Agents 位於 `.codex/agents/`；兩者不是 Claude Markdown Agent 的別名。
- 其他工具若另有指令檔，應維持薄入口並避免重複整套規則。

## 來源

{PROJECT_CONVENTION_EVIDENCE}
