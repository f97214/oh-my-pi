> 這是根目錄 [`README.md`](../../README.md) 的繁體中文翻譯。
> 翻譯基準：`1c7170e11`（2026-08-14）。**英文原文為準** —— 上游更新後本檔可能過期。

<p align="center">
  <img src="https://github.com/can1357/oh-my-pi/blob/main/assets/hero.png?raw=true" alt="omp">
</p>

<p align="center">
  <strong>把 IDE 接進來的 coding agent。</strong>
  <strong><a href="https://omp.sh">omp.sh</a></strong>
</p>

<p align="center">
  <a href="https://www.npmjs.com/package/@oh-my-pi/pi-coding-agent"><img src="https://img.shields.io/npm/v/@oh-my-pi/pi-coding-agent?style=flat&colorA=222222&colorB=CB3837" alt="npm version"></a>
  <a href="https://github.com/can1357/oh-my-pi/blob/main/packages/coding-agent/CHANGELOG.md"><img src="https://img.shields.io/badge/changelog-keep-E05735?style=flat&colorA=222222" alt="Changelog"></a>
  <a href="https://github.com/can1357/oh-my-pi/actions"><img src="https://img.shields.io/github/actions/workflow/status/can1357/oh-my-pi/ci.yml?style=flat&colorA=222222&colorB=3FB950" alt="CI"></a>
  <a href="https://github.com/can1357/oh-my-pi/blob/main/LICENSE"><img src="https://img.shields.io/github/license/can1357/oh-my-pi?style=flat&colorA=222222&colorB=58A6FF" alt="License"></a>
  <a href="https://www.typescriptlang.org"><img src="https://img.shields.io/badge/TypeScript-3178C6?style=flat&colorA=222222&logo=typescript&logoColor=white" alt="TypeScript"></a>
  <a href="https://www.rust-lang.org"><img src="https://img.shields.io/badge/Rust-DEA584?style=flat&colorA=222222&logo=rust&logoColor=white" alt="Rust"></a>
  <a href="https://bun.sh"><img src="https://img.shields.io/badge/runtime-Bun-f472b6?style=flat&colorA=222222" alt="Bun"></a>
  <a href="https://discord.gg/4NMW9cdXZa"><img src="https://img.shields.io/badge/Discord-5865F2?style=flat&colorA=222222&logo=discord&logoColor=white" alt="Discord"></a>
</p>

<p align="center">
  <a href="https://github.com/mariozechner">@mariozechner</a> 的 <a href="https://github.com/badlogic/pi-mono">Pi</a> 的 fork
</p>

目前出貨中最完整的 agent 介面。持續依真實使用調校 —— 開箱即完整，往下開放到底。

**60+** 供應商 · **31** 個內建工具 · **14** 種 lsp 操作 · **28** 種 dap 操作 · **~8 萬**行 Rust 核心。

> [!NOTE]
> Pull request 目前**暫時對所有人開放**，屬於試行。我們先前要求在接受 PR 之前需要有人背書（vouch）；該要求暫時解除，我們正在評估開放貢獻的成效。依結果而定，vouch 制度有可能回歸。

## 安裝

**macOS · Linux**

```sh
curl -fsSL https://omp.sh/install | sh
```

> **Alpine / musl：** 預建的 musl binary 動態連結 `libstdc++`／`libgcc`，而原生的 Alpine 並不隨附它們。請先安裝：`apk add libstdc++ libgcc`。

**Homebrew**

```sh
brew install can1357/tap/omp
```

**Bun（建議）**

```sh
bun install -g @oh-my-pi/pi-coding-agent
```

**Nix**

```sh
# Run without installing
nix run github:can1357/oh-my-pi

# Or install into the active profile
nix profile install github:can1357/oh-my-pi
```

Flake 使用者可以用 `packages.<system>.omp`、`overlays.default`、`nixosModules.default` 或 `homeManagerModules.default`。Home Manager 的設定可以安裝 OMP 並以宣告式方式擁有它的設定：

```nix
{
  inputs.omp.url = "github:can1357/oh-my-pi";

  # In your Home Manager module:
  imports = [ inputs.omp.homeManagerModules.default ];
  programs.omp = {
    enable = true;
    settings.startup.quiet = true;
  };
}
```

**Windows（PowerShell）**

```powershell
irm https://omp.sh/install.ps1 | iex
```

**釘住版本（mise）**

```sh
mise use -g github:can1357/oh-my-pi
```

macOS · Linux · Windows · bun ≥ 1.3.14

### Shell 補完

`omp` 會從即時的命令／旗標 metadata 產生自己的 **bash**、**zsh** 與 **fish** 補完腳本，所以它們永遠不會跟實際的 CLI 漂移。子命令、旗標與列舉值是靜態補完；模型名稱（`--model`、`--smol`、`--slow`、`--plan`）對照內建的模型目錄解析，`--resume` 則對照你磁碟上的 session。

```sh
# zsh — add to ~/.zshrc (or write the output into a file on your $fpath)
eval "$(omp completions zsh)"

# bash — add to ~/.bashrc
eval "$(omp completions bash)"

# fish
omp completions fish > ~/.config/fish/completions/omp.fish
```

## 每個工具都被 _benchmaxxed_ 過。

第一次嘗試就落地的編輯。會摘要檔案而不是把內容整個倒出來的讀取。瞬間回傳的搜尋。挑任何模型 —— omp 都會把它做對。

| 模型 | 指標 | 是什麼 |
| ---------------- | ------------ | --------------------------------------------------------------------- |
| Grok Code Fast 1 | 6.7% → 68.3% | 編輯格式不再把模型生吞活剝的那一刻，提升了十倍。 |
| Gemini 3 Flash | +5 pp | 相較 str_replace —— 在這個格式上勝過 Google 自己最好的嘗試。 |
| Grok 4 Fast | −61% tokens | 壞掉的 diff 不再引發重試迴圈之後，輸出量直接崩落。 |
| MiniMax | 2.1× | 通過率超過翻倍。同樣的權重、同樣的 prompt。 |

- `read`：摘要式片段 · 理想的預設值 · selector 命中率
- `grep`：西部最快的槍
- `lsp`：你的 IDE 知道的，agent 都知道
- `prompts`：為每個模型不斷調整

[讀完整篇文章 ↗](https://blog.can.ac/2026/02/12/the-harness-problem/)

## 你愛的那個 Pi，**電池已附**。

最初建立在 [Mario Zechner](https://github.com/mariozechner) 出色的 [Pi](https://github.com/badlogic/pi-mono) 之上，omp 補上了你缺的每一樣東西。

### 01 · 帶 tool-calling 的程式碼執行

多數 harness 給 agent 一個 Python 沙箱就當作結案。我們跑的是常駐的 Python 與一個 Bun worker，而且**任一個 kernel 都能透過 loopback bridge 回呼 agent 自己的工具** —— read、search、task。Agent 在 Python 裡用 tool.read 載入 CSV、從 JavaScript 畫圖，全程不離開那個 cell。

![omp TUI：單一 eval session 中，`[1/2] pandas describe`（Python）印出真實的 DataFrame.describe() 表格，接著 `[2/2] top scorer`（JavaScript）跑一個 reduce。頁尾：'Both kernels ran in one session.'](https://omp.sh/captures/eval.webp)

### 02 · LSP 接進每一次寫入

你要求 rename，得到的就是 rename。呼叫會走 `workspace/willRenameFiles`，所以 re-export、barrel 檔與別名 import 都會在檔案移動之前先更新。你的 IDE 知道的，agent 都知道。

![omp TUI：`LSP references` 為符號 `formatBytes` 在三個檔案中回傳五個命中，接著 `LSP rename` 套用變更並編輯 format.ts/report.ts/cli.ts，然後 `Search formatBytes 0 matches` 確認。最後一行：'Rename complete. Five edits across three files…'](https://omp.sh/captures/lsp.webp)

_[閱讀 LSP 設定文件](../lsp-config.md)_

### 03 · 驅動真正的除錯器

C binary segfault：agent 掛上 lldb、單步走到壞掉的指標、讀取 frame。Go 服務卡住：它掛上 dlv 並走訪 goroutine。Python 行程卡死：debugpy、暫停、檢視、求值。多數 agent 還在灑 print。

![omp TUI：對原生 binary /tmp/omp-native/demo 的即時 lldb-dap session。Adapter=lldb-dap、Status=stopped、Frame=xorshift32、Instruction pointer 0x10000055C、Location demo.c:6:10。Debug scopes 與 Debug variables 卡片顯示區域變數（x = 57351），agent 確認了算式：x 從 7 → 57351（= 7 ^ (7<<13)）。](https://omp.sh/clips/dap-poster.webp)

_[觀看錄影 ↗](https://omp.sh/clips/dap.mp4)_

### 04 · 會時間旅行的 stream rules

你的 rule 平常休眠，直到模型脫稿演出。regex 命中會在 token 中途中止串流、把 rule 當成 system reminder 注入，然後從同一個點重試。你得到即時修正，卻不必為此在每一輪付出 context 成本。注入內容能撐過 compaction，所以修正會留住。

![omp TUI：agent 讀取 src.rs 並即將寫下 Box::leak 時請求被中止（紅色 `Error: Request was aborted`），一張琥珀色的 `⚠ Injecting rule: box-leak` 卡片注入 rule 內文 `Don't reach for Box::leak in production code paths`，接著 agent 改提 `Arc<str>` 並請使用者確認。](https://omp.sh/clips/ttsr-poster.webp)

_[觀看錄影 ↗](https://omp.sh/clips/ttsr.mp4)_

### 05 · 第一級的子代理

把工作拆給多個 worker，拿回**帶型別**的結果。task 會 fan out 到各自隔離的 worktree，每個 worker 跑自己的工具面，最終的 yield 是一個經 schema 驗證、parent 可直接讀取的物件。沒有散文要解析、兄弟節點之間沒有 merge 衝突、沒有孤兒編輯。

![omp TUI 顯示 `task` spawn 兩個子代理 `ComponentsExports` 與 `RoutesExports`、要求同儕之間進行 IRC DM 的 constraints 區塊、各子代理的狀態卡片（含成本與時長），以及最後列出兩者 exports 的 Findings 區段，加上一段誠實的「IRC coordination note」說明握手其實是單向的。](https://omp.sh/clips/irc-poster.webp)

_[觀看錄影 ↗](https://omp.sh/clips/irc.mp4)_

在 fan-out 進行時觀看它：`Alt+A` 開啟 [Agent Hub](./agent-hub.md)，名冊會顯示每個子代理目前的活動與用量。點開其中一個可以讀它的即時 transcript、輸入導引訊息、復活被 park 的 worker，或在不中止 parent session 的情況下終止卡住的那個。

### 06 · 第二個模型，盯著每一輪。

把 reviewer 模型配到「advisor」角色，它會讀主 agent 的每一輪，並行內注入註記 —— 可能是安靜的旁白、一個疑慮，或一個硬性阻擋。它跑在自己的 context 與自己的模型上，所以會抓到那個「做事的」趕過去沒看的東西。主 agent 看到註記後會修正路線，或告訴你為什麼它不打算改。

![omp TUI：/advisor status 顯示 advisor 跑在 openai-codex/gpt-5.5；在主 agent 把一個 catch 收窄成 ENOENT 而不是吞掉所有錯誤之後，一張琥珀色的 'Advisor 1 note (concern)' 卡片警告這個修法已不再符合使用者字面上的驗收標準。](https://omp.sh/clips/advisor-poster.webp)

_[觀看錄影 ↗](https://omp.sh/clips/advisor.mp4)_

### 07 · 把連結給人，他們就進來了。

/collab 把你的即時 session 放上 relay，回給你一個連結 —— 還有一個 QR。隊友可以從另一個終端機用 omp join 加入，或直接在瀏覽器開啟。用讀寫模式共享來一起操作同一個 agent，或用 /collab view 產生任何人都能看但沒人能操控的唯讀連結。frame 在 client 端封裝，relay 永遠看不到你的金鑰。

![omp TUI：/collab view 印出 'Collab session started!'，附上 omp join 命令、my.omp.sh 瀏覽器連結、註記 'Anyone with this link can watch the session but cannot prompt the agent'，以及一個可掃描的大型 QR code。](https://omp.sh/clips/collab-poster.webp)

_[觀看錄影 ↗](https://omp.sh/clips/collab.mp4)_

### 08 · 讀 arxiv 上的 pdf，為什麼不？

web_search 串起二十三個排序過的供應商，把找到的 URL 直接交給 read。Arxiv PDF、GitHub 頁面、Stack Overflow 討論串都會以結構化 markdown 回來，錨點完好 —— 跟你用在本機檔案上的是同一套工具面。引用、跟進、摘錄，永遠不會弄丟你從哪裡來。

![omp TUI：web_search 為 inference-time compute scaling 回傳 10 個排序過的 Perplexity 來源，agent 挑了一篇 arxiv 論文、呼叫 read https://arxiv.org/pdf/2604.10739v1，並用真實數字摘要該論文的主要結果。](https://omp.sh/clips/web-poster.webp)

_[觀看錄影 ↗](https://omp.sh/clips/web.mp4)_

### 09 · 毫不妥協地原生。連 Windows 上也是。

其他 agent 會 shell out 去呼叫 rg、grep、find 與 bash。在很多機器上那些執行檔根本不存在，而在有的機器上，每次呼叫都要付一次 fork-exec 的來回成本。omp 把真正的實作連結進行程內。ripgrep、glob、find：都在行程內。brush 就是那個 bash —— session 能跨呼叫存活，而且有 58 個命令列工具（ls、sed、sort、xargs，甚至 jq）被移植進 builtins crate 並在行程內執行，零 fork/exec。同一個 omp binary 在 macOS、Linux 與 Windows 上執行 —— 不需要 WSL 橋接。

### 10 · 帶優先度與結論的程式碼審查

你會得到「這個變更能不能出貨」的明確結論，每個問題都從 P0 排到 P3 並附信心分數。/review 會 spawn 專用的 reviewer 子代理，平行掃過分支、單一 commit 或未提交的工作。你先處理擋住發布的那些；沒有重要的東西會藏在一大片散文裡。

### 11 · Hashline：以內容雜湊編輯

完美的編輯，更少的 token。模型指向**錨點**而不是重打它想改的那些行，所以空白字元的戰爭與 string-not-found 迴圈就這樣停了。編輯一個過期的檔案時錨點會分歧 —— 我們會在它把東西改壞之前拒絕這個 patch。Grok 4 Fast 在同樣的工作上少花 61% 的輸出 token。

### 12 · GitHub 只是另一個檔案系統

其他 harness 外掛 gh_issue_view、gh_pr_view、gh_search —— 每個都有自己的參數，agent 要學、你要 debug。我們跳過了那一步。read 本來就處理路徑；PR 就是路徑。教給模型的介面只有一個，要維持正確的介面也只有一個。

### 13 · 由 agent 自己策展的記憶

Agent 會記得你的 codebase，跨 session。它在執行中用 retain 寫下事實、用 learn 捕捉可重用的教訓、用 recall 把它們拉回來，並把每個 session 壓縮成一個心智模型，在下一個 session 的第一輪載入。用 `memory.backend` 挑選引擎 —— local、Hindsight 或 Mnemopi。預設以專案為範圍，所以它對這個 repo 學到的東西就留在這個 repo。

### 14 · ACP：可由編輯器驅動的 agent

在 Zed 裡跑 omp，你得到的就是你從終端機驅動的那個 agent —— 讀你正在看的那個 buffer、透過編輯器的儲存路徑寫入、在編輯器的終端機裡開 shell。破壞性工具會暫停等一個你可以回答一次就忘掉的權限提示。沒有橋接、沒有外掛、沒有第二顆要同步的大腦。

### 15 · 繼承你其他工具已經寫好的東西

其他每個 agent 都出貨一個匯入器，然後期待你去轉檔。omp 直接以原生形狀讀取磁碟上已經存在的八種格式 —— Cursor MDC、Cline .clinerules、Codex AGENTS.md、Copilot applyTo，以及其餘那些。沒有遷移腳本、沒有 YAML 轉 TOML 的移植、沒有「支援部分子集」的註腳。你的團隊上一季寫的設定，今晚照樣能用。

### 16 · omp commit：原子式拆分、經驗證的訊息

omp 透過 git_overview、git_file_diff 與 git_hunk 讀取工作樹，然後把不相關的改動拆成原子 commit，並依相依關係排序。有環的話會在寫入任何東西之前就被拒絕。原始碼檔案的分數高於測試、文件與設定，所以領頭的那個 commit 就是重要的那個。Lock 檔案完全被排除在分析之外。

### 17 · 讀 PR。_走訪 skill。_ 從子代理裡拉出 JSON。

十六種內部 scheme —— `pr://`、`issue://`、`agent://`、`skill://`、`ssh://` 以及其餘那些 —— 在 agent 已經會呼叫的每一個檔案系統形狀的工具中透明解析。`read pr://1428` 回傳的形狀跟 `read src/foo.ts` 一樣。`grep` 走訪 diff 就像走訪目錄。`agent://<id>/findings.0.path` 依路徑從子代理的輸出中拉出一個欄位。

![omp TUI 讀取 pr://can1357/oh-my-pi/1063 然後 /diff/1，顯示 hunk 標頭、新增的行，以及一個 [MODIFIED] (+12 -0) 摘要。](https://omp.sh/captures/pr.webp)

### 18 · 衝突解決，變簡單了。

每個 merge 衝突變成一個 URL。Agent 把 `@theirs`、`@ours` 或 `@base` 寫進 `conflict://N`，檔案就乾淨地解決了。批次形式：`conflict://*`。

![omp TUI：✓ Read src/session.ts (⚠ 1 conflict)，然後 ✓ Write conflict://1 · 1 line 內容為 @theirs，接著一句確認 'Resolved.'](https://omp.sh/clips/conflict-poster.webp)

_[觀看錄影 ↗](https://omp.sh/clips/conflict.mp4)_

### 19 · 先預覽，再接受。

`ast_edit` 回傳一張帶取代次數的 _(proposed)_ 卡片。變更處於暫存狀態。Agent 把一行理由寫進 `xd://resolve`；TUI 把它變成一張 **Accept** 卡片，然後磁碟上的搬移才真的發生 —— 原子式，全有或全無。

![omp TUI：✓ AST Edit: console.log($X) (proposed) 3 replacements · 1 file，然後 ✓ Accept: 3 replacements in 1 file (AST Edit)，接著 'Applied 3 replacements in src/auth.ts.'](https://omp.sh/clips/codemod-poster.webp)

_[觀看錄影 ↗](https://omp.sh/clips/codemod.mp4)_

### 20 · 驅動一個_真正的瀏覽器_。_或是你的 Slack？_

Stealth 預設開啟，所以頁面看到的是一般使用者而不是 headless bot。同一套 API 可以就地驅動任何 Electron 應用 —— 把它指向 Slack，agent 讀你的 DM 就像它讀網頁一樣。或者完全跳過沙箱：browser relay 擴充套件讓 agent 接管你已經開著的 Chrome 分頁，而且不會搶走焦點。

![omp TUI 用 browser 工具操作 DuckDuckGo](https://omp.sh/captures/browser.webp)

### 21 · 手直接放在桌面上

`computer` 對真實主機執行常駐的 JavaScript：列舉視窗與顯示器、擷取螢幕、送出原生輸入、走訪 OS 的無障礙樹、操作剪貼簿。這不是 browser 工具、沒有 DOM —— 就是你正在看的那個桌面。

## 不管任務需要什麼，_盒子裡都有了_。

31 個工具與 `read`、`bash` 活在同一個命名空間。用 `--tools read,edit,bash,…` 釘住啟用集合；很少用的可探索工具留在 `xd://` device 後面。`read xd://` 列出它們，`write xd://<tool>` 在 `tools.xdev` 啟用時執行其中一個。

**檔案與搜尋**

- `read` —— 檔案、目錄、封存檔、SQLite、PDF、notebook、URL、遠端 `ssh://` 路徑，以及內部 `://` scheme，全部走同一條路徑。
- `write` —— 建立或覆寫一個檔案、封存檔項目或 SQLite 資料列。
- `edit` —— 帶內容雜湊錨點的 hashline patch，含錨點失效的復原機制。
- `ast_edit` —— 套用前先預覽的結構化改寫，透過 ast-grep。
- `ast_grep` —— 對 50+ 種 tree-sitter 文法的結構化程式碼查詢。
- `grep` —— 對檔案、glob 與內部 URL 的正規表達式搜尋。
- `glob` —— 以 glob 查找路徑；需要內容比對時用 `grep`。

**執行時期**

- `bash` —— 工作區 shell，含 46 個行程內 coreutils、可選 PTY，以及背景 job 派發。
- `eval` —— 常駐的 Python 與 JavaScript cell，共用 prelude 且可回呼工具。

**程式碼智慧**

- `lsp` —— 診斷、導覽、符號、rename、code action、raw request。
- `debug` —— 驅動 DAP session —— 中斷點、單步、執行緒、堆疊、變數。
- `security_scan` —— 規劃並執行原生的安全審查；驅動 Codex Security 雲端掃描。

**協調**

- `task` —— 平行 fan out 子代理，可選工作區隔離。
- `hub` —— 對執行中的 agent 傳訊、等待或取消背景 job、監督長跑行程。
- `todo` —— 對 session todo 清單的有序變更，含階段追蹤。
- `ask` —— 給互動式執行用的結構化追問。

**桌面與網路**

- `browser` —— 在 headless Chromium、CDP 附著的應用，或透過 relay 接管你自己的 Chrome 上操作 Puppeteer 分頁。
- `computer` —— 對主機桌面執行常駐 JS：視窗、螢幕擷取、原生輸入、AX tree、剪貼簿。
- `web_search` —— 一次查詢跨所有已設定的供應商，回傳答案加引用。
- `github` —— GitHub CLI 操作 —— repo、PR、issue、程式碼搜尋、Actions run-watch。
- `generate_image` —— 透過 Gemini、GPT 或 xAI Grok 影像模型產生或編輯點陣圖。
- `inspect_image` —— 對本機影像檔的視覺模型分析。
- `tts` —— 透過 xAI Grok Voice 的文字轉語音 —— 五種內建聲音，WAV 或 MP3。

**記憶與 skill**

- `checkpoint` —— 標記對話狀態，供之後收合並回報。
- `rewind` —— 修剪探索性的 context，保留一份精簡報告。
- `retain` —— 把持久事實排入目前的記憶庫。
- `recall` —— 在記憶庫中搜尋原始記憶。
- `reflect` —— 對記憶庫綜合出一個答案。
- `memory_edit` —— 依 id 更新、遺忘或作廢已儲存的記憶。
- `learn` —— 捕捉可重用的教訓；可選擇把它升級成 managed skill。
- `manage_skill` —— 建立、更新或刪除一個隔離的 managed skill。

受設定管控、預設關閉：`github`、`security_scan`、`generate_image`、`tts`、`checkpoint`、`rewind`，以及記憶工具（`retain`／`recall`／`reflect`／`memory_edit`，依 `memory.backend` 而定）。`inspect_image` 會在目前模型看不見時自動啟用。

[完整參考 →](https://omp.sh/docs/tools)

### Prompt 控制

三個獨立的小寫字詞讓單一回合進入特化的 agent 行為：

- `ultrathink` —— 要求仔細的多步推理，以及支援範圍內最高的自動 thinking 強度。
- `orchestrate` —— 透過平行子代理執行大塊獨立工作，並逐階段驗證。
- `workflowz` —— 用目前的 `task` 工具建立確定性的多子代理 workflow。

它們只在散文中觸發，不會在 code span、fenced code block、XML/HTML 區段、識別字或路徑中觸發。精確的比對規則與設定請見 [Magic keywords](./magic-keywords.md)。

### Session 控制

Slash command 改變整個 session 的運作方式：

- `/vibe` —— 進入 [Vibe mode](./vibe-mode.md)：以導演身分驅動常駐的 `fast`／`good` worker session，工具面只留 `read`。
- `/fresh` —— 重置供應商的串流狀態（過期的 prompt cache、卡住的串流），不改變本機 transcript。見 [Session operations](../session-operations-export-share-fork-resume.md#fresh)。

## 六十多個供應商、上千個模型，_一個 /model 之遙_。

十個角色依意圖分流工作。`default` 給一般回合。`smol` 給便宜的子代理 fan-out。`slow` 給深度推理。`plan` 給 plan mode。`commit` 給變更紀錄。再加上 `vision`、`designer`、`task`、`advisor` 與 `tiny` 各司其職。啟動時用 `--smol`、`--slow`、`--plan` 覆寫；用 `Ctrl+P` 在目前角色已設定的模型間循環。用 `/model` slash command 在 session 中途切換啟用的模型。

下面的認證標籤：`oauth` 用你的供應商帳號登入，`plan` 走 coding-plan 訂閱路由，`local` 對本機 server 執行且金鑰可選。

### 前沿 API

直連 API 與 gateway。可以逐角色混搭供應商。

Anthropic `oauth` · OpenAI · OpenAI Codex `oauth` · Google Gemini · Google Vertex · Google Antigravity `oauth` · xAI · SuperGrok `oauth` · DeepSeek · Mistral · Groq · Cerebras · Fireworks · Together · Baseten · Hugging Face · NVIDIA · Meta · Amazon Bedrock · Azure OpenAI · SiliconFlow · GMI Cloud · CoreWeave · Sakana AI · OpenRouter · Synthetic · Vercel AI Gateway · Cloudflare AI Gateway · Wafer Serverless

### Coding plan

以訂閱路由。`/login` 把 session 掛上去。

Cursor `oauth` · GitHub Copilot `oauth` · GitLab Duo · Devin `oauth` · Kimi Code `plan` · Moonshot · MiniMax Coding Plan `plan` · MiniMax Coding Plan CN `plan` · Alibaba Coding Plan `plan` · Qwen Portal `oauth` · Z.AI / GLM Coding Plan `plan` · Zhipu Coding Plan `plan` · Xiaomi MiMo · Qianfan · Umans `plan` · NanoGPT · Novita · Venice · Kilo · ZenMux · OpenCode Go · OpenCode Zen

### 自己跑

OpenAI 相容的 `/v1/models`。本機實例可略過金鑰。

Ollama `local` · Ollama Cloud · LM Studio `local` · llama.cpp `local` · vLLM `local` · LiteLLM

### 自訂 OpenAI 相容供應商

在 `~/.omp/agent/models.yml` 定義自訂供應商：

```yaml
providers:
  spark:
    baseUrl: http://192.168.10.223:8000/v1
    api: openai-completions
    apiKey: dummy
    models:
      - id: minimax-m3
        name: MiniMax M3
        contextWindow: 100000
        maxTokens: 32000
```

執行 `omp models spark` 驗證 discovery。然後執行 `omp setup` 並在預設模型那一步選擇它，或在 session 中開啟 `/model` 把它指派給 `default` 角色。

要在不使用選單的情況下預先設定預設值，把選擇子加進 `~/.omp/agent/config.yml`：

```yaml
modelRoles:
  default: spark/minimax-m3
```

### 讓路由真正有用的四個旋鈕

- **自訂供應商** —— 在 `~/.omp/agent/models.yml` 中宣告任何說得通 `openai-completions`、`openai-responses`、`openai-codex-responses`、`azure-openai-responses`、`anthropic-messages`、`bedrock-converse-stream`、`google-generative-ai`、`google-gemini-cli` 或 `google-vertex` 的端點。
- **Fallback 鏈** —— 在 `retry.fallbackChains` 底下設定 per-role 或 per-model 的鏈。當主要端點丟 429 或撞上配額牆時，下一個接手該回合的其餘部分 —— 冷卻後恢復。
- **路徑範圍模型** —— 把 `enabledModels` 與 `disabledProviders` 的項目限定在 `path:` 前綴，就能在單一 repo 上釘住不同的模型集合而不動到全域設定。範圍項目涵蓋該路徑及其下的一切。
- **輪替憑證** —— 每個供應商可以疊多把 API key，執行時期會以 session affinity 與 per-credential backoff 輪替。當一把金鑰會在午餐前燒光配額時很有用。

完整的供應商與路由參考在 [omp.sh/docs/providers](https://omp.sh/docs/providers)。

## 二十三個後端。_一個 agent 早就會用的工具_。

`web_search` 是內建的，不是外掛上去的。`auto` 會走過二十三個供應商組成的鏈；如果你已經在付費用某一個，就用名字釘住它。在每個命中的背後，站台感知的萃取會把 GitHub、registry、arXiv、Stack Overflow 與各種文件轉成結構化 markdown —— 錨點與連結目標都會存活下來。

### 搜尋供應商

二十三個後端。釘住一個，或讓 `auto` 依序走過整條鏈。

| provider | 認證 |
| ------------ | ----------------------------------------- |
| `auto` | chain |
| `perplexity` | `PERPLEXITY_API_KEY`（有匿名 fallback） |
| `gemini` | oauth |
| `anthropic` | oauth |
| `codex` | oauth |
| `xai` | oauth 或 `XAI_API_KEY` |
| `zai` | `ZAI_API_KEY` |
| `exa` | `EXA_API_KEY`（或 mcp） |
| `tinyfish` | `TINYFISH_API_KEY` |
| `jina` | `JINA_API_KEY` |
| `kagi` | `KAGI_API_KEY` |
| `tavily` | `TAVILY_API_KEY` |
| `firecrawl` | `FIRECRAWL_API_KEY`（有免金鑰 fallback） |
| `brave` | `BRAVE_API_KEY` |
| `kimi` | `/login kimi-code` 或搜尋金鑰 |
| `parallel` | `PARALLEL_API_KEY` |
| `synthetic` | `SYNTHETIC_API_KEY` |
| `searxng` | 自架 |
| `duckduckgo` | 免金鑰 |
| `startpage` | 免金鑰 |
| `google` | 免金鑰（瀏覽器） |
| `ecosia` | 免金鑰（瀏覽器） |
| `mojeek` | 免金鑰（瀏覽器） |
| `public` | 免金鑰（以上全部，整合在一起） |

Exa 也接受透過 `/login exa` 儲存的 API key；明確選擇免金鑰時會走公開的 MCP fallback。

### 專門處理器

Agent 拿到的是結構化內容，不是被剝過的 HTML。

- **程式碼託管** —— github、gitlab
- **套件 registry** —— npm、PyPI、crates.io、Hex、Hackage、NuGet、Maven、RubyGems、Packagist、pub.dev、Go packages
- **研究來源** —— arxiv、semantic scholar
- **論壇** —— stack overflow、reddit、hn
- **文件** —— mdn、readthedocs、docs.rs

頁面會轉成 markdown 並保留連結結構。Agent 可以引用、跟進與摘錄，而不會弄丟錨點。

### 安全資料庫

弱點查詢回答的是廠商資料，不是部落格摘要。

- **NVD** —— national vulnerability database
- **OSV** —— open source vuln feed
- **CISA KEV** —— known exploited vulns

[`web_search` 參考 ↗](https://omp.sh/docs/tools#web_search)

## 大約 **~80,000** 行 Rust，做著其他 harness 只能 shell out 的事。

六個 crate、一個標記平台的 N-API addon。搜尋、shell、AST、語法標示、PTY、桌面控制、影像解碼、BPE 計數 —— 全部在 libuv pool 上、在行程內完成。熱路徑上沒有 fork/exec。另外約 8 萬行隨行 vendored：brush bash fork，加上 58 個命令列工具 —— coreutils、findutils、sed、jq、以 ripgrep 為底的 grep、fd、diff、moreutils —— 被移植進 builtins crate 並直接編譯進 shell。

- Crate：`pi-natives`、`pi-shell`、`pi-ast`、`pi-iso`、`pi-voice`、`pi-walker`
- 平台：`linux-x64`、`linux-arm64`、`darwin-x64`、`darwin-arm64`、`win32-x64` —— x64 同時出 AVX2 與 baseline 兩個 binary

各 crate 的程式碼行數（不含註解）：

| Crate | 做什麼 | ~LoC |
| ------------- | -------------------------------------------------------------------------------------- | -----: |
| pi-shell | 內嵌 bash 引擎 · 常駐 session · 行程內 coreutils 分派 · minimizer | 38,000 |
| pi-natives | N-API 介面 —— 下表中的每一個模組 | 25,000 |
| pi-walker | 平行、遵守 ignore 的 walker + grep · glob · workspace · shell 共用的 scan cache | 5,200 |
| pi-iso | 工作區隔離 · apfs · btrfs · zfs · reflink · overlayfs · projfs · rcopy | 3,300 |
| pi-ast | tree-sitter + ast-grep 比對、區塊解析、結構化摘要 | 2,900 |
| pi-voice | 音訊擷取／播放 · Opus · 即時 WebRTC | 1,000 |

在 `pi-natives` 內部，各模組的細分（略去膠水程式碼與測試）：

| 模組 | 做什麼 | 由什麼驅動 | ~LoC |
| ------------- | --------------------------------------------------------------------------------- | ----------------------------------------- | -----: |
| desktop | 視窗／顯示器列舉 · 螢幕擷取 · 原生輸入 · 給 `computer` 用的 AX tree | xcap · enigo · OS AX FFI | 10,600 |
| grep | 正規表達式搜尋 · 平行／循序 · glob 與型別篩選 · 模糊搜尋 | grep-regex · grep-searcher | 3,280 |
| text | ANSI 感知的寬度 · 截斷 · 欄位切片 · 保留 SGR 的換行 | unicode-width · segmentation | 2,070 |
| snapcompact | 給 context 壓縮用的點陣 frame 光柵化 + PNG 編碼 | image · png | 1,760 |
| keys | Kitty 鍵盤協定，含 xterm fallback · PHF 完美雜湊查找 | phf | 1,740 |
| ast | ast-grep 樣式比對與結構化改寫 | ast-grep-core | 1,510 |
| diff | 給工具與預覽用的結構化檔案 diff | in-tree | 1,030 |
| pty | 給 sudo · ssh 互動提示用的原生 PTY 配置 | portable-pty | 630 |
| crash_handler | 原生的當機擷取與回報 | in-tree | 610 |
| highlight | 語法標示 · 11 種語意類別 · 30+ 別名 | syntect | 550 |
| appearance | Mode 2031 + 透過 CoreFoundation FFI 的原生 macOS 深／淺色 | core-foundation | 450 |
| task | 在 libuv thread pool 上的阻塞工作 · 取消 · 逾時 · profiling | tokio · napi | 440 |
| glob | 以 glob 探索 · 型別篩選 · mtime 排序 · 遵守 gitignore | ignore · globset | 430 |
| fd | 取代 find 工具的檔案系統 walker | ignore | 385 |
| clipboard | 從系統剪貼簿複製文字與讀取影像 · 不需 xclip/pbcopy | arboard | 370 |
| workspace | 一次走訪即完成 gitignore + AGENTS.md 探索的 workspace walker | ignore | 275 |
| power | macOS 電源斷言 API，用於防止閒置／系統／顯示器睡眠 | IOKit FFI | 270 |
| prof | 環狀緩衝 profiler，輸出 folded stack 與 SVG 火焰圖 | inferno | 240 |
| file_lock | 跨行程的建議式檔案鎖 | in-tree | 210 |
| ps | 跨平台的行程樹終止與後代列舉 | libc · libproc · CreateToolhelp32Snapshot | 195 |
| tokens | O200k / Cl100k BPE token 計數 · 兩張表都內嵌 | tiktoken-rs | 70 |
| html | HTML 轉 Markdown，可選內容清理 | html-to-markdown-rs | 60 |
| sixel | 終端機影像渲染 · 解碼 PNG · JPEG · WebP · GIF · 縮放 · SIXEL 編碼 | icy_sixel · image | 55 |

## 四個進入點：_互動式_、_一次性_、RPC 與 ACP。

同一個引擎，四種包裝。`omp` 跑 TUI。`omp -p` 回答單一 prompt 後結束。Node SDK 把 session 嵌進你的行程。`omp --mode rpc` 與 `omp acp` 透過 stdio 把方向盤交給另一個程式。

### 互動式 —— 拿不準時，agent 會問

TUI 是預設的介面。Tool call 渲染成卡片、編輯在落地前先預覽，而模稜兩可之處會走 `ask` 工具 —— 一個 agent 可以在回合中途呼叫的結構化選項選單。其餘的交給鍵盤。

同樣的 prompt 卡片也會出現在 ACP 上，所以編輯器不用自己寫一個就有選單可用。

![omp TUI：ask 工具渲染出一個三選項的選單，第一個帶 (Recommended) 徽章，頁尾是 'up/down navigate · enter select · esc cancel'。](https://omp.sh/captures/ask.webp)

### SDK —— 嵌進 Node

`@oh-my-pi/pi-coding-agent`

Node 與 TypeScript 宿主可以直接把引擎拉進來。這個套件暴露 `ModelRegistry`、`SessionManager`、`createAgentSession` 與 `discoverAuthStorage`；session 會發出你可以訂閱的具型別事件。

```ts
import {
  ModelRegistry,
  SessionManager,
  createAgentSession,
  discoverAuthStorage,
} from "@oh-my-pi/pi-coding-agent";

const auth = await discoverAuthStorage();
const models = new ModelRegistry(auth);
await models.refresh();

const { session } = await createAgentSession({
  sessionManager: SessionManager.inMemory(),
  authStorage: auth,
  modelRegistry: models,
});
await session.prompt("list .ts files");
```

### RPC —— 透過 stdio 驅動

`omp --mode rpc`

給非 Node 的嵌入者，或你想要行程隔離的時候。NDJSON 命令進去，回應與事件 frame 出來。`--mode rpc-ui` 額外把 tool 卡片、選取器與對話框以 `extension_ui_request` frame 送出，由宿主負責回應。

```
$ omp --mode rpc --no-session
> {"id":"r1","type":"prompt","message":"list .ts files"}
< {"id":"r1","type":"response", ...}
> {"id":"r2","type":"set_model","provider":"anthropic","modelId":"sonnet-4.5"}
> {"id":"r3","type":"abort"}
```

### ACP —— 跟編輯器對話

`omp acp`

透過 JSON-RPC 的 [Agent Client Protocol](https://github.com/zed-industries/agent-client-protocol)。當編輯器宣告它的能力時，工具 I/O 會走它的路徑，而寫入會由 `session/request_permission` 把關。

| omp 工具 | ACP 路徑 |
| ------------ | ----------------------------------- |
| `bash` | `terminal/create + terminal/output` |
| `read` | `fs/read_text_file` |
| `write` | `fs/write_text_file` |
| `edit, bash` | `session/request_permission` |

完整參考：[omp.sh/docs/sdk](https://omp.sh/docs/sdk)。

## 值得留下的 harness，是那個你_不會_長大到用不下的。

到 **[omp.sh](https://omp.sh)** 把它拿起來用。

omp 是 [Mario Zechner](https://github.com/mariozechner) 的 [Pi](https://github.com/badlogic/pi-mono) 的 fork，被重寫成 coding-first 的介面：sessions、子代理、slash command、extension —— 全部是 TypeScript、全部 MIT、全部在 [GitHub](https://github.com/can1357/oh-my-pi) 上。從設定形塑它、從外部 hook 它，或在你需要時直接讀原始碼。

### 原語

Extension 就是一個 TypeScript module。跟內建的用同一套 tool API、同一個 slash command registry、同一張 hotkey 表、同一組 TUI 原語。沒有任何東西是保留的。

### 探索

首次執行時，omp 會繼承磁碟上已經存在的東西：來自 `.claude`、`.cursor`、`.windsurf`、`.gemini`、`.codex`、`.cline`、`.github/copilot` 與 `.vscode` 的 rules、skills 與 MCP server。沒有遷移腳本。

### 可擴充性

叫 omp 幫你寫缺的那一塊，然後 `/reload-plugins`。留在本機、包進 `marketplace`，或發布到 npm。

## 理念

omp 是 [Mario Zechner](https://github.com/mariozechner) 的 [pi-mono](https://github.com/badlogic/pi-mono) 的 fork，擴充成一套電池已附的 coding 工作流。

核心想法：

- 為真正的 coding 工作保留互動式、終端機優先的使用體驗
- 納入務實的內建能力（工具、sessions、branching、子代理、可擴充性）
- 讓進階行為可設定，而不是把它藏起來

---

## 開發

### 從原始碼開始

新 clone 需要先取得 workspace 相依與本機的 Rust/N-API addon，原始碼版的 CLI 才能啟動。

```sh
bun setup
bun dev
```

`bun setup` 會安裝 Bun workspace 並建置 `@oh-my-pi/pi-natives`。改動 Rust crate 或 `packages/natives` 後請重跑 `bun run build:native`。

Nix 使用者可以拿到釘住的 Bun 與 Rust 工具鏈，加上所有原生建置相依：

```sh
nix develop
bun setup
bun dev
```

用 `nix build .#omp` 建置並冒煙測試可散布的 Nix 套件。Wayland 螢幕擷取預設關閉（連結 libpipewire 會讓執行時期 closure 增加約 750 MB）；用 `omp.override { withWaylandScreencast = true; }` 啟用它。`nix/bun.nix` 只在 `bun.lock` 改變時產生；發布時會自動重新產生。相依變更時，執行：

```sh
bun run gen:nix
```

這個命令在可用時會使用 `nix develop` 中的 `bun2nix`，否則透過 Nix 進入開發 shell，再退回釘住的 `bunx bun2nix@2.1.2`。不要手動編輯 `nix/bun.nix`。

非互動式的冒煙檢查：

```sh
bun dev -- --version
```

### Debug 命令

`/debug` 開啟除錯、回報與 profiling 的工具。

架構與貢獻指南請見 [packages/coding-agent/DEVELOPMENT.md](../../packages/coding-agent/DEVELOPMENT.md)。

---

## Monorepo 套件

| 套件 | 說明 |
| ----------------------------------------------------------------------------- | --------------------------------------------------------------------------- |
| **[@oh-my-pi/collab-web](../../packages/collab-web)** | collab 即時 session 的瀏覽器 guest client、mock host 與本機 relay |
| **[@oh-my-pi/pi-ai](../../packages/ai)** | 多供應商 LLM client，含串流與模型／供應商整合 |
| **[@oh-my-pi/pi-catalog](../../packages/catalog)** | 模型目錄：內建模型資料庫、供應商描述子與身分識別 |
| **[@oh-my-pi/pi-agent-core](../../packages/agent)** | 帶 tool calling 與狀態管理的 agent runtime |
| **[@oh-my-pi/pi-coding-agent](../../packages/coding-agent)** | 互動式 coding agent CLI 與 SDK |
| **[@oh-my-pi/pi-tui](../../packages/tui)** | 帶差分渲染的終端 UI 函式庫 |
| **[@oh-my-pi/pi-natives](../../packages/natives)** | grep、shell、影像、文字、語法標示等的 N-API 綁定 |
| **[@oh-my-pi/omp-stats](../../packages/stats)** | AI 用量統計的本機可觀測性儀表板 |
| **[@oh-my-pi/omptype](../../packages/omptype)** | ArkType 相容的 schema 驗證，含 lazy JIT 編譯 |
| **[@oh-my-pi/pi-utils](../../packages/utils)** | 共用工具（logging、streams、dirs/env/process helper） |
| **[@oh-my-pi/pi-wire](../../packages/wire)** | 共用的 collab 即時 session 協定型別與 relay 常數 |
| **[@oh-my-pi/hashline](../../packages/hashline)** | `edit` 工具背後的行錨定 patch 語言與套用器 |
| **[@oh-my-pi/pi-mnemopi](../../packages/mnemopi)** | 給 Oh My Pi agent 用的本機 SQLite 記憶引擎 |
| **[@oh-my-pi/snapcompact](../../packages/snapcompact)** | 點陣 frame 的 context 壓縮套件與 SQuAD eval 套組 |
| **[@oh-my-pi/browser-relay](../../packages/browser-relay)** | 讓 browser 工具驅動你現有分頁的 Chrome 擴充套件 |
| **[@oh-my-pi/pi-metaharness](../../packages/metaharness)** | 統一的 benchmark runner、Harbor run 儲存、REST/SSE API、即時儀表板 |
| **[@oh-my-pi/typescript-edit-benchmark](../../packages/typescript-edit-benchmark)** | 建立在 TypeScript 原始碼變異上的編輯 benchmark 套組 |

### Rust Crates

| Crate | 說明 |
| -------------------------------------------------- | --------------------------------------------------------------------------------------------------- |
| **[pi-natives](../../crates/pi-natives)** | 核心 Rust 原生 addon（N-API `cdylib`），由 `@oh-my-pi/pi-natives` 使用；聚合下列各 crate |
| **[pi-shell](../../crates/pi-shell)** | 從 `pi-natives` 拆出的內嵌 shell / PTY / 行程管理（包裝 `brush-*`） |
| **[pi-ast](../../crates/pi-ast)** | 以 tree-sitter 為基礎的程式碼摘要器與 AST 工具（50+ 語言文法） |
| **[pi-iso](../../crates/pi-iso)** | Task 隔離後端解析器：APFS clone、btrfs/zfs reflink、overlayfs、projfs、rcopy |
| **[pi-voice](../../crates/pi-voice)** | 音訊擷取／播放、Opus 編解碼，以及即時 WebRTC 串流原語 |
| **[pi-walker](../../crates/pi-walker)** | 平行、遵守 ignore 的檔案系統 walker，含 grep、glob 與 workspace 共用的 scan cache |
| **[brush-core](../../crates/vendor/brush-core)** | [brush-shell](https://github.com/reubeno/brush) 的 vendored fork，用於內嵌 bash 執行 |
| **[pi-builtins](../../crates/pi-builtins)** | Bash builtins（cd、echo、test、printf、read、export……）加上 67 個行程內命令列工具 |

## 貢獻

Issue 與 pull request 對所有人開放。開放 PR 目前是**試行** —— 先前的 vouch 要求在我們評估成效期間暫時解除，未來可能回歸。貢獻指南請見 **[CONTRIBUTING.md](./contributing.md)**。

---

## 授權

MIT。見 [LICENSE](../../LICENSE)。

© 2025 Mario Zechner
© 2025-2026 Can Bölük

_made for terminals that stay open_

- [omp.sh](https://omp.sh)
- [GitHub](https://github.com/can1357/oh-my-pi)
- [Changelog](https://github.com/can1357/oh-my-pi/blob/main/packages/coding-agent/CHANGELOG.md)
- [npm](https://www.npmjs.com/package/@oh-my-pi/pi-coding-agent)
- [Discord](https://discord.gg/4NMW9cdXZa)
- [MIT](https://github.com/can1357/oh-my-pi/blob/main/LICENSE)
