// AI Radar 대시보드 (Vanilla JS). 서버 시각 기준 60초 카운트다운 + 5초 폴링.
const INTERVAL = 60;
const SOURCE_LABEL = { kakaotalk: '카톡', github: 'GitHub', hn: 'HN' };
const TABS = [['', '전체'], ['kakaotalk', '카카오톡'], ['github', 'GitHub'], ['hn', 'Hacker News']];

const TOP_SCORE = 10; // 핵심 추천글 기준 점수
// scope: 'top' = 10점 이상 추천글(기본), 'all' = 낮은 점수 포함 전체
let state = { source: '', scope: 'top', nextRunAt: null, offsetMs: 0, refreshing: false };
const $ = (id) => document.getElementById(id);

function el(tag, cls, text) {
  const e = document.createElement(tag);
  if (cls) e.className = cls;
  if (text !== undefined) e.textContent = text;
  return e;
}

function relTime(iso) {
  if (!iso) return '';
  const diff = Math.max(0, (Date.now() + state.offsetMs - new Date(iso).getTime()) / 1000);
  if (diff < 60) return `${Math.floor(diff)}초 전`;
  if (diff < 3600) return `${Math.floor(diff / 60)}분 전`;
  if (diff < 86400) return `${Math.floor(diff / 3600)}시간 전`;
  return `${Math.floor(diff / 86400)}일 전`;
}

function showBanner(msg) {
  const b = $('banner');
  if (msg) { b.textContent = msg; b.classList.remove('hidden'); } else { b.classList.add('hidden'); }
}

async function getJSON(url) {
  const r = await fetch(url);
  if (!r.ok) throw new Error(`${url} → HTTP ${r.status}`);
  return r.json();
}

function badge(source) {
  // 카카오톡은 노란색 배지(#FEE500), 나머지는 회색 톤
  const base = 'inline-block text-xs font-semibold px-2 py-0.5 rounded-full shrink-0 ';
  if (source === 'kakaotalk') {
    const b = el('span', base, '카톡');
    b.style.background = '#FEE500'; b.style.color = '#191919';
    return b;
  }
  const colors = { github: 'bg-slate-800 text-white dark:bg-slate-200 dark:text-slate-900', hn: 'bg-orange-500 text-white' };
  return el('span', base + (colors[source] || 'bg-slate-300 text-slate-800'), SOURCE_LABEL[source] || source);
}

function safeUrl(u) {
  return /^https?:\/\//i.test(u || '') ? u : null;
}

function makeTextWithLinks(text) {
  const container = document.createDocumentFragment();
  const urlRegex = /(https?:\/\/[^\s]+)/g;
  let lastIdx = 0;
  let match;
  while ((match = urlRegex.exec(text)) !== null) {
    if (match.index > lastIdx) {
      container.append(document.createTextNode(text.substring(lastIdx, match.index)));
    }
    const a = document.createElement('a');
    a.href = match[0];
    a.target = '_blank';
    a.rel = 'noopener noreferrer';
    a.className = 'text-indigo-600 dark:text-indigo-400 hover:underline break-all font-medium';
    a.textContent = match[0];
    container.append(a);
    lastIdx = urlRegex.lastIndex;
  }
  if (lastIdx < text.length) {
    container.append(document.createTextNode(text.substring(lastIdx)));
  }
  return container;
}

function renderFeed(items) {
  const ul = $('feed');
  ul.replaceChildren();
  if (!items.length) {
    const msg = state.scope === 'top' ? `${TOP_SCORE}점 이상 추천글이 아직 없습니다. '전체 글 보기'를 눌러 보세요.` : '아직 수집된 항목이 없습니다.';
    ul.append(el('li', 'p-6 text-center text-slate-400 text-sm', msg));
    return;
  }
  for (const it of items) {
    const li = el('li', 'p-4 flex gap-3 items-start hover:bg-slate-50 dark:hover:bg-slate-700/40');
    li.append(badge(it.source));
    const body = el('div', 'min-w-0 flex-1');
    const url = safeUrl(it.url);
    const title = url ? el('a', 'font-medium hover:underline break-words', it.title) : el('p', 'font-medium break-words', it.title);
    if (url) { title.href = url; title.target = '_blank'; title.rel = 'noopener noreferrer'; }
    body.append(title);

    // 번역이 실패했거나 원문과 같으면(중복) 한글 요약 상자를 만들지 않는다
    const ko = (it.summary_ko || '').trim();
    if (ko && ko !== (it.summary || '').trim() && ko !== it.title) {
      const koBox = el('div', 'mt-1.5 px-3 py-2 bg-indigo-50 dark:bg-indigo-950/50 rounded-lg border-l-4 border-indigo-500 text-sm text-slate-800 dark:text-indigo-100 leading-relaxed');
      koBox.append(el('span', 'font-bold text-indigo-600 dark:text-indigo-300 mr-1.5', '🇰🇷 한글 요약:'), document.createTextNode(ko));
      body.append(koBox);
    }

    // 본문 내용 (카톡 글이나 긴 글은 '전체 보기' 토글 및 링크 클릭 지원)
    const contentText = (it.summary || '').trim();
    if (contentText && contentText !== it.title) {
      const p = el('div', 'text-sm text-slate-600 dark:text-slate-300 mt-1 whitespace-pre-wrap leading-relaxed');
      const isLong = contentText.length > 70 || contentText.includes('\n') || it.source === 'kakaotalk';
      if (isLong) {
        p.classList.add('line-clamp-2');
        p.append(makeTextWithLinks(contentText));
        body.append(p);

        const toggleBtn = el('button', 'text-xs text-indigo-600 dark:text-indigo-400 hover:underline font-semibold mt-1 inline-flex items-center gap-1', '전체 보기 ▼');
        toggleBtn.type = 'button';
        toggleBtn.onclick = (e) => {
          e.preventDefault();
          if (p.classList.contains('line-clamp-2')) {
            p.classList.remove('line-clamp-2');
            toggleBtn.textContent = '간략히 접기 ▲';
          } else {
            p.classList.add('line-clamp-2');
            toggleBtn.textContent = '전체 보기 ▼';
          }
        };
        body.append(toggleBtn);
      } else {
        p.append(makeTextWithLinks(contentText));
        body.append(p);
      }
    }

    const meta = [];
    if (it.room) meta.push(it.room);
    if (it.author) meta.push(it.author);
    if (it.stars) meta.push(`★ ${it.stars}`);
    meta.push(relTime(it.first_seen_at));
    body.append(el('p', 'text-xs text-slate-400 mt-1', meta.join(' · ')));
    li.append(body, el('span', 'text-xs font-semibold text-indigo-600 dark:text-indigo-300 shrink-0', `${it.score}점`));
    ul.append(li);
  }
}

function renderRuns(runs) {
  const tb = $('runs');
  tb.replaceChildren();
  for (const r of runs.slice(0, 20)) {
    const tr = el('tr', r.status === 'error' ? 'bg-red-50 text-red-700 dark:bg-red-900/30 dark:text-red-300' : '');
    const t = new Date(r.started_at).toLocaleTimeString('ko-KR');
    for (const [v, cls] of [[t, ''], [r.source, ''], [r.fetched, 'text-right'], [r.inserted, 'text-right'], [r.status === 'ok' ? '✅ ok' : '❌ error', ''], [r.error || '', 'max-w-xs truncate']]) {
      tr.append(el('td', `px-4 py-2 ${cls}`, String(v)));
    }
    tb.append(tr);
  }
}

function renderStats(s, h) {
  $('card-new').textContent = s.new_24h;
  $('card-total').textContent = s.total;
  $('card-sources').textContent = Object.entries(s.by_source).map(([k, v]) => `${SOURCE_LABEL[k] || k} ${v}`).join(' · ') || ' ';
  $('card-rate').textContent = s.success_rate === null ? '-' : `${s.success_rate}%`;
  $('card-slack').textContent = `Slack 오늘 ${s.slack_sent_today}/${s.slack_daily_limit}건`;
  const fails = Object.values(h.sources).reduce((a, x) => a + x.consecutive_failures, 0);
  $('card-status').textContent = h.scheduler_running ? (fails ? '🟠 일부 실패' : '🟢 정상') : '🔴 중지됨';
  $('card-status-sub').textContent = fails ? '수집 로그의 오류를 확인하세요' : '60초마다 자동 수집';
}

function renderTabs() {
  const box = $('tabs');
  box.replaceChildren();
  for (const [key, label] of TABS) {
    const active = state.source === key;
    const b = el('button', 'px-3 py-1 rounded-full ' + (active ? 'bg-indigo-600 text-white' : 'bg-slate-100 dark:bg-slate-700 hover:bg-slate-200 dark:hover:bg-slate-600'), label);
    b.addEventListener('click', () => { state.source = key; renderTabs(); refresh(); });
    box.append(b);
  }
}

function renderScope() {
  const box = $('scope');
  box.replaceChildren();
  for (const [key, label] of [['top', `⭐ ${TOP_SCORE}점 이상 추천글`], ['all', '📜 전체 글 보기 (낮은 점수 포함)']]) {
    const active = state.scope === key;
    const b = el('button', 'px-3 py-1 rounded-lg border ' + (active ? 'bg-indigo-600 border-indigo-600 text-white font-semibold' : 'border-slate-300 dark:border-slate-600 hover:bg-slate-100 dark:hover:bg-slate-700'), label);
    b.setAttribute('aria-pressed', String(active));
    b.addEventListener('click', () => { state.scope = key; renderScope(); refresh(); });
    box.append(b);
  }
}

async function refresh() {
  if (state.refreshing) return;
  state.refreshing = true;
  try {
    const q = (state.source ? `&source=${encodeURIComponent(state.source)}` : '')
      + (state.scope === 'top' ? `&min_score=${TOP_SCORE}` : '');
    const [health, stats, items, runs] = await Promise.all([
      getJSON('/api/health'), getJSON('/api/stats'), getJSON(`/api/items?limit=50${q}`), getJSON('/api/runs?limit=20'),
    ]);
    state.offsetMs = new Date(health.server_time).getTime() - Date.now();
    state.nextRunAt = health.next_run_at ? new Date(health.next_run_at).getTime() : null;
    renderStats(stats, health); renderFeed(items); renderRuns(runs);
    const failing = Object.entries(health.sources).filter(([, v]) => v.consecutive_failures >= 1);
    showBanner(failing.length ? `⚠ 수집 오류: ${failing.map(([k, v]) => `${k} (연속 ${v.consecutive_failures}회)`).join(', ')}` : '');
  } catch (e) {
    showBanner(`⚠ 서버에 연결할 수 없습니다. (${e.message})`);
  } finally {
    state.refreshing = false;
  }
}

function tick() {
  $('clock').textContent = new Date().toLocaleString('ko-KR');
  if (!state.nextRunAt) { $('countdown').textContent = '--'; return; }
  const remain = Math.ceil((state.nextRunAt - (Date.now() + state.offsetMs)) / 1000);
  $('countdown').textContent = Math.max(remain, 0);
  $('gauge').style.width = `${Math.min(Math.max(remain, 0) / INTERVAL, 1) * 100}%`;
  if (remain <= -2) refresh(); // 수집 직후 새 next_run_at 과 데이터를 다시 받는다
}

renderScope();
renderTabs();
refresh();
setInterval(refresh, 5000);
setInterval(tick, 1000);
tick();
