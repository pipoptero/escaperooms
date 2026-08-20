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


ROOM_ALIASES = {}
ROOM_ALIAS_ROOMS = {}


def load_room_aliases():
    data = read_json(ROOT / "room_aliases.json", {})
    aliases = data.get("aliases") or {}
    rooms = data.get("rooms") or {}
    for alias, target in aliases.items():
        alias_key = slugify(alias, "_")
        target_key = slugify(target, "_")
        if alias_key and target_key:
            ROOM_ALIASES[alias_key] = target_key
    for key, meta in rooms.items():
        target_key = slugify(key, "_")
        if not target_key:
            continue
        ROOM_ALIAS_ROOMS[target_key] = meta or {}
        for alias in (meta or {}).get("aliases") or []:
            alias_key = slugify(alias, "_")
            if alias_key:
                ROOM_ALIASES[alias_key] = target_key


load_room_aliases()


def canonical_room_identity(value):
    key = slugify(value, "_")
    return ROOM_ALIASES.get(key, key)


def canonical_room_name(room):
    meta = ROOM_ALIAS_ROOMS.get(room_identity(room), {})
    return text(meta.get("canonical_name")) or text(room.get("nombre"))


def canonical_room_company(room):
    meta = ROOM_ALIAS_ROOMS.get(room_identity(room), {})
    return text(meta.get("canonical_company")) or text(room.get("empresa"))


def room_alias_keys(room):
    identity = room_identity(room)
    keys = {
        identity,
        canonical_room_identity(room.get("id")),
        canonical_room_identity(room.get("nombre")),
        slugify(room.get("id"), "_"),
        slugify(room.get("nombre"), "_"),
    }
    meta = ROOM_ALIAS_ROOMS.get(identity, {})
    for alias in meta.get("aliases") or []:
        keys.add(slugify(alias, "_"))
    for alias, target in ROOM_ALIASES.items():
        if target == identity:
            keys.add(alias)
    return [key for key in keys if key and key != "escape_room"]


def app_hash_key(room):
    return slugify(canonical_room_name(room), "_").replace("_", "-")


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
    for key in room_alias_keys(room):
        entry = photos_data.get(key, {})
        if entry.get("photos"):
            return entry.get("photos") or []
    return []


def room_identity(room):
    return canonical_room_identity(room.get("id") or room.get("nombre"))


def room_url_slug(room):
    return slugify(canonical_room_name(room))


def source_label(source_id, meta):
    labels = meta.get("sources", {}) if isinstance(meta, dict) else {}
    return labels.get(source_id, {}).get("label") or {
        "giba": "Giba Escape",
        "ocioterror": "OcioTerror",
        "todoescaperooms": "TodoEscapeRooms",
        "the_vault_community": "Comunidad The Vault",
    }.get(source_id, source_id)


def merge_room_data(base, extra):
    merged = dict(base or {})
    for key, value in (extra or {}).items():
        if text(value) and not text(merged.get(key)):
            merged[key] = value
    return merged


def apply_canonical_room_fields(room):
    merged = dict(room or {})
    name = canonical_room_name(merged)
    company = canonical_room_company(merged)
    if name:
        merged["nombre"] = name
    if company:
        merged["empresa"] = company
    return merged


def review_rooms(data):
    by_key = {}
    for room in data.get("hechos", []) or []:
        if not text(room.get("nombre")):
            continue
        key = room_identity(room)
        if not key:
            continue
        by_key[key] = merge_room_data(by_key.get(key, {}), room)
    rooms = [apply_canonical_room_fields(room) for room in by_key.values()]
    rooms.sort(key=lambda room: (int(decimal(room.get("ranking")) or 999), text(room.get("nombre")).lower()))
    return rooms


def build_room_lookup(data):
    lookup = {}
    for collection in ("hechos", "pendientes"):
        for room in data.get(collection, []) or []:
            key = room_identity(room)
            if key:
                lookup[key] = merge_room_data(lookup.get(key, {}), room)
    catalog = read_json(ROOT / "catalog.json", [])
    if isinstance(catalog, dict):
        catalog = catalog.get("rooms") or catalog.get("catalog") or []
    for room in catalog or []:
        key = room_identity(room)
        if key:
            lookup[key] = merge_room_data(lookup.get(key, {}), room)
    return lookup


def ranked_rooms(data):
    external = read_json(ROOT / "external_ratings.json", {})
    ratings = external.get("ratings", {})
    meta = external.get("meta", {})
    lookup = build_room_lookup(data)
    by_identity = {}
    for key, rating in ratings.items():
        rating_room = rating.get("room") or {}
        identity = room_identity(rating_room) if text(rating_room.get("nombre")) or text(rating_room.get("id")) else canonical_room_identity(key)
        room = apply_canonical_room_fields(merge_room_data(rating_room, lookup.get(identity, {})))
        if not text(room.get("nombre")):
            room["nombre"] = key.replace("_", " ").title()
        item = {"key": key, "room": room, "rating": rating, "meta": meta}
        current = by_identity.get(identity)
        item_score = (
            decimal(rating.get("global_score")),
            int(rating.get("source_count") or 0),
            int(rating.get("award_count") or 0),
        )
        current_score = (
            decimal(current["rating"].get("global_score")),
            int(current["rating"].get("source_count") or 0),
            int(current["rating"].get("award_count") or 0),
        ) if current else (-1, -1, -1)
        if not current or item_score > current_score:
            by_identity[identity] = item
    rows = list(by_identity.values())
    rows.sort(
        key=lambda item: (
            -decimal(item["rating"].get("global_score")),
            -int(item["rating"].get("source_count") or 0),
            -int(item["rating"].get("award_count") or 0),
            text(item["room"].get("nombre")).lower(),
        )
    )
    return rows


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
    name = canonical_room_name(room) or "Escape room"
    company = canonical_room_company(room)
    slug = room_url_slug(room)
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
    <h2>Opinión del grupo</h2>
    <div class="review">{escape(text(room.get("descripcion")) or "Review pendiente de completar.")}</div>
  </section>
  <section class="section">
    <h2>Valoración por categorías</h2>
    <div class="cats">{cat_html}</div>
  </section>
  {f'<section class="section"><h2>Fotos de la experiencia</h2><div class="photos">{photo_html}</div></section>' if photo_html else ''}
</main>
</body>
</html>
"""


def reviews_index_page(rooms):
    canonical = site_url("/reviews/")
    description = "Reviews de escape rooms jugados por The Vault Escape, con opinión del grupo, puntuaciones y fotos."
    image = site_url("/images/brand/social-card.png")
    title = f"Reviews de escape rooms | {SITE_NAME}"
    items = []
    list_items = []
    for idx, room in enumerate(rooms, 1):
        name = canonical_room_name(room) or "Escape room"
        slug = room_url_slug(room)
        url = site_url(f"/reviews/{slug}/")
        items.append(
            f'<a class="review-link" href="{escape(url)}"><strong>{escape(name)}</strong>'
            f'<span>{escape(canonical_room_company(room))}{(" - " + escape(room_location(room))) if room_location(room) else ""}</span></a>'
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


def ranking_index_page(rows):
    top_rows = rows
    canonical = site_url("/ranking/")
    description = "Ranking ponderado de escape rooms en España según fuentes externas, comunidad y premios recopilados por The Vault Escape."
    image = site_url("/images/brand/social-card.png")
    title = f"Ranking de escape rooms en España | {SITE_NAME}"
    items = []
    list_items = []
    for idx, item in enumerate(top_rows, 1):
        room = item["room"]
        rating = item["rating"]
        name = canonical_room_name(room) or "Escape room"
        url = site_url(f"/salas/{room_url_slug(room)}/")
        score = decimal(rating.get("global_score"))
        location = room_location(room)
        items.append(
            f'<a class="rank-link" href="{escape(url)}">'
            f'<span class="pos">#{idx}</span><strong>{escape(name)}</strong>'
            f'<span>{escape(canonical_room_company(room))}{(" - " + escape(location)) if location else ""}</span>'
            f'<em>{score:.1f}/10 · {int(rating.get("source_count") or 0)} fuentes</em></a>'
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
  main{{width:min(980px,calc(100% - 32px));margin:0 auto;padding:32px 0 48px;}}
  a{{color:#7dbb3f;}}
  .brand{{display:flex;align-items:center;gap:12px;text-decoration:none;text-transform:uppercase;letter-spacing:.12em;color:#9a9ab6;font-size:.72rem;margin-bottom:24px;}}
  .brand img{{width:42px;height:42px;border-radius:50%;}}
  h1{{font-family:Georgia,serif;font-size:clamp(2rem,5vw,3.5rem);line-height:1.05;margin:0 0 10px;}}
  p{{color:#b8b8c8;line-height:1.6;}}
  .list{{display:grid;gap:10px;margin-top:24px;}}
  .rank-link{{display:grid;grid-template-columns:56px minmax(0,1fr) auto;gap:8px 12px;align-items:center;border:1px solid rgba(125,187,63,.2);background:rgba(255,255,255,.025);padding:13px;text-decoration:none;}}
  .pos{{grid-row:1/3;color:#7dbb3f;font-weight:700;font-size:1.1rem;}}
  .rank-link strong{{color:#f0f0ea;font-family:Georgia,serif;font-size:1.15rem;}}
  .rank-link span:not(.pos){{color:#9a9ab6;}}
  .rank-link em{{grid-column:3;grid-row:1/3;color:#7dbb3f;font-style:normal;font-weight:700;white-space:nowrap;}}
  @media(max-width:680px){{.rank-link{{grid-template-columns:44px minmax(0,1fr);}}.rank-link em{{grid-column:2;grid-row:auto;}}}}
</style>
</head>
<body>
<main>
  <a class="brand" href="../"><img src="../images/brand/icon-round-192.png" alt="">The Vault Escape</a>
  <h1>Ranking de escape rooms en España</h1>
  <p>Ranking ponderado con fuentes externas, comunidad y premios. Esta página estática ayuda a Google a descubrir salas destacadas y enlaza con sus fichas SEO.</p>
  <div class="list">
    {''.join(items)}
  </div>
</main>
</body>
</html>
"""


def source_pills(rating, meta):
    items = []
    for source_id, source in (rating.get("sources") or {}).items():
        score = decimal(source.get("score"))
        votes = f" · {int(source.get('votes'))} votos" if source.get("votes") else ""
        items.append(f'<span class="pill">{escape(source_label(source_id, meta))}: {score:.1f}/10{votes}</span>')
    if decimal(rating.get("award_bonus")):
        items.append(f'<span class="pill">Premios +{decimal(rating.get("award_bonus")):.1f}</span>')
    return "\n".join(items)


def room_page(item, position):
    room = item["room"]
    rating = item["rating"]
    meta = item["meta"]
    name = canonical_room_name(room) or "Escape room"
    company = canonical_room_company(room)
    slug = room_url_slug(room)
    canonical = site_url(f"/salas/{slug}/")
    app_link = site_url(f"/#room/{app_hash_key(room)}")
    score = decimal(rating.get("global_score"))
    description = short_description({
        **room,
        "descripcion": text(room.get("descripcion")) or (
            f"{name} aparece en el ranking ponderado de The Vault Escape con una nota global de {score:.1f}/10 "
            f"calculada a partir de {int(rating.get('source_count') or 0)} fuentes."
        ),
    })
    image = asset_url(room.get("imagen") or "images/brand/social-card.png")
    cover = page_asset(room.get("imagen") or "images/brand/social-card.png")
    title = f"{name}: ranking y puntuaciones | {SITE_NAME}"
    location = room_location(room)
    meta_values = [
        location,
        text(room.get("tematica")),
        text(room.get("tipo")),
        f'{text(room.get("duracion"))} min' if text(room.get("duracion")) else "",
        text(room.get("dificultad")),
    ]
    meta_html = "\n".join(f'<span class="pill">{escape(value)}</span>' for value in meta_values if value)
    sources_html = source_pills(rating, meta)
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
                "@type": "EntertainmentBusiness",
                "name": f"{name}{' - ' + company if company else ''}",
                "image": image,
                "address": {
                    "@type": "PostalAddress",
                    "addressLocality": text(room.get("ciudad")),
                    "addressRegion": text(room.get("provincia")),
                    "addressCountry": "ES",
                },
                "aggregateRating": {
                    "@type": "AggregateRating",
                    "ratingValue": f"{score:.1f}",
                    "bestRating": "10",
                    "worstRating": "0",
                    "ratingCount": max(1, int(rating.get("source_count") or 1)),
                },
            },
            {
                "@type": "BreadcrumbList",
                "itemListElement": [
                    {"@type": "ListItem", "position": 1, "name": "Inicio", "item": site_url("/")},
                    {"@type": "ListItem", "position": 2, "name": "Ranking", "item": site_url("/ranking/")},
                    {"@type": "ListItem", "position": 3, "name": name, "item": canonical},
                ],
            },
        ],
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
      <div class="kicker">Sala destacada #{position}</div>
      <h1>{escape(name)}</h1>
      <div class="company">{escape(company)}</div>
      <div class="meta">{meta_html}</div>
      <div class="score">Nota global: {score:.1f}/10</div>
      <p>{escape(description)}</p>
      <div class="actions">
        <a class="btn" href="{escape(app_link)}">Abrir ficha interactiva</a>
        <a class="btn secondary" href="../../ranking/">Ver ranking completo</a>
      </div>
    </div>
  </article>
  <section class="section">
    <h2>Fuentes del ranking</h2>
    <div class="meta">{sources_html}</div>
  </section>
  {f'<section class="section"><h2>Sinopsis</h2><div class="review">{escape(text(room.get("descripcion")))}</div></section>' if text(room.get("descripcion")) else ''}
</main>
</body>
</html>
"""


def sitemap_xml(review_rooms, ranking_rows):
    entries = [
        (site_url("/"), "daily", "1.0"),
        (site_url("/reviews/"), "weekly", "0.8"),
        (site_url("/ranking/"), "weekly", "0.9"),
    ]
    entries.extend((site_url(f"/reviews/{room_url_slug(room)}/"), "monthly", "0.7") for room in review_rooms)
    entries.extend((site_url(f"/salas/{room_url_slug(item['room'])}/"), "monthly", "0.7") for item in ranking_rows)
    unique_entries = []
    seen_urls = set()
    for entry in entries:
        if entry[0] in seen_urls:
            continue
        unique_entries.append(entry)
        seen_urls.add(entry[0])
    body = "\n".join(
        f"  <url><loc>{escape(url)}</loc><lastmod>{TODAY}</lastmod><changefreq>{freq}</changefreq><priority>{priority}</priority></url>"
        for url, freq, priority in unique_entries
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
    rooms = review_rooms(data)
    ranking_rows = [row for row in ranked_rooms(data) if decimal(row["rating"].get("global_score")) > 0]

    reviews_dir = ROOT / "reviews"
    reviews_dir.mkdir(exist_ok=True)
    for room in rooms:
        slug = slugify(room.get("nombre"))
        page_dir = reviews_dir / slug
        page_dir.mkdir(parents=True, exist_ok=True)
        photos = photo_entries(room, photos_data)
        (page_dir / "index.html").write_text(review_page(room, photos), encoding="utf-8", newline="\n")

    (reviews_dir / "index.html").write_text(reviews_index_page(rooms), encoding="utf-8", newline="\n")
    ranking_dir = ROOT / "ranking"
    ranking_dir.mkdir(exist_ok=True)
    (ranking_dir / "index.html").write_text(ranking_index_page(ranking_rows), encoding="utf-8", newline="\n")

    salas_dir = ROOT / "salas"
    salas_dir.mkdir(exist_ok=True)
    for position, item in enumerate(ranking_rows, 1):
        page_dir = salas_dir / room_url_slug(item["room"])
        page_dir.mkdir(parents=True, exist_ok=True)
        (page_dir / "index.html").write_text(room_page(item, position), encoding="utf-8", newline="\n")

    (ROOT / "sitemap.xml").write_text(sitemap_xml(rooms, ranking_rows), encoding="utf-8", newline="\n")
    (ROOT / "robots.txt").write_text(robots_txt(), encoding="utf-8", newline="\n")
    print(f"SEO generado: {len(rooms)} reviews, {len(ranking_rows)} salas, ranking, sitemap.xml y robots.txt")


if __name__ == "__main__":
    main()
