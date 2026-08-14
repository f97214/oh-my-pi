# 測試

來源：`package.json:scripts`、`scripts/ci-test-ts.ts`、`bunfig.toml`、`AGENTS.md:Testing Guidance`。

## 測試命令

| 命令 | 實際執行 | 範圍 |
|---|---|---|
| `bun test` *(root script)* | `bun scripts/ci-test-ts.ts local` | 本機預設的 TypeScript 測試集 |
| `bun run test:ts` | `bun scripts/ci-test-ts.ts local-ts` | 只跑 TS，不含 native |
| `bun run test:rs` | `bun scripts/run-rs-task.ts test:rs` | Rust workspace |
| `bun run test:py` | `python3 -m pytest -x python/omp-rpc/tests` **且** `python3 -m pytest -x python/robomp/tests` | Python 兩個子專案 |
| `bun run test:scripts` | `bun test scripts/*.test.ts`（release／binary 相關四支） | 建置與發布腳本 |
| `bun run ci:test:ts` | `bun scripts/ci-test-ts.ts all` | CI 的完整 TS 集 |
| `bun run ci:test:smoke` | CLI `--version`、`--help`、`stats --help`、`--smoke-test` | 冒煙探針 |
| `bun run check` | `bun run --parallel check:ts check:rs` | 型別與 lint 檢查，非測試 |

`bun run test:py` 是 `&&` 串接的複合命令；需要單獨觀測其中一段時要拆開跑。

## 測試拓樸

`scripts/ci-test-ts.ts` 是 TypeScript 測試的唯一調度器，支援的 mode：`all`、`local`、`local-ts`、`workspace`、`native`，以及 `coding-agent-` 開頭的五個分桶。

`packages/coding-agent` 的測試切成四個 bucket，各有不同的並行度與分塊策略（`scripts/ci-test-ts.ts:codingAgentBucketPlans`）：

| Bucket | parallel | chunkSize | 原因 |
|---|---|---|---|
| `singleton` | 1 | 不分塊 | 這些 suite 刻意共處一個 process 以驗證 process-wide 狀態，**不得拆開** |
| `ui` | 1 | 5 | 累積 ghostty-vt native cell 會讓 bun 1.3.14 的 GC 在約 10 個檔案共用 heap 時 abort（SIGTRAP/SIGABRT，exit 133/134）。二分法確認不是單一檔案的錯，是累積 heap 量 |
| `runtime` | — | 依預設 | — |
| `native` | — | 依預設 | — |

分塊的通用理由：每個 chunk 開新 process，重置 Bun heap 並回收殘留的子行程，讓尖峰 RSS 不撞到 CI runner 的 OOM 上限（單次 170–370 檔的呼叫會被 SIGKILL，exit 137）。

### 輸出模式

預設 `--only-failures`：每個 chunk 收斂成一行 pass/fail，只有失敗的 chunk 才重播完整 stdout/stderr。加 `--full` 換成逐行輸出。`--only-failures` 只是輸出過濾器，**不跳過任何測試、也不共用跨行程快取**，所以 chunk 之間可以安全併行。

### 掃描範圍

`bun test` **不遵守 `.gitignore`**，所以 `bunfig.toml:[test].pathIgnorePatterns` 明確排除 `node_modules`、`.git`、`target`、`dist`、`python/**`、`docs/**`、`runs/**`、`python/robomp/data/**`、`.wt/**`、`.worktrees/**` —— 否則 root 層的 `bun test` 會走進 robomp 的 repo clone 與暫存目錄。

## Worker 冒煙探針

`omp --smoke-test` 會 spawn stats sync worker 與 tiny-model 子行程、ping 它們、然後結束。它接在 `ci:test:smoke` 與 `scripts/install-tests/run-ci.sh` 上，讓 binary、source-link、tarball 三種安裝方式都跑到。

**新增 worker 種類時**，若它在不同的 module graph 上，必須加一支對應的 smoke。這是 worker 契約的實際驗證手段（`AGENTS.md:Worker scripts`）。

## 撰寫測試的契約

完整規則在 `AGENTS.md:Testing Guidance`，這裡只摘出最容易踩的幾條：

- 每個新測試都必須守住**一個具體、可從外部觀察的契約**。講不出那個契約就不要加。
- **禁止 source-grep**：讀取實作檔並對其**文字**斷言（`expect(src).toContain(...)`、`.toMatch(/import .../)`、「註解必須寫 X」）一律禁止。它測的是程式碼長什麼樣，不是它做什麼。改成執行程式碼並斷言輸出／狀態／錯誤；結構性不變條件用型別測試或 lint 規則守。
- **禁止 `mock.module()`**：Bun 的 `mock.module()` 會汙染全域 module registry 並跨檔外洩（[oven-sh/bun#12823](https://github.com/oven-sh/bun/issues/12823)）。改用 `spyOn` 打在 import 進來的 module 物件上。
- 測試必須**全套件安全**，不只是單檔安全。不要對 `Bun.*`、`process.platform`、`process.env`、`Bun.env` 做檔案層級的長生命週期改動；用 per-test `vi.spyOn(...)` 搭配 `afterEach` 的 `vi.restoreAllMocks()`。單獨跑會過但毒害後續檔案的測試是壞的。
- 不要用假斷言：`expect(true).toBe(true)`、裸 `not.toThrow()`、非空字串檢查、長度變大檢查都不算數。

## 已知限制

- **本機目前跑不了 TypeScript 測試**：`bun` 未安裝、`node_modules/` 不存在。先跑 `bun setup`（安裝 workspace 相依並建置 `@oh-my-pi/pi-natives`）。
- 改動 Rust crate 或 `packages/natives` 後要重跑 `bun run build:native`。
- Rust 側需要 `rust-toolchain.toml` 指定的 `nightly-2026-07-28`。
- Windows 上輸出中文若出現亂碼，設 `PYTHONUTF8=1` 或修正 console encoding，**不要改檔案編碼**。

## 收工前的自動驗證

`.ai/bootstrap-ai-project/verify-gate.json` 列出 session 結束前會跑的檢查。它只看退出碼，並以 `paths` 限定觸發範圍。目前的覆蓋範圍與缺口見該檔與 [`DEVELOPMENT.md`](DEVELOPMENT.md)。
