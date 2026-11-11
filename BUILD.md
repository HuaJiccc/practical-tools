# 实用工具 1.0 — 源码说明

Windows 桌面小工具。界面是本地 HTML/CSS/JS，逻辑在 Python，两者通过本机回环 HTTP 通信（`POST /api/<method>`，带 `X-Token`）。

- v2.0：移除「影视书籍」模块；界面与布局全部重做，去掉玻璃/模糊材质。
- v2.1：新应用图标；新增「每日规划」（时间轴）；随机选择加「转盘」模式；待办可手动选日期时间；记事本加分类。
- v2.2：新增「时间」页（番茄钟 / 倒数日 / 世界时钟）、「心情日记」、「数据成图」（支持直接拖入 Excel）、全局搜索 `Ctrl+K`。
- v2.2.1：数据成图支持直接拖入 `.xlsx`（前端自解 zip+xml，不引 SheetJS）。
- v2.3：新增「图片工具」页——证件照（换底 / 尺寸）、视频转 GIF、压缩到指定大小，三合一页签，产物存 `data/exports/`。
- v2.4：翻译通道扩到 6 条——新增「腾讯交互翻译」（免 key）和「AI 接口」（OpenAI 兼容，自带 7 个服务商预设），智能选择增加兜底。
- v2.5：设置页重做为「左侧六类分类 + 右侧内容」；新增界面密度 / 界面动效 / 启动页面 / 启动最大化 / 开机自启 / 自动翻译延迟 / 导出目录 / 占用统计 / 备份数据 / 打开说明 / 复制诊断等 11 项设置。
- v2.6：数据目录与图片保存目录都可自定义，带「恢复默认」；切换数据目录时自动搬现有数据，重启生效；默认位置不可写时自动退到 `%APPDATA%`。
- v0.9：更名「实用工具」；新增 Inno Setup 安装程序（协议页 / 自定义目录 / 快捷方式 / 卸载项 / WebView2 检测）；安装版数据固定放 `%LOCALAPPDATA%\实用工具\data`，卸载保留；功能描述统一改写。
- v1.0：首个对外正式版。中英文界面切换（DOM 翻译层，覆盖 500+ 条文案）；系统托盘（最小化/关闭收托盘、右键菜单）；关于页显示版本与更新说明；检查更新支持原地下载安装与跳转发布页。版本号从 3.0.0 回落到 1.0.0。**内核 `app/ptools` 从预编译 `.pyc` 全部重写为纯标准库源码**，仓库不再有黑盒模块；点 × 关闭改为首次二选一（收进托盘 / 直接退出），选过就记住，设置里可改回「先问我」。

## 目录

```
personaltools/
├─ app/
│  ├─ app.py            入口：组装后端、起本地服务、开窗口
│  ├─ uistore.py        界面侧独立存储（规划 / 分类 / 番茄钟 / 倒数日 / 心情 / 图表）
│  ├─ aitranslate.py    翻译的扩展渠道（AI 接口 / 腾讯交互翻译），在 ptools 的四条之外另加
│  ├─ ptools/           内核：纯标准库，无第三方依赖
│  │  ├─ media.py       占位：影视书籍已移除，访问即抛错
│  │  ├─ metadata.py    同上
│  │  └─ ...            api / server / translate / todo / notes / units / currency / picker / notify ...
│  └─ web/
│     ├─ index.html     单页骨架，内联 SVG 图标 symbol
│     ├─ style.css      CSS 变量主题 + 组件（纯实色，无 backdrop-filter）
│     └─ app.js         hash 路由 + 各页逻辑，约 6200 行
├─ assets/icon.ico      应用图标（256/128/64/48/32/24/16，由 dev/make_icon.py 生成）
├─ installer/
│  ├─ app.iss           Inno Setup 脚本：协议页 / 目录选择 / 快捷方式 / 卸载 / WebView2 检测
│  ├─ 许可协议.txt       安装向导里显示的协议（UTF-8 带 BOM）
│  └─ ChineseSimplified.isl  向导的简体中文语言包（Inno 官方已不再内置）
├─ dist/实用工具.exe     打包产物
├─ dist-installer/      安装程序产物
└─ dev/                 自测脚本（截图、交互断言、打包运行、安装/卸载流程、图标生成）
```

## uistore：界面侧数据的落脚处

`app/uistore.py` 按用途各写一个 JSON，通过 `UiApi` 暴露方法给前端。写入用临时文件 +
`os.replace` 原子替换，避免中断产生半截 JSON。

起初这么分是因为 `ptools` 是编译产物、加不了新字段；现在 `ptools` 已经是源码，改起来没有
门槛，但这些数据本来就只服务于界面（规划、番茄钟、偏好），留在这里省事，也不打算搬。
真正的理由是**职责**：`ptools` 存的是"程序的数据"，`uistore` 存的是"这次界面长什么样"。

| 类 | 文件 | 职责 |
| --- | --- | --- |
| `PlanStore` | `plan_data.json` | 按 `YYYY-MM-DD` 存任务块，空则删键，只留最近 400 天 |
| `NoteMetaStore` | `note_meta.json` | `{note_id: {category, at}}`，分类限定 5 类 |
| `FocusStore` | `focus_log.json` | 番茄钟每轮记录，`stats(day)` 算今日分钟/番茄数/连续天数 |
| `CountdownStore` | `countdown_data.json` | 倒数日条目，同标题+同日期+同重复规则不重复添加 |
| `MoodStore` | `mood_diary.json` | 一天一条 `{mood, text, at}`，另出月度统计 |
| `ChartStore` | `chart_data.json` | 只存最后一次 `{raw, type, title}`，`raw` 截 20000 字符 |

`UiApi.notes_delete()` 包装原方法，删笔记时顺手清掉它的分类记录。

## 直接跑源码

```bash
cd personaltools
python app/app.py
```

需要 `pywebview`（本机为 6.2.1）+ Windows WebView2 运行时。
数据默认写在 `app/data/`（未打包时 `app_dir()` = `app/`），也可用环境变量 `PERSONALTOOLS_DATA` 指到别处：

```bash
PERSONALTOOLS_DATA=/d/tmp/ptdata python app/app.py
```

调试：`PT_DEBUG=1` 打开 WebView 的 devtools，界面里的 `window.__errs` 收集了所有 JS 异常。

## 打包

```bash
python -m PyInstaller --noconfirm --clean 实用工具.spec
```

产物：`dist/实用工具.exe`（约 13 MB，单文件）。
用户数据仍在 exe 旁的 `data/`，覆盖升级 exe 即可，数据不动。

注意：
- onefile 会解压到临时目录，运行期资源路径用 `sys._MEIPASS`；`app.py` 顶部已把它插进 `sys.path`，这样 `ptools` 能导入。
- 打包后首次启动慢 3-5 秒属正常。
- 缺界面文件 / 启动异常会写到 `data/startup-error.log`。

## 安装程序

用 Inno Setup 6.7（免费）。装着的话直接：

```bash
ISCC.exe installer\app.iss
# 产物：dist-installer\实用工具-<版本>-安装程序.exe（约 15 MB）
```

设计上的几条约束，改脚本前先看：

| 决定 | 原因 |
|---|---|
| `PrivilegesRequired=lowest` | 默认装到 `%LOCALAPPDATA%\Programs`，不弹 UAC；装了没权限的机器也能用 |
| 数据写 `%LOCALAPPDATA%\实用工具\data` | 卸载不删程序目录外的文件，所以数据天然保留；也不用担心装在只读位置 |
| `data-dir.txt` 用 **UTF-8 带 BOM** 写 | 程序按 `utf-8-sig` 读；用默认 ANSI 写会把中文路径变成乱码，程序随即回落到默认目录 |
| 只写一行路径 | `ptools` 只认第一行有效内容，写注释会让整段失效 |
| 卸载阶段不放 `MsgBox` | 会阻塞卸载线程，进度条停在 0% 不动。数据保留是默认行为，不需要问 |
| `[InstallDelete]` 删 `个人工具.exe` | 改名前的旧文件，留着占 13 MB 且容易误点 |

`InitializeSetup` 会查三处注册表确认 WebView2 是否存在（HKLM 的 WOW6432Node / HKLM / HKCU），
缺失时提示并给出微软下载页，不阻断安装。

## 界面结构

左侧固定侧栏（品牌 + 三组导航 + 设置 + 联网状态）+ 右侧顶栏（页面标题 / 副标题 / 页面按钮）+ 滚动内容区。
路由是 hash：`#/home`、`#/plan`、`#/translate`、`#/notes`、`#/todo`、`#/time`、`#/units`、`#/picker`、`#/chart`、`#/image`、`#/mood`、`#/history`、`#/favorites`、`#/settings`。

各页要点：

- **每日规划** `#/plan`：6:00–24:00 时间轴，`PLAN_HOUR_H = 56` px/小时；`layoutPlan()` 对重叠块贪心分列（复用最早结束的列），宽度 `calc(100%/cols - 12px)`；现在时刻是红线 `#planNow`，进页面自动滚到它附近；点空白按 30 分钟吸附新建，点块编辑。
- **待办** `#/todo`：`groupTodos()` 今日视图按 已逾期/上午/下午/晚上/未定时间 分组，全部视图按日期分组；`openDateTimePicker()` 的快捷日期 + 时刻 chips + 精确输入，选中结果存 `state.todo.when`，优先级高于 NLP 识别结果。
- **记事本** `#/notes`：`state.notes.cat` 是当前分类筛选，`renderNoteCats()` 出 chip 与计数，新建自动归入当前分类。
- **随机选择** `#/picker`：`data-mode="wheel|list"` 两种模式。转盘用 SVG 扇区 path + 沿半径旋转的 `<text>`，`state.picker.rotation` 累加，落点算法 `want = ((-(index+0.5)*step) % 360 + 360) % 360`，CSS `transition: transform 4.4s` 负责动画。

### v2.2 三件「必须准」的实现

- **番茄钟** `#/time?focus`：不用 `setInterval` 累减。开始时记 `endAt = Date.now() + left*1000`，
  每 250ms 用 `Math.ceil((endAt - Date.now())/1000)` 重算剩余秒，所以切走、最小化、休眠回来都不会走偏。
  走完调 `api('focus_log')` 记账 + `api('ui_notify')` 弹系统通知，然后 `setFocusPreset('short', true)` 自动切短休；
  切到休息时清空 `f.label`，避免把上一轮的任务描述带到休息里。圆环 `stroke-dasharray = 653.45`（2π×104），
  进度写 `strokeDashoffset`。
- **倒数日**：`days` 一律用「本机零点的 `Date` 相减 ÷ 86400000」取整；`repeat=year|month` 时用
  `daysInMonth()` 夹住 `Math.min(base.getDate(), 当月天数)`，2 月 29 日落在平年时变成 2 月 28 日而不是 3 月 1 日。
- **世界时钟**：`Intl.DateTimeFormat(..., { timeZone })` + `formatToParts` 取各时区本地时分秒（夏令时由
  浏览器时区数据库负责），时差用 `tzOffsetMinutes()` 反算后取整到 0.1 小时。城市表在 `WORLD_PRESETS`（19 个），
  也接受 `Asia/Tokyo` 形式和模糊匹配；最多 12 个，存 `localStorage['personal-tools.world']`。

### 心情日记 / 数据成图 / 全局搜索

- **心情日记** `#/mood`：日历以周一开头，`mood_days` 里没记录的日子是空格；选中日期写 `state.mood.selected`
  再渲染右侧编辑区；`moodStats` 四格来自后端 `stats(ym)`（记录天数 / 平均分 / 连续天数 / 最高分）。
- **数据成图** `#/chart`：`parseChart()` 按行 `splitCells`（支持 `\t`、`,`、连续空格、全角空格），
  第一列当标签、其余列当系列，数字清洗掉千分位与货币符号；**整列没有数字的列不当系列**
  （日期 / 备注列），最多取三组。出图是手写 SVG（柱状 rect / 折线 polyline+circle / 环形 path），
  **宽度取容器 `clientWidth`**、横轴标签放不下才旋转、标签多于 24 个时按 `ceil(n/10)` 抽稀、
  图例固定右上角，`window.resize` 时 `redrawChart()` 防抖重画；复制图片走 `canvas.toBlob` + `ClipboardItem`，
  尺寸读 `svg.viewBox.baseVal`。
  注意 `.chart-canvas svg { fill:none; stroke:none; stroke-width:0 }` —— 全局 svg 样式会继承给 rect，不重置会把柱子描边盖住。

### 拖入 Excel 怎么做的（无第三方库）

`.xlsx` 本质是 zip + XML，前端直接解，不引 SheetJS、也不加 Python 依赖：

1. `zipEntries()`：从尾部找 EOCD（`0x06054b50`），读中央目录拿到每个条目的
   压缩方式 / 压缩后长度 / 本地头偏移，再定位数据段；`method 0` 原样取，`method 8` 走
   `DecompressionStream('deflate-raw')`（WebView2 自带，不支持时提示另存 CSV）。
2. `readWorkbookSheets()`：`xl/workbook.xml` 的 `<sheet>` + `xl/_rels/workbook.xml.rels`
   拼出「表名 → `xl/worksheets/sheetN.xml`」，支持多工作表切换。
3. `readSharedStrings()` / `readDateStyles()`：共享字符串表；`styles.xml` 里
   `cellXfs[].numFmtId` 落在 14–22 / 45–47 或自定义格式含 `y|m|d` 的算日期，
   序列号用 `excelSerial()` 按 `1899-12-30` 基准换成 `YYYY-MM-DD`。
4. `readSheetRows()`：按 `<c r="B3">` 解列号（`sheetColIndex`），`t="s|inlineStr|b|n"` 分别取值；
   行/单元格缺 `r` 属性时退回顺序计数（部分导出工具会省）。
5. 结果拼成 TSV 塞进原来的多行文本框，再走既有的 `drawChart()` —— 所以「拖文件」和
   「粘贴」共用同一套解析与渲染，落库也还是 `chart_data.json` 里的 `raw`。
6. CSV / TSV 走 `decodeTextFile()`（UTF-8 失败自动转 GBK）+ `parseDelimited()`（支持引号内换行、`""` 转义）。

`bindChartDrop()` 把 dragenter/over/leave/drop 挂在 `[data-page="chart"]` 上，
用计数器避免子元素间移动时闪烁；window 级别只 `preventDefault`，防止误拖把文件当网页打开。
- **全局搜索** Ctrl+K：`search_all(query)` 在后端汇总 6 类（笔记 / 待办 / 规划 / 倒数日 / 翻译历史 / 心情），
  每类 `max(4, limit//4)` 条、各自 try/except，坏一类不影响其他；前端 `debounce(170ms)` + 递增 `seq` 丢弃过期响应，
  ↑↓ 选择、Enter 跳转、Esc 关闭；跳到待办/笔记后给目标行加 `.flash` 并 `scrollIntoView`。

### 图片工具三件套 `#/image`（v2.3）

证件照 / 视频转 GIF / 压缩图片放在**同一个页面**，用三个 `.img-tab` 切 `.img-panel`，
`setImageTab(tool)` 只切 class 不重建 DOM，所以拖进来的图片来回换页签不会丢。
三件事全部在前端做，**没有 ffmpeg、没有 sharp/jimp、没有任何新依赖**；
保存走 `api('image_save', name, base64)`，后端 base64 解码后写 `data/exports/`。

- **存盘** `UiApi.image_save`：`re.sub(r'[\\/:*?"<>|\r\n\t]+', '_', name)` 洗文件名、截 90 字符，
  重名自动加 `-2 / -3` 后缀；上限 200 MB。`image_open_dir()` 用 `os.startfile` 打开目录。
  前端 `saveBlob()` 用分块 `btoa` 转 base64（几 MB 的串一次性 `String.fromCharCode(...)` 会爆栈），
  成功后 hint 显示文件名 ＋ 一个「打开文件夹」链接（`title` 里放全路径）。

- **证件照**：`drawId()` 把原图按 `cover` 铺到目标尺寸的 canvas 上，叠加 `state.image.id.ox/oy/zoom`
  做平移缩放（pointer 拖动 + wheel 缩放，缩放围绕鼠标点）。`idReplaceBg()` 从**四条边**做洪水填充：
  队列里取像素，与种子色距离小于 `Math.min(72, 6 + tol)` 就继续蔓延，同时和**邻居**的色差要小于
  `Math.max(14, limit * 0.32)`，两道门槛一起挡，才不会顺着阴影吃进人脸。
  关键细节：比较一律读 `const src = new Uint8ClampedArray(d)` 这份**原始副本**，
  只有写入才用正在被改写的 `d`——否则邻居已经被染成目标色，局部色差恒为 0，换底直接失效。

- **视频转 GIF**：自写编码器，`GifBuf`（自动扩容的 byte/u16/ascii 缓冲）+ `gifPalette()`
  （15 位色键直方图 → 中位切分 256 色 → 全键 LUT）+ `gifLzw()`（变长码 9→12 位）+
  `gifBuild()`（GIF89a 头 + 全局色表 + NETSCAPE2.0 循环 + 每帧 GCE/图像描述符/分包）。
  LZW 加宽判定必须用**尚未分配的 next**：`if (next >= (1 << size) && size < 12) size += 1;`
  再 `dict.set(key, next); next += 1;`，晚一拍 PIL 就报 `broken data stream`。
  抓帧优先 `video.play()` + `requestVideoFrameCallback` 按 `meta.mediaTime` 抽，
  **以第一帧实际位置 `base` 为基准**判 `t - base >= next * step - 0.002`——
  MediaRecorder 产的 webm 没有索引，`seek` 落点会偏后，按绝对时间判会一次把整段抓满（帧全一样）；
  不支持 `requestVideoFrameCallback` 时回退逐帧 seek。总像素超 `GIF_PIXEL_BUDGET`（900 万）自动降宽。
  载入视频期间 `#gifMake` 保持 disabled，并用 `loadSeq` 序号丢弃过期的加载回调。

- **压缩图片**：`compressToTarget()` 先试 q=0.95，超了就 `[0.45, 0.95]` 二分 8 次 `toBlob`；
  8 轮还没进目标就 `scale *= 0.78` 重来（最多 8 次外循环），所以既能压到 200 KB 又不会糊成马赛克。
  「最长边」可选原始 / 1920 / 1280 / 800，只缩不放。

## 翻译渠道：6 条怎么接的（v2.4）

`ptools/translate.py` 里 `PROVIDER_ORDER` / `PROVIDERS` 决定了内置的四条渠道，
`app/aitranslate.py` 另外实现两条，`UiApi.translate()` 先分流：认识的走新模块，
其余原样丢给 `Engine`，四个内置渠道的行为一行没动。

- **AI 接口**（`provider="ai"`）：OpenAI 兼容 `/chat/completions`。配置直接复用已有的
  `ai_base_url` / `ai_api_key` / `ai_model` 三个键——`Settings` 有键白名单，
  `save_settings` 会把不认识的键丢掉（实测过），所以别另造键名；
  这三个键原本是待办智能识别 `aihint` 在用，两边共用一份配置，用户只填一次。
  `normalize_endpoint()` 负责补全：`https://api.deepseek.com` → 加 `/v1/chat/completions`，
  已带 `/v1` 或 `/compatible-mode/v1` 的只补尾段，完整地址原样放过。
  提示词要求「只输出译文」，回来再用 `_clean()` 剥掉 ``` 围栏和整体引号。
- **腾讯交互翻译**（`provider="transmart"`）：`POST https://transmart.qq.com/api/imt`，
  `header.fn = auto_translation`；`source.lang` 支持 `auto` 并会回 `src_lang`。
  语言码和 ptools 的 id 不一样（`zh-Hans → zh`、`zh-Hant → zh-TW`），单独映射一张表。
  免注册免 key，实测 150-250ms，1520 字一次也能翻。
- **智能选择兜底**：`auto` 先走原引擎，返回 `ok:false` 时再用腾讯翻译试一次，
  成功就把原来的错误塞进 `attempts` 一起返回。治的是「外网被墙、四条全挂」的情况。
- **`probe()` 覆盖**：原 `api.probe()` 只测 4 条，这里追加腾讯和 AI 两条
  （AI 未配置时给一条 `还没配置接口地址和 Key`）。

设置页那张卡在 `bindSettingsPage()` 里。预设来自 bootstrap 的 `ai.presets`，
点一下只填地址和模型；`fillAiCard(force)` 的 `force=false` 只在空值时填，
免得切个主题就把用户正在敲的内容冲掉。「保存并测试」是先 `save_settings` 再 `ai_test`，
用真请求验证，不靠猜。

**试过但放弃的免费渠道**（省得以后再踩一遍）：

| 渠道 | 结果 |
| --- | --- |
| DeepL 公开 jsonrpc | 返回 `You're using an older version of DeepL`，三种 payload 结构都试了，服务端反爬 |
| 搜狗翻译 | `errorCode: s10`，要签名 `s` |
| 百度 `transapi` | `errno 1022`，要首页 token + Cookie |
| Yandex | 403 `Session is invalid` |
| Papago | 404，接口已改版 |
| 微软 Edge `translate/auth` | 404 |
| LibreTranslate 公共实例 | 502 / 证书域名不匹配 |
| 小牛翻译 | `apikey is empty` |

结论：当前能免 key 直接用的只多出一条腾讯交互翻译；其余「优质免费」基本都要注册拿 key，
所以把它们做成 OpenAI 兼容预设（DeepSeek / 通义 / 智谱 / Kimi / 硅基流动 / Ollama），
填个 key 就能用，比硬接一堆随时失效的接口稳。

## 设置页结构（v2.5）

`#/settings` 是 `.set-wrap` 两栏：左边 `.set-rail`（6 个 `.set-tab`），右边 `.set-body` 里 6 个
`.set-pane[data-set-pane]`，同一时间只显示一个。切换靠 `setSettingsTab(name)`，
分类名写进 `prefs().settingsTab`，下次进设置直接停在上次那一类。
窗口窄于 1100px 时 `.set-rail` 变成顶部横向页签（`flex-direction: row` + 横向滚动）。

设置项分三类存储，加新开关时先想清楚放哪：

| 存在哪 | 适合什么 | 例子 |
|---|---|---|
| `settings.json`（`save_settings`） | 后端也需要的配置 | 通道、语言、提醒开关、`auto_translate_delay` |
| `ui_prefs.json`（`savePrefs` → `ui_prefs`） | 纯界面偏好 | 主题、强调色、`density`、`motion`、`startPage`、`maximized`、`settingsTab`、`lastPage` |
| 注册表 / 文件系统 | 系统级开关 | 开机自启（`sys_autostart`）、备份（`data_backup`） |

**两个坑，都踩过：**

1. `ptools` 里的 `Settings` 只认自己那份白名单（`config.DEFAULT_SETTINGS`），
   `save_settings({'start_maximized': True})` 会返回 `ok` 但其实不落盘。新键得先加进
   `DEFAULT_SETTINGS`，否则写进去也会被丢掉——类型不符同理。
2. **localStorage 活不过一次重启**。本地服务每次 `ApiServer.start()` 都换端口（实测 8941 / 8943），
   而 localStorage 是按「协议+主机+端口」隔离的，换个端口就是一个全新的空存储。
   所以 `savePrefs()` 除了写 localStorage，还会 350ms 防抖 `POST ui_prefs` 把整份偏好写到
   `data/ui_prefs.json`；启动时 `adoptPrefs(res.ui_prefs)` 先合并再 applyPrefs。
   写「记不住的设置」这类 bug 时，先怀疑这个。

界面密度和动效是通过 `<html>` 的 data 属性驱动的（`applyPrefs()` 里写）：
`:root[data-density="compact"]` 收紧 `.page/.panel/.setting-row` 的 padding，
`:root[data-motion="off"]` 把所有动画/过渡压到 0.001ms。

开机自启写 `HKCU\Software\Microsoft\Windows\CurrentVersion\Run` 的 `实用工具` 值，
不需要管理员权限；`sys.frozen` 决定命令是 `exe` 还是 `python app.py`，卸载/移动位置后开关重开一次即可重新登记。
改名前的 `个人工具` 值会在首次读取时自动改写过来（`_adopt_legacy_autostart`），否则升级后自启会指向旧 exe。

诊断信息 `diag_info()` 同时返回 `items`（给界面渲染成两列表格）和 `text`（给「复制」用），
**不要**把 `ai_api_key` 放进去，只输出「已配置 / 未配置」。

## 主题

主题由两个 data 属性驱动，落在 `<html>` 上：

```html
<html data-theme="light|dark" data-accent="blue|teal|amber|rose">
```

- 颜色全部走 CSS 变量（`--bg / --surface / --border / --text / --accent ...`），深色在 `:root[data-theme="dark"]` 里覆盖一遍。
- 强调色在 `:root[data-accent="..."]` 里改 `--accent / --accent-hover / --accent-soft / --accent-line / --accent-ink`。
- 主题/强调色存 `localStorage['personal-tools.prefs']`；主题另外同步到 `settings.json`（强调色后端没有这一项，只存本机）。
- 切到深色时前端调 `ui_theme('dark')`，后端用 `DwmSetWindowAttribute` 让系统标题栏一起变深；启动早期窗口还没建好会失败，所以前端 900ms 后重试一次。

界面里没有任何 `backdrop-filter` / 半透明层 / 渐变光晕，卡片 = 实色底 + 1px 边框 + 轻阴影 + 14px 圆角。

## 已移除的影视书籍

- `ptools/media.py`、`ptools/metadata.py` 换成占位模块，任何属性访问都抛 `RuntimeError("影视书籍功能已移除")`。
- `app.py` 的 `UiApi` 拦截所有 `media_*` 方法（`AttributeError`），`bootstrap()` 自己组装返回体，不含 media 字段。
- `App` 构造时传 `media=None`。
- `settings.json` 里的 TMDB/OMDb key、玻璃参数会在启动和每次保存设置后被 `strip_legacy_settings()` 清掉。
- `data/media.json`、`data/covers/` 不再读取；是否删除由用户决定。

## 存储位置（v2.6）

两个目录分别由不同机制决定，改的时候别搞混：

| 目录 | 存在哪 | 生效时机 |
|---|---|---|
| 数据目录 | `data-dir.txt`（一行纯路径，放在 EXE 旁边 / 源码时 `app/` 下） | 重启 |
| 图片保存目录 | `data/ui_prefs.json` 的 `export_dir` | 立即 |

`ptools.config.data_dir()` 的解析顺序（`app/ptools/config.py`）：

1. 环境变量 `PERSONALTOOLS_DATA`（测试脚本靠它隔离数据）
2. `data-dir.txt` 第一行有效路径
3. `EXE 同级 /data`
4. 上面那个不可写（`_writable()` 真写探针文件）→ `%APPDATA%` 下的旧位置

**坑**：`data-dir.txt` 只认第一行有效路径，`#` 注释会让它整段失效。
一开始往里写了三行注释头，界面显示切换成功、重启后却还是老目录，
原因是 `app.py` 里的 `read_data_override()` 是逐行跳过注释的，比 `config.data_dir()`
的实现宽松，自测写成了「能读回」所以没发现。现在只写路径一行。

`data_dir()` 在 **import 时就算死并存进 `_DATA_DIR`**，所以同进程内改环境变量无效，
验证切换必须开子进程（`dev_dirs26.py` 就是这么做的）。

切换数据目录时会复制 json 记录 / `exports` / `backup`，**不复制 `webview` 缓存**；
新目录若从当前目录内部创建，跳过复制避免套娃。

## 自测

```bash
cd personaltools

# 内核对照测试（不开界面，最该先跑）
python dev/dev_ptools_diff.py     # 新旧实现逐项对照，12 组 87 项

# 其余后端测试
python dev/dev_translate_extra.py # v2.4：翻译扩展渠道，本地 mock 的 AI 接口 + 真实腾讯翻译，41 项断言
python dev/dev_dirs26.py          # v2.6：目录切换 / 恢复默认 / 非法路径拒绝，含子进程验证真的生效
python dev/dev_settings25_api.py  # v2.5：开机自启 / 占用统计 / 备份 / 诊断，21 项断言（自启测完会还原）
python dev/dev_update.py          # v1.0：版本比较 / 两种清单格式 / 下载与 SHA-256 校验 / 错误路径，24 项
python dev/dev_check_assets.py    # 静态检查：SVG symbol 重复定义与悬空引用（CI 也跑这个）

# 界面回归（需要桌面会话，会真开窗口）
python dev/dev_check3.py          # v2.1：记事本分类 / 待办选时间 / 每日规划 / 转盘
python dev/dev_check22.py         # v2.2：番茄钟 / 倒数日 / 世界时钟 / 心情 / 成图 / 全局搜索
python dev/dev_drop_check.py      # v2.2：拖入 xlsx / csv、切工作表、60 行截断（先跑 make_test_xlsx.py）
python dev/dev_image_probe.py     # v2.3：图片工具冒烟，三项各跑一遍并校验产物
python dev/dev_image_stress.py    # v2.3：压力测试，三项各 12 用例，输出 dev/_shots/v23/stress_report.json
python dev/dev_installed23.py     # v2.3：启动已安装 exe，点侧栏进图片工具再逐个切页签
python dev/dev_tray.py            # v1.0：托盘图标、最小化收托盘、双击恢复（11 项）
python dev/dev_close_ask.py       # v1.0：首次点 × 弹二选一、选择落盘、二次不再问、设置里可改回「先问我」（13 项）
python dev/dev_lang.py            # v1.0：切英文逐页扫残留中文、切回中文验还原、英文溢出检测
python dev/dev_lang_shots.py      # v1.0：英文界面各页截图 + 窗口标题跟随语言
python dev/dev_update_ui.py       # v1.0：关于页版本 / 更新说明 / 检出新版 / 下载提示（本地 mock 更新源）
python dev/dev_packaged_v10.py "D:/安装目录"  # v1.0：打包版实测托盘与最小化
python dev/dev_dark_inputs.py     # v1.0：深色下时间 / 日期框背景与文字颜色（10 项）
python dev/dev_settings25_ui.py   # v2.5：六个分类逐个点开截图 + 密度 / 动效 / 启动页 / 延迟 / 统计 / 诊断联动
python dev/dev_dirs26_ui.py       # v2.6：数据 / 图片目录两行的路径、徽章、按钮渲染与窄窗口排版
python dev/dev_settings25_narrow.py # v2.5：1000px 窄窗口下分类变横向页签、无横向溢出
python dev/dev_startpage25.py set last     # v2.5：把启动页设为「上次停留」并停在记事
python dev/dev_startpage25.py check notes  # v2.5：重启后确认真的回到记事（验证 ui_prefs.json 生效）
python dev/dev_installer_shots.py          # v1.0：跑安装向导（欢迎 / 协议 / 目录）逐页截图并断言
python dev/dev_uninstall_test.py "D:/测试目录"  # v1.0：卸载后程序与安装目录清空、用户数据保留
python dev/dev_readme_shots.py             # 重拍 docs/screenshots 里的五张图（浅色 + 中文）

# 工具
python dev/make_test_xlsx.py      # 造测试用 xlsx（两个工作表 / 日期列 / 200 行大表），不依赖 openpyxl
python dev/make_icon.py           # 重新生成 assets/icon.ico 与预览图
```

每个脚本覆盖什么、有哪些前提，见 `dev/README.md`。

`dev_image_stress.py` 怎么测：`MediaRecorder` + `canvas.captureStream()` 现场录一段色相在变的测试视频，
用真实 `DataTransfer` + 合成 `drop` 事件把文件喂给页面，前端算完把结果写进 `window.__job`，
Python 侧轮询取值（**`evaluate_js` 对 Promise 只返回 `{}`，不能直接 await**），最后用 PIL 解码校验：
证件照看尺寸 + 四角至少两角命中目标底色 + 中心不是底色；GIF 看尺寸/帧数 ±1/9 个采样点帧间有差异/字节数；
压缩看结果 ≤ 目标、不低于目标 5%、最长边与格式符合。三项各 12 个用例，连跑两轮共 72 次，0 失败。

截图脚本支持环境变量：`PT_DATA`（数据目录）、`PT_SHOTS`（输出目录）、`PT_PAGES`（页面列表）、`PT_THEME=dark`。

打包校验（确认 exe 内嵌的前端就是当前源码）：

```bash
python -c "
from PyInstaller.archive.readers import CArchiveReader
r = CArchiveReader('dist/实用工具.exe')
print(r.extract('web\\\\app.js') == open('app/web/app.js','rb').read())
"
```

## ptools 重写：怎么保证「重写」不等于「重做」

1.0.0 把 `app/ptools` 从一批没有源码的 `.pyc` 重写成了纯标准库的 `.py`。这件事的风险不在
能不能写出来，而在**写出来的是不是原来那个行为**——凭印象补一个函数，看起来能用，
实际上把 `clear()` 的返回值、`update()` 的标题推导、落盘顺序全都改了，界面不会报错，
用户也看不出，直到某天数据对不上。

所以做法是「先立标准，再写代码」：

1. 把旧版 `ptools` 的字节码副本放到 `dev/_oracle/ptools_old/`（`.gitignore` 已排除，不进仓库）。
2. `dev/dev_ptools_diff.py` 让新旧两套实现跑**完全相同的一串操作**，比对**返回值**和**落盘后的 JSON**。
3. 比对前递归抹掉 `id` / `created_at` / `fetched_at` 这类每次都不一样的字段，浮点统一 round 到 9 位。
4. 不通过的逐条查：是写错了，还是旧实现本身就是 bug。前者改代码，后者在脚本里单列一张
   `NLPTIME_FIXED` / `EXPECTED` 表把**新行为**钉住，附上为什么不一样。

这套对照抓出的问题都不是"跑不起来"，而是"跑得跟以前不一样"，例如：

| 模块 | 差点写错的地方 |
|---|---|
| `store.History.clear()` | 返回的是**剩余条数**，不是删掉的条数 |
| `notes.update(id, title=...)` | 不传 content 时，标题会从内容重算成「无标题」 |
| `notes` | 保存前已按置顶 / 更新时间排过序，文件顺序 = 界面顺序 |
| `todo.complete()` | 返回 `(完成的, 下一次)` 二元组，且排序最后一段是 `-created_at` |
| `todo` | `get()` 返回的是副本，不是内部对象 |
| `currency` | 少于 **5** 个币种就判失败，防止半截数据污染缓存 |
| `aihint` | HTTP 异常不包装，直接往外抛 |
| `server` | 空 body 是 `invalid body`，不是 `invalid json` |
| `languages.normalize()` | 渠道会回 `en-US` 这种带地区的码，要退一步按语言主体再匹配 |
| `nlptime` | 说了「今晚八点」却按月日 + 默认 9 点算，跨年日期不跨年 |

反过来，旧实现本身就错的地方按正确语义实现，不用为了"一致"把 bug 一起搬过来：

- 「今晚八点吃饭」以前算成**明天早上 8 点**，「明晚八点」同理
- 标题里残留「中午」「明早」「每」这类时间碎片
- 「1 月 1 日」在 11 月说，给的是今年 1 月 2 日（已经过去，被顺延了一天）
- 「明晚」「明早」「零点」直接识别不出来

数值敏感的部分单独加码：`units.format_number` 用 616 个样本（含 `1e-7`、`1e16`、`-0.0` 这类边界）逐个比，
`languages.normalize` 用 4 渠道 × 68 个语言码的笛卡尔积比。当前 87 项全通过。

## 发布前清单

改版本号、出包、发 Release 的时候照这个顺序走，漏一步都会在用户那边出问题。

**1. 替换更新源地址**（唯一必须手改的一行）

`app/app.py` 顶部：

```python
UPDATE_REPO = "your-name/practical-tools"   # ← 换成实际仓库，形如 "octocat/practical-tools"
```

没替换也不会有 404 报错，关于页会明确说「还没有配置更新源」，但检查更新就用不了。

**2. 改版本号**，三处要一致：`app/app.py` 的 `VERSION`、`installer/app.iss` 的 `#define AppVersion`、
`CHANGELOG.md` 新开一节。`RELEASE_NOTES` 也一起改，关于页显示的就是它。

**3. 出包并核对**

```bash
python dev/dev_ptools_diff.py                 # 内核对齐
python dev/dev_check_assets.py                # 资源引用
python -m PyInstaller --noconfirm --clean 实用工具.spec
ISCC.exe installer\app.iss
```

安装包在 `dist-installer/`，附上 sha256：

```bash
certutil -hashfile "dist-installer\实用工具-<版本>-安装程序.exe" SHA256
```

**4. 发 Release**：tag 用 `v<版本>`（与 `app/app.py` 的 `VERSION`、`installer/app.iss` 的
`AppVersion` 三处一致），附件传安装包与免安装的 `实用工具.exe`，
正文直接贴 `CHANGELOG.md` 里对应那节。检查更新走的是
`https://api.github.com/repos/<仓库>/releases/latest`，所以 tag 必须存在、附件必须挂在
release 上，光 push tag 不够。

**5. 装一遍再卸一遍**（别只跑源码）

```bash
python dev/dev_packaged_v10.py "D:/装到的目录"
python dev/dev_uninstall_test.py "D:/装到的目录"
```

安装包未做代码签名，首次运行会触发 SmartScreen 提示「未知发布者」，这是预期行为，
要消掉只能买证书。
