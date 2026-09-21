> 這是 [`docs/vibe-mode.md`](../vibe-mode.md) 的繁體中文翻譯。
> 翻譯基準：`1c7170e11`（2026-08-14）。**英文原文為準** —— 上游更新後本檔可能過期。

# Vibe mode

Vibe mode 把最上層的互動 session 變成常駐背景 worker session 的**導演（director）**，而不是讓它自己編輯或執行命令。導演的可用工具縮減為 `read`、可選的由 parent 持有的 `todo`，以及五個 worker 控制工具。搜尋、編輯、執行與建置都由 worker 做；導演則透過讀取被動過的檔案來驗證它們的宣稱。`todo` 若可用，只屬於 parent 導演。

## 啟用與停用

用 `/vibe` slash command 切換：

```text
/vibe                 # enter vibe mode
/vibe fix the flaky test in packages/tui   # enter and submit a first directive
/vibe                 # run again to exit
```

- 進入時會啟動一個 parent-session worker scope、安裝 vibe 工具、把可用工具集縮減為 `read`、可選的 parent 持有 `todo` 與 vibe 工具，並注入導演指示。
- 行內 prompt（`/vibe <prompt>`）會進入該模式並把那段 prompt 當成第一道指令送出。
- 離開時會還原先前的工具集、取消進行中的 worker 回合、終止該 scope 內的所有 worker session，並保存終止的生命週期紀錄。worker 絕不會存活過一次刻意的模式離開。
- Vibe mode 與 plan／goal 模式互斥 —— **啟用中與暫停中的都算**；請先離開那些模式。
- Vibe mode 啟用期間，啟動、fork、移動或交接 session 都會被拒絕。
- 模式開啟時狀態列會顯示 `Vibe` 指示。

`/vibe` 是互動式 TUI 命令。模式與 worker 的生命週期事件會與 parent session 一起保存。恢復一個目前模式為 `vibe` 的 session 時，已完成的 worker 會連同其子 transcript 一起被復原成 idle／parked session；被行程重啟中斷的回合**不會**自動恢復。明確被終止或因離開模式而結束的 worker 維持終止狀態。

## 兩種 worker 層級

每個 worker 都是真正的、keep-alive 的 task-executor 子代理，具備一般的 coding 工具面與自己的持久化子 transcript。spawn 時選擇層級：

| 層級 | Bundled agent | 預設角色 | 適用於 |
| ------ | ------------- | ------------ | --------------------------------------------------- |
| `fast` | `sonic` | `@smol` | 機械性執行、草稿、大量工作 |
| `good` | `task` | `@task` | 設計、需要判斷的取捨，以及審查 `fast` 的產出 |

層級一律選用 bundled 的 `sonic` 或 `task` 定義，**不會**選到同名的、透過 discovery 找到的自訂 agent。除此之外，模型解析與 task-agent 路由一致：`task.agentModelOverrides.sonic` / `.task` 優先於 bundled agent 的模型，角色別名透過 `modelRoles` 解析，並以 parent 的 active／default 模型作為 fallback。

## Worker 控制工具

| 工具 | 輸入與行為 |
| ------------ | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `vibe_spawn` | `{ cli: "fast" \| "good", prompt, name? }`。以一份完整、自給自足的初始 brief 啟動一個空白 worker。`name` 會被淨化並限制在 48 字元；省略時自動產生 id。 |
| `vibe_send` | `{ session, message }`。在串流回合的下一個步驟導引它；若回合存在但無法導引，則排入一個自動的下一回合；若處於 idle／parked，立即開始下一回合。 |
| `vibe_wait` | `{ sessions?, timeout? }`。等待第一個被監看的回合結束（省略時等所有進行中的 worker），預設 30 秒。它會確認已結束的 job，避免同一份結果被送達兩次。 |
| `vibe_kill` | `{ session }`。取消進行中的回合、清除排隊訊息、釋放該 worker，並保留任何已初始化的 transcript 於 `history://<id>`。 |
| `vibe_list` | `{}`。依 spawn 順序列出 session，含層級、狀態、回合／佇列計數、解析後的模型與近期活動。 |

spawn 與 send 會立即回傳。每個 worker 回合的結果會透過非同步 job manager 自行送達導演的對話中；過長的回應文字在那裡會被截成預覽，完整輸出可在 `agent://<id>` 取得。讓 `fast` 與 `good` worker 各自跑在獨立的工作流上並行推進，是常態用法。

## 作用範圍與失敗行為

Worker id 的作用範圍限於持有它的 agent 與 parent session；來自其他 scope 的 worker 會被回報為未知且無法控制。spawn 需要 session 的非同步 job manager。spawn 失敗會拆除半成品紀錄；回合失敗會以失敗的 job 結果自行送達，而可回復的 keep-alive worker 會回到 `idle` 等待下一次 `vibe_send`。若某個 worker 已註冊的子 session 再也無法解析，它會變成 `dead`。

## 工作流程

1. 把請求拆成互相獨立的工作流 —— 每個工作流一個常駐 worker，讓各自累積有用的對話脈絡。
2. 呼叫 `vibe_spawn` 並給一份自給自足的 brief：檔案、限制條件與可觀察的驗收標準。worker 是空白起始的，**永遠看不到**導演的對話。
3. 回合進行中就繼續指揮其他 worker。只有在被擋住時才用 `vibe_wait`；逾時的等待可以重下。
4. 用 `vibe_send` 自然地下修正與後續步驟。回合中途的 send 會在可能時導引該回合；否則會自動變成該 worker 的下一回合。
5. 結果送達時，`read` 被動過的檔案；預覽不足時檢視完整輸出。已驗證的工作透過可選的 parent `todo` 收攏。
6. 依難度分流：用 `fast` 打草稿，機械性執行卡住或需要判斷時升級到 `good`。
7. 對已完成／卡住的 worker 用 `vibe_kill`。離開模式會終止整個剩餘的 scope。

導演始終要為最終結果負責：worker 完成只代表那個回合結束了，**不代表它的宣稱是正確的**。
