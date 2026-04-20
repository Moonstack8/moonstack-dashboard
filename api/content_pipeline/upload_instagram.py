import time
from pathlib import Path

import requests
from moviepy import VideoFileClip

GRAPH_BASE   = "https://graph.facebook.com/v25.0"
RUPLOAD_BASE = "https://rupload.facebook.com/ig-api-upload/v25.0"


def _params(access_token: str, **extra) -> dict:
    return {"access_token": access_token, **extra}


# ── Re-encode ─────────────────────────────────────────────────────────────────

IG_W, IG_H = 1080, 1920


def _reencode(video_path: Path) -> Path:
    out = video_path.with_stem(video_path.stem + "_ig").with_suffix(".mp4")
    clip = VideoFileClip(str(video_path))

    duration = clip.duration
    if duration < 3:
        raise ValueError(f"Video too short ({duration:.1f}s) — minimum is 3s")
    if duration > 900:
        raise ValueError(f"Video too long ({duration:.1f}s) — maximum is 900s")

    cw, ch = clip.size
    scale = max(IG_W / cw, IG_H / ch)
    new_w = int(cw * scale) & ~1
    new_h = int(ch * scale) & ~1
    scaled = clip.resized((new_w, new_h))
    x1 = (new_w - IG_W) // 2
    y1 = (new_h - IG_H) // 2
    final = scaled.cropped(x1=x1, y1=y1, x2=x1 + IG_W, y2=y1 + IG_H)

    final.write_videofile(
        str(out),
        codec="libx264",
        audio_codec="aac",
        audio=clip.audio is not None,
        fps=30,
        ffmpeg_params=[
            "-profile:v", "main",
            "-level", "4.0",
            "-pix_fmt", "yuv420p",
            "-b:a", "128k",
            "-ar", "44100",
            "-movflags", "+faststart",
            "-g", "30",
            "-keyint_min", "30",
            "-sc_threshold", "0",
            "-bf", "0",
            "-maxrate", "3500k",
            "-bufsize", "7000k",
            "-b:v", "2500k",
        ],
        temp_audiofile=str(out.parent / "temp_ig_audio.m4a"),
        remove_temp=True,
        logger=None,
    )
    clip.close()
    scaled.close()
    final.close()
    return out


# ── Upload ────────────────────────────────────────────────────────────────────

def _create_upload_session(ig_user_id: str, access_token: str, caption: str) -> tuple[str, str]:
    """Step 1: create resumable upload session. Returns (container_id, upload_uri)."""
    resp = requests.post(
        f"{GRAPH_BASE}/{ig_user_id}/media",
        data=_params(
            access_token,
            media_type="REELS",
            upload_type="resumable",
            caption=caption,
        ),
    )
    if not resp.ok:
        raise requests.HTTPError(f"{resp.status_code} — {resp.text}", response=resp)
    data = resp.json()
    return data["id"], data["uri"]


def _upload_bytes(container_id: str, access_token: str, video_path: Path) -> None:
    """Step 2: stream video bytes to the resumable upload endpoint."""
    file_size = video_path.stat().st_size
    with open(video_path, "rb") as f:
        resp = requests.post(
            f"{RUPLOAD_BASE}/{container_id}",
            headers={
                "Authorization": f"OAuth {access_token}",
                "offset": "0",
                "file_size": str(file_size),
                "Content-Type": "application/octet-stream",
            },
            data=f,
        )
    if not resp.ok:
        raise requests.HTTPError(f"{resp.status_code} — {resp.text}", response=resp)
    if not resp.json().get("success"):
        raise RuntimeError(f"Upload did not succeed: {resp.text}")


def _wait_until_ready(container_id: str, access_token: str, timeout: int = 300) -> None:
    """Poll container status until FINISHED."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        resp = requests.get(
            f"{GRAPH_BASE}/{container_id}",
            params=_params(access_token, fields="status_code,status"),
        )
        resp.raise_for_status()
        data = resp.json()
        status = data.get("status_code")
        print(f"  Container status: {status}")
        if status == "FINISHED":
            return
        if status == "ERROR":
            raise RuntimeError(f"Instagram container failed: {data}")
        time.sleep(10)
    raise TimeoutError(f"Container {container_id} not ready after {timeout}s")


def _publish(ig_user_id: str, access_token: str, container_id: str) -> str:
    """Step 3: publish the container. Returns the published media ID."""
    resp = requests.post(
        f"{GRAPH_BASE}/{ig_user_id}/media_publish",
        data=_params(access_token, creation_id=container_id),
    )
    if not resp.ok:
        raise requests.HTTPError(f"{resp.status_code} — {resp.text}", response=resp)
    return resp.json()["id"]


# ── Public entry point ────────────────────────────────────────────────────────

def upload_reel(video_path: Path, caption: str, ig_user_id: str, access_token: str) -> str:
    """Re-encode, upload, and publish a Reel. Returns the published media ID."""
    print("Re-encoding for Instagram ...")
    ig_path = _reencode(video_path)

    print("Creating upload session ...")
    container_id, _ = _create_upload_session(ig_user_id, access_token, caption)

    print(f"Uploading {ig_path.name} ({ig_path.stat().st_size / 1e6:.1f} MB) ...")
    _upload_bytes(container_id, access_token, ig_path)

    print("Waiting for Instagram to process ...")
    _wait_until_ready(container_id, access_token)

    media_id = _publish(ig_user_id, access_token, container_id)
    print(f"Published! Media ID: {media_id}")
    return media_id
