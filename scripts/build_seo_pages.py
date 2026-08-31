import argparse
import json
import re
import shutil
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
LATEST_REVIEW_THUMB_DIR = Path("images/seo/latest")
CITY_PAGE_MIN_ROOMS = 8
REGION_PAGE_MIN_ROOMS = 10
ROOM_LOCATIONS_CACHE = None
SEO_ROOM_SLUGS = {}

SEO_STYLES = """
:root {
  --bg: #0a0a0f;
  --bg2: #0f0f18;
  --bg3: #141422;
  --card: #12121e;
  --border: #2a2a45;
  --green: #7dbb3f;
  --green-dark: #5f9f32;
  --gold: #f0f0ea;
  --text: #e8e8f0;
  --text2: #9090b0;
  --text3: #5a5a80;
}
* { box-sizing: border-box; }
html { color-scheme: dark; scroll-behavior: smooth; }
body {
  margin: 0;
  min-height: 100vh;
  overflow-x: hidden;
  background: var(--bg);
  color: var(--text);
  font-family: 'Rajdhani', sans-serif;
  font-size: 17px;
  line-height: 1.55;
}
body::before {
  content: '';
  position: fixed;
  inset: 0;
  z-index: -1;
  pointer-events: none;
  opacity: .25;
  background-image: url("data:image/svg+xml,%3Csvg viewBox='0 0 256 256' xmlns='http://www.w3.org/2000/svg'%3E%3Cfilter id='n'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='.9' numOctaves='4' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23n)' opacity='.04'/%3E%3C/svg%3E");
}
a { color: var(--green); }
img { max-width: 100%; }
.skip-link { position: fixed; left: 12px; top: -80px; z-index: 100; background: var(--green); color: #081005; padding: 9px 12px; text-decoration: none; }
.skip-link:focus { top: 12px; }
.site-header { border-bottom: 1px solid var(--border); background: rgba(10,10,15,.97); }
.site-header-inner {
  width: min(1180px, calc(100% - 40px));
  min-height: 78px;
  margin: 0 auto;
  display: grid;
  grid-template-columns: minmax(190px, 1fr) auto auto;
  align-items: center;
  gap: 24px;
}
.site-brand { display: inline-flex; align-items: center; width: fit-content; text-decoration: none; }
.site-brand img { display: block; width: 228px; height: auto; }
.site-nav { display: flex; align-items: stretch; gap: 4px; }
.site-nav a,
.site-app-link {
  min-height: 38px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border: 1px solid transparent;
  padding: 7px 10px;
  color: var(--text2);
  font-family: 'Share Tech Mono', monospace;
  font-size: .68rem;
  letter-spacing: .08em;
  text-decoration: none;
  text-transform: uppercase;
}
.site-nav a:hover,
.site-nav a:focus-visible,
.site-nav a[aria-current='page'] { border-color: rgba(125,187,63,.34); color: var(--green); background: rgba(125,187,63,.06); }
.site-app-link { border-color: rgba(125,187,63,.4); color: var(--green); background: rgba(125,187,63,.07); }
.seo-main,
.wrap { width: min(1120px, calc(100% - 40px)); margin: 0 auto; padding: 38px 0 60px; }
.page-intro { padding: 8px 0 24px; border-bottom: 1px solid var(--border); }
.kicker,
.updated {
  color: var(--green);
  font-family: 'Share Tech Mono', monospace;
  font-size: .68rem;
  letter-spacing: .15em;
  text-transform: uppercase;
}
h1, h2, h3, .rank-link strong, .review-link strong, .location-link strong {
  font-family: 'Cinzel', serif;
  letter-spacing: 0;
}
h1 { margin: 8px 0 12px; color: var(--gold); font-size: clamp(2rem, 5vw, 3.7rem); line-height: 1.05; }
h2 { margin: 0 0 12px; color: var(--gold); font-size: 1.35rem; }
p { color: var(--text2); }
.lead { max-width: 900px; margin: 0; font-size: 1.08rem; }
.detail-hero { display: grid; grid-template-columns: minmax(220px, 360px) minmax(0, 1fr); gap: 30px; align-items: start; }
.cover { width: 100%; max-height: 540px; object-fit: contain; background: #050507; border: 1px solid rgba(255,255,255,.09); }
.company { color: var(--text3); font-family: 'Share Tech Mono', monospace; font-size: .72rem; letter-spacing: .1em; text-transform: uppercase; }
.meta, .summary, .nav, .actions, .internal-links { display: flex; flex-wrap: wrap; gap: 8px; }
.meta { margin: 18px 0; }
.pill, .summary span { border: 1px solid rgba(125,187,63,.24); background: rgba(125,187,63,.055); color: #cde3bc; padding: 5px 8px; font-size: .86rem; }
.score { display: inline-flex; margin: 8px 0 14px; border: 1px solid rgba(125,187,63,.4); background: rgba(125,187,63,.08); color: var(--green); padding: 8px 12px; font-family: 'Cinzel', serif; font-weight: 700; }
.section { margin-top: 24px; border-top: 1px solid var(--border); padding: 20px 0 0; }
.review { color: #cfcfdb; white-space: pre-line; }
.cats { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 10px; }
.cat, .fact { border: 1px solid rgba(255,255,255,.08); background: var(--bg2); padding: 11px; }
.cat span, .fact dt { display: block; color: var(--text3); font-family: 'Share Tech Mono', monospace; font-size: .62rem; letter-spacing: .08em; text-transform: uppercase; }
.cat strong { color: var(--green); font-size: 1.25rem; }
.facts { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 10px; margin: 0; }
.fact { min-width: 0; }
.fact dd { margin: 4px 0 0; color: var(--text); overflow-wrap: anywhere; }
.photos { display: grid; grid-template-columns: repeat(auto-fill, minmax(170px, 1fr)); gap: 10px; }
.photos img { width: 100%; aspect-ratio: 4/3; object-fit: cover; border: 1px solid rgba(125,187,63,.22); background: #050507; }
.video-frame { width: 100%; aspect-ratio: 16/9; display: block; border: 1px solid rgba(125,187,63,.24); background: #050507; }
.media-note, .note, .explain { color: var(--text2); }
.share, .method { margin-top: 20px; border-left: 2px solid var(--green); background: rgba(125,187,63,.035); padding: 14px 16px; }
.share strong { display: block; color: var(--gold); font-family: 'Cinzel', serif; }
.share span { display: block; color: var(--text2); margin: 4px 0 10px; }
.actions { margin-top: 18px; }
.btn, .nav a {
  min-height: 40px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border: 1px solid rgba(125,187,63,.34);
  background: rgba(125,187,63,.065);
  color: var(--green);
  padding: 8px 12px;
  font-family: 'Share Tech Mono', monospace;
  font-size: .68rem;
  letter-spacing: .08em;
  text-decoration: none;
  text-transform: uppercase;
  cursor: pointer;
}
.btn.secondary { border-color: rgba(255,255,255,.12); background: rgba(255,255,255,.025); color: var(--text2); }
.list { display: grid; gap: 9px; margin-top: 24px; }
.rank-link {
  display: grid;
  grid-template-columns: 56px minmax(0, 1fr) auto;
  gap: 6px 12px;
  align-items: center;
  border: 1px solid rgba(255,255,255,.08);
  background: var(--bg2);
  padding: 13px;
  text-decoration: none;
}
.rank-link:hover, .review-link:hover, .location-link:hover { border-color: rgba(125,187,63,.4); background: rgba(125,187,63,.045); }
.rank-link .pos { grid-row: 1/3; color: var(--green); font-family: 'Share Tech Mono', monospace; font-weight: 700; }
.rank-link strong { color: var(--gold); font-size: 1.02rem; }
.rank-link span:not(.pos) { color: var(--text2); }
.rank-link em { grid-column: 3; grid-row: 1/3; color: var(--green); font-style: normal; font-weight: 700; white-space: nowrap; }
.review-link { display: block; border: 1px solid rgba(255,255,255,.08); background: var(--bg2); padding: 14px; text-decoration: none; }
.review-link strong { display: block; color: var(--gold); font-size: 1.05rem; }
.review-link span { display: block; color: var(--text2); margin-top: 3px; }
.summary { margin-top: 16px; }
.method h2, .faq h2 { margin-top: 0; }
.faq { margin-top: 26px; }
.faq details { border-top: 1px solid rgba(255,255,255,.1); padding: 12px 0; }
.faq summary { color: var(--text); font-weight: 700; cursor: pointer; }
.grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(220px, 1fr)); gap: 10px; }
.section-label { margin: 30px 0 12px; color: var(--green); font-family: 'Share Tech Mono', monospace; font-size: .68rem; letter-spacing: .14em; text-transform: uppercase; }
.location-link { display: flex; justify-content: space-between; gap: 10px; align-items: center; border: 1px solid rgba(255,255,255,.08); background: var(--bg2); padding: 12px; color: var(--text); text-decoration: none; }
.location-link span { color: var(--text2); font-size: .82rem; white-space: nowrap; }
.site-footer { border-top: 1px solid var(--border); background: var(--bg2); }
.site-footer-inner { width: min(1180px, calc(100% - 40px)); margin: 0 auto; padding: 24px 0 30px; display: flex; justify-content: space-between; gap: 22px; align-items: center; }
.site-footer strong { display: block; color: var(--gold); font-family: 'Cinzel', serif; }
.site-footer span { display: block; color: var(--text3); font-family: 'Share Tech Mono', monospace; font-size: .62rem; letter-spacing: .06em; text-transform: uppercase; }
.footer-links { display: flex; flex-wrap: wrap; justify-content: flex-end; gap: 12px; }
.footer-links a { color: var(--text2); font-family: 'Share Tech Mono', monospace; font-size: .62rem; letter-spacing: .06em; text-decoration: none; text-transform: uppercase; }
@media (max-width: 860px) {
  .site-header-inner { grid-template-columns: 1fr auto; gap: 12px; padding: 12px 0; }
  .site-brand img { width: 190px; }
  .site-nav { grid-column: 1/-1; overflow-x: auto; padding-top: 2px; }
  .site-nav a { flex: 0 0 auto; }
  .detail-hero { grid-template-columns: 1fr; }
  .cover { max-height: 430px; }
  .facts { grid-template-columns: 1fr 1fr; }
}
@media (max-width: 620px) {
  body { font-size: 16px; }
  .site-header-inner, .seo-main, .wrap, .site-footer-inner { width: min(100% - 24px, 1120px); }
  .site-header-inner { display: flex; flex-wrap: wrap; }
  .site-brand { flex: 1; }
  .site-brand img { width: 168px; }
  .site-app-link { min-height: 34px; padding: 6px 8px; }
  .site-nav { width: 100%; order: 3; }
  .seo-main, .wrap { padding-top: 24px; }
  .cats, .facts { grid-template-columns: 1fr 1fr; }
  .rank-link { grid-template-columns: 42px minmax(0, 1fr); }
  .rank-link em { grid-column: 2; grid-row: auto; }
  .site-footer-inner { align-items: flex-start; flex-direction: column; }
  .footer-links { justify-content: flex-start; }
}
@media (max-width: 420px) {
  .facts { grid-template-columns: 1fr; }
}
"""

TEXT_FIXES = {
    "Espa�a": "España",
    "M�laga": "Málaga",
    "Matar�": "Mataró",
    "Gij�n": "Gijón",
    "Pa�s Vasco": "País Vasco",
    "Arag�n": "Aragón",
    "Andaluc�a": "Andalucía",
    "Regi�n de Murcia": "Región de Murcia",
    "Castell�n": "Castellón",
    "Coru�a": "Coruña",
    "C�diz": "Cádiz",
    "C�rdoba": "Córdoba",
    "Le�n": "León",
    "Ja�n": "Jaén",
}


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


def room_locations():
    global ROOM_LOCATIONS_CACHE
    if ROOM_LOCATIONS_CACHE is None:
        payload = read_json(ROOT / "room_locations.json", {})
        ROOM_LOCATIONS_CACHE = payload.get("locations") or {}
    return ROOM_LOCATIONS_CACHE


def exact_room_location(room):
    locations = room_locations()
    candidates = []
    for value in (room.get("id"), room_identity(room), room_url_slug(room), *room_alias_keys(room)):
        raw = text(value)
        if raw:
            candidates.extend((raw, slugify(raw), slugify(raw, "_")))
    for key in dict.fromkeys(candidates):
        location = locations.get(key)
        if location:
            return location
    return {}


def app_hash_key(room):
    return slugify(canonical_room_name(room), "_").replace("_", "-")


def text(value):
    return str(value or "").strip()


def folded(value):
    value = unicodedata.normalize("NFD", text(value).lower())
    return "".join(ch for ch in value if unicodedata.category(ch) != "Mn")


def clean_text(value):
    value = text(value)
    for bad, good in TEXT_FIXES.items():
        value = value.replace(bad, good)
    return value


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
    return " - ".join(part for part in [clean_text(room.get("ciudad")), clean_text(room.get("provincia"))] if part)


def photo_entries(room, photos_data):
    for key in room_alias_keys(room):
        entry = photos_data.get(key, {})
        if entry.get("photos"):
            return entry.get("photos") or []
    return []


def video_entry(room, videos_data):
    candidates = []
    for value in (room.get("id"), room_identity(room), room_url_slug(room), *room_alias_keys(room)):
        raw = text(value)
        if raw:
            candidates.extend((raw, slugify(raw), slugify(raw, "_")))
    for key in dict.fromkeys(candidates):
        video = videos_data.get(key)
        if video:
            return video
    return {}


def room_identity(room):
    return canonical_room_identity(room.get("id") or room.get("nombre"))


def room_url_slug(room):
    return slugify(canonical_room_name(room))


def seo_room_url_slug(room):
    return SEO_ROOM_SLUGS.get(room_identity(room), room_url_slug(room))


def assign_seo_room_slugs(rows):
    SEO_ROOM_SLUGS.clear()
    groups = {}
    for item in rows:
        room = item.get("room") or {}
        groups.setdefault(room_url_slug(room), []).append(item)

    used = set()
    for base_slug, items in groups.items():
        ordered = sorted(
            items,
            key=lambda item: (
                item.get("position") is None,
                item.get("position") or 10**9,
                room_identity(item.get("room") or {}),
            ),
        )
        for index, item in enumerate(ordered):
            room = item.get("room") or {}
            identity = room_identity(room)
            if index == 0:
                candidate = base_slug
            else:
                suffixes = [
                    canonical_room_company(room),
                    room.get("ciudad"),
                    room.get("id"),
                    identity,
                ]
                candidate = ""
                for suffix in suffixes:
                    value = slugify(suffix)
                    if value and value != base_slug:
                        candidate = f"{base_slug}-{value}"
                        if candidate not in used:
                            break
                if not candidate or candidate in used:
                    candidate = f"{base_slug}-{index + 1}"
            serial = 2
            unique = candidate
            while unique in used:
                unique = f"{candidate}-{serial}"
                serial += 1
            SEO_ROOM_SLUGS[identity] = unique
            used.add(unique)


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
    canvas.save(out_path, "JPEG", quality=82, optimize=True)
    return out_rel.as_posix()


def generate_latest_review_thumbnail(room, photos):
    if Image is None:
        return ""
    slugs = []
    for value in [
        canonical_room_name(room),
        room.get("nombre"),
        room.get("id"),
        room.get("_reviewKey"),
        room.get("roomKey"),
    ]:
        slug = slugify(value)
        if slug and slug not in slugs:
            slugs.append(slug)
    if not slugs:
        return ""

    candidates = [
        room.get("imagen"),
        *((photo.get("src") for photo in photos if photo.get("src")) if photos else []),
        DEFAULT_SOCIAL_CARD,
    ]
    source_path = None
    for candidate in candidates:
        source_path = local_asset_path(candidate)
        if source_path:
            break
    if not source_path:
        return ""

    image = safe_open_image(source_path)
    if not image:
        return ""
    try:
        thumb = cover_resize(image, (124, 166))
        for slug in slugs:
            out_rel = LATEST_REVIEW_THUMB_DIR / f"{slug}.webp"
            out_path = ROOT / out_rel
            out_path.parent.mkdir(parents=True, exist_ok=True)
            thumb.save(out_path, "WEBP", quality=68, method=6)
    finally:
        image.close()
    return (LATEST_REVIEW_THUMB_DIR / f"{slugs[0]}.webp").as_posix()


def seo_header(active=""):
    links = [
        ("catalog", "/escape-rooms/", "Catálogo"),
        ("reviews", "/reviews/", "Reviews"),
        ("ranking", "/ranking-escape-rooms/", "Ranking"),
        ("terror", "/mejores-escape-rooms-terror/", "Terror"),
    ]
    nav_items = []
    for key, href, label in links:
        current = ' aria-current="page"' if key == active else ""
        nav_items.append(f'<a href="{href}"{current}>{label}</a>')
    nav = "".join(nav_items)
    return f"""
<a class="skip-link" href="#contenido">Saltar al contenido</a>
<header class="site-header">
  <div class="site-header-inner">
    <a class="site-brand" href="/" aria-label="The Vault Escape - Inicio">
      <img src="/images/brand/the-vault-wordmark-wide.webp" alt="The Vault Escape" width="1000" height="206">
    </a>
    <nav class="site-nav" aria-label="Navegación principal">{nav}</nav>
    <a class="site-app-link" href="/">Abrir The Vault</a>
  </div>
</header>
"""


def seo_footer():
    return """
<footer class="site-footer">
  <div class="site-footer-inner">
    <div><strong>The Vault Escape</strong><span>Escape Room Chronicles</span></div>
    <nav class="footer-links" aria-label="Enlaces legales">
      <a href="/aviso-legal/">Aviso legal</a>
      <a href="/privacidad/">Privacidad</a>
      <a href="/escape-rooms/">Escape rooms por zona</a>
      <a href="https://www.instagram.com/thevault_escape/" target="_blank" rel="noopener">Instagram</a>
    </nav>
  </div>
</footer>
"""


def legacy_seo_page(name, canonical, target="", retired=False):
    if retired:
        title = f"{name}: sala cerrada | {SITE_NAME}"
        description = f"La ficha de {name} se ha retirado del catálogo público porque la sala está cerrada."
        message = "Esta sala está cerrada y su ficha ya no forma parte del catálogo público."
        action_label = "Explorar el catálogo actual"
        action_url = site_url("/escape-rooms/")
        redirect_meta = ""
    else:
        title = f"{name}: nueva dirección | {SITE_NAME}"
        description = f"La ficha de {name} se ha unificado y ahora está disponible en una única dirección."
        message = "Esta ficha se ha unificado para evitar contenido duplicado. Te llevamos a su dirección actual."
        action_label = "Abrir la ficha actual"
        action_url = target
        redirect_meta = f'<meta http-equiv="refresh" content="0; url={escape(target)}">'
    return base_head(
        title,
        description,
        canonical,
        site_url("/images/brand/social-card.png"),
        "website",
        "noindex, follow",
    ) + f"""
{redirect_meta}
</head>
<body>
{seo_header("catalog")}
<main class="seo-main" id="contenido">
  <section class="page-intro">
    <div class="kicker">Catálogo The Vault</div>
    <h1>{escape(name)}</h1>
    <p class="lead">{escape(message)}</p>
    <div class="actions"><a class="btn" href="{escape(action_url)}">{escape(action_label)}</a></div>
  </section>
</main>
{seo_footer()}
</body>
</html>
"""


def base_head(title, description, canonical, image, og_type="article", robots="index, follow, max-image-preview:large"):
    return f"""<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{escape(title)}</title>
<meta name="description" content="{escape(description)}">
<meta name="robots" content="{escape(robots)}">
<meta name="author" content="{SITE_NAME}">
<link rel="canonical" href="{escape(canonical)}">
<meta name="theme-color" content="#0a0a0f">
<link rel="icon" href="/images/brand/favicon-round-32.png" sizes="32x32" type="image/png">
<link rel="apple-touch-icon" href="/images/brand/apple-touch-icon-round.png">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Cinzel:wght@400;600;700;900&family=Rajdhani:wght@400;500;600;700&family=Share+Tech+Mono&display=swap" rel="stylesheet">
<link rel="stylesheet" href="/seo.css">
<meta property="og:type" content="{escape(og_type)}">
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
"""


def review_page(room, photos, social_image_path=""):
    name = canonical_room_name(room) or "Escape room"
    company = canonical_room_company(room)
    slug = room_url_slug(room)
    canonical = site_url(f"/reviews/{slug}/")
    app_link = site_url(f"/#review/{app_hash_key(room)}")
    room_link = site_url(f"/salas/{seo_room_url_slug(room)}/")
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
{seo_header("reviews")}
<main class="wrap" id="contenido">
  <article class="detail-hero">
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
        <a class="btn secondary" href="{escape(room_link)}">Datos y puntuaciones</a>
        <a class="btn secondary" href="../">Todas las reviews</a>
        <a class="btn secondary" href="../../ranking-escape-rooms/">Ver ranking</a>
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
{seo_footer()}
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
    return base_head(title, description, canonical, image, "website") + f"""
<script type="application/ld+json">
{json_ld(schema)}
</script>
</head>
<body>
{seo_header("reviews")}
<main class="seo-main" id="contenido">
  <section class="page-intro">
    <div class="kicker">The Vault Escape</div>
    <h1>Reviews de escape rooms</h1>
    <p class="lead">Opiniones del grupo The Vault Escape sobre salas jugadas, con puntuaciones, fotos y enlaces a la ficha interactiva.</p>
  </section>
  <div class="list">
    {''.join(items)}
  </div>
</main>
{seo_footer()}
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
        url = site_url(f"/salas/{seo_room_url_slug(room)}/")
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
    return base_head(title, description, canonical, image, "website") + f"""
<script type="application/ld+json">
{json_ld(schema)}
</script>
</head>
<body>
{seo_header("ranking")}
<main class="seo-main" id="contenido">
  <section class="page-intro">
    <div class="kicker">Ranking The Vault</div>
    <h1>Ranking de escape rooms en España</h1>
    <p class="lead">Ranking ponderado con fuentes externas, comunidad y premios. Consulta las salas destacadas y abre cada ficha para ver sus puntuaciones y fuentes.</p>
  </section>
  <div class="list">
    {''.join(items)}
  </div>
</main>
{seo_footer()}
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
    page_limits = {
        "ranking-escape-rooms": 100,
        "mejores-escape-rooms": 30,
        "mejores-escape-rooms-terror": 40,
    }
    top_rows = rows[: page_limits.get(slug, limit)]
    faq_by_slug = {
        "ranking-escape-rooms": [
            ("¿Cómo se calcula el ranking de escape rooms?", "La clasificación combina puntuaciones de varias fuentes, reviews de The Vault, votos de la comunidad y premios o nominaciones. También se valora disponer de varias fuentes para reducir el peso de una única nota aislada."),
            ("¿Cada cuánto se actualiza el ranking?", "El ranking se regenera cuando se incorporan nuevas puntuaciones, reviews, premios o salas al catálogo. Por eso las posiciones pueden cambiar con el tiempo."),
            ("¿Una nota alta garantiza que sea la mejor sala para mí?", "No. El ranking es una referencia comparativa. La temática, el terror, la dificultad, la ubicación y el tamaño del grupo también influyen en la elección."),
        ],
        "mejores-escape-rooms": [
            ("¿Qué significa mejores escape rooms en esta selección?", "Son salas destacadas dentro del ranking ponderado de The Vault por sus puntuaciones, variedad de fuentes, premios y opiniones disponibles. No es una selección comercial ni implica pago por aparecer."),
            ("¿Cómo elegir un escape room de la lista?", "Además de la nota, conviene revisar la ciudad, la temática, el número de jugadores, la dificultad y las reviews enlazadas en cada ficha."),
            ("¿La selección incluye salas de toda España?", "Sí. El catálogo reúne escape rooms de distintas comunidades y ciudades españolas cuando existe información suficiente para construir su ficha."),
        ],
        "mejores-escape-rooms-terror": [
            ("¿Qué salas aparecen en el ranking de terror?", "Aparecen experiencias identificadas como terror, horror o miedo y que cuentan con puntuaciones, premios o reviews suficientes para formar parte de la clasificación."),
            ("¿Todas las salas tienen la misma intensidad de miedo?", "No. Algunas se centran en tensión y ambientación, mientras otras incluyen actores, persecuciones o terror intenso. Revisa la ficha y la web oficial antes de reservar."),
            ("¿El ranking de terror se calcula de forma distinta?", "Parte del mismo sistema ponderado del ranking general, pero se limita a salas cuya temática o experiencia está relacionada con terror y miedo."),
        ],
    }
    faqs = faq_by_slug.get(slug, [])
    items = []
    list_items = []
    for idx, item in enumerate(top_rows, 1):
        room = item["room"]
        rating = item.get("rating") or {}
        name = canonical_room_name(room) or "Escape room"
        company = canonical_room_company(room)
        url = site_url(f"/salas/{seo_room_url_slug(room)}/")
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
    if faqs:
        schema["@graph"].append({
            "@type": "FAQPage",
            "mainEntity": [
                {
                    "@type": "Question",
                    "name": question,
                    "acceptedAnswer": {"@type": "Answer", "text": answer},
                }
                for question, answer in faqs
            ],
        })
    faq_html = "".join(
        f'<details><summary>{escape(question)}</summary><p>{escape(answer)}</p></details>'
        for question, answer in faqs
    )
    return base_head(title, description, canonical, image, "website") + f"""
<script type="application/ld+json">
{json_ld(schema)}
</script>
</head>
<body>
{seo_header("terror" if slug == "mejores-escape-rooms-terror" else "ranking")}
<main class="seo-main" id="contenido">
  <section class="page-intro">
    <div class="kicker">The Vault Escape</div>
    <h1>{escape(h1)}</h1>
    <p class="lead">{escape(intro)}</p>
    <div class="nav">
      <a href="../ranking/">Ranking completo</a>
      <a href="../reviews/">Reviews</a>
      <a href="../mejores-escape-rooms/">Mejores escape rooms</a>
      <a href="../mejores-escape-rooms-terror/">Terror</a>
      <a href="../escape-rooms-barcelona/">Barcelona</a>
      <a href="../escape-rooms-madrid/">Madrid</a>
      <a href="../escape-rooms-valencia/">Valencia</a>
      <a href="../">Abrir web</a>
    </div>
  </section>
  <div class="list">
    {''.join(items)}
  </div>
  <section class="method" aria-labelledby="metodologia-ranking">
    <div class="updated">Actualizado el {TODAY}</div>
    <h2 id="metodologia-ranking">Cómo elaboramos esta selección</h2>
    <p>{escape(keyword_note)}</p>
    <p>Las fichas enlazadas permiten consultar las puntuaciones y señales disponibles para cada sala. El resultado es orientativo, independiente y puede variar cuando se incorporan datos nuevos.</p>
  </section>
  <section class="faq" aria-labelledby="preguntas-ranking">
    <h2 id="preguntas-ranking">Preguntas frecuentes</h2>
    {faq_html}
  </section>
  <p class="note">Consulta también el <a href="../aviso-legal/">aviso legal y la explicación de fuentes</a> de The Vault Escape.</p>
</main>
{seo_footer()}
</body>
</html>
"""


def canonical_region(value):
    raw = clean_text(value)
    key = folded(raw)
    mapping = {
        "andalucia": "Andalucía",
        "aragon": "Aragón",
        "asturias": "Asturias",
        "cantabria": "Cantabria",
        "canarias": "Canarias",
        "castilla y leon": "Castilla y León",
        "castilla-la mancha": "Castilla-La Mancha",
        "castilla la mancha": "Castilla-La Mancha",
        "catalunya": "Catalunya",
        "cataluna": "Catalunya",
        "comunidad de madrid": "Comunidad de Madrid",
        "madrid": "Comunidad de Madrid",
        "comunitat valenciana": "Comunitat Valenciana",
        "comunidad valenciana": "Comunitat Valenciana",
        "extremadura": "Extremadura",
        "galicia": "Galicia",
        "la rioja": "La Rioja",
        "navarra": "Navarra",
        "pais vasco": "País Vasco",
        "euskadi": "País Vasco",
        "region de murcia": "Región de Murcia",
        "murcia": "Región de Murcia",
    }
    return mapping.get(key, raw)


def location_sort_key(item):
    rating = item.get("rating") or {}
    return (
        item.get("position") is None,
        item.get("position") or 999999,
        -decimal(rating.get("global_score")),
        -int(rating.get("source_count") or 0),
        text(item.get("room", {}).get("nombre")).lower(),
    )


def location_landing_page(slug, kind, label, rows, total_count):
    canonical = site_url(f"/{slug}/")
    image = site_url("/images/brand/social-card.png")
    is_city = kind == "city"
    title = (
        f"Escape rooms en {label} | Ranking y mejores salas | {SITE_NAME}"
        if is_city else
        f"Escape rooms en {label} | Ranking y catálogo | {SITE_NAME}"
    )
    description = (
        f"Catálogo de escape rooms en {label} con ranking, puntuaciones, premios, ubicación y fichas de salas destacadas."
        if is_city else
        f"Escape rooms en {label}: catálogo, ranking ponderado, mejores salas, premios y fichas públicas de The Vault Escape."
    )
    intro = (
        f"Descubre escape rooms en {label} ordenados con el criterio de The Vault Escape: ranking ponderado, fuentes externas, premios, reviews y datos de catálogo."
        if is_city else
        f"Explora escape rooms en {label} por ranking y catálogo. Esta página agrupa salas destacadas de la zona para facilitar búsquedas locales y comparar experiencias antes de reservar."
    )
    top_rows = sorted(rows, key=location_sort_key)[:80]
    items = []
    list_items = []
    for idx, item in enumerate(top_rows, 1):
        room = item["room"]
        rating = item.get("rating") or {}
        name = canonical_room_name(room) or "Escape room"
        company = canonical_room_company(room)
        url = site_url(f"/salas/{seo_room_url_slug(room)}/")
        score = decimal(rating.get("global_score"))
        source_count = int(rating.get("source_count") or 0)
        awards = int(rating.get("award_count") or 0)
        location = room_location(room)
        details = [value for value in [company, location] if value]
        if source_count:
            details.append(f"{source_count} fuentes")
        if awards:
            details.append(f"{awards} premios o nominaciones")
        score_html = f"{score:.1f}/10" if score else "Ficha"
        items.append(
            f'<a class="rank-link" href="{escape(url)}">'
            f'<span class="pos">#{idx}</span>'
            f'<strong>{escape(name)}</strong>'
            f'<span>{escape(" · ".join(details))}</span>'
            f'<em>{escape(score_html)}</em></a>'
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
                "keywords": f"escape rooms {label}, mejores escape rooms {label}, ranking escape rooms {label}",
                "isPartOf": {"@id": site_url("/#website")},
                "mainEntity": {"@type": "ItemList", "itemListElement": list_items},
            },
            {
                "@type": "BreadcrumbList",
                "itemListElement": [
                    {"@type": "ListItem", "position": 1, "name": "Inicio", "item": site_url("/")},
                    {"@type": "ListItem", "position": 2, "name": f"Escape rooms en {label}", "item": canonical},
                ],
            },
        ],
    }
    return base_head(title, description, canonical, image, "website") + f"""
<script type="application/ld+json">
{json_ld(schema)}
</script>
</head>
<body>
{seo_header("catalog")}
<main class="seo-main" id="contenido">
  <section class="page-intro">
    <div class="kicker">Escape rooms por ubicación</div>
    <h1>Escape rooms en {escape(label)}</h1>
    <p class="lead">{escape(intro)}</p>
    <div class="summary">
      <span>{len(top_rows)} salas destacadas</span>
      <span>{total_count} salas detectadas en la zona</span>
      <span>Ranking, premios y fichas públicas</span>
    </div>
    <div class="nav">
      <a href="../ranking-escape-rooms/">Ranking España</a>
      <a href="../mejores-escape-rooms/">Mejores salas</a>
      <a href="../mejores-escape-rooms-terror/">Terror</a>
      <a href="../reviews/">Reviews</a>
      <a href="../">Abrir web</a>
    </div>
  </section>
  <div class="list">
    {''.join(items)}
  </div>
  <p class="note">Página local orientativa para búsquedas de escape rooms en {escape(label)}. Las posiciones pueden cambiar cuando se actualizan nuevas fuentes, premios, reviews o datos de catálogo.</p>
</main>
{seo_footer()}
</body>
</html>
"""


def build_location_page_specs(sala_rows):
    city_groups = {}
    region_groups = {}
    for item in sala_rows:
        room = item.get("room") or {}
        city = clean_text(room.get("ciudad"))
        region = canonical_region(room.get("comunidad"))
        if city:
            city_groups.setdefault(slugify(city), {"kind": "city", "label": city, "rows": []})["rows"].append(item)
        if region:
            region_groups.setdefault(slugify(region), {"kind": "region", "label": region, "rows": []})["rows"].append(item)

    specs = []
    used_slugs = set()
    for group in city_groups.values():
        if len(group["rows"]) < CITY_PAGE_MIN_ROOMS:
            continue
        slug = f"escape-rooms-{slugify(group['label'])}"
        used_slugs.add(slug)
        specs.append({**group, "slug": slug})

    for group in region_groups.values():
        if len(group["rows"]) < REGION_PAGE_MIN_ROOMS:
            continue
        base_slug = f"escape-rooms-{slugify(group['label'])}"
        slug = base_slug if base_slug not in used_slugs else f"escape-rooms-comunidad-{slugify(group['label'])}"
        used_slugs.add(slug)
        specs.append({**group, "slug": slug})

    specs.sort(key=lambda spec: (spec["kind"] != "city", -len(spec["rows"]), spec["label"].lower()))
    return specs


def location_index_page(location_specs):
    canonical = site_url("/escape-rooms/")
    image = site_url("/images/brand/social-card.png")
    city_specs = [spec for spec in location_specs if spec["kind"] == "city"]
    region_specs = [spec for spec in location_specs if spec["kind"] == "region"]

    def links(specs):
        return "\n".join(
            f'<a class="location-link" href="../{escape(spec["slug"])}/">'
            f'<strong>{escape(spec["label"])}</strong>'
            f'<span>{len(spec["rows"])} salas detectadas</span>'
            "</a>"
            for spec in specs
        )

    schema = {
        "@context": "https://schema.org",
        "@type": "CollectionPage",
        "@id": canonical,
        "url": canonical,
        "name": f"Escape rooms por ciudad y comunidad | {SITE_NAME}",
        "description": "Índice de escape rooms en España por ciudad y comunidad autónoma con enlaces a rankings locales y fichas públicas.",
        "inLanguage": "es",
        "isPartOf": {"@id": site_url("/#website")},
    }
    title = f"Escape rooms por ciudad y comunidad | {SITE_NAME}"
    description = "Encuentra escape rooms en España por ciudad y comunidad autónoma: Barcelona, Madrid, Valencia, Catalunya, Andalucía, País Vasco y más."
    return base_head(title, description, canonical, image, "website") + f"""
<script type="application/ld+json">
{json_ld(schema)}
</script>
</head>
<body>
{seo_header("catalog")}
<main class="seo-main" id="contenido">
  <section class="page-intro">
    <div class="kicker">Escape rooms por ubicación</div>
    <h1>Escape rooms por ciudad y comunidad</h1>
    <p class="lead">Accede a rankings locales y fichas públicas de escape rooms en España. Cada página agrupa salas por ciudad o comunidad autónoma para ayudar a descubrir, comparar y planificar próximas experiencias.</p>
    <div class="nav">
      <a href="../ranking-escape-rooms/">Ranking España</a>
      <a href="../mejores-escape-rooms/">Mejores salas</a>
      <a href="../reviews/">Reviews</a>
      <a href="../">Abrir web</a>
    </div>
  </section>
  <h2 class="section-label">Ciudades</h2>
  <div class="grid">
    {links(city_specs)}
  </div>
  <h2 class="section-label">Comunidades autónomas</h2>
  <div class="grid">
    {links(region_specs)}
  </div>
</main>
{seo_footer()}
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


def room_players(room):
    minimum = text(room.get("min_personas"))
    maximum = text(room.get("max_personas"))
    if minimum and maximum:
        return minimum if minimum == maximum else f"{minimum} a {maximum}"
    return minimum or maximum


def room_price(room):
    minimum = decimal(room.get("precio_min"))
    maximum = decimal(room.get("precio_max"))
    if minimum and maximum:
        if minimum == maximum:
            return f"{minimum:g} €"
        low, high = sorted((minimum, maximum))
        return f"{low:g} a {high:g} €"
    value = minimum or maximum
    return f"{value:g} €" if value else ""


def room_facts(room, location_data):
    city = text(location_data.get("city")) or text(room.get("ciudad"))
    province = text(location_data.get("province")) or text(room.get("provincia"))
    facts = [
        ("Empresa", canonical_room_company(room)),
        ("Ciudad", city),
        ("Provincia", province),
        ("Comunidad", canonical_region(room.get("comunidad"))),
        ("Dirección", text(location_data.get("address"))),
        ("Duración", f'{text(room.get("duracion"))} minutos' if text(room.get("duracion")) else ""),
        ("Jugadores", room_players(room)),
        ("Precio orientativo", room_price(room)),
        ("Dificultad", text(room.get("dificultad"))),
        ("Temática", text(room.get("tematica")) or text(room.get("tipo"))),
    ]
    return [(label, value) for label, value in facts if value]


def room_page(item, position, location_links=None, review_slugs=None, videos_data=None, photos_data=None):
    room = item["room"]
    rating = item.get("rating") or {}
    meta = item.get("meta") or {}
    name = canonical_room_name(room) or "Escape room"
    company = canonical_room_company(room)
    slug = seo_room_url_slug(room)
    canonical = site_url(f"/salas/{slug}/")
    app_link = site_url(f"/#room/{app_hash_key(room)}")
    score = decimal(rating.get("global_score"))
    has_score = score > 0
    synopsis = text(room.get("descripcion"))
    location_data = exact_room_location(room)
    city = text(location_data.get("city")) or text(room.get("ciudad"))
    province = text(location_data.get("province")) or text(room.get("provincia"))
    source_count = int(rating.get("source_count") or 0)
    award_count = int(rating.get("award_count") or 0)
    fallback_description = f"Ficha de {name}{' de ' + company if company else ''}"
    if city:
        fallback_description += f" en {city}"
    fallback_description += ", con datos de ubicación, duración, jugadores y enlaces de consulta."
    if has_score:
        identity_detail = name
        if company:
            identity_detail += f" de {company}"
        if city:
            identity_detail += f" en {city}"
        rating_detail = f"Nota global {score:.1f}/10"
        if source_count:
            rating_detail += f" con {source_count} fuentes"
        if award_count:
            rating_detail += f" y {award_count} premios o nominaciones"
        seo_description = f"{identity_detail}. {rating_detail}. Consulta datos, sinopsis, ubicación y fuentes del ranking."
    else:
        seo_description = fallback_description
    description = short_description({"descripcion": seo_description})
    image = asset_url(room.get("imagen") or "images/brand/social-card.png")
    cover = page_asset(room.get("imagen") or "images/brand/social-card.png")
    title = f"{name}: ranking y puntuaciones | {SITE_NAME}" if has_score else f"{name}: ficha de escape room | {SITE_NAME}"
    location = " · ".join(value for value in (city, province) if value)
    meta_values = [
        location,
        text(room.get("tematica")),
        text(room.get("tipo")),
        f'{text(room.get("duracion"))} min' if text(room.get("duracion")) else "",
        text(room.get("dificultad")),
    ]
    meta_html = "\n".join(f'<span class="pill">{escape(value)}</span>' for value in meta_values if value)
    sources_html = source_pills(rating, meta) if has_score else ""
    facts_html = "\n".join(
        f'<div class="fact"><dt>{escape(label)}</dt><dd>{escape(value)}</dd></div>'
        for label, value in room_facts(room, location_data)
    )
    links = []
    location_links = location_links or {}
    city_link = location_links.get(("city", slugify(city))) if city else None
    region = canonical_region(room.get("comunidad"))
    region_link = location_links.get(("region", slugify(region))) if region else None
    if city_link:
        links.append((f"Escape rooms en {city}", site_url(f"/{city_link}/")))
    if region_link and region_link != city_link:
        links.append((f"Escape rooms en {region}", site_url(f"/{region_link}/")))
    links.append(("Ranking de escape rooms", site_url("/ranking-escape-rooms/")))
    review_slug = room_url_slug(room)
    if review_slug in (review_slugs or set()):
        links.append((f"Review de {name}", site_url(f"/reviews/{review_slug}/")))
    internal_links_html = "\n".join(
        f'<a class="btn secondary" href="{escape(url)}">{escape(label)}</a>' for label, url in links
    )
    official_url = text(room.get("web"))
    if official_url and not official_url.startswith(("http://", "https://")):
        official_url = f"https://{official_url.lstrip('/')}"
    video = video_entry(room, videos_data or {})
    video_url = text(video.get("embed_url") or video.get("video_url"))
    if video_url and not video_url.startswith(("http://", "https://")):
        video_url = ""
    video_provider = folded(video.get("provider"))
    video_thumbnail = text(video.get("thumbnail"))
    if video_thumbnail and not video_thumbnail.startswith(("http://", "https://")):
        video_thumbnail = asset_url(video_thumbnail)
    photos = photo_entries(room, photos_data or {})
    photo_html = "\n".join(
        f'<img src="{escape(page_asset(photo.get("src")))}" alt="{escape(photo.get("alt") or f"{name} - foto del grupo")}" loading="lazy" decoding="async">'
        for photo in photos
        if photo.get("src")
    )
    if video_url and video_provider in {"youtube", "vimeo"}:
        video_html = (
            f'<iframe class="video-frame" src="{escape(video_url)}" title="Vídeo oficial de {escape(name)}" '
            'loading="lazy" allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture" '
            'allowfullscreen></iframe>'
        )
    elif video_url:
        poster = f' poster="{escape(video_thumbnail)}"' if video_thumbnail else ""
        video_html = (
            f'<video class="video-frame" controls preload="metadata"{poster}>'
            f'<source src="{escape(video_url)}">Tu navegador no puede reproducir este vídeo.</video>'
        )
    else:
        video_html = ""
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
                "isPartOf": {"@id": site_url("/#website")},
                "primaryImageOfPage": image,
            },
            {
                "@type": "EntertainmentBusiness",
                "name": f"{name}{' - ' + company if company else ''}",
                "image": image,
                "description": description,
                "url": canonical,
                "address": {
                    "@type": "PostalAddress",
                    "streetAddress": text(location_data.get("address")),
                    "addressLocality": city,
                    "addressRegion": province,
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
    if official_url:
        schema["@graph"][1]["sameAs"] = [official_url]
    if decimal(location_data.get("lat")) and decimal(location_data.get("lon")):
        schema["@graph"][1]["geo"] = {
            "@type": "GeoCoordinates",
            "latitude": decimal(location_data.get("lat")),
            "longitude": decimal(location_data.get("lon")),
        }
    if photos:
        schema["@graph"][1]["image"] = [image] + [asset_url(photo.get("src")) for photo in photos if photo.get("src")]
    video_upload_date = text(video.get("upload_date"))
    if video_html and video_upload_date:
        direct_video_url = text(video.get("video_url"))
        if video_provider in {"youtube", "vimeo"}:
            direct_video_url = ""
        video_schema = {
            "@type": "VideoObject",
            "name": text(video.get("label")) or f"Vídeo oficial de {name}",
            "description": f"Vídeo de introducción oficial de la experiencia {name}{' de ' + company if company else ''}.",
            "thumbnailUrl": video_thumbnail or image,
            "embedUrl": video_url if video_provider in {"youtube", "vimeo"} else None,
            "contentUrl": direct_video_url or (video_url if video_provider not in {"youtube", "vimeo"} else None),
            "uploadDate": video_upload_date,
            "isPartOf": {"@id": canonical},
        }
        schema["@graph"].append({key: value for key, value in video_schema.items() if value})
    return base_head(title, description, canonical, image) + f"""
<script type="application/ld+json">
{json_ld(schema)}
</script>
</head>
<body>
{seo_header("catalog")}
<main class="wrap" id="contenido">
  <article class="detail-hero">
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
    <h2>Datos rápidos de {escape(name)}</h2>
    <dl class="facts">{facts_html}</dl>
  </section>''' if facts_html else ''}
  {f'''<section class="section">
    <h2>Fuentes del ranking</h2>
    <div class="meta">{sources_html}</div>
    <p class="explain">La nota global combina las fuentes disponibles para esta sala, las reviews publicadas en The Vault, la comunidad y el peso moderado de premios o nominaciones. En caso de empate se prioriza la sala contrastada por más fuentes.</p>
  </section>''' if sources_html else ''}
  {f'<section class="section"><h2>Sinopsis</h2><div class="review">{escape(synopsis)}</div></section>' if synopsis and folded(synopsis) != 'sin sinopsis' else ''}
  {f'''<section class="section">
    <h2>Vídeo de introducción</h2>
    {video_html}
    <p class="media-note">Vídeo localizado en la web oficial de la sala.</p>
  </section>''' if video_html else ''}
  {f'''<section class="section">
    <h2>Fotos del grupo</h2>
    <div class="photos">{photo_html}</div>
  </section>''' if photo_html else ''}
  <section class="section">
    <h2>Explorar más</h2>
    <nav class="internal-links" aria-label="Enlaces relacionados">{internal_links_html}</nav>
  </section>
</main>
{seo_footer()}
</body>
</html>
"""


def sitemap_xml(review_rooms, sala_rows, location_specs=None):
    entries = [
        (site_url("/"), "daily", "1.0"),
        (site_url("/escape-rooms/"), "weekly", "0.9"),
        (site_url("/reviews/"), "weekly", "0.8"),
        (site_url("/ranking/"), "weekly", "0.9"),
        (site_url("/ranking-escape-rooms/"), "weekly", "0.95"),
        (site_url("/mejores-escape-rooms/"), "weekly", "0.95"),
        (site_url("/mejores-escape-rooms-terror/"), "weekly", "0.9"),
    ]
    entries.extend((site_url(f"/reviews/{room_url_slug(room)}/"), "monthly", "0.7") for room in review_rooms)
    entries.extend((site_url(f"/{spec['slug']}/"), "weekly", "0.86") for spec in (location_specs or []))
    entries.extend((site_url(f"/salas/{seo_room_url_slug(item['room'])}/"), "monthly", "0.7") for item in sala_rows)
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


def video_sitemap_xml(sala_rows, videos_data):
    entries = []
    seen_pages = set()
    for item in sala_rows:
        room = item.get("room") or {}
        video = video_entry(room, videos_data or {})
        upload_date = text(video.get("upload_date"))
        thumbnail = text(video.get("thumbnail"))
        provider = folded(video.get("provider"))
        embed_url = text(video.get("embed_url") or video.get("video_url"))
        direct_url = text(video.get("video_url")) if provider not in {"youtube", "vimeo"} else ""
        if not upload_date or not thumbnail or not (embed_url or direct_url):
            continue
        if not thumbnail.startswith(("http://", "https://")):
            thumbnail = asset_url(thumbnail)
        page_url = site_url(f"/salas/{seo_room_url_slug(room)}/")
        if page_url in seen_pages:
            continue
        seen_pages.add(page_url)
        name = canonical_room_name(room) or "Escape room"
        company = canonical_room_company(room)
        title = text(video.get("label")) or f"Vídeo oficial de {name}"
        description = f"Vídeo de introducción oficial de la experiencia {name}{' de ' + company if company else ''}."
        source_tag = "video:player_loc" if provider in {"youtube", "vimeo"} else "video:content_loc"
        source_url = embed_url if provider in {"youtube", "vimeo"} else (direct_url or embed_url)
        entries.append(
            "  <url>\n"
            f"    <loc>{escape(page_url)}</loc>\n"
            "    <video:video>\n"
            f"      <video:thumbnail_loc>{escape(thumbnail)}</video:thumbnail_loc>\n"
            f"      <video:title>{escape(title)}</video:title>\n"
            f"      <video:description>{escape(description)}</video:description>\n"
            f"      <{source_tag}>{escape(source_url)}</{source_tag}>\n"
            f"      <video:publication_date>{escape(upload_date)}</video:publication_date>\n"
            "    </video:video>\n"
            "  </url>"
        )
    body = "\n".join(entries)
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9" '
        'xmlns:video="http://www.google.com/schemas/sitemap-video/1.1">\n'
        f"{body}\n</urlset>\n"
    )


def robots_txt():
    return f"""User-agent: *
Allow: /

Sitemap: {site_url('/sitemap.xml')}
Sitemap: {site_url('/video-sitemap.xml')}
"""


def site_stats_json(review_rooms, sala_rows, location_specs):
    payload = {
        "catalog": len(catalog_rooms()),
        "reviews": len(review_rooms),
        "ranking": sum(1 for item in sala_rows if decimal(item.get("rating", {}).get("global_score")) > 0),
        "locations": len(location_specs or []),
        "updated": TODAY,
    }
    return json.dumps(payload, ensure_ascii=False, indent=2) + "\n"


def update_inline_site_stats(stats_json):
    index_path = ROOT / "index.html"
    if not index_path.exists():
        return
    stats = json.loads(stats_json)
    inline = json.dumps(stats, ensure_ascii=False, separators=(",", ":"))
    html = index_path.read_text(encoding="utf-8")
    pattern = r"const FALLBACK_SITE_STATS = \{.*?\};"
    replacement = f"const FALLBACK_SITE_STATS = {inline};"
    next_html, count = re.subn(pattern, replacement, html, count=1)
    if count:
        index_path.write_text(next_html, encoding="utf-8", newline="\n")


def llms_txt():
    return f"""# {SITE_NAME}

The Vault Escape es un catálogo y archivo de escape rooms en España. Incluye fichas de salas, reviews propias, ranking ponderado con varias fuentes, premios, fotos y herramientas personales para usuarios registrados.

## URLs principales
- [Inicio y aplicación interactiva]({site_url('/')})
- [Reviews publicadas]({site_url('/reviews/')})
- [Ranking de escape rooms]({site_url('/ranking/')})
- [Ranking escape rooms España]({site_url('/ranking-escape-rooms/')})
- [Mejores escape rooms España]({site_url('/mejores-escape-rooms/')})
- [Mejores escape rooms de terror]({site_url('/mejores-escape-rooms-terror/')})
- [Índice SEO por ciudad y comunidad]({site_url('/escape-rooms/')})
- Landings SEO por ubicación: /escape-rooms-{{ciudad}}/ y /escape-rooms-{{comunidad}}/
- [Sitemap XML]({site_url('/sitemap.xml')})

## Contenido
- Fichas públicas en /salas/{{slug}}/ con nombre, empresa, ubicación, sinopsis cuando existe y puntuaciones si están disponibles.
- Reviews públicas en /reviews/{{slug}}/ con opinión del grupo, puntuaciones por categorías, fotos y enlaces para compartir.
- Ranking calculado con fuentes externas, comunidad The Vault y premios, descrito en las páginas legales de la web.

## Contacto
- [Instagram The Vault Escape](https://www.instagram.com/thevault_escape/)
- [Web The Vault Escape]({BASE_URL})
"""


def main():
    parser = argparse.ArgumentParser(description="Genera las páginas SEO estáticas de The Vault.")
    parser.add_argument(
        "--update-main-stats",
        action="store_true",
        help="Actualiza también el contador de respaldo incluido en index.html.",
    )
    args = parser.parse_args()
    (ROOT / "seo.css").write_text(SEO_STYLES.strip() + "\n", encoding="utf-8", newline="\n")
    data = read_json(ROOT / "data.json", {})
    photos_data = read_json(ROOT / "review_photos.json", {}).get("photos", {})
    videos_data = read_json(ROOT / "official_videos.json", {}).get("videos", {})
    rooms = published_review_rooms(data) or review_rooms(data)
    ranking_rows = [row for row in ranked_rooms(data) if decimal(row["rating"].get("global_score")) > 0]
    sala_rows = catalog_seo_rows(data, ranking_rows)
    assign_seo_room_slugs(sala_rows)

    reviews_dir = ROOT / "reviews"
    reviews_dir.mkdir(exist_ok=True)
    generated_review_pages = []
    for room in rooms:
        slug = room_url_slug(room)
        page_dir = reviews_dir / slug
        page_dir.mkdir(parents=True, exist_ok=True)
        photos = photo_entries(room, photos_data)
        social_card = generate_review_social_card(room, photos)
        generate_latest_review_thumbnail(room, photos)
        (page_dir / "index.html").write_text(review_page(room, photos, social_card), encoding="utf-8", newline="\n")
        generated_review_pages.append(slug)

    review_by_identity = {room_identity(room): room for room in rooms}
    legacy_review_pages = 0
    for old_page in reviews_dir.glob("*/index.html"):
        old_slug = old_page.parent.name
        if old_slug in generated_review_pages:
            continue
        current_room = review_by_identity.get(canonical_room_identity(old_slug))
        if not current_room:
            continue
        target = site_url(f"/reviews/{room_url_slug(current_room)}/")
        old_page.write_text(
            legacy_seo_page(canonical_room_name(current_room), target, target=target),
            encoding="utf-8",
            newline="\n",
        )
        legacy_review_pages += 1

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

    for old_location_dir in ROOT.glob("escape-rooms-*"):
        if old_location_dir.is_dir():
            shutil.rmtree(old_location_dir)
    location_specs = build_location_page_specs(sala_rows)
    for spec in location_specs:
        page_dir = ROOT / spec["slug"]
        page_dir.mkdir(exist_ok=True)
        (page_dir / "index.html").write_text(
            location_landing_page(
                spec["slug"],
                spec["kind"],
                spec["label"],
                spec["rows"],
                len(spec["rows"]),
            ),
            encoding="utf-8",
            newline="\n",
        )
    location_index_dir = ROOT / "escape-rooms"
    location_index_dir.mkdir(exist_ok=True)
    (location_index_dir / "index.html").write_text(
        location_index_page(location_specs),
        encoding="utf-8",
        newline="\n",
    )

    salas_dir = ROOT / "salas"
    salas_dir.mkdir(exist_ok=True)
    location_links = {
        (spec["kind"], slugify(spec["label"])): spec["slug"]
        for spec in location_specs
    }
    review_slugs = {room_url_slug(room) for room in rooms}
    generated_sala_slugs = set()
    for item in sala_rows:
        sala_slug = seo_room_url_slug(item["room"])
        generated_sala_slugs.add(sala_slug)
        page_dir = salas_dir / sala_slug
        page_dir.mkdir(parents=True, exist_ok=True)
        (page_dir / "index.html").write_text(
            room_page(item, item.get("position") or 0, location_links, review_slugs, videos_data, photos_data),
            encoding="utf-8",
            newline="\n",
        )

    sala_by_identity = {room_identity(item["room"]): item for item in sala_rows}
    closed_rooms = read_json(ROOT / "private" / "closed_rooms.json", {}).get("rooms", [])
    closed_by_slug = {slugify(room.get("id") or room.get("nombre")): room for room in closed_rooms}
    legacy_sala_pages = 0
    retired_sala_pages = 0
    for old_page in salas_dir.glob("*/index.html"):
        old_slug = old_page.parent.name
        if old_slug in generated_sala_slugs:
            continue
        current_item = sala_by_identity.get(canonical_room_identity(old_slug))
        if current_item:
            current_room = current_item["room"]
            target = site_url(f"/salas/{seo_room_url_slug(current_room)}/")
            old_page.write_text(
                legacy_seo_page(canonical_room_name(current_room), target, target=target),
                encoding="utf-8",
                newline="\n",
            )
            legacy_sala_pages += 1
            continue
        closed_room = closed_by_slug.get(old_slug)
        if closed_room:
            old_page.write_text(
                legacy_seo_page(text(closed_room.get("nombre")) or old_slug, site_url(f"/salas/{old_slug}/"), retired=True),
                encoding="utf-8",
                newline="\n",
            )
            retired_sala_pages += 1

    stats_json = site_stats_json(rooms, sala_rows, location_specs)
    if args.update_main_stats:
        update_inline_site_stats(stats_json)
    (ROOT / "sitemap.xml").write_text(sitemap_xml(rooms, sala_rows, location_specs), encoding="utf-8", newline="\n")
    (ROOT / "video-sitemap.xml").write_text(video_sitemap_xml(sala_rows, videos_data), encoding="utf-8", newline="\n")
    (ROOT / "robots.txt").write_text(robots_txt(), encoding="utf-8", newline="\n")
    (ROOT / "llms.txt").write_text(llms_txt(), encoding="utf-8", newline="\n")
    (ROOT / "site_stats.json").write_text(stats_json, encoding="utf-8", newline="\n")
    print(
        "SEO generado: "
        f"{len(generated_review_pages)} reviews, "
        f"{len(sala_rows)} salas, "
        f"{len(location_specs)} landings por ubicacion, "
        f"{legacy_sala_pages + legacy_review_pages} alias redirigidos, "
        f"{retired_sala_pages} fichas cerradas retiradas, "
        f"{len(generated_review_pages)} tarjetas sociales, "
        "ranking, landings SEO, sitemap.xml, video-sitemap.xml, robots.txt y llms.txt"
    )


if __name__ == "__main__":
    main()
