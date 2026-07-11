#!/usr/bin/env python3
"""Build review_photos.json from images/Hechos.

The site is static, so the browser cannot list files in a folder. This
manifest lets the reviews page attach local group photos automatically.
"""

from __future__ import annotations

import json
import re
import unicodedata
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA_FILE = ROOT / "data.json"
CATALOG_FILE = ROOT / "catalog.json"
PHOTOS_DIR = ROOT / "images" / "Hechos"
OUT_FILE = ROOT / "review_photos.json"
EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".avif"}
PHOTO_ROOM_ALIASES = {
    "la_historia_de_charlotte": "whitechapel",
}


def slugify(text: str) -> str:
    text = str(text or "").strip().lower()
    text = unicodedata.normalize("NFD", text)
    text = "".join(ch for ch in text if unicodedata.category(ch) != "Mn")
    text = re.sub(r"[^a-z0-9]+", "_", text).strip("_")
    return text


def tokens(text: str) -> set[str]:
    return {part for part in slugify(text).split("_") if len(part) > 1}


def compact(text: str) -> str:
    return slugify(text).replace("_", "")


def photo_base(path: Path) -> str:
    # "Nightshift 1.jpeg" -> "Nightshift"; "Tao.jpeg" -> "Tao".
    return re.sub(r"\s+\d+$", "", path.stem).strip()


def load_done_rooms() -> list[dict]:
    if not DATA_FILE.exists():
        return []
    payload = json.loads(DATA_FILE.read_text(encoding="utf-8"))
    return payload.get("hechos", []) if isinstance(payload, dict) else []


def load_catalog_rooms() -> list[dict]:
    if not CATALOG_FILE.exists():
        return []
    payload = json.loads(CATALOG_FILE.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        return []
    return payload.get("salas") or payload.get("catalogo") or []


def match_room_key(base: str, done_rooms: list[dict]) -> tuple[str, str]:
    base_compact = compact(base)
    base_tokens = tokens(base)
    alias_slug = PHOTO_ROOM_ALIASES.get(slugify(base))
    exact = []
    scored = []
    single_token_matches = []
    ignored_tokens = {"escape", "room", "sala", "seccion", "section"}

    for room in done_rooms:
        name = room.get("nombre") or ""
        room_slug = slugify(name)
        if not room_slug:
            continue
        if alias_slug and room_slug == alias_slug:
            return room_slug, name
        if compact(name) == base_compact:
            exact.append((room_slug, name))
            continue
        shared = len(base_tokens & tokens(name))
        if shared >= 2:
            scored.append((shared, room_slug, name))
        elif shared == 1:
            token = next(iter(base_tokens & tokens(name)))
            if len(token) >= 3 and token not in ignored_tokens:
                single_token_matches.append((room_slug, name, token))

    if len(exact) == 1:
        return exact[0]
    if scored:
        scored.sort(reverse=True)
        if len(scored) == 1 or scored[0][0] > scored[1][0]:
            return scored[0][1], scored[0][2]
    if len(single_token_matches) == 1:
        return single_token_matches[0][0], single_token_matches[0][1]
    return slugify(base), base


def build() -> dict:
    done_rooms = load_done_rooms()
    catalog_rooms = load_catalog_rooms()
    groups: dict[str, dict] = {}
    unmatched = []

    if PHOTOS_DIR.exists():
        for path in sorted(PHOTOS_DIR.iterdir(), key=lambda item: item.name.lower()):
            if not path.is_file() or path.suffix.lower() not in EXTENSIONS:
                continue
            base = photo_base(path)
            key, room_name = match_room_key(base, done_rooms)
            done_compacts = {compact(room.get("nombre")) for room in done_rooms}
            if key == slugify(base) and compact(base) not in done_compacts:
                key, room_name = match_room_key(base, catalog_rooms)
                catalog_compacts = {compact(room.get("nombre")) for room in catalog_rooms}
                if key == slugify(base) and compact(base) not in catalog_compacts:
                    unmatched.append(path.name)
            group = groups.setdefault(key, {"room": room_name, "photos": []})
            group["photos"].append({
                "src": path.relative_to(ROOT).as_posix(),
                "alt": f"{room_name} - foto del grupo",
            })

    payload = {
        "meta": {
            "generated_at": datetime.now().isoformat(timespec="seconds"),
            "source": PHOTOS_DIR.relative_to(ROOT).as_posix(),
            "groups": len(groups),
            "photos": sum(len(item["photos"]) for item in groups.values()),
            "unmatched": unmatched,
        },
        "photos": dict(sorted(groups.items())),
    }
    OUT_FILE.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return payload


if __name__ == "__main__":
    result = build()
    meta = result["meta"]
    print(f"review_photos.json generado -> {meta['photos']} fotos en {meta['groups']} reviews")
    if meta["unmatched"]:
        print("Fotos sin coincidencia exacta:")
        for name in meta["unmatched"]:
            print(f"- {name}")
