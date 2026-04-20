"""
Meta Ads Dashboard - FastAPI Backend
Proxies Meta Graph API calls and serves data to the React frontend.
"""
import os
import yaml
from fastapi import FastAPI, HTTPException, Query, UploadFile, File, Form, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from dotenv import load_dotenv
import httpx
import jwt
from jwt import PyJWKClient
from typing import Optional
from pydantic import BaseModel

from contextlib import asynccontextmanager
from apscheduler.schedulers.background import BackgroundScheduler

load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), '..', '.env'))

REPORT_HOUR = int(os.getenv("REPORT_HOUR", "8"))
GRAPH_BASE = "https://graph.facebook.com/v21.0"

# ---------------------------------------------------------------------------
# Client config — loaded from config/clients.yaml
# Falls back to META_ACCESS_TOKEN in .env if no yaml exists.
# ---------------------------------------------------------------------------

_CLIENTS_PATH = os.path.join(os.path.dirname(__file__), '..', 'config', 'clients.yaml')

def load_clients() -> list[dict]:
    """Return list of {name, token} from clients.yaml, falling back to .env."""
    if os.path.exists(_CLIENTS_PATH):
        with open(_CLIENTS_PATH) as f:
            data = yaml.safe_load(f) or {}
        clients = data.get("clients", [])
        if clients:
            return clients
    # Fallback: single client from .env
    token = os.getenv("META_ACCESS_TOKEN", "")
    return [{"name": "Default", "token": token}] if token else []


# account_id -> {token, client_name} — populated on startup
ACCOUNT_MAP: dict[str, dict] = {}

def _build_account_map():
    """Fetch all accounts for every client and build the lookup map."""
    ACCOUNT_MAP.clear()
    for client in load_clients():
        token = client.get("token", "")
        name  = client.get("name", "Unknown")
        if not token:
            continue
        try:
            resp = httpx.get(
                f"{GRAPH_BASE}/me/adaccounts",
                params={"fields": "id,name,account_status,currency,timezone_name,amount_spent,balance", "access_token": token},
                timeout=15.0,
            ).json()
            for acct in resp.get("data", []):
                ACCOUNT_MAP[acct["id"]] = {"token": token, "client": name}
            print(f"[clients] {name}: {len(resp.get('data', []))} accounts loaded")
        except Exception as e:
            print(f"[clients] Failed to load accounts for {name}: {e}")

def _normalize_account_id(account_id: str) -> str:
    """Ensure account_id has act_ prefix."""
    if account_id and not account_id.startswith("act_"):
        return f"act_{account_id}"
    return account_id

def _token_for(account_id: str) -> str:
    aid = _normalize_account_id(account_id)
    entry = ACCOUNT_MAP.get(aid)
    if entry:
        return entry["token"]
    # Fallback to first available token
    for v in ACCOUNT_MAP.values():
        return v["token"]
    return os.getenv("META_ACCESS_TOKEN", "")


def _start_scheduler(app):
    scheduler = BackgroundScheduler(timezone="America/New_York")
    scheduler.add_job(
        lambda: __import__('api.reporter', fromlist=['send_daily_report']).send_daily_report(),
        trigger="cron",
        hour=REPORT_HOUR,
        minute=0,
        id="daily_report",
    )
    scheduler.start()
    app.state.scheduler = scheduler
    print(f"[scheduler] Daily report scheduled at {REPORT_HOUR}:00 ET")

@asynccontextmanager
async def lifespan(app):
    _build_account_map()
    _start_scheduler(app)
    yield
    if hasattr(app.state, "scheduler"):
        app.state.scheduler.shutdown()

app = FastAPI(title="Meta Ads Dashboard API", lifespan=lifespan)

# ---------------------------------------------------------------------------
# Clerk JWT verification
# ---------------------------------------------------------------------------
CLERK_JWKS_URL = os.getenv("CLERK_JWKS_URL", "")
_jwks_client = None

def _get_jwks_client():
    global _jwks_client
    if _jwks_client is None and CLERK_JWKS_URL:
        _jwks_client = PyJWKClient(CLERK_JWKS_URL, cache_keys=True)
    return _jwks_client

def verify_clerk_token(token: str) -> dict:
    client = _get_jwks_client()
    signing_key = client.get_signing_key_from_jwt(token)
    return jwt.decode(token, signing_key.key, algorithms=["RS256"],
                      options={"verify_aud": False})

class ClerkAuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if not CLERK_JWKS_URL:
            request.state.role = "admin"
            request.state.allowed_accounts = []
            return await call_next(request)
        if request.method == "OPTIONS" or request.url.path in ("/api/health", "/api/clients/reload"):
            return await call_next(request)
        auth = request.headers.get("Authorization", "")
        if not auth.startswith("Bearer "):
            return JSONResponse({"error": "Unauthorized"}, status_code=401)
        try:
            claims = verify_clerk_token(auth[7:])
            meta = claims.get("public_metadata", {})
            request.state.role = meta.get("role", "client")
            request.state.allowed_accounts = meta.get("accounts", [])
        except Exception:
            return JSONResponse({"error": "Unauthorized"}, status_code=401)
        return await call_next(request)

app.add_middleware(ClerkAuthMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=r"http://localhost:\d+|https://.*\.trymoonstack\.com|https://.*\.vercel\.app",
    allow_methods=["*"],
    allow_headers=["*"],
)

# Keep ACCESS_TOKEN for backwards compat (agent, executor, upload)
ACCESS_TOKEN = os.getenv("META_ACCESS_TOKEN", "")

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def ensure_account_id_format(account_id: str) -> str:
    if not account_id.startswith("act_"):
        return f"act_{account_id}"
    return account_id


def meta_get(path: str, params: dict = None, account_id: str = None) -> dict:
    """Make a GET request to the Meta Graph API.
    If account_id is known, uses its token directly.
    Otherwise tries all client tokens until one succeeds.
    """
    if account_id and _normalize_account_id(account_id) in ACCOUNT_MAP:
        token = ACCOUNT_MAP[_normalize_account_id(account_id)]["token"]
        p = {"access_token": token, **(params or {})}
        resp = httpx.get(f"{GRAPH_BASE}{path}", params=p, timeout=30.0)
        data = resp.json()
        if "error" in data:
            raise HTTPException(status_code=400, detail=data["error"].get("message", "Meta API error"))
        return data

    # No known account — try all client tokens
    clients = load_clients()
    if not clients:
        raise HTTPException(status_code=500, detail="No Meta access tokens configured")
    last_error = "Meta API error"
    for client in clients:
        token = client.get("token", "")
        if not token:
            continue
        p = {"access_token": token, **(params or {})}
        resp = httpx.get(f"{GRAPH_BASE}{path}", params=p, timeout=30.0)
        data = resp.json()
        if "error" not in data:
            return data
        last_error = data["error"].get("message", last_error)
    raise HTTPException(status_code=400, detail=last_error)


INSIGHT_FIELDS = (
    "spend,impressions,reach,clicks,ctr,cpc,cpm,cpp,"
    "actions,action_values,cost_per_action_type,"
    "frequency,unique_clicks,unique_ctr"
)


# ---------------------------------------------------------------------------
# Routes: Accounts
# ---------------------------------------------------------------------------

@app.get("/api/accounts")
def get_accounts(request: Request):
    """List all ad accounts across all configured clients."""
    results = []
    seen = set()
    for client in load_clients():
        token = client.get("token", "")
        if not token:
            continue
        data = httpx.get(
            f"{GRAPH_BASE}/me/adaccounts",
            params={"fields": "id,name,account_status,currency,timezone_name,amount_spent,balance", "access_token": token},
            timeout=15.0,
        ).json()
        for acct in data.get("data", []):
            if acct["id"] not in seen:
                seen.add(acct["id"])
                acct["client"] = client.get("name", "")
                results.append(acct)
    role = getattr(request.state, "role", "client")
    if role != "admin":
        allowed = getattr(request.state, "allowed_accounts", [])
        results = [a for a in results if a["id"] in allowed]
    return results


@app.post("/api/clients/reload")
def reload_clients():
    """Reload client account map from clients.yaml (no restart needed)."""
    _build_account_map()
    return {"status": "ok", "accounts_loaded": len(ACCOUNT_MAP)}


@app.get("/api/accounts/{account_id}/overview")
def get_account_overview(
    account_id: str,
    date_preset: str = Query("last_7d"),
):
    """Account-level aggregate insights + account info."""
    info = meta_get(f"/{account_id}", {
        "fields": "id,name,account_status,currency,timezone_name,amount_spent,balance,spend_cap"
    }, account_id=account_id)
    info["client"] = ACCOUNT_MAP.get(account_id, {}).get("client", "")
    insights = meta_get(f"/{account_id}/insights", {
        "fields": INSIGHT_FIELDS,
        "date_preset": date_preset,
        "level": "account",
    }, account_id=account_id)
    return {
        "info": info,
        "insights": insights.get("data", [{}])[0] if insights.get("data") else {},
    }


# ---------------------------------------------------------------------------
# Routes: Campaigns
# ---------------------------------------------------------------------------

@app.get("/api/accounts/{account_id}/campaigns")
def get_campaigns(
    account_id: str,
    date_preset: str = Query("last_7d"),
):
    campaigns = meta_get(f"/{account_id}/campaigns", {
        "fields": "id,name,status,effective_status,objective,daily_budget,lifetime_budget,budget_remaining,start_time,stop_time",
        "limit": 100,
    }, account_id=account_id)
    campaign_data = campaigns.get("data", [])

    if not campaign_data:
        return []

    # Fetch insights for each campaign in one batch call
    ids = ",".join(c["id"] for c in campaign_data)
    insights_resp = meta_get(f"/{account_id}/insights", {
        "fields": "campaign_id," + INSIGHT_FIELDS,
        "date_preset": date_preset,
        "level": "campaign",
        "filtering": f'[{{"field":"campaign.id","operator":"IN","value":[{ids}]}}]',
        "limit": 100,
    }, account_id=account_id)
    insights_by_id = {i["campaign_id"]: i for i in insights_resp.get("data", []) if "campaign_id" in i}

    for c in campaign_data:
        c["insights"] = insights_by_id.get(c["id"], {})

    return campaign_data


# ---------------------------------------------------------------------------
# Routes: Ad Sets
# ---------------------------------------------------------------------------

@app.get("/api/campaigns/{campaign_id}/adsets")
def get_adsets(
    campaign_id: str,
    date_preset: str = Query("last_7d"),
):
    adsets = meta_get(f"/{campaign_id}/adsets", {
        "fields": "id,name,status,effective_status,daily_budget,lifetime_budget,budget_remaining,targeting,start_time,end_time,optimization_goal,billing_event,account_id",
        "limit": 100,
    })
    adset_data = adsets.get("data", [])

    if not adset_data:
        return []

    account_id = adset_data[0].get("account_id")
    ids = ",".join(a["id"] for a in adset_data)
    insights_resp = meta_get(f"/{campaign_id}/insights", {
        "fields": "adset_id," + INSIGHT_FIELDS,
        "date_preset": date_preset,
        "level": "adset",
        "filtering": f'[{{"field":"adset.id","operator":"IN","value":[{ids}]}}]',
        "limit": 100,
    }, account_id=account_id)
    insights_by_id = {i["adset_id"]: i for i in insights_resp.get("data", []) if "adset_id" in i}

    for a in adset_data:
        a["insights"] = insights_by_id.get(a["id"], {})

    return adset_data


# ---------------------------------------------------------------------------
# Routes: Ads
# ---------------------------------------------------------------------------

@app.get("/api/ads/{ad_id}/timeseries")
def get_ad_timeseries(
    ad_id: str,
    date_preset: str = Query("last_30d"),
    time_increment: int = Query(1),
):
    data = meta_get(f"/{ad_id}/insights", {
        "fields": "spend,impressions,clicks,ctr,cpc,cpm",
        "date_preset": date_preset,
        "time_increment": time_increment,
        "level": "ad",
    })
    return data.get("data", [])


@app.get("/api/ads/{ad_id}")
def get_ad(ad_id: str):
    data = meta_get(f"/{ad_id}", {
        "fields": "id,name,status,effective_status,adset_id,campaign_id,creative{id,name,thumbnail_url,object_story_spec},account_id",
    })
    # Attach insights
    insights_resp = meta_get(f"/{ad_id}/insights", {
        "fields": INSIGHT_FIELDS,
        "date_preset": "last_30d",
    })
    data["insights"] = insights_resp.get("data", [{}])[0] if insights_resp.get("data") else {}
    return data


@app.get("/api/adsets/{adset_id}")
def get_adset(adset_id: str):
    data = meta_get(f"/{adset_id}", {
        "fields": "id,name,status,effective_status,daily_budget,lifetime_budget,budget_remaining,start_time,end_time,optimization_goal,account_id",
    })
    return data


@app.get("/api/adsets/{adset_id}/ads")
def get_ads(
    adset_id: str,
    date_preset: str = Query("last_7d"),
):
    ads = meta_get(f"/{adset_id}/ads", {
        "fields": "id,name,status,effective_status,creative{id,name,thumbnail_url,object_story_spec},account_id",
        "limit": 100,
    })
    ad_data = ads.get("data", [])

    if not ad_data:
        return []

    account_id = ad_data[0].get("account_id")
    ids = ",".join(a["id"] for a in ad_data)
    insights_resp = meta_get(f"/{adset_id}/insights", {
        "fields": "ad_id," + INSIGHT_FIELDS,
        "date_preset": date_preset,
        "level": "ad",
        "filtering": f'[{{"field":"ad.id","operator":"IN","value":[{ids}]}}]',
        "limit": 100,
    }, account_id=account_id)
    insights_by_id = {i["ad_id"]: i for i in insights_resp.get("data", []) if "ad_id" in i}

    for a in ad_data:
        a["insights"] = insights_by_id.get(a["id"], {})

    return ad_data


# ---------------------------------------------------------------------------
# Routes: Insights (time series)
# ---------------------------------------------------------------------------

@app.get("/api/accounts/{account_id}/timeseries")
def get_account_timeseries(
    account_id: str,
    date_preset: str = Query("last_30d"),
    time_increment: int = Query(1),
):
    """Daily breakdown for spend/impressions/clicks chart."""
    data = meta_get(f"/{account_id}/insights", {
        "fields": "spend,impressions,clicks,ctr,cpc,cpm",
        "date_preset": date_preset,
        "time_increment": time_increment,
        "level": "account",
    }, account_id=account_id)
    return data.get("data", [])


@app.get("/api/campaigns/{campaign_id}/timeseries")
def get_campaign_timeseries(
    campaign_id: str,
    date_preset: str = Query("last_30d"),
    time_increment: int = Query(1),
):
    data = meta_get(f"/{campaign_id}/insights", {
        "fields": "spend,impressions,clicks,ctr,cpc,cpm",
        "date_preset": date_preset,
        "time_increment": time_increment,
        "level": "campaign",
    })
    return data.get("data", [])


# ---------------------------------------------------------------------------
# Delete (archives object in Meta — ads, adsets, campaigns)
# ---------------------------------------------------------------------------

def meta_update(object_id: str, payload: dict, account_id: str = None) -> dict:
    token = _token_for(account_id) if account_id else ACCESS_TOKEN
    r = httpx.post(
        f"{GRAPH_BASE}/{object_id}",
        json={"access_token": token, **payload},
        timeout=20.0,
    )
    result = r.json()
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"].get("message", "Update failed"))
    return result

def meta_delete(object_id: str, account_id: str = None) -> dict:
    return meta_update(object_id, {"status": "DELETED"}, account_id)

@app.delete("/api/ads/{ad_id}")
def delete_ad(ad_id: str):
    return meta_delete(ad_id)

@app.delete("/api/adsets/{adset_id}")
def delete_adset(adset_id: str):
    return meta_delete(adset_id)

@app.delete("/api/campaigns/{campaign_id}")
def delete_campaign(campaign_id: str):
    return meta_delete(campaign_id)


# ---------------------------------------------------------------------------
# Status toggle (ACTIVE ↔ PAUSED)
# ---------------------------------------------------------------------------

class StatusUpdateRequest(BaseModel):
    status: str  # "ACTIVE" or "PAUSED"

@app.post("/api/ads/{ad_id}/status")
def update_ad_status(ad_id: str, req: StatusUpdateRequest):
    if req.status not in ("ACTIVE", "PAUSED"):
        raise HTTPException(status_code=400, detail="status must be ACTIVE or PAUSED")
    return meta_update(ad_id, {"status": req.status})

@app.post("/api/adsets/{adset_id}/status")
def update_adset_status(adset_id: str, req: StatusUpdateRequest):
    if req.status not in ("ACTIVE", "PAUSED"):
        raise HTTPException(status_code=400, detail="status must be ACTIVE or PAUSED")
    return meta_update(adset_id, {"status": req.status})

@app.post("/api/campaigns/{campaign_id}/status")
def update_campaign_status(campaign_id: str, req: StatusUpdateRequest):
    if req.status not in ("ACTIVE", "PAUSED"):
        raise HTTPException(status_code=400, detail="status must be ACTIVE or PAUSED")
    return meta_update(campaign_id, {"status": req.status})


# ---------------------------------------------------------------------------
# Account pages (needed for ad creation)
# ---------------------------------------------------------------------------

@app.get("/api/accounts/{account_id}/pages")
def get_account_pages(account_id: str):
    data = meta_get("/me/accounts", {"fields": "id,name"}, account_id=account_id)
    return data.get("data", [])


# ---------------------------------------------------------------------------
# Image upload (multipart, from frontend file picker)
# ---------------------------------------------------------------------------

@app.post("/api/upload-image")
async def upload_image(account_id: str = Form(...), file: UploadFile = File(...)):
    account_id = ensure_account_id_format(account_id)
    image_bytes = await file.read()
    mime = "image/png" if file.filename.lower().endswith(".png") else "image/jpeg"
    token = _token_for(account_id)
    r = httpx.post(
        f"{GRAPH_BASE}/{account_id}/adimages",
        data={"access_token": token},
        files={"filename": (file.filename, image_bytes, mime)},
        timeout=60.0,
    )
    result = r.json()
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"].get("message", "Upload failed"))
    images = result.get("images", {})
    if not images:
        raise HTTPException(status_code=400, detail="No image data returned")
    image_data = next(iter(images.values()))
    return {"image_hash": image_data["hash"], "url": image_data.get("url"), "name": file.filename}


# ---------------------------------------------------------------------------
# Agent: Campaign planning (streaming SSE)
# ---------------------------------------------------------------------------

class PlanRequest(BaseModel):
    brief: str
    account_id: str

@app.post("/api/agent/plan")
def agent_plan(req: PlanRequest):
    from api.agent import run_planning_agent
    return StreamingResponse(
        run_planning_agent(req.brief, req.account_id),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


# ---------------------------------------------------------------------------
# Agent: Optimize existing ad
# ---------------------------------------------------------------------------

class OptimizeRequest(BaseModel):
    ad_id: str
    account_id: str

@app.post("/api/agent/optimize")
def agent_optimize(req: OptimizeRequest):
    from api.optimizer import run_optimizer_agent
    token = _token_for(req.account_id)
    return StreamingResponse(
        run_optimizer_agent(req.ad_id, req.account_id, token),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


# ---------------------------------------------------------------------------
# Agent: Execute approved plan
# ---------------------------------------------------------------------------

class ExecuteRequest(BaseModel):
    plan: dict
    account_id: str
    page_id: str
    image_hashes: dict  # {"0": "hash", "1": "hash", ...}

@app.post("/api/agent/execute")
def agent_execute(req: ExecuteRequest):
    import traceback
    from api.executor import execute_plan
    try:
        result = execute_plan(req.plan, req.account_id, req.page_id, req.image_hashes)
        return result
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=400, detail=str(e))


# ---------------------------------------------------------------------------
# Reports
# ---------------------------------------------------------------------------

@app.post("/api/reports/send-now")
def send_report_now():
    """Trigger the daily report immediately (for testing)."""
    from api.reporter import send_daily_report
    try:
        result = send_daily_report()
        return {"status": "sent", "result": str(result)}
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------

@app.get("/api/health")
def health():
    return {"status": "ok", "token_set": bool(ACCESS_TOKEN), "report_hour": REPORT_HOUR}
