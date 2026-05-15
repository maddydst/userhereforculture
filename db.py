import os
from supabase import create_client, Client

_client: Client | None = None


def get_client() -> Client:
    global _client
    if _client is None:
        url = os.environ["SUPABASE_URL"]
        key = os.environ["SUPABASE_KEY"]
        _client = create_client(url, key)
    return _client


def fetch_articles(category: str | None = None) -> list[dict]:
    sb = get_client()
    q = sb.table("newsletters").select("*").order("date", desc=True).order("score", desc=True)
    if category and category != "all":
        q = q.eq("categorie", category)
    return q.execute().data


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
