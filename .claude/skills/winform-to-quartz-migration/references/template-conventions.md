# QuartzTemplate 慣例與骨架

可貼上的骨架。**落地前對照範本現有檔**（`SampleJob`、既有 Repository、`DataTools/DataHelp.cs`、`Program.cs`），簽章可能隨版本微調。

## 目錄
- [Job 骨架](#job-骨架)
- [Service 骨架](#service-骨架)
- [Repository 骨架（MSSQL：EF Core + Dapper）](#repository-骨架mssqlef-core--dapper)
- [Oracle Repository（多租戶，重用）](#oracle-repository多租戶重用)
- [實體 POCO + DbContext](#實體-poco--dbcontext)
- [DataHelp 工具簽章](#datahelp-工具簽章)
- [設定與 test/prod 開關](#設定與-testprod-開關)
- [Program.cs 註冊](#programcs-註冊)
- [NLog 等級分流](#nlog-等級分流)

## Job 骨架
薄 Job：防重入 + 記 log + 委派 Service。`_JobName` 要全程一致（Mutex 與 log 都用它）。

```csharp
using DataTools;
using Quartz;
using QuartzTemplate.Service;

namespace QuartzTemplate.Jobs
{
    [DisallowConcurrentExecution]
    public class XxxJob : IJob
    {
        public Task Execute(IJobExecutionContext context)
        {
            bool isFirstOpen = false;
            string _JobName = "XxxJob";
            string seqNo = $"0_{DateTime.Now:MMddHHmmssffff}";
            var mutex = new System.Threading.Mutex(false, _JobName, out isFirstOpen);

            if (isFirstOpen)
            {
                try
                {
                    new DataHelp().SaveNlog(seqNo, _JobName, "info", new { Msg = "開始" });
                    new XxxService().DoWork(seqNo, _JobName);
                }
                catch (Exception ex)
                {
                    new DataHelp().SaveNlog(seqNo, _JobName, "err", new { Msg = ex.Message });
                }
                finally
                {
                    new DataHelp().SaveNlog(seqNo, _JobName, "info", new { Msg = "結束" });
                }
            }

            mutex.Dispose();
            GC.Collect();
            return Task.CompletedTask;
        }
    }
}
```

## Service 骨架
業務邏輯在這。接 `(seqNo, jobName)` 供 log 串接；多租戶/多分區用 `Task.WhenAll` 平行、每單位獨立 try/catch。

```csharp
public class XxxService
{
    public void DoWork(string seqNo, string jobName)
    {
        var log = new DataHelp();
        // 多單位平行；單一失敗不影響其他
        var units = new[] { "1", "2", "3" };
        var tasks = units.Select(u => Task.Run(() =>
        {
            try { CollectOne(u, seqNo, jobName, log); }
            catch (Exception ex) { log.SaveNlog(seqNo, jobName, "err", new { Msg = $"unit={u} 失敗", Err = ex.Message }); }
        })).ToArray();
        Task.WhenAll(tasks).GetAwaiter().GetResult();
    }

    private void CollectOne(string unit, string seqNo, string jobName, DataHelp log)
    {
        using (var repo = new XxxRepository<SomeEntity>())
        {
            // repo.GetAllData<T>(sql, pa) / repo.BulkInsert(rows) ...
        }
    }
}
```

## Repository 骨架（MSSQL：EF Core + Dapper）
建構式依 `AppInfo.AppRunType` 選 test/prod、解密密碼、外注 `DbContextOptions`。讀走 Dapper、寫走 BulkExtensions。

```csharp
using System.Linq.Expressions;
using Dapper;
using Microsoft.Data.SqlClient;
using Microsoft.EntityFrameworkCore;
using DataTools;
using DataTools.Model;          // AppInfo
using DbAccess.Models;          // *_DbInfo
using EFCore.BulkExtensions;

public class XxxRepository<TEntity> : IXxxRepository<TEntity> where TEntity : class
{
    public XxxContext Db { get; set; }

    public XxxRepository()
    {
        bool isTest = string.Equals(AppInfo.AppRunType, "0");
        var sb = new SqlConnectionStringBuilder
        {
            ConnectTimeout = 1200, PersistSecurityInfo = true,
            ApplicationName = "EntityFramework", TrustServerCertificate = true,
            DataSource      = isTest ? Xxx_DbInfo.DbIp_Test   : Xxx_DbInfo.DbIp,
            InitialCatalog  = isTest ? Xxx_DbInfo.DbName_Test : Xxx_DbInfo.DbName,
            UserID          = isTest ? Xxx_DbInfo.UserName_Test : Xxx_DbInfo.UserName,
            Password = DataHelp.Decrypt_CFB(isTest ? Xxx_DbInfo.UserPwd_Test : Xxx_DbInfo.UserPwd, AppInfo.SQL_DecryptKey)
        };
        var options = new DbContextOptionsBuilder<XxxContext>().UseSqlServer(sb.ConnectionString).Options;
        Db = new XxxContext(options);
    }

    public DateTime GetServerTime() { using var c = Db.Database.GetDbConnection(); c.Open(); return c.QueryFirst<DateTime>("SELECT GETDATE()"); }
    public T GetData<T>(string sql, DynamicParameters? pa) where T : class { using var c = Db.Database.GetDbConnection(); c.Open(); return c.Query<T>(sql, pa ?? new()).FirstOrDefault(); }
    public List<T> GetAllData<T>(string sql, DynamicParameters? pa) where T : class { using var c = Db.Database.GetDbConnection(); c.Open(); return c.Query<T>(sql, pa ?? new()).ToList(); }
    public T ExecuteScalar<T>(string sql, DynamicParameters? pa = null) { using var c = Db.Database.GetDbConnection(); c.Open(); return c.ExecuteScalar<T>(sql, pa ?? new()); }   // COUNT 等（T 不限 class）
    public int ExecuteSql(string sql, DynamicParameters? pa = null) { using var c = Db.Database.GetDbConnection(); c.Open(); return c.Execute(sql, pa ?? new()); }
    public List<TEntity> GetAll(Expression<Func<TEntity, bool>> p) => Db.Set<TEntity>().AsNoTracking().Where(p).ToList();
    public bool BulkInsert(List<TEntity> rows) { using var t = Db.Database.BeginTransaction(); Db.BulkInsert(rows); t.Commit(); return true; }
    public bool BulkUpdate(List<TEntity> rows) { using var t = Db.Database.BeginTransaction(); Db.BulkUpdate(rows); t.Commit(); return true; }
    public void SaveChanges() => Db.SaveChanges();
    public void Dispose() { Db?.Dispose(); GC.SuppressFinalize(this); }
}
```
注意：`GetData<T>/GetAllData<T>` 有 `where T : class` 限制——**`COUNT(*)` 等純量值要用 `ExecuteScalar<int>`**（無此限制）。

## Oracle Repository（多租戶，重用）
範本通常已有 `OracleRepository<TEntity>(string compcode)`，依 compcode 切租戶連線（test/prod 由 `IsNewOraDb` 控制）。**直接重用**：
```csharp
using (var ora = new OracleRepository<object>(compcode))   // TEntity 任意（泛型方法不依賴它）
{
    var rows = ora.GetAllData<SomeDto>(sql, new DynamicParameters());
}
```
注意 Oracle 端 test/prod 開關**獨立**於 `AppRunType`（見下）。

## 實體 POCO + DbContext
EF6 實體移植成 EF Core POCO：保留 `[Table]/[Key]/[StringLength]/[Column]`，移除 `System.Data.Entity.*`，字串用 `string?`。
```csharp
[Table("Xxx")]
public partial class Xxx
{
    [Key] public long Sn { get; set; }
    [StringLength(20)] public string? Node_No { get; set; }
    [Column(TypeName = "date")] public DateTime? Date { get; set; }
    public int? Count { get; set; }
}
```
DbContext：options 一律外注，`OnConfiguring` 未設定時擲例外（避免誤用預設連線）。
```csharp
public partial class XxxContext : DbContext
{
    public XxxContext() { }
    public XxxContext(DbContextOptions<XxxContext> options) : base(options) { }
    public virtual DbSet<Xxx> Xxx { get; set; }
    protected override void OnConfiguring(DbContextOptionsBuilder o)
    { if (!o.IsConfigured) throw new InvalidOperationException("DbContext options must be provided externally."); }
}
```

## DataHelp 工具簽章
- `static string ExecAPI(string method, string url, string param)`：HttpClient（**有限逾時**，取代無逾時 HttpWebRequest）。回傳字串;失敗回 `"error:..."`——呼叫端要先判 `resp.StartsWith("error:")`。另有帶帳密 / 帶 contentType 的多載。
- `static string Encrypt_CFB(string plain, string key)` / `static string Decrypt_CFB(string cipher, string key)`：AES-CFB；key 用 `AppInfo.SQL_DecryptKey`。
- `void SaveNlog(string seqNo, string jobName, string saveType, dynamic para)`（實例）：`saveType=="err"`→`logger.Error`（→ Logs/Error），其他→`logger.Info`（→ Logs/Info）。另有 `static SaveNlog(string saveType, dynamic para)`。
- `AppInfo`（`DataTools.Model`）：`static AppRunType`（"0"=測試）、`static SQL_DecryptKey`。
- `AppJsonInfo`（`QuartzTemplate.UserDefind.AppJsonInfo`）：各 API URL 的 static 屬性（+ `_Test`）。

## 設定與 test/prod 開關
- `appsettings.json`：`SQL_DecryptKey`、各 DB `*_IP/*_DbName/*_User/*_Pwd`（密碼為 `Encrypt_CFB` 密文）+ `_Test` 變體、Quartz 持久化連線、Oracle 區（含 **Oracle 自己的 test/prod 開關，如 `IsNewOraDb`**）。
- `AppJsonInfo.Json`（複製到輸出目錄）：`AppRunType`（"0"=測試 / 其他=正式）、對外 API URL（+ `_Test`）。新增欄位時三處同步：`AppJsonInfoModel`、`AppJsonInfo`(static)、`Program.cs` 的指派。
- **兩個開關**：`AppRunType` 管 MSSQL/API；Oracle 另有獨立開關。要進測試區，兩個都要切 "0"/測試。

## Program.cs 註冊
```csharp
// 靜態 DbInfo 初始化（每顆 DB）
Xxx_DbInfo.DbIp = builder.Configuration["Xxx_IP"];
// ... 其餘欄位 + _Test ...

builder.Services.AddQuartz(q =>
{
    q.UseJobFactory<MicrosoftDependencyInjectionJobFactory>();
    q.UsePersistentStore(s => { s.UseSqlServer(/* QRTZ_ */); s.UseClustering(); s.UseJsonSerializer(); });

    void AddJobAndTrigger<TJob>(string jobName, string triggerName, string cron,
        string jobGroup, string triggerGroup, int startAfterSeconds = 30, TimeZoneInfo? tz = null) where TJob : IJob
    {
        var key = new JobKey(jobName, jobGroup);
        q.AddJob<TJob>(o => o.WithIdentity(key));
        q.AddTrigger(t => t.ForJob(key).WithIdentity(triggerName, triggerGroup)
            .StartAt(DateBuilder.FutureDate(startAfterSeconds, IntervalUnit.Second))
            .WithCronSchedule(cron, x => { x.WithMisfireHandlingInstructionIgnoreMisfires(); if (tz != null) x.InTimeZone(tz); }));
    }

    // 明設時區（跨平台容錯）
    TimeZoneInfo taipei;
    try { taipei = TimeZoneInfo.FindSystemTimeZoneById("Asia/Taipei"); }
    catch (TimeZoneNotFoundException) { taipei = TimeZoneInfo.FindSystemTimeZoneById("Taipei Standard Time"); }

    AddJobAndTrigger<XxxBatchJob>("XxxBatchJob", "XxxBatchJob_trigger", "0 40 1,7,13,19 * * ?", "群組", "觸發群組", tz: taipei);
    AddJobAndTrigger<XxxSyncJob>("XxxSyncJob", "XxxSyncJob_trigger", "0 0/10 * * * ?", "群組", "觸發群組");
});
builder.Services.AddQuartzHostedService(o => o.WaitForJobsToComplete = true);
```

## NLog 等級分流
`NLog.config` 將 Info→`Logs/Info/`、Error→`Logs/Error/`、Fatal→`Logs/Fatal/`。所以用 `SaveNlog(...,"info"/"err",...)` 就會落到正確目錄——**避免來源那種「全部 logger.Fatal」**。
