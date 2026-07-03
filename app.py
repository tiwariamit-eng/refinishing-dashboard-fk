import streamlit as st
import pandas as pd
import numpy as np
import json
import base64
import io
import streamlit.components.v1 as components
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload

st.set_page_config(
    page_title="Refinishing Conversion Dashboard",
    page_icon="👕",
    layout="wide"
)

# ── File IDs ───────────────────────────────────────────────────────────────────
FILE_IDS = [
    "1ibNXvkUGNRhjuEQ37svRukLekD60Q9oc",  # Wk 01-03
    "192ZfI7KCH-2GJ3i0eYVwefM0dAMbbErM",  # Wk 04-05
    "1uxLSaaRHQQpvkwE6N2oubDS2KE2Pvukh",  # Wk 06-08
    "1_W4uVC_6BnaQlijsS7aFqLJjGhGQhF88",  # Wk 09-10
    "1VEDLEnSplFvPsktoLvZSgjYtSMnTJ6-5",  # Wk 11-12
    "1bBCgtEZcMKDJNy-n0UvvIvTIebrqLMmj",  # Wk 15-16
    "1BbC0pBBNiZJjA5Bx6Ia9kvTivgQGeMc4",  # Wk 17-18
    "1yvwFqke1NgtdzXta0xuSkwmATVbPwkhO",  # Wk 19-22
    "1r1_dJUQuzvklC1Cb_8NtmsoiT2jkf8jA",  # Wk 23-26
]

TARGET = 90.0

SITE_MAP = {
    'Bhiwandi bts': 'Bhiwandi BTS RC',
    'Bhiwandi BTS': 'Bhiwandi BTS RC',
    'Bhiwandi BTS RC': 'Bhiwandi BTS RC',
    'Malur BTS': 'Malur BTS RC',
    'Malur BTS RC': 'Malur BTS RC',
    'Malur_BTS': 'Malur BTS RC',
    'Haringhata RC': 'Haringhata NLRC',
    'Haringhata NLFC': 'Haringhata NLRC',
    'Haringhata NLRC': 'Haringhata NLRC',
    'Haringhata NLFC 01': 'Haringhata NLRC',
    'Sanpka': 'Sanpka RC',
    'Sanpka RC': 'Sanpka RC',
    'FRK BTS RC': 'FRK BTS RC',
    'Frk_bts': 'FRK BTS RC',
    'FRK BTS': 'FRK BTS RC',
    'Bilaspur RPC': 'Bilaspur RPC',
    'Uluberia BTS RC': 'Uluberia BTS RC',
}

MONTHS_ORDER = ['Jan 26','Feb 26','Mar 26','Apr 26','May 26','Jun 26',
                'Jul 26','Aug 26','Sep 26','Oct 26','Nov 26','Dec 26']

# ── Drive auth ─────────────────────────────────────────────────────────────────
@st.cache_resource
def get_drive_service():
    creds = Credentials(
        token=None,
        refresh_token=st.secrets["GOOGLE_REFRESH_TOKEN"],
        client_id=st.secrets["GOOGLE_CLIENT_ID"],
        client_secret=st.secrets["GOOGLE_CLIENT_SECRET"],
        token_uri="https://oauth2.googleapis.com/token",
    )
    return build("drive", "v3", credentials=creds)

# ── helpers ────────────────────────────────────────────────────────────────────
def safe_col(df, candidates, default=None):
    for c in candidates:
        if c in df.columns:
            return df[c].copy()
    if default is not None:
        return pd.Series([default] * len(df), index=df.index)
    return pd.Series([np.nan] * len(df), index=df.index)

def conv_pct(p, f):
    t = p + f
    return round(p / t * 100, 1) if t > 0 else None

# ── data loading ───────────────────────────────────────────────────────────────
@st.cache_data(ttl=3600)
def load_data():
    service = get_drive_service()
    dfs = []
    for fid in FILE_IDS:
        buf = io.BytesIO()
        req = service.files().get_media(fileId=fid)
        dl = MediaIoBaseDownload(buf, req)
        done = False
        while not done:
            _, done = dl.next_chunk()
        buf.seek(0)
        try:
            raw = pd.read_csv(buf, on_bad_lines='skip', low_memory=False)
        except TypeError:
            buf.seek(0)
            raw = pd.read_csv(buf, error_bad_lines=False, low_memory=False)
        raw.columns = [str(c).strip() for c in raw.columns]

        tmp = pd.DataFrame({
            's': safe_col(raw, ['Warehouse Name', 'Warehouse ID']).astype(str).str.strip(),
            'z': safe_col(raw, ['Zone', 'zone']).astype(str).str.strip().str.title(),
            'w': pd.to_numeric(safe_col(raw, ['week', 'Week'], 0), errors='coerce'),
            'r': safe_col(raw, ['Result', 'result']).astype(str).str.strip(),
            'q': safe_col(raw, ['QA remark', 'QA Remark']).astype(str).str.strip(),
            'v': safe_col(raw, ['Vertical/Category', 'Vertical', 'vertical']).astype(str).str.strip(),
        })
        dfs.append(tmp)

    df = pd.concat(dfs, ignore_index=True)
    df = df[df['w'].notna() & (df['w'] > 0)]
    df['w'] = df['w'].astype(int)
    df = df[df['r'].isin(['Pass', 'Fail'])]
    df = df[~df['s'].str.lower().isin(['', 'nan', 'none', 'warehouse id', 'warehouse name'])]
    df['s'] = df['s'].replace(SITE_MAP)

    def norm_v(v):
        v = str(v).lower()
        if 'footwear' in v or 'sandal' in v:
            return 'Footwear'
        if 'apparel' in v or 'clothing' in v:
            return 'Apparel'
        return 'Other'
    df['v'] = df['v'].apply(norm_v)

    def w2m(w):
        if w <= 4:   return 'Jan 26'
        if w <= 8:   return 'Feb 26'
        if w <= 13:  return 'Mar 26'
        if w <= 17:  return 'Apr 26'
        if w <= 22:  return 'May 26'
        if w <= 26:  return 'Jun 26'
        if w <= 30:  return 'Jul 26'
        if w <= 35:  return 'Aug 26'
        if w <= 39:  return 'Sep 26'
        if w <= 44:  return 'Oct 26'
        if w <= 48:  return 'Nov 26'
        return 'Dec 26'
    df['m'] = df['w'].apply(w2m)
    return df

# ── aggregation helpers ────────────────────────────────────────────────────────
def build_week_site(df):
    out = {}
    for (w, s), g in df.groupby(['w', 's']):
        p = int((g['r'] == 'Pass').sum())
        f = int((g['r'] == 'Fail').sum())
        c = conv_pct(p, f)
        if w not in out:
            out[w] = {}
        out[w][s] = {'p': p, 'f': f, 'c': c}
    return out

def build_failure_reasons(df):
    fdf = df[
        (df['r'] == 'Fail') &
        ~df['q'].str.lower().str.contains('no issue', na=False)
    ]
    out = []
    for (s, q), g in fdf.groupby(['s', 'q']):
        out.append({'site': s, 'reason': str(q), 'count': int(len(g))})
    out.sort(key=lambda x: -x['count'])
    return out

# ─────────────────────────────────────────────────────────────────────────────
# HTML TEMPLATE
# ─────────────────────────────────────────────────────────────────────────────
TEMPLATE_HTML = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"/>
<style>
  * { box-sizing: border-box; margin: 0; padding: 0; font-family: 'Segoe UI', Arial, sans-serif; }
  body { background: #f0f2f5; padding: 16px; font-size: 13px; color: #1a1a2e; }

  /* header */
  .header { background: linear-gradient(135deg,#1a1a2e 0%,#16213e 60%,#0f3460 100%);
    color:#fff; padding:18px 24px; border-radius:12px; margin-bottom:16px;
    display:flex; justify-content:space-between; align-items:center; }
  .header h1 { font-size:20px; font-weight:700; }
  .header .sub { font-size:12px; color:#a0aec0; margin-top:4px; }
  .badge { background:#e94560; color:#fff; padding:4px 10px; border-radius:20px; font-size:11px; font-weight:600; }

  /* filters */
  .filter-bar { background:#fff; border-radius:10px; padding:14px 18px;
    margin-bottom:14px; display:flex; gap:16px; flex-wrap:wrap; align-items:flex-end;
    box-shadow:0 1px 4px rgba(0,0,0,.06); }
  .filter-group { display:flex; flex-direction:column; gap:4px; }
  .filter-group label { font-size:11px; font-weight:600; color:#718096; text-transform:uppercase; letter-spacing:.5px; }
  .filter-group select { padding:6px 10px; border:1.5px solid #e2e8f0; border-radius:6px;
    font-size:12px; background:#f8fafc; cursor:pointer; outline:none; min-width:130px; }
  .filter-group select:focus { border-color:#0f3460; }
  .reset-btn { padding:7px 16px; background:#e94560; color:#fff; border:none;
    border-radius:6px; font-size:12px; font-weight:600; cursor:pointer; align-self:flex-end; }
  .reset-btn:hover { background:#c73652; }

  /* KPI cards */
  .kpi-row { display:grid; grid-template-columns:repeat(5,1fr); gap:12px; margin-bottom:14px; }
  .kpi { background:#fff; border-radius:10px; padding:14px 16px;
    box-shadow:0 1px 4px rgba(0,0,0,.06); border-left:4px solid #ccc; }
  .kpi.green  { border-color:#48bb78; }
  .kpi.red    { border-color:#e94560; }
  .kpi.blue   { border-color:#4299e1; }
  .kpi.purple { border-color:#9f7aea; }
  .kpi.orange { border-color:#ed8936; }
  .kpi .label { font-size:11px; color:#718096; font-weight:600; text-transform:uppercase; letter-spacing:.4px; }
  .kpi .value { font-size:26px; font-weight:700; margin:4px 0 2px; }
  .kpi .sub   { font-size:11px; color:#a0aec0; }
  .kpi.green  .value { color:#2f855a; }
  .kpi.red    .value { color:#c53030; }
  .kpi.blue   .value { color:#2b6cb0; }
  .kpi.purple .value { color:#6b46c1; }
  .kpi.orange .value { color:#c05621; }

  /* section */
  .section { background:#fff; border-radius:10px; padding:16px;
    margin-bottom:14px; box-shadow:0 1px 4px rgba(0,0,0,.06); }
  .section h3 { font-size:14px; font-weight:700; color:#1a1a2e;
    margin-bottom:12px; padding-bottom:8px; border-bottom:2px solid #f0f2f5;
    display:flex; align-items:center; gap:8px; }

  /* observation */
  .obs-box { width:100%; min-height:70px; padding:10px 12px;
    border:1.5px solid #e2e8f0; border-radius:8px; font-size:12px;
    resize:vertical; outline:none; font-family:inherit; color:#2d3748; }
  .obs-box:focus { border-color:#0f3460; }

  /* tables */
  .tbl-wrap { overflow-x:auto; }
  table { border-collapse:collapse; width:100%; font-size:12px; }
  th { background:#1a1a2e; color:#fff; padding:8px 10px; text-align:center;
    white-space:nowrap; font-weight:600; font-size:11px; position:sticky; top:0; z-index:2; }
  th.left { text-align:left; }
  td { padding:6px 10px; text-align:center; border-bottom:1px solid #f0f2f5; }
  td.left { text-align:left; font-weight:600; white-space:nowrap; }
  tr:hover td { background:#f7fafc; }
  tr.total-row td { background:#edf2f7; font-weight:700; border-top:2px solid #cbd5e0; }

  .g  { background:#c6f6d5 !important; color:#22543d; font-weight:600; border-radius:4px; }
  .r  { background:#fed7d7 !important; color:#742a2a; font-weight:600; border-radius:4px; }
  .y  { background:#fefcbf !important; color:#744210; font-weight:600; border-radius:4px; }
  .na { color:#a0aec0; font-size:11px; }

  /* frozen site column */
  .site-tbl-wrap { overflow-x:auto; position:relative; }
  .site-tbl-wrap table { min-width:600px; }
  .site-tbl-wrap td.frozen,
  .site-tbl-wrap th.frozen {
    position:sticky; left:0; z-index:3; background:#1a1a2e;
    color:#fff; min-width:150px;
  }
  .site-tbl-wrap td.frozen { background:#f8fafc; color:#1a1a2e; z-index:1; }
  .obs-col { min-width:180px; max-width:220px; }

  /* sample monitor */
  .sample-grid { display:grid; grid-template-columns:repeat(auto-fill,minmax(180px,1fr)); gap:10px; }
  .sample-card { border-radius:8px; padding:12px 14px; border-left:4px solid #48bb78; background:#f8fafc; }
  .sample-card.low { border-color:#ed8936; background:#fffaf0; }
  .sample-card.alert { border-color:#e94560; background:#fff5f5; }
  .sample-card .site-name { font-size:11px; font-weight:700; color:#2d3748; margin-bottom:4px; }
  .sample-card .count { font-size:20px; font-weight:700; color:#2d3748; }
  .sample-card .tag { font-size:10px; margin-top:3px; }
  .sample-card.low .tag  { color:#c05621; }
  .sample-card.alert .tag { color:#c53030; }
  .sample-card .prev { font-size:10px; color:#718096; }

  /* failure reasons */
  .tabs { display:flex; gap:6px; margin-bottom:12px; }
  .tab  { padding:6px 16px; border-radius:6px; border:none; cursor:pointer;
    font-size:12px; font-weight:600; background:#edf2f7; color:#4a5568; }
  .tab.active { background:#1a1a2e; color:#fff; }

  .reason-bar-wrap { display:flex; flex-direction:column; gap:6px; }
  .reason-row { display:flex; align-items:center; gap:8px; }
  .reason-label { width:240px; min-width:160px; font-size:11px; color:#2d3748; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }
  .reason-bar-bg { flex:1; background:#f0f2f5; border-radius:4px; height:16px; }
  .reason-bar-fill { height:16px; border-radius:4px; background:#e94560; transition:width .3s; }
  .reason-count { width:40px; text-align:right; font-size:11px; font-weight:700; color:#4a5568; }

  /* declining sites */
  .decline-grid { display:grid; grid-template-columns:repeat(auto-fill,minmax(220px,1fr)); gap:10px; }
  .decline-card { border-radius:8px; padding:12px 14px; background:#fff5f5; border-left:4px solid #e94560; }
  .decline-card .site { font-size:12px; font-weight:700; color:#2d3748; }
  .decline-card .trend { font-size:11px; color:#c53030; margin-top:4px; }
  .no-decline { color:#48bb78; font-size:12px; font-weight:600; }

  /* wow chart */
  .chart-wrap { overflow-x:auto; }
  .bar-chart { display:flex; gap:12px; align-items:flex-end; min-height:160px;
    padding:10px 0; border-bottom:2px solid #e2e8f0; }
  .bar-col { display:flex; flex-direction:column; align-items:center; gap:4px; min-width:40px; }
  .bar { width:32px; border-radius:4px 4px 0 0; position:relative; cursor:default;
    transition:opacity .2s; }
  .bar:hover { opacity:.85; }
  .bar-val { font-size:9px; font-weight:700; text-align:center; }
  .bar-lbl { font-size:9px; color:#718096; white-space:nowrap; }
  .chart-legend { display:flex; gap:14px; flex-wrap:wrap; margin-top:10px; }
  .legend-item { display:flex; align-items:center; gap:5px; font-size:11px; color:#4a5568; }
  .legend-dot { width:10px; height:10px; border-radius:2px; }

  .info-msg { color:#718096; font-size:12px; font-style:italic; }
</style>
</head>
<body>

<!-- HEADER -->
<div class="header">
  <div>
    <h1>👕 Refinishing Conversion Dashboard</h1>
    <div class="sub">Lifestyle Category — Apparel &amp; Footwear | Live Returns QC Tracking</div>
  </div>
  <span class="badge">Target: &gt;90%</span>
</div>

<!-- FILTERS -->
<div class="filter-bar">
  <div class="filter-group">
    <label>Zone</label>
    <select id="fZone" onchange="render()">
      <option value="All">All Zones</option>
      <option value="East">East</option>
      <option value="North">North</option>
      <option value="South">South</option>
      <option value="West">West</option>
    </select>
  </div>
  <div class="filter-group">
    <label>Site</label>
    <select id="fSite" onchange="render()">
      <option value="All">All Sites</option>
    </select>
  </div>
  <div class="filter-group">
    <label>Vertical</label>
    <select id="fVert" onchange="render()">
      <option value="All">All (Apparel + Footwear)</option>
      <option value="Apparel">Apparel Only</option>
      <option value="Footwear">Footwear Only</option>
    </select>
  </div>
  <button class="reset-btn" onclick="resetFilters()">↺ Reset</button>
</div>

<!-- KPI CARDS -->
<div class="kpi-row" id="kpiRow"></div>

<!-- OBSERVATION -->
<div class="section">
  <h3>📝 Observations &amp; Notes</h3>
  <textarea class="obs-box" id="obsBox" placeholder="Add observations, action items, or notes here…"></textarea>
</div>

<!-- MONTH-WISE TABLE -->
<div class="section">
  <h3>📅 Month-wise Conversion % by Site</h3>
  <div class="tbl-wrap"><table id="monthTbl"></table></div>
</div>

<!-- ZONE-WISE TABLE -->
<div class="section">
  <h3>🗺️ Zone-wise Conversion %</h3>
  <div class="tbl-wrap"><table id="zoneTbl"></table></div>
</div>

<!-- WEEK-WISE TABLE -->
<div class="section">
  <h3>📆 Week-wise Conversion % by Site</h3>
  <div class="tbl-wrap"><table id="weekTbl"></table></div>
</div>

<!-- SITE-WISE TABLE (FROZEN) -->
<div class="section">
  <h3>🏭 Site-wise Conversion (All Weeks)</h3>
  <div class="site-tbl-wrap"><table id="siteTbl"></table></div>
</div>

<!-- SAMPLE MONITOR -->
<div class="section">
  <h3>📊 Sample Size Monitor</h3>
  <div class="sample-grid" id="sampleGrid"></div>
</div>

<!-- FAILURE REASONS -->
<div class="section">
  <h3>❌ Failure Reason Analysis</h3>
  <div class="tabs">
    <button class="tab active" id="tabOv"  onclick="setReasonTab('ov')">Overall</button>
    <button class="tab"        id="tabApp" onclick="setReasonTab('app')">Apparel</button>
    <button class="tab"        id="tabFtw" onclick="setReasonTab('ftw')">Footwear</button>
  </div>
  <div id="reasonPanel"></div>
</div>

<!-- SITE-LEVEL REASON -->
<div class="section">
  <h3>🔍 Site-level Failure Reason Breakdown</h3>
  <div style="margin-bottom:10px">
    <select id="siteReasonSel" onchange="renderSiteReason()" style="padding:6px 10px;border:1.5px solid #e2e8f0;border-radius:6px;font-size:12px;">
      <option value="">— Select a site —</option>
    </select>
  </div>
  <div id="siteReasonPanel"></div>
</div>

<!-- DECLINING SITES -->
<div class="section">
  <h3>📉 Declining Sites (Last 4 Weeks Trend)</h3>
  <div id="declinePanel"></div>
</div>

<!-- WoW CHART -->
<div class="section">
  <h3>📊 Week-on-Week Conversion Chart</h3>
  <div class="chart-wrap" id="wowChart"></div>
</div>

<script>
// ── injected data ──────────────────────────────────────────────────────────
const D = __DATA__;

// ── state ──────────────────────────────────────────────────────────────────
let reasonTab = 'ov';

// ── init ───────────────────────────────────────────────────────────────────
(function init() {
  const siteSel = document.getElementById('fSite');
  D.sites.forEach(s => {
    const o = document.createElement('option');
    o.value = s; o.text = s;
    siteSel.appendChild(o);
  });
  const srSel = document.getElementById('siteReasonSel');
  D.sites.forEach(s => {
    const o = document.createElement('option');
    o.value = s; o.text = s;
    srSel.appendChild(o);
  });
  render();
})();

function resetFilters() {
  document.getElementById('fZone').value = 'All';
  document.getElementById('fSite').value = 'All';
  document.getElementById('fVert').value = 'All';
  render();
}

// ── filtered sites ─────────────────────────────────────────────────────────
function filteredSites() {
  const z = document.getElementById('fZone').value;
  const s = document.getElementById('fSite').value;
  let sites = D.sites;
  if (z !== 'All') sites = sites.filter(x => D.zone_of[x] === z);
  if (s !== 'All') sites = sites.filter(x => x === s);
  return sites;
}

// ── get data matrix depending on vertical filter ───────────────────────────
function getMatrix() {
  const v = document.getElementById('fVert').value;
  if (v === 'Apparel') return D.wk_app;
  if (v === 'Footwear') return D.wk_ftw;
  return D.wk_ov;
}

// ── conv helper ────────────────────────────────────────────────────────────
function getConv(mat, wk, site) {
  const ws = mat[String(wk)];
  if (!ws || !ws[site]) return null;
  return ws[site].c;
}
function getPF(mat, wk, site) {
  const ws = mat[String(wk)];
  if (!ws || !ws[site]) return {p:0, f:0};
  return {p: ws[site].p || 0, f: ws[site].f || 0};
}
function siteOverall(mat, site) {
  let tp = 0, tf = 0;
  D.weeks.forEach(w => {
    const ws = mat[String(w)];
    if (ws && ws[site]) { tp += ws[site].p||0; tf += ws[site].f||0; }
  });
  return {p:tp, f:tf, c: tp+tf>0 ? Math.round(tp/(tp+tf)*1000)/10 : null};
}
function globalOverall(mat, sites) {
  let tp = 0, tf = 0;
  sites.forEach(s => {
    const o = siteOverall(mat, s);
    tp += o.p; tf += o.f;
  });
  return {p:tp, f:tf, c: tp+tf>0 ? Math.round(tp/(tp+tf)*1000)/10 : null};
}

// ── cell colour ────────────────────────────────────────────────────────────
function cls(v) {
  if (v === null || v === undefined) return 'na';
  if (v >= D.target) return 'g';
  if (v >= D.target - 5) return 'y';
  return 'r';
}
function fmt(v) {
  if (v === null || v === undefined) return '<span class="na">—</span>';
  return v.toFixed(1) + '%';
}

// ── RENDER ──────────────────────────────────────────────────────────────────
function render() {
  const sites = filteredSites();
  const mat   = getMatrix();
  renderKPI(sites, mat);
  renderMonthTable(sites, mat);
  renderZoneTable(sites);
  renderWeekTable(sites, mat);
  renderSiteTable(sites, mat);
  renderSampleMonitor(sites);
  renderReasonPanel();
  renderDeclining(sites, mat);
  renderWoW(sites, mat);
}

// ── KPI ────────────────────────────────────────────────────────────────────
function renderKPI(sites, mat) {
  const ov   = globalOverall(D.wk_ov, sites);
  const app  = globalOverall(D.wk_app, sites);
  const ftw  = globalOverall(D.wk_ftw, sites);
  const total = ov.p + ov.f;
  const passing = sites.filter(s => {
    const o = siteOverall(mat, s);
    return o.c !== null && o.c >= D.target;
  }).length;

  const cards = [
    {label:'Overall Conv%', val: ov.c !== null ? ov.c.toFixed(1)+'%' : '—',
     sub: `${ov.p.toLocaleString()} pass / ${ov.f.toLocaleString()} fail`,
     color: ov.c !== null ? (ov.c >= D.target ? 'green' : 'red') : 'blue'},
    {label:'Apparel Conv%', val: app.c !== null ? app.c.toFixed(1)+'%' : '—',
     sub: `${app.p.toLocaleString()} pass / ${app.f.toLocaleString()} fail`,
     color: app.c !== null ? (app.c >= D.target ? 'green' : 'red') : 'purple'},
    {label:'Footwear Conv%', val: ftw.c !== null ? ftw.c.toFixed(1)+'%' : '—',
     sub: `${ftw.p.toLocaleString()} pass / ${ftw.f.toLocaleString()} fail`,
     color: ftw.c !== null ? (ftw.c >= D.target ? 'green' : 'red') : 'orange'},
    {label:'Total Samples', val: total.toLocaleString(),
     sub: 'across all selected sites', color:'blue'},
    {label:'Sites ≥ Target', val: `${passing}/${sites.length}`,
     sub: 'sites meeting 90% target', color: passing === sites.length ? 'green' : 'orange'},
  ];

  document.getElementById('kpiRow').innerHTML = cards.map(c =>
    `<div class="kpi ${c.color}">
       <div class="label">${c.label}</div>
       <div class="value">${c.val}</div>
       <div class="sub">${c.sub}</div>
     </div>`
  ).join('');
}

// ── MONTH-WISE TABLE ────────────────────────────────────────────────────────
function renderMonthTable(sites, mat) {
  const months = D.months;
  let h = '<thead><tr><th class="left">Month</th>';
  sites.forEach(s => { h += `<th>${s}</th>`; });
  if (sites.length > 1) h += '<th>Pan India</th>';
  h += '</tr></thead><tbody>';

  months.forEach(m => {
    h += `<tr><td class="left">${m}</td>`;
    const wks = D.weeks.filter(w => D.wk_to_month[w] === m);
    let tp = 0, tf = 0;
    sites.forEach(s => {
      let sp = 0, sf = 0;
      wks.forEach(w => { const pf = getPF(mat, w, s); sp += pf.p; sf += pf.f; });
      const c = sp + sf > 0 ? Math.round(sp/(sp+sf)*1000)/10 : null;
      tp += sp; tf += sf;
      h += `<td class="${cls(c)}">${fmt(c)}</td>`;
    });
    if (sites.length > 1) {
      const c = tp + tf > 0 ? Math.round(tp/(tp+tf)*1000)/10 : null;
      h += `<td class="${cls(c)}" style="font-weight:700">${fmt(c)}</td>`;
    }
    h += '</tr>';
  });

  // Overall row
  h += '<tr class="total-row"><td class="left">Overall</td>';
  let gp = 0, gf = 0;
  sites.forEach(s => {
    const o = siteOverall(mat, s);
    gp += o.p; gf += o.f;
    h += `<td class="${cls(o.c)}">${fmt(o.c)}</td>`;
  });
  if (sites.length > 1) {
    const c = gp + gf > 0 ? Math.round(gp/(gp+gf)*1000)/10 : null;
    h += `<td class="${cls(c)}">${fmt(c)}</td>`;
  }
  h += '</tr></tbody>';
  document.getElementById('monthTbl').innerHTML = h;
}

// ── ZONE-WISE TABLE ─────────────────────────────────────────────────────────
function renderZoneTable(sites) {
  const zones = ['East','North','South','West'];
  const months = D.months;
  const mat = D.wk_ov;

  let h = '<thead><tr><th class="left">Zone</th><th>#Sites</th>';
  months.forEach(m => { h += `<th>${m}</th>`; });
  h += '<th>Overall</th><th>vs Target</th></tr></thead><tbody>';

  const fZone = document.getElementById('fZone').value;
  const zonesToShow = fZone !== 'All' ? [fZone] : zones;

  zonesToShow.forEach(z => {
    const zSites = sites.filter(s => D.zone_of[s] === z);
    if (zSites.length === 0) return;
    h += `<tr><td class="left">${z}</td><td>${zSites.length}</td>`;
    months.forEach(m => {
      const wks = D.weeks.filter(w => D.wk_to_month[w] === m);
      let tp = 0, tf = 0;
      zSites.forEach(s => wks.forEach(w => {
        const pf = getPF(mat, w, s); tp += pf.p; tf += pf.f;
      }));
      const c = tp + tf > 0 ? Math.round(tp/(tp+tf)*1000)/10 : null;
      h += `<td class="${cls(c)}">${fmt(c)}</td>`;
    });
    const o = globalOverall(mat, zSites);
    const gap = o.c !== null ? (o.c - D.target).toFixed(1) : null;
    h += `<td class="${cls(o.c)}" style="font-weight:700">${fmt(o.c)}</td>`;
    h += `<td class="${gap !== null ? (parseFloat(gap)>=0?'g':'r') : 'na'}">
      ${gap !== null ? (parseFloat(gap)>=0?'✅ +':'⚠️ ')+gap+'%' : '—'}</td>`;
    h += '</tr>';
  });

  // Pan India row
  if (sites.length > 1) {
    h += '<tr class="total-row"><td class="left">Pan India</td>';
    h += `<td>${sites.length}</td>`;
    months.forEach(m => {
      const wks = D.weeks.filter(w => D.wk_to_month[w] === m);
      let tp = 0, tf = 0;
      sites.forEach(s => wks.forEach(w => {
        const pf = getPF(mat, w, s); tp += pf.p; tf += pf.f;
      }));
      const c = tp + tf > 0 ? Math.round(tp/(tp+tf)*1000)/10 : null;
      h += `<td class="${cls(c)}">${fmt(c)}</td>`;
    });
    const o = globalOverall(mat, sites);
    const gap = o.c !== null ? (o.c - D.target).toFixed(1) : null;
    h += `<td class="${cls(o.c)}">${fmt(o.c)}</td>`;
    h += `<td class="${gap !== null ? (parseFloat(gap)>=0?'g':'r') : 'na'}">
      ${gap !== null ? (parseFloat(gap)>=0?'✅ +':'⚠️ ')+gap+'%' : '—'}</td>`;
    h += '</tr>';
  }
  h += '</tbody>';
  document.getElementById('zoneTbl').innerHTML = h;
}

// ── WEEK-WISE TABLE ─────────────────────────────────────────────────────────
function renderWeekTable(sites, mat) {
  let h = '<thead><tr><th class="left">Week</th><th>Month</th>';
  sites.forEach(s => { h += `<th>${s}</th>`; });
  if (sites.length > 1) h += '<th>Pan India</th>';
  h += '</tr></thead><tbody>';

  D.weeks.forEach(w => {
    h += `<tr><td class="left">Wk ${w}</td><td>${D.wk_to_month[w] || ''}</td>`;
    let tp = 0, tf = 0;
    sites.forEach(s => {
      const c = getConv(mat, w, s);
      const pf = getPF(mat, w, s); tp += pf.p; tf += pf.f;
      h += `<td class="${cls(c)}">${fmt(c)}</td>`;
    });
    if (sites.length > 1) {
      const c = tp + tf > 0 ? Math.round(tp/(tp+tf)*1000)/10 : null;
      h += `<td class="${cls(c)}" style="font-weight:700">${fmt(c)}</td>`;
    }
    h += '</tr>';
  });

  // Overall row
  h += '<tr class="total-row"><td class="left">Overall</td><td></td>';
  let gp = 0, gf = 0;
  sites.forEach(s => {
    const o = siteOverall(mat, s); gp += o.p; gf += o.f;
    h += `<td class="${cls(o.c)}">${fmt(o.c)}</td>`;
  });
  if (sites.length > 1) {
    const c = gp + gf > 0 ? Math.round(gp/(gp+gf)*1000)/10 : null;
    h += `<td class="${cls(c)}">${fmt(c)}</td>`;
  }
  h += '</tr></tbody>';
  document.getElementById('weekTbl').innerHTML = h;
}

// ── SITE-WISE TABLE (frozen first col) ─────────────────────────────────────
function renderSiteTable(sites, mat) {
  const weeks = D.weeks;
  let h = '<thead><tr><th class="frozen left">Site</th><th>Zone</th><th>Overall</th>';
  weeks.forEach(w => { h += `<th>Wk ${w}</th>`; });
  h += '<th class="obs-col">Observation</th></tr></thead><tbody>';

  sites.forEach(s => {
    const o = siteOverall(mat, s);
    h += `<tr>
      <td class="frozen left">${s}</td>
      <td>${D.zone_of[s] || '—'}</td>
      <td class="${cls(o.c)}">${fmt(o.c)}<br><span style="font-size:10px;color:#718096">${o.p+o.f} smpls</span></td>`;
    weeks.forEach(w => {
      const c = getConv(mat, w, s);
      const pf = getPF(mat, w, s);
      const smp = pf.p + pf.f;
      h += `<td class="${cls(c)}">${fmt(c)}${smp>0?`<br><span style="font-size:9px;color:#718096">(${smp})</span>`:''}</td>`;
    });
    h += `<td class="obs-col"><input type="text" placeholder="note…"
      style="width:100%;border:1px solid #e2e8f0;border-radius:4px;padding:4px 6px;font-size:11px;"
      id="obs_${s.replace(/\s/g,'_')}"></td></tr>`;
  });

  // Pan India row
  if (sites.length > 1) {
    const o = globalOverall(mat, sites);
    h += `<tr class="total-row"><td class="frozen left">Pan India</td><td>All</td>
      <td class="${cls(o.c)}">${fmt(o.c)}<br><span style="font-size:10px">${o.p+o.f} smpls</span></td>`;
    weeks.forEach(w => {
      let tp = 0, tf = 0;
      sites.forEach(s => { const pf = getPF(mat, w, s); tp += pf.p; tf += pf.f; });
      const c = tp + tf > 0 ? Math.round(tp/(tp+tf)*1000)/10 : null;
      h += `<td class="${cls(c)}">${fmt(c)}</td>`;
    });
    h += '<td></td></tr>';
  }
  h += '</tbody>';
  document.getElementById('siteTbl').innerHTML = h;
}

// ── SAMPLE MONITOR ──────────────────────────────────────────────────────────
function renderSampleMonitor(sites) {
  const mat = getMatrix();
  const sortedWks = [...D.weeks].sort((a,b)=>b-a);
  const lastWk = sortedWks[0];
  const prevWk = sortedWks[1];

  let html = '';
  sites.forEach(s => {
    const cur  = (getPF(mat, lastWk, s).p + getPF(mat, lastWk, s).f);
    const prev = prevWk ? (getPF(mat, prevWk, s).p + getPF(mat, prevWk, s).f) : null;
    const drop = prev && prev > 0 ? ((prev - cur) / prev * 100) : 0;

    let cls2 = '';
    let tag = '';
    if (cur < 100) { cls2 = 'low'; tag = '⚠️ Low sample (<100)'; }
    if (drop >= 50 && prev > 0) { cls2 = 'alert'; tag = `🔴 ${drop.toFixed(0)}% WoW drop`; }

    html += `<div class="sample-card ${cls2}">
      <div class="site-name">${s}</div>
      <div class="count">${cur.toLocaleString()}</div>
      <div class="prev">Wk ${lastWk} samples</div>
      ${prev !== null ? `<div class="prev">Prev wk: ${prev.toLocaleString()}</div>` : ''}
      ${tag ? `<div class="tag">${tag}</div>` : ''}
    </div>`;
  });
  document.getElementById('sampleGrid').innerHTML = html || '<span class="info-msg">No data for selected filters.</span>';
}

// ── FAILURE REASONS ─────────────────────────────────────────────────────────
function setReasonTab(t) {
  reasonTab = t;
  document.getElementById('tabOv').classList.toggle('active', t==='ov');
  document.getElementById('tabApp').classList.toggle('active', t==='app');
  document.getElementById('tabFtw').classList.toggle('active', t==='ftw');
  renderReasonPanel();
}

function renderReasonPanel() {
  const sites = filteredSites();
  const rawList = reasonTab === 'ov' ? D.fr_ov : reasonTab === 'app' ? D.fr_app : D.fr_ftw;
  const list = rawList.filter(x => sites.includes(x.site));

  // aggregate by reason
  const agg = {};
  list.forEach(x => { agg[x.reason] = (agg[x.reason]||0) + x.count; });
  const sorted = Object.entries(agg).sort((a,b)=>b[1]-a[1]).slice(0, 15);
  const max = sorted.length ? sorted[0][1] : 1;

  if (!sorted.length) {
    document.getElementById('reasonPanel').innerHTML = '<span class="info-msg">No failures for selected filters.</span>';
    return;
  }
  let h = '<div class="reason-bar-wrap">';
  sorted.forEach(([reason, count]) => {
    const pct = Math.round(count/max*100);
    h += `<div class="reason-row">
      <div class="reason-label" title="${reason}">${reason}</div>
      <div class="reason-bar-bg"><div class="reason-bar-fill" style="width:${pct}%"></div></div>
      <div class="reason-count">${count}</div>
    </div>`;
  });
  h += '</div>';
  document.getElementById('reasonPanel').innerHTML = h;
}

// ── SITE REASON ─────────────────────────────────────────────────────────────
function renderSiteReason() {
  const s = document.getElementById('siteReasonSel').value;
  if (!s) { document.getElementById('siteReasonPanel').innerHTML = ''; return; }

  const combined = [...D.fr_ov].filter(x => x.site === s);
  const agg = {};
  combined.forEach(x => { agg[x.reason] = (agg[x.reason]||0) + x.count; });
  const sorted = Object.entries(agg).sort((a,b)=>b[1]-a[1]);
  const total = sorted.reduce((s,[,c])=>s+c,0);
  const max = sorted.length ? sorted[0][1] : 1;

  if (!sorted.length) {
    document.getElementById('siteReasonPanel').innerHTML = '<span class="info-msg">No failures recorded for this site.</span>';
    return;
  }
  let h = `<div style="margin-bottom:8px;font-size:12px;color:#4a5568;">Total failures: <strong>${total}</strong></div>`;
  h += '<div class="reason-bar-wrap">';
  sorted.forEach(([reason, count]) => {
    const pct = Math.round(count/max*100);
    const share = Math.round(count/total*100);
    h += `<div class="reason-row">
      <div class="reason-label" title="${reason}">${reason}</div>
      <div class="reason-bar-bg"><div class="reason-bar-fill" style="width:${pct}%"></div></div>
      <div class="reason-count">${count}<span style="font-size:9px;color:#a0aec0"> (${share}%)</span></div>
    </div>`;
  });
  h += '</div>';
  document.getElementById('siteReasonPanel').innerHTML = h;
}

// ── DECLINING SITES ─────────────────────────────────────────────────────────
function renderDeclining(sites, mat) {
  const sortedWks = [...D.weeks].sort((a,b)=>a-b);
  const last4 = sortedWks.slice(-4);
  if (last4.length < 2) {
    document.getElementById('declinePanel').innerHTML = '<span class="info-msg">Need at least 2 weeks of data.</span>';
    return;
  }

  const declining = [];
  sites.forEach(s => {
    const vals = last4.map(w => getConv(mat, w, s)).filter(v => v !== null);
    if (vals.length < 2) return;
    const isDecline = vals.every((v, i) => i === 0 || v <= vals[i-1]);
    const firstLast = vals[0] - vals[vals.length-1];
    if (isDecline && firstLast > 0) {
      declining.push({site: s, vals, drop: firstLast.toFixed(1)});
    }
  });

  if (!declining.length) {
    document.getElementById('declinePanel').innerHTML = '<span class="no-decline">✅ No consistently declining sites in the last 4 weeks!</span>';
    return;
  }
  let h = '<div class="decline-grid">';
  declining.sort((a,b)=>b.drop-a.drop).forEach(d => {
    const trend = d.vals.map((v,i) => `Wk${last4[i]}: ${v.toFixed(1)}%`).join(' → ');
    h += `<div class="decline-card">
      <div class="site">${d.site}</div>
      <div class="trend">▼ ${d.drop}% drop over 4 weeks</div>
      <div style="font-size:10px;color:#718096;margin-top:4px">${trend}</div>
    </div>`;
  });
  h += '</div>';
  document.getElementById('declinePanel').innerHTML = h;
}

// ── WoW CHART ───────────────────────────────────────────────────────────────
function renderWoW(sites, mat) {
  const sortedWks = [...D.weeks].sort((a,b)=>a-b);
  const showWks = sortedWks.slice(-12); // last 12 weeks

  const colors = ['#e94560','#4299e1','#48bb78','#ed8936','#9f7aea','#f6e05e',
                  '#fc8181','#68d391','#63b3ed','#b794f4','#fbd38d','#76e4f7'];

  const showSites = sites.slice(0, 8); // max 8 sites for readability
  const maxH = 140;

  // get max conv for scaling
  let maxC = 0;
  showSites.forEach(s => showWks.forEach(w => {
    const c = getConv(mat, w, s);
    if (c && c > maxC) maxC = c;
  }));
  maxC = Math.max(maxC, D.target + 5, 100);

  let h = '<div class="bar-chart">';
  showWks.forEach(w => {
    h += `<div style="display:flex;flex-direction:column;align-items:center;gap:2px;">`;
    h += `<div style="display:flex;align-items:flex-end;gap:2px;height:${maxH}px;">`;
    showSites.forEach((s, i) => {
      const c = getConv(mat, w, s);
      if (c === null) {
        h += `<div style="width:8px;height:4px;background:#e2e8f0;border-radius:2px 2px 0 0" title="${s}: no data"></div>`;
        return;
      }
      const barH = Math.round(c / maxC * maxH);
      h += `<div style="width:8px;height:${barH}px;background:${colors[i%colors.length]};
        border-radius:2px 2px 0 0" title="${s}: ${c.toFixed(1)}%"></div>`;
    });
    // target line reference
    const targetH = Math.round(D.target / maxC * maxH);
    h += `</div>`;
    h += `<div style="font-size:9px;color:#718096;margin-top:2px">Wk${w}</div>`;
    h += '</div>';
  });
  h += '</div>';

  // Legend
  h += '<div class="chart-legend">';
  showSites.forEach((s,i) => {
    h += `<div class="legend-item">
      <div class="legend-dot" style="background:${colors[i%colors.length]}"></div>
      ${s}
    </div>`;
  });
  h += '</div>';

  if (sites.length > 8) {
    h += `<div style="margin-top:8px;font-size:11px;color:#718096;">Showing first 8 sites. Select a specific site or zone to see individual trends.</div>`;
  }

  document.getElementById('wowChart').innerHTML = h;
}
</script>
</body>
</html>"""

# ─────────────────────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────────────────────
with st.spinner("⏳ Loading Refinishing data from Google Drive…"):
    df = load_data()

if df.empty:
    st.error("No data loaded. Please check Drive credentials and file IDs.")
    st.stop()

# Build aggregations
sites_all = sorted(df['s'].unique().tolist())
zone_of   = df.drop_duplicates('s').set_index('s')['z'].to_dict()
weeks_all = sorted(df['w'].unique().tolist())
months_present = [m for m in MONTHS_ORDER if m in df['m'].unique()]

wk_ov  = build_week_site(df)
wk_app = build_week_site(df[df['v'] == 'Apparel'])
wk_ftw = build_week_site(df[df['v'] == 'Footwear'])

fr_ov  = build_failure_reasons(df)
fr_app = build_failure_reasons(df[df['v'] == 'Apparel'])
fr_ftw = build_failure_reasons(df[df['v'] == 'Footwear'])

wk_to_month = {}
for w in weeks_all:
    sub = df[df['w'] == w]['m']
    if not sub.empty:
        wk_to_month[w] = sub.iloc[0]

DATA = {
    'sites': sites_all,
    'zone_of': zone_of,
    'weeks': weeks_all,
    'months': months_present,
    'wk_to_month': {str(k): v for k, v in wk_to_month.items()},
    'wk_ov':  {str(k): v for k, v in wk_ov.items()},
    'wk_app': {str(k): v for k, v in wk_app.items()},
    'wk_ftw': {str(k): v for k, v in wk_ftw.items()},
    'fr_ov':  fr_ov,
    'fr_app': fr_app,
    'fr_ftw': fr_ftw,
    'target': TARGET,
}

# Inject data into HTML
data_json = json.dumps(DATA, ensure_ascii=False)
html_final = TEMPLATE_HTML.replace('__DATA__', data_json)
html_clean = html_final.encode('utf-8', 'replace').decode('utf-8')

components.html(html_clean, height=7500, scrolling=False)
