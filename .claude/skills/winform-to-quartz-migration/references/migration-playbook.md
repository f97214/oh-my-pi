# 遷移 playbook（方法論 + 雷達實例 + 踩坑）

## 目錄
- [來源 → 範本 對應表](#來源--範本-對應表)
- [分階段做法（細節）](#分階段做法細節)
- [雷達實例（Radar_gw → Radar_Quartz）](#雷達實例radar_gw--radar_quartz)
- [踩坑清單](#踩坑清單)
- [對帳怎麼做](#對帳怎麼做)

## 來源 → 範本 對應表
| 來源（WinForm/legacy） | 範本做法 | 備註 |
|---|---|---|
| `Timer` + `if (Hour==.. && Min==..)` 觸發 | `AddJobAndTrigger<T>` cron + `InTimeZone` | 多個時點可用一條 cron（如 `0 40 1,7,13,19 * * ?`） |
| N 個 `BackgroundWorker` 平行 | 單一 Job 內 `Task.WhenAll`，每單位獨立 try/catch | 重現平行＋失敗隔離 |
| EF6 code-first / `SqlQuery<T>` | EF Core POCO + Dapper（`GetAllData<T>`） | 讀 Dapper、寫 BulkExtensions |
| EF6 `repo.Create/Update(list)` | `BulkInsert` / `BulkUpdate`（空集合先擋） | BulkUpdate 依 PK 覆寫整列 |
| Oracle 動態 per-租戶連線 | `new OracleRepository<object>(compcode)` | 多半可直接重用 |
| `HttpWebRequest`（常無 timeout） | `DataHelp.ExecAPI(method,url,param)` | HttpClient 有限逾時;先判 `resp.StartsWith("error:")` |
| `ConfigurationManager.AppSettings[...]` | `appsettings.json` / `AppJsonInfo.Json` | 密碼加密、test/prod 變體 |
| 連線字串密碼明文 | `Encrypt_CFB`/`Decrypt_CFB` + `SQL_DecryptKey` | 勿明文進版控 |
| `DisplayResults()`（WinForms UI） | 移除 UI，改 `DataHelp.SaveNlog` | host 無 UI |
| `logger.Fatal(...)` 當一般訊息 | `SaveNlog(...,"info"/"err",...)` 等級分流 | 修掉等級濫用 |
| 設定表（如 `GWRunTime`）查表決定批次參數 | 照查（Repository 讀該表） | 手動觸發需有對應列 |

## 分階段做法（細節）
**階段0 探索＋映射**：平行探索來源與範本。產出「對應表」＋關鍵決策（忠實度、Job 拆法、平行模型、時區）。若專案已用 Spectra/openspec，建議 `/spectra-discuss` 收斂、`/spectra-propose` 立案（分階段 tasks）。

**階段1 資料層＋設定＋骨架**：建 Context/Repository/介面 + 移植實體;設定移轉（加密、`_Test`、`Program.cs` 初始化 DbInfo）;最小 Job 打通連線。**閘：`dotnet build` 綠 + CrystalQuartz 看得到 + 手動觸發連得上 DB。**

**階段2 業務邏輯**：逐資料集/關注點移植進 Service;`Task.WhenAll` 平行;HTTP 改 `ExecAPI`;log 等級;抽共用 helper。**閘：每資料集 build 綠 + 測試區對帳。**

**階段3 次要 Job＋韌性**：同步/回寫抽成獨立短週期 Job;自我修復（補跑）獨立或併入;失敗隔離。**閘：缺資料情境能自動補齊。**

每階段一個 commit（依專案 commit 慣例處理產物），方便回溯與對帳。

## 雷達實例（Radar_gw → Radar_Quartz）
> 本節引用的檔案路徑（`openspec/...`、`ScheduleTools/...`、`DbAccess/...`）只存在於原遷移的那個 repo。若當前不是該 repo，別花時間找這些檔——把本節當「一次完整遷移長什麼樣」的敘事範例讀即可。

完整實作見歸檔：`openspec/changes/archive/2026-06-03-migrate-radar-gw-to-quartz/`（proposal/design/tasks）＋正式 specs `openspec/specs/radar-batch-collection`、`repair-order-sync`。可直接讀現有檔當範例：`ScheduleTools/Service/RadarBatchService.cs`、`Jobs/RadarBatchJob.cs`、`DbAccess/MsSQL/Repository/TBC_MapRepository.cs`、`DbAccess/MsSQL/TBC_Map/*`。

來源 `NodeNoTimeoutGET`（WinForm）的對應：
- **timer 10 分 + 四時間窗（01:40/07:40/13:40/19:40）** → `RadarBatchJob` cron `0 40 1,7,13,19 * * ?`（Asia/Taipei）。批次參數（ImportBatch/DataTime/日期/批號）由觸發時間 + `GWRunTime` 表推導（`RadarBatchContext` / `DeriveContext`）。
- **5 個 BackgroundWorker（CompCode 1–5＝NTY/BEST/SH/CY/CCTV）** → 單 Job 內 `Task.WhenAll`，每家獨立 try/catch。
- **資料集範圍**：T3 collection/detail 每窗都取;Bonded/T4/GPON power/CM-quality 僅 `ImportBatch=1`（DataTime=00:00）窗取——忠實保留。
- **T3 collection**：API 取數 → `Percentage`/`CumAvg` → `HealthLevel` 查表給 `Score` → 每節點 POST 查 HD 工單 → `HelpDeskStatus`(2/1/0) → `BulkInsert`。
- **detail（T3/T4/Bonded）**：取明細 → 每 500 筆組 IN 向 Oracle 查 SO004/SO004D/SO001/SO007/SO008 補客戶類別/工單（抽成共用 `CollectCmRepairOrders` + `ResolveCustomerInfo`）。
- **GPON**：逐 BuildNo 以 `gponinfo/buildinfo`（OLT/vhub，含 `1_split→OneStID` 置換）+ `GetGponMDUDeviceList`（NODENO/ADDRESS/MDUNAME）補充。
- **約修同步**（原本每 tick 開頭做）→ 獨立 `ReserveRepairSyncJob`（每 10 分）：取工單單號 + 完修結案回寫。
- **自我修復**（原非批次窗 tick）→ 獨立 `SelfHealingJob`（每 10 分）：依時間推得應完成的窗 → 各家查筆數 → 低於門檻或缺表 → 刪除重跑該家。門檻沿用原寫死值（1/2/3/4/5 = 1003/436/114/126/587）。

## 踩坑清單
- **bin/obj 納版控**：本範本 repo 把建置產物納入版控。commit 前先確認該專案慣例——是要排除產物，還是連產物一起 commit（兩種需求都遇過，依當下指示）。
- **勿擴充 legacy .NET FW 專案**：.NET 8 host 跨 runtime 參考 .NET Framework 專案（如 `Applications.Models`/EF6）只是相容、易碎。新資料層一律走 `DbAccess`（EF Core）;該 legacy 專案若已無用，連帶移除（含其唯一使用者，如某 sample controller）+ 清 `.csproj` ProjectReference + 兩個 `.sln` 專案項。
- **`ExecAPI` 的 GET 帶空 body**：`HttpClient` 送 GET 時會附空 `StringContent`;若來源 API 拒絕 GET 帶 body，需加一條不帶 body 的 GET 路徑。
- **`SaveNlog` 重設全域 NLog**：實例 `SaveNlog` 每次 `NLog.LogManager.Configuration = ...`;同 Job 名多執行緒併發呼叫雖大致無害（同設定）但會反覆重配置。高併發/多 Job 名時注意。
- **手動觸發批次需查得到設定列**：批次 Job 一觸發先算 `RunTime`（現在時間取到十分位）再查設定表（如 `GWRunTime`）;對不上就略過。離窗測試要先在表內暫加對應「現在」的列（測完刪）。
- **cron 時區**：舊碼用 `DateTime.Now`＝伺服器本地時間，**不是 UTC**;cron 用 `InTimeZone` 明設（如 Asia/Taipei），別依賴主機預設。
- **兩個 test/prod 開關**：`AppRunType`（MSSQL/API）與 Oracle 的獨立開關（如 `IsNewOraDb`）要**都**切到測試才算測試區。
- **`_Test` 連線若沒有測試 DB**：別把 `_Test` 直接填正式值就以為安全——那其實還是寫正式。沒測試 DB 時，要嘛建影子 DB，要嘛停舊系統後在正式跑單一切點。
- **純量查詢**：`GetData<T>` 限 `T:class`，`COUNT(*)` 要用 `ExecuteScalar<int>`。
- **數值轉換**：來源常用 `Convert.ToDouble(item.xxx)`（字串/可空）;移植時注意 null/空字串與除以零（忠實保留行為，或加防呆並註明）。

- **拆 Job 會弄丟原本的互斥**：原 WinForm 在同一 timer tick 內「批次 vs 自我修復」是互斥的；拆成獨立 Quartz Job 後兩者可並行，自我修復可能在批次窗執行中對「同一窗」做刪除+重抓而與批次互踩、刪到剛寫的資料。對策（批次優先）：由批次 Job 主導——開始時 `PauseTrigger` + `Interrupt` 其他協調 Job、`finally` `ResumeTrigger`；被協調的 Job 用 `IJobExecutionContext.CancellationToken` 在**安全點**（資料一致邊界，如每家 CompCode 之間）停止，**不在「刪除→重抓」中途停**；主機啟動時對這些 trigger `ResumeTrigger` 以防上次當機留下 paused。`Interrupt` 只影響本節點，`Pause/Resume` 經持久化 store 為叢集層級。

## 對帳怎麼做
資料是時間點相依、且常無獨立測試 DB，難新舊並行精確 diff。務實做法：
1. 設好 test/prod 開關（兩個都切測試;Oracle 別漏）。
2. 在對應批次窗觸發（或暫加設定列），看 `Logs/Info` 各表「新增資料成功，共 N 筆」、`Logs/Error` 乾淨。
3. 依 `BatchNumber`（`{單位}-{yyyyMMdd}`）查各目標表筆數，落在歷史日量合理範圍;抽樣比對關鍵欄位（評分、狀態、補充欄位）與舊系統一致。
4. 自我修復：人為刪少某家某批資料，看 Job 是否偵測並重跑補齊。
