import argparse
from datetime import datetime
from pathlib import Path

import yaml
from upload_youtube import get_youtube_client, next_publish_time, upload

from generate_clips import (
    CLIP_CACHE,
    OUTPUT_DIR,
    ROOT,
    collect_approved_clips,
    splice_clips,
)


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

    CLIP_CACHE.mkdir(parents=True, exist_ok=True)
    youtube = get_youtube_client(
        secrets_file=config_dir / "client_secrets.json",
        token_file=config_dir / "youtube_token.json",
    )

    approved = collect_approved_clips(query)
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
