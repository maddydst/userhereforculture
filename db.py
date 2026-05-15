import os
from pathlib import Path
from supabase import create_client, Client

_client: Client | None = None
_service_client: Client | None = None

STORAGE_URL = "https://omnczbjvrvphqgzeswim.supabase.co/storage/v1/object/public/images/"


def get_client() -> Client:
    global _client
    if _client is None:
        _client = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_KEY"])
    return _client


def get_service_client() -> Client:
    global _service_client
    if _service_client is None:
        key = os.environ.get("SUPABASE_SERVICE_KEY", os.environ["SUPABASE_KEY"])
        _service_client = create_client(os.environ["SUPABASE_URL"], key)
    return _service_client


def image_url(filename: str | None) -> str | None:
    if not filename:
        return None
    return STORAGE_URL + filename


def fetch_articles(category: str | None = None) -> list[dict]:
    sb = get_client()
    q = sb.table("newsletters").select("*").order("date", desc=True).order("score", desc=True)
    if category and category != "all":
        q = q.eq("categorie", category)
    articles = q.execute().data
    for a in articles:
        a["image_url"] = image_url(a.get("image"))
    return articles


def seen_ids() -> set[str]:
    sb = get_client()
    rows = sb.table("newsletters").select("gmail_id").execute().data
    return {r["gmail_id"] for r in rows}


def insert_article(entry: dict):
    sb = get_client()
    sb.table("newsletters").upsert({
        "gmail_id":     entry["_id"],
        "titre":        entry["titre"],
        "categorie":    entry["categorie"],
        "resume":       entry["resume"],
        "score":        int(entry["score"]),
        "score_raison": entry.get("score_raison", ""),
        "image_prompt": entry.get("image_prompt", ""),
        "image":        entry.get("image"),
        "date":         entry.get("date"),
        "source":       entry.get("source", ""),
        "tags":         entry.get("tags", []),
    }, on_conflict="gmail_id").execute()


def upload_image(filename: str, filepath: Path) -> bool:
    sb = get_service_client()
    try:
        with open(filepath, "rb") as f:
            sb.storage.from_("images").upload(filename, f.read(), {"content-type": "image/png", "upsert": "true"})
        return True
    except Exception:
        return False
