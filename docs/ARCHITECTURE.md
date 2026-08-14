# 架構

oh-my-pi（binary 名稱 `omp`）是一個以 Bun 執行的 TypeScript monorepo，底下掛一個 Rust workspace 提供效能關鍵的原生能力。它是 [pi-mono](https://github.com/badlogic/pi-mono) 的 fork，重寫為 coding-first 的 agent 介面。

來源：`package.json`、`Cargo.toml`、`bunfig.toml`、`README.md`、`AGENTS.md`。

## 兩個 workspace

| Workspace | 宣告位置 | 成員 |
|---|---|---|
| Bun / npm | `package.json:workspaces` = `packages/*`、`python/robomp/web` | `packages/` 下 17 個套件 |
| Cargo | `Cargo.toml` | `crates/` 下 7 個 crate 加 `crates/vendor/brush-core` |

套件管理器固定為 `bun@1.3.14`（`package.json:packageManager`）；Rust toolchain 固定為 `nightly-2026-07-28`（`rust-toolchain.toml`）。另有 Bazel 設定（`MODULE.bazel`、`BUILD.bazel`、`.bazelrc`）與 Nix flake（`flake.nix`），供替代建置路徑使用。

## 相依方向

由上而下，上層依賴下層，不得反向：

```
packages/coding-agent      CLI / TUI / SDK / RPC / ACP 四個入口
        ├── packages/agent      agent runtime、tool calling、狀態管理
        │       └── packages/ai      多供應商 LLM client、串流
        │               └── packages/catalog   模型目錄、供應商描述、模型識別
        ├── packages/tui        差分渲染的終端 UI
        ├── packages/hashline   edit 工具背後的 line-anchored patch 語言
        ├── packages/natives    N-API 綁定 → crates/pi-natives
        └── packages/utils      logger、streams、temp files、env/process
```

**catalog import 慣例**（`AGENTS.md` 明訂）：程式碼取 catalog 的**值**一律從 `@oh-my-pi/pi-catalog/<module>`，不得經由 `@oh-my-pi/pi-ai`；`pi-ai` 的 barrel 只 re-export 它自己簽章用到的**型別**（`Model`、`Api`、`ThinkingConfig`、`Effort`）。這是一條刻意維持的單向邊界。

## 主套件

`packages/coding-agent` 是主要焦點（`AGENTS.md:Default Context`）。使用者說「agent」時指的是這個套件的實作，不是對話中的助理。

四個入口共用同一個引擎：

| 入口 | 啟動方式 | 用途 |
|---|---|---|
| 互動 TUI | `omp` | 預設介面 |
| 一次性 | `omp -p "<prompt>"` | 回答單一 prompt 後結束 |
| RPC | `omp --mode rpc` / `--mode rpc-ui` | NDJSON over stdio，供非 Node 嵌入者 |
| ACP | `omp acp` | Agent Client Protocol over JSON-RPC，供編輯器（Zed） |

Node/TypeScript 宿主另可直接嵌入 SDK：`ModelRegistry`、`SessionManager`、`createAgentSession`、`discoverAuthStorage`（`README.md:SDK`）。

### Worker 契約

Workers **重新進入 CLI entrypoint**，不存在獨立的 worker entry module。`cli.ts` 啟動時以 `declareWorkerHostEntry()`（`@oh-my-pi/pi-utils/env`）宣告自己是 worker host，並在載入 command registry 前分派隱藏的 argv selector：`__omp_worker_stats_sync`、`__omp_worker_tab`、`__omp_worker_js_eval`、`__omp_worker_tiny_inference`。

Spawn 端一律走 `workerHostEntry()`：從 omp CLI 啟動時它是 `Bun.main`，worker 重新進入單一 entry module；在 CLI 宿主之外（`bun test`、SDK 嵌入、獨立 `omp-stats`）回傳 `null`，退回直接載入 worker 原始碼。

新增 worker 種類**必須**同時在 `cli.ts` 的 dispatch table 加 selector 並保留 fallback 分支，再以 `omp --smoke-test` 驗證。歷史脈絡與失敗案例見 `AGENTS.md:Worker scripts`（issues #1011、#1027、#1150）。

## Rust 原生層

約 8 萬行 Rust，另有約 8 萬行 vendored（brush bash fork 與 58 個 in-process 命令列工具）。目的是把其他 harness 需要 fork/exec 的操作放進 libuv thread pool，熱路徑上不再有 fork/exec。

| Crate | 職責 |
|---|---|
| `pi-natives` | N-API `cdylib`，聚合下列 crate 並提供 JS 綁定 |
| `pi-shell` | 內嵌 bash 引擎、持久 session、in-process coreutils 分派（wraps `brush-*`） |
| `pi-walker` | 平行、遵守 ignore 規則的檔案系統走訪與 scan cache，供 grep／glob／workspace／shell 共用 |
| `pi-iso` | 工作區隔離後端解析：APFS clone、btrfs/zfs reflink、overlayfs、projfs、rcopy |
| `pi-ast` | tree-sitter + ast-grep 比對、區塊解析、結構化摘要 |
| `pi-voice` | 音訊擷取／播放、Opus、WebRTC |
| `pi-builtins` | bash builtins 與 67 個 in-process 命令列工具 |

平台：`linux-x64`、`linux-arm64`、`darwin-x64`、`darwin-arm64`、`win32-x64`；x64 同時出 AVX2 與 baseline 兩個 binary。

Windows 上不透過 WSL：同一個 `omp` binary 直接在 macOS、Linux、Windows 執行（`README.md:09`）。

模組層級的細節見 [`natives-architecture.md`](natives-architecture.md)、[`natives-binding-contract.md`](natives-binding-contract.md)、[`native-crates.md`](native-crates.md)。

## 產生物邊界

`packages/catalog/src/models.json` 是**產生物，禁止手改**。它由 `packages/catalog/scripts/generate-models.ts` 與 `packages/catalog/src/provider-models/` 下的 descriptor／resolver 從上游來源產生。要改內容必須改來源，再跑 `bun run gen:models` 並把 `models.json` 與來源改動一起 commit。回歸測試要打在 resolver／descriptor 上，不是打在產生的 JSON 上。詳見 `AGENTS.md:Generated Files`。

## 外部邊界

| 邊界 | 說明 |
|---|---|
| LLM 供應商 | 60+ 家，涵蓋直連 API、gateway、訂閱制 coding plan 與本地 server；設定在 `~/.omp/agent/models.yml` 與 `config.yml` |
| web_search | 23 個後端串成 chain，站台專屬萃取器把 GitHub、registry、arXiv 等轉成結構化 markdown |
| LSP | 依語言啟動語言伺服器，rename 走 `workspace/willRenameFiles` |
| DAP | lldb-dap、dlv、debugpy 等除錯器 |
| 瀏覽器 | Puppeteer over headless Chromium、CDP 附著、或 browser-relay 擴充套件接管既有 Chrome 分頁 |
| MCP | 多種 transport，見 `mcp-protocol-transports.md` |
| 桌面 | `computer` 工具透過 `pi-natives::desktop` 操作視窗、螢幕擷取、原生輸入與 AX tree |

Log 一律寫到 `~/.omp/logs/omp.YYYY-MM-DD.log` 並自動輪替；在 TUI、RPC、SDK、worker 或背景 runtime 可能執行的程式碼**不得**使用 `console.*`，必須用 `@oh-my-pi/pi-utils` 的 `logger`（`AGENTS.md:Logging and CLI Output`）。

## Python 側

`python/` 下有 `omp-rpc` 與 `robomp` 兩個子專案，各自有 pytest 測試（`package.json:scripts.test:py`）。`python/robomp/web` 也是 Bun workspace 成員。這一側與 TypeScript 主線的耦合關係**未確認**——本次 bootstrap 未深讀該目錄。

## 未確認

- `bazel/`、`infra/`、`patches/`、`types/` 四個頂層目錄的職責未深讀確認。
- Python 側與 TypeScript 主線的執行時期關係未確認。
