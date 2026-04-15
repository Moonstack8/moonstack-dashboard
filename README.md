# Moonstack Dashboard

A local Meta Ads management platform for agencies. Monitor all client accounts from a unified dashboard, autonomously create campaigns with AI, and receive daily performance reports by email.

---

## Stack

| Layer | Tech |
|---|---|
| Frontend | React + Vite + Tailwind CSS + Recharts |
| Backend | FastAPI (Python) |
| AI Agent | Claude (Anthropic SDK) |
| Email | Resend |
| Scheduler | APScheduler |
| Meta API | Graph API v21.0 |

---

## Setup

### 1. Clone and install

```bash
# Backend deps (uses .venv)
.venv/bin/python -m pip install fastapi "uvicorn[standard]" httpx python-dotenv anthropic resend apscheduler

# Frontend deps
cd dashboard && npm install
```

### 2. Configure `.env`

```env
ANTHROPIC_API_KEY=your_anthropic_api_key
RESEND_API_KEY=your_resend_api_key
REPORT_EMAIL=you@example.com
REPORT_HOUR=8
```

`META_ACCESS_TOKEN` is no longer needed in `.env` — client tokens are managed in `config/clients.yaml` (see below).

### 3. Add clients to `config/clients.yaml`

Each entry is one business you manage. The token is their Meta access token. Accounts are discovered automatically on startup — no need to specify account IDs manually.

```yaml
clients:
  - name: Acme Corp
    token: EAAxxxxxxx...

  - name: Client B
    token: EAAyyyyyyy...
```

**To add a new client:** add an entry to `clients.yaml`, then either restart the server or call:

```bash
curl -X POST http://localhost:8000/api/clients/reload
```

This picks up the new client without a restart.

### 4. Start

```bash
./start.sh
```

- Dashboard → http://localhost:5173
- API → http://localhost:8000

`start.sh` kills any stale processes on ports 8000 and 5173 before starting.

---

## Features

### Dashboard — Overview

**Route:** `/`

Aggregated view across all connected Meta ad accounts.

- Total spend, impressions, clicks, reach, CTR, CPC, CPM, ROAS
- Conversions and revenue (when pixel data is available)
- Per-account summary cards — click any to drill down
- Date range picker: Today / Yesterday / 7d / 14d / 30d / 90d
- Auto-refreshes every 30 seconds

---

### Dashboard — Account View

**Route:** `/accounts/:accountId`

Full breakdown for a single ad account.

- Account-level metrics: spend, impressions, clicks, reach, CTR, CPC, CPM, frequency, ROAS
- All-time spend and balance
- Area chart with daily spend / impressions / clicks (toggle metrics on/off)
- Campaigns table with inline insights and status badges
- Click any campaign to drill down

---

### Dashboard — Campaign View

**Route:** `/campaigns/:campaignId`

- Aggregated metrics across all ad sets in the campaign
- Daily performance chart
- Ad sets table with targeting summary, budget, optimization goal, and insights
- Click any ad set to drill down
- Delete ad sets directly from the table

---

### Dashboard — Ad Set View

**Route:** `/adsets/:adsetId`

- Ad-level metrics: spend, impressions, clicks, CTR, CPC, CPM, reach, frequency
- Ads table with creative thumbnails, status, and full performance metrics
- Delete individual ads from the table

---

### Delete

Available at every level (campaigns, ad sets, ads).

- Trash icon on every table row
- First click shows **Confirm?** (3-second window)
- Second click deletes and removes the row instantly (no page reload)
- Deletes set the object status to `DELETED` via the Meta API

---

### Campaign Builder (AI Agent)

**Route:** `/builder`

Autonomous campaign creation powered by Claude.

**Flow:**
1. Select an ad account
2. Write a natural-language client brief (or pick an example)
3. Click **Generate Campaign Plan**
4. The agent streams its work in real-time:
   - Searches for relevant interest targeting
   - Looks up geographic targeting keys
   - Estimates audience size (iterates if too narrow or too broad)
   - Writes 2–3 ad copy variations with distinct hooks/angles
5. A full campaign plan appears for review:
   - Campaign name, objective, budget, budget type (CBO/ABO)
   - Ad sets with targeting chips (interests, age range, geo, placements)
   - Ads with headline, primary text, CTA, and destination URL
6. Upload images for the variations you want (ads without images are skipped)
7. Select a Facebook Page
8. Click **Launch** — creates everything in Meta as PAUSED

**Agent tools:**
| Tool | Description |
|---|---|
| `search_interests` | Finds relevant Facebook/Instagram interest categories |
| `search_geo` | Resolves geographic targeting keys (countries, regions, cities) |
| `estimate_audience` | Estimates reach for a targeting spec, flags too-narrow or too-broad |
| `submit_plan` | Outputs the final structured campaign JSON for human review |

**Naming conventions enforced by the agent:**
- Campaign: `[Objective] | [Client] | [Funnel] | [Budget Type]`
- Ad Set: `[Targeting] | [Age] | [Geo] | [Notes]`
- Ad: `[Hook] | [Format] | [Version]`

All campaigns and ads are created **PAUSED** — nothing goes live until you activate manually.

---

### Daily Email Reports

Sent automatically every day at the time set in `REPORT_HOUR` (default: 8:00 AM ET).

**Email includes:**
- Total spend, impressions, clicks, reach, CTR, CPC, CPM, ROAS across all accounts
- Revenue and conversions (when available)
- Full campaign breakdown table with status indicators
- Alerts:
  - High frequency (> 4x) — audience fatigue warning
  - Low CTR (< 0.5%) — creative refresh suggestion
  - Zero spend — campaign status check

**To send a report immediately:**
```bash
curl -X POST http://localhost:8000/api/reports/send-now
```

**To change send time:** update `REPORT_HOUR` in `.env` (24h format, ET timezone) and restart.

---

## Client Onboarding

### The agency approach (recommended)

Instead of having clients create system users and tokens, use **Business Manager Partner Access**. You use your own Moonstack token — clients just grant you access to their account.

**What the client does (3 steps):**

1. **Create a Facebook Page** — [facebook.com/pages](https://www.facebook.com/pages) → Create Page
2. **Set up a Business Portfolio + Ad Account**
   - [business.facebook.com](https://business.facebook.com) → Business Portfolio → Create a business portfolio → attach the Page
   - Settings → Ad Accounts → Create new ad account → add payment info
3. **Send you three IDs:**
   - **Business Portfolio ID:** Settings → Business Info → Business Portfolio ID
   - **Ad Account ID:** `business.facebook.com/latest/settings/ad_accounts`
   - **Page ID:** `business.facebook.com/latest/settings/pages`

**What you do:**

1. Go to your Moonstack Business Manager → Settings → Partners → Add Partner
2. Enter the client's Business Portfolio ID and request access to their Ad Account and Page
3. Client clicks Accept
4. Go to Business Settings → **System Users** → click the Moonstack system user → **Assign Assets**
5. Under **Ad Accounts**, the client's account will now appear — assign it with **Full Control**
6. **Regenerate the system user token** (Generate New Token → Never expiry → all permissions) and update `config/clients.yaml`
7. Run `curl -X POST http://localhost:8000/api/clients/reload` — their account will appear in the dashboard

No Meta app setup. No system users. No token generation on the client's side.

---

### If a client needs a token (advanced)

Only needed if you want the client to have their own system user instead of partner access.

1. Client creates Business Portfolio + Ad Account (steps 1–2 above)
2. **Create a System User:** Business Settings → System Users → New → role: Admin
3. Assign the system user to the Ad Account and Page (Full Control)
4. **Generate token:** System Users → Generate Token → expiry: Never → select all permissions
5. Client sends you the token → add to `config/clients.yaml`

---

## API Reference

| Method | Endpoint | Description |
|---|---|---|
| GET | `/api/accounts` | List all ad accounts |
| GET | `/api/accounts/:id/overview` | Account info + aggregate insights |
| GET | `/api/accounts/:id/campaigns` | Campaigns with insights |
| GET | `/api/accounts/:id/timeseries` | Daily breakdown for charts |
| GET | `/api/accounts/:id/pages` | Facebook pages for the account |
| GET | `/api/campaigns/:id/adsets` | Ad sets with insights |
| GET | `/api/campaigns/:id/timeseries` | Campaign daily breakdown |
| GET | `/api/adsets/:id/ads` | Ads with insights and creative |
| POST | `/api/upload-image` | Upload ad image, returns hash |
| POST | `/api/agent/plan` | Stream AI campaign planning (SSE) |
| POST | `/api/agent/execute` | Execute an approved campaign plan |
| DELETE | `/api/ads/:id` | Delete an ad |
| DELETE | `/api/adsets/:id` | Delete an ad set |
| DELETE | `/api/campaigns/:id` | Delete a campaign |
| POST | `/api/reports/send-now` | Trigger daily report immediately |
| POST | `/api/clients/reload` | Reload clients.yaml without restart |
| GET | `/api/health` | Health check |

All insight endpoints accept a `?date_preset=` query param: `today`, `yesterday`, `last_7d`, `last_14d`, `last_30d`, `last_90d`.

---

## Project Structure

```
.
├── api/
│   ├── main.py          # FastAPI app, all routes
│   ├── agent.py         # Claude agent (planning tools + streaming)
│   ├── executor.py      # Deterministic Meta API campaign executor
│   └── reporter.py      # Daily email report builder + sender
├── dashboard/
│   └── src/
│       ├── pages/
│       │   ├── Overview.jsx
│       │   ├── AccountView.jsx
│       │   ├── CampaignView.jsx
│       │   ├── AdSetView.jsx
│       │   └── CampaignBuilder.jsx
│       ├── components/
│       │   ├── Sidebar.jsx
│       │   ├── AgentStream.jsx
│       │   ├── CampaignPlanPreview.jsx
│       │   ├── DataTable.jsx
│       │   ├── DeleteButton.jsx
│       │   ├── MetricCard.jsx
│       │   ├── SparkChart.jsx
│       │   ├── StatusBadge.jsx
│       │   ├── DatePresetPicker.jsx
│       │   └── LoadingSpinner.jsx
│       └── lib/
│           ├── api.js   # Axios API client
│           └── format.js # Number/currency/date formatters
├── config/
│   └── clients.yaml     # Client businesses (name + Meta token per client)
├── initial_tests/       # Original Meta API test scripts
├── .env                 # API keys (Anthropic, Resend, report config)
└── start.sh             # Start both servers
```
