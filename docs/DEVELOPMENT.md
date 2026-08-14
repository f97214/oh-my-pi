# 開發

來源：`package.json`、`bunfig.toml`、`rust-toolchain.toml`、`biome.json`、`flake.nix`、`packages/coding-agent/scripts/build-binary.ts`、`scripts/bazel-natives.ts`、`README.md:Development`、`AGENTS.md`。

## 環境需求

**不是每一項都要裝。** 只做 TypeScript 的話，bun 一個就夠開始；Rust 與 Bazel 只在你真的碰到那一層時才需要。

| 工具 | 什麼時候需要 | 版本 |
|---|---|---|
| **Bun** | 一定要 —— 它是套件管理器、執行時期與測試 runner | `bun@1.3.14`（`package.json:packageManager`） |
| **Rust** | 改 `crates/` 或建置原生 addon 時 | `nightly-2026-07-28`（`rust-toolchain.toml`） |
| **VS Build Tools** | 僅 Windows，建置原生 addon 時 | 2022，含「Desktop development with C++」 |
| **Node / npm** | 部分工具鏈與 `bun` 的其中一種安裝方式 | — |
| **Python 3** | `python/omp-rpc`、`python/robomp` 測試與治理 hook | 3.x |
| **bazelisk** | **僅 linux/macOS 且要建非 host 目標時** —— Windows 完全用不到 | `.bazelversion` = `9.2.0` |
| **Docker** | 只有要跑 `pi:image` 或 robomp 那組時 | — |

平台：macOS、Linux、Windows。Windows **不需要** WSL。

### 安裝方式

**Bun**（挑一種）：

```bash
npm install -g bun                                   # 任何平台，已有 node 時最省事
curl -fsSL https://bun.sh/install | bash             # macOS / Linux
brew install oven-sh/bun/bun                         # Homebrew
```

```powershell
powershell -c "irm bun.sh/install.ps1 | iex"         # Windows 官方安裝腳本
winget install Oven-sh.Bun                           # 或 winget
scoop install bun                                    # 或 scoop
```

**Rust** —— 裝 rustup 就好，**版本不用自己選**：`rust-toolchain.toml` 會讓 rustup 在第一次執行 cargo 時自動抓 `nightly-2026-07-28` 與 rustfmt、clippy、rust-analyzer。

```bash
curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh   # macOS / Linux
```

```powershell
winget install Rustlang.Rustup                                    # Windows
```

**VS Build Tools**（僅 Windows，原生 addon 靠它連結）：

```powershell
winget install Microsoft.VisualStudio.2022.BuildTools
```

安裝時要勾「Desktop development with C++」工作負載（`Microsoft.VisualStudio.Workload.VCTools`）。裝完還有一步環境設定，見[下面的 Windows 段落](#windows先把-msvc-環境帶進來)。

**bazelisk**（僅 linux/macOS 且要建非 host 目標）：

```bash
npm install -g @bazel/bazelisk
brew install bazelisk
go install github.com/bazelbuild/bazelisk@latest
```

CI 的 Rust 驗證用的就是 bazelisk（`.github/workflows/ci.yml`）。

**Nix 使用者**可以跳過上面全部：`nix develop` 會給你釘住的 Bun 與 Rust toolchain，加上所有原生建置相依。

### 本機目前狀態（2026-08-14 實測）

| 項目 | 狀態 |
|---|---|
| bun `1.3.14`、node、rustup／cargo、python `3.14.0`、docker | ✓ 已就緒 |
| VS Build Tools 2022（含 `VC.Tools.x86.x64`） | ✓ 已安裝 |
| `node_modules/` | ✓ 已建立（`bun install` 成功） |
| 原生 addon（`packages/natives/native/*.node`） | ✗ **未產出** |
| `omp` 是否在 PATH | ✗ 未 link |
| bazel / bazelisk | ✗ 未裝（Windows 用不到） |

`bun setup` 跑到**第二步 `build:native` 失敗**，所以後面的 link 兩步沒執行。原因不是缺工具 —— VS Build Tools 有裝，是 `LIB`／`INCLUDE` 沒帶進 shell。修法見 [Windows：先把 MSVC 環境帶進來](#windows先把-msvc-環境帶進來)。

## 起步

```bash
bun setup
```

它是**四個步驟串起來的**，任一步失敗，後面都不會跑：

| # | 步驟 | 做什麼 |
|---|---|---|
| 1 | `bun install` | 安裝 workspace 相依，建立 `node_modules/` |
| 2 | `bun run build:native` | 建置 `@oh-my-pi/pi-natives` 原生 addon |
| 3 | `bun --cwd=packages/coding-agent link` | 把套件註冊到 Bun 的 global link registry |
| 4 | `sh scripts/link-omp.sh` | 把 `packages/coding-agent/scripts/omp` 這支 wrapper 裝進 Bun 的 global bin |

第 4 步刻意**取代** `bun link` 預設建的 symlink —— 那個 symlink 直接指向 `src/cli.ts`，會踩到 bunfig.toml 的 preload bug（理由見該 wrapper 的檔頭註解與 issue #3701）。走完之後，直接打 `omp` 就是這份原始碼。

## 執行

```bash
bun dev                    # 從原始碼跑 CLI（= bun --cwd=packages/coding-agent src/cli.ts）
bun dev -- --version       # 傳參數給 CLI；也是非互動式冒煙檢查
bun dev -- -p "list .ts files"
bun run dev:timing         # 帶啟動計時（PI_TIMING=x + module-timer preload）
bun run stats              # 本地觀測儀表板
```

`bun setup` 走完之後，`omp` 也可以直接用，效果與 `bun dev` 相同。

Docker：

```bash
bun run pi:image           # docker build -t oh-my-pi/pi:dev .
bun run pi:run             # docker run --rm -it oh-my-pi/pi:dev
PI_IMAGE=my/tag bun run pi:image   # 覆寫 tag
```

robomp 那組（`robomp:build`／`up`／`down`／`logs`／`dev`／`reset`）走 `docker compose --project-directory python/robomp`。

## 編譯

```bash
bun run build
```

這是 workspace 遞迴建置（`bun run --workspaces --if-present build`）。對 `packages/coding-agent` 而言，它走 `scripts/build-binary.ts`，用 Bun 的 compile 產出**單一獨立執行檔**：

```
packages/coding-agent/dist/omp
```

### 交叉編譯

設 `CROSS_TARGET` 就能為別的平台產出 binary，輸出檔名會帶上目標 id（`build-binary.ts`）：

| `CROSS_TARGET` | 輸出 | Bun compile target |
|---|---|---|
| `darwin-arm64` | `dist/omp-darwin-arm64` | `bun-darwin-arm64` |
| `darwin-x64` | `dist/omp-darwin-x64` | `bun-darwin-x64` |
| `linux-arm64` | `dist/omp-linux-arm64` | `bun-linux-arm64` |
| `linux-x64` | `dist/omp-linux-x64` | `bun-linux-x64-baseline` |
| `win32-x64` | `dist/omp-win32-x64` | `bun-windows-x64-baseline` |
| `windows-x64` | `dist/omp-windows-x64` | `bun-windows-x64-baseline` |

```bash
CROSS_TARGET=linux-x64 bun run build
```

`win32-x64` 與 `windows-x64` 編出來的 binary 相同，但**輸出檔名跟著你傳進去的字串走**（`build-binary.ts` 的 `id: value` 原樣帶入），所以兩者產出的檔名不同。不在這張表裡的值會直接以 `Unsupported CROSS_TARGET` 失敗，不會默默退回預設。

macOS 上的**非交叉**建置會自動做 adhoc codesign；設 `BUN_NO_CODESIGN_MACHO_BINARY=1` 可跳過。

### 原生層

改動 `crates/` 或 `packages/natives` 之後要重跑：

```bash
bun run build:native
```

它依平台走兩條**不同**的路（`scripts/bazel-natives.ts`）：

| 平台 | 走哪條 | 需要什麼 |
|---|---|---|
| Windows | 本機 napi build（`packages/natives/scripts/build-bindings.ts`） | VS Build Tools |
| linux / macOS | Bazel | bazelisk `9.2.0` |

**Windows host 跑不了任何 bazel addon build** —— `bazel/toolchains/msvc` 的 clang-cl+xwin wrapper 只支援 linux/mac 作為 exec host，所以 `host` 這個偽目標會改走本機 napi 路徑；在 Windows 上要求其他目標會直接 fail fast 並給出指引。

其他系統若 Bazel 的預建 host 工具跑不起來，可以強制走同一條本機 N-API 路徑：

```bash
OMP_NATIVE_BUILD_BACKEND=cargo bun run build:native
```

這個環境變數**只支援 host 目標**，指定其他目標會報錯。

### Windows：先把 MSVC 環境帶進來

在一般的 PowerShell 或 Git Bash 裡跑 `bun run build:native`（或 `cargo check`）會這樣死：

```
LINK : fatal error LNK1104: 無法開啟檔案 'msvcrt.lib'
```

**工具本身沒問題** —— VS Build Tools 有裝、Windows SDK 也在。問題是 `LIB` 與 `INCLUDE` 兩個環境變數是空的，linker 找不到 CRT 與 SDK 的 lib 目錄。這兩個變數是由 MSVC 的環境設定腳本注入的，不會憑空存在。

兩種解法，挑一個：

1. **從 Developer PowerShell for VS 2022 啟動**（開始選單搜尋得到），再在那個 shell 裡跑 bun 命令。
2. **先跑 vcvars**：

   ```
   "C:\Program Files (x86)\Microsoft Visual Studio\2022\BuildTools\VC\Auxiliary\Build\vcvars64.bat"
   ```

   跑完的那個 shell 才有 `LIB`／`INCLUDE`。

這跟[收工閘門的覆蓋缺口](#閘門目前的覆蓋缺口)是**同一個環境問題**：閘門 hook 直接 spawn 命令、不經 shell，所以它沒辦法自己 source `vcvars64.bat`。要讓 Rust 檢查進閘門，得讓這兩個變數在 Claude Code 啟動時就已存在。

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
| 冒煙探針（含 worker 驗證） | `bun run ci:test:smoke` |
| 建置／發布腳本的測試 | `bun run test:scripts` |
| 建置獨立執行檔 | `bun run build` |
| 重建原生 addon | `bun run build:native` |
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

**TypeScript** —— bun 與 `node_modules/` 都已就緒，缺的只是**先實際跑過一次確認跑得完**（別重蹈 `cargo check` 沒驗就加進閘門、結果每次收工都被擋的覆轍）。確認之後把這兩項加進 `verify-gate.json`：

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

跟原生 addon 建置失敗是**同一個根因**：`LIB` 與 `INCLUDE` 為空。完整說明與兩種解法見 [Windows：先把 MSVC 環境帶進來](#windows先把-msvc-環境帶進來)。

對閘門而言多一層限制：**hook 直接 spawn 命令、不經 shell**，所以它無法自己先 source `vcvars64.bat`。要納入 Rust 檢查，得讓 `LIB`／`INCLUDE` 在 Claude Code **啟動時**就已存在 —— 從 Developer PowerShell 啟動，或把兩者寫進 `.claude/settings.json` 的 `env`。確認 `cargo check --workspace --all-targets` 真的跑得完（冷編譯可能超過 600 秒上限）之後再加。

## SDD 流程

本 repo 已啟用 Spectra（`.spectra.yaml`：`tdd: true`、`parallel_tasks: true`、`locale: tw`），規格在 `openspec/specs/`、變更提案在 `openspec/changes/`。流程與可用 skill 見 [`AGENTS.md`](../AGENTS.md)。
