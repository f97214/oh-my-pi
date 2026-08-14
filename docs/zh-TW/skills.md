> 這是 [`docs/skills.md`](../skills.md) 的繁體中文翻譯。
> 翻譯基準：`1c7170e11`（2026-08-14）。**英文原文為準** —— 上游更新後本檔可能過期。

# Skills

Skill 是以檔案為後端的能力包，在啟動時被探索出來，並以下列方式暴露給模型：

- system prompt 中的輕量 metadata（name + description）
- 透過 `read` 工具對 `skill://...` 取得的隨選內容
- 可選的互動式 `/skill:<name>` 命令

本文件描述 `packages/coding-agent/src/extensibility/skills.ts`、`packages/coding-agent/src/discovery/builtin.ts`、`packages/coding-agent/src/internal-urls/skill-protocol.ts` 與 `packages/coding-agent/src/discovery/agents-md.ts` 目前的執行時期行為。

## 在這個 codebase 裡 skill 是什麼

一個被探索到的 skill 表示為：

- `name`
- `description`
- `filePath`（`SKILL.md` 的路徑）
- `baseDir`（skill 目錄）
- 來源 metadata（`provider`、`level`、path）

執行時期只要求 `name` 與 `path` 就算有效。但實務上，匹配品質取決於 `description` 是否有意義。

## 必要的目錄結構與 SKILL.md 的期待

### 目錄結構

對 provider 式的探索（native／Claude／Codex／Agents／plugin providers），skill 是在 **`skills/` 底下一層** 被找到的：

- `<skills-root>/<skill-name>/SKILL.md`

像 `<skills-root>/group/<skill>/SKILL.md` 這種巢狀樣式**不會**被 provider loader 找到。

對 `skills.customDirectories`，掃描採用相同的非遞迴結構（`*/SKILL.md`）。

```text
Provider-discovered layout (non-recursive under skills/):

<root>/skills/
  ├─ postgres/
  │   └─ SKILL.md      ✅ discovered
  ├─ pdf/
  │   └─ SKILL.md      ✅ discovered
  └─ team/
      └─ internal/
          └─ SKILL.md  ❌ not discovered by provider loaders

Custom-directory scanning is also non-recursive, so nested paths are ignored unless you point `customDirectories` at that nested parent.
```

### `SKILL.md` frontmatter

skill 型別上支援的 frontmatter 欄位：

- `name?: string`
- `description?: string`
- `globs?: string[]`
- `alwaysApply?: boolean`
- `hide?: boolean`
- `disableModelInvocation?: boolean`（Agent Skills 中等同於 `hide`；由 kebab-case 的 `disable-model-invocation` 正規化而來）
- 其他鍵會以未知 metadata 的形式保留

目前的執行時期行為：

- `name` 預設為 skill 的目錄名稱
- 下列情況**必須**有 `description`：
  - native `.omp` provider 的 skill 探索（`requireDescription: true`）
  - `omp-plugins` extension-package skill 與 `github` provider（`.github/skills/`），兩者同樣傳入 `requireDescription: true`
  - `skills.customDirectories` 透過 `src/discovery/helpers.ts` 的 `scanSkillsFromDir` 掃描（非遞迴）
- claude／codex／agents／opencode／claude-plugins 這些 provider 可以載入沒有 description 的 skill

## 探索流程

`packages/coding-agent/src/extensibility/skills.ts` 中的 `loadSkills()` 會跑三個階段：

1. **能力 provider**，透過 `loadCapability("skills")`（managed／auto-learn provider 的 skill 在這裡會被跳過，改在第 3 階段處理）
2. **自訂目錄**，透過 `scanSkillsFromDir(..., { requireDescription: true })`（單層目錄列舉）。自訂目錄的 skill 會覆寫同名的預設 provider skill；自訂目錄之間若有重名，仍是先到先贏。
3. **Managed（auto-learn）skill**（`omp-managed` provider）最後才解析，所以來自 provider 或自訂目錄、同名且已啟用的手寫 skill 一律優先

若 `skills.enabled` 為 `false`，探索不回傳任何 skill。

### 內建 skill provider 與優先順序

Provider 排序以優先度優先（數字大者勝），同分時依註冊順序。

目前註冊的 skill provider：

1. `native`（優先度 100）—— 透過 `src/discovery/builtin.ts` 的 `.omp` 使用者／專案 skill
2. `omp-plugins`（優先度 90）—— 與 extension package 併放的 `skills/`，透過 `extensions:`、`--extension`/`-e` 載入，或安裝在 `~/.omp/plugins/node_modules` 底下的 plugin
3. `claude`（優先度 80）
4. 優先度 70 的群組（依註冊順序）：
   - `claude-plugins`
   - `agents`
   - `codex`
5. `opencode`（優先度 55）
6. `github`（優先度 30）—— `.github/skills/<name>/SKILL.md`（GitHub Agent Skills 結構，僅限專案層）
7. `omp-managed`（優先度 5）—— `~/.omp/agent/managed-skills` 底下的 auto-learn skill，在 `src/discovery/builtin.ts` 註冊並無條件探索（只有寫入／提示受 `autolearn.enabled` 管控）；一律讓位給同名的手寫 skill

去重的鍵是 skill 名稱。同名者第一個勝出。

### 來源開關與篩選

`loadSkills()` 套用這些控制項：

- 來源開關：`enableCodexUser`、`enableClaudeUser`、`enableClaudeProject`、`enablePiUser`、`enablePiProject`、`enableAgentsUser`、`enableAgentsProject`
- `disabledExtensions` 中形如 `skill:<name>` 的項目
- `ignoredSkills`（排除；glob 樣式）
- `includeSkills`（納入白名單；glob 樣式；空的代表全部納入）

篩選順序是：

1. 未被 `disabledExtensions` 停用
2. 來源已啟用
3. 未被忽略
4. 有在納入清單中（若有提供納入清單）

`agents` provider（`.agent[s]/skills`）是 OMP 原生的標準位置，有自己的 `enableAgentsUser`／`enableAgentsProject` 開關 —— 停用 Claude／Codex／Pi **不會**把它關掉。沒有專屬開關的 provider（`claude-plugins`、`opencode`、`github`……）只要**任一個**具名的第三方來源開關是開的，它們就會啟用。

### 衝突與重複的處理

- 能力層的去重已經為每個名稱保留第一個 skill（優先度最高的 provider）
- `extensibility/skills.ts` 額外做：
  - 以 `realpath` 對相同檔案去重（symlink 安全）
  - 後續 skill 名稱衝突時發出警告
  - 保留便利 API `loadSkillsFromDir({ dir, source })`，它是 `scanSkillsFromDir` 的薄轉接層
- 自訂目錄的 skill 在 provider skill 之後合併，並覆寫同名的預設路徑 provider skill。自訂目錄彼此之間，同名者第一個勝出。

## 執行時期的使用行為

### System prompt 曝光

System prompt 的組建（`src/system-prompt.ts`）這樣使用探索到的 skill：

- 若 `read` 工具可用：
  - 在 prompt 中納入探索到的 skill 清單，排除 `hide: true` 的 skill
- 否則：
  - 略去該清單

`hide: true` **不會**停用 skill。被隱藏的 skill 仍然會被載入，且在 skill 命令啟用時仍可透過 `skill://<name>` 與 `/skill:<name>` 取用。

Task 工具的子代理透過一般的 session 建立流程取得該 session 探索到／提供的 skill 清單；沒有 per-task 的 skill 釘選覆寫機制。

### 互動式 `/skill:<name>` 命令

若 `skills.enableSkillCommands` 為 true，互動模式會為每個探索到的 skill 註冊一個 slash command。

`/skill:<name> [args]` 的行為：

- 同時辨識傳統的開頭形式，以及嵌在一般散文中、以空白分隔的 `/skill:<name>` token
- 對嵌入的 token，會移除該 token 並把周圍的散文當成參數傳入
- 當草稿以另一個 slash command 或本機 bash／Python 執行的 sigil 開頭時，不把嵌入的 token 當成呼叫
- 直接從 `filePath` 讀取 skill 檔案
- 移除 frontmatter
- 以 skill 名稱、base directory 與可選的使用者參數包裹內文，然後以 custom message 的形式注入
- 傳遞模式取決於**送出時使用的 keybinding**：
  - **Enter** → 串流中時把 skill 放進 `steer` 佇列呼叫（與自由文字的 Enter 一致，那也是 steer），代理不在串流時則作為一般的 idle prompt
  - **Ctrl+Enter**（`app.message.followUp`）→ 串流中時把 skill 放進 `followUp` 佇列呼叫，代理不在串流時則作為一般的 idle prompt

沒有任何旗標、模式選擇器或 frontmatter 開關可以覆寫傳遞模式 —— keybinding **就是**那個選擇，與串流中自由文字的路由方式完全相同。

## `skill://` URL 行為

`src/internal-urls/skill-protocol.ts` 支援：

- `skill://<name>` → 解析到該 skill 的 `SKILL.md`
- `skill://<name>/<relative-path>` → 解析到該 skill 目錄內

```text
skill:// URL resolution

skill://pdf
  -> <pdf-base>/SKILL.md

skill://pdf/references/tables.md
  -> <pdf-base>/references/tables.md

Guards:
- reject absolute paths
- reject `..` traversal
- reject any resolved path escaping <pdf-base>
```

解析細節：

- skill 名稱必須完全相符
- 相對路徑會做 URL 解碼
- 絕對路徑會被拒絕
- 路徑穿越（`..`）會被拒絕
- 解析後的路徑必須留在 `baseDir` 之內
- 找不到檔案時回傳明確的 `File not found` 錯誤

Content type：

- `.md` => `text/markdown`
- 其他一律 => `text/plain`

找不到資產時**不會**做任何 fallback 搜尋。

## Skills 與 AGENTS.md、命令、工具、hooks 的差別

### Skills 與 AGENTS.md

- **Skills**：具名的、可選的能力包，依任務脈絡選用或明確要求
- **AGENTS.md／context 檔案**：常駐的指示檔案，以 context-file 能力載入，並依層級／深度規則合併

`src/discovery/agents-md.ts` 會從 `cwd` 往上走祖先目錄，找出獨立的 `AGENTS.md`。對於位在使用者家目錄底下的 repository，它會繼續往上經過外圍的 workspace 目錄，一直到家目錄為止（不含家目錄）。若家目錄底下沒有 repository root，家目錄這個邊界仍然被包含。否則它會停在 repository root；家目錄之外若不知道 repository root，則停在檔案系統的 root。隱藏的 owner 目錄中的檔案會被跳過。

### Skills 與 slash command

- **Skills**：可供模型讀取的知識／工作流內容
- **Slash command**：由使用者觸發的命令入口
- `/skill:<name>` 是注入 skill 文字的便利包裝；它不改變 skill 的探索語意

### Skills 與自訂工具

- **Skills**：透過 prompt context 與 `read` 載入的文件／工作流內容
- **自訂工具**：可由模型呼叫、帶 schema 與執行時期副作用的可執行工具 API

### Skills 與 hooks

- **Skills**：被動的內容
- **Hooks**：事件驅動的執行時期攔截器，可在執行過程中阻擋／修改行為

## 與探索邏輯相關的實務撰寫建議

- 每個 skill 放在自己的目錄：`<skills-root>/<skill-name>/SKILL.md`
- 一律明確寫上 `name` 與 `description` frontmatter
- 被參照的資產放在同一個 skill 目錄底下，並以 `skill://<name>/...` 存取
- 需要巢狀分類（`team/domain/skill`）時，把 `skills.customDirectories` 指到那個巢狀的父目錄；掃描本身仍然是非遞迴的
- 避免跨來源的 skill 重名；依 provider 優先順序，第一個命中者勝出
