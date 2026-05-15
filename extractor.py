import json
import os
import re

from dotenv import load_dotenv
from mistralai.client import Mistral

load_dotenv()
client = Mistral(api_key=os.environ["MISTRAL_API_KEY"])

SYSTEM_PROMPT = """Tu es le moteur éditorial de UserHereForCulture, un magazine de curation Finance & Tech en mode sombre.

Ton rôle : analyser des newsletters et retourner UNIQUEMENT un objet JSON valide (sans markdown, sans backticks, sans preamble).

Structure stricte :
{
  "titre": "Titre court percutant (max 80 chars)",
  "categorie": "Finance" | "Tech" | "IA" | "Marché" | "Startup" | "Crypto" | "Autre",
  "resume": ["Point clé 1", "Point clé 2", "Point clé 3"],
  "score": <entier 1-10>,
  "score_raison": "Justification courte",
  "image_prompt": "Abstract concept of: [sujet en anglais], minimalist editorial illustration, dark background, geometric shapes, no text, high contrast"
}

Critères score : 9-10=rupture majeure, 7-8=tendance forte, 5-6=info utile, 3-4=bruit, 1-2=spam.

Si l'email est une alerte de sécurité, confirmation de commande ou message personnel, retourne exactement :
{"statut": "ignore"}

RÈGLE ABSOLUE : JSON pur uniquement. Tout autre output fait planter l'app."""

VALID_CATEGORIES = {"Finance", "Tech", "IA", "Marché", "Startup", "Crypto", "Autre"}
REQUIRED_KEYS    = {"titre", "categorie", "resume", "score", "score_raison", "image_prompt"}


def _clean_raw(text: str) -> str:
    text = text.strip()
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    match = re.search(r"\{[\s\S]*\}", text)
    return match.group(0) if match else text


def _validate(data: dict) -> dict:
    if data.get("statut") == "ignore":
        return data

    missing = REQUIRED_KEYS - data.keys()
    if missing:
        raise ValueError(f"Champs manquants : {missing}")

    if data["categorie"] not in VALID_CATEGORIES:
        raise ValueError(f"Catégorie invalide : {data['categorie']!r}")

    if not isinstance(data["resume"], list) or len(data["resume"]) == 0:
        raise ValueError("'resume' doit être une liste non vide.")
    data["resume"] = data["resume"][:3]

    score = data["score"]
    if not isinstance(score, (int, float)) or not (1 <= score <= 10):
        raise ValueError(f"score hors plage : {score}")

    return data


def extract(email_date: str, sender: str, subject: str, body: str) -> dict:
    """
    Analyse un email et retourne un dict JSON structuré.
    Retourne {"statut": "ignore"} si non pertinent.
    Lève ValueError si le JSON est malformé.
    """
    user_message = (
        f"Date : {email_date}\n"
        f"Expéditeur : {sender}\n"
        f"Sujet : {subject}\n\n"
        f"{body[:6000]}"
    )

    response = client.chat.complete(
        model="mistral-small-latest",
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_message},
        ],
    )

    raw     = response.choices[0].message.content
    cleaned = _clean_raw(raw)
    data    = json.loads(cleaned)
    return _validate(data)
