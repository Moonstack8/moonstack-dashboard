"""
Meta Ads Dashboard - FastAPI Backend
Proxies Meta Graph API calls and serves data to the React frontend.
"""
import os
from fastapi import FastAPI, HTTPException, Query, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from dotenv import load_dotenv
import httpx
from typing import Optional
from pydantic import BaseModel

load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), '..', '.env'))

app = FastAPI(title="Meta Ads Dashboard API")

app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=r"http://localhost:\d+",
    allow_methods=["*"],
    allow_headers=["*"],
)

ACCESS_TOKEN = os.getenv("META_ACCESS_TOKEN", "")
GRAPH_BASE = "https://graph.facebook.com/v21.0"

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def ensure_account_id_format(account_id: str) -> str:
    if not account_id.startswith("act_"):
        return f"act_{account_id}"
    return account_id


def meta_get(path: str, params: dict = None) -> dict:
    """Make a GET request to the Meta Graph API."""
    if not ACCESS_TOKEN:
        raise HTTPException(status_code=500, detail="META_ACCESS_TOKEN not set")
    p = {"access_token": ACCESS_TOKEN, **(params or {})}
    resp = httpx.get(f"{GRAPH_BASE}{path}", params=p, timeout=30.0)
    data = resp.json()
    if "error" in data:
        raise HTTPException(status_code=400, detail=data["error"].get("message", "Meta API error"))
    return data


INSIGHT_FIELDS = (
    "spend,impressions,reach,clicks,ctr,cpc,cpm,cpp,"
    "actions,action_values,cost_per_action_type,"
    "frequency,unique_clicks,unique_ctr"
)


# ---------------------------------------------------------------------------
# Routes: Accounts
# ---------------------------------------------------------------------------

@app.get("/api/accounts")
def get_accounts():
    """List all ad accounts accessible by the token."""
    data = meta_get("/me/adaccounts", {
        "fields": "id,name,account_status,currency,timezone_name,amount_spent,balance"
    })
    return data.get("data", [])


@app.get("/api/accounts/{account_id}/overview")
def get_account_overview(
    account_id: str,
    date_preset: str = Query("last_7d"),
):
    """Account-level aggregate insights + account info."""
    info = meta_get(f"/{account_id}", {
        "fields": "id,name,account_status,currency,timezone_name,amount_spent,balance,spend_cap"
    })
    insights = meta_get(f"/{account_id}/insights", {
        "fields": INSIGHT_FIELDS,
        "date_preset": date_preset,
        "level": "account",
    })
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
    })
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
    })
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
        "fields": "id,name,status,effective_status,daily_budget,lifetime_budget,budget_remaining,targeting,start_time,end_time,optimization_goal,billing_event",
        "limit": 100,
    })
    adset_data = adsets.get("data", [])

    if not adset_data:
        return []

    ids = ",".join(a["id"] for a in adset_data)
    insights_resp = meta_get(f"/{campaign_id}/insights", {
        "fields": "adset_id," + INSIGHT_FIELDS,
        "date_preset": date_preset,
        "level": "adset",
        "filtering": f'[{{"field":"adset.id","operator":"IN","value":[{ids}]}}]',
        "limit": 100,
    })
    insights_by_id = {i["adset_id"]: i for i in insights_resp.get("data", []) if "adset_id" in i}

    for a in adset_data:
        a["insights"] = insights_by_id.get(a["id"], {})

    return adset_data


# ---------------------------------------------------------------------------
# Routes: Ads
# ---------------------------------------------------------------------------

@app.get("/api/adsets/{adset_id}/ads")
def get_ads(
    adset_id: str,
    date_preset: str = Query("last_7d"),
):
    ads = meta_get(f"/{adset_id}/ads", {
        "fields": "id,name,status,effective_status,creative{id,name,thumbnail_url,object_story_spec}",
        "limit": 100,
    })
    ad_data = ads.get("data", [])

    if not ad_data:
        return []

    ids = ",".join(a["id"] for a in ad_data)
    insights_resp = meta_get(f"/{adset_id}/insights", {
        "fields": "ad_id," + INSIGHT_FIELDS,
        "date_preset": date_preset,
        "level": "ad",
        "filtering": f'[{{"field":"ad.id","operator":"IN","value":[{ids}]}}]',
        "limit": 100,
    })
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
    })
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
# Account pages (needed for ad creation)
# ---------------------------------------------------------------------------

@app.get("/api/accounts/{account_id}/pages")
def get_account_pages(account_id: str):
    data = meta_get("/me/accounts", {"fields": "id,name"})
    return data.get("data", [])


# ---------------------------------------------------------------------------
# Image upload (multipart, from frontend file picker)
# ---------------------------------------------------------------------------

@app.post("/api/upload-image")
async def upload_image(account_id: str = Form(...), file: UploadFile = File(...)):
    account_id = ensure_account_id_format(account_id)
    image_bytes = await file.read()
    mime = "image/png" if file.filename.lower().endswith(".png") else "image/jpeg"
    r = httpx.post(
        f"{GRAPH_BASE}/{account_id}/adimages",
        data={"access_token": ACCESS_TOKEN},
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
# Health check
# ---------------------------------------------------------------------------

@app.get("/api/health")
def health():
    return {"status": "ok", "token_set": bool(ACCESS_TOKEN)}
