import json
import re
import unicodedata
from datetime import date, datetime, timezone
from html import escape
from pathlib import Path
from urllib.parse import quote

try:
    from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageOps
except ImportError:  # The SEO pages still build without social card generation.
    Image = ImageDraw = ImageFont = ImageFilter = ImageOps = None


ROOT = Path(__file__).resolve().parents[1]
BASE_URL = "https://thevaultescape.com"
SITE_NAME = "The Vault Escape"
TODAY = date.today().isoformat()
DEFAULT_SOCIAL_CARD = "images/brand/social-card.png"
REVIEW_SOCIAL_DIR = Path("images/seo/reviews")


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


def folded(value):
    value = unicodedata.normalize("NFD", text(value).lower())
    return "".join(ch for ch in value if unicodedata.category(ch) != "Mn")


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


def local_asset_path(path):
    value = text(path).replace("\\", "/")
    if not value or value.startswith("http://") or value.startswith("https://"):
        return None
    candidate = ROOT / value
    return candidate if candidate.exists() else None


def short_description(room, limit=155):
    source = re.sub(r"\s+", " ", text(room.get("descripcion")))
    if not source:
        source = f"Review de {text(room.get('nombre'))} en {SITE_NAME}."
    if len(source) <= limit:
        return source
    return source[: limit - 1].rsplit(" ", 1)[0] + "..."


def short_text(value, limit=135):
    source = re.sub(r"\s+", " ", text(value))
    if len(source) <= limit:
        return source
    return source[: limit - 1].rsplit(" ", 1)[0] + "..."


def social_text(value):
    cleaned = []
    for ch in text(value):
        category = unicodedata.category(ch)
        if category.startswith("C") or category in {"Mn", "So", "Sk"}:
            continue
        cleaned.append(ch)
    return re.sub(r"\s+", " ", "".join(cleaned)).strip()


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


def catalog_rooms():
    catalog = read_json(ROOT / "catalog.json", [])
    if isinstance(catalog, dict):
        return catalog.get("catalogo") or catalog.get("rooms") or catalog.get("catalog") or []
    return catalog or []


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


def merge_room_override(base, extra):
    merged = dict(base or {})
    for key, value in (extra or {}).items():
        if text(value) or isinstance(value, (int, float, bool)):
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


def published_review_rooms(data):
    published = read_json(ROOT / "published_reviews.json", {})
    reviews = published.get("reviews") or {}
    lookup = build_room_lookup(data)
    rooms = []
    seen = set()
    for key, record in reviews.items():
        if text(record.get("status") or "published").lower() != "published":
            continue
        review = record.get("review") or {}
        identity = canonical_room_identity(
            record.get("roomKey")
            or record.get("sourceRoomKey")
            or review.get("id")
            or review.get("nombre")
            or key
        )
        if not identity or identity in seen:
            continue
        base = lookup.get(identity, {})
        room = merge_room_override(base, review)
        if not text(room.get("id")):
            room["id"] = identity
        room["_reviewKey"] = identity
        room["_publishedAt"] = record.get("publishedAt") or record.get("updatedAt") or 0
        room["_updatedAt"] = record.get("updatedAt") or record.get("publishedAt") or 0
        room["_reviewAuthorName"] = record.get("publishedByName") or review.get("_reviewAuthorName") or "The Vault"
        room["_arkkadiaCommunityReview"] = room["_reviewAuthorName"] not in ("", "The Vault")
        rooms.append(apply_canonical_room_fields(room))
        seen.add(identity)
    rooms.sort(key=lambda room: (-review_timestamp(room), text(room.get("nombre")).lower()))
    return rooms


def build_room_lookup(data):
    lookup = {}
    for collection in ("hechos", "pendientes"):
        for room in data.get(collection, []) or []:
            key = room_identity(room)
            if key:
                lookup[key] = merge_room_data(lookup.get(key, {}), room)
    for room in catalog_rooms():
        key = room_identity(room)
        if key:
            lookup[key] = merge_room_data(lookup.get(key, {}), room)
    return lookup


def review_timestamp(room):
    for key in ("_updatedAt", "_publishedAt", "updatedAt", "publishedAt"):
        try:
            value = int(room.get(key) or 0)
        except (TypeError, ValueError):
            value = 0
        if value:
            return value
    return 0


def timestamp_iso(ms):
    try:
        value = int(ms or 0)
    except (TypeError, ValueError):
        return ""
    if not value:
        return ""
    return datetime.fromtimestamp(value / 1000, tz=timezone.utc).date().isoformat()


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


def catalog_seo_rows(data, ranking_rows):
    rows = []
    by_identity = {}
    for position, item in enumerate(ranking_rows, 1):
        identity = room_identity(item.get("room"))
        if not identity:
            continue
        seo_item = dict(item)
        seo_item["position"] = position
        by_identity[identity] = seo_item

    for room in catalog_rooms():
        if not text(room.get("nombre")):
            continue
        room = apply_canonical_room_fields(room)
        identity = room_identity(room)
        if not identity:
            continue
        if identity in by_identity:
            by_identity[identity]["room"] = merge_room_data(by_identity[identity]["room"], room)
        else:
            by_identity[identity] = {
                "key": identity,
                "room": room,
                "rating": {},
                "meta": {},
                "position": None,
            }

    ranked_identities = {room_identity(item.get("room")) for item in ranking_rows}
    rows.extend(item for item in by_identity.values() if room_identity(item.get("room")) in ranked_identities)
    remaining = [
        item for item in by_identity.values()
        if room_identity(item.get("room")) not in ranked_identities
    ]
    remaining.sort(key=lambda item: text(item["room"].get("nombre")).lower())
    rows.extend(remaining)
    return rows


def json_ld(data):
    return json.dumps(data, ensure_ascii=False, indent=2)


def load_font(candidates, size):
    if ImageFont is None:
        return None
    for candidate in candidates:
        path = Path(candidate)
        if path.exists():
            try:
                return ImageFont.truetype(str(path), size=size)
            except OSError:
                pass
        try:
            return ImageFont.truetype(candidate, size=size)
        except OSError:
            pass
    return ImageFont.load_default()


def text_width(draw, value, font):
    box = draw.textbbox((0, 0), value, font=font)
    return box[2] - box[0]


def wrap_lines(draw, value, font, max_width, max_lines=3):
    words = text(value).split()
    lines = []
    current = ""
    for word in words:
        candidate = f"{current} {word}".strip()
        if not current or text_width(draw, candidate, font) <= max_width:
            current = candidate
            continue
        lines.append(current)
        current = word
        if len(lines) >= max_lines:
            break
    if current and len(lines) < max_lines:
        lines.append(current)
    if words and len(lines) == max_lines:
        consumed = " ".join(lines).split()
        if len(consumed) < len(words):
            lines[-1] = lines[-1].rstrip(".,;:") + "..."
    return lines or [""]


def cover_resize(image, size):
    if ImageOps is None:
        return image.resize(size)
    return ImageOps.fit(image, size, method=Image.Resampling.LANCZOS, centering=(0.5, 0.5))


def safe_open_image(path):
    try:
        return Image.open(path).convert("RGB")
    except Exception:
        return None


def review_social_source(room, photos):
    candidates = [
        *((photo.get("src") for photo in photos if photo.get("src")) if photos else []),
        room.get("imagen"),
        DEFAULT_SOCIAL_CARD,
    ]
    for candidate in candidates:
        path = local_asset_path(candidate)
        if path:
            return path
    return None


def generate_review_social_card(room, photos):
    if Image is None:
        return ""
    slug = room_url_slug(room)
    out_rel = REVIEW_SOCIAL_DIR / f"{slug}.jpg"
    out_path = ROOT / out_rel
    out_path.parent.mkdir(parents=True, exist_ok=True)

    name = canonical_room_name(room) or "Escape room"
    company = canonical_room_company(room)
    location = room_location(room)
    score = score_label(room.get("valoracion") or room.get("rating"))
    author = text(room.get("_reviewAuthorName")) or "The Vault"

    canvas = Image.new("RGB", (1200, 630), "#07080d")
    draw = ImageDraw.Draw(canvas)
    for y in range(630):
        glow = int(28 * (1 - y / 630))
        draw.line([(0, y), (1200, y)], fill=(7 + glow // 3, 8 + glow // 2, 13 + glow))
    draw.rectangle((0, 0, 1200, 630), outline=(125, 187, 63), width=3)
    draw.rectangle((24, 24, 1176, 606), outline=(42, 58, 38), width=1)

    source_path = review_social_source(room, photos)
    if source_path:
        image = safe_open_image(source_path)
        if image:
            cover = cover_resize(image, (470, 590))
            canvas.paste(cover, (704, 20))
            shade = Image.new("RGBA", (470, 590), (0, 0, 0, 48))
            canvas.paste(shade.convert("RGB"), (704, 20), shade)
            image.close()

    logo_path = local_asset_path("images/brand/icon-round-192.png") or local_asset_path("images/brand/the-vault-round-logo.jpg")
    if logo_path:
        logo = safe_open_image(logo_path)
        if logo:
            logo = cover_resize(logo, (86, 86))
            canvas.paste(logo, (62, 52))
            logo.close()

    title_font = load_font(["C:/Windows/Fonts/georgiab.ttf", "Georgia Bold", "DejaVuSerif-Bold.ttf"], 58)
    meta_font = load_font(["C:/Windows/Fonts/bahnschrift.ttf", "C:/Windows/Fonts/arialbd.ttf", "Arial Bold"], 25)
    small_font = load_font(["C:/Windows/Fonts/bahnschrift.ttf", "C:/Windows/Fonts/arial.ttf", "Arial"], 21)
    score_font = load_font(["C:/Windows/Fonts/georgiab.ttf", "Georgia Bold", "DejaVuSerif-Bold.ttf"], 52)

    green = (125, 187, 63)
    amber = (246, 166, 25)
    white = (245, 245, 238)
    muted = (172, 170, 205)

    draw.text((168, 66), "THE VAULT ESCAPE", fill=green, font=small_font)
    draw.text((62, 168), f"REVIEW {author.upper()}", fill=muted, font=small_font)
    y = 215
    for line in wrap_lines(draw, name.upper(), title_font, 580, max_lines=3):
        draw.text((62, y), line, fill=white, font=title_font)
        y += 64
    if company:
        draw.text((64, y + 6), company, fill=green, font=meta_font)
        y += 42
    if location:
        draw.text((64, y), location, fill=muted, font=small_font)

    if score:
        draw.rounded_rectangle((62, 478, 270, 560), radius=0, outline=amber, width=2, fill=(22, 19, 17))
        draw.text((84, 478), "NOTA", fill=muted, font=small_font)
        draw.text((84, 492), score, fill=amber, font=score_font)
        draw.text((188, 517), "/10", fill=muted, font=small_font)

    quote_text = short_text(social_text(room.get("descripcion")), 120)
    if quote_text:
        for idx, line in enumerate(wrap_lines(draw, quote_text, small_font, 360, max_lines=3)):
            draw.text((304, 486 + idx * 28), line, fill=(215, 215, 224), font=small_font)

    draw.text((62, 578), "thevaultescape.com", fill=green, font=small_font)
    canvas.save(out_path, "JPEG", quality=88, optimize=True)
    return out_rel.as_posix()


def base_head(title, description, canonical, image):
    return f"""<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{escape(title)}</title>
<meta name="description" content="{escape(description)}">
<meta name="robots" content="index, follow, max-image-preview:large">
<meta name="author" content="{SITE_NAME}">
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
<meta property="og:image:width" content="1200">
<meta property="og:image:height" content="630">
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
  .share {{ margin:18px 0 4px; border:1px solid rgba(125,187,63,.24); background:rgba(125,187,63,.055); padding:13px; }}
  .share strong {{ display:block; color:var(--text); font-family:Georgia,serif; font-size:1.08rem; margin-bottom:4px; }}
  .share span {{ display:block; color:var(--muted); font-size:.9rem; margin-bottom:10px; }}
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
  .btn {{ display:inline-flex; align-items:center; justify-content:center; min-height:42px; padding:9px 13px; border:1px solid rgba(125,187,63,.32); background:rgba(125,187,63,.07); color:var(--green); text-decoration:none; text-transform:uppercase; letter-spacing:.08em; font-size:.78rem; cursor:pointer; }}
  button.btn {{ font-family:inherit; }}
  .btn.secondary {{ border-color:rgba(255,255,255,.12); background:rgba(255,255,255,.025); color:var(--muted); }}
  @media(max-width:720px) {{ .hero {{ grid-template-columns:1fr; padding:16px; }} .cover {{ max-height:360px; }} .cats {{ grid-template-columns:1fr 1fr; }} .wrap {{ width:min(100% - 22px,1020px); padding-top:18px; }} }}
</style>
"""


def review_page(room, photos, social_image_path=""):
    name = canonical_room_name(room) or "Escape room"
    company = canonical_room_company(room)
    slug = room_url_slug(room)
    canonical = site_url(f"/reviews/{slug}/")
    app_link = site_url(f"/#review/{app_hash_key(room)}")
    description = short_description(room)
    image = asset_url(social_image_path or room.get("imagen") or (photos[0].get("src") if photos else DEFAULT_SOCIAL_CARD))
    title = f"Review de {name} | {SITE_NAME}"
    location = room_location(room)
    score = score_label(room.get("valoracion"))
    cover = page_asset(room.get("imagen") or (photos[0].get("src") if photos else DEFAULT_SOCIAL_CARD))
    author = text(room.get("_reviewAuthorName")) or "The Vault"
    date_published = timestamp_iso(room.get("_publishedAt"))
    date_modified = timestamp_iso(room.get("_updatedAt")) or date_published
    share_text = f"Review de {name} en {SITE_NAME} {canonical}"
    whatsapp_link = f"https://wa.me/?text={quote(share_text, safe='')}"
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
                "inLanguage": "es",
                "keywords": ["escape rooms", "review escape room", name, company, text(room.get("ciudad"))],
                "about": {"@type": "Thing", "name": "Escape rooms en España"},
                "isPartOf": {"@id": site_url("/#website")},
                "primaryImageOfPage": image,
            },
            {
                "@type": "Organization",
                "@id": site_url("/#organization"),
                "name": SITE_NAME,
                "url": BASE_URL,
                "logo": site_url("/images/brand/icon-round-512.png"),
                "sameAs": ["https://www.instagram.com/thevault_escape/"],
            },
            {
                "@type": "Review",
                "name": f"Review de {name}",
                "reviewBody": text(room.get("descripcion")),
                "author": {"@type": "Person" if author != "The Vault" else "Organization", "name": author, "url": BASE_URL},
                "publisher": {"@id": site_url("/#organization")},
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
        schema["@graph"][2]["reviewRating"] = {
            "@type": "Rating",
            "ratingValue": score.replace(",", "."),
            "bestRating": "10",
            "worstRating": "0",
        }
    if date_published:
        schema["@graph"][2]["datePublished"] = date_published
    if date_modified:
        schema["@graph"][2]["dateModified"] = date_modified
    article_meta = "\n".join([
        f'<meta property="article:published_time" content="{escape(date_published)}">' if date_published else "",
        f'<meta property="article:modified_time" content="{escape(date_modified)}">' if date_modified else "",
        '<meta property="article:section" content="Escape rooms">',
        '<meta property="article:tag" content="escape rooms">',
        '<meta property="article:tag" content="review escape room">',
        f'<meta property="article:tag" content="{escape(name)}">',
    ])
    return base_head(title, description, canonical, image) + f"""
{article_meta}
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
      <div class="kicker">Review {escape(author)}</div>
      <h1>{escape(name)}</h1>
      <div class="company">{escape(company)}</div>
      <div class="meta">{meta_html}</div>
      {f'<div class="score">Nota The Vault: {escape(score)}/10</div>' if score else ''}
      <p>{escape(description)}</p>
      <div class="share">
        <strong>Comparte esta review</strong>
        <span>Enlace directo preparado para WhatsApp, Instagram, buscadores y vistas previas con imagen.</span>
        <div class="actions">
          <a class="btn" href="{escape(whatsapp_link)}" target="_blank" rel="noopener">Compartir por WhatsApp</a>
          <button class="btn secondary" type="button" onclick="navigator.clipboard?.writeText('{escape(canonical)}')">Copiar enlace</button>
        </div>
      </div>
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


def is_terror_room(item):
    room = item.get("room") or {}
    rating = item.get("rating") or {}
    meta = item.get("meta") or {}
    parts = [
        room.get("nombre"),
        room.get("empresa"),
        room.get("descripcion"),
        room.get("tematica"),
        room.get("tipo"),
        room.get("dificultad"),
    ]
    for source_id in (rating.get("sources") or {}).keys():
        parts.append(source_label(source_id, meta))
    haystack = folded(" ".join(text(part) for part in parts))
    tokens = (
        "terror",
        "horror",
        "miedo",
        "paranormal",
        "exorc",
        "posesion",
        "maldito",
        "maldicion",
        "asylum",
        "haunted",
        "inferno",
        "pesadilla",
    )
    return any(token in haystack for token in tokens)


def ranking_landing_page(slug, title, h1, description, intro, rows, keyword_note, limit=60):
    canonical = site_url(f"/{slug}/")
    image = site_url("/images/brand/social-card.png")
    top_rows = rows[:limit]
    items = []
    list_items = []
    for idx, item in enumerate(top_rows, 1):
        room = item["room"]
        rating = item.get("rating") or {}
        name = canonical_room_name(room) or "Escape room"
        company = canonical_room_company(room)
        url = site_url(f"/salas/{room_url_slug(room)}/")
        score = decimal(rating.get("global_score"))
        sources = int(rating.get("source_count") or 0)
        awards = int(rating.get("award_count") or 0)
        location = room_location(room)
        extra = []
        if location:
            extra.append(location)
        if sources:
            extra.append(f"{sources} fuentes")
        if awards:
            extra.append(f"{awards} premios o nominaciones")
        items.append(
            f'<a class="rank-link" href="{escape(url)}">'
            f'<span class="pos">#{idx}</span>'
            f'<strong>{escape(name)}</strong>'
            f'<span>{escape(company)}{(" - " + escape(" · ".join(extra))) if extra else ""}</span>'
            f'<em>{score:.1f}/10</em></a>'
        )
        list_items.append({"@type": "ListItem", "position": idx, "name": name, "url": url})
    schema = {
        "@context": "https://schema.org",
        "@graph": [
            {
                "@type": "CollectionPage",
                "@id": canonical,
                "url": canonical,
                "name": title,
                "description": description,
                "inLanguage": "es",
                "keywords": keyword_note,
                "isPartOf": {"@id": site_url("/#website")},
                "mainEntity": {"@type": "ItemList", "itemListElement": list_items},
            },
            {
                "@type": "BreadcrumbList",
                "itemListElement": [
                    {"@type": "ListItem", "position": 1, "name": "Inicio", "item": site_url("/")},
                    {"@type": "ListItem", "position": 2, "name": h1, "item": canonical},
                ],
            },
        ],
    }
    return f"""<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{escape(title)}</title>
<meta name="description" content="{escape(description)}">
<meta name="robots" content="index, follow, max-image-preview:large">
<link rel="canonical" href="{escape(canonical)}">
<link rel="icon" href="../images/brand/favicon-round-32.png" sizes="32x32" type="image/png">
<meta property="og:type" content="website">
<meta property="og:site_name" content="{SITE_NAME}">
<meta property="og:title" content="{escape(title)}">
<meta property="og:description" content="{escape(description)}">
<meta property="og:url" content="{escape(canonical)}">
<meta property="og:image" content="{escape(image)}">
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:title" content="{escape(title)}">
<meta name="twitter:description" content="{escape(description)}">
<meta name="twitter:image" content="{escape(image)}">
<script type="application/ld+json">
{json_ld(schema)}
</script>
<style>
  :root{{--bg:#0a0a0f;--card:#12121e;--border:#2a2a45;--green:#7dbb3f;--amber:#ffa91f;--text:#f0f0ea;--muted:#9a9ab6;}}
  *{{box-sizing:border-box;}}
  body{{margin:0;background:radial-gradient(ellipse at top,rgba(125,187,63,.14),transparent 38%),var(--bg);color:var(--text);font-family:Arial,Helvetica,sans-serif;line-height:1.55;}}
  main{{width:min(1040px,calc(100% - 32px));margin:0 auto;padding:32px 0 54px;}}
  a{{color:var(--green);}}
  .brand{{display:flex;align-items:center;gap:12px;text-decoration:none;text-transform:uppercase;letter-spacing:.12em;color:var(--muted);font-size:.72rem;margin-bottom:24px;}}
  .brand img{{width:42px;height:42px;border-radius:50%;}}
  .hero{{border:1px solid rgba(125,187,63,.25);background:linear-gradient(135deg,rgba(255,255,255,.035),rgba(125,187,63,.04));padding:22px;margin-bottom:18px;}}
  .kicker{{color:var(--amber);text-transform:uppercase;letter-spacing:.16em;font-size:.72rem;margin-bottom:8px;}}
  h1{{font-family:Georgia,serif;font-size:clamp(2rem,5vw,3.5rem);line-height:1.05;margin:0 0 12px;}}
  p{{color:#b8b8c8;line-height:1.65;max-width:880px;}}
  .nav{{display:flex;gap:9px;flex-wrap:wrap;margin-top:16px;}}
  .nav a{{border:1px solid rgba(125,187,63,.25);background:rgba(125,187,63,.055);padding:8px 11px;text-decoration:none;text-transform:uppercase;letter-spacing:.08em;font-size:.74rem;}}
  .list{{display:grid;gap:10px;margin-top:24px;}}
  .rank-link{{display:grid;grid-template-columns:56px minmax(0,1fr) auto;gap:8px 12px;align-items:center;border:1px solid rgba(125,187,63,.2);background:rgba(255,255,255,.025);padding:13px;text-decoration:none;}}
  .pos{{grid-row:1/3;color:var(--green);font-weight:700;font-size:1.1rem;}}
  .rank-link strong{{color:var(--text);font-family:Georgia,serif;font-size:1.15rem;}}
  .rank-link span:not(.pos){{color:var(--muted);}}
  .rank-link em{{grid-column:3;grid-row:1/3;color:var(--amber);font-style:normal;font-weight:700;white-space:nowrap;}}
  .note{{margin-top:22px;border-top:1px solid rgba(255,255,255,.08);padding-top:16px;color:var(--muted);font-size:.92rem;}}
  @media(max-width:680px){{main{{width:min(100% - 22px,1040px);padding-top:20px;}}.hero{{padding:16px;}}.rank-link{{grid-template-columns:44px minmax(0,1fr);}}.rank-link em{{grid-column:2;grid-row:auto;}}}}
</style>
</head>
<body>
<main>
  <a class="brand" href="../"><img src="../images/brand/icon-round-192.png" alt="">The Vault Escape</a>
  <section class="hero">
    <div class="kicker">The Vault Escape</div>
    <h1>{escape(h1)}</h1>
    <p>{escape(intro)}</p>
    <div class="nav">
      <a href="../ranking/">Ranking completo</a>
      <a href="../reviews/">Reviews</a>
      <a href="../mejores-escape-rooms/">Mejores escape rooms</a>
      <a href="../mejores-escape-rooms-terror/">Terror</a>
      <a href="../">Abrir web</a>
    </div>
  </section>
  <div class="list">
    {''.join(items)}
  </div>
  <p class="note">{escape(keyword_note)}</p>
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
    rating = item.get("rating") or {}
    meta = item.get("meta") or {}
    name = canonical_room_name(room) or "Escape room"
    company = canonical_room_company(room)
    slug = room_url_slug(room)
    canonical = site_url(f"/salas/{slug}/")
    app_link = site_url(f"/#room/{app_hash_key(room)}")
    score = decimal(rating.get("global_score"))
    has_score = score > 0
    description = short_description({
        **room,
        "descripcion": text(room.get("descripcion")) or (
            f"{name} forma parte del catálogo de The Vault Escape con datos de ubicación, empresa y ficha pública para consulta."
        ),
    })
    image = asset_url(room.get("imagen") or "images/brand/social-card.png")
    cover = page_asset(room.get("imagen") or "images/brand/social-card.png")
    title = f"{name}: ranking y puntuaciones | {SITE_NAME}" if has_score else f"{name}: ficha de escape room | {SITE_NAME}"
    location = room_location(room)
    meta_values = [
        location,
        text(room.get("tematica")),
        text(room.get("tipo")),
        f'{text(room.get("duracion"))} min' if text(room.get("duracion")) else "",
        text(room.get("dificultad")),
    ]
    meta_html = "\n".join(f'<span class="pill">{escape(value)}</span>' for value in meta_values if value)
    sources_html = source_pills(rating, meta) if has_score else ""
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
    if has_score:
        schema["@graph"][1]["aggregateRating"] = {
            "@type": "AggregateRating",
            "ratingValue": f"{score:.1f}",
            "bestRating": "10",
            "worstRating": "0",
            "ratingCount": max(1, int(rating.get("source_count") or 1)),
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
      <div class="kicker">{f'Sala destacada #{position}' if has_score else 'Ficha de catálogo'}</div>
      <h1>{escape(name)}</h1>
      <div class="company">{escape(company)}</div>
      <div class="meta">{meta_html}</div>
      {f'<div class="score">Nota global: {score:.1f}/10</div>' if has_score else ''}
      <p>{escape(description)}</p>
      <div class="actions">
        <a class="btn" href="{escape(app_link)}">Abrir ficha interactiva</a>
        {f'<a class="btn secondary" href="../../ranking/">Ver ranking completo</a>' if has_score else '<a class="btn secondary" href="../../">Ver catálogo</a>'}
      </div>
    </div>
  </article>
  {f'''<section class="section">
    <h2>Fuentes del ranking</h2>
    <div class="meta">{sources_html}</div>
  </section>''' if sources_html else ''}
  {f'<section class="section"><h2>Sinopsis</h2><div class="review">{escape(text(room.get("descripcion")))}</div></section>' if text(room.get("descripcion")) else ''}
</main>
</body>
</html>
"""


def sitemap_xml(review_rooms, sala_rows):
    entries = [
        (site_url("/"), "daily", "1.0"),
        (site_url("/reviews/"), "weekly", "0.8"),
        (site_url("/ranking/"), "weekly", "0.9"),
        (site_url("/ranking-escape-rooms/"), "weekly", "0.95"),
        (site_url("/mejores-escape-rooms/"), "weekly", "0.95"),
        (site_url("/mejores-escape-rooms-terror/"), "weekly", "0.9"),
    ]
    entries.extend((site_url(f"/reviews/{room_url_slug(room)}/"), "monthly", "0.7") for room in review_rooms)
    entries.extend((site_url(f"/salas/{room_url_slug(item['room'])}/"), "monthly", "0.7") for item in sala_rows)
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


def llms_txt():
    return f"""# {SITE_NAME}

The Vault Escape es un catálogo y archivo de escape rooms en España. Incluye fichas de salas, reviews propias, ranking ponderado con varias fuentes, premios, fotos y herramientas personales para usuarios registrados.

## URLs principales
- Inicio y aplicación interactiva: {site_url('/')}
- Reviews publicadas: {site_url('/reviews/')}
- Ranking de escape rooms: {site_url('/ranking/')}
- Landing SEO ranking escape rooms España: {site_url('/ranking-escape-rooms/')}
- Landing SEO mejores escape rooms España: {site_url('/mejores-escape-rooms/')}
- Landing SEO mejores escape rooms de terror: {site_url('/mejores-escape-rooms-terror/')}
- Sitemap XML: {site_url('/sitemap.xml')}

## Contenido
- Fichas públicas en /salas/{{slug}}/ con nombre, empresa, ubicación, sinopsis cuando existe y puntuaciones si están disponibles.
- Reviews públicas en /reviews/{{slug}}/ con opinión del grupo, puntuaciones por categorías, fotos y enlaces para compartir.
- Ranking calculado con fuentes externas, comunidad The Vault y premios, descrito en las páginas legales de la web.

## Contacto
Instagram: https://www.instagram.com/thevault_escape/
Web: {BASE_URL}
"""


def main():
    data = read_json(ROOT / "data.json", {})
    photos_data = read_json(ROOT / "review_photos.json", {}).get("photos", {})
    rooms = published_review_rooms(data) or review_rooms(data)
    ranking_rows = [row for row in ranked_rooms(data) if decimal(row["rating"].get("global_score")) > 0]
    sala_rows = catalog_seo_rows(data, ranking_rows)

    reviews_dir = ROOT / "reviews"
    reviews_dir.mkdir(exist_ok=True)
    generated_review_pages = []
    for room in rooms:
        slug = room_url_slug(room)
        page_dir = reviews_dir / slug
        page_dir.mkdir(parents=True, exist_ok=True)
        photos = photo_entries(room, photos_data)
        social_card = generate_review_social_card(room, photos)
        (page_dir / "index.html").write_text(review_page(room, photos, social_card), encoding="utf-8", newline="\n")
        generated_review_pages.append(slug)

    (reviews_dir / "index.html").write_text(reviews_index_page(rooms), encoding="utf-8", newline="\n")
    ranking_dir = ROOT / "ranking"
    ranking_dir.mkdir(exist_ok=True)
    (ranking_dir / "index.html").write_text(ranking_index_page(ranking_rows), encoding="utf-8", newline="\n")

    landing_pages = [
        (
            "ranking-escape-rooms",
            f"Ranking escape rooms España | {SITE_NAME}",
            "Ranking de escape rooms en España",
            "Ranking escape rooms España con puntuaciones ponderadas, fuentes externas, reviews The Vault, premios y comunidad.",
            "Consulta un ranking de escape rooms en España calculado con varias señales: puntuaciones externas, reviews The Vault, votos de comunidad y premios o nominaciones. La intención es ayudarte a descubrir salas destacadas con más contexto que una nota aislada.",
            ranking_rows,
            "Ranking orientativo de escape rooms en España. The Vault Escape combina varias fuentes disponibles, reviews propias, comunidad y premios para evitar que una única puntuación aislada domine el resultado.",
        ),
        (
            "mejores-escape-rooms",
            f"Mejores escape rooms de España | {SITE_NAME}",
            "Mejores escape rooms de España",
            "Selección de mejores escape rooms de España según ranking ponderado, premios, reviews y fuentes contrastadas.",
            "Explora una selección de los mejores escape rooms de España con fichas enlazadas, ubicación, empresa y nota global. Esta página está pensada para búsquedas generales y para compartir una referencia rápida antes de elegir próxima sala.",
            ranking_rows,
            "Selección basada en el ranking global de The Vault Escape. Las posiciones pueden variar cuando se actualizan nuevas fuentes, premios, reviews o votos de comunidad.",
        ),
        (
            "mejores-escape-rooms-terror",
            f"Mejores escape rooms de terror en España | {SITE_NAME}",
            "Mejores escape rooms de terror en España",
            "Ranking de mejores escape rooms de terror y miedo en España con fuentes externas, premios y reviews The Vault.",
            "Si buscas terror, miedo o experiencias oscuras, esta selección filtra las salas con señales de terror dentro del ranking global y prioriza las que tienen varias fuentes, premios o reviews.",
            [item for item in ranking_rows if is_terror_room(item)],
            "Ranking orientativo de escape rooms de terror en España. El filtro usa temática, descripciones, fuentes de puntuación y premios relacionados con terror, horror o miedo.",
        ),
    ]
    for slug, title, h1, description, intro, rows, note in landing_pages:
        page_dir = ROOT / slug
        page_dir.mkdir(exist_ok=True)
        (page_dir / "index.html").write_text(
            ranking_landing_page(slug, title, h1, description, intro, rows, note),
            encoding="utf-8",
            newline="\n",
        )

    salas_dir = ROOT / "salas"
    salas_dir.mkdir(exist_ok=True)
    for item in sala_rows:
        page_dir = salas_dir / room_url_slug(item["room"])
        page_dir.mkdir(parents=True, exist_ok=True)
        (page_dir / "index.html").write_text(room_page(item, item.get("position") or 0), encoding="utf-8", newline="\n")

    (ROOT / "sitemap.xml").write_text(sitemap_xml(rooms, sala_rows), encoding="utf-8", newline="\n")
    (ROOT / "robots.txt").write_text(robots_txt(), encoding="utf-8", newline="\n")
    (ROOT / "llms.txt").write_text(llms_txt(), encoding="utf-8", newline="\n")
    print(
        "SEO generado: "
        f"{len(generated_review_pages)} reviews, "
        f"{len(sala_rows)} salas, "
        f"{len(generated_review_pages)} tarjetas sociales, "
        "ranking, landings SEO, sitemap.xml, robots.txt y llms.txt"
    )


if __name__ == "__main__":
    main()
