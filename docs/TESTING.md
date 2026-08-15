# 測試

來源：`package.json:scripts`、`scripts/ci-test-ts.ts`、`scripts/run-rs-task.ts`、`bunfig.toml`、`AGENTS.md:Testing Guidance`。

## 測試命令

| 命令 | 實際執行 | 範圍 |
|---|---|---|
| `bun test` *(root script)* | `bun scripts/ci-test-ts.ts local` | 本機預設的 TypeScript 測試集 |
| `bun run test:ts` | `bun scripts/ci-test-ts.ts local-ts` | 只跑 TS，不含 native |
| `bun run test:rs` | `bun scripts/run-rs-task.ts test:rs` | Rust workspace（排除 vendored `brush-core`）—— **本機多半整個跳過**，見[下節](#rust-task-的跳過行為) |
| `bun run test:py` | `python3 -m pytest -x python/omp-rpc/tests` **且** `python3 -m pytest -x python/robomp/tests` | Python 兩個子專案 |
| `bun run test:scripts` | `bun test scripts/*.test.ts`（release／binary 相關四支） | 建置與發布腳本 |
| `bun run ci:test:ts` | `bun scripts/ci-test-ts.ts all` | CI 的完整 TS 集 |
| `bun run ci:test:smoke` | CLI `--version`、`--help`、`stats --help`、`--smoke-test` | 冒煙探針 |
| `bun run check` | `bun run --parallel check:ts check:rs` | 型別與 lint 檢查，非測試 |

`bun run test:py` 是 `&&` 串接的複合命令；需要單獨觀測其中一段時要拆開跑。

## Rust task 的跳過行為

`test:rs`、`check:rs`、`lint:rs`、`fix:rs` 都不直接呼叫 cargo，而是經過 `scripts/run-rs-task.ts`。**在多數本機情境下，它一個 cargo 命令都不會執行就以 exit 0 結束**：

```
$ bun run check:rs
$ bun scripts/run-rs-task.ts check:rs
Skipping check:rs (not in CI and no Rust-affecting changes were found).
```

（2026-08-15 於本機實測，退出碼 0。）

**退出碼分辨不出「跳過」與「通過」**，只有 stdout 那行 `Skipping ...` 會說。所以「`bun run test:rs` 沒報錯」不等於 Rust 測試跑過了；把這些命令交給只看退出碼的自動化（例如收工閘門）時，也要先想清楚它在什麼情況下才真的驗東西。

### 跳過條件

判斷式在 `scripts/run-rs-task.ts:71`：

```ts
if (taskName !== "fmt:rs" && !(isCI() || (await hasRustAffectingChanges()))) {
```

- **`fmt:rs` 是唯一豁免的 task**，永遠執行。其餘四個都受此邏輯管轄。
- 下列**任一**條件成立就照常執行：
  - `isCI()`（`:87`）—— 環境變數 `CI` 有值，且 trim 並轉小寫後不是 `""`、`0`、`false`。因此 `CI=1 bun run test:rs` 是明確的強制執行手段。
  - `hasRustAffectingChanges()`（`:94`）—— `git status --porcelain -z` 的輸出中含 Rust 相關路徑。判定規則在 `:131`：副檔名 `.rs`、路徑以 `.cargo/` 開頭，或檔名屬於 `:6` 的清單（`Cargo.toml`、`Cargo.lock`、`build.rs`、`rust-toolchain`、`rust-toolchain.toml`、`clippy.toml`、`.clippy.toml`、`rustfmt.toml`、`.rustfmt.toml`）。
- `git status` 本身失敗時（`:96`）印警告並**保守地照常執行**。

`git status --porcelain` 只反映**工作樹與索引**。Rust 改動一旦 commit、工作樹回到乾淨狀態，本機就會恢復跳過 —— 「改完 → 跑檢查 → commit → 再跑一次」的第二次會是空跑。

### 各 task 實際執行的命令

出自 `scripts/run-rs-task.ts:26` 的 `TASK_COMMANDS`，多命令者依序執行，任一非零退出即中止（`:76`）：

| Task | 實際命令 | 受跳過邏輯影響 |
|---|---|---|
| `check:rs` | `cargo fmt --all -- --check` → `cargo clippy --workspace --exclude brush-core --no-deps -- -D warnings` | 是 |
| `lint:rs` | `cargo clippy --workspace --exclude brush-core --no-deps -- -D warnings` | 是 |
| `fix:rs` | `cargo fmt --all` → `cargo clippy --workspace --exclude brush-core --fix --allow-dirty --no-deps --allow-staged --allow-no-vcs` | 是 |
| `test:rs` | `cargo nextest run --workspace --exclude brush-core --status-level=fail --final-status-level=fail` | 是 |
| `fmt:rs` | `cargo fmt --all` | **否** |

三件容易誤解的事：

- **`bun run check:rs` 不含 `cargo check`** —— 它是 fmt 檢查加 clippy。要編譯／型別檢查得自己跑 `cargo check`，兩者不能互相取代。
- **`test:rs` 走 `cargo nextest`，不是 `cargo test`** —— 那是要另外安裝的 binary（`nix/dev-shell.nix` 與 self-hosted runner image 都明確裝了它）。
- `--exclude brush-core`（`:25`）把 vendored fork 排除在 workspace 的 lint／test 閘門外；`pi-builtins` **不**在排除之列（`:17` 的註解特別點出這件事），它照常受 default clippy 與零 rustc warning 約束。

cargo 執行檔本身透過 `rustup which cargo` 解析（`:143`），繞開 macOS 上 Homebrew `rustup-init` 搶先於 PATH 的問題。

### CI 不走這條路

`.github/workflows/ci.yml` 的 Rust 驗證是獨立的 bazel job（`bazelisk test //crates/...`，加上 `--config=clippy` 系列與 `--config=rustfmt`），整份 workflow **沒有任何一處呼叫 `test:rs`／`check:rs`／`lint:rs`**。所以 `isCI()` 那條旁路在本 repo 的 CI 裡實際上不會被觸發 —— 這些 cargo task 是本機開發用的工具，CI 的 Rust 閘門在 bazel 那邊。

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

- **本機的 TypeScript 測試跑得動**（2026-08-15 實測）：`bun` `1.3.14` 與 `node_modules/` 都已就緒，以 `bun test` 對三個測試檔跑出 147 pass／2 skip／3 fail，約 12 秒。那 3 個失敗的成因**未查**，也還沒跑過完整的 `bun test`。全新 clone 仍要先跑 `bun setup`（安裝 workspace 相依並建置 `@oh-my-pi/pi-natives`）。
- **Rust 測試在本機從未跑過，目前沒有任何「Rust 測試通過」的證據。** 除了上面那層跳過邏輯之外，`test:rs` 需要的 `cargo nextest` 本機也沒裝（2026-08-16 實測 `cargo nextest --version` → exit 101，`no such command: nextest`），所以即使強制不跳過也跑不起來。
- 已通過的只有編譯檢查：`cargo check --workspace --all-targets` exit 0（2026-08-15 實測，約 22 秒，快取熱），`cargo check -p pi-builtins --all-targets` exit 0（18.99 秒）。**這不是測試，也不是 `bun run check:rs` 會跑的東西。**
- 改動 Rust crate 或 `packages/natives` 後要重跑 `bun run build:native`。
- Rust 側需要 `rust-toolchain.toml` 指定的 `nightly-2026-07-28`。
- Windows 上輸出中文若出現亂碼，設 `PYTHONUTF8=1` 或修正 console encoding，**不要改檔案編碼**。

## 收工前的自動驗證

`.ai/bootstrap-ai-project/verify-gate.json` 列出 session 結束前會跑的檢查。它只看退出碼，並以 `paths` 限定觸發範圍。目前的覆蓋範圍與缺口見該檔與 [`DEVELOPMENT.md`](DEVELOPMENT.md)。

要把 Rust 命令加進去之前，先讀[上面的跳過行為](#rust-task-的跳過行為) —— 只看退出碼的閘門分辨不出空跑。
