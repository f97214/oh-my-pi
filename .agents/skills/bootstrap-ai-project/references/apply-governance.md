# Apply：Governance、Rules、Hooks、Agents

## 目錄

- [共同原則](#共同原則)
- [Settings](#settings)
- [Rules](#rules)
- [Hooks](#hooks)
- [Agents](#agents)

## 共同原則

本 reference 只在完整模式且使用者至少選擇一項治理功能時讀取。

- 只建立明確選取的項目。
- JSON 與 `.gitignore` 必須由 bundled CLI 合併。
- 既有檔無法解析時 fail closed，不以文字拼接修復。
- `AGENTS.md` 是共同規範來源；`CLAUDE.md` 只用 `@AGENTS.md` 匯入，不複製全文。
- Claude 與 Codex 的原生 schema 分開產生，不建立 `CODEX.md`。

## Settings

安全合併 `.claude/settings.json`：

- 保留未知欄位。
- 既有 `env` 同名值不覆蓋；只補缺漏鍵。
- UTF-8 env 依平台處理：
  - Windows 可設定 `PYTHONUTF8=1`、`PYTHONIOENCODING=UTF-8`、`DOTNET_CLI_UI_LANGUAGE=zh-TW` 等實際需要的鍵，但不寫不支援的 sandbox。
  - macOS／Linux 可依需求補 `LANG`、`LC_ALL`；macOS 預設以 `en_US.UTF-8` 相容性為先。
- deny 基線包含遞迴刪除、特權提升、push、hard reset、建立／刪除分支與 worktree 等高風險操作。
- 允許清單依實際技術棧最小化，不複製通用大清單。

## Rules

逐項選擇並依實際目錄設定 `paths`。測試 Rule 保留：

1. 先讀既有測試並沿用位置、命名與 helper。
2. 新測試必須被正式測試命令收錄並實際執行。
3. 外部相依以 mock、fake 或可控測試替身隔離。
4. 避免時間、隨機、排序、網路與共享狀態造成脆弱測試。
5. Unit test 不跨越持久化、網路或真實第三方服務邊界。
6. 驗證欄必須指名測試檔與可觀察判準，不只寫「測試通過」。

### ADR 契約 Rule

由 [templates/rules/adr.md](../templates/rules/adr.md) 建立 `.claude/rules/adr.md`，是與測試 Rule 平行的獨立選項。

- 建立條件：完整模式且使用者明確選取。target 已使用 Spectra／OpenSpec 或已存在 `docs/adr/` 時可主動建議，但仍須取得選擇。
- `paths` 依實際目錄設定，至少涵蓋 `docs/adr/**`；target 使用 Spectra／OpenSpec 時加入 `openspec/**`，未使用時不得寫入不存在的路徑。
- 既有 `.claude/rules/adr.md` 沒有 `bootstrap-ai-project:adr` marker 時視為 conflict，不覆寫。
- 本 Rule 只約束 agent 行為，不建立 ADR、不建立 `docs/adr/` 目錄，也不修改 Spectra 的命令、artifact 或狀態。
- 三條件與 supersede 文字必須與 `templates/rules/adr.md` 完全一致；不要在此重述或改寫。

### 詞彙表 Rule

由 [templates/rules/glossary.md](../templates/rules/glossary.md) 建立 `.claude/rules/glossary.md`，同樣是獨立選項。

- 建立條件：完整模式且使用者明確選取。target 已存在 `CONTEXT.md` 或 `CONTEXT-MAP.md` 時可主動建議，仍須取得選擇。
- `paths` 至少涵蓋 `CONTEXT.md`；存在 `CONTEXT-MAP.md` 或多個 context 詞彙表時一併列入，並加上實際原始碼目錄，讓命名紀律在實作時生效。
- 既有 `.claude/rules/glossary.md` 沒有 `bootstrap-ai-project:glossary` marker 時視為 conflict，不覆寫。
- 本 Rule 只約束 agent 行為，不建立詞彙表、不撰寫術語內容。

### 工程紀律 Rule

由 [templates/rules/engineering.md](../templates/rules/engineering.md) 建立 `.claude/rules/engineering.md`，涵蓋四項實作期紀律：非瑣碎決策的對抗審查、介面與契約設計、可觀測性、以官方文件為準。

- 建立條件：完整模式且使用者明確選取。
- `paths` 設為實際原始碼目錄；不要列入文件或設定專用目錄。
- 四節各自帶適用條件，寫在檔案內由 agent 自行判斷，**Preview 不得依 target 性質刪節**——純函式庫專案自然跳過可觀測性節，不用框架的專案自然跳過文件佐證節，不需要為此產生變體檔案。
- 文件佐證節要求抓官方文件。target 已連接 context7 之類的文件 MCP 時可在 Preview 註明；沒有也不影響——該節的替代路徑是直接抓官方文件 URL。
- 既有 `.claude/rules/engineering.md` 沒有 `bootstrap-ai-project:engineering` marker 時視為 conflict，不覆寫。
- 本 Rule 不引入任何函式庫、不指定 logging 或 metrics 實作、不修改既有遙測設定；它只規範怎麼判斷與怎麼寫。
- 內容改寫自 addyosmani/agent-skills（MIT），來源標注在檔案開頭，不得移除。

### Code Review 規則產出

建立 `.opencodereview/rule.json`，把上述 Rules 契約中能由 diff 檢出的部分翻成 path-scoped 審查規則。細節見 [apply-opencodereview.md](apply-opencodereview.md)。

- 建立條件：完整模式、`discovery.stacks` 非空，且使用者明確選取。純文件 target 不提供這個選項。
- 這是**產出**不是 Rule——它不進 `.claude/rules/`，也不取代任何 Rule。Rules 仍照原本的選擇建立。
- **create-only**：既有檔案一律 conflict，不覆寫也不合併。JSON 沒有註解語法可放 managed marker，而自訂鍵相依未經證實的外部行為。
- 不安裝 `ocr`、不執行它、不寫入它的設定；只產生規則檔並在摘要附安裝命令。
- 不得寫進 `verify-gate.json`——收工閘門不可相依外部 CLI。

## Hooks

共用 Hook scripts 與 config 放在 `.ai/bootstrap-ai-project/`，遵守 `policy/hook-policy.json`。Claude 由 `.claude/settings.json` 註冊，Codex 由 `.codex/hooks.json` 註冊；Preview 要分別標示宿主 schema，不得宣稱兩者的 matcher 或事件完全相同。

- 一般 Governance Hook 固定使用無第三方依賴的 `.py` 共用 runtime。Spectra TDD evidence observer 只複製 Preview 已選定的 `.py` 或 `.mjs` 其中一套。
- Claude registration 使用 `command` 加 `args`，將 `${CLAUDE_PROJECT_DIR}` 路徑作為獨立參數；Codex registration 使用官方 command string，只寫固定 executable 與專案相對 `.ai/bootstrap-ai-project/` 路徑。
- `Stop`、`UserPromptSubmit` 等禁止 matcher 的事件不得出現 matcher。
- 條件使用 handler `if`，不放入 shell quoting。
- 註冊時以 `(event, matcher, type, canonical command, args)` 去重。
- `.py`、`.mjs` 使用 UTF-8 without BOM，並在 Windows 上明確設定標準輸入輸出編碼。
- Verify 只做靜態檢查，不觸發 Hook。

Spectra TDD effective 時的 evidence observer 是獨立決策，細節見 [tdd-observability.md](tdd-observability.md)。它即使在一般 Hooks 被跳過時也需要自己的 Preview 與確認；不得把它當成一般 Hooks 已獲得同意，也不得讓它執行或變更測試與 Spectra。

### 驗證閘門 Hook

由 [templates/hooks/verify-gate.py](../templates/hooks/verify-gate.py) 建立為 `.ai/bootstrap-ai-project/hooks/verify-gate.py`，在兩個已選宿主的 `SessionStart`、`Stop`、`SessionEnd` 註冊。SessionStart 記錄 HEAD 與工作區 fingerprint；Stop 驗證本 session 的未提交與已提交變更，未通過即擋下並把失敗內容回饋給 agent；SessionEnd 清理暫存狀態。

- 建立條件：完整模式、使用者明確選取，且**已能指名至少一個真實可跑的驗證命令**。指不出來就不要建立空閘門。
- 同時建立設定檔 `.ai/bootstrap-ai-project/verify-gate.json`，必須符合 [schemas/verify-gate.schema.json](../schemas/verify-gate.schema.json)。命令以陣列形式撰寫，由 hook 直接 spawn，**不經 shell、不使用 eval**。
- 通過與否**只看退出碼**，不比對輸出樣式——退出碼才是命令的契約。
- 每個 check 可用 `paths` 限定觸發範圍；路徑由 NUL-delimited Git 輸出解析，包含本 session 已提交的變更。checkpoint 缺少、損壞或無法判斷變更時一律跑，不靜默跳過。
- 驗證全部成功才更新 checkpoint；失敗時保留原基準，避免下一個 Stop 把尚未通過的變更視為已驗證。
- 必須保留迴圈上限（預設 3 次）：達上限後改以 `additionalContext` 告知並放行，不得讓 agent 卡死。
- Preview 要列出每個命令、預估耗時與觸發路徑；耗時久的命令應設 `paths` 收斂。

### 宣稱證據 Hook

由 [templates/hooks/claim-ledger.py](../templates/hooks/claim-ledger.py)（`PostToolUse`，matcher `Bash|Grep|Glob`）與 [templates/hooks/claim-guard.py](../templates/hooks/claim-guard.py)（`Stop`）成對建立。前者把執行過的命令分成 `test`／`check`／`search` 三類記帳，後者在收工時比對訊息中的宣稱是否有對應類別的紀錄。

- **兩支必須一起安裝**：只裝記帳的沒有效果，只裝檢查的會永遠攔錯人。Preview 要把它們呈現為單一 operation。
- 帳本寫在系統暫存目錄，不進專案、不進版控。
- 必須保留迴圈上限（預設 2 次）。
- **要向使用者說明它的極限**：這是防呆不是防駭——換個說法就繞得過去，而且只比對類別、不驗證宣稱與紀錄是否真的對應。它擋的是「沒跑測試卻順口說測試通過」這種疏忽。

與 TDD evidence observer 的分工：observer 只認 allowlist 內、description 符合固定格式的正式測試命令，產出結構化證據等級供 `test-evidence.md` 使用，範圍限 Spectra change；claim-guard 是粗粒度的有無判定，涵蓋所有工作。兩者互補，不互相取代，可同時啟用。

### Hook 註冊的共同要求

- Claude registration 使用 `command` 加 `args` 的 exec 形式，`${CLAUDE_PROJECT_DIR}` 作為 `args` 的獨立元素。Codex `hooks.json` 依官方 schema 使用 command string，但只允許固定 executable 與專案相對 `.ai/bootstrap-ai-project/` 路徑；不得插入使用者輸入或動態 shell 片段。
- `Stop` 事件依 `policy/hook-policy.json` 屬 `matcher_forbidden_events`，**不得帶 matcher**。
- 這三支 hook 是 Python，與 TDD observer 同屬 `.ps1`／`.sh` 規則的既有例外——理由是跨平台且不需要額外相依。

Commit 防護若被選取：

- 掃描完整 commit command 與 `-F` 指向的 message file。
- 高風險規則 block；疑似高熵值 warn-only。
- 不提供通用 skip marker，不允許 `--no-verify` 繞過。
- 不從 diff 拼接 commit message。

## Agents

四個角色只從 `roles/*.json` canonical contracts 產生。Python／Node `render-roles` 必須輸出相同 bytes；不得讓模型重新改寫 instructions。

選 `Skill` 或 `Both`：

- Codex：`.agents/skills/<role>/SKILL.md` 與 `agents/openai.yaml`；`allow_implicit_invocation: false`。
- Claude：`.claude/skills/<role>/SKILL.md`；`disable-model-invocation: true`。

選 `Agent` 或 `Both`：

- Codex：`.codex/agents/<role>.toml`，只含 `name`、`description`、`developer_instructions`。
- Claude：`.claude/agents/<role>.md`，使用原生 Markdown frontmatter。

不硬編 model、reasoning effort 或權限模式，全部繼承父 session。Skill 在主線程執行；Agent 使用隔離上下文後回報主代理。主代理保留需求、架構、公開介面、整合、驗證與最終輸出所有權，並必須回讀實際 diff、檔案與測試證據。

同一 checkout 同時只允許一個 writer；唯讀 Agent 才可平行。Worker 不得建立子代理、重新解讀最終目標或擴張範圍。`git-commit` 必須由使用者明確啟動，檢查 staged 敏感檔與 `.gitignore`，不建立／切換分支、不繞過 Hook、不 push。
