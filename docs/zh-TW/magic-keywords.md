> 這是 [`docs/magic-keywords.md`](../magic-keywords.md) 的繁體中文翻譯。
> 翻譯基準：`1c7170e11`（2026-08-14）。**英文原文為準** —— 上游更新後本檔可能過期。

# Magic keywords

Magic keyword 是使用者 prompt 裡獨立出現的散文字詞，能為該回合加上隱藏的、歸屬於使用者的指令。notice 注入預設為啟用。TUI 在編輯時會用動態漸層標示辨識到的字詞，已送出的訊息則用靜態漸層；標示只是視覺提示，目前即使在設定中關閉了 notice 注入，標示仍會保留。

## 關鍵字

| 關鍵字 | 效果 |
| ------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `ultrathink` | 加上仔細多步推理的 notice。自動 thinking 啟用時，它同時會為該回合選用目前模型支援的最高推理強度。 |
| `orchestrate` | 加上多代理協作契約：界定完整任務範圍、把大塊獨立工作平行委派出去、逐階段驗證，並持續進行到請求完成為止。 |
| `workflowz` | 加上確定性的多子代理 workflow 契約，核心是常駐 `eval` kernel 的 `agent()`、`parallel()`、`pipeline()` 與 `completion()` 這幾個 helper。它適用於大範圍研究、審查、遷移與對抗式覆蓋。只有在 `eval` 與 `task` 兩者都啟用時才會注入這個 notice。 |

在 prompt 的散文裡任何位置使用關鍵字皆可：

```text
ultrathink about the failure modes before changing this API

orchestrate the migration described in docs/plan.md

workflowz an adversarial review of the authentication changes
```

## 比對規則

比對規則刻意嚴格，避免程式碼與路徑意外改變 agent 的行為：

- 必須是完全小寫的拼法。`Ultrathink`、`Orchestrate` 與 `Workflowz` 不會觸發。
- 關鍵字必須是獨立的散文。句子的標點與引號可以緊鄰它，但字母、數字、底線、斜線、反斜線、連字號、副檔名、符號參照與呼叫語法都不算命中。舉例來說，`orchestrate,` 會命中；`orchestrated`、`orchestrate.ts`、`foo::orchestrate` 與 `orchestrate()` 不會。
- fenced code block（反引號或波浪號）、行內 code span、HTML/XML 註解／標籤／元素，以及它們的內容一律忽略。
- 同一個 prompt 裡所有已啟用的關鍵字都可以各自加上自己的 notice。可見的字詞會留在使用者訊息中；隱藏的 notice 則是不顯示的自訂訊息，歸屬於使用者。
- 該指令只作用於包含關鍵字的那一個回合。

## 設定

開啟 `/settings` 並使用 **Interaction → Magic Keywords**，或從 shell 修改設定：

```bash
# Disable every magic keyword
omp config set magicKeywords.enabled false

# Disable one keyword while leaving the others enabled
omp config set magicKeywords.ultrathink false
omp config set magicKeywords.orchestrate false
omp config set magicKeywords.workflow false
```

全域開關與三個個別關鍵字開關預設都是 `true`。全域開關管控所有隱藏 notice；個別開關只管控該項 notice（以及 ultrathink 的最高自動 thinking 覆寫）。這些設定目前**不會**關閉編輯器／訊息的漸層標示。執行 `omp config list` 可檢視所有設定與其目前的值。設定的作用範圍、優先順序與專案層覆寫請見 [Settings](../settings.md)。
