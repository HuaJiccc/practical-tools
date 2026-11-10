# dev — 自测与开发脚本

这些脚本**不随程序分发**，只在开发/发版前用来验证功能。仓库里只保留有长期回归价值的，
一次性的临时探针在迭代过程中已经清掉。

## 运行前提

- **Python 3.13**（`app/ptools` 字节码绑定版本，3.11 / 3.12 会 `bad magic number`）
- `pip install -r requirements.txt`
- 标「需要桌面」的脚本会真开窗口，必须在有 WebView2 的 Windows 桌面会话里跑，
  无头环境 / 远程会话里会卡在等窗口
- 脚本会往 `dev/_data*/`、`dev/_shots*/` 写临时数据，这些目录已在 `.gitignore` 里排除

## 界面自测（需要桌面）

| 脚本 | 覆盖 |
|---|---|
| `dev_check3.py` | v2.1 回归：记事本分类、待办选日期时间、每日规划、转盘的端到端断言 |
| `dev_check22.py` | v2.2 回归：番茄钟 / 倒数日 / 世界时钟、心情日记、数据成图、全局搜索 |
| `dev_drop_check.py` | v2.2 回归：拖入 `.xlsx` / `.csv`、切工作表、60 行截断（先跑 `make_test_xlsx.py`） |
| `dev_image_stress.py` | 图片工具压力测试。证件照换底 / 视频转 GIF / 压缩，每项 12 次真实链路（合成文件 → drop → 点 UI → 后端落盘 → PIL 解码校验） |
| `dev_image_probe.py` | 图片工具冒烟：一遍走通页面、拖放、编码、保存 |
| `dev_settings25_ui.py` | 设置页六个分类逐个点开、截图，验证新设置联动 |
| `dev_settings25_narrow.py` | 窄窗口（1000px）下设置页排版：分类导航转横向页签、内容不溢出 |
| `dev_dirs26_ui.py` | v2.6：数据 / 图片目录两行的路径、徽章、按钮渲染，含 1000px 窄窗口排版 |
| `dev_startpage25.py` | 启动页面跨重启是否生效（顺带验证偏好写进了 `data/ui_prefs.json`） |
| `dev_installed23.py` | 启动**已安装的 exe**，确认图片工具页在打包版里正常渲染 |
| `dev_installer_shots.py` | 安装向导（欢迎 → 协议 → 目录）逐页截图并断言页面文字；加 `--install` 会真的装到临时目录 |
| `dev_uninstall_test.py` | 跑一遍卸载，确认程序与安装目录被清空、用户数据保留 |
| `dev_tray.py` | v1.0：托盘图标注册、最小化收进托盘、关闭留托盘、双击恢复、关掉开关后真退出（11 项） |
| `dev_lang.py` | v1.0：切英文后逐页扫残留中文（当前 5 条，全是路径）、切回中文验还原、英文溢出检测 |
| `dev_lang_shots.py` | v1.0：英文界面各页截图，并确认窗口标题跟着语言变 |
| `dev_update_ui.py` | v1.0：关于页版本号、更新说明、检出新版、下载提示、英文下的状态文案（本地 mock 更新源） |
| `dev_packaged_v10.py` | v1.0：对**已安装的 exe** 验证启动、托盘出现、最小化隐藏、双击恢复 |
| `dev_dark_inputs.py` | v1.0：深色下时间 / 日期输入框的计算样式（背景、文字、`color-scheme`），并回切浅色确认没带坏 |

## 后端自测（无界面，可直接跑）

| 脚本 | 覆盖 |
|---|---|
| `dev_translate_extra.py` | 翻译扩展渠道：本地 mock OpenAI 服务 + 腾讯 TranSmart，以及内置渠道不被影响 |
| `dev_settings25_api.py` | 设置页后端接口：开机自启 / 占用统计 / 备份 / 诊断信息 |
| `dev_dirs26.py` | v2.6：目录切换 / 恢复默认 / 拒绝非法路径，**含子进程验证 `data-dir.txt` 真的生效** |
| `dev_check_assets.py` | 静态检查：SVG symbol 重复定义与悬空引用（CI 里也跑这个） |
| `dev_update.py` | v1.0：版本比较、自定义清单 / GitHub Releases 两种格式、下载与 SHA-256 校验、
  404 / 断网 / 格式错误等失败路径，24 项断言 |

## 工具

| 脚本 | 用途 |
|---|---|
| `make_icon.py` | 重新生成 `assets/icon.ico`（16~256 多尺寸）与 `icon.png` |
| `make_test_xlsx.py` | 造一个最小合法 xlsx（两个工作表 / 共享字符串 / 日期单元格），用于测「数据成图」 |
| `shot_util.py` | 按窗口标题截图（GDI `PrintWindow`），供上面几个 UI 脚本复用 |
| `dump_texts.py` | 导出各页面渲染后的所有中文文案 → `dev/_texts.json`，用来校对中英切换的覆盖面 |

## 注意

脚本用 `ROOT = Path(__file__).resolve().parent.parent` 定位项目根，再找 `app/`。
所以这些脚本**必须留在 `dev/` 根目录**，挪进子目录层级就错了。

几个约定：
- 改 `ui_prefs.json` 会真的影响本机偏好（语言、托盘开关都会被改），
  需要确定性结果时脚本会先把它重置成固定值
- 涉及窗口的都按**标题**找句柄：onefile 打包后会另起子进程，
  父进程 pid 和窗口所属 pid 不是同一个
- `dev_lang.py` 的报告写到 `dev/_lang_report.json`，里面是当次仍未翻译的文案
**必须留在 `dev/` 根目录**，挪进子目录会导致路径层级错位。
