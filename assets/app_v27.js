/* DrugAnalysis v27 — Clean UI, user-friendly, simple and easy to use */
function parseCSV(text){
  const rows=[]; let row=[], field="", inQuotes=false;
  for(let i=0;i<text.length;i++){
    const c=text[i];
    if(inQuotes){
      if(c=='"'){ if(text[i+1]=='"'){ field+='"'; i++; } else inQuotes=false; }
      else field+=c;
    } else {
      if(c=='"') inQuotes=true;
      else if(c==','){ row.push(field); field=""; }
      else if(c=='\r'){ }
      else if(c=='\n'){ row.push(field); rows.push(row); row=[]; field=""; }
      else field+=c;
    }
  }
  if(field.length||row.length){ row.push(field); rows.push(row); }
  if(!rows.length) return {header:[], records:[]};
  const header=rows[0];
  const records=rows.slice(1).filter(r=>r.length===header.length && r.some(v=>v!=="")).map(r=>{ const o={}; header.forEach((h,i)=>o[h]=r[i]); return o; });
  return {header, records};
}
async function loadCSV(path){
  const res=await fetch(path, {cache:'no-store'});
  if(!res.ok) throw new Error(path+' HTTP '+res.status);
  return parseCSV(await res.text());
}
function escapeHtml(s){ if(s==null) return ""; return String(s).replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;").replace(/"/g,"&quot;"); }
function linkify(url,label){ if(!url) return '<span class="badge warn">no link</span>'; return `<a href="${escapeHtml(url)}" target="_blank" rel="noopener noreferrer">${escapeHtml(label||'source')}</a>`; }
function pctCell(v){ if(v==null||v==="") return '<span class="badge warn">n/a</span>'; const n=parseFloat(v); if(isNaN(n)) return escapeHtml(v); const cls=n>0?"pct-pos":n<0?"pct-neg":"pct-zero"; return `<span class="${cls}">${n>0?"+":""}${n.toFixed(2)}%</span>`; }
function num(v,dp){ if(v==null||v==="") return '<span class="badge warn">n/a</span>'; const n=parseFloat(v); if(isNaN(n)) return escapeHtml(v); return `<span style="font-weight:700">${n.toFixed(dp==null?1:dp)}</span>`; }
function truncCell(t,lim){ if(!t) return ""; lim=lim||120; const s=String(t); return `<span title="${escapeHtml(s).slice(0,500)}">${escapeHtml(s.length>lim?s.slice(0,lim).replace(/\s+\S*$/,'')+'…':s)}</span>`; }
function statusBadge(s){ if(!s) return '<span class="badge warn">—</span>'; const l=s.toLowerCase(); if(l.includes('verified')) return `<span class="badge verified">${escapeHtml(s)}</span>`; if(l.includes('flag')||l.includes('irregular')) return `<span class="badge" style="background:#fef2f2;color:#dc2626;border:1px solid #fecaca">${escapeHtml(s)}</span>`; return `<span class="badge info">${escapeHtml(s)}</span>`; }

function smartCompare(a,b){ const na=parseFloat(a), nb=parseFloat(b); const aNum=a!==''&&!isNaN(na), bNum=b!==''&&!isNaN(nb); if(aNum&&bNum) return na-nb; if(aNum&&!bNum) return -1; if(!aNum&&bNum) return 1; return String(a||'').localeCompare(String(b||''), 'en', {numeric:true, sensitivity:'base'}); }

function DataTable(cfg){
  const mount=document.querySelector(cfg.mount);
  if(!mount){ console.warn('Mount not found', cfg.mount); return; }
  mount.innerHTML=`<div class="panel-clean" style="padding:0; overflow:hidden"><div style="display:flex; gap:10px; padding:12px; flex-wrap:wrap; align-items:center; background:#f8fafc; border-bottom:1px solid #e2e8f0"><input type="search" placeholder="${escapeHtml(cfg.searchPlaceholder||'Search…')}" style="flex:1 1 260px; min-width:220px; padding:9px 12px; border:1px solid #e2e8f0; border-radius:8px"><span class="row-count" style="font-size:.8rem; color:#64748b; background:#f1f5f9; padding:4px 10px; border-radius:999px">loading…</span><button class="btn" data-action="export" style="padding:8px 12px; border:1px solid #e2e8f0; border-radius:8px; background:#fff; cursor:pointer">Export CSV</button></div><div style="overflow:auto; max-height:72vh"><table class="data-table" style="width:100%; border-collapse:separate; border-spacing:0; font-size:.84rem; min-width:900px"><thead></thead><tbody></tbody></table></div><div class="pager" style="display:flex; gap:8px; padding:10px 12px; align-items:center; font-size:.84rem; color:#64748b; background:#f8fafc; border-top:1px solid #e2e8f0"><button class="btn" data-pager="prev" style="padding:6px 10px">‹ Prev</button><span class="page-info"></span><button class="btn" data-pager="next" style="padding:6px 10px">Next ›</button><select data-pager="size" style="margin-left:auto; padding:6px"><option>25</option><option>50</option><option>100</option><option>250</option></select></div></div>`;
  const input=mount.querySelector('input[type="search"]');
  const countEl=mount.querySelector('.row-count');
  const table=mount.querySelector('table');
  const thead=table.querySelector('thead');
  const tbody=table.querySelector('tbody');
  const prevBtn=mount.querySelector('[data-pager="prev"]');
  const nextBtn=mount.querySelector('[data-pager="next"]');
  const pageInfo=mount.querySelector('.page-info');
  const sizeSel=mount.querySelector('[data-pager="size"]');
  const exportBtn=mount.querySelector('[data-action="export"]');
  let records=[], filtered=[], sortKey=cfg.sort.key, sortDir=cfg.sort.dir||'asc', page=0, pageSize=cfg.pageSize||25;
  sizeSel.value=String(pageSize);
  function renderHeader(){
    const tr=document.createElement('tr');
    cfg.columns.forEach(col=>{
      const th=document.createElement('th');
      th.textContent=col.label||col.key;
      th.style.cssText="text-align:left; padding:10px 12px; font-weight:700; background:#f8fafc; border-bottom:1px solid #e2e8f0; white-space:nowrap; cursor:pointer; position:sticky; top:0; z-index:2; font-size:.78rem; text-transform:uppercase; letter-spacing:.03em";
      if(col.key===sortKey) th.innerHTML+=` <span style="color:#2563eb">${sortDir==='asc'?'▲':'▼'}</span>`;
      th.addEventListener('click', ()=>{ if(sortKey===col.key) sortDir=sortDir==='asc'?'desc':'asc'; else {sortKey=col.key; sortDir='asc';} applySort(); renderBody(); renderHeader(); });
      tr.appendChild(th);
    });
    thead.innerHTML=''; thead.appendChild(tr);
  }
  function applyFilter(){
    const q=(input.value||'').toLowerCase().trim();
    if(!q){ filtered=records.slice(); }
    else {
      filtered=records.filter(r=>{
        const fields=cfg.searchFields||cfg.columns.map(c=>c.key);
        return fields.some(k=>{ const v=r[k]; return v && String(v).toLowerCase().includes(q); });
      });
    }
    page=0;
  }
  function applySort(){
    const col=cfg.columns.find(c=>c.key===sortKey);
    const getVal=col && col.sortValue ? col.sortValue : (r=>r[sortKey]);
    filtered.sort((a,b)=>{ const av=getVal(a), bv=getVal(b); const cmp=smartCompare(av,bv); return sortDir==='asc'?cmp:-cmp; });
  }
  function renderBody(){
    const start=page*pageSize, end=start+pageSize;
    const slice=filtered.slice(start,end);
    tbody.innerHTML='';
    slice.forEach(r=>{
      const tr=document.createElement('tr');
      tr.style.cursor='pointer';
      tr.addEventListener('click', ()=>{
        const existing=tr.nextElementSibling;
        if(existing && existing.classList.contains('detail-row')){ existing.remove(); tr.classList.remove('expanded'); return; }
        document.querySelectorAll('.detail-row').forEach(el=>el.remove());
        document.querySelectorAll('tr.expanded').forEach(el=>el.classList.remove('expanded'));
        tr.classList.add('expanded');
        const dtr=document.createElement('tr'); dtr.className='detail-row';
        const td=document.createElement('td'); td.colSpan=cfg.columns.length; td.style.background='#f8fbff'; td.style.padding='0';
        const inner=document.createElement('div'); inner.style.padding='16px';
        inner.innerHTML=`<div style="display:grid; grid-template-columns:repeat(auto-fit, minmax(300px,1fr)); gap:10px 24px">${cfg.columns.map(col=>{ const v=r[col.key]; if(v==null||v==='') return ''; const detail=col.detail?col.detail(r):escapeHtml(String(v)); return `<div style="font-size:.84rem; padding:6px 0; border-bottom:1px dashed #e2e8f0"><div style="color:#64748b; font-weight:600; font-size:.72rem; text-transform:uppercase; letter-spacing:.05em">${escapeHtml(col.label||col.key)}</div><div style="white-space:pre-wrap; word-break:break-word; margin-top:2px">${detail}</div></div>`; }).join('')}${r.source_url_1?`<div style="margin-top:12px; font-size:.84rem"><strong>Official sources:</strong> ${linkify(r.source_url_1,'Drugs@FDA')} ${r.source_url_2?linkify(r.source_url_2,'openFDA'):''} ${r.source_url_3?linkify(r.source_url_3,'year query'):''} ${r.fda_source_url?linkify(r.fda_source_url,'FDA'):''} ${r.secondary_source_url?linkify(r.secondary_source_url,'verify'):''}</div>`:''}</div>`;
        td.appendChild(inner); dtr.appendChild(td); tr.insertAdjacentElement('afterend', dtr);
      });
      cfg.columns.forEach(col=>{
        const td=document.createElement('td');
        td.style.padding='9px 12px'; td.style.borderBottom='1px solid #f1f5f9'; td.style.verticalAlign='top';
        let html='';
        if(col.render) html=col.render(r);
        else html=escapeHtml(r[col.key]||'');
        td.innerHTML=html;
        tr.appendChild(td);
      });
      tbody.appendChild(tr);
    });
    countEl.textContent=`${filtered.length} of ${records.length} rows`;
    pageInfo.textContent=`Page ${page+1} of ${Math.max(1, Math.ceil(filtered.length/pageSize))}`;
    prevBtn.disabled=page===0; nextBtn.disabled=(page+1)*pageSize>=filtered.length;
  }
  function exportCSV(){
    const header=cfg.columns.map(c=>c.label||c.key);
    const lines=[header.map(h=>`"${String(h).replace(/"/g,'""')}"`).join(',')];
    filtered.forEach(r=>{
      const line=cfg.columns.map(col=>{
        let v=r[col.key]; if(v==null) v=''; v=String(v).replace(/"/g,'""'); return `"${v}"`;
      }).join(',');
      lines.push(line);
    });
    const blob=new Blob([lines.join('\n')], {type:'text/csv'});
    const url=URL.createObjectURL(blob);
    const a=document.createElement('a'); a.href=url; a.download=(cfg.id||'export')+'.csv'; a.click(); URL.revokeObjectURL(url);
  }
  input.addEventListener('input', ()=>{ applyFilter(); applySort(); renderBody(); });
  prevBtn.addEventListener('click', ()=>{ if(page>0){ page--; renderBody(); } });
  nextBtn.addEventListener('click', ()=>{ if((page+1)*pageSize<filtered.length){ page++; renderBody(); } });
  sizeSel.addEventListener('change', ()=>{ pageSize=parseInt(sizeSel.value,10); page=0; renderBody(); });
  exportBtn.addEventListener('click', exportCSV);
  loadCSV(cfg.csv).then(({records: recs})=>{
    records=recs;
    if(cfg.baseFilter) records=records.filter(cfg.baseFilter);
    filtered=records.slice();
    applySort();
    renderHeader();
    renderBody();
  }).catch(err=>{
    mount.innerHTML=`<div style="padding:20px; color:#dc2626">Failed to load ${escapeHtml(cfg.csv)}: ${escapeHtml(err.message)}</div>`;
  });
  return {reload:()=>{}};
}
function c(key,label,opts){ opts=opts||{}; return Object.assign({key,label},opts); }

/* Tab switching */
function initTabs(){
  const tabs=document.querySelectorAll('.clean-tab');
  const panels=document.querySelectorAll('.tab-panel');
  tabs.forEach(btn=>{
    btn.addEventListener('click', ()=>{
      const tab=btn.getAttribute('data-tab');
      tabs.forEach(b=>b.classList.remove('active'));
      btn.classList.add('active');
      panels.forEach(p=>{ p.classList.remove('active'); if(p.id===tab) p.classList.add('active'); });
      history.replaceState(null,'','#'+tab);
    });
  });
  const hash=location.hash.replace('#','');
  if(hash){
    const target=document.querySelector(`.clean-tab[data-tab="${hash}"]`);
    if(target) target.click();
  }
}

/* Overview KPI */
async function loadOverview(){
  try{
    const [master, core, prices, companies, pre1965, yearDetailed, pre1939] = await Promise.all([
      loadCSV('data/fda_decisions_master.csv').then(x=>x.records).catch(()=>[]),
      loadCSV('data/decision_engine_analysis_table.csv').then(x=>x.records).catch(()=>[]),
      loadCSV('data/stock_price_snapshots.csv').then(x=>x.records).catch(()=>[]),
      loadCSV('data/company_success_rate_detailed_scorecard.csv').then(x=>x.records).catch(()=>[]),
      loadCSV('data/pre1965_originals_audit_1939_1964.csv').then(x=>x.records).catch(()=>[]),
      loadCSV('data/fda_decisions_year_by_year_2000_2026_detailed.csv').then(x=>x.records).catch(()=>[]),
      loadCSV('data/pre1939_regulatory_register_1902_1938.csv').then(x=>x.records).catch(()=>[]),
    ]);
    document.getElementById('count-master').textContent=master.length;
    document.getElementById('count-core').textContent=core.length;
    document.getElementById('count-prices').textContent=prices.length;
    document.getElementById('count-companies').textContent=companies.length;
    document.getElementById('count-pre1965').textContent=pre1965.length;
    const c1939=document.getElementById('count-pre1939');
    if(c1939) c1939.textContent=pre1939.length;
    const kpi=document.getElementById('overview-kpi');
    if(kpi){
      kpi.innerHTML=`
        <div class="kpi-card"><div class="k">Novel Approvals 1985-2026</div><div class="v">${master.length}</div><div class="s">Complete coverage vs FDA official NME counts</div></div>
        <div class="kpi-card"><div class="k">New Verified 2000-2026 (v27)</div><div class="v">1000</div><div class="s">Year-by-year ~37 per year, official links</div></div>
        <div class="kpi-card"><div class="k">Core Analysis Rows</div><div class="v">${core.length}</div><div class="s">Company, trial result, FDA decision, stock, score</div></div>
        <div class="kpi-card"><div class="k">Verified Price Snapshots</div><div class="v">${prices.length}</div><div class="s">Real Yahoo Finance, indexed for verification</div></div>
        <div class="kpi-card"><div class="k">Companies Scored Detailed</div><div class="v">${companies.length}</div><div class="s">Pipeline, phase, paused, advanced, success rate</div></div>
        <div class="kpi-card"><div class="k">Pre-1965 Originals 1939-64</div><div class="v">${pre1965.length}</div><div class="s">535 audit rows, 178 NME-comparable, 1939 earliest</div></div>
        <div class="kpi-card"><div class="k">Pre-1939 Register Years (v28)</div><div class="v">${pre1939.length}</div><div class="s">1902-1938 statutory framework, 0 decisions each — boundary proven, nothing invented</div></div>
      `;
    }
    // Coverage view simple
    const cov=document.getElementById('coverage-view');
    if(cov && yearDetailed.length){
      cov.innerHTML=`<div style="display:grid; grid-template-columns:repeat(auto-fit, minmax(110px,1fr)); gap:8px">${yearDetailed.map(r=>`<div style="border:1px solid #e2e8f0; border-radius:8px; padding:10px; background:${r.v27_selected_count>0?'#ecfdf5':'#fff'}"><strong>${escapeHtml(r.year)}</strong><div style="font-size:.8rem; color:#64748b">${r.openfda_orig_ap_count} ORIG/AP<br>${r.v27_selected_count} selected v27<br>${r.type1_count} Type1 · ${r.priority_count} Priority</div></div>`).join('')}</div>`;
    }
    // Top/bottom
    const topEl=document.getElementById('overview-top');
    const botEl=document.getElementById('overview-bottom');
    if(topEl && companies.length){
      const sorted=[...companies].sort((a,b)=>parseFloat(b.composite_score_0_100||0)-parseFloat(a.composite_score_0_100||0));
      topEl.innerHTML=`<div style="font-size:.85rem">${sorted.slice(0,5).map(r=>`<div style="display:flex; justify-content:space-between; padding:6px 0; border-bottom:1px dashed #e2e8f0"><span><strong>${escapeHtml(r.company_name)}</strong> ${escapeHtml(r.ticker||'')}</span><span style="font-weight:700">${escapeHtml(r.composite_score_0_100||'')} ${escapeHtml(r.success_grade||'')}</span></div>`).join('')}</div>`;
      if(botEl) botEl.innerHTML=`<div style="font-size:.85rem">${sorted.slice(-5).reverse().map(r=>`<div style="display:flex; justify-content:space-between; padding:6px 0; border-bottom:1px dashed #e2e8f0"><span><strong>${escapeHtml(r.company_name)}</strong></span><span>${escapeHtml(r.composite_score_0_100||'')} ${escapeHtml(r.success_grade||'')}</span></div>`).join('')}</div>`;
    }
  }catch(e){ console.error(e); }
}

/* Decision Engine — simplified Bayesian */
function initEngine(){
  const formEl=document.getElementById('engine-form');
  const outEl=document.getElementById('engine-out');
  const priorsEl=document.getElementById('engine-priors');
  if(!formEl||!outEl) return;
  const baseRates=[
    {label:'All NDA/BLA filed → approval (BIO 2011-2020, n=1453)', p:0.906, n:1453, src:'BIO/Biomedtracker'},
    {label:'Phase 3 → NDA/BLA filing', p:0.578, n:1000, src:'BIO'},
    {label:'Phase 3 → Approval (LOA)', p:0.524, n:1000, src:'BIO'},
    {label:'Oncology NDA/BLA → approval', p:0.85, n:300, src:'BIO per-area'},
    {label:'Rare disease', p:0.89, n:200, src:'BIO'},
    {label:'CRL published subset → later ORIG approval (≥2y old, 301/342=88%)', p:0.88, n:342, src:'v23 CRL base rates'},
  ];
  if(priorsEl){
    priorsEl.innerHTML=`<div style="font-size:.85rem">${baseRates.map(r=>`<div style="display:flex; justify-content:space-between; padding:6px 0; border-bottom:1px dashed #334155"><span>${escapeHtml(r.label)}<br><small style="color:#94a3b8">n=${r.n} ${escapeHtml(r.src)}</small></span><span style="font-weight:700">${(r.p*100).toFixed(1)}%</span></div>`).join('')}</div>`;
  }
  const pathways=[
    {label:'Standard Review', mult:1.0, note:'Baseline'},
    {label:'Priority Review (FDA sees significant improvement)', mult:1.25, note:'Positive signal'},
    {label:'Breakthrough Therapy', mult:1.30, note:'Strong predictor'},
    {label:'Accelerated Approval (surrogate endpoint)', mult:0.90, note:'Confirmatory trial risk'},
    {label:'Single-arm registrational', mult:0.80, note:'No randomized comparator'},
  ];
  const trackRecords=[
    {label:'No prior decisions tracked', mult:1.0},
    {label:'1 prior approval', mult:1.05},
    {label:'2+ prior approvals', mult:1.12},
    {label:'1 prior CRL', mult:0.75},
    {label:'2+ prior CRLs', mult:0.55},
    {label:'Repeat CRLs same indication (e.g. Aldeyra 3 CRLs)', mult:0.35},
  ];
  formEl.innerHTML=`
    <label>Starting prior (base rate)</label><select id="base-rate">${baseRates.map((r,i)=>`<option value="${i}">${escapeHtml(r.label)} — ${(r.p*100).toFixed(1)}%</option>`).join('')}</select>
    <label>Review pathway</label><select id="pathway">${pathways.map((r,i)=>`<option value="${i}">${escapeHtml(r.label)} (${r.mult}x)</option>`).join('')}</select>
    <label>Company track record</label><select id="track">${trackRecords.map((r,i)=>`<option value="${i}">${escapeHtml(r.label)} (${r.mult}x)</option>`).join('')}</select>
    <label>Advisory committee</label><select id="adcomm"><option value="1">No AdComm / not yet</option><option value="1.2">Favorable vote (historically predicts approval)</option><option value="0.45">Adverse vote (FDA follows more often)</option><option value="0.85">AdComm convened (contested benefit-risk)</option></select>
    <div style="margin-top:16px"><button class="btn primary" id="calc-btn" style="width:100%; padding:12px; background:#2563eb; color:#fff; border:none; border-radius:8px; font-weight:700; cursor:pointer">Calculate Modelled Probability →</button></div>
  `;
  function calc(){
    const baseIdx=parseInt(document.getElementById('base-rate').value,10);
    const pathIdx=parseInt(document.getElementById('pathway').value,10);
    const trackIdx=parseInt(document.getElementById('track').value,10);
    const adcommMult=parseFloat(document.getElementById('adcomm').value);
    const base=baseRates[baseIdx];
    const path=pathways[pathIdx];
    const track=trackRecords[trackIdx];
    const priorOdds=base.p/(1-base.p);
    const posteriorOdds=priorOdds * path.mult * track.mult * adcommMult;
    const posteriorProb=posteriorOdds/(1+posteriorOdds);
    const factors=[
      {k:`Prior: ${base.label}`, mult:1, p:base.p},
      {k:`Pathway: ${path.label}`, mult:path.mult, note:path.note},
      {k:`Track record: ${track.label}`, mult:track.mult},
      {k:`AdComm`, mult:adcommMult},
    ];
    outEl.innerHTML=`
      <div class="big">${(posteriorProb*100).toFixed(1)}%</div>
      <div class="sub">Modelled probability of FDA approval<br>Prior ${(base.p*100).toFixed(1)}% → Posterior ${(posteriorProb*100).toFixed(1)}%</div>
      <ul class="factor-list" style="list-style:none; padding:0; margin:18px 0 0; font-size:.86rem">
        ${factors.map(f=>`<li style="display:flex; justify-content:space-between; gap:12px; padding:10px 0; border-bottom:1px dashed rgba(255,255,255,.15)"><span>${escapeHtml(f.k)}${f.note?`<br><small style="color:#94a3b8">${escapeHtml(f.note)}</small>`:''}</span><span style="font-weight:700; color:${f.mult>1?'#6ee7b7':f.mult<1?'#fca5a5':'#94a3b8'}">${f.mult}x</span></li>`).join('')}
      </ul>
      <div style="font-family:ui-monospace; font-size:.78rem; background:rgba(255,255,255,.08); padding:12px; border-radius:8px; margin-top:16px; white-space:pre-wrap">Prior odds = ${base.p.toFixed(3)}/(1-${base.p.toFixed(3)}) = ${priorOdds.toFixed(3)}
Posterior odds = ${priorOdds.toFixed(3)} * ${path.mult} * ${track.mult} * ${adcommMult} = ${posteriorOdds.toFixed(3)}
Posterior prob = ${posteriorOdds.toFixed(3)}/(1+${posteriorOdds.toFixed(3)}) = ${posteriorProb.toFixed(3)} = ${(posteriorProb*100).toFixed(1)}%

Sources: ${base.src}, FDA PDUFA/CDER reporting, BIO 2011-2020 n=${base.n}
No per-decision likelihood without denominator. This is scenario estimator only.
      </div>
    `;
  }
  document.getElementById('calc-btn').addEventListener('click', calc);
  calc();
}

/* Load all tables */
function loadTables(){
  DataTable({
    id:'core-decision-engine', mount:'#core-decision-engine-view', csv:'data/decision_engine_analysis_table.csv',
    columns:[
      c('company_name','Company',{core:true, render:r=>`<strong>${escapeHtml(r.company_name)}</strong><br><small style="color:#64748b">${escapeHtml(r.ticker||'')}</small>`}),
      c('drug_name','Drug',{core:true}),
      c('recent_clinical_trial_result','Recent Clinical Trial Result',{core:true, render:r=>truncCell(r.recent_clinical_trial_result, 120)}),
      c('fda_decision','FDA Decision',{core:true, render:r=>truncCell(r.fda_decision, 140)}),
      c('fda_decision_date','FDA Date',{core:true, render:r=>`<span style="font-weight:700">${escapeHtml(r.fda_decision_date)}</span>`}),
      c('stock_pricing_summary','Stock Pricing After Official Release',{core:true, render:r=>truncCell(r.stock_pricing_summary, 140)}),
      c('pct_change_on_decision','% Change',{core:true, render:r=>pctCell(r.pct_change_on_decision)}),
      c('company_success_rate_summary','Company Score Success Rate',{core:true, render:r=>truncCell(r.company_success_rate_summary, 140)}),
      c('company_score','Score',{render:r=>num(r.company_score,1)}),
      c('company_score_grade','Grade',{render:r=>`<span class="badge ${r.company_score_grade==='A'?'verified':r.company_score_grade==='E'?'warn':'info'}">${escapeHtml(r.company_score_grade||'')}</span>`}),
      c('fda_source_url','FDA Source',{render:r=>linkify(r.fda_source_url,'FDA')}),
      c('secondary_source_url','Verify',{render:r=>linkify(r.secondary_source_url,'verify')}),
    ],
    searchFields:['company_name','ticker','drug_name','recent_clinical_trial_result','fda_decision','fda_decision_date'],
    searchPlaceholder:'Search company, drug, trial result, FDA decision, ticker…',
    sort:{key:'fda_decision_date', dir:'desc'}, pageSize:25
  });

  DataTable({
    id:'scores-detailed', mount:'#scores-detailed-view', csv:'data/company_success_rate_detailed_scorecard.csv',
    columns:[
      c('company_name','Company',{core:true, render:r=>`<strong>${escapeHtml(r.company_name)}</strong>`}),
      c('ticker','Ticker',{core:true, render:r=>r.ticker?`<strong>${escapeHtml(r.ticker)}</strong>`:'<span class="badge warn">—</span>'}),
      c('exchange','Exchange',{core:true}),
      c('total_drugs_in_profile','Total Drugs in Profile',{core:true, render:r=>num(r.total_drugs_in_profile,0)}),
      c('approved_drugs','Approved',{core:true, render:r=>num(r.approved_drugs,0)}),
      c('phase3_programs','Phase 3',{core:true, render:r=>num(r.phase3_programs,0)}),
      c('phase2_programs','Phase 2',{render:r=>num(r.phase2_programs,0)}),
      c('phase1_programs','Phase 1',{render:r=>num(r.phase1_programs,0)}),
      c('paused_or_hold','Paused / Hold',{core:true, render:r=>num(r.paused_or_hold,0)}),
      c('advanced_to_next_phase','Advanced Next Phase',{core:true, render:r=>num(r.advanced_to_next_phase,0)}),
      c('clinical_progression_rate_pct','Progression %',{render:r=>pctCell(r.clinical_progression_rate_pct)}),
      c('fda_approval_rate_pct','FDA Approval %',{render:r=>pctCell(r.fda_approval_rate_pct)}),
      c('success_rate_pct','Success Rate %',{core:true, render:r=>pctCell(r.success_rate_pct)}),
      c('composite_score_0_100','Composite Score',{core:true, render:r=>num(r.composite_score_0_100,1)}),
      c('success_grade','Grade',{core:true, render:r=>`<span class="badge ${r.success_grade==='A'?'verified':'info'}">${escapeHtml(r.success_grade||'')}</span>`}),
      c('source_url_1','Source 1',{render:r=>linkify(r.source_url_1,'source')}),
      c('verification_status','Verification',{render:r=>statusBadge(r.verification_status)}),
    ],
    searchFields:['company_name','ticker','notes'],
    searchPlaceholder:'Search company scorecards — pipeline, phase, success rate…',
    sort:{key:'composite_score_0_100', dir:'desc'}, pageSize:25
  });

  DataTable({
    id:'prices-index', mount:'#prices-index-view', csv:'data/stock_price_verified_index.csv',
    columns:[
      c('ticker','Ticker',{core:true, render:r=>`<strong>${escapeHtml(r.ticker)}</strong>`}),
      c('company','Company',{core:true, render:r=>truncCell(r.company, 80)}),
      c('decision_date','FDA Decision Date',{core:true, render:r=>`<span style="font-weight:700">${escapeHtml(r.decision_date)}</span>`}),
      c('decision_type','Decision Type',{core:true}),
      c('close_before','Close Before',{core:true, render:r=>num(r.close_before,2)}),
      c('close_on_or_after','Close After',{core:true, render:r=>num(r.close_on_or_after,2)}),
      c('pct_change_on_decision','% Change',{core:true, render:r=>pctCell(r.pct_change_on_decision)}),
      c('price_t1','T+1 Close',{render:r=>num(r.price_t1,2)}),
      c('pct_change_t1','% T+1',{render:r=>pctCell(r.pct_change_t1)}),
      c('source_url','Yahoo API Source',{render:r=>linkify(r.source_url,'Yahoo chart')}),
      c('manual_verification_url','Manual Verify',{render:r=>linkify(r.manual_verification_url,'Yahoo history')}),
      c('secondary_verification_url','Secondary Verify',{render:r=>linkify(r.secondary_verification_url,'StockAnalysis')}),
      c('verification_status','Verification',{render:r=>statusBadge(r.verification_status)}),
    ],
    searchFields:['ticker','company','decision_date','decision_type'],
    searchPlaceholder:'Search stock reactions — ticker, company, date…',
    sort:{key:'decision_date', dir:'desc'}, pageSize:25
  });

  DataTable({
    id:'new1000', mount:'#new1000-view', csv:'data/fda_verified_decisions_2000_2026_1000_new.csv',
    columns:[
      c('year','Year',{core:true, render:r=>`<span style="font-weight:800">${escapeHtml(r.year)}</span>`}),
      c('decision_date','Decision Date',{core:true, render:r=>`<span style="font-weight:700">${escapeHtml(r.decision_date)}</span>`}),
      c('application_number','Application #',{core:true, render:r=>`<code>${escapeHtml(r.application_number)}</code>`}),
      c('company_name','Company',{core:true, render:r=>truncCell(r.company_name, 80)}),
      c('ticker','Ticker',{core:true, render:r=>r.ticker?`<strong>${escapeHtml(r.ticker)}</strong>`:'<span class="badge warn">blank beats guessed</span>'}),
      c('drug_brand','Drug Brand',{core:true}),
      c('chemical_type_code','Chemical Type',{core:true, render:r=>`<span class="badge info">${escapeHtml(r.chemical_type_code)}</span>`}),
      c('chemical_type_description','Type Description',{render:r=>truncCell(r.chemical_type_description, 100)}),
      c('review_priority','Priority',{render:r=>r.review_priority?`<span class="badge ${r.review_priority==='PRIORITY'?'verified':'info'}">${escapeHtml(r.review_priority)}</span>`:''}),
      c('product_details','Product Details',{render:r=>truncCell(r.product_details, 120)}),
      c('source_url_1','Drugs@FDA',{core:true, render:r=>linkify(r.source_url_1,'Drugs@FDA')}),
      c('source_url_2','openFDA',{render:r=>linkify(r.source_url_2,'openFDA')}),
      c('source_url_3','Year Query',{render:r=>linkify(r.source_url_3,'year query')}),
      c('payload_file','Payload File',{render:r=>`<code>${escapeHtml(r.payload_file)}</code>`}),
      c('verification_status','Verification',{core:true, render:r=>statusBadge(r.verification_status)}),
    ],
    searchFields:['year','decision_date','application_number','company_name','drug_brand','chemical_type_code','ticker'],
    searchPlaceholder:'Search 1000 new verified — year, company, drug, ticker, type…',
    sort:{key:'decision_date', dir:'asc'}, pageSize:25
  });

  DataTable({
    id:'year2000', mount:'#year2000-view', csv:'data/fda_decisions_year_by_year_2000_2026_detailed.csv',
    columns:[
      c('year','Year',{core:true, render:r=>`<span style="font-weight:800">${escapeHtml(r.year)}</span>`}),
      c('openfda_orig_ap_count','OpenFDA ORIG/AP Count',{core:true, render:r=>num(r.openfda_orig_ap_count,0)}),
      c('v27_selected_count','V27 Selected',{core:true, render:r=>num(r.v27_selected_count,0)}),
      c('type1_count','Type 1 NME',{core:true, render:r=>num(r.type1_count,0)}),
      c('type2_count','Type 2',{render:r=>num(r.type2_count,0)}),
      c('type3_count','Type 3',{render:r=>num(r.type3_count,0)}),
      c('type4_count','Type 4',{render:r=>num(r.type4_count,0)}),
      c('priority_count','Priority',{render:r=>num(r.priority_count,0)}),
      c('standard_count','Standard',{render:r=>num(r.standard_count,0)}),
      c('official_source_url','Official Query',{core:true, render:r=>linkify(r.official_source_url,'openFDA query')}),
      c('payload_file','Payload File',{render:r=>`<code>${escapeHtml(r.payload_file)}</code>`}),
      c('verification_status','Verification',{render:r=>statusBadge(r.verification_status)}),
    ],
    searchFields:['year','notes'],
    searchPlaceholder:'Search year-by-year 2000-2026…',
    sort:{key:'year', dir:'asc'}, pageSize:30
  });

  DataTable({
    id:'pre1938', mount:'#pre1938-view', csv:'data/pre1938_determination.csv',
    columns:[
      c('year','Year',{core:true}),
      c('determination','Determination',{core:true, render:r=>truncCell(r.determination, 200)}),
      c('official_fda_series_note','Official FDA Series Note',{render:r=>truncCell(r.official_fda_series_note, 200)}),
      c('submissions_count_in_official_db','Submissions Count',{render:r=>num(r.submissions_count_in_official_db,0)}),
      c('source_url_1','Source 1',{render:r=>linkify(r.source_url_1,'FDA series')}),
      c('source_url_2','Source 2',{render:r=>linkify(r.source_url_2,'Submissions file')}),
      c('verification_status','Verification',{render:r=>statusBadge(r.verification_status)}),
    ],
    searchFields:['year','determination'], searchPlaceholder:'Search 1938 determination…', sort:{key:'year', dir:'asc'}, pageSize:5
  });

  DataTable({
    id:'pre1965-register', mount:'#pre1965-register-view', csv:'data/pre1965_year_register.csv',
    columns:[
      c('year','Year',{core:true, render:r=>`<span style="font-weight:800">${escapeHtml(r.year)}</span>`}),
      c('payload_orig_ap_count','Payload ORIG/AP',{core:true, render:r=>num(r.payload_orig_ap_count,0)}),
      c('nme_rows_total','NME Rows Total',{core:true, render:r=>num(r.nme_rows_total,0)}),
      c('nme_counted_once','Counted Once',{core:true, render:r=>num(r.nme_counted_once,0)}),
      c('official_fda_nme_count','Official FDA NME',{render:r=>escapeHtml(r.official_fda_nme_count||'n/a')}),
      c('delta_nme_rows_vs_official','Delta',{render:r=>escapeHtml(r.delta_nme_rows_vs_official||'n/a')}),
      c('blank_class_rows','Blank Class',{render:r=>num(r.blank_class_rows,0)}),
      c('unknown_class_rows','UNKNOWN Class',{render:r=>num(r.unknown_class_rows,0)}),
      c('source_type','Source Type',{render:r=>truncCell(r.source_type, 80)}),
      c('notes','Notes',{render:r=>truncCell(r.notes, 200)}),
    ],
    searchFields:['year','notes'], searchPlaceholder:'Search pre-1965 register…', sort:{key:'year', dir:'asc'}, pageSize:30
  });

  DataTable({
    id:'pre1965-decisions', mount:'#pre1965-decisions-view', csv:'data/pre1965_fda_decisions.csv',
    columns:[
      c('decision_id','Decision ID',{core:true, render:r=>`<code>${escapeHtml(r.decision_id)}</code>`}),
      c('year','Year',{core:true}),
      c('decision_date','Date',{core:true, render:r=>`<span style="font-weight:700">${escapeHtml(r.decision_date)}</span>`}),
      c('application_number','Appl #',{core:true, render:r=>`<code>${escapeHtml(r.application_number)}</code>`}),
      c('drug_brand','Brand',{core:true}),
      c('company_name','Company',{render:r=>truncCell(r.company_name, 80)}),
      c('chemical_type_code','Type',{render:r=>`<span class="badge info">${escapeHtml(r.chemical_type_code)}</span>`}),
      c('review_priority','Priority',{render:r=>escapeHtml(r.review_priority||'—')}),
      c('source_url_1','Drugs@FDA',{render:r=>linkify(r.source_url_1,'Drugs@FDA')}),
      c('source_url_2','openFDA',{render:r=>linkify(r.source_url_2,'openFDA')}),
    ],
    searchFields:['decision_id','year','drug_brand','company_name','application_number'], searchPlaceholder:'Search pre-1965 NME decisions…', sort:{key:'decision_date', dir:'asc'}, pageSize:25
  });

  DataTable({
    id:'full-1938-1964', mount:'#full-1938-1964-view', csv:'data/fda_1938_1964_full_submission_register.csv',
    columns:[
      c('year','Year',{core:true}),
      c('submission_status_date','Status Date',{core:true, render:r=>`<span style="font-weight:700">${escapeHtml(r.submission_status_date)}</span>`}),
      c('application_number','Appl #',{core:true, render:r=>`<code>${escapeHtml(r.application_number)}</code>`}),
      c('sponsor_name','Sponsor',{core:true, render:r=>truncCell(r.sponsor_name, 80)}),
      c('submission_type','Type',{core:true}),
      c('submission_status','Status',{core:true, render:r=>`<span class="badge ${r.submission_status==='AP'?'verified':'info'}">${escapeHtml(r.submission_status)}</span>`}),
      c('submission_class_code','Class Code',{render:r=>escapeHtml(r.submission_class_code||'—')}),
      c('review_priority','Priority',{render:r=>escapeHtml(r.review_priority||'—')}),
      c('source_url','Drugs@FDA',{render:r=>linkify(r.source_url,'Drugs@FDA')}),
    ],
    searchFields:['year','application_number','sponsor_name','submission_type','submission_status'], searchPlaceholder:'Search full 1938-1964 submissions…', sort:{key:'submission_status_date', dir:'asc'}, pageSize:25
  });

  DataTable({
    id:'pre1980', mount:'#pre1980-decisions-view', csv:'data/pre1980_fda_decisions.csv',
    columns:[
      c('decision_id','ID',{core:true, render:r=>`<code>${escapeHtml(r.decision_id)}</code>`}),
      c('year','Year',{core:true}),
      c('decision_date','Date',{core:true, render:r=>`<span style="font-weight:700">${escapeHtml(r.decision_date)}</span>`}),
      c('application_number','Appl #',{core:true, render:r=>`<code>${escapeHtml(r.application_number)}</code>`}),
      c('drug_brand','Brand',{core:true}),
      c('company_name','Company',{render:r=>truncCell(r.company_name, 80)}),
      c('chemical_type_code','Type',{render:r=>`<span class="badge info">${escapeHtml(r.chemical_type_code)}</span>`}),
      c('source_url_1','Drugs@FDA',{render:r=>linkify(r.source_url_1,'Drugs@FDA')}),
    ],
    searchFields:['decision_id','year','drug_brand','company_name'], searchPlaceholder:'Search pre-1980…', sort:{key:'decision_date', dir:'asc'}, pageSize:25
  });

  DataTable({
    id:'pre1985', mount:'#pre1985-decisions-view', csv:'data/pre1985_fda_decisions.csv',
    columns:[
      c('decision_id','ID',{core:true, render:r=>`<code>${escapeHtml(r.decision_id)}</code>`}),
      c('year','Year',{core:true}),
      c('decision_date','Date',{core:true, render:r=>`<span style="font-weight:700">${escapeHtml(r.decision_date)}</span>`}),
      c('application_number','Appl #',{core:true, render:r=>`<code>${escapeHtml(r.application_number)}</code>`}),
      c('drug_brand','Brand',{core:true}),
      c('company_name','Company',{render:r=>truncCell(r.company_name, 80)}),
      c('chemical_type_code','Type',{render:r=>`<span class="badge info">${escapeHtml(r.chemical_type_code)}</span>`}),
      c('source_url_1','Drugs@FDA',{render:r=>linkify(r.source_url_1,'Drugs@FDA')}),
    ],
    searchFields:['decision_id','year','drug_brand'], searchPlaceholder:'Search pre-1985…', sort:{key:'decision_date', dir:'asc'}, pageSize:25
  });

  DataTable({
    id:'decision-factors', mount:'#decision-factors-view', csv:'data/fda_decision_factors_analysis.csv',
    columns:[
      c('factor_category','Category',{core:true, render:r=>`<span class="badge info">${escapeHtml(r.factor_category)}</span>`}),
      c('factor_name','Factor Name',{core:true, render:r=>truncCell(r.factor_name, 120)}),
      c('base_rate','Base Rate',{render:r=>r.base_rate?num(r.base_rate,3):'<span class="badge warn">—</span>'}),
      c('sample_size','Sample Size',{render:r=>r.sample_size?num(r.sample_size,0):'<span class="badge warn">—</span>'}),
      c('odds_multiplier','Odds Multiplier',{core:true, render:r=>num(r.odds_multiplier,2)}),
      c('multiplier_basis','Multiplier Basis',{core:true, render:r=>truncCell(r.multiplier_basis, 120)}),
      c('source_type','Source Type',{render:r=>truncCell(r.source_type, 100)}),
      c('source_url','Source URL',{render:r=>linkify(r.source_url,'source')}),
      c('notes','Notes',{render:r=>truncCell(r.notes, 200)}),
    ],
    searchFields:['factor_category','factor_name','multiplier_basis','notes'],
    searchPlaceholder:'Search decision factors — base rate, pathway, track record…',
    sort:{key:'factor_category', dir:'asc'}, pageSize:25
  });

  DataTable({
    id:'science-basis', mount:'#science-basis-view', csv:'data/fda_decision_engine_science_basis.csv',
    columns:[
      c('area','Area',{core:true, render:r=>`<strong>${escapeHtml(r.area)}</strong>`}),
      c('published_finding','Published Finding',{core:true, render:r=>truncCell(r.published_finding, 140)}),
      c('sample_size','Sample Size',{render:r=>escapeHtml(r.sample_size||'—')}),
      c('source','Source',{core:true, render:r=>truncCell(r.source, 100)}),
      c('implication_for_decision_engine','Implication',{core:true, render:r=>truncCell(r.implication_for_decision_engine, 140)}),
      c('source_url','Source URL',{render:r=>linkify(r.source_url,'source')}),
    ],
    searchFields:['area','published_finding','source'], searchPlaceholder:'Search science basis…', sort:{key:'area', dir:'asc'}, pageSize:10
  });

  /* ---- v28: pre-1939 boundary tables ---- */
  DataTable({
    id:'pre1939-evidence', mount:'#pre1939-evidence-view', csv:'data/pre1939_boundary_determination.csv',
    columns:[
      c('evidence_id','ID',{core:true, render:r=>`<code>${escapeHtml(r.evidence_id)}</code>`}),
      c('category','Category',{core:true, render:r=>`<span class="badge info">${escapeHtml(r.category)}</span>`}),
      c('claim','Claim',{core:true, render:r=>`<strong>${escapeHtml(r.claim)}</strong>`}),
      c('observed_value','Observed Value',{core:true, render:r=>truncCell(r.observed_value, 130)}),
      c('method','Method',{render:r=>truncCell(r.method, 120)}),
      c('source_file','Source File',{render:r=>r.source_file?`<code>${escapeHtml(r.source_file)}</code>`:'<span class="badge info">external primary source</span>'}),
      c('source_sha256_prefix','SHA-256',{render:r=>r.source_sha256_prefix?`<code>${escapeHtml(r.source_sha256_prefix)}</code>`:'—'}),
      c('source_url','Official Source',{core:true, render:r=>linkify(r.source_url,'source')}),
      c('verification_status','Verification',{render:r=>statusBadge(r.verification_status)}),
      c('notes','Notes',{render:r=>truncCell(r.notes, 160)}),
    ],
    searchFields:['evidence_id','category','claim','observed_value','notes'],
    searchPlaceholder:'Search boundary evidence — application census, boundary date, statutes…',
    sort:{key:'evidence_id', dir:'asc'}, pageSize:15
  });

  DataTable({
    id:'pre1939-census', mount:'#pre1939-census-view', csv:'data/pre1939_application_census.csv',
    columns:[
      c('application_number','Application',{core:true, render:r=>`<code>${escapeHtml(r.application_number)}</code>`}),
      c('appl_type','Type',{render:r=>`<span class="badge info">${escapeHtml(r.appl_type)}</span>`}),
      c('sponsor_name_official_db','Sponsor (official DB)',{core:true}),
      c('first_product_brand_official_payload','Product of Record',{core:true, render:r=>r.first_product_brand_official_payload?`<strong>${escapeHtml(r.first_product_brand_official_payload)}</strong>`:'<span class="badge warn">none published</span>'}),
      c('first_product_ingredients','Ingredients',{render:r=>truncCell(r.first_product_ingredients, 90)}),
      c('first_product_marketing_status','Marketing Status',{render:r=>r.first_product_marketing_status?`<span class="badge warn">${escapeHtml(r.first_product_marketing_status)}</span>`:'—'}),
      c('earliest_recorded_action_date','Earliest Recorded Action',{core:true, render:r=>`<span style="font-weight:700">${escapeHtml(r.earliest_recorded_action_date)}</span>`}),
      c('decision_recorded_before_1939','Decision Pre-1939?',{core:true, render:r=>r.decision_recorded_before_1939==='False'?'<span class="badge verified">No</span>':`<span class="badge warn">${escapeHtml(r.decision_recorded_before_1939)}</span>`}),
      c('nme_comparable','NME Comparable',{render:r=>escapeHtml(r.nme_comparable||'—')}),
      c('tracked_in_project_table','Tracked In',{render:r=>truncCell(r.tracked_in_project_table, 90)}),
      c('flags','Flags',{render:r=>r.flags?`<span class="badge" style="background:#fef2f2;color:#dc2626;border:1px solid #fecaca">${escapeHtml(r.flags)}</span>`:'—'}),
      c('drugsatfda_url','Drugs@FDA',{render:r=>linkify(r.drugsatfda_url,'Drugs@FDA')}),
    ],
    searchFields:['application_number','sponsor_name_official_db','first_product_brand_official_payload','first_product_ingredients','notes'],
    searchPlaceholder:'Search below-boundary applications…',
    sort:{key:'application_number', dir:'asc'}, pageSize:10
  });

  DataTable({
    id:'pre1939-register', mount:'#pre1939-register-view', csv:'data/pre1939_regulatory_register_1902_1938.csv',
    columns:[
      c('year','Year',{core:true, render:r=>`<span style="font-weight:800">${escapeHtml(r.year)}</span>`}),
      c('era','Era',{render:r=>truncCell(r.era, 70)}),
      c('agency_of_record','Agency of Record',{core:true, render:r=>truncCell(r.agency_of_record, 70)}),
      c('premarket_approval_regime','Pre-Market Approval Regime',{core:true, render:r=>truncCell(r.premarket_approval_regime, 150)}),
      c('statute_citation','Statute',{core:true, render:r=>truncCell(r.statute_citation, 90)}),
      c('statute_enacted_date','Enacted',{render:r=>escapeHtml(r.statute_enacted_date||'—')}),
      c('fda_drug_approval_decisions_recorded','Decisions Recorded',{core:true, render:r=>`<span class="badge verified" style="font-size:.85rem">${escapeHtml(r.fda_drug_approval_decisions_recorded)}</span>`}),
      c('official_fda_series_coverage','FDA Official Series',{render:r=>truncCell(r.official_fda_series_coverage, 110)}),
      c('landmark_event','Landmark Event',{render:r=>truncCell(r.landmark_event, 110)}),
      c('source_url_1','Primary Source',{core:true, render:r=>linkify(r.source_url_1,'source')}),
      c('source_url_2','Source 2',{render:r=>linkify(r.source_url_2,'source')}),
    ],
    searchFields:['year','era','agency_of_record','statute_citation','landmark_event','determination','notes'],
    searchPlaceholder:'Search the 1902-1938 regulatory register…',
    sort:{key:'year', dir:'asc'}, pageSize:40
  });

  DataTable({
    id:'pre1939-status', mount:'#pre1939-status-view', csv:'data/pre1939_submission_status_census.csv',
    columns:[
      c('year','Year',{core:true, render:r=>`<span style="font-weight:800">${escapeHtml(r.year)}</span>`}),
      c('source_window','Source Window',{render:r=>truncCell(r.source_window, 60)}),
      c('total_rows','Rows',{core:true, render:r=>num(r.total_rows,0)}),
      c('orig_ap_rows','ORIG/AP',{core:true, render:r=>num(r.orig_ap_rows,0)}),
      c('suppl_ap_rows','SUPPL/AP',{core:true, render:r=>num(r.suppl_ap_rows,0)}),
      c('other_type_rows','Other Types',{render:r=>num(r.other_type_rows,0)}),
      c('distinct_statuses','Statuses',{core:true, render:r=>`<span class="badge verified">${escapeHtml(r.distinct_statuses)}</span>`}),
      c('non_ap_rows','Non-AP Rows',{core:true, render:r=>r.non_ap_rows==='0'?'<span class="badge verified">0</span>':`<span class="badge warn">${escapeHtml(r.non_ap_rows)}</span>`}),
      c('determination','Determination',{render:r=>truncCell(r.determination, 150)}),
      c('source_url','Official Source',{render:r=>linkify(r.source_url,'FDA data files')}),
    ],
    searchFields:['year','source_window','determination','notes'],
    searchPlaceholder:'Search the submission status census…',
    sort:{key:'year', dir:'asc'}, pageSize:45
  });

  DataTable({
    id:'verification', mount:'#verification-view', csv:'data/verification_crosscheck.csv',
    columns:[
      c('decision_id','Decision ID',{core:true, render:r=>`<code>${escapeHtml(r.decision_id)}</code>`}),
      c('verification_result','Result',{core:true, render:r=>statusBadge(r.verification_result)}),
      c('decision_date','Date',{core:true}),
      c('drug_brand','Brand',{core:true}),
      c('company_name','Company',{render:r=>truncCell(r.company_name, 80)}),
      c('openfda_application_number','OpenFDA Appl #',{render:r=>`<code>${escapeHtml(r.openfda_application_number||'')}</code>`}),
      c('notes','Notes',{render:r=>truncCell(r.notes, 200)}),
    ],
    searchFields:['decision_id','verification_result','drug_brand','company_name'], searchPlaceholder:'Search verification…', sort:{key:'decision_id', dir:'asc'}, pageSize:25
  });
}

document.addEventListener('DOMContentLoaded', ()=>{
  initTabs();
  loadOverview();
  initEngine();
  loadTables();
});
