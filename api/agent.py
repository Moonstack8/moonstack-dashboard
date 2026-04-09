"""
Claude Agent for autonomous Meta Ads campaign planning.

The agent:
1. Receives a natural-language client brief
2. Uses research tools (search interests, geo lookup, audience estimation)
3. Generates 2-3 ad copy variations
4. Calls submit_plan with a complete, structured campaign JSON
5. Streams its entire reasoning process via SSE
"""
import json
import os
import httpx
import anthropic
from dotenv import load_dotenv

load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), '..', '.env'))

META_TOKEN = os.getenv("META_ACCESS_TOKEN", "")
ANTHROPIC_KEY = os.getenv("ANTHROPIC_API_KEY", "")
GRAPH_BASE = "https://graph.facebook.com/v21.0"

ai = anthropic.Anthropic(api_key=ANTHROPIC_KEY)


# ---------------------------------------------------------------------------
# Meta API helpers
# ---------------------------------------------------------------------------

def _meta_get(path: str, params: dict = None) -> dict:
    p = {"access_token": META_TOKEN, **(params or {})}
    r = httpx.get(f"{GRAPH_BASE}{path}", params=p, timeout=20.0)
    return r.json()


# ---------------------------------------------------------------------------
# Tool implementations (read-only, safe to call during planning)
# ---------------------------------------------------------------------------

def tool_search_interests(query: str, limit: int = 8) -> dict:
    data = _meta_get("/search", {"type": "adinterest", "q": query, "limit": limit})
    interests = [
        {
            "id": i["id"],
            "name": i["name"],
            "audience_size": i.get("audience_size_lower_bound", 0),
        }
        for i in data.get("data", [])
    ]
    return {"interests": interests}


def tool_search_geo(query: str, location_types: list = None) -> dict:
    params = {"type": "adgeolocation", "q": query, "limit": 10}
    if location_types:
        params["location_types"] = json.dumps(location_types)
    data = _meta_get("/search", params)
    locs = [
        {
            "key": l["key"],
            "name": l["name"],
            "type": l.get("type"),
            "country_code": l.get("country_code"),
        }
        for l in data.get("data", [])
    ]
    return {"locations": locs}


def tool_estimate_audience(account_id: str, targeting_spec: dict) -> dict:
    data = _meta_get(
        f"/{account_id}/reachestimate",
        {
            "targeting_spec": json.dumps(targeting_spec),
            "optimization_goal": "LINK_CLICKS",
        },
    )
    return {
        "users_lower_bound": data.get("users_lower_bound"),
        "users_upper_bound": data.get("users_upper_bound"),
        "estimate_ready": data.get("estimate_ready"),
    }


def tool_get_pages(account_id: str) -> dict:
    data = _meta_get(f"/{account_id}/assigned_pages", {"fields": "id,name"})
    # fallback: check /me/accounts
    pages = data.get("data", [])
    if not pages:
        data2 = _meta_get("/me/accounts", {"fields": "id,name,access_token"})
        pages = data2.get("data", [])
    return {"pages": [{"id": p["id"], "name": p["name"]} for p in pages]}


# ---------------------------------------------------------------------------
# Tool schemas for Claude
# ---------------------------------------------------------------------------

TOOLS = [
    {
        "name": "search_interests",
        "description": (
            "Search Facebook/Instagram interest targeting options. "
            "Use multiple searches to find the best interests for the audience."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Interest keyword to search"},
                "limit": {"type": "integer", "default": 8},
            },
            "required": ["query"],
        },
    },
    {
        "name": "search_geo",
        "description": "Search for geographic targeting locations (countries, regions, cities).",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Location name"},
                "location_types": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Optional filter: country, region, city, zip",
                },
            },
            "required": ["query"],
        },
    },
    {
        "name": "estimate_audience",
        "description": "Estimate audience size for a targeting spec. Use this to validate the audience isn't too narrow (<100K) or too broad (>50M).",
        "input_schema": {
            "type": "object",
            "properties": {
                "account_id": {"type": "string"},
                "targeting_spec": {
                    "type": "object",
                    "description": "Meta targeting spec with age_min, age_max, geo_locations, interests, etc.",
                },
            },
            "required": ["account_id", "targeting_spec"],
        },
    },
    {
        "name": "submit_plan",
        "description": (
            "Submit the complete campaign plan for human review. "
            "Call this once you have researched the audience and written ad copy. "
            "This ends the planning phase."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "rationale": {
                    "type": "string",
                    "description": "2-3 sentence explanation of the strategy and why these choices were made.",
                },
                "campaign": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string"},
                        "objective": {
                            "type": "string",
                            "enum": ["TRAFFIC", "AWARENESS", "OUTCOME_LEADS", "OUTCOME_SALES", "OUTCOME_ENGAGEMENT", "OUTCOME_TRAFFIC"],
                        },
                        "daily_budget_usd": {"type": "number"},
                        "budget_type": {"type": "string", "enum": ["CBO", "ABO"]},
                    },
                    "required": ["name", "objective", "daily_budget_usd", "budget_type"],
                },
                "adsets": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "name": {"type": "string"},
                            "targeting": {
                                "type": "object",
                                "description": "Full Meta targeting spec",
                            },
                            "optimization_goal": {
                                "type": "string",
                                "enum": ["LINK_CLICKS", "LANDING_PAGE_VIEWS", "IMPRESSIONS", "REACH", "LEAD_GENERATION", "OFFSITE_CONVERSIONS"],
                            },
                            "daily_budget_usd": {
                                "type": "number",
                                "description": "Only set for ABO campaigns",
                            },
                        },
                        "required": ["name", "targeting", "optimization_goal"],
                    },
                },
                "ads": {
                    "type": "array",
                    "description": "2-3 ad variations to A/B test",
                    "items": {
                        "type": "object",
                        "properties": {
                            "name": {"type": "string"},
                            "adset_index": {
                                "type": "integer",
                                "description": "Index of the parent adset (0-based)",
                            },
                            "headline": {"type": "string", "description": "Max 40 chars"},
                            "primary_text": {"type": "string", "description": "Max 125 chars for best results"},
                            "description": {"type": "string"},
                            "cta_type": {
                                "type": "string",
                                "enum": ["LEARN_MORE", "SIGN_UP", "GET_QUOTE", "SHOP_NOW", "BOOK_NOW", "CONTACT_US", "DOWNLOAD"],
                            },
                            "destination_url": {"type": "string"},
                        },
                        "required": ["name", "adset_index", "headline", "primary_text", "cta_type", "destination_url"],
                    },
                },
            },
            "required": ["rationale", "campaign", "adsets", "ads"],
        },
    },
]

SYSTEM_PROMPT = """\
You are an expert Meta Ads media buyer working for a performance marketing agency.

Given a client brief, build a complete, battle-tested campaign plan:

PROCESS:
1. Search for 3-5 relevant interest categories using search_interests
2. Confirm geo targeting keys using search_geo (always confirm country keys)
3. Build a targeting spec and estimate_audience — iterate if too narrow (<200K) or too broad (>30M)
4. Write 2-3 distinct ad variations with different hooks/angles
5. Call submit_plan with the full structured plan

NAMING CONVENTIONS:
- Campaign: [Objective] | [Client] | [Funnel] | [Budget Type]  (e.g. "Traffic | Acme | TOFU | CBO")
- Ad Set:   [Targeting] | [Age] | [Geo] | [Notes]              (e.g. "Interest-SaaS | 25-45 | US | Broad")
- Ad:       [Hook] | [Format] | [Version]                      (e.g. "Pain Point | IMG | V1")

TARGETING SPEC FORMAT:
{
  "age_min": 25, "age_max": 45,
  "genders": [1, 2],
  "geo_locations": {"countries": ["US"]},
  "interests": [{"id": "...", "name": "..."}],
  "publisher_platforms": ["facebook", "instagram"],
  "facebook_positions": ["feed", "story"],
  "instagram_positions": ["stream", "story"]
}

AD COPY GUIDELINES:
- Headlines: max 40 chars, hook-first, benefit-driven
- Primary text: max 125 chars, lead with pain point or desire, end with soft CTA
- Each variation should test a different angle (pain point, social proof, curiosity, benefit)

OBJECTIVES:
- OUTCOME_TRAFFIC: drive URL clicks (use optimization_goal: LINK_CLICKS or LANDING_PAGE_VIEWS)
- OUTCOME_LEADS: lead gen (LEAD_GENERATION)
- OUTCOME_SALES: purchases/ROAS (OFFSITE_CONVERSIONS)
- AWARENESS: reach/brand (IMPRESSIONS or REACH)

Always create PAUSED campaigns. Be specific and actionable. Do not ask for clarification — make your best professional judgment from the brief.
"""


# ---------------------------------------------------------------------------
# Streaming agent runner
# ---------------------------------------------------------------------------

def run_planning_agent(brief: str, account_id: str):
    """
    Generator that yields SSE-formatted strings as the agent plans.
    Events: text | tool_call | tool_result | plan | error | done
    """
    messages = [{"role": "user", "content": brief}]

    MAX_TURNS = 10
    for _ in range(MAX_TURNS):
        try:
            response = ai.messages.create(
                model="claude-sonnet-4-6",
                max_tokens=4096,
                system=SYSTEM_PROMPT,
                tools=TOOLS,
                messages=messages,
            )
        except Exception as e:
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"
            return

        # Emit text blocks
        for block in response.content:
            if block.type == "text" and block.text.strip():
                yield f"data: {json.dumps({'type': 'text', 'content': block.text})}\n\n"

        if response.stop_reason == "end_turn":
            break

        if response.stop_reason == "tool_use":
            messages.append({"role": "assistant", "content": response.content})
            tool_results = []

            for block in response.content:
                if block.type != "tool_use":
                    continue

                yield f"data: {json.dumps({'type': 'tool_call', 'tool': block.name, 'input': block.input})}\n\n"

                try:
                    if block.name == "search_interests":
                        result = tool_search_interests(**block.input)
                    elif block.name == "search_geo":
                        result = tool_search_geo(**block.input)
                    elif block.name == "estimate_audience":
                        result = tool_estimate_audience(**block.input)
                    elif block.name == "submit_plan":
                        yield f"data: {json.dumps({'type': 'plan', 'data': block.input})}\n\n"
                        yield f"data: {json.dumps({'type': 'done'})}\n\n"
                        return
                    else:
                        result = {"error": f"Unknown tool: {block.name}"}

                    yield f"data: {json.dumps({'type': 'tool_result', 'tool': block.name, 'result': result})}\n\n"
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": json.dumps(result),
                    })

                except Exception as e:
                    err = {"error": str(e)}
                    yield f"data: {json.dumps({'type': 'tool_result', 'tool': block.name, 'result': err})}\n\n"
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": json.dumps(err),
                    })

            messages.append({"role": "user", "content": tool_results})

    yield f"data: {json.dumps({'type': 'done'})}\n\n"
