# Changelog

## Unreleased

<!-- lang:en -->

### Fixed

- Deleting a template can now be undone, including restoring the template image file.
- Macro property changes, such as hotkeys and run mode options, can now be undone.
- The running overlay now shows the current nested loop count instead of staying on the outer loop.
- Template editor cards now keep their expanded or collapsed state after a template is updated.

<!-- lang:zh_tw -->

### 修正

- 刪除模板現在可以復原，並會一併還原模板圖片檔案。
- 巨集屬性變更現在可以復原，例如快捷鍵與執行模式選項。
- 執行浮動面板現在會顯示目前正在執行的巢狀迴圈次數，不再停留在外層迴圈。
- 更新模板後，模板編輯卡片現在會保留原本的展開或收合狀態。

<!-- lang:zh_cn -->

### 修复

- 删除模板现在可以撤销，并会一并还原模板图片文件。
- 宏属性变更现在可以撤销，例如快捷键和运行模式选项。
- 执行浮动面板现在会显示当前正在执行的嵌套循环次数，不再停留在外层循环。
- 更新模板后，模板编辑卡片现在会保留原本的展开或收合状态。

## v0.11.1

<!-- lang:en -->

### Fixed

- OCR is now working.

<!-- lang:zh_tw -->

### 修正

- OCR 現在可以正常運作了。

<!-- lang:zh_cn -->

### 修复

- OCR 现在可以正常运作了。

## v0.11.0

<!-- lang:en -->

### Added

- Added number recognition steps for selected screen areas, so macros can wait, branch, or repeat until a visible number reaches the target value.
- Added a Down/Up Delay setting to mouse click steps, so clicks can hold the button briefly before releasing.
- Macros now support user-defined variables with four types (text, number, boolean, key). Define variables in the macro properties panel, then switch any step property from Fixed to Variable mode to reference a variable instead of a hardcoded value. Changing a variable's value updates all steps that use it at once.

### Changed

- Duplicating or pasting steps now creates independent template copies instead of sharing the original template.
- Copying and pasting steps now includes any variables referenced by those steps, with automatic renaming when variable names conflict.
- Step descriptions in the step tree now show variable references as `${Label}`, so you can tell at a glance which properties are using variables.

### Fixed

- Hotkey-related translations ("Select a hotkey", "Press a key", "Remove") are now properly translated in both Traditional and Simplified Chinese.
- The new mouse click delay setting is now translated in both Traditional and Simplified Chinese.
- The text input field in Text Input steps no longer stretches to fill all available space, staying at a comfortable 3-line height instead.
- Re-capturing or replacing a template on one step no longer removes the template file when other steps also use that template.
- The running overlay no longer crashes when a macro starts before its first step is shown.
- Macro recording now starts reliably on some Windows systems where a compatibility issue prevented it from working.

<!-- lang:zh_tw -->

### 新增

- 新增選取畫面區域的數字辨識步驟，巨集可以等待、分支，或重複執行直到畫面上的數字達到目標值。
- 滑鼠點擊步驟新增按下/放開延遲設定，可讓按鈕短暫按住後再放開。
- 巨集現在支援使用者自訂變數，提供四種類型（文字、數字、布林值、按鍵）。在巨集屬性面板中定義變數後，可將任意步驟屬性從「固定」切換為「變數」模式，以參照變數取代手動輸入的值。修改變數值後，所有使用該變數的步驟都會同步更新。

### 變更

- 複製或貼上步驟現在會建立獨立的模板副本，而非共享原來模板。
- 複製貼上步驟時，現在會一併包含步驟所參照的變數，變數名稱衝突時會自動重新命名。
- 步驟樹中的步驟描述現在會以 `${標籤}` 格式顯示變數參照，讓您一眼看出哪些屬性使用了變數。

### 修正

- 快捷鍵相關翻譯（「選擇快捷鍵」、「按下按鍵」、「移除」）現已正確翻譯為正體中文。
- 新增的滑鼠點擊延遲設定現已正確翻譯為正體中文與簡體中文。
- 文字輸入步驟中的文字欄位不再撐滿所有可用高度，改為維持約 3 行高度的舒適大小。
- 重新截取或替換步驟的模板時，若其他步驟也使用相同模板，不再會誤刪模板檔案。
- 巨集剛開始執行、第一個步驟尚未顯示時，執行浮動面板不再當機。
- 修正部分 Windows 系統上的相容性問題，現在巨集錄製可確實啟動。

<!-- lang:zh_cn -->

### 新增

- 新增可选取画面区域的数字识别步骤，宏可以等待、分支，或重复执行直到画面上的数字达到目标值。
- 鼠标点击步骤新增按下/松开延迟设置，可让按钮短暂按住后再松开。
- 宏现在支持用户自定义变量，提供四种类型（文字、数字、布尔值、按键）。在宏属性面板中定义变量后，可将任意步骤属性从「固定」切换为「变量」模式，以引用变量取代手动输入的值。修改变量值后，所有使用该变量的步骤都会同步更新。

### 变更

- 复制或粘贴步骤现在会创建独立的模板副本，而非共享原来模板。
- 复制粘贴步骤时，现在会一并包含步骤所引用的变量，变量名称冲突时会自动重命名。
- 步骤树中的步骤描述现在会以 `${标签}` 格式显示变量引用，让您一眼看出哪些属性使用了变量。

### 修复

- 快捷键相关翻译（「选择快捷键」、「按下按键」、「移除」）现已正确翻译为简体中文。
- 新增的鼠标点击延迟设置现已正确翻译为繁体中文与简体中文。
- 文字输入步骤中的文字字段不再撑满所有可用高度，改为维持约 3 行高度的舒适大小。
- 重新截取或替换步骤的模板时，若其他步骤也使用相同模板，不再会误删模板文件。
- 宏刚开始执行、第一步尚未显示时，运行浮动面板不再崩溃。
- 修复部分 Windows 系统上的兼容性问题，现在宏录制可正常启动。

## v0.10.0

<!-- lang:en -->

### Added

- Hotkey picker dialog: click "Select a hotkey" to open a dialog with toggle buttons for modifier keys (Shift, Ctrl, Win, Alt) and a key capture field. Used in Settings, macro properties, and step key editing.
- Macro recording: click the Record button to capture keyboard and mouse actions outside the application, then stop to insert the recorded steps into your macro. The recording overlay shows elapsed time and event count, and typed text is recorded correctly for your keyboard layout.
- The status bar now shows elapsed time when a macro finishes or is stopped (e.g., `Done: MyMacro (01:23)`).
- Background Input: a new macro option (enabled by default) that sends keystrokes and mouse actions directly to the target window without switching focus. Turn it off to use normal foreground input when a game ignores background messages.
- Prevent Focus Loss: a new macro option that periodically keeps the target window from detecting that it lost focus, so the game won't pause when you click away. This may not work with all games.
- Each macro option (Gaming Mode, Background Input, Prevent Focus Loss) now has a tooltip icon explaining what it does.
- Multi-monitor support: the region selector, recording overlay, and template capture now work correctly regardless of which display the application or target window is on.

### Changed

- Mouse click step descriptions now use natural word order (e.g., "Left Click at ..." instead of "Click Left at ...").
- Keyboard shortcuts (paste, undo, delete, etc.) are now suppressed while any hotkey input field is focused, preventing accidental actions when editing hotkeys.
- The Tab key is now captured as a hotkey key instead of moving focus when a hotkey field is active.
- The theme dropdown in Settings now lists Light before Dark.
- Light and dark themes now use warmer accent colors for buttons, highlights, and other themed controls.
- When a macro is running, the right panel, File/Edit menus, and global actions (Settings, New Macro, Duplicate Macro, Import/Export, Macro Explorer) are now disabled to prevent changes that could affect the runner.
- "Pack Explorer" has been renamed to "Macro Explorer".

### Fixed

- Editing step notes and template labels can now be undone and redone correctly.
- The status bar message shown when a macro finishes with an error is now properly translatable.
- Step tree icons now update correctly when switching from dark theme to light theme.

<!-- lang:zh_tw -->

### 新增

- 快捷鍵選擇對話框：點擊「選擇快捷鍵」開啟對話框，內含修飾鍵（Shift、Ctrl、Win、Alt）切換按鈕與按鍵擷取欄位。適用於設定、巨集屬性與步驟按鍵編輯。
- 巨集錄製：按下「錄製」按鈕即可捕捉應用程式外部的鍵盤與滑鼠操作，停止後將錄製的步驟插入目前巨集。錄製浮動面板會顯示已耗時間與事件數量，且輸入的文字會根據你的鍵盤佈局正確錄製。
- 狀態列現在會在巨集完成或停止時顯示經過時間（例如 `完成：MyMacro（01:23）`）。
- 背景輸入：新增巨集選項（預設開啟），直接將按鍵和滑鼠操作送到目標視窗而不切換焦點。當遊戲忽略背景訊息時，可關閉此選項改用一般前景輸入。
- 防止失焦：新增巨集選項，定期防止目標視窗偵測失焦，讓你切換視窗時遊戲不會暫停。不一定適用所有遊戲。
- 每個巨集選項（遊戲模式、背景輸入、防止失焦）現在都有提示圖示說明其用途。
- 多螢幕支援：區域選擇器、錄製浮動面板和範本擷取現在無論應用程式或目標視窗在哪個螢幕上，都能正確運作。

### 變更

- 滑鼠點擊步驟描述現在使用自然語序（例如「左鍵點擊於 ...」取代「點擊左鍵於 ...」）。
- 當任何快捷鍵輸入欄位取得焦點時，鍵盤快捷鍵（貼上、復原、刪除等）會被暫時停用，避免編輯快捷鍵時誤觸操作。
- 在快捷鍵欄位使用時，Tab 鍵現在會被擷取為快捷鍵而非移動焦點。
- 設定中的主題下拉選單順序調整為淺色在深色之前。
- 淺色與深色主題現在會在按鈕、醒目提示和其他主題控制項使用較溫暖的強調色。
- 巨集執行期間，右側面板、檔案/編輯選單和全域操作（設定、新增巨集、複製巨集、匯入/匯出、巨集瀏覽器）現在會停用，防止變更影響執行中的巨集。
- 「Pack Explorer」已重新命名為「Macro Explorer」。

### 修正

- 編輯步驟備註與範本名稱後，現在可以正確復原與重做。
- 巨集因錯誤結束時顯示的狀態列訊息現在可以正確翻譯。
- 從深色主題切換到淺色主題時，步驟樹圖示現在會正確更新。

<!-- lang:zh_cn -->

### 新增

- 快捷键选择对话框：点击「选择快捷键」打开对话框，内含修饰键（Shift、Ctrl、Win、Alt）切换按钮与按键捕获字段。适用于设置、宏属性与步骤按键编辑。
- 宏录制：按下「录制」按钮即可捕捉应用程序外部的键盘与鼠标操作，停止后将录制的步骤插入当前宏。录制浮动面板会显示已用时间与事件数量，且输入的文字会根据你的键盘布局正确录制。
- 状态栏现在会在宏完成或停止时显示经过时间（例如 `完成：MyMacro（01:23）`）。
- 背景输入：新增宏选项（默认开启），直接将按键和鼠标操作发送到目标窗口而不切换焦点。当游戏忽略背景消息时，可关闭此选项改用常规前台输入。
- 防止失焦：新增宏选项，定期防止目标窗口检测失焦，让你切换窗口时游戏不会暂停。不一定适用于所有游戏。
- 每个宏选项（游戏模式、背景输入、防止失焦）现在都有提示图标说明其用途。
- 多显示器支持：区域选择器、录制浮动面板和模板捕获现在无论应用程序或目标窗口在哪个显示器上，都能正确运作。

### 变更

- 鼠标点击步骤描述现在使用自然语序（例如「左键点击于 ...」取代「点击左键于 ...」）。
- 当任何快捷键输入字段获得焦点时，键盘快捷键（粘贴、撤销、删除等）会被暂时禁用，避免编辑快捷键时误触操作。
- 在快捷键字段使用时，Tab 键现在会被捕获为快捷键而非移动焦点。
- 设置中的主题下拉菜单顺序调整为浅色在深色之前。
- 浅色与深色主题现在会在按钮、高亮和其他主题控件使用更温暖的强调色。
- 宏执行期间，右侧面板、文件/编辑菜单和全局操作（设置、新建宏、复制宏、导入/导出、宏浏览器）现在会禁用，防止变更影响运行中的宏。
- 「Pack Explorer」已重命名为「Macro Explorer」。

### 修复

- 编辑步骤备注与模板名称后，现在可以正确撤销与重做。
- 宏因错误结束时显示的状态栏消息现在可以正确翻译。
- 从深色主题切换到浅色主题时，步骤树图标现在会正确更新。

## v0.9.0

<!-- lang:en -->

### Added

- Pack Explorer now lets you choose an available macro language before importing a pack
- The status bar now shows what changed after undoing or redoing an edit.

### Fixed

- An unfinished translation entry for "Press a hotkey" in both Traditional and Simplified Chinese is now properly marked as complete.
- The translation of "Hotkey" now uses consistent terminology across all UI labels in both Traditional and Simplified Chinese.
- Deleting a step now also removes its template files and metadata when no other step in the same macro uses them.
- Adding a template to an if-any-image step can now be undone and redone correctly.
- Undoing a captured or picked template image now restores the template files correctly without deleting other templates from the same if-any-image step.
- Quickly adding multiple templates to an if-any-image step now creates distinct template entries instead of reusing the same timestamp ID.
- Pasting multiple steps that start with an if-any-image step now keeps the pasted steps at the same level instead of adding them to the first branch.

<!-- lang:zh_tw -->

### 新增

- Pack Explorer 現在可在匯入套件前選擇可用的巨集語言
- 狀態列現在會顯示復原或重做後變更了什麼。

### 修正

- 「Press a hotkey」的翻譯標記已補完，不再顯示為未完成。
- 「Hotkey」的翻譯已統一使用「快捷鍵」，設定與快捷鍵編輯器用詞一致。
- 刪除步驟時，如果同一個巨集中沒有其他步驟使用該範本，現在會一併移除範本檔案與資料。
- 在 if-any-image 步驟新增範本後，現在可以正確復原與重做。
- 復原擷取或選擇的範本圖片時，現在會正確還原範本檔案，不會刪除同一個 if-any-image 步驟中的其他範本。
- 快速在 if-any-image 步驟新增多個範本時，現在會建立不同的範本項目，不再重複使用同一個時間戳記 ID。
- 貼上以 if-any-image 步驟開頭的多個步驟時，現在會讓貼上的步驟保持在同一層，不會加入第一個分支。

<!-- lang:zh_cn -->

### 新增

- Pack Explorer 现在可在导入包前选择可用的宏语言
- 状态栏现在会显示撤销或重做后变更了什么。

### 修复

- 「Press a hotkey」的翻译标记已补完，不再显示为未完成。
- 「Hotkey」的翻译已统一使用「快捷键」，设置与快捷键编辑器用词一致。
- 删除步骤时，如果同一个宏中没有其他步骤使用该模板，现在会一并移除模板文件与数据。
- 在 if-any-image 步骤新增模板后，现在可以正确撤销与重做。
- 撤销捕获或选择的模板图片时，现在会正确还原模板文件，不会删除同一个 if-any-image 步骤中的其他模板。
- 快速在 if-any-image 步骤新增多个模板时，现在会创建不同的模板项目，不再重复使用同一个时间戳 ID。
- 粘贴以 if-any-image 步骤开头的多个步骤时，现在会让粘贴的步骤保持在同一层，不会加入第一个分支。

## v0.8.0

<!-- lang:en -->

### Added

- Macro execution can now be paused and resumed using a configurable hotkey (default: Ctrl+Alt+P) or the new pause button on the status overlay
- New "Pause/Resume Hotkey" setting in General settings for customizing the global pause hotkey

### Changed

- Status overlay now has separate pause and stop buttons instead of a single toggle button

### Fixed

- When picking a template image from file, the Capture Width and Capture Height fields now correctly show the physical screen resolution instead of the logical resolution (fixes template scaling mismatch on displays with HiDPI scaling like 150%)

<!-- lang:zh_tw -->

### 新增

- 巨集執行現在可使用可自訂的熱鍵（預設：Ctrl+Alt+P）或狀態浮窗上的暫停按鈕來暫停和恢復
- 通用設定中新增「暫停/繼續熱鍵」設定，可用於自訂全域暫停熱鍵

### 變更

- 狀態浮窗現在有獨立的暫停和停止按鈕，取代原本的單一切換按鈕

### 修正

- 從檔案選擇範本圖片時，擷取寬度與擷取高度欄位現在會正確顯示實體螢幕解析度而非邏輯解析度（修正啟用 HiDPI 縮放如 150% 時範本比對比例錯誤的問題）

<!-- lang:zh_cn -->

### 新增

- 宏执行现在可使用可自定义的快捷键（默认：Ctrl+Alt+P）或状态浮窗上的暂停按钮来暂停和恢复
- 通用设置中新增「暂停/继续快捷键」设置，可用于自定义全局暂停快捷键

### 变更

- 状态浮窗现在有独立的暂停和停止按钮，取代原本的单一切换按钮

### 修复

- 从文件选择模板图片时，捕获宽度与捕获高度字段现在会正确显示物理屏幕分辨率而非逻辑分辨率（修复启用 HiDPI 缩放如 150% 时模板匹配比例错误的问题）

## v0.7.0

<!-- lang:en -->

### Fixed

- If-image steps now correctly save the else branch so it is not lost after saving and reloading the macro
- Changing the target window for a macro now takes effect immediately without needing to restart the application
- When a target window is closed and reopened during macro execution, the macro now automatically re-finds it instead of getting stuck
- Error messages shown in the status bar when a macro finishes are now properly translated instead of showing raw internal codes like "window_not_found" or "wait_timeout"

### Added

- Text input steps can now type custom Unicode text with an optional delay between characters
- New mouse action steps: click at a coordinate or image center, move the cursor to a position, and scroll the mouse wheel
- Each macro now has a Gaming Mode toggle that can be turned off to skip template image scaling, useful for desktop automation where the window size stays the same
- Key steps now support modifier key combinations (Ctrl, Alt, Shift, Win), so you can record shortcuts like Ctrl+S or Ctrl+Shift+S with a single keystroke
- Template matching now supports color mode for more precise matching when images have distinct colors

<!-- lang:zh_tw -->

### 修正

- if-image 步驟現在能正確儲存 else 分支，儲存後重新載入巨集不再遺失 else 中的步驟
- 變更巨集的目標視窗現在會立即生效，不需要重啟應用程式
- 巨集執行期間若目標視窗被關閉再重新開啟，現在能自動重新找到視窗，不再卡住
- 巨集執行完成後顯示在狀態列的錯誤訊息現在已正確翻譯，不再顯示 "window_not_found" 或 "wait_timeout" 等內部程式碼

### 新增

- 文字輸入步驟現在可輸入自訂 Unicode 文字，並可設定每個字元之間的延遲
- 新增滑鼠動作步驟：點擊座標或圖片中心、移動游標到指定位置、滾動滑鼠滾輪
- 每個巨集現在具有遊戲模式開關，關閉後將跳過模板圖片縮放，適合視窗大小不變的桌面自動化場景
- 按鍵步驟現在支援修飾鍵組合（Ctrl、Alt、Shift、Win），可一次錄製 Ctrl+S 或 Ctrl+Shift+S 等快捷鍵
- 模板匹配現在支援彩色模式，當圖片具有明顯色彩時可提供更精確的匹配

<!-- lang:zh_cn -->

### 修复

- if-image 步骤现在能正确保存 else 分支，保存后重新加载宏不再丢失 else 中的步骤
- 变更宏的目标窗口现在会立即生效，不需要重启应用程序
- 宏执行期间若目标窗口被关闭再重新打开，现在能自动重新找到窗口，不再卡住
- 宏执行完成后显示在状态栏的错误消息现在已正确翻译，不再显示 "window_not_found" 或 "wait_timeout" 等内部代码

### 新增

- 文字输入步骤现在可输入自定义 Unicode 文字，并可设置每个字符之间的延迟
- 新增鼠标动作步骤：点击坐标或图片中心、移动光标到指定位置、滚动鼠标滚轮
- 每个宏现在具有游戏模式开关，关闭后将跳过模板图片缩放，适合窗口大小不变的桌面自动化场景
- 按键步骤现在支持修饰键组合（Ctrl、Alt、Shift、Win），可一次录制 Ctrl+S 或 Ctrl+Shift+S 等快捷键
- 模板匹配现在支持彩色模式，当图片具有明显色彩时可提供更精确的匹配

## v0.6.1

<!-- lang:en -->

### Fixed

- Old template branches in if-any-image steps are now properly removed after re-capturing or replacing a template image
- System language detection now reliably uses the system language and script settings, falling back to display language preferences when the regional format is set to a different language

<!-- lang:zh_tw -->

### 修正

- 重新擷取或更換 if-any-image 步驟中的模板圖片後，舊的模板分支現在會正確移除
- 系統語言偵測現在能可靠地使用系統語言與文字設定，當地區格式設為不同語言時會退回使用顯示語言偏好

<!-- lang:zh_cn -->

### 修复

- 重新捕获或替换 if-any-image 步骤中的模板图片后，旧的模板分支现在会正确移除
- 系统语言检测现在能可靠地使用系统语言与文字设置，当区域格式设为不同语言时会回退使用显示语言偏好

## v0.6.0

<!-- lang:en -->

### Added

- Clicking empty space in the step tree now shows the macro properties panel
- Numeric input fields now show a red error border when empty or invalid, and only save valid numbers instead of silently falling back to zero
- File menu now includes an "Open Macro Folder" option for quick access to macro files
- Step branches now have their own details panel with an add button, so steps can be added directly inside then/else, template, and grid navigation branches
- File menu now includes Pack Explorer, where you can browse official macro packs and import compatible macros directly

### Changed

- Step tree now displays branches (then/else, template branches, grid navigation) directly in the tree, making it easier to see and navigate step structure
- Wait image steps now show an on-timeout action dropdown in the right panel, letting you choose whether the macro stops or continues when the image is not found
- Settings are now saved automatically as you change them, removing the need to click a save button
- Dialog windows have been visually improved with clearer descriptions and better layout
- Templates in if-any-image steps are now grouped inside cards for better visibility and organization
- Icons and translated text now follow the selected theme and language more consistently throughout the app

### Fixed

- Right-clicking a macro now selects it before opening the context menu, so rename, duplicate, and delete actions always target the clicked macro
- Clicking on empty space in the step tree now deselects the current step and resets the toolbar buttons
- Toolbar buttons for deleting and moving steps now refresh correctly when the step selection changes
- Selecting multiple steps now disables the move up and move down buttons, since they only apply to a single step
- Selecting the first or last step now correctly disables the move up or move down button when no further movement is possible
- Changing the display language now automatically restarts the app, no manual restart needed
- Update dialog now displays correctly when using light theme
- Screen capture now falls back to a more compatible method when fast capture is unavailable, avoiding startup failures on unsupported devices

<!-- lang:zh_tw -->

### 新增

- 點擊步驟樹的空白區域現在會顯示巨集屬性面板
- 數字輸入欄位現在在空白或無效時會顯示紅色錯誤邊框，僅儲存有效數字，不再默默回退為零
- 檔案選單現在包含「開啟巨集資料夾」選項，可快速存取巨集檔案
- 步驟分支現在有自己的詳細面板和新增按鈕，可直接在 then/else、模板及網格導航分支內加入步驟
- 檔案選單現在包含 Pack Explorer，可瀏覽官方巨集包並直接匯入相容的巨集

### 變更

- 步驟樹現在直接在樹狀結構中顯示分支（then/else、模板分支、網格導航），更方便檢視及導覽步驟結構
- 等待圖片步驟的右側面板現在顯示逾時動作下拉選單，可選擇找不到圖片時停止或繼續執行
- 設定現在會隨變更自動儲存，不再需要點擊儲存按鈕
- 對話框視覺改進，加入更清晰的說明文字與更好的版面配置
- if-any-image 步驟中的模板現在以卡片方式分組顯示，提升可視性與組織性
- 圖示與翻譯文字現在會更一致地跟隨所選主題與語言顯示

### 修正

- 右鍵點擊巨集時現在會先選取該巨集再開啟選單，確保重新命名、複製、刪除操作永遠作用在點擊的巨集上
- 點擊步驟樹的空白區域現在會取消選取目前步驟，並重置工具列按鈕狀態
- 刪除、上移、下移步驟的工具列按鈕現在會在步驟選取變更時正確更新
- 選取多個步驟時現在會停用上移和下移按鈕，因為它們僅適用於單一步驟
- 選取第一個或最後一個步驟時現在會正確停用無法再移動方向的上移或下移按鈕
- 變更顯示語言後現在會自動重啟應用程式，無需手動重開
- 更新對話框在淺色主題下現在能正確顯示
- 快速螢幕擷取無法使用時，現在會改用相容性更高的方式，避免不支援的裝置啟動失敗

<!-- lang:zh_cn -->

### 新增

- 点击步骤树的空白区域现在会显示宏属性面板
- 数字输入字段现在在空白或无效时会显示红色错误边框，仅保存有效数字，不再静默回退为零
- 文件菜单现在包含「打开宏文件夹」选项，可快速访问宏文件
- 步骤分支现在有自己的详情面板和新增按钮，可直接在 then/else、模板及网格导航分支内加入步骤
- 文件菜单现在包含 Pack Explorer，可浏览官方宏包并直接导入兼容的宏

### 变更

- 步骤树现在直接在树状结构中显示分支（then/else、模板分支、网格导航），更方便查看及导航步骤结构
- 等待图片步骤的右侧面板现在显示超时动作下拉菜单，可选择找不到图片时停止或继续执行
- 设置现在会随变更自动保存，不再需要点击保存按钮
- 对话框视觉改进，加入更清晰的说明文字与更好的版面配置
- if-any-image 步骤中的模板现在以卡片方式分组显示，提升可见性与组织性
- 图标与翻译文字现在会更一致地跟随所选主题与语言显示

### 修复

- 右键点击宏时现在会先选中该宏再打开菜单，确保重命名、复制、删除操作始终作用在点击的宏上
- 点击步骤树的空白区域现在会取消选中当前步骤，并重置工具栏按钮状态
- 删除、上移、下移步骤的工具栏按钮现在会在步骤选中变更时正确更新
- 选中多个步骤时现在会禁用上移和下移按钮，因为它们仅适用于单一步骤
- 选中第一个或最后一个步骤时现在会正确禁用无法再移动方向的上移或下移按钮
- 变更显示语言后现在会自动重启应用程序，无需手动重启
- 更新对话框在浅色主题下现在能正确显示
- 快速屏幕捕获无法使用时，现在会改用兼容性更高的方式，避免不支持的设备启动失败

## v0.5.1

<!-- lang:en -->

### Fixed

- Macro hotkey and key-step inputs can now save Esc as the selected key instead of clearing the field

<!-- lang:zh_tw -->

### 修正

- 巨集快捷鍵與按鍵步驟輸入現在可以將 Esc 儲存為指定按鍵，不會再把欄位直接清空

<!-- lang:zh_cn -->

### 修复

- 宏快捷键与按键步骤输入现在可以将 Esc 保存为指定按键，不会再把字段直接清空

## v0.5.0

<!-- lang:en -->

### Changed

- Macro editor step list now uses a tree view, allowing nested steps (repeat, if_image, if_any_image, grid_nav) to be collapsed and expanded for better organization

### Fixed

- Running a macro now migrates legacy template resolution metadata before execution, so older templates keep matching at the resolution they were originally captured at
- Templates with missing or invalid legacy resolution metadata no longer silently fall back to the current screen resolution, avoiding incorrect scaling during image matching

<!-- lang:zh_tw -->

### 變更

- 巨集編輯器步驟列表現在使用樹狀檢視，允許巢狀步驟（重複、if_image、if_any_image、grid_nav）折疊與展開，以便更好地組織

### 修正

- 現在執行巨集前會先遷移舊版模板解析度中繼資料，讓舊模板仍能依照原本擷取時的解析度進行比對
- 缺少或損壞的舊版模板解析度中繼資料現在不會再悄悄改用目前螢幕解析度，避免影像比對時出現錯誤縮放

<!-- lang:zh_cn -->

### 变更

- 宏编辑器步骤列表现在使用树状视图，允许嵌套步骤（重复、if_image、if_any_image、grid_nav）折叠与展开，以便更好地组织

### 修复

- 现在执行宏前会先迁移旧版模板分辨率元数据，让旧模板仍能按照原本捕获时的分辨率进行匹配
- 缺少或损坏的旧版模板分辨率元数据现在不会再悄悄改用当前屏幕分辨率，避免图像匹配时出现错误缩放

## v0.4.0

<!-- lang:en -->

### Changed

- Foreground window checking is now automatic during macro execution, removing the need for a separate "Check Foreground" step
- Template capture resolution metadata is now stored inside the macro file instead of separate JSON files, with automatic migration for existing macros
- Beta channel now checks both stable and beta releases, always offering the highest available version instead of only the most recently published one
- Update dialog now shows the active channel when beta is selected
- "Open Download Page" now links to the specific release instead of always the latest release page

### Fixed

- Fixed a crash when adding a note containing only numbers to a step
- Fixed a crash on startup when the config file is empty or contains invalid JSON; the app now falls back to default settings
- Fixed screen capture failing with an unrecoverable error when the GPU is temporarily busy; the app now retries a few times before giving up
- Fixed update check always failing with a certificate error in the packaged build; the app now uses a bundled certificate store
- Fixed adding multiple steps in a row sometimes leaving the selection stuck on an earlier step instead of jumping to the newly added one

<!-- lang:zh_tw -->

### 變更

- 前景視窗檢查現在在巨集執行時自動進行，不再需要獨立的「確認前景」步驟
- 模板擷取解析度中繼資料現在儲存在巨集檔案內，而非獨立的 JSON 檔案，現有巨集會自動遷移
- Beta 頻道現在會同時檢查穩定版與測試版，永遠提供最高可用版本，而非僅檢查最新發布的一筆
- 更新對話框在選用 Beta 頻道時現在會顯示目前頻道
- 「開啟下載頁」現在會導向該版本的具體頁面，而非固定的最新版本頁面

### 修正

- 修正步驟備註僅包含數字時導致程式崩潰的問題
- 修正設定檔為空或 JSON 格式錯誤時程式無法啟動的問題，現在會自動套用預設值
- 修正 GPU 暫時忙碌時螢幕擷取直接失敗的問題，現在會自動重試數次後才放棄
- 修正打包版更新檢查必定因憑證錯誤而失敗的問題，現在使用內建憑證存取區
- 修正連續新增多個步驟時，選取項目有時沒有跳至最新步驟的問題

<!-- lang:zh_cn -->

### 变更

- 前景窗口检查现在在宏执行时自动进行，不再需要独立的「确认前台」步骤
- 模板捕获分辨率元数据现在存储在宏文件内，而非独立的 JSON 文件，现有宏会自动迁移
- Beta 频道现在会同时检查稳定版与测试版，永远提供最高可用版本，而非仅检查最新发布的一笔
- 更新对话框在选用 Beta 频道时现在会显示当前频道
- 「打开下载页」现在会导向该版本的具体页面，而非固定的最新版本页面

### 修复

- 修复步骤备注仅包含数字时导致程序崩溃的问题
- 修复配置文件为空或 JSON 格式错误时程序无法启动的问题，现在会自动套用默认值
- 修复 GPU 暂时忙碌时屏幕捕获直接失败的问题，现在会自动重试数次后才放弃
- 修复打包版更新检查必定因证书错误而失败的问题，现在使用内置证书存储区
- 修复连续新增多个步骤时，选中项目有时没有跳至最新步骤的问题

## v0.3.0

<!-- lang:en -->

### Added

- Template steps now show the capture resolution (width and height) in the right panel, so you can view and adjust the resolution at which the template was captured
- Steps now have an optional note field in the right panel to describe what each step does; notes are also shown inline in the step list with a tooltip on hover
- Key step input now uses key-press capture instead of manual typing, matching the hotkey field UX and preventing invalid keys
- Status bar now shows the total elapsed time after a macro finishes running

### Changed

- Refactored internal step data model from flat arrays to a proper tree structure (`StepNode` / `StepTree`), improving correctness of copy, paste, wrap-in-repeat, and move operations
- Completed migration of all step operations (delete, move, duplicate, add, paste) to use the tree model, removing all flat array helpers

### Fixed

- Fixed selection after pasting container steps pointing to the wrong step
- Fixed wrap in repeat not working when selecting a container step together with its child steps
- Fixed pasting container steps (repeat, if_image, if_any_image, grid_nav) duplicating their child steps
- Skipping a repeat now also skips all its child steps, and children's skip checkboxes are disabled while the repeat is skipped
- Fixed steps in grid nav branches (on_next_row / on_next_col) cannot be moved in or out of the block
- Fixed template labels and capture resolution metadata not being copied when copying and pasting steps
- Fixed right-click context menu not opening in the center panel when there are no steps
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

### 變更

- 重構內部步驟資料模型，從平坦陣列改為正式樹狀結構（`StepNode` / `StepTree`），提升複製、貼上、包進重複區塊及移動操作的正確性
- 完成所有步驟操作（刪除、移動、複製、新增、貼上）遷移至樹狀模型，移除所有平坦陣列輔助方法

### 修正

- 修正貼上容器步驟後選取的步驟不正確的問題
- 修正選取容器步驟及其子步驟時，「包進重複區塊」功能無法運作的問題
- 修正貼上容器步驟（repeat、if_image、if_any_image、grid_nav）時子步驟被重複貼上的問題
- 跳過重複區塊時現在會同時跳過所有子步驟，且子步驟的跳過核取方塊在重複區塊被跳過時會停用
- 修正網格導覽分支（on_next_row / on_next_col）中的步驟無法移入或移出區塊的問題
- 修正複製貼上步驟時，模板標籤及擷取解析度中繼資料未一併複製的問題
- 修正步驟為空時，中央面板無法開啟右鍵選單的問題
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

### 变更

- 重构内部步骤数据模型，从平坦数组改为正式树状结构（`StepNode` / `StepTree`），提升复制、粘贴、包进重复区块及移动操作的正确性
- 完成所有步骤操作（删除、移动、复制、新增、粘贴）迁移至树状模型，移除所有平坦数组辅助方法

### 修复

- 修复粘贴容器步骤后选中的步骤不正确的问题
- 修复选中容器步骤及其子步骤时，"包进重复区块"功能无法运作的问题
- 修复粘贴容器步骤（repeat、if_image、if_any_image、grid_nav）时子步骤被重复粘贴的问题
- 跳过重复区块时现在会同时跳过所有子步骤，且子步骤的跳过复选框在重复区块被跳过时会停用
- 修复网格导航分支（on_next_row / on_next_col）中的步骤无法移入或移出区块的问题
- 修复复制粘贴步骤时，模板标签及捕获分辨率元数据未一并复制的问题
- 修复步骤为空时，中央面板无法打开右键菜单的问题
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
