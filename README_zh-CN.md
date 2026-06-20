# Remaku

开源、可视化、以图像识别为核心的桌面宏工具。

[下载最新版](https://github.com/remaku/remaku/releases/latest/download/Remaku_Setup.exe) · [remaku.com](https://remaku.com) · [Discord](https://discord.gg/MZfks29yTA)

[English](README.md) | [繁體中文](README_zh-TW.md)

## 安装注意事项

首次运行时，Windows SmartScreen 可能会显示"Windows 已保护你的电脑"警告，点击"更多信息"->"仍要运行"即可正常执行。

这个警告无害，原因是程序没有经过代码签名。本项目是开源软件，代码签名证书每年需要 $200 美元以上，因此目前没有签名。

## 特色

- **不用写代码** -- 列表式 UI 组合动作，支持拖拽排序与右键菜单
- **图像识别驱动** -- 截图当模板，比对画面决定何时触发动作
- **轻量单一 exe** -- 不需要额外的 runtime 环境
- **开源透明** -- 代码完全公开，社区可审计与贡献
- **JSON 流程格式** -- 导入/导出 ZIP，社区分享即用
- **全局快捷键** -- 每个宏可设定独立热键，一键触发
- **键盘与鼠标自动化** -- 可发送按键组合、输入 Unicode 文本、点击、移动与滚轮操作
- **分支友好编辑器** -- 嵌套步骤与分支会显示在树状结构中，分支内可直接添加步骤
- **状态栏** -- 显示当前步骤、模板名称，以及执行完成后的总执行时间
- **状态浮窗** -- 全屏游戏上方显示运行状态的迷你浮动窗口，含播放/停止按钮，位置自动记忆且不超出屏幕范围
- **宏录制** -- 从应用程序外部录制键盘与鼠标操作，转换为宏步骤
- **自动更新** -- 启动时检查 GitHub Release，支持稳定版与测试版频道
- **Macro Explorer** -- 在应用程序内浏览官方宏包并导入兼容宏

## 支持的步骤类型

| 类型                               | 说明                                               |
| ---------------------------------- | -------------------------------------------------- |
| 按键 (key)                         | 模拟按下指定按键或修饰键组合，可设定按住时间       |
| 文本输入 (text_input)              | 输入自定义 Unicode 文本，可设定每个字符之间的延迟  |
| 鼠标点击 (mouse_click)             | 点击坐标或模板图片中心                             |
| 鼠标移动 (mouse_move)              | 移动光标到指定坐标或模板图片中心                   |
| 鼠标滚轮 (mouse_scroll)            | 滚动鼠标滚轮指定格数                               |
| 等待时间 (delay)                   | 固定毫秒延迟                                       |
| 等待图片 (wait_image)              | 等待模板图片出现，可设定相似度阈值、超时与后续动作 |
| 等待任一图片 (if_any_image)        | 同时监控多个模板，任一匹配即执行对应分支           |
| 条件分支 (if_image)                | 根据模板是否出现，执行 then 或 else 路径           |
| 重复循环 (repeat)                  | 重复执行子步骤 N 次                                |
| 长按直到消失 (hold_key_until_gone) | 按住按键直到模板图片消失才放开                     |
| 网格导航 (grid_nav)                | 逐格轮替操作（例如背包菜单）                       |

## 步骤编辑功能

- **添加步骤**：从类型菜单选择，通过工具栏按钮或右键菜单
- **删除步骤**：支持多选删除
- **复制粘贴**：支持跨宏剪切/复制/粘贴步骤，模板图片一并携带
- **移动步骤**：Alt+上/下移动步骤，智能处理进入、离开与穿越区块边界
- **包裹进重复**：将选取步骤一次包裹进 repeat 区块
- **分支编辑**：then/else、模板与网格导航分支都有自己的详情面板与添加按钮
- **树状视图**：嵌套步骤与分支可展开或折叠，方便查看流程
- **撤销/重做**：50 步历史，Ctrl+Z / Ctrl+Y
- **跳过开关**：每个步骤可单独设为跳过，保留但不执行
- **备注**：为步骤加入可选的备注说明，会显示在步骤列表中

## 图像识别

使用 OpenCV 的 TM_CCOEFF_NORMED 算法进行模板匹配。启用游戏模式时，模板会按窗口大小自动缩放；若用于窗口大小固定的桌面自动化，可关闭游戏模式避免缩放。可在属性面板中调整相似度阈值 (0--100%)，也可在需要明显色彩判断时启用彩色模式。

### 模板管理

- 从屏幕截取区域作为模板（半透明全屏拖拽选取工具）
- 从文件系统挑选 PNG 图片作为模板
- 属性面板中预览模板图片
- 捕获分辨率显示：显示模板捕获时的宽度与高度
- 可对色彩明显的模板启用彩色匹配
- 模板重命名与删除
- 模板与宏合并存储，导出时一并打包

## 窗口管理

- 按标题自动寻找目标窗口，支持部分匹配
- 下拉菜单列出所有可见窗口
- 捕获窗口客户区域（扣除边框与标题栏）
- 背景捕获与输入：选定目标窗口后，不需要保持焦点也能持续执行
- 每个宏可切换背景输入或常规输入，也可向目标窗口发送类似焦点的消息，帮助部分程序避免进入暂停画面
- 宏执行期间若目标窗口关闭后重新打开，会自动重新寻找目标窗口
- 权限不一致警告：若目标窗口以管理员权限运行但 Remaku 没有，会显示警告（UIPI 会阻挡 SendInput）

## 设定

### 宏

| 项目     | 说明                                                   |
| -------- | ------------------------------------------------------ |
| 目标窗口 | 执行宏前 Remaku 要寻找的窗口标题                       |
| 热键     | 此宏专用的全局快捷键                                   |
| 游戏模式 | 为游戏启用模板缩放；固定大小的桌面自动化流程可将其关闭 |

### 一般

| 项目         | 说明                                  |
| ------------ | ------------------------------------- |
| 最上层显示   | 让 Remaku 窗口保持所有窗口最上方      |
| 开机检查更新 | 启动时自动检查 GitHub Release         |
| 更新频道     | stable（稳定版）或 beta（测试版）     |
| 主题         | 跟随系统、浅色、深色                  |
| 语言         | 自动检测、繁体中文、简体中文、English |

### 捕获

| 项目 | 说明         |
| ---- | ------------ |
| FPS  | 每秒捕获帧数 |

### 输入

| 项目     | 说明                                                  |
| -------- | ----------------------------------------------------- |
| 抖动毫秒 | 每次按键加入随机延迟范围 (ms)，避免被侦测为机器人操作 |

### 其他

- 显示目前已跳过的更新版本，可一键清除以重新提示更新

## 宏包

- 从文件菜单打开 Macro Explorer
- 在 Remaku 内浏览官方宏包
- 将兼容宏直接导入本地宏文件夹

## 自动更新机制

- 通过 GitHub API 检查最新 Release 版本
- 更新对话框显示 Release Notes（Markdown 格式）
- 支持直接下载安装程序，含进度条
- 一键静默安装：下载完成后自动以 `/VERYSILENT` 参数启动安装程序并关闭 Remaku，安装完成后新版会自动启动
- 可选择"跳过此版本"，该版本不再提示

## 键盘快捷键

| 快捷键       | 功能         |
| ------------ | ------------ |
| Ctrl+N       | 新建宏       |
| Ctrl+,       | 打开设定     |
| Ctrl+Shift+N | 添加步骤     |
| Delete       | 删除所选步骤 |
| Alt+上       | 步骤上移     |
| Alt+下       | 步骤下移     |
| Ctrl+Z       | 撤销         |
| Ctrl+Y       | 重做         |
| Ctrl+D       | 复制步骤     |
| Ctrl+C       | 复制         |
| Ctrl+X       | 剪切         |
| Ctrl+V       | 粘贴         |

## 宏文件位置

所有宏、模板与配置文件存储在 `Documents\remaku\` 目录下：

```
Documents\remaku\
  config.json        # 应用程序设置
  macros\            # 宏 JSON 文件
    1680000000.json
  templates\         # 模板 PNG 图片
    <宏名称>\
      1680000001.png
  logs\              # 执行日志
    remaku.log
```

## 开发

需要 Python 3.12 与 [uv](https://docs.astral.sh/uv/)。GUI 使用 PySide6 (Qt6) 与 qfluentwidgets。

### 项目结构

```
remaku/
  main.py                         # 入口点，设置记录器、载入翻译、迁移旧版数据并启动主窗口
  paths.py                        # 文件路径工具
  theme.py                        # 主题管理
  version.py                      # 版本信息（从 pyproject.toml 读取）
  controllers/
    home_controller.py            # 主编辑器控制器（步骤编辑、宏管理）
    main_controller.py            # 应用层控制器（菜单、更新、窗口）
    macro_explorer_controller.py   # Macro Explorer 浏览与导入逻辑
    settings_controller.py        # 设置页面控制器
  core/
    capture.py                    # 画面捕获（BetterCam / DXGI）
    dialogs.py                    # 原生对话框辅助工具
    display.py                    # 显示器与屏幕信息工具
    event_bus.py                  # 全局事件系统
    i18n.py                       # 多语言
    keymap.py                     # 虚拟键码与按键名称映射
    keys.py                       # 键盘输入模拟（pydirectinput）
    vision.py                     # OpenCV 图像识别（模板匹配）
    window.py                     # Windows 窗口管理（查找、前景、权限检查）
  models/
    config_model.py               # 设置数据模型
    macro_model.py                # 宏数据模型
    pack_model.py                 # 宏包目录模型
    step_dict.py                  # 步骤序列化／反序列化
    step_node.py                  # 步骤树节点模型，含父子引用
    step_tree.py                  # 步骤树管理器，处理宏步骤操作
  resources/
    icon.py                       # SVG 图标引擎（Lucide 图标）
    resources.qrc                 # Qt 资源文件
    resources_rc.py               # 已编译的 Qt 资源
    icons/                        # SVG 图标文件
    images/                       # 图片资源（logo.png）
    locales/                      # Qt 翻译文件（.ts / .qm）
  services/
    clipboard_service.py          # 步骤复制／粘贴的剪贴板操作，含模板携带
    engine.py                     # JSON 宏解析与执行引擎
    hotkey_service.py             # 全局热键注册与管理
    macro_import_service.py       # 宏导入／导出（ZIP）逻辑
    macro_recorder.py             # 键盘与鼠标操作录制
    macro_runner.py               # 宏执行器（含线程管理）
    migration.py                  # 旧版数据迁移
    pack_service.py               # 宏包目录获取与管理
    template_service.py           # 模板文件管理（重命名、删除、列表）
    updater.py                    # 自动更新检查与安装
  views/
    home_view.py                  # 主编辑器视图（三栏界面）
    main_window.py                # 主应用程序窗口
    macro_explorer_view.py         # Macro Explorer 界面
    region_selector.py            # 屏幕区域选取工具
    settings_view.py              # 设置页面界面
    components/
      about_dialog.py             # 关于对话框
      base_overlay.py             # 浮动窗口基类
      center_panel.py             # 中央面板（步骤树）
      confirm_dialog.py           # 确认对话框
      elided_label.py             # 文字省略标签组件
      hotkey_edit.py              # 热键捕获输入组件
      left_panel.py               # 左侧面板（宏列表）
      message_dialog.py           # 消息对话框
      new_macro_dialog.py         # 新建宏对话框
      overlay.py                  # 状态浮窗组件
      recording_overlay.py        # 录制操作浮动控制面板
      rename_macro_dialog.py      # 重命名宏对话框
      right_panel.py              # 右侧面板（步骤属性）
      step_menu.py                # 步骤类型右键菜单
      template_editor.py          # 模板编辑器组件
      toolbar.py                  # 工具栏（步骤操作）
      update_dialog.py            # 更新对话框（含更新说明）
tests/
  conftest.py                     # 共享测试 fixture
  test_main.py                    # 入口点测试
  test_paths.py                   # 路径工具测试
  test_resources.py               # 资源编译测试
  controllers/                    # 控制器单元测试
  core/                           # 核心模块单元测试
  models/                         # 模型单元测试
  services/                       # 服务单元测试
  views/                          # 视图单元测试
    components/                   # 组件单元测试
```

### 快速开始

`Makefile` 提供常用命令。运行 `make` 可查看所有可用目标。

```powershell
make setup        # 创建虚拟环境并安装依赖
make dev          # 热重载运行（需要 nodemon）
make test         # 运行测试（含覆盖率报告）
make lint         # 运行 ruff 代码检查
make format       # 运行 ruff 格式化
make format-check # 检查格式但不更改
make typecheck    # 运行 pyright 类型检查
make check-all    # 运行 lint、格式检查、类型检查与测试
make translate    # 更新并编译翻译文件
make build        # 构建安装程序（PyInstaller + Inno Setup）
make clean        # 清除所有构建产物与缓存
```

## 支持

如果这个工具对你有帮助，欢迎请我喝杯咖啡

[![GitHub Sponsors](https://img.shields.io/badge/GitHub%20Sponsors-support-ea4aaa?logo=githubsponsors)](https://github.com/sponsors/nelsonlaidev)
[![Buy Me A Coffee](https://img.shields.io/badge/Buy%20Me%20A%20Coffee-support-yellow?logo=buymeacoffee)](https://buymeacoffee.com/nelsonlaidev)

## 授权

[AGPL-3.0](LICENSE)
