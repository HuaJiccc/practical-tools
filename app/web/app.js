(() => {
  'use strict';

  // 收集运行时错误，便于排查（不在界面上显示）
  window.__errs = [];
  window.addEventListener('error', (ev) => {
    window.__errs.push(`${ev.message} @${ev.filename || ''}:${ev.lineno || 0}`);
  });
  window.addEventListener('unhandledrejection', (ev) => {
    window.__errs.push(`promise: ${ev.reason && (ev.reason.stack || ev.reason.message) || ev.reason}`);
  });

  /* ---------------- 基础工具 ---------------- */
  const $ = (sel, root = document) => root.querySelector(sel);
  const $$ = (sel, root = document) => Array.from(root.querySelectorAll(sel));
  const ic = (name) => `<svg aria-hidden="true"><use href="#i-${name}"/></svg>`;

  const esc = (value) => String(value ?? '')
    .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;').replace(/'/g, '&#39;');

  const pad = (n) => String(n).padStart(2, '0');

  function debounce(fn, wait) {
    let timer = null;
    return (...args) => {
      clearTimeout(timer);
      timer = setTimeout(() => fn(...args), wait);
    };
  }

  async function api(method, ...args) {
    try {
      const res = await fetch(`/api/${method}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'X-Token': window.__TOKEN__ || '' },
        body: JSON.stringify({ args }),
      });
      if (!res.ok) return { ok: false, error: `请求失败（HTTP ${res.status}）` };
      const out = await res.json();
      return out && typeof out === 'object' ? out : { ok: true };
    } catch (err) {
      return { ok: false, error: (err && err.message) || String(err) };
    }
  }

  function toast(message, kind = 'info', ms = 2600) {
    const host = $('#toasts');
    const el = document.createElement('div');
    el.className = `toast ${kind}`;
    el.innerHTML = `${ic(kind === 'ok' ? 'check' : kind === 'err' ? 'warning' : 'info')}<span></span>`;
    el.lastElementChild.textContent = message;
    host.appendChild(el);
    setTimeout(() => {
      el.classList.add('out');
      setTimeout(() => el.remove(), 220);
    }, ms);
  }

  /* ---------------- 弹层 ---------------- */
  let modalEsc = null;

  function openModal({ title, subtitle = '', body = '', footer = '', wide = false, onClose = null }) {
    const root = $('#modalRoot');
    root.innerHTML = `
      <div class="modal-backdrop"></div>
      <div class="modal ${wide ? 'wide' : ''}" role="dialog" aria-modal="true" tabindex="-1">
        <div class="modal-head">
          <div><h3></h3><p></p></div>
          <button class="modal-close" aria-label="关闭">${ic('x')}</button>
        </div>
        <div class="modal-body">${body}</div>
        ${footer ? `<div class="modal-foot">${footer}</div>` : ''}
      </div>`;
    root.querySelector('.modal-head h3').textContent = title;
    const sub = root.querySelector('.modal-head p');
    if (subtitle) sub.textContent = subtitle; else sub.remove();

    root.classList.add('open');
    let closed = false;
    const close = () => {
      if (closed) return;
      closed = true;
      root.classList.remove('open');
      root.innerHTML = '';
      if (modalEsc) { document.removeEventListener('keydown', modalEsc); modalEsc = null; }
      if (onClose) onClose();
    };
    root.querySelector('.modal-close').onclick = close;
    root.querySelector('.modal-backdrop').onclick = close;
    modalEsc = (ev) => { if (ev.key === 'Escape') close(); };
    document.addEventListener('keydown', modalEsc);

    const focusTarget = root.querySelector('input, textarea, select')
      || root.querySelector('[data-cancel]')
      || root.querySelector('.modal');
    setTimeout(() => focusTarget && focusTarget.focus(), 30);

    return {
      el: root.querySelector('.modal'),
      body: root.querySelector('.modal-body'),
      foot: root.querySelector('.modal-foot'),
      close,
    };
  }

  function confirmAction({ title, message, confirm = '确定', danger = true }) {
    return new Promise((resolve) => {
      let settled = false;
      const done = (value) => { if (!settled) { settled = true; resolve(value); } };
      const modal = openModal({
        title,
        body: `<p class="confirm-text">${esc(message)}</p>`,
        footer: `<button class="btn" data-cancel>取消</button>
                 <button class="btn ${danger ? 'btn-danger' : 'btn-primary'}" data-ok>${esc(confirm)}</button>`,
        onClose: () => done(false),
      });
      modal.foot.querySelector('[data-cancel]').onclick = () => modal.close();
      modal.foot.querySelector('[data-ok]').onclick = () => { done(true); modal.close(); };
    });
  }

  /* ---------------- 时间格式 ---------------- */
  const sameDay = (a, b) => a.getFullYear() === b.getFullYear() && a.getMonth() === b.getMonth() && a.getDate() === b.getDate();

  function parseLocal(value) {
    if (!value) return null;
    const d = new Date(value);
    return Number.isNaN(d.getTime()) ? null : d;
  }

  function dueLabel(dueAt) {
    const d = parseLocal(dueAt);
    if (!d) return '';
    const now = new Date();
    const time = (d.getHours() || d.getMinutes()) ? ` ${pad(d.getHours())}:${pad(d.getMinutes())}` : '';
    const dayDiff = Math.round(
      (new Date(d.getFullYear(), d.getMonth(), d.getDate())
        - new Date(now.getFullYear(), now.getMonth(), now.getDate())) / 86400000,
    );
    const relative = { 0: '今天', 1: '明天', 2: '后天', '-1': '昨天', '-2': '前天' };
    if (relative[dayDiff] !== undefined) return relative[dayDiff] + time;
    const date = d.getFullYear() === now.getFullYear()
      ? `${d.getMonth() + 1}月${d.getDate()}日`
      : `${d.getFullYear()}/${d.getMonth() + 1}/${d.getDate()}`;
    return date + time;
  }

  function relTime(ts) {
    if (!ts) return '';
    const d = new Date(ts * 1000);
    const diff = Date.now() - d.getTime();
    if (diff < 60000) return '刚刚';
    if (diff < 3600000) return `${Math.floor(diff / 60000)} 分钟前`;
    if (diff < 86400000) return `${Math.floor(diff / 3600000)} 小时前`;
    const now = new Date();
    if (sameDay(d, now)) return `今天 ${pad(d.getHours())}:${pad(d.getMinutes())}`;
    const yesterday = new Date(now.getFullYear(), now.getMonth(), now.getDate() - 1);
    if (sameDay(d, yesterday)) return `昨天 ${pad(d.getHours())}:${pad(d.getMinutes())}`;
    if (d.getFullYear() === now.getFullYear()) return `${d.getMonth() + 1}月${d.getDate()}日`;
    return `${d.getFullYear()}/${d.getMonth() + 1}/${d.getDate()}`;
  }

  function stamp(d = new Date()) {
    return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`;
  }

  const langName = (id) => (state.langs.find((l) => l.id === id) || {}).name || id || '';

  /* ---------------- 状态 ---------------- */
  const state = {
    boot: null,
    settings: {},
    langs: [],
    providers: [],
    ai: { ready: false, presets: [], base_url: '', model: '', endpoint: '', has_key: false },
    online: true,
    dataDir: '',
    historyStats: { total: 0, favorites: 0 },
    notes: { items: [], stats: { total: 0, pinned: 0, chars: 0 }, currentId: null, query: '', cat: '', meta: {} },
    todo: { view: 'today', items: [], stats: {}, meta: {}, tag: '', when: null },
    units: { cat: 'length', from: null, to: null },
    picker: { options: [], history: [], lastResult: '', mode: 'wheel', rotation: 0, spinning: false, winner: -1 },
    plan: { date: '', items: [], stats: { total: 0, done: 0, minutes: 0 }, scrollKey: '' },
    time: { tab: 'focus' },
    focus: {
      preset: 'focus', total: 25 * 60, left: 25 * 60, running: false,
      endAt: 0, startedAt: 0, label: '', timer: null, stats: {}, sessions: [],
    },
    cd: { items: [] },
    world: { cities: [] },
    mood: { ym: '', days: {}, stats: {}, selected: '', mood: 0, text: '' },
    chart: { raw: '', type: 'bar', data: null, file: null },
    image: {
      tab: 'id',
      id: { img: null, name: '', size: 'one', back: 'white', tol: 34, zoom: 100, ox: 0, oy: 0, blob: null },
      gif: { url: '', name: '', duration: 0, start: 0, len: 3, fps: 10, width: 320, blob: null, busy: false },
      cmp: { file: null, img: null, target: 200, fmt: 'image/jpeg', max: 0, blob: null, meta: null },
    },
    cmd: { open: false, items: [], idx: -1, query: '', seq: 0 },
    currency: null,
    lastConv: null,
    trans: { last: null, busy: false, entryId: null },
  };

  /* 分类：工作 / 生活 / 学习 / 灵感 / 其他（笔记和日程共用） */
  const CATEGORIES = [
    { id: 'work', name: '工作', color: 'var(--c-work)' },
    { id: 'life', name: '生活', color: 'var(--c-life)' },
    { id: 'study', name: '学习', color: 'var(--c-study)' },
    { id: 'idea', name: '灵感', color: 'var(--c-idea)' },
    { id: 'other', name: '其他', color: 'var(--c-other)' },
  ];
  const catOf = (id) => CATEGORIES.find((c) => c.id === id) || null;
  const catName = (id) => (catOf(id) || {}).name || '未分类';
  const catColor = (id) => (catOf(id) || {}).color || 'var(--text-3)';

  const PAGES = {
    home: { title: '概览', sub: '今天的事项与进度' },
    plan: { title: '每日规划', sub: '以时间块方式安排一天' },
    translate: { title: '翻译', sub: '六个渠道可选，长文本自动分段' },
    notes: { title: '记事本', sub: '自动保存，标题取自首行' },
    todo: { title: '待办', sub: '快速创建任务，到点提醒' },
    time: { title: '时间', sub: '番茄钟、倒数日与世界时钟' },
    chart: { title: '数据成图', sub: '粘贴两列数据，即时生成图表' },
    image: { title: '图片工具', sub: '证件照换底、视频转 GIF、图片压缩' },
    mood: { title: '心情日记', sub: '每日一句，按月回顾' },
    units: { title: '单位换算', sub: '长度、重量、温度、汇率等 8 类单位' },
    picker: { title: '随机选择', sub: '随机抽取，用于选择与分组' },
    history: { title: '历史记录', sub: '翻译记录自动留存，可检索' },
    favorites: { title: '收藏夹', sub: '长期保存，不受自动清理影响' },
    settings: { title: '设置', sub: '外观、通用、翻译、接口与数据' },
  };

  /** 取当前语言下的文案；没装 i18n 时原样返回。 */
  function tr(text) {
    return window.PTI18n ? window.PTI18n.t(text) : text;
  }

  /* ---------------- 偏好 ---------------- */
  const PREF_KEY = 'personal-tools.prefs';

  function prefs() {
    try { return JSON.parse(localStorage.getItem(PREF_KEY) || '{}') || {}; } catch { return {}; }
  }

  function savePrefs(patch) {
    localStorage.setItem(PREF_KEY, JSON.stringify({ ...prefs(), ...patch }));
    pushPrefs();
  }

  /** 本地服务端口每次都变，localStorage 按源隔离记不住，真正的副本要写回后端。 */
  let prefsPushTimer = null;
  function pushPrefs() {
    clearTimeout(prefsPushTimer);
    prefsPushTimer = setTimeout(() => {
      api('ui_prefs', prefs());
    }, 350);
  }

  /** 启动时把后端存的偏好合并进来：同源缓存优先，其余用服务端的。 */
  function adoptPrefs(server) {
    if (!server || typeof server !== 'object' || !Object.keys(server).length) return;
    const merged = { ...server, ...prefs() };
    localStorage.setItem(PREF_KEY, JSON.stringify(merged));
    applyPrefs();
  }

  function applyPrefs() {
    const p = prefs();
    const theme = p.theme === 'dark' ? 'dark' : 'light';
    document.documentElement.dataset.theme = theme;
    document.documentElement.dataset.accent = p.accent || 'blue';
    document.documentElement.dataset.density = p.density === 'compact' ? 'compact' : 'normal';
    document.documentElement.dataset.motion = p.motion === 'off' ? 'off' : 'on';
    const lang = p.language === 'en' ? 'en' : 'zh';
    document.documentElement.dataset.lang = lang;
    if (window.PTI18n && window.PTI18n.lang !== lang) window.PTI18n.setLang(lang, { silent: true });
    api('ui_theme', theme);
    clearTimeout(applyPrefs.retry);
    applyPrefs.retry = setTimeout(() => api('ui_theme', theme), 900);
  }

  /** 本机没有偏好记录时，用 settings.json 里的主题/强调色作为初始值。 */
  function seedPrefs() {
    const p = prefs();
    if (p.theme || p.accent) return;
    const s = state.settings || {};
    const patch = {};
    if (s.theme === 'dark' || s.theme === 'light') patch.theme = s.theme;
    // 强调色只存本机（后端设置里没有这一项）

    if (!Object.keys(patch).length) return;
    savePrefs(patch);
    applyPrefs();
  }

  /* ---------------- 路由 ---------------- */
  function currentPage() {
    const raw = (location.hash || '').replace(/^#\/?/, '');
    return PAGES[raw] ? raw : 'home';
  }

  function go(page, opts = {}) {
    if (opts.newNote) sessionStorage.setItem('pt.newNote', '1');
    if (opts.focusTodo) sessionStorage.setItem('pt.focusTodo', '1');
    if (opts.timeTab) state.time.tab = opts.timeTab;
    location.hash = `#/${page}`;
  }

  async function route() {
    const page = currentPage();
    $$('.page').forEach((el) => el.classList.toggle('active', el.dataset.page === page));
    $$('[data-nav]').forEach((el) => el.classList.toggle('active', el.dataset.nav === page));
    $('#pageTitle').textContent = tr(PAGES[page].title);
    $('#pageSub').textContent = tr(PAGES[page].sub);
    $('#scroll').scrollTop = 0;
    savePrefs({ lastPage: page });

    if (page === 'home') await refreshHome();
    if (page === 'plan') await renderPlanPage();
    if (page === 'time') await renderTimePage();
    if (page === 'mood') await renderMoodPage();
    if (page === 'chart') renderChartPage();
    if (page === 'image') renderImagePage();
    if (page === 'notes') await renderNotesPage(true);
    if (page === 'todo') await loadTodo();
    if (page === 'units') renderUnitsPage();
    if (page === 'picker') renderPickerPage();
    if (page === 'history') await loadHistory('history');
    if (page === 'favorites') await loadHistory('favorites');
    if (page === 'settings') {
      syncSettingsUi();
      setSettingsTab(prefs().settingsTab || 'look', true);
    }
    if (page === 'translate') {
      const target = sessionStorage.getItem('pt.translateTarget');
      if (target) {
        sessionStorage.removeItem('pt.translateTarget');
        if (target !== 'auto') $('#dstLang').value = target;
        $('#srcLang').value = 'auto';
      }
      if (sessionStorage.getItem('pt.translateDraft')) {
        const draft = sessionStorage.getItem('pt.translateDraft');
        sessionStorage.removeItem('pt.translateDraft');
        $('#srcText').value = draft;
        onTranslateInput();
        doTranslate();
      }
    }
    if (page === 'notes' && sessionStorage.getItem('pt.newNote')) {
      sessionStorage.removeItem('pt.newNote');
      await createNote();
    }
    if (page === 'todo' && sessionStorage.getItem('pt.focusTodo')) {
      sessionStorage.removeItem('pt.focusTodo');
      $('#todoInput').focus();
    }
  }

  /* ---------------- 启动 ---------------- */
  async function boot() {
    applyPrefs();
    bindChrome();

    const res = await api('bootstrap');
    if (!res || res.ok === false) {
      toast((res && res.error) || '程序启动失败', 'err', 6000);
      return;
    }

    state.boot = res;
    state.settings = res.settings || {};
    adoptPrefs(res.ui_prefs);
    seedPrefs();
    state.langs = res.languages || [];
    state.providers = res.providers || [];
    state.ai = res.ai || { ready: false, presets: [] };
    state.dataDir = res.data_dir || '';
    state.exportsDir = res.exports_dir || '';
    state.historyStats = res.stats || { total: 0, favorites: 0 };
    state.notes.items = (res.notes || []).slice();
    state.notes.stats = res.note_stats || { total: 0, pinned: 0, chars: 0 };
    state.notes.meta = res.note_categories || {};
    state.plan.items = res.plan_today || [];
    state.plan.date = planDateKey(new Date());
    state.plan.stats = planStats(state.plan.items);
    state.focus.stats = res.focus || {};
    state.cd.items = res.countdowns || [];
    state.mood.ym = moodMonthKey();
    state.mood.days = res.mood_month || {};
    state.mood.stats = res.mood_stats || {};
    state.mood.selected = planDateKey(new Date());
    loadWorld();
    const lastChart = res.chart_last;
    if (lastChart && lastChart.raw) {
      state.chart.raw = lastChart.raw;
      state.chart.type = CHART_TYPES.includes(lastChart.type) ? lastChart.type : 'bar';
    }
    state.picker.mode = localStorage.getItem('personal-tools.pickMode') === 'list' ? 'list' : 'wheel';
    state.todo.stats = res.todo_stats || {};
    state.todo.meta = res.todo_meta || {};
    state.units.cats = res.unit_categories || [];
    state.currency = res.currency || null;
    state.lastConv = res.last_conversion || null;
    const picker = res.picker || {};
    state.picker.options = (picker.options || []).slice();
    state.picker.history = (picker.history || []).slice();
    state.picker.lastResult = picker.lastResult || '';
    state.picker.rotation = 0;
    state.picker.spinning = false;
    state.online = !!res.online;

    buildLanguageSelects();
    buildProviderSelects();
    syncTranslateSettings();
    syncSettingsUi();
    syncBadges();
    setNet(state.online);

    // 先算好要进哪一页：route() 会把当前页写进 lastPage，晚读就被覆盖成 home
    const startTarget = pickStartPage();
    await route();
    if (startTarget) go(startTarget);

    if (prefs().maximized) api('window_control', 'maximize');
    startNetWatch();
  }

  /** 按「启动页面」决定首次进哪一页；带 hash 进来（刷新/深链）就不干预。 */
  function pickStartPage() {
    if ((location.hash || '').replace(/^#\/?/, '')) return '';
    const p = prefs();
    const want = p.startPage || 'last';
    const target = want === 'last' ? (p.lastPage || 'home') : want;
    return PAGES[target] && target !== 'home' ? target : '';
  }

  function bindChrome() {
    window.addEventListener('hashchange', route);

    document.addEventListener('click', (ev) => {
      const goBtn = ev.target.closest('[data-go]');
      if (goBtn) {
        go(goBtn.dataset.go, { newNote: goBtn.dataset.new === '1', timeTab: goBtn.dataset.timeTab });
      }
    });

    $('#netPill').onclick = async () => {
      const res = await api('net_state', true);
      if (res && typeof res.online === 'boolean') {
        setNet(res.online);
        toast(res.online ? '网络已连接' : '当前没有网络连接', res.online ? 'ok' : 'err');
      }
    };
  }

  function setNet(online) {
    state.online = online;
    const pill = $('#netPill');
    pill.classList.toggle('online', online);
    pill.classList.toggle('offline', !online);
    pill.querySelector('span').textContent = online ? '已联网' : '离线 · 本地可用';
  }

  let netTimer = null;
  function startNetWatch() {
    clearInterval(netTimer);
    netTimer = setInterval(async () => {
      if (document.hidden) return;
      const res = await api('net_state');
      if (res && typeof res.online === 'boolean' && res.online !== state.online) {
        setNet(res.online);
        toast(res.online ? '网络已恢复' : '已断网，本地功能仍可用', res.online ? 'ok' : 'info');
      }
    }, 25000);
  }

  function syncBadges() {
    const set = (id, value) => {
      const el = $(id);
      if (!el) return;
      const count = Number(value) || 0;
      el.textContent = count;
      el.hidden = count <= 0;
    };
    set('#navNotes', state.notes.stats.total);
    set('#navTodo', state.todo.stats && state.todo.stats.today_count);
    set('#navFav', state.historyStats.favorites);
  }

  /* ---------------- 概览 ---------------- */
  async function refreshHome() {
    const now = new Date();
    const hour = now.getHours();
    const hello = hour < 6 ? '凌晨好' : hour < 9 ? '早上好' : hour < 12 ? '上午好'
      : hour < 14 ? '中午好' : hour < 18 ? '下午好' : '晚上好';
    $('#greeting').textContent = `${hello}`;
    const week = ['星期日', '星期一', '星期二', '星期三', '星期四', '星期五', '星期六'][now.getDay()];
    $('#greetingSub').textContent = `${now.getMonth() + 1}月${now.getDate()}日 ${week}`;

    const todayKey = planDateKey(now);
    const [todoRes, noteRes, histRes, planRes] = await Promise.all([
      api('todo_list', 'today'),
      api('notes_list'),
      api('history_list', '', false, 4),
      state.plan.date === todayKey && state.plan.items.length
        ? Promise.resolve({ ok: true, items: state.plan.items })
        : api('plan_get', todayKey),
    ]);

    if (todoRes && todoRes.ok) {
      state.todo.stats = todoRes.stats || state.todo.stats;
      const items = todoRes.items || [];
      $('#statToday').textContent = (todoRes.stats && todoRes.stats.today_count) || 0;
      const overdue = items.filter((it) => it.is_overdue).length;
      $('#statTodaySub').textContent = overdue ? `${overdue} 件已逾期` : '件待处理';
      renderHomeTodos(items);
    }

    if (noteRes && noteRes.ok) {
      state.notes.items = noteRes.items || [];
      state.notes.stats = noteRes.stats || state.notes.stats;
      $('#statNotes').textContent = state.notes.stats.total || 0;
      $('#statNotesSub').textContent = state.notes.stats.pinned ? `${state.notes.stats.pinned} 篇置顶` : '篇';
      renderHomeNotes();
    }

    if (histRes && histRes.ok) {
      state.historyStats = histRes.stats || state.historyStats;
      $('#statHistory').textContent = state.historyStats.total || 0;
      $('#statFav').textContent = state.historyStats.favorites || 0;
      renderHomeHistory(histRes.items || []);
    }

    if (planRes && planRes.ok) {
      if (planRes.items) state.plan.items = planRes.items;
      const plan = planStats(state.plan.items);
      $('#statPlan').textContent = plan.total ? `${plan.done}/${plan.total}` : '0';
      $('#statPlanSub').textContent = plan.total
        ? `已排 ${Math.round(plan.minutes / 6) / 10} 小时`
        : '项安排';
      syncPlanDot();
    }

    syncBadges();
  }

  function renderHomeTodos(items) {
    const host = $('#homeTodos');
    if (!items.length) {
      host.innerHTML = `<li class="mini-empty">今天没有待办，清静。</li>`;
      return;
    }
    host.innerHTML = items.slice(0, 5).map((it) => `
      <li>
        <button class="mini-check" data-home-todo="${esc(it.id)}" title="标记完成"></button>
        <span class="mini-title">${esc(it.title)}</span>
        <span class="mini-meta ${it.is_overdue ? 'overdue' : ''}">${it.is_overdue ? '逾期 · ' : ''}${esc(dueLabel(it.due_at) || '')}</span>
      </li>`).join('');
    $$('[data-home-todo]', host).forEach((btn) => {
      btn.onclick = async () => {
        const res = await api('todo_complete', btn.dataset.homeTodo);
        if (res.ok) {
          toast(res.follow_up ? `已完成，下次 ${dueLabel(res.follow_up.due_at)}` : '已完成', 'ok');
          await refreshHome();
          if (currentPage() === 'todo') await loadTodo();
        } else toast(res.error || '操作失败', 'err');
      };
    });
  }

  function renderHomeNotes() {
    const host = $('#homeNotes');
    const items = state.notes.items.slice(0, 4);
    if (!items.length) {
      host.innerHTML = `<li class="mini-empty">还没有笔记，记下第一笔吧。</li>`;
      return;
    }
    host.innerHTML = items.map((n) => `
      <li>
        <button class="mini-link" data-home-note="${esc(n.id)}">
          <span class="mini-title">${esc(n.title || '无标题')}</span>
          <span class="mini-meta">${esc(relTime(n.updated || n.ts))}</span>
        </button>
      </li>`).join('');
    $$('[data-home-note]', host).forEach((btn) => {
      btn.onclick = () => {
        state.notes.currentId = btn.dataset.homeNote;
        go('notes');
      };
    });
  }

  function renderHomeHistory(items) {
    const host = $('#homeHistory');
    if (!items.length) {
      host.innerHTML = `<li class="mini-empty">还没有翻译记录。</li>`;
      return;
    }
    host.innerHTML = items.map((it) => `
      <li>
        <button class="mini-link" data-home-hist="${esc(it.id)}">
          <span class="mini-title">${esc(it.text)}</span>
          <span class="mini-meta">${esc(relTime(it.ts))}</span>
        </button>
      </li>`).join('');
    $$('[data-home-hist]', host).forEach((btn) => {
      btn.onclick = () => {
        const item = items.find((x) => x.id === btn.dataset.homeHist);
        if (!item) return;
        loadRecordIntoTranslate(item);
      };
    });
  }

  /* ---------------- 每日规划 ---------------- */
  const PLAN_START = 6;
  const PLAN_END = 24;
  const PLAN_HOUR_H = 56;

  function planDateKey(d) {
    return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
  }

  function planDateFromKey(key) {
    const [y, m, d] = String(key).split('-').map(Number);
    return new Date(y, (m || 1) - 1, d || 1);
  }

  function toMinutes(hhmm) {
    const [h, m] = String(hhmm || '0:0').split(':').map(Number);
    return (h || 0) * 60 + (m || 0);
  }

  function toHHMM(minutes) {
    const value = Math.max(0, Math.min(24 * 60, Math.round(minutes)));
    return `${pad(Math.floor(value / 60))}:${pad(value % 60)}`;
  }

  function planStats(items) {
    const list = items || [];
    return {
      total: list.length,
      done: list.filter((it) => it.done).length,
      minutes: list.reduce((sum, it) => sum + Math.max(0, toMinutes(it.end) - toMinutes(it.start)), 0),
    };
  }

  function planDayLabel(key) {
    const date = planDateFromKey(key);
    const now = new Date();
    const week = ['星期日', '星期一', '星期二', '星期三', '星期四', '星期五', '星期六'][date.getDay()];
    const label = `${date.getMonth() + 1}月${date.getDate()}日 ${week}`;
    const diff = Math.round((new Date(date.getFullYear(), date.getMonth(), date.getDate())
      - new Date(now.getFullYear(), now.getMonth(), now.getDate())) / 86400000);
    let sub = '';
    if (diff === 0) sub = '今天';
    else if (diff === 1) sub = '明天';
    else if (diff === 2) sub = '后天';
    else if (diff === -1) sub = '昨天';
    else if (diff === -2) sub = '前天';
    else if (diff > 0) sub = `${diff} 天后`;
    else sub = `${-diff} 天前`;
    return { label, sub, diff };
  }

  async function renderPlanPage() {
    if (!state.plan.date) state.plan.date = planDateKey(new Date());
    await loadPlan();
  }

  async function loadPlan() {
    const res = await api('plan_get', state.plan.date);
    if (!res || !res.ok) {
      toast((res && res.error) || '加载规划失败', 'err');
      return;
    }
    state.plan.items = res.items || [];
    state.plan.stats = planStats(state.plan.items);
    renderPlan();
    syncPlanDot();
  }

  function syncPlanDot() {
    const dot = $('#navPlanDot');
    if (!dot) return;
    const today = planDateKey(new Date());
    dot.hidden = !(state.plan.date === today && state.plan.items.length);
  }

  function renderPlan() {
    const key = state.plan.date;
    const info = planDayLabel(key);
    $('#planDateLabel').textContent = info.label;
    $('#planDateSub').textContent = info.sub;
    $('#planTodayBtn').hidden = info.diff === 0;

    const items = state.plan.items || [];
    const stats = planStats(items);
    const hours = Math.round(stats.minutes / 6) / 10;
    $('#planStat').textContent = stats.total
      ? `${stats.done}/${stats.total} 项完成 · 已排 ${hours} 小时`
      : '今天还没有安排';
    const dayMinutes = (PLAN_END - PLAN_START) * 60;
    $('#planFree').textContent = stats.total ? `空余 ${Math.max(0, Math.round((dayMinutes - stats.minutes) / 6) / 10)} 小时` : '';
    $('#planProgress').style.width = `${stats.total ? (stats.done / stats.total) * 100 : 0}%`;
    $('#planSideSub').textContent = stats.total ? `${stats.total} 项 · ${stats.done} 项已完成` : '还没有安排';

    // 小时刻度
    const hourHost = $('#planHours');
    if (hourHost.childElementCount !== PLAN_END - PLAN_START) {
      let html = '';
      for (let h = PLAN_START; h < PLAN_END; h += 1) {
        html += `<div class="plan-hour">${pad(h)}:00</div>`;
      }
      hourHost.innerHTML = html;
    }

    const body = $('#planBody');
    const totalH = (PLAN_END - PLAN_START) * PLAN_HOUR_H;
    body.style.height = `${totalH}px`;

    // 时间块：重叠时自动分列
    const positioned = layoutPlan(items);
    const blocks = positioned.map(({ item, col, cols }) => {
      const top = ((toMinutes(item.start) - PLAN_START * 60) / 60) * PLAN_HOUR_H;
      const height = ((toMinutes(item.end) - toMinutes(item.start)) / 60) * PLAN_HOUR_H;
      const h = Math.max(22, height - 3);
      const width = `calc(${(100 / cols).toFixed(4)}% - 12px)`;
      const left = `calc(${((col * 100) / cols).toFixed(4)}% + 6px)`;
      const mini = h < 34;
      return `<div class="plan-block ${item.done ? 'done' : ''} ${mini ? 'mini' : ''}"
        data-plan-id="${esc(item.id)}"
        style="top:${top.toFixed(1)}px;height:${h.toFixed(1)}px;left:${left};width:${width};background:${catColor(item.category)}">
        <b title="${esc(item.title)}">${esc(item.title)}</b>
        ${mini ? '' : `<span>${esc(item.start)}–${esc(item.end)}${item.notes ? ' · ' + esc(item.notes) : ''}</span>`}
      </div>`;
    }).join('');

    const nowLine = body.querySelector('#planNow');
    body.innerHTML = blocks;
    if (nowLine) body.appendChild(nowLine);

    // 当前时间线
    const now = new Date();
    const nowMinutes = now.getHours() * 60 + now.getMinutes();
    const showNow = info.diff === 0 && nowMinutes >= PLAN_START * 60 && nowMinutes <= PLAN_END * 60;
    const line = $('#planNow');
    line.hidden = !showNow;
    if (showNow) {
      line.style.top = `${(((nowMinutes - PLAN_START * 60) / 60) * PLAN_HOUR_H).toFixed(1)}px`;
      line.innerHTML = `<i></i><em>${pad(now.getHours())}:${pad(now.getMinutes())}</em>`;
    }

    // 打开页面时把时间轴滚到「现在」附近
    if (state.plan.scrollKey !== key) {
      state.plan.scrollKey = key;
      const scroller = $('#planScroll');
      scroller.scrollTop = showNow
        ? Math.max(0, (((nowMinutes - PLAN_START * 60) / 60) * PLAN_HOUR_H) - 150)
        : 0;
    }

    // 打开页面时把时间轴滚到「现在」附近
    if (state.plan.scrollKey !== key) {
      state.plan.scrollKey = key;
      const scroller = $('#planScroll');
      scroller.scrollTop = showNow
        ? Math.max(0, (((nowMinutes - PLAN_START * 60) / 60) * PLAN_HOUR_H) - 150)
        : 0;
    }

    $$('#planBody .plan-block').forEach((el) => {
      el.onclick = (ev) => {
        ev.stopPropagation();
        const item = state.plan.items.find((it) => it.id === el.dataset.planId);
        if (item) openPlanEditor(item);
      };
    });

    // 右侧列表
    const listHost = $('#planList');
    if (!items.length) {
      listHost.innerHTML = `<li class="empty small">${ic('plan')}<p>这天还是空的</p></li>`;
    } else {
      listHost.innerHTML = items.map((it) => `
        <li class="${it.done ? 'done' : ''}" data-side-id="${esc(it.id)}">
          <button class="plan-check ${it.done ? 'on' : ''}" data-plan-toggle="${esc(it.id)}" title="${it.done ? '标记未完成' : '标记完成'}">${ic('check')}</button>
          <div style="flex:1;min-width:0">
            <strong>${esc(it.title)}</strong>
            <small>${esc(it.start)}–${esc(it.end)} · ${esc(catName(it.category))}</small>
          </div>
        </li>`).join('');
      $$('#planList [data-plan-toggle]').forEach((btn) => {
        btn.onclick = (ev) => {
          ev.stopPropagation();
          togglePlanDone(btn.dataset.planToggle);
        };
      });
      $$('#planList [data-side-id]').forEach((li) => {
        li.onclick = () => {
          const item = state.plan.items.find((it) => it.id === li.dataset.sideId);
          if (item) openPlanEditor(item);
        };
      });
    }

    // 分类用时
    const legendHost = $('#planCats');
    const byCat = CATEGORIES.map((cat) => ({
      ...cat,
      minutes: items.filter((it) => it.category === cat.id)
        .reduce((sum, it) => sum + Math.max(0, toMinutes(it.end) - toMinutes(it.start)), 0),
    })).filter((c) => c.minutes > 0);
    if (!byCat.length) {
      legendHost.innerHTML = `<li class="empty small">${ic('grid')}<p>安排之后这里会显示用时</p></li>`;
    } else {
      const max = Math.max(...byCat.map((c) => c.minutes));
      legendHost.innerHTML = byCat.map((c) => `
        <li>
          <span class="dot" style="background:${c.color}"></span>
          <span class="name">${esc(c.name)}</span>
          <span class="bar"><i style="width:${(c.minutes / max) * 100}%;background:${c.color}"></i></span>
          <em>${Math.round(c.minutes / 6) / 10} 小时</em>
        </li>`).join('');
    }
  }

  /** 同一时段重叠的安排自动分列显示。 */
  function layoutPlan(items) {
    const sorted = items.slice().sort((a, b) => toMinutes(a.start) - toMinutes(b.start) || toMinutes(b.end) - toMinutes(a.end));
    const columns = [];
    const placed = sorted.map((item) => {
      const start = toMinutes(item.start);
      const end = toMinutes(item.end);
      let col = columns.findIndex((colEnd) => colEnd <= start);
      if (col === -1) {
        col = columns.length;
        columns.push(end);
      } else {
        columns[col] = Math.max(columns[col], end);
      }
      return { item, col };
    });
    // 每块按覆盖到的最大列数确定宽度
    return placed.map((entry) => {
      const start = toMinutes(entry.item.start);
      const end = toMinutes(entry.item.end);
      const overlapping = placed.filter((other) => {
        const s2 = toMinutes(other.item.start);
        const e2 = toMinutes(other.item.end);
        return s2 < end && e2 > start;
      });
      const cols = Math.max(1, ...overlapping.map((o) => o.col + 1));
      return { ...entry, cols };
    });
  }

  function planPreset(hour) {
    const now = new Date();
    const base = hour != null ? hour * 60 : Math.min(23 * 60, Math.max(6 * 60, Math.ceil((now.getHours() * 60 + now.getMinutes()) / 30) * 30));
    return { start: toHHMM(base), end: toHHMM(Math.min(24 * 60, base + 60)), category: 'work' };
  }

  function openPlanEditor(item, preset) {
    const isNew = !item;
    const data = item || { title: '', notes: '', done: false, ...(preset || planPreset()) };
    const info = planDayLabel(state.plan.date);
    let pickedCat = data.category || 'work';

    const catChips = () => CATEGORIES.map((c) =>
      `<button class="dt-chip ${c.id === pickedCat ? 'active' : ''}" data-cat="${c.id}">
        <span class="dot" style="display:inline-block;width:6px;height:6px;border-radius:50%;background:${c.color};margin-right:5px"></span>${c.name}
      </button>`).join('');

    const modal = openModal({
      title: isNew ? '添加安排' : '编辑安排',
      subtitle: `${info.label} · ${info.sub}`,
      body: `<div class="form-grid">
        <div class="form-field full"><label>做什么</label>
          <input id="plTitle" maxlength="60" placeholder="例如：写周报 / 健身 / 读书" value="${esc(data.title)}"></div>
        <div class="form-field"><label>开始</label><input id="plStart" type="time" step="300" value="${esc(data.start)}"></div>
        <div class="form-field"><label>结束</label><input id="plEnd" type="time" step="300" value="${esc(data.end)}"></div>
        <div class="form-field full"><label>分类</label><div class="dt-chips" id="plCats">${catChips()}</div></div>
        <div class="form-field full"><label>备注</label>
          <input id="plNotes" maxlength="120" placeholder="可选" value="${esc(data.notes || '')}"></div>
      </div>`,
      footer: `${isNew ? '' : '<button class="btn danger-quiet" data-del style="margin-right:auto">删除</button>'}
        <button class="btn" data-cancel>取消</button>
        <button class="btn btn-primary" data-ok>${isNew ? '添加' : '保存'}</button>`,
    });

    const syncCat = () => {
      $$('#plCats [data-cat]', modal.body).forEach((btn) => {
        btn.classList.toggle('active', btn.dataset.cat === pickedCat);
      });
    };
    $$('#plCats [data-cat]', modal.body).forEach((btn) => {
      btn.onclick = () => { pickedCat = btn.dataset.cat; syncCat(); };
    });

    modal.foot.querySelector('[data-cancel]').onclick = () => modal.close();

    const del = modal.foot.querySelector('[data-del]');
    if (del) {
      del.onclick = async () => {
        const ok = await confirmAction({ title: '删除这条安排？', message: data.title, confirm: '删除' });
        if (!ok) return;
        modal.close();
        await savePlanItems(state.plan.items.filter((it) => it.id !== data.id));
        toast('已删除', 'ok', 1400);
      };
    }

    modal.foot.querySelector('[data-ok]').onclick = async () => {
      const title = $('#plTitle').value.trim();
      if (!title) { toast('写上要做什么', 'info'); $('#plTitle').focus(); return; }
      const start = $('#plStart').value || '09:00';
      const end = $('#plEnd').value || '10:00';
      if (toMinutes(end) <= toMinutes(start)) { toast('结束时间要晚于开始时间', 'info'); return; }
      const next = {
        id: data.id || '',
        title,
        start,
        end,
        category: pickedCat,
        notes: $('#plNotes').value.trim(),
        done: !!data.done,
      };
      const items = state.plan.items.filter((it) => it.id !== data.id);
      items.push(next);
      items.sort((a, b) => toMinutes(a.start) - toMinutes(b.start));
      modal.close();
      await savePlanItems(items);
      toast(isNew ? '已加入日程' : '已保存', 'ok', 1400);
    };
  }

  async function savePlanItems(items) {
    const res = await api('plan_save', state.plan.date, items);
    if (!res || !res.ok) { toast((res && res.error) || '保存失败', 'err'); return; }
    state.plan.items = res.items || [];
    state.plan.stats = planStats(state.plan.items);
    renderPlan();
    syncPlanDot();
    if (currentPage() === 'home') refreshHome();
  }

  async function togglePlanDone(id) {
    const items = state.plan.items.map((it) => (it.id === id ? { ...it, done: !it.done } : it));
    await savePlanItems(items);
  }

  async function importPlanFromTodo() {
    const today = planDateKey(new Date());
    if (state.plan.date !== today) {
      toast('先回到今天，才能导入今日待办', 'info', 3000);
      return;
    }
    const res = await api('todo_list', 'today');
    if (!res || !res.ok) { toast((res && res.error) || '读取待办失败', 'err'); return; }
    const items = (res.items || []).filter((it) => it.status !== 'done' && it.due_at);
    if (!items.length) { toast('今天的待办都没有具体时间', 'info', 3000); return; }

    const existing = new Set(state.plan.items.map((it) => it.title.trim()));
    const next = state.plan.items.slice();
    let added = 0;
    items.forEach((it) => {
      const due = parseLocal(it.due_at);
      if (!due || !sameDay(due, new Date())) return;
      if (existing.has((it.title || '').trim())) return;
      const start = due.getHours() * 60 + due.getMinutes();
      next.push({
        id: '',
        title: it.title,
        start: toHHMM(start),
        end: toHHMM(Math.min(24 * 60, start + 30)),
        category: 'work',
        notes: '',
        done: false,
      });
      existing.add((it.title || '').trim());
      added += 1;
    });
    if (!added) { toast('这些待办都已经在日程里了', 'info'); return; }
    await savePlanItems(next);
    toast(`已导入 ${added} 条待办`, 'ok');
  }

  function bindPlanPage() {
    const shift = async (days) => {
      const date = planDateFromKey(state.plan.date);
      date.setDate(date.getDate() + days);
      state.plan.date = planDateKey(date);
      await loadPlan();
    };
    $('#planPrev').onclick = () => shift(-1);
    $('#planNext').onclick = () => shift(1);
    $('#planTodayBtn').onclick = async () => {
      state.plan.date = planDateKey(new Date());
      await loadPlan();
    };
    $('#planAdd').onclick = () => openPlanEditor(null, planPreset());
    $('#planFromTodo').onclick = importPlanFromTodo;

    $('#planBody').addEventListener('click', (ev) => {
      if (ev.target.closest('.plan-block')) return;
      const rect = $('#planBody').getBoundingClientRect();
      const y = ev.clientY - rect.top;
      const raw = PLAN_START * 60 + (y / PLAN_HOUR_H) * 60;
      const start = Math.max(PLAN_START * 60, Math.min(PLAN_END * 60 - 30, Math.round(raw / 30) * 30));
      openPlanEditor(null, { start: toHHMM(start), end: toHHMM(Math.min(24 * 60, start + 60)), category: 'work' });
    });
  }

  /* ---------------- 翻译 ---------------- */
  function buildLanguageSelects() {
    const opts = state.langs.map((l) => `<option value="${esc(l.id)}">${esc(l.name)}</option>`).join('');
    $('#srcLang').innerHTML = opts;
    $('#dstLang').innerHTML = state.langs.filter((l) => l.id !== 'auto')
      .map((l) => `<option value="${esc(l.id)}">${esc(l.name)}</option>`).join('');
    $('#setTarget').innerHTML = $('#dstLang').innerHTML;
  }

  function buildProviderSelects() {
    const opts = state.providers.map((p) => `<option value="${esc(p.key)}">${esc(p.label)}</option>`).join('');
    $('#provider').innerHTML = opts;
    $('#setProvider').innerHTML = opts;
  }

  function syncTranslateSettings() {
    const s = state.settings;
    $('#srcLang').value = s.source_lang || 'auto';
    $('#dstLang').value = s.target_lang || 'zh-Hans';
    $('#provider').value = s.provider || 'auto';
    setSwitch($('#autoToggle'), !!s.auto_translate);
  }

  function setSwitch(el, on) {
    if (!el) return;
    el.classList.toggle('on', on);
    el.setAttribute('aria-checked', on ? 'true' : 'false');
  }

  function onTranslateInput() {
    const text = $('#srcText').value;
    $('#srcCount').textContent = `${text.length} 字`;
    if (!text.trim()) {
      $('#srcHint').textContent = '自动检测语言';
    }
    clearTimeout(state.trans.detectTimer);
    state.trans.detectTimer = setTimeout(async () => {
      if (!text.trim()) return;
      const res = await api('detect_language', text);
      if (res && res.ok && res.lang) $('#srcHint').textContent = `检测到 ${langName(res.lang)}`;
    }, 500);

    if (state.settings.auto_translate) {
      clearTimeout(state.trans.autoTimer);
      state.trans.autoTimer = setTimeout(() => {
        if ($('#srcText').value.trim()) doTranslate();
      }, Math.max(400, Number(state.settings.auto_translate_delay) || 900));
    }
  }

  async function doTranslate() {
    if (state.trans.busy) return;
    const text = $('#srcText').value.trim();
    if (!text) {
      toast('先输入要翻译的内容', 'info');
      $('#srcText').focus();
      return;
    }
    const source = $('#srcLang').value;
    const target = $('#dstLang').value;
    const provider = $('#provider').value;
    if (provider === 'ai' && !aiConfigured()) {
      toast('AI 接口还没配置，去「设置 → AI 翻译接口」填一下', 'info', 3600);
    }

    state.trans.busy = true;
    const btn = $('#doTranslate');
    const original = btn.innerHTML;
    btn.disabled = true;
    btn.innerHTML = `${ic('refresh')}翻译中…`;
    $('#dstText').classList.add('loading');
    $('#dstText').innerHTML = `<div class="empty small"><svg class="spin"><use href="#i-refresh"/></svg><p>正在翻译…</p></div>`;

    const args = provider && provider !== 'auto' ? [text, source, target, provider] : [text, source, target];
    const res = await api('translate', ...args);

    state.trans.busy = false;
    btn.disabled = false;
    btn.innerHTML = original;
    $('#dstText').classList.remove('loading');

    if (res && res.ok) {
      state.trans.last = res;
      state.trans.entryId = res.entry ? res.entry.id : null;
      $('#dstText').textContent = res.text || '';
      $('#dstCount').textContent = `${(res.text || '').length} 字`;
      const bits = [];
      if (res.provider_label) bits.push(res.provider_label);
      if (res.elapsed_ms) bits.push(`${(res.elapsed_ms / 1000).toFixed(1)}s`);
      if (res.detected_name) bits.push(`检测 ${res.detected_name}`);
      $('#dstMeta').textContent = bits.join(' · ');
      if (res.stats) {
        state.historyStats = res.stats;
        syncBadges();
      }
      if (currentPage() === 'home') refreshHome();
    } else {
      $('#dstText').innerHTML = `<div class="empty small">${ic('warning')}<p>${esc(res.error || '翻译失败，换个通道再试试')}</p></div>`;
      $('#dstMeta').textContent = '';
      toast(res.error || '翻译失败', 'err', 4000);
    }
  }

  function loadRecordIntoTranslate(item) {
    state.notes.currentId = null;
    sessionStorage.setItem('pt.translateDraft', item.text || '');
    sessionStorage.setItem('pt.translateTarget', item.target || 'zh-Hans');
    go('translate');
  }

  async function copyText(text) {
    if (!text) return;
    const res = await api('clipboard_write', text);
    if (res && res.ok !== false) toast('已复制', 'ok', 1600);
    else toast('复制失败', 'err');
  }

  function bindTranslatePage() {
    $('#srcLang').onchange = () => saveSetting({ source_lang: $('#srcLang').value });
    $('#dstLang').onchange = () => saveSetting({ target_lang: $('#dstLang').value });
    $('#provider').onchange = () => saveSetting({ provider: $('#provider').value });
    $('#autoToggle').onclick = () => {
      const on = !$('#autoToggle').classList.contains('on');
      setSwitch($('#autoToggle'), on);
      saveSetting({ auto_translate: on });
    };

    $('#swapLang').onclick = () => {
      const src = $('#srcLang');
      const dst = $('#dstLang');
      const srcVal = src.value === 'auto' ? (state.trans.last && state.trans.last.detected) || 'en' : src.value;
      const dstVal = dst.value;
      if (dstVal === 'auto') return;
      src.value = dstVal;
      dst.value = srcVal;
      saveSetting({ source_lang: src.value, target_lang: dst.value });
      const result = $('#dstText').textContent.trim();
      if (result && !$('#dstText').querySelector('.empty')) {
        $('#srcText').value = result;
        $('#dstText').innerHTML = `<div class="empty small">${ic('translate')}<p>译文会显示在这里</p></div>`;
        $('#dstMeta').textContent = '';
        $('#dstCount').textContent = '';
        onTranslateInput();
      }
    };

    $('#srcText').addEventListener('input', onTranslateInput);
    $('#srcText').addEventListener('keydown', (ev) => {
      if (ev.key === 'Enter' && (ev.ctrlKey || ev.metaKey)) {
        ev.preventDefault();
        doTranslate();
      }
    });
    $('#doTranslate').onclick = doTranslate;
    $('#srcClear').onclick = () => {
      $('#srcText').value = '';
      $('#dstText').innerHTML = `<div class="empty small">${ic('translate')}<p>译文会显示在这里</p></div>`;
      $('#dstMeta').textContent = '';
      $('#dstCount').textContent = '';
      $('#srcHint').textContent = '自动检测语言';
      $('#srcCount').textContent = '0 字';
      $('#srcText').focus();
    };

    $$('[data-dst]').forEach((btn) => {
      btn.onclick = async () => {
        const act = btn.dataset.dst;
        const last = state.trans.last;
        if (!last) { toast('先翻译一段内容', 'info'); return; }
        if (act === 'copy') return copyText(last.text);
        if (act === 'speak') {
          const res = await api('speak', last.text, last.target);
          if (res && res.ok && res.url) {
            try { await new Audio(res.url).play(); } catch { toast('朗读失败', 'err'); }
          } else toast((res && res.error) || '朗读失败', 'err');
          return;
        }
        if (act === 'fav') {
          if (!state.trans.entryId) { toast('这条记录已不在历史里', 'info'); return; }
          const res = await api('history_toggle', state.trans.entryId);
          if (res.ok) {
            const on = res.item ? res.item.favorite : true;
            toast(on ? '已收藏' : '已取消收藏', 'ok');
            if (res.stats) { state.historyStats = res.stats; syncBadges(); }
          } else toast(res.error || '操作失败', 'err');
          return;
        }
        if (act === 'note') {
          const content = `原文\n${last.entry ? last.entry.text : ''}\n\n译文\n${last.text}`;
          const res = await api('notes_create', content);
          if (res.ok) {
            state.notes.items.unshift(res.item);
            state.notes.stats = res.stats || state.notes.stats;
            syncBadges();
            toast('已存为笔记', 'ok');
          } else toast(res.error || '保存失败', 'err');
        }
      };
    });
  }

  async function saveSetting(patch) {
    const res = await api('save_settings', patch);
    if (res && res.ok) {
      state.settings = res.settings || { ...state.settings, ...patch };
      syncTranslateSettings();
      syncSettingsUi();
    } else {
      toast((res && res.error) || '保存失败', 'err');
    }
  }

  /* ---------------- 记事本 ---------------- */
  let noteSaveTimer = null;

  async function renderNotesPage(resetSelection = false) {
    $('#noteSearch').value = state.notes.query || '';
    if (resetSelection && !state.notes.currentId && state.notes.items.length) {
      state.notes.currentId = state.notes.items[0].id;
    }
    renderNoteCats();
    renderNoteList();
    const current = state.notes.items.find((n) => n.id === state.notes.currentId);
    if (current) loadNoteIntoEditor(current);
    else showNoteEmpty(true);
  }

  function sortedNotes() {
    return state.notes.items.slice().sort((a, b) => {
      if (!!b.pinned !== !!a.pinned) return b.pinned ? 1 : -1;
      return (b.updated || b.ts) - (a.updated || a.ts);
    });
  }

  function noteCategory(noteId) {
    const meta = state.notes.meta[noteId];
    return (meta && meta.category) || '';
  }

  function renderNoteCats() {
    const host = $('#noteCats');
    if (!host) return;
    const counts = {};
    state.notes.items.forEach((n) => {
      const key = noteCategory(n.id);
      counts[key] = (counts[key] || 0) + 1;
    });
    const items = [{ id: '', name: '全部', color: 'transparent', count: state.notes.items.length }]
      .concat(CATEGORIES.map((c) => ({ ...c, count: counts[c.id] || 0 })));
    host.innerHTML = items.map((c) => `
      <button class="cat-chip ${state.notes.cat === c.id ? 'active' : ''}" data-note-cat="${esc(c.id)}">
        ${c.id ? `<span class="dot" style="background:${c.color}"></span>` : ''}${esc(c.name)}${c.count ? `<span style="opacity:.6">${c.count}</span>` : ''}
      </button>`).join('');
    $$('#noteCats [data-note-cat]').forEach((btn) => {
      btn.onclick = () => {
        state.notes.cat = btn.dataset.noteCat;
        renderNoteCats();
        renderNoteList();
      };
    });
  }

  function renderNoteList() {
    const host = $('#noteList');
    const query = (state.notes.query || '').trim().toLowerCase();
    let items = sortedNotes();
    if (state.notes.cat) items = items.filter((n) => noteCategory(n.id) === state.notes.cat);
    if (query) items = items.filter((n) => `${n.title} ${n.content}`.toLowerCase().includes(query));

    $('#noteCount').textContent = `${state.notes.stats.total || 0} 篇`;
    $('#noteChars').textContent = `${state.notes.stats.chars || 0} 字`;

    if (!items.length) {
      const tip = query ? '没有匹配的笔记' : state.notes.cat ? '这个分类还没有笔记' : '还没有笔记';
      host.innerHTML = `<li class="empty small">${ic('search')}<p>${tip}</p></li>`;
      return;
    }
    host.innerHTML = items.map((n) => {
      const first = (n.content || '').split('\n').find((line) => line.trim()) || '空笔记';
      const snippet = (n.content || '').split('\n').filter((l) => l.trim()).slice(1).join(' ').slice(0, 40);
      const cat = noteCategory(n.id);
      return `<li class="note-item ${n.id === state.notes.currentId ? 'active' : ''}" data-note-id="${esc(n.id)}">
        ${n.pinned ? `<svg class="pin-mark"><use href="#i-pin"/></svg>` : ''}
        <h4>${esc(n.title || first)}</h4>
        <p>${esc(snippet || '（继续写点什么）')}</p>
        <div class="note-tags">
          ${cat ? `<span class="note-cat"><span class="dot" style="background:${catColor(cat)}"></span>${esc(catName(cat))}</span>` : ''}
          <span class="note-time">${esc(relTime(n.updated || n.ts))}</span>
        </div>
      </li>`;
    }).join('');

    $$('[data-note-id]', host).forEach((el) => {
      el.onclick = () => selectNote(el.dataset.noteId);
    });
  }

  function loadNoteIntoEditor(note) {
    $('#noteEmpty').classList.remove('show');
    const body = $('#noteBody');
    if (body.value !== note.content) body.value = note.content || '';
    $('#notePinLabel').textContent = note.pinned ? '取消置顶' : '置顶';
    const noteCat = noteCategory(note.id);
    $('#noteCatLabel').textContent = noteCat ? catName(noteCat) : '分类';
    $('#noteDelLabel').textContent = '删除';
    $('#noteSaved').textContent = '';
    $('#noteMeta').textContent = `${(note.content || '').length} 字 · 创建于 ${relTime(note.ts)}`;
    $('#noteBody').disabled = false;
  }

  function showNoteEmpty(show) {
    $('#noteEmpty').classList.toggle('show', show);
    if (show) {
      $('#noteBody').value = '';
      $('#noteBody').disabled = true;
      $('#noteMeta').textContent = '';
      $('#noteSaved').textContent = '';
    }
  }

  async function selectNote(id) {
    if (!id) return;
    state.notes.currentId = id;
    const note = state.notes.items.find((n) => n.id === id);
    if (note) loadNoteIntoEditor(note);
    $$('#noteList .note-item').forEach((el) => el.classList.toggle('active', el.dataset.noteId === id));
    $('#noteBody').focus();
  }

  async function createNote() {
    const res = await api('notes_create', '');
    if (!res.ok) { toast(res.error || '新建失败', 'err'); return; }
    state.notes.items.unshift(res.item);
    state.notes.stats = res.stats || state.notes.stats;
    state.notes.currentId = res.item.id;
    state.notes.query = '';
    $('#noteSearch').value = '';
    if (state.notes.cat) {
      const metaRes = await api('note_meta_set', res.item.id, state.notes.cat);
      if (metaRes && metaRes.ok && metaRes.map) state.notes.meta = metaRes.map;
    }
    renderNoteCats();
    renderNoteList();
    loadNoteIntoEditor(res.item);
    syncBadges();
    $('#noteBody').focus();
  }

  function scheduleNoteSave() {
    const id = state.notes.currentId;
    if (!id) return;
    const content = $('#noteBody').value;
    $('#noteSaved').textContent = '正在保存…';
    clearTimeout(noteSaveTimer);
    noteSaveTimer = setTimeout(() => saveNote(id, content), 550);
  }

  async function saveNote(id, content) {
    const res = await api('notes_update', id, content);
    if (!res || !res.ok) {
      if (state.notes.currentId === id) $('#noteSaved').textContent = '保存失败';
      return;
    }
    const item = state.notes.items.find((n) => n.id === id);
    if (item) {
      item.content = res.item.content;
      item.title = res.item.title;
      item.updated = res.item.updated;
      const row = $(`#noteList [data-note-id="${CSS.escape(id)}"]`);
      if (row) {
        const h4 = row.querySelector('h4');
        if (h4) h4.textContent = item.title || '无标题';
        const time = row.querySelector('.note-time');
        if (time) time.textContent = relTime(item.updated);
      }
    }
    state.notes.stats = res.stats || state.notes.stats;
    if (state.notes.currentId === id) {
      $('#noteSaved').textContent = `已保存 ${pad(new Date().getHours())}:${pad(new Date().getMinutes())}`;
      $('#noteMeta').textContent = `${content.length} 字 · 创建于 ${relTime(item ? item.ts : Date.now() / 1000)}`;
    }
    syncBadges();
  }

  function openNoteCategory(note) {
    const current = noteCategory(note.id);
    const modal = openModal({
      title: '给笔记分个类',
      subtitle: note.title || '无标题',
      body: `<div class="dt-chips" id="noteCatPick">
        <button class="dt-chip ${current ? '' : 'active'}" data-cat="">未分类</button>
        ${CATEGORIES.map((c) => `<button class="dt-chip ${current === c.id ? 'active' : ''}" data-cat="${c.id}">
          <span style="display:inline-block;width:6px;height:6px;border-radius:50%;background:${c.color};margin-right:5px"></span>${c.name}
        </button>`).join('')}
      </div><p class="dt-tip" style="margin-top:12px">分类只影响筛选和显示，不会改动笔记内容。</p>`,
      footer: `<button class="btn" data-cancel>关闭</button>`,
    });
    modal.foot.querySelector('[data-cancel]').onclick = () => modal.close();
    $$('#noteCatPick [data-cat]', modal.body).forEach((btn) => {
      btn.onclick = async () => {
        const res = await api('note_meta_set', note.id, btn.dataset.cat);
        if (!res || !res.ok) { toast((res && res.error) || '设置失败', 'err'); return; }
        state.notes.meta = res.map || {};
        modal.close();
        renderNoteCats();
        renderNoteList();
        loadNoteIntoEditor(note);
        toast(btn.dataset.cat ? `已归到「${catName(btn.dataset.cat)}」` : '已取消分类', 'ok', 1400);
      };
    });
  }

  function bindNotesPage() {
    $('#noteNew').onclick = createNote;
    $('#noteEmptyNew').onclick = createNote;
    $('#noteBody').addEventListener('input', scheduleNoteSave);
    $('#noteSearch').addEventListener('input', debounce((ev) => {
      state.notes.query = ev.target.value;
      renderNoteList();
    }, 180));

    $$('[data-note]').forEach((btn) => {
      btn.onclick = async () => {
        const id = state.notes.currentId;
        if (!id) { toast('先选中一篇笔记', 'info'); return; }
        const note = state.notes.items.find((n) => n.id === id);
        const act = btn.dataset.note;

        if (act === 'time') {
          const ta = $('#noteBody');
          const value = stamp();
          const start = ta.selectionStart;
          const insert = `${start > 0 ? '\n' : ''}${value}\n`;
          ta.setRangeText(insert, start, ta.selectionEnd, 'end');
          ta.focus();
          scheduleNoteSave();
          return;
        }
        if (act === 'copy') return copyText(note.content);

        if (act === 'category') { openNoteCategory(note); return; }

        if (act === 'pin') {
          const res = await api('notes_pin', id);
          if (res.ok) {
            note.pinned = res.item.pinned;
            state.notes.stats = res.stats || state.notes.stats;
            $('#notePinLabel').textContent = note.pinned ? '取消置顶' : '置顶';
    const noteCat = noteCategory(note.id);
    $('#noteCatLabel').textContent = noteCat ? catName(noteCat) : '分类';
            renderNoteList();
            syncBadges();
            toast(note.pinned ? '已置顶' : '已取消置顶', 'ok', 1500);
          } else toast(res.error || '操作失败', 'err');
          return;
        }

        if (act === 'translate') {
          const content = ($('#noteBody').value || '').trim();
          if (!content) { toast('这篇笔记是空的', 'info'); return; }
          const det = await api('detect_language', content);
          const lang = (det && det.lang) || 'en';
          const target = lang.startsWith('zh') ? 'en' : 'zh-Hans';
          sessionStorage.setItem('pt.translateDraft', content);
          sessionStorage.setItem('pt.translateTarget', target);
          go('translate');
          return;
        }

        if (act === 'delete') {
          const ok = await confirmAction({
            title: '删除这篇笔记？',
            message: `「${note.title || '无标题'}」删除后无法恢复。`,
            confirm: '删除',
          });
          if (!ok) return;
          const res = await api('notes_delete', id);
          if (res.ok) {
            state.notes.items = state.notes.items.filter((n) => n.id !== id);
            delete state.notes.meta[id];
            state.notes.stats = res.stats || state.notes.stats;
            state.notes.currentId = (sortedNotes()[0] || {}).id || null;
            renderNoteList();
            const next = state.notes.items.find((n) => n.id === state.notes.currentId);
            if (next) loadNoteIntoEditor(next);
            else showNoteEmpty(true);
            syncBadges();
            toast('已删除', 'ok', 1500);
          } else toast(res.error || '删除失败', 'err');
        }
      };
    });
  }

  /* ---------------- 待办 ---------------- */
  function todoDueMeta(item) {
    const bits = [];
    if (item.due_at) {
      const label = dueLabel(item.due_at);
      const overdue = !!item.is_overdue;
      bits.push(`<span class="${overdue ? 'overdue' : ''}">${esc(overdue ? `已逾期 · ${label}` : label)}</span>`);
    }
    if (item.repeat_rule && item.repeat_rule !== 'none') {
      const meta = (state.todo.meta.repeats || []).find((r) => r.id === item.repeat_rule);
      bits.push(`<span class="rep">${ic('refresh')}${esc(meta ? meta.name : item.repeat_rule)}</span>`);
    }
    if (item.priority === 'high') bits.push('<span class="overdue">高优先级</span>');
    (item.tags || []).forEach((tag) => bits.push(`<span class="tag">#${esc(tag)}</span>`));
    if (item.notes) bits.push(`<span>${esc(item.notes.slice(0, 30))}</span>`);
    return bits.join('');
  }

  function renderTodo() {
    const host = $('#todoList');
    const items = state.todo.items || [];
    const view = state.todo.view;

    $('#tabToday').textContent = (state.todo.stats.today_count || 0);
    $('#tabAll').textContent = (state.todo.stats.todo_count || 0);
    $('#tabDone').textContent = (state.todo.stats.done_count || 0);
    $('#todoClearDone').hidden = view !== 'done' || !items.length;

    if (!items.length) {
      const text = view === 'done' ? '还没有完成的任务' : view === 'today' ? '今天没有待办' : '没有未完成的任务';
      host.innerHTML = `<li class="empty">${ic(view === 'done' ? 'check' : 'todo')}<p>${text}</p></li>`;
      return;
    }

    const groups = groupTodos(items, view);
    let html = '';
    groups.forEach((group) => {
      if (group.label) {
        html += `<li class="todo-section-label">${esc(group.label)}<em>${group.items.length}</em></li>`;
      }
      html += group.items.map(todoRow).join('');
    });
    host.innerHTML = html;

    $$('[data-todo-act]', host).forEach((btn) => {
      btn.onclick = (ev) => {
        ev.stopPropagation();
        const id = btn.closest('[data-todo-id]').dataset.todoId;
        todoAction(btn.dataset.todoAct, id);
      };
    });
    $$('[data-todo-row]', host).forEach((row) => {
      row.onclick = (ev) => {
        if (ev.target.closest('button')) return;
        const item = state.todo.items.find((it) => it.id === row.dataset.todoId);
        if (item) openTodoEditor(item);
      };
    });

    // 从全局搜索跳过来时，把那条任务闪一下
    if (state.todo.highlight) {
      const target = $(`[data-todo-id="${state.todo.highlight}"]`, host);
      state.todo.highlight = '';
      if (target) {
        target.classList.add('flash');
        target.scrollIntoView({ block: 'center', behavior: 'smooth' });
        setTimeout(() => target.classList.remove('flash'), 2200);
      }
    }
  }

  /** 待办分组：今日按 已逾期/上午/下午/晚上/未定时间，全部按日期分。 */
  function groupTodos(items, view) {
    if (view === 'done') return [{ label: '', items }];

    const byTime = (a, b) => {
      const ta = a.due_at ? new Date(a.due_at).getTime() : Infinity;
      const tb = b.due_at ? new Date(b.due_at).getTime() : Infinity;
      return ta - tb;
    };
    const hasClock = (item) => {
      const d = parseLocal(item.due_at);
      return !!(d && (d.getHours() || d.getMinutes()));
    };
    const groups = [];
    const push = (label, list) => { if (list.length) groups.push({ label, items: list }); };

    if (view === 'today') {
      const overdue = items.filter((it) => it.is_overdue).sort(byTime);
      const rest = items.filter((it) => !it.is_overdue);
      push('已逾期', overdue);
      [
        { label: '上午', test: (h) => h < 12 },
        { label: '下午', test: (h) => h >= 12 && h < 18 },
        { label: '晚上', test: (h) => h >= 18 },
      ].forEach((bucket) => {
        push(bucket.label, rest.filter((it) => {
          const d = parseLocal(it.due_at);
          return d && hasClock(it) && bucket.test(d.getHours());
        }).sort(byTime));
      });
      push('未定时间', rest.filter((it) => !hasClock(it)).sort(byTime));
      return groups;
    }

    const map = new Map();
    items.forEach((it) => {
      const d = parseLocal(it.due_at);
      const key = d ? planDateKey(d) : 'none';
      if (!map.has(key)) map.set(key, []);
      map.get(key).push(it);
    });
    const keys = [...map.keys()].sort((a, b) => {
      if (a === 'none') return 1;
      if (b === 'none') return -1;
      return a.localeCompare(b);
    });
    const today = new Date();
    const todayStart = new Date(today.getFullYear(), today.getMonth(), today.getDate());
    keys.forEach((key) => {
      const list = map.get(key).sort(byTime);
      if (key === 'none') {
        groups.push({ label: '未安排时间', items: list });
        return;
      }
      const date = planDateFromKey(key);
      const diff = Math.round((date - todayStart) / 86400000);
      let label;
      if (diff === 0) label = '今天';
      else if (diff === 1) label = '明天';
      else if (diff === 2) label = '后天';
      else if (diff === -1) label = '昨天';
      else label = `${date.getMonth() + 1}月${date.getDate()}日`;
      if (diff < 0) label += ' · 已过期';
      groups.push({ label, items: list });
    });
    return groups;
  }

  function todoRow(item) {
    const done = item.status === 'done';
    return `<li class="todo-row ${done ? 'done' : ''}" data-todo-row data-todo-id="${esc(item.id)}">
      <button class="todo-check" data-todo-act="${done ? 'reopen' : 'complete'}" title="${done ? '标记未完成' : '标记完成'}">${ic('check')}</button>
      <div class="todo-main">
        <div class="todo-title">${esc(item.title)}</div>
        ${done ? `<div class="todo-meta"><span>完成于 ${esc(relTime(item.completed_at ? new Date(item.completed_at).getTime() / 1000 : 0))}</span></div>` : `<div class="todo-meta">${todoDueMeta(item)}</div>`}
      </div>
      <div class="todo-actions">
        ${done ? '' : `<button data-todo-act="postpone">推迟</button>`}
        <button data-todo-act="edit">编辑</button>
        <button class="del" data-todo-act="delete">删除</button>
      </div>
    </li>`;
  }

  async function loadTodo() {
    const view = state.todo.view;
    const tag = state.todo.tag || null;
    const res = await api('todo_list', view, tag);
    if (!res || !res.ok) { toast((res && res.error) || '加载待办失败', 'err'); return; }
    state.todo.items = res.items || [];
    state.todo.stats = res.stats || state.todo.stats;
    renderTodo();
    renderTodoTags();
    syncBadges();
  }

  function renderTodoTags() {
    const select = $('#todoTag');
    const tags = Object.keys(state.todo.stats.tags || {});
    const current = state.todo.tag;
    select.innerHTML = `<option value="">全部标签</option>` + tags.map((t) =>
      `<option value="${esc(t)}">#${esc(t)}（${state.todo.stats.tags[t]}）</option>`).join('');
    select.value = current;
  }

  const parseHint = debounce(async () => {
    const input = $('#todoInput');
    const text = input.value.trim();
    const hint = $('#todoHint');
    if (!text) {
      hint.classList.remove('parsed');
      hint.textContent = '支持 今天 / 明天 / 下周三、下午 3 点、每周一、每月 1 号、3 天后…';
      return;
    }
    const res = await api('todo_parse', text);
    if (!res.ok || !res.draft) return;
    const d = res.draft;
    const bits = [];
    if (d.due_at) bits.push(dueLabel(d.due_at));
    if (d.repeat_rule && d.repeat_rule !== 'none') {
      const meta = (state.todo.meta.repeats || []).find((r) => r.id === d.repeat_rule);
      bits.push(meta ? meta.name : d.repeat_rule);
    }
    if (d.priority === 'high') bits.push('高优先级');
    (d.tags || []).forEach((t) => bits.push(`#${t}`));
    if (bits.length) {
      hint.classList.add('parsed');
      hint.textContent = `识别为：${bits.join(' · ')}`;
    } else {
      hint.classList.remove('parsed');
      hint.textContent = '没有识别到时间，会作为普通任务添加';
    }
  }, 380);

  async function addTodo() {
    const input = $('#todoInput');
    const text = input.value.trim();
    if (!text) { input.focus(); return; }
    const btn = $('#todoAdd');
    btn.disabled = true;
    const parsed = await api('todo_parse', text);
    const draft = (parsed && parsed.ok && parsed.draft) ? parsed.draft : null;
    const payload = draft ? {
      title: draft.title || text,
      notes: draft.notes || '',
      due_at: draft.due_at || null,
      remind_at: draft.remind_at || null,
      repeat_rule: draft.repeat_rule || 'none',
      priority: draft.priority || 'medium',
      tags: draft.tags || [],
    } : { title: text };

    // 手动选的时间优先于句子里的时间
    const when = state.todo.when;
    if (when) {
      payload.due_at = `${when.date}T${when.time || '00:00'}`;
      payload.remind_at = when.time
        ? `${when.date}T${toHHMM(toMinutes(when.time) - 15)}`
        : null;
    }
    const res = await api('todo_create', payload);
    btn.disabled = false;
    if (!res.ok) { toast(res.error || '添加失败', 'err'); return; }
    input.value = '';
    setTodoWhen('', '');
    $('#todoHint').classList.remove('parsed');
    $('#todoHint').textContent = '支持 今天 / 明天 / 下周三、下午 3 点、每周一、每月 1 号、3 天后…';
    toast('已添加', 'ok', 1400);
    const now = new Date();
    const todayKey = planDateKey(now);
    const dueDay = payload.due_at ? String(payload.due_at).slice(0, 10) : '';
    state.todo.view = dueDay === todayKey ? 'today' : 'all';
    $$('#todoTabs .tab').forEach((t) => t.classList.toggle('active', t.dataset.view === state.todo.view));
    await loadTodo();
    if (currentPage() === 'home') refreshHome();
  }

  async function todoAction(act, id) {
    const item = state.todo.items.find((it) => it.id === id);
    if (!item) return;

    if (act === 'complete') {
      const res = await api('todo_complete', id);
      if (res.ok) {
        toast(res.follow_up ? `已完成，下次 ${dueLabel(res.follow_up.due_at)}` : '已完成', 'ok', 2000);
        await loadTodo();
        if (currentPage() === 'home') refreshHome();
      } else toast(res.error || '操作失败', 'err');
      return;
    }
    if (act === 'reopen') {
      const res = await api('todo_reopen', id);
      if (res.ok) { await loadTodo(); } else toast(res.error || '操作失败', 'err');
      return;
    }
    if (act === 'delete') {
      const ok = await confirmAction({ title: '删除这个任务？', message: item.title, confirm: '删除' });
      if (!ok) return;
      const res = await api('todo_delete', id);
      if (res.ok) {
        toast('已删除', 'ok', 1400);
        await loadTodo();
        if (currentPage() === 'home') refreshHome();
      } else toast(res.error || '删除失败', 'err');
      return;
    }
    if (act === 'postpone') {
      const modal = openModal({
        title: '推迟任务',
        subtitle: item.title,
        body: `<div class="postpone-grid">
          <button class="btn" data-p="60">1 小时后</button>
          <button class="btn" data-p="1440">明天</button>
          <button class="btn" data-p="10080">一周后</button>
        </div>`,
      });
      $$('[data-p]', modal.body).forEach((btn) => {
        btn.onclick = async () => {
          const minutes = Number(btn.dataset.p);
          modal.close();
          const res = await api('todo_postpone', id, Math.floor(minutes / 1440), minutes % 1440);
          if (res.ok) { toast('已推迟', 'ok', 1400); await loadTodo(); }
          else toast(res.error || '操作失败', 'err');
        };
      });
      return;
    }
    if (act === 'edit') openTodoEditor(item);
  }

  function localStamp(date) {
    return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}T${pad(date.getHours())}:${pad(date.getMinutes())}`;
  }

  function openTodoEditor(item) {
    const repeats = state.todo.meta.repeats || [];
    const priorities = state.todo.meta.priorities || [];
    const due = parseLocal(item.due_at);
    const remind = parseLocal(item.remind_at);
    const dateValue = due ? planDateKey(due) : '';
    const timeValue = due && (due.getHours() || due.getMinutes())
      ? `${pad(due.getHours())}:${pad(due.getMinutes())}` : '';
    const offsets = [0, 5, 15, 30, 60, 1440];
    let offset = due && remind ? Math.round((due.getTime() - remind.getTime()) / 60000) : 0;
    if (!offsets.includes(offset)) offset = 15;

    const modal = openModal({
      title: '编辑任务',
      subtitle: item.title,
      wide: true,
      body: `<div class="form-grid">
        <div class="form-field full"><label>标题</label><input id="edTitle" value="${esc(item.title)}"></div>
        <div class="form-field"><label>日期</label><input id="edDate" type="date" value="${esc(dateValue)}"></div>
        <div class="form-field"><label>时间</label><input id="edTime" type="time" step="300" value="${esc(timeValue)}"></div>
        <div class="form-field"><label>提醒</label><select id="edRemind">
          ${offsets.map((o) => `<option value="${o}" ${o === offset ? 'selected' : ''}>${o === 0 ? '不提醒' : o === 1440 ? '提前 1 天' : `提前 ${o} 分钟`}</option>`).join('')}
        </select></div>
        <div class="form-field"><label>重复</label><select id="edRepeat">${repeats.map((r) => `<option value="${esc(r.id)}" ${r.id === item.repeat_rule ? 'selected' : ''}>${esc(r.name)}</option>`).join('')}</select></div>
        <div class="form-field"><label>优先级</label><select id="edPriority">${priorities.map((p) => `<option value="${esc(p.id)}" ${p.id === item.priority ? 'selected' : ''}>${esc(p.name)}</option>`).join('')}</select></div>
        <div class="form-field"><label>标签（逗号分隔）</label><input id="edTags" value="${esc((item.tags || []).join(', '))}"></div>
        <div class="form-field full"><label>备注</label><textarea id="edNotes">${esc(item.notes || '')}</textarea></div>
      </div>`,
      footer: `<button class="btn" data-cancel>取消</button><button class="btn btn-primary" data-ok>保存</button>`,
    });

    // 日期快捷按钮
    const quick = document.createElement('div');
    quick.className = 'dt-chips';
    quick.style.marginTop = '2px';
    quick.innerHTML = [['今天', 0], ['明天', 1], ['后天', 2], ['下周一', 7]]
      .map(([label]) => `<button class="dt-chip" data-off="${label}">${label}</button>`).join('');
    $('#edDate').closest('.form-field').appendChild(quick);
    $$('[data-off]', quick).forEach((btn) => {
      btn.onclick = () => {
        const now = new Date();
        const map = { 今天: 0, 明天: 1, 后天: 2 };
        let target;
        if (btn.dataset.off === '下周一') {
          const add = (8 - now.getDay()) % 7 || 7;
          target = new Date(now.getFullYear(), now.getMonth(), now.getDate() + add);
        } else {
          target = new Date(now.getFullYear(), now.getMonth(), now.getDate() + map[btn.dataset.off]);
        }
        $('#edDate').value = planDateKey(target);
        if (!$('#edTime').value) $('#edTime').value = '09:00';
      };
    });

    modal.foot.querySelector('[data-cancel]').onclick = () => modal.close();
    modal.foot.querySelector('[data-ok]').onclick = async () => {
      const title = $('#edTitle').value.trim();
      if (!title) { toast('标题不能为空', 'info'); return; }
      const date = $('#edDate').value;
      const time = $('#edTime').value;
      const dueAt = date ? `${date}T${time || '00:00'}` : null;
      const minutes = Number($('#edRemind').value) || 0;
      let remindAt = null;
      if (dueAt && minutes > 0) {
        remindAt = localStamp(new Date(new Date(dueAt).getTime() - minutes * 60000));
      }
      const payload = {
        title,
        due_at: dueAt,
        remind_at: remindAt,
        repeat_rule: $('#edRepeat').value,
        priority: $('#edPriority').value,
        tags: $('#edTags').value.split(/[,，\s]+/).map((t) => t.replace(/^#/, '').trim()).filter(Boolean),
        notes: $('#edNotes').value.trim(),
      };
      const res = await api('todo_update', item.id, payload);
      if (res.ok) { modal.close(); toast('已保存', 'ok', 1400); await loadTodo(); }
      else toast(res.error || '保存失败', 'err');
    };
  }

  /** 通用的「选日期 + 选时间」弹层，待办和日程都能用。 */
  function openDateTimePicker({ title = '选择时间', subtitle = '', date = '', time = '', onPick }) {
    let pickedDate = date || planDateKey(new Date());
    let pickedTime = time || '';

    const dateOfOffset = (offset) => {
      const now = new Date();
      if (offset === null) {
        const add = (8 - now.getDay()) % 7 || 7;
        return new Date(now.getFullYear(), now.getMonth(), now.getDate() + add);
      }
      return new Date(now.getFullYear(), now.getMonth(), now.getDate() + offset);
    };
    const quickDates = [
      { label: '今天', key: planDateKey(dateOfOffset(0)) },
      { label: '明天', key: planDateKey(dateOfOffset(1)) },
      { label: '后天', key: planDateKey(dateOfOffset(2)) },
      { label: '下周一', key: planDateKey(dateOfOffset(null)) },
    ];
    const times = ['09:00', '12:00', '14:00', '18:00', '20:00'];

    const modal = openModal({
      title,
      subtitle,
      body: `<div class="dt-grid">
        <div class="dt-row">
          <span class="dt-label">日期</span>
          <div class="dt-chips" id="dtDates">
            ${quickDates.map((d) => `<button class="dt-chip" data-date="${d.key}">${d.label}</button>`).join('')}
          </div>
          <div class="dt-inputs"><input type="date" id="dtDate" value="${esc(pickedDate)}"></div>
        </div>
        <div class="dt-row">
          <span class="dt-label">时间</span>
          <div class="dt-chips" id="dtTimes">
            ${times.map((t) => `<button class="dt-chip" data-time="${t}">${t}</button>`).join('')}
          </div>
          <div class="dt-inputs"><input type="time" id="dtTime" step="300" value="${esc(pickedTime)}"></div>
        </div>
        <p class="dt-tip">时间可以不填：任务会放在这天，但不占具体时刻。</p>
      </div>`,
      footer: `<button class="btn" data-clear style="margin-right:auto">清除时间</button>
               <button class="btn" data-cancel>取消</button>
               <button class="btn btn-primary" data-ok>确定</button>`,
    });

    const sync = () => {
      $('#dtDate').value = pickedDate;
      $('#dtTime').value = pickedTime;
      $$('#dtDates [data-date]').forEach((b) => b.classList.toggle('active', b.dataset.date === pickedDate));
      $$('#dtTimes [data-time]').forEach((b) => b.classList.toggle('active', b.dataset.time === pickedTime));
    };
    sync();

    $$('#dtDates [data-date]', modal.body).forEach((btn) => {
      btn.onclick = () => { pickedDate = btn.dataset.date; sync(); };
    });
    $$('#dtTimes [data-time]', modal.body).forEach((btn) => {
      btn.onclick = () => {
        pickedTime = btn.dataset.time === pickedTime ? '' : btn.dataset.time;
        sync();
      };
    });
    $('#dtDate').onchange = (ev) => { pickedDate = ev.target.value || pickedDate; sync(); };
    $('#dtTime').onchange = (ev) => { pickedTime = ev.target.value || ''; sync(); };

    modal.foot.querySelector('[data-cancel]').onclick = () => modal.close();
    modal.foot.querySelector('[data-clear]').onclick = () => {
      modal.close();
      if (onPick) onPick('', '');
    };
    modal.foot.querySelector('[data-ok]').onclick = () => {
      modal.close();
      if (onPick) onPick(pickedDate, pickedTime);
    };
  }

  function setTodoWhen(date, time) {
    const btn = $('#todoWhen');
    const label = $('#todoWhenLabel');
    if (!date) {
      state.todo.when = null;
      label.textContent = '选时间';
      btn.classList.remove('set');
      btn.title = '自己选日期和时间';
      return;
    }
    state.todo.when = { date, time: time || '' };
    label.textContent = dueLabel(`${date}T${time || '00:00'}`) + (time ? '' : ' · 当天');
    btn.classList.add('set');
    btn.title = '点击修改时间';
  }

  function bindTodoPage() {
    $('#todoInput').addEventListener('input', parseHint);
    $('#todoInput').addEventListener('keydown', (ev) => {
      if (ev.key === 'Enter' && !ev.shiftKey) { ev.preventDefault(); addTodo(); }
    });
    $('#todoAdd').onclick = addTodo;
    $('#todoWhen').onclick = () => {
      const when = state.todo.when || {};
      openDateTimePicker({
        title: '这条任务什么时候做',
        subtitle: '选好日期和时间，或者只选日期',
        date: when.date || '',
        time: when.time || '',
        onPick: (date, time) => setTodoWhen(date, time),
      });
    };

    $$('#todoTabs .tab').forEach((tab) => {
      tab.onclick = async () => {
        state.todo.view = tab.dataset.view;
        $$('#todoTabs .tab').forEach((t) => t.classList.toggle('active', t === tab));
        await loadTodo();
      };
    });
    $('#todoTag').onchange = async () => {
      state.todo.tag = $('#todoTag').value;
      await loadTodo();
    };
    $('#todoClearDone').onclick = async () => {
      const ok = await confirmAction({ title: '清空已完成任务？', message: '只会删除已完成的任务，未完成的会保留。', confirm: '清空' });
      if (!ok) return;
      const res = await api('todo_clear_done');
      if (res.ok) { toast('已清空', 'ok'); await loadTodo(); } else toast(res.error || '操作失败', 'err');
    };
  }

  /* ---------------- 单位换算 ---------------- */
  function formatNumber(value) {
    if (!Number.isFinite(value)) return '—';
    const rounded = Math.round(value * 1e6) / 1e6;
    if (Object.is(rounded, -0)) return '0';
    if (Math.abs(rounded) >= 1e15) return rounded.toExponential(6);
    return String(rounded);
  }

  function unitList(cat) {
    return cat.id === 'currency' ? ((state.currency && state.currency.currencies) || []) : (cat.units || []);
  }

  function renderUnitsPage() {
    const cats = state.units.cats || [];
    $('#unitCats').innerHTML = cats.map((c) =>
      `<button class="chip ${c.id === state.units.cat ? 'active' : ''}" data-cat="${esc(c.id)}">${esc(c.name)}</button>`).join('');
    $$('#unitCats [data-cat]').forEach((el) => {
      el.onclick = () => selectUnitCategory(el.dataset.cat);
    });

    const cat = currentUnitCategory();
    if (!cat) return;
    if (!state.units.from || !state.units.to) {
      state.units.from = cat.default_from;
      state.units.to = cat.default_to;
    }
    renderUnitSelects();
    convertUnits();
    renderRecentConversion();
  }

  function currentUnitCategory() {
    return (state.units.cats || []).find((c) => c.id === state.units.cat);
  }

  function renderUnitSelects() {
    const cat = currentUnitCategory();
    if (!cat) return;
    const list = unitList(cat);
    const options = list.map((u) => `<option value="${esc(u.id)}">${esc(u.name)}${u.symbol ? ` (${esc(u.symbol)})` : ''}</option>`).join('');
    const from = $('#convFrom');
    const to = $('#convTo');
    from.innerHTML = options;
    to.innerHTML = options;
    const ids = list.map((u) => u.id);
    if (!ids.includes(state.units.from)) state.units.from = cat.default_from || ids[0];
    if (!ids.includes(state.units.to)) state.units.to = cat.default_to || ids[1] || ids[0];
    from.value = state.units.from;
    to.value = state.units.to;

    const isCurrency = cat.id === 'currency';
    $('#convRefresh').hidden = !isCurrency;
    $('#convValue').value = $('#convValue').value || '1';
    updateCurrencyNote();
  }

  function updateCurrencyNote() {
    if (state.units.cat !== 'currency') { $('#convNote').textContent = ''; return; }
    const c = state.currency;
    if (!c || !c.currencies || !c.currencies.length) {
      $('#convNote').textContent = '正在获取汇率…';
      return;
    }
    const age = c.age_seconds;
    const ageText = age == null ? '' : age < 60 ? '刚刚更新' : age < 3600 ? `${Math.floor(age / 60)} 分钟前更新` : `${Math.floor(age / 3600)} 小时前更新`;
    $('#convNote').textContent = c.stale ? `${ageText} · 使用缓存汇率` : `${ageText}${c.source ? ` · ${c.source}` : ''}`;
  }

  async function selectUnitCategory(id) {
    state.units.cat = id;
    const cat = currentUnitCategory();
    state.units.from = cat ? cat.default_from : null;
    state.units.to = cat ? cat.default_to : null;
    $$('#unitCats .chip').forEach((el) => el.classList.toggle('active', el.dataset.cat === id));
    $('#convNote').textContent = '';
    renderUnitSelects();
    convertUnits();
    if (id === 'currency') await ensureCurrency();
    renderRecentConversion();
  }

  async function ensureCurrency(force = false) {
    const c = state.currency;
    if (!force && c && c.currencies && c.currencies.length && !c.stale) return;
    const res = await api('currency_refresh');
    if (res && res.currencies) {
      state.currency = res;
      if (state.units.cat === 'currency') {
        renderUnitSelects();
        convertUnits();
      }
      updateCurrencyNote();
      if (force) toast('汇率已更新', 'ok', 1600);
    } else {
      updateCurrencyNote();
      if (force) toast((res && res.error) || '汇率获取失败', 'err');
    }
  }

  function conversionValue(cat, value, fromId, toId) {
    if (!Number.isFinite(value)) return NaN;
    if (cat.id === 'currency') {
      const list = (state.currency && state.currency.currencies) || [];
      const from = list.find((u) => u.id === fromId);
      const to = list.find((u) => u.id === toId);
      if (!from || !to || !from.rate || !to.rate) return NaN;
      return (value / from.rate) * to.rate;
    }
    const from = (cat.units || []).find((u) => u.id === fromId);
    const to = (cat.units || []).find((u) => u.id === toId);
    if (!from || !to) return NaN;
    const base = value * from.factor + (from.offset || 0);
    return (base - (to.offset || 0)) / to.factor;
  }

  function convertUnits() {
    const cat = currentUnitCategory();
    if (!cat) return;
    const raw = $('#convValue').value.trim();
    const value = Number(raw.replace(/,/g, ''));
    const out = $('#convResult');
    if (!raw || !Number.isFinite(value)) {
      out.textContent = '—';
      renderFacts(cat, NaN);
      return;
    }
    const result = conversionValue(cat, value, state.units.from, state.units.to);
    out.textContent = formatNumber(result);
    if (Number.isFinite(result)) scheduleConversionSave(cat, value, result);
    renderFacts(cat, value);
  }

  function renderFacts(cat, value) {
    const host = $('#factsList');
    const from = unitList(cat).find((u) => u.id === state.units.from);
    if (!from) { host.innerHTML = ''; return; }
    let others = unitList(cat).filter((u) => u.id !== from.id);
    if (cat.id === 'currency') {
      const priority = ['CNY', 'USD', 'EUR', 'JPY', 'GBP', 'HKD', 'KRW', 'AUD'];
      const target = unitList(cat).find((u) => u.id === state.units.to);
      others = others
        .filter((u) => priority.includes(u.id) || (target && u.id === target.id))
        .sort((a, b) => priority.indexOf(a.id) - priority.indexOf(b.id))
        .slice(0, 8);
    }
    $('#factsTitle').textContent = Number.isFinite(value)
      ? `${formatNumber(value)} ${from.name} 约等于`
      : `${from.name} 换算对照`;
    if (cat.id === 'currency' && !((state.currency && state.currency.currencies) || []).length) {
      host.innerHTML = `<li class="fact-empty">汇率还在获取中…</li>`;
      return;
    }
    if (!others.length) {
      host.innerHTML = `<li class="fact-empty">这一类只有一个单位</li>`;
      return;
    }
    const baseValue = Number.isFinite(value) ? value : 1;
    host.innerHTML = others.map((u) => {
      const v = conversionValue(cat, baseValue, from.id, u.id);
      return `<li data-fact="${esc(u.name)}" data-val="${esc(formatNumber(v))}">
        <span class="fact-unit">${esc(u.name)}${u.symbol ? ` · ${esc(u.symbol)}` : ''}</span>
        <span class="fact-value">${esc(formatNumber(v))}</span>
      </li>`;
    }).join('');
    $$('#factsList [data-fact]').forEach((li) => {
      li.onclick = () => copyText(`${li.dataset.val} ${li.dataset.fact}`);
    });
  }

  const scheduleConversionSave = debounce((cat, value, result) => {
    const record = {
      category: cat.id,
      from: state.units.from,
      to: state.units.to,
      value: String($('#convValue').value),
      result: formatNumber(result),
    };
    state.lastConv = record;
    api('save_conversion', record);
    renderRecentConversion();
  }, 900);

  function unitName(cat, id) {
    const found = unitList(cat).find((u) => u.id === id);
    return found ? found.name : id;
  }

  function renderRecentConversion() {
    const record = state.lastConv;
    if (!record) { $('#convRecent').textContent = ''; return; }
    const cat = (state.units.cats || []).find((c) => c.id === record.category);
    if (!cat) { $('#convRecent').textContent = ''; return; }
    $('#convRecent').textContent = `上次换算：${record.value} ${unitName(cat, record.from)} = ${record.result} ${unitName(cat, record.to)}`;
  }

  function bindUnitsPage() {
    $('#convValue').addEventListener('input', convertUnits);
    $('#convFrom').onchange = () => { state.units.from = $('#convFrom').value; convertUnits(); };
    $('#convTo').onchange = () => { state.units.to = $('#convTo').value; convertUnits(); };
    $('#convSwap').onclick = () => {
      const from = state.units.from;
      state.units.from = state.units.to;
      state.units.to = from;
      $('#convFrom').value = state.units.from;
      $('#convTo').value = state.units.to;
      convertUnits();
    };
    $('#convCopy').onclick = () => {
      const text = $('#convResult').textContent;
      if (text && text !== '—') copyText(text);
    };
    $('#convRefresh').onclick = () => ensureCurrency(true);
  }

  /* ---------------- 随机选择 ---------------- */
  const WHEEL_COLORS = [
    '#4C6FFF', '#2FA98C', '#D98324', '#C2547B', '#5B7BD5',
    '#3F8F6B', '#B4682B', '#8C5AA8', '#3E7CA8', '#A85751',
  ];

  function renderPickerPage() {
    renderPickList();
    renderPickHistory();
    setPickerMode(state.picker.mode, true);
    const result = $('#pickResult');
    result.textContent = state.picker.lastResult
      || (state.picker.options.length ? '转一下试试' : '先加两个选项');
    result.classList.toggle('hit', !!state.picker.lastResult);
    if (state.picker.winner < 0 && state.picker.lastResult) {
      const index = state.picker.options.indexOf(state.picker.lastResult);
      if (index >= 0) {
        state.picker.winner = index;
        renderWheel();
        alignWheelTo(index);
      }
    }
    result.classList.remove('rolling');
    $('#pickDraw').disabled = state.picker.options.length < 2;
    const spin = $('#pickSpin');
    if (spin) {
      spin.disabled = state.picker.options.length < 2;
      spin.querySelector('span').textContent = state.picker.options.length < 2 ? '开始' : '开始';
    }
    $('#pickCount').textContent = `${state.picker.options.length} 个选项`;
  }

  function setPickerMode(mode, silent = false) {
    state.picker.mode = mode === 'list' ? 'list' : 'wheel';
    localStorage.setItem('personal-tools.pickMode', state.picker.mode);
    const grid = $('.picker-grid');
    if (grid) grid.dataset.mode = state.picker.mode;
    $$('#pickMode button').forEach((b) => b.classList.toggle('active', b.dataset.mode === state.picker.mode));
    const count = state.picker.options.length;
    if (!silent) {
      $('#pickDraw').textContent = state.picker.mode === 'wheel' ? '开始转动' : '随机选择';
    } else {
      $('#pickDraw').textContent = state.picker.mode === 'wheel' ? '开始转动' : '随机选择';
    }
    $('#pickModeTip').textContent = count < 2
      ? '至少两个选项才能抽'
      : state.picker.mode === 'wheel' ? '点中间或下面的按钮开始' : '逐条滚动后定格';
  }

  function renderPickList() {
    const host = $('#pickList');
    if (!state.picker.options.length) {
      host.innerHTML = `<li class="pick-empty" style="background:transparent">${ic('shuffle')}<span>还没有选项，先加两个吧</span></li>`;
      $('#pickCount').textContent = '0 个选项';
      $('#pickDraw').disabled = true;
      const emptySpin = $('#pickSpin');
      if (emptySpin) emptySpin.disabled = true;
      renderWheel();
      setPickerMode(state.picker.mode, true);
      $('#pickModeTip').textContent = '至少两个选项才能抽';
      return;
    }
    host.innerHTML = state.picker.options.map((opt, index) => `
      <li data-index="${index}">
        <span title="点击编辑">${esc(opt)}</span>
        <button data-remove="${index}" title="删除">${ic('x')}</button>
      </li>`).join('');
    $('#pickCount').textContent = `${state.picker.options.length} 个选项`;
    $('#pickDraw').disabled = state.picker.options.length < 2;
    const spinBtn = $('#pickSpin');
    if (spinBtn) spinBtn.disabled = state.picker.options.length < 2;
    setPickerMode(state.picker.mode, true);
    renderWheel();

    $$('#pickList [data-remove]').forEach((btn) => {
      btn.onclick = async () => {
        state.picker.options.splice(Number(btn.dataset.remove), 1);
        await persistPicker();
        renderPickList();
      };
    });
    $$('#pickList li[data-index] span').forEach((span) => {
      span.onclick = () => startEditOption(span);
    });
  }

  function renderWheel() {
    const svg = $('#pickWheel');
    if (!svg) return;
    const opts = state.picker.options || [];
    const n = opts.length;
    const cx = 160;
    const cy = 160;
    const R = 148;

    if (!n) {
      svg.innerHTML = `<circle cx="160" cy="160" r="${R}" fill="var(--surface-3)"/>
        <text x="160" y="160" text-anchor="middle" dominant-baseline="middle" fill="var(--text-3)" font-size="13">先添加选项</text>`;
      return;
    }
    if (n === 1) {
      svg.innerHTML = `<circle cx="160" cy="160" r="${R}" fill="${WHEEL_COLORS[0]}"/>
        <text x="160" y="112" text-anchor="middle" fill="#fff" font-size="13" font-weight="600">${esc(opts[0].slice(0, 8))}</text>
        <circle cx="160" cy="160" r="46" fill="var(--surface)"/>`;
      return;
    }

    const step = 360 / n;
    const fs = n > 16 ? 9 : n > 10 ? 10 : n > 7 ? 11 : 12;
    const maxChars = n > 16 ? 4 : n > 10 ? 5 : n > 7 ? 7 : 9;
    const toXY = (angle, radius) => {
      const rad = (angle * Math.PI) / 180;
      return [cx + Math.cos(rad) * radius, cy + Math.sin(rad) * radius];
    };

    let parts = [`<circle cx="160" cy="160" r="${R}" fill="var(--surface-3)"/>`];
    opts.forEach((opt, i) => {
      const a0 = -90 + i * step;
      const a1 = a0 + step;
      const [x0, y0] = toXY(a0, R);
      const [x1, y1] = toXY(a1, R);
      const large = step > 180 ? 1 : 0;
      const color = WHEEL_COLORS[i % WHEEL_COLORS.length];
      const winner = state.picker.winner === i;
      parts.push(`<path d="M${cx},${cy} L${x0.toFixed(2)},${y0.toFixed(2)} A${R},${R} 0 ${large} 1 ${x1.toFixed(2)},${y1.toFixed(2)} Z"
        fill="${color}" stroke="${winner ? '#FFFFFF' : 'rgba(255,255,255,.7)'}" stroke-width="${winner ? 3 : 1}"/>`);

      const mid = a0 + step / 2;
      const [lx, ly] = toXY(mid, R * 0.66);
      let rot = mid;
      if (mid > 90 || mid < -90) rot += 180;
      const label = opt.length > maxChars ? `${opt.slice(0, maxChars)}…` : opt;
      parts.push(`<text x="${lx.toFixed(2)}" y="${ly.toFixed(2)}"
        transform="rotate(${rot.toFixed(2)} ${lx.toFixed(2)} ${ly.toFixed(2)})"
        text-anchor="middle" dominant-baseline="middle"
        fill="#fff" font-size="${fs}" font-weight="600"
        stroke="rgba(0,0,0,.22)" stroke-width="2.2" paint-order="stroke"
        style="pointer-events:none">${esc(label)}</text>`);
    });
    parts.push(`<circle cx="160" cy="160" r="48" fill="var(--surface)" opacity="0.98"/>`);
    parts.push(`<circle cx="160" cy="160" r="${R}" fill="none" stroke="var(--border)" stroke-width="1"/>`);
    svg.innerHTML = parts.join('');
  }

  // 恢复上次结果时，让指针真的停在那个扇区上（不带动画）
  function alignWheelTo(index) {
    const n = state.picker.options.length;
    if (n < 2 || index < 0) return;
    const step = 360 / n;
    state.picker.rotation = (((-(index + 0.5) * step) % 360) + 360) % 360;
    const svg = $('#pickWheel');
    if (!svg) return;
    svg.style.transition = 'none';
    svg.style.transform = `rotate(${state.picker.rotation}deg)`;
    void svg.offsetWidth;
    svg.style.transition = '';
  }

  function startEditOption(span) {
    const li = span.closest('li');
    const index = Number(li.dataset.index);
    const input = document.createElement('input');
    input.value = state.picker.options[index];
    span.replaceWith(input);
    input.focus();
    input.select();
    const commit = async () => {
      const value = input.value.trim();
      if (value && !state.picker.options.some((o, i) => i !== index && o === value)) {
        state.picker.options[index] = value;
        await persistPicker();
      }
      renderPickList();
    };
    input.onblur = commit;
    input.onkeydown = (ev) => {
      if (ev.key === 'Enter') { ev.preventDefault(); input.blur(); }
      if (ev.key === 'Escape') { input.onblur = null; renderPickList(); }
    };
  }

  function renderPickHistory() {
    const host = $('#pickHistory');
    const items = state.picker.history || [];
    if (!items.length) {
      host.innerHTML = `<li class="pick-empty">${ic('clock')}<span>还没有抽取记录</span></li>`;
      return;
    }
    host.innerHTML = items.slice(0, 30).map((h) => `
      <li data-hist="${esc(h.value)}"><span>${esc(h.value)}</span><time>${esc(relTime(h.at))}</time></li>`).join('');
    $$('[data-hist]', host).forEach((li) => {
      li.onclick = () => copyText(li.dataset.hist);
    });
  }

  async function persistPicker() {
    const res = await api('picker_save', {
      options: state.picker.options,
      lastResult: state.picker.lastResult,
      history: state.picker.history,
    });
    if (res.ok && res.state) applyPickerState(res.state);
  }

  function applyPickerState(s) {
    state.picker.options = s.options || [];
    state.picker.history = s.history || [];
    state.picker.lastResult = s.lastResult || '';
  }

  function finishPick(choice) {
    state.picker.lastResult = choice;
    const result = $('#pickResult');
    result.classList.remove('rolling');
    result.classList.add('hit');
    result.textContent = choice;
    api('picker_record', choice).then((res) => {
      if (res.ok && res.state) {
        state.picker.history = res.state.history || state.picker.history;
        renderPickHistory();
      }
    });
  }

  function startRoll() {
    const opts = state.picker.options;
    if (opts.length < 2 || state.picker.spinning) return;
    state.picker.spinning = true;
    const result = $('#pickResult');
    const btn = $('#pickDraw');
    btn.disabled = true;
    result.classList.remove('hit');
    result.classList.add('rolling');
    let ticks = 0;
    const timer = setInterval(() => {
      result.textContent = opts[Math.floor(Math.random() * opts.length)];
      ticks += 1;
      if (ticks > 12) {
        clearInterval(timer);
        state.picker.spinning = false;
        btn.disabled = false;
        finishPick(opts[Math.floor(Math.random() * opts.length)]);
      }
    }, 65);
  }

  function spinWheel() {
    const opts = state.picker.options;
    if (opts.length < 2 || state.picker.spinning) return;
    state.picker.spinning = true;
    const svg = $('#pickWheel');
    const btn = $('#pickDraw');
    const center = $('#pickSpin');
    const result = $('#pickResult');
    btn.disabled = true;
    center.disabled = true;
    center.classList.add('spinning');
    center.querySelector('span').textContent = '转…';
    result.classList.remove('hit');
    result.classList.add('rolling');
    result.textContent = '转动中…';

    const n = opts.length;
    const step = 360 / n;
    const index = Math.floor(Math.random() * n);
    const turns = 4 + Math.floor(Math.random() * 3);
    const want = (((-(index + 0.5) * step) % 360) + 360) % 360;
    let target = state.picker.rotation + turns * 360;
    const cur = ((target % 360) + 360) % 360;
    target += (((want - cur) % 360) + 360) % 360;
    state.picker.rotation = target;
    svg.style.transform = `rotate(${target}deg)`;

    setTimeout(() => {
      state.picker.spinning = false;
      state.picker.winner = index;
      btn.disabled = false;
      center.disabled = false;
      center.classList.remove('spinning');
      center.querySelector('span').textContent = '再转';
      finishPick(opts[index]);
      renderWheel();
    }, 4500);
  }

  function bindPickerPage() {
    const add = async () => {
      const input = $('#pickInput');
      const value = input.value.trim();
      if (!value) return;
      if (state.picker.options.length >= 20) { toast('最多 20 个选项', 'info'); return; }
      if (state.picker.options.includes(value)) { toast('这个选项已经有了', 'info'); return; }
      state.picker.options.push(value);
      state.picker.winner = -1;
      input.value = '';
      await persistPicker();
      renderPickList();
      input.focus();
    };
    $('#pickAdd').onclick = add;
    $('#pickInput').addEventListener('keydown', (ev) => {
      if (ev.key === 'Enter') { ev.preventDefault(); add(); }
    });

    $$('#pickMode button').forEach((btn) => {
      btn.onclick = () => {
        setPickerMode(btn.dataset.mode);
        if (btn.dataset.mode === 'wheel') renderWheel();
      };
    });

    $('#pickClear').onclick = async () => {
      if (!state.picker.options.length) return;
      const ok = await confirmAction({ title: '清空所有选项？', message: '抽取历史会保留，之后可以单独清理。', confirm: '清空' });
      if (!ok) return;
      state.picker.options = [];
      await persistPicker();
      renderPickList();
      renderPickerPage();
    };

    $('#pickClearHist').onclick = async () => {
      const res = await api('picker_clear_history');
      if (res.ok && res.state) applyPickerState(res.state);
      renderPickHistory();
      toast('已清空抽取历史', 'ok', 1500);
    };

    $('#pickDraw').onclick = () => {
      if (state.picker.mode === 'wheel') spinWheel();
      else startRoll();
    };
    $('#pickSpin').onclick = spinWheel;
  }

  /* ---------------- 时间：番茄钟 / 倒数日 / 世界时钟 ---------------- */
  const FOCUS_PRESETS = [
    { id: 'focus', name: '专注', minutes: 25 },
    { id: 'short', name: '短休', minutes: 5 },
    { id: 'long', name: '长休', minutes: 15 },
  ];
  const FOCUS_CIRC = 653.45; // 2π × 104

  const WORLD_PRESETS = [
    { name: '北京', tz: 'Asia/Shanghai' },
    { name: '香港', tz: 'Asia/Hong_Kong' },
    { name: '台北', tz: 'Asia/Taipei' },
    { name: '东京', tz: 'Asia/Tokyo' },
    { name: '首尔', tz: 'Asia/Seoul' },
    { name: '新加坡', tz: 'Asia/Singapore' },
    { name: '曼谷', tz: 'Asia/Bangkok' },
    { name: '孟买', tz: 'Asia/Kolkata' },
    { name: '迪拜', tz: 'Asia/Dubai' },
    { name: '莫斯科', tz: 'Europe/Moscow' },
    { name: '柏林', tz: 'Europe/Berlin' },
    { name: '巴黎', tz: 'Europe/Paris' },
    { name: '伦敦', tz: 'Europe/London' },
    { name: '纽约', tz: 'America/New_York' },
    { name: '芝加哥', tz: 'America/Chicago' },
    { name: '洛杉矶', tz: 'America/Los_Angeles' },
    { name: '圣保罗', tz: 'America/Sao_Paulo' },
    { name: '悉尼', tz: 'Australia/Sydney' },
    { name: '奥克兰', tz: 'Pacific/Auckland' },
  ];

  const MOODS = [
    { v: 1, emoji: '😞', name: '很差' },
    { v: 2, emoji: '😕', name: '低落' },
    { v: 3, emoji: '😐', name: '一般' },
    { v: 4, emoji: '🙂', name: '不错' },
    { v: 5, emoji: '😄', name: '很好' },
  ];
  const moodOf = (v) => MOODS.find((m) => m.v === Number(v)) || null;

  const CHART_TYPES = ['bar', 'line', 'donut'];
  const CHART_COLORS = ['#2F6BEB', '#0E9384', '#B4670A', '#C64663'];

  function setTimeTab(tab, silent = false) {
    state.time.tab = ['focus', 'countdown', 'world'].includes(tab) ? tab : 'focus';
    $$('#timeTabs .tab').forEach((b) => b.classList.toggle('active', b.dataset.tab === state.time.tab));
    $$('.time-panel').forEach((p) => { p.hidden = p.dataset.panel !== state.time.tab; });
    const hints = {
      focus: '计时按本机时间校准，切走也不会走偏',
      countdown: '按本机日期算整天数，跨时区也准',
      world: '按城市时区换算，夏令时自动生效',
    };
    $('#timeHint').textContent = hints[state.time.tab];
    if (silent) return;
    if (state.time.tab === 'focus') loadFocusState();
    if (state.time.tab === 'countdown') loadCountdowns();
    if (state.time.tab === 'world') renderWorld(true);
  }

  async function renderTimePage() {
    setTimeTab(state.time.tab || 'focus', true);
    if (state.time.tab === 'focus') await loadFocusState();
    if (state.time.tab === 'countdown') await loadCountdowns();
    if (state.time.tab === 'world') renderWorld(true);
  }

  /* ---- 番茄钟 ---- */
  function focusPreset(id = state.focus.preset) {
    return FOCUS_PRESETS.find((p) => p.id === id) || FOCUS_PRESETS[0];
  }

  function mmss(seconds) {
    const s = Math.max(0, Math.round(seconds));
    const h = Math.floor(s / 3600);
    const m = Math.floor((s % 3600) / 60);
    const sec = s % 60;
    return h ? `${h}:${pad(m)}:${pad(sec)}` : `${pad(m)}:${pad(sec)}`;
  }

  function renderFocusTime() {
    const f = state.focus;
    const time = $('#focusTime');
    if (!time) return;
    time.textContent = mmss(f.left);
    const elapsed = f.total ? 1 - f.left / f.total : 0;
    $('#focusRing').style.strokeDashoffset = (FOCUS_CIRC * Math.min(1, Math.max(0, elapsed))).toFixed(1);
  }

  function renderFocus() {
    const f = state.focus;
    const preset = focusPreset();
    const mode = $('#focusMode');
    if (!mode) return;
    mode.textContent = preset.name;
    $('.focus-ring').classList.toggle('rest', f.preset !== 'focus');
    $('#focusSub').textContent = f.preset === 'focus'
      ? `第 ${(f.stats.today_rounds || 0) + 1} 个番茄`
      : `休息 ${Math.round(preset.minutes)} 分钟`;
    const btn = $('#focusStart');
    btn.querySelector('span').textContent = f.running ? '暂停' : (f.left < f.total && f.left > 0 ? '继续' : '开始');
    btn.querySelector('use').setAttribute('href', f.running ? '#i-pause' : '#i-play');
    $$('#focusModes button').forEach((b) => b.classList.toggle('active', b.dataset.preset === f.preset));
    const label = $('#focusLabel');
    if (document.activeElement !== label && label.value !== (f.label || '')) label.value = f.label || '';
    renderFocusTime();
    renderFocusSide();
  }

  function renderFocusSide() {
    const f = state.focus;
    const s = f.stats || {};
    const host = $('#focusStats');
    if (!host) return;
    host.innerHTML = `
      <div class="focus-stat"><strong>${s.today_minutes || 0}</strong><span>今天专注（分钟）</span></div>
      <div class="focus-stat"><strong>${s.today_rounds || 0}</strong><span>完成的番茄</span></div>
      <div class="focus-stat"><strong>${s.streak || 0}</strong><span>连续天数</span></div>
      <div class="focus-stat"><strong>${((s.total_minutes || 0) / 60).toFixed(1)}</strong><span>累计小时</span></div>`;
    const logs = (f.sessions || []).filter((it) => it.kind === 'focus').slice(0, 8);
    $('#focusLog').innerHTML = logs.length
      ? logs.map((it) => {
        const d = new Date((it.ended || 0) * 1000);
        return `<li><span class="fl-label">${esc(it.label || '专注')}</span>
          <span class="fl-min">${it.minutes}′</span>
          <span class="fl-time">${pad(d.getHours())}:${pad(d.getMinutes())}</span></li>`;
      }).join('')
      : '<li class="empty-line">还没有完成的番茄</li>';
  }

  async function loadFocusState() {
    const res = await api('focus_state');
    if (!res || !res.ok) return;
    state.focus.sessions = res.sessions || [];
    state.focus.stats = res.stats || {};
    renderFocusSide();
    const sub = $('#focusSub');
    if (sub && state.focus.preset === 'focus') sub.textContent = `第 ${(state.focus.stats.today_rounds || 0) + 1} 个番茄`;
  }

  function setFocusPreset(id, silent = false) {
    const preset = focusPreset(id);
    const f = state.focus;
    stopFocusTimer();
    f.preset = preset.id;
    f.running = false;
    f.total = preset.minutes * 60;
    f.left = preset.minutes * 60;
    f.endAt = 0;
    // 休息不需要任务描述，别把上一轮的「这轮专注做什么」带进休息里
    if (preset.id !== 'focus') f.label = '';
    renderFocus();
    if (!silent) toast(`切到${preset.name} ${Math.round(preset.minutes)} 分钟`, 'info', 1600);
  }

  function startFocusTimer() {
    stopFocusTimer();
    state.focus.timer = setInterval(tickFocus, 250);
  }

  function stopFocusTimer() {
    if (state.focus.timer) {
      clearInterval(state.focus.timer);
      state.focus.timer = null;
    }
  }

  function tickFocus() {
    const f = state.focus;
    if (!f.running) return;
    const left = Math.max(0, Math.ceil((f.endAt - Date.now()) / 1000));
    f.left = left;
    renderFocusTime();
    if (left <= 0) completeFocus();
  }

  async function completeFocus() {
    const f = state.focus;
    if (!f.running) return;
    const preset = focusPreset();
    f.running = false;
    f.left = 0;
    stopFocusTimer();
    renderFocusTime();
    playChime();
    const rounds = (f.stats.today_rounds || 0) + 1;
    if (f.preset === 'focus') {
      const res = await api('focus_log', {
        kind: 'focus',
        minutes: preset.minutes,
        label: f.label || '',
        started: f.startedAt / 1000,
        ended: Date.now() / 1000,
        completed: true,
      });
      if (res.ok) {
        f.stats = res.stats || f.stats;
        f.sessions = [res.item].concat(f.sessions || []);
      }
      api('ui_notify', '专注结束', f.label ? `${f.label} · ${preset.minutes} 分钟` : `完成 ${preset.minutes} 分钟专注`);
      toast(`第 ${rounds} 个番茄完成，休息 ${Math.round(focusPreset('short').minutes)} 分钟`, 'ok', 4200);
      setFocusPreset('short', true);
    } else {
      api('ui_notify', '休息结束', '准备好就再开一轮');
      toast('休息结束，回来继续', 'ok', 4200);
      setFocusPreset('focus', true);
    }
    renderFocus();
  }

  let audioCtx = null;
  function ensureAudio() {
    try {
      if (!audioCtx) audioCtx = new (window.AudioContext || window.webkitAudioContext)();
      if (audioCtx.state === 'suspended') audioCtx.resume();
    } catch (err) { /* 没有声音也能用 */ }
  }

  function playChime() {
    if (!audioCtx) return;
    try {
      const now = audioCtx.currentTime;
      [[880, 0], [1174, 0.16], [1568, 0.32]].forEach(([freq, offset]) => {
        const osc = audioCtx.createOscillator();
        const gain = audioCtx.createGain();
        osc.type = 'sine';
        osc.frequency.value = freq;
        gain.gain.setValueAtTime(0.0001, now + offset);
        gain.gain.exponentialRampToValueAtTime(0.18, now + offset + 0.02);
        gain.gain.exponentialRampToValueAtTime(0.0001, now + offset + 0.34);
        osc.connect(gain).connect(audioCtx.destination);
        osc.start(now + offset);
        osc.stop(now + offset + 0.36);
      });
    } catch (err) { /* 忽略 */ }
  }

  /* ---- 倒数日 ---- */
  function parseDay(key) {
    const [y, m, d] = String(key || '').split('-').map(Number);
    return new Date(y || 1970, (m || 1) - 1, d || 1);
  }

  function todayStart() {
    const now = new Date();
    return new Date(now.getFullYear(), now.getMonth(), now.getDate());
  }

  function daysInMonth(year, month) {
    return new Date(year, month + 1, 0).getDate();
  }

  function cdInfo(item) {
    const today = todayStart();
    const base = parseDay(item.date);
    if (item.repeat === 'year') {
      const build = (year) => new Date(
        year,
        base.getMonth(),
        Math.min(base.getDate(), daysInMonth(year, base.getMonth())),
      );
      let target = build(today.getFullYear());
      if (target < today) target = build(today.getFullYear() + 1);
      return { target, days: Math.round((target - today) / 86400000), repeat: 'year' };
    }
    if (item.repeat === 'month') {
      const build = (year, month) => new Date(
        year,
        month,
        Math.min(base.getDate(), daysInMonth(year, month)),
      );
      let target = build(today.getFullYear(), today.getMonth());
      if (target < today) target = build(today.getFullYear(), today.getMonth() + 1);
      return { target, days: Math.round((target - today) / 86400000), repeat: 'month' };
    }
    return { target: base, days: Math.round((base - today) / 86400000), repeat: 'none' };
  }

  const WEEK_CN = ['周日', '周一', '周二', '周三', '周四', '周五', '周六'];

  async function loadCountdowns() {
    const res = await api('countdown_all');
    if (!res || !res.ok) return;
    state.cd.items = res.items || [];
    renderCountdowns();
  }

  function renderCountdowns() {
    const host = $('#cdList');
    if (!host) return;
    const rows = (state.cd.items || []).map((item) => ({ item, info: cdInfo(item) }));
    rows.sort((a, b) => {
      const av = a.info.days >= 0 ? a.info.days : 100000 - a.info.days;
      const bv = b.info.days >= 0 ? b.info.days : 100000 - b.info.days;
      return av - bv;
    });
    $('#cdHint').textContent = rows.length
      ? `${rows.length} 个日子，最近的排在最前面`
      : '还没有倒数日，点右上角添加';
    if (!rows.length) {
      host.innerHTML = `<li class="cd-empty" style="grid-column:1/-1;color:var(--text-3);font-size:12.5px;padding:24px 4px">还没有记录，加一个生日或截止日期试试。</li>`;
      return;
    }
    host.innerHTML = rows.map(({ item, info }) => {
      const d = info.target;
      const cls = info.days === 0 ? 'today' : info.days < 0 ? 'past' : '';
      const big = info.days === 0 ? '今天' : Math.abs(info.days);
      const unit = info.days === 0 ? (info.repeat !== 'none' ? '就是今天' : '') : info.days > 0 ? '天后' : '天前';
      const repeat = info.repeat === 'year' ? '每年' : info.repeat === 'month' ? '每月' : '';
      return `<li class="cd-item ${cls}">
        <div class="cd-days"><strong>${big}</strong><span>${unit}</span></div>
        <div class="cd-main">
          <strong title="${esc(item.title)}">${esc(item.title)}</strong>
          <div class="cd-meta">
            <span>${d.getMonth() + 1}月${d.getDate()}日 ${WEEK_CN[d.getDay()]}</span>
            ${repeat ? `<em class="cd-tag">${repeat}</em>` : ''}
            ${item.note ? `<span>${esc(item.note)}</span>` : ''}
          </div>
        </div>
        <div class="cd-actions">
          <button data-cd-edit="${esc(item.id)}" title="编辑">${ic('edit')}</button>
          <button class="danger" data-cd-del="${esc(item.id)}" title="删除">${ic('trash')}</button>
        </div>
      </li>`;
    }).join('');

    $$('[data-cd-edit]', host).forEach((btn) => {
      btn.onclick = () => openCountdownEditor((state.cd.items || []).find((it) => it.id === btn.dataset.cdEdit));
    });
    $$('[data-cd-del]', host).forEach((btn) => {
      btn.onclick = async () => {
        const item = (state.cd.items || []).find((it) => it.id === btn.dataset.cdDel);
        const ok = await confirmAction({
          title: '删除这个倒数日？',
          message: item ? `「${item.title}」会被移除，不影响其他数据。` : '删除后不可恢复。',
          confirm: '删除',
        });
        if (!ok) return;
        const res = await api('countdown_delete', btn.dataset.cdDel);
        if (res.ok) {
          state.cd.items = res.items || [];
          renderCountdowns();
          toast('已删除', 'ok');
        } else toast(res.error || '删除失败', 'err');
      };
    });
  }

  function openCountdownEditor(item) {
    const editing = !!item;
    const today = planDateKey(new Date());
    const modal = openModal({
      title: editing ? '编辑倒数日' : '添加倒数日',
      subtitle: '日期按本机日历计算，每年重复的会自动跳到下一次',
      body: `
        <div class="form-stack">
          <label class="form-field"><span>名称</span>
            <input id="cdTitle" maxlength="60" placeholder="例如：妈妈生日 / 项目上线" value="${editing ? esc(item.title) : ''}">
          </label>
          <div class="form-row">
            <label class="form-field"><span>日期</span>
              <input id="cdDate" type="date" value="${editing ? esc(item.date) : today}">
            </label>
            <label class="form-field"><span>重复</span>
              <div class="select-wrap"><select id="cdRepeat">
                <option value="none">不重复</option>
                <option value="year">每年</option>
                <option value="month">每月</option>
              </select><svg><use href="#i-chevron"/></svg></div>
            </label>
          </div>
          <label class="form-field"><span>备注（可留空）</span>
            <input id="cdNote" maxlength="200" placeholder="提醒自己准备什么" value="${editing ? esc(item.note || '') : ''}">
          </label>
        </div>`,
      footer: `<button class="btn" data-cancel>取消</button>
               <button class="btn btn-primary" data-ok>${editing ? '保存' : '添加'}</button>`,
    });
    if (editing) $('#cdRepeat').value = item.repeat || 'none';
    modal.foot.querySelector('[data-cancel]').onclick = modal.close;
    modal.foot.querySelector('[data-ok]').onclick = async () => {
      const title = $('#cdTitle').value.trim();
      const date = $('#cdDate').value;
      if (!title) { toast('先起个名字', 'info'); return; }
      if (!date) { toast('选个日期', 'info'); return; }
      const payload = {
        id: editing ? item.id : '',
        title,
        date,
        repeat: $('#cdRepeat').value,
        note: $('#cdNote').value.trim(),
      };
      const res = await api('countdown_save', payload);
      if (res.ok) {
        state.cd.items = res.items || [];
        renderCountdowns();
        modal.close();
        toast(editing ? '已保存' : '已添加', 'ok');
      } else toast(res.error || '保存失败', 'err');
    };
  }

  /* ---- 世界时钟 ---- */
  const TZ_FMT_CACHE = new Map();

  function tzParts(tz, date) {
    let fmt = TZ_FMT_CACHE.get(tz);
    if (!fmt) {
      fmt = new Intl.DateTimeFormat('en-US', {
        timeZone: tz,
        hour12: false,
        year: 'numeric',
        month: '2-digit',
        day: '2-digit',
        hour: '2-digit',
        minute: '2-digit',
        second: '2-digit',
      });
      TZ_FMT_CACHE.set(tz, fmt);
    }
    const out = {};
    fmt.formatToParts(date).forEach((part) => {
      if (part.type !== 'literal') out[part.type] = part.value;
    });
    return {
      y: Number(out.year), m: Number(out.month), d: Number(out.day),
      h: Number(out.hour) % 24, mi: Number(out.minute), s: Number(out.second),
    };
  }

  function tzOffsetMinutes(tz, date) {
    const p = tzParts(tz, date);
    const asUTC = Date.UTC(p.y, p.m - 1, p.d, p.h, p.mi, p.s);
    return Math.round((asUTC - Math.floor(date.getTime() / 1000) * 1000) / 60000);
  }

  function localTz() {
    try { return Intl.DateTimeFormat().resolvedOptions().timeZone || 'Asia/Shanghai'; } catch (err) { return 'Asia/Shanghai'; }
  }

  function saveWorld() {
    localStorage.setItem('personal-tools.world', JSON.stringify(state.world.cities || []));
  }

  function loadWorld() {
    let list = [];
    try { list = JSON.parse(localStorage.getItem('personal-tools.world') || '[]') || []; } catch (err) { list = []; }
    if (!Array.isArray(list) || !list.length) {
      list = [
        { name: '东京', tz: 'Asia/Tokyo' },
        { name: '伦敦', tz: 'Europe/London' },
        { name: '纽约', tz: 'America/New_York' },
      ];
    }
    state.world.cities = list.filter((c) => c && c.tz);
  }

  function renderWorld(full = false) {
    const host = $('#worldGrid');
    if (!host) return;
    if (!state.world.cities.length) loadWorld();
    if (full || host.childElementCount !== state.world.cities.length) {
      const me = localTz();
      host.innerHTML = state.world.cities.map((city) => {
        const isLocal = city.tz === me;
        return `<div class="world-city ${isLocal ? 'local' : ''}" data-tz="${esc(city.tz)}">
          <button class="world-del" data-world-del="${esc(city.tz)}" title="移除">${ic('x')}</button>
          <div class="world-top"><strong>${esc(city.name)}</strong><span data-role="day"></span></div>
          <div class="world-time" data-role="time">--:--</div>
          <div class="world-meta"><span data-role="date">—</span><span data-role="diff"></span></div>
        </div>`;
      }).join('');
      $$('[data-world-del]', host).forEach((btn) => {
        btn.onclick = () => {
          state.world.cities = state.world.cities.filter((c) => c.tz !== btn.dataset.worldDel);
          saveWorld();
          renderWorld(true);
          renderWorldPresets();
        };
      });
      renderWorldPresets();
    }
    tickWorld();
  }

  function tickWorld() {
    if (currentPage() !== 'time' || state.time.tab !== 'world') return;
    const me = localTz();
    const now = new Date();
    const mine = tzParts(me, now);
    const myKey = `${mine.y}-${mine.m}-${mine.d}`;
    const myOffset = tzOffsetMinutes(me, now);
    $$('#worldGrid .world-city').forEach((card) => {
      const tz = card.dataset.tz;
      let p;
      try { p = tzParts(tz, now); } catch (err) { return; }
      const key = `${p.y}-${p.m}-${p.d}`;
      const dayDiff = Math.sign(new Date(p.y, p.m - 1, p.d) - new Date(mine.y, mine.m - 1, mine.d));
      card.querySelector('[data-role="time"]').innerHTML = `${pad(p.h)}:${pad(p.mi)}<em>:${pad(p.s)}</em>`;
      card.querySelector('[data-role="date"]').textContent = `${p.m}月${p.d}日 ${WEEK_CN[new Date(p.y, p.m - 1, p.d).getDay()]}`;
      card.querySelector('[data-role="day"]').textContent = dayDiff > 0 ? '明天' : dayDiff < 0 ? '昨天' : '';
      const diff = tzOffsetMinutes(tz, now) - myOffset;
      const hours = Math.round(Math.abs(diff) / 60 * 10) / 10;
      const diffText = diff === 0 ? '与本地同步'
        : `比本地${diff > 0 ? '快' : '慢'} ${hours % 1 === 0 ? hours : hours.toFixed(1)} 小时`;
      card.querySelector('[data-role="diff"]').textContent = diffText;
      card.classList.toggle('local', tz === me);
      if (key === myKey && tz !== me) card.dataset.same = '1';
    });
  }

  function renderWorldPresets() {
    const host = $('#worldPresets');
    if (!host) return;
    const used = new Set(state.world.cities.map((c) => c.tz));
    host.innerHTML = WORLD_PRESETS.map((p) => `<button data-world-add="${esc(p.tz)}" data-name="${esc(p.name)}" class="${used.has(p.tz) ? 'added' : ''}">${esc(p.name)}</button>`).join('');
    $$('[data-world-add]', host).forEach((btn) => {
      btn.onclick = () => {
        if (used.has(btn.dataset.worldAdd)) return;
        addWorldCity(btn.dataset.name, btn.dataset.worldAdd);
      };
    });
  }

  function addWorldCity(name, tz) {
    if (state.world.cities.some((c) => c.tz === tz)) {
      toast('这个时区已经加过了', 'info');
      return;
    }
    if (state.world.cities.length >= 12) {
      toast('最多同时看 12 个城市', 'info');
      return;
    }
    try { tzParts(tz, new Date()); } catch (err) { toast('这个时区识别不了', 'err'); return; }
    state.world.cities.push({ name, tz });
    saveWorld();
    renderWorld(true);
    toast(`已添加 ${name}`, 'ok', 1600);
  }

  function submitWorldCity() {
    const input = $('#worldInput');
    const raw = input.value.trim();
    if (!raw) return;
    const preset = WORLD_PRESETS.find((p) => p.name === raw)
      || WORLD_PRESETS.find((p) => p.name.includes(raw) || raw.includes(p.name));
    if (preset) {
      addWorldCity(preset.name, preset.tz);
      input.value = '';
      return;
    }
    // 也允许直接输入时区名，比如 Asia/Tokyo
    if (/^[A-Za-z_]+\/[A-Za-z_+\-0-9]+$/.test(raw)) {
      try {
        tzParts(raw, new Date());
      } catch (err) {
        toast('这个时区名不认识，试试「东京」或 Asia/Tokyo', 'err');
        return;
      }
      addWorldCity(raw.split('/').pop().replace(/_/g, ' '), raw);
      input.value = '';
      return;
    }
    toast('没找到这个城市，可以试试列表里的，或输入 Asia/Tokyo 这样的时区', 'info', 3600);
  }

  /* ---- 心情日记 ---- */
  function moodMonthKey(date = new Date()) {
    return `${date.getFullYear()}-${pad(date.getMonth() + 1)}`;
  }

  async function loadMood(ym = state.mood.ym) {
    const res = await api('mood_month', ym);
    if (!res || !res.ok) return;
    state.mood.ym = ym;
    state.mood.days = res.days || {};
    state.mood.stats = res.stats || {};
    renderMood();
  }

  async function renderMoodPage() {
    if (!state.mood.ym) state.mood.ym = moodMonthKey();
    if (!state.mood.selected) state.mood.selected = planDateKey(new Date());
    await loadMood(state.mood.ym);
    loadMoodRecent();
  }

  function renderMood() {
    const [year, month] = state.mood.ym.split('-').map(Number);
    const title = $('#moodTitle');
    if (!title) return;
    title.textContent = `${year} 年 ${month} 月`;
    const stats = state.mood.stats || {};
    $('#moodSub').textContent = stats.days
      ? `这个月记了 ${stats.days} 天，平均 ${stats.avg} 分`
      : '点一天记录，或看看这个月过得怎么样';

    const firstDay = new Date(year, month - 1, 1);
    const startOffset = (firstDay.getDay() + 6) % 7; // 周一为一周开头
    const total = daysInMonth(year, month - 1);
    const prevTotal = daysInMonth(year, month - 2 < 0 ? 11 : month - 2);
    const todayKey = planDateKey(new Date());
    const cells = [];
    for (let i = startOffset; i > 0; i -= 1) {
      cells.push({ day: prevTotal - i + 1, out: true });
    }
    for (let d = 1; d <= total; d += 1) cells.push({ day: d, out: false });
    while (cells.length % 7 !== 0 || cells.length < 35) {
      cells.push({ day: cells.length - startOffset - total + 1, out: true });
    }

    $('#moodWeek').innerHTML = ['一', '二', '三', '四', '五', '六', '日']
      .map((w) => `<span>${w}</span>`).join('');

    $('#moodDays').innerHTML = cells.map((cell) => {
      if (cell.out) return `<div class="mood-day out"><b>${cell.day}</b></div>`;
      const key = `${year}-${pad(month)}-${pad(cell.day)}`;
      const entry = state.mood.days[key];
      const mood = entry ? moodOf(entry.mood) : null;
      const cls = [
        'mood-day',
        entry ? 'has' : '',
        key === todayKey ? 'today' : '',
        key === state.mood.selected ? 'sel' : '',
      ].filter(Boolean).join(' ');
      return `<button class="${cls}" data-mood-day="${key}">
        <b>${cell.day}</b>
        <span class="m-emoji">${mood ? mood.emoji : ''}</span>
      </button>`;
    }).join('');

    $$('[data-mood-day]').forEach((btn) => {
      btn.onclick = () => {
        state.mood.selected = btn.dataset.moodDay;
        const entry = state.mood.days[state.mood.selected];
        state.mood.mood = entry ? entry.mood : 0;
        state.mood.text = entry ? entry.text || '' : '';
        renderMood();
        renderMoodEditor();
      };
    });

    $('#moodLegend').innerHTML = MOODS.map((m) => `<span><i>${m.emoji}</i>${m.name}</span>`).join('');
    renderMoodEditor();
    renderMoodStats();
  }

  function renderMoodEditor() {
    const day = state.mood.selected;
    if (!day) return;
    const [, m, d] = day.split('-').map(Number);
    const isToday = day === planDateKey(new Date());
    $('#moodEditTitle').textContent = `${m} 月 ${d} 日${isToday ? '（今天）' : ''}`;
    $('#moodPicks').innerHTML = MOODS.map((mood) => `
      <button class="mood-pick ${state.mood.mood === mood.v ? 'on' : ''}" data-mood-pick="${mood.v}">
        <i>${mood.emoji}</i><span>${mood.name}</span>
      </button>`).join('');
    $$('[data-mood-pick]').forEach((btn) => {
      btn.onclick = () => {
        state.mood.mood = Number(btn.dataset.moodPick);
        renderMoodEditor();
      };
    });
    const text = $('#moodText');
    if (document.activeElement !== text) text.value = state.mood.text || '';
    $('#moodCount').textContent = `${(text.value || '').length}/120`;
    $('#moodClear').hidden = !state.mood.days[day];
  }

  function renderMoodStats() {
    const s = state.mood.stats || {};
    $('#moodStats').innerHTML = `
      <div class="mood-stat"><strong>${s.days || 0}</strong><span>本月记录天数</span></div>
      <div class="mood-stat"><strong>${s.avg || 0}</strong><span>平均心情（5 分制）</span></div>
      <div class="mood-stat"><strong>${s.streak || 0}</strong><span>连续记录天数</span></div>
      <div class="mood-stat"><strong>${s.best || 0}</strong><span>最好的一天（分）</span></div>`;
  }

  async function loadMoodRecent() {
    const res = await api('mood_recent', 6);
    const host = $('#moodRecent');
    if (!host) return;
    const items = (res && res.items) || [];
    host.innerHTML = items.length
      ? items.map((it) => {
        const mood = moodOf(it.mood);
        const [, m, d] = String(it.date).split('-').map(Number);
        return `<li>
          <span class="mr-emoji">${mood ? mood.emoji : '📝'}</span>
          <span class="mr-text">${esc(it.text || '（只记了心情）')}</span>
          <span class="mr-date">${m}/${d}</span>
        </li>`;
      }).join('')
      : '<li class="empty-line">还没有记录</li>';
  }

  async function saveMoodEntry() {
    const day = state.mood.selected;
    if (!day) return;
    const text = $('#moodText').value.trim();
    if (!state.mood.mood && !text) {
      toast('先选个心情，或者写一句话', 'info');
      return;
    }
    const res = await api('mood_set', day, state.mood.mood || 0, text);
    if (!res.ok) { toast(res.error || '保存失败', 'err'); return; }
    state.mood.days = res.days || {};
    state.mood.stats = res.stats || {};
    state.mood.text = text;
    renderMood();
    loadMoodRecent();
    toast('记下了', 'ok');
  }

  /* ---- 数据成图 ---- */
  function splitCells(line) {
    if (line.includes('\t')) return line.split('\t');
    if (line.includes(',')) return line.split(',');
    if (line.includes(';')) return line.split(';');
    return line.split(/\s{2,}/);
  }

  function parseChart(raw) {
    const lines = String(raw || '').split(/\r?\n/).map((l) => l.trim()).filter(Boolean);
    if (!lines.length) return null;
    const rows = lines.map((line, index) => {
      const cells = splitCells(line);
      const label = (cells[0] || '').trim() || `第${index + 1}行`;
      const values = cells.slice(1).map((cell) => Number(String(cell).replace(/[,\s¥$%]/g, '')));
      return { label, values };
    });
    const width = Math.max(...rows.map((r) => r.values.length));
    if (!width) return null;
    let header = null;
    const first = rows[0];
    const firstNumeric = first.values.filter((v) => Number.isFinite(v)).length;
    if (firstNumeric < width && rows.length > 1) header = rows.shift();
    const columnNames = [];
    for (let i = 0; i < width; i += 1) {
      columnNames.push(header && header.values[i] !== undefined
        ? splitCells(lines[0])[i + 1] || `系列 ${i + 1}`
        : `系列 ${i + 1}`);
    }
    // 整列都没有数字的就不当系列（日期 / 备注 / 文本列），最多取前三组
    const series = [];
    columnNames.forEach((name, index) => {
      if (series.length >= 3) return;
      if (!rows.some((r) => Number.isFinite(r.values[index]))) return;
      series.push({
        name: header ? pieceName(lines[0], index + 1) : name,
        values: rows.map((r) => (Number.isFinite(r.values[index]) ? r.values[index] : 0)),
      });
    });
    if (!series.length) return null;
    return {
      labels: rows.map((r) => r.label),
      series,
      rows: rows.length,
      header: header ? header.label : '',
    };
  }

  function pieceName(headerLine, index) {
    const cells = splitCells(headerLine);
    return (cells[index] || `系列 ${index}`).trim();
  }

  /* ---------------- 成图：拖入 Excel / CSV ---------------- */

  // xlsx 就是个 zip：解析中央目录，按需解压，不依赖任何第三方库
  async function inflateRaw(raw) {
    if (typeof DecompressionStream === 'undefined') {
      throw new Error('这个内核不支持解压 xlsx，请另存为 CSV');
    }
    const stream = new Blob([raw]).stream().pipeThrough(new DecompressionStream('deflate-raw'));
    return new Uint8Array(await new Response(stream).arrayBuffer());
  }

  async function zipEntries(bytes) {
    const dv = new DataView(bytes.buffer, bytes.byteOffset, bytes.byteLength);
    let eocd = -1;
    const floor = Math.max(0, bytes.length - 22 - 65535);
    for (let i = bytes.length - 22; i >= floor; i -= 1) {
      if (dv.getUint32(i, true) === 0x06054b50) { eocd = i; break; }
    }
    if (eocd < 0) throw new Error('不是有效的 xlsx 文件');
    const count = dv.getUint16(eocd + 10, true);
    let off = dv.getUint32(eocd + 16, true);
    const pending = [];
    for (let i = 0; i < count; i += 1) {
      if (dv.getUint32(off, true) !== 0x02014b50) break;
      const method = dv.getUint16(off + 10, true);
      const csize = dv.getUint32(off + 20, true);
      const nameLen = dv.getUint16(off + 28, true);
      const extraLen = dv.getUint16(off + 30, true);
      const commentLen = dv.getUint16(off + 32, true);
      const lho = dv.getUint32(off + 42, true);
      const name = new TextDecoder('utf-8').decode(bytes.subarray(off + 46, off + 46 + nameLen));
      const lNameLen = dv.getUint16(lho + 26, true);
      const lExtraLen = dv.getUint16(lho + 28, true);
      const start = lho + 30 + lNameLen + lExtraLen;
      if (!name.endsWith('/')) pending.push({ name, method, raw: bytes.subarray(start, start + csize) });
      off += 46 + nameLen + extraLen + commentLen;
    }
    const files = new Map();
    for (const item of pending) {
      files.set(item.name, item.method === 0 ? item.raw : await inflateRaw(item.raw));
    }
    return files;
  }

  function xmlDoc(bytes) {
    const text = new TextDecoder('utf-8').decode(bytes);
    return new DOMParser().parseFromString(text, 'application/xml');
  }

  function sheetColIndex(ref) {
    const m = /^([A-Z]+)/.exec(String(ref || '').toUpperCase());
    if (!m) return 0;
    let n = 0;
    for (const ch of m[1]) n = n * 26 + (ch.charCodeAt(0) - 64);
    return n - 1;
  }

  // Excel 的日期是「1900 起的序列号」，需要按样式判断该列是不是日期
  function excelSerial(value) {
    const serial = Number(value);
    if (!Number.isFinite(serial) || serial <= 0 || serial > 2958465) return String(value);
    const ms = Math.round((serial - 25569) * 86400000);
    const d = new Date(ms);
    if (Number.isNaN(d.getTime())) return String(value);
    const p2 = (n) => String(n).padStart(2, '0');
    const day = `${d.getUTCFullYear()}-${p2(d.getUTCMonth() + 1)}-${p2(d.getUTCDate())}`;
    const frac = serial - Math.floor(serial);
    if (frac > 0.0001) return `${day} ${p2(d.getUTCHours())}:${p2(d.getUTCMinutes())}`;
    return day;
  }

  function readDateStyles(bytes) {
    const set = new Set();
    if (!bytes) return set;
    const doc = xmlDoc(bytes);
    const custom = {};
    for (const nf of doc.getElementsByTagName('numFmt')) {
      custom[nf.getAttribute('numFmtId')] = nf.getAttribute('formatCode') || '';
    }
    const builtin = new Set(['14', '15', '16', '17', '22', '45', '46', '47']);
    const xfs = doc.getElementsByTagName('cellXfs')[0];
    if (!xfs) return set;
    const list = xfs.getElementsByTagName('xf');
    for (let i = 0; i < list.length; i += 1) {
      const id = list[i].getAttribute('numFmtId') || '0';
      const code = custom[id] || '';
      if (builtin.has(id) || (/[ymd]/i.test(code) && !/^[#0.,%\s]+$/.test(code))) set.add(i);
    }
    return set;
  }

  function readSharedStrings(bytes) {
    if (!bytes) return [];
    const doc = xmlDoc(bytes);
    return Array.from(doc.getElementsByTagName('si')).map(
      (si) => Array.from(si.getElementsByTagName('t')).map((t) => t.textContent).join(''),
    );
  }

  function readSheetRows(bytes, shared, dateStyles) {
    const doc = xmlDoc(bytes);
    const rows = [];
    let seq = 0;
    for (const rowEl of doc.getElementsByTagName('row')) {
      const rAttr = rowEl.getAttribute('r');
      const rIdx = rAttr ? Math.max(0, parseInt(rAttr, 10) - 1) : seq;
      seq = rIdx + 1;
      const cells = [];
      let col = 0;
      for (const c of rowEl.getElementsByTagName('c')) {
        const ref = c.getAttribute('r');
        const idx = ref ? sheetColIndex(ref) : col;
        col = idx + 1;
        const type = c.getAttribute('t') || 'n';
        const vEl = c.getElementsByTagName('v')[0];
        const raw = vEl ? vEl.textContent : '';
        let value = raw;
        if (type === 's') {
          const at = parseInt(raw, 10);
          value = Number.isFinite(at) ? (shared[at] ?? '') : '';
        } else if (type === 'inlineStr') {
          value = Array.from(c.getElementsByTagName('t')).map((t) => t.textContent).join('');
        } else if (type === 'b') {
          value = raw === '1' ? '是' : '否';
        } else if (raw && type === 'n') {
          const styleIndex = parseInt(c.getAttribute('s') || '-1', 10);
          if (dateStyles.has(styleIndex)) value = excelSerial(raw);
          else {
            const num = Number(raw);
            value = Number.isFinite(num) ? String(num) : raw;
          }
        }
        cells[idx] = String(value);
      }
      for (let i = 0; i < cells.length; i += 1) if (cells[i] === undefined) cells[i] = '';
      rows[rIdx] = cells;
    }
    const out = [];
    for (let i = 0; i < rows.length; i += 1) out.push(rows[i] || []);
    return out;
  }

  function readWorkbookSheets(entries) {
    const wb = entries.get('xl/workbook.xml');
    const rels = entries.get('xl/_rels/workbook.xml.rels');
    if (!wb || !rels) return [];
    const relMap = {};
    for (const rel of xmlDoc(rels).getElementsByTagName('Relationship')) {
      relMap[rel.getAttribute('Id')] = rel.getAttribute('Target') || '';
    }
    const list = [];
    for (const sheet of xmlDoc(wb).getElementsByTagName('sheet')) {
      let rid = '';
      for (const attr of Array.from(sheet.attributes)) {
        if (attr.localName === 'id') rid = attr.value;
      }
      const target = relMap[rid];
      if (!target) continue;
      const path = `xl/${target.replace(/^\/?(xl\/)?/, '')}`;
      list.push({ name: sheet.getAttribute('name') || 'Sheet', path });
    }
    return list;
  }

  async function parseXlsx(file) {
    const entries = await zipEntries(new Uint8Array(await file.arrayBuffer()));
    const shared = readSharedStrings(entries.get('xl/sharedStrings.xml'));
    const dateStyles = readDateStyles(entries.get('xl/styles.xml'));
    const list = readWorkbookSheets(entries);
    if (!list.length) throw new Error('没找到工作表');
    const sheets = [];
    for (const item of list) {
      const bytes = entries.get(item.path);
      if (!bytes) continue;
      const rows = readSheetRows(bytes, shared, dateStyles)
        .filter((r) => r.some((cell) => String(cell).trim() !== ''));
      if (rows.length) sheets.push({ name: item.name, rows });
    }
    if (!sheets.length) throw new Error('工作簿里没有可用数据');
    return sheets;
  }

  function decodeTextFile(buffer) {
    const utf8 = new TextDecoder('utf-8').decode(buffer);
    if (!utf8.includes('\ufffd')) return utf8;
    try {
      return new TextDecoder('gbk').decode(buffer);
    } catch (err) {
      return utf8;
    }
  }

  function detectDelimiter(text) {
    const head = text.split(/\r?\n/).slice(0, 6).join('\n');
    const count = (ch) => (head.match(new RegExp(ch === '\t' ? '\\t' : `\\${ch}`, 'g')) || []).length;
    const tab = count('\t');
    const comma = count(',');
    const semi = count(';');
    if (tab >= comma && tab >= semi && tab > 0) return '\t';
    if (semi > comma && semi > 0) return ';';
    return ',';
  }

  function parseDelimited(text, delim) {
    const rows = [];
    let row = [];
    let cell = '';
    let quoted = false;
    const src = text.replace(/^\ufeff/, '');
    for (let i = 0; i < src.length; i += 1) {
      const ch = src[i];
      if (quoted) {
        if (ch === '"') {
          if (src[i + 1] === '"') { cell += '"'; i += 1; } else quoted = false;
        } else cell += ch;
      } else if (ch === '"') {
        quoted = true;
      } else if (ch === delim) {
        row.push(cell);
        cell = '';
      } else if (ch === '\n') {
        row.push(cell);
        rows.push(row);
        row = [];
        cell = '';
      } else if (ch !== '\r') {
        cell += ch;
      }
    }
    row.push(cell);
    rows.push(row);
    return rows.filter((r) => r.some((c) => String(c).trim() !== ''));
  }

  function rowsToTsv(rows) {
    return rows.map((r) => r.map((c) => String(c).replace(/[\t\r\n]+/g, ' ').trim()).join('\t')).join('\n');
  }

  function renderChartFile() {
    const bar = $('#chartFilebar');
    if (!bar) return;
    const file = state.chart.file;
    if (!file) {
      bar.hidden = true;
      return;
    }
    bar.hidden = false;
    const sheet = file.sheets[file.index];
    $('#chartFileName').textContent = file.name;
    $('#chartFileName').title = file.name;
    $('#chartFileInfo').textContent = `${file.sheets.length > 1 ? `${file.index + 1}/${file.sheets.length} 表 · ` : ''}${sheet ? sheet.rows.length : 0} 行`;
    const host = $('#chartSheets');
    if (file.sheets.length > 1) {
      host.hidden = false;
      host.innerHTML = file.sheets.map(
        (s, i) => `<button data-sheet="${i}" class="${i === file.index ? 'active' : ''}">${esc(s.name)}</button>`,
      ).join('');
    } else {
      host.hidden = true;
      host.innerHTML = '';
    }
  }

  function applyChartSheet(index, notify = false) {
    const file = state.chart.file;
    if (!file || !file.sheets[index]) return;
    file.index = index;
    let rows = file.sheets[index].rows;
    let clipped = false;
    if (rows.length > 61) {
      rows = rows.slice(0, 61); // 表头 + 最多 60 行，再多图就看不清了
      clipped = true;
    }
    $('#chartInput').value = rowsToTsv(rows);
    drawChart(true);
    renderChartFile();
    if (clipped) toast('数据较多，先画前 60 行', 'info', 3200);
    else if (notify) toast(`已导入「${file.sheets[index].name}」`, 'ok', 2000);
  }

  async function importChartFile(file) {
    if (!file) return;
    const name = String(file.name || '数据');
    const ext = (name.split('.').pop() || '').toLowerCase();
    $('#chartParse').textContent = '正在读取…';
    try {
      let sheets;
      if (ext === 'xls') {
        throw new Error('老版 .xls 认不了，请在 Excel 里另存为 .xlsx 或 CSV');
      } else if (ext === 'xlsx' || ext === 'xlsm' || ext === 'et') {
        // 新版 WPS 的 .et 就是 OOXML 包，能按 xlsx 解；老版才会失败
        try {
          sheets = await parseXlsx(file);
        } catch (inner) {
          if (ext === 'et') throw new Error('这个 .et 不是新版格式，请在 WPS 里另存为 .xlsx');
          throw inner;
        }
      } else if (ext === 'csv' || ext === 'tsv' || ext === 'txt') {
        const text = decodeTextFile(new Uint8Array(await file.arrayBuffer()));
        sheets = [{ name, rows: parseDelimited(text, ext === 'tsv' ? '\t' : detectDelimiter(text)) }];
      } else {
        throw new Error('只支持 xlsx / xlsm / csv / tsv / txt');
      }
      if (!sheets.length || !sheets[0].rows.length) throw new Error('文件里没有数据');
      state.chart.file = { name, sheets, index: 0 };
      applyChartSheet(0, true);
    } catch (err) {
      $('#chartParse').textContent = '读取失败，试试 CSV';
      renderChartFile();
      toast(`读取失败：${(err && err.message) || err}`, 'err', 5200);
    }
  }

  function hasFileDrag(ev) {
    const dt = ev.dataTransfer;
    return !!(dt && ((dt.types && Array.from(dt.types).includes('Files')) || (dt.files && dt.files.length)));
  }

  function bindChartDrop() {
    const page = $('[data-page="chart"]');
    const drop = $('#chartDrop');
    if (!page || !drop) return;
    let depth = 0;
    const leave = () => { depth = 0; drop.classList.remove('over'); };
    ['dragenter', 'dragover'].forEach((type) => {
      page.addEventListener(type, (ev) => {
        if (!hasFileDrag(ev)) return;
        ev.preventDefault();
        ev.stopPropagation();
        if (type === 'dragenter') depth += 1;
        drop.classList.add('over');
      });
    });
    page.addEventListener('dragleave', (ev) => {
      if (!hasFileDrag(ev)) return;
      ev.preventDefault();
      depth -= 1;
      if (depth <= 0) leave();
    });
    page.addEventListener('drop', (ev) => {
      if (!hasFileDrag(ev)) return;
      ev.preventDefault();
      ev.stopPropagation();
      leave();
      const file = ev.dataTransfer.files && ev.dataTransfer.files[0];
      if (file) importChartFile(file);
    });
    // 拖到别处松手时别让 WebView 直接打开文件；拖出窗口时把提示层收掉
    window.addEventListener('dragover', (ev) => { if (hasFileDrag(ev)) ev.preventDefault(); });
    window.addEventListener('drop', (ev) => { if (hasFileDrag(ev)) ev.preventDefault(); });
    window.addEventListener('dragleave', (ev) => { if (ev.relatedTarget === null) leave(); });
    window.addEventListener('dragend', leave);
  }

  function niceMax(value) {
    if (value <= 0) return 10;
    const exp = Math.pow(10, Math.floor(Math.log10(value)));
    const step = [1, 2, 2.5, 5, 10].find((s) => value <= s * exp) || 10;
    return step * exp;
  }

  // 粗略估算文字宽度：中日韩字符按 1em，其余按 0.56em
  function textW(str, size) {
    let w = 0;
    for (const ch of String(str)) {
      w += /[\u2e80-\u9fff\uff00-\uffef]/.test(ch) ? size : size * 0.56;
    }
    return w;
  }

  function renderChart() {
    const host = $('#chartCanvas');
    if (!host) return;
    const data = state.chart.data;
    if (!data || !data.labels.length) {
      host.innerHTML = `<div class="empty small">${ic('chart')}<p>还没有数据</p></div>`;
      $('#chartMeta').textContent = '粘贴数据后点生成';
      return;
    }
    const type = state.chart.type;
    // 按容器实际宽度出图，字号才不会被缩放糊掉
    const W = Math.max(440, Math.round(host.clientWidth || 700));
    const padL = 54;
    const padR = 18;
    const plotW = W - padL - padR;
    const palette = CHART_COLORS;
    const labels = data.labels;
    const series = type === 'donut' ? data.series.slice(0, 1) : data.series;
    const allValues = series.flatMap((s) => s.values);
    const maxValue = niceMax(Math.max(...allValues, 1));
    const n = labels.length;
    // 横轴标签放得下就横排，放不下才斜排；标签太多时隔几个画一个
    const short = labels.map((l) => (l.length > 6 ? `${l.slice(0, 6)}…` : l));
    const labelW = Math.max(...short.map((t) => textW(t, 11)), 0);
    const labelStep = n > 24 ? Math.ceil(n / 10) : (n > 12 ? Math.ceil(n / 8) : 1);
    const slot = (plotW / Math.max(1, n)) * labelStep;
    const rotateX = labelW > slot - 8;
    const padB = rotateX ? Math.min(112, 26 + Math.round(labelW * 0.56)) : 32;
    const padT = type === 'donut' ? 18 : (series.length > 1 ? 34 : 20);
    const plotH = type === 'donut' ? 386 : 344;
    const H = padT + plotH + padB;
    const parts = [`<rect x="0" y="0" width="${W}" height="${H}" fill="var(--surface)"/>`];

    if (type === 'donut') {
      const values = series[0].values;
      const total = values.reduce((a, b) => a + Math.max(0, b), 0) || 1;
      const R = Math.max(84, Math.min(134, plotW * 0.27));
      const r = Math.round(R * 0.59);
      const legendW = 176;
      const cx = Math.max(R + 24, (W - (R * 2 + 46 + legendW)) / 2 + R);
      const cy = padT + plotH / 2;
      let angle = -90;
      values.forEach((value, index) => {
        const sweep = (Math.max(0, value) / total) * 360;
        const a0 = angle;
        const a1 = angle + sweep;
        angle = a1;
        const rad = (deg) => (deg * Math.PI) / 180;
        const p0 = [cx + Math.cos(rad(a0)) * R, cy + Math.sin(rad(a0)) * R];
        const p1 = [cx + Math.cos(rad(a1)) * R, cy + Math.sin(rad(a1)) * R];
        const q1 = [cx + Math.cos(rad(a1)) * r, cy + Math.sin(rad(a1)) * r];
        const q0 = [cx + Math.cos(rad(a0)) * r, cy + Math.sin(rad(a0)) * r];
        const large = sweep > 180 ? 1 : 0;
        const color = palette[index % palette.length];
        parts.push(`<path d="M${p0[0].toFixed(1)},${p0[1].toFixed(1)} A${R},${R} 0 ${large} 1 ${p1[0].toFixed(1)},${p1[1].toFixed(1)} L${q1[0].toFixed(1)},${q1[1].toFixed(1)} A${r},${r} 0 ${large} 0 ${q0[0].toFixed(1)},${q0[1].toFixed(1)} Z" fill="${color}" stroke="var(--surface)" stroke-width="2">
          <title>${esc(labels[index] || '')}：${value}</title></path>`);
      });
      parts.push(`<text x="${cx}" y="${cy - 6}" text-anchor="middle" font-size="13" fill="var(--text-3)">合计</text>`);
      parts.push(`<text x="${cx}" y="${cy + 22}" text-anchor="middle" font-size="24" font-weight="600" fill="var(--text)">${total}</text>`);
      // 图例（右侧，垂直居中）
      const items = labels.slice(0, 8);
      const legendX = cx + R + 46;
      const step = 26;
      const startY = cy - ((items.length - 1) * step) / 2;
      items.forEach((label, index) => {
        const y = startY + index * step;
        const name = label.length > 5 ? `${label.slice(0, 5)}…` : label;
        parts.push(`<rect x="${legendX}" y="${(y - 10).toFixed(1)}" width="10" height="10" rx="3" fill="${palette[index % palette.length]}"/>`);
        parts.push(`<text x="${legendX + 16}" y="${y.toFixed(1)}" font-size="12" fill="var(--text-2)">${esc(name)}　${values[index]}</text>`);
      });
    } else {
      // 坐标轴与网格
      for (let i = 0; i <= 4; i += 1) {
        const value = (maxValue / 4) * i;
        const y = padT + plotH - (plotH * i) / 4;
        parts.push(`<line x1="${padL}" y1="${y.toFixed(1)}" x2="${W - padR}" y2="${y.toFixed(1)}" stroke="var(--border)" stroke-width="1" ${i === 0 ? '' : 'stroke-dasharray="3 4"'}/>`);
        parts.push(`<text x="${padL - 10}" y="${(y + 4).toFixed(1)}" text-anchor="end" font-size="11" fill="var(--text-3)">${Math.round(value)}</text>`);
      }
      const band = plotW / n;
      const groupW = band * 0.66;
      const barW = Math.max(4, groupW / series.length);
      labels.forEach((label, index) => {
        if (labelStep > 1 && index % labelStep !== 0 && index !== n - 1) return;
        const cx = padL + band * index + band / 2;
        const text = short[index];
        const y = padT + plotH + 18;
        if (rotateX) {
          parts.push(`<text x="${cx.toFixed(1)}" y="${y}" text-anchor="end" font-size="11" fill="var(--text-3)" transform="rotate(-32 ${cx.toFixed(1)} ${y})">${esc(text)}</text>`);
        } else {
          parts.push(`<text x="${cx.toFixed(1)}" y="${y}" text-anchor="middle" font-size="11" fill="var(--text-3)">${esc(text)}</text>`);
        }
      });
      series.forEach((s, si) => {
        const color = palette[si % palette.length];
        if (type === 'bar') {
          const rects = s.values.map((value, index) => {
            const h = Math.max(1, (Math.max(0, value) / maxValue) * plotH);
            const cx = padL + band * index + band / 2;
            const x = cx - groupW / 2 + si * barW + barW * 0.12;
            const y = padT + plotH - h;
            return `<rect x="${x.toFixed(1)}" y="${y.toFixed(1)}" width="${(barW * 0.76).toFixed(1)}" height="${h.toFixed(1)}" rx="3" fill="${color}">
              <title>${esc(labels[index] || '')}${series.length > 1 ? ' · ' + esc(s.name) : ''}：${value}</title></rect>`;
          }).join('');
          parts.push(`<g class="chart-bars">${rects}</g>`);
        } else {
          const pts = s.values.map((value, index) => {
            const x = padL + band * index + band / 2;
            const y = padT + plotH - (Math.max(0, value) / maxValue) * plotH;
            return [x, y];
          });
          parts.push(`<polyline points="${pts.map((p) => `${p[0].toFixed(1)},${p[1].toFixed(1)}`).join(' ')}" fill="none" stroke="${color}" stroke-width="2.4" stroke-linejoin="round" stroke-linecap="round"/>`);
          parts.push(pts.map((p, index) => `<circle cx="${p[0].toFixed(1)}" cy="${p[1].toFixed(1)}" r="3.6" fill="var(--surface)" stroke="${color}" stroke-width="2.2">
            <title>${esc(labels[index] || '')}：${s.values[index]}</title></circle>`).join(''));
        }
      });
      // 图例（多系列时放右上角，把底部整条留给横轴标签）
      if (series.length > 1) {
        const ly = padT - 12;
        let lx = W - padR;
        for (let index = series.length - 1; index >= 0; index -= 1) {
          const name = series[index].name;
          const wItem = 16 + textW(name, 11);
          lx -= wItem;
          parts.push(`<rect x="${lx.toFixed(1)}" y="${ly - 9}" width="10" height="10" rx="3" fill="${palette[index % palette.length]}"/>`);
          parts.push(`<text x="${(lx + 14).toFixed(1)}" y="${ly}" font-size="11" fill="var(--text-2)">${esc(name)}</text>`);
          lx -= 16;
        }
      }
    }
    host.innerHTML = `<svg width="${W}" height="${H}" viewBox="0 0 ${W} ${H}" role="img" aria-label="数据图表">${parts.join('')}</svg>`;

    const flat = data.series.flatMap((s) => s.values);
    const total = flat.reduce((a, b) => a + b, 0);
    const max = Math.max(...flat);
    const maxIndex = data.series[0].values.indexOf(Math.max(...data.series[0].values));
    $('#chartMeta').textContent = `${data.rows} 行 · 合计 ${Math.round(total * 10) / 10} · 最高 ${max}${labels[maxIndex] ? `（${labels[maxIndex]}）` : ''}`;
    $('#chartTitle').textContent = data.header || '图表';
  }

  function drawChart(remember = true) {
    const raw = $('#chartInput').value;
    state.chart.raw = raw;
    const data = parseChart(raw);
    state.chart.data = data;
    if (!data) {
      $('#chartParse').textContent = raw.trim() ? '没解析出数字，检查一下格式' : '等待粘贴数据';
      renderChart();
      return;
    }
    $('#chartParse').textContent = `识别到 ${data.rows} 行 · ${data.labels.length} 个标签 · ${data.series.length} 个系列`;
    renderChart();
    if (remember) api('chart_save', { raw, type: state.chart.type, title: data.header || '' });
  }

  async function copyChartImage() {
    const svg = $('#chartCanvas svg');
    if (!svg) { toast('先生成图表', 'info'); return; }
    try {
      const clone = svg.cloneNode(true);
      clone.setAttribute('xmlns', 'http://www.w3.org/2000/svg');
      const vb = svg.viewBox.baseVal;
      const vw = Math.round(vb && vb.width ? vb.width : 760);
      const vh = Math.round(vb && vb.height ? vb.height : 440);
      clone.setAttribute('width', String(vw));
      clone.setAttribute('height', String(vh));
      const bg = document.createElementNS('http://www.w3.org/2000/svg', 'rect');
      bg.setAttribute('x', '0'); bg.setAttribute('y', '0');
      bg.setAttribute('width', String(vw)); bg.setAttribute('height', String(vh));
      bg.setAttribute('fill', document.documentElement.dataset.theme === 'dark' ? '#181b20' : '#ffffff');
      clone.insertBefore(bg, clone.firstChild);
      // 把 CSS 变量换成实际颜色，导出后才不会发灰
      const styles = getComputedStyle(document.documentElement);
      const map = {
        'var(--surface)': styles.getPropertyValue('--surface').trim(),
        'var(--border)': styles.getPropertyValue('--border').trim(),
        'var(--text)': styles.getPropertyValue('--text').trim(),
        'var(--text-2)': styles.getPropertyValue('--text-2').trim(),
        'var(--text-3)': styles.getPropertyValue('--text-3').trim(),
      };
      let xml = new XMLSerializer().serializeToString(clone);
      Object.keys(map).forEach((key) => { xml = xml.split(key).join(map[key] || '#888'); });
      const url = `data:image/svg+xml;charset=utf-8,${encodeURIComponent(xml)}`;
      const img = new Image();
      await new Promise((resolve, reject) => {
        img.onload = resolve;
        img.onerror = reject;
        img.src = url;
      });
      const canvas = document.createElement('canvas');
      const scale = 2;
      canvas.width = vw * scale;
      canvas.height = vh * scale;
      const ctx = canvas.getContext('2d');
      ctx.scale(scale, scale);
      ctx.drawImage(img, 0, 0, vw, vh);
      const blob = await new Promise((resolve) => canvas.toBlob(resolve, 'image/png'));
      if (navigator.clipboard && window.ClipboardItem) {
        await navigator.clipboard.write([new ClipboardItem({ 'image/png': blob })]);
        toast('图片已复制，可直接粘贴到微信或文档', 'ok', 3200);
      } else {
        throw new Error('clipboard');
      }
    } catch (err) {
      toast('这个环境复制不了图片，可以截图或换个方式保存', 'err', 4000);
    }
  }

  /* ---------------- 页面绑定：时间 / 心情 / 数据成图 ---------------- */
  function bindTimePage() {
    $$('#timeTabs .tab').forEach((btn) => {
      btn.onclick = () => setTimeTab(btn.dataset.tab);
    });

    $('#focusStart').onclick = () => {
      const f = state.focus;
      if (f.running) {
        f.left = Math.max(0, Math.round((f.endAt - Date.now()) / 1000));
        f.running = false;
        stopFocusTimer();
        renderFocus();
        toast('已暂停', 'info', 1400);
        return;
      }
      if (f.left <= 0) f.left = f.total;
      ensureAudio();
      f.endAt = Date.now() + f.left * 1000;
      f.startedAt = Date.now();
      f.running = true;
      startFocusTimer();
      renderFocus();
    };

    $('#focusReset').onclick = () => {
      stopFocusTimer();
      const f = state.focus;
      f.running = false;
      f.total = focusPreset().minutes * 60;
      f.left = f.total;
      f.endAt = 0;
      renderFocus();
    };

    $('#focusLabel').addEventListener('input', (ev) => {
      state.focus.label = ev.target.value.slice(0, 40);
    });

    $$('#focusModes button').forEach((btn) => {
      btn.onclick = () => setFocusPreset(btn.dataset.preset);
    });

    $('#cdAdd').onclick = () => openCountdownEditor(null);

    $('#worldAdd').onclick = submitWorldCity;
    $('#worldInput').addEventListener('keydown', (ev) => {
      if (ev.key === 'Enter') { ev.preventDefault(); submitWorldCity(); }
    });

    setInterval(() => {
      if (currentPage() === 'time' && state.time.tab === 'world') tickWorld();
    }, 1000);

    renderFocus();
  }

  function shiftMoodMonth(step) {
    const [y, m] = state.mood.ym.split('-').map(Number);
    const d = new Date(y, m - 1 + step, 1);
    state.mood.ym = `${d.getFullYear()}-${pad(d.getMonth() + 1)}`;
    const today = planDateKey(new Date());
    state.mood.selected = today.startsWith(state.mood.ym) ? today : `${state.mood.ym}-01`;
    state.mood.mood = 0;
    state.mood.text = '';
    loadMood(state.mood.ym).then(() => {
      const entry = state.mood.days[state.mood.selected];
      state.mood.mood = entry ? entry.mood : 0;
      state.mood.text = entry ? entry.text || '' : '';
      renderMoodEditor();
    });
  }

  function bindMoodPage() {
    $('#moodPrev').onclick = () => shiftMoodMonth(-1);
    $('#moodNext').onclick = () => shiftMoodMonth(1);
    $('#moodToday').onclick = () => {
      state.mood.ym = moodMonthKey();
      state.mood.selected = planDateKey(new Date());
      const entry = state.mood.days[state.mood.selected];
      state.mood.mood = entry ? entry.mood : 0;
      state.mood.text = entry ? entry.text || '' : '';
      renderMoodPage();
    };
    $('#moodSave').onclick = saveMoodEntry;
    $('#moodText').addEventListener('input', (ev) => {
      state.mood.text = ev.target.value;
      $('#moodCount').textContent = `${ev.target.value.length}/120`;
    });
    $('#moodClear').onclick = async () => {
      const day = state.mood.selected;
      if (!day || !state.mood.days[day]) return;
      const ok = await confirmAction({ title: '删除这一天的记录？', message: '只删这一天的心情和那句话。', confirm: '删除' });
      if (!ok) return;
      const res = await api('mood_delete', day);
      if (!res.ok) { toast(res.error || '删除失败', 'err'); return; }
      state.mood.days = res.days || {};
      state.mood.stats = res.stats || {};
      state.mood.mood = 0;
      state.mood.text = '';
      $('#moodText').value = '';
      renderMood();
      loadMoodRecent();
      toast('已删除', 'ok');
    };
  }

  const CHART_SAMPLE = '月份\t销量\t利润\n1月\t120\t36\n2月\t132\t41\n3月\t101\t28\n4月\t154\t47\n5月\t168\t52\n6月\t143\t44';

  function bindChartPage() {
    $$('#chartTypes button').forEach((btn) => {
      btn.onclick = () => {
        state.chart.type = btn.dataset.type;
        $$('#chartTypes button').forEach((b) => b.classList.toggle('active', b === btn));
        if (state.chart.data) renderChart();
        api('chart_save', { raw: $('#chartInput').value, type: state.chart.type, title: '' });
      };
    });
    $('#chartDraw').onclick = () => drawChart();
    $('#chartInput').addEventListener('paste', () => setTimeout(() => drawChart(true), 40));
    $('#chartInput').addEventListener('keydown', (ev) => {
      if ((ev.ctrlKey || ev.metaKey) && ev.key === 'Enter') {
        ev.preventDefault();
        drawChart();
      }
    });
    $('#chartSample').onclick = () => {
      $('#chartInput').value = CHART_SAMPLE;
      drawChart();
    };
    $('#chartClear').onclick = () => {
      $('#chartInput').value = '';
      state.chart.raw = '';
      state.chart.data = null;
      state.chart.file = null;
      $('#chartParse').textContent = '等待粘贴数据';
      renderChartFile();
      renderChart();
      api('chart_save', { raw: '', type: state.chart.type, title: '' });
    };
    $('#chartCopy').onclick = copyChartImage;
    // 导入文件：点按钮选，或直接把文件拖进页面
    $('#chartPick').onclick = () => $('#chartFile').click();
    $('#chartFile').addEventListener('change', (ev) => {
      const file = ev.target.files && ev.target.files[0];
      ev.target.value = '';
      if (file) importChartFile(file);
    });
    $('#chartSheets').addEventListener('click', (ev) => {
      const btn = ev.target.closest('[data-sheet]');
      if (!btn) return;
      applyChartSheet(Number(btn.dataset.sheet), true);
    });
    bindChartDrop();
    window.addEventListener('resize', redrawChart);
    if (state.chart.raw) $('#chartInput').value = state.chart.raw;
    $$('#chartTypes button').forEach((b) => b.classList.toggle('active', b.dataset.type === state.chart.type));
  }

  const redrawChart = debounce(() => {
    if (currentPage() === 'chart' && state.chart.data) renderChart();
  }, 180);

  function renderChartPage() {
    const input = $('#chartInput');
    if (input && document.activeElement !== input && input.value !== state.chart.raw) {
      input.value = state.chart.raw || '';
    }
    $$('#chartTypes button').forEach((b) => b.classList.toggle('active', b.dataset.type === state.chart.type));
    if (!state.chart.data && (state.chart.raw || '').trim()) drawChart(false);
    else renderChart();
  }

  /* ---------------- 图片工具：通用 ---------------- */
  const ID_SIZES = [
    { id: 'one', name: '一寸', w: 295, h: 413, mm: '25×35' },
    { id: 'small', name: '小一寸', w: 260, h: 378, mm: '22×32' },
    { id: 'two', name: '二寸', w: 413, h: 579, mm: '35×49' },
    { id: 'big', name: '大一寸', w: 390, h: 567, mm: '33×48' },
    { id: 'visa', name: '签证', w: 413, h: 531, mm: '35×45' },
    { id: 'us', name: '美签', w: 600, h: 600, mm: '51×51' },
  ];
  const ID_BACKS = [
    { id: 'none', name: '原图', color: '' },
    { id: 'white', name: '白底', color: '#FFFFFF' },
    { id: 'blue', name: '蓝底', color: '#438EDB' },
    { id: 'red', name: '红底', color: '#D93A49' },
    { id: 'gray', name: '灰底', color: '#EDEDED' },
  ];
  const idSize = (id) => ID_SIZES.find((s) => s.id === id) || ID_SIZES[0];
  const idBack = (id) => ID_BACKS.find((b) => b.id === id) || ID_BACKS[1];

  function fmtBytes(n) {
    if (!Number.isFinite(n) || n < 0) return '—';
    if (n < 1024) return `${Math.round(n)} B`;
    if (n < 1048576) return `${(n / 1024).toFixed(n < 10240 ? 1 : 0)} KB`;
    return `${(n / 1048576).toFixed(2)} MB`;
  }

  function stamp() {
    const d = new Date();
    return `${d.getFullYear()}${pad(d.getMonth() + 1)}${pad(d.getDate())}-${pad(d.getHours())}${pad(d.getMinutes())}${pad(d.getSeconds())}`;
  }

  function hexRgb(hex) {
    const n = parseInt(hex.slice(1), 16);
    return [(n >> 16) & 255, (n >> 8) & 255, n & 255];
  }

  function fileToImage(file) {
    return new Promise((resolve, reject) => {
      const url = URL.createObjectURL(file);
      const img = new Image();
      img.onload = () => { URL.revokeObjectURL(url); resolve(img); };
      img.onerror = () => { URL.revokeObjectURL(url); reject(new Error('这张图片打不开')); };
      img.src = url;
    });
  }

  const canvasBlob = (cv, type, quality) => new Promise((resolve, reject) => {
    cv.toBlob((blob) => (blob ? resolve(blob) : reject(new Error('编码失败'))), type, quality);
  });

  function blobToB64(blob) {
    return blob.arrayBuffer().then((buf) => {
      const bytes = new Uint8Array(buf);
      let out = '';
      const CHUNK = 0x8000;
      for (let i = 0; i < bytes.length; i += CHUNK) {
        out += String.fromCharCode.apply(null, bytes.subarray(i, i + CHUNK));
      }
      return btoa(out);
    });
  }

  async function saveBlob(name, blob, hintSel) {
    const hint = hintSel ? $(hintSel) : null;
    if (hint) { hint.className = 'save-hint'; hint.textContent = '正在保存…'; hint.removeAttribute('title'); }
    let b64 = '';
    try { b64 = await blobToB64(blob); }
    catch (err) {
      if (hint) { hint.className = 'save-hint err'; hint.textContent = '文件读取失败'; }
      return false;
    }
    const res = await api('image_save', name, b64);
    if (res && res.ok) {
      if (hint) {
        hint.className = 'save-hint ok';
        hint.title = res.path;
        hint.innerHTML = `已保存 ${fmtBytes(res.size)} · ${esc(res.name)}<a href="#" class="mini-link" data-exports>打开文件夹</a>`;
      }
      toast(`已保存 ${res.name}`, 'ok', 3200);
      return true;
    }
    if (hint) { hint.className = 'save-hint err'; hint.textContent = (res && res.error) || '保存失败'; }
    return false;
  }

  function bindDrop(zone, onFile) {
    let depth = 0;
    zone.addEventListener('dragenter', (ev) => {
      ev.preventDefault();
      depth += 1;
      zone.classList.add('dragover');
    });
    zone.addEventListener('dragover', (ev) => { ev.preventDefault(); });
    zone.addEventListener('dragleave', (ev) => {
      ev.preventDefault();
      depth -= 1;
      if (depth <= 0) { depth = 0; zone.classList.remove('dragover'); }
    });
    zone.addEventListener('drop', (ev) => {
      ev.preventDefault();
      depth = 0;
      zone.classList.remove('dragover');
      const file = ev.dataTransfer && ev.dataTransfer.files && ev.dataTransfer.files[0];
      if (file) onFile(file);
    });
  }

  function renderImagePage() {
    setImageTab(state.image.tab, true);
    if (state.image.id.img) drawId(false);
  }

  function setImageTab(tool, silent) {
    state.image.tab = tool;
    $$('#imgTabs .img-tab').forEach((b) => b.classList.toggle('active', b.dataset.tool === tool));
    $$('[data-img-panel]').forEach((p) => p.classList.toggle('active', p.dataset.imgPanel === tool));
    if (!silent) $('#scroll').scrollTop = 0;
  }

  /* ---------------- 图片工具：证件照 ---------------- */
  function drawId(quick) {
    const S = state.image.id;
    const cv = $('#idCanvas');
    const size = idSize(S.size);
    if (cv.width !== size.w) cv.width = size.w;
    if (cv.height !== size.h) cv.height = size.h;
    const ctx = cv.getContext('2d', { willReadFrequently: true });
    const back = idBack(S.back);
    ctx.setTransform(1, 0, 0, 1, 0, 0);
    ctx.clearRect(0, 0, size.w, size.h);
    ctx.fillStyle = back.color || '#FFFFFF';
    ctx.fillRect(0, 0, size.w, size.h);
    $('#idPx').textContent = `${size.w}×${size.h}`;
    const img = S.img;
    if (!img) return;
    const cover = Math.max(size.w / img.width, size.h / img.height);
    const scale = cover * (S.zoom / 100);
    const dw = img.width * scale;
    const dh = img.height * scale;
    const x = (size.w - dw) / 2 + S.ox * size.w;
    const y = (size.h - dh) / 2 + S.oy * size.h;
    ctx.imageSmoothingEnabled = true;
    ctx.imageSmoothingQuality = 'high';
    ctx.drawImage(img, x, y, dw, dh);
    if (!quick && back.color) idReplaceBg(ctx, size.w, size.h, S.tol, hexRgb(back.color));
  }

  /** 取边缘出现最多的颜色（量化到 5 位再投票），作为背景参考色 */
  function idEdgeColor(d, W, H) {
    const bins = new Map();
    const add = (x, y) => {
      const i = (y * W + x) << 2;
      const key = ((d[i] >> 3) << 10) | ((d[i + 1] >> 3) << 5) | (d[i + 2] >> 3);
      const e = bins.get(key);
      if (e) { e.n += 1; e.r += d[i]; e.g += d[i + 1]; e.b += d[i + 2]; }
      else bins.set(key, { n: 1, r: d[i], g: d[i + 1], b: d[i + 2] });
    };
    const step = Math.max(1, Math.round(W / 140));
    for (let x = 0; x < W; x += step) { add(x, 0); add(x, H - 1); }
    const half = Math.max(1, Math.round(H * 0.42));
    for (let y = 0; y < half; y += Math.max(1, Math.round(step / 2))) { add(0, y); add(W - 1, y); }
    let best = null;
    bins.forEach((e) => { if (!best || e.n > best.n) best = e; });
    if (!best) return [255, 255, 255];
    return [best.r / best.n, best.g / best.n, best.b / best.n];
  }

  /** 从四条边向内做洪水填充，只替换与背景参考色接近且连通的像素 */
  function idReplaceBg(ctx, W, H, tol, rgb) {
    const frame = ctx.getImageData(0, 0, W, H);
    const d = frame.data;
    const src = new Uint8ClampedArray(d);   // 比较一律用原像素，写入才用 d
    const ref = idEdgeColor(src, W, H);
    // 上限 72：比常见「背景 vs 皮肤」的色差还小，容差拉满也不会把脸吃进去
    const limit = Math.min(72, 6 + tol);
    const lim2 = limit * limit;
    // 局部阈值：与相邻像素颜色跳得太厉害就停，避免顺着脖子一路吃到脸上
    const local = Math.max(14, limit * 0.32);
    const local2 = local * local;
    const seen = new Uint8Array(W * H);
    const stack = [];
    const visit = (p, from) => {
      if (seen[p]) return;
      const i = p << 2;
      const dr = src[i] - ref[0];
      const dg = src[i + 1] - ref[1];
      const db = src[i + 2] - ref[2];
      if (dr * dr + dg * dg + db * db > lim2) return;
      if (from >= 0) {
        const j = from << 2;
        const lr = src[i] - src[j];
        const lg = src[i + 1] - src[j + 1];
        const lb = src[i + 2] - src[j + 2];
        if (lr * lr + lg * lg + lb * lb > local2) return;
      }
      seen[p] = 1;
      stack.push(p, from);
    };
    for (let x = 0; x < W; x += 1) { visit(x, -1); visit((H - 1) * W + x, -1); }
    for (let y = 0; y < H; y += 1) { visit(y * W, -1); visit(y * W + W - 1, -1); }
    let touched = 0;
    while (stack.length) {
      const from = stack.pop();
      const p = stack.pop();
      const i = p << 2;
      d[i] = rgb[0]; d[i + 1] = rgb[1]; d[i + 2] = rgb[2]; d[i + 3] = 255;
      touched += 1;
      const x = p % W;
      if (x > 0) visit(p - 1, p);
      if (x < W - 1) visit(p + 1, p);
      if (p >= W) visit(p - W, p);
      if (p < (H - 1) * W) visit(p + W, p);
    }
    if (touched) ctx.putImageData(frame, 0, 0);
    return touched;
  }

  function bindIdTool() {
    const S = state.image.id;
    const sizes = $('#idSizes');
    const backs = $('#idBgs');

    sizes.innerHTML = ID_SIZES
      .map((s) => `<button data-size="${s.id}" class="${s.id === S.size ? 'active' : ''}">${s.name}</button>`)
      .join('');
    backs.innerHTML = ID_BACKS.map((b) => (b.id === 'none'
      ? `<button class="id-bg none ${b.id === S.back ? 'active' : ''}" data-back="none" title="保留原背景">原</button>`
      : `<button class="id-bg ${b.id === S.back ? 'active' : ''}" data-back="${b.id}" style="--swatch:${b.color}" title="${b.name}"></button>`))
      .join('');

    sizes.addEventListener('click', (ev) => {
      const btn = ev.target.closest('[data-size]');
      if (!btn) return;
      S.size = btn.dataset.size;
      $$('button', sizes).forEach((b) => b.classList.toggle('active', b === btn));
      drawId(false);
    });

    backs.addEventListener('click', (ev) => {
      const btn = ev.target.closest('[data-back]');
      if (!btn) return;
      S.back = btn.dataset.back;
      $$('button', backs).forEach((b) => b.classList.toggle('active', b === btn));
      drawId(false);
    });

    $('#idTol').addEventListener('input', (ev) => {
      S.tol = Number(ev.target.value);
      $('#idTolVal').textContent = String(S.tol);
      drawId(false);
    });

    const redrawIdSoft = debounce(() => drawId(false), 160);
    $('#idZoom').addEventListener('input', (ev) => {
      S.zoom = Number(ev.target.value);
      $('#idZoomVal').textContent = `${S.zoom}%`;
      drawId(true);
      redrawIdSoft();
    });

    $('#idReset').onclick = () => {
      S.ox = 0; S.oy = 0; S.zoom = 100; S.tol = 34;
      $('#idZoom').value = 100;
      $('#idZoomVal').textContent = '100%';
      $('#idTol').value = 34;
      $('#idTolVal').textContent = '34';
      drawId(false);
    };

    $('#idPick').onclick = () => $('#idFile').click();
    $('#idFile').addEventListener('change', (ev) => {
      const file = ev.target.files && ev.target.files[0];
      if (file) loadIdImage(file);
      ev.target.value = '';
    });
    bindDrop($('#idStage'), (file) => {
      if (!/^image\//.test(file.type)) { toast('这里是照片，不是文件', 'err'); return; }
      loadIdImage(file);
    });

    async function loadIdImage(file) {
      try {
        const img = await fileToImage(file);
        S.img = img;
        S.name = file.name;
        S.ox = 0; S.oy = 0; S.zoom = 100;
        $('#idZoom').value = 100;
        $('#idZoomVal').textContent = '100%';
        $('#idDrop').hidden = true;
        $('#idFrame').hidden = false;
        $('#idFilebar').hidden = false;
        $('#idFileName').textContent = file.name;
        $('#idFileInfo').textContent = `${img.width}×${img.height} · ${fmtBytes(file.size)}`;
        $('#idSave').disabled = false;
        $('#idCopy').disabled = false;
        $('#idSaveHint').textContent = '';
        drawId(false);
      } catch (err) {
        toast(err.message || '这张图片打不开', 'err');
      }
    }

    // 拖动平移 + 滚轮缩放
    const cv = $('#idCanvas');
    let drag = null;
    cv.addEventListener('pointerdown', (ev) => {
      if (!S.img) return;
      drag = { x: ev.clientX, y: ev.clientY, ox: S.ox, oy: S.oy };
      cv.classList.add('dragging');
      try { cv.setPointerCapture(ev.pointerId); } catch (e) { /* 忽略 */ }
    });
    cv.addEventListener('pointermove', (ev) => {
      if (!drag) return;
      const rect = cv.getBoundingClientRect();
      if (!rect.width || !rect.height) return;
      S.ox = Math.max(-0.55, Math.min(0.55, drag.ox + (ev.clientX - drag.x) / rect.width));
      S.oy = Math.max(-0.55, Math.min(0.55, drag.oy + (ev.clientY - drag.y) / rect.height));
      drawId(true);
    });
    const endDrag = (ev) => {
      if (!drag) return;
      drag = null;
      cv.classList.remove('dragging');
      if (ev && ev.pointerId != null && cv.hasPointerCapture && cv.hasPointerCapture(ev.pointerId)) {
        cv.releasePointerCapture(ev.pointerId);
      }
      drawId(false);
    };
    cv.addEventListener('pointerup', endDrag);
    cv.addEventListener('pointercancel', endDrag);
    cv.addEventListener('wheel', (ev) => {
      if (!S.img) return;
      ev.preventDefault();
      const next = Math.max(100, Math.min(260, S.zoom + (ev.deltaY < 0 ? 5 : -5)));
      S.zoom = next;
      $('#idZoom').value = next;
      $('#idZoomVal').textContent = `${next}%`;
      drawId(true);
      redrawIdSoft();
    }, { passive: false });

    $('#idSave').onclick = async () => {
      if (!S.img) return;
      const blob = await canvasBlob($('#idCanvas'), 'image/png');
      const size = idSize(S.size);
      await saveBlob(`证件照-${size.name}-${stamp()}.png`, blob, '#idSaveHint');
    };

    $('#idCopy').onclick = async () => {
      if (!S.img) return;
      try {
        const blob = await canvasBlob($('#idCanvas'), 'image/png');
        await navigator.clipboard.write([new ClipboardItem({ 'image/png': blob })]);
        toast('已复制到剪贴板', 'ok');
      } catch (err) {
        toast(`复制失败：${(err && err.message) || err}`, 'err');
      }
    };
  }

  /* ---------------- 图片工具：视频转 GIF ---------------- */
  const GIF_PIXEL_BUDGET = 9000000;

  /** 带自动扩容的字节缓冲，避免百万次 push */
  class GifBuf {
    constructor(size) {
      this.buf = new Uint8Array(Math.max(2048, size));
      this.n = 0;
    }

    need(k) {
      if (this.n + k <= this.buf.length) return;
      let cap = this.buf.length * 2;
      while (cap < this.n + k) cap *= 2;
      const next = new Uint8Array(cap);
      next.set(this.buf.subarray(0, this.n));
      this.buf = next;
    }

    byte(v) { this.need(1); this.buf[this.n] = v & 255; this.n += 1; }
    u16(v) {
      this.need(2);
      this.buf[this.n] = v & 255;
      this.buf[this.n + 1] = (v >> 8) & 255;
      this.n += 2;
    }
    ascii(s) {
      this.need(s.length);
      for (let i = 0; i < s.length; i += 1) this.buf[this.n + i] = s.charCodeAt(i) & 255;
      this.n += s.length;
    }
    bytes(arr) {
      this.need(arr.length);
      this.buf.set(arr, this.n);
      this.n += arr.length;
    }
    result() { return this.buf.subarray(0, this.n); }
  }

  /** 中位切分建 256 色调色板，并把 15 位颜色键映射成索引 */
  function gifPalette(frames, W, H) {
    const hist = new Map();
    const total = W * H;
    const stride = Math.max(1, Math.floor(total / 14000));
    for (const frame of frames) {
      const d = frame.data;
      for (let p = 0; p < total; p += stride) {
        const i = p << 2;
        const key = ((d[i] >> 3) << 10) | ((d[i + 1] >> 3) << 5) | (d[i + 2] >> 3);
        const e = hist.get(key);
        if (e) { e.n += 1; e.r += d[i]; e.g += d[i + 1]; e.b += d[i + 2]; }
        else hist.set(key, { n: 1, r: d[i], g: d[i + 1], b: d[i + 2] });
      }
    }
    const items = [];
    hist.forEach((e, key) => {
      items.push({ key, n: e.n, r: e.r / e.n, g: e.g / e.n, b: e.b / e.n });
    });
    if (!items.length) items.push({ key: 0, n: 1, r: 0, g: 0, b: 0 });

    const boxOf = (list) => {
      let rMin = 255, rMax = 0, gMin = 255, gMax = 0, bMin = 255, bMax = 0, n = 0;
      for (const it of list) {
        if (it.r < rMin) rMin = it.r;
        if (it.r > rMax) rMax = it.r;
        if (it.g < gMin) gMin = it.g;
        if (it.g > gMax) gMax = it.g;
        if (it.b < bMin) bMin = it.b;
        if (it.b > bMax) bMax = it.b;
        n += it.n;
      }
      const range = [rMax - rMin, gMax - gMin, bMax - bMin];
      return { list, n, range, span: Math.max(range[0], range[1], range[2]) };
    };

    let boxes = [boxOf(items)];
    while (boxes.length < 256) {
      let pick = -1;
      let score = -1;
      for (let i = 0; i < boxes.length; i += 1) {
        const b = boxes[i];
        if (b.list.length < 2) continue;
        const s = b.n * (b.span + 1);
        if (s > score) { score = s; pick = i; }
      }
      if (pick < 0) break;
      const box = boxes[pick];
      const ch = box.range[0] >= box.range[1] && box.range[0] >= box.range[2] ? 'r'
        : (box.range[1] >= box.range[2] ? 'g' : 'b');
      const list = box.list.slice().sort((a, b) => a[ch] - b[ch]);
      const half = box.n / 2;
      let acc = 0;
      let cut = list.length - 1;
      for (let i = 0; i < list.length - 1; i += 1) {
        acc += list[i].n;
        if (acc >= half) { cut = i + 1; break; }
      }
      cut = Math.max(1, Math.min(list.length - 1, cut));
      boxes.splice(pick, 1, boxOf(list.slice(0, cut)), boxOf(list.slice(cut)));
    }

    const palette = new Uint8Array(768);
    const owner = new Int16Array(32768).fill(-1);
    boxes.forEach((box, idx) => {
      let r = 0, g = 0, b = 0, n = 0;
      for (const it of box.list) {
        r += it.r * it.n; g += it.g * it.n; b += it.b * it.n; n += it.n;
      }
      n = n || 1;
      palette[idx * 3] = Math.round(r / n);
      palette[idx * 3 + 1] = Math.round(g / n);
      palette[idx * 3 + 2] = Math.round(b / n);
      for (const it of box.list) if (owner[it.key] < 0) owner[it.key] = idx;
    });

    const used = Math.min(boxes.length, 256);
    const lut = new Uint8Array(32768);
    for (let k = 0; k < 32768; k += 1) {
      if (owner[k] >= 0) { lut[k] = owner[k]; continue; }
      const r = (((k >> 10) & 31) << 3) | 4;
      const g = (((k >> 5) & 31) << 3) | 4;
      const b = ((k & 31) << 3) | 4;
      let best = 0;
      let bestD = Infinity;
      for (let i = 0; i < used; i += 1) {
        const dr = r - palette[i * 3];
        const dg = g - palette[i * 3 + 1];
        const db = b - palette[i * 3 + 2];
        const dd = dr * dr + dg * dg + db * db;
        if (dd < bestD) { bestD = dd; best = i; }
      }
      lut[k] = best;
    }
    return { palette, lut };
  }

  /** GIF 变长 LZW（码长从小往大长，字典满 4096 发 clear 重置） */
  function gifLzw(indices, minCodeSize) {
    const clear = 1 << minCodeSize;
    const eoi = clear + 1;
    const out = [];
    let cur = 0;
    let bits = 0;
    const emit = (code, size) => {
      cur |= code << bits;
      bits += size;
      while (bits >= 8) {
        out.push(cur & 255);
        cur >>>= 8;
        bits -= 8;
      }
    };
    let dict = new Map();
    let next = eoi + 1;
    let size = minCodeSize + 1;
    emit(clear, size);
    let prefix = indices[0];
    for (let i = 1; i < indices.length; i += 1) {
      const k = indices[i];
      const key = prefix * 4096 + k;
      const hit = dict.get(key);
      if (hit !== undefined) { prefix = hit; continue; }
      emit(prefix, size);
      if (next < 4096) {
        // 加宽判定要用「尚未分配」的 next：和解码端读到这个码后的 RunningCode 对齐
        if (next >= (1 << size) && size < 12) size += 1;
        dict.set(key, next);
        next += 1;
      } else {
        emit(clear, size);
        dict = new Map();
        next = eoi + 1;
        size = minCodeSize + 1;
      }
      prefix = k;
    }
    emit(prefix, size);
    emit(eoi, size);
    if (bits > 0) out.push(cur & 255);
    return Uint8Array.from(out);
  }

  function gifBuild(frames, W, H, fps, palette) {
    const delay = Math.max(2, Math.round(100 / fps));
    const buf = new GifBuf(W * H * Math.min(frames.length, 120) + 8192);
    buf.ascii('GIF89a');
    buf.u16(W);
    buf.u16(H);
    buf.byte(0xF7);      // 全局调色板，256 色
    buf.byte(0);
    buf.byte(0);
    buf.bytes(palette);
    // NETSCAPE2.0 无限循环
    buf.byte(0x21); buf.byte(0xFF); buf.byte(0x0B);
    buf.ascii('NETSCAPE2.0');
    buf.byte(0x03); buf.byte(0x01); buf.u16(0); buf.byte(0x00);
    for (const indices of frames) {
      buf.byte(0x21); buf.byte(0xF9); buf.byte(0x04); buf.byte(0x04);
      buf.u16(delay);
      buf.byte(0);
      buf.byte(0x00);
      buf.byte(0x2C);
      buf.u16(0); buf.u16(0); buf.u16(W); buf.u16(H); buf.byte(0);
      buf.byte(8);
      const data = gifLzw(indices, 8);
      for (let i = 0; i < data.length; i += 255) {
        const n = Math.min(255, data.length - i);
        buf.byte(n);
        buf.bytes(data.subarray(i, i + n));
      }
      buf.byte(0);
    }
    buf.byte(0x3B);
    return buf.result();
  }

  function seekVideo(video, t) {
    return new Promise((resolve) => {
      let settled = false;
      const done = () => {
        if (settled) return;
        settled = true;
        video.removeEventListener('seeked', done);
        resolve();
      };
      video.addEventListener('seeked', done);
      try { video.currentTime = t; } catch (e) { done(); }
      setTimeout(done, 3000);
    });
  }

  /**
   * 抓帧：优先「播放 + requestVideoFrameCallback 按 mediaTime 抽帧」，
   * 这样即使容器没有索引（MediaRecorder 生成的 webm）也能拿到真实变化的画面；
   * 不支持时退回逐帧 seek。
   */
  async function gifGrab(video, start, len, fps, W, H, onProgress) {
    const cv = document.createElement('canvas');
    cv.width = W;
    cv.height = H;
    const ctx = cv.getContext('2d', { willReadFrequently: true });
    const count = Math.max(1, Math.round(len * fps));
    const step = 1 / fps;
    const frames = [];

    const shoot = () => {
      ctx.drawImage(video, 0, 0, W, H);
      frames.push(ctx.getImageData(0, 0, W, H));
      if (onProgress) onProgress(frames.length, count);
    };

    if (typeof video.requestVideoFrameCallback === 'function') {
      try {
        await seekVideo(video, start);
        await video.play();
        await new Promise((resolve) => {
          let next = 0;
          let base = null;      // 以第一帧的实际位置为基准，避免 seek 落点偏后时一把抓满
          let lastT = -1;
          let settled = false;
          const stop = () => {
            if (settled) return;
            settled = true;
            resolve();
          };
          const tick = (now, meta) => {
            if (settled) return;
            const t = meta && Number(meta.mediaTime);
            if (Number.isFinite(t) && t > lastT + 0.001) {
              lastT = t;
              if (base === null) base = t;
              while (next < count && t - base >= next * step - 0.002) {
                shoot();
                next += 1;
              }
            }
            if (next >= count) { stop(); return; }
            video.requestVideoFrameCallback(tick);
          };
          video.requestVideoFrameCallback(tick);
          setTimeout(stop, len * 1000 + 6000);
        });
      } catch (err) {
        // 播放被拒或解码失败，走下面的回退
      } finally {
        try { video.pause(); } catch (e) { /* 忽略 */ }
      }
      if (frames.length >= count) return frames.slice(0, count);
    }

    frames.length = 0;
    for (let i = 0; i < count; i += 1) {
      const t = Math.min(start + i * step, Math.max(0, (video.duration || 0) - 0.03));
      await seekVideo(video, t);
      await new Promise((r) => setTimeout(r, 14));
      shoot();
      await new Promise((r) => setTimeout(r, 0));
    }
    try { video.pause(); } catch (e) { /* 忽略 */ }
    return frames;
  }

  function bindGifTool() {
    const S = state.image.gif;
    const video = $('#gifVideo');
    const drop = $('#gifDrop');
    const stage = $('#gifStage');

    $('#gifPick').onclick = () => $('#gifFile').click();
    $('#gifFile').addEventListener('change', (ev) => {
      const file = ev.target.files && ev.target.files[0];
      if (file) loadVideo(file);
      ev.target.value = '';
    });
    bindDrop(stage, (file) => {
      if (!/^video\//.test(file.type)) { toast('这里要放视频文件', 'err'); return; }
      loadVideo(file);
    });

    $('#gifDur').addEventListener('input', (ev) => {
      S.len = Number(ev.target.value);
      $('#gifDurVal').textContent = `${S.len.toFixed(1)} s`;
      syncStartRange();
    });
    $('#gifStart').addEventListener('input', (ev) => {
      S.start = Number(ev.target.value);
      $('#gifStartVal').textContent = `${S.start.toFixed(1)} s`;
      if (S.url) {
        try { video.currentTime = Math.min(S.start, Math.max(0, (S.duration || 1) - 0.05)); } catch (e) { /* 忽略 */ }
      }
    });

    $('#gifFps').addEventListener('click', (ev) => {
      const btn = ev.target.closest('[data-fps]');
      if (!btn) return;
      S.fps = Number(btn.dataset.fps);
      $$('#gifFps button').forEach((b) => b.classList.toggle('active', b === btn));
    });
    $('#gifWidth').addEventListener('click', (ev) => {
      const btn = ev.target.closest('[data-w]');
      if (!btn) return;
      S.width = Number(btn.dataset.w);
      $$('#gifWidth button').forEach((b) => b.classList.toggle('active', b === btn));
    });

    function syncStartRange() {
      const limit = Math.max(0, (S.duration || 0) - S.len);
      $('#gifStart').max = limit.toFixed(1);
      if (S.start > limit) {
        S.start = limit;
        $('#gifStart').value = limit;
        $('#gifStartVal').textContent = `${limit.toFixed(1)} s`;
      }
    }

    let loadSeq = 0;

    async function loadVideo(file) {
      const mine = (loadSeq += 1);
      if (S.url) URL.revokeObjectURL(S.url);
      S.url = URL.createObjectURL(file);
      S.name = file.name;
      S.blob = null;
      S.start = 0;
      S.duration = 0;
      $('#gifPreview').hidden = true;
      $('#gifSave').disabled = true;
      $('#gifSaveHint').textContent = '';
      $('#gifProgress').hidden = true;
      drop.hidden = true;
      video.hidden = false;
      video.src = S.url;
      $('#gifFilebar').hidden = false;
      $('#gifFileName').textContent = file.name;
      $('#gifFileInfo').textContent = fmtBytes(file.size);
      $('#gifMeta').textContent = '读取中…';
      $('#gifMake').disabled = true;

      await new Promise((resolve) => {
        if (video.readyState >= 1) return resolve();
        const done = () => { video.removeEventListener('loadedmetadata', done); resolve(); };
        video.addEventListener('loadedmetadata', done);
        setTimeout(done, 5000);
        return undefined;
      });

      let dur = video.duration;
      if (!Number.isFinite(dur) || dur <= 0) {
        // 部分 webm 不写时长，跳到很远处逼它算出 duration
        await new Promise((resolve) => {
          let settled = false;
          const done = () => {
            if (settled) return;
            settled = true;
            video.removeEventListener('timeupdate', done);
            resolve();
          };
          video.addEventListener('timeupdate', done);
          try { video.currentTime = 1e6; } catch (e) { done(); }
          setTimeout(done, 1500);
        });
        try { video.currentTime = 0; } catch (e) { /* 忽略 */ }
        dur = video.duration;
      }
      if (mine !== loadSeq) return;   // 期间又拖进来一个，交给新的那次处理
      S.duration = Number.isFinite(dur) && dur > 0 ? dur : 0;

      const total = S.duration || 0;
      const maxLen = Math.max(1, Math.min(10, total || 10));
      S.len = Math.min(S.len || 3, maxLen);
      $('#gifDur').max = maxLen;
      $('#gifDur').value = S.len;
      $('#gifDurVal').textContent = `${S.len.toFixed(1)} s`;
      syncStartRange();
      $('#gifStart').value = 0;
      $('#gifStartVal').textContent = '0.0 s';

      const w = video.videoWidth || 0;
      const h = video.videoHeight || 0;
      $('#gifMeta').textContent = total ? `${w}×${h} · ${total.toFixed(1)}s` : `${w}×${h}`;
      $('#gifFileInfo').textContent = `${w}×${h} · ${total ? `${total.toFixed(1)} 秒 · ` : ''}${fmtBytes(file.size)}`;
      $('#gifMake').disabled = !(total > 0);
      if (!(total > 0)) toast('读不到视频时长，换一个 mp4 试试', 'err', 4000);
    }

    $('#gifMake').onclick = async () => {
      if (S.busy) return;
      if (!S.url || !(S.duration > 0)) { toast('先放一个视频进来', 'err'); return; }
      S.busy = true;
      $('#gifMake').disabled = true;
      $('#gifSave').disabled = true;
      $('#gifProgress').hidden = false;
      $('#gifBar').style.width = '0%';
      $('#gifProgressText').textContent = '准备中…';
      try {
        const len = Math.min(S.len, S.duration);
        const start = Math.max(0, Math.min(S.start, Math.max(0, S.duration - 0.05)));
        const srcW = video.videoWidth || 640;
        const srcH = video.videoHeight || 360;
        let W = Math.min(S.width, srcW);
        W -= W % 2;
        let H = Math.max(2, Math.round((W * srcH) / srcW));
        H -= H % 2;
        const count = Math.max(1, Math.round(len * S.fps));
        while (W * H * count > GIF_PIXEL_BUDGET && W > 120) {
          W = Math.round(W * 0.8);
          W -= W % 2;
          H = Math.max(2, Math.round((W * srcH) / srcW));
          H -= H % 2;
        }

        const frames = await gifGrab(video, start, len, S.fps, W, H, (done, total) => {
          $('#gifBar').style.width = `${Math.round((done / total) * 55)}%`;
          $('#gifProgressText').textContent = `抓取画面 ${done}/${total}`;
        });
        if (!frames.length) throw new Error('没抓到画面');

        $('#gifProgressText').textContent = '计算调色板…';
        await new Promise((r) => setTimeout(r, 0));
        const { palette, lut } = gifPalette(frames, W, H);

        const indexed = [];
        for (let f = 0; f < frames.length; f += 1) {
          const d = frames[f].data;
          const idx = new Uint8Array(W * H);
          for (let p = 0; p < idx.length; p += 1) {
            const i = p << 2;
            idx[p] = lut[((d[i] >> 3) << 10) | ((d[i + 1] >> 3) << 5) | (d[i + 2] >> 3)];
          }
          indexed.push(idx);
          $('#gifBar').style.width = `${55 + Math.round(((f + 1) / frames.length) * 35)}%`;
          $('#gifProgressText').textContent = `编码 ${f + 1}/${frames.length}`;
          await new Promise((r) => setTimeout(r, 0));
        }

        const bytes = gifBuild(indexed, W, H, S.fps, palette);
        const blob = new Blob([bytes], { type: 'image/gif' });
        S.blob = blob;
        if (S.previewUrl) URL.revokeObjectURL(S.previewUrl);
        S.previewUrl = URL.createObjectURL(blob);
        $('#gifImg').src = S.previewUrl;
        $('#gifPreview').hidden = false;
        $('#gifInfo').textContent = `${W}×${H} · ${frames.length} 帧 · ${S.fps}fps · ${fmtBytes(blob.size)}`;
        $('#gifSave').disabled = false;
        $('#gifBar').style.width = '100%';
        $('#gifProgressText').textContent = `完成，${fmtBytes(blob.size)}`;
        toast(`GIF 生成好了，${fmtBytes(blob.size)}`, 'ok');
      } catch (err) {
        $('#gifProgressText').textContent = `失败：${(err && err.message) || err}`;
        toast(`转换失败：${(err && err.message) || err}`, 'err', 4200);
      } finally {
        S.busy = false;
        $('#gifMake').disabled = false;
        video.currentTime = 0;
      }
    };

    $('#gifSave').onclick = async () => {
      if (!S.blob) return;
      await saveBlob(`动图-${stamp()}.gif`, S.blob, '#gifSaveHint');
    };
  }

  /* ---------------- 图片工具：压缩图片 ---------------- */
  async function compressToTarget(img, targetBytes, fmt, maxEdge) {
    let w = img.naturalWidth || img.width;
    let h = img.naturalHeight || img.height;
    if (maxEdge && Math.max(w, h) > maxEdge) {
      const k = maxEdge / Math.max(w, h);
      w = Math.max(1, Math.round(w * k));
      h = Math.max(1, Math.round(h * k));
    }
    const cv = document.createElement('canvas');
    const ctx = cv.getContext('2d');
    let scale = 1;
    for (let round = 0; round < 8; round += 1) {
      const cw = Math.max(1, Math.round(w * scale));
      const ch = Math.max(1, Math.round(h * scale));
      cv.width = cw;
      cv.height = ch;
      ctx.clearRect(0, 0, cw, ch);
      if (fmt === 'image/jpeg') {
        ctx.fillStyle = '#FFFFFF';
        ctx.fillRect(0, 0, cw, ch);
      }
      ctx.imageSmoothingEnabled = true;
      ctx.imageSmoothingQuality = 'high';
      ctx.drawImage(img, 0, 0, cw, ch);

      const top = await canvasBlob(cv, fmt, 0.95);
      if (top.size <= targetBytes) return { blob: top, quality: 0.95, w: cw, h: ch };

      let lo = 0.45;
      let hi = 0.95;
      let found = null;
      for (let i = 0; i < 8; i += 1) {
        const q = (lo + hi) / 2;
        const blob = await canvasBlob(cv, fmt, q);
        if (blob.size <= targetBytes) { found = { blob, quality: q, w: cw, h: ch }; lo = q; }
        else hi = q;
      }
      if (found) return found;
      scale *= 0.78;
    }
    return null;
  }

  function bindCmpTool() {
    const S = state.image.cmp;
    const stage = $('#cmpStage');

    $('#cmpPick').onclick = () => $('#cmpFile').click();
    $('#cmpFile').addEventListener('change', (ev) => {
      const file = ev.target.files && ev.target.files[0];
      if (file) loadCmp(file);
      ev.target.value = '';
    });
    bindDrop(stage, (file) => {
      if (!/^image\//.test(file.type)) { toast('这里要放图片', 'err'); return; }
      loadCmp(file);
    });

    $('#cmpTargets').addEventListener('click', (ev) => {
      const btn = ev.target.closest('[data-kb]');
      if (!btn) return;
      $('#cmpKb').value = btn.dataset.kb;
      $$('#cmpTargets button').forEach((b) => b.classList.toggle('active', b === btn));
    });
    $('#cmpKb').addEventListener('input', () => {
      $$('#cmpTargets button').forEach((b) => b.classList.remove('active'));
    });
    $('#cmpFmt').addEventListener('click', (ev) => {
      const btn = ev.target.closest('[data-fmt]');
      if (!btn) return;
      S.fmt = btn.dataset.fmt;
      $$('#cmpFmt button').forEach((b) => b.classList.toggle('active', b === btn));
    });
    $('#cmpMax').addEventListener('click', (ev) => {
      const btn = ev.target.closest('[data-max]');
      if (!btn) return;
      S.max = Number(btn.dataset.max);
      $$('#cmpMax button').forEach((b) => b.classList.toggle('active', b === btn));
    });

    async function loadCmp(file) {
      try {
        const img = await fileToImage(file);
        S.file = file;
        S.img = img;
        S.blob = null;
        S.meta = null;
        $('#cmpDrop').hidden = true;
        $('#cmpPreview').hidden = true;
        $('#cmpFilebar').hidden = false;
        $('#cmpFileName').textContent = file.name;
        $('#cmpFileInfo').textContent = `${img.width}×${img.height} · ${fmtBytes(file.size)}`;
        $('#cmpOrigMeta').textContent = fmtBytes(file.size);
        $('#cmpRun').disabled = false;
        $('#cmpSave').disabled = true;
        $('#cmpStat').hidden = true;
        $('#cmpSaveHint').textContent = '';
      } catch (err) {
        toast(err.message || '这张图片打不开', 'err');
      }
    }

    $('#cmpRun').onclick = async () => {
      if (!S.img) return;
      const kb = Math.max(10, Math.min(20000, Number($('#cmpKb').value) || 200));
      S.target = kb;
      const target = kb * 1024;
      $('#cmpRun').disabled = true;
      $('#cmpRun').textContent = '压缩中…';
      try {
        const out = await compressToTarget(S.img, target, S.fmt, S.max);
        if (!out) {
          toast('压不到这个大小，把目标调大一点或换 WebP', 'err', 4000);
          return;
        }
        S.blob = out.blob;
        S.meta = out;
        if (S.previewUrl) URL.revokeObjectURL(S.previewUrl);
        S.previewUrl = URL.createObjectURL(out.blob);
        $('#cmpImg').src = S.previewUrl;
        $('#cmpPreview').hidden = false;
        $('#cmpStat').hidden = false;
        const origW = S.img.naturalWidth || S.img.width;
        $('#cmpBefore').textContent = `${fmtBytes(S.file.size)} · ${origW}×${S.img.naturalHeight || S.img.height}`;
        $('#cmpAfter').textContent = `${fmtBytes(out.blob.size)} · ${out.w}×${out.h}`;
        const after = $('#cmpAfter');
        after.className = out.blob.size <= target ? 'good' : 'bad';
        $('#cmpSize').textContent = `${Math.round((out.w / origW) * 100)}%`;
        $('#cmpQuality').textContent = out.quality >= 0.949 ? '最高' : out.quality.toFixed(2);
        $('#cmpSave').disabled = false;
        toast(`压到 ${fmtBytes(out.blob.size)}`, 'ok');
      } catch (err) {
        toast(`压缩失败：${(err && err.message) || err}`, 'err', 4000);
      } finally {
        $('#cmpRun').disabled = false;
        $('#cmpRun').innerHTML = `${ic('compress')}开始压缩`;
      }
    };

    $('#cmpSave').onclick = async () => {
      if (!S.blob) return;
      const ext = S.fmt === 'image/webp' ? 'webp' : 'jpg';
      const base = (S.file && S.file.name ? S.file.name.replace(/\.[^.]+$/, '') : '图片').slice(0, 40);
      await saveBlob(`压缩-${base}-${S.target}KB.${ext}`, S.blob, '#cmpSaveHint');
    };
  }

  function bindImagePage() {
    $$('#imgTabs .img-tab').forEach((btn) => {
      btn.addEventListener('click', () => setImageTab(btn.dataset.tool));
    });
    document.addEventListener('click', async (ev) => {
      const link = ev.target.closest('[data-exports]');
      if (!link) return;
      ev.preventDefault();
      const res = await api('image_open_dir');
      if (!res || !res.ok) toast('打不开文件夹', 'err');
    });
    bindIdTool();
    bindGifTool();
    bindCmpTool();
  }

  /* ---------------- 全局搜索 ---------------- */
  const CMD_TYPES = {
    note: { label: '笔记', icon: 'note' },
    todo: { label: '待办', icon: 'todo' },
    plan: { label: '日程', icon: 'plan' },
    countdown: { label: '倒数日', icon: 'hourglass' },
    history: { label: '翻译', icon: 'translate' },
    mood: { label: '心情', icon: 'smile' },
  };

  function hlText(text, query) {
    const safe = esc(text || '');
    if (!query) return safe;
    const low = safe.toLowerCase();
    const q = query.toLowerCase();
    let out = '';
    let from = 0;
    let at = low.indexOf(q);
    while (at >= 0) {
      out += `${safe.slice(from, at)}<mark>${safe.slice(at, at + q.length)}</mark>`;
      from = at + q.length;
      at = low.indexOf(q, from);
    }
    return out + safe.slice(from);
  }

  function cmdOpen() {
    state.cmd.open = true;
    state.cmd.items = [];
    state.cmd.idx = -1;
    $('#cmdRoot').classList.add('open');
    $('#cmdRoot').setAttribute('aria-hidden', 'false');
    const input = $('#cmdInput');
    input.value = '';
    input.focus();
    $('#cmdList').innerHTML = `<div class="cmd-empty">输入关键词，翻遍笔记、待办、日程、倒数日、翻译和心情</div>`;
    $('#cmdMeta').textContent = '';
  }

  function cmdClose() {
    state.cmd.open = false;
    $('#cmdRoot').classList.remove('open');
    $('#cmdRoot').setAttribute('aria-hidden', 'true');
    $('#cmdInput').blur();
  }

  function renderCmdList() {
    const host = $('#cmdList');
    const items = state.cmd.items || [];
    const q = state.cmd.query || '';
    if (!q.trim()) {
      host.innerHTML = `<div class="cmd-empty">输入关键词试试，比如「周报」「生日」</div>`;
      $('#cmdMeta').textContent = '';
      return;
    }
    if (!items.length) {
      host.innerHTML = `<div class="cmd-empty">没有找到「${esc(q)}」相关的内容</div>`;
      $('#cmdMeta').textContent = '0 条结果';
      return;
    }
    let html = '';
    let lastType = '';
    items.forEach((item, index) => {
      const meta = CMD_TYPES[item.type] || { label: '内容', icon: 'search' };
      if (item.type !== lastType) {
        html += `<li class="cmd-group">${meta.label}</li>`;
        lastType = item.type;
      }
      html += `<li class="cmd-row ${index === state.cmd.idx ? 'on' : ''}" data-cmd-idx="${index}">
        <span class="cmd-ico-cell">${ic(meta.icon)}</span>
        <span class="cmd-text">
          <strong>${hlText(item.title, q)}</strong>
          <span>${hlText(item.sub || '', q)}</span>
        </span>
        <span class="cmd-type">${meta.label}</span>
      </li>`;
    });
    host.innerHTML = html;
    $$('[data-cmd-idx]', host).forEach((row) => {
      row.onclick = () => cmdActivate(Number(row.dataset.cmdIdx));
    });
    $('#cmdMeta').textContent = `${items.length} 条结果`;
  }

  function cmdMove(step) {
    const items = state.cmd.items || [];
    if (!items.length) return;
    state.cmd.idx = (state.cmd.idx + step + items.length) % items.length;
    $$('.cmd-row').forEach((row) => row.classList.toggle('on', Number(row.dataset.cmdIdx) === state.cmd.idx));
    const active = $(`.cmd-row[data-cmd-idx="${state.cmd.idx}"]`);
    if (active) active.scrollIntoView({ block: 'nearest' });
  }

  function cmdActivate(index) {
    const item = (state.cmd.items || [])[index];
    if (!item) return;
    cmdClose();
    if (item.type === 'note') {
      state.notes.currentId = item.id;
      go('notes');
      return;
    }
    if (item.type === 'todo') {
      state.todo.view = 'all';
      state.todo.highlight = item.id;
      go('todo');
      return;
    }
    if (item.type === 'plan') {
      state.plan.date = item.date;
      go('plan');
      return;
    }
    if (item.type === 'countdown') {
      state.time.tab = 'countdown';
      go('time');
      return;
    }
    if (item.type === 'mood') {
      state.mood.ym = String(item.date).slice(0, 7);
      state.mood.selected = item.date;
      state.mood.mood = 0;
      state.mood.text = '';
      go('mood');
      return;
    }
    go('history');
  }

  const runSearch = debounce(async (query) => {
    const seq = (state.cmd.seq = (state.cmd.seq || 0) + 1);
    state.cmd.query = query;
    if (!query.trim()) {
      state.cmd.items = [];
      renderCmdList();
      return;
    }
    const res = await api('search_all', query.trim());
    if (seq !== state.cmd.seq) return; // 后发的请求优先
    state.cmd.items = (res && res.items) || [];
    state.cmd.idx = state.cmd.items.length ? 0 : -1;
    renderCmdList();
  }, 170);

  function bindCommandPalette() {
    $('#cmdOpen').onclick = cmdOpen;
    $$('[data-cmd-close]').forEach((el) => { el.onclick = cmdClose; });
    const input = $('#cmdInput');
    input.addEventListener('input', () => runSearch(input.value));
    input.addEventListener('keydown', (ev) => {
      if (ev.key === 'ArrowDown') { ev.preventDefault(); cmdMove(1); }
      else if (ev.key === 'ArrowUp') { ev.preventDefault(); cmdMove(-1); }
      else if (ev.key === 'Enter') {
        ev.preventDefault();
        if (state.cmd.idx >= 0) cmdActivate(state.cmd.idx);
        else if (state.cmd.items.length) cmdActivate(0);
      } else if (ev.key === 'Escape') {
        ev.preventDefault();
        cmdClose();
      }
    });
    document.addEventListener('keydown', (ev) => {
      if ((ev.ctrlKey || ev.metaKey) && (ev.key === 'k' || ev.key === 'K')) {
        ev.preventDefault();
        if (state.cmd.open) cmdClose(); else cmdOpen();
      }
    });
  }

  /* ---------------- 历史 / 收藏 ---------------- */
  async function loadHistory(kind, query = '') {
    const fav = kind === 'favorites';
    const res = await api('history_list', query, fav, 200);
    if (!res || !res.ok) { toast((res && res.error) || '加载失败', 'err'); return; }
    state.historyStats = res.stats || state.historyStats;
    renderRecords(kind, res.items || []);
    if (fav) $('#favCount').textContent = `${(res.items || []).length} 条收藏`;
    syncBadges();
  }

  function renderRecords(kind, items) {
    const host = kind === 'favorites' ? $('#favList') : $('#histList');
    if (!items.length) {
      host.innerHTML = `<div class="card"><div class="empty">${ic(kind === 'favorites' ? 'star' : 'clock')}<p>${kind === 'favorites' ? '还没有收藏的翻译' : '还没有翻译记录'}</p></div></div>`;
      return;
    }
    host.innerHTML = items.map((it) => `
      <div class="record" data-id="${esc(it.id)}">
        <div class="record-top">
          <span class="record-langs">${esc(langName(it.source) === '自动检测' ? '自动' : langName(it.source))} → ${esc(langName(it.target))}</span>
          ${it.provider_label ? `<span class="record-provider">${esc(it.provider_label)}</span>` : ''}
          <span class="record-time">${esc(relTime(it.ts))}</span>
        </div>
        <div class="record-text">${esc(it.text)}</div>
        <div class="record-result">${esc(it.result)}</div>
        <div class="record-actions">
          <button class="ghost-btn" data-r-act="load">${ic('translate')}接着翻译</button>
          <button class="ghost-btn" data-r-act="copy">${ic('copy')}复制译文</button>
          <button class="ghost-btn fav ${it.favorite ? 'on' : ''}" data-r-act="fav">${ic('star')}${it.favorite ? '已收藏' : '收藏'}</button>
          <button class="ghost-btn" data-r-act="delete">${ic('trash')}删除</button>
        </div>
      </div>`).join('');

    $$('[data-r-act]', host).forEach((btn) => {
      btn.onclick = async () => {
        const row = btn.closest('[data-id]');
        const id = row.dataset.id;
        const item = items.find((x) => x.id === id);
        const act = btn.dataset.rAct;
        if (act === 'load') return loadRecordIntoTranslate(item);
        if (act === 'copy') return copyText(item.result);
        if (act === 'fav') {
          const res = await api('history_toggle', id);
          if (res.ok) {
            if (res.stats) state.historyStats = res.stats;
            await loadHistory(kind, kind === 'favorites' ? $('#favSearch').value : $('#histSearch').value);
          } else toast(res.error || '操作失败', 'err');
          return;
        }
        if (act === 'delete') {
          const res = await api('history_delete', id);
          if (res.ok) {
            if (res.stats) state.historyStats = res.stats;
            await loadHistory(kind, kind === 'favorites' ? $('#favSearch').value : $('#histSearch').value);
            toast('已删除', 'ok', 1400);
          } else toast(res.error || '删除失败', 'err');
        }
      };
    });
  }

  function bindHistoryPage() {
    $('#histSearch').addEventListener('input', debounce((ev) => loadHistory('history', ev.target.value), 260));
    $('#favSearch').addEventListener('input', debounce((ev) => loadHistory('favorites', ev.target.value), 260));

    $('#histClear').onclick = async () => {
      const ok = await confirmAction({ title: '清空翻译历史？', message: '收藏的内容会保留，其余记录会被删除。', confirm: '清空' });
      if (!ok) return;
      const res = await api('history_clear', true);
      if (res.ok) {
        state.historyStats = res.stats || state.historyStats;
        await loadHistory('history', $('#histSearch').value);
        syncBadges();
        toast('已清空', 'ok');
      } else toast(res.error || '操作失败', 'err');
    };
  }

  /* ---------------- 设置 ---------------- */
  function aiConfigured() {
    const s = state.settings || {};
    return !!(state.ai && state.ai.endpoint && (s.ai_api_key || '').trim());
  }

  function renderAiPresets() {
    const host = $('#aiPresets');
    if (!host) return;
    const list = (state.ai && state.ai.presets) || [];
    host.innerHTML = list
      .map((p) => `<button class="chip" data-ai-preset="${esc(p.id)}" title="${esc(p.note || '')}">${esc(p.name)}</button>`)
      .join('');
    host.querySelectorAll('[data-ai-preset]').forEach((btn) => {
      btn.onclick = () => {
        const preset = list.find((p) => p.id === btn.dataset.aiPreset);
        if (!preset) return;
        $('#aiBase').value = preset.base;
        $('#aiModel').value = preset.model;
        host.querySelectorAll('.chip').forEach((b) => b.classList.toggle('active', b === btn));
        $('#aiResult').textContent = `已填好 ${preset.name}，粘上 Key 再点保存`;
        ($('#aiKey').value ? $('#aiSave') : $('#aiKey')).focus();
      };
    });
  }

  function fillAiCard(force) {
    const s = state.settings || {};
    const ai = state.ai || {};
    const put = (sel, value) => {
      const el = $(sel);
      if (el && (force || !el.value)) el.value = value || '';
    };
    put('#aiBase', ai.base_url || s.ai_base_url);
    put('#aiModel', ai.model || s.ai_model);
    put('#aiKey', s.ai_api_key);
    syncAiState();
  }

  function syncAiState() {
    const tag = $('#aiState');
    if (!tag) return;
    const ready = aiConfigured();
    tag.textContent = ready ? '已就绪' : '未配置';
    tag.classList.toggle('muted', !ready);
    tag.title = ready ? (state.ai.endpoint || '') : '填地址和 Key 后点保存';
  }

  const START_PAGES = [
    ['last', '上次停留的页面'],
    ['home', '概览'],
    ['plan', '每日规划'],
    ['translate', '翻译'],
    ['notes', '记事'],
    ['todo', '待办'],
    ['time', '时间'],
    ['chart', '数据成图'],
    ['mood', '心情日记'],
    ['image', '图片工具'],
  ];

  let setTab = 'look';

  function setSettingsTab(name, silent) {
    if (!name) name = 'look';
    setTab = name;
    $$('#setRail .set-tab').forEach((b) => b.classList.toggle('active', b.dataset.setTab === name));
    $$('.set-pane').forEach((p) => p.classList.toggle('active', p.dataset.setPane === name));
    if (!silent) savePrefs({ settingsTab: name });
    const scroll = $('#scroll');
    if (scroll) scroll.scrollTop = 0;
    if (name === 'data') {
      loadDirs();
      refreshUsage();
    }
    if (name === 'about') {
      loadDiag();
      loadAbout();
    }
  }

  function fillStartPages() {
    const sel = $('#startPage');
    if (!sel || sel.options.length) return;
    sel.innerHTML = START_PAGES.map(([key, label]) => `<option value="${key}">${label}</option>`).join('');
  }

  async function syncAutoStart() {
    if (!$('#autoStartSwitch')) return;
    const res = await api('sys_autostart');
    if (res && res.ok) {
      setSwitch($('#autoStartSwitch'), !!res.enabled);
      const hint = $('#autoStartHint');
      if (hint) hint.textContent = res.enabled ? '已加入开机启动，取消勾选即移除' : '随 Windows 启动，不弹黑窗';
    }
  }

  // ---- v2.6：存储位置（数据目录 / 图片保存目录）----

  async function loadDirs() {
    const res = await api('dirs_info');
    if (!res || !res.ok) return;
    state.dirs = res;

    const setPath = (sel, value) => {
      const el = $(sel);
      if (!el) return;
      el.textContent = value || '—';
      el.title = value || '';
    };
    setPath('#dataPath', res.data_dir);
    setPath('#exportPath', res.export_dir);

    const setBadge = (sel, custom) => {
      const el = $(sel);
      if (!el) return;
      el.textContent = custom ? '自定义' : '默认';
      el.classList.toggle('custom', !!custom);
    };
    setBadge('#dataBadge', res.data_custom);
    setBadge('#exportBadge', res.export_custom);

    const hint = $('#dataHint');
    if (hint) {
      hint.textContent = res.can_move_data
        ? '笔记、待办、设置都存在这里'
        : '程序所在目录不可写，这里改不了';
    }
    const dReset = $('#resetData');
    if (dReset) dReset.hidden = !res.data_custom;
    const eReset = $('#resetExport');
    if (eReset) eReset.hidden = !res.export_custom;
  }

  function restartHint(text) {
    const hint = $('#dataHint');
    if (!hint) return;
    hint.innerHTML = `${text}，重启后生效 <button type="button" class="set-link" id="doRestart">立即重启</button>`;
    const btn = $('#doRestart');
    if (!btn) return;
    btn.onclick = async () => {
      btn.disabled = true;
      btn.textContent = '正在重启…';
      const res = await api('app_restart');
      if (!res || !res.ok) {
        btn.disabled = false;
        btn.textContent = '立即重启';
        toast((res && res.error) || '重启失败', 'err', 4000);
      }
    };
  }

  async function pickFolder(current) {
    const picked = await api('pick_folder', current || '');
    if (!picked || !picked.ok) {
      if (picked && !picked.cancelled) toast(picked.error || '打不开选择框', 'err', 3600);
      return null;
    }
    return picked.path;
  }

  async function moveDataDir() {
    const info = state.dirs || (await api('dirs_info')) || {};
    const target = await pickFolder(info.data_dir);
    if (!target) return;
    const res = await api('data_set_dir', target);
    if (!res || !res.ok) {
      toast((res && res.error) || '切换失败', 'err', 4200);
      return;
    }
    await loadDirs();
    if (!res.restart) {
      toast('已经在用这个目录了', 'info');
      return;
    }
    const extra = res.copied ? `，已搬 ${res.copied} 个文件过去` : '';
    restartHint(`已切换${extra}`);
  }

  async function moveExportDir() {
    const info = state.dirs || (await api('dirs_info')) || {};
    const target = await pickFolder(info.export_dir);
    if (!target) return;
    const res = await api('export_set_dir', target);
    if (!res || !res.ok) {
      toast((res && res.error) || '切换失败', 'err', 4200);
      return;
    }
    await loadDirs();
    toast('图片以后存到这里', 'ok');
  }

  async function refreshUsage() {
    const label = $('#dataUsage');
    const list = $('#usageList');
    if (!label) return;
    label.textContent = '正在统计…';
    if (list) list.innerHTML = '';
    const res = await api('data_stats');
    if (!res || !res.ok) {
      label.textContent = '统计失败';
      return;
    }
    label.textContent = `共 ${fmtBytes(res.total)} · ${res.files} 个文件`;
    label.title = res.dir || '';
    if (!$('#exportPath')) return;
    $('#exportPath').textContent = res.exports_dir || '—';
    $('#exportPath').title = res.exports_dir || '';
    if (list) {
      const chips = (res.rows || []).map((row) => `<span class="usage-chip">${row.name} <b>${fmtBytes(row.size)}</b></span>`);
      chips.push(`<span class="usage-chip">导出 <b>${fmtBytes(res.exports.size)}</b> · ${res.exports.count} 个</span>`);
      list.innerHTML = chips.join('');
    }
  }

  /* ---------------- 关于与更新 ---------------- */

  async function loadAbout() {
    const res = await api('app_about');
    if (!res || !res.ok) return null;
    state.about = res;
    if ($('#appVersion')) $('#appVersion').textContent = res.version;
    if ($('#aboutVersionBadge')) $('#aboutVersionBadge').textContent = `v${res.version}`;
    if ($('#releaseNotes')) {
      $('#releaseNotes').innerHTML = (res.notes || '')
        .split('\n')
        .map((line) => (line.trim() ? `<span class="rn-line">${esc(line)}</span>` : ''))
        .join('');
    }
    return res;
  }

  function tf(key, params) {
    return window.PTI18n ? window.PTI18n.tf(key, params) : key;
  }

  function updateStatus(html, kind) {
    const box = $('#updateStatus');
    if (!box) return;
    box.hidden = false;
    box.className = `update-status ${kind || ''}`.trim();
    box.innerHTML = html;
  }

  function showUpdateFallback(res) {
    const reason = (res && res.error) || tf('feedFailed');
    updateStatus(
      `<b>${esc(reason)}</b><br>${esc(tf('noFeed'))}`
      + '<div class="update-actions">'
      + `<button class="btn" data-upd="page">${esc(tf('openPage'))}</button>`
      + `<button class="btn" data-upd="retry">${esc(tf('retry'))}</button>`
      + '</div>',
      'warn'
    );
    bindUpdateActions();
  }

  function bindUpdateActions() {
    $$('#updateStatus [data-upd]').forEach((btn) => {
      btn.onclick = () => {
        const action = btn.dataset.upd;
        if (action === 'page') {
          api('update_open_page', state.about ? state.about.page : '').then((r) => {
            if (!r || !r.ok) toast((r && r.error) || '打开发布页失败', 'err', 3000);
          });
        }
        if (action === 'retry') runCheckUpdate();
        if (action === 'install') installUpdate(btn.dataset.url || '', btn.dataset.sha || '');
      };
    });
  }

  async function runCheckUpdate() {
    const btn = $('#checkUpdate');
    const label = $('#checkUpdateText');
    if (btn) btn.disabled = true;
    if (label) label.textContent = tr('检查中…');
    updateStatus(esc(tf('checking')), '');

    const res = await api('update_check');
    if (btn) btn.disabled = false;
    if (label) label.textContent = tr('检查更新');

    if (!res || !res.ok) {
      showUpdateFallback(res || {});
      return;
    }
    if (!res.has_update) {
      updateStatus(`<b>${esc(tf('upToDate', { v: res.current }))}</b>`, 'ok');
      return;
    }

    const notes = (res.notes || '').trim();
    const brief = notes
      ? esc(notes.split('\n').slice(0, 4).join('\n')).replace(/\n/g, '<br>')
      : esc(tf('noNotes'));
    updateStatus(
      `<b>${esc(tf('newVersion', { v: res.latest, c: res.current }))}</b><br>${brief}`
      + '<div class="update-actions">'
      + (res.url
        ? `<button class="btn primary" data-upd="install" data-url="${esc(res.url)}" data-sha="${esc(res.sha256 || '')}">${esc(tf('updateNow'))}</button>`
        : '')
      + `<button class="btn" data-upd="page">${esc(tf('openPage'))}</button>`
      + '</div>',
      res.url ? 'ok' : 'warn'
    );
    if (!res.url) {
      updateStatus(
        `<b>${esc(tf('newVersion', { v: res.latest, c: res.current }))}</b><br>${brief}`
        + `<br>${esc(tf('noInstaller'))}`
        + '<div class="update-actions">'
        + `<button class="btn" data-upd="page">${esc(tf('openPage'))}</button>`
        + '</div>',
        'warn'
      );
    }
    bindUpdateActions();
  }

  async function installUpdate(url, sha) {
    const btn = $('#checkUpdate');
    if (btn) btn.disabled = true;
    updateStatus(esc(tf('downloading')), '');

    const res = await api('update_install', url, sha || '');
    if (btn) btn.disabled = false;

    if (!res || !res.ok) {
      updateStatus(`<b>${esc(tf('installFailed'))}</b><br>${esc((res && res.error) || '')}`
        + '<div class="update-actions">'
        + `<button class="btn" data-upd="page">${esc(tf('manual'))}</button>`
        + '</div>', 'err');
      bindUpdateActions();
      return;
    }
    if (res.installed) {
      updateStatus(`<b>${esc(tf('installStarted'))}</b>`, 'ok');
      return;
    }
    const mb = res.size ? (res.size / 1048576).toFixed(1) : '?';
    updateStatus(`<b>${esc(tf('downloaded', { size: mb }))}</b><br>`
      + `<span class="set-note">${esc(res.path || '')}</span>`, 'ok');
  }

  async function loadDiag() {
    const box = $('#diagBox');
    if (!box) return;
    const res = await api('diag_info');
    if (!res || !res.ok) {
      box.innerHTML = `<div class="diag-row"><span>${(res && res.error) || '读取失败'}</span></div>`;
      return;
    }
    box.innerHTML = (res.items || [])
      .map(([name, value]) => `<div class="diag-row"><span>${esc(name)}</span><b>${esc(String(value))}</b></div>`)
      .join('');
    box.dataset.text = res.text || '';
  }

  function syncSettingsUi() {
    const s = state.settings || {};
    const p = prefs();
    $$('#themeSeg button').forEach((b) => b.classList.toggle('active', b.dataset.theme === (p.theme || 'light')));
    $$('#langSeg button').forEach((b) => b.classList.toggle('active', (b.dataset.lang || 'zh') === (p.language || 'zh')));
    setSwitch($('#traySwitch'), p.tray_enabled !== false);
    setSwitch($('#minTraySwitch'), p.minimize_to_tray !== false);
    setSwitch($('#closeTraySwitch'), p.close_to_tray === true);
    $$('#accentRow .sw').forEach((b) => b.classList.toggle('active', b.dataset.accent === (p.accent || 'blue')));
    $$('#densitySeg button').forEach((b) => b.classList.toggle('active', (b.dataset.density || 'normal') === (p.density || 'normal')));
    setSwitch($('#motionSwitch'), p.motion !== 'off');
    setSwitch($('#pinSwitch'), !!s.always_on_top);
    setSwitch($('#setRemind'), s.reminders_enabled !== false);
    setSwitch($('#setAuto'), !!s.auto_translate);
    setSwitch($('#autoToggle'), !!s.auto_translate);
    setSwitch($('#maxSwitch'), !!p.maximized);
    fillStartPages();
    if ($('#startPage')) $('#startPage').value = p.startPage || 'last';
    if ($('#delaySeg')) {
      const current = Number(s.auto_translate_delay) || 900;
      const btns = $$('#delaySeg button');
      let best = btns[0];
      btns.forEach((b) => {
        if (Math.abs(Number(b.dataset.delay) - current) < Math.abs(Number(best.dataset.delay) - current)) best = b;
      });
      btns.forEach((b) => b.classList.toggle('active', b === best));
    }
    if ($('#setProvider')) $('#setProvider').value = s.provider || 'auto';
    if ($('#setTarget')) $('#setTarget').value = s.target_lang || 'zh-Hans';
    if ($('#setLimit')) $('#setLimit').value = s.history_limit || 300;
    if ($('#dataPath')) {
      $('#dataPath').textContent = state.dataDir || '—';
      $('#dataPath').title = state.dataDir || '';
    }
    if ($('#exportPath') && state.exportsDir) {
      $('#exportPath').textContent = state.exportsDir;
      $('#exportPath').title = state.exportsDir;
    }
    if ($('#appVersion')) $('#appVersion').textContent = (state.boot && state.boot.version) || '2.0.0';
    if ($('#provider')) $('#provider').value = s.provider || 'auto';
    if ($('#dstLang')) $('#dstLang').value = s.target_lang || 'zh-Hans';
    if ($('#srcLang')) $('#srcLang').value = s.source_lang || 'auto';
    if ($('#aiBase')) fillAiCard(false);
    if ($('#aiPresets') && !$('#aiPresets').children.length) renderAiPresets();
    syncAutoStart();
  }

  function bindSettingsPage() {
    $$('#setRail .set-tab').forEach((btn) => {
      btn.onclick = () => setSettingsTab(btn.dataset.setTab);
    });

    $$('#langSeg button').forEach((btn) => {
      btn.onclick = () => {
        const next = btn.dataset.lang === 'en' ? 'en' : 'zh';
        savePrefs({ language: next });
        applyPrefs();
        syncSettingsUi();
        route();
        toast(next === 'en' ? 'Language switched to English' : '已切换为中文', 'ok', 1800);
      };
    });
    [['#traySwitch', 'tray_enabled', false],
     ['#minTraySwitch', 'minimize_to_tray', false],
     ['#closeTraySwitch', 'close_to_tray', true]].forEach(([sel, key, defOn]) => {
      if (!$(sel)) return;
      $(sel).onclick = () => {
        const on = !$(sel).classList.contains('on');
        setSwitch($(sel), on);
        savePrefs({ [key]: on });
        const hint = {
          tray_enabled: on ? '托盘图标已显示，重启后生效' : '托盘图标已隐藏，重启后生效',
          minimize_to_tray: on ? '最小化会收进托盘' : '最小化仍留在任务栏',
          close_to_tray: on ? '点关闭会留在托盘' : '点关闭直接退出'
        }[key];
        toast(hint, 'ok', 2000);
        void defOn;
      };
    });
    $$('#themeSeg button').forEach((btn) => {
      btn.onclick = () => {
        savePrefs({ theme: btn.dataset.theme });
        state.settings.theme = btn.dataset.theme;
        saveSetting({ theme: btn.dataset.theme });
        applyPrefs();
        syncSettingsUi();
      };
    });
    $$('#accentRow .sw').forEach((btn) => {
      btn.onclick = () => {
        savePrefs({ accent: btn.dataset.accent });
        applyPrefs();
        syncSettingsUi();
      };
    });
    $$('#densitySeg button').forEach((btn) => {
      btn.onclick = () => {
        savePrefs({ density: btn.dataset.density || 'normal' });
        applyPrefs();
        syncSettingsUi();
      };
    });
    if ($('#motionSwitch')) {
      $('#motionSwitch').onclick = () => {
        const on = $('#motionSwitch').classList.contains('on');
        savePrefs({ motion: on ? 'off' : 'on' });
        applyPrefs();
        syncSettingsUi();
        toast(on ? '界面动效已关闭' : '界面动效已开启', 'ok', 1600);
      };
    }
    if ($('#startPage')) {
      $('#startPage').onchange = () => {
        savePrefs({ startPage: $('#startPage').value });
        const label = START_PAGES.find(([key]) => key === $('#startPage').value);
        toast(`下次打开会进入「${label ? label[1] : '概览'}」`, 'ok', 2000);
      };
    }
    if ($('#maxSwitch')) {
      $('#maxSwitch').onclick = () => {
        const on = !$('#maxSwitch').classList.contains('on');
        setSwitch($('#maxSwitch'), on);
        savePrefs({ maximized: on });
        toast(on ? '下次打开会直接最大化' : '下次打开用上次的窗口大小', 'ok', 2000);
      };
    }
    if ($('#autoStartSwitch')) {
      $('#autoStartSwitch').onclick = async () => {
        const want = !$('#autoStartSwitch').classList.contains('on');
        const res = await api('sys_autostart', want);
        if (res && res.ok) {
          setSwitch($('#autoStartSwitch'), !!res.enabled);
          toast(res.enabled ? '已加入开机启动' : '已取消开机启动', 'ok', 2000);
          const hint = $('#autoStartHint');
          if (hint) hint.textContent = res.enabled ? '已加入开机启动，取消勾选即移除' : '随 Windows 启动，不弹黑窗';
        } else toast((res && res.error) || '设置失败', 'err', 3600);
      };
    }
    $$('#delaySeg button').forEach((btn) => {
      btn.onclick = () => saveSetting({ auto_translate_delay: Number(btn.dataset.delay) || 900 });
    });

    $('#pinSwitch').onclick = async () => {
      const res = await api('window_control', 'pin');
      if (res.ok) {
        state.settings.always_on_top = !!res.pinned;
        setSwitch($('#pinSwitch'), !!res.pinned);
        toast(res.pinned ? '窗口已置顶' : '已取消置顶', 'ok', 1500);
      } else toast(res.error || '操作失败', 'err');
    };

    $('#setProvider').onchange = () => saveSetting({ provider: $('#setProvider').value });
    $('#setTarget').onchange = () => saveSetting({ target_lang: $('#setTarget').value });
    $('#setAuto').onclick = () => {
      const on = !$('#setAuto').classList.contains('on');
      setSwitch($('#setAuto'), on);
      saveSetting({ auto_translate: on });
    };
    $('#setLimit').onchange = () => {
      const value = Math.min(2000, Math.max(20, Number($('#setLimit').value) || 300));
      $('#setLimit').value = value;
      saveSetting({ history_limit: value });
    };
    $('#setRemind').onclick = () => {
      const on = !$('#setRemind').classList.contains('on');
      setSwitch($('#setRemind'), on);
      saveSetting({ reminders_enabled: on }).then(() => toast(on ? '提醒已开启，重启程序后开始生效' : '提醒已关闭，重启程序后生效', 'info', 3000));
    };
    $('#testNotify').onclick = async () => {
      const res = await api('todo_test_notification');
      toast(res.ok ? '已发送，看看屏幕右下角' : (res.error || '通知发送失败'), res.ok ? 'ok' : 'err', 3000);
    };

    $('#testProviders').onclick = async () => {
      const btn = $('#testProviders');
      btn.disabled = true;
      const label = btn.innerHTML;
      btn.innerHTML = `${ic('refresh')}检测中…`;
      $('#probeResult').textContent = '正在逐个测试，可能需要几秒';
      const res = await api('probe');
      btn.disabled = false;
      btn.innerHTML = label;
      if (res.ok && res.results) {
        const okList = res.results.filter((r) => r.ok);
        const total = res.results.length;
        $('#probeResult').textContent = okList.length
          ? `${okList.length}/${total} 可用 · ${okList.map((r) => r.label).join('、')}`
          : '当前网络下没有可用通道';
        $('#probeResult').title = res.results
          .map((r) => (r.ok ? `${r.label} ${r.latency_ms}ms` : `${r.label}：${r.error || '不可用'}`))
          .join('\n');
        toast(okList.length ? `${okList.length} 条通道可用` : '没有可用通道', okList.length ? 'ok' : 'err', 3200);
      } else {
        $('#probeResult').textContent = '检测失败';
        toast((res && res.error) || '检测失败', 'err');
      }
    };

    if ($('#aiSave')) {
      $('#aiSave').onclick = async () => {
        const base = $('#aiBase').value.trim();
        const key = $('#aiKey').value.trim();
        const model = $('#aiModel').value.trim() || 'gpt-4o-mini';
        if (!base) {
          toast('先填接口地址', 'err');
          $('#aiBase').focus();
          return;
        }
        if (!key) {
          toast('先填 API Key', 'err');
          $('#aiKey').focus();
          return;
        }
        const btn = $('#aiSave');
        btn.disabled = true;
        const label = btn.innerHTML;
        btn.innerHTML = `${ic('refresh')}测试中…`;
        $('#aiResult').textContent = '正在请求模型，可能要几秒';
        const saved = await api('save_settings', { ai_base_url: base, ai_api_key: key, ai_model: model });
        if (saved && saved.settings) state.settings = saved.settings;
        const res = await api('ai_test');
        btn.disabled = false;
        btn.innerHTML = label;
        if (res && res.ok) {
          state.ai = Object.assign({}, state.ai, {
            ready: true, endpoint: res.endpoint, model: res.model, base_url: base, has_key: true,
          });
          $('#aiResult').textContent = `${res.elapsed_ms}ms · ${res.text}`;
          toast('AI 接口已连通', 'ok', 2600);
        } else {
          state.ai = Object.assign({}, state.ai, { ready: false });
          $('#aiResult').textContent = (res && res.error) || '测试失败';
          toast((res && res.error) || '测试失败', 'err', 5000);
        }
        syncAiState();
      };

      $('#aiClear').onclick = async () => {
        const ok = await confirmAction({
          title: '清空 AI 配置？',
          message: '地址和 Key 会被清掉，翻译仍然可以用内置渠道。',
          confirm: '清空',
        });
        if (!ok) return;
        const saved = await api('save_settings', { ai_base_url: '', ai_api_key: '', ai_model: '' });
        if (saved && saved.settings) state.settings = saved.settings;
        state.ai = Object.assign({}, state.ai, { ready: false, endpoint: '', has_key: false, base_url: '', model: '' });
        ['#aiBase', '#aiKey', '#aiModel'].forEach((sel) => { if ($(sel)) $(sel).value = ''; });
        $('#aiResult').textContent = '';
        syncAiState();
        toast('已清空', 'ok');
      };

      ['#aiBase', '#aiKey', '#aiModel'].forEach((sel) => {
        const el = $(sel);
        if (el) {
          el.oninput = () => {
            const out = $('#aiResult');
            if (out) out.textContent = '';
          };
        }
      });
    }

    $('#openData').onclick = async () => {
      const res = await api('open_data_dir');
      if (!res.ok) toast(res.error || '打开失败', 'err');
    };
    if ($('#moveData')) $('#moveData').onclick = () => moveDataDir();
    if ($('#moveExport')) $('#moveExport').onclick = () => moveExportDir();
    if ($('#resetData')) {
      $('#resetData').onclick = async () => {
        const res = await api('data_reset_dir');
        if (!res || !res.ok) return toast((res && res.error) || '恢复失败', 'err', 3600);
        await loadDirs();
        if (res.restart) restartHint('已恢复默认位置');
      };
    }
    if ($('#resetExport')) {
      $('#resetExport').onclick = async () => {
        const res = await api('export_reset_dir');
        if (!res || !res.ok) return toast((res && res.error) || '恢复失败', 'err', 3600);
        await loadDirs();
        toast('图片保存目录已恢复默认', 'ok');
      };
    }
    if ($('#openExports')) {
      $('#openExports').onclick = async () => {
        const res = await api('open_exports');
        if (!res.ok) toast(res.error || '打开失败', 'err');
      };
    }
    if ($('#refreshUsage')) $('#refreshUsage').onclick = () => refreshUsage();
    if ($('#backupData')) {
      $('#backupData').onclick = async () => {
        const btn = $('#backupData');
        btn.disabled = true;
        const res = await api('data_backup');
        btn.disabled = false;
        if (res && res.ok) toast(`已备份 ${res.count} 个文件到 data\\backup`, 'ok', 3200);
        else toast((res && res.error) || '备份失败', 'err', 3600);
      };
    }
    if ($('#checkUpdate')) {
      $('#checkUpdate').onclick = () => runCheckUpdate();
    }
    if ($('#openGuide')) {
      $('#openGuide').onclick = async () => {
        const res = await api('open_guide');
        if (!res.ok) toast(res.error || '打开失败', 'err', 3200);
      };
    }
    if ($('#copyDiag')) {
      $('#copyDiag').onclick = async () => {
        const text = ($('#diagBox') && $('#diagBox').dataset.text) || '';
        if (!text) {
          toast('信息还没读出来，稍等一下', 'info');
          return;
        }
        await copyText(text);
        toast('诊断信息已复制', 'ok', 1800);
      };
    }

    $('#clearHistory').onclick = async () => {
      const ok = await confirmAction({ title: '清空翻译历史？', message: '收藏的内容会保留。', confirm: '清空' });
      if (!ok) return;
      const res = await api('history_clear', true);
      if (res.ok) {
        state.historyStats = res.stats || state.historyStats;
        syncBadges();
        toast('已清空', 'ok');
        refreshUsage();
      } else toast(res.error || '操作失败', 'err');
    };
    $('#resetSettings').onclick = async () => {
      const ok = await confirmAction({ title: '恢复默认设置？', message: '只重置翻译、提醒等设置，不会删除笔记、待办和历史。', confirm: '恢复默认' });
      if (!ok) return;
      const res = await api('reset_settings');
      if (res.ok) {
        state.settings = res.settings || {};
        syncTranslateSettings();
        syncSettingsUi();
        toast('已恢复默认设置', 'ok');
      } else toast(res.error || '操作失败', 'err');
    };
  }

  /* ---------------- 启动 ---------------- */
  function init() {
    bindTranslatePage();
    bindNotesPage();
    bindTodoPage();
    bindUnitsPage();
    bindPickerPage();
    bindHistoryPage();
    bindSettingsPage();
    bindPlanPage();
    bindTimePage();
    bindMoodPage();
    bindChartPage();
    bindImagePage();
    bindCommandPalette();

    window.addEventListener('keydown', (ev) => {
      if (ev.key === 'Escape') {
        if (state.cmd.open) { cmdClose(); return; }
        if (!$('#modalRoot').classList.contains('open')) {
          if (document.activeElement && document.activeElement.tagName === 'INPUT') document.activeElement.blur();
        }
      }
    });

    $('#srcText').addEventListener('input', onTranslateInput);

    boot();
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init);
  else init();
})();
