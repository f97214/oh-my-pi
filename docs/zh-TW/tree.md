> 這是 [`docs/tree.md`](../tree.md) 的繁體中文翻譯。
> 翻譯基準：`1c7170e11`（2026-08-14）。**英文原文為準** —— 上游更新後本檔可能過期。

# `/tree` 命令參考

`/tree` 開啟互動式的 **Session Tree** 導覽器。它讓你跳到目前 session 檔案中的任一筆項目，並從那個點繼續。

這是**檔案內的 leaf 移動**，不是匯出成新的 session。

## `/tree` 做什麼

- 從目前的 session 項目建出一棵樹（`SessionManager.getTree()`）
- 開啟 `TreeSelectorComponent`，具備鍵盤導覽、篩選與搜尋
- 選取時呼叫 `AgentSession.navigateTree(targetId, { summarize, customInstructions })`
- 依新的 leaf 路徑重建可見的對話
- 選到 user／custom 訊息時，可選擇性地把文字預填進編輯器

主要實作：

- `src/slash-commands/builtin-registry.ts`（`/tree`、`/branch` 命令路由）
- `src/modes/controllers/input-controller.ts`（keybinding 接線、double-escape 行為）
- `src/modes/controllers/selector-controller.ts`（樹狀 UI 啟動 + 摘要提示流程）
- `src/modes/components/tree-selector.ts`（導覽、篩選、搜尋、標籤、渲染）
- `src/session/agent-session.ts`（`navigateTree` 的 leaf 切換 + 可選摘要）
- `src/session/session-manager.ts`（`getTree`、`branch`、`branchWithSummary`、`resetLeaf`、標籤保存）

## 怎麼開啟

下列任一方式都會開啟同一個選取器：

- `/tree`
- 為 `app.session.tree` 動作設定的 keybinding
- 當 `doubleEscapeAction = "tree"`（預設）時，在空白編輯器上連按兩次 escape
- 當 `doubleEscapeAction = "tree"` 時的 `/branch`（會導向樹狀選取器，而不是只含 user 訊息的 branch 選單）

## 樹狀 UI 模型

這棵樹是依 session 項目的 parent 指標（`id` / `parentId`）渲染出來的。

- 子節點依時間戳記遞增排序
- 含有目前 active leaf 的分支會排在選取器最前面；其他歷史仍然可達
- Active 分支（root 到 leaf 的路徑）會以圓點標示
- 標籤以 `[label]` 形式渲染在節點文字之前
- 找不到 parent、self-parent 的項目，以及明確為 null parent 的項目都會成為 root；多個 root 共用一個虛擬的分岔 root

```text
Example tree view (active path marked with •):

├─ user: "Start task"
│  └─ assistant: "Plan"
│     ├─ • user: "Try approach A"
│     │  └─ • assistant: "A result"
│     │     └─ • [milestone] user: "Continue A"
│     └─ user: "Try approach B"
│        └─ assistant: "B result"
```

選取器會以目前選取項為中心重新置中，最多顯示：

- `max(5, floor(terminalHeight / 2))` 列

## 樹狀選取器內的按鍵

- `Up` / `Down`：移動選取（會繞回）
- `Alt+Up` / `Alt+Down`：跳到上／下一個 user 或 assistant 回合
- `Page Up` / `Page Down`，或 `Left` / `Right`：翻頁
- `Home` / `End`：第一／最後一個可見項目
- `Enter`：選取節點
- `Shift+Enter`：直接摘要並切換，不開啟摘要選項提示
- `Esc`：搜尋中則清除搜尋；否則關閉選取器
- `Ctrl+C`：關閉選取器
- 輸入文字：附加到搜尋字串
- `Backspace`：刪除一個搜尋字元
- `Shift+L`：搜尋為空時，編輯／清除標籤
- `Ctrl+O`：向前循環切換篩選
- `Shift+Ctrl+O`：向後循環切換篩選
- `Alt+D/T/U/L/A`：直接跳到某個篩選

## 篩選與搜尋語意

初始模式取自 `treeFilterMode`（預設 `default`）。各模式依此順序循環：

1. `default`
2. `no-tools`
3. `user-only`
4. `labeled-only`
5. `all`

### `default`

顯示對話類節點，加上所有未被明確抑制的項目型別。它會隱藏這些設定／記帳類的項目型別：

- `label`
- `custom`
- `model_change`
- `thinking_level_change`

其他沒有專屬渲染的項目型別（例如 service-tier、title、credential-pin、reset 與 mode 項目）在目前的程式碼中可能顯示為空白列。

### `no-tools`

與 `default` 相同，再額外隱藏 `toolResult` 訊息。

### `user-only`

只顯示 role 為 `user` 的 `message` 項目。

### `labeled-only`

只顯示目前解析得到標籤的項目。

### `all`

session 樹中的全部內容，包含記帳／自訂項目。

### 只含工具呼叫的 assistant 節點行為

只包含 tool call（沒有標準文字）的 assistant 訊息，在**所有**篩選模式下都會被隱藏，包含 `all`，除非：

- 該訊息是 error／aborted（`stopReason` 既不是 `stop` 也不是 `toolUse`），或
- 它就是目前的 leaf

### 搜尋行為

- 查詢字串以空白切成 token
- 比對是模糊的（子序列）且不分大小寫（`fuzzyMatch`）
- 所有 token 都必須命中（AND 語意）
- 可搜尋的文字包含標籤、role，以及各型別專屬的內容（訊息文字、branch 摘要文字、custom 型別、工具命令片段等）

## 選取結果（重要）

`navigateTree` 依所選項目的型別決定新的 leaf 行為：

### 選到 `user` 訊息

- 新的 leaf 變成該項目的 `parentId`
- 選到 root 的 user 訊息會把 leaf 重設到 root
- 文字與圖片附件會被重建成可編輯的草稿
- **只有在編輯器目前為空時**，選取器才會寫入該草稿

### 選到 `custom_message`

- 一般的 custom 訊息採用與 user 訊息相同的 parent-leaf 規則與文字預填
- `skill-prompt` 類的 custom 訊息不可編輯；選到它時會像其他非 user 項目一樣直接落在該節點

### 選到過去的 `ask` 工具結果

- 互動式的 `/tree` 會重新開啟原本的問題 UI，而不是沿用過期的答案
- 取消不會改變這棵樹
- 新答案會以 sibling 的 tool result 形式附加，保留舊答案的分支，然後代理從它繼續
- 若舊版／損壞的資料無法還原出原本的問題，選取會退回成單純的 leaf 移動

### 選到其他節點

- 新的 leaf 變成所選節點的 id
- 編輯器不預填

### 選到目前的 leaf

- 通常會以 `Already at this point` 關閉
- 但目前 leaf 若是 `ask` 結果，仍然允許重新作答的流程

```text
Selection decision (simplified):

selected node
   │
   ├─ current leaf (not ask result)? ──> close selector (no-op)
   │
   ├─ ask tool result? ──> re-answer as a sibling branch when questions are recoverable
   │
   ├─ user or ordinary custom message? ──> leaf := parentId (or root)
   │                                         + prefill only into an empty editor
   │
   └─ otherwise ──> leaf := selected node id
                    + no editor prefill
```

## 切換時的摘要流程

摘要提示由 `branchSummary.enabled` 控制（預設 `false`）。`Shift+Enter` 不論該設定為何都會直接要求摘要；此時必須有可用的模型與供應商憑證。

啟用提示時，一般的 Enter 會提供：

- `No summary`
- `Summarize`
- `Summarize with custom prompt`

流程細節：

- 在摘要提示中按 Escape 會重新開啟樹狀選取器
- 取消自訂 prompt 會回到摘要選項
- 摘要進行中，UI 顯示載入指示，並把 Esc 綁到 `abortBranchSummary()`
- 若摘要被中止，樹狀選取器會重新開啟，且不套用任何移動

`navigateTree` 的內部流程：

- flush 待處理的 bash 輸出並驗證目標
- 收集從舊 leaf 到共同祖先之間被放棄分支的項目
- 發出可取消的 `session_before_tree`；extension 可以提供所要求的摘要
- 只有在有要求、項目確實需要摘要，且 hook 沒有提供摘要時，才跑預設的 summarizer
- 視情況套用 `branchWithSummary(...)`、`branch(newLeafId)` 或 `resetLeaf()`
- 重建模型 context、checkpoint／rewind 狀態、advisor 狀態、todo，以及受歷史改寫影響的供應商 session
- 發出 `session_tree`，並在 handler 可能已附加項目時再重建一次

若要求了摘要但沒有東西可摘要，導覽會照常進行，不產生摘要項目。

## 標籤

樹狀 UI 中的標籤編輯會呼叫 `appendLabelChange(targetId, label)`。

- 非空標籤會設定／更新解析後的標籤
- 空標籤會清除它
- 標籤以 append-only 的 `label` 項目儲存
- 樹狀節點顯示的是解析後的標籤狀態，不是原始的標籤項目歷史

## `/tree` 與鄰近操作的差異

| 操作 | 作用範圍 | 結果 |
| --------- | ------------------------------------------------ | -------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `/tree` | 目前的 session 檔案 | 把 leaf 移到選取的點（同一個檔案） |
| `/branch` | 通常是目前 session 檔案 -> 新的 session 檔案 | 預設從選取的 **user** 訊息分支到一個新的 session 檔案；若 `doubleEscapeAction = "tree"`，`/branch` 改為開啟樹狀導覽 UI |
| `/fork` | 整個目前 session | 把 session 複製成一個新的持久化 session 檔案 |
| `/resume` | Session 清單 | 切換到另一個 session 檔案 |

關鍵差異：`/tree` 是**單一 session 檔案內**的導覽／重新定位工具。`/branch`、`/fork` 與 `/resume` 都會改變 session 檔案的脈絡。

## 操作者工作流程

### 從較早的 user prompt 重跑，且不失去目前分支

1. `/tree`
2. 搜尋／選取較早的 user 訊息
3. 選 `No summary`（需要的話選摘要）
4. 在編輯器中編輯預填的文字
5. 送出

效果：新分支在同一個 session 檔案內從選取點長出來。

### 離開目前分支並留下脈絡麵包屑

1. 啟用 `branchSummary.enabled`
2. `/tree` 並選取目標節點
3. 選 `Summarize`（或自訂 prompt）

效果：在繼續之前，於目標位置附加一筆 `branch_summary` 項目。

### 調查被隱藏的記帳項目

1. `/tree`
2. 按 `Alt+A`（all）
3. 搜尋 `model`、`thinking`、`custom` 或標籤

效果：檢視完整的內部時間軸，而不只是對話節點。

### 標記樞紐點以便日後跳轉

1. `/tree`
2. 移動到某筆項目
3. `Shift+L` 並設定標籤
4. 日後用 `Alt+L`（`labeled-only`）快速跳轉

效果：在持久的分支地標之間快速導覽。
