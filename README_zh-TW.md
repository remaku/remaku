# Remaku

開源、視覺化、以圖像辨識為核心的桌面巨集工具。

[下載最新版](https://github.com/remaku/remaku/releases/latest/download/Remaku_Setup.exe) · [remaku.com](https://remaku.com) · [Discord](https://discord.gg/MZfks29yTA)

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
- **鍵盤與滑鼠自動化** — 可送出按鍵組合、輸入 Unicode 文字、點擊、移動與滾輪操作
- **分支友善編輯器** — 巢狀步驟與分支會顯示在樹狀結構中，分支內可直接新增步驟
- **狀態列** — 顯示目前步驟、模板名稱，以及執行完成後的總執行時間
- **狀態浮窗** — 全螢幕遊戲上方顯示執行狀態的迷你浮動視窗，含播放/停止按鈕，位置自動記憶且不超出螢幕範圍
- **自動更新** — 啟動時檢查 GitHub Release，支援穩定版與測試版頻道
- **Pack Explorer** — 在應用程式內瀏覽官方巨集包並匯入相容巨集

## 支援的步驟類型

| 類型                               | 說明                                               |
| ---------------------------------- | -------------------------------------------------- |
| 按鍵 (key)                         | 模擬按下指定按鍵或修飾鍵組合，可設定按住時間       |
| 文字輸入 (text_input)              | 輸入自訂 Unicode 文字，可設定每個字元之間的延遲    |
| 滑鼠動作 (mouse_action)            | 點擊座標或圖片中心、移動游標到指定位置、滾動滾輪   |
| 等待時間 (delay)                   | 固定毫秒延遲                                       |
| 等待圖片 (wait_image)              | 等待模板圖片出現，可設定相似度門檻、超時與後續動作 |
| 等待任一圖片 (if_any_image)        | 同時監控多個模板，任一匹配即執行對應分支           |
| 條件分支 (if_image)                | 根據模板是否出現，執行 then 或 else 路徑           |
| 重複迴圈 (repeat)                  | 重複執行子步驟 N 次                                |
| 長按直到消失 (hold_key_until_gone) | 按住按鍵直到模板圖片消失才放開                     |
| 網格導航 (grid_nav)                | 逐格輪替操作（例如背包選單）                       |

## 步驟編輯功能

- **新增步驟**：從類型選單選擇，透過工具列按鈕或右鍵選單
- **刪除步驟**：支援多選刪除
- **複製貼上**：支援跨巨集剪下/複製/貼上步驟，模板圖片一併攜帶
- **移動步驟**：Alt+上/下移動步驟，智慧處理進入、離開與穿越區塊邊界
- **包裹進重複**：將選取步驟一次包裹進 repeat 區塊
- **分支編輯**：then/else、模板與網格導航分支都有自己的詳細面板與新增按鈕
- **樹狀檢視**：巢狀步驟與分支可展開或折疊，方便檢視流程
- **復原/重做**：50 步歷程，Ctrl+Z / Ctrl+Y
- **跳過開關**：每個步驟可單獨設為跳過，保留但不執行
- **備註**：為步驟加入可選的備註說明，會顯示在步驟列表中

## 影像辨識

使用 OpenCV 的 TM_CCOEFF_NORMED 演算法進行模板匹配。啟用遊戲模式時，模板會依視窗大小自動縮放；若用於視窗大小固定的桌面自動化，可關閉遊戲模式避免縮放。可在屬性面板中調整相似度門檻 (0–100%)，也可在需要明顯色彩判斷時啟用彩色模式。

### 模板管理

- 從螢幕截取區域作為模板（半透明全螢幕拖曳選取工具）
- 從檔案系統挑選 PNG 圖片作為模板
- 屬性面板中預覽模板圖片
- 擷取解析度顯示：顯示模板擷取時的寬度與高度
- 可對色彩明顯的模板啟用彩色匹配
- 模板重新命名與刪除
- 模板與巨集合併儲存，匯出時一併打包

## 視窗管理

- 依標題自動尋找目標視窗，支援部分匹配
- 下拉選單列出所有可見視窗
- 擷取視窗客戶區域（扣除邊框與標題列）
- 背景擷取與輸入：選定目標視窗後，不需要保持焦點也能持續執行
- 每個巨集可切換背景輸入或一般輸入，也可向目標視窗送出類似焦點的訊息，協助部分程式避免進入暫停畫面
- 巨集執行期間若目標視窗關閉後重新開啟，會自動重新尋找目標視窗
- 權限不一致警告：若目標視窗以管理員權限執行但 Remaku 沒有，會顯示警告（UIPI 會阻擋 SendInput）

## 設定

### 巨集

| 項目     | 說明                                                   |
| -------- | ------------------------------------------------------ |
| 目標視窗 | 執行巨集前 Remaku 要尋找的視窗標題                     |
| 熱鍵     | 此巨集專用的全域快捷鍵                                 |
| 遊戲模式 | 為遊戲啟用模板縮放；固定大小的桌面自動化流程可將其關閉 |

### 一般

| 項目         | 說明                                  |
| ------------ | ------------------------------------- |
| 最上層顯示   | 讓 Remaku 視窗保持在所有視窗最上方    |
| 開機檢查更新 | 啟動時自動檢查 GitHub Release         |
| 更新頻道     | stable（穩定版）或 beta（測試版）     |
| 主題         | 跟隨系統、淺色、深色                  |
| 語言         | 自動偵測、繁體中文、簡體中文、English |

### 擷取

| 項目 | 說明         |
| ---- | ------------ |
| FPS  | 每秒擷取幀數 |

### 輸入

| 項目     | 說明                                                  |
| -------- | ----------------------------------------------------- |
| 抖動毫秒 | 每次按鍵加入隨機延遲範圍 (ms)，避免被偵測為機器人操作 |

### 其他

- 顯示目前已跳過的更新版本，可一鍵清除以重新提示更新

## 巨集包

- 從檔案選單開啟 Pack Explorer
- 在 Remaku 內瀏覽官方巨集包
- 將相容巨集直接匯入本機巨集資料夾

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
remaku/
  main.py                         # 進入點，初始化設定與啟動主視窗
  paths.py                        # 檔案路徑工具
  theme.py                        # 主題管理
  version.py                      # 版本資訊（從 pyproject.toml 讀取）
  controllers/
    home_controller.py            # 主編輯器控制器（步驟編輯、巨集管理）
    main_controller.py            # 應用層控制器（選單、更新、視窗）
    pack_explorer_controller.py   # Pack Explorer 瀏覽與匯入邏輯
    settings_controller.py        # 設定頁面控制器
  core/
    capture.py                    # 畫面擷取（BetterCam / DXGI）
    dialogs.py                    # 原生對話框輔助工具
    event_bus.py                  # 全域事件系統
    i18n.py                       # 多國語言
    keys.py                       # 鍵盤輸入模擬（pydirectinput）
    vision.py                     # OpenCV 影像辨識（模板匹配）
    window.py                     # Windows 視窗管理（尋找、前景、權限檢查）
  models/
    config_model.py               # 設定資料模型
    macro_model.py                # 巨集資料模型
    pack_model.py                 # 巨集包目錄模型
    step_dict.py                  # 步驟序列化／反序列化
    step_node.py                  # 步驟樹節點模型，含父子參照
    step_tree.py                  # 步驟樹管理器，處理巨集步驟操作
  resources/
    icon.py                       # SVG 圖示引擎（Lucide 圖示）
    resources.qrc                 # Qt 資源檔
    resources_rc.py               # 已編譯的 Qt 資源
    icons/                        # SVG 圖示檔案
    images/                       # 圖片資源（logo.png）
    locales/                      # Qt 翻譯檔（.ts / .qm）
  services/
    engine.py                     # JSON 巨集解析與執行引擎
    macro_import_service.py       # 巨集匯入／匯出（ZIP）邏輯
    macro_runner.py               # 巨集執行器（含執行緒管理）
    migration.py                  # 舊版資料遷移
    pack_service.py               # 巨集包目錄擷取與管理
    updater.py                    # 自動更新檢查與安裝
  views/
    home_view.py                  # 主編輯器檢視（三欄介面）
    main_window.py                # 主應用程式視窗
    pack_explorer_view.py         # Pack Explorer 介面
    region_selector.py            # 螢幕區域選取工具
    settings_view.py              # 設定頁面介面
    components/
      about_dialog.py             # 關於對話框
      center_panel.py             # 中央面板（步驟樹）
      confirm_dialog.py           # 確認對話框
      elided_label.py             # 文字省略標籤元件
      left_panel.py               # 左側面板（巨集列表）
      message_dialog.py           # 訊息對話框
      new_macro_dialog.py         # 新增巨集對話框
      overlay.py                  # 狀態浮窗元件
      rename_macro_dialog.py      # 重新命名巨集對話框
      right_panel.py              # 右側面板（步驟屬性）
      step_menu.py                # 步驟類型右鍵選單
      template_editor.py          # 模板編輯器元件
      toolbar.py                  # 工具列（步驟操作）
      update_dialog.py            # 更新對話框（含更新說明）
tests/
  controllers/                    # 控制器單元測試
  core/                           # 核心模組單元測試
  models/                         # 模型單元測試
  services/                       # 服務單元測試
  views/                          # 檢視單元測試
    components/                   # 元件單元測試
```

### 快速開始

`Makefile` 提供常用指令。執行 `make` 可查看所有可用目標。

```powershell
make setup        # 建立虛擬環境並安裝依賴
make dev          # 熱重載執行（需要 nodemon）
make test         # 執行測試（含覆蓋率報表）
make lint         # 執行 ruff 程式碼檢查
make format       # 執行 ruff 格式化
make format-check # 檢查格式但不變更
make typecheck    # 執行 pyright 型別檢查
make check-all    # 執行 lint、格式檢查、型別檢查與測試
make translate    # 更新並編譯翻譯檔案
make build        # 建置安裝程式（PyInstaller + Inno Setup）
make clean        # 清除所有建置產物與快取
```

## 支持

如果這個工具對你有幫助，歡迎請我喝杯咖啡

[![GitHub Sponsors](https://img.shields.io/badge/GitHub%20Sponsors-support-ea4aaa?logo=githubsponsors)](https://github.com/sponsors/nelsonlaidev)
[![Buy Me A Coffee](https://img.shields.io/badge/Buy%20Me%20A%20Coffee-support-yellow?logo=buymeacoffee)](https://buymeacoffee.com/nelsonlaidev)

## 授權

[AGPL-3.0](LICENSE)
