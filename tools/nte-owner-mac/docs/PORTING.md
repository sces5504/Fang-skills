# 來源檢查與移植差異

參考 commit：`893525d5c62eb86fb596956b85d3f136e0209918`。

- [OwnerSelectionTask.py](https://github.com/BnanZ0/ok-nte/blob/893525d5c62eb86fb596956b85d3f136e0209918/src/tasks/OwnerSelectionTask.py)：原版說明明確不製作餐點，只處理退出／重開；可錄製兩步選關（捲動、選取）。`CONTROL_TIMEOUT=120`。其三星判定實際是右上固定區域 RGB 黃色比例 >0.1，沒有真的跑營業額 OCR。
- `src/tasks/BaseNTETask.py`：`find_confirm` 使用兩種通用確認圖示；`wait_click_confirm` 等圖示出現再點擊，等圖示消失。
- `assets/coco_annotations.json`、`assets/templates/`：有通用 confirm 圖示，沒有此關專用的顧客訂單、番茄汁或紅色材料包模板。兩個 confirm 圖示保留在 `assets/reference/` 供來源檢查，不預設用於判定結算。
- `src/config.py`：Windows 任務框架註冊，不移植其他日常、戰鬥、錄製或 OCR 系統。
- 原專案為 GPL-3.0，本專案保留授權與來源資訊，沒有改動原 repo。

新增 macOS 專案拆成：`engine.py` 純狀態機、`vision.py` 模板／星星／活力辨識、`macos.py` 前景及遮擋檢查與系統輸入、`runner.py` 可停止執行緒、`gui.py` 校準介面。

擷取使用 macOS 內建 `/usr/sbin/screencapture -R`，沒有使用已棄用的 CGWindowListCreateImage，也沒有宣稱已實作 ScreenCaptureKit 串流。每次擷取可能有數百毫秒延遲，先重視容易測試的前景流程；若實機無法及時出餐，再換 ScreenCaptureKit 擷取服務而不改變狀態機。

相較原版，三星改成分別檢查三個校準區域；每個都達到黃色比例才成立。所有一般畫面需穩定多幀。非目標判斷需正向確認訂單氣泡存在；找不到目標並不直接等於其他訂單。

使用者六張附圖用於建立繁體中文預設，只保留不含 UID 的小圖示／文字裁切。紅色手寫標記不納入模板。完整附圖未打包。活力 0 的字形取自同字型分母 `700`，真正歸零畫面尚未收到，需實機驗證。

打包參考：[PyInstaller macOS 支援](https://pyinstaller.org/en/stable/feature-notes.html#macos-multi-arch-support)。CI runner 標籤參考：[GitHub runner 文件](https://docs.github.com/en/actions/how-tos/write-workflows/choose-where-workflows-run/choose-the-runner-for-a-job)。
