# Decide 與 Preview

## 目錄

- [決策順序](#決策順序)
- [模式](#模式)
- [run_config](#run_config)
- [預覽](#預覽)
- [確認閘門](#確認閘門)

## 決策順序

依序取得：

1. target
2. 模式
3. 宿主，預設 Claude＋Codex
4. AI 設定目錄的 Git 策略
5. 完整模式逐角色選 Disabled／Skill／Agent／Both
6. 完整模式的 settings、Rules、Hooks 選項
7. 完整模式的 Spectra TDD
8. 完整模式且 `discovery.stacks` 非空時的 Code Review 規則產出（是／否，預設否）
9. Plugin 建議

所有選項逐項說明「會建立／修改什麼」。超過四個選項時拆成多次互動，不用全包式套餐。

能由 repository 確認的資訊不要詢問；只有產品偏好、衝突或需要外部副作用時才問。

文件模式仍要確認 Git 策略，因為它會決定 `AGENTS.md`／`CLAUDE.md` 如何描述團隊共享或個人設定；但文件模式不得因此修改 `.gitignore` 或建立 `.claude/`、`.agents/`、`.codex/`、`.ai/`。文件中將它明確標成未來新增設定時採用的政策。

## 模式

### 只撰寫文件（預設）

產生或安全更新：

- 根目錄 README
- `AGENTS.md`
- `CLAUDE.md`
- `docs/README.md`
- `docs/ARCHITECTURE.md`
- `docs/FEATURES.md`
- `docs/DEVELOPMENT.md`
- `docs/TESTING.md`

不詢問、不建立 settings、Rules、Hooks、Skills、Agents、Spectra 設定或 Plugin 安裝。四個角色的 `surfaces` 都固定為空陣列。

### 完整 Bootstrap

先完成文件，再依使用者逐項選擇加入 governance 與 Spectra。沒有被選擇的項目不得建立。

### 宿主與角色入口

`decisions.hosts` 是 `claude`、`codex` 的非空子集合，顯示時固定依 Claude、Codex 排序。完整模式逐一決定：

| 選項 | `surfaces` | 行為 |
|---|---|---|
| Disabled | `[]` | 不產生該角色 |
| Skill | `[skill]` | 使用者在目前主線程直接呼叫 |
| Agent | `[agent]` | 主代理以隔離子代理委派 |
| Both | `[skill, agent]` | 同時提供直接入口與隔離入口 |

四個固定角色為 `implementer`、`test-engineer`、`doc-writer`、`git-commit`。Codex Skill 使用 `$name`；Claude Skill 使用 `/name`。自訂 Agent 皆由主代理依名稱委派；Codex Agent 不冒充可用 `$name` 直接啟動。`git-commit` 不論宿主都必須 manual-only。

## `run_config`

使用 `schemas/run-config.schema.json`。檔案全文與可能的敏感內容只存在 Skill 專用暫存 request；對使用者顯示的預覽只能包含摘要與安全差異。

重要狀態：

- `schema_version` 固定為 2。
- `hosts` 表示實際產生入口的宿主。
- `roles.<role>.surfaces` 是已正規化且不重複的入口集合。
- `spectra_tdd.requested` 表示使用者意圖。
- `spectra_tdd.effective` 只有在測試可用且設定成功後才是 true。
- `dependency_execution: pending` 不構成安裝同意。
- `commit_patterns_source` 固定為 `skill-policy`，不依賴某個可選 Hook。
- `code_review_rules` 記在 `decisions`，不放 `derived`——它是使用者的是／否選擇，沒有需要推導的 effective 狀態。它也不構成安裝 `ocr` 的同意。

## 預覽

每個 operation 顯示：

| 欄位 | 說明 |
|---|---|
| action | create、update、skip、conflict、command |
| path | target-relative path |
| reason | 來源證據或使用者決策 |
| before/after | hash 與精簡差異 |
| validation | 寫後如何驗證 |

角色 operation 另顯示 `role`、`host`、`surface` 與 `atomic_group`，例如：

```text
doc-writer
  Codex Skill  create .agents/skills/doc-writer/SKILL.md
  Codex Agent  create .codex/agents/doc-writer.toml
  Claude Skill create .claude/skills/doc-writer/SKILL.md
  Claude Agent create .claude/agents/doc-writer.md
```

同一角色同一 surface 的跨宿主檔案是一個原子群組。任一既有檔缺少相符 managed marker 時，整組 action 都是 `conflict`，Apply 不更新也不建立該組任何檔案；其他不相依群組仍可套用並如實回報 `needs-input`。

不要顯示 secret scanner 的 matched text。若既有檔可能含祕密，預覽只顯示欄位或區塊級摘要。

## 確認閘門

1. **依賴閘門**：只有需要測試補建時出現。列出固定版本、manifest/lockfile、虛擬環境、完整命令與工作目錄。
2. 使用者拒絕後，重算 effective 狀態與 operations。
3. **Apply 閘門**：顯示最終 `plan_sha256` 並取得明確確認。

`plan_sha256` 同時綁定 canonical target、公開 operations、祕密例外與 policy digest。任一檔案、target、policy 或例外清單在預覽後改變時，原確認失效；回到 Discover，產生新的 plan hash，不得跨 target 或自行沿用舊同意。
