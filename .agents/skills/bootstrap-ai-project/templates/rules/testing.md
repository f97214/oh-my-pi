<!-- bootstrap-ai-project:tdd-observability -->
# 測試與 Spectra TDD 證據

只有目前工作屬於 Spectra change 時，才套用本節的 TDD 證據流程；其他測試工作仍遵循專案既有慣例。

## 測試前

1. 從目前 change 的 Requirement、Scenario 或 Example 找出正在驗證的行為，不確定時標記「未確認」。
2. 讀取既有測試，沿用測試位置、命名、helper 與隔離方式。
3. 指名 Spectra task、Scenario／Example、測試檔案與案例名稱。不得捏造對應關係。
4. 只使用 `.ai/bootstrap-ai-project/tdd-observer.json` 已列入 allowlist 的正式測試命令或安全 selector 變體。

## 執行測試

每次由 Bash 工具執行可觀測測試時，description 必須完全符合以下其中一種格式：

```text
TDD Red: task=<task-id>; evidence=<safe-key>
TDD Green: task=<task-id>; evidence=<safe-key>
TDD Refactor: task=<task-id>; evidence=<safe-key>
```

`task-id` 與 `safe-key` 只能使用 ASCII 英數、`.`、`_`、`-`。直接在 IDE、外部終端或 CI 執行的測試，以及 compound、redirect、環境變數插入、未知 wrapper 或未列入 allowlist 的命令，都必須標示為「未觀測」。

## 證明規則

- 只有同一個 `task + scenario/example + test case` 先出現有效 assertion／行為 Red，再出現 Green，且 Refactor 後正式 regression suite 通過，才能標示 `proven`。
- 編譯錯誤、缺少相依、設定或權限錯誤、取消與 timeout 都不是有效 Red。
- 只有 Green、既有測試原本就通過，或缺少有效階段標記時，只能標示 `tested-not-proven`。
- Refactor regression 失敗時標示 `failed`；缺少必要觀測或對應關係時標示 `incomplete`。
- 證據來源只能是 `hook-observed`、`source-inspected`、`agent-declared`、`unavailable`；後兩者不得改寫成已觀測結果。

## Task 完成前

在呼叫 `spectra task done` 前：

1. 更新 `openspec/changes/<change-name>/test-evidence.md`。
2. 寫入預計驗證的行為、Spec 對應、測試檔案／案例、工作目錄、實際命令、Red／Green／Refactor、統計、耗時、變更案例與未覆蓋情境。
3. Observer 的 `TDD_OBSERVATION` 可作為 `hook-observed` 證據；不得自行補造缺少的欄位。
4. 完整 suite 只保留統計及失敗／跳過案例，不展開未變更的成功案例。
5. 不把 raw stdout/stderr、環境變數或機密寫入報告；失敗摘要只能使用已遮蔽、已截斷內容。
6. 在終端輸出以 `## TDD 測試摘要` 開頭的精簡 Task 摘要，包含狀態、測試案例、命令 key、統計與報告路徑。

終端摘要固定採用：

```text
## TDD 測試摘要
- Task：<task-id>
- 狀態：proven / tested-not-proven / failed / incomplete
- 行為與 Spec：<behavior> — <requirement/scenario/example>
- 新增／修改案例：<test-file> — <case>
- Red → Green → Refactor：<result-chain>
- 正式命令：<command-key>（<passed> passed / <failed> failed / <skipped> skipped，<duration>）
- 完整報告：openspec/changes/<change-name>/test-evidence.md
- 未觀測／未覆蓋：<none-or-gaps>
```

Observer 只觀察結果，不執行或修改測試、Spectra 命令、artifact、task 或狀態。
