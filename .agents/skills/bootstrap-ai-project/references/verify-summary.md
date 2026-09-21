# Verify 與摘要

## 驗證順序

1. 以原 request 執行 bundled `verify`。
2. 確認 planned create/update 的 current SHA-256 等於 after hash。
3. 重新解析 JSON；檢查 `.gitignore` marker 恰好一組。
4. 靜態驗證 Hook 註冊、event/matcher、command/args、腳本路徑與編碼。
   Spectra TDD evidence observer 要另驗證其 setup/effective、允許的 lifecycle 與未支援 lifecycle 的 `unavailable` 狀態；不得觸發 observer。
5. 重新掃描生成／更新的文字檔。
6. 只執行 Preview 已確認的測試命令。
7. 搜尋 Skill 本身的禁止殘留詞，結果必須為零。

驗證不觸發新 Hook、不安裝 Plugin、不執行未預覽命令。

Codex project Skills、Agents 與 Hooks 的 discovery 必須在受信任專案的新 task/session 驗證；目前 task 啟動時已載入的 metadata 不算寫後驗證。

## 摘要資料來源

摘要只讀 `run_config.results` 與 Verify 實際輸出。禁止從範例、原始 plan 或預期狀態推測成功。

至少回報：

- selected target 與模式
- Git 策略
- 實際建立／更新／跳過／衝突的檔案
- README 處置
- 文件證據中「未確認」的項目
- 寫前／寫後機密掃描結果，並註明其限制
- hosts、逐角色 surfaces、Skills、Agents、Rules 與共用 Hooks 的實際狀態
- Spectra TDD requested／effective
- TDD evidence observer setup／effective、實際報告路徑與不可用 lifecycle
- 證據報告的 task 統計：`proven`、`tested-not-proven`、`failed`、`incomplete`；不得以缺少 evidence 推測為 proven
- 測試 profile、補建、回復與驗證結果
- Code Review 規則 setup／skipped；setup 時附 `ocr` 安裝與使用命令，並註明 bootstrap 沒有執行 `ocr`、規則生效與否未經驗證
- Plugin 建議來源或動態清單不可用
- 失敗命令的安全摘要與人工後續步驟

不要輸出祕密匹配內容、完整 stderr 中的 credential，或把「未執行」寫成「通過」。

## Skill 自我驗收

重構或發布此 Skill 時執行：

1. Python 與 Node fixture parity。
2. docs-only、full+Spectra、full+skip 三種情境。
3. Monorepo 單 target、env key-only、secret block、JSON merge、Hook schema、gitignore marker/symlink、plan drift。
4. Codex canonical Skill：
   - `SKILL.md` frontmatter 只含 `name` 與 `description`
   - `agents/openai.yaml` 有 `allow_implicit_invocation: false`
   - `default_prompt` 提及 `$bootstrap-ai-project`
5. Claude 薄入口：
   - `name: bootstrap-ai-project`
   - `argument-hint: "[target-path]"`
   - `disable-model-invocation: true`
   - body 使用 `$ARGUMENTS`
6. 四個角色的 Claude Skill、Codex Skill、Claude Agent、Codex Agent 都能解析，且 canonical instructions 正規化後逐字一致。
7. Claude-only、Codex-only、Both、Disabled renderer parity 與跨宿主原子 conflict。
8. 搜尋所有禁止殘留詞。

不得把 Claude 專屬 frontmatter 放入 Codex canonical Skill，也不得為了通過 Codex 驗證而刪除 Claude 薄入口的 `argument-hint` 與 `disable-model-invocation`。兩個入口使用各自宿主 schema，bundled validator 與通用 lint 都必須通過。

Codex live smoke test 預設跳過，避免離線驗證意外消耗模型額度。要在全新暫存專案實際驗證 `$doc-writer` discovery，設定 `RUN_CODEX_LIVE_TESTS=1` 後執行 `tests/test_live_codex_smoke.py`。具名 Agent 的 spawn 測試另需 `RUN_CODEX_AGENT_LIVE_TESTS=1`；若當前 Codex CLI／帳戶的 multi-agent runtime 沒有提供可選的自訂 agent type，必須如實回報未通過，不得以 TOML 解析成功代替 live spawn 證據。
