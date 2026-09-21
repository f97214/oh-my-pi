# ADR 格式

<!-- shared-contract:adr:start -->
## ADR 共用契約

### 何時建立

以下三條件必須**全部**成立：

1. **難以回頭**——之後改變主意的成本很可觀
2. **沒脈絡會困惑**——未來的讀者看到程式碼會納悶「當初到底為什麼這樣做？」
3. **真實取捨的結果**——確實有其他選項，而你基於特定理由選了這個

缺任何一項就跳過。容易回頭的決策不用記——要改就改。不令人意外的決策沒人會納悶為什麼。沒有真實替代方案的決策，除了「我們做了理所當然的事」以外沒東西可記。

## 範本

ADR 存放於 `docs/adr/`，採連續編號 `0001-slug.md`、`0002-slug.md`……；目錄採 lazy 建立，第一份 ADR 需要時才建。編號取現有最大編號加一。

```md
# {決策的簡短標題}

{一到三句：脈絡是什麼、我們決定了什麼、為什麼。}
```

就這樣。一份 ADR 可以只有一段話。價值在於記下「做過這個決策」以及「為什麼」——不在於填滿章節。

可選章節只有真正加值時才加，多數 ADR 不需要：

- **Status** frontmatter（`proposed | accepted | deprecated | superseded by ADR-NNNN`）——決策可能被重新檢視時有用
- **Considered Options**——只在被否決的替代方案值得記住時
- **Consequences**——只在需要點出不明顯的下游影響時

### supersede

新決策推翻既有 ADR 時：

1. 舊 ADR 加上 `Status: superseded by ADR-NNNN`。
2. 新 ADR 註明它取代了哪一份。
3. 兩份的狀態同步反映到索引。

**禁止刪除或改寫既有 ADR 的決策內容**——只能改狀態並新增取代者。被推翻的決策本身也是脈絡：它能阻止下一個人再次提出同一個已被評估過的方案。
<!-- shared-contract:adr:end -->

## 索引維護

`docs/adr/README.md` 是 ADR 的索引，與 `docs/adr/` 目錄一起 lazy 建立——第一份 ADR 出現時才建。每次新增 ADR 或變更狀態，**當場**更新索引，不累積批次處理。

| 欄位 | 說明 |
|---|---|
| 編號 | `ADR-NNNN`，連結到檔案 |
| 標題 | ADR 的 H1 |
| 狀態 | `accepted` / `proposed` / `deprecated` / `superseded by ADR-NNNN` |
| 來源 | 訪談主題、change 名稱或其他脈絡來源 |

### 什麼夠格

- **架構形狀。**「我們採 monorepo。」「寫入模型採 event sourcing，讀取模型投影到 Postgres。」
- **Context 之間的整合模式。**「Ordering 與 Billing 以 domain event 溝通，不用同步 HTTP。」
- **帶有 lock-in 的技術選型。** 資料庫、message bus、認證供應商、部署目標。不是每個函式庫都算——只記換掉要花一季的那些。
- **邊界與範圍決策。**「客戶資料由 Customer context 擁有；其他 context 只能以 ID 參照。」明確說「不做」的和說「做」的一樣有價值。
- **刻意偏離顯而易見路線的做法。**「我們用手寫 SQL 而不用 ORM，因為 X。」任何合理的讀者會假設相反的地方——這能阻止下一位工程師去「修正」一個刻意的決定。
- **程式碼裡看不見的限制。**「因法遵要求不能用 AWS。」「因合作方 API 契約，回應時間必須低於 200ms。」
- **否決理由不明顯的替代方案。** 若你評估過 GraphQL、基於微妙理由選了 REST，記下來——否則半年後又會有人提 GraphQL。
