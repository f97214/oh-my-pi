---
name: winform-to-quartz-migration
description: 將 WinForm、timer 或 console 批次遷移至 QuartzTemplate，或在該範本新增 Job／Service／Repository 時使用；一般 Quartz.NET 問題不適用。
---

# QuartzTemplate 遷移與新增排程

先搜尋 `AddJobAndTrigger` 與 `DbAccess` 確認環境為此範本；找不到時才詢問範本位置，不把專屬骨架套到其他專案。

## 選擇工作路徑

- **遷移舊程式**：讀 [migration-playbook.md](references/migration-playbook.md)，對照來源觸發時機、資料存取、業務結果與互斥行為；實作時再讀 [template-conventions.md](references/template-conventions.md)。忠實保留行為，只在授權範圍修正明確問題，分段建置與對帳。
- **新增 Job／Service／Repository**：直接讀 [template-conventions.md](references/template-conventions.md)，對照現有 SampleJob、SampleService 與 Repository；不載入舊程式遷移實例。

現有範本檔案是簽章與依賴版本的事實來源，reference 骨架需對照後使用。沿用 `Job → Service → Repository`，不因 skill 的舊範例新增相容性假設。

## 重要操作限制

- cron 明設時區；遷移時查明舊程式使用的時區，不能直接假設 Asia/Taipei。
- MSSQL/API 的 `AppRunType` 與 Oracle 的獨立開關（如 `IsNewOraDb`）都要確認。`_Test` 名稱不證明是測試資料庫；確認實際隔離與授權後才能執行 Job 或連線測試，不把正式連線當測試 fallback。
- 拆 Job 必須保留原本互斥與失敗隔離，避免同步／補跑並行踩到批次資料；有此情況再讀 playbook 的互斥處理。
- 不讀取或輸出祕密真值；沿用範本的設定及加密機制，不將明文密碼放進版控。
- HTTP 需有限逾時；`ExecAPI` 的 GET 空 body 與 `SaveNlog` 全域設定副作用須對照現況。

## 完成條件

完成已授權的程式與設定修改、相關建置與測試。遷移另需在隔離測試區比對筆數與關鍵欄位；無法連線或對帳時明確回報未驗證，繼續完成可獨立驗證的部分。保留原專案對 bin/obj 的版控政策；不自動提交或執行正式排程。
