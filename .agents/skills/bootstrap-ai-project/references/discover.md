# Discover：唯讀盤點

## 目錄

- [目標選擇](#目標選擇)
- [來源清單](#來源清單)
- [技術棧與測試](#技術棧與測試)
- [既有產物](#既有產物)
- [證據規則](#證據規則)

## 目標選擇

1. 先解析使用者指定路徑，再找 Git root。
2. 單一 repository 內若有多個 manifest、solution、workspace 或可獨立部署單元，列出候選 target：
   - 相對路徑
   - manifest／solution
   - 推測技術棧
   - 既有測試證據
3. 未取得選擇前不得進入 Decide。不要使用「第一個非測試專案」之類的隱含 fallback。
4. 選定後，所有掃描、文件、Hooks、測試與命令的工作目錄都限制在該 target。

## 來源清單

使用 `policy/source-inventory.json`。不得讓模型遞迴讀取整個 repository。

- 排除 dependency、build、coverage、generated、binary、minified 與大型檔。
- 不跟隨 symlink；指向 target 外部的 symlink 只記錄排除原因。
- 不讀 `.env`、私鑰、credentials 或已知 secret filename。
- `.env.example`、`.env.sample` 由 bundled CLI 解析，輸出只包含合法鍵名。
- 優先讀入口、manifest、設定 schema、路由、資料模型、外部整合與既有測試。

每個 inventory item 記錄：

```text
path
kind
size
sha256
included | excluded
reason
```

## 技術棧與測試

技術棧至少以兩種證據交叉確認，例如 manifest 加入口副檔名。僅有副檔名時標記「候選」。

測試以 target 為單位建立 profiles，不得使用全 repository 單一布林：

```text
framework
project_or_directory
manifest
command
source = existing | planned-bootstrap | bootstrapped | unavailable
evidence[]
```

偵測 `.NET`、Node、Python、Go、Ruby、Rust 的既有測試框架與可執行命令；未執行命令前不得宣稱測試可用。

## 既有產物

盤點但不修改：

- README、AGENTS.md、CLAUDE.md、docs
- `docs/adr/`（既有 ADR 編號、標題與狀態）與 `CONTEXT.md`；兩者決定 ADR Rule 與文件清單是否適用
- `.agents/skills/`、`.claude/skills/`、`.claude/agents/`、`.codex/agents/` 與既有角色 managed markers
- `.claude/settings*.json`、`.codex/hooks.json`、`.ai/bootstrap-ai-project/`、rules 與 hooks
- `.gitignore` 舊 managed marker
- `.spectra.yaml` 與 `openspec/config.yaml`
- `.github/copilot-instructions.md`

解析 `.spectra.yaml` 時只正規化可確認的布林值。無法解析則標記 conflict，不猜測或覆蓋。

舊版或使用者客製內容一律保持原狀；只在 Preview 說明新版不再產生的項目，不要主動列舉或宣傳舊工作流。

## 證據規則

每個重要結論存為：

```json
{
  "claim": "專案使用 PostgreSQL",
  "status": "confirmed",
  "sources": ["src/config/database.ts", "package.json"]
}
```

- `confirmed`：有可引用來源。
- `unconfirmed`：合理但證據不足；文件必須顯示「未確認」。
- `conflict`：來源互相矛盾；Preview 要求人工選擇。

不要引用 dependency/build 產物作為架構事實來源。
