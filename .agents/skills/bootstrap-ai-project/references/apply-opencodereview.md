# Apply：Code Review 規則產出

本 reference 只在完整模式、`discovery.stacks` 非空，且使用者明確選取「Code Review 規則」時讀取。

產出一個檔案：`.opencodereview/rule.json`。它把既有 Rules 契約中**能由 diff 檢出**的部分，翻成依檔案路徑套用的審查規則，供 [open-code-review](https://github.com/alibaba/open-code-review)（`ocr`）使用。

## 界線

- **不安裝任何東西。** 不執行 `npm install`，不執行 `ocr`，不寫入 `ocr` 的設定。只產生規則檔並在摘要附上安裝命令。
- **不得寫入 `verify-gate.json`。** 收工閘門不可相依外部 CLI；`ocr` 沒裝時整個閘門會失效。
- **不是機械強制。** `rule` 欄位是自然語言，判斷仍由模型做。它與驗證閘門（只看退出碼）本質不同，摘要不得描述成「補上了硬強制」。
- **不取代既有機制。** 它不取代 `spectra analyze`（驗規格完整性）、測試證據觀測層，或任何 Rule 本身。Rules 仍照常建立。
- 只在 `discovery.stacks` 非空時提供這個選項。純文件 target 產生規則檔沒有意義。

## create-only

**既有的 `.opencodereview/rule.json` 一律標為 `conflict`，不覆寫、不合併。**

這個檔案是團隊會持續調整的審查契約，不是 bootstrap 的託管產物——重跑 bootstrap 不應該把調整過的規則洗掉。

JSON 沒有註解語法，無法比照 Rules 在檔首放 `bootstrap-ai-project:*` managed marker；而把 marker 塞成自訂鍵（例如 `$managed`）會相依「`ocr` 容忍未知 top-level 鍵」這個未經證實的行為。create-only 同時解掉這兩件事：conflict 時如實回報，請使用者自行合併。

## 規則內容

從 [templates/opencodereview-rule.json](../templates/opencodereview-rule.json) 建立，**只填 glob，不改規則文字**。

三條規則對應的既有契約：

| 規則 | 來源契約 |
|---|---|
| 可觀測性 | `templates/rules/engineering.md` 第 3 節 |
| 介面與契約 | `templates/rules/engineering.md` 第 2 節 |
| ADR 不可刪改 | `templates/rules/adr.md` |

**不要自行增加規則。** 其餘契約無法由 diff 檢出——對抗審查、以官方文件為準、升級格式與 Context 工程都是流程紀律，不留 diff 痕跡；詞彙表要把 `CONTEXT.md` 內容嵌進規則字串才能檢查，會隨詞彙表更新而過期。使用者要求時可說明可以手動加，但 bootstrap 不自動產生。

## 填 glob

| Placeholder | 填法 |
|---|---|
| `{OBSERVABILITY_GLOB}` | 長期執行的服務、排程作業與外部整合所在目錄 |
| `{INTERFACE_GLOB}` | 對外 API、跨模組介面與被其他程式消費的資料結構所在目錄 |
| `{ADR_GLOB}` | 實際的 ADR 目錄，通常是 `docs/adr/*.md` |

規則：

- glob 只能取自 `discovery.stacks` 中狀態為 `confirmed` 的技術棧。標記 `unconfirmed` 的技術棧**不得**產生 glob——寫出去的規則永遠不會命中，比沒有更糟。
- 兩個 glob 指向同一個目錄是可接受的；分不出邊界時就都用主要原始碼目錄，不要臆造分層。
- 目錄不存在時整條規則**移除**，不要留下指向不存在路徑的規則。三條都不適用時，不建立這個檔案。
- 依實際偵測到的副檔名收斂，例如 `.NET` 用 `**/*.cs`、Node 用 `**/*.{ts,js}`。`path` 支援 `**` 遞迴與 `{a,b}` 展開。
- 不輸出 `exclude` 欄位——它的正確層級未經官方文件證實，而規則本身已是 path-scoped，不需要它。

## Preview

以獨立 operation 顯示：

- 完整檔案路徑與內容
- 每條規則填入的 glob，以及該 glob 來自哪一項 `confirmed` 證據
- 因目錄不存在而移除的規則
- 明確標示這是 create-only，既有檔案會是 conflict

## 摘要

回報 setup 或 skipped，並附上使用方式——這是使用者唯一會拿到安裝資訊的地方：

```text
安裝：npm install -g @alibaba-group/open-code-review
使用：ocr delegate preview --format json
      ocr delegate rule --format json <paths...>
驗證規則命中：ocr rules check <file>
```

`ocr delegate` 不需要設定 LLM endpoint——它只做檔案選取與規則解析，實際審查由宿主 agent 用自己的模型執行。`ocr rules check` 同樣不需要 LLM，可以確定性地確認某個檔案命中哪些規則。

不要宣稱已驗證規則生效；bootstrap 沒有執行 `ocr`。
