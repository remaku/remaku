# Changelog

## Unreleased

<!-- lang:en -->

### Added

- Template steps now show the capture resolution (width and height) in the right panel, so you can view and adjust the resolution at which the template was captured
- Steps now have an optional note field in the right panel to describe what each step does; notes are also shown inline in the step list with a tooltip on hover
- Key step input now uses key-press capture instead of manual typing, matching the hotkey field UX and preventing invalid keys
- Status bar now shows the total elapsed time after a macro finishes running

### Fixed

- Fixed target window selection not being saved when changing macros
- Templates without capture resolution metadata now automatically get a metadata file created when the macro is saved or loaded, preventing silent scaling issues
- Fixed step list selection persisting when switching between macros
- Fixed target window not waiting for foreground focus before running, which could send keystrokes to the wrong window

<!-- lang:zh_tw -->

### 新增

- 模板步驟的右側面板現在顯示擷取解析度（寬度和高度），可檢視並調整模板擷取時的解析度
- 步驟現在可在右側面板加入備註來說明步驟用途；備註也會顯示在步驟列表中，滑鼠懸停時以工具提示顯示
- 按鍵步驟現在使用按鍵捕捉取代手動輸入，與快捷鍵欄位體驗一致且無法輸入無效按鍵
- 狀態列現在會在巨集執行完成後顯示總執行時間

### 修正

- 修正切換巨集時，目標視窗選項無法儲存的問題
- 缺少擷取解析度中繼資料的模板現在會在儲存或載入巨集時自動補建，避免無聲的縮放問題
- 修正切換巨集時步驟列表選擇狀態殘留的問題
- 修正指定目標視窗時未等待視窗取得前景焦點的問題，避免按鍵發送到錯誤的視窗

<!-- lang:zh_cn -->

### 新增

- 模板步骤的右侧面板现在显示捕获分辨率（宽度和高度），可查看并调整模板捕获时的分辨率
- 步骤现在可在右侧面板添加备注来说明步骤用途；备注也会显示在步骤列表中，鼠标悬停时以工具提示显示
- 按键步骤现在使用按键捕捉取代手动输入，与快捷键字段体验一致且无法输入无效按键
- 状态栏现在会在宏执行完成后显示总执行时间

### 修复

- 修复切换宏时，目标窗口选项无法保存的问题
- 缺少捕获分辨率元数据的模板现在会在保存或加载宏时自动创建，避免静默的缩放问题
- 修复切换宏时步骤列表选择状态残留的问题
- 修复指定目标窗口时未等待窗口获得前台焦点的问题，避免按键发送到错误的窗口

## v0.2.0

<!-- lang:en -->

### Added

- Status overlay: a floating mini status bar that shows on top of fullscreen games with play/stop controls
- Overlay position is remembered and automatically kept within screen bounds

### Changed

- Status bar now shows the current step number, step summary, and which template is being compared

### Fixed

- Fixed a crash when pressing Enter in the step properties panel
- Fixed a crash when the target window is partially or fully outside the screen
- Discord invite link updated to a working one

<!-- lang:zh_tw -->

### 新增

- 狀態浮窗：全螢幕遊戲上方顯示執行狀態的迷你浮動視窗，含播放/停止按鈕
- 浮窗位置會自動記憶，且不會超出螢幕範圍

### 變更

- 狀態列現在會顯示目前步驟編號、步驟摘要，以及正在比對的模板名稱

### 修正

- 修正在步驟屬性面板按 Enter 時程式閃退的問題
- 修正目標視窗部分或完全超出螢幕時程式閃退的問題
- 更新了失效的 Discord 邀請連結

<!-- lang:zh_cn -->

### 新增

- 状态浮窗：全屏游戏上方显示运行状态的迷你浮动窗口，含播放/停止按钮
- 浮窗位置会自动记忆，且不会超出屏幕范围

### 变更

- 状态栏现在会显示当前步骤编号、步骤摘要，以及正在比对的模板名称

### 修复

- 修复在步骤属性面板按 Enter 时程序崩溃的问题
- 修复目标窗口部分或完全超出屏幕时程序崩溃的问题
- 更新了失效的 Discord 邀请链接

## v0.1.6

<!-- lang:en -->

### Fixed

- Loop counter in the status bar now shows correctly when running a macro more than once

<!-- lang:zh_tw -->

### 修正

- 重複執行巨集時，狀態列的迴圈次數現在能正確顯示

<!-- lang:zh_cn -->

### 修复

- 重复执行宏时，状态栏的循环次数现在能正确显示

## v0.1.5

<!-- lang:en -->

### Fixed

- Window now has rounded corners and is resizable in the production build

<!-- lang:zh_tw -->

### 修正

- 正式版視窗現在有圓角且可調整大小

<!-- lang:zh_cn -->

### 修复

- 正式版窗口现在有圆角且可调整大小

## v0.1.4

<!-- lang:en -->

### Fixed

- Templates picked from file now support automatic scaling across different screen resolutions

<!-- lang:zh_tw -->

### 修正

- 從檔案選取的模板現在支援不同螢幕解析度下的自動縮放

<!-- lang:zh_cn -->

### 修复

- 从文件选取的模板现在支持不同屏幕分辨率下的自动缩放

## v0.1.3

<!-- lang:en -->

### Fixed

- Auto-check for updates on startup now actually works

<!-- lang:zh_tw -->

### 修正

- 啟動時自動檢查更新現在能正常運作

<!-- lang:zh_cn -->

### 修复

- 启动时自动检查更新现在能正常运作

## v0.1.2

<!-- lang:en -->

### Added

- Drag-and-drop reordering for macro list, order is saved automatically
- Undo/redo buttons in toolbar with disabled state when unavailable

### Changed

- Shortened "Open Logs Folder" menu label to "Open Logs"

### Fixed

- Update checker now correctly detects new versions when running a beta release
- Update checker now correctly distinguishes between different beta versions
- Right-click menu on macro list now targets the clicked macro instead of the selected one

<!-- lang:zh_tw -->

### 新增

- 巨集列表支援拖拉排序，順序自動儲存
- 工具列新增復原/重做按鈕，無可用操作時自動停用

### 變更

- 「開啟日誌資料夾」選單文字縮短為「開啟日誌」

### 修正

- 更新檢查現在能正確偵測新版本
- 更新檢查現在能正確區分不同 beta 版本
- 右鍵選單現在會作用在點擊的巨集上，而非目前選取的巨集

<!-- lang:zh_cn -->

### 新增

- 宏列表支持拖拉排序，顺序自动保存
- 工具栏新增撤销/重做按钮，无可用操作时自动禁用

### 变更

- 「打开日志文件夹」菜单文字缩短为「打开日志」

### 修复

- 更新检查现在能正确检测新版本
- 更新检查现在能正确区分不同 beta 版本
- 右键菜单现在会作用在点击的宏上，而非当前选中的宏

## v0.1.1

<!-- lang:en -->

### Added

- "Open Logs Folder" option in Help menu

### Fixed

- Template matching now works correctly across different screen resolutions
- Imported macro packs now include resolution metadata for proper scaling
- Update dialog now shows release notes in the correct language

### Changed

- Default similarity threshold lowered from 95% to 85% for more flexible matching
- Improved spacing in the update dialog for better readability

<!-- lang:zh_tw -->

### 新增

- 說明選單新增「開啟日誌資料夾」選項

### 修正

- 模板比對現在能在不同螢幕解析度下正確運作
- 匯入的巨集包現在會包含解析度資訊以正確縮放
- 更新對話框現在會顯示正確語言的更新說明

### 變更

- 預設相似度門檻從 95% 降至 85%，提升匹配彈性
- 改善更新對話框的間距，提升可讀性

<!-- lang:zh_cn -->

### 新增

- 帮助菜单新增「打开日志文件夹」选项

### 修复

- 模板匹配现在能在不同屏幕分辨率下正确运作
- 导入的宏包现在会包含分辨率信息以正确缩放
- 更新对话框现在会显示正确语言的更新说明

### 变更

- 默认相似度阈值从 95% 降至 85%，提升匹配弹性
- 改善更新对话框的间距，提升可读性

## v0.1.0

<!-- lang:en -->

### Added

- List-based UI for composing macro actions with drag-and-drop reordering
- Image recognition driven: capture screenshots as templates, match against screen to trigger actions
- Supported step types: key, delay, wait image, wait any image, conditional branch, repeat loop, hold key until gone, foreground check, grid navigation
- Cut/copy/paste steps across macros with templates carried along
- Alt+Up/Down to move steps with smart block boundary handling
- Undo/redo (50-step history)
- Screen region capture as templates
- Global hotkeys with independent hotkey per macro
- Auto update with stable and beta channels
- Multi-language support: Traditional Chinese, Simplified Chinese, English
- Import/export macros as ZIP

<!-- lang:zh_tw -->

### 新增

- 列表式 UI 組合巨集動作，支援拖拉排序
- 圖像辨識驅動：截圖當模板，比對畫面觸發動作
- 支援步驟類型：按鍵、等待時間、等待圖片、等待任一圖片、條件分支、重複迴圈、長按直到消失、確認前景、網格導航
- 步驟剪下/複製/貼上，跨巨集模板一併攜帶
- Alt+上/下移動步驟，智慧處理區塊邊界
- 復原/重做（50 步歷程）
- 螢幕截取區域作為模板
- 全域快捷鍵，每個巨集獨立熱鍵
- 自動更新，支援穩定版與測試版頻道
- 多國語言支援：繁體中文、簡體中文、English
- 匯入/匯出 ZIP 格式巨集

<!-- lang:zh_cn -->

### 新增

- 列表式 UI 组合宏动作，支持拖拉排序
- 图像识别驱动：截图当模板，比对画面触发动作
- 支持步骤类型：按键、等待时间、等待图片、等待任一图片、条件分支、重复循环、长按直到消失、确认前景、网格导航
- 步骤剪切/复制/粘贴，跨宏模板一并携带
- Alt+上/下移动步骤，智能处理区块边界
- 撤销/重做（50 步历程）
- 屏幕截取区域作为模板
- 全局快捷键，每个宏独立热键
- 自动更新，支持稳定版与测试版频道
- 多语言支持：繁体中文、简体中文、English
- 导入/导出 ZIP 格式宏
