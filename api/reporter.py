"""
Daily performance email reporter.
Pulls yesterday's Meta Ads data across all accounts and sends a formatted HTML email.
"""
import os
import httpx
import resend
from datetime import date, timedelta
from dotenv import load_dotenv

load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), '..', '.env'))

META_TOKEN = os.getenv("META_ACCESS_TOKEN", "")
RESEND_KEY = os.getenv("RESEND_API_KEY", "")
REPORT_EMAIL = os.getenv("REPORT_EMAIL", "")
GRAPH_BASE = "https://graph.facebook.com/v21.0"

# api_key set per-call to ensure it's always fresh

INSIGHT_FIELDS = "spend,impressions,reach,clicks,ctr,cpc,cpm,actions,action_values,frequency"


# ---------------------------------------------------------------------------
# Data fetching
# ---------------------------------------------------------------------------

def _get(path, params=None):
    p = {"access_token": META_TOKEN, **(params or {})}
    r = httpx.get(f"{GRAPH_BASE}{path}", params=p, timeout=30.0)
    return r.json()


def _get_accounts():
    data = _get("/me/adaccounts", {
        "fields": "id,name,currency,account_status,amount_spent"
    })
    return [a for a in data.get("data", []) if a.get("account_status") == 1]


def _get_account_insights(account_id, date_preset="yesterday"):
    data = _get(f"/{account_id}/insights", {
        "fields": INSIGHT_FIELDS,
        "date_preset": date_preset,
        "level": "account",
    })
    return data.get("data", [{}])[0] if data.get("data") else {}


def _get_campaign_insights(account_id, date_preset="yesterday"):
    campaigns = _get(f"/{account_id}/campaigns", {
        "fields": "id,name,status,effective_status,objective",
        "limit": 50,
    }).get("data", [])

    if not campaigns:
        return []

    ids = ",".join(c["id"] for c in campaigns)
    insights_resp = _get(f"/{account_id}/insights", {
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


def build_email_html(report_date: str, accounts_data: list) -> str:
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
            <tr style="border-bottom:1px solid #1e2130;">
              <td style="padding:10px 12px;color:#e2e8f0;font-size:13px;">
                <span style="display:inline-block;width:7px;height:7px;border-radius:50%;background:{dot_color};margin-right:6px;"></span>
                {camp['name'][:45]}{'...' if len(camp['name']) > 45 else ''}
              </td>
              <td style="padding:10px 12px;color:#94a3b8;font-size:12px;">{acct['name']}</td>
              <td style="padding:10px 12px;color:#e2e8f0;font-size:13px;text-align:right;font-weight:600;">{_fmt_currency(ins.get('spend'))}</td>
              <td style="padding:10px 12px;color:#94a3b8;font-size:13px;text-align:right;">{_fmt_number(ins.get('impressions'))}</td>
              <td style="padding:10px 12px;color:#94a3b8;font-size:13px;text-align:right;">{_fmt_number(ins.get('clicks'))}</td>
              <td style="padding:10px 12px;color:#94a3b8;font-size:13px;text-align:right;">{_fmt_pct(ins.get('ctr'))}</td>
              <td style="padding:10px 12px;color:#94a3b8;font-size:13px;text-align:right;">{_fmt_currency(ins.get('cpc'))}</td>
            </tr>"""

    if not all_campaign_rows:
        all_campaign_rows = """
            <tr><td colspan="7" style="padding:20px;text-align:center;color:#4b5563;font-size:13px;">No active campaign spend yesterday</td></tr>"""

    # Flags / alerts
    flags_html = ""
    flags = []
    for acct in accounts_data:
        ins = acct["insights"]
        freq = float(ins.get("frequency", 0))
        ctr = float(ins.get("ctr", 0))
        spend = float(ins.get("spend", 0))
        if freq > 4:
            flags.append(f"⚠️ <b>{acct['name']}</b>: High frequency ({freq:.1f}x) — audience may be fatigued")
        if ctr < 0.5 and spend > 5:
            flags.append(f"⚠️ <b>{acct['name']}</b>: Low CTR ({_fmt_pct(ctr)}) — consider refreshing creative")
        if spend == 0:
            flags.append(f"🔴 <b>{acct['name']}</b>: Zero spend yesterday — check campaign status")

    if flags:
        flags_items = "".join(f'<li style="margin-bottom:8px;color:#fbbf24;font-size:13px;">{f}</li>' for f in flags)
        flags_html = f"""
        <div style="background:#1a1410;border:1px solid #78350f;border-radius:10px;padding:16px 20px;margin-bottom:24px;">
          <p style="color:#f59e0b;font-size:12px;font-weight:700;text-transform:uppercase;letter-spacing:0.1em;margin:0 0 10px 0;">Alerts</p>
          <ul style="margin:0;padding-left:16px;">{flags_items}</ul>
        </div>"""

    return f"""<!DOCTYPE html>
<html>
<head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1.0"></head>
<body style="margin:0;padding:0;background:#0f1117;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;">
  <div style="max-width:680px;margin:0 auto;padding:32px 16px;">

    <!-- Header -->
    <div style="margin-bottom:28px;">
      <div style="display:flex;align-items:center;gap:10px;margin-bottom:8px;">
        <div style="width:28px;height:28px;background:#3b5bdb;border-radius:7px;display:inline-flex;align-items:center;justify-content:center;">
          <span style="color:white;font-size:14px;">📈</span>
        </div>
        <span style="color:#3b82f6;font-size:13px;font-weight:600;letter-spacing:0.05em;">ADPILOT</span>
      </div>
      <h1 style="color:#f1f5f9;font-size:22px;font-weight:700;margin:0 0 4px 0;">Daily Performance Report</h1>
      <p style="color:#64748b;font-size:13px;margin:0;">{report_date} · {len(accounts_data)} account{'s' if len(accounts_data) != 1 else ''}</p>
    </div>

    <!-- Top metrics -->
    <div style="display:grid;grid-template-columns:repeat(2,1fr);gap:12px;margin-bottom:24px;">
      {_metric_card("Total Spend", _fmt_currency(total_spend), highlight=True)}
      {_metric_card("Impressions", _fmt_number(total_impressions))}
      {_metric_card("Clicks", _fmt_number(total_clicks))}
      {_metric_card("Reach", _fmt_number(total_reach))}
      {_metric_card("CTR", _fmt_pct(avg_ctr))}
      {_metric_card("CPC", _fmt_currency(avg_cpc))}
      {_metric_card("CPM", _fmt_currency(avg_cpm))}
      {_metric_card("ROAS", f"{roas:.2f}x" if roas else "—")}
    </div>

    {'<!-- Revenue -->' + _metric_card("Revenue", _fmt_currency(total_revenue), highlight=True, wide=True) if total_revenue > 0 else ''}

    <!-- Flags -->
    {flags_html}

    <!-- Campaign table -->
    <div style="background:#13151f;border:1px solid #1e2130;border-radius:10px;overflow:hidden;margin-bottom:24px;">
      <div style="padding:14px 16px;border-bottom:1px solid #1e2130;">
        <p style="color:#94a3b8;font-size:11px;font-weight:700;text-transform:uppercase;letter-spacing:0.1em;margin:0;">Campaign Breakdown</p>
      </div>
      <table style="width:100%;border-collapse:collapse;">
        <thead>
          <tr style="border-bottom:1px solid #1e2130;">
            <th style="padding:8px 12px;text-align:left;color:#4b5563;font-size:11px;font-weight:600;text-transform:uppercase;letter-spacing:0.05em;">Campaign</th>
            <th style="padding:8px 12px;text-align:left;color:#4b5563;font-size:11px;font-weight:600;text-transform:uppercase;">Account</th>
            <th style="padding:8px 12px;text-align:right;color:#4b5563;font-size:11px;font-weight:600;text-transform:uppercase;">Spend</th>
            <th style="padding:8px 12px;text-align:right;color:#4b5563;font-size:11px;font-weight:600;text-transform:uppercase;">Impr.</th>
            <th style="padding:8px 12px;text-align:right;color:#4b5563;font-size:11px;font-weight:600;text-transform:uppercase;">Clicks</th>
            <th style="padding:8px 12px;text-align:right;color:#4b5563;font-size:11px;font-weight:600;text-transform:uppercase;">CTR</th>
            <th style="padding:8px 12px;text-align:right;color:#4b5563;font-size:11px;font-weight:600;text-transform:uppercase;">CPC</th>
          </tr>
        </thead>
        <tbody>{all_campaign_rows}</tbody>
      </table>
    </div>

    <!-- Footer -->
    <p style="color:#374151;font-size:12px;text-align:center;margin:0;">
      Sent by AdPilot · Daily at 8:00 AM ET · <a href="#" style="color:#3b5bdb;">Unsubscribe</a>
    </p>
  </div>
</body>
</html>"""


def _metric_card(label, value, highlight=False, wide=False):
    bg = "#0f1a3e" if highlight else "#13151f"
    border = "#1e3a8a" if highlight else "#1e2130"
    val_color = "#60a5fa" if highlight else "#f1f5f9"
    span = 'colspan="2"' if wide else ""
    return f"""
      <div {span} style="background:{bg};border:1px solid {border};border-radius:10px;padding:16px;">
        <p style="color:#64748b;font-size:11px;font-weight:600;text-transform:uppercase;letter-spacing:0.08em;margin:0 0 6px 0;">{label}</p>
        <p style="color:{val_color};font-size:22px;font-weight:700;margin:0;">{value}</p>
      </div>"""


# ---------------------------------------------------------------------------
# Main send function
# ---------------------------------------------------------------------------

def send_daily_report():
    print("[reporter] Fetching accounts...")
    accounts = _get_accounts()
    if not accounts:
        print("[reporter] No active accounts found.")
        return

    accounts_data = []
    for acct in accounts:
        print(f"[reporter] Fetching insights for {acct['name']}...")
        ins = _get_account_insights(acct["id"], "yesterday")
        campaigns = _get_campaign_insights(acct["id"], "yesterday")
        accounts_data.append({**acct, "insights": ins, "campaigns": campaigns})

    yesterday = (date.today() - timedelta(days=1)).strftime("%B %d, %Y")
    html = build_email_html(yesterday, accounts_data)

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
