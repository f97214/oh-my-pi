# CONTEXT.md 格式

<!-- shared-contract:glossary:start -->
## 詞彙表共用契約

## 結構

```md
## Language

**Order**：
客戶送出、由本系統承接履行的採購請求。
_避免_：Purchase、transaction
```

- **要有立場。** 同一個概念有多個講法時，選定最好的那一個，其餘列在 `_避免_` 底下。
- **定義要緊。** 最多一到兩句。定義它「是什麼」，不是它「做什麼」。
- **只收錄專屬於這個專案 context 的術語。** 一般程式概念（timeout、錯誤型別、utility 模式）即使專案大量使用也不該收。加詞之前先問：這是這個 context 獨有的概念，還是一般程式概念？只有前者才能進。
- **出現自然的群聚時用子標題分組。** 若所有術語屬於同一個緊密領域，平鋪列表即可。
<!-- shared-contract:glossary:end -->

## 單一 vs 多重 context 的 repo

**單一 context（多數 repo）**：repo 根目錄放一份 `CONTEXT.md`。

檔案以 context 名稱為 H1，接一到兩句說明它是什麼、為何存在，再依上方格式維護術語。

**多重 context**：repo 根目錄放 `CONTEXT-MAP.md`，列出各 context 的位置與彼此關係：

```md
# Context Map

## Contexts

- [Ordering](./src/ordering/CONTEXT.md) — 接收並追蹤客戶訂單
- [Billing](./src/billing/CONTEXT.md) — 產生發票並處理付款
- [Fulfillment](./src/fulfillment/CONTEXT.md) — 管理倉儲揀貨與出貨

## Relationships

- **Ordering → Fulfillment**：Ordering 發出 `OrderPlaced` 事件；Fulfillment 消費後開始揀貨
- **Fulfillment → Billing**：Fulfillment 發出 `ShipmentDispatched` 事件；Billing 消費後產生發票
- **Ordering ↔ Billing**：共用 `CustomerId` 與 `Money` 型別
```

由現況推斷適用哪種結構：

- 存在 `CONTEXT-MAP.md` → 讀它找出各 context
- 只有根目錄 `CONTEXT.md` → 單一 context
- 兩者皆無 → 第一個術語敲定時，lazy 建立根目錄 `CONTEXT.md`

多重 context 時，推斷目前話題屬於哪個 context；不確定就問。
