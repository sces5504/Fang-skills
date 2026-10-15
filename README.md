# Fang-skills

集中存放、維護與分享個人使用的 Agent Skills，供不同 Codex 專案取用。

## 目錄

```text
Fang-skills/
├── skills/                 # 技能原始檔；每個技能一個資料夾
│   └── <skill-name>/
│       ├── SKILL.md        # 必要：名稱、描述與工作流程
│       ├── scripts/        # 選用：執行腳本
│       ├── references/     # 選用：參考資料
│       └── assets/         # 選用：範本與素材
└── third-party/
    └── SOURCES.md          # 第三方技能來源與授權紀錄
```

上方 `<skill-name>` 為目錄格式示意。

## 已收錄技能

| 技能 | 用途 |
| --- | --- |
| [polisher](skills/polisher/SKILL.md) | 為既有 GitHub Pages 專案改善社群分享預覽，並在首次使用時一次性潤飾 README。只允許修改必要 metadata、專用圖片與首次 README；不改動應用程式或全專案指令。 |

安裝時請複製整個 `skills/polisher/` 到目標專案的 `.agents/skills/polisher/`，保留 `scripts/` 和 `references/`。接著呼叫：「請使用 polisher，一次性潤飾這個 GitHub Pages 專案的社群預覽與 README。」後續若只檢查預覽，明確告知 README 已完成即可。

## 新增技能

在 `skills/<skill-name>/SKILL.md` 建立檔案，至少包含：

```markdown
---
name: skill-name
description: 說明何時應使用此技能，以及不適用的情況。
---

在這裡寫下工作流程、輸入需求與完成條件。
```

技能引用的腳本、參考文件與素材也應一併放入該技能資料夾。避免使用只存在於自己電腦的絕對路徑。

## 在其他 Codex 專案使用

1. 從本 repo 選定技能與來源 commit 或 tag。
2. 將整個 `skills/<skill-name>/` 複製到目標專案的 `.agents/skills/<skill-name>/`。
3. 保留必要的授權文件，記錄來源 commit，再提交至目標專案。
4. 在 Codex 對話中明確指定「請使用 `<skill-name>` 技能完成……」。

可以直接請目標專案的 Codex 協助：

> 從 https://github.com/sces5504/Fang-skills 取得 skills/<skill-name>，將整個技能資料夾及必要資源複製到本專案的 .agents/skills/<skill-name>。保留來源、授權資訊，記錄來源 commit，檢查 SKILL.md 的名稱與描述。若目的地已有自訂內容，先比較再更新。

中央 repo 更新後，各專案需要重新同步；不會自動更新。Codex Cloud 可以使用專案 repo 內的技能，本機個人技能不會自動同步至雲端。下載本 repo 時，執行環境也需要能存取 GitHub。

官方文件：[Build skills](https://learn.chatgpt.com/docs/build-skills)、[Cloud environments](https://learn.chatgpt.com/docs/environments/cloud-environments)。

## 收錄第三方技能

- 先確認原作者授權允許預定的使用、修改與再散布。
- 保留原始授權、版權與必要的 NOTICE 等文件，並填寫 [來源紀錄](third-party/SOURCES.md)。
- 記錄上游 commit 或 tag，以及自行修改的內容。
- 若原作沒有明確授權，先取得作者同意，或僅記錄來源連結。
- 第三方內容依其各自授權；本 repo 的公開狀態不會取代原始授權。

## 公開內容與授權

本 repo 為公開儲存庫。請勿提交密碼、API 金鑰、私人文件或不宜公開的資料。

目前尚未為本 repo 的自製內容選定開源授權。公開可讀取不等於授予任意再散布權利；對外提供廣泛重用前應明確選定授權。
