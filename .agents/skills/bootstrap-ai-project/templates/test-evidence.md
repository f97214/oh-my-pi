<!-- bootstrap-ai-project:tdd-evidence -->
# TDD Test Evidence

## Change 與測試設定

| 欄位 | 值 |
|---|---|
| Change | `<change-name>` |
| Framework | `<framework>` |
| Commands（正式 allowlist） | `<allowlisted-command-key>` |
| Observer | `<setup/effective/unavailable>` |
| 更新時間 | `<ISO-8601>` |

## TDD 測試摘要

| Task | Status | Proven | Tested-not-proven | Failed | Incomplete | Source |
|---|---|---:|---:|---:|---:|---|
| `<task-id>` | `incomplete` | 0 | 0 | 0 | 1 | `unavailable` |

完整 suite 僅列統計與失敗／跳過；不列出所有成功測試。

## Spec Mapping

| Task | 預計驗證行為 | Requirement / Scenario / Example | Test file | Case | 狀態 | Source |
|---|---|---|---|---|---|---|
| `<task-id>` | `<observable-behavior>` | `<source-path-and-heading>` | `<test-path>` | `<case>` | `incomplete` | `unavailable` |

## Red / Green / Refactor Evidence

| Phase | Task | Scenario / Example | Case | Command key / actual command | Working directory | Result / failure kind | Passed / Failed / Skipped | Duration | Source | Safe notes |
|---|---|---|---|---|---|---|---|---:|---|---|
| Red | `<task-id>` | `<scenario-or-example>` | `<case>` | `<key>` / `<command>` | `<cwd>` | `unavailable` | `? / ? / ?` | — | `unavailable` | `<safe-summary>` |
| Green | `<task-id>` | `<scenario-or-example>` | `<case>` | `<key>` / `<command>` | `<cwd>` | `unavailable` | `? / ? / ?` | — | `unavailable` | `<safe-summary>` |
| Refactor | `<task-id>` | `<scenario-or-example>` | `<case>` | `<key>` / `<command>` | `<cwd>` | `unavailable` | `? / ? / ?` | — | `unavailable` | `<safe-summary>` |

<!-- evidence:<safe-key> -->

每筆 evidence 都以 `<!-- evidence:<safe-key> -->` 開始，且 `Source` 僅可為 `hook-observed`、`source-inspected`、`agent-declared` 或 `unavailable`。

## Changed Tests

| File | Case | Change | Source |
|---|---|---|---|
| `<test-path>` | `<case>` | `added / modified` — `<what changed>` | `source-inspected` |

## Regression

| Scope | Command / cwd | Passed | Failed | Skipped | Duration | Source | Failures / skipped / safe summary |
|---|---|---:|---:|---:|---:|---|---|
| `<suite-or-command-key>` | `<command>` / `<cwd>` | 0 | 0 | 0 | — | `unavailable` | `<safe-summary>` |

## Gaps / Follow-up

- `<missing lifecycle, assertion verification, skipped command, or manual follow-up>`
