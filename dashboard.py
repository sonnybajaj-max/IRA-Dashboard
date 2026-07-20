#!/usr/bin/env python3
"""
UKB IRA Playbook v2.17 Dashboard
Run: python dashboard.py [portfolio.csv]
Outputs: index.html (GitHub Pages compatible)
"""

import sys, json, csv, os
from datetime import datetime, date, timedelta
from pathlib import Path

# ── PLAYBOOK KNOWLEDGE BASE ────────────────────────────────────────
PEAK = 1_433_927
ACCOUNT_HINT = 1_426_014  # updated after each CSV parse

RULE3_SCORES = {
    "NVDA": 5, "AVGO": 5, "GOOG": 4, "AMZN": 4, "CRWD": 5,
    "MSFT": 4, "META": 4, "AAPL": 4, "AMD":  3, "PLTR": 4,
    "MU":   4, "SOXX": 4, "QQQM": 4, "SPY":  4, "TER":  4,
    "COHR": 4, "LLY":  4, "GEV":  4, "VRT":  4, "NOW":  4,
    "TSM":  4, "GE":   4, "JPM":  4, "UNH":  4, "RTX":  3,
    "GS":   3, "ENB":  3, "PANW": 4, "MP":   3, "NEE":  3,
    "O":    3, "SCHD": 3, "JEPQ": 3, "COPX": 3, "CRM":  4,
    "QCOM": 3, "ARM":  4, "GLD":  4, "GLTR": 3,
}

PEER_GROUPS = {
    "NVDA": "Mag7+Semi", "AVGO": "Mag7+Semi", "GOOG": "Mag7",
    "AMZN": "Mag7", "MSFT": "Mag7", "META": "Mag7", "AAPL": "Mag7",
    "CRWD": "Cybersecurity", "PANW": "Cybersecurity",
    "PLTR": "AI Software", "NOW":  "AI Software", "CRM": "AI Software",
    "MU":   "Memory Semi", "SOXX": "Semi ETF",  "TER": "Semi Equip",
    "COHR": "Semi Optical", "AMD": "Semi", "TSM": "Semi",
    "VRT":  "AI Infra",    "QCOM": "Semi",  "ARM": "Semi IP",
    "LLY":  "Healthcare",  "UNH":  "Healthcare",
    "JPM":  "Financials",  "GS":   "Financials",
    "GE":   "Industrials", "GEV":  "Industrials",
    "QQQM": "Broad Index", "SPY":  "Broad Index",
    "GLD":  "Ballast",     "JEPQ": "Income",
}

RULE4_ACTIVE = {"NVDA","AVGO","GOOG","AMZN","CRWD","PLTR","MU","COHR","VRT","NOW","PANW","LLY","GEV","TSM","ARM"}
RULE4_SUSPENDED = {"MSFT", "CRM"}
SECTION19_OPEN = {
    "MSFT": {"opened": "2026-06-10", "catalyst": "None — clock expired", "status": "TRIM REQUIRED"},
    "CRM":  {"opened": "2026-07-10", "catalyst": "None identified",      "status": "INVESTIGATING"},
    "MP":   {"opened": "2026-05-15", "catalyst": "Independence TX Q4 2026 (Long-Cycle)", "status": "LONG-CYCLE HOLD"},
}
THREE_PILLARS = {
    "NVDA": 3, "AVGO": 3, "CRWD": 3, "GOOG": 3, "AMZN": 3,
    "NOW": 3, "VRT": 3, "COHR": 2, "PLTR": 3, "MU": 3,
    "MSFT": 1, "META": 2, "ORCL": 1, "TER": 2, "MP": 1,
}
RSI_BOT_POSITIONS = {
    "GOOG": {"shares": 25, "entry": 371.10, "stop": 348.02, "target": 417.26, "strategy": "RSI Divergence"},
    "AMZN": {"shares": 45, "entry": 244.39, "stop": 233.94, "target": 265.29, "strategy": "RSI Divergence"},
    "AAPL": {"shares": 36, "entry": 278.55, "stop": 270.69, "target": 283.05, "strategy": "Triple RSI MR"},
}


# ── CSV PARSER ─────────────────────────────────────────────────────
def parse_fidelity_csv(filepath):
    positions = {}
    with open(filepath, newline='', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        for row in reader:
            sym = (row.get('Symbol','') or row.get('symbol','')).strip().upper()
            if not sym or sym in ('ACCOUNT','TOTAL','','--'):
                continue
            def clean(k):
                for key in row:
                    if k.lower() in key.lower():
                        v = row[key].replace('$','').replace(',','').replace('%','').strip()
                        try: return float(v)
                        except: return 0.0
                return 0.0
            val  = clean('Current Value') or clean('Market Value') or clean('value')
            cost = clean('Cost Basis') or clean('cost')
            qty  = clean('Quantity') or clean('qty') or clean('shares')
            if val == 0: continue
            if sym in positions:
                positions[sym]['val']  += abs(val)
                positions[sym]['cost'] += abs(cost)
                positions[sym]['qty']  += abs(qty)
            else:
                positions[sym] = {'val': abs(val), 'cost': abs(cost), 'qty': abs(qty)}
    return positions


# ── RULE ENGINES ───────────────────────────────────────────────────
def run_rule14(sym, val, cost):
    if cost <= 0: return None
    gl = (val - cost) / cost * 100
    if gl >= 200: return {'level': 3, 'label': '🔴 +200% — Rule 14 FIRED (3rd rung)', 'gl': gl}
    if gl >= 100: return {'level': 2, 'label': '🔴 +100% — Rule 14 TRIGGERED', 'gl': gl}
    if gl >= 75:  return {'level': 1, 'label': '🟡 +75% — Approaching Rule 14', 'gl': gl}
    return None

def run_rule20(account):
    dd = (account - PEAK) / PEAK * 100
    buffers = {
        -8:  ('🟡', 'Watch', PEAK * 0.92),
        -12: ('🟠', 'Alert', PEAK * 0.88),
        -15: ('🔴', 'CRITICAL', PEAK * 0.85),
        -20: ('💀', 'MAJOR REVIEW', PEAK * 0.80),
    }
    status = '🟢'; label = 'Clear'; trigger = None
    for threshold, (icon, lbl, lvl) in sorted(buffers.items(), reverse=True):
        if account <= lvl:
            status = icon; label = lbl; trigger = lvl; break
    return {'dd_pct': dd, 'status': status, 'label': label,
            'buffer': account - PEAK * 0.92, 'peak': PEAK}

def run_sndk(sym, val, account):
    minimum = account * 0.015
    gap = minimum - val
    pct = val / account * 100
    return {'val': val, 'pct': pct, 'min': minimum, 'gap': max(0, gap),
            'met': gap <= 0}

def run_rule29(sym, score, pillars, suspended, sec19):
    if score == 5 and pillars == 3 and not suspended and sym not in sec19:
        return 'TIER1'
    return 'TIER2'

def section19_days(opened_str):
    try:
        opened = datetime.strptime(opened_str, '%Y-%m-%d').date()
        elapsed = (date.today() - opened).days
        remaining = max(0, 30 - elapsed)
        return elapsed, remaining
    except: return 0, 30


# ── SECTION 24 HEAT MONITOR ────────────────────────────────────────
def fetch_market_signals():
    """Try to fetch live signals; fall back to last-known values."""
    signals = {
        'vix': {'value': 19.47, 'source': 'last known (Jul 10)', 'status': 'OK'},
        'skew': {'value': 143.14, 'source': 'last known (Jul 10)', 'status': 'WELL-HEDGED'},
        'hy_oas': {'value': 310.0, 'source': 'FRED estimate', 'status': 'OK'},
        'vix_backwardation': False,
    }
    try:
        import urllib.request
        url = "https://query1.finance.yahoo.com/v8/finance/chart/%5EVIX?interval=1d&range=5d"
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=5) as r:
            data = json.loads(r.read())
            closes = data['chart']['result'][0]['indicators']['quote'][0]['close']
            vix = [c for c in closes if c][-1]
            signals['vix'] = {'value': round(vix, 2), 'source': 'Yahoo Finance (live)',
                              'status': '🔴 ALERT' if vix > 25 else ('🟡 WATCH' if vix > 20 else '🟢 OK')}
    except: pass
    try:
        url2 = "https://query1.finance.yahoo.com/v8/finance/chart/%5ESKEW?interval=1d&range=5d"
        req2 = urllib.request.Request(url2, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req2, timeout=5) as r:
            data2 = json.loads(r.read())
            closes2 = data2['chart']['result'][0]['indicators']['quote'][0]['close']
            skew = [c for c in closes2 if c][-1]
            skew_status = ('🔴 UNHEDGED' if skew < 115 else
                          ('🟡 PARTIAL' if skew < 130 else '🟢 WELL-HEDGED'))
            signals['skew'] = {'value': round(skew, 2), 'source': 'Yahoo Finance (live)',
                               'status': skew_status}
    except: pass
    vix_val = signals['vix']['value']
    signals['vix_alert'] = vix_val > 25
    signals['raise_cash'] = vix_val > 25
    return signals


# ── HTML GENERATOR ─────────────────────────────────────────────────
def generate_html(positions, account, signals, run_date):
    rule20 = run_rule20(account)
    dd_color = '#22c55e' if rule20['dd_pct'] > -8 else ('#f59e0b' if rule20['dd_pct'] > -12 else '#ef4444')

    def gl_color(gl):
        if gl > 50: return '#22c55e'
        if gl > 0:  return '#86efac'
        if gl > -8: return '#fbbf24'
        return '#ef4444'

    def tier_badge(tier):
        if tier == 'TIER1':
            return '<span class="badge t1">⚡ Compound Engine</span>'
        return '<span class="badge t2">🔄 Active Review</span>'

    def score_badge(s):
        colors = {5:'#22c55e', 4:'#3b82f6', 3:'#f59e0b', 2:'#f97316', 1:'#ef4444'}
        c = colors.get(s, '#6b7280')
        return f'<span class="score-badge" style="background:{c}">{s}/5</span>'

    # Build position rows
    pos_rows = []
    rule14_alerts = []
    sndk_gaps = []
    sec19_rows = []

    for sym, p in sorted(positions.items(), key=lambda x: -x[1]['val']):
        if sym == 'SPAXX': continue
        val = p['val']; cost = p['cost']
        gl = (val - cost) / cost * 100 if cost > 0 else 0
        pct = val / account * 100
        score = RULE3_SCORES.get(sym, 0)
        pillars = THREE_PILLARS.get(sym, 0)
        suspended = sym in RULE4_SUSPENDED
        tier = run_rule29(sym, score, pillars, suspended, SECTION19_OPEN)
        sndk = run_sndk(sym, val, account)
        r14 = run_rule14(sym, val, cost)
        r4 = '🔴 SUSPENDED' if suspended else ('✅ Active' if sym in RULE4_ACTIVE else '—')
        peer = PEER_GROUPS.get(sym, '—')

        if r14: rule14_alerts.append({'sym': sym, **r14})
        if not sndk['met'] and score >= 4 and sym not in ['GLD','GLTR','COPX','SCHD','O','NEE','RTX','GS','ENB','PANW','VRT','NOW','ARM','QCOM','GEV']:
            sndk_gaps.append({'sym': sym, 'gap': sndk['gap'], 'pct': pct, 'score': score})

        sec19 = SECTION19_OPEN.get(sym)
        if sec19:
            elapsed, remaining = section19_days(sec19['opened'])
            clock_color = '#ef4444' if remaining == 0 else ('#f59e0b' if remaining <= 5 else '#3b82f6')
            sec19_rows.append({
                'sym': sym, 'elapsed': elapsed, 'remaining': remaining,
                'catalyst': sec19['catalyst'], 'status': sec19['status'],
                'color': clock_color
            })

        pos_rows.append(f"""
        <tr>
          <td class="sym">{sym}</td>
          <td>{peer}</td>
          <td class="num">${val:,.0f}</td>
          <td class="num" style="color:{gl_color(gl)}">{gl:+.1f}%</td>
          <td class="num">{pct:.2f}%</td>
          <td>{score_badge(score)}</td>
          <td>{tier_badge(tier)}</td>
          <td style="color:{'#ef4444' if suspended else '#22c55e'}">{r4}</td>
          <td class="num" style="color:{'#22c55e' if sndk['met'] else '#f59e0b'}">
            {'✅' if sndk['met'] else f'${sndk["gap"]:,.0f} gap'}
          </td>
        </tr>""")

    # Alerts panel
    alerts_html = ''
    if rule20['dd_pct'] < -8:
        alerts_html += f'<div class="alert red">⚠️ Rule 20: Drawdown {rule20["dd_pct"]:.1f}% — {rule20["label"]}</div>'
    for a in rule14_alerts:
        alerts_html += f'<div class="alert {"red" if a["level"]==2 else "amber"}">{a["label"]} on <b>{a["sym"]}</b> ({a["gl"]:+.1f}%)</div>'
    for s in sec19_rows:
        if s['remaining'] == 0:
            alerts_html += f'<div class="alert red">⏰ Section 19 EXPIRED: <b>{s["sym"]}</b> — {s["status"]}</div>'
        elif s['remaining'] <= 5:
            alerts_html += f'<div class="alert amber">⏰ Section 19 Clock: <b>{s["sym"]}</b> — {s["remaining"]} days remaining</div>'
    if signals.get('vix_alert'):
        alerts_html += f'<div class="alert red">🔴 R-IRA 2: VIX {signals["vix"]["value"]} — Check backwardation and stage deployment ticket</div>'
    spaxx = positions.get('SPAXX', {}).get('val', 0)
    rira2_min = account * 0.015
    if spaxx < rira2_min + 18500:
        alerts_html += f'<div class="alert amber">💰 Cash Warning: SPAXX ${spaxx:,.0f} may be below combined reserves</div>'
    if not alerts_html:
        alerts_html = '<div class="alert green">✅ No immediate alerts — all systems normal</div>'

    # Section 24 panel
    vix_v = signals['vix']['value']
    skew_v = signals['skew']['value']
    vix_pct = min(100, (vix_v / 40) * 100)
    skew_pct = min(100, (skew_v / 180) * 100)
    hy_v = signals['hy_oas']['value']
    vix_gauge_color = '#22c55e' if vix_v < 20 else ('#f59e0b' if vix_v < 25 else '#ef4444')
    skew_gauge_color = '#ef4444' if skew_v < 115 else ('#f59e0b' if skew_v < 130 else '#22c55e')

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>UKB IRA — Playbook v2.17 Dashboard</title>
<style>
  :root {{
    --navy: #0D1B2A; --slate: #1B3A5C; --teal: #1A9B8F;
    --gold: #C9922A; --red: #ef4444; --amber: #f59e0b;
    --green: #22c55e; --blue: #3b82f6; --bg: #0f172a; --card: #1e293b;
  }}
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ font-family: 'SF Mono', 'Consolas', monospace; background: var(--bg);
    color: #e2e8f0; font-size: 13px; line-height: 1.5; }}
  .header {{ background: var(--navy); border-bottom: 2px solid var(--gold);
    padding: 20px 24px; display: flex; justify-content: space-between; align-items: center; }}
  .header h1 {{ font-size: 20px; color: var(--gold); letter-spacing: 0.05em; }}
  .header .meta {{ color: #94a3b8; font-size: 11px; text-align: right; }}
  .grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
    gap: 12px; padding: 16px 24px; }}
  .kpi {{ background: var(--card); border: 1px solid #334155; border-radius: 8px;
    padding: 16px; }}
  .kpi .label {{ color: #94a3b8; font-size: 10px; text-transform: uppercase;
    letter-spacing: 0.1em; margin-bottom: 4px; }}
  .kpi .value {{ font-size: 24px; font-weight: 700; }}
  .kpi .sub {{ color: #64748b; font-size: 11px; margin-top: 4px; }}
  .section {{ padding: 0 24px 16px; }}
  .section h2 {{ color: var(--teal); font-size: 13px; text-transform: uppercase;
    letter-spacing: 0.1em; margin-bottom: 10px; padding-bottom: 6px;
    border-bottom: 1px solid #334155; }}
  .alerts {{ padding: 0 24px 16px; }}
  .alert {{ padding: 10px 14px; border-radius: 6px; margin-bottom: 8px; font-size: 12px; }}
  .alert.red {{ background: rgba(239,68,68,0.15); border-left: 3px solid var(--red); }}
  .alert.amber {{ background: rgba(245,158,11,0.15); border-left: 3px solid var(--amber); }}
  .alert.green {{ background: rgba(34,197,94,0.15); border-left: 3px solid var(--green); }}
  table {{ width: 100%; border-collapse: collapse; font-size: 12px; }}
  th {{ background: var(--slate); color: #94a3b8; font-size: 10px; text-transform: uppercase;
    letter-spacing: 0.05em; padding: 8px 10px; text-align: left; position: sticky; top: 0; }}
  td {{ padding: 7px 10px; border-bottom: 1px solid #1e293b; }}
  tr:hover {{ background: rgba(255,255,255,0.03); }}
  .sym {{ font-weight: 700; color: var(--gold); font-size: 13px; }}
  .num {{ text-align: right; font-feature-settings: 'tnum'; }}
  .badge {{ font-size: 10px; padding: 2px 8px; border-radius: 4px; font-weight: 600; }}
  .t1 {{ background: rgba(34,197,94,0.2); color: var(--green); border: 1px solid rgba(34,197,94,0.3); }}
  .t2 {{ background: rgba(245,158,11,0.2); color: var(--amber); border: 1px solid rgba(245,158,11,0.3); }}
  .score-badge {{ font-size: 10px; padding: 2px 6px; border-radius: 3px; color: white; font-weight: 700; }}
  .table-wrap {{ background: var(--card); border: 1px solid #334155; border-radius: 8px;
    overflow: auto; max-height: 600px; }}
  .heat-grid {{ display: grid; grid-template-columns: repeat(2, 1fr); gap: 12px; }}
  .heat-card {{ background: var(--card); border: 1px solid #334155; border-radius: 8px; padding: 16px; }}
  .heat-card h3 {{ font-size: 11px; color: #94a3b8; text-transform: uppercase; margin-bottom: 12px; }}
  .gauge-bar {{ background: #1e293b; border-radius: 4px; height: 8px; margin: 8px 0; }}
  .gauge-fill {{ height: 100%; border-radius: 4px; transition: width 0.3s; }}
  .signal-row {{ display: flex; justify-content: space-between; align-items: center;
    padding: 6px 0; border-bottom: 1px solid #334155; }}
  .signal-row:last-child {{ border-bottom: none; }}
  .clock-card {{ background: var(--card); border: 1px solid #334155; border-radius: 8px;
    padding: 14px; margin-bottom: 8px; }}
  .clock-card .sym {{ font-size: 16px; }}
  .progress {{ background: #1e293b; border-radius: 4px; height: 6px; margin: 8px 0; }}
  .progress-fill {{ height: 100%; border-radius: 4px; }}
  .sndk-item {{ display: flex; justify-content: space-between; align-items: center;
    padding: 8px 12px; border-bottom: 1px solid #1e293b; }}
  .rsi-card {{ background: var(--card); border: 1px solid #334155; border-radius: 8px;
    padding: 12px; margin-bottom: 8px; }}
  footer {{ text-align: center; color: #475569; font-size: 10px; padding: 20px;
    border-top: 1px solid #1e293b; }}
  @media (max-width: 768px) {{
    .grid {{ grid-template-columns: repeat(2, 1fr); }}
    .heat-grid {{ grid-template-columns: 1fr; }}
  }}
</style>
</head>
<body>

<div class="header">
  <div>
    <h1>UKB IRA — Playbook Dashboard v2.17</h1>
    <div style="color:#94a3b8;font-size:11px;margin-top:4px">
      Account 250718173 · Fidelity
    </div>
  </div>
  <div class="meta">
    <div style="color:var(--gold);font-size:16px;font-weight:700">${account:,.0f}</div>
    <div>Generated {run_date}</div>
    <div>Peak: ${PEAK:,}</div>
  </div>
</div>

<!-- KPI STRIP -->
<div class="grid">
  <div class="kpi">
    <div class="label">Account Value</div>
    <div class="value" style="color:var(--gold)">${account:,.0f}</div>
    <div class="sub">Peak: ${PEAK:,}</div>
  </div>
  <div class="kpi">
    <div class="label">Drawdown from Peak</div>
    <div class="value" style="color:{dd_color}">{rule20['dd_pct']:+.2f}%</div>
    <div class="sub">Rule 20 buffer: ${rule20['buffer']:,.0f}</div>
  </div>
  <div class="kpi">
    <div class="label">SPAXX / Cash</div>
    <div class="value" style="color:var(--teal)">${spaxx:,.0f}</div>
    <div class="sub">{spaxx/account*100:.2f}% of account</div>
  </div>
  <div class="kpi">
    <div class="label">VIX</div>
    <div class="value" style="color:{vix_gauge_color}">{vix_v:.1f}</div>
    <div class="sub">{signals['vix']['source']}</div>
  </div>
  <div class="kpi">
    <div class="label">SKEW</div>
    <div class="value" style="color:{skew_gauge_color}">{skew_v:.1f}</div>
    <div class="sub">{signals['skew']['status']}</div>
  </div>
  <div class="kpi">
    <div class="label">Positions Tracked</div>
    <div class="value" style="color:#e2e8f0">{len(positions)-1}</div>
    <div class="sub">Excl. SPAXX</div>
  </div>
</div>

<!-- ALERTS -->
<div class="alerts">
  <div class="section"><h2>⚡ Action Required This Week</h2></div>
  {alerts_html}
</div>

<!-- SECTION 24 HEAT MONITOR -->
<div class="section">
  <h2>📡 Section 24 — Predictive Heat Monitor</h2>
  <div class="heat-grid">
    <div class="heat-card">
      <h3>VIX — Fear Gauge</h3>
      <div class="signal-row">
        <span>Spot VIX</span>
        <span style="color:{vix_gauge_color};font-weight:700">{vix_v:.1f}</span>
      </div>
      <div class="gauge-bar"><div class="gauge-fill" style="width:{vix_pct:.0f}%;background:{vix_gauge_color}"></div></div>
      <div class="signal-row"><span>R-IRA 2 Trigger</span><span style="color:#64748b">VIX &gt;25 + backwardation</span></div>
      <div class="signal-row"><span>Status</span><span style="color:{vix_gauge_color}">{signals['vix']['status']}</span></div>
    </div>
    <div class="heat-card">
      <h3>SKEW — Hedging Gauge</h3>
      <div class="signal-row">
        <span>SKEW Index</span>
        <span style="color:{skew_gauge_color};font-weight:700">{skew_v:.1f}</span>
      </div>
      <div class="gauge-bar"><div class="gauge-fill" style="width:{skew_pct:.0f}%;background:{skew_gauge_color}"></div></div>
      <div class="signal-row"><span>&lt;115</span><span style="color:#ef4444">Unhedged — Block deploy</span></div>
      <div class="signal-row"><span>115-130</span><span style="color:#f59e0b">Partial — R-IRA Tier 1 only</span></div>
      <div class="signal-row"><span>&gt;130</span><span style="color:#22c55e">Well-hedged — Full deploy OK</span></div>
    </div>
    <div class="heat-card">
      <h3>HY Credit Spreads (BAMLH0A0HYM2)</h3>
      <div class="signal-row"><span>OAS</span>
        <span style="color:{'#ef4444' if hy_v>500 else ('#f59e0b' if hy_v>400 else '#22c55e')};font-weight:700">{hy_v:.0f} bps</span>
      </div>
      <div class="signal-row"><span>Trigger</span><span style="color:#64748b">&gt;500bps + widening &gt;50bps/5d</span></div>
      <div class="signal-row"><span>Status</span>
        <span style="color:{'#ef4444' if hy_v>500 else '#22c55e'}">{'🔴 ALERT' if hy_v>500 else '🟢 OK'}</span>
      </div>
      <div class="signal-row"><span>Data source</span><span style="color:#64748b">FRED: BAMLH0A0HYM2</span></div>
    </div>
    <div class="heat-card">
      <h3>Rule 20 — Drawdown Control</h3>
      <div class="signal-row"><span>Current</span>
        <span style="color:{dd_color};font-weight:700">{rule20['dd_pct']:+.2f}%</span>
      </div>
      <div class="signal-row"><span>-8% trigger</span><span style="color:#64748b">${PEAK*0.92:,.0f}</span></div>
      <div class="signal-row"><span>-12% alert</span><span style="color:#64748b">${PEAK*0.88:,.0f}</span></div>
      <div class="signal-row"><span>Buffer to -8%</span>
        <span style="color:{dd_color}">${rule20['buffer']:,.0f}</span>
      </div>
    </div>
  </div>
</div>

<!-- SECTION 19 CLOCKS -->
<div class="section">
  <h2>⏱ Section 19 — Decision Clocks</h2>
  {''.join(f"""
  <div class="clock-card">
    <div style="display:flex;justify-content:space-between;align-items:center">
      <span class="sym">{s['sym']}</span>
      <span style="color:{s['color']};font-weight:700">
        {f"⚠️ EXPIRED — ACTION NOW" if s['remaining']==0 else f"{s['remaining']} days remaining"}
      </span>
    </div>
    <div class="progress" style="margin:10px 0">
      <div class="progress-fill" style="width:{min(100,(s['elapsed']/30)*100):.0f}%;background:{s['color']}"></div>
    </div>
    <div style="color:#94a3b8;font-size:11px">Catalyst: {s['catalyst']}</div>
    <div style="color:#64748b;font-size:11px;margin-top:4px">Status: {s['status']}</div>
  </div>""" for s in sec19_rows) or '<div style="color:#64748b;padding:12px">No open Section 19 investigations</div>'}
</div>

<!-- SNDK GAPS -->
<div class="section">
  <h2>📏 SNDK Minimum Status (1.5% = ${account*0.015:,.0f})</h2>
  <div style="background:var(--card);border:1px solid #334155;border-radius:8px;overflow:hidden">
    {''.join(f"""
    <div class="sndk-item">
      <span class="sym">{g['sym']}</span>
      <div style="flex:1;margin:0 12px">
        <div class="gauge-bar"><div class="gauge-fill" 
          style="width:{min(100,g['pct']/1.5*100):.0f}%;background:{'#22c55e' if g['pct']>=1.5 else '#f59e0b'}"></div>
        </div>
      </div>
      <span style="color:#94a3b8;font-size:11px;min-width:80px;text-align:right">{g['pct']:.2f}% / 1.50%</span>
      <span style="color:#f59e0b;margin-left:12px;min-width:80px;text-align:right">${g['gap']:,.0f} gap</span>
    </div>""" for g in sorted(sndk_gaps, key=lambda x:-x['gap'])) or
    '<div class="sndk-item" style="color:#22c55e">✅ All conviction positions at or above SNDK minimum</div>'}
  </div>
</div>

<!-- RSI BOT POSITIONS -->
<div class="section">
  <h2>🤖 RSI Bot Positions (Outside Rule 4)</h2>
  <div style="background:var(--card);border:1px solid #334155;border-radius:8px;overflow:hidden">
    {''.join(f"""
    <div class="rsi-card">
      <div style="display:flex;justify-content:space-between">
        <span class="sym">{sym}</span>
        <span style="color:#94a3b8;font-size:11px">{p['strategy']}</span>
      </div>
      <div style="display:grid;grid-template-columns:repeat(3,1fr);gap:8px;margin-top:8px;font-size:11px">
        <div><span style="color:#64748b">Entry</span><br><span>${p['entry']}</span></div>
        <div><span style="color:#ef4444">Stop</span><br><span>${p['stop']}</span></div>
        <div><span style="color:#22c55e">Target</span><br><span>${p['target']}</span></div>
      </div>
    </div>""" for sym, p in RSI_BOT_POSITIONS.items())}
  </div>
</div>

<!-- FULL POSITION TABLE -->
<div class="section">
  <h2>📊 Full Portfolio — All Positions</h2>
  <div class="table-wrap">
    <table>
      <thead>
        <tr>
          <th>Symbol</th><th>Peer Group</th><th>Value</th>
          <th>Gain/Loss</th><th>Weight</th><th>Rule 3</th>
          <th>Rule 29 Tier</th><th>Rule 4</th><th>SNDK</th>
        </tr>
      </thead>
      <tbody>{''.join(pos_rows)}</tbody>
    </table>
  </div>
</div>

<footer>
  UKB IRA Playbook v2.17 Dashboard · Generated {run_date} ·
  Peak ${PEAK:,} · Account 250718173 · Not financial advice
</footer>

</body></html>"""
    return html


# ── MAIN ───────────────────────────────────────────────────────────
def main():
    csv_path = sys.argv[1] if len(sys.argv) > 1 else None
    positions = {}

    if csv_path and Path(csv_path).exists():
        positions = parse_fidelity_csv(csv_path)
        print(f"Loaded {len(positions)} positions from {csv_path}")
    else:
        print("No CSV provided — using demo data")
        positions = {
            'SPAXX': {'val':38875,'cost':38875,'qty':38875},
            'NVDA':  {'val':85840,'cost':67608,'qty':250},
            'AVGO':  {'val':81059,'cost':68434,'qty':202},
            'QQQM':  {'val':139188,'cost':116973,'qty':466},
            'GOOG':  {'val':102826,'cost':80591,'qty':285},
            'SPY':   {'val':119867,'cost':107225,'qty':305},
            'CRWD':  {'val':46830,'cost':35472,'qty':250},
            'AAPL':  {'val':60856,'cost':48981,'qty':193},
            'MSFT':  {'val':65126,'cost':72014,'qty':167},
            'AMZN':  {'val':80116,'cost':76632,'qty':325},
            'META':  {'val':46642,'cost':45235,'qty':67},
            'AMD':   {'val':20706,'cost':8164,'qty':37},
            'MU':    {'val':35502,'cost':25630,'qty':36},
            'LLY':   {'val':37302,'cost':28479,'qty':30},
            'GEV':   {'val':14638,'cost':7894,'qty':31},
            'TER':   {'val':40964,'cost':44980,'qty':113},
            'COHR':  {'val':24695,'cost':20733,'qty':66},
            'VRT':   {'val':20022,'cost':16797,'qty':66},
            'NOW':   {'val':20500,'cost':14846,'qty':200},
            'PLTR':  {'val':17080,'cost':20928,'qty':135},
            'SOXX':  {'val':58529,'cost':42707,'qty':100},
            'JPM':   {'val':27108,'cost':25336,'qty':80},
            'GE':    {'val':29778,'cost':24688,'qty':82},
            'UNH':   {'val':24924,'cost':22651,'qty':58},
            'PANW':  {'val':7093,'cost':4235,'qty':18},
            'JEPQ':  {'val':30775,'cost':27342,'qty':194},
            'TSM':   {'val':14632,'cost':10220,'qty':67},
            'QCOM':  {'val':10794,'cost':10160,'qty':57},
            'ARM':   {'val':5235,'cost':5200,'qty':16},
            'MP':    {'val':15672,'cost':21611,'qty':286},
            'GLD':   {'val':18181,'cost':19984,'qty':95},
            'ENB':   {'val':18383,'cost':17804,'qty':850},
            'CRM':   {'val':17945,'cost':19915,'qty':98},
            'RTX':   {'val':15500,'cost':14021,'qty':98},
            'GS':    {'val':10638,'cost':9477,'qty':10},
            'NEE':   {'val':11185,'cost':10975,'qty':140},
            'O':     {'val':11633,'cost':11364,'qty':120},
            'SCHD':  {'val':6368,'cost':6130,'qty':77},
            'COPX':  {'val':4608,'cost':4999,'qty':120},
        }

    account = sum(p['val'] for p in positions.values())
    signals = fetch_market_signals()
    run_date = datetime.now().strftime('%B %d, %Y at %H:%M')
    html = generate_html(positions, account, signals, run_date)

    out = Path('index.html')
    out.write_text(html, encoding='utf-8')
    print(f"Dashboard generated → {out.absolute()}")
    print(f"Account: ${account:,.0f}")

if __name__ == '__main__':
    main()
