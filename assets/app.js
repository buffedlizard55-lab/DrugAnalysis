/* =====================================================================
   DrugAnalysis — site logic (dependency-free, no build step)

   Contents
     1. CSV parsing / loading
     2. Cell formatters (badges, % moves, scores, links)
     3. DataTable component  — sticky header, sticky first column,
        SYNCED TOP + BOTTOM horizontal scrollbars, sortable columns,
        column show/hide, density, paging, click-to-expand full row,
        CSV export of the current view
     4. Views: Overview, Core Analysis, FDA Approvals (US-investable),
        Private & Non-US, CRLs, Price Snapshots, Scorecards,
        Decision Engine
   ===================================================================== */

/* ----------------------------- 1. CSV ----------------------------- */

function parseCSV(text) {
  const rows = [];
  let row = [], field = "", inQuotes = false;
  for (let i = 0; i < text.length; i++) {
    const c = text[i];
    if (inQuotes) {
      if (c === '"') {
        if (text[i + 1] === '"') { field += '"'; i++; } else { inQuotes = false; }
      } else field += c;
    } else {
      if (c === '"') inQuotes = true;
      else if (c === ',') { row.push(field); field = ""; }
      else if (c === '\r') { /* skip */ }
      else if (c === '\n') { row.push(field); rows.push(row); row = []; field = ""; }
      else field += c;
    }
  }
  if (field.length || row.length) { row.push(field); rows.push(row); }
  if (!rows.length) return { header: [], records: [] };
  const header = rows[0];
  const records = rows.slice(1)
    .filter(r => r.length === header.length && r.some(v => v !== ""))
    .map(r => { const o = {}; header.forEach((h, i) => o[h] = r[i]); return o; });
  return { header, records };
}

async function loadCSV(path) {
  const res = await fetch(path, { cache: 'no-store' });
  if (!res.ok) throw new Error(path + ' → HTTP ' + res.status);
  return parseCSV(await res.text());
}

/* --------------------------- 2. Formatters --------------------------- */

function escapeHtml(s) {
  if (s === undefined || s === null) return "";
  return String(s).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
}

function linkify(url, label) {
  if (!url) return '<span class="badge neutral">no link</span>';
  return `<a href="${escapeHtml(url)}" target="_blank" rel="noopener noreferrer">${escapeHtml(label || 'source')}</a>`;
}

function statusBadge(status) {
  if (!status) return '<span class="badge neutral">—</span>';
  const s = status.toLowerCase();
  /* Verification-audit statuses (data/verification_crosscheck.csv). A true
     source-vs-source conflict must read as a warning; a confirmed match must
     read as verified; "could not be machine-checked" must read as neither. */
  if (s.startsWith('mismatch')) return `<span class="badge flagged">${escapeHtml(status)}</span>`;
  if (s.startsWith('match')) return `<span class="badge verified">${escapeHtml(status)}</span>`;
  if (s.startsWith('date_differs')) return `<span class="badge info">${escapeHtml(status)}</span>`;
  if (s === 'no_appl_number' || s === 'not_in_openfda')
    return `<span class="badge caveat">${escapeHtml(status)}</span>`;
  if (s.includes('flag') || s.includes('irregular') || s.includes('correction') || s.includes('rejected'))
    return `<span class="badge flagged">${escapeHtml(status)}</span>`;
  if (s.includes('caveat') || s.includes('foreign') || s.includes('no public') || s.includes('private') ||
      s.includes('unavailable') || s.includes('partial') || s.includes('incomplete') || s.includes('pending') ||
      s.includes('not captured') || s.includes('no us'))
    return `<span class="badge caveat">${escapeHtml(status)}</span>`;
  if (s.includes('verified')) return `<span class="badge verified">${escapeHtml(status)}</span>`;
  return `<span class="badge neutral">${escapeHtml(status)}</span>`;
}

function classBadge(cls) {
  if (!cls) return '<span class="badge neutral">unclassified</span>';
  const c = cls.toUpperCase();
  let kind = 'neutral';
  if (c.startsWith('US-LISTED') || c.startsWith('US LISTED')) kind = 'verified';
  else if (c.includes('ADR')) kind = 'info';
  else if (c.includes('DELIST') || c.includes('FORMERLY')) kind = 'caveat';
  else if (c.includes('PRIVATE') || c.includes('NON-US') || c.includes('NOT US-INVESTABLE')) kind = 'flagged';
  return `<span class="badge ${kind}">${escapeHtml(cls)}</span>`;
}

function pctCell(v) {
  if (v === undefined || v === null || v === "") return '<span class="badge neutral">n/a</span>';
  const num = parseFloat(v);
  if (isNaN(num)) return escapeHtml(v);
  const cls = num > 0 ? "pct-pos" : (num < 0 ? "pct-neg" : "pct-zero");
  return `<span class="${cls}">${num > 0 ? "+" : ""}${num.toFixed(2)}%</span>`;
}

function num(v, dp) {
  if (v === undefined || v === null || v === "") return '<span class="badge neutral">n/a</span>';
  const n = parseFloat(v);
  if (isNaN(n)) return escapeHtml(v);
  return `<span class="num-strong">${n.toFixed(dp === undefined ? 1 : dp)}</span>`;
}

function gradeBadge(g) {
  const letter = (g || 'N').charAt(0).toUpperCase();
  const known = ['A', 'B', 'C', 'D', 'E'].includes(letter) ? letter : 'N';
  return `<span class="grade grade-${known}">${escapeHtml(g || 'n/a')}</span>`;
}

function scorePill(score, grade) {
  const s = parseFloat(score);
  if (isNaN(s)) return '<span class="badge neutral">not scored</span>';
  const pct = Math.max(0, Math.min(100, s));
  const colour = pct >= 80 ? '#12784a' : pct >= 65 ? '#2f6fed' : pct >= 50 ? '#c08a10' : pct >= 35 ? '#c25a2c' : '#7a3f8c';
  return `<span class="score-pill"><span class="num-strong">${s.toFixed(1)}</span>` +
         `<span class="score-bar"><i style="width:${pct}%;background:${colour}"></i></span>${gradeBadge(grade)}</span>`;
}

function truncCell(text, chars) {
  if (!text) return "";
  const limit = chars || 110;
  const t = String(text);
  const clipped = t.length > limit ? t.slice(0, limit).replace(/\s+\S*$/, '') + '…' : t;
  return `<span class="clip" title="Click the row to expand full text">${escapeHtml(clipped)}</span>`;
}

/* --------------------------- 3. DataTable --------------------------- */

const LS = {
  get(k, d) { try { const v = localStorage.getItem(k); return v === null ? d : JSON.parse(v); } catch (e) { return d; } },
  set(k, v) { try { localStorage.setItem(k, JSON.stringify(v)); } catch (e) { /* private mode */ } }
};

/* Dark mode: honour prefers-color-scheme, remember the last explicit choice. */
(function initTheme() {
  const stored = LS.get('theme', null);
  const prefersDark = window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches;
  const theme = stored || (prefersDark ? 'dark' : 'light');
  document.documentElement.setAttribute('data-theme', theme);
  window.addEventListener('DOMContentLoaded', () => {
    const btn = document.getElementById('theme-toggle');
    if (!btn) return;
    const sync = () => {
      const t = document.documentElement.getAttribute('data-theme') || 'light';
      btn.textContent = t === 'dark' ? '☀' : '◐';
      btn.setAttribute('aria-label', t === 'dark' ? 'Switch to light mode' : 'Switch to dark mode');
    };
    sync();
    btn.addEventListener('click', () => {
      const next = document.documentElement.getAttribute('data-theme') === 'dark' ? 'light' : 'dark';
      document.documentElement.setAttribute('data-theme', next);
      LS.set('theme', next);
      sync();
    });
  });
})();

function smartCompare(a, b) {
  const na = parseFloat(a), nb = parseFloat(b);
  const aNum = a !== '' && !isNaN(na), bNum = b !== '' && !isNaN(nb);
  if (aNum && bNum) return na - nb;
  if (aNum && !bNum) return -1;      // numbers sort before blanks/text
  if (!aNum && bNum) return 1;
  return String(a || '').localeCompare(String(b || ''), 'en', { numeric: true, sensitivity: 'base' });
}

/**
 * cfg = {
 *   id, mount (selector), csv, columns, searchFields, sort {key,dir},
 *   baseFilter(row)->bool, filters [{key,label,field,options?|valuesFrom,match(row,val)}],
 *   pageSize, hideColumns:true|false, note (html)
 * }
 * column = { key, label, field, render(row), detail(row), sticky, num, trunc, sortValue(row), hidden }
 */
function DataTable(cfg) {
  const state = {
    records: [], rows: [], page: 0, sort: Object.assign({ key: cfg.sort.key, dir: cfg.sort.dir }, {}),
    q: '', filters: {}, hidden: new Set(LS.get('dt:' + cfg.id + ':hidden', [])),
    pageSize: LS.get('dt:' + cfg.id + ':size', cfg.pageSize || 50),
    compact: LS.get('dt:' + cfg.id + ':compact', false),
    expanded: null, loading: true, error: null
  };

  const mount = document.querySelector(cfg.mount);
  mount.innerHTML = `
    <div class="table-controls">
      <input type="search" id="${cfg.id}-q" placeholder="${escapeHtml(cfg.searchPlaceholder || 'Search…')}" aria-label="Search table">
      <span class="filter-slot"></span>
      <select id="${cfg.id}-size" aria-label="Rows per page">
        ${[25, 50, 100, 250].map(n => `<option value="${n}" ${state.pageSize === n ? 'selected' : ''}>${n} rows</option>`).join('')}
        <option value="0" ${state.pageSize === 0 ? 'selected' : ''}>All rows</option>
      </select>
      <button type="button" class="btn" id="${cfg.id}-allrows" title="Show every filtered row in one scrollable table">Show all rows</button>
      ${cfg.hideColumns === false ? '' : `<details class="colmenu" id="${cfg.id}-colmenu">
        <summary>Columns ⚙</summary>
        <div class="colmenu-panel">
          <div class="colmenu-actions"><button type="button" data-act="all">Show all</button><button type="button" data-act="core">Key columns</button></div>
          <div class="colmenu-list"></div>
        </div></details>`}
      <button type="button" class="btn" id="${cfg.id}-density" title="Toggle row height">Density</button>
      <button type="button" class="btn" id="${cfg.id}-expand-text" title="Show full text in cells instead of clipping">Full text</button>
      <button type="button" class="btn" id="${cfg.id}-export" title="Download the currently filtered rows as CSV">Export CSV</button>
      <span class="row-count" id="${cfg.id}-count"></span>
    </div>
    ${cfg.note || ''}
    <div class="hscroll hscroll-top" id="${cfg.id}-topscroll" role="region" tabindex="0" aria-label="Horizontal column navigator"><div class="hscroll-inner"></div></div>
    <p class="hscroll-hint" id="${cfg.id}-hint"></p>
    <div class="table-scroll" id="${cfg.id}-scroll">
      <table class="data-table" id="${cfg.id}-table"><thead></thead><tbody></tbody></table>
    </div>
    <div class="pager" id="${cfg.id}-pager"></div>`;

  const el = id => document.getElementById(cfg.id + '-' + id);
  const table = el('table'), scrollBox = el('scroll'), topScroll = el('topscroll'),
        topInner = topScroll.querySelector('.hscroll-inner'), hint = el('hint');

  /* ---- filters ---- */
  const filterSlot = mount.querySelector('.filter-slot');
  (cfg.filters || []).forEach(f => {
    const sel = document.createElement('select');
    sel.id = cfg.id + '-f-' + f.key;
    sel.setAttribute('aria-label', f.label);
    sel.dataset.fkey = f.key;
    sel.innerHTML = `<option value="">${escapeHtml(f.label)}</option>`;
    filterSlot.appendChild(sel);
  });

  function populateFilterOptions() {
    (cfg.filters || []).forEach(f => {
      const sel = document.getElementById(cfg.id + '-f-' + f.key);
      const opts = f.options ? f.options()
        : [...new Set(state.records.map(f.valuesFrom || (r => r[f.field])).filter(v => v !== '' && v !== undefined))].sort();
      opts.forEach(o => {
        const val = typeof o === 'object' ? o.value : o, lab = typeof o === 'object' ? o.label : o;
        const opt = document.createElement('option');
        opt.value = val; opt.textContent = lab;
        sel.appendChild(opt);
      });
      sel.addEventListener('change', () => { state.filters[f.key] = sel.value; state.page = 0; draw(); });
    });
  }

  /* ---- column visibility menu ---- */
  if (cfg.hideColumns !== false) {
    const list = mount.querySelector('.colmenu-list');
    list.innerHTML = cfg.columns.map((c, i) => `
      <label><input type="checkbox" data-ci="${i}" ${state.hidden.has(c.key) ? '' : 'checked'}> ${escapeHtml(c.label)}</label>`).join('');
    list.addEventListener('change', e => {
      const c = cfg.columns[+e.target.dataset.ci];
      if (e.target.checked) state.hidden.delete(c.key); else state.hidden.add(c.key);
      LS.set('dt:' + cfg.id + ':hidden', [...state.hidden]);
      draw();
    });
    const menu = el('colmenu');
    menu.querySelector('[data-act="all"]').addEventListener('click', () => {
      state.hidden.clear(); LS.set('dt:' + cfg.id + ':hidden', []); syncMenu(); draw();
    });
    menu.querySelector('[data-act="core"]').addEventListener('click', () => {
      state.hidden = new Set(cfg.columns.filter(c => !c.core).map(c => c.key));
      LS.set('dt:' + cfg.id + ':hidden', [...state.hidden]); syncMenu(); draw();
    });
    document.addEventListener('click', e => { if (!menu.contains(e.target)) menu.open = false; });
    var syncMenu = () => list.querySelectorAll('input').forEach(inp => {
      inp.checked = !state.hidden.has(cfg.columns[+inp.dataset.ci].key);
    });
  }

  /* ---- visible columns ---- */
  const visCols = () => cfg.columns.filter(c => !state.hidden.has(c.key));

  /* ---- filtering + sorting ---- */
  function computeRows() {
    let rows = state.records;
    if (cfg.baseFilter) rows = rows.filter(cfg.baseFilter);
    if (state.q) {
      const q = state.q.toLowerCase();
      rows = rows.filter(r => cfg.searchFields.some(f => String(r[f] || '').toLowerCase().includes(q)));
    }
    (cfg.filters || []).forEach(f => {
      const v = state.filters[f.key];
      if (!v) return;
      rows = rows.filter(r => f.match ? f.match(r, v) : String((f.valuesFrom || (x => x[f.field]))(r) || '') === String(v));
    });
    const col = cfg.columns.find(c => c.key === state.sort.key);
    const val = r => col && col.sortValue ? col.sortValue(r) : (col ? (r[col.field !== undefined ? col.field : col.key] || '') : '');
    rows = rows.slice().sort((a, b) => {
      const d = smartCompare(val(a), val(b));
      return state.sort.dir === 'asc' ? d : -d;
    });
    return rows;
  }

  /* ---- header ---- */
  function drawHead(cols) {
    table.querySelector('thead').innerHTML = '<tr>' + cols.map((c, i) => {
      const ind = state.sort.key === c.key ? `<span class="sort-ind">${state.sort.dir === 'asc' ? '▲' : '▼'}</span>` : '';
      return `<th data-key="${escapeHtml(c.key)}" class="${c.num ? 'num ' : ''}${i === 0 ? 'sticky-col' : ''}" ` +
             `title="Sort by ${escapeHtml(c.label)}">${escapeHtml(c.label)}${ind}</th>`;
    }).join('') + '</tr>';
    table.querySelectorAll('thead th').forEach(th => {
      th.addEventListener('click', () => {
        const k = th.dataset.key;
        if (state.sort.key === k) state.sort.dir = state.sort.dir === 'asc' ? 'desc' : 'asc';
        else { state.sort.key = k; state.sort.dir = 'desc'; }
        draw();
      });
    });
  }

  /* ---- body ---- */
  function drawBody(cols, pageRows) {
    const tb = table.querySelector('tbody');
    if (!pageRows.length) {
      tb.innerHTML = `<tr><td colspan="${cols.length}" class="empty-note">No rows match the current search / filters.</td></tr>`;
      return;
    }
    tb.innerHTML = pageRows.map((r, i) => {
      const rid = state.rows.indexOf(r);
      const cells = cols.map((c, ci) => {
        const cls = [c.num ? 'num' : '', ci === 0 ? 'sticky-col' : '', c.trunc ? 'trunc' : ''].filter(Boolean).join(' ');
        return `<td class="${cls}">${ci === 0 ? '<span class="caret">▶</span> ' : ''}${c.render(r)}</td>`;
      }).join('');
      const isExp = state.expanded === rid;
      let html = `<tr class="data-row ${isExp ? 'expanded' : ''}" data-rid="${rid}">${cells}</tr>`;
      if (isExp) html += `<tr class="detail-row"><td colspan="${cols.length}"><div class="detail-inner">${detailHtml(r)}</div></td></tr>`;
      return html;
    }).join('');
    tb.querySelectorAll('tr.data-row').forEach(tr => {
      tr.addEventListener('click', e => {
        if (e.target.closest('a')) return;
        const rid = +tr.dataset.rid;
        state.expanded = state.expanded === rid ? null : rid;
        drawBody(cols, currentPageRows());
      });
    });
  }

  function detailHtml(r) {
    const items = cfg.columns.map(c => {
      const raw = c.detail ? c.detail(r) : (r[c.field !== undefined ? c.field : c.key] || '');
      const long = String(raw).length > 120;
      return `<div class="detail-item ${long ? 'full' : ''}"><span class="k">${escapeHtml(c.label)}</span>` +
             `<span class="v">${String(raw).startsWith('http') ? linkify(raw, raw) : escapeHtml(String(raw || '—'))}</span></div>`;
    }).join('');
    return `<div class="detail-grid">${items}</div>
            <div class="detail-links">
              <span class="badge info">row ${state.rows.indexOf(r) + 1} of ${state.rows.length}</span>
              <span style="color:var(--muted);font-size:.8rem">Every field on this row is shown above exactly as stored in the source CSV — nothing is clipped here.
              Raw file: <a href="https://github.com/buffedlizard55-lab/DrugAnalysis/tree/main/data" target="_blank" rel="noopener">/data</a></span>
            </div>`;
  }

  function currentPageRows() {
    if (!state.pageSize) return state.rows;
    return state.rows.slice(state.page * state.pageSize, (state.page + 1) * state.pageSize);
  }

  /* ---- synced scrollbars + sticky column width ---- */
  let syncing = false;
  function syncBars() {
    const overflow = table.scrollWidth - scrollBox.clientWidth;
    if (overflow > 4) {
      topScroll.classList.remove('hidden');
      topInner.style.width = table.scrollWidth + 'px';
      hint.textContent = '↔ Drag this bar (or the one under the table) to move across columns — the two stay in sync. Click any row to expand it and read every field, including long notes, without scrolling sideways.';
    } else {
      topScroll.classList.add('hidden');
      hint.textContent = '';
    }
    topScroll.scrollLeft = scrollBox.scrollLeft;
  }
  scrollBox.addEventListener('scroll', () => {
    if (syncing) return; syncing = true; topScroll.scrollLeft = scrollBox.scrollLeft; syncing = false;
  });
  topScroll.addEventListener('scroll', () => {
    if (syncing) return; syncing = true; scrollBox.scrollLeft = topScroll.scrollLeft; syncing = false;
  });
  window.addEventListener('resize', () => { syncBars(); });

  /* ---- pager ---- */
  function drawPager() {
    const p = el('pager');
    if (!state.pageSize) { p.innerHTML = `<span>Showing all ${state.rows.length} rows.</span>`; return; }
    const pages = Math.max(1, Math.ceil(state.rows.length / state.pageSize));
    if (state.page >= pages) state.page = pages - 1;
    const from = state.rows.length ? state.page * state.pageSize + 1 : 0;
    const to = Math.min(state.rows.length, (state.page + 1) * state.pageSize);
    p.innerHTML = `<button class="btn" data-p="first" ${state.page === 0 ? 'disabled' : ''}>« First</button>
      <button class="btn" data-p="prev" ${state.page === 0 ? 'disabled' : ''}>‹ Prev</button>
      <span>Page ${state.page + 1} / ${pages} — rows ${from}–${to}</span>
      <button class="btn" data-p="next" ${state.page >= pages - 1 ? 'disabled' : ''}>Next ›</button>
      <button class="btn" data-p="last" ${state.page >= pages - 1 ? 'disabled' : ''}>Last »</button>`;
    p.querySelectorAll('button').forEach(b => b.addEventListener('click', () => {
      const act = b.dataset.p;
      if (act === 'first') state.page = 0;
      if (act === 'prev') state.page = Math.max(0, state.page - 1);
      if (act === 'next') state.page = Math.min(pages - 1, state.page + 1);
      if (act === 'last') state.page = pages - 1;
      draw();
      scrollBox.scrollTop = 0;
    }));
  }

  /* ---- export ---- */
  function exportCSV() {
    const cols = cfg.columns;
    const esc = v => '"' + String(v === undefined || v === null ? '' : v).replace(/"/g, '""') + '"';
    const lines = [cols.map(c => esc(c.label)).join(',')];
    state.rows.forEach(r => lines.push(cols.map(c => esc(c.detail ? c.detail(r) : (r[c.field !== undefined ? c.field : c.key] || ''))).join(',')));
    const blob = new Blob(['\ufeff' + lines.join('\r\n')], { type: 'text/csv;charset=utf-8' });
    const a = document.createElement('a');
    a.href = URL.createObjectURL(blob);
    a.download = cfg.id + '_filtered_' + new Date().toISOString().slice(0, 10) + '.csv';
    a.click();
    setTimeout(() => URL.revokeObjectURL(a.href), 4000);
  }

  /* ---- main draw ---- */
  function draw() {
    if (state.loading) return;
    state.rows = computeRows();
    const cols = visCols();
    drawHead(cols);
    drawBody(cols, currentPageRows());
    drawPager();
    table.classList.toggle('compact', !!state.compact);
    el('count').textContent = state.rows.length + ' of ' +
      (cfg.baseFilter ? state.records.filter(cfg.baseFilter).length : state.records.length) + ' rows';
    requestAnimationFrame(syncBars);
  }

  /* ---- wire controls ---- */
  el('q').addEventListener('input', e => { state.q = e.target.value; state.page = 0; state.expanded = null; draw(); });
  el('size').addEventListener('change', e => {
    state.pageSize = +e.target.value; LS.set('dt:' + cfg.id + ':size', state.pageSize); state.page = 0; draw();
  });
  el('allrows').addEventListener('click', () => {
    state.pageSize = 0; state.page = 0;
    LS.set('dt:' + cfg.id + ':size', 0);
    el('size').value = '0';
    draw();
    scrollBox.scrollTop = 0;
  });
  el('density').addEventListener('click', () => { state.compact = !state.compact; LS.set('dt:' + cfg.id + ':compact', state.compact); draw(); });
  el('expand-text').addEventListener('click', () => {
    document.body.classList.toggle('wide-text');
    el('expand-text').classList.toggle('primary', document.body.classList.contains('wide-text'));
    requestAnimationFrame(syncBars);
  });
  el('export').addEventListener('click', exportCSV);

  /* ---- load ---- */
  loadCSV(cfg.csv).then(({ records }) => {
    state.records = records;
    state.loading = false;
    populateFilterOptions();
    draw();
    if (cfg.onLoad) cfg.onLoad(records);
  }).catch(err => {
    state.loading = false;
    mount.insertAdjacentHTML('beforeend',
      `<div class="notice">Could not load <code>${escapeHtml(cfg.csv)}</code>: ${escapeHtml(err.message)}</div>`);
  });

  return { state, redraw: draw, mount };
}

/* ----------------------------- 4. Views ----------------------------- */

const REPO_DATA = 'https://github.com/buffedlizard55-lab/DrugAnalysis/tree/main/data';

/* tabs */
document.querySelectorAll('.tab-btn').forEach(btn => {
  btn.addEventListener('click', () => {
    if (!btn.dataset.tab) return;
    document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
    document.querySelectorAll('.tab-panel').forEach(p => p.classList.remove('active'));
    btn.classList.add('active');
    const panel = document.getElementById(btn.dataset.tab);
    if (!panel) return;
    panel.classList.add('active');
    if (location.hash !== '#' + btn.dataset.tab) history.replaceState(null, '', '#' + btn.dataset.tab);
    window.dispatchEvent(new Event('resize'));   // re-measure scrollbars
    window.scrollTo({ top: 0 });
  });
});

/* deep-link support (#approvals etc.) */
function openTabFromHash() {
  const id = location.hash.replace('#', '');
  const btn = document.querySelector(`.tab-btn[data-tab="${id}"]`);
  if (btn) btn.click();
}

/* ---- shared column helpers ---- */
const c = (key, label, opt) => Object.assign({ key, label, field: key, render: r => escapeHtml(r[key] || '—') }, opt || {});

/* US-investability classes used by the approvals / private views */
const US_INVESTABLE = ['US-LISTED', 'US-LISTED (ADR)', 'FORMERLY US-LISTED (DELISTED/ACQUIRED)'];
const isUSInvestable = r => US_INVESTABLE.includes((r.us_investable_class || '').trim());
const isPrivate = r => (r.us_investable_class || '').includes('PRIVATE');
const isNonUS = r => (r.us_investable_class || '').includes('NON-US');
/* Rows whose issuer could not be tied to a listed security without guessing
   (openFDA no longer returns the applicant, or the symbol stopped returning
   data). Kept out of the investable universe, shown with the non-US rows and
   always carrying the reason in the row notes. */
const isUnverified = r => (r.us_investable_class || '').includes('NOT US-INVESTABLE');
const isOutOfScope = r => isPrivate(r) || isNonUS(r) || isUnverified(r);

const listingClassFilter = {
  key: 'cls', label: 'All listing classes', field: 'us_investable_class'
};

const APPROVAL_COLUMNS = [
  c('company_name', 'Company', { core: true, trunc: true, render: r => escapeHtml(r.company_name || '—') }),
  c('ticker', 'Ticker', { core: true, render: r => `<strong>${escapeHtml(r.ticker || '—')}</strong>` }),
  c('drug_brand', 'Drug (brand)', { core: true, render: r => escapeHtml(r.drug_brand || '—') }),
  c('drug_generic', 'Generic', { core: true }),
  c('decision_type', 'Decision', { core: true }),
  c('decision_date', 'Date', { core: true, render: r => `<span class="num-strong">${escapeHtml(r.decision_date || '')}</span>` }),
  c('indication', 'Indication', { core: true, trunc: true }),
  c('review_pathway', 'Pathway', { core: true, render: r => r.review_pathway ? `<span class="badge info">${escapeHtml(r.review_pathway)}</span>` : '<span class="badge neutral">not published</span>' }),
  c('us_investable_class', 'US investable?', { core: true, render: r => classBadge(r.us_investable_class) }),
  c('source_url_1', 'Source 1 (FDA)', { render: r => linkify(r.source_url_1, 'FDA source'), detail: r => r.source_url_1 }),
  c('source_url_2', 'Source 2', { render: r => linkify(r.source_url_2, 'verify'), detail: r => r.source_url_2 }),
  c('verification_status', 'Verification', { core: true, render: r => statusBadge(r.verification_status) }),
  c('notes', 'Notes', { trunc: true, render: r => truncCell(r.notes) }),
  /* Exchange is deliberately second-to-last and ID last, per project spec */
  c('exchange', 'Exchange', { core: true }),
  c('decision_id', 'ID', { render: r => `<code>${escapeHtml(r.decision_id || '')}</code>` })
];

/* ---- Core Analysis ---- */
function coreColumns() {
  return [
    c('company_name', 'Company', { core: true, trunc: true }),
    c('ticker', 'Ticker', { core: true, render: r => `<strong>${escapeHtml(r.ticker)}</strong>` }),
    c('company_score', 'Score /100', {
      core: true, num: true,
      render: r => scorePill(r.company_score, r.company_score_grade),
      detail: r => (r.company_score || '') + ' /100 (' + (r.company_score_grade || 'n/a') + ', confidence: ' + (r.company_score_confidence || 'n/a') + ')'
    }),
    c('drug_name', 'Drug', { core: true }),
    c('decision_type', 'Decision', { core: true }),
    c('decision_date', 'Date', { core: true, render: r => `<span class="num-strong">${escapeHtml(r.decision_date)}</span>` }),
    c('indication', 'Indication', { core: true, trunc: true }),
    c('review_pathway', 'Pathway', { render: r => r.review_pathway ? escapeHtml(r.review_pathway) : '<span class="badge neutral">not published</span>' }),
    c('stock_price_before', 'Price before', { core: true, num: true, render: r => num(r.stock_price_before, 2) }),
    c('stock_price_after', 'Price after', { core: true, num: true, render: r => num(r.stock_price_after, 2) }),
    c('pct_change', '% on decision', { core: true, num: true, render: r => pctCell(r.pct_change) }),
    c('price_t1', 'Price T+1', { num: true, render: r => num(r.price_t1, 2) }),
    c('pct_change_t1', '% T+1', { core: true, num: true, render: r => pctCell(r.pct_change_t1) }),
    c('price_data_status', 'Price data', { render: r => statusBadge(r.price_data_status) }),
    c('us_investable_class', 'US investable?', { core: true, render: r => classBadge(r.us_investable_class) }),
    c('flags', 'Flags', { core: true, render: r => r.flags ? r.flags.split(';').map(f => `<span class="badge flagged">${escapeHtml(f.trim())}</span>`).join(' ') : '' }),
    c('company_success_rate_summary', 'Track-record summary', { trunc: true, render: r => truncCell(r.company_success_rate_summary) }),
    c('fda_source_url', 'FDA source', { render: r => linkify(r.fda_source_url, 'FDA link'), detail: r => r.fda_source_url }),
    c('secondary_source_url', 'Source 2', { render: r => linkify(r.secondary_source_url, 'source 2'), detail: r => r.secondary_source_url }),
    c('verification_status', 'Verification', { core: true, render: r => statusBadge(r.verification_status) })
  ];
}

/* ---- Overview dashboard ---- */
const overview = { core: [], master: [], scores: [], snapshots: [], crls: [] };

function median(arr) {
  const v = arr.filter(x => !isNaN(parseFloat(x))).map(Number).sort((a, b) => a - b);
  if (!v.length) return null;
  const m = Math.floor(v.length / 2);
  return v.length % 2 ? v[m] : (v[m - 1] + v[m]) / 2;
}

function drawCoverage(master) {
  const years = Array.from({ length: 27 }, (_, i) => String(2000 + i));
  const counts = Object.fromEntries(years.map(y => [y, 0]));
  master.forEach(r => { const y = String(r.decision_date || '').slice(0, 4); if (counts[y] !== undefined) counts[y]++; });
  const covered = years.filter(y => counts[y]);
  const missing = years.filter(y => !counts[y]);
  const sourceNote = y => master.filter(r => String(r.decision_date || '').startsWith(y))
    .filter(r => [r.source_url_1, r.source_url_2].some(u => /(^|\.)fda\.gov\//i.test(u || ''))).length;
  document.getElementById('coverage-view').innerHTML = `
    <div class="coverage-summary"><strong>${covered.length} of ${years.length} years represented</strong>
      <span>${master.length} rows currently published · ${missing.length ? 'research backlog: ' + missing.join(', ') : 'no year gaps detected'}</span></div>
    <div class="coverage-grid" role="list" aria-label="FDA decision rows by year">
      ${years.map(y => `<div class="coverage-year ${counts[y] ? 'has-data' : 'no-data'}" role="listitem">
        <strong>${y}</strong><span>${counts[y] ? counts[y] + ' rows' : 'not populated'}</span>
        ${counts[y] ? `<small>${sourceNote(y)} FDA-domain source${sourceNote(y) === 1 ? '' : 's'}</small>` : ''}
      </div>`).join('')}
    </div>`;
}

function drawOverview() {
  const core = overview.core, master = overview.master, scores = overview.scores;
  if (!core.length) return;
  const approvals = core.filter(r => r.decision_type.startsWith('Approval'));
  const crls = core.filter(r => r.decision_type.startsWith('Complete Response'));
  const priced = core.filter(r => !isNaN(parseFloat(r.pct_change)));
  const flagged = core.filter(r => r.flags);
  const usRows = master.filter(isUSInvestable);
  const medAppr = median(approvals.map(r => r.pct_change));
  const medCrl = median(crls.map(r => r.pct_change));
  const medApprT1 = median(approvals.map(r => r.pct_change_t1));
  const fmt = v => v === null ? 'n/a' : (v >= 0 ? '+' : '') + v.toFixed(2) + '%';
  const latest = core.map(r => r.decision_date).sort().pop();
  /* 2026 is a separate audit slice: do not imply that a secondary article is
     an official FDA record. Count rows with an FDA-domain source explicitly. */
  const y2026 = master.filter(r => String(r.decision_date || '').startsWith('2026'));
  const official2026 = y2026.filter(r => [r.source_url_1, r.source_url_2].some(u => /(^|\.)fda\.gov\//i.test(u || '')));

  const cards = [
    { k: 'FDA decisions tracked', v: core.length, s: 'latest verified action ' + latest },
    { k: 'Approvals', v: approvals.length, s: 'median move on decision day ' + fmt(medAppr) + ' · T+1 ' + fmt(medApprT1) },
    { k: 'Rejections (CRLs)', v: crls.length, s: 'median move on CRL day ' + fmt(medCrl) },
    { k: 'US-investable issuers', v: usRows.length, s: 'of ' + master.length + ' approval rows in the master list' },
    { k: 'Rows with verified prices', v: priced.length, s: 'blank cells are never estimated' },
    { k: 'Rows flagged for review', v: flagged.length, s: 'irregularities explained in Notes' },
    { k: 'Companies scored', v: scores.length, s: 'numeric track-record score 0–100' },
    { k: '2026 decisions audited', v: y2026.length, s: official2026.length + ' include an FDA-domain source; others are flagged for source review' },
    { k: 'Original non-NME approvals', v: (overview.orig || []).length, s: ((overview.orig || []).filter(r => (r.us_investable_class || '').startsWith('US-LISTED')).length) + ' US-listed · Type 2/3/4/5, biosimilars, new-indication originals' },
    { k: 'Type 1 unmatched (flagged)', v: (overview.t1gap || []).length, s: 'openFDA Type 1 not merged into the NME master — CBER biologics / copacks, blank beats guessed' }
  ];
  document.getElementById('overview-stats').innerHTML = cards.map(x => `
    <div class="stat-card"><div class="stat-card-value">${escapeHtml(String(x.v))}</div>
    <div class="stat-card-key">${escapeHtml(x.k)}</div><div class="stat-card-sub">${escapeHtml(x.s)}</div></div>`).join('');

  /* top-scoped companies by score (minimum 3 tracked decisions so the score means something) */
  const ranked = scores.filter(s => +s.decisions_tracked >= 3 && !isNaN(parseFloat(s.total_score_0_100)))
    .sort((a, b) => parseFloat(b.total_score_0_100) - parseFloat(a.total_score_0_100));
  const top = ranked.slice(0, 12), bottom = ranked.slice(-8).reverse();
  const rankRow = s => `<tr><td>${escapeHtml(s.company_name)}</td><td><strong>${escapeHtml(s.ticker || '—')}</strong></td>
     <td class="num">${scorePill(s.total_score_0_100, s.grade)}</td>
     <td class="num">${escapeHtml(s.decisions_tracked)}</td>
     <td class="num">${escapeHtml(s.success_rate_pct)}%</td>
     <td class="num">${escapeHtml(s.confidence || '')}</td></tr>`;
  const rankTable = rows => `<table class="data-table" style="min-width:auto"><thead><tr>
     <th>Company</th><th>Ticker</th><th class="num">Score</th><th class="num">Decisions</th>
     <th class="num">FDA success rate</th><th class="num">Confidence</th></tr></thead>
     <tbody>${rows.map(rankRow).join('')}</tbody></table>`;
  document.getElementById('overview-top').innerHTML = ranked.length ? rankTable(top) : '<p class="empty-note">Scores not built yet.</p>';
  document.getElementById('overview-bottom').innerHTML = ranked.length ? rankTable(bottom) : '';

  /* latest decisions */
  const latestRows = core.slice().sort((a, b) => smartCompare(b.decision_date, a.decision_date)).slice(0, 12);
  document.getElementById('overview-latest').innerHTML = `<table class="data-table" style="min-width:auto"><thead><tr>
    <th>Date</th><th>Company</th><th>Drug</th><th>Decision</th><th class="num">% on day</th><th class="num">% T+1</th></tr></thead>
    <tbody>${latestRows.map(r => `<tr><td class="num">${escapeHtml(r.decision_date)}</td><td>${escapeHtml(r.company_name)}</td>
      <td>${escapeHtml(r.drug_name)}</td><td>${escapeHtml(r.decision_type)}</td>
      <td class="num">${pctCell(r.pct_change)}</td><td class="num">${pctCell(r.pct_change_t1)}</td></tr>`).join('')}</tbody></table>`;

  /* empirical market reaction distribution — computed from verified rows only */
  const buckets = [
    ['Approval — positive day', approvals.filter(r => parseFloat(r.pct_change) > 0).length],
    ['Approval — negative day', approvals.filter(r => parseFloat(r.pct_change) < 0).length],
    ['Approval — no price data', approvals.filter(r => isNaN(parseFloat(r.pct_change))).length],
    ['CRL — negative day', crls.filter(r => parseFloat(r.pct_change) < 0).length],
    ['CRL — positive day', crls.filter(r => parseFloat(r.pct_change) > 0).length]
  ];
  const maxB = Math.max(1, ...buckets.map(b => b[1]));
  document.getElementById('overview-dist').innerHTML = buckets.map(b => `
    <div style="display:flex;align-items:center;gap:10px;margin:6px 0;font-size:.85rem">
      <span style="flex:0 0 210px;color:var(--muted)">${escapeHtml(b[0])}</span>
      <span style="flex:1;background:#eef1f6;border-radius:4px;height:14px;overflow:hidden">
        <span style="display:block;height:100%;width:${(b[1] / maxB * 100).toFixed(1)}%;background:${b[0].includes('negative') ? '#c53434' : '#2f6fed'}"></span></span>
      <span class="num-strong" style="flex:0 0 40px;text-align:right">${b[1]}</span>
    </div>`).join('');
}

/* ---- numeric scorecards view ---- */
function scoreColumns() {
  return [
    c('company_name', 'Company', { core: true, trunc: true }),
    c('ticker', 'Ticker', { core: true, render: r => `<strong>${escapeHtml(r.ticker || '—')}</strong>` }),
    c('total_score_0_100', 'Score /100', {
      core: true, num: true, render: r => scorePill(r.total_score_0_100, r.grade),
      detail: r => r.total_score_0_100 + ' /100'
    }),
    c('grade', 'Grade', { core: true, render: r => gradeBadge(r.grade) }),
    c('confidence', 'Confidence', { core: true, render: r => statusBadge(r.confidence) }),
    c('decisions_tracked', 'Decisions', { core: true, num: true, render: r => num(r.decisions_tracked, 0) }),
    c('approvals_tracked', 'Approvals', { core: true, num: true, render: r => num(r.approvals_tracked, 0) }),
    c('crls_tracked', 'CRLs', { core: true, num: true, render: r => `<span class="${+r.crls_tracked ? 'pct-neg' : ''}">${escapeHtml(r.crls_tracked || '0')}</span>` }),
    c('withdrawals_flagged', 'Withdrawals', { num: true, render: r => num(r.withdrawals_flagged, 0) }),
    c('success_rate_pct', 'Success rate', { core: true, num: true, render: r => num(r.success_rate_pct, 1) + '%' }),
    c('success_rate_shrunk_pct', 'Shrunk rate (scored)', { core: true, num: true, render: r => num(r.success_rate_shrunk_pct, 1) + '%', detail: r => 'Empirical-Bayes shrunk approval rate = (approvals + 3 × 0.906) / (decisions + 3). This is the number the Outcome component scores; the raw rate and the Wilson lower bound are reported beside it as statistics.' }),
    c('success_rate_wilson_lower_pct', 'Wilson LB', { core: true, num: true, render: r => num(r.success_rate_wilson_lower_pct, 1) + '%', detail: r => '95% Wilson lower bound of the approval rate: ' + r.success_rate_wilson_lower_pct + '% (reported as a statistic, not scored since the 2026-09-12 model revision)' }),
    c('score_outcome', 'Outcome pts (40)', { num: true, render: r => num(r.score_outcome, 1) }),
    c('score_market', 'Market pts (20)', { num: true, render: r => num(r.score_market, 1) }),
    c('score_experience', 'Experience pts (15)', { num: true, render: r => num(r.score_experience, 1) }),
    c('score_pathway', 'Pathway pts (15)', { num: true, render: r => num(r.score_pathway, 1) }),
    c('score_pipeline', 'Pipeline pts (10)', { num: true, render: r => num(r.score_pipeline, 1) }),
    c('price_events', 'Price events', { num: true, render: r => num(r.price_events, 0) }),
    c('median_pct_on_decision', 'Median % day', { core: true, num: true, render: r => pctCell(r.median_pct_on_decision) }),
    c('median_pct_t1', 'Median % T+1', { num: true, render: r => pctCell(r.median_pct_t1) }),
    c('positive_reaction_rate_pct', '% positive reactions', { num: true, render: r => num(r.positive_reaction_rate_pct, 1) + '%' }),
    c('priority_review_count', 'Priority reviews', { num: true, render: r => num(r.priority_review_count, 0) }),
    c('accelerated_approval_count', 'Accelerated approvals', { num: true, render: r => num(r.accelerated_approval_count, 0) }),
    c('standard_review_count', 'Standard reviews', { num: true, render: r => num(r.standard_review_count, 0) }),
    c('pipeline_programs', 'Pipeline programs', { num: true, render: r => num(r.pipeline_programs, 0) }),
    c('advanced_count', 'Advanced phase', { num: true, render: r => num(r.advanced_count, 0) }),
    c('paused_count', 'Paused / hold', { num: true, render: r => num(r.paused_count, 0) }),
    c('pipeline_progression_pct', 'Pipeline progression', { num: true, render: r => num(r.pipeline_progression_pct, 1) + '%' }),
    c('us_investable_class', 'US investable?', { core: true, render: r => classBadge(r.us_investable_class) }),
    c('data_scope', 'Data scope', { render: r => statusBadge(r.data_scope) }),
    c('last_decision_date', 'Last decision', { num: true }),
    c('recency_days', 'Days since', { num: true, render: r => num(r.recency_days, 0) }),
    c('inputs_source', 'Inputs', { trunc: true, render: r => truncCell(r.inputs_source) }),
    c('notes', 'Score notes', { trunc: true, render: r => truncCell(r.notes) })
  ];
}

/* ---- Decision Engine ---- */
/* Every prior below is a published, citable figure — see the table rendered
   next to the calculator. Modifiers are applied as odds ratios, and the full
   arithmetic is printed so a reviewer can redo it by hand. Nothing here is
   fitted to hidden data and no number is invented. */
const ENGINE_PRIORS = [
  /* Every base rate below was read directly from the cited primary source on
     2026-09-12. The BIO / QLS / Informa figures come from "Clinical Development
     Success Rates 2011-2020" (n = 1,453 NDA/BLA filings including resubmissions).
     Sample sizes are printed in the label so small-n priors are not over-read. */
  { id: 'bio_all', label: 'NDA/BLA filed → approval, all therapeutic areas (2011–2020, n = 1,453)', base: 0.906,
    src: 'BIO / Biomedtracker / Informa Pharma Intelligence, "Clinical Development Success Rates 2011–2020": likelihood of approval from the NDA/BLA phase = 90.6% (includes resubmissions).',
    url: 'https://go.bio.org/rs/490-EHZ-999/images/ClinicalDevelopmentSuccessRates2011_2020.pdf' },
  { id: 'bio_onc', label: 'NDA/BLA filed → approval, oncology (n = 324)', base: 0.920,
    src: 'BIO 2011–2020, disease-area table: oncology 92.0% (haematologic 90.0% n=100, solid tumour 92.9% n=212, immuno-oncology 98.4% n=62).',
    url: 'https://go.bio.org/rs/490-EHZ-999/images/ClinicalDevelopmentSuccessRates2011_2020.pdf' },
  { id: 'bio_heme', label: 'NDA/BLA filed → approval, haematology (n = 72)', base: 0.931,
    src: 'BIO 2011–2020 disease-area table: haematology 93.1%.', url: 'https://go.bio.org/rs/490-EHZ-999/images/ClinicalDevelopmentSuccessRates2011_2020.pdf' },
  { id: 'bio_autoimmune', label: 'NDA/BLA filed → approval, autoimmune / inflammation (n = 202)', base: 0.941,
    src: 'BIO 2011–2020 disease-area table: autoimmune/inflammation 94.1%.', url: 'https://go.bio.org/rs/490-EHZ-999/images/ClinicalDevelopmentSuccessRates2011_2020.pdf' },
  { id: 'bio_infect', label: 'NDA/BLA filed → approval, infectious disease (n = 156)', base: 0.929,
    src: 'BIO 2011–2020 disease-area table: infectious disease 92.9%.', url: 'https://go.bio.org/rs/490-EHZ-999/images/ClinicalDevelopmentSuccessRates2011_2020.pdf' },
  { id: 'bio_neuro', label: 'NDA/BLA filed → approval, neurology (n = 165)', base: 0.867,
    src: 'BIO 2011–2020 disease-area table: neurology 86.7%.', url: 'https://go.bio.org/rs/490-EHZ-999/images/ClinicalDevelopmentSuccessRates2011_2020.pdf' },
  { id: 'bio_endo', label: 'NDA/BLA filed → approval, endocrine / metabolic (n = 124 / n = 48)', base: 0.863,
    src: 'BIO 2011–2020 disease-area table: endocrine 86.3%, metabolic 87.5%.', url: 'https://go.bio.org/rs/490-EHZ-999/images/ClinicalDevelopmentSuccessRates2011_2020.pdf' },
  { id: 'bio_cv', label: 'NDA/BLA filed → approval, cardiovascular (n = 80) — lowest of the 16 areas', base: 0.825,
    src: 'BIO 2011–2020 disease-area table: cardiovascular 82.5%, the weakest filing-to-approval rate of any disease area.', url: 'https://go.bio.org/rs/490-EHZ-999/images/ClinicalDevelopmentSuccessRates2011_2020.pdf' },
  { id: 'bio_rare', label: 'NDA/BLA filed → approval, rare disease (n = 172)', base: 0.936,
    src: 'BIO 2011–2020: rare-disease filings 93.6% vs chronic high-prevalence 92.6% (n = 217).', url: 'https://go.bio.org/rs/490-EHZ-999/images/ClinicalDevelopmentSuccessRates2011_2020.pdf' },
  { id: 'bio_mab', label: 'NDA/BLA filed → approval, monoclonal antibody modality', base: 0.954,
    src: 'BIO 2011–2020 modality table: mAb 95.4%, protein 89.7%, small molecule 89.5%, peptide 88.1%, antisense 66.7%.', url: 'https://go.bio.org/rs/490-EHZ-999/images/ClinicalDevelopmentSuccessRates2011_2020.pdf' },
  { id: 'ph3_to_sub', label: 'Phase III start → NDA/BLA filed, all areas', base: 0.578,
    src: 'BIO 2011–2020 phase-transition table: Phase III → NDA/BLA = 57.8% (oncology 47.7%, haematology 76.8%).', url: 'https://go.bio.org/rs/490-EHZ-999/images/ClinicalDevelopmentSuccessRates2011_2020.pdf' },
  { id: 'ph3_loa', label: 'Phase III start → approval (LOA from Phase III), all areas', base: 0.524,
    src: 'BIO 2011–2020: LOA from Phase III = 52.4% (oncology 43.9%, non-oncology 55.3%, haematology 71.5%).', url: 'https://go.bio.org/rs/490-EHZ-999/images/ClinicalDevelopmentSuccessRates2011_2020.pdf' },
  { id: 'ph1_loa', label: 'Phase I start → approval (LOA), all areas', base: 0.079,
    src: 'BIO 2011–2020: LOA from Phase I = 7.9% (PhI→II 52.0%, PhII→III 28.9%, PhIII→NDA/BLA 57.8%, NDA/BLA→approval 90.6%). Rare disease 17.0%, chronic high-prevalence 5.9%, haematology 23.9%, immuno-oncology 12.4%, all-oncology 5.3%, urology 3.6%.', url: 'https://go.bio.org/rs/490-EHZ-999/images/ClinicalDevelopmentSuccessRates2011_2020.pdf' },
  { id: 'accel_conv', label: 'Accelerated approval → converted to regular approval (oncology, n = 205, 1992–2024)', base: 0.52,
    src: '52% converted, 15% withdrawn, 33% still ongoing (205 oncology accelerated indications, 1992–2024). A Lancet eClinicalMedicine series of 133 oncology indications found 77% converted / 23% withdrawn (median 3.81 years to withdrawal), and non-oncology indications convert more often (75%). Use 0.52 as the conservative central estimate for oncology.',
    url: 'https://www.sciencedirect.com/science/article/abs/pii/S2213538325000414' },
  { id: 'accel_wd', label: 'Accelerated approval → withdrawn (all indications)', base: 0.13,
    src: 'HHS OIG OEI-01-21-00401: FDA and sponsors withdrew 13% of all accelerated approvals, half of them since January 2021.',
    url: 'https://oig.hhs.gov/oei/reports/OEI-01-21-00401.pdf' },
  { id: 'crl', label: 'Resubmission after a Complete Response Letter → approval  ⚠ NOT re-verified in this pass', base: 0.81,
    src: 'Retained as an explicit ASSUMPTION, not a verified figure: FDA publishes CRL letters (458 in the transparency API as of 2026-08-13) but not a resubmission-outcome rate, and no primary source was re-read for this value in the 2026-09-12 pass. Treat engine outputs that use it as indicative.',
    url: 'https://api.fda.gov/transparency/crl.json' }
];

const ENGINE_MODIFIERS = {
  pathway: [
    { v: 'Priority Review', m: 1.25, why: 'FDA grants Priority Review when it judges the drug potentially offers a significant improvement over available therapy — a positive signal about the review division\'s view of the data.' },
    { v: 'Breakthrough Therapy', m: 1.30, why: 'Requires preliminary clinical evidence of substantial improvement on a clinically significant endpoint; historically a strong predictor of approval.' },
    { v: 'Standard Review', m: 1.00, why: 'Neutral baseline.' },
    { v: 'Accelerated Approval (surrogate endpoint)', m: 0.90, why: 'Approval on a surrogate endpoint is faster but carries confirmatory-trial risk; slightly lower odds of a clean, durable action.' },
    { v: 'Single-arm registrational trial', m: 0.80, why: 'No randomised comparator: FDA advisory committees and ODAC have repeatedly pushed back on single-arm evidence for confirmatory indications.' }
  ],
  history: [
    { v: 'No prior FDA action for this company', m: 1.00, why: 'No track record in this dataset.' },
    { v: '1 prior approval, no CRL', m: 1.05, why: 'Demonstrated ability to complete a filing.' },
    { v: '2+ prior approvals, no CRL', m: 1.12, why: 'Repeat approvals: experienced regulatory/CMC organisation.' },
    { v: '1 prior CRL', m: 0.75, why: 'A previous CRL for this sponsor raises the prior probability of review issues recurring (CMC, efficacy evidence, safety database).' },
    { v: '2+ prior CRLs', m: 0.55, why: 'Repeat CRLs (see Aldeyra/Reproxalap: three CRLs for the same indication) are a strong negative signal.' }
  ],
  asset: [
    { v: 'First-in-class / novel mechanism', m: 1.00, why: 'Neutral: novel mechanism cuts both ways (unmet need vs. less predictable safety).' },
    { v: 'Follow-on / me-too in a crowded class', m: 0.95, why: 'FDA still requires demonstration of an acceptable benefit-risk profile; marginal differentiation adds little.' },
    { v: 'Resubmission after CRL (same asset)', m: 0.81, why: 'Uses the resubmission prior — flagged in the priors table as NOT re-verified in this pass.' },
    { v: 'Rare disease / orphan designation', m: 1.08, why: 'Smaller databases are acceptable; FDA has dedicated rare-disease review support.' },
    { v: 'Oncology, accelerated-approval seek', m: 0.85, why: 'Oncology registrational success is below the all-indication average (BIO 2011–2020).' }
  ],
  advisory: [
    { v: 'No advisory committee scheduled', m: 1.00, why: 'Neutral.' },
    { v: 'AdCom voted in favour', m: 1.20, why: 'A favourable vote is followed by approval in the large majority of cases.' },
    { v: 'AdCom voted against', m: 0.45, why: 'FDA follows an adverse committee vote more often than not.' },
    { v: 'AdCom scheduled, outcome unknown', m: 0.85, why: 'Convening a committee usually signals a contested benefit-risk question.' }
  ]
};

function initEngine() {
  const form = document.getElementById('engine-form');
  if (!form) return;

  /* priors table */
  document.getElementById('engine-priors').innerHTML = `<table class="data-table" style="min-width:auto">
    <thead><tr><th>Prior (base rate)</th><th class="num">P(approval)</th><th>Source</th></tr></thead>
    <tbody>${ENGINE_PRIORS.map(p => `<tr><td>${escapeHtml(p.label)}</td>
      <td class="num"><span class="num-strong">${(p.base * 100).toFixed(1)}%</span></td>
      <td>${escapeHtml(p.src)} ${linkify(p.url, 'official source')}</td></tr>`).join('')}</tbody></table>`;

  const selOpts = arr => arr.map(o => `<option value="${o.m}">${escapeHtml(o.v)}</option>`).join('');
  form.innerHTML = `
    <label for="e-prior">Starting prior (published base rate)</label>
    <select id="e-prior">${ENGINE_PRIORS.map(p => `<option value="${p.base}">${escapeHtml(p.label)} — ${(p.base * 100).toFixed(1)}%</option>`).join('')}</select>

    <label for="e-pathway">Review pathway / evidence package</label>
    <select id="e-pathway">${selOpts(ENGINE_MODIFIERS.pathway)}</select>

    <label for="e-history">Company track record (from this dataset)</label>
    <select id="e-history">${selOpts(ENGINE_MODIFIERS.history)}</select>

    <label for="e-asset">Asset characteristics</label>
    <select id="e-asset">${selOpts(ENGINE_MODIFIERS.asset)}</select>

    <label for="e-advisory">Advisory committee</label>
    <select id="e-advisory">${selOpts(ENGINE_MODIFIERS.advisory)}</select>

    <label for="e-company">Load a company's verified track record from this dataset (optional)</label>
    <select id="e-company"><option value="">— pick a company —</option></select>
    <p class="hscroll-hint" id="e-company-note"></p>`;

  /* populate companies from the numeric scorecard */
  const compSel = document.getElementById('e-company');
  overview.scores.slice()
    .sort((a, b) => a.company_name.localeCompare(b.company_name))
    .forEach(s => {
      const o = document.createElement('option');
      o.value = s.company_name;
      o.textContent = `${s.company_name} (${s.ticker || '—'}) — ${s.approvals_tracked || 0} approvals / ${s.crls_tracked || 0} CRLs`;
      o.dataset.crls = s.crls_tracked || 0; o.dataset.appr = s.approvals_tracked || 0;
      o.dataset.score = s.total_score_0_100 || ''; o.dataset.rate = s.success_rate_pct || '';
      o.dataset.wilson = s.success_rate_wilson_lower_pct || '';
      o.dataset.class = s.us_investable_class || '';
      /* Label-expansion evidence: approved efficacy supplements are direct,
         FDA-documented evidence that this company's trials keep converting.
         Joined on ticker from data/company_label_expansion_scorecard.csv. */
      const exp = (overview.expansion || []).find(e => e.ticker && e.ticker === s.ticker);
      if (exp) {
        o.dataset.suppl = exp.total_efficacy_supplements || 0;
        o.dataset.suppl5y = exp.expansions_last_5y || 0;
        o.dataset.supplprio = exp.priority_review_share_pct || '';
        o.dataset.suppldrugs = exp.distinct_drugs_expanded || 0;
      }
      compSel.appendChild(o);
    });

  compSel.addEventListener('change', () => {
    const o = compSel.selectedOptions[0];
    const note = document.getElementById('e-company-note');
    if (!o || !o.value) { note.textContent = ''; return; }
    const crls = +o.dataset.crls, appr = +o.dataset.appr;
    const bucket = crls >= 2 ? '2+ prior CRLs' : crls === 1 ? '1 prior CRL'
      : appr >= 2 ? '2+ prior approvals, no CRL' : appr === 1 ? '1 prior approval, no CRL' : 'No prior FDA action for this company';
    const histSel = document.getElementById('e-history');
    [...histSel.options].forEach((opt, i) => {
      if (ENGINE_MODIFIERS.history[i] && ENGINE_MODIFIERS.history[i].v === bucket) { histSel.value = opt.value; }
    });
    note.innerHTML = `Loaded from verified data: <strong>${escapeHtml(o.dataset.appr)}</strong> approvals, ` +
      `<strong>${escapeHtml(o.dataset.crls)}</strong> CRLs, FDA success rate <strong>${escapeHtml(o.dataset.rate)}%</strong> ` +
      `(95% Wilson lower bound ${escapeHtml(o.dataset.wilson)}%), composite score <strong>${escapeHtml(o.dataset.score)}</strong>/100, ` +
      `class ${escapeHtml(o.dataset.class)}.`;
    if (o.dataset.suppl) {
      note.innerHTML += `<br>Label-expansion record (FDA efficacy supplements, 2000-2026): ` +
        `<strong>${escapeHtml(o.dataset.suppl)}</strong> approved across ` +
        `<strong>${escapeHtml(o.dataset.suppldrugs)}</strong> drug(s), ` +
        `<strong>${escapeHtml(o.dataset.suppl5y)}</strong> in the last 5 years, ` +
        `${escapeHtml(o.dataset.supplprio)}% granted Priority Review. ` +
        `<em>A long, recent expansion record is direct evidence the company's late-stage trials keep ` +
        `converting into FDA approvals — weigh it alongside the novel-approval count above, which for ` +
        `most companies is a very small sample.</em>`;
    } else {
      note.innerHTML += `<br><em>No approved FDA efficacy supplements recorded for this issuer 2000-2026 — ` +
        `the track record here rests only on novel approvals, which is a small sample. Treat the estimate ` +
        `as correspondingly uncertain.</em>`;
    }
    if (o.dataset.origclin) {
      note.innerHTML += `<br>Original non-NME approvals (2000–2026): ` +
        `<strong>${escapeHtml(o.dataset.origclin)}</strong> clinical-relevant (Type 2/3/4 + new-indication originals) ` +
        `out of <strong>${escapeHtml(o.dataset.origtot)}</strong> original non-NME decisions ` +
        `(${escapeHtml(o.dataset.origt3)} Type 3 new dosage forms; ` +
        `<strong>${escapeHtml(o.dataset.orig5y)}</strong> in the last 5 years). ` +
        `<em>Type 5 manufacturer changes and medical gases are excluded from the clinical-relevant count.</em>`;
    }
    compute();
  });

  function compute() {
    const prior = parseFloat(document.getElementById('e-prior').value);
    const picks = ['e-pathway', 'e-history', 'e-asset', 'e-advisory'].map(id => parseFloat(document.getElementById(id).value));
    const odds0 = prior / (1 - prior);
    let odds = odds0, lines = [`prior odds      = ${prior.toFixed(3)} / (1 - ${prior.toFixed(3)}) = ${odds0.toFixed(3)}`];
    picks.forEach((m, i) => {
      const sel = document.getElementById(['e-pathway', 'e-history', 'e-asset', 'e-advisory'][i]);
      const label = sel.selectedOptions[0].textContent;
      odds *= m;
      lines.push(`× ${m.toFixed(2)}  ${label.slice(0, 46)}`);
    });
    const p = odds / (1 + odds);
    const out = document.getElementById('engine-out');
    const band = p >= 0.85 ? ['A — approval highly likely', 'grade-A'] :
                 p >= 0.65 ? ['B — approval more likely than not', 'grade-B'] :
                 p >= 0.45 ? ['C — genuinely contested', 'grade-C'] :
                 p >= 0.25 ? ['D — rejection risk is material', 'grade-D'] : ['E — rejection more likely', 'grade-E'];
    out.innerHTML = `
      <div class="big">${(p * 100).toFixed(1)}%</div>
      <div class="sub">modelled probability of a positive FDA action for this scenario</div>
      <div style="margin-top:12px"><span class="grade ${band[1]}">${escapeHtml(band[0])}</span></div>
      <ul class="factor-list">${picks.map((m, i) => {
        const sel = document.getElementById(['e-pathway', 'e-history', 'e-asset', 'e-advisory'][i]);
        const cls = m > 1 ? 'mult-up' : m < 1 ? 'mult-dn' : 'mult-flat';
        const def = Object.values(ENGINE_MODIFIERS).flat().find(x => x.v === sel.selectedOptions[0].textContent);
        return `<li><span>${escapeHtml(sel.selectedOptions[0].textContent)}<br>
          <span style="color:#a9c3ea;font-size:.76rem">${escapeHtml(def ? def.why : '')}</span></span>
          <span class="${cls}">×${m.toFixed(2)}</span></li>`;
      }).join('')}</ul>
      <div class="engine-math">${escapeHtml(lines.join('\n'))}
posterior odds  = ${odds.toFixed(3)}
P(approval)     = ${odds.toFixed(3)} / (1 + ${odds.toFixed(3)}) = ${(p * 100).toFixed(1)}%</div>`;
  }

  form.addEventListener('change', compute);
  compute();
}

/* ---- live counts in the header and section copy (never hard-coded) ---- */
function setCount(key, value) {
  document.querySelectorAll(`[data-count="${key}"]`).forEach(e => { e.textContent = value; });
}

function fillCounts() {
  const master = overview.master || [], core = overview.core || [];
  setCount('master', master.length);
  setCount('us', master.filter(isUSInvestable).length);
  setCount('unverified', master.filter(isUnverified).length);
  setCount('prices', (overview.snapshots || []).length);
  setCount('scores', (overview.scores || []).length);
  setCount('private', master.filter(isPrivate).length);
  setCount('nonus', master.filter(r => isNonUS(r) || isUnverified(r)).length);
  setCount('latest', core.map(r => r.decision_date).sort().pop() || '—');
  setCount('pipeline', (overview.pipeline || []).length);
  setCount('pdufa', (overview.pdufa || []).length);
  setCount('trials', (overview.trials || []).length);

  /* Efficacy supplements + verification audit */
  const suppl = overview.suppl || [], audit = overview.audit || [];
  setCount('suppl', suppl.length);
  setCount('supplus', suppl.filter(r => (r.us_investable_class || '').startsWith('US-LISTED')).length);
  setCount('supplletters', suppl.filter(r => (r.approval_letter_url || '').trim()).length);
  const orig = overview.orig || [];
  setCount('orig', orig.length);
  setCount('origus', orig.filter(r => (r.us_investable_class || '').startsWith('US-LISTED')).length);
  setCount('t1gap', (overview.t1gap || []).length);
  setCount('alldecisions', (overview.master || []).length + suppl.length + orig.length);
  const confirmed = audit.filter(r => (r.crosscheck_status || '').startsWith('MATCH')).length;
  const conflicts = audit.filter(r => (r.crosscheck_status || '').startsWith('MISMATCH')).length;
  setCount('auditconfirmed', confirmed);
  setCount('auditconflicts', conflicts);
  setCount('auditrows', audit.length);
}

/* ---- qualitative pipeline cards (deep-dive scorecards) ---- */
function drawPipelineCards(records) {
  const deep = records.filter(r => !/partial pipeline view/i.test(r.verification_status || ''));
  const rest = records.filter(r => /partial pipeline view/i.test(r.verification_status || ''));
  const card = r => `
    <div class="card">
      <h3>${escapeHtml(r.company_name)}</h3>
      <div class="ticker">${escapeHtml(r.ticker || '—')} ${statusBadge(r.verification_status)}</div>
      <div class="stat-row"><span>Programs tracked</span><strong>${escapeHtml(r.total_pipeline_programs_tracked)}</strong></div>
      <div class="stat-row"><span>Approved</span><strong>${escapeHtml(r.approved_count)}</strong></div>
      <div class="stat-row"><span>Advanced to next phase</span><strong>${escapeHtml(r.advanced_to_next_phase_count)}</strong></div>
      <div class="stat-row"><span>Paused / clinical hold</span><strong>${escapeHtml(r.paused_or_clinical_hold_count)}</strong></div>
      <div class="stat-row"><span>CRLs (rejections)</span><strong>${escapeHtml(r.crl_rejected_count)}</strong></div>
      <div class="phase-details">${escapeHtml(r.phase_details)}</div>
      <div class="card-links">${linkify(r.source_url_1, 'Source 1')} ${linkify(r.source_url_2, 'Source 2')}</div>
      <div class="phase-details"><em>${escapeHtml(r.notes)}</em></div>
    </div>`;
  document.getElementById('cards-deep').innerHTML = deep.map(card).join('');
  document.getElementById('cards-deep-count').textContent = deep.length;
  document.getElementById('cards-rest').innerHTML = rest.map(card).join('');
  document.getElementById('cards-rest-count').textContent = rest.length;
  setCount('deepcards', deep.length);
  setCount('restcards', rest.length);
}

/* ----------------------------- boot ----------------------------- */

const yearFilter = field => ({
  key: 'year', label: 'All years', field,
  valuesFrom: r => String(r[field] || '').slice(0, 4),
  match: (r, v) => String(r[field] || '').slice(0, 4) === v
});

Promise.all([
  loadCSV('data/core_analysis_table.csv').then(x => x.records).catch(() => []),
  loadCSV('data/fda_decisions_master.csv').then(x => x.records).catch(() => []),
  loadCSV('data/company_scores.csv').then(x => x.records).catch(() => []),
  loadCSV('data/stock_price_snapshots.csv').then(x => x.records).catch(() => []),
  loadCSV('data/fda_crl_master.csv').then(x => x.records).catch(() => []),
  loadCSV('data/pipeline_tracker.csv').then(x => x.records).catch(() => []),
  loadCSV('data/upcoming_pdufa_calendar.csv').then(x => x.records).catch(() => []),
  loadCSV('data/clinical_trial_endpoints.csv').then(x => x.records).catch(() => []),
  loadCSV('data/fda_supplement_decisions.csv').then(x => x.records).catch(() => []),
  loadCSV('data/verification_crosscheck.csv').then(x => x.records).catch(() => []),
  loadCSV('data/company_label_expansion_scorecard.csv').then(x => x.records).catch(() => []),
  loadCSV('data/fda_original_non_nme_decisions.csv').then(x => x.records).catch(() => []),
  loadCSV('data/company_original_approval_scorecard.csv').then(x => x.records).catch(() => []),
  loadCSV('data/fda_type1_not_in_nme_master.csv').then(x => x.records).catch(() => [])
]).then(([core, master, scores, snapshots, crls, pipeline, pdufa, trials, suppl, audit, expansion, orig, origScores, t1gap]) => {
  overview.core = core; overview.master = master; overview.scores = scores;
  overview.snapshots = snapshots; overview.crls = crls;
  overview.pipeline = pipeline; overview.pdufa = pdufa; overview.trials = trials;
  overview.suppl = suppl; overview.audit = audit; overview.expansion = expansion;
  overview.orig = orig; overview.origScores = origScores; overview.t1gap = t1gap;

  fillCounts();
  drawCoverage(master);
  drawOrigCoverage(orig || []);
  drawOverview();
  initEngine();

  /* Pipeline tracker in overview */
  const pipeEl = document.getElementById('pipeline-view');
  if (pipeEl) {
    if (pipeline && pipeline.length) {
      pipeEl.innerHTML = `<table class="data-table" style="min-width:auto"><thead><tr><th>Company</th><th>Ticker</th><th class="num">Programs</th><th class="num">Approved</th><th class="num">Phase 3</th><th class="num">Success %</th><th>Source</th></tr></thead><tbody>` +
        pipeline.slice().sort((a,b)=> parseInt(b.total_programs||0)-parseInt(a.total_programs||0)).slice(0,12).map(r => `<tr><td>${escapeHtml(r.company_name)}</td><td><strong>${escapeHtml(r.ticker)}</strong></td><td class="num">${escapeHtml(r.total_programs)}</td><td class="num">${escapeHtml(r.approved)}</td><td class="num">${escapeHtml(r.phase_3)}</td><td class="num">${pctCell(r.success_rate_pct)}</td><td>${linkify(r.source_url_1,'pipeline')}</td></tr>`).join('') + `</tbody></table><p class="hscroll-hint"><a href="#" onclick="document.querySelector('[data-tab=scorecards]').click(); return false;">View all ${pipeline.length} pipeline trackers in Scorecards tab →</a> · <a href="https://github.com/buffedlizard55-lab/DrugAnalysis/blob/main/data/pipeline_tracker.csv" target="_blank">Raw CSV</a></p>`;
    } else {
      pipeEl.innerHTML = '<p class="empty-note">Pipeline tracker not loaded — <a href="https://github.com/buffedlizard55-lab/DrugAnalysis/blob/main/data/pipeline_tracker.csv" target="_blank">view raw CSV</a></p>';
    }
  }
  const pdufaEl = document.getElementById('pdufa-view');
  if (pdufaEl) {
    if (pdufa && pdufa.length) {
      // Sort by PDUFA date ascending (soonest first) and add countdown
      const today = new Date(); today.setHours(0,0,0,0);
      const withDays = pdufa.map(r => {
        let days = null;
        try { const d = new Date(r.pdufa_date); if (!isNaN(d)) days = Math.round((d - today)/86400000); } catch(e){}
        return {...r, _days: days};
      }).sort((a,b) => String(a.pdufa_date).localeCompare(String(b.pdufa_date)));
      const fmtDays = d => {
        if (d===null || isNaN(d)) return '<span class="badge neutral">—</span>';
        if (d < 0) return `<span class="badge flagged">${Math.abs(d)}d ago</span>`;
        if (d === 0) return '<span class="badge verified">today</span>';
        if (d <= 30) return `<span class="badge flagged">${d}d</span>`;
        if (d <= 90) return `<span class="badge caveat">${d}d</span>`;
        return `<span class="badge neutral">${d}d</span>`;
      };
      pdufaEl.innerHTML = `<table class="data-table" style="min-width:auto"><thead><tr><th>Company</th><th>Drug</th><th>PDUFA Date</th><th>Countdown</th><th>Indication</th><th>Pathway</th><th>Status</th></tr></thead><tbody>` +
        withDays.map(r => `<tr><td>${escapeHtml(r.company_name)} <strong>${escapeHtml(r.ticker)}</strong></td><td>${escapeHtml(r.drug_brand)}</td><td class="num"><span class="num-strong">${escapeHtml(r.pdufa_date)}</span></td><td class="num">${fmtDays(r._days)}</td><td>${escapeHtml((r.indication||'').slice(0,80))}</td><td>${escapeHtml(r.review_pathway)}</td><td>${statusBadge(r.verification_status)}</td></tr>`).join('') + `</tbody></table><p class="hscroll-hint">${pdufa.length} upcoming PDUFA dates tracked (sorted soonest first, countdown from today) · <a href="https://github.com/buffedlizard55-lab/DrugAnalysis/blob/main/data/upcoming_pdufa_calendar.csv" target="_blank">Raw CSV</a> · All with 2 source links for manual verification · Caps: extended Aug 22→Nov 22 2026 after major amendment</p>`;
    } else {
      pdufaEl.innerHTML = '<p class="empty-note">PDUFA calendar not loaded — <a href="https://github.com/buffedlizard55-lab/DrugAnalysis/blob/main/data/upcoming_pdufa_calendar.csv" target="_blank">view raw CSV</a></p>';
    }
  }

  /* Core analysis */
  DataTable({
    id: 'core', mount: '#core-view', csv: 'data/core_analysis_table.csv',
    columns: coreColumns(),
    searchFields: ['company_name', 'drug_name', 'indication', 'ticker'],
    searchPlaceholder: 'Search company, drug, indication, ticker…',
    sort: { key: 'decision_date', dir: 'desc' },
    filters: [
      { key: 'type', label: 'All decision types', field: 'decision_type' },
      yearFilter('decision_date'),
      { key: 'cls', label: 'All listing classes', field: 'us_investable_class' },
      { key: 'flag', label: 'Flagged rows only', options: () => ['IRREGULARITY', 'OWNERSHIP-CHANGE', 'WITHDRAWN', 'PRICE-GAP'],
        match: (r, v) => (r.flags || '').indexOf(v) !== -1 }
    ]
  });

  /* FDA approvals — US-investable issuers (the investable universe) */
  DataTable({
    id: 'approvals', mount: '#approvals-view', csv: 'data/fda_decisions_master.csv',
    columns: APPROVAL_COLUMNS,
    searchFields: ['company_name', 'drug_brand', 'drug_generic', 'ticker', 'indication', 'exchange'],
    searchPlaceholder: 'Search company, drug, ticker, indication…',
    sort: { key: 'decision_date', dir: 'desc' },
    baseFilter: r => !isOutOfScope(r),
    filters: [yearFilter('decision_date'), listingClassFilter,
      { key: 'pathway', label: 'All pathways', field: 'review_pathway' },
      { key: 'exch', label: 'All exchanges', field: 'exchange' }],
    note: '<p class="hscroll-hint">This view shows the <strong>investable universe</strong>: US-listed issuers, US OTC ADRs, and companies that were US-listed at the time of the decision but have since been acquired or delisted (their price reaction is still part of the historical record). Private companies and non-US-only listings are on their own tabs. Exchange is the second-to-last column and the row ID is last.</p>'
  });

  /* Keep the two review modes available at the top of the section. The
     generated DataTable owns pagination/state, so these buttons delegate to
     its existing controls rather than creating a second source of truth. */
  document.getElementById('approvals-review-all').addEventListener('click', () => {
    const allRows = document.getElementById('approvals-allrows');
    if (allRows) allRows.click();
    document.getElementById('approvals-view').scrollIntoView({ behavior: 'smooth', block: 'start' });
  });
  document.getElementById('approvals-jump-table').addEventListener('click', () => {
    document.getElementById('approvals-view').scrollIntoView({ behavior: 'smooth', block: 'start' });
  });

  /* Private companies — their own subpage, out of the investable universe */
  DataTable({
    id: 'private', mount: '#private-view', csv: 'data/fda_decisions_master.csv',
    columns: APPROVAL_COLUMNS,
    searchFields: ['company_name', 'drug_brand', 'drug_generic', 'indication'],
    searchPlaceholder: 'Search private-company approvals…',
    sort: { key: 'decision_date', dir: 'desc' },
    baseFilter: isPrivate
  });

  /* Non-US-only listings — publicly traded, but no US-accessible equity */
  DataTable({
    id: 'nonus', mount: '#nonus-view', csv: 'data/fda_decisions_master.csv',
    columns: APPROVAL_COLUMNS,
    searchFields: ['company_name', 'drug_brand', 'drug_generic', 'ticker', 'indication', 'exchange'],
    searchPlaceholder: 'Search non-US listings…',
    sort: { key: 'decision_date', dir: 'desc' },
    baseFilter: r => isNonUS(r) || isUnverified(r)
  });

  /* CRLs */
  DataTable({
    id: 'crls', mount: '#crls-view', csv: 'data/fda_crl_master.csv',
    columns: [
      c('company_name', 'Company', { core: true }),
      c('ticker', 'Ticker', { core: true, render: r => `<strong>${escapeHtml(r.ticker)}</strong>` }),
      c('drug_name', 'Drug', { core: true }),
      c('indication', 'Indication', { core: true, trunc: true }),
      c('crl_date', 'CRL date', { core: true, render: r => `<span class="num-strong">${escapeHtml(r.crl_date)}</span>` }),
      c('reason_category', 'Reason', { core: true, trunc: true }),
      c('stock_reaction', 'Stock reaction', { core: true, trunc: true }),
      c('source_url_1', 'Source 1', { render: r => linkify(r.source_url_1, 'source'), detail: r => r.source_url_1 }),
      c('source_url_2', 'Source 2', { render: r => linkify(r.source_url_2, 'secondary'), detail: r => r.source_url_2 }),
      c('verification_status', 'Verification', { core: true, render: r => statusBadge(r.verification_status) }),
      c('notes', 'Notes', { trunc: true, render: r => truncCell(r.notes) }),
      c('exchange', 'Exchange'),
      c('crl_id', 'ID', { render: r => `<code>${escapeHtml(r.crl_id)}</code>` })
    ],
    searchFields: ['company_name', 'drug_name', 'indication', 'ticker'],
    searchPlaceholder: 'Search rejections…',
    sort: { key: 'crl_date', dir: 'desc' }, pageSize: 25
  });

  /* Efficacy supplements (label expansions) */
  DataTable({
    id: 'supplements', mount: '#supplements-view', csv: 'data/fda_supplement_decisions.csv',
    columns: [
      c('company_name', 'Company', { core: true, trunc: true }),
      c('ticker', 'Ticker', { core: true, render: r => `<strong>${escapeHtml(r.ticker)}</strong>` }),
      c('drug_brand', 'Drug', { core: true }),
      c('drug_generic', 'Generic', { trunc: true }),
      c('decision_date', 'Approved', { core: true, render: r => `<span class="num-strong">${escapeHtml(r.decision_date)}</span>` }),
      c('review_priority', 'Review', { core: true, render: r => r.review_priority ? `<span class="badge ${/PRIORITY/i.test(r.review_priority) ? 'verified' : 'neutral'}">${escapeHtml(r.review_priority)}</span>` : '' }),
      c('submission_property_type', 'Designations', { core: true, trunc: true }),
      c('application_number', 'Application', { core: true, render: r => `<code>${escapeHtml(r.application_number)}</code>` }),
      c('submission_number', 'Suppl #', { render: r => `<code>${escapeHtml(r.submission_number)}</code>` }),
      c('approval_letter_url', 'FDA letter', { core: true, render: r => linkify(r.approval_letter_url, 'letter'), detail: r => r.approval_letter_url }),
      c('label_url', 'Label', { render: r => linkify(r.label_url, 'label'), detail: r => r.label_url }),
      c('source_url_drugsatfda', 'Drugs@FDA', { render: r => linkify(r.source_url_drugsatfda, 'record'), detail: r => r.source_url_drugsatfda }),
      c('pharm_class_epc', 'Class', { trunc: true }),
      c('us_investable_class', 'US investable?', { core: true, render: r => classBadge(r.us_investable_class) }),
      c('verification_status', 'Verification', { core: true, render: r => statusBadge(r.verification_status) }),
      c('openfda_sponsor_name', 'openFDA sponsor', { trunc: true }),
      c('sponsor_resolution_basis', 'How resolved', { trunc: true, render: r => truncCell(r.sponsor_resolution_basis) }),
      c('supplement_id', 'ID', { render: r => `<code>${escapeHtml(r.supplement_id)}</code>` })
    ],
    searchFields: ['company_name', 'drug_brand', 'drug_generic', 'ticker', 'application_number'],
    searchPlaceholder: 'Search drug, company or application…',
    sort: { key: 'decision_date', dir: 'desc' }, pageSize: 25,
    filters: [
      yearFilter('decision_date'),
      { key: 'cls', label: 'All listing classes', field: 'us_investable_class' },
      { key: 'prio', label: 'All review priorities', field: 'review_priority' }
    ]
  });

  /* Label-expansion scorecard */
  DataTable({
    id: 'expansion-scores', mount: '#expansion-scores-view', csv: 'data/company_label_expansion_scorecard.csv',
    columns: [
      c('company_name', 'Company', { core: true, trunc: true }),
      c('ticker', 'Ticker', { core: true, render: r => `<strong>${escapeHtml(r.ticker)}</strong>` }),
      c('total_efficacy_supplements', 'Label expansions', { core: true, num: true, render: r => num(r.total_efficacy_supplements, 0) }),
      c('distinct_drugs_expanded', 'Drugs expanded', { core: true, num: true, render: r => num(r.distinct_drugs_expanded, 0) }),
      /* A share, not a change: pctCell() would colour it green and prefix "+". */
      c('priority_review_share_pct', 'Priority %', { core: true, num: true,
        render: r => `<span class="num-strong">${num(r.priority_review_share_pct, 1)}%</span>` }),
      c('priority_review_count', 'Priority count', { num: true, render: r => num(r.priority_review_count, 0) }),
      c('orphan_supplement_count', 'Orphan', { num: true, render: r => num(r.orphan_supplement_count, 0) }),
      c('expansions_last_5y', 'Last 5 yrs', { core: true, num: true, render: r => num(r.expansions_last_5y, 0) }),
      c('expansion_velocity_per_yr', 'Per year', { core: true, num: true, render: r => num(r.expansion_velocity_per_yr, 2) }),
      c('novel_approvals_tracked', 'Novel approvals', { core: true, num: true, render: r => num(r.novel_approvals_tracked, 0) }),
      c('breadth_ratio_suppl_per_novel', 'Breadth ratio', { core: true, num: true, render: r => r.breadth_ratio_suppl_per_novel ? num(r.breadth_ratio_suppl_per_novel, 2) : '<span class="muted">n/a</span>' }),
      c('first_expansion_date', 'First', { render: r => escapeHtml(r.first_expansion_date) }),
      c('last_expansion_date', 'Most recent', { core: true, render: r => `<span class="num-strong">${escapeHtml(r.last_expansion_date)}</span>` }),
      c('rows_flagged_for_review', 'Flagged', { num: true, render: r => num(r.rows_flagged_for_review, 0) }),
      c('us_investable_class', 'US investable?', { core: true, render: r => classBadge(r.us_investable_class) }),
      c('evidence_basis', 'Evidence', { trunc: true, render: r => truncCell(r.evidence_basis) }),
      c('verification_status', 'Verification', { render: r => statusBadge(r.verification_status) })
    ],
    searchFields: ['company_name', 'ticker'],
    searchPlaceholder: 'Search company or ticker…',
    sort: { key: 'total_efficacy_supplements', dir: 'desc' },
    filters: [
      { key: 'cls', label: 'All listing classes', field: 'us_investable_class' },
      { key: 'min', label: 'Minimum label expansions', options: () => ['1', '5', '10', '25', '50'],
        match: (r, v) => +r.total_efficacy_supplements >= +v }
    ]
  });

  /* Original non-NME NDA/BLA approvals */
  DataTable({
    id: 'orig', mount: '#orig-view', csv: 'data/fda_original_non_nme_decisions.csv',
    columns: [
      c('company_name', 'Company', { core: true, trunc: true }),
      c('ticker', 'Ticker', { core: true, render: r => `<strong>${escapeHtml(r.ticker)}</strong>` }),
      c('drug_brand', 'Drug', { core: true }),
      c('drug_generic', 'Generic', { trunc: true }),
      c('decision_date', 'Approved', { core: true, render: r => `<span class="num-strong">${escapeHtml(r.decision_date)}</span>` }),
      c('chemical_type_group', 'Chemical type', { core: true, trunc: true,
        render: r => `<span class="badge info">${escapeHtml(r.chemical_type_group || r.chemical_type_description || '—')}</span>` }),
      c('review_priority', 'Review', { core: true, render: r => r.review_priority ? `<span class="badge ${/PRIORITY/i.test(r.review_priority) ? 'verified' : 'neutral'}">${escapeHtml(r.review_priority)}</span>` : '' }),
      c('application_kind', 'Kind', { core: true }),
      c('application_number', 'Application', { core: true, render: r => `<code>${escapeHtml(r.application_number)}</code>` }),
      c('source_url_1', 'Drugs@FDA', { core: true, render: r => linkify(r.source_url_1, 'record'), detail: r => r.source_url_1 }),
      c('source_url_2', 'openFDA query', { render: r => linkify(r.source_url_2, 'API'), detail: r => r.source_url_2 }),
      c('us_investable_class', 'US investable?', { core: true, render: r => classBadge(r.us_investable_class) }),
      c('verification_status', 'Verification', { core: true, render: r => statusBadge(r.verification_status) }),
      c('openfda_sponsor_name', 'openFDA sponsor', { trunc: true }),
      c('sponsor_resolution_basis', 'How resolved', { trunc: true, render: r => truncCell(r.sponsor_resolution_basis) }),
      c('notes', 'Notes', { trunc: true, render: r => truncCell(r.notes) }),
      c('orig_id', 'ID', { render: r => `<code>${escapeHtml(r.orig_id)}</code>` })
    ],
    searchFields: ['company_name', 'drug_brand', 'drug_generic', 'ticker', 'application_number', 'chemical_type_group', 'openfda_sponsor_name'],
    searchPlaceholder: 'Search drug, company, ticker or application…',
    sort: { key: 'decision_date', dir: 'desc' }, pageSize: 25,
    filters: [
      yearFilter('decision_date'),
      { key: 'cls', label: 'All listing classes', field: 'us_investable_class' },
      { key: 'chem', label: 'All chemical types', field: 'chemical_type_group' },
      { key: 'prio', label: 'All review priorities', field: 'review_priority' },
      { key: 'kind', label: 'NDA or BLA', field: 'application_kind' }
    ]
  });

  /* Original-approval scorecard */
  DataTable({
    id: 'orig-scores', mount: '#orig-scores-view', csv: 'data/company_original_approval_scorecard.csv',
    columns: [
      c('company_name', 'Company', { core: true, trunc: true }),
      c('ticker', 'Ticker', { core: true, render: r => `<strong>${escapeHtml(r.ticker)}</strong>` }),
      c('clinical_relevant_count', 'Clinical-relevant', { core: true, num: true, render: r => num(r.clinical_relevant_count, 0) }),
      c('total_original_non_nme', 'Total originals', { core: true, num: true, render: r => num(r.total_original_non_nme, 0) }),
      c('n_type2_new_active', 'Type 2', { core: true, num: true, render: r => num(r.n_type2_new_active, 0) }),
      c('n_type3_new_dosage', 'Type 3 dosage', { core: true, num: true, render: r => num(r.n_type3_new_dosage, 0) }),
      c('n_type4_new_combination', 'Type 4 combo', { core: true, num: true, render: r => num(r.n_type4_new_combination, 0) }),
      c('n_type5_formulation_or_manufacturer', 'Type 5', { core: true, num: true, render: r => num(r.n_type5_formulation_or_manufacturer, 0) }),
      c('n_new_indication_original', 'New-indication orig', { num: true, render: r => num(r.n_new_indication_original, 0) }),
      c('n_biosimilar_or_unpublished_bla', 'Biosimilar / BLA', { num: true, render: r => num(r.n_biosimilar_or_unpublished_bla, 0) }),
      c('n_medical_gas', 'Medical gas', { num: true, render: r => num(r.n_medical_gas, 0) }),
      c('priority_review_count', 'Priority', { num: true, render: r => num(r.priority_review_count, 0) }),
      c('priority_review_share_pct', 'Priority %', { core: true, num: true,
        render: r => `<span class="num-strong">${num(r.priority_review_share_pct, 1)}%</span>` }),
      c('orig_last_5y', 'Last 5 yrs', { core: true, num: true, render: r => num(r.orig_last_5y, 0) }),
      c('orig_velocity_per_yr', 'Per year', { core: true, num: true, render: r => num(r.orig_velocity_per_yr, 2) }),
      c('novel_approvals_tracked', 'Novel approvals', { core: true, num: true, render: r => num(r.novel_approvals_tracked, 0) }),
      c('last_orig_date', 'Most recent', { core: true, render: r => `<span class="num-strong">${escapeHtml(r.last_orig_date)}</span>` }),
      c('us_investable_class', 'US investable?', { core: true, render: r => classBadge(r.us_investable_class) }),
      c('evidence_basis', 'Evidence', { trunc: true, render: r => truncCell(r.evidence_basis) }),
      c('verification_status', 'Verification', { render: r => statusBadge(r.verification_status) })
    ],
    searchFields: ['company_name', 'ticker'],
    searchPlaceholder: 'Search company or ticker…',
    sort: { key: 'clinical_relevant_count', dir: 'desc' },
    filters: [
      { key: 'cls', label: 'All listing classes', field: 'us_investable_class' },
      { key: 'min', label: 'Minimum clinical-relevant', options: () => ['1', '5', '10', '20'],
        match: (r, v) => +r.clinical_relevant_count >= +v }
    ]
  });

  /* Verification audit */
  DataTable({
    id: 'crosscheck', mount: '#crosscheck-view', csv: 'data/verification_crosscheck.csv',
    columns: [
      c('decision_id', 'ID', { core: true, render: r => `<code>${escapeHtml(r.decision_id)}</code>` }),
      c('crosscheck_status', 'Audit result', { core: true, render: r => statusBadge(r.crosscheck_status) }),
      c('company_name', 'Company (master)', { core: true, trunc: true }),
      c('drug_brand', 'Drug (master)', { core: true }),
      c('decision_date', 'Date (master)', { core: true, render: r => `<span class="num-strong">${escapeHtml(r.decision_date)}</span>` }),
      c('openfda_decision_date', 'Date (openFDA)', { core: true, render: r => escapeHtml(r.openfda_decision_date) }),
      c('openfda_brand_name', 'Brand (openFDA)', { core: true, trunc: true }),
      c('openfda_sponsor_name', 'Sponsor (openFDA)', { trunc: true }),
      c('application_number', 'Application', { core: true, render: r => `<code>${escapeHtml(r.application_number)}</code>` }),
      c('openfda_source_url', 'Primary source', { core: true, render: r => linkify(r.openfda_source_url, 'Drugs@FDA'), detail: r => r.openfda_source_url }),
      c('detail', 'Audit detail', { core: true, trunc: true, render: r => truncCell(r.detail) })
    ],
    searchFields: ['decision_id', 'company_name', 'drug_brand', 'application_number', 'detail'],
    searchPlaceholder: 'Search by drug, company or decision ID…',
    sort: { key: 'decision_date', dir: 'desc' }, pageSize: 25,
    filters: [
      { key: 'status', label: 'All audit results', field: 'crosscheck_status' },
      yearFilter('decision_date')
    ]
  });

  /* Pipeline Tracker Full */
  DataTable({
    id: 'pipeline-full', mount: '#pipeline-full-view', csv: 'data/pipeline_tracker.csv',
    columns: [
      c('company_name', 'Company', { core: true, trunc: true }),
      c('ticker', 'Ticker', { core: true, render: r => `<strong>${escapeHtml(r.ticker)}</strong>` }),
      c('total_programs', 'Total Programs', { core: true, num: true, render: r => num(r.total_programs,0) }),
      c('approved', 'Approved', { core: true, num: true, render: r => num(r.approved,0) }),
      c('phase_3', 'Phase 3', { core: true, num: true, render: r => num(r.phase_3,0) }),
      c('phase_2', 'Phase 2', { num: true, render: r => num(r.phase_2,0) }),
      c('phase_1', 'Phase 1', { num: true, render: r => num(r.phase_1,0) }),
      c('preclinical', 'Preclinical', { num: true, render: r => num(r.preclinical,0) }),
      c('paused_hold', 'Paused/Hold', { core: true, num: true, render: r => num(r.paused_hold,0) }),
      c('advanced_next_phase', 'Advanced', { core: true, num: true, render: r => num(r.advanced_next_phase,0) }),
      c('success_rate_pct', 'Success %', { core: true, num: true, render: r => pctCell(r.success_rate_pct) }),
      c('source_url_1', 'Source', { render: r => linkify(r.source_url_1,'pipeline'), detail: r => r.source_url_1 }),
      c('verification_status', 'Verification', { core: true, render: r => statusBadge(r.verification_status) }),
      c('notes', 'Notes', { trunc: true, render: r => truncCell(r.notes) })
    ],
    searchFields: ['company_name','ticker','notes'],
    searchPlaceholder: 'Search pipeline…',
    sort: { key: 'total_programs', dir: 'desc' },
    filters: [{ key: 'status', label: 'All verification', field: 'verification_status' }]
  });

  /* PDUFA Calendar Full */
  DataTable({
    id: 'pdufa-full', mount: '#pdufa-full-view', csv: 'data/upcoming_pdufa_calendar.csv',
    columns: [
      c('company_name', 'Company', { core: true, trunc: true }),
      c('ticker', 'Ticker', { core: true, render: r => `<strong>${escapeHtml(r.ticker)}</strong>` }),
      c('drug_brand', 'Drug', { core: true }),
      c('drug_generic', 'Generic', { core: true }),
      c('indication', 'Indication', { core: true, trunc: true }),
      c('phase', 'Phase', { core: true }),
      c('pdufa_date', 'PDUFA Date', { core: true, render: r => `<span class="num-strong">${escapeHtml(r.pdufa_date)}</span>` }),
      c('submission_type', 'Submission', { core: true }),
      c('review_pathway', 'Pathway', { core: true, render: r => r.review_pathway ? `<span class="badge info">${escapeHtml(r.review_pathway)}</span>` : '' }),
      c('source_url_1', 'Source 1', { render: r => linkify(r.source_url_1,'FDA source'), detail: r => r.source_url_1 }),
      c('source_url_2', 'Source 2', { render: r => linkify(r.source_url_2,'verify'), detail: r => r.source_url_2 }),
      c('verification_status', 'Verification', { core: true, render: r => statusBadge(r.verification_status) }),
      c('notes', 'Notes', { trunc: true, render: r => truncCell(r.notes) }),
      c('exchange', 'Exchange', { core: true })
    ],
    searchFields: ['company_name','drug_brand','indication','ticker'],
    searchPlaceholder: 'Search PDUFA…',
    sort: { key: 'pdufa_date', dir: 'asc' },
    filters: [yearFilter('pdufa_date'), { key: 'pathway', label: 'All pathways', field: 'review_pathway' }]
  });

  /* Clinical Trial Endpoints */
  DataTable({
    id: 'trials', mount: '#trials-view', csv: 'data/clinical_trial_endpoints.csv',
    columns: [
      c('company_name', 'Company', { core: true }),
      c('ticker', 'Ticker', { core: true, render: r => `<strong>${escapeHtml(r.ticker)}</strong>` }),
      c('drug', 'Drug', { core: true, trunc: true }),
      c('indication', 'Indication', { core: true, trunc: true }),
      c('phase', 'Phase', { core: true }),
      c('endpoint_type', 'Endpoint', { core: true }),
      c('expected_date', 'Expected', { core: true, render: r => `<span class="num-strong">${escapeHtml(r.expected_date)}</span>` }),
      c('status', 'Status', { core: true, render: r => statusBadge(r.status) }),
      c('source_url_1', 'Source 1', { render: r => linkify(r.source_url_1,'source'), detail: r => r.source_url_1 }),
      c('source_url_2', 'Source 2', { render: r => linkify(r.source_url_2,'source2'), detail: r => r.source_url_2 }),
      c('verification_status', 'Verification', { core: true, render: r => statusBadge(r.verification_status) }),
      c('notes', 'Notes', { trunc: true, render: r => truncCell(r.notes) })
    ],
    searchFields: ['company_name','drug','indication','ticker'],
    searchPlaceholder: 'Search trial endpoints…',
    sort: { key: 'expected_date', dir: 'asc' },
    filters: [{ key: 'phase', label: 'All phases', field: 'phase' }]
  });

  /* Prices */
  DataTable({
    id: 'prices', mount: '#prices-view', csv: 'data/stock_price_snapshots.csv',
    columns: [
      c('ticker', 'Ticker', { core: true, render: r => `<strong>${escapeHtml(r.ticker)}</strong>` }),
      c('company', 'Company', { core: true, trunc: true }),
      c('decision_date', 'Decision date', { core: true, render: r => `<span class="num-strong">${escapeHtml(r.decision_date)}</span>` }),
      c('decision_type', 'Type', { core: true }),
      c('close_before', 'Close before', { core: true, num: true, render: r => num(r.close_before, 2) }),
      c('date_before', 'Date before', { num: true }),
      c('close_on_or_after', 'Close on/after', { core: true, num: true, render: r => num(r.close_on_or_after, 2) }),
      c('date_on_or_after', 'Date on/after', { num: true }),
      c('close_few_days_later', 'Close later', { num: true, render: r => num(r.close_few_days_later, 2) }),
      c('date_few_days_later', 'Date later', { num: true }),
      c('pct_change_on_decision', '% change', { core: true, num: true, render: r => pctCell(r.pct_change_on_decision) }),
      c('source_url', 'Source (raw API)', { render: r => linkify(r.source_url, 'Yahoo chart API'), detail: r => r.source_url }),
      c('verification_status', 'Status', { core: true, render: r => statusBadge(r.verification_status) }),
      c('notes', 'Notes', { trunc: true, render: r => truncCell(r.notes) })
    ],
    searchFields: ['ticker', 'company', 'decision_type'],
    searchPlaceholder: 'Search ticker or company…',
    sort: { key: 'decision_date', dir: 'desc' },
    filters: [yearFilter('decision_date'), { key: 'type', label: 'All decision types', field: 'decision_type' }]
  });

  /* Numeric scorecards */
  const scoreTable = DataTable({
    id: 'scores', mount: '#scores-view', csv: 'data/company_scores.csv',
    columns: scoreColumns(),
    searchFields: ['company_name', 'ticker'],
    searchPlaceholder: 'Search company or ticker…',
    sort: { key: 'total_score_0_100', dir: 'desc' },
    filters: [
      { key: 'conf', label: 'All confidence levels', field: 'confidence' },
      { key: 'cls', label: 'All listing classes', field: 'us_investable_class' },
      { key: 'min', label: 'Minimum decisions tracked', options: () => ['1', '2', '3', '5'],
        match: (r, v) => +r.decisions_tracked >= +v }
    ]
  });

  /* Qualitative pipeline cards */
  loadCSV('data/company_scorecards.csv').then(({ records }) => drawPipelineCards(records)).catch(() => {
    document.getElementById('cards-deep').innerHTML = '<div class="notice">company_scorecards.csv could not be loaded.</div>';
  });
}).catch(err => {
  document.querySelector('main').insertAdjacentHTML('afterbegin',
    `<div class="notice">Data load failed: ${escapeHtml(err.message)}</div>`);
});

openTabFromHash();
es', field: 'us_investable_class' },
      { key: 'min', label: 'Minimum decisions tracked', options: () => ['1', '2', '3', '5'],
        match: (r, v) => +r.decisions_tracked >= +v }
    ]
  });

  /* Qualitative pipeline cards */
  loadCSV('data/company_scorecards.csv').then(({ records }) => drawPipelineCards(records)).catch(() => {
    document.getElementById('cards-deep').innerHTML = '<div class="notice">company_scorecards.csv could not be loaded.</div>';
  });
}).catch(err => {
  document.querySelector('main').insertAdjacentHTML('afterbegin',
    `<div class="notice">Data load failed: ${escapeHtml(err.message)}</div>`);
});

openTabFromHash();
