# 掃描模式 sink patterns 參考

各語言的危險 sink 與搜尋方向。這些是**代表性 pattern，非窮舉**——grep 命中只代表「值得看」，必須回到 SKILL.md Step 2 確認「可控輸入是否真的到得了這個 sink」才算數。

依專案主要語言讀對應章節即可，不需全部讀完。

---

## C#/.NET

| 弱點 | 搜尋方向（範例） | 確認方向 |
| --- | --- | --- |
| SQL Injection (CWE-89) | 字串拼接/內插進 SQL：`new SqlCommand("... " + var)`、`$"SELECT ... {var}"`、`string.Format` 組 SQL 後丟 `ExecuteReader/ExecuteNonQuery`；Dapper/EF 的 `FromSqlRaw`、`ExecuteSqlRaw` 吃拼接字串 | 拼進去的變數是否來自 request、設定檔或 DB 中使用者可寫的欄位；已是 `SqlParameter`/內插版 `FromSqlInterpolated` 則多半安全 |
| Command Injection (CWE-78) | `Process.Start(...)`、`ProcessStartInfo` 的 `FileName`/`Arguments` 含變數，尤其 `cmd.exe /c` + 拼接 | Arguments 是否含使用者可控字串；固定指令+固定參數不算 |
| Path Traversal (CWE-22) | `Path.Combine(base, userInput)` 未驗證、`Server.MapPath(userInput)`、`File.ReadAllText/WriteAllText` 吃可控路徑 | 是否有 `Path.GetFullPath` 後比對根目錄的檢查；注意 `Path.Combine` 遇絕對路徑會**整段取代** base |
| 不安全反序列化 (CWE-502) | `BinaryFormatter`、`SoapFormatter`、`NetDataContractSerializer`、`LosFormatter`、`JavaScriptSerializer` + `SimpleTypeResolver`、Json.NET `TypeNameHandling` 非 `None` | 反序列化的資料來源是否跨信任邊界（HTTP body、檔案上傳、MQ）；`BinaryFormatter` 在 .NET 8 已標記淘汰，一律建議換掉 |
| XSS (CWE-79) | `Response.Write(var)`、Razor 中 `@Html.Raw(var)`、`HtmlString`、WebForms `<%= var %>` | Razor 的 `@var` 預設會編碼，`Html.Raw` 才是重點；WebForms 要看 `ValidateRequest` 是否被關 |
| SSRF / Open Redirect (CWE-918/601) | `HttpClient.GetAsync(url)`、`WebRequest.Create(url)`、`Response.Redirect(url)`、`RedirectToAction` 吃 `returnUrl` 未經 `Url.IsLocalUrl` | URL 是否使用者可控、有無 allowlist 或 `IsLocalUrl` 檢查 |
| 硬編碼祕密 (CWE-798) | 原始碼與 `web.config`/`appsettings.json` 中的明文 `connectionString`、`password=`、`apiKey`；`machineKey` 寫死 | 是否進過版控；設定檔的祕密應走環境變數、User Secrets 或 Key Vault |
| 不安全亂數 (CWE-330) | 安全情境（token、密碼重設碼、session id）用 `new Random()`、`Guid.NewGuid()` 當亂數 | 用途是否涉及安全；應改 `RandomNumberGenerator` |
| 設定類 | `customErrors mode="Off"`（對外洩漏堆疊）、`enableViewStateMac="false"`、`validateRequest="false"`、`compilation debug="true"` 上正式環境 | 該設定是否作用於對外環境 |

## Python

| 弱點 | 搜尋方向（範例） | 確認方向 |
| --- | --- | --- |
| SQL Injection | 字串拼接/格式化進 SQL：`"... " + var`、`f"...{var}..."`、`%`-format 進 `execute()` | `execute(sql, params)` 的參數化寫法安全；拼接的來源是否可控 |
| Command Injection | `os.system`、`subprocess.run(..., shell=True)`、`eval`/`exec`、反引號 | `shell=False` + list 參數多半安全；看拼進指令的變數來源 |
| Path Traversal | `open(base + name)`、`os.path.join(base, userInput)`、`../` 未正規化 | 有無 `os.path.realpath` 後比對根目錄 |
| 不安全反序列化 | `pickle.loads`、`yaml.load`（非 `safe_load`）、`marshal.loads` | 資料是否跨信任邊界；`yaml.load(..., Loader=SafeLoader)` 等同 safe_load |
| XSS | 樣板關閉自動跳脫：Jinja2 `autoescape=False`、`| safe` filter、`Markup(var)` | 塞進去的內容是否可控 |
| SSRF / Open Redirect | `requests.get(url)`、`urllib.request.urlopen(url)`、Flask/Django `redirect(url)` 未經 allowlist | URL 來源與有無網段/協定限制 |
| 不安全亂數 | 安全情境用 `random` 模組 | 應改 `secrets` 模組 |

## JavaScript / Node.js

| 弱點 | 搜尋方向（範例） | 確認方向 |
| --- | --- | --- |
| Command Injection | `child_process.exec(cmd)` 拼接、`execSync` | `execFile`/`spawn` + 陣列參數多半安全 |
| XSS | `innerHTML =`、`outerHTML =`、`document.write`、React `dangerouslySetInnerHTML`、Vue `v-html` | 塞入內容是否可控、有無經 DOMPurify 之類消毒 |
| 程式碼注入 | `eval(var)`、`new Function(var)`、`setTimeout(string)` | 參數是否含任何外部輸入 |
| Prototype Pollution (CWE-1321) | 自寫 `merge`/`extend`/`deepCopy` 未擋 `__proto__`/`constructor`/`prototype` key；lodash 舊版 `merge` | 合併的物件是否來自 JSON body 等可控來源 |
| SQL Injection | 樣板字串拼 SQL 丟 `query()`；ORM 的 raw query | `query(sql, [params])` 佔位符寫法安全 |
| SSRF / Open Redirect | `fetch(url)`/`axios.get(url)`、`res.redirect(req.query.next)` | URL 是否可控、有無 allowlist |
| Path Traversal | `path.join(base, req.params.file)`、`fs.readFile` 吃可控路徑 | 有無 `path.resolve` 後前綴檢查 |
| ReDoS (CWE-1333) | 使用者可控字串丟進含巢狀量詞的 regex：`(a+)+`、`(.*)*` | regex 是否處理可控輸入、長度有無上限 |

## 通用（跨語言）

| 弱點 | 搜尋方向（範例） | 確認方向 |
| --- | --- | --- |
| 硬編碼祕密 | `password\s*=`、`api[_-]?key`、`secret`、`token\s*=` 後接字面值；`-----BEGIN (RSA |EC )?PRIVATE KEY-----`；連線字串含 `pwd=`/`password=` | 是字面值還是從環境/祕密管理讀入；測試用假值要看是否真的只用於測試。命中後走 SKILL.md「特殊情境：硬編碼祕密」流程 |
| 過度詳盡錯誤 | 把 exception 全文/堆疊直接回給 client | 是否對外；內部 log 記詳細、對外回泛化訊息才是正解 |
| 缺認證/授權 | 對外 endpoint 沒有 auth middleware/attribute；用 id 直接查資料未驗 ownership（IDOR） | 該路由是否刻意公開；資源是否屬於當前使用者 |
