# Spectra TDD 證據觀測契約

## 目的與界線

此 observer 只觀察已選宿主實際支援的 lifecycle，將可驗證的測試結果整理為 evidence。它**不執行測試、不改寫測試、不安裝 coverage 工具，也不修改 Spectra、`.spectra.yaml`、OpenSpec task 或 `spectra task done` 的行為**。它不是測試 runner，也不能把 agent 的敘述升格為已驗證事實。

只有 `spectra_tdd.effective: true`，且使用者在獨立 `tdd_observability` Preview 確認後，才可建立 observer。docs-only、Spectra TDD skip、dependency declined，或 effective 為 false 時一律不建立。一般 Hooks 是否跳過不影響此獨立確認要求。

`tdd_observability` 是一個獨立決策，固定採用 `rules-and-hook`、`change-report`、`task-summary`、`red-green-required` 四個 profile 值，並整體列入 Preview 與確認。使用者未確認時，observer 為 `skipped`；宿主不支援的 lifecycle 為 `unavailable`，不可假裝 setup 成功。

## 下游元件與 Preview

Preview 必須逐一列出且只在確認後建立：

| 下游路徑 | 來源／內容 |
|---|---|
| `.claude/rules/testing.md` | 由 [testing.md](../templates/rules/testing.md) 建立測試證據契約；既有檔沒有 `bootstrap-ai-project:tdd-observability` marker 時視為衝突，不覆寫。 |
| `.ai/bootstrap-ai-project/hooks/test-observer.py` 或 `.mjs` | 複製本 Skill 已選定且驗證成功的單一共用 observer runtime，不同時安裝兩套。 |
| `.ai/bootstrap-ai-project/tdd-observer.json` | 依 `schemas/test-observer-config.schema.json` 產生；framework、正式命令與 command id 來自 Discover／Preview，`secret_rules` 必須精確複製 `policy/secret-rules.json` 的 `rules`。 |
| `.claude/settings.json`、`.codex/hooks.json` | 只在已選宿主以各自原生 schema 註冊支援的 lifecycle；不得覆寫未知或同名不相容 Hook。 |
| `openspec/changes/<change>/test-evidence.md` | 執行 `/spectra-apply` 時由 project Rule 依 [test-evidence.md](../templates/test-evidence.md) 建立或更新，observer 不直接寫入。 |

observer 設定的固定值為：

```json
{
  "schema_version": 1,
  "report_pattern": "openspec/changes/{change_name}/test-evidence.md",
  "max_failure_summary_chars": 500,
  "required_report_marker": "<!-- bootstrap-ai-project:tdd-evidence -->",
  "required_summary_heading": "## TDD 測試摘要"
}
```

`framework` 只能是 `vitest`、`jest`、`pytest`、`xunit`、`go`、`rspec` 或 `cargo`；`commands` 是非空的 `{ "id", "base" }` 清單。不得把範例命令或未經 Discover 確認的 runner 加入 allowlist。

Claude command handler 使用 Preview 已確認的 Python 或 Node executable，並以獨立 `args` 傳入 observer、`--config`、設定路徑、`--project-root` 與 `${CLAUDE_PROJECT_DIR}`。Codex registration 依其 `hooks.json` command schema 使用專案相對的 `.ai/bootstrap-ai-project/` 路徑。不得把未驗證的 shell 片段或使用者內容插入 command。宿主矩陣為：

| Event | Matcher |
|---|---|
| Claude `UserPromptExpansion`／Codex `UserPromptSubmit` | `spectra-apply`；只有目前 host schema 支援時註冊 |
| `PreToolUse` | `Bash` |
| `PostToolUse` | `Bash` |
| Claude `PostToolUseFailure`；Codex 由 `PostToolUse` 的非零結果表示 | `Bash` |
| `Stop` | 不得有 matcher |
| `SessionEnd` | 不設 matcher，只用於清除 session 暫存狀態 |

設定 merge 後必須驗證 observer 腳本、config、runtime 路徑與事件 schema；只做靜態驗證，不觸發 Hook。`run_config.results` 要逐項記錄 rule、observer、config、settings 與 lifecycle：已套用使用 `status: success`，未選或不需要使用 `skipped`，衝突使用 `needs-input`，能力不存在使用 `warning` 並另記 `outcome: unavailable`。只有所有必要元件均為 `success` 時 `tdd_observability.effective` 才可為 true。

## Lifecycle 與最小資料

| Lifecycle | 可做的觀察 | 禁止事項 |
|---|---|---|
| `UserPromptExpansion` | 偵測直接輸入的 `/spectra-apply`、取得安全的 change argument，並注入本契約。 | 推測 task、scenario、case 或聲稱測試已執行。若 host schema 未支援，標記 `unavailable` 且不註冊。 |
| `PreToolUse`（僅 Bash） | 只辨識獨立的 `spectra instructions apply --change <name> --json`，補齊省略參數時的 change name。 | 改寫、允許或執行命令；把一般 Bash 或測試命令當成 change discovery。 |
| `PostToolUse`（僅 Bash） | 以對應 invocation 的 exit/result 更新 pass evidence。 | 從一般文字、未對應輸出或預期結果推測 pass。 |
| `PostToolUseFailure`（僅 Bash） | 記錄已觀察命令的失敗類型與安全摘要。 | 將 compile、dependency、permission 或 timeout 視為 Red。 |
| `Stop` | 若目前 task 尚未有必需摘要或 evidence，以 `additionalContext` 要求補齊一次。 | 使用 `decision: block` 永久阻擋、重跑命令或第二次要求補齊；第二次一律警告後放行。 |
| `SessionEnd` | 完成已觀察資料的安全摘要，標記未完成項目。 | 產生未觀察到的 Red/Green/Refactor 或寫入原始輸出。 |

Prompt expansion 是 capability，不代表每個 Hook schema 使用相同事件。註冊前必須依目前宿主 schema 驗證；Claude 可用 `UserPromptExpansion` 時直接取得 command，Codex 使用 `UserPromptSubmit` 時只接受明確的 `$spectra-apply` 或 `/spectra-apply` prompt。無支援時保留其他已支援 lifecycle，並在報告的 source/gaps 中寫 `unavailable`。

Stop 的完整性檢查至少包含：報告與 evidence markers、不得殘留模板 placeholder、每筆已分類 observation 的 phase／task／command／`hook-observed` evidence row、已觀察失敗／跳過案例，以及終端摘要中的 task 狀態與精確報告路徑。它只驗證觀測資料是否被帶入，不替代 Rule 對 Requirement／Scenario／case 對應與 `proven` 判定的語義審查。

## 正式測試命令與 description

觀察只接受 Discover 與 Preview 已確認、以 executable 與 argv 正規化的正式命令 allowlist。每一項以已核准的 base command 比對；只有 policy 明確允許的安全 selector suffix 可附加。allowlist 可包含已偵測 framework 的單一命令，例如 `dotnet test`、`npm test`、`npm run test --`、`pnpm test`、`pnpm run test --`、`yarn test`、`yarn run test`、`npx vitest run`、`npx jest`、`pytest`、`python -m pytest`、`go test`、`bundle exec rspec`、`cargo test`；範例不是自動允許，實際項目只能來自 Preview。

命令含 `;`、`&`、`&&`、`||`、`|`、換行、redirect、subshell、glob、環境變數插入，或在一個 Bash invocation 內混合其他命令時，均是 compound／不安全命令，**ignored**，不作 evidence。selector 不得使用絕對路徑或 `..` 離開選定 target；未列入 allowlist 的命令同樣 ignored。observer 可保存已命中 allowlist 的實際測試命令與安全 selector，讓使用者知道真正執行了什麼；不得保存環境變數、compound command 或未識別的 command line。任何可保存命令仍須先執行機密遮蔽。

可觀察的正式命令必須有完全相符的 description：

```text
TDD Red: task=<id>; evidence=<key>
TDD Green: task=<id>; evidence=<key>
TDD Refactor: task=<id>; evidence=<key>
```

`<id>` 必須對應目前 Spectra task；`<key>` 必須是 safe key（ASCII 英數、`.`、`_`、`-`，且不得含空白、路徑分隔符或 secret）。無效 description、task 不相符或 key 不安全時記 `incomplete`，不寫入 evidence marker。

## 證據狀態與 TDD 判定

每個 evidence 都要有來源標籤，且只能使用下列值：

| source | 意義 |
|---|---|
| `hook-observed` | lifecycle 已觀察到相符命令與結果。 |
| `source-inspected` | 人工讀取既有測試／設定可確認的靜態事實。 |
| `agent-declared` | agent 的敘述，未由 hook 或 source 證實。 |
| `unavailable` | lifecycle、輸出或必要資料不可取得。 |

不得把 `agent-declared` 或 `unavailable` 寫成實際執行結果，也不得捏造任何 source。

同一 `task + scenario/example + case` 只有符合以下順序才是 `proven`：先有帶有效 assertion 的 `Red` 失敗，再有相同識別的 `Green` 成功，最後有 `Refactor` regression pass。編譯失敗、dependency 安裝／解析失敗、權限失敗與 timeout 都不是 Red。只有 Green 成功時是 `tested-not-proven`；缺少相關 observation 是 `incomplete`；已觀察到不符合預期或 regression 失敗才是 `failed`。

assertion 是否有效必須來自可檢查的測試來源或 runner 訊號；無法判定時寫 `unavailable`，不得假設。Red、Green、Refactor 可以使用不同 allowlisted command，但三者 task、scenario/example、case 必須相同。

## 報告、完成閘門與隱私

每個 Spectra task 在執行 `spectra task done` **之前**，更新 `openspec/changes/<change>/test-evidence.md`，並在 task 完成回報顯示 `## TDD 測試摘要`。報告必須從 [test-evidence.md](../templates/test-evidence.md) 的 marker 開始；有 marker 時整份檔案由此契約管理，既有檔案沒有 marker 時視為使用者內容並停止回報衝突。

完整 suite 只記錄統計、失敗與跳過項目；不得展開所有成功測試。coverage 只在既有、已觀察輸出可安全取得時記錄；observer 不安裝 coverage 套件，也不因缺少 coverage 改變 TDD 判定。

不得落盤 raw stdout/stderr、完整 shell 命令、環境變數或 credential。將 token、password、key、connection string 與疑似高熵值遮蔽為 `[REDACTED]`；錯誤只保留分類與必要的安全摘要。
