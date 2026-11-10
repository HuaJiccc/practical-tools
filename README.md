# 实用工具 · Utility Toolkit

一个运行在 Windows 上的本地工具集合。翻译、记事、待办、时间管理、图片处理等 13 项功能
整合在同一个窗口内，数据保存在本机，无需注册账号，也不会上传。

A local-first Windows toolbox built with pywebview. 13 everyday utilities in one window,
no account, no cloud, everything stays on your disk.

![主界面](docs/screenshots/home.png)

## 下载与安装

到 [Releases](../../releases) 下载 `实用工具-3.0.0-安装程序.exe`，双击按向导完成安装。

| 项目 | 说明 |
|---|---|
| 权限 | 默认装到当前用户目录（`%LOCALAPPDATA%\Programs\实用工具`），**不需要管理员权限**，不弹 UAC |
| 安装向导 | 欢迎页 → 许可协议 → 选择安装目录（可自由更改）→ 附加任务 → 完成 |
| 快捷方式 | 开始菜单、「卸载 实用工具」，桌面快捷方式可选 |
| 运行环境 | **不需要另外安装 Python 或其它运行时**。界面依赖的 WebView2 在 Windows 11 与较新的 Windows 10 上随系统提供，安装时会自动检测，缺失时给出提示与下载入口 |
| 数据位置 | `%LOCALAPPDATA%\实用工具\data`，卸载时保留，重新安装后仍可继续使用 |
| 卸载 | 「设置 → 应用 → 已安装的应用」或开始菜单中的「卸载 实用工具」 |

也提供免安装的 `实用工具.exe`：放入任意文件夹双击运行，数据存放在它旁边的 `data` 里，
整个文件夹复制即可换机器。

## 功能

### 工作区

| 功能 | 说明 |
|---|---|
| **概览** | 汇总今日待办、规划与最近记录，常用操作一键进入 |
| **每日规划** | 以时间块方式安排一天，支持分类与完成状态，可导入待办 |
| **翻译** | 6 条渠道自动兜底，长文本自动分段，结果可留存与收藏 |
| **记事本** | 自动保存，标题取自首行，支持分类管理 |
| **待办** | 快速创建任务，支持自然语言时间识别（如「明天下午三点交房租」），到点系统通知 |

### 小工具

| 功能 | 说明 |
|---|---|
| **时间** | 番茄钟、倒数日与世界时钟 |
| **单位换算** | 长度、重量、温度、面积、体积、速度、数据、汇率共 8 类 |
| **随机选择** | 轮盘抽取，选项可保存复用 |
| **数据成图** | 粘贴两列数据即时生成图表，也支持直接拖入 `.xlsx` / `.csv` |
| **图片工具** | 证件照换底、视频转 GIF、图片压缩，三项合并在同一页签内，全部本地处理 |

### 记录

| 功能 | 说明 |
|---|---|
| **心情日记** | 每日一句，按月回顾 |
| **历史记录** | 翻译记录自动留存，可检索 |
| **收藏夹** | 长期保存，不受自动清理影响 |

全局搜索 `Ctrl+K`，支持深色 / 浅色主题、四套强调色、界面密度与动效开关。

## 界面

| 翻译 | 图片工具 |
|---|---|
| ![翻译](docs/screenshots/translate.png) | ![图片工具](docs/screenshots/image.png) |

| 设置 |
|---|
| ![设置](docs/screenshots/settings.png) |

## 实现上的几个选择

- **图片处理全部在前端完成**，没有塞 ffmpeg：
  - GIF 编码器为手写实现（15 位色键直方图 → 中位切分 256 色 → 变长 LZW）
  - 证件照换底使用四边洪水填充，比较时读取原始像素副本
  - 压缩使用 `canvas.toBlob` 二分搜索质量，仍超出目标才退而缩小尺寸
  - 抓帧使用 `requestVideoFrameCallback` 按 `mediaTime` 采样，对无索引的 webm 同样可靠
- **Excel 解析不依赖 SheetJS**：用 `DecompressionStream('deflate-raw')` 自行解压 zip
- **零外部资源**：没有 CDN、没有 `node_modules`、没有网络字体，图标为手写 SVG symbol
- **偏好写回磁盘**：localStorage 按源隔离，而本地服务端口每次启动都会变，
  因此主题、密度等偏好另存一份 `data/ui_prefs.json`

## 从源码运行

### 环境要求

- Windows 10 / 11
- [WebView2 Runtime](https://developer.microsoft.com/microsoft-edge/webview2/)（Win11 自带，Win10 多数已装）
- **Python 3.13**（见下方「关于 app/ptools」，这一点不能将就）

```bash
pip install -r requirements.txt
python app/app.py
```

数据默认写到 `data/`（可用环境变量 `PERSONALTOOLS_DATA` 指定别处）。

### 构建

```bash
# 1. 打包可执行文件（产物 dist/实用工具.exe，约 13 MB）
pip install pyinstaller
python -m PyInstaller --noconfirm --clean 实用工具.spec

# 2. 生成安装程序（需 Inno Setup 6.7+，产物 dist-installer/*.exe）
ISCC.exe installer\app.iss
```

安装脚本 `installer/app.iss` 负责许可协议页、安装目录选择、快捷方式、卸载项，
以及安装时写入数据目录配置。更换版本号或图标只改该文件顶部的 `#define` 与 `[Setup]`。

## 目录结构

```
app/
  app.py           入口：创建窗口、注入 UiApi、起本地 HTTP 服务
  aitranslate.py   翻译的扩展通道（AI 接口 / 腾讯交互翻译）
  uistore.py       界面侧独立存储（规划 / 分类 / 番茄钟 / 倒数日 / 心情 / 图表 / 偏好）
  ptools/          核心逻辑（大部分为预编译模块，见下）
  web/             前端：index.html + style.css + app.js，无框架
assets/            应用图标
installer/         安装程序脚本与许可协议文本
dev/               自测脚本 19 个：功能回归、图片压力测试、安装/卸载流程（见 dev/README.md）
docs/              截图与使用说明
```

## 关于 `app/ptools`

这个目录下大部分文件是 **预编译的 `.pyc`**（翻译、存储、通知、时间解析等核心逻辑），
仓库中没有它们的源码。由此带来两个限制：

1. **必须用 Python 3.13**。字节码的 magic number 绑定版本，3.11 / 3.12 会直接
   `ImportError: bad magic number`。
2. **这部分无法修改**。要调整其中行为，需要自行编写同名模块替换，或直接使用 Release 中的 exe。

`app/app.py`、`app/web/`、`app/uistore.py`、`app/aitranslate.py` 均为完整源码，可以自由修改。
计划后续把 `ptools` 的核心逻辑用标准库重写并开源，使整个项目可读可改。

## 数据

所有数据都是数据目录下的普通 JSON：

```
settings.json      设置（含 AI 接口的 Key，明文，仅存本机）
notes.json         记事本
todo_data.json     待办
plan_data.json     每日规划
mood_diary.json    心情日记
history.json       翻译历史
ui_prefs.json      界面偏好（主题、密度、启动页等）
exports/           图片工具保存的成品
backup/            「备份数据」生成的副本
```

换机器时复制整个数据目录即可。

**两个目录都可以更改**：「设置 → 数据」可分别指定数据目录与图片保存目录。
安装版默认在 `%LOCALAPPDATA%\实用工具\data`，免安装版默认在 exe 旁的 `data`；
若该位置不可写（例如装在 `C:\Program Files`），程序会自动改用 `%APPDATA%`，无需手动配置。

## 更新日志

各版本变更见 [CHANGELOG.md](CHANGELOG.md)。

## 已知限制

- 仅支持 Windows（依赖 WebView2 与部分 Win32 调用）
- 世界时钟、汇率换算需要联网，其余功能离线可用
- 翻译渠道走的是各服务的公开网页接口，服务方改版即可能失效

## 免责声明

翻译中的「微软必应 / 网易有道 / Google / MyMemory / 腾讯交互翻译」使用的是这些服务
**公开的网页接口**，并非官方开放 API。本项目仅用于学习与技术研究，请遵守各服务商的
使用条款，不要用于商业用途或高频批量调用。需要稳定商用请申请官方 API，或在
「设置 → AI 接口」中配置自己的 OpenAI 兼容接口（已内置 DeepSeek、通义千问、
智谱 GLM、Kimi、硅基流动、OpenAI、本地 Ollama 七个预设）。

## 协议

[MIT](LICENSE)
