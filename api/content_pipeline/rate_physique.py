import base64
import json
import os
import random
from pathlib import Path

from dotenv import load_dotenv
from moviepy import CompositeVideoClip, TextClip, VideoFileClip
from openai import OpenAI
from PIL import Image, ImageDraw, ImageFont

load_dotenv()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

_client = OpenAI(api_key=OPENAI_API_KEY)

# ── Template constants (1320×2868) ────────────────────────────────────────────

RATE_TEMPLATE = Path("/Users/ericcho/Desktop/cs/moonstack-dashboard/config/swolely_rate/swolely_template.png")

# Pixel coords [x, y] — anchor="mm" (center of each score number)
SCORE_POSITIONS = {
    "overall":     [554,  1442],
    "proportions": [1069, 1442],
    "chest":       [554,  1682],
    "arms":        [1069, 1682],
    "shoulders":   [554,  1922],
    "back":        [1069, 1922],
    "legs":        [554,  2162],
    "abs":         [1069, 2162],
}

# Photo slot expanded ~60% (centered on original, 10% more than previous)
PHOTO_BOX = (102, 265, 1224, 1163)

SCORE_FONT_SIZE = 160

# Green for high scores, amber for lower — matches the app palette
def _score_color(score: int) -> tuple:
    return (0, 214, 106) if score >= 90 else (255, 184, 0)

# ── Fallback defaults ─────────────────────────────────────────────────────────

DEFAULT_RANGES = {
    "overall":     (51, 83),
    "proportions": (51, 83),
    "chest":       (51, 83),
    "arms":        (51, 83),
    "shoulders":   (51, 83),
    "back":        (51, 83),
    "legs":        (51, 83),
    "abs":         (51, 83),
}

def _rand(lo: int, hi: int) -> int:
    return round(lo + random.random() * (hi - lo))

def _default_rating(lo: int, hi: int) -> dict:
    return {"score": _rand(lo, hi), "confidence": 0.5, "reasoning": ""}

def _default_metrics() -> dict:
    return {k: _default_rating(*r) for k, r in DEFAULT_RANGES.items()}

def _clamp(n) -> int:
    return max(0, min(100, round(n)))

# ── OpenAI schema (mirrors TS responseSchema) ─────────────────────────────────

_RESPONSE_SCHEMA = {
    "type": "json_schema",
    "json_schema": {
        "name": "physique_metrics",
        "strict": True,
        "schema": {
            "type": "object",
            "properties": {k: {"$ref": "#/$defs/Rating"} for k in DEFAULT_RANGES},
            "required": list(DEFAULT_RANGES.keys()),
            "additionalProperties": False,
            "$defs": {
                "Rating": {
                    "type": "object",
                    "properties": {
                        "score":      {"type": "number", "description": "0-100"},
                        "confidence": {"type": "number", "description": "0-1"},
                        "reasoning":  {"type": "string"},
                    },
                    "required": ["score", "confidence", "reasoning"],
                    "additionalProperties": False,
                }
            },
        },
    },
}

# ── Core functions ─────────────────────────────────────────────────────────────

def extract_last_frame(clip_path: Path, output_path: Path) -> Path:
    """Save the last frame of a video as a PNG."""
    clip = VideoFileClip(str(clip_path))
    output_path.parent.mkdir(parents=True, exist_ok=True)
    clip.save_frame(str(output_path), t=clip.duration - 0.1)
    clip.close()
    print(f"Last frame saved: {output_path}")
    return output_path


def rate_physique(frame_path: Path) -> dict:
    """Send the frame to GPT-4o and return a metrics dict matching ScanMetrics."""
    try:
        with open(frame_path, "rb") as f:
            b64 = base64.b64encode(f.read()).decode()

        suffix = frame_path.suffix.lower()
        mime = "image/png" if suffix == ".png" else "image/webp" if suffix == ".webp" else "image/jpeg"

        response = _client.chat.completions.create(
            model="gpt-4o",
            response_format=_RESPONSE_SCHEMA,
            messages=[
                {
                    "role": "system",
                    "content": "You are a professional physique evaluator. Rate each category from 0-100. Confidence is 0-1.",
                },
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": "Evaluate this physique."},
                        {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{b64}", "detail": "high"}},
                    ],
                },
            ],
            max_tokens=512,
        )

        data = json.loads(response.choices[0].message.content)

        metrics = {}
        for key in DEFAULT_RANGES:
            raw = data.get(key, {})
            metrics[key] = {
                "score":      _clamp(raw.get("score", 0)),
                "confidence": raw.get("confidence", 0.8),
                "reasoning":  raw.get("reasoning", ""),
            }

        # Replace zero scores with fallback range
        for key, (lo, hi) in DEFAULT_RANGES.items():
            if metrics[key]["score"] == 0:
                metrics[key] = _default_rating(lo, hi)

        print(f"Ratings: { {k: v['score'] for k, v in metrics.items()} }")
        return metrics

    except Exception as err:
        print(f"rate_physique error: {err} — using defaults")
        return _default_metrics()


def composite_scores(frame_path: Path, scores: dict, output_path: Path) -> Path:
    """Paste last frame into the photo slot and draw scores onto the template."""
    img = Image.open(RATE_TEMPLATE).convert("RGBA")

    # Replace photo slot — scale to fill width (preserve ratio), center-crop height
    l, t, r, b = PHOTO_BOX
    slot_w, slot_h = r - l, b - t
    frame = Image.open(frame_path).convert("RGBA")
    fw, fh = frame.size
    scale = slot_w / fw
    new_w, new_h = slot_w, int(fh * scale)
    frame = frame.resize((new_w, new_h), Image.LANCZOS)
    crop_y = max((new_h - slot_h) // 2, 0)
    frame = frame.crop((0, crop_y, slot_w, crop_y + slot_h))
    img.paste(frame, (l, t))

    draw = ImageDraw.Draw(img)

    font = None
    for _p in ["/System/Library/Fonts/SF Pro/SF-Pro-Display-Black.otf",
               "/System/Library/Fonts/Helvetica.ttc"]:
        try:
            font = ImageFont.truetype(_p, SCORE_FONT_SIZE)
            break
        except OSError:
            continue
    if font is None:
        font = ImageFont.load_default()

    for key, (x, y) in SCORE_POSITIONS.items():
        rating = scores.get(key)
        if rating is None:
            continue
        score = rating["score"] if isinstance(rating, dict) else rating
        draw.text((x, y), str(score), font=font, fill=_score_color(score), anchor="mm")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    img.save(str(output_path))
    print(f"Scorecard saved: {output_path}")
    return output_path


def add_caption(clip_path: Path, output_path: Path, text: str = "rate my physique") -> Path:
    """Burn a caption onto the top of a video clip."""
    clip = VideoFileClip(str(clip_path))
    _, h = clip.size

    _caption_font = next(
        (p for p in [
            "/System/Library/Fonts/SF Pro/SF-Pro-Display-Black.otf",
            "/System/Library/Fonts/Helvetica.ttc",
        ] if Path(p).exists()),
        None,
    )

    caption = (
        TextClip(
            text=text,
            font_size=int(h * 0.07),
            color="white",
            stroke_color="black",
            stroke_width=8,
            **({"font": _caption_font} if _caption_font else {}),
        )
        .with_duration(clip.duration)
        .with_position(("center", "center"))
    )

    final = CompositeVideoClip([clip, caption])
    output_path.parent.mkdir(parents=True, exist_ok=True)
    final.write_videofile(
        str(output_path),
        codec="libx264",
        audio_codec="aac",
        fps=clip.fps or 30,
        temp_audiofile=str(output_path.parent / "temp_caption_audio.m4a"),
        remove_temp=True,
        logger=None,
    )
    clip.close()
    final.close()
    return output_path
