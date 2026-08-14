> 這是 [`CONTRIBUTING.md`](../../CONTRIBUTING.md) 的繁體中文翻譯。
> 翻譯基準：`1c7170e11`（2026-08-14）。**英文原文為準** —— 上游更新後本檔可能過期。

# 貢獻 oh-my-pi

歡迎 pull request。請保持聚焦、了解你送出的內容，並準備好為它解釋與維護。

> [!NOTE]
> Pull request 目前**暫時對所有人開放**，屬於試行。我們先前要求在接受 PR 之前需要有人背書（vouch）；該要求暫時解除，我們正在評估開放貢獻的成效。依結果而定，vouch 制度有可能回歸。

## 開始之前

### 小改動

Bug 修正、文件更新，以及範圍很窄的改進，可以直接開 pull request。

### 重大改動

重大功能，以及大範圍的架構或行為變更，請**在動手實作之前**先到 [Discord](https://discord.gg/4NMW9cdXZa) 討論。這包含新的子系統、大型 UI 變更、新的相依套件，以及跨多個套件的改動。GitHub issue **不能**取代這個討論，而且事先討論過也不保證 pull request 一定會被 merge。

### 不要為你即將送出的工作開 issue

如果你打算自己實作某個變更，**不要先為它建立 issue**。robomp 會把可執行的 issue 當成可以接手的工作，可能平行開始做同一個修正，浪費運算資源與維護者的時間。

在你要回報問題、或提出你尚未著手轉成 pull request 的工作時，才開 issue。如果已經有相關的 issue，請在你的 pull request 中連結它，而不是再開一個。

## AI 輔助的貢獻

AI 代理歡迎作為工具，但不歡迎作為無人監督的貢獻者。不要給代理一個模糊的目標，然後把它產出的東西直接送出。

開 pull request 之前，你必須：

- 把代理約束在講好的範圍內，並拒絕不相關的變更；
- 審查每一個被改動的檔案，並理解由此產生的行為；
- 跑過相關的檢查，並親自操作被改動的行為；以及
- 在完成上述審查之後才送出 pull request，而不是讓代理自主發布。

不論程式碼是誰、是什麼產生的，你都要為它負責。

## Pull request 的要求

每個 pull request 的內文**必須至少包含一句你自己寫的、用你自己的話**說明改了什麼、為什麼改。光是產生的摘要、貼上的代理 transcript，或只有一份檢查清單，都不滿足這項要求。

一句誠實的話就夠了：

> I reviewed the full diff; this change fixes duplicate PR reviews by reusing
> the existing delivery guard.

你**必須驗證這個變更確實如預期運作**。相關情況下會期待有 `bun check` 與自動化測試，但它們**不是**行為正常的證明。請親自操作被改動的路徑，並在 pull request 中回報確切的情境與結果：

- 修 bug 時，重現該 bug 並確認同一個重現方式不再失敗；
- 做功能時，啟動產品並端到端地使用該功能；以及
- 改 UI 時，實際操作它並檢視渲染結果。

單靠「`bun check` 通過」不算充分的驗證。coding-agent 的開發命令與 repository 結構請見 [`packages/coding-agent/DEVELOPMENT.md`](../../packages/coding-agent/DEVELOPMENT.md)。

每個 pull request 只做一件邏輯上的事。避免不相關的清理、順手的重構、產生出來的雜訊，或不在講好範圍內的功能。

## 審查

維護者審查的是送出的行為，以及貢獻者對它的理解 —— 不是產生出來的程式碼數量。請自己回應審查意見，並且只採納你已經檢查過的建議。

Pull request 在以下情況可能被關閉：跳過必要的事前討論、缺少人寫的說明、包含未經審查的代理輸出，或混入不相關的變更。
