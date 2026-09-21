---
name: bootstrap-ai-project
description: Claude Code 專屬的 Bootstrap 薄入口；將 target 參數交給 repository canonical skill，建立 Claude／Codex 雙入口、文件與可選治理。使用者明確要求初始化或 bootstrap 專案時使用。
argument-hint: "[target-path]"
disable-model-invocation: true
---

# Bootstrap AI Project（Claude 入口）

這是 Claude Code 的 `/bootstrap-ai-project` 薄入口。Canonical workflow、references、renderer、schemas 與 templates 只維護在 [`.agents/skills/bootstrap-ai-project/SKILL.md`](../../../.agents/skills/bootstrap-ai-project/SKILL.md)。

1. 將 `$ARGUMENTS` 視為候選 target；空值時以目前 repository 為候選。
2. 完整讀取 canonical `SKILL.md`，再依它的 progressive disclosure 規則讀取 references。
3. 所有相對路徑以 canonical skill 目錄為基準，不以本薄入口目錄為基準。
4. 嚴格執行 canonical 的 `Discover → Decide → Preview → Apply → Verify`，不得在此入口另建一套行為。
