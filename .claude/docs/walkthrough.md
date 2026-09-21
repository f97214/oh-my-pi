# 實例走查：新增一支對外拉資料的排程 Job

用一個具體例子走完整條流程：在 QuartzTemplate 新增一支 Job，每 15 分鐘向外部 API 拉取資料並寫入資料庫。

每一段都寫出：**你下什麼指令、產出什麼檔案、這一步被哪條規則約束、AI 會在哪裡停下來問你**。

---

## 前置：這個專案初始化過了嗎

流程的規則不是憑空生效的，它們是 `/bootstrap-ai-project` 產生到專案裡的檔案。

```
/bootstrap-ai-project
```

完整模式下逐項確認後，專案會拿到：

| 檔案 | 作用 |
|---|---|
| `CLAUDE.md`、`AGENTS.md`、`docs/` | 專案文件與協作規範 |
| `.spectra.yaml` | `tdd: true` 等旗標，決定 `/spectra-apply` 的紀律 |
| `.claude/rules/testing.md` | 測試證據契約 |
| `.claude/rules/adr.md` | 架構決策的讀取義務與檢查點 |
| `.claude/rules/glossary.md` | 詞彙表紀律 |
| `.claude/rules/engineering.md` | 對抗審查、介面契約、可觀測性 |

**已經初始化過的舊專案不會自動獲得新增的 rule**——要重跑一次 bootstrap 並選取才有。

---

## 階段 0：需求還講不清楚時

```
/grill 新增一支排程 Job，定期同步外部報價資料
```

AI 會分輪提問，每題附建議答案。你只需要做決策，事實由 AI 自己查。這一輪可能會問：

- 拉取失敗時是整批重試，還是逐筆記錄失敗？
- 「報價」在這個系統裡指的是什麼？和既有的 `Price` 是同一個概念嗎？
- 15 分鐘是硬需求，還是「大約每小時幾次就好」？
- 上一次成功時間要持久化嗎？服務重啟後要補跑嗎？

過程中：

- 敲定的術語**當場**寫進 `CONTEXT.md`——例如確認「報價（Quote）」與既有的「價格（Price）」是不同概念
- 符合三條件（難以回頭、沒脈絡會困惑、真實取捨）的決策寫成 ADR——例如「失敗批次不阻塞後續批次，改記錄到補償佇列」
- 與既有 `accepted` ADR 衝突時，AI **停下來問你**，不會默默推翻

需求本來就清楚就跳過這一階。

---

## 階段 1：把需求變成規格

```
/spectra-propose 新增報價同步 Job
```

產出並自動 park：

```
openspec/changes/add-quote-sync-job/
├── proposal.md   # 為什麼要做、會改什麼、影響範圍
├── design.md     # Job → Service → Repository 的分層、重試策略、資料流
├── tasks.md      # - [ ] 形式的可執行任務
└── specs/quote-sync/spec.md   # Requirement + GIVEN/WHEN/THEN + Example
```

這一步的關鍵是 **spec.md 裡的 `##### Example:` 區塊**——階段 2 的測試值會直接取自那裡，不是實作時現編的。

`design.md` 寫完後觸發 **ADR 檢查點①**：其中的架構取捨若滿足三條件，AI 會提議寫成 `docs/adr/NNNN-*.md`。因為 `design.md` 會隨 change 一起歸檔，決策脈絡必須先脫離它。

超過 15 個 task 時 AI 會建議拆成多個 change。

---

## 階段 2：實作

```
/spectra-apply add-quote-sync-job
```

一個指令跑完整個循環。每個 `- [ ]` task 走 Red → Green → Refactor：

**Red** — 先寫失敗測試，測試值取自 spec 的 Example：

```
TDD Red: task=2.1; evidence=quote-sync-retry
```

命令的 description 必須完全符合這個格式，test-observer 才會把它算成證據。編譯錯誤、缺相依、逾時都**不算**有效的 Red。

**Green** — 不違反 `design.md` 分層的最小實作。

這裡會踩到 `.claude/rules/engineering.md`：

- 決定「重試是否冪等」時觸發**對抗審查**——這是型別系統驗證不了的性質。AI 會寫下 CLAIM、把「產物＋契約」交給獨立審查（**不給 CLAIM**，否則審查者會附和）、分類發現、最多三輪就升級問你
- 寫 log 時**不能**寫成 `log.Info($"同步 {count} 筆完成")`，要用結構化欄位，並帶上貫穿全程的 correlation ID
- 對外 API 呼叫要有 RED 指標（次數、失敗率、延遲分布），延遲看 p95 不看平均
- 這支 Job 的名稱、欄位、型別要照 `CONTEXT.md` 的 canonical term——不能一邊叫 Quote 一邊叫 Price

**Refactor** — 測試持續通過下改善品質，不得跨層搬遷。

每完成一個 task 立即：

```
spectra task done --change "add-quote-sync-job" 2.1
```

**禁止直接編輯 tasks.md 的 checkbox**——CLI 同時更新 checkbox 與 `.spectra/touched/`，後者是歸檔時注入 @trace 的唯一來源。

AI 會在這些情況停下來問你：測試與 spec 衝突、需求超出 spec 的 Scenario、與既有 ADR 衝突、詞彙表定義矛盾、對抗審查三輪未收斂。

---

## 階段 3：驗證完整性

```
spectra analyze add-quote-sync-job --json
```

檢查每個 Requirement 都有對應實作、design 與 spec 一致、有沒有模糊或缺口。有 Critical 發現就回頭修。

---

## 歸檔

```
/spectra-archive add-quote-sync-job
```

歸檔前觸發 **ADR 檢查點②**：確認這次引入的長期決策已經脫離 `openspec/changes/`，否則它會跟著被埋進 `archive/`。

歸檔會把 spec delta 併進主規格、注入 @trace、把整個 change 目錄移到 `openspec/changes/archive/YYYY-MM-DD-add-quote-sync-job/`。

---

## 上線

**流程到歸檔為止是 AI 主導的；上線之後由你主導。**

上線前先過檢查清單（排程服務適用的部分）：祕密沒有進版控、環境變數已設定、資料庫遷移已備妥、log 與錯誤回報接好、健康檢查會回應。

排程 Job 的分階段推出通常是：

```
staging 跑一輪完整週期
  → 正式環境部署，但 Job 的 trigger 先停用
  → 手動觸發一次，確認資料正確
  → 恢復排程，觀察 24 小時
```

觀察錯誤率與 p95 延遲：超過基準兩倍、或延遲惡化逾五成，立即回滾，不先討論。

若這支新 Job 是要取代舊的 WinForm gateway，汰除照三步走：新舊並行 → 用指標確認舊的零使用 → 才移除。資料庫欄位一律**擴充 → 遷移 → 收縮**，絕不原地改名。

---

## 換手

```
/handoff 報價同步 Job 已完成階段 2，剩下 analyze 與上線
```

把對話濃縮成交接文件存到系統暫存目錄（不進工作區），列出接手的 agent 該呼叫哪些 skill。
