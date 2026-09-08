"""Validate The Vault public data before publishing.

Hard errors stop CI. Editorial gaps are warnings and remain visible in reports.
"""

import argparse
import json
import re
import sys
import unicodedata
import xml.etree.ElementTree as ET
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse


ROOT = Path(__file__).resolve().parents[1]
REPORT_DIR = ROOT / "reports"
SPAIN_BOUNDS = (27.0, 44.5, -19.0, 5.0)


def load_json(name, errors):
    path = ROOT / name
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        errors.append(f"{name}: JSON no válido ({exc})")
        return {}


def slug(value):
    value = unicodedata.normalize("NFKD", str(value or "")).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "_", value.lower()).strip("_")


def is_remote(value):
    return urlparse(str(value or "")).scheme in {"http", "https"}


def local_asset_exists(value):
    if not value or is_remote(value):
        return True
    clean = str(value).split("?", 1)[0].lstrip("/")
    return (ROOT / clean).is_file()


def detect_alias_cycles(aliases):
    cycles = []
    for start in aliases:
        seen = []
        current = start
        while current in aliases and aliases[current] != current:
            if current in seen:
                cycles.append(seen[seen.index(current):] + [current])
                break
            seen.append(current)
            current = aliases[current]
    return cycles


def resolve_alias(value, aliases):
    current = slug(value)
    seen = set()
    while current in aliases and aliases[current] != current and current not in seen:
        seen.add(current)
        current = aliases[current]
    return current


def validate():
    errors, warnings = [], []
    catalog_payload = load_json("catalog.json", errors)
    catalog = catalog_payload.get("catalogo") or []
    aliases_payload = load_json("room_aliases.json", errors)
    aliases = {slug(k): slug(v) for k, v in (aliases_payload.get("aliases") or {}).items()}
    videos = (load_json("official_videos.json", errors).get("videos") or {})
    locations = (load_json("room_locations.json", errors).get("locations") or {})
    reviews = (load_json("published_reviews.json", errors).get("reviews") or {})
    review_photos = (load_json("review_photos.json", errors).get("photos") or {})
    relationships = load_json("room_relationships.json", errors).get("families") or []

    index_html = (ROOT / "index.html").read_text(encoding="utf-8")
    function_names = re.findall(r"(?m)^\s*(?:async\s+)?function\s+([A-Za-z_$][\w$]*)\s*\(", index_html)
    duplicate_functions = sorted(name for name, count in Counter(function_names).items() if count > 1)
    if duplicate_functions:
        errors.append(f"index.html: funciones JavaScript duplicadas: {', '.join(duplicate_functions)}")

    ids = [str(room.get("id") or "").strip() for room in catalog]
    missing_ids = sum(not value for value in ids)
    duplicate_ids = sorted(key for key, count in Counter(ids).items() if key and count > 1)
    if missing_ids:
        errors.append(f"catalog.json: {missing_ids} salas sin id")
    if duplicate_ids:
        errors.append(f"catalog.json: ids duplicados: {', '.join(duplicate_ids[:20])}")

    identities = defaultdict(list)
    thin_synopses = 0
    missing_images = []
    for room in catalog:
        identity = (slug(room.get("nombre")), slug(room.get("empresa")), slug(room.get("ciudad")))
        if all(identity):
            identities[identity].append(room.get("id"))
        synopsis = str(room.get("descripcion") or "").strip()
        if synopsis.lower() == "sin sinopsis" or len(synopsis) < 80:
            thin_synopses += 1
        image = room.get("imagen")
        if image and not local_asset_exists(image):
            missing_images.append(f"{room.get('id')}: {image}")
    exact_duplicates = [values for values in identities.values() if len(values) > 1]
    unresolved_duplicates = [
        values for values in exact_duplicates
        if len({resolve_alias(value, aliases) for value in values}) > 1
    ]
    if unresolved_duplicates:
        warnings.append(f"Catálogo: {len(unresolved_duplicates)} identidades repetidas aún no consolidadas con alias")
    if thin_synopses:
        warnings.append(f"Catálogo: {thin_synopses} fichas con sinopsis ausente o menor de 80 caracteres")
    if missing_images:
        errors.append(f"Catálogo: {len(missing_images)} imágenes locales no encontradas")

    cycles = detect_alias_cycles(aliases)
    if cycles:
        errors.append(f"Alias: {len(cycles)} ciclos detectados")

    catalog_tokens = {slug(value) for value in ids}
    catalog_tokens.update(slug(room.get("nombre")) for room in catalog)
    relation_members = 0
    for family in relationships:
        if not family.get("id") or not family.get("parentId"):
            errors.append("room_relationships.json: familia sin id o parentId")
        members = family.get("members") or []
        relation_members += len(members)
        if not members:
            warnings.append(f"Relaciones: {family.get('id', '?')} no tiene miembros")
        if slug(family.get("parentId")) not in catalog_tokens and slug(family.get("parentName")) not in catalog_tokens:
            warnings.append(f"Relaciones: no se localiza el padre de {family.get('id', '?')} en catálogo")

    invalid_locations = 0
    for key, value in locations.items():
        try:
            lat = float(value.get("lat"))
            lon = float(value.get("lon"))
            if not (SPAIN_BOUNDS[0] <= lat <= SPAIN_BOUNDS[1] and SPAIN_BOUNDS[2] <= lon <= SPAIN_BOUNDS[3]):
                invalid_locations += 1
        except (TypeError, ValueError, AttributeError):
            invalid_locations += 1
    if invalid_locations:
        errors.append(f"Ubicaciones: {invalid_locations} coordenadas inválidas o fuera del ámbito español")

    video_missing_dates = 0
    video_missing_thumbnails = 0
    for key, video in videos.items():
        if not video.get("upload_date"):
            video_missing_dates += 1
        if not video.get("thumbnail"):
            video_missing_thumbnails += 1
        for field in ("embed_url", "video_url"):
            value = video.get(field)
            if value and not is_remote(value):
                errors.append(f"Vídeos: URL inválida en {key}.{field}")
    if video_missing_dates:
        warnings.append(f"Vídeos: {video_missing_dates} sin upload_date; se excluyen de datos estructurados")
    if video_missing_thumbnails:
        warnings.append(f"Vídeos: {video_missing_thumbnails} sin miniatura; se excluyen del video sitemap")

    empty_reviews = 0
    missing_review_media = 0
    for record in reviews.values():
        review = record.get("review") if isinstance(record, dict) else {}
        if len(str((review or {}).get("descripcion") or "").strip()) < 20:
            empty_reviews += 1
        image = (review or {}).get("imagen")
        if image and not local_asset_exists(image):
            missing_review_media += 1
    if empty_reviews:
        warnings.append(f"Reviews: {empty_reviews} sin texto publicable")
    if missing_review_media:
        errors.append(f"Reviews: {missing_review_media} imágenes locales no encontradas")

    review_media = []
    for entries in review_photos.values():
        if isinstance(entries, dict):
            entries = entries.get("items") or entries.get("photos") or []
        for media in entries if isinstance(entries, list) else []:
            if isinstance(media, dict) and media.get("src"):
                review_media.append(media.get("src"))
    missing_gallery_media = [value for value in review_media if not local_asset_exists(value)]
    if missing_gallery_media:
        errors.append(f"Galerías: {len(missing_gallery_media)} archivos locales no encontrados")
    oversized_media = []
    for value in review_media:
        if not value or is_remote(value):
            continue
        path = ROOT / str(value).split("?", 1)[0].lstrip("/")
        if path.is_file() and path.stat().st_size > 20 * 1024 * 1024:
            oversized_media.append(value)
    if oversized_media:
        errors.append(f"Galerías: {len(oversized_media)} archivos superan 20 MB")

    sitemap_counts = {}
    for path in sorted(ROOT.glob("sitemap*.xml")):
        try:
            tree = ET.parse(path)
            root = tree.getroot()
            sitemap_counts[path.name] = len(list(root))
        except ET.ParseError as exc:
            errors.append(f"{path.name}: XML no válido ({exc})")

    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "status": "error" if errors else "ok",
        "summary": {
            "catalog_rooms": len(catalog),
            "reviews": len(reviews),
            "videos": len(videos),
            "locations": len(locations),
            "relationship_families": len(relationships),
            "relationship_members": relation_members,
            "review_media": len(review_media),
            "errors": len(errors),
            "warnings": len(warnings),
        },
        "sitemaps": sitemap_counts,
        "errors": errors,
        "warnings": warnings,
    }
    return report


def write_report(report):
    REPORT_DIR.mkdir(exist_ok=True)
    (REPORT_DIR / "site-quality.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    lines = ["# Calidad del sitio", "", f"Estado: **{report['status']}**", ""]
    lines.extend(f"- {key}: {value}" for key, value in report["summary"].items())
    for heading, key in (("Errores", "errors"), ("Avisos", "warnings")):
        lines.extend(["", f"## {heading}", ""])
        lines.extend(f"- {item}" for item in report[key]) or lines.append("- Ninguno")
    (REPORT_DIR / "site-quality.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--strict", action="store_true", help="Devuelve error si hay fallos estructurales")
    args = parser.parse_args()
    report = validate()
    write_report(report)
    print(json.dumps(report["summary"], ensure_ascii=False))
    for message in report["errors"]:
        print(f"ERROR: {message}")
    for message in report["warnings"]:
        print(f"AVISO: {message}")
    if args.strict and report["errors"]:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
