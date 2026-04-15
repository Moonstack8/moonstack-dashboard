"""
Ad Optimizer Agent.
Fetches an existing ad's creative + performance data, then uses Claude
to analyze weaknesses and generate 2-3 improved copy variations.
"""
import json
import os
import httpx
import anthropic
from dotenv import load_dotenv

load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), '..', '.env'))

ANTHROPIC_KEY = os.getenv("ANTHROPIC_API_KEY", "")
GRAPH_BASE = "https://graph.facebook.com/v21.0"

ai = anthropic.Anthropic(api_key=ANTHROPIC_KEY)

INSIGHT_FIELDS = "spend,impressions,reach,clicks,ctr,cpc,cpm,frequency,actions,action_values"

SUBMIT_VARIATIONS_TOOL = {
    "name": "submit_variations",
    "description": "Submit the optimized ad copy variations after your analysis.",
    "input_schema": {
        "type": "object",
        "properties": {
            "variations": {
                "type": "array",
                "description": "2-3 improved ad variations",
                "items": {
                    "type": "object",
                    "properties": {
                        "angle": {
                            "type": "string",
                            "description": "The hook/angle this variation tests (e.g. 'Pain Point', 'Social Proof', 'Curiosity', 'Benefit-Led', 'Urgency')",
                        },
                        "headline": {
                            "type": "string",
                            "description": "Max 40 characters",
                        },
                        "primary_text": {
                            "type": "string",
                            "description": "Max 125 characters for best results",
                        },
                        "description": {"type": "string"},
                        "cta_type": {
                            "type": "string",
                            "enum": ["LEARN_MORE", "SIGN_UP", "GET_QUOTE", "SHOP_NOW", "BOOK_NOW", "CONTACT_US", "DOWNLOAD"],
                        },
                        "reasoning": {
                            "type": "string",
                            "description": "One sentence on why this variation should outperform the original.",
                        },
                        "suggested_prompt": {
                            "type": "string",
                            "description": (
                                "A ready-to-use campaign brief (2-4 sentences) that a media buyer could paste "
                                "into a campaign builder to create this ad. Include the angle, target audience, "
                                "key message, and any creative direction. Write it as a natural-language brief, "
                                "not as a list of fields."
                            ),
                        },
                    },
                    "required": ["angle", "headline", "primary_text", "cta_type", "reasoning", "suggested_prompt"],
                },
            }
        },
        "required": ["variations"],
    },
}

SYSTEM_PROMPT = """\
You are an expert Meta Ads copywriter, creative strategist, and performance analyst.

When an image is provided, analyze it critically:
- Is it scroll-stopping or generic stock-photo energy?
- Does the visual tell a story or create emotion on its own?
- Is there a mismatch between the image tone and the copy tone?
- Does the image reinforce the headline, or do they fight each other?
- What does the image communicate before the user reads a word?

Analyze performance data critically:
- CTR < 0.5% = hook is not landing — rewrite the headline and opening line
- CTR 0.5–1% = mediocre — test a sharper angle
- CPC > $3 = weak click intent or wrong audience signal in copy
- Frequency > 3 = audience fatigue — fresh angle and new hook needed
- Low spend with 0 conversions = copy never built enough trust

Generate 3 variations each testing a distinct angle (pain point, social proof, curiosity, benefit-led, urgency).
For each variation, write copy that plays to what the image actually shows — use the visual as your context.
Be specific and punchy — write like a human, not a marketer.
After your analysis, call submit_variations with the 3 improved variations.\
"""


def run_optimizer_agent(ad_id: str, account_id: str, token: str):
    """Generator that yields SSE-formatted strings."""

    # 1. Fetch ad details
    try:
        ad_resp = httpx.get(
            f"{GRAPH_BASE}/{ad_id}",
            params={
                "fields": "id,name,creative{id,name,object_story_spec,thumbnail_url}",
                "access_token": token,
            },
            timeout=20.0,
        ).json()

        if "error" in ad_resp:
            yield f"data: {json.dumps({'type': 'error', 'message': ad_resp['error'].get('message', 'Failed to fetch ad')})}\n\n"
            return

        # 2. Fetch insights (last 30 days)
        insights_resp = httpx.get(
            f"{GRAPH_BASE}/{ad_id}/insights",
            params={
                "fields": INSIGHT_FIELDS,
                "date_preset": "last_30d",
                "access_token": token,
            },
            timeout=20.0,
        ).json()

        insights = insights_resp.get("data", [{}])[0] if insights_resp.get("data") else {}

        # 3. Fetch ad image (thumbnail) for visual analysis
        thumbnail_url = ad_resp.get("creative", {}).get("thumbnail_url")
        image_b64 = None
        image_mime = "image/jpeg"
        if thumbnail_url:
            try:
                img_resp = httpx.get(thumbnail_url, timeout=20.0, follow_redirects=True)
                if img_resp.status_code == 200:
                    import base64
                    content_type = img_resp.headers.get("content-type", "image/jpeg").split(";")[0].strip()
                    image_mime = content_type if content_type.startswith("image/") else "image/jpeg"
                    image_b64 = base64.standard_b64encode(img_resp.content).decode("utf-8")
            except Exception:
                pass  # Image is optional — proceed without it

    except Exception as e:
        yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"
        return

    # 3. Extract creative copy
    creative = ad_resp.get("creative", {})
    story_spec = creative.get("object_story_spec", {})
    link_data = story_spec.get("link_data", {})

    headline = link_data.get("name", "")
    primary_text = link_data.get("message", "")
    description = link_data.get("description", "")
    cta = link_data.get("call_to_action", {}).get("type", "LEARN_MORE")
    destination_url = link_data.get("link", "")

    # 4. Extract metrics
    spend = float(insights.get("spend") or 0)
    impressions = int(insights.get("impressions") or 0)
    clicks = int(insights.get("clicks") or 0)
    ctr = float(insights.get("ctr") or 0)
    cpc = float(insights.get("cpc") or 0)
    cpm = float(insights.get("cpm") or 0)
    frequency = float(insights.get("frequency") or 0)

    actions = insights.get("actions", [])
    conversions = sum(
        int(a.get("value", 0))
        for a in actions
        if "purchase" in a.get("action_type", "") or "lead" in a.get("action_type", "")
    )

    no_data = spend == 0 and impressions == 0
    perf_section = (
        "No performance data yet (ad hasn't spent). Optimize based on copy quality alone."
        if no_data
        else f"""- Spend: ${spend:.2f}
- Impressions: {impressions:,}
- Clicks: {clicks:,}
- CTR: {ctr:.2f}%
- CPC: ${cpc:.2f}
- CPM: ${cpm:.2f}
- Frequency: {frequency:.2f}
- Conversions: {conversions}"""
    )

    image_note = "The ad creative image is attached above." if image_b64 else "No image available."
    prompt = f"""Analyze this Meta ad and generate 3 improved variations.

{image_note}

CURRENT AD COPY:
- Name: {ad_resp.get('name', 'Unknown')}
- Headline: {headline or '(none)'}
- Primary Text: {primary_text or '(none)'}
- Description: {description or '(none)'}
- CTA: {cta}
- Destination URL: {destination_url or '(none)'}

PERFORMANCE (last 30 days):
{perf_section}

Analyze both the visual and the copy — does the image match the message? Is it scroll-stopping? Does the headline complement or compete with the visual? Then generate 3 variations, each testing a different angle. Keep the same destination URL unless there's a clear reason to change it."""

    # Build multimodal message content
    if image_b64:
        user_content = [
            {
                "type": "image",
                "source": {
                    "type": "base64",
                    "media_type": image_mime,
                    "data": image_b64,
                },
            },
            {"type": "text", "text": prompt},
        ]
    else:
        user_content = prompt

    # 5. Call Claude
    try:
        response = ai.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=2048,
            system=SYSTEM_PROMPT,
            tools=[SUBMIT_VARIATIONS_TOOL],
            messages=[{"role": "user", "content": user_content}],
        )
    except Exception as e:
        yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"
        return

    # Emit analysis text
    for block in response.content:
        if block.type == "text" and block.text.strip():
            yield f"data: {json.dumps({'type': 'text', 'content': block.text})}\n\n"

    # Emit variations
    for block in response.content:
        if block.type == "tool_use" and block.name == "submit_variations":
            yield f"data: {json.dumps({'type': 'variations', 'data': block.input})}\n\n"
            break

    yield f"data: {json.dumps({'type': 'done'})}\n\n"
