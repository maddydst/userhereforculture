import os
from datetime import date

from dotenv import load_dotenv
from flask import Flask, render_template, request, send_from_directory

load_dotenv()

from db import fetch_articles

app = Flask(__name__)

CATEGORIES = {
    "Tech":    {"color": "#00d4ff", "bg": "#00d4ff18", "border": "#00d4ff35"},
    "Finance": {"color": "#d4af37", "bg": "#d4af3718", "border": "#d4af3735"},
    "IA":      {"color": "#bf5fff", "bg": "#bf5fff18", "border": "#bf5fff35"},
    "Marché":  {"color": "#ff8c00", "bg": "#ff8c0018", "border": "#ff8c0035"},
    "Startup": {"color": "#00e5cc", "bg": "#00e5cc18", "border": "#00e5cc35"},
    "Crypto":  {"color": "#f7931a", "bg": "#f7931a18", "border": "#f7931a35"},
    "Autre":   {"color": "#8892b0", "bg": "#8892b018", "border": "#8892b035"},
}


def enrich(articles: list[dict]) -> list[dict]:
    for a in articles:
        cat = a.get("categorie", "Autre")
        a["_theme"] = CATEGORIES.get(cat, CATEGORIES["Autre"])
    return articles


@app.route("/")
def index():
    category = request.args.get("cat", "all")
    articles = enrich(fetch_articles(category))
    featured = articles[0] if articles else None
    rest = articles[1:] if len(articles) > 1 else []
    today = date.today().strftime("%-d %B %Y")
    return render_template(
        "index.html",
        featured=featured,
        articles=rest,
        categories=list(CATEGORIES.keys()),
        themes=CATEGORIES,
        active_cat=category,
        today=today,
        total=len(articles),
    )


@app.route("/images/<path:filename>")
def serve_image(filename):
    return send_from_directory("generated_images", filename)


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port, debug=False)
