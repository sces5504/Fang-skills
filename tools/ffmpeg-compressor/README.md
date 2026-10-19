# ff-tool

純靜態的 FFmpeg 影片壓縮指令產生器。選擇目標大小、解析度與音訊設定，複製或下載腳本，在自己的電腦執行。影片不會上傳；無分析追蹤、localStorage、後端或瀏覽器轉檔。

- **預定 Pages 入口**：[ff-tool](https://sces5504.github.io/Fang-skills/tools/ffmpeg-compressor/)（此 PR 合併並發布後可用）。
- 單支／批次，各影片分別計算相同目標大小。
- macOS zsh／bash；Windows PowerShell 5.1+／7。輸出為 MP4、libx264、yuv420p、兩次編碼與 faststart。
- 解析度上限依長短邊處理直式影片，不放大來源並調整為偶數寬高；可保留 FPS 或選 30／60。

## 使用

1. 安裝含 `libx264` 的 [FFmpeg 與 ffprobe](https://ffmpeg.org/download.html)，確認兩者都在 PATH。macOS 既有 Homebrew 使用者可用 `brew install ffmpeg`。
2. 手動填入影片路徑，或選檔／拖放讀取片長與大小。瀏覽器無法提供完整路徑，**選檔不會自動填入路徑**；無法讀取時，手動填秒數或 `HH:MM:SS`（含小數秒），或留空讓腳本實測。
3. 設定目標與輸出路徑。預設與來源同資料夾，後綴 `_30MB.mp4`；輸出資料夾必須存在，既有檔案不覆寫。
4. 下載後在自己的終端機執行：

```sh
# macOS：在腳本所在資料夾執行；相對影片路徑依目前工作資料夾解析。
bash ./ff-tool.sh
```

```powershell
# Windows：下載為 UTF-8 BOM，避免 Windows PowerShell 5.1 誤讀中文路徑。
& .\ff-tool.ps1
```

若 Windows 執行原則阻擋，依你的組織政策處理，或檢查內容後將完整腳本貼到 PowerShell。工具不要求永久放寬全系統的執行原則。macOS 的完整腳本也可直接貼到 zsh／bash；以子 shell 執行，不關閉原本的終端機。

音軌「未知」時，網頁先按 AAC 位元率保守估計；兩種腳本都會用 ffprobe 確認實際音軌，有才保留第一音軌並轉 AAC 雙聲道，無則移除音訊預算。腳本以實測片長為準，僅在 format duration 無效時使用手動片長。若連 ffprobe 都讀不到檔案，安全失敗。

只處理第一影像／第一音軌，不保留其他軌道、章節、字幕或來源 metadata。不是 HDR 色調轉換或專業保真工具。

## 大小估算

```text
MB  = 1,000,000 bytes
MiB = 1,048,576 bytes
總位元率 = 目標 bytes × (1 − 餘裕) × 8 ÷ 秒數
影片 kbps = floor((總位元率 − 音訊 kbps × 1000) ÷ 1000)
```

預設 30 MB、3.2% 餘裕（僅扣一次），移除音訊時，974／532／652 秒約為 **238／436／356 kbps**。最小影片預算為 16 kbps；不足時不能生成已知無效的設定，腳本亦會在轉檔前重驗。

顯示的大小是媒體資料估算，不含實際 MP4 開銷。AAC 與 x264 仍有誤差，尤其短片的容器占比高；**不能保證每次低於限制**。腳本會檢查輸出 bytes，超標時保留檔案、標示失敗並建議提高安全餘裕／降低目標、換新輸出名稱重跑。批次最後總結成功與失敗；有失敗或超標時回傳非零狀態。

## 檔案安全與引用

輸入路徑作為單引號字串資料與獨立參數傳給程式，沒有 `eval`／`Invoke-Expression`。支援空白、中文、括號、方括號、`$`、反引號、`&` 與單引號。POSIX 路徑也支援雙引號；Windows 的雙引號、`< > | ? *` 本來就是非法檔名字元，因此直接拒絕。換行、NUL 與其他控制字元也拒絕。

每個工作都在輸出目錄建立獨立的隨機暫存目錄與 pass log。第一輪失敗不會進第二輪，第二輪產物先留在暫存目錄，成功後才發布；退出時只清理該工作自己的暫存目錄。批次逐支執行，其他影片不因單一檔案失敗而被跳過。

macOS 以 POSIX `link` 建立同磁碟硬連結，原子地拒絕已存在的目標；不支援硬連結的檔案系統（例如部分外接磁碟格式）會安全失敗。Windows 以不覆寫的 .NET `File.Move` 發布。這些保護包含同時執行的碰撞；原始影片不被覆寫。

## 維護與 Pages

`core.mjs` 負責純計算、驗證與路徑引用；`templates/` 是兩種 shell 腳本；`app.mjs` 處理 UI、本機 metadata、複製與下載。沒有第三方執行期依賴。

本 repo 已從 `main:/docs` 以 branch Pages 發布。為保留原流程，原始碼留在這裡，發布副本在 `docs/tools/ffmpeg-compressor/`。更改後執行：

```sh
node scripts/sync-tools.mjs
node scripts/sync-tools.mjs --check
node --test tests/*.test.mjs
```

同步程式只複製明列的六個網站檔案，README 不進發布副本。CI 檢查副本一致性並執行測試；不變更 Pages 設定、不新增第二套部署。合併後既有 Pages 自動發布，不需管理員做額外設定。若另建 repo，設定 Pages 來源為 `main` 的 `/docs`。

本機預覽可在 repo 根目錄執行 `python3 -m http.server 8765 --directory docs`，開啟 `/tools/ffmpeg-compressor/`。所有資源都使用相對路徑，適用 project Pages 子路徑。

測試需 Node.js 20+。有 FFmpeg 時會額外跑短合成影片的實際 two-pass、解碼、尺寸、音軌、原檔保留、錯誤清理與同時任務；沒有 FFmpeg 會明確跳過這些測試。此開發環境沒有 Windows／pwsh：PowerShell 已做字串引用、腳本結構與下載 BOM 的靜態驗證，**尚未在 Windows 實際轉檔**。Windows 實機驗證仍應包含特殊字元路徑、音軌、失敗清理和不覆寫輸出。

依據：[FFmpeg CLI](https://ffmpeg.org/ffmpeg.html)、[scale filter](https://ffmpeg.org/ffmpeg-filters.html#scale-1)、[PowerShell quoting](https://learn.microsoft.com/en-us/powershell/module/microsoft.powershell.core/about/about_quoting_rules)。
