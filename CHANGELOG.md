# Changelog

## v0.1.2-beta.3

<!-- lang:en -->

### Fixed

- Update checker now correctly distinguishes between different beta versions (e.g. beta.1 vs beta.2)

<!-- lang:zh_tw -->

### 修正

- 更新檢查現在能正確區分不同 beta 版本（如 beta.1 vs beta.2）

<!-- lang:zh_cn -->

### 修复

- 更新检查现在能正确区分不同 beta 版本（如 beta.1 vs beta.2）

## v0.1.2-beta.2

<!-- lang:en -->

### Added

- Drag-and-drop reordering for macro list, order is saved automatically

### Fixed

- Right-click menu on macro list now targets the clicked macro instead of the selected one

<!-- lang:zh_tw -->

### 新增

- 巨集列表支援拖拉排序，順序自動儲存

### 修正

- 右鍵選單現在會作用在點擊的巨集上，而非目前選取的巨集

<!-- lang:zh_cn -->

### 新增

- 宏列表支持拖拉排序，顺序自动保存

### 修复

- 右键菜单现在会作用在点击的宏上，而非当前选中的宏

## v0.1.2-beta.1

<!-- lang:en -->

### Fixed

- Update checker now correctly detects new versions when running a beta release
- Beta channel users can now see stable updates as well

<!-- lang:zh_tw -->

### 修正

- 更新檢查現在能在 beta 版本下正確偵測新版本
- Beta 頻道使用者現在也能看到穩定版更新

<!-- lang:zh_cn -->

### 修复

- 更新检查现在能在 beta 版本下正确检测新版本
- Beta 频道用户现在也能看到稳定版更新

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
