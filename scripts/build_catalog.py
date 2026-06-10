#!/usr/bin/env python3
"""Genera catalog.json desde el catálogo público de Escape Collector."""

import json
import os
import re
import unicodedata
from pathlib import Path
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
CATALOG_FILE = ROOT / "catalog.json"
CATALOG_IMAGES_DIR = ROOT / "images" / "ec-all"

API_KEY = os.environ.get("GOOGLE_API_KEY", "").strip()
PROJECT = "room-escapes"
PAGE_SIZE = 300
if not API_KEY:
    raise RuntimeError("GOOGLE_API_KEY no configurada. Exporta la clave antes de ejecutar este script.")

USER_AGENT = "scaperooms-catalog-builder/1.0"

COMMUNITIES_BY_PROVINCE_ID = {
    "01": "Pais Vasco", "20": "Pais Vasco", "48": "Pais Vasco",
    "02": "Castilla-La Mancha", "13": "Castilla-La Mancha", "16": "Castilla-La Mancha", "19": "Castilla-La Mancha", "45": "Castilla-La Mancha",
    "03": "Comunitat Valenciana", "12": "Comunitat Valenciana", "46": "Comunitat Valenciana",
    "04": "Andalucia", "11": "Andalucia", "14": "Andalucia", "18": "Andalucia", "21": "Andalucia", "23": "Andalucia", "29": "Andalucia", "41": "Andalucia",
    "05": "Castilla y Leon", "09": "Castilla y Leon", "24": "Castilla y Leon", "34": "Castilla y Leon", "37": "Castilla y Leon", "40": "Castilla y Leon", "42": "Castilla y Leon", "47": "Castilla y Leon", "49": "Castilla y Leon",
    "06": "Extremadura", "10": "Extremadura",
    "07": "Illes Balears",
    "08": "Catalunya", "17": "Catalunya", "25": "Catalunya", "43": "Catalunya",
    "15": "Galicia", "27": "Galicia", "32": "Galicia", "36": "Galicia",
    "22": "Aragon", "44": "Aragon", "50": "Aragon",
    "26": "La Rioja",
    "28": "Comunidad de Madrid",
    "30": "Region de Murcia",
    "31": "Comunidad Foral de Navarra",
    "33": "Asturias",
    "35": "Canarias", "38": "Canarias",
    "39": "Cantabria",
    "51": "Ceuta",
    "52": "Melilla",
}


def slugify(text):
    text = str(text or "").strip().lower()
    text = unicodedata.normalize("NFD", text)
    text = "".join(ch for ch in text if unicodedata.category(ch) != "Mn")
    text = re.sub(r"[^a-z0-9]+", "-", text).strip("-")
    return text or "escape-room"


def value(field):
    if not field:
        return ""
    if "stringValue" in field:
        return field["stringValue"]
    if "integerValue" in field:
        return int(field["integerValue"])
    if "doubleValue" in field:
        return round(float(field["doubleValue"]), 2)
    if "booleanValue" in field:
        return bool(field["booleanValue"])
    if "timestampValue" in field:
        return field["timestampValue"]
    if "arrayValue" in field:
        return [value(item) for item in field.get("arrayValue", {}).get("values", [])]
    if "mapValue" in field:
        return {k: value(v) for k, v in field.get("mapValue", {}).get("fields", {}).items()}
    return ""


def fetch_json(url):
    req = Request(url, headers={"User-Agent": USER_AGENT})
    with urlopen(req, timeout=45) as response:
        return json.loads(response.read().decode("utf-8"))


def fetch_rooms():
    rooms = []
    page_token = ""
    while True:
        url = (
            f"https://firestore.googleapis.com/v1/projects/{PROJECT}/databases/(default)"
            f"/documents/rooms?pageSize={PAGE_SIZE}&key={API_KEY}"
        )
        if page_token:
            url += f"&pageToken={page_token}"
        payload = fetch_json(url)
        rooms.extend(payload.get("documents", []))
        page_token = payload.get("nextPageToken", "")
        if not page_token:
            return rooms


def difficulty_label(raw):
    return {
        "easy": "Baja",
        "medium": "Media",
        "hard": "Alta",
        "expert": "Experta",
    }.get(str(raw or "").lower(), raw or "")


def local_image(room_id):
    path = CATALOG_IMAGES_DIR / f"{slugify(room_id)}.webp"
    if path.exists():
        return path.relative_to(ROOT).as_posix()
    return ""


def community_from_province(province):
    province_id = str(province.get("province_id", "")).zfill(2)
    return COMMUNITIES_BY_PROVINCE_ID.get(province_id, "")


def build():
    result = []
    for doc in fetch_rooms():
        fields = {k: value(v) for k, v in doc.get("fields", {}).items()}
        room_id = doc["name"].split("/")[-1]
        province = fields.get("province") if isinstance(fields.get("province"), dict) else {}
        result.append({
            "id": room_id,
            "nombre": fields.get("name") or room_id,
            "empresa": fields.get("company") or "",
            "ciudad": fields.get("city") or "",
            "provincia": province.get("name", ""),
            "comunidad": community_from_province(province),
            "pais": fields.get("country") or "",
            "duracion": fields.get("duration") or "",
            "min_personas": fields.get("min_players") or "",
            "max_personas": fields.get("max_players") or "",
            "precio_min": fields.get("min_price") or "",
            "precio_max": fields.get("max_price") or "",
            "dificultad": difficulty_label(fields.get("difficulty")),
            "rating": fields.get("score") or "",
            "votos": fields.get("totalReviews") or "",
            "terror": fields.get("terror") is True,
            "abierto": fields.get("status") == 1,
            "verificado": fields.get("verified") is True,
            "web": fields.get("url") or "",
            "descripcion": fields.get("description") or "",
            "imagen": local_image(room_id),
        })

    result.sort(key=lambda room: (float(room["rating"] or 0), int(room["votos"] or 0)), reverse=True)
    data = {
        "catalogo": result,
        "meta": {
            "source": "Escape Collector / Firestore público",
            "count": len(result),
            "with_images": sum(1 for room in result if room.get("imagen")),
        },
    }
    CATALOG_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"catalog.json generado -> {data['meta']['count']} salas, {data['meta']['with_images']} con imagen")


if __name__ == "__main__":
    build()
