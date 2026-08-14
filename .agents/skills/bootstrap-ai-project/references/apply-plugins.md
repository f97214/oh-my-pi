# Plugin 建議

本 reference 只在完整模式且使用者要求 Plugin 建議時讀取。

## 動態盤點

1. 執行 `claude plugin list --available --json`。
2. 驗證 JSON；不可用或格式未知時停止自動推薦，改提示使用 `/plugin` 手動瀏覽。
3. 依 selected target 的技術棧、既有 agent 與使用者需求篩選候選。
4. 對候選執行 `claude plugin details <name>`，只引用實際回傳的元件、需求與可用 metadata。
5. LSP 類 Plugin 必須顯示 BYO language server binary 前置與驗證命令。
6. 與既有 Agents／Hooks 功能重疊時明確提示，不宣稱一定衝突。

## 輸出

逐項顯示：

- Plugin 名稱與來源
- 推薦理由與 repository 證據
- 元件與前置條件
- 可取得時的 context cost／metadata
- 建議 scope
- 精確安裝與驗證命令

CLI 支援非互動安裝，但本 Skill 基於安全政策不代為安裝。不要使用硬編碼清單、固定數量、Claude 版本門檻或「AI 無法安裝」等說法。

只輸出 `claude plugin install <plugin> --scope <scope>` 建議，不執行命令。若 CLI 只提供 `/plugin install`，據實呈現，不猜測旗標。
