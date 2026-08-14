# 開發

來源：`package.json`、`bunfig.toml`、`rust-toolchain.toml`、`biome.json`、`flake.nix`、`README.md:Development`、`AGENTS.md`。

## 環境需求

| 工具 | 版本 | 來源 |
|---|---|---|
| Bun | `bun@1.3.14`（README 標示 ≥ 1.3.14） | `package.json:packageManager` |
| Rust | `nightly-2026-07-28`，含 rustfmt、clippy、rust-analyzer | `rust-toolchain.toml` |
| Node | 部分工具鏈使用 | — |
| Python 3 | `python/omp-rpc`、`python/robomp` 與治理 hook 使用 | `package.json:scripts.test:py` |

平台：macOS、Linux、Windows。Windows **不需要** WSL。

Nix 使用者可用 `nix develop` 取得釘住的 Bun 與 Rust toolchain 加上原生建置相依。

### 本機目前狀態

`bun` **未安裝**、`node_modules/` **不存在**。跑任何 TypeScript 相關命令前先執行 `bun setup`。

## 起步

```bash
bun setup      # 安裝 workspace 相依 + 建置 @oh-my-pi/pi-natives + link CLI
bun dev        # 從原始碼跑 CLI（= bun --cwd=packages/coding-agent src/cli.ts）
bun dev -- --version   # 非互動式冒煙檢查
```

改動 Rust crate 或 `packages/natives` 後重跑：

```bash
bun run build:native
```

## 常用指令

| 目的 | 命令 |
|---|---|
| 型別＋lint 檢查（**取代 `tsc`**） | `bun check` |
| 只檢查 TS | `bun run check:ts` |
| 只檢查 Rust | `bun run check:rs` |
| Lint | `bun run lint` |
| 格式化 | `bun run fmt` |
| 自動修正 | `bun run fix` |
| 測試 | `bun test`（細節見 [`TESTING.md`](TESTING.md)） |
| 建置 | `bun run build` |
| 產生模型目錄 | `bun run gen:models` |
| 產生 Nix 相依 | `bun run gen:nix` |
| 本地觀測儀表板 | `bun run stats` |
| 除錯／回報／profiling | session 內輸入 `/debug` |

**永遠不要用 `tsc` 或 `npx tsc`** —— 一律 `bun check`（`AGENTS.md:Commands`）。

## 程式碼慣例

完整規則在 [`AGENTS.md`](../AGENTS.md)，這裡摘出最常違反的幾條。

### 型別與匯入

- 非必要不用 `any`。
- **絕不用 `ReturnType<>`** —— 寫出實際型別名稱。
- **絕不用 inline import**：沒有 `await import()`、沒有型別位置的 `import("pkg").Type`。一律 top-level。
- 外部 API 型別去 `node_modules` 查，不要用猜的。
- Barrel export 優先 `export * from "./module"`，含 `export type`。

### 類別

用 ES `#private` 欄位；對外可存取的成員裸寫。**欄位與方法不加 `private`/`protected`/`public` 關鍵字**，唯一例外是 TypeScript 語法要求的 constructor parameter property。

### 其他硬規則

- Promise 用 `Promise.withResolvers()`，不用 `new Promise((resolve, reject) => ...)`。
- **Prompt 不在程式碼裡組**：不用 inline string、template literal 或字串串接。Prompt 放在靜態 `.md`，動態內容用 Handlebars，以 `import content from "./prompt.md" with { type: "text" }` 匯入。
- Node 模組用 **namespace import**：`import * as fs from "node:fs/promises"`。
- 寫 helper 前先找有沒有現成的（`packages/coding-agent/src/utils/`、`@oh-my-pi/pi-utils`、`@oh-my-pi/pi-tui`）。同一件事兩份實作是 bug，即使兩份都能動。git／jj 一律走 `src/utils/git.ts`、`src/utils/jj.ts`，**不得**自己 `$`／`Bun.spawn`。

### Bun 優先

有 Bun API 就用 Bun，`node:*` 只用來補 Bun 沒有的。**絕不為有正式 API 的操作 spawn shell**。

| 操作 | 用 | 不要用 |
|---|---|---|
| 檔案讀寫 | `Bun.file()`、`Bun.write()` | `readFileSync`、`writeFileSync` |
| 開行程 | `` $`cmd` ``、`Bun.spawn()` | `child_process` |
| Sleep | `Bun.sleep(ms)` | `setTimeout` promise |
| 找執行檔 | `$which("git")`（`@oh-my-pi/pi-utils`） | `spawnSync(["which", ...])` |
| SQLite | `bun:sqlite` | `better-sqlite3` |
| Hash | `Bun.hash()`、`Bun.password.*`、WebCrypto | `node:crypto` |
| 路徑 | `import.meta.dir`、`import.meta.path` | `fileURLToPath` |
| 字串寬度 | `Bun.stringWidth()` | 自製 |
| 換行 | `Bun.wrapAnsi()` | 自製 ANSI wrapper |

`Bun.write` 會自動建立父目錄，不需要先 `mkdir`。

### Log 與輸出

TUI、RPC、SDK、worker 或背景 runtime 執行期間可能跑到的程式碼 **不得** 用 `console.log`/`error`/`warn` —— 會弄壞渲染與協定。用 `logger`：

```typescript
import { logger } from "@oh-my-pi/pi-utils";
logger.error("MCP request failed", { url, method });
```

例外是純 CLI 命令：不進 TUI 就結束的命令可以用 `console.*` 輸出給使用者看的內容。這是**語意上的例外，不是看檔名**。

### TUI 淨化

所有顯示在工具 renderer 的文字都要淨化，**每一條 render 路徑都要**，不只 happy path：

- Tab → 空白：`replaceTabs()`
- 截斷：`truncateToWidth()` / `ui.truncate()`，用 `TRUNCATE_LENGTHS` 常數
- 路徑縮短：`shortenPath()`（家目錄換成 `~`）
- 預覽上限：`PREVIEW_LIMITS`，不要自訂數字

**錯誤訊息也算** —— 它們常常內嵌檔案內容（例如 patch 失敗訊息會帶未比中的行）。

## Git 與提交

- **未經要求不得 commit**（`AGENTS.md:Commands`）。
- 不得未經授權建立、切換或刪除分支與 worktree。
- 維護者合併 PR 的訊息格式：`Merge PR #<number>: <conventional PR subject> (@<author>)`。

## 變更紀錄

位置：各套件的 `packages/*/CHANGELOG.md`。新項目一律放進 `## [Unreleased]`；已發布的區段**不可修改**。區段順序與格式不必在 review 或 PR 裡挑 —— `bun run release` 會跑 `fix-changelogs` 自動正規化。

歸屬格式：

- 內部（來自 issue）：`Fixed foo bar ([#123](https://github.com/can1357/oh-my-pi/issues/123))`
- 外部貢獻：`Added feature X ([#456](...) by [@username](...))`

## 發布

1. 確認自上次發布以來的所有變更都在各受影響套件的 `[Unreleased]`。
2. 跑 `bun run release` —— 它處理版號、CHANGELOG 定版、commit、tag、publish，並補上新的 `[Unreleased]`。

## 治理與收工閘門

`.ai/bootstrap-ai-project/` 下的共用 hook runtime 由 `.claude/settings.json`（Claude）與 `.codex/hooks.json`（Codex）各自註冊：

- **驗證閘門** `verify-gate.py` —— SessionStart 記錄基準，Stop 對本 session 的變更跑 `verify-gate.json` 的檢查，SessionEnd 清理。只看退出碼，連續三次未過就放行並要求如實告知。
- **宣稱證據** `claim-ledger.py` + `claim-guard.py` —— 記錄跑過的 test／check／search 類命令，收工時比對訊息裡的宣稱有沒有對應紀錄。

這兩個是**防呆不是防駭**：宣稱檢查靠關鍵字，換個說法就繞得過去。它們擋的是疏忽。

### 閘門目前的覆蓋缺口

`verify-gate.json` 目前**只涵蓋 Python 工具鏈**（skill lint、build_docs 來源檢查、tools 測試、bootstrap CLI parity／角色 renderer／TDD observer／Spectra 相容性）。TypeScript 與 Rust 兩側都是**零覆蓋**。

**TypeScript** —— `bun` 未安裝、`node_modules/` 不存在。跑完 `bun setup` 後把這兩項加進 `verify-gate.json`：

```json
{ "name": "TS 型別與 lint", "command": ["bun", "run", "check:ts"],
  "paths": ["packages/", "scripts/", "tsconfig.base.json", "package.json"], "timeout": 600 }
{ "name": "冒煙探針", "command": ["bun", "run", "ci:test:smoke"],
  "paths": ["packages/coding-agent/"], "timeout": 300 }
```

`timeout` 上限是 600 秒，完整的 `bun test` 塞不進去 —— 那個留給 CI。

**Rust** —— `cargo check --workspace --all-targets` 在本機失敗：

```
LINK : fatal error LNK1104: 無法開啟檔案 'msvcrt.lib'
```

原因是 `LIB` 與 `INCLUDE` 環境變數為空 —— 這個 session 不是從 Developer Command Prompt 啟動的，MSVC linker 找不到 CRT 與 Windows SDK 的 lib 目錄（SDK 本身存在，版本 `10.0.26100.0`）。

**閘門 hook 直接 spawn 命令、不經 shell**，所以它無法自己先 source `vcvarsall.bat`。要納入 Rust 檢查，得讓 `LIB`／`INCLUDE` 在 Claude Code 啟動時就已存在：從 Developer Command Prompt 啟動，或把兩者寫進 `.claude/settings.json` 的 `env`。確認 `cargo check --workspace --all-targets` 真的跑得完（冷編譯可能超過 600 秒上限）之後再加。

## SDD 流程

本 repo 已啟用 Spectra（`.spectra.yaml`：`tdd: true`、`parallel_tasks: true`、`locale: tw`），規格在 `openspec/specs/`、變更提案在 `openspec/changes/`。流程與可用 skill 見 [`AGENTS.md`](../AGENTS.md)。
