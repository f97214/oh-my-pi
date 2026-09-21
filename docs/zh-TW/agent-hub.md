> 這是 [`docs/agent-hub.md`](../agent-hub.md) 的繁體中文翻譯。
> 翻譯基準：`1c7170e11`（2026-08-14）。**英文原文為準** —— 上游更新後本檔可能過期。

# Agent Hub

Agent Hub 是用來觀看與控制目前 session 相關子代理的互動式 TUI。它整合了即時名冊、各代理的活動與用量、transcript 存取，以及導引（steer）、復活（revive）與終止（kill）控制。主代理不會列在裡面，因為它的對話就是當前的 session 檢視。

Hub 在 session 被恢復時，也會從該 session 已保存的產物中找出 parked 的子代理。Advisor 的 transcript 檔案會以唯讀列的形式出現。

## 開啟 Hub

| 輸入 | 行為 |
| -------------- | ---------------------------------------------------------------------------------------------- |
| `Alt+A` | 透過 `app.agents.hub` 開啟或關閉 Agent Hub。即使名冊是空的也會開啟。 |
| `Ctrl+S` | 透過舊有的 `app.session.observe` 動作開啟或關閉同一個 Hub。 |
| 連按兩下 `←` | 當目前 session 有代理可顯示時，從空白的主 session 編輯器開啟 Hub。 |

執行 `/hotkeys` 可查看目前生效的組合鍵。兩個動作都可以在 `~/.omp/agent/keybindings.yml` 重新對應：

```yaml
app.agents.hub: Alt+A
app.session.observe: Ctrl+S
```

連按兩下 `←` 這個手勢不是一個 keybinding 動作。當焦點在某個子代理上時，連按兩下 `←` 會回到主 session，而不是開啟 Hub。

## 名冊與檢視器

名冊會依 session 的代理註冊表與進度事件更新。它的自適應列會顯示：

- 狀態（`running`、`idle`、`parked` 或 `aborted`）、代理身分、parent，以及未讀的 IRC 數量；
- 模型角色、解析後的模型，以及距離上次活動的時間；
- 指派的任務或目前的活動；
- 成本、活躍時間或經過時間、request 數、tool-call 數與 token 數。

標題列會彙總所有已量測代理的狀態與用量。按 `t` 可在穩定的扁平名冊與 parent/child 樹狀檢視之間切換。

終端機夠寬時，被選取代理的檢視器會顯示在名冊旁邊。終端機較窄時，按 `Tab` 用它取代名冊。檢視器額外提供：

- 目前的工具與參數、最後的意圖，以及重試狀態；
- context window 的使用量（可取得時）；
- parent 與 child 的血緣關係；
- 輸出與 patch 路徑，以及存在時的隔離 worktree 分支 metadata。

各項指標取決於該代理有哪些進度或已保存的用量資料。缺少資料時會顯示 `usage —`，而不是給出估計值。

### 名冊控制

| 按鍵或輸入 | 動作 |
| --------------------------- | ---------------------------------------------------------------------------- |
| `j` / `k`、`↑` / `↓`、滾輪 | 選取代理。 |
| `Enter` 或點擊 | 開啟選取的代理。 |
| `t` | 切換扁平與 parent/child 檢視。 |
| `Tab` | 在窄終端機上切換檢視器。 |
| `PageUp` / `PageDown` | 捲動已開啟的檢視器。 |
| `r` | 復活選取的 parked 代理。 |
| `x` | 必要時先中止進行中的回合，然後終止並釋放選取的代理。 |
| `Esc` | 在窄終端機上先關閉檢視器，再關閉 Hub。 |

只有 `parked` 狀態的代理可以被復活。`x` 是立即生效的；只有在你確定要捨棄該代理實例時才使用。

## 讀取與導引子代理

對一般的本機子代理，按 `Enter` 或點擊會把主 TUI 的焦點移到該代理的 session 並關閉 Hub。聚焦一個 parked 代理會使其復活。此時 transcript、狀態列與編輯器都屬於那個子代理：

1. 讀取它的即時 transcript 與工具活動。
2. 輸入訊息並按 `Enter`，可導引進行中的回合，或對 idle 的代理下 prompt。
3. 在編輯器為空時按 `Esc`，或連按兩下 `←`，回到主 session。

導引走的是一般的 prompt 路徑，所以訊息與回應都會寫進該子代理已保存的 session 歷史。子代理被聚焦時，`Esc` 是回到主 session，**不會**中斷該子代理。

沒有可聚焦本機 session 的情境，則改用 Hub 的全螢幕 transcript 檢視器。這包含 collab 訪客與 advisor 列。該檢視器會漸進式地 tail 以檔案為後端的 transcript，並且只在選取的代理可被傳訊時才提供輸入列。在那裡送出訊息的語意相同：parked 就復活、running 就導引、idle 就下 prompt。

## 已保存的代理與 advisor

為一個已保存的 session 開啟 Hub 時，會掃描該 session 的產物樹。歷史子代理的 JSONL 檔案會變成 parked 列；被終止代理的 tombstone 會讓它維持 aborted。巢狀子代理會保留其 parent/child 血緣。輸出與 patch 產物會掛在對應的檢視器列上。

Advisor 的 transcript 檔案（`__advisor*.jsonl`）會在其所屬 session 底下以 `advisor` 類別的列出現。它們是可觀測性紀錄，不是對等節點：

- 它們的 transcript 可以開啟與追蹤；
- 不能對它們傳訊；
- 不能復活；
- 不能終止。

這些限制同樣適用於控制 host 端 Hub 的 collab 訪客。

## 相關介面

Agent Hub 是面向人的即時 session 檢視。鄰近的命令與內部 URL 各有更窄的用途：

- `/jobs` 印出正在執行與最近結束的非同步工具 job 快照。它**不**取代各代理的 transcript 或控制檢視。
- `history://<id>` 給 coding agent 一份即時或 parked 子代理的精簡 transcript。
- `agent://<id>` 解析子代理已儲存的最終輸出產物；它不是即時 transcript。
- `hub` 的 `list` 把對等名冊暴露給 coding agent，`hub` 的 `send` 則以程式方式導引一般子代理或對它追加訊息。對 parked 子代理傳訊會使其復活。

Advisor 列刻意排除在面向代理的 `hub`、`history://` 與 `agent://` 對等工作流之外。

另見 [Task Agent Discovery and Selection](../task-agent-discovery.md)、[Collaboration](../collab.md) 與 [Advisor, WATCHDOG.md, and WATCHDOG.yml](../advisor-watchdog.md)。
