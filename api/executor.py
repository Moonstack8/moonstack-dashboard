"""
Deterministic plan executor.
Takes an approved campaign plan + image hashes and creates everything in Meta, all PAUSED.
"""
import json
import os
import httpx
from dotenv import load_dotenv
import traceback

load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), '..', '.env'))

META_TOKEN = os.getenv("META_ACCESS_TOKEN", "")
GRAPH_BASE = "https://graph.facebook.com/v21.0"


def _post(path: str, data: dict) -> dict:
    payload = {k: v for k, v in data.items() if k != "access_token"}
    print(f"\n→ POST {GRAPH_BASE}{path}")
    print(f"  payload: {json.dumps(payload, indent=2)}")

    data["access_token"] = META_TOKEN
    r = httpx.post(f"{GRAPH_BASE}{path}", json=data, timeout=30.0)
    result = r.json()

    print(f"  status: {r.status_code}")
    print(f"  response: {json.dumps(result, indent=2)}")

    if "error" in result:
        err = result["error"]
        msg = err.get("message", str(err))
        code = err.get("code", "")
        subcode = err.get("error_subcode", "")
        raise RuntimeError(f"Meta API error [{code}/{subcode}] on {path}: {msg}")
    return result


# Map campaign objective → ad set destination_type
OBJECTIVE_DESTINATION = {
    "OUTCOME_TRAFFIC": "WEBSITE",
    "OUTCOME_LEADS": "WEBSITE",
    "OUTCOME_SALES": "WEBSITE",
    "OUTCOME_ENGAGEMENT": "WEBSITE",
    "OUTCOME_AWARENESS": "WEBSITE",
    "TRAFFIC": "WEBSITE",
    "CONVERSIONS": "WEBSITE",
    "LEAD_GENERATION": "ON_AD",
    "AWARENESS": None,
    "REACH": None,
}


def _upload_image(account_id: str, image_url: str) -> str:
    """Upload image from URL and return its hash."""
    img_bytes = httpx.get(image_url, timeout=30.0).content
    name = image_url.split("/")[-1].split("?")[0] or "ad_image.jpg"
    mime = "image/png" if name.endswith(".png") else "image/jpeg"
    r = httpx.post(
        f"{GRAPH_BASE}/{account_id}/adimages",
        data={"access_token": META_TOKEN},
        files={"filename": (name, img_bytes, mime)},
        timeout=60.0,
    )
    result = r.json()
    if "error" in result:
        raise RuntimeError(f"Image upload error: {result['error'].get('message')}")
    images = result.get("images", {})
    if not images:
        raise RuntimeError("Image upload returned no data")
    image_data = next(iter(images.values()))
    return image_data["hash"]


def execute_plan(
    plan: dict,
    account_id: str,
    page_id: str,
    image_hashes: dict,  # {"0": "hash_for_ad_0", "1": "hash_for_ad_1", ...}
) -> dict:
    """
    Execute an approved plan. Returns IDs of created objects.
    All objects are created PAUSED.
    """
    log = []
    results = {"campaign_id": None, "adset_ids": [], "ad_ids": [], "log": log}

    campaign_spec = plan["campaign"]
    budget_cents = int(float(campaign_spec["daily_budget_usd"]) * 100)
    is_cbo = campaign_spec.get("budget_type", "CBO") == "CBO"

    # 1. Create Campaign
    campaign_payload = {
        "name": campaign_spec["name"],
        "objective": campaign_spec["objective"],
        "status": "PAUSED",
        "special_ad_categories": [],
    }
    if is_cbo:
        campaign_payload["daily_budget"] = budget_cents
        campaign_payload["bid_strategy"] = "LOWEST_COST_WITHOUT_CAP"

    camp = _post(f"/{account_id}/campaigns", campaign_payload)
    campaign_id = camp["id"]
    results["campaign_id"] = campaign_id
    log.append(f"✓ Campaign created: {campaign_spec['name']} ({campaign_id})")

    objective = campaign_spec["objective"]
    destination_type = OBJECTIVE_DESTINATION.get(objective, "WEBSITE")

    # 2. Create Ad Sets
    adset_ids = []
    for adset_spec in plan["adsets"]:
        adset_payload = {
            "name": adset_spec["name"],
            "campaign_id": campaign_id,
            "targeting": adset_spec["targeting"],
            "optimization_goal": adset_spec["optimization_goal"],
            "billing_event": "IMPRESSIONS",
            "bid_strategy": "LOWEST_COST_WITHOUT_CAP",
            "status": "PAUSED",
        }
        if destination_type:
            adset_payload["destination_type"] = destination_type

        # Meta now requires advantage_audience to be explicitly set
        adset_payload["targeting"]["targeting_automation"] = {"advantage_audience": 0}

        if not is_cbo and adset_spec.get("daily_budget_usd"):
            adset_payload["daily_budget"] = int(float(adset_spec["daily_budget_usd"]) * 100)
        elif not is_cbo:
            adset_payload["daily_budget"] = budget_cents

        adset = _post(f"/{account_id}/adsets", adset_payload)
        adset_id = adset["id"]
        adset_ids.append(adset_id)
        results["adset_ids"].append(adset_id)
        log.append(f"  ✓ Ad Set created: {adset_spec['name']} ({adset_id})")

    # 3. Create Ads
    for i, ad_spec in enumerate(plan["ads"]):
        adset_idx = ad_spec.get("adset_index", 0)
        adset_id = adset_ids[adset_idx] if adset_idx < len(adset_ids) else adset_ids[0]

        image_hash = image_hashes.get(str(i))
        if not image_hash:
            log.append(f"    — Skipped ad: {ad_spec['name']} (no image provided)")
            continue

        # Create ad creative
        creative_payload = {
            "name": ad_spec["name"] + " Creative",
            "object_story_spec": {
                "page_id": page_id,
                "link_data": {
                    "image_hash": image_hash,
                    "link": ad_spec["destination_url"],
                    "message": ad_spec["primary_text"],
                    "name": ad_spec["headline"],
                    "description": ad_spec.get("description", ""),
                    "call_to_action": {
                        "type": ad_spec["cta_type"],
                        "value": {"link": ad_spec["destination_url"]},
                    },
                },
            },
        }
        creative = _post(f"/{account_id}/adcreatives", creative_payload)
        creative_id = creative["id"]

        # Create ad
        ad_payload = {
            "name": ad_spec["name"],
            "adset_id": adset_id,
            "creative": {"creative_id": creative_id},
            "status": "PAUSED",
        }
        ad = _post(f"/{account_id}/ads", ad_payload)
        results["ad_ids"].append(ad["id"])
        log.append(f"    ✓ Ad created: {ad_spec['name']} ({ad['id']})")

    return results
