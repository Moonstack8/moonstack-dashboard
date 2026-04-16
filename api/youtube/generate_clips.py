import argparse
import os
import random
import subprocess
import sys
from datetime import datetime
from pathlib import Path

import PIL.Image
import requests
from dotenv import load_dotenv
from moviepy import VideoFileClip, concatenate_videoclips

import yaml
from upload_youtube import get_youtube_client, next_publish_time, upload

load_dotenv()

if not hasattr(PIL.Image, "ANTIALIAS"):
    PIL.Image.ANTIALIAS = PIL.Image.LANCZOS  # removed in Pillow 10+

# ── Config ────────────────────────────────────────────────────────────────────
ROOT           = Path(__file__).resolve().parent.parent.parent
OUTPUT_DIR     = ROOT / "output_dir"
CLIP_CACHE     = ROOT / ".clip_cache"
DOWNLOAD_CHUNK = 64 * 1024  # bytes per streaming chunk

def fetch_pexels(query: str, api_key: str) -> str:
    """Return a download URL from Pexels Videos. Skips the top result to stay niche."""
    resp = requests.get(
        "https://api.pexels.com/videos/search",
        headers={"Authorization": api_key},
        params={"query": query, "per_page": 15, "orientation": "portrait"},
    )
    resp.raise_for_status()
    videos = resp.json().get("videos", [])

    if not videos:
        raise RuntimeError(f"Pexels: no results for '{query}'")

    pool = videos[1:] if len(videos) > 1 else videos
    chosen = random.choice(pool)

    files = sorted(chosen["video_files"], key=lambda f: f.get("width", 0), reverse=True)
    download_url = files[0]["link"]

    print(f"Pexels: '{chosen.get('url', '')}' ({files[0].get('width')}x{files[0].get('height')})")
    return download_url

# ── Download ──────────────────────────────────────────────────────────────────

def download_video(url: str, dest: Path) -> Path:
    """Stream-download a video URL to dest."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    print(f"Downloading → {dest.name} ...")

    with requests.get(url, stream=True) as r:
        r.raise_for_status()
        with open(dest, "wb") as f:
            for chunk in r.iter_content(chunk_size=DOWNLOAD_CHUNK):
                f.write(chunk)

    print(f"Downloaded: {dest.stat().st_size / 1_000_000:.1f} MB")
    return dest


# ── Splice ────────────────────────────────────────────────────────────────────

def splice_clips(scraped_path: Path, cut_secs: float, output_path: Path, template_video: Path):
    """Prepend cut_secs of the scraped clip to the template, replacing the template's opening."""
    if not template_video.exists():
        raise FileNotFoundError(f"Template not found: {template_video}")

    print("\nLoading template ...")
    template = VideoFileClip(str(template_video))
    tw, th = template.size
    fps = template.fps or 30
    print(f"  Template: {tw}x{th} @ {fps:.2f} fps, {template.duration:.2f}s")

    print("Loading scraped clip ...")
    scraped = VideoFileClip(str(scraped_path))
    print(f"  Scraped:  {scraped.size[0]}x{scraped.size[1]} @ {scraped.fps:.2f} fps, {scraped.duration:.2f}s")
    
    intro = scraped.subclipped(0, min(cut_secs, scraped.duration))
    intro = intro.resized((tw, th)).with_fps(fps)

    tail = template.subclipped(min(cut_secs, template.duration))

    print(f"\nSplicing: {intro.duration:.2f}s stock intro + {tail.duration:.2f}s template tail")
    final = concatenate_videoclips([intro, tail], method="compose")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    print(f"Writing → {output_path}")
    final.write_videofile(
        str(output_path),
        codec="libx264",
        audio_codec="aac",
        fps=fps,
        temp_audiofile=str(output_path.parent / "temp_audio.m4a"),
        remove_temp=True,
        logger=None,
    )

    scraped.close()
    template.close()
    final.close()


# ── Clip approval ─────────────────────────────────────────────────────────────

def pick_one_clip(query: str, pexels_key: str) -> Path:
    """Fetch and preview Pexels clips until the user approves one."""
    while True:
        download_url = fetch_pexels(query, pexels_key)
        filename     = f"{abs(hash(download_url))}.mp4"
        candidate    = CLIP_CACHE / filename

        if not candidate.exists():
            download_video(download_url, candidate)
        else:
            print(f"Cache hit: {candidate.name}")

        subprocess.run(["open", str(candidate)], check=False)
        answer = input("\nKeep this clip? [y/n]: ").strip().lower()

        if answer == "y":
            return candidate

        candidate.unlink(missing_ok=True)
        print("Rejected — fetching another clip ...\n")


def collect_approved_clips(query: str, pexels_key: str) -> list:
    """Keep approving clips until the user is done."""
    approved = []
    while True:
        clip = pick_one_clip(query, pexels_key)
        approved.append(clip)
        print(f"{len(approved)} clip(s) approved.")
        if input("Approve another clip? [y/n]: ").strip().lower() != "y":
            return approved


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Splice a copyright-free stock clip into Swolely Template"
    )
    parser.add_argument("--config-dir", type=Path, default=ROOT / "config/swolely",
                        help="Path to config directory (must contain upload_config.yaml and template)")
    args = parser.parse_args()

    config_dir = args.config_dir
    config     = yaml.safe_load((config_dir / "upload_config.yaml").read_text())

    query          = config.get("query", "").strip() or None
    seconds        = float(config.get("seconds", 3.82))
    title          = config["title"]
    description    = config["description"].strip()
    template_video = config_dir / "Swolely Template.mp4"

    pexels_key = os.getenv("PEXELS_API_KEY")
    if not pexels_key:
        sys.exit(
            "ERROR: PEXELS_API_KEY not set.\n"
            "Get a free key at https://www.pexels.com/api/ and add it to .env"
        )

    CLIP_CACHE.mkdir(parents=True, exist_ok=True)
    youtube = get_youtube_client(
        secrets_file=config_dir / "client_secrets.json",
        token_file=config_dir / "youtube_token.json",
    )

    approved = collect_approved_clips(query, pexels_key)
    print(f"\n{len(approved)} clip(s) approved. Splicing and uploading ...\n")

    for i, cached in enumerate(approved, 1):
        print(f"── Clip {i}/{len(approved)} ──────────────────────────────")
        timestamp   = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_path = OUTPUT_DIR / f"video_{timestamp}.mp4"
        splice_clips(cached, seconds, output_path, template_video)
        publish_at = next_publish_time(youtube)
        upload(output_path, title, description, publish_at, youtube)
        print(f"Saved to: {output_path}")


if __name__ == "__main__":
    main()