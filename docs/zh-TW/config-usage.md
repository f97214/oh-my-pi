> 這是 [`docs/config-usage.md`](../config-usage.md) 的繁體中文翻譯。
> 翻譯基準：`1c7170e11`（2026-08-14）。**英文原文為準** —— 上游更新後本檔可能過期。

# 設定的探索與解析

本文件描述 coding-agent 目前如何解析設定：掃描哪些根目錄、優先順序怎麼運作，以及解析後的設定如何被 settings、skills、hooks、tools 與 extensions 使用。

## 範圍

主要實作：

- `packages/coding-agent/src/config.ts`
- `packages/coding-agent/src/config/config-file.ts`（由 `config.ts` re-export）
- `packages/coding-agent/src/config/settings.ts`
- `packages/coding-agent/src/config/settings-schema.ts`
- `packages/coding-agent/src/discovery/builtin.ts`
- `packages/coding-agent/src/discovery/helpers.ts`

主要整合點：

- `packages/coding-agent/src/capability/index.ts`
- `packages/coding-agent/src/discovery/index.ts`
- `packages/coding-agent/src/extensibility/skills.ts`
- `packages/coding-agent/src/extensibility/hooks/loader.ts`
- `packages/coding-agent/src/extensibility/custom-tools/loader.ts`
- `packages/coding-agent/src/extensibility/extensions/loader.ts`

---

## 解析流程（圖示）

```text
         Generic helper order (`config.ts`)
┌───────────────────────────────────────┐
│ 1) ~/.omp/agent, ~/.claude, ...       │
│ 2) <cwd>/.omp, <cwd>/.claude, ...     │
└───────────────────────────────────────┘
                    │
                    ▼
        capability providers enumerate items
 (native provider scans project .omp before user .omp;
  other providers have their own loading rules)
                    │
                    ▼
      provider priority sort + capability dedup
                    │
                    ▼
          subsystem-specific consumption
   (settings, skills, hooks, tools, extensions)
```

## 1) 設定根目錄與來源順序

## 標準根目錄

`src/config.ts` 定義了一組固定的來源優先順序：

1. `.omp`（native）
2. `.claude`
3. `.codex`
4. `.gemini`

使用者層的基底：

- OMP native：`~/<PI_CONFIG_DIR>/agent`（一般是 `~/.omp/agent`；具名 profile 會改變它，說明如下）
- `~/.claude`
- `~/.codex`
- `~/.gemini`

專案層的基底：

- `<cwd>/.omp`
- `<cwd>/.claude`
- `<cwd>/.codex`
- `<cwd>/.gemini`

`CONFIG_DIR_NAME` 是 `.omp`（`packages/utils/src/dirs.ts`）。`PI_CONFIG_DIR` 會改變泛用 helper 所使用的 OMP 使用者根目錄。`PI_CODING_AGENT_DIR` 則不同：在預設 profile 下，它會改變 `getAgentDir()` 的使用者（例如 native discovery、settings 與執行時期狀態），但它**不會**改變泛用的 `getConfigDirs()` / `findConfigFile()` 所用的 OMP 基底。具名 profile 會忽略 `PI_CODING_AGENT_DIR`。

## Profile

具名 profile（`omp --profile <name>`、`OMP_PROFILE`，或舊有的 fallback `PI_PROFILE`）會搬移 OMP 使用者基底。`OMP_PROFILE` 只要有定義就勝出，包含明確設為空字串的情況；`default`、空字串或空白會選到預設 profile。有 profile 生效時，本文中所有寫成 `~/.omp/agent/...` 的 OMP 原生使用者層路徑，一般會解析到 `~/.omp/profiles/<name>/agent/...`。`--alias <command>` 本身不會選擇 profile：與 `--profile` 搭配時，它會為該 profile 建立一個 shell 捷徑。

這個搬移在 native provider（`builtin.ts`）與泛用的 `config.ts` helper 之間是一致的，所以涵蓋 slash command、rules、prompts、instructions、hooks、tools、extensions、settings、skills 與 MCP，加上頂層的 `SYSTEM.md` / `RULES.md` / `AGENTS.md` 檔案與執行時期狀態（sessions、blobs、`agent.db`）。一個 profile 只看得到自己的 OMP 設定，永遠看不到預設 profile 的 agent 設定。

Keybinding 是唯一的例外：具名 profile 會把預設 profile 的 `~/.omp/agent/keybindings.*` 合併到自己的 `~/.omp/profiles/<name>/agent/keybindings.*` 底下，並由 profile 的檔案逐條覆寫（[#4867](https://github.com/can1357/oh-my-pi/issues/4867)）。Keybinding 描述的是使用者眼前的終端機／鍵盤，這不會隨著生效的 profile 改變，所以使用者層的重新對應在每個 profile 都持續有效，除非該 profile 明確覆寫它們。被繼承的檔案對 profile 行程而言是唯讀的 —— 預設 profile 檔案的舊格式遷移，只在預設 profile 自己執行時才會發生。

在 macOS 與 Linux 上，已存在的 `$XDG_DATA_HOME/omp`、`$XDG_STATE_HOME/omp` 或 `$XDG_CACHE_HOME/omp` 可以搬移對應的 data、state 或 cache 路徑。對具名 profile 而言，OMP 只有在該 XDG 類別**已經**包含 `omp/profiles/<name>` 時才會使用它；否則該類別仍留在 `~/.omp/profiles/<name>` 底下。要依賴 XDG 路徑前，請先執行 `omp config init-xdg`。

其他來源基底不受 profile 影響，在所有 profile 下的載入方式相同：外部工具的基底（`~/.claude`、`~/.codex`、`~/.gemini`）屬於那些工具，而專案層基底（`<cwd>/.omp`、`<cwd>/.claude`……）是以工作目錄為鍵。在本文件中，除非正在討論環境變數覆寫或 XDG 路徑，否則請把 `~/.omp/agent` 讀成「目前生效 profile 的 agent 目錄」的簡寫。

## 重要限制

`src/config.ts` 中的泛用 helper **不會**把 `.pi` 納入來源探索順序。

---

## 2) 核心探索 helper（`src/config.ts`）

## `getConfigDirs(subpath, options)`

回傳排序後的項目：

- 使用者層的項目在前（依來源優先順序）
- 接著是專案層的項目（依相同的來源優先順序）

選項：

- `user`（預設 `true`）
- `project`（預設 `true`）
- `cwd`（預設 `getProjectDir()`）
- `existingOnly`（預設 `false`）

這個 API 用於以目錄為基礎的設定查找（commands、hooks、tools、agents 等）。

## `findConfigFile(subpath, options)` / `findConfigFileWithMeta(...)`

在排序後的基底中尋找第一個存在的檔案，回傳第一個命中（只給路徑，或路徑加 metadata）。

## `findAllNearestProjectConfigDirs(subpath, cwd)`

往上走父目錄，回傳**每個來源基底最近的既存目錄**（`.omp`、`.claude`、`.codex`、`.gemini`），然後依來源優先順序排序結果。

當專案設定應該從祖先目錄繼承時（monorepo／巢狀 workspace 行為）使用它。

---

## 3) 檔案設定包裝（`src/config/config-file.ts` 的 `ConfigFile<T>`，由 `src/config.ts` re-export）

`ConfigFile<T>` 是單一設定檔的 schema 驗證載入器。

支援的格式：

- `.yml` / `.yaml`
- `.json` / `.jsonc`

行為：

- 依提供的 omptype schema 驗證解析後的資料。
- 快取載入結果直到 `invalidate()`。
- 透過 `tryLoad()` 回傳三態結果：
  - `ok`
  - `not-found`
  - `error`（帶 schema／解析脈絡的 `ConfigError`）

仍然支援的舊版遷移：

- 若目標路徑是 `.yml`/`.yaml`，同層的 `.json` 會被自動遷移一次（`migrateJsonToYml`）。

---

## 4) Settings 解析模型（`src/config/settings.ts`）

執行時期的 settings 模型是分層的：

1. 全域 settings：`~/.omp/agent/config.yml` 與 `config.yaml` 中第一個存在的檔案
2. 專案 settings：透過 settings capability 探索（來自各 provider 的 `settings.json` 與 `config.yml`）
3. 設定覆蓋層：`PI_CONFIG_FILES`（平台路徑清單），接著是重複的 `omp --config <path>` 檔案；全部以 `config.yml` 風格的 YAML 載入，且只對本行程生效
4. 執行時期覆寫：在記憶體中，不持久化
5. Schema 預設值：來自 `SETTINGS_SCHEMA`

實際的優先順序：

`defaults <- global <- project <- PI_CONFIG_FILES overlays <- --config overlays <- runtime overrides`

在任一覆蓋層清單內，較後面的檔案覆寫較前面的檔案。覆蓋層路徑相對於目前生效的專案目錄解析（在展開 `~` 之後）。

寫入行為：

- `settings.set(...)` 寫入**全域**層（啟動時選定的全域 YAML 檔案）並排入背景儲存。
- 專案 settings 與設定覆蓋層，從 settings API 的角度是唯讀的。

### Settings 載入失敗

- 缺少全域／專案 YAML 視為空設定。
- 無效的全域或 native 專案 YAML 會在檔案鎖保護下被移到同層唯一的 `.broken-<timestamp>-<pid>-<uuid>`，然後啟動失敗並附上原始與備份路徑。無法讀取的檔案會直接失敗，不做搬移。
- 每個 `PI_CONFIG_FILES` / `--config` 覆蓋層都是嚴格的：缺檔、無效 YAML，以及非 mapping 的文件根都是硬性錯誤。覆蓋層檔案不會被隔離。

## 仍然生效的遷移行為

啟動時，若全域的 `config.yml` 與 `config.yaml` 都不存在：

1. 從 `~/.omp/agent/settings.json` 遷移（成功後改名為 `.bak`）
2. 與 `agent.db` 中的舊版 DB settings 合併（衝突時 DB 的值勝出）
3. 把合併結果寫入 `config.yml`

`#migrateRawSettings` 中的欄位層級遷移：

- `queueMode` -> `steeringMode`
- `ask.timeout` 毫秒 -> 秒（當舊值看起來像毫秒時，即 `> 1000`）
- 舊的扁平 `theme: "..."` -> `theme.dark/theme.light` 結構

---

## 5) Capability／discovery 整合

多數非核心的設定載入都經過 capability registry（`src/capability/index.ts` + `src/discovery/index.ts`）。

## Provider 排序

Provider 依數值優先度排序（高者在前）。優先度範例：

- Native OMP（`builtin.ts`）：`100`
- Claude：`80`
- Codex / agents / Claude marketplace：`70`
- Gemini：`60`

```text
Provider precedence (higher wins)

native (.omp)          priority 100
claude                 priority  80
codex / agents / ...   priority  70
gemini                 priority  60
```

## 去重語意

Capability 定義一個 `key(item)`：

- 相同 key => 第一個項目勝出（優先度較高／較早載入者）
- 沒有 key（`undefined`）=> 不去重，保留所有項目

相關的 key：

- skills：`name`
- tools：`name`
- hooks：`${type}:${tool}:${name}`
- extension modules：`name`
- extensions：`name`
- settings：不去重（保留全部項目）

---

## 6) Native `.omp` provider 的行為（`packages/coding-agent/src/discovery/builtin.ts`）

Native provider（`id: native`）從這些位置讀取原生設定：

- 專案：`<cwd>/.omp/...`
- 使用者：`~/.omp/agent/...`

### 目錄採納規則

- Slash command、目錄 rules、prompts、instructions、hooks、tools、extensions、extension modules 與 settings，只有在根目錄存在且非空時才會使用該專案／使用者根目錄。
- Skills 會從目前工作目錄往上到 repo root／家目錄邊界，逐一掃描每個祖先的 `<ancestor>/.omp/skills`，再加上 `~/.omp/agent/skills`，而且**不要求** `.omp` 根目錄本身非空。
- `SYSTEM.md`、`RULES.md` 與 `.omp/AGENTS.md` 直接讀取使用者層檔案，專案檔案則使用最近的非空祖先 `.omp` 目錄。`RULES.md` 會變成 always-apply 的黏性 rule。完整的 `SYSTEM.md` / `APPEND_SYSTEM.md` 契約請見 [`docs/system-prompt-customization.md`](../system-prompt-customization.md)。
- MCP 不使用「非空根目錄」的採納 helper。它直接讀取專案的 `.omp/mcp.json` 然後 `.omp/.mcp.json`，接著是使用者的 `mcp.json` 然後 `.mcp.json`。

### 各範疇的載入方式

- Skills：`<ancestor>/.omp/skills/*/SKILL.md` 與 `~/.omp/agent/skills/*/SKILL.md`
- Slash commands：`commands/*.md`
- Rules：`rules/*.{md,mdc}` 加上頂層 `RULES.md`
- Prompts：`prompts/*.md`
- Instructions：`instructions/*.md`
- Hooks：`hooks/pre/*`、`hooks/post/*`
- Tools：`tools/*.{json,md,ts,js,sh,bash,py}` 與 `tools/<name>/index.ts`
- Extension modules：在 `extensions/` 底下探索（＋舊版的 `settings.json.extensions` 字串陣列）
- Extensions：`extensions/<name>/gemini-extension.json`
- Settings capability：`settings.json`，然後 `config.yml`
- Context 檔案：`.omp/AGENTS.md`；獨立的祖先 `AGENTS.md` 檔案由低優先度的 `agents-md` provider 另外載入

### 最近專案查找的細節

對 `SYSTEM.md`、`RULES.md` 與 `.omp/AGENTS.md`，native provider 會往上走到最近的**非空**專案 `.omp` 目錄。

## 7) 主要子系統如何使用設定

## Settings 子系統

- `Settings.init()` 依上述優先順序載入全域 YAML 檔案、探索到的專案 settings、`PI_CONFIG_FILES` / `--config` 覆蓋層，以及執行時期覆寫。
- 只有 `level === "project"` 的 capability 項目會被合併進專案層。

### Session 標題 prompt 覆寫

在任一泛用設定基底中建立 `TITLE_SYSTEM.md`：

```text
# ~/.omp/agent/TITLE_SYSTEM.md
Generate a session name using lowercase `<type>:<primary-objective>`.
```

- 沒有 `TITLE_SYSTEM.md` 就保留內建的標題 prompt。
- 探索會先檢查目前專案目錄的基底（`<cwd>/.omp`、`.claude`、`.codex`、`.gemini`），然後依泛用 helper 的順序檢查使用者基底。與 native 的 `SYSTEM.md` 不同，專案層的標題探索**不會**往上走祖先目錄。
- 此覆寫只取代自動產生 session 標題的 system prompt；一般的 `SYSTEM.md` / `APPEND_SYSTEM.md` prompt 客製不受影響。
- 線上路徑會要求標題模型把標題包在 `<title>...</title>` 中，並以寬鬆方式從文字解析（純句子、被截斷／未閉合的標籤，或多餘的 `{"title": "..."}` JSON 回聲都仍然可用）。`TITLE_SYSTEM.md` 的覆寫後面會被附加「包在 `<title>` 中」的指示。本機的 tiny-title 路徑保留 `<title>...</title>` 的 prefill／stop 包裝，並把這個檔案當成它的 system turn。

## Skills 子系統

- `extensibility/skills.ts` 透過 `loadCapability(skillCapability.id, { cwd })` 載入。
- 套用來源開關與篩選（`ignoredSkills`、`includeSkills`、自訂目錄）。
- 舊名稱的開關仍然存在（`skills.enablePiUser`、`skills.enablePiProject`），但它們管控的是 native provider（`provider === "native"`）。

## Hooks 子系統

- `discoverAndLoadHooks()` 從 hook capability 加上明確設定的路徑解析出 hook 路徑。
- 然後透過 Bun import 載入模組。

## Tools 子系統

- `discoverAndLoadCustomTools()` 從 tool capability 加上 plugin 的 tool 路徑與明確設定的路徑解析出 tool 路徑。
- 宣告式的 `.md`/`.json` tool 檔案只是 metadata；可執行的載入需要程式碼模組。

## Extensions 子系統

- `discoverAndLoadExtensions()` 載入 native 的 extension-module capability 項目、JS/TS hook factory、已安裝 plugin 的進入點，以及明確設定的路徑。
- 環境式的 extension-module capability 探索明確限制為 `provider: "native"`；此步驟不掃描外部 provider。

---

## 8) 可以依賴的優先順序規則

用這個心智模型：

1. `config.ts` 的來源目錄排序決定候選路徑的順序。
2. Capability provider 的優先度決定跨 provider 的優先順序。
3. Capability 的 key 去重決定衝突行為（有 key 的 capability 是第一個勝出）。
4. 子系統各自的合併邏輯可以再改變實際優先順序（尤其是 settings）。

### Settings 專屬的注意事項

Settings capability 的項目**不會**去重；`Settings.#loadProjectSettings()` 依回傳順序 deep-merge 專案項目，所以後面的項目覆寫前面的。Provider 是由高優先度往低優先度走訪，這代表**較低優先度的 provider settings 可以覆寫較高優先度的 settings**。在 native provider 內部，專案的 `config.yml` 排在 `settings.json` 之後並覆寫它。接著 native `.omp/config.yml` 的 model role 會被重新套用，作為權威的專案層 model-role 層。

---

## 9) 仍然存在的舊版／相容行為

- 對以 YAML 為目標的檔案，`ConfigFile` 的 JSON -> YAML 遷移。
- Settings 從 `settings.json` 與 `agent.db` 遷移到 `config.yml`。
- 欄位遷移涵蓋被更名／移除的設定與值形狀的變化，包含 `queueMode`、changelog 設定、`ask.timeout`、扁平的 `theme`、`inspect_image.enabled`、task 隔離／eager 設定、被移除的 edit 與 compaction 模式、`inlineToolDescriptors`、狀態列區段、provider／search 設定、memories／hindsight 設定，以及巢狀葉節點的更名。目前完整的清單請查閱 `Settings.#migrateRawSettings()`。
- 舊的設定名稱 `skills.enablePiUser` / `skills.enablePiProject` 仍然是 native skill 來源的有效開關。

若這些相容路徑在程式碼中被移除，請立即更新本文件；今天仍有數個執行時期行為依賴它們。
