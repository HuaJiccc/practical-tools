# 个人工具 · PersonalTools

一个跑在 Windows 上的本地工具箱。翻译、记事、待办、时间管理、图片处理等 13 项功能收在一个窗口里，
数据全部留在本机，不注册、不上传。

A local-first Windows toolbox built with pywebview. 13 everyday utilities in one window,
no account, no cloud, everything stays on your disk.

![主界面](docs/screenshots/home.png)

## 功能

### 工作区

| 功能 | 说明 |
|---|---|
| **概览** | 今日待办、规划、笔记与翻译计数，常用操作一键直达 |
| **每日规划** | 把一天排成看得见的时间块，支持分类与完成状态 |
| **翻译** | 6 条通道自动兜底，长文本分段，历史与收藏 |
| **记事本** | 边写边存，标题自动取第一行，可分类 |
| **待办** | 一句话建任务（`明天下午三点交房租` 自动解析时间），到点系统通知 |

### 小工具

| 功能 | 说明 |
|---|---|
| **时间** | 番茄钟、倒数日、世界时钟 |
| **单位换算** | 长度、重量、温度、面积、体积、速度、数据、汇率 8 类 |
| **随机选择** | 轮盘抽签，选项可保存复用 |
| **数据成图** | 粘贴两列数据直接出图，也支持把 `.xlsx` 直接拖进来 |
| **图片工具** | 证件照换底、视频转 GIF、压缩到指定体积，三合一页签 |

### 记录

| 功能 | 说明 |
|---|---|
| **心情日记** | 一天一句，月底回看 |
| **历史记录** | 每次翻译自动落库，可搜索 |
| **收藏夹** | 长期保留，不会被自动清理 |

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
  - GIF 编码器是手写的（15 位色键直方图 → 中位切分 256 色 → 变长 LZW）
  - 证件照换底用四边洪水填充，比较时读原始像素副本
  - 压缩用 `canvas.toBlob` 二分搜质量，压不下去才退而缩尺寸
  - 抓帧用 `requestVideoFrameCallback` 按 `mediaTime` 采样，对无索引的 webm 也可靠
- **Excel 解析不依赖 SheetJS**：用 `DecompressionStream('deflate-raw')` 自己解 zip
- **零外部资源**：没有 CDN、没有 `node_modules`、没有网络字体，图标是手写的 SVG symbol

## 运行

### 环境要求

- Windows 10 / 11
- [WebView2 Runtime](https://developer.microsoft.com/microsoft-edge/webview2/)（Win11 自带，Win10 多数已装）
- **Python 3.13**（见下方「关于 app/ptools」，这一点不能将就）

### 从源码启动

```bash
pip install -r requirements.txt
python app/app.py
```

数据会写到 `data/`（可用环境变量 `PERSONALTOOLS_DATA` 指定别处）。

### 打包成单文件 exe

```bash
pip install pyinstaller
pyinstaller --noconfirm --clean --onefile --windowed --name "个人工具" \
  --icon assets/icon.ico \
  --add-data "app/web;web" --add-data "app/ptools;ptools" --add-data "assets/icon.ico;assets" \
  --paths app --hidden-import webview.platforms.edgechromium \
  --exclude-module tkinter --exclude-module PIL app/app.py
```

产物在 `dist/个人工具.exe`，约 13 MB。

## 目录结构

```
app/
  app.py           入口：创建窗口、注入 UiApi、起本地 HTTP 服务
  aitranslate.py   翻译的扩展通道（AI 接口 / 腾讯交互翻译）
  uistore.py       界面侧独立存储（规划 / 分类 / 番茄钟 / 倒数日 / 心情 / 图表 / 偏好）
  ptools/          核心逻辑（大部分为预编译模块，见下）
  web/             前端：index.html + style.css + app.js，无框架
assets/            应用图标
dev/               自测脚本 13 个：功能回归、图片压力测试、打包校验（见 dev/README.md）
docs/screenshots/  README 用图
```

## 关于 `app/ptools`

这个目录下大部分文件是 **预编译的 `.pyc`**（翻译、存储、通知、时间解析等核心逻辑），
仓库里没有它们的源码。由此带来两个限制，请先知道：

1. **必须用 Python 3.13**。字节码的 magic number 绑定版本，3.11 / 3.12 会直接
   `ImportError: bad magic number`。
2. **这部分改不了**。要调整其中行为，需要自己写同名模块替换，或直接用 Release 里的 exe。

`app/app.py`、`app/web/`、`app/uistore.py`、`app/aitranslate.py` 都是完整源码，可以随意改。
计划后续把 `ptools` 的核心逻辑用标准库重写并开源，让整个项目可读可改。

## 数据

所有数据是 `data/` 下的普通 JSON：

```
settings.json      设置（含 AI 接口的 Key，明文，只在本机）
notes.json         记事本
todo_data.json     待办
plan_data.json     每日规划
mood_diary.json    心情日记
history.json       翻译历史
ui_prefs.json      界面偏好（主题、密度、启动页等）
exports/           图片工具保存的成品
backup/            「备份数据」生成的副本
```

换机器直接整个复制 `data/` 即可。

## 更新日志

各版本改了什么见 [CHANGELOG.md](CHANGELOG.md)。

## 已知限制

- 只支持 Windows（依赖 WebView2 与部分 Win32 调用）
- 世界时钟、汇率换算需要联网，其余功能离线可用
- 翻译通道走的是各服务的公开网页接口，服务方改版就可能失效

## 免责声明

翻译里的「微软必应 / 网易有道 / Google / MyMemory / 腾讯交互翻译」使用的是这些服务
**公开的网页接口**，不是官方开放 API。本项目仅用于学习与技术研究，请遵守各服务商的
使用条款，不要用于商业用途或高频批量调用。需要稳定商用请申请官方 API，或在
「设置 → AI 接口」里配置自己的 OpenAI 兼容接口（已内置 DeepSeek、通义千问、
智谱 GLM、Kimi、硅基流动、OpenAI、本地 Ollama 七个预设）。

## 协议

[MIT](LICENSE)
