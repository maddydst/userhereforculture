#!/usr/bin/env python3
"""
Pipeline : Gmail → Claude → newsletters.json
Compte cible : userhereforculture@gmail.com
Usage : python main.py [nb_jours]   (défaut : 1)
"""

import base64
import hashlib
import json
import os
import re
import sys
from datetime import datetime, timedelta
from email.utils import parsedate_to_datetime
from pathlib import Path

from dotenv import load_dotenv

from gmail_auth import get_gmail_service
from extractor import extract
from db import seen_ids as db_seen_ids, insert_article, upload_image

load_dotenv()

OUTPUT_FILE = Path("newsletters.json")
IMAGES_DIR  = Path("generated_images")
IMAGES_DIR.mkdir(exist_ok=True)
MAX_EMAILS   = 200
BODY_LIMIT   = 6000

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
_gemini_client = None
if GEMINI_API_KEY:
    try:
        from google import genai
        _gemini_client = genai.Client(api_key=GEMINI_API_KEY)
    except Exception:
        pass


def _card_id(titre: str) -> str:
    return hashlib.md5(titre.encode()).hexdigest()[:10]


def _generate_image(prompt: str, card_id: str) -> str | None:
    path = IMAGES_DIR / f"{card_id}.png"
    if path.exists():
        return str(path)
    if not _gemini_client:
        return None
    try:
        from PIL import Image
        response = _gemini_client.models.generate_images(
            model="imagen-3.0-generate-002",
            prompt=prompt,
            config={"number_of_images": 1, "aspect_ratio": "16:9"},
        )
        img_data = response.generated_images[0].image
        pil_img = Image.open(img_data._blob.io)
        pil_img.save(path, format="PNG")
        print(f"         🎨 image générée")
        return str(path)
    except Exception as e:
        print(f"         ⚠ image échouée : {e}")
        return None

# Expéditeurs systématiquement ignorés avant tout appel API
IGNORE_SENDERS = re.compile(
    r"(noreply@accounts\.google\.com"
    r"|no-reply@.*google\.com"
    r"|security-noreply"
    r"|mailer-daemon)",
    re.IGNORECASE,
)


# ---------------------------------------------------------------------------
# Helpers Gmail
# ---------------------------------------------------------------------------

def _header(headers: list[dict], name: str) -> str:
    for h in headers:
        if h["name"].lower() == name.lower():
            return h["value"]
    return ""


def _decode_part(data: str) -> str:
    return base64.urlsafe_b64decode(data).decode("utf-8", errors="replace")


def _extract_body(payload: dict) -> str:
    """Parcourt récursivement le payload MIME. Préfère text/plain, fallback HTML."""
    plain = []
    html  = []

    def walk(part: dict):
        mime = part.get("mimeType", "")
        data = part.get("body", {}).get("data", "")
        if mime == "text/plain" and data:
            plain.append(_decode_part(data))
        elif mime == "text/html" and data:
            raw = _decode_part(data)
            # Supprime balises, liens et espaces multiples
            raw = re.sub(r"<a[^>]*>.*?</a>", " ", raw, flags=re.IGNORECASE | re.DOTALL)
            raw = re.sub(r"<[^>]+>", " ", raw)
            raw = re.sub(r"[ \t]{2,}", " ", raw)
            raw = re.sub(r"\n{3,}", "\n\n", raw)
            html.append(raw.strip())
        for sub in part.get("parts", []):
            walk(sub)

    walk(payload)
    text = "\n".join(plain) if plain else "\n".join(html)
    return text.strip()


# ---------------------------------------------------------------------------
# Récupération Gmail
# ---------------------------------------------------------------------------

def fetch_emails(days: int = 1) -> list[dict]:
    """Retourne les emails des dernières `days` journées (hors expéditeurs bannis)."""
    service = get_gmail_service()
    after   = int((datetime.now() - timedelta(days=days)).timestamp())

    query = f"after:{after}"

    response = service.users().messages().list(
        userId="me", q=query, maxResults=MAX_EMAILS
    ).execute()

    message_refs = response.get("messages", [])
    emails = []

    for ref in message_refs:
        msg     = service.users().messages().get(
            userId="me", id=ref["id"], format="full"
        ).execute()
        headers = msg["payload"].get("headers", [])
        sender  = _header(headers, "From")

        if IGNORE_SENDERS.search(sender):
            continue

        subject  = _header(headers, "Subject")
        date_raw = _header(headers, "Date")
        msg_id   = _header(headers, "Message-ID") or ref["id"]

        try:
            date = parsedate_to_datetime(date_raw).strftime("%Y-%m-%d")
        except Exception:
            date = datetime.now().strftime("%Y-%m-%d")

        body = _extract_body(msg["payload"])

        emails.append({
            "id":      msg_id,
            "date":    date,
            "sender":  sender,
            "subject": subject,
            "body":    body,
        })

    return emails


# ---------------------------------------------------------------------------
# Persistance JSON (append sans écraser, déduplication par Message-ID)
# ---------------------------------------------------------------------------

def _load_existing() -> tuple[list[dict], set[str]]:
    if not OUTPUT_FILE.exists():
        return [], set()
    try:
        data = json.loads(OUTPUT_FILE.read_text(encoding="utf-8"))
        seen = {entry.get("_id", "") for entry in data}
        return data, seen
    except json.JSONDecodeError:
        print(f"[WARN] {OUTPUT_FILE} corrompu — fichier réinitialisé.")
        return [], set()


def _save(entries: list[dict]):
    OUTPUT_FILE.write_text(
        json.dumps(entries, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


# ---------------------------------------------------------------------------
# Pipeline principal
# ---------------------------------------------------------------------------

def run(days: int = 1):
    print(f"[→] Récupération des emails ({days} dernier(s) jour(s))...")
    emails = fetch_emails(days=days)
    print(f"[→] {len(emails)} email(s) à analyser.\n")

    existing_ids = db_seen_ids()
    stats = {"ok": 0, "ignored": 0, "error": 0, "duplicate": 0}

    for email in emails:
        label = email["subject"][:55] or "(sans sujet)"

        if email["id"] in existing_ids:
            print(f"  [DUP]  {label}")
            stats["duplicate"] += 1
            continue

        print(f"  [→]    {label}")
        try:
            result = extract(
                email_date=email["date"],
                sender=email["sender"],
                subject=email["subject"],
                body=email["body"][:BODY_LIMIT],
            )

            if result.get("statut") == "ignore":
                print(f"  [IGN]  ignoré par Mistral")
                stats["ignored"] += 1
                continue

            result["_id"]    = email["id"]
            result["date"]   = email["date"]
            result["source"] = email["sender"]
            cid = _card_id(result["titre"])
            img_path = _generate_image(result.get("image_prompt", result["titre"]), cid)
            if img_path:
                filename = cid + ".png"
                upload_image(filename, IMAGES_DIR / filename)
                result["image"] = filename

            insert_article(result)
            existing_ids.add(email["id"])
            stats["ok"] += 1
            print(f"         ✓ [{result['categorie']}] score {result['score']}/10")

        except (ValueError, KeyError) as e:
            print(f"  [ERR]  Validation : {e}")
            stats["error"] += 1
        except Exception as e:
            print(f"  [ERR]  Inattendu : {e}")
            stats["error"] += 1

    print(
        f"\n[OK] {stats['ok']} extraite(s) · "
        f"{stats['ignored']} ignorée(s) · "
        f"{stats['duplicate']} doublon(s) · "
        f"{stats['error']} erreur(s)"
    )


if __name__ == "__main__":
    days_arg = int(sys.argv[1]) if len(sys.argv) > 1 else 1
    run(days=days_arg)
