<!-- bootstrap-ai-project:adr -->
# 架構決策紀錄（ADR）

ADR 記錄跨 change 的長期架構約束，存放於 `docs/adr/`，採連續編號 `0001-slug.md`、`0002-slug.md`……

`design.md` 是單一 change 的實作設計，會隨 change 一起歸檔；ADR 是脫離 change 生命週期的決策脈絡。兩者職責不同，不互相取代。

## 開工前必讀

1. 建立提案或開始實作任何 change 之前，先讀 `docs/adr/README.md` 索引；只有需要細節時才展開個別 ADR。
2. 提案或實作與 `accepted` 狀態的 ADR 衝突時：**停止並回報**，由使用者決定要修訂提案，或以新 ADR supersede 舊決策。不得自行選邊，不得默默推翻既有決策。
3. `docs/adr/` 不存在時本節不適用；不要為此建立空目錄或空索引。

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

夠格的類型：架構形狀、模組之間的整合模式、帶 lock-in 的技術選型（資料庫、message bus、認證供應商、部署目標——不是每個函式庫都算）、邊界與範圍決策、刻意偏離顯而易見路線的做法、程式碼裡看不見的外部限制、否決理由不明顯的替代方案。

## 檢查點

**1. design 收斂後**

`design.md` 寫完時，逐一檢視其中的架構取捨。滿足三條件者建立 ADR，並在 ADR 內註明來源 change 名稱。`design.md` 保留實作細節，ADR 只留「決定了什麼、為什麼」——不要整段複製。

**2. 歸檔前**

執行 archive 之前，確認此 change 引入的長期決策已脫離 `openspec/changes/`。尚未落地者現在補寫，否則決策脈絡會隨 change 一起被埋進 `archive/`。

**3. 需求訪談中**

訪談過程敲定的重大取捨即時建檔，不累積到最後批次處理。

## 索引

- 每次新增 ADR 或變更狀態，**當場**更新 `docs/adr/README.md`，不累積批次處理。

`docs/adr/README.md` 的欄位固定為：

| 欄位 | 說明 |
|---|---|
| 編號 | `ADR-NNNN`，連結到檔案 |
| 標題 | ADR 的 H1 |
| 狀態 | `accepted` / `proposed` / `deprecated` / `superseded by ADR-NNNN` |
| 來源 | change 名稱、訪談主題或其他脈絡來源 |
