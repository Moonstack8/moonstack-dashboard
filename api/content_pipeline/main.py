import argparse
import json
from datetime import datetime
from pathlib import Path

import yaml
from upload_instagram import upload_reel
from upload_youtube import get_youtube_client, next_publish_time, upload

from generate_clips import (
    CLIP_CACHE,
    OUTPUT_DIR,
    ROOT,
    collect_approved_clips,
    splice_clips,
    splice_rate_physique,
)
from rate_physique import add_caption, composite_scores, extract_last_frame, rate_physique


def main():
    parser = argparse.ArgumentParser(
        description="Create viral clips, and automatically upload it"
    )
    parser.add_argument("--config-dir", type=Path, default=ROOT / "config/swolely",
                        help="Path to config directory")
    args = parser.parse_args()

    config_dir = args.config_dir
    config     = yaml.safe_load((config_dir / "upload_config.yaml").read_text())

    pipeline        = config.get("pipeline").strip().lower()
    upload_target   = config.get("upload_target").strip().lower()
    query           = config.get("query").strip() or None
    seconds         = float(config.get("seconds"))
    title           = config["title"]
    description     = config["description"].strip()
    template_video  = config_dir / "Swolely Template.mp4"

    CLIP_CACHE.mkdir(parents=True, exist_ok=True)
    youtube = None
    ig_user_id = ig_access_token = None

    if upload_target == "youtube":
        youtube = get_youtube_client(
            secrets_file=config_dir / "client_secret.json",
            token_file=config_dir / "youtube_token.json",
        )
    elif upload_target == "instagram":
        creds = json.loads((config_dir / "instagram_credentials.json").read_text())
        ig_user_id     = creds["user_id"]
        ig_access_token = creds["access_token"]

    approved = collect_approved_clips(query)
    print(f"\n{len(approved)} clip(s) approved. Running '{pipeline}' pipeline ...\n")

    for i, cached in enumerate(approved, 1):
        print(f"── Clip {i}/{len(approved)} ──────────────────────────────")
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        run_dir   = OUTPUT_DIR / timestamp
        run_dir.mkdir(parents=True, exist_ok=True)

        output_path = run_dir / "video.mp4"

        if pipeline == "rate my physique":
            frame_path = run_dir / "frame.png"
            extract_last_frame(cached, frame_path)

            scores = rate_physique(frame_path)

            scorecard_path = run_dir / "scorecard.png"
            composite_scores(frame_path, scores, scorecard_path)

            captioned_path = run_dir / "captioned.mp4"
            add_caption(cached, captioned_path)

            splice_rate_physique(captioned_path, scorecard_path, output_path, template_video, total_secs=seconds)

        elif pipeline == "fitness girls":
            splice_clips(cached, seconds, output_path, template_video)

        else:
            raise ValueError(f"Unknown pipeline '{pipeline}'. Set 'pipeline' in upload_config.yaml to 'rate my physique' or 'fitness girls'.")

        if upload_target == "youtube":
            publish_at = next_publish_time(youtube)
            upload(output_path, title, description, publish_at, youtube)
        elif upload_target == "instagram":
            upload_reel(output_path, description, ig_user_id, ig_access_token)
        else:
            raise ValueError(f"Unknown upload_target '{upload_target}'. Use 'youtube' or 'instagram'.")
        print(f"Saved to: {output_path}")


if __name__ == "__main__":
    main()
