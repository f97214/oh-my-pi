# 功能清單

本檔是**附來源的能力盤點**，供 agent 定位「這件事由哪裡負責」。敘事版本與截圖在根目錄 [`README.md`](../README.md)，兩者不重複維護 —— 有出入時以原始碼為準。

盤點來源：`README.md`、`AGENTS.md`、`docs/` 目錄、`package.json`、`Cargo.toml`。標為「未確認」的項目本次未回原始碼驗證。

## 工具表面

31 個工具與 `read`、`bash` 同一個命名空間。以 `--tools read,edit,bash,…` 釘住啟用集合；少用的工具留在 `xd://` device 後面（`read xd://` 列出，`write xd://<tool>` 執行，需開 `tools.xdev`）。

### 檔案與搜尋

| 工具 | 能力 | 文件 |
|---|---|---|
| `read` | 檔案、目錄、壓縮檔、SQLite、PDF、notebook、URL、`ssh://` 遠端路徑與內部 `://` scheme 走同一條路徑 | — |
| `write` | 建立或覆寫檔案、archive entry、SQLite row | — |
| `edit` | hashline patch，以內容雜湊當錨點，含失效錨點復原 | `packages/hashline` |
| `ast_edit` | 結構化改寫，套用前先預覽（ast-grep） | — |
| `ast_grep` | 50+ tree-sitter 文法的結構化查詢 | `crates/pi-ast` |
| `grep` | 檔案、glob 與內部 URL 的正規表達式搜尋 | `natives-text-search-pipeline.md` |
| `glob` | glob 路徑查找 | — |

### 執行時期

| 工具 | 能力 | 文件 |
|---|---|---|
| `bash` | 工作區 shell，46 個 in-process coreutils、可選 PTY、背景 job 派發 | `bash-tool-runtime.md` |
| `eval` | 持久的 Python 與 JavaScript cell，共用 prelude，可回呼 agent 自己的工具 | `python-repl.md` |

### 程式碼智慧

| 工具 | 能力 | 文件 |
|---|---|---|
| `lsp` | 診斷、導覽、符號、rename、code action、raw request（14 種操作） | `lsp-config.md` |
| `debug` | 驅動 DAP session：中斷點、單步、執行緒、堆疊、變數（28 種操作） | — |
| `security_scan` | 原生安全審查，可驅動 Codex Security 雲端掃描 | — |

`lsp` 的 rename 走 `workspace/willRenameFiles`，所以 re-export、barrel 檔與別名 import 會在檔案搬動前先更新。

### 協調

| 工具 | 能力 | 文件 |
|---|---|---|
| `task` | 平行 fan-out 子代理，可選工作區隔離，回傳 schema 驗證過的物件 | `task-agent-discovery.md` |
| `hub` | 對執行中 agent 傳訊、等待或取消背景 job、監督長跑行程 | `agent-hub.md` |
| `todo` | session todo list 的有序變更與階段追蹤 | — |
| `ask` | 互動式執行時的結構化追問（TUI 與 ACP 共用同一組 prompt card） | — |

### 桌面與網路

| 工具 | 能力 | 文件 |
|---|---|---|
| `browser` | Puppeteer 分頁、CDP 附著的 app、或透過 relay 接管你自己的 Chrome | — |
| `computer` | 對主機桌面跑持久 JS：視窗、螢幕擷取、原生輸入、AX tree、剪貼簿 | `computer-use.md` |
| `web_search` | 單一查詢跨多個供應商，回傳答案加引用 | — |
| `github` | GitHub CLI 操作 | — |
| `generate_image` | Gemini／GPT／xAI Grok 影像模型 | — |
| `inspect_image` | 本地影像的視覺模型分析（模型看不見時自動啟用） | — |
| `tts` | xAI Grok Voice，五種內建聲音，WAV 或 MP3 | — |

### 記憶與 skill

| 工具 | 能力 | 文件 |
|---|---|---|
| `checkpoint` / `rewind` | 標記對話狀態以便後續收合回報／修剪探索性 context | — |
| `retain` / `recall` / `reflect` / `memory_edit` | 記憶庫的寫入、搜尋、綜合與編輯 | `memory.md`、`mnemosyne-memory-backend.md` |
| `learn` / `manage_skill` | 捕捉可重用教訓、建立／更新／刪除隔離的 managed skill | `skills.md` |

**預設關閉、需設定開啟**：`github`、`security_scan`、`generate_image`、`tts`、`checkpoint`、`rewind`，以及記憶工具（依 `memory.backend`）。

## Session 與流程控制

| 能力 | 說明 | 文件 |
|---|---|---|
| Magic keywords | `ultrathink`、`orchestrate`、`workflowz` 三個小寫獨立字啟用特化行為；只在散文中觸發，不在 code span、fenced block、XML/HTML、識別字或路徑中 | `magic-keywords.md` |
| `/vibe` | 導演模式，驅動常駐的 `fast`/`good` worker session，工具面只留 `read` | `vibe-mode.md` |
| `/fresh` | 重置供應商串流狀態（陳舊 prompt cache、卡住的串流），不動本地 transcript | `session-operations-export-share-fork-resume.md` |
| Time-traveling stream rules | regex 命中時在 token 中途中止串流、注入規則、從同一點重試；注入內容能撐過 compaction | `ttsr-injection-lifecycle.md` |
| Advisor | 第二個模型讀每一輪，行內注入 aside／concern／blocker，跑在自己的 context 與模型上 | `advisor-watchdog.md` |
| `/collab` | 把 session 放上 relay 並給出連結與 QR；讀寫或唯讀，frame 在 client 端封裝，relay 看不到金鑰 | `collab.md` |
| Compaction | context 壓縮與非壓縮重試策略 | `compaction.md`、`non-compaction-retry-policy.md` |
| `/review` | 專用 reviewer 子代理平行掃 branch、單一 commit 或未提交工作，issue 分 P0–P3 並給信心分數與 verdict | — |
| `omp commit` | 讀工作樹後把不相關改動拆成原子 commit 並依相依排序；有環就拒絕，lock 檔完全排除在分析外 | — |

## 模型路由

十個角色依意圖分流：`default`、`smol`、`slow`、`plan`、`commit`、`vision`、`designer`、`task`、`advisor`、`tiny`。啟動時以 `--smol`、`--slow`、`--plan` 覆寫；`Ctrl+P` 循環目前角色的已設定模型；`/model` 在 session 中途切換。

| 機制 | 說明 |
|---|---|
| 自訂供應商 | 在 `~/.omp/agent/models.yml` 宣告任何說得通 `openai-completions`、`openai-responses`、`openai-codex-responses`、`azure-openai-responses`、`anthropic-messages`、`bedrock-converse-stream`、`google-generative-ai`、`google-gemini-cli`、`google-vertex` 的端點 |
| Fallback chain | `retry.fallbackChains` 下的 per-role 或 per-model 鏈；主要端點 429 或撞配額時由下一個接手，冷卻後復原 |
| 路徑範圍模型 | `enabledModels`、`disabledProviders` 可加 `path:` 前綴，只在特定 repo 生效（涵蓋該路徑及其下） |
| 輪替憑證 | 每個供應商可疊多把 API key，執行時以 session affinity 與 per-credential backoff 輪替 |

供應商總數 60+，涵蓋直連 API、gateway、訂閱制 coding plan 與本地 server。細節見 `providers.md`、`models.md`。

## 擴充

| 能力 | 說明 | 文件 |
|---|---|---|
| Extension | TypeScript module，與內建同一套 tool API、slash command registry、hotkey table 與 TUI primitive；沒有保留字 | `extensions.md`、`extension-loading.md` |
| 繼承既有設定 | 首次執行時直接讀 `.claude`、`.cursor`、`.windsurf`、`.gemini`、`.codex`、`.cline`、`.github/copilot`、`.vscode` 的 rules、skills 與 MCP server，維持原生格式，不需要遷移腳本 | `context-files.md` |
| Marketplace | 本地保留、包進 marketplace 或發到 npm；`/reload-plugins` 熱載 | `marketplace.md`、`plugin-manager-installer-plumbing.md` |
| MCP | 多種 transport 與執行時期生命週期 | `mcp-*.md` |
| 內部 URL scheme | 16 種（`pr://`、`issue://`、`agent://`、`skill://`、`ssh://` 等）在所有 FS 形狀的工具中透明解析；`read pr://1428` 與 `read src/foo.ts` 回傳同樣的形狀 | — |
| `conflict://N` | 每個 merge conflict 一個 URL，寫入 `@theirs`／`@ours`／`@base` 即解決；批次形式 `conflict://*` | — |

## 未確認

- 工具數（31）、LSP 操作數（14）、DAP 操作數（28）、供應商數（60+）、搜尋後端數（23）皆取自 `README.md`，本次未逐一回原始碼清點。
- `README.md` 效能對照表（Grok Code Fast 1 6.7% → 68.3% 等）取自該檔，未驗證其量測方法。
