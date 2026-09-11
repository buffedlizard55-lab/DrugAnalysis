// Minimal, dependency-free CSV loader + table renderer for the DrugAnalysis site.

function parseCSV(text) {
  const rows = [];
  let row = [];
  let field = "";
  let inQuotes = false;
  for (let i = 0; i < text.length; i++) {
    const c = text[i];
    if (inQuotes) {
      if (c === '"') {
        if (text[i + 1] === '"') { field += '"'; i++; }
        else { inQuotes = false; }
      } else {
        field += c;
      }
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
  const records = rows.slice(1).filter(r => r.length === header.length && r.some(v => v !== "")).map(r => {
    const obj = {};
    header.forEach((h, idx) => obj[h] = r[idx]);
    return obj;
  });
  return { header, records };
}

async function loadCSV(path) {
  const res = await fetch(path);
  const text = await res.text();
  return parseCSV(text);
}

function statusBadge(status) {
  if (!status) return '<span class="badge neutral">—</span>';
  const s = status.toLowerCase();
  if (s.includes('correction') || s.includes('flag')) return `<span class="badge flagged">${escapeHtml(status)}</span>`;
  if (s.includes('caveat') || s.includes('foreign') || s.includes('no public') || s.includes('unavailable') || s.includes('partial')) return `<span class="badge caveat">${escapeHtml(status)}</span>`;
  if (s.includes('verified')) return `<span class="badge verified">${escapeHtml(status)}</span>`;
  return `<span class="badge neutral">${escapeHtml(status)}</span>`;
}

function escapeHtml(str) {
  if (str === undefined || str === null) return "";
  return String(str)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");
}

function linkify(url, label) {
  if (!url) return "";
  return `<a href="${escapeHtml(url)}" target="_blank" rel="noopener">${escapeHtml(label || 'source')}</a>`;
}

function pctCell(v) {
  if (v === undefined || v === null || v === "") return "";
  const num = parseFloat(v);
  if (isNaN(num)) return escapeHtml(v);
  const cls = num >= 0 ? "pct-pos" : "pct-neg";
  const sign = num >= 0 ? "+" : "";
  return `<span class="${cls}">${sign}${num.toFixed(2)}%</span>`;
}

function renderTable(tableEl, header, rows, columnDefs) {
  const thead = tableEl.querySelector('thead');
  const tbody = tableEl.querySelector('tbody');
  thead.innerHTML = '<tr>' + columnDefs.map(c => `<th>${c.label}</th>`).join('') + '</tr>';
  tbody.innerHTML = rows.map(r => {
    return '<tr>' + columnDefs.map(c => `<td>${c.render(r)}</td>`).join('') + '</tr>';
  }).join('');
}

function filterRows(rows, query, fields) {
  if (!query) return rows;
  const q = query.toLowerCase();
  return rows.filter(r => fields.some(f => (r[f] || '').toLowerCase().includes(q)));
}

// ----- Tabs -----
document.querySelectorAll('.tab-btn').forEach(btn => {
  btn.addEventListener('click', () => {
    document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
    document.querySelectorAll('.tab-panel').forEach(p => p.classList.remove('active'));
    btn.classList.add('active');
    document.getElementById(btn.dataset.tab).classList.add('active');
  });
});

// ----- Core Analysis Table -----
let coreRecords = [];
loadCSV('data/core_analysis_table.csv').then(({ records }) => {
  coreRecords = records;
  const types = [...new Set(records.map(r => r.decision_type))].sort();
  const sel = document.getElementById('core-filter-type');
  types.forEach(t => {
    const opt = document.createElement('option');
    opt.value = t; opt.textContent = t;
    sel.appendChild(opt);
  });
  drawCore();
});

function drawCore() {
  const q = document.getElementById('core-search').value;
  const typeFilter = document.getElementById('core-filter-type').value;
  let rows = filterRows(coreRecords, q, ['company_name', 'drug_name', 'indication', 'ticker']);
  if (typeFilter) rows = rows.filter(r => r.decision_type === typeFilter);
  renderTable(document.getElementById('core-table'), null, rows, [
    { label: 'Company', render: r => escapeHtml(r.company_name) },
    { label: 'Ticker', render: r => escapeHtml(r.ticker) },
    { label: 'Drug', render: r => escapeHtml(r.drug_name) },
    { label: 'Decision', render: r => escapeHtml(r.decision_type) },
    { label: 'Date', render: r => escapeHtml(r.decision_date) },
    { label: 'Indication', render: r => escapeHtml(r.indication) },
    { label: 'Price Before', render: r => escapeHtml(r.stock_price_before) },
    { label: 'Price After', render: r => escapeHtml(r.stock_price_after) },
    { label: '% Change', render: r => pctCell(r.pct_change) },
    { label: 'Price Data', render: r => statusBadge(r.price_data_status) },
    { label: 'Pipeline Success Summary', render: r => escapeHtml(r.company_success_rate_summary) },
    { label: 'FDA Source', render: r => linkify(r.fda_source_url, 'FDA link') },
    { label: 'Verification', render: r => statusBadge(r.verification_status) },
  ]);
}
document.getElementById('core-search').addEventListener('input', drawCore);
document.getElementById('core-filter-type').addEventListener('change', drawCore);

// ----- Approvals Table -----
let approvalRecords = [];
loadCSV('data/fda_decisions_master.csv').then(({ records }) => {
  approvalRecords = records;
  drawApprovals();
});

function drawApprovals() {
  const q = document.getElementById('approvals-search').value;
  const rows = filterRows(approvalRecords, q, ['company_name', 'drug_brand', 'drug_generic', 'ticker', 'indication']);
  renderTable(document.getElementById('approvals-table'), null, rows, [
    { label: 'ID', render: r => escapeHtml(r.decision_id) },
    { label: 'Company', render: r => escapeHtml(r.company_name) },
    { label: 'Ticker', render: r => escapeHtml(r.ticker) },
    { label: 'Exchange', render: r => escapeHtml(r.exchange) },
    { label: 'Drug (brand)', render: r => escapeHtml(r.drug_brand) },
    { label: 'Generic', render: r => escapeHtml(r.drug_generic) },
    { label: 'Decision', render: r => escapeHtml(r.decision_type) },
    { label: 'Date', render: r => escapeHtml(r.decision_date) },
    { label: 'Indication', render: r => escapeHtml(r.indication) },
    { label: 'Pathway', render: r => escapeHtml(r.review_pathway) },
    { label: 'Source 1', render: r => linkify(r.source_url_1, 'FDA label') },
    { label: 'Source 2', render: r => linkify(r.source_url_2, 'secondary') },
    { label: 'Verification', render: r => statusBadge(r.verification_status) },
    { label: 'Notes', render: r => escapeHtml(r.notes) },
  ]);
}
document.getElementById('approvals-search').addEventListener('input', drawApprovals);

// ----- CRLs Table -----
loadCSV('data/fda_crl_master.csv').then(({ records }) => {
  renderTable(document.getElementById('crls-table'), null, records, [
    { label: 'ID', render: r => escapeHtml(r.crl_id) },
    { label: 'Company', render: r => escapeHtml(r.company_name) },
    { label: 'Ticker', render: r => escapeHtml(r.ticker) },
    { label: 'Drug', render: r => escapeHtml(r.drug_name) },
    { label: 'Indication', render: r => escapeHtml(r.indication) },
    { label: 'CRL Date', render: r => escapeHtml(r.crl_date) },
    { label: 'Reason', render: r => escapeHtml(r.reason_category) },
    { label: 'Stock Reaction', render: r => escapeHtml(r.stock_reaction) },
    { label: 'Source 1', render: r => linkify(r.source_url_1, 'source') },
    { label: 'Source 2', render: r => linkify(r.source_url_2, 'secondary') },
    { label: 'Verification', render: r => statusBadge(r.verification_status) },
    { label: 'Notes', render: r => escapeHtml(r.notes) },
  ]);
});

// ----- Stock Price Snapshots -----
loadCSV('data/stock_price_snapshots.csv').then(({ records }) => {
  renderTable(document.getElementById('prices-table'), null, records, [
    { label: 'Ticker', render: r => escapeHtml(r.ticker) },
    { label: 'Company', render: r => escapeHtml(r.company) },
    { label: 'Decision Date', render: r => escapeHtml(r.decision_date) },
    { label: 'Type', render: r => escapeHtml(r.decision_type) },
    { label: 'Close Before', render: r => escapeHtml(r.close_before) },
    { label: 'Date Before', render: r => escapeHtml(r.date_before) },
    { label: 'Close On/After', render: r => escapeHtml(r.close_on_or_after) },
    { label: 'Date On/After', render: r => escapeHtml(r.date_on_or_after) },
    { label: '% Change', render: r => pctCell(r.pct_change_on_decision) },
    { label: 'Source', render: r => linkify(r.source_url, 'Yahoo Finance') },
    { label: 'Status', render: r => statusBadge(r.verification_status) },
    { label: 'Notes', render: r => escapeHtml(r.notes) },
  ]);
});

// ----- Company Scorecards (cards) -----
loadCSV('data/company_scorecards.csv').then(({ records }) => {
  const container = document.getElementById('scorecards-cards');
  container.innerHTML = records.map(r => `
    <div class="card">
      <h3>${escapeHtml(r.company_name)}</h3>
      <div class="ticker">${escapeHtml(r.ticker)} ${statusBadge(r.verification_status)}</div>
      <div class="stat-row"><span>Total programs tracked</span><strong>${escapeHtml(r.total_pipeline_programs_tracked)}</strong></div>
      <div class="stat-row"><span>Approved</span><strong>${escapeHtml(r.approved_count)}</strong></div>
      <div class="stat-row"><span>Advancing to next phase</span><strong>${escapeHtml(r.advanced_to_next_phase_count)}</strong></div>
      <div class="stat-row"><span>Paused / clinical hold</span><strong>${escapeHtml(r.paused_or_clinical_hold_count)}</strong></div>
      <div class="stat-row"><span>CRLs (rejections)</span><strong>${escapeHtml(r.crl_rejected_count)}</strong></div>
      <div class="phase-details">${escapeHtml(r.phase_details)}</div>
      <div class="card-links">
        ${linkify(r.source_url_1, 'Source 1')}
        ${linkify(r.source_url_2, 'Source 2')}
      </div>
      <div class="phase-details"><em>${escapeHtml(r.notes)}</em></div>
    </div>
  `).join('');
});
