import streamlit as st
import pandas as pd
import numpy as np
import json, io
import streamlit.components.v1 as components
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload

st.set_page_config(page_title="Refinishing Conversion", layout="wide")
st.markdown(
    "<style>.block-container{padding:0rem 0.5rem;max-width:100%}"
    "header[data-testid='stHeader']{height:0;display:none;}"
    "[data-testid='stAppViewBlockContainer']{overflow:hidden;}"
    "iframe{border:none !important;height:95vh !important;}</style>",
    unsafe_allow_html=True)

FILE_IDS = [
    "1ibNXvkUGNRhjuEQ37svRukLekD60Q9oc",
    "192ZfI7KCH-2GJ3i0eYVwefM0dAMbbErM",
    "1uxLSaaRHQQpvkwE6N2oubDS2KE2Pvukh",
    "1_W4uVC_6BnaQlijsS7aFqLJjGhGQhF88",
    "1VEDLEnSplFvPsktoLvZSgjYtSMnTJ6-5",
    "1bBCgtEZcMKDJNy-n0UvvIvTIebrqLMmj",
    "1BbC0pBBNiZJjA5Bx6Ia9kvTivgQGeMc4",
    "1yvwFqke1NgtdzXta0xuSkwmATVbPwkhO",
    "1r1_dJUQuzvklC1Cb_8NtmsoiT2jkf8jA",
]
TARGET = 90.0
MONTHS_ORDER = ['Jan 26','Feb 26','Mar 26','Apr 26','May 26','Jun 26',
                'Jul 26','Aug 26','Sep 26','Oct 26','Nov 26','Dec 26']
SITE_MAP = {
    'Bhiwandi bts':'Bhiwandi BTS RC','Bhiwandi BTS':'Bhiwandi BTS RC',
    'Bhiwandi BTS RC':'Bhiwandi BTS RC','Bhiwandi BTS Rc':'Bhiwandi BTS RC',
    'Malur BTS':'Malur BTS RC','Malur BTS RC':'Malur BTS RC',
    'Malur_BTS':'Malur BTS RC','Malur BTS Rc':'Malur BTS RC',
    'Haringhata':'Haringhata NLRC','Haringhata RC':'Haringhata NLRC',
    'Haringhata NLFC':'Haringhata NLRC','Haringhata NLRC':'Haringhata NLRC',
    'Haringhata NLFC 01':'Haringhata NLRC',
    'Sanpka':'Sanpka RC','Sankpa':'Sanpka RC','Sanpka RC':'Sanpka RC','Sankpa RC':'Sanpka RC',
    'FRK BTS RC':'FRK BTS RC','Frk_bts':'FRK BTS RC','FRK BTS':'FRK BTS RC',
    'Uluberia BTS RC':'Uluberia BTS RC','Ulu_ BTS_ RC':'Uluberia BTS RC',
    'Uluberia BTS Rc':'Uluberia BTS RC',
    'Bilaspur RPC':'Bilaspur RPC',
}

@st.cache_resource
def get_drive_service():
    creds = Credentials(token=None,
        refresh_token=st.secrets["GOOGLE_REFRESH_TOKEN"],
        client_id=st.secrets["GOOGLE_CLIENT_ID"],
        client_secret=st.secrets["GOOGLE_CLIENT_SECRET"],
        token_uri="https://oauth2.googleapis.com/token")
    return build("drive","v3",credentials=creds)

def safe_col(df, cols, default=None):
    for c in cols:
        if c in df.columns: return df[c].copy()
    return pd.Series([default]*len(df),index=df.index) if default is not None else pd.Series([np.nan]*len(df),index=df.index)

def cp(p,f): t=p+f; return round(p/t*100,1) if t>0 else None

@st.cache_data(ttl=3600)
def load_data():
    service = get_drive_service()
    dfs = []
    for fid in FILE_IDS:
        buf = io.BytesIO()
        dl = MediaIoBaseDownload(buf, service.files().get_media(fileId=fid))
        done=False
        while not done: _,done=dl.next_chunk()
        buf.seek(0)
        try: raw=pd.read_csv(buf,on_bad_lines='skip',low_memory=False)
        except TypeError:
            buf.seek(0); raw=pd.read_csv(buf,error_bad_lines=False,low_memory=False)
        raw.columns=[str(c).strip() for c in raw.columns]
        tmp=pd.DataFrame({
            's':safe_col(raw,['Warehouse Name','Warehouse ID']).astype(str).str.strip(),
            'z':safe_col(raw,['Zone','zone']).astype(str).str.strip().str.title(),
            'w':pd.to_numeric(safe_col(raw,['week','Week'],0),errors='coerce'),
            'r':safe_col(raw,['Result','result']).astype(str).str.strip(),
            'q':safe_col(raw,['QA remark','QA Remark']).astype(str).str.strip(),
            'v':safe_col(raw,['Vertical/Category','Vertical','vertical']).astype(str).str.strip(),
            't':safe_col(raw,['RF Task','rf_task'],'Unknown').astype(str).str.strip(),
        })
        dfs.append(tmp)
    df=pd.concat(dfs,ignore_index=True)
    df=df[df['w'].notna()&(df['w']>0)]
    df['w']=df['w'].astype(int)
    df=df[df['r'].isin(['Pass','Fail'])]
    df=df[~df['s'].str.lower().isin(['','nan','none','warehouse id','warehouse name'])]
    df['s']=df['s'].apply(lambda x:SITE_MAP.get(x,SITE_MAP.get(x.strip(),x.strip())))
    def nv(v):
        v=str(v).lower()
        if 'footwear' in v or 'sandal' in v: return 'Footwear'
        if 'apparel' in v or 'clothing' in v: return 'Apparel'
        return 'Other'
    df['v']=df['v'].apply(nv)
    def w2m(w):
        if w<=4: return 'Jan 26'
        if w<=8: return 'Feb 26'
        if w<=13: return 'Mar 26'
        if w<=17: return 'Apr 26'
        if w<=22: return 'May 26'
        if w<=26: return 'Jun 26'
        if w<=30: return 'Jul 26'
        if w<=35: return 'Aug 26'
        return 'Other'
    df['m']=df['w'].apply(w2m)
    return df

def build_payload(df):
    weeks=sorted(df['w'].unique().tolist())
    months=[m for m in MONTHS_ORDER if m in df['m'].unique()]
    sites=sorted(df['s'].unique().tolist())
    zones=['North','South','East','West']
    zone_of=df.drop_duplicates('s').set_index('s')['z'].to_dict()
    wk2m={int(w):df[df['w']==w]['m'].iloc[0] for w in weeks}

    def wpf(sub):
        p=int((sub['r']=='Pass').sum()); f=int((sub['r']=='Fail').sum())
        return p,f,cp(p,f)

    # base fact: week × site × vertical
    base=[]
    for (w,s,v),g in df.groupby(['w','s','v']):
        p,f,c=wpf(g)
        base.append({'w':int(w),'s':s,'v':v,'p':p,'f':f,'c':c,'z':zone_of.get(s,'')})

    # failure reasons per week × site (exclude no issue)
    fails_df=df[(df['r']=='Fail')&~df['q'].str.lower().str.contains('no issue',na=False)]
    fail_reasons=[]
    for (w,s,q),g in fails_df.groupby(['w','s','q']):
        fail_reasons.append({'w':int(w),'s':s,'reason':str(q),'count':int(len(g)),'v':str(g['v'].mode().iloc[0]) if len(g) else ''})

    # RF task × site failure heat
    task_heat=[]
    for (t,s),g in fails_df.groupby(['t','s']):
        f=int(len(g))
        task_heat.append({'task':str(t),'site':s,'fails':f})

    # site findings
    site_findings={}
    for s, sg in df.groupby('s'):
        p,f,c=wpf(sg)
        ap,af,ac=wpf(sg[sg['v']=='Apparel'])
        fp2,ff,fc=wpf(sg[sg['v']=='Footwear'])
        # worst week
        wk_data={}
        for w,wg in sg.groupby('w'):
            _p,_f,_c=wpf(wg); wk_data[int(w)]={'p':_p,'f':_f,'c':_c}
        wkvals=[(w,d['c']) for w,d in wk_data.items() if d['c'] is not None]
        worst_wk=min(wkvals,key=lambda x:x[1]) if wkvals else (0,0)
        best_wk=max(wkvals,key=lambda x:x[1]) if wkvals else (0,0)
        # top failure reason
        sfails=fails_df[fails_df['s']==s]
        top_reason=sfails['q'].value_counts().index[0] if len(sfails) else '—'
        top_reason_cnt=int(sfails['q'].value_counts().iloc[0]) if len(sfails) else 0
        total_fails=int(len(sfails))
        site_findings[s]={
            'zone':zone_of.get(s,''),
            'p':p,'f':f,'c':c,
            'ac':ac,'fc':fc,
            'worst_wk':worst_wk[0],'worst_c':worst_wk[1],
            'best_wk':best_wk[0],'best_c':best_wk[1],
            'top_reason':top_reason,'top_reason_cnt':top_reason_cnt,
            'total_fails':total_fails,
            'gap':round((c or 0)-TARGET,1),
        }

    # zone summary
    zone_summary={}
    for z in zones:
        zdf=df[df['z']==z]
        if len(zdf)==0: continue
        p,f,c=wpf(zdf)
        worst_site=None; worst_c=100
        for s,sg in zdf.groupby('s'):
            _,_,sc=wpf(sg)
            if sc is not None and sc<worst_c: worst_c=sc; worst_site=s
        ap,af,ac=wpf(zdf[zdf['v']=='Apparel'])
        fp2,ff,fc=wpf(zdf[zdf['v']=='Footwear'])
        top_r=fails_df[fails_df['z']==z]['q'].value_counts()
        zone_summary[z]={'p':p,'f':f,'c':c,'ac':ac,'fc':fc,
            'worst_site':worst_site,'worst_c':worst_c,
            'top_reason':str(top_r.index[0]) if len(top_r) else '—',
            'sites':[s for s in sites if zone_of.get(s,'')==z]}

    # overall stats
    ov_p,ov_f,ov_c=wpf(df)
    ap,af,ac_=wpf(df[df['v']=='Apparel'])
    fp2,ff,fc_=wpf(df[df['v']=='Footwear'])
    latest_wk=weeks[-1] if weeks else 0
    lwdf=df[df['w']==latest_wk]
    lw_p,lw_f,lw_c=wpf(lwdf)
    prev_wk=weeks[-2] if len(weeks)>1 else 0
    pwdf=df[df['w']==prev_wk]
    _,_,pw_c=wpf(pwdf)
    passing=[s for s in sites if (site_findings[s]['c'] or 0)>=TARGET]

    return {
        'weeks':weeks,'months':months,'sites':sites,'zone_of':zone_of,
        'wk2m':{str(k):v for k,v in wk2m.items()},
        'base':base,'fail_reasons':fail_reasons,'task_heat':task_heat,
        'site_findings':site_findings,'zone_summary':zone_summary,
        'meta':{
            'total_samples':ov_p+ov_f,'ov_c':ov_c,'ac':ac_,'fc':fc_,
            'latest_wk':latest_wk,'lw_c':lw_c,'pw_c':pw_c,
            'passing_sites':len(passing),'total_sites':len(sites),
            'months_range':f"{months[0] if months else ''} – {months[-1] if months else ''}",
        },
        'target':TARGET,
    }

with st.spinner("Loading Refinishing data…"):
    df=load_data()
if df.empty:
    st.error("No data loaded."); st.stop()
payload=build_payload(df)
data_str=json.dumps(payload,separators=(',',':'))

TEMPLATE_HTML = r"""<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Refinishing Conversion Dashboard</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@500;600;700&family=Inter:wght@400;500;600&display=swap" rel="stylesheet">
<style>
:root{
  --bg:#f6f7f9;--panel:#ffffff;--ink:#141b26;--muted:#6a7482;--faint:#98a1ad;
  --line:#e7eaef;--line2:#eef1f5;--accent:#2f5bd4;
  --north:#3b6fd4;--south:#0e9b8a;--east:#e0952a;--west:#8a4fd0;--unknown:#94a0af;
  --up:#d64550;--down:#1f9d6b;--hit:#1f9d6b;--miss:#d64550;--warn:#d4900a;
  --shadow:0 1px 2px rgba(20,27,38,.04),0 2px 8px rgba(20,27,38,.05);
}
*{box-sizing:border-box}
html,body{height:100%;overflow:hidden}
body{margin:0;background:var(--bg);color:var(--ink);
  font-family:Inter,-apple-system,Segoe UI,Roboto,sans-serif;font-size:13px;line-height:1.45;
  display:flex;flex-direction:column}
h1,h2,h3{font-family:"Space Grotesk",Inter,sans-serif;margin:0;letter-spacing:-.01em}
.num{font-family:"Space Grotesk",Inter,sans-serif;font-variant-numeric:tabular-nums}
.scroll-container{flex:1;overflow-y:auto;padding:0 20px 64px}
.wrap{max-width:1480px;margin:0 auto}
.split{display:grid;grid-template-columns:1.7fr 1fr;gap:14px}
@media(max-width:1000px){.split{grid-template-columns:1fr}}

.sticky-top-panel{position:sticky;top:0;z-index:100;background:var(--bg);
  border-bottom:1px solid var(--line);padding:0 20px}
header{padding:18px 0 10px}
.eyebrow{font-size:11px;font-weight:600;letter-spacing:.14em;text-transform:uppercase;color:var(--accent)}
header h1{font-size:24px;font-weight:700;margin-top:3px}
.sub{color:var(--muted);margin-top:4px;font-size:12.5px;display:flex;gap:10px;align-items:center;flex-wrap:wrap}
.pill-hdr{display:inline-flex;align-items:center;gap:5px;padding:3px 9px;border-radius:999px;
  font-size:11px;font-weight:600;border:1px solid var(--line);background:var(--panel)}
.pill-hdr.g{border-color:#b7e4c7;background:#f0fff4;color:var(--down)}
.pill-hdr.r{border-color:#ffc9c9;background:#fff5f5;color:var(--up)}
.pill-hdr.w{border-color:#ffe8a1;background:#fffbeb;color:var(--warn)}

.filters{padding:10px 0 14px}
.filters .row{display:flex;gap:14px;flex-wrap:wrap;align-items:flex-end}
.fg{display:flex;flex-direction:column;gap:5px;min-width:150px}
.fg label{font-size:10.5px;font-weight:600;letter-spacing:.08em;text-transform:uppercase;color:var(--muted)}
.chips{display:flex;gap:5px;flex-wrap:wrap;max-width:380px}
.chip{border:1px solid var(--line);background:var(--panel);border-radius:999px;
  padding:4px 10px;font-size:11.5px;cursor:pointer;user-select:none;transition:.12s;font-weight:500}
.chip:hover{border-color:var(--accent)}
.chip.on{background:var(--accent);border-color:var(--accent);color:#fff}
.chip[data-z]{padding-left:22px;position:relative}
.chip[data-z]::before{content:"";position:absolute;left:9px;top:50%;transform:translateY(-50%);
  width:7px;height:7px;border-radius:2px}
.chip[data-z="North"]::before{background:var(--north)}
.chip[data-z="South"]::before{background:var(--south)}
.chip[data-z="East"]::before{background:var(--east)}
.chip[data-z="West"]::before{background:var(--west)}
select{font-family:inherit;font-size:12.5px;padding:6px 9px;border:1px solid var(--line);
  border-radius:8px;background:var(--panel);color:var(--ink);min-width:150px}
.btn{border:1px solid var(--line);background:var(--panel);border-radius:8px;padding:7px 13px;
  font-size:12px;font-weight:600;cursor:pointer;font-family:inherit}
.btn:hover{border-color:var(--accent);color:var(--accent)}
.scope{font-size:12px;color:var(--muted);margin-left:auto}
.scope b{color:var(--ink);font-weight:600}

.kpis{display:grid;grid-template-columns:repeat(6,1fr);gap:12px;margin-bottom:26px;margin-top:16px}
.kpi{background:var(--panel);border:1px solid var(--line);border-radius:12px;padding:14px 15px;box-shadow:var(--shadow)}
.kpi .k{font-size:10.5px;font-weight:600;letter-spacing:.06em;text-transform:uppercase;color:var(--muted)}
.kpi .v{font-size:23px;font-weight:700;margin-top:6px;font-family:"Space Grotesk";font-variant-numeric:tabular-nums}
.kpi .d{font-size:11.5px;margin-top:3px;color:var(--faint)}
.kpi.hit .v{color:var(--hit)}.kpi.miss .v{color:var(--miss)}.kpi.warn .v{color:var(--warn)}.kpi.acc .v{color:var(--accent)}

section{margin-bottom:30px}
.shead{display:flex;align-items:baseline;gap:10px;margin-bottom:12px}
.shead .n{font-family:"Space Grotesk";font-weight:700;color:var(--accent);font-size:13px}
.shead h2{font-size:16px;font-weight:600}
.shead .h{font-size:12px;color:var(--muted);margin-left:6px}
.card{background:var(--panel);border:1px solid var(--line);border-radius:12px;box-shadow:var(--shadow);overflow:hidden}
.pad{padding:16px 18px}

.statrow{display:flex;gap:0;flex-wrap:wrap;border-bottom:1px solid var(--line2)}
.stat{padding:12px 18px;border-right:1px solid var(--line2)}
.stat .l{font-size:11px;color:var(--muted);display:flex;align-items:center;gap:6px;font-weight:500}
.stat .l .dot{width:8px;height:8px;border-radius:2px}
.stat .v{font-size:18px;font-weight:700;font-family:"Space Grotesk";font-variant-numeric:tabular-nums;margin-top:3px}
.stat.total{background:#f0f4ff}
.stat.total .l{color:var(--accent);font-weight:600}
.stat.hit .v{color:var(--hit)}.stat.miss .v{color:var(--miss)}.stat.warn .v{color:var(--warn)}

.tscroll{max-height:460px;overflow:auto}
table{width:100%;border-collapse:separate;border-spacing:0;font-size:12.5px}
thead th{position:sticky;top:0;z-index:2;background:#f2f4f8;color:var(--muted);
  font-weight:600;text-align:right;padding:9px 12px;font-size:11px;letter-spacing:.03em;
  text-transform:uppercase;border-bottom:1px solid var(--line);white-space:nowrap}
thead th:first-child,thead th.lft{text-align:left}
tbody td{padding:8px 12px;text-align:right;border-bottom:1px solid var(--line2);white-space:nowrap;font-variant-numeric:tabular-nums}
tbody td:first-child,tbody td.lft{text-align:left;font-weight:500}
tbody tr:hover{background:#f8fafc}
tr.tot-row td{background:#f2f4f8;font-weight:700;border-top:1px solid var(--line)}
.zband{border-left:3px solid var(--unknown)}
.zband.North{border-left-color:var(--north)}.zband.South{border-left-color:var(--south)}
.zband.East{border-left-color:var(--east)}.zband.West{border-left-color:var(--west)}

.cv-g{background:#e8f5ee;color:#1a7a4a;font-weight:600;border-radius:3px;padding:1px 3px}
.cv-y{background:#fef9e7;color:#946800;font-weight:600;border-radius:3px;padding:1px 3px}
.cv-r{background:#fdecea;color:#b91c1c;font-weight:600;border-radius:3px;padding:1px 3px}
.cv-n{color:var(--faint);font-size:11px}
.delta-up{color:var(--up);font-weight:600}.delta-dn{color:var(--down);font-weight:600}
.pill{display:inline-block;padding:2px 8px;border-radius:6px;font-size:11px;font-weight:600;background:#eef1f5;color:var(--muted)}
.muted{color:var(--muted)}
.hbar{height:9px;border-radius:3px;background:var(--accent);display:inline-block;vertical-align:middle}
.hbar-r{height:9px;border-radius:3px;background:var(--up);display:inline-block;vertical-align:middle}

.subhead{font-size:11px;font-weight:600;text-transform:uppercase;letter-spacing:.05em;color:var(--muted);padding:12px 18px 4px}
.note{font-size:11.5px;color:var(--faint);padding:0 18px 14px}
.controls{display:flex;gap:10px;align-items:center;padding:12px 18px;border-bottom:1px solid var(--line2);flex-wrap:wrap}

.finds{display:grid;grid-template-columns:repeat(auto-fill,minmax(280px,1fr));gap:12px}
.find{background:var(--panel);border:1px solid var(--line);border-radius:10px;padding:13px 15px;box-shadow:var(--shadow)}
.find .fh{display:flex;justify-content:space-between;align-items:baseline;margin-bottom:8px}
.find .fh .w{font-family:"Space Grotesk";font-weight:700;font-size:14px}
.find .fh .c{font-weight:700;font-variant-numeric:tabular-nums}
.find .fh .c.hit{color:var(--hit)}.find .fh .c.miss{color:var(--miss)}.find .fh .c.warn{color:var(--warn)}
.find .line{font-size:12px;padding:5px 0;border-top:1px solid var(--line2)}
.find .line .k{color:var(--muted);font-size:11px}
.find .line b{color:var(--ink)}

.dcards{display:grid;grid-template-columns:repeat(3,1fr);gap:12px;padding:16px 18px 4px}
.dc{border:1px solid var(--line);border-radius:10px;padding:12px 14px;background:#fafbfd}
.dc .l{font-size:10.5px;text-transform:uppercase;letter-spacing:.06em;color:var(--muted);font-weight:600}
.dc .v{font-size:15px;font-weight:700;margin-top:4px;font-family:"Space Grotesk"}
.dc .v.hit{color:var(--hit)}.dc .v.miss{color:var(--miss)}.dc .v.warn{color:var(--warn)}
.two{display:grid;grid-template-columns:1fr 1fr;gap:0}
.two>div:first-child{border-right:1px solid var(--line2)}
tr.row-selected td{background:#eef2ff !important;font-weight:600}
tr.row-selected td.lft{color:var(--accent)}
.site-tag{display:inline-flex;align-items:center;gap:6px;padding:2px 8px;border-radius:6px;
  font-size:11px;font-weight:600;background:#eef2ff;color:var(--accent);border:1px solid #c7d4ff}
.site-tag .x{cursor:pointer;font-size:12px;color:var(--accent);margin-left:2px}
.site-tag .x:hover{color:var(--up)}
@media(max-width:1000px){.kpis{grid-template-columns:repeat(3,1fr)}.dcards,.two{grid-template-columns:1fr}}
@media(prefers-reduced-motion:reduce){*{transition:none!important}}
</style>

<div class="sticky-top-panel">
<div class="wrap">
  <header>
    <div class="eyebrow">Reverse Chain · Returns Centre · Lifestyle</div>
    <h1>Refinishing Conversion Dashboard</h1>
    <div class="sub" id="subline">Loading…</div>
  </header>
  <div class="filters">
    <div class="row">
      <div class="fg"><label>Zone</label><div class="chips" id="f-zone"></div></div>
      <div class="fg"><label>Month</label><div class="chips" id="f-month"></div></div>
      <div class="fg"><label>Vertical</label><div class="chips" id="f-vert"></div></div>
      <div class="fg"><label>Week</label>
        <div class="chips" id="f-week" style="max-width:500px;flex-wrap:wrap"></div>
      </div>
      <div class="fg"><label>Week range <span style="font-size:9px;color:var(--faint)">(when no week selected)</span></label>
        <select id="f-wkrange" onchange="render()">
          <option value="last8">Last 8 weeks</option>
          <option value="all">All weeks</option>
          <option value="last4">Last 4 weeks</option>
          <option value="last12">Last 12 weeks</option>
        </select>
      </div>
      <div class="fg"><label>Site</label>
        <select id="f-site" onchange="render()"><option value="">All sites</option></select>
      </div>
      <button class="btn" id="reset-btn">Reset filters</button>
      <div class="scope" id="scope"></div>
    </div>
  </div>
</div>
</div>

<div class="scroll-container"><div class="wrap">

<div class="kpis" id="kpis"></div>

<section>
  <div class="shead"><span class="n">01</span><h2>Month × site conversion %</h2><span class="h">all months · then last 8 weeks · with MoM % change</span></div>
  <div class="card tscroll"><table id="month-trend"></table></div>
</section>

<section>
  <div class="shead"><span class="n">02</span><h2>Zone hotspots</h2><span class="h">worst site · top failure · apparel vs footwear gap</span></div>
  <div class="card" style="margin-bottom:14px">
    <div class="subhead">Zone × week (Pan India &amp; zone-wise conversion %)</div>
    <div class="tscroll"><table id="zone-trend"></table></div>
  </div>
  <div class="finds" id="zone-finds"></div>
</section>

<section>
  <div class="shead"><span class="n">03</span><h2>Vertical breakdown</h2><span class="h">Apparel vs Footwear · last 8 weeks · site × vertical conversion</span></div>
  <div class="split">
    <div class="card tscroll"><div class="subhead" id="vert-subhead">Site × vertical — Last 8 weeks</div><table id="vert-table"></table></div>
    <div class="card" style="min-width:0;overflow:hidden">
      <div style="display:flex;align-items:center;gap:8px;padding:12px 18px 4px;border-bottom:1px solid var(--line2)">
        <span style="font-size:11px;font-weight:600;letter-spacing:.05em;text-transform:uppercase;color:var(--muted)" id="reason-head">Failure reasons</span>
        <span id="reason-site-tag" style="margin-left:4px"></span>
      </div>
      <div style="overflow-x:hidden"><table id="reason-table" style="table-layout:fixed;width:100%"></table></div>
      <div class="subhead" style="margin-top:8px">Week-on-week · top 5 failure reasons (%)</div>
      <div class="note" style="padding:4px 18px 6px">Bar = % share of that week's total failures · Trend = first vs last week in view</div>
      <div style="overflow-x:auto;padding:0 4px 10px"><table id="wow-reason-table" style="width:100%;font-size:11px"></table></div>
    </div>
  </div>
  <div style="margin-top:14px"><div class="finds" id="site-finds"></div></div>
</section>

<section>
  <div class="shead"><span class="n">04</span><h2>RF task × site failure heat map</h2><span class="h">which refinishing task drives most failures · per site</span></div>
  <div class="card tscroll"><table id="task-heat"></table></div>
  <div class="note">Cell shading intensity = failure count (darker = more failures).</div>
</section>

<section>
  <div class="shead"><span class="n">05</span><h2>Week-wise failure drill</h2><span class="h">select a week · stat row + reason breakdown</span></div>
  <div class="card">
    <div class="controls"><span class="muted">Select week</span><select id="drill-wk"></select><span class="note" style="padding:0" id="drill-note"></span></div>
    <div class="statrow" id="drill-stats"></div>
    <div class="tscroll"><table id="drill-table"></table></div>
  </div>
</section>

</div></div>

<script>
const D=/*__RF_DATA__*/;
const ZC={North:'#3b6fd4',South:'#0e9b8a',East:'#e0952a',West:'#8a4fd0',Unknown:'#94a0af'};
const state={zone:new Set(),month:new Set(),vert:new Set(),week:new Set()};
let selectedSite=null;

function cvCls(v){if(v===null||v===undefined)return'cv-n';if(v>=D.target)return'cv-g';if(v>=D.target-5)return'cv-y';return'cv-r';}
function fmt(v,d=1){if(v===null||v===undefined)return'<span class="cv-n">—</span>';return`<span class="${cvCls(v)}">${v.toFixed(d)}%</span>`;}
function fmtPlain(v){if(v===null||v===undefined)return'—';return v.toFixed(1)+'%';}
function n(v){return v===null||v===undefined?'—':Number(v).toLocaleString('en-IN');}
function delta(a,b){if(a===null||b===null)return'';const d=b-a;const s=d>0?`<span class="delta-up">▲ ${d.toFixed(1)}%</span>`:`<span class="delta-dn">▼ ${Math.abs(d).toFixed(1)}%</span>`;return s;}

function chip(txt,set,val,zone){
  const c=document.createElement('span');
  c.className='chip'+(set.has(val)?' on':'');
  c.textContent=txt;
  if(zone)c.dataset.z=val;
  c.onclick=()=>{set.has(val)?set.delete(val):set.add(val);render();};
  return c;
}
function buildFilters(){
  const fz=document.getElementById('f-zone');
  ['North','South','East','West'].forEach(z=>fz.appendChild(chip(z,state.zone,z,true)));
  const fm=document.getElementById('f-month');
  D.months.forEach(m=>fm.appendChild(chip(m,state.month,m,false)));
  const fv=document.getElementById('f-vert');
  ['Apparel','Footwear'].forEach(v=>fv.appendChild(chip(v,state.vert,v,false)));
  // week chips — compact style
  const fw=document.getElementById('f-week');
  D.weeks.forEach(w=>{
    const c=document.createElement('span');
    c.className='chip'+(state.week.has(w)?' on':'');
    c.textContent='Wk'+w;
    c.style.padding='3px 7px';c.style.fontSize='11px';
    c.dataset.wk=w;
    c.onclick=()=>{state.week.has(w)?state.week.delete(w):state.week.add(w);render();};
    fw.appendChild(c);
  });
  const fs=document.getElementById('f-site');
  D.sites.forEach(s=>{const o=document.createElement('option');o.value=s;o.text=s;fs.appendChild(o);});
  const dw=document.getElementById('drill-wk');
  D.weeks.slice().reverse().forEach(w=>{const o=document.createElement('option');o.value=w;o.text='Wk '+w+' · '+(D.wk2m[w]||'');dw.appendChild(o);});
  dw.onchange=drawDrill;
  document.getElementById('reset-btn').onclick=()=>{
    state.zone.clear();state.month.clear();state.vert.clear();state.week.clear();
    document.getElementById('f-site').value='';
    document.getElementById('f-wkrange').value='last8';
    selectedSite=null;
    buildChips();render();
  };
}
function buildChips(){
  document.querySelectorAll('#f-zone .chip').forEach(c=>c.classList.toggle('on',state.zone.has(c.dataset.z)));
  document.querySelectorAll('#f-month .chip').forEach(c=>c.classList.toggle('on',state.month.has(c.textContent)));
  document.querySelectorAll('#f-vert .chip').forEach(c=>c.classList.toggle('on',state.vert.has(c.textContent)));
  document.querySelectorAll('#f-week .chip').forEach(c=>c.classList.toggle('on',state.week.has(parseInt(c.dataset.wk))));
}

function fSites(){
  const zf=[...state.zone],sf=document.getElementById('f-site').value;
  let list=D.sites;
  if(zf.length)list=list.filter(s=>zf.includes(D.zone_of[s]));
  if(sf)list=list.filter(s=>s===sf);
  return list;
}
function fWeeks(){
  // Priority: 1) individual week chips, 2) month chips, 3) week range dropdown
  if(state.week.size>0) return D.weeks.filter(w=>state.week.has(w));
  const mf=[...state.month],wr=document.getElementById('f-wkrange').value;
  let wks=D.weeks;
  if(mf.length) return wks.filter(w=>mf.includes(D.wk2m[w]));
  if(wr==='last8') return D.weeks.slice(-8);
  if(wr==='last4') return D.weeks.slice(-4);
  if(wr==='last12') return D.weeks.slice(-12);
  return D.weeks; // all
}
function fVerts(){const vf=[...state.vert];return vf.length?vf:['Apparel','Footwear','Other'];}

function getBase(sites,weeks,verts){
  const vs=new Set(verts),ss=new Set(sites),ws=new Set(weeks);
  return D.base.filter(r=>ss.has(r.s)&&ws.has(r.w)&&vs.has(r.v));
}
function aggPFC(rows){
  let p=0,f=0;rows.forEach(r=>{p+=r.p;f+=r.f;});
  return{p,f,c:p+f>0?Math.round(p/(p+f)*1000)/10:null};
}

function render(){
  buildChips();
  const sites=fSites(),weeks=fWeeks(),verts=fVerts();
  const base=getBase(sites,weeks,verts);
  const ov=aggPFC(base);
  const abase=getBase(sites,weeks,['Apparel']);const app=aggPFC(abase);
  const fbase2=getBase(sites,weeks,['Footwear']);const ftw=aggPFC(fbase2);
  const lw=weeks[weeks.length-1],pw=weeks[weeks.length-2];
  const lwBase=getBase(sites,[lw],verts);const lw_=aggPFC(lwBase);
  const pwBase=pw?getBase(sites,[pw],verts):null;const pw_=pwBase?aggPFC(pwBase):{c:null};
  const passing=sites.filter(s=>{const o=aggPFC(getBase([s],weeks,verts));return o.c!==null&&o.c>=D.target;});

  // subline
  document.getElementById('subline').innerHTML=
    `${n(ov.p+ov.f)} samples · Pan India <b>${fmtPlain(ov.c)}</b> · ${sites.length} sites · ${weeks.length} weeks · ${D.meta.months_range}`;

  // scope
  document.getElementById('scope').innerHTML=`In scope: <b>${sites.length}</b> sites · <b>${weeks.length}</b> weeks`;

  // KPI
  const wowDelta=lw_.c!==null&&pw_.c!==null?lw_.c-pw_.c:null;
  const K=[
    {k:'Overall conv%',v:fmtPlain(ov.c),d:n(ov.p+ov.f)+' samples',cls:ov.c===null?'acc':(ov.c>=D.target?'hit':'miss')},
    {k:'Apparel conv%',v:fmtPlain(app.c),d:n(app.p+app.f)+' samples',cls:app.c===null?'acc':(app.c>=D.target?'hit':'miss')},
    {k:'Footwear conv%',v:fmtPlain(ftw.c),d:n(ftw.p+ftw.f)+' samples',cls:ftw.c===null?'acc':(ftw.c>=D.target?'hit':'miss')},
    {k:'Latest week',v:lw_.c!==null?fmtPlain(lw_.c):'—',d:'Wk '+lw+(wowDelta!==null?' · WoW '+(wowDelta>0?'▲ +':'▼ ')+Math.abs(wowDelta).toFixed(1)+'%':''),
      cls:lw_.c===null?'acc':(lw_.c>=D.target?'hit':(wowDelta!==null&&wowDelta<-3?'miss':'warn'))},
    {k:'Sites ≥ '+D.target+'%',v:passing.length+'/'+sites.length,d:passing.length===sites.length?'All on target':(sites.length-passing.length)+' below target',
      cls:passing.length===sites.length?'hit':(passing.length===0?'miss':'warn')},
    {k:'Failures (period)',v:n(ov.f),d:'pass rate gap: '+(ov.c!==null?(ov.c-D.target).toFixed(1):'—')+'%',cls:ov.f>5000?'miss':'warn'},
  ];
  document.getElementById('kpis').innerHTML=K.map(k=>
    `<div class="kpi ${k.cls}"><div class="k">${k.k}</div><div class="v num">${k.v}</div><div class="d">${k.d}</div></div>`).join('');

  // validate selectedSite against current filtered sites
  if(selectedSite && !sites.includes(selectedSite)) selectedSite=null;

  drawMonthTrend(sites,verts);
  drawZoneTrend(sites,weeks,verts);
  drawZoneFinds(sites,weeks,verts);
  drawVertTable(sites,weeks,verts);
  const reasonSites=selectedSite?[selectedSite]:sites;
  drawReasonTable(reasonSites,weeks,verts);
  drawWoWReasons(reasonSites,weeks,verts);
  drawTaskHeat(sites,weeks);
  drawSiteFinds(sites,weeks,verts);
  drawDrill();
}

function drawMonthTrend(sites,verts){
  const months=D.months;
  const last8=D.weeks.slice(-8);
  // build header: Site | Zone | [months] | [SEP] | [last 8 wks] | MoM% | Overall
  let h='<thead><tr><th class="lft">Site</th><th class="lft">Zone</th>';
  months.forEach((m,i)=>{
    const isLast=i===months.length-1;
    h+=`<th style="${isLast?'border-right:3px solid var(--line);':''}">${m}</th>`;
  });
  last8.forEach(w=>{
    h+=`<th style="background:#f8f9fd;font-size:10px">Wk${w}<br><span style="font-size:9px;font-weight:400;color:var(--faint)">${(D.wk2m[w]||'').replace(' 26','')}</span></th>`;
  });
  h+='<th>MoM%</th><th>Overall</th></tr></thead><tbody>';

  sites.forEach(s=>{
    const z=D.zone_of[s]||'';
    const mVals=months.map((m,i)=>{
      const wks=D.weeks.filter(w=>D.wk2m[w]===m);
      return aggPFC(getBase([s],wks,verts)).c;
    });
    const wkVals=last8.map(w=>aggPFC(getBase([s],[w],verts)).c);
    const ov2=aggPFC(getBase([s],D.weeks,verts));
    const momA=mVals[mVals.length-2],momB=mVals[mVals.length-1];
    h+=`<tr class="zband ${z}"><td class="lft">${s}</td><td class="lft muted" style="font-size:11px">${z}</td>`;
    mVals.forEach((c,i)=>{
      const isLast=i===mVals.length-1;
      h+=`<td style="${isLast?'border-right:3px solid var(--line);':''}">${fmt(c)}</td>`;
    });
    wkVals.forEach(c=>{h+=`<td style="background:#fafbfd">${fmt(c)}</td>`;});
    h+=`<td>${delta(momA,momB)}</td><td>${fmt(ov2.c)}</td></tr>`;
  });

  // Pan India row
  const piMVals=months.map(m=>{
    const wks=D.weeks.filter(w=>D.wk2m[w]===m);
    return aggPFC(getBase(sites,wks,verts)).c;
  });
  const piWkVals=last8.map(w=>aggPFC(getBase(sites,[w],verts)).c);
  const piOv=aggPFC(getBase(sites,D.weeks,verts));
  const piMomA=piMVals[piMVals.length-2],piMomB=piMVals[piMVals.length-1];
  h+='<tr class="tot-row"><td class="lft">Pan India</td><td class="lft muted" style="font-size:11px">All</td>';
  piMVals.forEach((c,i)=>{
    const isLast=i===piMVals.length-1;
    h+=`<td style="${isLast?'border-right:3px solid var(--line);':''}">${fmt(c)}</td>`;
  });
  piWkVals.forEach(c=>{h+=`<td style="background:#f2f4f8">${fmt(c)}</td>`;});
  h+=`<td>${delta(piMomA,piMomB)}</td><td>${fmt(piOv.c)}</td></tr>`;
  h+='</tbody>';
  document.getElementById('month-trend').innerHTML=h;
}

function drawZoneTrend(sites,weeks,verts){
  const zones=['North','South','East','West'].filter(z=>sites.some(s=>D.zone_of[s]===z));
  let h='<thead><tr><th>Zone</th>';
  weeks.forEach(w=>{h+=`<th>Wk ${w}</th>`;});
  h+='<th>Overall</th><th>vs target</th></tr></thead><tbody>';
  zones.forEach(z=>{
    const zs=sites.filter(s=>D.zone_of[s]===z);
    if(!zs.length)return;
    h+=`<tr class="zband ${z}"><td>${z}</td>`;
    weeks.forEach(w=>{const o=aggPFC(getBase(zs,[w],verts));h+=`<td>${fmt(o.c)}</td>`;});
    const ov2=aggPFC(getBase(zs,weeks,verts));
    const gap=ov2.c!==null?(ov2.c-D.target).toFixed(1):null;
    h+=`<td>${fmt(ov2.c)}</td>`;
    h+=`<td class="${gap!==null?(parseFloat(gap)>=0?'delta-dn':'delta-up'):''}">${gap!==null?(parseFloat(gap)>=0?'▼ +':'+▲ ')+gap+'%':'—'}</td></tr>`;
  });
  h+='<tr class="tot-row"><td>Pan India</td>';
  weeks.forEach(w=>{const o=aggPFC(getBase(sites,[w],verts));h+=`<td>${fmt(o.c)}</td>`;});
  const ov3=aggPFC(getBase(sites,weeks,verts));
  const gap2=ov3.c!==null?(ov3.c-D.target).toFixed(1):null;
  h+=`<td>${fmt(ov3.c)}</td><td class="${gap2!==null?(parseFloat(gap2)>=0?'delta-dn':'delta-up'):''}">${gap2!==null?(parseFloat(gap2)>=0?'▼ +':'▲ ')+gap2+'%':'—'}</td></tr>`;
  h+='</tbody>';
  document.getElementById('zone-trend').innerHTML=h;
}

function drawZoneFinds(sites,weeks,verts){
  const zones=['North','South','East','West'].filter(z=>sites.some(s=>D.zone_of[s]===z));
  const html=zones.map(z=>{
    const zs=sites.filter(s=>D.zone_of[s]===z);
    const ov2=aggPFC(getBase(zs,weeks,verts));
    const app2=aggPFC(getBase(zs,weeks,['Apparel']));
    const ftw2=aggPFC(getBase(zs,weeks,['Footwear']));
    // worst site
    let worstS=null,worstC=100;
    zs.forEach(s=>{const o=aggPFC(getBase([s],weeks,verts));if(o.c!==null&&o.c<worstC){worstC=o.c;worstS=s;}});
    const sf=D.site_findings;
    const topR=zs.map(s=>sf[s]).filter(Boolean).sort((a,b)=>b.total_fails-a.total_fails)[0];
    const gap=ov2.c!==null?(ov2.c-D.target).toFixed(1):'—';
    const ccls=ov2.c===null?'':ov2.c>=D.target?'hit':'miss';
    return `<div class="find">
      <div class="fh">
        <span class="w">${z}<span class="muted" style="font-size:11px;font-weight:500"> · ${zs.length} sites</span></span>
        <span class="c ${ccls}">${fmtPlain(ov2.c)}</span>
      </div>
      <div class="line"><span class="k">gap vs target: <b style="color:${parseFloat(gap)<0?'var(--up)':'var(--down)'}">${gap}%</b></span></div>
      <div class="line"><span class="k">apparel: <b>${fmtPlain(app2.c)}</b> · footwear: <b>${fmtPlain(ftw2.c)}</b></span></div>
      ${worstS?`<div class="line"><span class="k">worst site: <b>${worstS}</b> <span class="muted">${fmtPlain(worstC)}</span></span></div>`:''}
      ${topR?`<div class="line"><span class="k">top failure: <b>${topR.top_reason}</b></span></div>`:''}
    </div>`;
  }).join('');
  document.getElementById('zone-finds').innerHTML=html||'<span class="muted">No zone data.</span>';
}

function drawVertTable(sites,weeks,verts){
  // update subhead dynamically
  const wr=document.getElementById('f-wkrange').value;
  const mf=[...state.month];
  const wkLabel=state.week.size>0?'Wk '+[...state.week].sort((a,b)=>a-b).join(', Wk '):
    mf.length?mf.join(', '):
    wr==='last8'?'Last 8 weeks':wr==='last4'?'Last 4 weeks':wr==='last12'?'Last 12 weeks':'All weeks';
  const el=document.getElementById('vert-subhead');
  if(el)el.textContent=`Site × vertical — ${wkLabel} · ${weeks.length} weeks · click a row to filter right panel →`;

  let h='<thead><tr><th class="lft">Site</th><th class="lft">Zone</th><th>Apparel</th><th>Footwear</th><th>App samples</th><th>Ftw samples</th><th>Gap (App−Ftw)</th></tr></thead><tbody>';
  sites.forEach(s=>{
    const z=D.zone_of[s]||'';
    const app2=aggPFC(getBase([s],weeks,['Apparel']));
    const ftw2=aggPFC(getBase([s],weeks,['Footwear']));
    const gap=app2.c!==null&&ftw2.c!==null?(app2.c-ftw2.c).toFixed(1):null;
    const isSel=selectedSite===s;
    h+=`<tr class="zband ${z}${isSel?' row-selected':''}" style="cursor:pointer" onclick="selectSite('${s.replace(/'/g,"\\'")}')">
      <td class="lft">${s}${isSel?' <span style="color:var(--accent);font-size:10px">◀</span>':''}</td>
      <td class="lft muted" style="font-size:11px">${z}</td>
      <td>${fmt(app2.c)}</td><td>${fmt(ftw2.c)}</td>
      <td class="muted">${n(app2.p+app2.f)}</td><td class="muted">${n(ftw2.p+ftw2.f)}</td>
      <td class="${gap!==null?(parseFloat(gap)<0?'delta-up':'delta-dn'):'cv-n'}">${gap!==null?(parseFloat(gap)<0?'▲ ':'▼ ')+Math.abs(parseFloat(gap))+'%':'—'}</td></tr>`;
  });
  h+='</tbody>';
  document.getElementById('vert-table').innerHTML=h;
}

function selectSite(s){
  selectedSite=(selectedSite===s)?null:s;
  const sites=fSites(),weeks=fWeeks(),verts=fVerts();
  drawVertTable(sites,weeks,verts);
  const reasonSites=selectedSite?[selectedSite]:sites;
  drawReasonTable(reasonSites,weeks,verts);
  drawWoWReasons(reasonSites,weeks,verts);
}

function drawReasonTable(sites,weeks,verts){
  const ss=new Set(sites),ws=new Set(weeks);
  const list=D.fail_reasons.filter(r=>{
    if(!ss.has(r.s)||!ws.has(r.w))return false;
    if(verts.includes('Apparel')&&!verts.includes('Footwear'))return r.v==='Apparel';
    if(verts.includes('Footwear')&&!verts.includes('Apparel'))return r.v==='Footwear';
    return true;
  });
  const agg={};let tot=0;
  list.forEach(r=>{agg[r.reason]=(agg[r.reason]||0)+r.count;tot+=r.count;});
  const sorted=Object.entries(agg).sort((a,b)=>b[1]-a[1]).slice(0,10);
  const mx=sorted.length?sorted[0][1]:1;

  // update site tag in header
  const tagEl=document.getElementById('reason-site-tag');
  const vertLabel=verts.includes('Apparel')&&!verts.includes('Footwear')?' · Apparel':!verts.includes('Apparel')&&verts.includes('Footwear')?' · Footwear':'';
  document.getElementById('reason-head').textContent=`Failure reasons · ${n(tot)} total${vertLabel}`;
  if(selectedSite){
    tagEl.innerHTML=`<span class="site-tag">${selectedSite}<span class="x" onclick="selectSite('${selectedSite.replace(/'/g,"\\'")}')">✕</span></span>`;
  } else {
    tagEl.innerHTML=`<span style="font-size:10px;color:var(--faint)">all sites · click a row to filter</span>`;
  }

  let h='<colgroup><col style="width:52%"><col style="width:18%"><col style="width:14%"><col style="width:16%"></colgroup>';
  h+='<thead><tr><th class="lft">Reason</th><th></th><th>Count</th><th>%</th></tr></thead><tbody>';
  h+=sorted.map(([k,v])=>`<tr>
    <td class="lft" style="font-size:11px;white-space:normal" title="${k}">${k.length>32?k.slice(0,31)+'…':k}</td>
    <td><span class="hbar-r" style="width:${Math.max(3,v/mx*40)}px"></span></td>
    <td style="font-size:11px">${n(v)}</td>
    <td class="muted" style="font-size:11px">${tot?(v/tot*100).toFixed(1):0}%</td></tr>`).join('')
    ||'<tr><td colspan="4" class="muted" style="padding:10px">No failures.</td></tr>';
  document.getElementById('reason-table').innerHTML=h+'</tbody>';
}

function drawWoWReasons(sites,weeks,verts){
  const ss=new Set(sites),ws=new Set(weeks);
  const list=D.fail_reasons.filter(r=>{
    if(!ss.has(r.s)||!ws.has(r.w))return false;
    if(verts.includes('Apparel')&&!verts.includes('Footwear'))return r.v==='Apparel';
    if(verts.includes('Footwear')&&!verts.includes('Apparel'))return r.v==='Footwear';
    return true;
  });
  const totAgg={};
  list.forEach(r=>{totAgg[r.reason]=(totAgg[r.reason]||0)+r.count;});
  const top5=Object.entries(totAgg).sort((a,b)=>b[1]-a[1]).slice(0,5).map(([r])=>r);
  if(!top5.length){document.getElementById('wow-reason-table').innerHTML='<tr><td class="muted" style="padding:10px">No failure data.</td></tr>';return;}
  const cell={};
  list.filter(r=>top5.includes(r.reason)).forEach(r=>{
    const k=r.reason+'|'+r.w;cell[k]=(cell[k]||0)+r.count;
  });
  const wkTot={};
  weeks.forEach(w=>{wkTot[w]=list.filter(r=>r.w===w).reduce((s,r)=>s+r.count,0);});
  const RCOL=['#d64550','#e0952a','#8a4fd0','#0e9b8a','#3b6fd4'];
  const showWks=weeks; // show ALL filtered weeks - respects top filters
  let h='<thead><tr><th class="lft" style="font-size:10px;min-width:100px">Reason</th>';
  showWks.forEach(w=>{h+=`<th style="font-size:10px;text-align:center;min-width:48px">Wk${w}<br><span style="font-size:9px;font-weight:400;color:var(--faint)">${(D.wk2m[w]||'').replace(' 26','')}</span></th>`;});
  h+='<th style="font-size:10px;text-align:center;min-width:52px">Trend</th></tr></thead><tbody>';
  top5.forEach((r,ri)=>{
    const rshort=r.length>20?r.slice(0,19)+'…':r;
    const col=RCOL[ri%RCOL.length];
    const pctVals=showWks.map(w=>{
      const cnt=cell[r+'|'+w]||0;
      return wkTot[w]>0?Math.round(cnt/wkTot[w]*100):0;
    });
    const firstPct=pctVals[0],lastPct=pctVals[pctVals.length-1];
    const trendDiff=lastPct-firstPct;
    const trendHtml=firstPct===0?'—':trendDiff<0
      ?`<span class="delta-dn" style="font-size:10px">▼ ${Math.abs(trendDiff)}pp</span>`
      :trendDiff>0?`<span class="delta-up" style="font-size:10px">▲ +${trendDiff}pp</span>`
      :`<span style="font-size:10px;color:var(--muted)">→</span>`;
    h+=`<tr><td class="lft" style="font-size:11px;white-space:normal;vertical-align:middle" title="${r}">${rshort}</td>`;
    pctVals.forEach(pct=>{
      const barW=Math.round(pct/100*44);
      h+=`<td style="text-align:center;padding:5px 3px;vertical-align:middle">
        <div style="display:flex;flex-direction:column;align-items:center;gap:1px">
          <div style="width:44px;height:10px;background:var(--line2);border-radius:2px;overflow:hidden">
            <div style="width:${Math.max(pct>0?2:0,barW)}px;height:10px;background:${col};border-radius:2px"></div>
          </div>
          <span style="font-size:9px;font-weight:600;color:${col}">${pct>0?pct+'%':''}</span>
        </div></td>`;
    });
    h+=`<td style="text-align:center">${trendHtml}</td></tr>`;
  });
  h+='<tr style="background:#f2f4f8;border-top:1px solid var(--line)"><td class="lft" style="font-size:11px;font-weight:600">Total fails</td>';
  showWks.forEach(w=>{h+=`<td style="text-align:center;font-size:11px;font-weight:600">${n(wkTot[w]||0)}</td>`;});
  h+='<td></td></tr></tbody>';
  document.getElementById('wow-reason-table').innerHTML=h;
}

function drawTaskHeat(sites,weeks){
  const ss=new Set(sites),ws=new Set(weeks);
  const list=D.task_heat.filter(r=>ss.has(r.site));
  const tasks=[...new Set(list.map(r=>r.task))].filter(t=>t&&t!=='Unknown').sort();
  const cell={};let cmax=0;
  list.forEach(r=>{const k=r.task+'|'+r.site;cell[k]=(cell[k]||0)+r.fails;cmax=Math.max(cmax,cell[k]);});
  const rowT={};tasks.forEach(t=>{rowT[t]=0;sites.forEach(s=>{rowT[t]+=(cell[t+'|'+s]||0);});});
  const sorted_t=tasks.sort((a,b)=>rowT[b]-rowT[a]).slice(0,10);
  let h='<thead><tr><th>RF task</th>'+sites.map(s=>`<th title="${s}">${s.length>14?s.slice(0,13)+'…':s}</th>`).join('')+'<th>Total fails</th></tr></thead><tbody>';
  sorted_t.forEach(t=>{
    h+=`<tr><td>${t}</td>`;
    sites.forEach(s=>{const v=cell[t+'|'+s]||0;
      const a=cmax?v/cmax:0;
      const bg=v?`background:rgba(212,69,80,${(0.06+a*0.55).toFixed(2)});color:${a>0.55?'#fff':'inherit'}`:'color:#c3cad3';
      h+=`<td style="${bg}">${v||'·'}</td>`;
    });
    h+=`<td><b>${n(rowT[t])}</b></td></tr>`;
  });
  const colT={};sites.forEach(s=>{colT[s]=sorted_t.reduce((a,t)=>a+(cell[t+'|'+s]||0),0);});
  h+=`<tr style="background:#f2f4f8"><td><b>Total</b></td>`+sites.map(s=>`<td><b>${n(colT[s])}</b></td>`).join('')+`<td><b>${n(sorted_t.reduce((a,t)=>a+rowT[t],0))}</b></td></tr>`;
  document.getElementById('task-heat').innerHTML=h+'</tbody>';
}

function drawSiteFinds(sites,weeks,verts){
  const html=sites.map(s=>{
    const sf=D.site_findings[s];if(!sf)return'';
    const ov2=aggPFC(getBase([s],weeks,verts));
    const app2=aggPFC(getBase([s],weeks,['Apparel']));
    const ftw2=aggPFC(getBase([s],weeks,['Footwear']));
    const gap=ov2.c!==null?(ov2.c-D.target).toFixed(1):'—';
    const ccls=ov2.c===null?'':ov2.c>=D.target?'hit':ov2.c>=D.target-5?'warn':'miss';
    // worst / best week in current filter
    const wkVals=weeks.map(w=>({w,c:aggPFC(getBase([s],[w],verts)).c})).filter(x=>x.c!==null);
    const worst=wkVals.length?wkVals.reduce((a,b)=>b.c<a.c?b:a):null;
    const best=wkVals.length?wkVals.reduce((a,b)=>b.c>a.c?b:a):null;
    return `<div class="find">
      <div class="fh">
        <span class="w">${s}<span class="muted" style="font-size:11px;font-weight:500"> · ${sf.zone}</span></span>
        <span class="c ${ccls}">${fmtPlain(ov2.c)}</span>
      </div>
      <div class="dcards" style="padding:8px 0 6px;grid-template-columns:repeat(3,1fr);gap:8px;display:grid">
        <div class="dc"><div class="l">Apparel</div><div class="v ${app2.c===null?'':app2.c>=D.target?'hit':'miss'}">${fmtPlain(app2.c)}</div></div>
        <div class="dc"><div class="l">Footwear</div><div class="v ${ftw2.c===null?'':ftw2.c>=D.target?'hit':'miss'}">${fmtPlain(ftw2.c)}</div></div>
        <div class="dc"><div class="l">Gap vs target</div><div class="v ${parseFloat(gap)<0?'miss':'hit'}">${gap}%</div></div>
      </div>
      <div class="line"><span class="k">best week: <b>Wk ${best?best.w:'—'}</b> <span class="muted">${best?fmtPlain(best.c):''}</span> · worst: <b>Wk ${worst?worst.w:'—'}</b> <span class="muted">${worst?fmtPlain(worst.c):''}</span></span></div>
      <div class="line"><span class="k">top failure: <b>${sf.top_reason}</b> <span class="muted">${n(sf.top_reason_cnt)} times</span> · total fails: <b>${n(sf.total_fails)}</b></span></div>
    </div>`;
  }).join('');
  document.getElementById('site-finds').innerHTML=html||'<span class="muted">No data.</span>';
}

function drawDrill(){
  const wk=parseInt(document.getElementById('drill-wk').value);
  if(!wk)return;
  const sites2=fSites(),verts=fVerts();
  const wkBase=getBase(sites2,[wk],verts);
  const ov2=aggPFC(wkBase);
  const zones=['North','South','East','West'];
  document.getElementById('drill-note').innerHTML=
    `Wk ${wk} · ${D.wk2m[wk]||''} · Pan India <b>${fmtPlain(ov2.c)}</b> · ${n(ov2.p+ov2.f)} samples`;
  let sh=`<div class="stat total"><div class="l">Wk ${wk} · Pan India</div><div class="v">${fmtPlain(ov2.c)}</div></div>`;
  zones.forEach(z=>{
    const zs=sites2.filter(s=>D.zone_of[s]===z);if(!zs.length)return;
    const zo=aggPFC(getBase(zs,[wk],verts));if(zo.c===null)return;
    const ccls=zo.c>=D.target?'hit':zo.c>=D.target-5?'warn':'miss';
    sh+=`<div class="stat ${ccls}"><div class="l"><span class="dot" style="background:${ZC[z]}"></span>${z}</div><div class="v">${fmtPlain(zo.c)}</div></div>`;
  });
  document.getElementById('drill-stats').innerHTML=sh;

  // site detail table for that week
  let h='<thead><tr><th>Site</th><th>Zone</th><th>Conv%</th><th>Pass</th><th>Fail</th><th>Samples</th><th>Apparel</th><th>Footwear</th><th>Top failure reason</th></tr></thead><tbody>';
  sites2.forEach(s=>{
    const z=D.zone_of[s]||'';
    const o=aggPFC(getBase([s],[wk],verts));
    const app2=aggPFC(getBase([s],[wk],['Apparel']));
    const ftw2=aggPFC(getBase([s],[wk],['Footwear']));
    const sf=D.site_findings[s]||{};
    const wkReasons=D.fail_reasons.filter(r=>r.s===s&&r.w===wk);
    wkReasons.sort((a,b)=>b.count-a.count);
    const topR=wkReasons[0];
    h+=`<tr class="zband ${z}"><td>${s}</td><td class="muted">${z}</td>
      <td>${fmt(o.c)}</td><td class="muted">${n(o.p)}</td><td class="muted">${n(o.f)}</td><td class="muted">${n(o.p+o.f)}</td>
      <td>${fmt(app2.c)}</td><td>${fmt(ftw2.c)}</td>
      <td><span class="pill">${topR?topR.reason:'—'}</span>${topR?` <span class="muted">${n(topR.count)}</span>`:''}</td></tr>`;
  });
  h+='</tbody>';
  document.getElementById('drill-table').innerHTML=h;
}

buildFilters();render();
document.getElementById('drill-wk').onchange=drawDrill;
</script>"""

html_final=TEMPLATE_HTML.replace('/*__RF_DATA__*/',data_str)
html_clean=html_final.encode('utf-8','replace').decode('utf-8')
components.html(html_clean,height=920,scrolling=False)
