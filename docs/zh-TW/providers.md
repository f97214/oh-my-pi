> 這是 [`docs/providers.md`](../providers.md) 的繁體中文翻譯。
> 翻譯基準：`1c7170e11`（2026-08-14）。**英文原文為準** —— 上游更新後本檔可能過期。

# 供應商（Providers）

供應商是 `omp` 可以把請求路由過去的模型後端：Anthropic、OpenAI、Google Gemini、Groq、OpenRouter、Mistral、xAI、Ollama 之類的本機引擎、託管 gateway、自訂的 `models.yml` 供應商，以及由 extension 註冊的供應商。

**供應商（provider）**指的是帳號或後端的命名空間，例如 `anthropic`、`openai`、`google` 或 `ollama`。**模型（model）**則是該供應商底下的具體模型，以 `provider/model-id` 形式選用，例如 `anthropic/claude-opus-4-6`。停用一個供應商會把它底下**所有**模型從可選清單移除；如果你只想收斂個別模型，請改用模型設定。

本頁說明供應商如何變成可用、憑證如何解析、供應商與環境變數的對照、本機引擎、停用供應商，以及自訂供應商。端點層級的請求、推理、工具、串流、用量與重試限制請見 [Provider endpoint constraints](../provider-endpoint-constraints.md)。模型選擇與完整的 `models.yml` schema 請見 [Model and Provider Configuration](../models.md)。設定檔位置與合併優先順序請見 [Settings](../settings.md)。憑證儲存與登入流程的細節請見 [Secrets and credentials](../secrets.md)。完整的環境變數參考請見 [Environment variables](../environment-variables.md)。本機引擎的設定請見 [Local models](../local-models.md)。Context 檔案的探索供應商請見 [Context files](../context-files.md)。

## `omp` 如何判定一個供應商可用

啟動時，模型註冊表依序從四個來源組出它的目錄：

1. 內建的模型目錄（所有內建供應商與它們的已知模型）。
2. `~/.omp/agent/models.yml` 中的自訂供應商與模型項目。
3. 對支援 discovery 的供應商，在執行時期探索到的模型（本機引擎與啟用 discovery 的 gateway）。
4. 由 extension 註冊的供應商與模型。

註冊表可以持有一個目前不可選的模型。一個模型只有在**兩個條件同時成立**時才**可用**：

1. 它的供應商 ID **不在**生效的 `disabledProviders` 清單中；**且**
2. 該供應商要嘛是**免金鑰的**（隱含的本機供應商，或設定 `auth: none` 的自訂供應商），要嘛**有可解析的憑證**。

`disabledProviders` 是在憑證**之前**檢查的。如果一個供應商 ID 被停用，任何已儲存的金鑰、OAuth session、環境變數、`.env` 項目或 `models.yml` 的 `apiKey` 都不會讓它變成可選 —— 不論憑證如何，該供應商的模型都會從可用清單中被移除。把該 ID 從生效清單中移除就會還原它們。

免金鑰的本機引擎是特例：`ollama`、`llama.cpp` 與 `lm-studio` 在沒有設定金鑰時被視為免金鑰，所以只要引擎有回應，它們探索到的模型就可以被選用 —— 不需要登入。見[內建本機引擎](#內建本機引擎)。

## 憑證與優先順序

當供應商需要 API key 時，`omp` 依此順序解析（第一個命中者勝出）：

1. **執行時期覆寫**：為目前行程提供的金鑰，例如 CLI 的 `--api-key`。永不持久化。
2. **`models.yml` 設定金鑰**：釘在自訂供應商上的 `apiKey`，註冊為來自設定的 bearer。這**刻意**勝過已儲存的 OAuth，讓為自訂 `baseUrl` 或 gateway 提供的金鑰被採用，而不是轉送一個 proxy 會拒絕的上游 OAuth token。
3. **已儲存的 OAuth 憑證**：需要時會自動更新；多個帳號會被排序並自動輪替。對 Anthropic 與 ChatGPT（Codex）而言，每個組織或 workspace 算是各自獨立的帳號：同一個 email 若同時持有 Team 或 Enterprise 席次與個人方案，可以為每個訂閱各登入一次（在瀏覽器同意頁選擇 workspace），輪替時會把它們當成兩個帳號。
4. **由登入取得的已儲存 API key**：一次成功的 `/login` 所儲存的 API-key 憑證。
5. **供應商環境變數**：包含從 `.env` 檔案載入的值（見[環境變數表](#環境變數與-env-檔案)）。
6. **其他已儲存的 API key**：例如由 broker 遷移過來的金鑰。這是最後手段，所以明確的環境變數會勝出。
7. **`models.yml` fallback resolver**：給那些沒有以其他方式註冊的自訂供應商用的金鑰。

已儲存的憑證放在 auth store：本機認證是 `~/.omp/agent/agent.db`，在 broker 模式下則是設定的 auth-broker 快照。（`PI_CODING_AGENT_DIR` 會搬移 `~/.omp/agent` 基底，auth store 也會跟著移動。）

### OAuth 與 API key，以及以供應商為範圍的登入

登入是**以供應商為範圍**的：認證 `anthropic` 不會認證 `openai`，每個供應商各自追蹤自己的憑證。被停用的供應商即使有有效的已儲存認證，仍然維持停用。

在 session 中使用互動式的 slash command：

- `/login` —— 開啟 OAuth／金鑰選取器。`/login <provider>` 直接跳到單一供應商（例如 `/login anthropic`）；若 OAuth 流程需要貼上 callback，執行 `/login <redirect-url>` 完成它。
- `/logout` —— 開啟供應商選取器以移除已儲存的憑證。

對於以共用 auth broker 為後端的 headless 或遠端環境，CLI 提供 `omp auth-broker login <provider>` / `omp auth-broker logout`（以及 `status`、`list`、`import`、`migrate`）。broker 模型請見 [Secrets and credentials](../secrets.md)。

當某個模型沒有憑證時，`omp` 會提示你執行 `/login` 或設定該供應商的環境變數。

### 在 `models.yml` 中釘一把金鑰

自訂供應商的 `apiKey` 以「**環境變數名稱或字面值**」的方式解析：若該值是某個既存環境變數的名稱，就使用那個變數的值；否則字串本身就是金鑰。在值前面加上 `!` 會把它當成 shell 命令執行，並使用去除首尾空白後的 stdout（完整的值語法請見 [Model and Provider Configuration](../models.md)）。

```yaml
# ~/.omp/agent/models.yml
providers:
  my-gateway:
    baseUrl: https://gateway.example.com/v1
    api: openai-completions
    apiKey: MY_GATEWAY_API_KEY # reads this env var if set, else literal text
    models:
      - id: claude-sonnet
        name: Claude Sonnet via Gateway
        contextWindow: 200000
        maxTokens: 8192
```

若在自訂供應商上設定 `authHeader: true`，解析出的金鑰會以 `Authorization: Bearer <key>` header 的形式注入到對該供應商的每一個請求。

## 環境變數與 `.env` 檔案

每個供應商都有一或多個環境變數，在沒有已儲存憑證時提供金鑰。下表是已驗證的「供應商 → 變數」對照；完整目錄很大，所以拆成核心與其他供應商兩張表。以 OAuth 為後端的供應商，也可以在 API key 之外（或取而代之）接受一個 token 變數。

### 核心供應商

| Provider ID | 環境變數 |
| ---------------- | ------------------------------------------------------------------------------------------------------------------------------------------------ |
| `anthropic` | `ANTHROPIC_OAUTH_TOKEN`，然後 `ANTHROPIC_API_KEY`（Foundry 模式在 `CLAUDE_CODE_USE_FOUNDRY=true` 時優先使用 `ANTHROPIC_FOUNDRY_API_KEY`） |
| `openai` | `OPENAI_API_KEY` |
| `openai-codex` | `OPENAI_CODEX_OAUTH_TOKEN` |
| `google` | `GEMINI_API_KEY` |
| `google-vertex` | `GOOGLE_CLOUD_API_KEY`，或 Application Default Credentials（`GOOGLE_APPLICATION_CREDENTIALS` + `GOOGLE_CLOUD_PROJECT` + `GOOGLE_CLOUD_LOCATION`） |
| `groq` | `GROQ_API_KEY` |
| `openrouter` | `OPENROUTER_API_KEY` |
| `mistral` | `MISTRAL_API_KEY` |
| `xai` | `XAI_API_KEY` |
| `xai-oauth` | `XAI_OAUTH_TOKEN`，然後 `XAI_API_KEY` |
| `github-copilot` | `COPILOT_GITHUB_TOKEN` |
| `cursor` | `CURSOR_ACCESS_TOKEN` |
| `azure` | `AZURE_OPENAI_API_KEY` |
| `amazon-bedrock` | `AWS_PROFILE`，或 `AWS_ACCESS_KEY_ID` + `AWS_SECRET_ACCESS_KEY`，或 ECS/IRSA 憑證鏈 |

### 其他託管供應商

| Provider ID | 環境變數 |
| -------------------------------- | ----------------------------------------------------------------------------- |
| `aiand` | `AIAND_API_KEY` |
| `cerebras` | `CEREBRAS_API_KEY` |
| `alibaba-token-plan` | `ALIBABA_TOKEN_PLAN_API_KEY`，然後 `BAILIAN_TOKEN_PLAN_API_KEY` |
| `baseten` | `BASETEN_API_KEY` |
| `bedrock-mantle` | `AWS_BEARER_TOKEN_BEDROCK` |
| `deepseek` | `DEEPSEEK_API_KEY` |
| `siliconflow` | `SILICONFLOW_API_KEY` |
| `siliconflow-cn` | `SILICONFLOW_CN_API_KEY` |
| `fireworks` | `FIREWORKS_API_KEY` |
| `together` | `TOGETHER_API_KEY` |
| `coreweave` | `COREWEAVE_API_KEY`，然後 `WANDB_API_KEY` |
| `nvidia` | `NVIDIA_API_KEY` |
| `devin` | `DEVIN_API_KEY` |
| `gmi-cloud` | `GMI_API_KEY` |
| `huggingface` | `HUGGINGFACE_HUB_TOKEN`，然後 `HF_TOKEN` |
| `moonshot` | `MOONSHOT_API_KEY`，然後 `KIMI_API_KEY` |
| `meta` | `MODEL_API_KEY`，然後 `META_API_KEY` |
| `nanogpt` | `NANO_GPT_API_KEY` |
| `novita` | `NOVITA_API_KEY` |
| `venice` | `VENICE_API_KEY` |
| `vercel-ai-gateway` | `AI_GATEWAY_API_KEY`（catalog discovery 也接受 `VERCEL_AI_GATEWAY_API_KEY`） |
| `cloudflare-ai-gateway` | `CLOUDFLARE_AI_GATEWAY_API_KEY` |
| `litellm` | `LITELLM_API_KEY`；proxy 端點可選用 `LITELLM_BASE_URL` |
| `kilo` | `KILO_API_KEY` |
| `zai` | `ZAI_API_KEY` |
| `zenmux` | `ZENMUX_API_KEY` |
| `zhipu-coding-plan` | `ZHIPU_API_KEY` |
| `umans` | `UMANS_AI_CODING_PLAN_API_KEY` |
| `qianfan` | `QIANFAN_API_KEY` |
| `qwen-portal` | `QWEN_OAUTH_TOKEN`，然後 `QWEN_PORTAL_API_KEY` |
| `synthetic` | `SYNTHETIC_API_KEY` |
| `minimax-code` | `MINIMAX_CODE_API_KEY` |
| `minimax-code-cn` | `MINIMAX_CODE_CN_API_KEY` |
| `minimax` | `MINIMAX_API_KEY` |
| `alibaba-coding-plan` | `ALIBABA_CODING_PLAN_API_KEY` |
| `sakana` | `SAKANA_API_KEY`，然後 `FUGU_API_KEY` |
| `aimlapi` | `AIMLAPI_API_KEY` |
| `gitlab-duo`、`gitlab-duo-agent` | `GITLAB_TOKEN` |
| `opencode-zen`、`opencode-go` | `OPENCODE_API_KEY` |
| `firepass` | `FIREPASS_API_KEY` |
| `wafer-serverless` | `WAFER_SERVERLESS_API_KEY` |
| `xiaomi` | `XIAOMI_API_KEY` |
| `xiaomi-token-plan-ams` | `XIAOMI_TOKEN_PLAN_AMS_API_KEY` |
| `xiaomi-token-plan-cn` | `XIAOMI_TOKEN_PLAN_CN_API_KEY` |
| `xiaomi-token-plan-sgp` | `XIAOMI_TOKEN_PLAN_SGP_API_KEY` |
| `ollama-cloud` | `OLLAMA_CLOUD_API_KEY` |
| `ollama` | `OLLAMA_API_KEY`（可選；本機 discovery 預設免金鑰） |
| `lm-studio` | `LM_STUDIO_API_KEY`（可選；預設免金鑰） |
| `llama.cpp` | `LLAMA_CPP_API_KEY`（只在 server 要求認證時需要） |
| `vllm` | `VLLM_API_KEY`（未認證的本機 server 可不設） |

以 OAuth 為後端的供應商，例如 `anthropic`、`github-copilot`、`cursor`、`ollama-cloud`、`qwen-portal`、`kimi-code`、`xai-oauth`、`wafer-serverless`、`google-gemini-cli` 與 `google-antigravity`，一般是透過 `/login` 而不是環境變數來使用。此處未列出的搜尋工具與組態變數請見 [Environment variables](../environment-variables.md)。

### `.env` 的探索與優先順序

`omp` 會在任何供應商查找之前，先積極地把 `.env` 檔案載入行程環境。它讀取四個檔案，而對每個變數而言，**第一個**定義它的來源勝出。實際優先順序由高到低：

1. `omp` 繼承到的行程環境（已設定的變數一律勝出）。
2. `<cwd>/.env`
3. `~/.omp/agent/.env`
4. `~/.omp/.env`
5. `~/.env`

已存在於行程環境中的變數，**永遠不會**被 `.env` 檔案覆寫。在這些檔案之間，`<cwd>/.env` 設定的值勝過 `~/.omp/agent/.env`，後者勝過 `~/.omp/.env`，再勝過 `~/.env`。所以在 shell export 的 `OPENAI_API_KEY` 勝過所有 `.env` 檔案，而專案的 `<cwd>/.env` 勝過你家目錄的 `~/.env`。

專案層的 `.env` 是讓單一 repository 使用專案專屬 gateway、金鑰或本機端點最簡單的方式：

```dotenv
# <project>/.env
OPENROUTER_API_KEY=sk-or-...
OLLAMA_BASE_URL=http://127.0.0.1:11434
```

`.env` 的解析刻意保持極簡：

- 空行與以 `#` 開頭的行會被忽略；
- 鍵必須符合 `[A-Za-z_][A-Za-z0-9_]*`（shell 識別字的形狀）—— 其他名稱會被丟棄；
- 值可以用單引號或雙引號包起來，引號會被移除；
- 含有 NUL 位元組的值會被丟棄；
- 以 `OMP_` 為前綴的鍵，也會被鏡射到對應的 `PI_` 前綴名稱。

## 內建本機引擎

有三個本機引擎會被自動探索，不需要 `models.yml` 項目。每個都使用一個可由環境變數覆寫的 base URL：

| Provider ID | Base URL（env 覆寫 → 預設） | 備註 |
| ----------- | --------------------------------------------------------------------------------- | ----------------------------------------------- |
| `ollama` | `OLLAMA_BASE_URL`，然後 `OLLAMA_HOST`（正規化後），否則 `http://127.0.0.1:11434` | 預設免金鑰。 |
| `llama.cpp` | `LLAMA_CPP_BASE_URL`，否則 `http://127.0.0.1:8080` | 除非為 `llama.cpp` 儲存了金鑰，否則免金鑰。 |
| `lm-studio` | `LM_STUDIO_BASE_URL`，否則 `http://127.0.0.1:1234/v1` | 預設免金鑰。 |

這些隱含引擎在下列情況會被**跳過**：

- `models.yml` 中已經設定了相同 ID 的供應商（你的明確設定勝出）；或
- 該供應商 ID 出現在生效的 `disabledProviders` 清單中。

這些引擎的安裝與執行請見 [Local models](../local-models.md)。

## 停用模型供應商

用 `disabledProviders` 設定把某個供應商的模型從可選清單移除：

```yaml
# ~/.omp/agent/config.yml or <project>/.omp/config.yml
disabledProviders:
  - anthropic
  - openai
  - google
  - groq
```

供應商 ID 是精確比對。停用 `google` 會隱藏 Google Gemini API 供應商；以 OAuth 為後端的 Google 供應商 `google-gemini-cli` 與 `google-antigravity` 是**不同的 ID**，必須個別停用。停用 `ollama`、`llama.cpp` 或 `lm-studio` 會停止該引擎的本機 discovery。

`disabledProviders` 一致地套用於：

- 內建目錄的供應商；
- 自訂 `models.yml` 供應商；
- 執行時期探索到的供應商模型；
- 由 extension 註冊的供應商；
- 隱含的本機引擎。

停用供應商**不會**刪除它已儲存的憑證 —— 把它的 ID 從生效清單中移除即可重新啟用。

## 專案專屬的供應商控制

專案設定放在 `<project>/.omp/config.yml`。當某個 repository 必須允許或隱藏與你全域預設不同的供應商集合時使用它：

```yaml
# <project>/.omp/config.yml
disabledProviders:
  - openai
  - openrouter
```

設定中的陣列會被較高優先層**整個取代**，不是合併也不是附加。如果全域檔案停用三個供應商、專案檔案停用一個，那麼專案只會看到專案的那份清單：

```yaml
# ~/.omp/agent/config.yml
disabledProviders:
  - anthropic
  - openai
  - google

# <project>/.omp/config.yml
disabledProviders:
  - groq
```

在該專案中的實際結果：

```json
["groq"]
```

專案的陣列為「從該專案啟動的 session」重新啟用了 `anthropic`、`openai` 與 `google`。如果你希望某個專案是**加到**全域集合上，就在專案檔案裡把全域的 ID 再寫一次。完整的優先順序鏈（包含 `--config` 覆蓋層與執行時期覆寫）請見 [Settings](../settings.md)。

## 路徑範圍的 `disabledProviders`

`disabledProviders` 可以混用純字串項目（處處適用）與路徑範圍項目（只在目前工作目錄符合設定路徑時適用）：

```yaml
disabledProviders:
  - ollama
  - path: ~/projects/sensitive
    providers:
      - anthropic
      - openai
  - paths:
      - ~/work/client-a
      - ~/work/client-b
    values:
      - openrouter
```

- 純字串項目一律適用。
- 範圍項目在目前工作目錄**就是**設定的路徑、或**位於它底下**時適用。`~` 會展開成家目錄。
- 可接受的路徑鍵：`path`、`paths`、`pathPrefix`、`pathPrefixes`。
- 可接受的值鍵：`providers`、`values`、`items`。

以上面的例子來說：

- `ollama` 處處停用。
- `anthropic` 與 `openai` 在 `~/projects/sensitive` 底下額外停用。
- `openrouter` 在 `~/work/client-a` 與 `~/work/client-b` 底下額外停用。

路徑範圍是在設定合併**之後**才解析。由於較高優先層會取代整個陣列，專案層的 `disabledProviders` 陣列會把只存在於全域陣列中的範圍項目全部丟掉。`enabledModels` 是唯一另一個支援相同路徑範圍形式的設定。細節請見 [Settings](../settings.md)。

## 供應商 ID 與 discovery 供應商 ID

`disabledProviders` 使用**單一共用的 ID 命名空間**，它管控兩個不同的子系統：

- **模型供應商** —— 本頁講的那些後端（`anthropic`、`openai`、`ollama`、自訂的 `models.yml` ID……）。停用一個會把它的模型從可選清單移除。
- **Discovery 供應商** —— context 檔案、MCP server、命令、skills、hooks、tools、prompts 與 settings 的來源。停用一個會讓該來源不再提供 capability 項目。

| 項目型別 | 範例 | 效果 |
| --------------------- | ----------------------------------------------------------------------------- | --------------------------------------------------------------- |
| 模型供應商 ID | `anthropic`、`openai`、`google`、`groq`、`openrouter`、`ollama`、`my-gateway` | 把該供應商的模型從可用清單移除。 |
| Discovery 供應商 ID | `native`、`claude`、`codex`、`gemini`、`agents`、`github` | 讓該 discovery 來源不再提供 capability 項目。 |

留意名稱相近的陷阱。Google Gemini **API** 的模型使用模型供應商 ID `google`；`gemini` 是 **discovery** 供應商 ID（讀取 `GEMINI.md` 的那個來源），不是 Google 的模型供應商。只有在你確實想停用整個設定來源時才使用 discovery ID。Discovery 供應商那一側請見 [Context files](../context-files.md)。

## `models.yml` 中的自訂供應商

自訂供應商放在 `~/.omp/agent/models.yml` 的 `providers:` 底下。在那裡定義的供應商 ID，適用與內建供應商完全相同的選用、憑證解析與 `disabledProviders` 規則。

最小的 OpenAI 相容供應商：

```yaml
providers:
  my-openai-compatible:
    baseUrl: https://api.example.com/v1
    api: openai-completions
    apiKey: MY_OPENAI_COMPATIBLE_KEY # env-var-name or literal
    models:
      - id: fast-chat
        name: Fast Chat
        contextWindow: 128000
        maxTokens: 8192
```

免金鑰的本機供應商（不需要憑證）：

```yaml
providers:
  local-proxy:
    baseUrl: http://127.0.0.1:4000/v1
    api: openai-completions
    auth: none
    models:
      - id: local-model
        name: Local Model
        contextWindow: 32768
        maxTokens: 4096
```

啟用 discovery 的供應商（模型在執行時期由端點取得）：

```yaml
providers:
  team-proxy:
    baseUrl: https://models.example.com/v1
    apiKey: TEAM_PROXY_API_KEY
    authHeader: true # send Authorization: Bearer <resolved key>
    disableStrictTools: true
    discovery:
      type: proxy
```

完整的 schema、所有允許的 `api` 值、discovery 的 `type`、模型覆寫與等價設定，請見 [Model and Provider Configuration](../models.md)。

要停用自訂供應商，精確列出它的 ID：

```yaml
disabledProviders:
  - my-openai-compatible
  - team-proxy
```

## 疑難排解

**某個供應商的模型無法選用。** 確認該供應商有憑證（`/login <provider>`、已 export 的環境變數，或 `models.yml` 的 `apiKey`），而且它的 ID 不在生效的 `disabledProviders` 清單中。記住那條規則：**未被停用** **且**（**免金鑰** **或** **有憑證**）。免金鑰的本機引擎只有在引擎確實在跑且有回應時才會出現。

**用到了錯的金鑰（來自 `.env` 的過期金鑰）。** 解析順序偏好執行時期的 `--api-key`，接著是 `models.yml` 的設定金鑰、已儲存的 OAuth、由 `/login` 儲存的金鑰、環境或 `.env`、其他已儲存的 API key，最後是 `models.yml` 的 fallback resolver。已設定的行程環境變數也勝過所有 `.env` 檔案，而 `<cwd>/.env` 勝過 `~/.env`。若勝出的是意料之外的金鑰，依優先順序檢查 shell export 的變數與那四個 `.env` 檔案，並清掉不該生效的那一個。

**我已經停用了某個供應商，它卻還在。** `disabledProviders` 陣列是被**取代**而非合併：專案的 `<project>/.omp/config.yml` 陣列會完全覆寫全域的那份。請驗證你所在目錄的**實際**清單（路徑範圍項目只在其設定路徑或其下適用），並確認 ID 拼寫完全正確。用 `omp config get disabledProviders` 檢視合併後的值（見 [Settings](../settings.md)）。

**Discovery 供應商名稱對模型沒有作用（或反過來）。** ID 命名空間是共用的。`gemini`、`codex`、`claude`、`native` 與 `agents` 是 discovery 來源 ID；Google 的模型後端是 `google`。請確認你停用的是正確種類的供應商。

**自訂的 `models.yml` 供應商沒有載入。** YAML 或 schema 錯誤會讓註冊表跳過整個自訂檔案。用 `omp models` 驗證該檔案（用 `omp models find <substr>` 收斂到單一供應商）。帶有自訂 `models` 的供應商需要 `baseUrl`、認證（`apiKey`，除非 `auth: none`），以及在供應商層級或每個模型上的 `api`。沒有模型的供應商也是合法的，只要它定義了至少一個支援的覆寫（`baseUrl`、`headers`、`apiKey`、`auth: none`、`compat`、`disableStrictTools`、`remoteCompaction`、`modelOverrides` 或 `discovery`）。Discovery 供應商可以省略 `models`，但除非 `discovery.type` 是 `proxy`，否則需要供應商層級的 `api`。明確寫出的 `ollama`、`lm-studio` 或 `llama.cpp` 項目會**刻意**取代該 ID 的內建 discovery。請見 [Model and Provider Configuration](../models.md)。
