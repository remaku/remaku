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
- **自动更新** -- 启动时检查 GitHub Release，支持稳定版与测试版频道

## 支持的步骤类型

| 类型                               | 说明                                     |
| ---------------------------------- | ---------------------------------------- |
| 按键 (key)                         | 模拟按下指定按键，可设定按住时间         |
| 等待时间 (delay)                   | 固定毫秒延迟                             |
| 等待图片 (wait_image)              | 等待模板图片出现，可设定相似度阈值与超时 |
| 等待任一图片 (if_any_image)        | 同时监控多个模板，任一匹配即执行对应分支 |
| 条件分支 (if_image)                | 根据模板是否出现，执行 then 或 else 路径 |
| 重复循环 (repeat)                  | 重复执行子步骤 N 次                      |
| 长按直到消失 (hold_key_until_gone) | 按住按键直到模板图片消失才放开           |
| 确认前景 (foreground)              | 等待目标窗口回到前景                     |
| 网格导航 (grid_nav)                | 逐格轮替操作（例如背包菜单）             |

## 步骤编辑功能

- **添加步骤**：从类型菜单选择，通过工具栏按钮或右键菜单
- **删除步骤**：支持多选删除
- **复制粘贴**：支持跨宏剪切/复制/粘贴步骤，模板图片一并携带
- **移动步骤**：Alt+上/下移动步骤，智能处理进入、离开与穿越区块边界
- **包裹进重复**：将选取步骤一次包裹进 repeat 区块
- **撤销/重做**：50 步历史，Ctrl+Z / Ctrl+Y
- **跳过开关**：每个步骤可单独设为跳过，保留但不执行

## 图像识别

使用 OpenCV 的 TM_CCOEFF_NORMED 算法进行模板匹配。若模板大于画面，会自动按比例缩小。可在属性面板中调整相似度阈值 (0--100%)。

### 模板管理

- 从屏幕截取区域作为模板（半透明全屏拖拽选取工具）
- 从文件系统挑选 PNG 图片作为模板
- 属性面板中预览模板图片
- 模板重命名与删除
- 模板与宏合并存储，导出时一并打包

## 窗口管理

- 按标题自动寻找目标窗口，支持部分匹配
- 下拉菜单列出所有可见窗口
- 捕获窗口客户区域（扣除边框与标题栏）
- 前景检测：非前景时自动等待
- 权限不一致警告：若目标窗口以管理员权限运行但 Remaku 没有，会显示警告（UIPI 会阻挡 SendInput）

## 设定

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
src/
  main.py              # 入口点，初始化设置与启动主窗口
  main_window.py       # 主窗口，三栏界面、菜单、步骤编辑
  runner.py            # 步骤执行器基础类，管理线程与状态
  macro_engine.py      # JSON 宏解析与执行引擎
  vision.py            # OpenCV 图像识别（模板匹配）
  capture.py           # 画面捕获（BetterCam / DXGI）
  keys.py              # 键盘输入模拟（pydirectinput）
  window.py            # Windows 窗口管理（查找、前景、权限检查）
  region_selector.py   # 屏幕区域选取工具
  config.py            # 配置文件读写
  settings.py          # 设置页面界面
  updater.py           # 自动更新检查与安装
  version.py           # 版本信息（从 pyproject.toml 读取）
  icons.py             # SVG 图标引擎（Lucide 图标）
  i18n/                # 多语言翻译文件
    __init__.py
    zh_tw.json
    zh_cn.json
    en.json
```

### 从源代码运行

```powershell
uv sync
uv run src/main.py
```

### 代码检查

```powershell
uv run ruff check --fix src
uv run ruff format src
```

### 构建 .exe

```powershell
.\build_exe.ps1
```

构建流程使用 PyInstaller 打包成单一可执行文件，并以 Inno Setup (`iscc`) 创建安装程序。

## 支持

如果这个工具对你有帮助，欢迎请我喝杯咖啡

[![GitHub Sponsors](https://img.shields.io/badge/GitHub%20Sponsors-support-ea4aaa?logo=githubsponsors)](https://github.com/sponsors/nelsonlaidev)
[![Buy Me A Coffee](https://img.shields.io/badge/Buy%20Me%20A%20Coffee-support-yellow?logo=buymeacoffee)](https://buymeacoffee.com/nelsonlaidev)

## 授权

[AGPL-3.0](LICENSE)
