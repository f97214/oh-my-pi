# Apply：Spectra TDD

## 目錄

- [選擇](#選擇)
- [既有測試](#既有測試)
- [補建預覽](#補建預覽)
- [套用與失敗回復](#套用與失敗回復)
- [品質關卡](#品質關卡)
- [TDD 證據觀測](#tdd-證據觀測)

## 選擇

完整模式只提供：

- **啟用 Spectra TDD**
- **跳過**

文件模式直接略過本 reference。

已選 Claude 與 Codex 兩個宿主時，初始化命令固定使用：

```text
spectra init <target> --tools claude,codex
```

只選單一宿主時才使用對應單值。Spectra 產生的 `.agents/skills/spectra-*` 與本 Bootstrap 產生的角色 Skills 共存；不得修改或覆寫既有 `.claude/skills/spectra-*`。

`requested` 與 `effective` 必須分開。使用者選啟用只代表 requested；測試可執行、依賴確認、設定寫入與驗證完成後 effective 才可為 true。

## 既有測試

選定 target 已有測試時：

1. 確認 framework、測試位置與正式命令。
2. 只有 Preview 已列出且使用者確認時才執行測試。
3. 測試成功後才可建立或更新 `.spectra.yaml`。

既有 `.spectra.yaml`：

- `tdd: true`：保持，Verify 實際測試狀態。
- `tdd: false`：Preview 精確差異；確認且測試成功後改為 true。
- 無法解析：conflict，不覆蓋。

## 補建預覽

沒有測試時，先依 `policy/test-bootstrap.json` 建立精確預覽：

| 技術棧 | 預設框架 | 必要前置 |
|---|---|---|
| .NET | xUnit | 明確受測 `.csproj` 與 TargetFramework |
| Node | Vitest；只有既有 Jest 證據才沿用 Jest | 明確 workspace 與 package manager |
| Python | pytest | 已偵測的 venv、uv、poetry 或 pipenv |
| Go | `testing` | 明確 module/package |
| Ruby | RSpec | 明確 Bundler project |
| Rust | 內建 test harness | 明確 Cargo package |

預覽必須列出：

- target 與 framework
- 所有新增／修改檔
- 直接依賴的明確版本
- manifest 與 lockfile 影響
- 工作目錄與完整命令
- 最後一道驗證命令

禁止：

- 未限定版本的 latest 安裝
- 全域 `pip install -U`
- 偵測不到 workspace、受測專案或隔離環境時自行選第一個候選

前置不足或使用者拒絕安裝時，設 `test_profile.source: unavailable`、`effective: false`，繼續其他 bootstrap 項目。

## 套用與失敗回復

1. 先記錄所有將修改檔案的 preimage 與 SHA-256。
2. 只執行已確認命令。
3. 最後測試命令實際成功後，才寫 `.spectra.yaml` 的 `tdd: true` 與品質關卡。
4. 任一補建／測試命令失敗：
   - 若檔案仍等於本次寫入 hash，回復本次新增／修改的測試骨架、manifest、lockfile 與 Spectra 設定。
   - 不刪除無法證明由本次建立的 dependency cache、venv 或 build directory。
   - `effective` 保持 false，結果標記 rolled-back 或 failed。
   - 繼續文件與其他治理項目。

## 品質關卡

Spectra TDD 啟用時保留雙層品質注入：

1. 上游 `openspec/config.yaml`：
   - `context` 加入測試品質基準。
   - `rules.tasks` 要求具體測試檔、測試可被正式命令收錄、外部相依隔離方式。
2. 下游宿主治理 Rule（Claude 為 `.claude/rules/testing.md`）：
   - 實作期注入相同的測試發現性、脆弱測試與 mock/fake 邊界。

既有 `context` 有內容時不覆蓋；在 Preview 提供人工合併建議。既有 `rules.tasks` 只追加不重複的條目。

`docs/TESTING.md` 只在 effective 為 true 時記錄 `.spectra.yaml`、測試框架、路徑、命令與 `/spectra-apply` 流程。

跳過時不建立測試骨架、`.spectra.yaml` 或 OpenSpec 品質關卡。

## TDD 證據觀測

僅在 Spectra TDD 為 `effective: true` 時，依 [tdd-observability.md](tdd-observability.md) 提供獨立的 `tdd_observability` 決策。其固定 profile 為：

- `rules-and-hook`
- `change-report`
- `task-summary`
- `red-green-required`

這不是一般治理 Hooks 的子選項：即使使用者跳過一般 Hooks，也要單獨 Preview observer 的宿主 lifecycle、檔案、限制與確認。observer 只觀察已選宿主實際支援的事件；**不執行、不修改測試，也不修改 Spectra 的命令、設定、task 或狀態**。

docs-only、Spectra TDD skip，或 `effective: false` 時，observer 一律不建立。若宿主 Hook schema 不支援某個 lifecycle，該 lifecycle 標記 `unavailable`，不得以未驗證的註冊方式替代。
