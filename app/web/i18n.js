/* 中英文切换。
 *
 * 做法是「渲染后替换 DOM」而不是给每个文案加 data-i18n：
 * 界面文案有 500 多条，其中一部分是运行时拼出来的（"3 条结果"、"11 月 10 日"），
 * 走 DOM 层可以同时覆盖静态与动态内容，也不用改动任何既有渲染代码。
 *
 * 每条替换都会把原文记在 WeakMap 里，切回中文时按原文还原，
 * 所以英文状态下重新渲染的节点（内容本身是中文）也不会丢。
 */
(function () {
  'use strict';

  const DICT = {
    // ── 壳 / 导航 ──
    '实用工具': 'Utility Toolkit',
    '概览': 'Overview',
    '每日规划': 'Daily Plan',
    '翻译': 'Translate',
    '记事本': 'Notes',
    '记事': 'Notes',
    '待办': 'To-do',
    '时间': 'Time',
    '数据成图': 'Charts',
    '图片工具': 'Image Tools',
    '心情日记': 'Mood Diary',
    '单位换算': 'Convert',
    '随机选择': 'Random Pick',
    '历史记录': 'History',
    '收藏夹': 'Favorites',
    '设置': 'Settings',
    '搜索': 'Search',
    '搜索笔记': 'Search notes',
    '搜索原文或译文': 'Search source or translation',
    '搜索收藏的翻译': 'Search saved translations',
    '常用入口': 'Quick access',
    '小工具': 'Utilities',
    '工作区': 'Workspace',
    '记录': 'Records',
    '今天的事项与进度': 'Today at a glance',
    '以时间块方式安排一天': 'Lay out the day in time blocks',
    '六个渠道可选，长文本自动分段': 'Six channels, long text is split automatically',
    '自动保存，标题取自首行': 'Auto-saved, title taken from the first line',
    '快速创建任务，到点提醒': 'Quick task entry with reminders',
    '番茄钟、倒数日与世界时钟': 'Pomodoro, countdowns and world clock',
    '粘贴两列数据，即时生成图表': 'Paste two columns, get a chart',
    '证件照换底、视频转 GIF、图片压缩': 'ID photo background, video to GIF, compression',
    '每日一句，按月回顾': 'One line a day, look back by month',
    '长度、重量、温度、汇率等 8 类单位': 'Length, weight, temperature, currency and more',
    '随机抽取，用于选择与分组': 'Random draws for picking and grouping',
    '翻译记录自动留存，可检索': 'Translation history is kept and searchable',
    '长期保存，不受自动清理影响': 'Kept permanently, never auto-cleaned',

    // ── 通用动作 ──
    '保存': 'Save',
    '保存并测试': 'Save and test',
    '取消': 'Cancel',
    '删除': 'Delete',
    '确认': 'Confirm',
    '添加': 'Add',
    '新建': 'New',
    '刷新': 'Refresh',
    '复制': 'Copy',
    '复制结果': 'Copy result',
    '复制图片': 'Copy image',
    '复制诊断信息': 'Copy diagnostics',
    '全部': 'All',
    '清空': 'Clear',
    '重置': 'Reset',
    '恢复': 'Restore',
    '恢复默认': 'Restore default',
    '恢复默认设置': 'Restore default settings',
    '默认': 'Default',
    '默认值': 'Default',
    '打开': 'Open',
    '更改': 'Change',
    '关闭': 'Close',
    '完成': 'Done',
    '查看': 'View',
    '展开': 'Expand',
    '收起': 'Collapse',
    '更多': 'More',
    '返回': 'Back',
    '下一步': 'Next',
    '上一步': 'Previous',
    '是': 'Yes',
    '否': 'No',
    '确定': 'OK',
    '导入': 'Import',
    '导出': 'Export',
    '测试': 'Test',
    '启动': 'Launch',
    '关于': 'About',
    '版本': 'Version',
    '其他': 'Other',

    // ── 首页 ──
    '早上好': 'Good morning',
    '下午好': 'Good afternoon',
    '晚上好': 'Good evening',
    '今日待办': 'Today',
    '今日规划': 'Today\u2019s plan',
    '最近笔记': 'Recent notes',
    '最近翻译': 'Recent translations',
    '最近完成': 'Recently done',
    '快捷操作': 'Shortcuts',
    '今天没有待办': 'Nothing for today',
    '今天没有待办，清静。': 'Nothing scheduled today.',
    '今天还没有安排': 'No plan yet today',
    '今天到期和已逾期的事情': 'Due today and overdue',
    '还没有数据': 'No data yet',
    '还没有笔记': 'No notes yet',
    '还没有笔记，记下第一笔吧。': 'No notes yet. Write the first one.',
    '还没有翻译记录': 'No translations yet',
    '还没有翻译记录。': 'No translations yet.',
    '还没有收藏的翻译': 'No saved translations',
    '还没有抽取记录': 'No draws yet',
    '还没有记录': 'No records yet',
    '还没有完成的番茄': 'No completed sessions',
    '件待处理': ' pending',
    '项安排': ' scheduled',
    '条': '',
    '篇': '',
    '字': ' chars',

    // ── 翻译 ──
    '翻译一段': 'Translate something',
    '原文': 'Source',
    '译文': 'Result',
    '原文语言': 'From',
    '译文语言': 'To',
    '自动检测': 'Auto-detect',
    '自动检测语言': 'Detect language',
    '翻译通道': 'Channel',
    '默认通道': 'Default channel',
    '智能选择': 'Smart pick',
    '智能选择会自动切换可用的通道': 'Smart pick falls back to any working channel',
    '检测通道可用性': 'Check channel health',
    '翻译记录': 'History',
    '译文会显示在这里': 'The translation appears here',
    '输入或粘贴要翻译的内容\nCtrl + Enter 立即翻译': 'Type or paste text\nCtrl + Enter to translate',
    '粘贴': 'Paste',
    '朗读': 'Read aloud',
    '互换语言': 'Swap languages',
    '存储位置': 'Storage',
    '存为笔记': 'Save as note',
    '新建翻译时使用': 'Used for new translations',
    '默认译文语言': 'Default target language',
    '自动翻译': 'Auto translate',
    '启用自动翻译': 'Enable auto translate',
    '停手多久后翻译': 'Translate after',
    '输入框停手后自动请求译文': 'Requests a translation once you stop typing',
    '打字停下来就自动翻': 'Translates when you pause typing',
    '太短容易打断手感，太长又慢': 'Too short feels jumpy, too long feels slow',
    '历史保留条数': 'History limit',
    '超出后自动清理最早的记录': 'Oldest entries are removed beyond this',
    '清空历史': 'Clear history',
    '清空翻译历史': 'Clear translation history',
    '搜索原文或译文': 'Search source or result',
    '搜索收藏的翻译': 'Search saved translations',

    // ── 记事 ──
    '新建笔记': 'New note',
    '标题取第一行': 'Title comes from the first line',
    '从左边选一篇，或者新建一篇': 'Pick a note on the left, or create one',
    '还没有选中笔记': 'No note selected',
    '接着上次写': 'Continue where you left off',
    '随手记点什么，内容会自动保存': 'Jot something down, it saves automatically',
    '搜索笔记': 'Search notes',
    '全部标签': 'All tags',
    '分类': 'Category',
    '置顶': 'Pin',
    '已置顶': 'Pinned',
    '篇置顶': ' pinned',
    '工作': 'Work',
    '生活': 'Life',
    '学习': 'Study',
    '灵感': 'Ideas',

    // ── 待办 ──
    '添加待办': 'Add to-do',
    '说一句话就能建任务，例如：明天下午3点提醒我取快递 #生活': 'One line to add a task, e.g. "Pick up parcel tomorrow 3pm #life"',
    '支持 今天 / 明天 / 下周三、下午 3 点、每周一、每月 1 号、3 天后…': 'Supports today / tomorrow / next Wed, 3pm, every Monday, monthly…',
    '启用提醒': 'Enable reminders',
    '到点弹出 Windows 通知': 'Windows notification when due',
    '清空已完成': 'Clear completed',
    '已完成': 'Completed',
    '标记完成': 'Mark done',
    '标记未完成': 'Mark not done',
    '导入待办': 'Import to-dos',
    '全部标签': 'All tags',

    // ── 时间 ──
    '番茄钟': 'Pomodoro',
    '倒数日': 'Countdown',
    '世界时钟': 'World clock',
    '开始专注': 'Start focus',
    '专注': 'Focus',
    '短休': 'Short break',
    '长休': 'Long break',
    '专注 25': 'Focus 25',
    '短休 5': 'Break 5',
    '长休 15': 'Break 15',
    '专注时长': 'Focus length',
    '休息时长': 'Break length',
    '只记专注，不记休息': 'Only log focus time',
    '完成一轮自动记账': 'Log a session when a round finishes',
    '这轮专注做什么？（可留空，方便事后回想）': 'What are you focusing on? (optional)',
    '今天的安排': 'Today\u2019s plan',
    '安排今天': 'Plan today',
    '还没有安排': 'Nothing planned',
    '这天还是空的': 'This day is empty',
    '添加安排': 'Add block',
    '分类用时': 'Time by category',
    '每类占了多少时间': 'How time is split',
    '统计与最近记录': 'Stats and recent',
    '今天专注（分钟）': 'Focus today (min)',
    '累计小时': 'Total hours',
    '连续天数': 'Streak',
    '最好的一天（分）': 'Best day (min)',
    '完成的番茄': 'Sessions done',
    '按开始时间排序': 'Sorted by start time',
    '点时间轴空白处即可安排，点已有块可修改': 'Click an empty slot to plan, click a block to edit',
    '安排之后这里会显示用时': 'Time spent shows up here',
    '计时按本机时间校准，切走也不会走偏': 'Timing follows the system clock',
    '新建倒数日': 'New countdown',
    '目标': 'Target',
    '起点': 'Start',
    '按剩余天数排序，生日类可以设成每年重复': 'Sorted by days left; birthdays can repeat yearly',
    '已过期': 'Expired',
    '天后': ' days left',
    '天前': ' days ago',
    '今天': 'Today',
    '明天': 'Tomorrow',
    '昨天': 'Yesterday',
    '返回今天': 'Back to today',
    '城市名或时区，如 东京 / Asia/Tokyo': 'City or timezone, e.g. Tokyo / Asia/Tokyo',
    '按城市时区实时换算，夏令时自动生效': 'Live conversion with daylight saving handled',

    // ── 数据成图 ──
    '粘贴两列数据，直接出图': 'Paste two columns to plot',
    '把 Excel / CSV 拖进来，或粘贴两列': 'Drop an Excel / CSV file, or paste two columns',
    '支持 xlsx / csv / tsv / txt': 'Supports xlsx / csv / tsv / txt',
    '月份\t销量\n1月\t120\n2月\t132\n3月\t101': 'Month\tSales\nJan\t120\nFeb\t132\nMar\t101',
    '数据.xlsx': 'data.xlsx',
    '生成图表': 'Generate chart',
    '等待粘贴数据': 'Waiting for data',
    '粘贴数据后点生成': 'Paste data, then generate',
    '导入文件': 'Import file',
    '图表': 'Chart',
    '柱状': 'Bar',
    '折线': 'Line',
    '环形': 'Donut',
    '面积': 'Area',
    '行': ' rows',
    '松手就导入': 'Drop to import',
    '拖进来，或点下面的按钮选择': 'Drop a file here, or pick one below',

    // ── 图片工具 ──
    '证件照': 'ID photo',
    '视频转 GIF': 'Video to GIF',
    '压缩图片': 'Compress',
    '一寸二寸 · 换底色': 'Standard sizes and background colors',
    '证件照换底、视频转 GIF、图片压缩': 'ID photo, video to GIF, compression',
    '拖一张照片进来': 'Drop a photo',
    '拖一张图片进来': 'Drop an image',
    '拖一个视频进来': 'Drop a video',
    '选择照片': 'Choose photo',
    '选择图片': 'Choose image',
    '选择视频': 'Choose video',
    '照片': 'Photo',
    '规格': 'Size',
    '底色': 'Background',
    '白底': 'White',
    '红底': 'Red',
    '蓝底': 'Blue',
    '灰底': 'Grey',
    '原背景': 'Original',
    '保留原背景': 'Keep original',
    '换底强度': 'Tolerance',
    '背景花就往上调；太高会咬到浅色衣服': 'Raise it for busy backgrounds; too high eats light clothing',
    '300 dpi 标准尺寸': '300 dpi standard size',
    '一寸': '1 inch',
    '二寸': '2 inch',
    '大一寸': 'Large 1 inch',
    '小一寸': 'Small 1 inch',
    '签证': 'Visa',
    '美签': 'US visa',
    '原图': 'Original',
    '原尺寸': 'Original size',
    '压缩后': 'Compressed',
    '目标大小': 'Target size',
    '压到指定大小': 'Compress to a target size',
    '压到指定体积以内，尽量保清晰': 'Fit under the target size, keep it sharp',
    '开始压缩': 'Compress',
    '拖进来或选择；拖动调整位置，滚轮缩放': 'Drop or choose; drag to move, scroll to zoom',
    'jpg / png / webp，背景越干净换底越准': 'jpg / png / webp; cleaner backgrounds work better',
    'mp4 / webm / mov，截一段转成动图': 'mp4 / webm / mov; convert a clip to animation',
    '截一段做成动图': 'Turn a clip into a GIF',
    '建议 10 秒以内、画面不要太花': 'Keep it under 10s and not too busy',
    '帧率': 'Frame rate',
    '画质': 'Quality',
    '开始': 'Start',
    '生成 GIF': 'Make GIF',
    '视频': 'Video',
    '尺寸': 'Dimensions',
    '宽度': 'Width',
    '最长边不超过': 'Longest side at most',
    '越短越清晰': 'Shorter is sharper',
    '目标': 'Target',
    '大小': 'Size',
    '格式': 'Format',
    '准备中…': 'Preparing…',
    '读取中…': 'Loading…',

    // ── 心情 ──
    '选个心情，再写一句话': 'Pick a mood, then write a line',
    '一句话记录今天，比如：把拖了两周的事做完了': 'One line about today, e.g. "finished the thing I put off"',
    '记一笔': 'Save entry',
    '这个月': 'This month',
    '本月记录天数': 'Days logged this month',
    '连续记录天数': 'Logging streak',
    '平均心情（5 分制）': 'Average mood (out of 5)',
    '点一天记录，或看看这个月过得怎么样': 'Click a day to log, or review the month',
    '很好': 'Great',
    '不错': 'Good',
    '一般': 'Okay',
    '低落': 'Low',
    '很差': 'Bad',

    // ── 单位换算 ──
    '长度': 'Length',
    '重量': 'Weight',
    '温度': 'Temperature',
    '面积': 'Area',
    '体积': 'Volume',
    '速度': 'Speed',
    '数据': 'Data',
    '汇率': 'Currency',
    '换算对照': 'Conversion table',
    '互换': 'Swap',
    '交换单位': 'Swap units',
    '上次换算': 'Last conversion',
    '点任意一行可复制数值': 'Click a row to copy the value',
    '更新汇率': 'Update rates',
    '使用缓存汇率': 'using cached rates',

    // ── 随机 ──
    '做个选择': 'Make a choice',
    '候选项': 'Options',
    '添加一个选项，回车确认': 'Add an option, press Enter',
    '先添加选项': 'Add options first',
    '还没有选项，先加两个吧': 'No options yet, add two',
    '先加两个选项': 'Add two options first',
    '至少两个选项才能抽': 'Needs at least two options',
    '清空选项': 'Clear options',
    '开始转动': 'Spin',
    '点中间开始转动': 'Click the center to spin',
    '抽取历史': 'Draw history',
    '选择轮盘': 'Select wheel',
    '轮盘': 'Wheel',
    '列表': 'List',

    // ── 设置 · 分类 ──
    '外观': 'Appearance',
    '外观、通用、翻译、接口与数据': 'Appearance, general, translation and data',
    '通用': 'General',
    '接口': 'API',
    'AI 接口': 'AI API',
    '维护': 'Maintenance',
    '主题 · 密度 · 动效': 'Theme, density, motion',
    '启动 · 提醒': 'Startup and reminders',
    '通道 · 语言 · 自动翻译': 'Channels and language',
    '目录 · 占用 · 维护': 'Folders, usage, maintenance',
    '版本 · 诊断': 'Version and diagnostics',
    '设置分类': 'Settings sections',
    '配色和明暗，只影响这台电脑': 'Colors and brightness, this device only',
    '主题': 'Theme',
    '浅色': 'Light',
    '深色': 'Dark',
    '跟随系统': 'Follow system',
    '浅色适合白天，深色适合晚上': 'Light for daytime, dark for night',
    '强调色': 'Accent color',
    '按钮、选中项和高亮的颜色': 'Used by buttons, selections and highlights',
    '蓝': 'Blue',
    '青': 'Teal',
    '玫瑰': 'Rose',
    '琥珀': 'Amber',
    '界面密度': 'Density',
    '紧凑': 'Compact',
    '标准': 'Standard',
    '宽松': 'Roomy',
    '紧凑模式一屏能多放几行': 'Compact fits more rows on screen',
    '排版松紧、动画和窗口行为': 'Spacing, motion and window behaviour',
    '界面动效': 'Motion',
    '关掉后切换页面、弹出窗口都不再播动画': 'Turns off page and dialog animations',
    '窗口置顶': 'Always on top',
    '让窗口始终显示在最前面': 'Keep the window above others',
    '启动页面': 'Start page',
    '每次打开先进到哪一页': 'Which page opens first',
    '上次停留的页面': 'Last page used',
    '启动时最大化': 'Start maximized',
    '省得每次再点一下最大化': 'Skips the maximize click each time',
    '程序打开时的样子': 'How the window opens',
    '开机自启': 'Launch at login',
    '随 Windows 启动，不弹黑窗': 'Starts with Windows, no console window',
    '启用提醒': 'Enable reminders',
    '待办到点的系统通知': 'System notification when a to-do is due',
    '测试通知': 'Send test notification',
    '确认系统通知能正常弹出': 'Check that notifications show up',
    '服务商': 'Provider',
    '模型': 'Model',
    '地址': 'Endpoint',
    '接口地址': 'API endpoint',
    '地址填到': 'Endpoint up to',
    '填到': 'up to',
    '即可，后面的': 'and keep the rest',
    '会自动补上': 'is filled in automatically',
    '填入示例': 'Fill example',
    '点一下自动填好地址和模型': 'One click fills endpoint and model',
    '怎么填': 'How to fill this in',
    '三个常见情况，照抄就行': 'Three common cases, copy them as-is',
    '任意 OpenAI 兼容接口': 'Any OpenAI-compatible endpoint',
    '接自己的大模型': 'Connect your own model',
    '接自己的大模型，长句和语气更自然': 'Your own model reads long text more naturally',
    '未配置': 'Not configured',
    '不填默认': 'Optional',
    '只存在本机的 settings.json 里，不会上传到别处': 'Stored only in the local settings.json, never uploaded',
    '填地址和 Key 后点保存': 'Fill endpoint and key, then save',
    'Last: 1 米 = 100 厘米': 'Last: 1 m = 100 cm',
    '报错了怎么看': 'Reading errors',
    '401 / 403 是 Key 不对或没权限；404 多半是地址少了': '401 / 403 means the key or permission; 404 usually a truncated URL',
    '；429 是额度用完或请求太频繁。': '; 429 means quota or rate limit.',
    '，Key 随便填': ', any key works',
    '，模型填服务商文档里的名字（如 deepseek-chat、qwen-plus、glm-4-flash）。': ', use the model name from the provider docs (e.g. deepseek-chat, qwen-plus, glm-4-flash).',
    '，模型填本地已拉取的（如 qwen2.5）。不联网、不花钱。': ', use a locally pulled model (e.g. qwen2.5). Offline and free.',
    '数据存储': 'Storage',
    '数据目录': 'Data folder',
    '图片保存目录': 'Image folder',
    '笔记、待办、设置都存在这里': 'Notes, to-dos and settings live here',
    '证件照、GIF、压缩图存这里': 'ID photos, GIFs and compressed images',
    '占用空间': 'Disk usage',
    '正在统计…': 'Measuring…',
    '备份数据': 'Back up data',
    '把 data 里的记录复制一份到 backup': 'Copies records into backup/',
    '备份': 'Backup',
    '清理和重置，操作前都会再问一次': 'Cleanup and reset, always confirmed first',
    '只重置设置，不删笔记和待办': 'Only settings are reset, notes and to-dos stay',
    '所有数据都在本机，不上传': 'Everything stays on this device',
    '所有设置即时保存，存在本机': 'Settings save instantly, on this device',
    '运行信息': 'Runtime info',
    '诊断': 'Diagnostics',
    '反馈问题时把这段贴过来就行': 'Paste this when reporting an issue',
    '打开使用说明': 'Open user guide',
    '版本描述': 'Version',
    '检查更新': 'Check for updates',
    '检查中…': 'Checking…',
    '已是最新版本': 'You are up to date',
    '发现新版本': 'Update available',
    '立即更新': 'Update now',
    '前往下载': 'Go to download',
    '打开发布页': 'Open release page',
    '更新说明': 'Release notes',
    '这一版改了什么': 'What changed in this build',
    '暂无更新说明': 'No release notes',

    // ── 语言名 ──
    '中文（简体）': 'Chinese (Simplified)',
    '中文（繁体）': 'Chinese (Traditional)',
    '英语': 'English',
    '日语': 'Japanese',
    '韩语': 'Korean',
    '法语': 'French',
    '德语': 'German',
    '西班牙语': 'Spanish',
    '葡萄牙语': 'Portuguese',
    '俄语': 'Russian',
    '意大利语': 'Italian',
    '荷兰语': 'Dutch',
    '波兰语': 'Polish',
    '土耳其语': 'Turkish',
    '阿拉伯语': 'Arabic',
    '泰语': 'Thai',
    '越南语': 'Vietnamese',
    '印尼语': 'Indonesian',
    '马来语': 'Malay',
    '印地语': 'Hindi',
    '希伯来语': 'Hebrew',
    '希腊语': 'Greek',
    '瑞典语': 'Swedish',
    '挪威语': 'Norwegian',
    '丹麦语': 'Danish',
    '芬兰语': 'Finnish',
    '捷克语': 'Czech',
    '匈牙利语': 'Hungarian',
    '罗马尼亚语': 'Romanian',
    '保加利亚语': 'Bulgarian',
    '乌克兰语': 'Ukrainian',
    '塞尔维亚语': 'Serbian',
    '克罗地亚语': 'Croatian',
    '斯洛伐克语': 'Slovak',
    '斯洛文尼亚语': 'Slovenian',
    '立陶宛语': 'Lithuanian',
    '拉脱维亚语': 'Latvian',
    '爱沙尼亚语': 'Estonian',
    '菲律宾语': 'Filipino',
    '缅甸语': 'Burmese',
    '高棉语': 'Khmer',
    '老挝语': 'Lao',
    '尼泊尔语': 'Nepali',
    '僧伽罗语': 'Sinhala',
    '泰米尔语': 'Tamil',
    '泰卢固语': 'Telugu',
    '孟加拉语': 'Bengali',
    '乌尔都语': 'Urdu',
    '波斯语': 'Persian',
    '斯瓦希里语': 'Swahili',
    '南非荷兰语': 'Afrikaans',
    '加泰罗尼亚语': 'Catalan',

    // ── 单位名 ──
    '米 (m)': 'Meter (m)',
    '米 · m': 'Meter · m',
    '千米 (km)': 'Kilometer (km)',
    '千米 · km': 'Kilometer · km',
    '厘米 (cm)': 'Centimeter (cm)',
    '厘米 · cm': 'Centimeter · cm',
    '毫米 (mm)': 'Millimeter (mm)',
    '毫米 · mm': 'Millimeter · mm',
    '英寸 (in)': 'Inch (in)',
    '英寸 · in': 'Inch · in',
    '英尺 (ft)': 'Foot (ft)',
    '英尺 · ft': 'Foot · ft',
    '码 (yd)': 'Yard (yd)',
    '码 · yd': 'Yard · yd',
    '英里 (mi)': 'Mile (mi)',
    '英里 · mi': 'Mile · mi',

    // ── 服务商 ──
    '微软必应': 'Microsoft Bing',
    '腾讯交互翻译': 'Tencent TranSmart',
    '网易有道': 'NetEase Youdao',
    '智谱 GLM': 'Zhipu GLM',
    '硅基流动': 'SiliconFlow',
    '通义千问': 'Qwen',
    '本地 Ollama': 'Local Ollama',

    // ── 杂项 ──
    '自动检测': 'Auto',
    '全部标签': 'All tags',
    '条通道可用': ' channels available',
    '条结果': ' results',
    '个日子，最近的排在最前面': ' days, soonest first',
    '件已逾期': ' overdue',
    '搜索笔记、待办、规划、倒数日、翻译、心情…': 'Search notes, to-dos, plan, countdowns, translations, mood…',
    '搜索全部内容（Ctrl + K）': 'Search everything (Ctrl + K)',
    '↑ ↓ 选择 · Enter 打开 · Esc 关闭': '↑ ↓ to select · Enter to open · Esc to close',
    '全局搜索': 'Search',
    '还没有搜索结果': 'No results',
    '不联网，不花钱': 'Offline and free',
    '长文本友好': 'Handles long text',
    '便宜，中文强': 'Cheap, strong Chinese',
    'flash 免费': 'flash is free',
    '注册送额度': 'Free credits on signup',
    '阿里云，有免费额度': 'Aliyun, free tier',
    '需要能连外网': 'Needs internet access',
    '已联网': 'Online',
    '离线': 'Offline',
    '点击重新检测网络': 'Click to test the connection',
    '上个月': 'Previous month',
    '下个月': 'Next month',
    '前一天': 'Previous day',
    '后一天': 'Next day',
    '自己选日期和时间': 'Pick a date and time',
    '回到今天': 'Back to today',
    '保留原背景': 'Keep original background',
    '清空选项': 'Clear options',
    '分类用时': 'Time by category',
    '数据成图': 'Charts',
    '集翻译、记事、待办、时间管理、单位换算、数据成图与图片处理于一体，13 项工具统一在一个窗口内运行。数据保存在本机，断网时除翻译与汇率外均可正常使用。':
      'Translation, notes, to-dos, time management, unit conversion, charts and image processing in one window. Data stays on this device; everything except translation and exchange rates works offline.',
    '作者 H.J. · MIT 协议': 'By H.J. · MIT License',

    // ── 补齐（v1.0 托盘与语言设置） ──
    'AI 翻译接口': 'AI translation API',
    '界面语言': 'Language',
    '切换后立即生效，重启也会记住': 'Applies right away and is remembered',
    '窗口与托盘': 'Window and tray',
    '关掉窗口之后程序留不留在后台': 'What happens once the window closes',
    '显示托盘图标': 'Show tray icon',
    '在任务栏右下角常驻一个图标': 'Keep an icon next to the clock',
    '最小化到托盘': 'Minimize to tray',
    '点最小化时收进托盘，不占任务栏': 'Minimizing hides it from the taskbar',
    '关闭窗口时留在托盘': 'Stay in tray when closed',
    '点 × 不退出程序，双击托盘图标可回来': 'The × hides it; double-click the tray icon to return',
    '界面': 'Interface',
    '明暗': 'Brightness',
    '提醒': 'Reminders',
    '待办提醒': 'To-do reminders',
    '发一条试试': 'Send one',
    '复位': 'Reset',
    '系统': 'System',
    '源码': 'Source',
    '运行方式': 'Runtime',
    '数据占用': 'Disk usage',
    '收藏的内容会保留': 'Saved items are kept',
    '点一条可继续编辑': 'Click one to keep editing',
    '翻译页初始的目标语言': 'Default target language on the translate page',
    '今日': 'Today',
    '历史': 'History',
    '收藏': 'Save',
    '笔记': 'Notes',
    '时长': 'Duration',
    '次翻译': ' translations',
    '选时间': 'Pick time',
    '转换': 'Convert',
    '原始': 'Raw',
    '原': 'Raw',
    '开': 'On',
    '关': 'Off',
    '中文': 'Chinese',
    // ── 关闭窗口时的二选一 ──
    '关闭窗口时': 'When closing the window',
    '先问我': 'Ask me',
    '收进托盘': 'Keep in tray',
    '直接退出': 'Quit',
    '第一次点 × 会问你，选过就照做': 'Asks the first time you click ×, then remembers',
    '关闭窗口后要怎样？': 'What should happen on close?',
    '选一次就记住，之后点 × 直接照做': 'Pick once and it will not ask again',
    '程序留在后台，待办提醒照常，双击托盘图标就能回来':
      'Keeps running in the background, reminders still fire, double-click the tray icon to return',
    '彻底关闭，托盘图标也一起消失': 'Closes completely and removes the tray icon',
    '选过之后不再询问；想改动到 设置 → 通用 → 关闭窗口时。':
      'It will not ask again. Change it later in Settings → General → When closing the window.',
    '下次点关闭时会问你': 'The next close will ask you',
    '现在点关闭会收进托盘': 'Closing now keeps it in the tray',
    '现在点关闭直接退出': 'Closing now quits the app',
    '一': 'Mon',
    '二': 'Tue',
    '三': 'Wed',
    '四': 'Thu',
    '五': 'Fri',
    '六': 'Sat',
    '日': 'Sun',
  };

  // 运行时拼出来的文案走正则：数字、日期、相对时间、单位都在这
  const PATTERNS = [
    [/^(\d+) 个选项$/, '$1 options'],
    [/^(\d+) 条收藏$/, '$1 saved'],
    [/^(\d+) 条结果$/, '$1 results'],
    [/^(\d+) 条通道可用$/, '$1 channels available'],
    [/^(\d+) 件已逾期$/, '$1 overdue'],
    [/^(\d+) 个日子，最近的排在最前面$/, '$1 days, soonest first'],
    [/^(\d+) 篇$/, '$1 notes'],
    [/^(\d+) 项安排$/, '$1 scheduled'],
    [/^(\d+) 字$/, '$1 chars'],
    [/^(\d+) 条$/, '$1 items'],
    [/^(\d+) 件待处理$/, '$1 pending'],
    [/^(\d+) 次翻译$/, '$1 translations'],
    [/^第 (\d+) 个番茄$/, 'Session $1'],
    [/^(\d+) 米 约等于$/, '$1 m is about'],
    [/^(\d+) 月 (\d+) 日$/, 'M$1/$2'],
    [/^(\d+) 月 (\d+) 日（今天）$/, 'M$1/$2 (today)'],
    [/^(\d+)月(\d+)日$/, 'M$1/$2'],
    [/^(\d+)月(\d+)日 星期(.)$/, '$1/$2'],
    [/^(\d+) 年 (\d+) 月$/, '$1/$2'],
    [/^(\d+) 小时前$/, '$1 h ago'],
    [/^(\d+) 分钟前$/, '$1 min ago'],
    [/^(\d+) 秒前$/, '$1 s ago'],
    [/^(\d+) 天前$/, '$1 d ago'],
    [/^(\d+) 小时后$/, 'in $1 h'],
    [/^(\d+) 分钟后$/, 'in $1 min'],
    [/^(\d+) 天后$/, 'in $1 d'],
    [/^(\d+) 天前(更新)?$/, '$1 d ago'],
    [/^(\d+) 分钟前更新$/, 'updated $1 min ago'],
    [/^(\d+) 小时前更新$/, 'updated $1 h ago'],
    [/^(\d+) 天前更新$/, 'updated $1 d ago'],
    [/^(\d+) \/ (\d+) 可用$/, '$1 / $2 working'],
    [/^(\d+)\/(\d+) 可用$/, '$1/$2 working'],
    [/^(\d+) 行 · 合计 ([\d.]+)$/, '$1 rows · total $2'],
    [/^(.+) 换算对照$/, 'Convert $1'],
    [/^(\d+) 帧 · (\d+)fps$/, '$1 frames · $2fps'],
    [/^上次换算：(.+)$/, 'Last: $1'],
    [/^共 (.+) · (\d+) 个文件$/, '$1 · $2 files'],
    [/^· (\d+) 个$/, '· $1'],
    [/^(\d+) 项$/, '$1 items'],
    [/^(\d+) 个文件$/, '$1 files'],
    [/^(.+) 个选项$/, '$1 options'],

    // 更新相关的报错文案来自后端，英文界面下也要能看懂
    [/^还没有配置更新源：作者尚未填写发布仓库地址$/, 'No update source yet: the release repository has not been set'],
    [/^还没有配置更新源$/, 'No update source configured yet'],
    [/^更新源不存在（404），检查地址是否写错$/, 'Update source not found (404)'],
    [/^更新源拒绝访问（(\d+)）$/, 'Update source refused access ($1)'],
    [/^更新源返回 (\d+)$/, 'Update source returned $1'],
    [/^连不上更新源：(.*)$/, 'Cannot reach the update server: $1'],
    [/^连接更新源超时$/, 'Connecting to the update server timed out'],
    [/^更新源返回的不是合法 JSON$/, 'The update source did not return valid JSON'],
    [/^更新源里没有版本信息$/, 'The update source has no version info'],
    [/^更新源格式无法识别$/, 'Unrecognised update feed format'],
    [/^更新源没有给出下载地址$/, 'The update source has no download link'],
    [/^下载失败（(\d+)）$/, 'Download failed ($1)'],
    [/^下载失败：(.*)$/, 'Download failed: $1'],
    [/^连不上下载地址：(.*)$/, 'Cannot reach the download address: $1'],
    [/^下载中断：(.*)$/, 'Download interrupted: $1'],
    [/^下载到的文件不完整$/, 'The downloaded file is incomplete'],
    [/^安装包校验失败，可能下载被截断或被替换$/, 'Checksum mismatch; the download may be truncated or replaced'],
    [/^安装包过大（(.*) MB）$/, 'Installer is too large ($1 MB)'],
    [/^安装包超出预期大小，已中止$/, 'Installer exceeded the expected size, aborted'],
    [/^安装包不存在，可能已被清理$/, 'Installer is gone, it may have been cleaned up'],
    [/^没有可下载的地址$/, 'No download link available'],
    [/^发布页地址无效$/, 'The release page address is invalid'],
    [/^发布页还没建好：作者尚未填写仓库地址$/, 'The release page is not published yet: the repository has not been set'],
    [/^打开浏览器失败：(.*)$/, 'Could not open the browser: $1'],
    [/^打开发布页失败$/, 'Could not open the release page']
  ];

  /* 带变量的句子没法整句查字典，单独给模板：{v} {c} 这些占位符照位置替换。 */
  const TEMPLATES = {
    newVersion: ['发现新版本 {v}，当前是 {c}。', 'Version {v} is available, you have {c}.'],
    upToDate: ['已是最新版本（v{v}）。', 'You are up to date (v{v}).'],
    checking: ['正在连接更新源…', 'Contacting the update server…'],
    downloading: ['正在下载安装包…下载完成后会自动关闭程序并开始安装，请先把手上的事保存好。',
      'Downloading the installer. The app will close and install automatically — save your work first.'],
    downloaded: ['安装包已下载（{size} MB）', 'Installer downloaded ({size} MB)'],
    installStarted: ['安装程序已启动，程序即将退出，请按提示完成安装。',
      'The installer has started. This window will close so the install can finish.'],
    installFailed: ['更新没成功', 'Update failed'],
    noInstaller: ['这个版本没有提供安装包，可以到发布页手动下载。',
      'No installer for this version; download it from the release page.'],
    noNotes: ['这个版本没有填写更新说明。', 'No release notes for this version.'],
    noFeed: ['还没配置更新源，或者发布页还没建好。',
      'No update source configured yet, or the release page is not published.'],
    openPage: ['打开发布页', 'Open release page'],
    retry: ['重试', 'Retry'],
    updateNow: ['立即更新', 'Update now'],
    manual: ['改去发布页手动下载', 'Download manually instead'],
    feedFailed: ['暂时没法检查更新', 'Could not check for updates']
  };

  function fill(template, params) {
    return String(template).replace(/\{(\w+)\}/g, (whole, key) => (
      params && key in params ? String(params[key]) : whole
    ));
  }

  const ATTRS = ['placeholder', 'title', 'aria-label'];
  const textOrigin = new WeakMap();   // Text -> 原文
  const attrOrigin = new WeakMap();   // Element -> {attr: 原文}

  let lang = 'zh';
  let enabled = false;
  let applying = false;

  function translate(text) {
    const raw = String(text);
    const core = raw.trim();
    if (!core || !/[\u4e00-\u9fa5]/.test(core)) return null;
    if (Object.prototype.hasOwnProperty.call(DICT, core)) return swapUnits(DICT[core]);
    for (let i = 0; i < PATTERNS.length; i += 1) {
      if (PATTERNS[i][0].test(core)) {
        return swapUnits(core.replace(PATTERNS[i][0], PATTERNS[i][1]));
      }
    }
    return null;
  }

  const UNIT_WORDS = {
    '千米': 'km', '公里': 'km', '厘米': 'cm', '毫米': 'mm',
    '英寸': 'in', '英尺': 'ft', '英里': 'mi', '米': 'm', '码': 'yd'
  };

  /** 数字后面的中文单位换成符号，"1 米 = 100 厘米" → "1 m = 100 cm"。 */
  function swapUnits(text) {
    return text.replace(/(\d)\s*(千米|公里|厘米|毫米|英寸|英尺|英里|米|码)/g,
      (whole, num, unit) => num + ' ' + (UNIT_WORDS[unit] || unit));
  }

  function setTextNode(node) {
    const value = node.nodeValue;
    if (!value) return;
    if (lang === 'en') {
      const out = translate(value);
      if (out === null) return;
      if (!textOrigin.has(node)) textOrigin.set(node, value);
      const lead = value.match(/^\s*/)[0];
      const trail = value.match(/\s*$/)[0];
      node.nodeValue = lead + out + trail;
    } else if (textOrigin.has(node)) {
      node.nodeValue = textOrigin.get(node);
      textOrigin.delete(node);
    }
  }

  function setAttrs(el) {
    for (let i = 0; i < ATTRS.length; i += 1) {
      const name = ATTRS[i];
      const value = el.getAttribute && el.getAttribute(name);
      if (!value) continue;
      let store = attrOrigin.get(el);
      if (lang === 'en') {
        const out = translate(value);
        if (out === null) continue;
        if (!store) { store = {}; attrOrigin.set(el, store); }
        if (!(name in store)) store[name] = value;
        el.setAttribute(name, out);
      } else if (store && name in store) {
        el.setAttribute(name, store[name]);
        delete store[name];
      }
    }
  }

  function walk(root) {
    if (!root) return;
    if (root.nodeType === 3) {
      setTextNode(root);
      return;
    }
    if (root.nodeType !== 1 && root.nodeType !== 9) return;
    const tag = root.tagName;
    if (tag === 'SCRIPT' || tag === 'STYLE' || tag === 'SVG' || tag === 'svg') return;
    if (root.nodeType === 1) setAttrs(root);

    const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT | NodeFilter.SHOW_ELEMENT, {
      acceptNode(node) {
        const t = node.nodeType === 1 ? node.tagName : '';
        if (t === 'SCRIPT' || t === 'STYLE' || t === 'SVG') return NodeFilter.FILTER_REJECT;
        return NodeFilter.FILTER_ACCEPT;
      }
    });
    let node = walker.nextNode();
    while (node) {
      if (node.nodeType === 3) setTextNode(node);
      else setAttrs(node);
      node = walker.nextNode();
    }
  }

  /** 少数几个「本来就该跟着语言变」的固定位置（英文副标题不该和主标题重复）。 */
  const FIXED = {
    en: [['.brand-text span', 'Everyday utilities']],
    zh: [['.brand-text span', 'Utility Toolkit']]
  };

  function applyFixed() {
    const list = FIXED[lang] || [];
    for (let i = 0; i < list.length; i += 1) {
      const el = document.querySelector(list[i][0]);
      if (el) el.textContent = list[i][1];
    }
  }

  function applyAll() {
    applying = true;
    try {
      walk(document.body);
      applyFixed();
      if (document.documentElement) document.documentElement.lang = lang === 'en' ? 'en' : 'zh-CN';
    } finally {
      applying = false;
    }
  }

  // ── 动态内容：只观察新增节点和文本变化，自身修改期间断开，避免自激 ──
  let timer = null;
  let pendingRoots = new Set();

  function flush() {
    timer = null;
    if (lang !== 'en') { pendingRoots.clear(); return; }
    const roots = Array.from(pendingRoots);
    pendingRoots.clear();
    applying = true;
    try {
      roots.forEach((r) => { if (r && r.isConnected !== false) walk(r); });
    } catch (e) {
      /* 单个节点失败不影响其它 */
    } finally {
      applying = false;
    }
  }

  function schedule(root) {
    if (lang !== 'en') return;
    pendingRoots.add(root || document.body);
    if (timer) return;
    timer = setTimeout(flush, 60);
  }

  let observer = null;

  function startObserver() {
    if (observer || typeof MutationObserver === 'undefined') return;
    observer = new MutationObserver((records) => {
      if (applying) return;
      for (let i = 0; i < records.length; i += 1) {
        const rec = records[i];
        if (rec.type === 'characterData') {
          schedule(rec.target);
        } else {
          for (let j = 0; j < rec.addedNodes.length; j += 1) schedule(rec.addedNodes[j]);
        }
      }
    });
    observer.observe(document.body, { childList: true, subtree: true, characterData: true });
  }

  function setLang(next, opts) {
    const value = next === 'en' ? 'en' : 'zh';
    if (value === lang) {
      if (!observer) startObserver();
      return lang;
    }
    lang = value;
    enabled = value === 'en';
    if (enabled) startObserver();
    applyAll();
    if (!enabled && observer) {
      // 回到中文：还原一次即可，后续不需要继续观察
      pendingRoots.clear();
    }
    if (!opts || !opts.silent) {
      document.dispatchEvent(new CustomEvent('pt:lang', { detail: { lang } }));
    }
    return lang;
  }

  window.PTI18n = {
    get lang() { return lang; },
    t: (text) => (lang === 'en' ? (translate(text) || text) : text),
    /** 句中带变量的场景：tf('newVersion', { v: '1.1.0', c: '1.0.0' }) */
    tf: (key, params) => {
      const pair = TEMPLATES[key];
      if (!pair) return key;
      return fill(pair[lang === 'en' ? 1 : 0], params);
    },
    setLang,
    apply: applyAll,
    ready() {
      startObserver();
      applyAll();
    }
  };
})();
