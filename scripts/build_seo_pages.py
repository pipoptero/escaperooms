import json
import re
import unicodedata
from datetime import date
from html import escape
from pathlib import Path
from urllib.parse import quote


ROOT = Path(__file__).resolve().parents[1]
BASE_URL = "https://thevaultescape.com"
SITE_NAME = "The Vault Escape"
TODAY = date.today().isoformat()


def read_json(path, fallback):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return fallback


def slugify(text, separator="-"):
    text = unicodedata.normalize("NFD", str(text or "").lower())
    text = "".join(ch for ch in text if unicodedata.category(ch) != "Mn")
    text = re.sub(r"[^a-z0-9]+", separator, text).strip(separator)
    return text or "escape-room"


def app_hash_key(room):
    return slugify(room.get("nombre"), "_").replace("_", "-")


def text(value):
    return str(value or "").strip()


def decimal(value):
    raw = text(value).replace(",", ".")
    try:
        return float(raw)
    except ValueError:
        return 0.0


def site_url(path="/"):
    if not path.startswith("/"):
        path = "/" + path
    return BASE_URL + path


def asset_url(path):
    value = text(path).replace("\\", "/")
    if not value:
        return site_url("/images/brand/social-card.png")
    if value.startswith("http://") or value.startswith("https://"):
        return value
    return BASE_URL + "/" + quote(value, safe="/")


def page_asset(path):
    value = text(path).replace("\\", "/")
    if not value:
        return "../../images/brand/social-card.png"
    if value.startswith("http://") or value.startswith("https://"):
        return value
    return "../../" + quote(value, safe="/")


def short_description(room, limit=155):
    source = re.sub(r"\s+", " ", text(room.get("descripcion")))
    if not source:
        source = f"Review de {text(room.get('nombre'))} en {SITE_NAME}."
    if len(source) <= limit:
        return source
    return source[: limit - 1].rsplit(" ", 1)[0] + "..."


def score_label(value):
    score = decimal(value)
    return f"{score:.1f}".replace(".0", "") if score else ""


def room_location(room):
    return " - ".join(part for part in [text(room.get("ciudad")), text(room.get("provincia"))] if part)


def photo_entries(room, photos_data):
    key = slugify(room.get("nombre"), "_")
    entry = photos_data.get(key, {})
    return entry.get("photos") or []


def json_ld(data):
    return json.dumps(data, ensure_ascii=False, indent=2)


def base_head(title, description, canonical, image):
    return f"""<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{escape(title)}</title>
<meta name="description" content="{escape(description)}">
<link rel="canonical" href="{escape(canonical)}">
<meta name="theme-color" content="#0a0a0f">
<link rel="icon" href="../../images/brand/favicon-round-32.png" sizes="32x32" type="image/png">
<link rel="apple-touch-icon" href="../../images/brand/apple-touch-icon-round.png">
<meta property="og:type" content="article">
<meta property="og:site_name" content="{SITE_NAME}">
<meta property="og:title" content="{escape(title)}">
<meta property="og:description" content="{escape(description)}">
<meta property="og:url" content="{escape(canonical)}">
<meta property="og:image" content="{escape(image)}">
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:title" content="{escape(title)}">
<meta name="twitter:description" content="{escape(description)}">
<meta name="twitter:image" content="{escape(image)}">
<style>
  :root {{ --bg:#0a0a0f; --card:#12121e; --border:#2a2a45; --green:#7dbb3f; --text:#f0f0ea; --muted:#9a9ab6; --soft:#151522; }}
  * {{ box-sizing:border-box; }}
  body {{ margin:0; background:radial-gradient(ellipse at top,rgba(125,187,63,.12),transparent 36%),var(--bg); color:var(--text); font-family:Arial,Helvetica,sans-serif; line-height:1.55; }}
  a {{ color:var(--green); }}
  .wrap {{ width:min(1020px,calc(100% - 32px)); margin:0 auto; padding:28px 0 44px; }}
  .brand {{ display:flex; align-items:center; gap:12px; margin-bottom:26px; color:var(--muted); text-decoration:none; text-transform:uppercase; letter-spacing:.12em; font-size:.72rem; }}
  .brand img {{ width:42px; height:42px; border-radius:50%; object-fit:cover; }}
  .hero {{ display:grid; grid-template-columns:minmax(220px,360px) minmax(0,1fr); gap:24px; align-items:start; border:1px solid rgba(125,187,63,.25); background:linear-gradient(135deg,rgba(255,255,255,.035),rgba(125,187,63,.04)); padding:22px; }}
  .cover {{ width:100%; max-height:520px; object-fit:contain; background:#050507; border:1px solid rgba(255,255,255,.08); }}
  .kicker {{ color:var(--green); text-transform:uppercase; letter-spacing:.16em; font-size:.72rem; margin-bottom:8px; }}
  h1 {{ margin:.1em 0 .25em; font-family:Georgia,serif; font-size:clamp(2rem,5vw,3.8rem); line-height:1.02; }}
  .company {{ color:var(--muted); text-transform:uppercase; letter-spacing:.08em; font-size:.84rem; }}
  .meta {{ display:flex; flex-wrap:wrap; gap:8px; margin:18px 0; }}
  .pill {{ border:1px solid rgba(125,187,63,.22); background:rgba(125,187,63,.06); color:#dbead2; padding:5px 8px; font-size:.86rem; }}
  .score {{ display:inline-flex; margin:8px 0 14px; border:1px solid rgba(125,187,63,.32); background:rgba(125,187,63,.08); color:var(--green); padding:8px 12px; font-weight:700; font-size:1.15rem; }}
  .section {{ margin-top:24px; border:1px solid rgba(255,255,255,.08); background:rgba(255,255,255,.025); padding:18px; }}
  h2 {{ margin:0 0 10px; font-family:Georgia,serif; font-size:1.35rem; }}
  .review {{ color:#d9d9e3; white-space:pre-line; }}
  .cats {{ display:grid; grid-template-columns:repeat(4,minmax(0,1fr)); gap:10px; }}
  .cat {{ border:1px solid rgba(255,255,255,.08); background:rgba(0,0,0,.16); padding:10px; }}
  .cat span {{ display:block; color:var(--muted); font-size:.75rem; text-transform:uppercase; letter-spacing:.08em; }}
  .cat strong {{ color:var(--green); font-size:1.25rem; }}
  .photos {{ display:grid; grid-template-columns:repeat(auto-fill,minmax(160px,1fr)); gap:10px; }}
  .photos img {{ width:100%; aspect-ratio:4/3; object-fit:cover; border:1px solid rgba(125,187,63,.22); background:#050507; }}
  .actions {{ display:flex; gap:10px; flex-wrap:wrap; margin-top:20px; }}
  .btn {{ display:inline-flex; align-items:center; justify-content:center; min-height:42px; padding:9px 13px; border:1px solid rgba(125,187,63,.32); background:rgba(125,187,63,.07); text-decoration:none; text-transform:uppercase; letter-spacing:.08em; font-size:.78rem; }}
  .btn.secondary {{ border-color:rgba(255,255,255,.12); background:rgba(255,255,255,.025); color:var(--muted); }}
  @media(max-width:720px) {{ .hero {{ grid-template-columns:1fr; padding:16px; }} .cover {{ max-height:360px; }} .cats {{ grid-template-columns:1fr 1fr; }} .wrap {{ width:min(100% - 22px,1020px); padding-top:18px; }} }}
</style>
"""


def review_page(room, photos):
    name = text(room.get("nombre")) or "Escape room"
    company = text(room.get("empresa"))
    slug = slugify(name)
    canonical = site_url(f"/reviews/{slug}/")
    app_link = site_url(f"/#review/{app_hash_key(room)}")
    description = short_description(room)
    image = asset_url(room.get("imagen") or (photos[0].get("src") if photos else "images/brand/social-card.png"))
    title = f"Review de {name} | {SITE_NAME}"
    location = room_location(room)
    score = score_label(room.get("valoracion"))
    cover = page_asset(room.get("imagen") or (photos[0].get("src") if photos else "images/brand/social-card.png"))
    photo_html = "\n".join(
        f'<img src="{escape(page_asset(photo.get("src")))}" alt="{escape(photo.get("alt") or name)}" loading="lazy">'
        for photo in photos
    )
    cat_values = [
        ("Historia", room.get("historia")),
        ("Ambientacion", room.get("ambientacion")),
        ("Jugabilidad", room.get("jugabilidad")),
        ("Game Master", room.get("gamemaster")),
    ]
    cat_html = "\n".join(
        f'<div class="cat"><span>{escape(label)}</span><strong>{escape(score_label(value) or "-")}</strong></div>'
        for label, value in cat_values
    )
    meta = [
        location,
        text(room.get("tematica")),
        text(room.get("tipo")),
        f'{text(room.get("duracion"))} min' if text(room.get("duracion")) else "",
        text(room.get("dificultad")),
    ]
    meta_html = "\n".join(f'<span class="pill">{escape(item)}</span>' for item in meta if item)
    schema = {
        "@context": "https://schema.org",
        "@graph": [
            {
                "@type": "WebPage",
                "@id": canonical,
                "url": canonical,
                "name": title,
                "description": description,
                "isPartOf": {"@id": site_url("/#website")},
                "primaryImageOfPage": image,
            },
            {
                "@type": "Review",
                "name": f"Review de {name}",
                "reviewBody": text(room.get("descripcion")),
                "author": {"@type": "Organization", "name": SITE_NAME, "url": BASE_URL},
                "publisher": {"@type": "Organization", "name": SITE_NAME, "url": BASE_URL},
                "itemReviewed": {
                    "@type": "EntertainmentBusiness",
                    "name": f"{name}{' - ' + company if company else ''}",
                    "address": {
                        "@type": "PostalAddress",
                        "addressLocality": text(room.get("ciudad")),
                        "addressRegion": text(room.get("provincia")),
                        "addressCountry": "ES",
                    },
                },
                "image": image,
            },
            {
                "@type": "BreadcrumbList",
                "itemListElement": [
                    {"@type": "ListItem", "position": 1, "name": "Inicio", "item": site_url("/")},
                    {"@type": "ListItem", "position": 2, "name": "Reviews", "item": site_url("/reviews/")},
                    {"@type": "ListItem", "position": 3, "name": name, "item": canonical},
                ],
            },
        ],
    }
    if score:
        schema["@graph"][1]["reviewRating"] = {
            "@type": "Rating",
            "ratingValue": score.replace(",", "."),
            "bestRating": "10",
            "worstRating": "0",
        }
    return base_head(title, description, canonical, image) + f"""
<script type="application/ld+json">
{json_ld(schema)}
</script>
</head>
<body>
<main class="wrap">
  <a class="brand" href="../../"><img src="../../images/brand/icon-round-192.png" alt="">The Vault Escape</a>
  <article class="hero">
    <img class="cover" src="{escape(cover)}" alt="Cartel de {escape(name)}">
    <div>
      <div class="kicker">Review The Vault</div>
      <h1>{escape(name)}</h1>
      <div class="company">{escape(company)}</div>
      <div class="meta">{meta_html}</div>
      {f'<div class="score">Nota The Vault: {escape(score)}/10</div>' if score else ''}
      <p>{escape(description)}</p>
      <div class="actions">
        <a class="btn" href="{escape(app_link)}">Abrir ficha interactiva</a>
        <a class="btn secondary" href="../">Ver todas las reviews</a>
      </div>
    </div>
  </article>
  <section class="section">
    <h2>Opinion del grupo</h2>
    <div class="review">{escape(text(room.get("descripcion")) or "Review pendiente de completar.")}</div>
  </section>
  <section class="section">
    <h2>Valoracion por categorias</h2>
    <div class="cats">{cat_html}</div>
  </section>
  {f'<section class="section"><h2>Fotos de la experiencia</h2><div class="photos">{photo_html}</div></section>' if photo_html else ''}
</main>
</body>
</html>
"""


def reviews_index_page(rooms):
    canonical = site_url("/reviews/")
    description = "Reviews de escape rooms jugados por The Vault Escape, con opinion del grupo, puntuaciones y fotos."
    image = site_url("/images/brand/social-card.png")
    title = f"Reviews de escape rooms | {SITE_NAME}"
    items = []
    list_items = []
    for idx, room in enumerate(rooms, 1):
        name = text(room.get("nombre")) or "Escape room"
        slug = slugify(name)
        url = site_url(f"/reviews/{slug}/")
        items.append(
            f'<a class="review-link" href="{escape(url)}"><strong>{escape(name)}</strong>'
            f'<span>{escape(text(room.get("empresa")))}{(" - " + escape(room_location(room))) if room_location(room) else ""}</span></a>'
        )
        list_items.append({"@type": "ListItem", "position": idx, "name": name, "url": url})
    schema = {
        "@context": "https://schema.org",
        "@type": "CollectionPage",
        "name": title,
        "url": canonical,
        "description": description,
        "mainEntity": {"@type": "ItemList", "itemListElement": list_items},
    }
    return f"""<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{escape(title)}</title>
<meta name="description" content="{escape(description)}">
<link rel="canonical" href="{escape(canonical)}">
<link rel="icon" href="../images/brand/favicon-round-32.png" sizes="32x32" type="image/png">
<meta property="og:type" content="website">
<meta property="og:site_name" content="{SITE_NAME}">
<meta property="og:title" content="{escape(title)}">
<meta property="og:description" content="{escape(description)}">
<meta property="og:url" content="{escape(canonical)}">
<meta property="og:image" content="{escape(image)}">
<script type="application/ld+json">
{json_ld(schema)}
</script>
<style>
  body{{margin:0;background:#0a0a0f;color:#f0f0ea;font-family:Arial,Helvetica,sans-serif;}}
  main{{width:min(920px,calc(100% - 32px));margin:0 auto;padding:32px 0 48px;}}
  a{{color:#7dbb3f;}}
  .brand{{display:flex;align-items:center;gap:12px;text-decoration:none;text-transform:uppercase;letter-spacing:.12em;color:#9a9ab6;font-size:.72rem;margin-bottom:24px;}}
  .brand img{{width:42px;height:42px;border-radius:50%;}}
  h1{{font-family:Georgia,serif;font-size:clamp(2rem,5vw,3.4rem);line-height:1.05;margin:0 0 10px;}}
  p{{color:#b8b8c8;line-height:1.6;}}
  .list{{display:grid;gap:10px;margin-top:24px;}}
  .review-link{{display:block;border:1px solid rgba(125,187,63,.2);background:rgba(255,255,255,.025);padding:14px;text-decoration:none;}}
  .review-link strong{{display:block;color:#f0f0ea;font-family:Georgia,serif;font-size:1.15rem;}}
  .review-link span{{display:block;color:#9a9ab6;margin-top:3px;}}
</style>
</head>
<body>
<main>
  <a class="brand" href="../"><img src="../images/brand/icon-round-192.png" alt="">The Vault Escape</a>
  <h1>Reviews de escape rooms</h1>
  <p>Opiniones del grupo The Vault Escape sobre salas jugadas, con puntuaciones, fotos y enlaces a la ficha interactiva.</p>
  <div class="list">
    {''.join(items)}
  </div>
</main>
</body>
</html>
"""


def sitemap_xml(review_rooms):
    entries = [
        (site_url("/"), "daily", "1.0"),
        (site_url("/reviews/"), "weekly", "0.8"),
    ]
    entries.extend((site_url(f"/reviews/{slugify(room.get('nombre'))}/"), "monthly", "0.7") for room in review_rooms)
    body = "\n".join(
        f"  <url><loc>{escape(url)}</loc><lastmod>{TODAY}</lastmod><changefreq>{freq}</changefreq><priority>{priority}</priority></url>"
        for url, freq, priority in entries
    )
    return f'<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n{body}\n</urlset>\n'


def robots_txt():
    return f"""User-agent: *
Allow: /

Sitemap: {site_url('/sitemap.xml')}
"""


def main():
    data = read_json(ROOT / "data.json", {})
    photos_data = read_json(ROOT / "review_photos.json", {}).get("photos", {})
    rooms = [room for room in data.get("hechos", []) if text(room.get("nombre"))]
    rooms.sort(key=lambda room: (int(decimal(room.get("ranking")) or 999), text(room.get("nombre")).lower()))

    reviews_dir = ROOT / "reviews"
    reviews_dir.mkdir(exist_ok=True)
    for room in rooms:
        slug = slugify(room.get("nombre"))
        page_dir = reviews_dir / slug
        page_dir.mkdir(parents=True, exist_ok=True)
        photos = photo_entries(room, photos_data)
        (page_dir / "index.html").write_text(review_page(room, photos), encoding="utf-8", newline="\n")

    (reviews_dir / "index.html").write_text(reviews_index_page(rooms), encoding="utf-8", newline="\n")
    (ROOT / "sitemap.xml").write_text(sitemap_xml(rooms), encoding="utf-8", newline="\n")
    (ROOT / "robots.txt").write_text(robots_txt(), encoding="utf-8", newline="\n")
    print(f"SEO generado: {len(rooms)} reviews, sitemap.xml y robots.txt")


if __name__ == "__main__":
    main()
