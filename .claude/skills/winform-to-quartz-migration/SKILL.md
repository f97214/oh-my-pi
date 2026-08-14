---
name: winform-to-quartz-migration
description: >-
  把舊的 .NET Framework WinForm（或其他 timer/console 常駐）批次、gateway、排程程式遷移／改寫進「本 QuartzTemplate（.NET 8 Quartz.NET 排程範本，專案 ScheduleTools/QuartzTemplate + DbAccess + DataTools）」，或要在本範本裡新增全新的 Job/Service/Repository（照範本慣例寫）時使用。當使用者想把某支舊程式「轉成 Quartz」「搬進範本」「WinForm 轉排程」「timer 改 cron」「BackgroundWorker 改寫」「改成排程服務」「在範本加一支新 Job／新排程」，或提到 NodeNoTimeoutGET / Radar_gw 之類舊 GW 程式要併進範本——即使沒明講「QuartzTemplate」也務必使用本技能。它提供：探索來源→映射觸發模型→資料層改寫(EF Core+Dapper)→業務邏輯移植(Job→Service→Repository)→設定/加密遷移→平行化/HTTP逾時/log 分流→次要 Job（同步、自我修復）→分階段驗證對帳的完整方法論與範本慣例。SKIP：一般 Quartz.NET 用法/觀念問題、與本範本無關的排程專案、單純同 stack 版本升級而不搬進範本（改用 modernize-uplift）。
---

# WinForm → QuartzTemplate 遷移

把 legacy WinForm／timer／console 批次程式，**忠實**遷移進本範本（.NET 8 + Quartz.NET）。這不是貼上即可——來源與範本通常跨越多個技術邊界（.NET Framework→.NET 8、timer→cron、BackgroundWorker→Task.WhenAll、EF6/ADO→EF Core/Dapper、App.config→appsettings/AppJsonInfo），要逐步映射、逐步驗證。

核心理念：**忠實移植行為**（與舊系統對帳一致）＋**只修明確會出事的問題**（如無逾時 HTTP、log 等級濫用），其餘照舊。**分階段、每段都 build 綠、能對帳**，不要一口氣產出無法驗證的大塊程式。

另一種情境：**沒有舊程式，只是要在範本裡新增全新的 Job/Service/Repository**——這時跳過下面的遷移方法論，直接讀 `references/template-conventions.md` 照慣例與骨架寫即可（踩坑清單仍適用）。

## 前置檢查

開工前先確認當前環境真的有這個範本：搜尋 `AddJobAndTrigger` 與 `DbAccess` 專案。找不到就**先問使用者範本在哪**（可能在別的 repo/路徑），不要拿本技能的骨架在不相干的專案上硬套——慣例與簽章都是這個範本特有的。

## 先讀懂目標範本

範本三個專案（名稱可能因專案而異，但結構一致）：
- **QuartzTemplate（資料夾常叫 ScheduleTools）**：ASP.NET Core + Quartz host。`Program.cs` 用 `AddJobAndTrigger<TJob>(...)` 註冊 Job；CrystalQuartz 監控面板在 `/quartz`；Quartz 用 SQL Server 持久化。
- **DbAccess**：資料層。MSSQL 走 **EF Core 9 + Dapper + EFCore.BulkExtensions**；Oracle 走 `OracleRepository<T>(compcode)` 多租戶。
- **DataTools**：共用工具 `DataHelp`（`ExecAPI`、`Encrypt/Decrypt_CFB`、`SaveNlog`）、`AppInfo`、`AppJsonInfo`。

慣例鏈：**`Job → Service → Repository`**。Job 很薄（防重入＋記 log＋委派），業務邏輯在 Service，DB 存取在 Repository。**開始遷移前，先讀範本既有的 `SampleJob`/`SampleService` 與一個現成 Repository**，照著寫。詳細可貼上的骨架見 `references/template-conventions.md`。

## 遷移方法論（分階段）

若專案已使用 Spectra/openspec，強烈建議用 **Spectra 驅動**（`/spectra-discuss → /spectra-propose → /spectra-apply → /spectra-archive`），把方向、決策、任務固化成 artifacts，分階段 apply；沒有的話照下面的階段順序做即可。

### 階段 0：探索 + 映射（先想清楚再動）
平行探索「來源程式」與「範本」，把來源的每個面向映射到範本做法：

| 來源（WinForm/legacy） | 範本（QuartzTemplate） |
|---|---|
| `System.Timers.Timer` + 時間判斷觸發 | `AddJobAndTrigger<T>` 的 **cron**（含時區） |
| 多個 `BackgroundWorker` 平行 | 單一 Job 內 **`Task.WhenAll`** |
| EF6 / ADO.NET / 動態連線 | **EF Core + Dapper**（仿 DbAccess 既有 Repository） |
| Oracle 動態 per-租戶連線 | 既有 **`OracleRepository<T>(compcode)`**（多半可直接重用） |
| `HttpWebRequest`（常無逾時） | **`DataHelp.ExecAPI`**（HttpClient，有限逾時） |
| `App.config` appSettings | **`appsettings.json` + `AppJsonInfo.Json`**（加密、test/prod 開關） |
| WinForms UI（`DisplayResults`）、`logger.Fatal` 濫用 | 丟掉 UI；一律 `DataHelp.SaveNlog(seqNo,job,level,obj)`，等級分流 |

（此表為精簡版；完整對應表含備註見 `references/migration-playbook.md`。）

先確認幾個常見決策：忠實度（建議「移植＋修關鍵問題」）、Job 怎麼拆（建議依職責拆多個 cron Job）、多租戶/多分區怎麼平行（建議單 Job 內 `Task.WhenAll`）、cron 時區（用 `DateTime.Now` 的舊碼＝伺服器本地，需明設，例如 Asia/Taipei）。

### 階段 1：資料層 + 設定 + 排程骨架（先打通）
- 仿範本既有 MSSQL Repository，建 `<DB>Context` + `<DB>Repository<TEntity>` + 介面；把來源 EF6 實體移植成 **EF Core POCO**（保留 DataAnnotations，字串用 `string?`）。
- 設定移轉：在 `appsettings.json` 加 DB 連線（密碼用 `Encrypt_CFB` 加密、加 `_Test` 變體）、`AppJsonInfo.Json` 加 API URL；`Program.cs` 初始化靜態 `*_DbInfo`。
- 建最小 Job（只打通 DB/API 連線＋log），用 `AddJobAndTrigger` 掛 cron（**指定時區**）。
- **驗證**：`dotnet build` 全綠；CrystalQuartz 看得到 Job；手動觸發能連到 DB 並記 log。

### 階段 2：業務邏輯移植（主體）
- 把來源主流程**逐「資料集 / 關注點」**移植進 Service（一次一塊、各自 build＋對帳，不要一次全上）。
- 多租戶/多分區用 `Task.WhenAll` 平行，**每家獨立 try/catch**（單家失敗不影響其他家）。
- 對外 HTTP 一律改 `DataHelp.ExecAPI`（有限逾時，修掉無逾時卡死）。
- log 等級正確：成功 `info`、錯誤 `err`（→ Error 目錄），不要一律 fatal。
- 抽出重複邏輯為共用 helper（例如多個 detail 共用的「查 Oracle 補資料」）。

### 階段 3：次要 Job + 韌性
- 把來源在主迴圈順帶做的事（狀態同步、回寫…）抽成**獨立短週期 cron Job**。
- 若來源有「自我修復／補跑」機制，移植為獨立 Job 或併入批次後檢查；門檻等魔術數字依決策保留或外部化。
- 失敗隔離貫穿各層。

### 每階段都要
`dotnet build` 綠 → 在**測試區**（設好 test/prod 開關）跑一輪 → 與舊系統**對帳**（筆數＋抽樣欄位）。

## 慣例 cheat-sheet（細節見 references/template-conventions.md）
- **Job**：`[DisallowConcurrentExecution]` + `Mutex(jobName)` + `seqNo="0_{MMddHHmmssffff}"` + `SaveNlog` 記 開始/結束/例外 + 委派 Service + `mutex.Dispose()` + `GC.Collect()`。
- **Repository**：建構式依 `AppInfo.AppRunType`（"0"=測試）選連線、`DataHelp.Decrypt_CFB(pwd, AppInfo.SQL_DecryptKey)` 解密、`DbContextOptions` 外注；查詢用 Dapper（`GetData<T>`/`GetAllData<T>`/`ExecuteScalar<T>`），寫入用 `BulkInsert/BulkUpdate`，原生用 `ExecuteSql`。
- **設定兩個 test/prod 開關**：`AppRunType`（管 MSSQL/API；在 `AppJsonInfo.Json`）與 **Oracle 另有獨立開關**（如 `IsNewOraDb`，在 `appsettings.json`）——**兩個都要切到測試**才算進測試區。
- **加密**：連線密碼一律 `Encrypt_CFB`/`Decrypt_CFB` + `SQL_DecryptKey`，勿明文進版控。

## 踩坑（細節見 references/migration-playbook.md）
- repo 可能把 **bin/obj 納入版控**——commit 前先確認該專案慣例（排除或納入產物）。
- **勿在 .NET Framework 的 legacy 專案上擴充新資料層**（.NET 8 host 跨 runtime 參考它只是相容、易碎）；必要時連帶移除。
- `ExecAPI` 送 GET 會帶一個空 body；若來源 API 拒絕 GET 帶 body，需改走不帶 body 的路徑。
- `SaveNlog` 實例方法每次會重設全域 NLog 設定——同 Job 名高併發下注意。
- 手動觸發批次型 Job 前，確認設定表（如 `GWRunTime`）有對應「現在」的列，否則會略過。
- cron 一定**明設時區**，不要依賴主機預設。
- **拆 Job 會弄丟原本的互斥**：來源在同一 timer tick 內互斥的事（如批次 vs 自我修復），拆成獨立 Job 後可能並行互踩、刪到剛寫的資料——對策（Pause/Interrupt 協調）見 playbook。
- **`_Test` 沒有真的測試 DB 時，填正式值＝其實還在寫正式**，別誤以為切了開關就安全——處理方式見 playbook。

## 讀檔指引
- 要寫 Job/Service/Repository/實體/設定/Program.cs 的具體程式 → 讀 **`references/template-conventions.md`**（可貼上的骨架與正確簽章）。
- 要規劃整個遷移、看「來源→範本」對應、看雷達實例與踩坑 → 讀 **`references/migration-playbook.md`**。
- 永遠以**範本中現有的對應檔**為最終事實來源（簽章可能隨版本微調）；本技能的骨架是起點，落地前對照現況。
