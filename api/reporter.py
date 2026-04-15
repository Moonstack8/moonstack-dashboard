"""
Daily performance email reporter.
Pulls yesterday's Meta Ads data across all accounts and sends a formatted HTML email.
"""
import os
import yaml
import httpx
import resend
from datetime import date, timedelta
from dotenv import load_dotenv

load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), '..', '.env'))

RESEND_KEY = os.getenv("RESEND_API_KEY", "")
REPORT_EMAIL = os.getenv("REPORT_EMAIL", "")
GRAPH_BASE = "https://graph.facebook.com/v21.0"

_CLIENTS_PATH = os.path.join(os.path.dirname(__file__), '..', 'config', 'clients.yaml')

INSIGHT_FIELDS = "spend,impressions,reach,clicks,ctr,cpc,cpm,actions,action_values,frequency"


# ---------------------------------------------------------------------------
# Data fetching
# ---------------------------------------------------------------------------

def _load_clients():
    if os.path.exists(_CLIENTS_PATH):
        with open(_CLIENTS_PATH) as f:
            data = yaml.safe_load(f) or {}
        clients = data.get("clients", [])
        if clients:
            return clients
    token = os.getenv("META_ACCESS_TOKEN", "")
    return [{"name": "Default", "token": token}] if token else []


def _get(path, token, params=None):
    p = {"access_token": token, **(params or {})}
    r = httpx.get(f"{GRAPH_BASE}{path}", params=p, timeout=30.0)
    return r.json()


def _get_accounts(token):
    data = _get("/me/adaccounts", token, {
        "fields": "id,name,currency,account_status,amount_spent"
    })
    return [a for a in data.get("data", []) if a.get("account_status") == 1]


def _get_account_insights(account_id, token, date_preset="yesterday"):
    data = _get(f"/{account_id}/insights", token, {
        "fields": INSIGHT_FIELDS,
        "date_preset": date_preset,
        "level": "account",
    })
    return data.get("data", [{}])[0] if data.get("data") else {}


def _get_campaign_insights(account_id, token, date_preset="yesterday"):
    campaigns = _get(f"/{account_id}/campaigns", token, {
        "fields": "id,name,status,effective_status,objective",
        "limit": 50,
    }).get("data", [])

    if not campaigns:
        return []

    ids = ",".join(c["id"] for c in campaigns)
    insights_resp = _get(f"/{account_id}/insights", token, {
        "fields": "campaign_id,campaign_name," + INSIGHT_FIELDS,
        "date_preset": date_preset,
        "level": "campaign",
        "filtering": f'[{{"field":"campaign.id","operator":"IN","value":[{ids}]}}]',
        "limit": 50,
    })
    insights_by_id = {
        i["campaign_id"]: i
        for i in insights_resp.get("data", [])
        if "campaign_id" in i
    }

    result = []
    for c in campaigns:
        ins = insights_by_id.get(c["id"], {})
        if float(ins.get("spend", 0)) > 0 or c.get("effective_status") == "ACTIVE":
            result.append({**c, "insights": ins})
    return result


def _get_ad_insights(account_id, token, date_preset="yesterday"):
    data = _get(f"/{account_id}/insights", token, {
        "fields": "ad_id,ad_name,campaign_name," + INSIGHT_FIELDS,
        "date_preset": date_preset,
        "level": "ad",
        "limit": 100,
    })
    return [i for i in data.get("data", []) if float(i.get("spend", 0)) > 0]


def _get_ad_timeseries(account_id, token):
    data = _get(f"/{account_id}/insights", token, {
        "fields": "ad_id,ad_name,ctr,spend,date_start",
        "date_preset": "last_7d",
        "time_increment": 1,
        "level": "ad",
        "limit": 200,
    })
    return data.get("data", [])


def _get_revenue(action_values):
    found = next((a for a in (action_values or []) if a["action_type"] == "purchase"), None)
    return float(found["value"]) if found else 0.0


def _get_conversions(actions):
    conv_types = ["purchase", "lead", "complete_registration"]
    return sum(
        int(a["value"])
        for a in (actions or [])
        if any(t in a["action_type"] for t in conv_types)
    )


# ---------------------------------------------------------------------------
# CTR line chart (inline SVG)
# ---------------------------------------------------------------------------

def _build_ctr_chart_html(ad_timeseries):
    """
    Gmail-safe HTML bar chart: CTR per ad over last 7 days.
    Each ad gets its own row with a fixed-height chart area and a baseline axis.
    Bars are anchored to the bottom via padding-top.
    """
    from datetime import datetime as dt
    if not ad_timeseries:
        return ""

    by_ad = {}
    for row in ad_timeseries:
        aid = row.get("ad_id", "")
        if not aid:
            continue
        if aid not in by_ad:
            by_ad[aid] = {"name": row.get("ad_name", aid), "days": {}, "total_spend": 0.0}
        by_ad[aid]["days"][row.get("date_start", "")] = float(row.get("ctr", 0))
        by_ad[aid]["total_spend"] += float(row.get("spend", 0))

    top_ads = sorted(
        [a for a in by_ad.values() if any(v > 0 for v in a["days"].values())],
        key=lambda a: a["total_spend"], reverse=True
    )[:5]
    if not top_ads:
        return ""

    all_dates = sorted(set(d for ad in top_ads for d in ad["days"]))
    if not all_dates:
        return ""

    max_ctr = max((ad["days"].get(d, 0) for ad in top_ads for d in all_dates), default=1) or 1
    colors = ["#111827", "#3b82f6", "#10b981", "#f59e0b", "#ef4444"]
    BAR_H = 44  # fixed chart area height per ad row

    def fmt_date(d):
        try:
            return dt.strptime(d, "%Y-%m-%d").strftime("%b %d")
        except Exception:
            return d

    NAME_W = 130

    # Date header
    date_ths = "".join(
        f'<td style="font-size:9px;color:#9ca3af;text-align:center;padding:0 3px 6px;white-space:nowrap;">{fmt_date(d)}</td>'
        for d in all_dates
    )
    html = (
        f'<table cellpadding="0" cellspacing="0" style="width:100%;border-collapse:collapse;">'
        f'<tr><td style="width:{NAME_W}px;"></td>{date_ths}</tr>'
    )

    for ai, ad in enumerate(top_ads):
        color = colors[ai % len(colors)]
        name = ad["name"][:26] + ("…" if len(ad["name"]) > 26 else "")

        bar_cells = ""
        for d in all_dates:
            ctr = ad["days"].get(d, 0)
            bar_h = max(2, int((ctr / max_ctr) * BAR_H)) if ctr > 0 else 0
            pad_top = BAR_H - bar_h
            label = f"{ctr:.1f}%" if ctr > 0 else ""
            bar_cells += (
                f'<td style="padding:0 3px;border-bottom:2px solid #e5e7eb;text-align:center;vertical-align:bottom;">'
                f'<div style="font-size:8px;color:#9ca3af;text-align:center;margin-bottom:2px;height:12px;line-height:12px;">{label}</div>'
                f'<div style="width:14px;height:{bar_h}px;background:{color};border-radius:2px 2px 0 0;margin:0 auto;"></div>'
                f'</td>'
            )

        html += (
            f'<tr>'
            f'<td style="padding:0 12px 2px 0;font-size:11px;color:#374151;vertical-align:bottom;'
            f'border-bottom:2px solid #e5e7eb;width:{NAME_W}px;white-space:nowrap;">'
            f'<span style="display:inline-block;width:8px;height:8px;border-radius:50%;'
            f'background:{color};margin-right:5px;vertical-align:middle;"></span>{name}'
            f'</td>'
            f'{bar_cells}'
            f'</tr>'
            f'<tr><td colspan="{1 + len(all_dates)}" style="height:10px;"></td></tr>'
        )

    html += '</table>'
    return html


# ---------------------------------------------------------------------------
# HTML email template
# ---------------------------------------------------------------------------

def _fmt_currency(val, currency="USD"):
    return f"${float(val or 0):,.2f}"

def _fmt_number(val):
    n = float(val or 0)
    if n >= 1_000_000: return f"{n/1_000_000:.1f}M"
    if n >= 1_000: return f"{n/1_000:.1f}K"
    return f"{int(n):,}"

def _fmt_pct(val):
    return f"{float(val or 0):.2f}%"

def _status_color(status):
    return {"ACTIVE": "#22c55e", "PAUSED": "#eab308"}.get(status, "#6b7280")


def build_email_html(report_date: str, accounts_data: list, all_ads: list = None, ad_timeseries: list = None) -> str:
    total_spend = sum(float(a["insights"].get("spend", 0)) for a in accounts_data)
    total_impressions = sum(int(a["insights"].get("impressions", 0)) for a in accounts_data)
    total_clicks = sum(int(a["insights"].get("clicks", 0)) for a in accounts_data)
    total_reach = sum(int(a["insights"].get("reach", 0)) for a in accounts_data)
    avg_ctr = (total_clicks / total_impressions * 100) if total_impressions else 0
    avg_cpc = (total_spend / total_clicks) if total_clicks else 0
    avg_cpm = (total_spend / total_impressions * 1000) if total_impressions else 0
    total_revenue = sum(_get_revenue(a["insights"].get("action_values", [])) for a in accounts_data)
    total_conversions = sum(_get_conversions(a["insights"].get("actions", [])) for a in accounts_data)
    roas = (total_revenue / total_spend) if total_spend else 0

    # Build campaign rows HTML
    all_campaign_rows = ""
    for acct in accounts_data:
        for camp in acct.get("campaigns", []):
            ins = camp.get("insights", {})
            spend = float(ins.get("spend", 0))
            if spend == 0:
                continue
            status = camp.get("effective_status", camp.get("status", ""))
            dot_color = _status_color(status)
            all_campaign_rows += f"""
            <tr style="border-top:1px solid #f3f4f6;">
              <td style="padding:10px 8px 10px 0;font-size:12px;color:#111827;">
                <span style="display:inline-block;width:6px;height:6px;border-radius:50%;background:{dot_color};margin-right:6px;vertical-align:middle;"></span>
                {camp['name'][:38]}{'...' if len(camp['name']) > 38 else ''}
              </td>
              <td style="padding:10px 8px;font-size:11px;color:#9ca3af;">{acct['name'][:16]}{'...' if len(acct['name']) > 16 else ''}</td>
              <td style="padding:10px 0;font-size:12px;color:#111827;text-align:right;font-weight:600;">{_fmt_currency(ins.get('spend'))}</td>
              <td style="padding:10px 0;font-size:12px;color:#6b7280;text-align:right;">{_fmt_number(ins.get('impressions'))}</td>
              <td style="padding:10px 0;font-size:12px;color:#6b7280;text-align:right;">{_fmt_number(ins.get('clicks'))}</td>
              <td style="padding:10px 0;font-size:12px;color:#6b7280;text-align:right;">{_fmt_pct(ins.get('ctr'))}</td>
              <td style="padding:10px 0;font-size:12px;color:#6b7280;text-align:right;">{_fmt_currency(ins.get('cpc'))}</td>
            </tr>"""

    if not all_campaign_rows:
        all_campaign_rows = '<tr><td colspan="5" style="padding:16px;font-size:13px;color:#9ca3af;">No active campaign spend yesterday.</td></tr>'

    # Flags / alerts
    flags = []
    for acct in accounts_data:
        ins = acct["insights"]
        freq = float(ins.get("frequency", 0))
        ctr  = float(ins.get("ctr", 0))
        spend = float(ins.get("spend", 0))
        if freq > 4:
            flags.append(f"{acct['name']}: High frequency ({freq:.1f}x) — audience may be fatigued")
        if ctr < 0.5 and spend > 5:
            flags.append(f"{acct['name']}: Low CTR ({_fmt_pct(ctr)}) — consider refreshing creative")
        if spend == 0:
            flags.append(f"{acct['name']}: Zero spend yesterday — check campaign status")

    flags_html = ""
    if flags:
        items = "".join(f'<li style="margin:0 0 6px 0;font-size:14px;color:#374151;">⚠ {f}</li>' for f in flags)
        flags_html = f"""
        <tr><td style="padding:0 0 28px 0;">
          <p style="margin:0 0 8px 0;font-size:12px;font-weight:600;color:#9ca3af;text-transform:uppercase;letter-spacing:0.06em;">Alerts</p>
          <ul style="margin:0;padding-left:0;list-style:none;">{items}</ul>
        </td></tr>"""

    stats = [
        ("Spend",       _fmt_currency(total_spend)),
        ("Impressions", _fmt_number(total_impressions)),
        ("Clicks",      _fmt_number(total_clicks)),
        ("Reach",       _fmt_number(total_reach)),
        ("CTR",         _fmt_pct(avg_ctr)),
        ("CPC",         _fmt_currency(avg_cpc)),
        ("CPM",         _fmt_currency(avg_cpm)),
        ("ROAS",        f"{roas:.2f}x" if roas else "—"),
    ]
    if total_revenue > 0:
        stats.append(("Revenue", _fmt_currency(total_revenue)))

    stats_rows = "".join(
        f"""<tr>
          <td style="padding:10px 0;border-bottom:1px solid #f3f4f6;font-size:14px;color:#6b7280;width:50%;">{label}</td>
          <td style="padding:10px 0;border-bottom:1px solid #f3f4f6;font-size:14px;font-weight:600;color:#111827;text-align:right;">{value}</td>
        </tr>"""
        for label, value in stats
    )

    # CTR per ad line chart (SVG)
    ctr_chart_html = _build_ctr_chart_html(ad_timeseries or [])
    timeseries_html = ""
    if ctr_chart_html:
        timeseries_html = f"""
  <tr><td style="padding-bottom:32px;">
    <p style="margin:0 0 12px 0;font-size:12px;font-weight:600;color:#9ca3af;text-transform:uppercase;letter-spacing:0.06em;">CTR — Last 7 Days</p>
    {ctr_chart_html}
  </td></tr>"""

    # Per-ad breakdown
    ad_rows_html = ""
    if all_ads:
        ad_rows = ""
        for ad in all_ads[:30]:  # cap at 30 ads
            ad_rows += f"""
            <tr style="border-top:1px solid #f3f4f6;">
              <td style="padding:10px 16px 10px 0;font-size:12px;color:#111827;">{ad.get('ad_name','')[:38]}{'...' if len(ad.get('ad_name','')) > 38 else ''}</td>
              <td style="padding:10px 8px;font-size:11px;color:#9ca3af;max-width:120px;overflow:hidden;">{ad.get('campaign_name','')[:28]}{'...' if len(ad.get('campaign_name','')) > 28 else ''}</td>
              <td style="padding:10px 0;font-size:12px;color:#111827;font-weight:600;text-align:right;white-space:nowrap;">{_fmt_currency(ad.get('spend'))}</td>
              <td style="padding:10px 0 10px 12px;font-size:12px;color:#6b7280;text-align:right;white-space:nowrap;">{_fmt_pct(ad.get('ctr'))}</td>
              <td style="padding:10px 0 10px 12px;font-size:12px;color:#6b7280;text-align:right;white-space:nowrap;">{_fmt_currency(ad.get('cpc'))}</td>
            </tr>"""
        ad_rows_html = f"""
  <tr><td style="padding-bottom:32px;">
    <p style="margin:0 0 12px 0;font-size:12px;font-weight:600;color:#9ca3af;text-transform:uppercase;letter-spacing:0.06em;">Ads</p>
    <table width="100%" cellpadding="0" cellspacing="0">
      <tr>
        <td style="padding:8px 16px 8px 0;border-bottom:1px solid #e5e7eb;font-size:11px;font-weight:600;text-transform:uppercase;letter-spacing:0.05em;color:#d1d5db;">Ad</td>
        <td style="padding:8px 8px;border-bottom:1px solid #e5e7eb;font-size:11px;font-weight:600;text-transform:uppercase;letter-spacing:0.05em;color:#d1d5db;">Campaign</td>
        <td style="padding:8px 0;border-bottom:1px solid #e5e7eb;font-size:11px;font-weight:600;text-transform:uppercase;letter-spacing:0.05em;color:#d1d5db;text-align:right;">Spend</td>
        <td style="padding:8px 0 8px 12px;border-bottom:1px solid #e5e7eb;font-size:11px;font-weight:600;text-transform:uppercase;letter-spacing:0.05em;color:#d1d5db;text-align:right;">CTR</td>
        <td style="padding:8px 0 8px 12px;border-bottom:1px solid #e5e7eb;font-size:11px;font-weight:600;text-transform:uppercase;letter-spacing:0.05em;color:#d1d5db;text-align:right;">CPC</td>
      </tr>
      {ad_rows}
    </table>
  </td></tr>"""

    return f"""<!DOCTYPE html>
<html lang="en" xmlns="http://www.w3.org/1999/xhtml">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width,initial-scale=1.0">
  <meta name="color-scheme" content="light">
  <meta name="supported-color-schemes" content="light">
  <style>
    :root {{ color-scheme: light only; }}
    body {{ background-color: #ffffff !important; color: #111827 !important; }}
  </style>
</head>
<body style="margin:0;padding:0;background:#ffffff !important;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;">
<table width="100%" cellpadding="0" cellspacing="0" style="background:#ffffff !important;">
<tr><td align="center" style="padding:48px 24px;">
<table width="520" cellpadding="0" cellspacing="0" style="max-width:520px;width:100%;">

  <!-- Header -->
  <tr><td style="padding-bottom:32px;">
    <p style="margin:0 0 20px 0;font-size:13px;font-weight:600;color:#9ca3af;letter-spacing:0.06em;text-transform:uppercase;">Moonstack Dashboard</p>
    <h1 style="margin:0 0 6px 0;font-size:22px;font-weight:700;color:#111827;">Daily Performance Report</h1>
    <p style="margin:0;font-size:14px;color:#9ca3af;">{report_date}</p>
  </td></tr>

  <!-- Divider -->
  <tr><td style="padding-bottom:32px;"><div style="height:1px;background:#e5e7eb;"></div></td></tr>

  <!-- Stats -->
  <tr><td style="padding-bottom:32px;">
    <p style="margin:0 0 12px 0;font-size:12px;font-weight:600;color:#9ca3af;text-transform:uppercase;letter-spacing:0.06em;">Overview</p>
    <table width="100%" cellpadding="0" cellspacing="0">
      {stats_rows}
    </table>
  </td></tr>

  <!-- Performance over time -->
  {timeseries_html}

  <!-- Alerts -->
  {flags_html}

  <!-- Campaign table -->
  <tr><td style="padding-bottom:32px;">
    <p style="margin:0 0 12px 0;font-size:12px;font-weight:600;color:#9ca3af;text-transform:uppercase;letter-spacing:0.06em;">Campaigns</p>
    <table width="100%" cellpadding="0" cellspacing="0">
      <tr>
        <td style="padding:8px 8px 8px 0;border-bottom:1px solid #e5e7eb;font-size:11px;font-weight:600;text-transform:uppercase;letter-spacing:0.05em;color:#d1d5db;width:36%;">Campaign</td>
        <td style="padding:8px 8px;border-bottom:1px solid #e5e7eb;font-size:11px;font-weight:600;text-transform:uppercase;letter-spacing:0.05em;color:#d1d5db;width:16%;">Account</td>
        <td style="padding:8px 0;border-bottom:1px solid #e5e7eb;font-size:11px;font-weight:600;text-transform:uppercase;letter-spacing:0.05em;color:#d1d5db;text-align:right;width:12%;">Spend</td>
        <td style="padding:8px 0;border-bottom:1px solid #e5e7eb;font-size:11px;font-weight:600;text-transform:uppercase;letter-spacing:0.05em;color:#d1d5db;text-align:right;width:10%;">Impr.</td>
        <td style="padding:8px 0;border-bottom:1px solid #e5e7eb;font-size:11px;font-weight:600;text-transform:uppercase;letter-spacing:0.05em;color:#d1d5db;text-align:right;width:10%;">Clicks</td>
        <td style="padding:8px 0;border-bottom:1px solid #e5e7eb;font-size:11px;font-weight:600;text-transform:uppercase;letter-spacing:0.05em;color:#d1d5db;text-align:right;width:8%;">CTR</td>
        <td style="padding:8px 0;border-bottom:1px solid #e5e7eb;font-size:11px;font-weight:600;text-transform:uppercase;letter-spacing:0.05em;color:#d1d5db;text-align:right;width:8%;">CPC</td>
      </tr>
      {all_campaign_rows}
    </table>
  </td></tr>

  <!-- Per-ad breakdown -->
  {ad_rows_html}

  <!-- Footer -->
  <tr><td style="border-top:1px solid #f3f4f6;padding-top:24px;">
    <p style="margin:0;font-size:12px;color:#d1d5db;">Moonstack Dashboard &middot; {report_date}</p>
  </td></tr>

</table>
</td></tr>
</table>
</body>
</html>"""


# ---------------------------------------------------------------------------
# Main send function
# ---------------------------------------------------------------------------

def send_daily_report():
    clients = _load_clients()
    if not clients:
        print("[reporter] No clients configured.")
        return

    accounts_data = []
    all_ads = []
    all_ad_timeseries = []

    for client in clients:
        token = client.get("token", "")
        client_name = client.get("name", "")
        if not token:
            continue
        print(f"[reporter] Loading accounts for {client_name}...")
        accounts = _get_accounts(token)
        for acct in accounts:
            print(f"[reporter]   Fetching {acct['name']}...")
            ins = _get_account_insights(acct["id"], token, "yesterday")
            campaigns = _get_campaign_insights(acct["id"], token, "yesterday")
            ads = _get_ad_insights(acct["id"], token, "yesterday")
            ad_ts = _get_ad_timeseries(acct["id"], token)
            all_ads.extend(ads)
            all_ad_timeseries.extend(ad_ts)
            accounts_data.append({**acct, "client": client_name, "insights": ins, "campaigns": campaigns})

    if not accounts_data:
        print("[reporter] No active accounts found.")
        return

    all_ads.sort(key=lambda a: float(a.get("spend", 0)), reverse=True)

    yesterday = (date.today() - timedelta(days=1)).strftime("%B %d, %Y")
    html = build_email_html(yesterday, accounts_data, all_ads=all_ads, ad_timeseries=all_ad_timeseries)

    total_spend = sum(float(a["insights"].get("spend", 0)) for a in accounts_data)

    resend.api_key = os.getenv("RESEND_API_KEY", RESEND_KEY)
    print(f"[reporter] Sending email to {REPORT_EMAIL}...")
    result = resend.Emails.send({
        "from": "onboarding@resend.dev",
        "to": [REPORT_EMAIL],
        "subject": f"📊 Daily Report — ${total_spend:,.2f} spent · {yesterday}",
        "html": html,
    })
    print(f"[reporter] Email sent: {result}")
    return result
