# Remaku

開源、視覺化、以圖像辨識為核心的桌面巨集工具。

[下載最新版](https://github.com/remaku/remaku/releases/latest/download/Remaku_Setup.exe) · [remaku.com](https://remaku.com) · [Discord](https://discord.gg/ncK4mhPkwt)

[English](README.md) | [简体中文](README_zh-CN.md)

## 安裝注意事項

首次執行時，Windows SmartScreen 可能會顯示「Windows 已保護您的電腦」警告，點擊「其他資訊」→「仍要執行」即可正常執行。

這個警告無害，原因是程式沒有經過程式碼簽章。本專案是開源軟體，程式碼簽章憑證每年需要 $200 美元以上，因此目前沒有簽章。

## 特色

- **不用寫程式** — 列表式 UI 組合動作，支援拖拉排序與右鍵選單
- **圖像辨識驅動** — 截圖當模板，比對畫面決定何時觸發動作
- **輕量單一 exe** — 不需要額外的 runtime 環境
- **開源透明** — 程式碼完全公開，社群可審計與貢獻
- **JSON 流程格式** — 匯入/匯出 ZIP，社群分享即用
- **全域快捷鍵** — 每個巨集可設定獨立熱鍵，一鍵觸發
- **自動更新** — 啟動時檢查 GitHub Release，支援穩定版與測試版頻道

## 支援的步驟類型

| 類型                               | 說明                                     |
| ---------------------------------- | ---------------------------------------- |
| 按鍵 (key)                         | 模擬按下指定按鍵，可設定按住時間         |
| 等待時間 (delay)                   | 固定毫秒延遲                             |
| 等待圖片 (wait_image)              | 等待模板圖片出現，可設定相似度門檻與超時 |
| 等待任一圖片 (if_any_image)        | 同時監控多個模板，任一匹配即執行對應分支 |
| 條件分支 (if_image)                | 根據模板是否出現，執行 then 或 else 路徑 |
| 重複迴圈 (repeat)                  | 重複執行子步驟 N 次                      |
| 長按直到消失 (hold_key_until_gone) | 按住按鍵直到模板圖片消失才放開           |
| 確認前景 (foreground)              | 等待目標視窗回到前景                     |
| 網格導航 (grid_nav)                | 逐格輪替操作（例如背包選單）             |

## 步驟編輯功能

- **新增步驟**：從類型選單選擇，透過工具列按鈕或右鍵選單
- **刪除步驟**：支援多選刪除
- **複製貼上**：支援跨巨集剪下/複製/貼上步驟，模板圖片一併攜帶
- **移動步驟**：Alt+上/下移動步驟，智慧處理進入、離開與穿越區塊邊界
- **包裹進重複**：將選取步驟一次包裹進 repeat 區塊
- **復原/重做**：50 步歷程，Ctrl+Z / Ctrl+Y
- **跳過開關**：每個步驟可單獨設為跳過，保留但不執行

## 影像辨識

使用 OpenCV 的 TM_CCOEFF_NORMED 演算法進行模板匹配。若模板大於畫面，會自動按比例縮小。可在屬性面板中調整相似度門檻 (0–100%)。

### 模板管理

- 從螢幕截取區域作為模板（半透明全螢幕拖曳選取工具）
- 從檔案系統挑選 PNG 圖片作為模板
- 屬性面板中預覽模板圖片
- 模板重新命名與刪除
- 模板與巨集合併儲存，匯出時一併打包

## 視窗管理

- 依標題自動尋找目標視窗，支援部分匹配
- 下拉選單列出所有可見視窗
- 擷取視窗客戶區域（扣除邊框與標題列）
- 前景偵測：非前景時自動等待
- 權限不一致警告：若目標視窗以管理員權限執行但 Remaku 沒有，會顯示警告（UIPI 會阻擋 SendInput）

## 設定

### 一般

| 項目         | 說明                                  |
| ------------ | ------------------------------------- |
| 最上層顯示   | 讓 Remaku 視窗保持在所有視窗最上方    |
| 開機檢查更新 | 啟動時自動檢查 GitHub Release         |
| 更新頻道     | stable（穩定版）或 beta（測試版）     |
| 主題         | 跟隨系統、淺色、深色                  |
| 語言         | 自動偵測、繁體中文、簡體中文、English |

### 擷取

| 項目    | 說明                     |
| ------- | ------------------------ |
| FPS     | 每秒擷取幀數             |

### 輸入

| 項目     | 說明                                                  |
| -------- | ----------------------------------------------------- |
| 抖動毫秒 | 每次按鍵加入隨機延遲範圍 (ms)，避免被偵測為機器人操作 |

### 其他

- 顯示目前已跳過的更新版本，可一鍵清除以重新提示更新

## 自動更新機制

- 透過 GitHub API 檢查最新 Release 版本
- 更新對話框顯示 Release Notes（Markdown 格式）
- 支援直接下載安裝程式，含進度條
- 一鍵靜默安裝：下載完成後自動以 `/VERYSILENT` 參數啟動安裝程式並關閉 Remaku，安裝完成後新版會自動啟動
- 可選擇「跳過此版本」，該版本不再提示

## 鍵盤快捷鍵

| 快捷鍵       | 功能         |
| ------------ | ------------ |
| Ctrl+N       | 新增巨集     |
| Ctrl+,       | 開啟設定     |
| Ctrl+Shift+N | 新增步驟     |
| Delete       | 刪除所選步驟 |
| Alt+上       | 步驟上移     |
| Alt+下       | 步驟下移     |
| Ctrl+Z       | 復原         |
| Ctrl+Y       | 重做         |
| Ctrl+D       | 複製步驟     |
| Ctrl+C       | 複製         |
| Ctrl+X       | 剪下         |
| Ctrl+V       | 貼上         |

## 巨集檔案位置

所有巨集、模板與設定檔儲存在 `Documents\remaku\` 目錄下：

```
Documents\remaku\
  config.json        # 應用程式設定
  macros\            # 巨集 JSON 檔案
    1680000000.json
  templates\         # 模板 PNG 圖片
    <巨集名稱>\
      1680000001.png
  logs\              # 執行紀錄
    remaku.log
```

## 開發

需要 Python 3.12 與 [uv](https://docs.astral.sh/uv/)。GUI 使用 PySide6 (Qt6) 與 qfluentwidgets。

### 專案結構

```
src/
  main.py              # 進入點，初始化設定與啟動主視窗
  main_window.py       # 主視窗，三欄介面、選單、步驟編輯
  runner.py            # 步驟執行器基礎類別，管理執行緒與狀態
  macro_engine.py      # JSON 巨集解析與執行引擎
  vision.py            # OpenCV 影像辨識（模板匹配）
  capture.py           # 畫面擷取（BetterCam / DXGI）
  keys.py              # 鍵盤輸入模擬（pydirectinput）
  window.py            # Windows 視窗管理（尋找、前景、權限檢查）
  region_selector.py   # 螢幕區域選取工具
  config.py            # 設定檔讀寫
  settings.py          # 設定頁面介面
  updater.py           # 自動更新檢查與安裝
  version.py           # 版本資訊（從 pyproject.toml 讀取）
  icons.py             # SVG 圖示引擎（Lucide 圖示）
  i18n/                # 多國語言翻譯檔案
    __init__.py
    zh_tw.json
    zh_cn.json
    en.json
```

### 從原始碼執行

```powershell
uv sync
uv run src/main.py
```

### 程式碼檢查

```powershell
uv run ruff check --fix src
uv run ruff format src
```

### 建置 .exe

```powershell
.\build_exe.ps1
```

建置流程使用 PyInstaller 打包成單一執行檔，並以 Inno Setup (`iscc`) 建立安裝程式。

## 支持

如果這個工具對你有幫助，歡迎請我喝杯咖啡

[![GitHub Sponsors](https://img.shields.io/badge/GitHub%20Sponsors-support-ea4aaa?logo=githubsponsors)](https://github.com/sponsors/nelsonlaidev)
[![Buy Me A Coffee](https://img.shields.io/badge/Buy%20Me%20A%20Coffee-support-yellow?logo=buymeacoffee)](https://buymeacoffee.com/nelsonlaidev)

## 授權

[AGPL-3.0](LICENSE)
