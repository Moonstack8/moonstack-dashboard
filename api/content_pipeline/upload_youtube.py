from datetime import datetime, timedelta, timezone
from typing import Optional
from pathlib import Path

from dotenv import load_dotenv
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

load_dotenv()

SCOPES = ["https://www.googleapis.com/auth/youtube"]

# ── Auth ──────────────────────────────────────────────────────────────────────

def get_youtube_client(secrets_file: Path, token_file: Path):
    creds = None
    if token_file.exists():
        creds = Credentials.from_authorized_user_file(str(token_file), SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(str(secrets_file), SCOPES)
            creds = flow.run_local_server(port=8080)
        token_file.write_text(creds.to_json())

    return build("youtube", "v3", credentials=creds)


# ── Scheduling ────────────────────────────────────────────────────────────────

def _latest_video_time(youtube) -> Optional[datetime]:
    """Return the latest publish time across both live and scheduled videos."""
    # Get the channel's uploads playlist (includes private/scheduled)
    ch_resp = youtube.channels().list(mine=True, part="contentDetails").execute()
    items   = ch_resp.get("items", [])
    if not items:
        return None

    uploads_playlist = items[0]["contentDetails"]["relatedPlaylists"]["uploads"]

    # Grab the 10 most recent items (enough to catch queued scheduled videos)
    pl_resp  = youtube.playlistItems().list(
        playlistId=uploads_playlist,
        part="contentDetails",
        maxResults=10,
    ).execute()
    video_ids = [i["contentDetails"]["videoId"] for i in pl_resp.get("items", [])]
    if not video_ids:
        return None

    # Fetch status for each video to get publishAt for scheduled ones
    v_resp = youtube.videos().list(
        id=",".join(video_ids),
        part="status,snippet",
    ).execute()

    latest = None
    for v in v_resp.get("items", []):
        status = v.get("status", {})
        # Scheduled videos have publishAt; published videos use snippet.publishedAt
        raw = status.get("publishAt") or v["snippet"].get("publishedAt")
        if not raw:
            continue
        dt = datetime.strptime(raw, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
        if latest is None or dt > latest:
            latest = dt

    return latest


def next_publish_time(youtube) -> datetime:
    """Return the next 24-h slot after the latest published or scheduled video."""
    last = _latest_video_time(youtube)
    now  = datetime.now(timezone.utc)

    if last is None or (now - last).total_seconds() > 86400:
        return now + timedelta(hours=24)

    return last + timedelta(hours=24)


# ── Upload ────────────────────────────────────────────────────────────────────

def upload(video_path: Path, title: str, description: str, publish_at: datetime, youtube) -> str:
    """Upload video as a scheduled private video and return its video ID."""
    if publish_at.tzinfo is None:
        publish_at = publish_at.replace(tzinfo=timezone.utc)
    publish_at_str = publish_at.strftime("%Y-%m-%dT%H:%M:%SZ")

    body = {
        "snippet": {
            "title": title,
            "description": description,
            "categoryId": "17",  # Sports
        },
        "status": {
            "privacyStatus": "private",
            "publishAt": publish_at_str,
            "selfDeclaredMadeForKids": False,
        },
    }

    media   = MediaFileUpload(str(video_path), mimetype="video/mp4", resumable=True)
    request = youtube.videos().insert(part="snippet,status", body=body, media_body=media)

    print(f"Uploading to YouTube (scheduled: {publish_at_str}) ...")
    response = None
    while response is None:
        status, response = request.next_chunk()
        if status:
            print(f"  {int(status.progress() * 100)}%")

    video_id = response["id"]
    print(f"Scheduled! https://www.youtube.com/watch?v={video_id}")
    return video_id
