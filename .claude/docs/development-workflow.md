# 開發流程（SDD + Spectra TDD）

本流程整合 Spectra（SDD）與 TDD；Codex 由 `$bootstrap-ai-project`、Claude 由 `/bootstrap-ai-project` 初始化，再由各宿主原生的 `spectra-*` Skills 驅動。

> **2026-08-13 更新（二）**：評估 alibaba/open-code-review（Apache-2.0）後，於階段 3 新增可選的程式碼審查段落，並讓 `/bootstrap-ai-project` 完整模式可選擇產出 `.opencodereview/rule.json`——把 `engineering.md` 第 2、3 節與 `adr.md` 中能由 diff 檢出的部分翻成 path-scoped 審查規則。採 delegate 模式（`ocr` 只做確定性的檔案選取與規則解析，判讀由 agent 自己的模型執行），不需要額外的 LLM endpoint。明訂不得寫進 `verify-gate.json`。

> **2026-08-13 更新**：評估 humanlayer/12-factor-agents 後只做精選撈取（該文件面向 LLM runtime 架構，與本流程不同層，13 條因子中多數不適用或已有等價機制）——`engineering.md` 新增第 5 節「升級給人的格式與迴圈上限」與第 6 節「Context 工程」，並新增「先判斷這件事要走到多深」任務分級章節（概念參考 humanlayer 的 ACE-FCA 與 WSFF，未引用原文）。

> **2026-08-09 更新**：Bootstrap 共同核心移至 `.agents/skills/bootstrap-ai-project/`，新增 Claude／Codex 四角色的 Skill／Agent 雙入口、schema v2、跨宿主原子衝突處理，以及 `.ai/bootstrap-ai-project/` 共用 Hook runtime。

> **2026-08-06 更新**：全面改寫以反映現況——
> - `tf-*` 系列（舊軌道 B）已於 a94e748 移除，TDD 只剩單一模式：內嵌於 `/spectra-apply` 的 Spectra TDD（`.spectra.yaml: tdd: true` 啟用）
> - `/init-project-docs` 已升級為 `/bootstrap-ai-project`（交易式 Discover → Decide → Preview → Apply → Verify）
> - 新增測試證據觀測層（fbbba0c）：`.claude/rules/testing.md` 契約 + test-observer Hook + `test-evidence.md` 報告
> - 新增 `/grill`（需求訪談＋領域建模）與 `/handoff`（session 交接），改編自 mattpocock/skills
> - 原 `sdd-preflight.md`（tf-* 專用共用片段）已併入本文件「統一規則」後移除
> - 補上 ADR 閉環：新增 `.claude/rules/adr.md` 契約（讀取端＋兩個檢查點）、`docs/adr/README.md` 索引與 supersede 程序
> - 補上詞彙表閉環：新增 `.claude/rules/glossary.md` 契約，讓 `CONTEXT.md` 在實作期被實際讀取與遵守
> - repo 自身補上 `README.md` / `AGENTS.md` / `CLAUDE.md` / `.gitignore`，並新增 `.claude/tools/lint_skills.py` 通用 skill lint
> - 補上四項工程空白（改寫自 addyosmani/agent-skills，MIT）：`.claude/rules/engineering.md`（對抗審查／介面契約／可觀測性）與「發布與汰除」章節
> - 新增 `walkthrough.md` 實例走查與 `.claude/tools/build_docs.py`，由本檔與各 `SKILL.md` 產生說明網頁 `index.html`（產生物，勿手動編輯）
> - 新增收工閘門 Hook（概念改寫自 agentcrew-academy/harness-starter-kit，MIT）：`verify-gate.py` 與 `claim-ledger.py`＋`claim-guard.py`，見統一規則 J；並新增 `/first-principles` skill
> - 第二輪撈取 addyosmani/agent-skills：`engineering.md` 新增第 4 節「以官方文件為準」，兩份 `AGENTS.md` 的分支章節擴為完整 Git 工作流

---

## 完整流程總覽

```
需求模糊 → /grill（分輪訪談＋沉澱 CONTEXT.md / ADR）
需求清楚 ─────────────┐
                      ↓
   /spectra-propose → /spectra-apply → spectra analyze → /spectra-archive
     ▲ ADR 檢查點①    （內嵌 TDD）                        ▲ ADR 檢查點②
     design 收斂後                                        歸檔前回收
                                                                ↓
                                              數個 change 累積後 → 發布與汰除
                                                        （人主導，不編號）
換手/收工 → /handoff
```

ADR 檢查點由下游專案的 `.claude/rules/adr.md` 契約驅動，詞彙表紀律由 `.claude/rules/glossary.md` 驅動——兩者都不修改 `spectra-*` Skill。開工前先讀 `CONTEXT.md` 與 `docs/adr/README.md`，詳見「統一規則 F、G」。

### Bootstrap 雙宿主角色入口

完整模式預設選 Claude＋Codex，並逐角色決定 Disabled／Skill／Agent／Both：

| 角色 | Skill 直接入口 | Agent 隔離入口 |
|---|---|---|
| `implementer` | `$implementer`／`/implementer` | 主代理依名稱委派 |
| `test-engineer` | `$test-engineer`／`/test-engineer` | 主代理依名稱委派 |
| `doc-writer` | `$doc-writer`／`/doc-writer` | 主代理依名稱委派 |
| `git-commit` | `$git-commit`／`/git-commit`，只能明確呼叫 | 主代理只能在使用者已要求 commit 時委派 |

Codex Skills 產生在 `.agents/skills/<role>/`，Claude Skills 在 `.claude/skills/<role>/`；Codex Agents 是 `.codex/agents/<role>.toml`，Claude Agents 是 `.claude/agents/<role>.md`。四者都直接內嵌同一份 canonical instructions，不要求代理再讀另一個角色檔，也不硬編模型或權限。

Codex 的 project Skills、Agents 與 Hooks 只有在專案受信任後載入；新增入口後以新 task/session 驗證 discovery。舊 task 的 skill metadata 不會保證熱更新。

Skill 在目前主線程執行；Agent 使用隔離上下文後回報主代理。主代理始終保留需求、架構、公開介面、整合、驗證與最終輸出所有權。同一 checkout 只允許一個 writer，唯讀 Agent 才可平行。

同一角色同一種入口是跨宿主原子群組：若任一既有檔缺少 managed marker，Claude 與 Codex 的該組入口全部標為 conflict，不會只更新一邊。Spectra 雙宿主初始化固定使用 `spectra init <target> --tools claude,codex`，產生的 `.agents/skills/spectra-*` 與角色 Skills 共存。

輔助指令（任何階段可用）：

| 指令 | 用途 |
|------|------|
| `/grill` | 決策樹分輪訪談釐清需求，同步維護 `CONTEXT.md` 詞彙表與 `docs/adr/` |
| `/spectra-discuss` | 針對單一主題聚焦討論並收斂結論 |
| `/spectra-ask` | 查詢 `openspec/` 文件回答問題 |
| `/spectra-ingest` | 用外部脈絡更新既有 change |
| `/spectra-debug` | 四階段系統化除錯 |
| `/spectra-audit` | 審查危險預設值、型別混淆、靜默失敗 |
| `/spectra-commit` | 提交特定 change 相關檔案 |
| `/handoff` | 把對話濃縮成交接文件（存 OS temp，不進工作區） |

---

## 先判斷這件事要走到多深

不是每個改動都值得走完整條流程。把一個改字串的工作硬拆成 15 個 task，結果是下次沒人願意走流程——**規範被繞過的主因是它對小事太重，不是對大事太輕**。

| 規模 | 判斷依據 | 走法 |
|---|---|---|
| 小 | 單一檔案、行為明確、可直接驗證 | 直接做，不開 change。專案 `AGENTS.md` 的驗證要求照跑 |
| 中 | 跨數個檔案但不動架構、不改對外介面 | `/spectra-propose` 走到 `design.md` 收斂即可，不必硬湊任務數 |
| 大 | 跨模組、不可逆、動到對外介面或資料結構 | 完整流程：`/grill` → `propose` → `apply` → `analyze` → `archive` |

**分級是使用者的決定，AI 不自行降級。** 判斷不確定時往上一級走，或直接問；把大事誤判成小事的代價，遠高於把小事誤判成大事。

拆 `tasks.md` 時**照垂直切片拆，不要照水平分層拆**：每個 task 應該是一條可獨立驗證的窄路徑（從入口到落地），而不是「先把所有 repository 寫完，再寫所有 service」。水平拆法要到最後一層合起來才知道對不對，前面所有 task 的「完成」都是空的。

---

## 階段 0 — 需求釐清（可選）

需求還模糊時先跑：

```
/grill <要釐清的題目>
```

以決策樹分輪提問（每題附建議答案），事實由 AI 自查、決策留給你；術語敲定即寫入 `CONTEXT.md`，重大取捨寫 ADR。訪談結論直接作為下一階段的輸入。已想清楚的需求可跳過，或改用 `/spectra-discuss` 做輕量討論。

## 階段 1 — 規格提案（SDD 起點）

```
/spectra-propose <feature>
```

產出並自動 park：

```
openspec/changes/{feature}/
├── proposal.md   # Why / What Changes / Impact
├── design.md     # 架構、資料流、API、DB 設計
├── tasks.md      # 可執行任務清單（- [ ]）
└── specs/<capability>/spec.md  # Requirement + Scenario（GIVEN/WHEN/THEN）
```

流程內建：placeholder 自查、內部一致性檢查、scope 檢查（>15 tasks 建議拆分）、`spectra analyze` 修正迴圈（最多 2 輪）、`spectra validate`。完成後 change 處於 parked 狀態，`/spectra-apply` 時自動詢問 unpark。

## 階段 2 — 實作（內嵌 TDD）

```
/spectra-apply <feature>
```

單一指令完成整個實作循環：

1. 選定 change → `spectra in-progress add`（idempotent、自動處理 unpark、啟動 `.spectra/touched/` 追蹤）
2. **Preflight**：檢查 artifacts 引用的檔案是否漂移／遺失（CLI `preflight` 欄位）
3. **Artifact 品質檢查**：`spectra analyze` 有 Critical 發現時先修再做
4. 讀取 contextFiles（proposal / design / spec / tasks）
5. 讀 `.spectra.yaml` 決定紀律（見下表）
6. 對每個 `- [ ]` task：
   - **Red**：先寫失敗測試——測試值**取自 spec.md 的 `##### Example:` 區塊**，不自行發明
   - **Green**：不違反 `design.md` 架構的最小實作；不得超出 spec Scenario
   - **Refactor**：測試持續通過下改善品質（不得跨層搬遷）
   - 完成即呼叫 `spectra task done --change "{feature}" <task-id>`（同時勾 checkbox + 寫 `.spectra/touched/`）
7. 全部完成後確認 `state: "all_done"`，建議 archive

### `.spectra.yaml` 旗標

| 旗標 | 效果 |
|------|------|
| `tdd: true` | 每個 task 跑 Red-Green-Refactor；TDD 細則由 `spectra instructions --skill tdd` 動態載入 |
| `audit: true` | 實作全程套用 sharp-edges 紀律（三種對抗視角、安全預設值、型別混淆檢查） |
| `parallel_tasks: true` | tasks.md 中連續 `[P]` 標記的 task 以平行 agent 派發 |

## 階段 3 — 完整性驗證

```
spectra analyze {feature} --json
```

驗證 Coverage（每個 Requirement 有對應實作）、Consistency（design 與 spec 一致）、Ambiguity / Gaps。結果由 CLI 直接輸出（JSON 可解析），不產生獨立報告檔。

### 程式碼審查（可選）

`spectra analyze` 驗的是**規格完整性**——每個 Requirement 有沒有對應實作、design 與 spec 一不一致。它不看程式碼本身寫得對不對。兩者不重疊，也不互相取代。

補這一段的可選工具是 [open-code-review](https://github.com/alibaba/open-code-review)（`ocr`）的 delegate 模式：

```bash
ocr delegate preview --format json          # 決定審哪些檔案、排除哪些
ocr delegate rule --format json <paths...>  # 解析每個檔案套用哪些規則
```

`ocr` 只做確定性的部分——檔案選取、相關檔案捆綁成審查單元、規則比對；**實際判讀由 agent 用自己的模型執行，不需要另外設定 LLM endpoint**。這個分工正是統一規則所依據的「確定性工作交給程式」：路由與比對用程式，判讀用模型。

專案層規則放在 `.opencodereview/rule.json`，依檔案路徑套用。`/bootstrap-ai-project` 完整模式可選擇產出一份，內容取自 `engineering.md` 第 2、3 節與 `adr.md` 中**能由 diff 檢出**的部分。`ocr rules check <file>` 不需要 LLM 就能確認某個檔案命中哪些規則。

三條界線：

1. **不得寫進 `verify-gate.json`。** 收工閘門不可相依外部 CLI——`ocr` 沒裝時整個閘門會失效。跑不跑、理不理它的發現，都是人的決定。
2. **它不是機械強制。** `rule` 欄位是自然語言，判斷仍由模型做，與驗證閘門（只看退出碼）本質不同。需要嚴謹證據鏈時仍要靠 Spectra TDD 的 test-observer。
3. **規則命中可證明，判斷結果不可當作已驗證事實。** `ocr rules check` 證明的是「這條規則套用到這個檔案」，不是「這個檔案沒問題」。

採納它的覆蓋率自查紀律：每個 previewed 檔案都要標為已審，或明確寫出跳過原因——這是本流程原本沒有的，過去沒有任何機制確保 review 沒漏檔。

## 階段 N — 歸檔

```
/spectra-archive <feature>
```

- spec snapshot + delta 套用到 `openspec/specs/<capability>/spec.md`
- **@trace injection**（依賴 `.spectra/touched/<feature>.json`，由前面 `spectra task done` 累積）
- identity recording / vector indexing
- 將 `openspec/changes/{feature}/` 移到 `openspec/changes/archive/YYYY-MM-DD-{feature}/`

---

## 發布與汰除（歸檔之後）

本節不編號——發布不是每個 change 都要做一次，通常是數個 change 累積後一起上線。它由**人主導**：推進與回滾是你的決定，不是 AI 的。方法論改寫自 [addyosmani/agent-skills](https://github.com/addyosmani/agent-skills)（MIT）。

### 上線前檢查清單

依專案性質取用，不適用的整組跳過。

**程式品質**：測試全通過；建置無警告；lint 與型別檢查通過；沒有該解決卻留著的 TODO；沒有除錯用的輸出殘留；預期的失效模式都有錯誤處理。

**安全**：程式與版控中沒有祕密；相依套件稽核無高風險項目；對外端點都有輸入驗證；認證與授權檢查到位；認證端點有速率限制。

**效能**：關鍵路徑沒有 N+1 查詢；資料庫查詢有對應索引；重複查詢與靜態資源有快取。

**基礎設施**：正式環境的環境變數已設定；資料庫遷移已套用或已備妥；log 與錯誤回報已接好；健康檢查端點存在且會回應。

**文件**：README 反映新的安裝需求；對外介面文件為最新；本次的架構決策已寫成 ADR；變更紀錄已更新。

前端專案另需檢查 Core Web Vitals、圖片最佳化、bundle 大小、鍵盤操作、螢幕閱讀器、色彩對比（WCAG 2.1 AA）與焦點管理。純後端服務、排程與 gateway 不適用這組。

### 分階段推出

```
staging（完整測試 + 手動煙霧測試）
  → 正式環境部署，功能旗標關閉（先確認部署本身沒問題）
  → 開給內部使用者，觀察 24 小時
  → 5% 使用者，觀察 24–48 小時
  → 25% → 50% → 100%，每一階都觀察
  → 全量後觀察一週，再清掉功能旗標
```

每一階用同一組門檻判斷：

| 指標 | 推進 | 停下來查 | 回滾 |
|---|---|---|---|
| 錯誤率 | 在基準的 10% 以內 | 高於基準 10–100% | 超過基準兩倍 |
| p95 延遲 | 在基準的 20% 以內 | 高於基準 20–50% | 惡化超過 50% |
| 業務指標 | 持平或變好 | 下滑 5% 以內 | 下滑超過 5% |

### 回滾

**部署前就要寫好**：觸發條件、實際步驟（關旗標或重新部署前一版）、回滾後的驗證方式、資料庫遷移該怎麼處理、預計需要多久。

錯誤率超過基準兩倍、p95 延遲惡化逾五成、發現資料完整性問題或安全漏洞——立即回滾，不要先討論。回滾是負責任的工程行為，把壞掉的功能留在線上才是失敗。

### 汰除舊功能

決定要不要汰除前先回答：它還有無可取代的價值嗎？有多少消費者依賴它？替代品存在嗎？每個消費者的遷移成本多少？**不汰除**的持續維護成本又是多少？

- **預設採建議性汰除**——給警告、文件與替代方案，讓使用者按自己的節奏遷移。
- 只有在舊系統有安全問題、阻擋進度，或維護成本已不可持續時，才用**強制性汰除**：給硬期限，並提供遷移工具。
- 順序固定：替代品先做好並在正式環境驗證過 → 公告汰除時程與遷移指南 → 逐一遷移消費者並確認行為一致 → **用指標或 log 確認零使用後**才移除程式、測試、文件與設定。

**資料庫結構一律三段式**：

```
擴充 → 遷移 → 收縮
新增可為空的欄位   回填既有資料、雙寫   另一次部署才刪掉舊欄位
```

絕不原地改名，也絕不在同一次部署裡既新增又刪除——推出期間新舊程式會同時在跑，其中一邊會查到不存在的欄位。遷移一定要寫好並測過回復路徑才能合併。

---

## 測試證據觀測層（可選，由 `/bootstrap-ai-project` 完整模式建立）

在 `spectra_tdd.effective: true` 且使用者於獨立 Preview 確認後，bootstrap 會在下游專案建立：

| 元件 | 作用 |
|------|------|
| `.claude/rules/testing.md` | 測試證據契約（帶 `bootstrap-ai-project:tdd-observability` marker） |
| `.ai/bootstrap-ai-project/hooks/test-observer.py`（或 `.mjs`） | 觀察已選宿主支援的 lifecycle，把 allowlist 內正式測試命令的實際結果整理為 evidence |
| `.ai/bootstrap-ai-project/tdd-observer.json` | 共用 observer 設定：framework、正式命令 allowlist、機密遮蔽規則 |
| `openspec/changes/{feature}/test-evidence.md` | 每個 change 的永久測試證據報告（由 Rule 建立，observer 提供觀測資料） |

重點界線：

- observer **只觀察、不執行測試**，不能把 agent 的敘述升格為已驗證事實
- 只有 description 完全符合 `TDD Red: task=<id>; evidence=<key>`（Green / Refactor 同格式）的 allowlist 命令才算 evidence
- compound command（含 `&&`、`|`、redirect 等）一律忽略，不作 evidence
- 細節見 `.agents/skills/bootstrap-ai-project/references/tdd-observability.md`

---

## 統一規則（原 sdd-preflight.md 併入）

### A. Spectra CLI 失敗處理

任何 `spectra` 指令回報 `command not found` 或非 0 退出碼時：**立即停止流程並回報錯誤輸出**。不可靜默忽略、不可改用 Edit 繞過、不可累積到最後再處理——否則 archive 會缺 trace 資料而失敗。

### B. tasks.md 同步規則

- 完成 task **必須**呼叫 `spectra task done --change "{feature}" <task-id>`（同時勾 checkbox + 寫 `.spectra/touched/`）
- **每完成一個 task 立即呼叫，不得累積批次處理**
- **禁止直接 Edit `tasks.md` 的 checkbox**
- 不使用任何外部 task 管理工具——tasks.md 是唯一進度來源

### C. SDD 文件唯讀規則

實作階段不得修改 `spec.md`、`design.md`、`proposal.md`、`tasks.md` 內容。需修改規格**必須回到 `/spectra-propose` 修訂**（或用 `/spectra-ingest` 帶入外部脈絡），不可在實作中自行調整。

### D. 衝突處理

測試與 `spec.md` 衝突時：**停止並回報**，由使用者決定修改測試或修訂規格。AI 不可自行選邊、不可自行降低測試標準。

### E. 不得超出規格

不得實作超出 `spec.md` Requirement / Scenario 的功能；Refactor 不得改變 `design.md` 規定的架構分層、資料流、模組職責。

### F. 詞彙表（CONTEXT.md）

`CONTEXT.md` 是領域術語的單一事實來源，由 `/grill` 沉澱。三條紀律：

1. **讀取義務**——建立提案或開始實作前先讀（不存在則跳過）。
2. **沿用 canonical term**——型別、函式、變數與 spec 用語照詞彙表寫；列在 `_避免_` 底下的講法不得出現在新程式碼。
3. **衝突停止**——使用者用語、程式碼現況與詞彙表定義矛盾時停止並回報，不自行選邊、不默默引入同義詞。

執行機制在下游專案的 `.claude/rules/glossary.md`，格式定義見 `grill/CONTEXT-FORMAT.md`。

### G. 架構決策紀錄（ADR）

`design.md` 是單一 change 的設計，會隨 change 歸檔；ADR 是脫離 change 生命週期的長期約束。三條紀律：

1. **讀取義務**——建立提案或開始實作前，先讀 `docs/adr/README.md` 索引（不存在則跳過）。
2. **衝突停止**——與 `accepted` 狀態的 ADR 衝突時停止並回報，由使用者決定修訂提案或以新 ADR supersede，AI 不可自行選邊。
3. **不可刪改**——supersede 只能標記舊 ADR 狀態並新增取代者，不得刪除或改寫既有決策內容。

執行機制在下游專案的 `.claude/rules/adr.md`（由 `/bootstrap-ai-project` 完整模式的 Rules 選項建立），不是修改 `spectra-*` Skill。ADR 三條件與 supersede 規則的完整文字見該 Rule 與 `grill/ADR-FORMAT.md`。

### H. 實作期工程紀律

由下游專案的 `.claude/rules/engineering.md` 注入，六節各有適用條件：

1. **非瑣碎決策的對抗審查**——跨模組、不可逆、或宣稱型別系統驗證不了的性質時，寫下 CLAIM、交出「產物＋契約」請求對抗式審查（不給 CLAIM，否則審查者會附和）、分類發現、最多三輪就升級給人。TDD 的 Red 步驟已滿足行為宣稱的懷疑要求。
2. **介面與契約設計**——契約先行、錯誤語意一致、只在邊界驗證、加而不改。
3. **可觀測性**——先寫值班會問的問題再加訊號、結構化 log 加 correlation ID、RED 指標與 p95、只對症狀告警。
4. **以官方文件為準**——定版本 → 抓具體文件頁 → 照文件簽章實作 → 標出處。Stack Overflow、部落格與訓練資料不算主要依據；查不到就明確標為未驗證，不要用模糊免責帶過。
5. **升級給人的格式與迴圈上限**——本文 D、F、G 與該 Rule 各節都會要求「停止並回報」，但沒說要報什麼。升級一次給齊四件事：卡在哪、試過什麼、具體選項 A/B/C 附建議、不決定的後果，並指明回答形式（是非／多選／自由）。同一個失敗連續嘗試三次仍未解決就停下來升級，與第 1 節的三輪門檻同一個數字。
6. **Context 工程**——大範圍探索交給唯讀 subagent，只把結論帶回主線程；每完成一個可驗證階段主動把狀態壓回產物再繼續，不要等宿主的自動壓縮；審查槓桿在理解與計畫，不在逐行 diff。取捨順序固定為正確性 > 完整性 > 精簡度。

`audit: true` 只涵蓋安全面向；本規則涵蓋一般性決策，兩者互補。

### I. 發布與汰除

上線與汰除由人決定，AI 不自行推進階段、不自行回滾。門檻、分階段順序與資料庫三段式遷移見「發布與汰除（歸檔之後）」章節。

### J. 收工閘門（由 Hook 強制）

前面 A–I 都是文字約束，靠 agent 記得遵守。兩個 `Stop` hook 把其中最容易被忽略的部分變成機械強制：

1. **驗證閘門**（`verify-gate.py`）——SessionStart 記錄 HEAD 與工作區 fingerprint；Stop 合併本 session 的未提交與已提交路徑，再跑 `.ai/bootstrap-ai-project/verify-gate.json` 列出的驗證命令，成功才更新 checkpoint；SessionEnd 清除暫存狀態。只看退出碼，不比對輸出樣式；`paths` 可避免無關慢測試，checkpoint 缺失或損壞時保守全跑；連續三次未過就放行並要求如實告知。
2. **宣稱證據**（`claim-ledger.py` + `claim-guard.py`）——記錄執行過的 `test`／`check`／`search` 類命令，收工時比對訊息中的宣稱是否有對應紀錄。沒跑測試就說「測試通過」會被擋。

**這兩個是防呆不是防駭**：宣稱檢查靠關鍵字，換個說法就繞得過去，也不驗證宣稱與紀錄是否真的對應。它們擋的是疏忽。需要嚴謹證據鏈時仍要靠 Spectra TDD 的 test-observer。

共用 scripts 與 config 位於 `.ai/bootstrap-ai-project/`。Claude 由 `.claude/settings.json`、Codex 由可信任專案的 `.codex/hooks.json` 註冊同一組 runtime；宿主設定格式不同，不共用同一份 registration 檔。

---

## Spectra UI 灰色 checkbox 的處理

若 Spectra app 顯示某 change 的 task checkbox 為灰色（disabled），代表 UI 層因 assignee 等原因將此 change 視為唯讀。**此時改用 CLI 補勾**：

```bash
spectra task done --change <feature> <task-id>
```

CLI 直接寫入 `tasks.md` 與 `.spectra/touched/<feature>.json`，不受 UI 權限限制。永遠優先使用 CLI——它才是唯一同時更新 checkbox 與 trace 資料的合法路徑。

---

## 與官方 Plugin 的互動點

`/bootstrap-ai-project` 的 Plugin 階段**只輸出建議、不代為安裝**（見 `references/apply-plugins.md`）。plugin 是輔助工具，不取代 spec.md 合約——若 plugin 建議的修改違反 `design.md`，仍應拒絕。

| 流程階段 | 可用 plugin | 邊界 |
|---------|-----------|------|
| 階段 2 實作 | `*-lsp`（typescript-lsp / pyright-lsp 等） | 型別檢查與 navigation，不影響 spec 合約 |
| 階段 2 Refactor 子步驟 | `code-simplifier`、`code-modernization` | 採納前必須重跑測試；不得跨層搬遷 |
| 階段 3 驗證 | `code-review` | 補通用品質審查，不取代 `spectra analyze` |
| 歸檔後 | `commit-commands`、`github` / `pr-review-toolkit` | 產生 commit / PR；task 完成標記仍須走 `spectra task done` |

---

## 產出檔案總覽

| 檔案 | 由哪個指令產生 / 更新 |
|------|---------------------|
| `CONTEXT.md` | `/grill`（術語敲定時 lazy 建立） |
| `.claude/rules/glossary.md` | `/bootstrap-ai-project`（完整模式選取詞彙表 Rule） |
| `.claude/rules/engineering.md` | `/bootstrap-ai-project`（完整模式選取工程紀律 Rule） |
| `.agents/skills/<role>/`、`.claude/skills/<role>/` | `$bootstrap-ai-project`／`/bootstrap-ai-project`（角色選 Skill 或 Both） |
| `.codex/agents/<role>.toml`、`.claude/agents/<role>.md` | `$bootstrap-ai-project`／`/bootstrap-ai-project`（角色選 Agent 或 Both） |
| `.ai/bootstrap-ai-project/hooks/`、`verify-gate.json` | `$bootstrap-ai-project`／`/bootstrap-ai-project`（共用 Hook runtime） |
| `.opencodereview/rule.json` | `$bootstrap-ai-project`／`/bootstrap-ai-project`（完整模式且偵測到應用程式碼時選取；**create-only**，既有檔案不覆寫） |
| `.claude/settings.json`、`.codex/hooks.json` | 各宿主的 Hook registration |
| `docs/adr/NNNN-*.md` | `/grill` 訪談中、`design.md` 收斂後、歸檔前回收——三條件成立時 lazy 建立 |
| `docs/adr/README.md` | ADR 索引，第一份 ADR 出現時建立；每次新增或改狀態當場更新 |
| `.claude/rules/adr.md` | `/bootstrap-ai-project`（完整模式選取 ADR 契約 Rule） |
| `openspec/changes/{feature}/proposal.md`、`design.md`、`specs/<capability>/spec.md` | `/spectra-propose` |
| `openspec/changes/{feature}/tasks.md` | `/spectra-propose` 建立、`spectra task done` 勾選（**禁止直接 Edit**） |
| `.spectra/touched/{feature}.json` | `spectra task done` 自動寫入（archive 的 @trace 來源） |
| `openspec/changes/{feature}/test-evidence.md` | 測試證據觀測層啟用時，`/spectra-apply` 過程中依 Rule 建立 |
| `openspec/changes/archive/YYYY-MM-DD-{feature}/` | `/spectra-archive` |
| `openspec/specs/<capability>/spec.md`（主規格） | `/spectra-archive` 同步 delta |
| `.spectra.yaml` | `/bootstrap-ai-project`（完整模式、Spectra TDD 確認後） |

---

## 維護提醒：需要同步的雙寫點

兩組規則各自存在於兩處，改動時必須一併更新：

| 規則 | 訪談當下使用 | 佈署到下游專案 |
|---|---|---|
| ADR 三條件、格式範本、supersede | `grill/ADR-FORMAT.md` | `.agents/skills/bootstrap-ai-project/templates/rules/adr.md` |
| 詞彙表格式與收錄規則 | `grill/CONTEXT-FORMAT.md` | `.agents/skills/bootstrap-ai-project/templates/rules/glossary.md` |

無法合併成單一檔案：下游專案不會有 grill skill 的檔案可以引用，Rule 必須自含全文。真正要求逐字一致的內容以 `shared-contract:adr`／`shared-contract:glossary` markers 圈選，並由 `.claude/tools/tests/test_shared_contracts.py` 自動阻擋漂移。
