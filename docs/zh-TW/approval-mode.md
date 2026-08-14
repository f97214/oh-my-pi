> 這是 [`docs/approval-mode.md`](../approval-mode.md) 的繁體中文翻譯。
> 翻譯基準：`1c7170e11`（2026-08-14）。**英文原文為準** —— 上游更新後本檔可能過期。

# 工具核准模式

工具核准有三個輸入：

1. **工具宣告** —— 每個工具都可以宣告一個 `approval` 層級：
   - `read`：讀取資料，或只更新 UI 層的 session metadata。
   - `write`：變更 workspace／session 狀態，但不執行任意程式碼。
   - `exec`：執行程式碼、開 shell、驅動瀏覽器、spawn 代理，或進行類似的大範圍動作。
2. **工具政策** —— 物件形式的宣告可以設定 `policy: allow | deny | prompt`，並可選擇加上 `override` 與理由。這用於依參數而定的安全／樣式規則。
3. **使用者政策** —— `tools.approval.<toolName>: allow | deny | prompt` 會覆寫目前的模式，但**不能**繞過工具自身的 deny/prompt 政策，也不能繞過非 yolo 模式下的安全覆寫。

沒有 `approval` 宣告的工具，以及格式錯誤的核准決策，一律當成 `exec` 處理。這是未知自訂工具的安全預設值。MCP server 工具宣告為 `write`。

## 模式

以 `tools.approvalMode` 設定：

| 模式 | 自動核准 | 會詢問 |
| ---------------- | ----------------------- | --------------- |
| `always-ask` | `read` | `write`、`exec` |
| `write` | `read`、`write` | `exec` |
| `yolo`（預設） | `read`、`write`、`exec` | 無 |

`--auto-approve` 與 `--yolo` 會為該 session 強制 `tools.approvalMode: yolo`。

## 使用者覆寫

`tools.approval` 在**所有**模式下都會被採用：

```yaml
tools:
  approvalMode: write
  approval:
    bash: prompt
    read: allow
    mcp__filesystem__delete: deny
```

每次 tool call 的解析順序：

1. 評估 `tool.approval(args)`；省略或格式錯誤的決策預設為 `exec` 層級。
2. 工具宣告的 `policy: deny` 一律拒絕。接著檢查使用者的 `deny`，同樣一律拒絕。
3. 在 `yolo` 下，工具明確的 `allow`／`prompt` 政策勝出；否則有效的使用者政策勝出，再否則就允許該呼叫。**光是 `override` 旗標在 `yolo` 下不會強制詢問。**
4. 在非 yolo 模式下，`override: true` 的決策只有在同時帶有工具 `policy: allow` 時才允許；其他所有未被拒絕的情況都會詢問。
5. 沒有 override 時，工具明確的 `allow`／`prompt` 政策勝出，其次是有效的使用者政策。
6. 完全沒有明確政策時，由目前模式依層級決定自動核准或詢問。

政策字串會去除空白並正規化大小寫。無效的使用者值會被忽略。

## 安全覆寫

工具可以用物件形式的 approval 強制詢問：

```ts
approval: { tier: "exec", override: true, reason: "Critical pattern detected" }
```

`bash` 用這個機制處理關鍵的破壞性樣式，例如 `rm -rf /`、fork bomb、遠端下載後執行、寫入 `/etc/passwd`，以及主機關機命令。它同時支援設定的 `bash.patterns` 規則：`deny` 是絕對的，`prompt` 強制詢問，`allow` 則明確地在 `write` 層級允許該命中的呼叫。理由會顯示在核准提示中。在 `yolo` 下，單純的關鍵覆寫會被忽略，但明確的工具／使用者 `prompt` 或 `deny` 政策仍然生效。

### Computer 安全機制

預設停用的 [`computer` 工具](../computer-use.md)依呼叫的 `read_only` 宣告決定層級：

- `read_only: true` 使用 `read`；
- `read_only: false`、缺少該欄位、參數格式錯誤，或任何其他值，都使用 `exec`。

核准提示在適用時會顯示 `read-only`，後面接著送出的 JavaScript（由標準格式化器截斷至 2,000 字元）。`read_only` 是一種由核准層級強制執行的**信任宣告**，不是對腳本做靜態分析。

另外，來自供應商的 computer-use 呼叫可能帶有 `pendingSafetyChecks` metadata。只要有任何待處理的檢查，就會強制互動式詢問，不論是否為 yolo、是否有 per-tool `allow`，或是否已核准過 `xd://` 派發。提示會列出每個 safety-check 的代碼、訊息，以及經過淨化／截斷的資料。沒有互動式 UI 時，該呼叫會 fail closed，訊息為 `pending provider safety checks but no interactive UI is available`。

工具核准**不等於**授權底層的真實世界動作。螢幕上的文字是不可信的，不能覆寫使用者的直接指示。除非使用者的直接訊息已經授權，否則有後果的動作仍然需要在風險點確認確切的目標、範圍與數值。

## 各工具的提示細節

工具可以用 `formatApprovalDetails(args)` 加上核准提示的內文行。標準提示包含：

- `Allow tool: <name>`
- 對未加註解的 `mcp__...` 工具顯示 `Origin: MCP server tool`
- 當工具決策有提供理由時顯示 `Reason: <reason>`
- 工具專屬細節，例如命令、路徑、程式碼、瀏覽器動作或子代理指派

## 在工具上定義 approval

內建工具與自訂工具使用相同的形狀：

```ts
export type ToolTier = "read" | "write" | "exec";
export type ToolApprovalDecision =
  | ToolTier
  | {
      tier: ToolTier;
      reason?: string;
      override?: boolean;
      policy?: "allow" | "deny" | "prompt";
    };
export type ToolApproval = ToolApprovalDecision | ((args: unknown) => ToolApprovalDecision);

approval?: ToolApproval;
formatApprovalDetails?: (args: unknown) => string | string[] | undefined;
```

範例：

```ts
approval: "read";

approval: (args) => (LSP_READONLY_ACTIONS.has(args.action) ? "read" : "write");

approval: (args) =>
  isCritical(args.command)
    ? { tier: "exec", override: true, reason: "Critical pattern detected" }
    : "exec";

approval: (args) =>
  isForbidden(args)
    ? { tier: "exec", policy: "deny", reason: "Blocked by tool policy" }
    : "write";
```

## ACP session

ACP（`omp acp`）使用與一般 OMP 啟動相同的設定解析器。全域 `~/.omp/agent/config.yml` 適用、ACP session `cwd` 的專案設定適用，而傳給 ACP server 行程的任何 `--config <file>` 覆蓋層，也適用於該行程建立的 session。

要自動核准 ACP 的 tool call，在全域或專案設定中設定模式：

```yaml
tools:
  approvalMode: yolo
```

或以執行時覆寫、單一行程的設定覆蓋層啟動 ACP server：

```bash
omp acp --yolo
omp acp --auto-approve
omp acp --approval-mode yolo
omp acp --config ./acp-yolo.yml   # file contains tools.approvalMode: yolo
```

優先順序就是一般的設定優先順序：執行時旗標（`--approval-mode`、`--auto-approve`、`--yolo`）覆寫 `--config` 覆蓋層，後者覆寫專案設定，專案設定覆寫全域設定。ACP 目前**沒有**定義 `session/new`、`session/load` 或 `session/resume` 的核准政策欄位，所以需要 per-session yolo 的 ACP client，應該用上述旗標之一或 session 專屬的 `--config` 覆蓋層另外啟動一個 `omp acp` 行程。

`tools.approvalMode: yolo` 在被明確設定或由執行時旗標提供時，完全適用於 ACP。它會跳過 OMP 的核准提示，也會跳過 `bash`、`edit`、`delete` 與 `move` 的 ACP client 權限閘門 —— 除非 `tools.approval.<tool>` 是 `prompt` 或 `deny`。schema 的預設值是 `yolo`，但採用預設設定的 ACP session 仍會保留 client 權限閘門；client 若想要無人值守執行，請明確設定 `tools.approvalMode: yolo`。

當 ACP 需要核准時，OMP 會透過 ACP client 而非終端機 TUI 進行。受 client 閘門管控的 `bash`、`edit`、`delete` 與 `move` 呼叫使用 ACP 的 `session/request_permission`；一般核准提示則在 client 宣告支援 `elicitation.form` 時使用 form elicitation。被拒絕、取消或不支援的提示會拒絕／取消該 tool call；OMP **不會**默默放行。

## 子代理

子代理以 headless 方式執行並套用 `tools.approvalMode: yolo`，讓一般的層級式提示不會把它們卡住。parent 的 `task` 核准才是授權邊界。使用者的 `tools.approval.<tool>` 設定依然具有決定性：`deny` 擋下該工具、`allow` 允許它，而 `prompt` 在 headless 子代理中無法被滿足，會拒絕該呼叫。
