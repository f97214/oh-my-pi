---
name: bootstrap-ai-project
description: 以交易式流程為既有或新專案建立來源可追溯的 README、AGENTS.md、CLAUDE.md 與專案文件，並可選擇設定 Claude／Codex Skills、Agents、共用治理、Hooks 與 Spectra TDD。當使用者明確要求初始化專案、建立跨 AI 協作規範或完整 bootstrap 時使用。
---

# Bootstrap AI Project

以單一入口完成文件與可選治理設定。預設只撰寫文件；除非使用者明確選擇完整模式，否則不得建立 Rules、Hooks、Agents、Spectra 設定或執行依賴命令。

## 不可違反的界線

- 只處理使用者指定或確認的單一 target。Monorepo 不得自行選第一個專案。
- 嚴格依序執行 `Discover → Decide → Preview → Apply → Verify`。
- Apply 前不得修改 target 的 repo tracked files。
- 不讀取真實 `.env`、credentials、私鑰或 secret 檔內容。
- `.env.example` 與 `.env.sample` 只能由 bundled script 抽取鍵名；不要把原始內容帶入上下文。
- 所有重要文件結論必須附來源路徑；無法確認時標記「未確認」。
- 不覆蓋使用者自訂內容。無法證明安全可合併時標記衝突並要求人工處理。
- 不代為安裝 Plugin。測試依賴只有在精確預覽後取得第二次確認才可執行。
- 不產生舊版測試流程、額外 SDD 預檢或平行 TDD 指令。
- 祕密掃描是第二層防護，不得宣稱能保證沒有機密外洩。

## Bundled resources

執行前依階段讀取下列 reference，不要一次載入全部：

| 階段 | 必讀 reference |
|---|---|
| Discover | [references/discover.md](references/discover.md) |
| Decide、Preview | [references/decide-preview.md](references/decide-preview.md) |
| Apply 文件 | [references/apply-docs.md](references/apply-docs.md) |
| Apply governance | [references/apply-governance.md](references/apply-governance.md) |
| Apply Spectra TDD | [references/apply-spectra.md](references/apply-spectra.md) |
| Spectra TDD 證據觀測 | [references/tdd-observability.md](references/tdd-observability.md) |
| Apply Code Review 規則 | [references/apply-opencodereview.md](references/apply-opencodereview.md) |
| Plugin 建議 | [references/apply-plugins.md](references/apply-plugins.md) |
| Verify、摘要 | [references/verify-summary.md](references/verify-summary.md) |

低容錯操作必須呼叫 bundled CLI：

```text
scripts/bootstrap.py   # Python 3.10+，首選
scripts/bootstrap.mjs  # Node.js 18+，fallback
```

兩者提供 `discover`、`render-roles`、`plan`、`scan`、`apply`、`verify`。`render-roles` 只能從 canonical role contracts 確定性產生宿主檔案，禁止由模型改寫角色內容。使用 `--request <temp-json>` 傳入請求；不要把含生成文件全文的 request 放在 target repository。Python 可用時使用 Python，否則使用 Node；不要在同一次正式 Apply 混用兩個 runtime。

`request.target` 可直接使用路徑字串，或使用依序辨識 `selected_root`、`path`、`repo_root`、`root` 的 object；`root` 僅保留舊版相容性。兩個 runtime 必須輸出相同的 canonical Windows 長路徑。

## Stage 1：Discover

1. 將使用者提供的路徑正規化為 target；未提供時以目前 repository 為候選。
2. 若偵測到多個可獨立建置的專案，先列出路徑與證據，要求使用者選擇一個。
3. 執行 bundled `discover`，取得技術棧、測試 profile、Spectra、OpenSpec、治理檔、env 鍵名與 evidence。
4. 深讀選定 target 的入口、manifest、設定 schema、測試與重要整合點；遵守 inventory 排除清單。
5. 將結論與來源存入記憶體中的 `run_config.discovery`。
6. 此階段只讀，不詢問可由 repository 證據回答的問題。

## Stage 2：Decide

先取得所有會影響內容的決策：

1. 模式：
   - **只撰寫文件（預設）**：README、AGENTS.md、CLAUDE.md、docs。
   - **完整 Bootstrap**：文件，加上使用者逐項選擇的 settings、Rules、Hooks、Agents、Spectra TDD 與 Plugin 建議。
2. 宿主：`claude`、`codex` 或兩者；預設兩者。未選宿主不得產生其專屬入口。
3. AI 設定目錄的 Git 策略：團隊追蹤或個人忽略。
4. 完整模式逐角色詢問 `Disabled`／`Skill`／`Agent`／`Both`：`implementer`、`test-engineer`、`doc-writer`、`git-commit`。Skill 在主線程由使用者直接呼叫；Agent 使用隔離上下文並回報主代理。`git-commit` 只能 manual-only。
5. 完整模式才詢問其他 governance 選項；逐項選擇，不使用含糊套餐。Rules 至少包含「測試 Rule」、「ADR 契約 Rule」、「詞彙表 Rule」與「工程紀律 Rule」四個獨立項目；Hooks 至少包含「驗證閘門」與「宣稱證據」兩個獨立項目（後者的兩支腳本為單一 operation，不可拆開安裝）。未被選取者不建立。
6. 完整模式才詢問 Spectra TDD「啟用／跳過」。
7. 使用者要求啟用 Spectra TDD，且測試 profile 並非 `unavailable` 時，才詢問獨立的 `tdd_observability` 決策：固定 profile 為 `rules-and-hook`／`change-report`／`task-summary`／`red-green-required`；即使一般 Hooks 未選取，也必須另行 Preview 與確認。只有 Apply 與 Verify 完成後才能將 observability effective 設為 true。
8. 完整模式且 `discovery.stacks` 非空時，才詢問「Code Review 規則」是／否，預設否。選是則產生 `.opencodereview/rule.json`；它是產出不是 Rule，不取代任何 Rule，也不構成安裝 `ocr` 的同意。
9. 依賴補建需要另行確認，初始狀態一律是 `pending`。

把答案寫入 `run_config.decisions`，再衍生：

- `spectra_tdd.requested`
- `spectra_tdd.effective`
- `hosts`：依 `claude`、`codex` 固定順序正規化。
- `roles.<role>.surfaces`：`[]`、`[skill]`、`[agent]` 或 `[skill, agent]`。
- `tdd_observability`：僅在 Spectra TDD effective 時可建立；記錄選取的觀測項目與實際 setup 結果。
- `test_profile.source`：`existing`、`planned-bootstrap`、`bootstrapped`、`unavailable`
- `commit_patterns_source: skill-policy`

Apply 後不得再改變這些決策。

## Stage 3：Preview

1. 先在記憶體或 Skill 專用暫存目錄生成內容。
2. 以 bundled `render-roles` 產生角色 operations；不要手寫或重述 canonical instructions。
3. 使用 bundled `scan` 掃描每份生成內容；阻擋項不得進入 plan。
4. 以 bundled `plan` 計算 create、update、skip、conflict、command、前後雜湊與 `plan_sha256`。
   `plan_sha256` 必須綁定 canonical target、公開 operations、祕密例外清單與 bundled policy digest。
5. 向使用者顯示：
   - 選定 target 與模式
   - 每個檔案的動作與精簡差異
   - 未確認的文件結論
   - 會執行的完整命令與驗證方式
   - 衝突、跳過與不會碰觸的既有檔案
   - 每個角色依宿主與入口逐檔顯示，例如 Codex Skill、Codex Agent、Claude Skill、Claude Agent
6. 同一角色同一 surface 使用相同 `atomic_group`。其中一個宿主檔存在但缺少 managed marker 時，整個 Skill group 或 Agent group 都標成 conflict；不得只更新另一邊。
7. 若需要依賴補建，依 [references/apply-spectra.md](references/apply-spectra.md) 顯示固定版本、manifest/lockfile 影響、隔離環境與命令，再取得第二次明確確認。
8. 使用者拒絕依賴變更時，設為 `declined`、將 TDD effective 設為 false，重新 plan 並顯示最終預覽。
9. `tdd_observability` 必須以獨立 operation 顯示 observer 建立範圍、可觀察的 lifecycle、報告路徑與限制；它不因一般 Hooks 跳過而隱藏，並須取得該 operation 的明確確認。
10. docs-only、Spectra TDD skip 或 `effective: false` 時，operation 必須為 skip，且不得建立 observer、Hook、證據報告或測試規則。
11. `.opencodereview/rule.json` 以獨立 operation 顯示完整內容、每條規則的 glob 來自哪一項 `confirmed` 證據，以及因目錄不存在而移除的規則。它是 **create-only**：既有檔案一律 conflict，不覆寫也不合併。
12. 取得最終 Apply 確認；確認值必須是當次 `plan_sha256`。

## Stage 4：Apply

1. 以原始 request 與 `--confirm <plan_sha256>` 呼叫 bundled `apply`。
2. 發生雜湊漂移、symlink、破損 managed block、解析失敗或安全阻擋時停止該操作；不得臨場猜測。
3. 文件模式只執行文件操作。
4. 完整模式按依賴順序套用：
   - 文件與 `.gitignore`
   - 共用 `.ai/bootstrap-ai-project/` runtime 與宿主 settings／hooks registration
   - Rules
   - Claude／Codex Skills
   - Claude／Codex Agents
   - 已確認且可驗證的 Spectra TDD
   - 已確認的 TDD evidence observer（僅於 Spectra TDD effective）
   - 已確認的 `.opencodereview/rule.json`
5. Plugin 階段與 Code Review 規則只輸出建議與安裝命令，不執行安裝。
6. 將每個實際結果加入 `run_config.results`。

## Stage 5：Verify

1. 使用 bundled `verify` 回讀所有 planned operations。
2. 重新解析 JSON/YAML、檢查 managed block、Hook schema、腳本編碼與路徑。
3. 寫後再次執行祕密掃描。
4. 只執行 Preview 已列出且使用者已確認的測試命令。
5. 根據 `results` 產生摘要；不要從範例或預期狀態抄值。
6. 未確認、未執行與失敗項目必須明確區分。

## `run_config` 契約

`run_config` 不得寫入 target repository，必須符合 [schemas/run-config.schema.json](schemas/run-config.schema.json)，至少包含：

```text
schema_version = 2
target { repo_root, selected_root, kind, snapshot_sha256 }
discovery { stacks, test_profiles, spectra, openspec, evidence }
decisions { mode, hosts, roles.<role>.surfaces, git_strategy, spectra_tdd, tdd_observability, dependency_execution, ... }
derived { hosts, spectra_tdd, tdd_observability, test_profile, commit_patterns_source }
operations[]
results[]
```

每個 operation 都要帶 `before_sha256`。Apply 必須以相同 target、policy 與例外清單重新計算 plan；不相同即回到 Discover／Preview，確認 hash 不得跨 target 重用。

## CLI 結束碼

| Code | 意義 | 行為 |
|---:|---|---|
| 0 | 成功或非阻斷警告 | 繼續並記錄結果 |
| 2 | 安全政策阻擋 | 不寫入受影響檔案 |
| 3 | 解析／驗證失敗 | 不寫入，回報格式問題 |
| 4 | 衝突、漂移或需要決策 | 回到 Discover／Preview |
| 64 | 參數錯誤 | 修正呼叫方式 |
| 1 | 內部錯誤 | 停止 Apply 並保留證據 |

## 相容性

- Claude Code 的 `.claude/skills/bootstrap-ai-project/SKILL.md` 只保留為薄入口；共同核心不得複製回該目錄。
- 辨識並沿用舊 `.gitignore` managed marker，避免建立第二組區塊。
- 不主動刪除既有專案中的舊測試流程文件、Copilot 指令檔或其他使用者內容。
- 不建立 `CODEX.md`，也不把 Claude Agent Markdown 當成 Codex Agent。
- 既有 `.spectra.yaml`、settings、Rules、Hooks、Skills 與 Agents 只有在通過 parse、預覽與確認後才可修改。
- 文件內不得留下 `{{PLACEHOLDER}}`、條件標記或未展開的模板片段。
