---
name: handoff
description: 使用者要求換 session 或交接工作時，將目前對話整理成可接續的暫存交接文件。
argument-hint: "[下一個 session 要做什麼？]"
disable-model-invocation: true
license: MIT
metadata:
  adaptedFrom: "https://github.com/mattpocock/skills"
  sourceCommit: "8b36d4fb2635b3c21998dcd8144439c9e5ba7302"
  sourcePaths:
    - skills/productivity/handoff/SKILL.md
---

撰寫一份交接文件，總結目前的對話，讓全新的 agent 能接續這份工作。存到作業系統的暫存目錄——不要存進目前的工作區。

文件中包含一節「建議的 skills」，列出接手的 agent 應該呼叫哪些 skill（例如接續實作用 `/spectra-apply`、需求還沒定用 `/grill`）。

其他 artifact（spec、計畫、ADR、issue、commit、diff）已記載的內容不要重複——以路徑或 URL 參照即可。

遮蔽所有敏感資訊，例如 API key、密碼或個資。

若使用者有帶參數，視為下一個 session 的工作重點描述，據此調整文件內容。
