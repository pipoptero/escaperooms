#!/usr/bin/env python3
"""Genera external_ratings.json con puntuaciones externas para el ranking global.

El script esta pensado para mantenimiento local automatizado:
- conserva datos previos si una fuente falla;
- nunca borra puntuaciones por un fallo temporal;
- usa emparejamiento tolerante por nombre, empresa y ciudad.
"""

from __future__ import annotations

import json
import math
import re
import unicodedata
from datetime import datetime
from html.parser import HTMLParser
from pathlib import Path
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
CATALOG_FILE = ROOT / "catalog.json"
DATA_FILE = ROOT / "data.json"
RATINGS_FILE = ROOT / "external_ratings.json"

USER_AGENT = "the-vault-ratings-builder/1.0 (+local personal maintenance)"
GIBA_URL = "https://www.gibaescape.com/ranking/ranking-salas-de-escape"
OCIOTERROR_URL = "https://ocioterror.es/mejores-experiencias-terror/mejores-escape-room-de-terror/"

SOURCE_META = {
    "escape_collector": {
        "label": "Escape Collector",
        "weight": 1.2,
        "kind": "community",
        "url": "https://escapecollector.com/escape-rooms",
    },
    "giba": {
        "label": "Giba Escape",
        "weight": 1.0,
        "kind": "editorial",
        "url": GIBA_URL,
    },
    "ocioterror": {
        "label": "OcioTerror",
        "weight": 1.0,
        "kind": "editorial_terror",
        "url": OCIOTERROR_URL,
    },
    "escaperoomlover": {
        "label": "Escape Room Lover",
        "weight": 1.0,
        "kind": "pending_adapter",
        "url": "https://www.escaperoomlover.com/es",
    },
}


class TextParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.texts: list[str] = []

    def handle_data(self, data: str) -> None:
        text = " ".join(data.split())
        if text:
            self.texts.append(text)


def load_json(path: Path, default):
    if not path.exists():
        return default
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def slugify(text: str) -> str:
    text = str(text or "").strip().lower()
    text = unicodedata.normalize("NFD", text)
    text = "".join(ch for ch in text if unicodedata.category(ch) != "Mn")
    text = re.sub(r"[^a-z0-9]+", "_", text).strip("_")
    return text


def normalized(text: str) -> str:
    text = str(text or "").strip().lower()
    text = unicodedata.normalize("NFD", text)
    text = "".join(ch for ch in text if unicodedata.category(ch) != "Mn")
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return " ".join(text.split())


def compact(text: str) -> str:
    return normalized(text).replace(" ", "")


def parse_score(value) -> float | None:
    if value in ("", None):
        return None
    try:
        score = float(str(value).replace(",", "."))
    except ValueError:
        return None
    if 0 < score <= 10:
        return round(score, 2)
    return None


def fetch_text(url: str) -> str:
    req = Request(url, headers={"User-Agent": USER_AGENT})
    with urlopen(req, timeout=45) as response:
        return response.read().decode("utf-8", errors="replace")


def html_texts(html: str) -> list[str]:
    parser = TextParser()
    parser.feed(html)
    return parser.texts


def catalog_rooms() -> list[dict]:
    payload = load_json(CATALOG_FILE, {"catalogo": []})
    return payload.get("catalogo", []) if isinstance(payload, dict) else payload


def local_rooms() -> list[dict]:
    payload = load_json(DATA_FILE, {"pendientes": [], "hechos": []})
    rooms = []
    if isinstance(payload, dict):
        rooms.extend(payload.get("pendientes", []) or [])
        rooms.extend(payload.get("hechos", []) or [])
    return rooms


def room_key(room: dict) -> str:
    return slugify(room.get("nombre") or room.get("id") or room.get("empresa") or "")


def room_tokens(room: dict) -> set[str]:
    tokens = {
        compact(room.get("nombre", "")),
        compact(f"{room.get('nombre', '')} {room.get('empresa', '')}"),
        compact(f"{room.get('empresa', '')} {room.get('nombre', '')}"),
    }
    room_id = room.get("id")
    if room_id:
        tokens.add(compact(room_id))
    return {token for token in tokens if token}


def build_room_index(rooms: list[dict]) -> tuple[dict[str, dict], dict[str, set[str]]]:
    by_key: dict[str, dict] = {}
    token_to_keys: dict[str, set[str]] = {}
    for room in rooms:
        key = room_key(room)
        if not key:
            continue
        by_key.setdefault(key, room)
        for token in room_tokens(room):
            token_to_keys.setdefault(token, set()).add(key)
    return by_key, token_to_keys


def split_external_title(title: str) -> tuple[str, str]:
    clean = re.sub(r"\s+", " ", str(title or "")).strip(" -")
    parts = [part.strip() for part in re.split(r"\s+-\s+|,\s+", clean) if part.strip()]
    if len(parts) >= 2:
        return parts[0], parts[-1]
    return clean, ""


def match_external(title: str, location: str, by_key: dict[str, dict], token_to_keys: dict[str, set[str]]) -> str:
    name, company = split_external_title(title)
    candidates = [
        compact(name),
        compact(f"{name} {company}"),
        compact(f"{company} {name}"),
        compact(title),
    ]
    for candidate in candidates:
        keys = token_to_keys.get(candidate)
        if keys and len(keys) == 1:
            return next(iter(keys))

    title_norm = normalized(title)
    location_norm = normalized(location)
    scored: list[tuple[int, str]] = []
    for key, room in by_key.items():
        room_name = normalized(room.get("nombre", ""))
        room_company = normalized(room.get("empresa", ""))
        room_city = normalized(room.get("ciudad", ""))
        room_prov = normalized(room.get("provincia", ""))
        score = 0
        if room_name and room_name in title_norm:
            score += 5
        if room_company and room_company in title_norm:
            score += 3
        if room_city and room_city in location_norm:
            score += 2
        if room_prov and room_prov in location_norm:
            score += 1
        if score >= 6:
            scored.append((score, key))
    if not scored:
        return ""
    scored.sort(reverse=True)
    if len(scored) > 1 and scored[0][0] == scored[1][0]:
        return ""
    return scored[0][1]


def source_record(score: float, source_id: str, **extra) -> dict:
    record = {
        "score": round(float(score), 2),
        "weight": SOURCE_META[source_id]["weight"],
        "url": SOURCE_META[source_id]["url"],
        "updated_at": datetime.now().date().isoformat(),
    }
    record.update({k: v for k, v in extra.items() if v not in ("", None)})
    return record


def collect_escape_collector(rooms: list[dict]) -> dict[str, dict]:
    result: dict[str, dict] = {}
    for room in rooms:
        score = parse_score(room.get("rating"))
        if not score:
            continue
        votes = int(room.get("votos") or 0)
        weight = SOURCE_META["escape_collector"]["weight"]
        if votes:
            weight = round(weight * min(1.25, 0.75 + math.log10(votes + 1) / 4), 2)
        record = source_record(score, "escape_collector", votes=votes)
        record["weight"] = weight
        result[room_key(room)] = record
    return result


def collect_giba(by_key: dict[str, dict], token_to_keys: dict[str, set[str]]) -> tuple[dict[str, dict], dict]:
    texts = html_texts(fetch_text(GIBA_URL))
    result: dict[str, dict] = {}
    matched = 0
    seen_titles = 0
    for i, text in enumerate(texts):
        if len(text) < 3 or text.upper() in {"INICIO", "RANKINGS:", "OPINIONES"}:
            continue
        window = texts[i + 1:i + 7]
        joined = " ".join(window)
        score = None
        rank_match = re.search(r"\bTOP\s+(\d+)\b", joined, re.I)
        score_match = next((parse_score(item) for item in window if re.fullmatch(r"\d+(?:[,.]\d+)?", item or "")), None)
        if rank_match:
            score = 10.0
        elif "Golden Giba" in joined:
            score = 10.0
        elif score_match:
            score = score_match
        if not score:
            continue
        if any(skip in text.lower() for skip in ["ranking", "voto", "golden giba", "anunciantes"]):
            continue
        location = joined
        key = match_external(text, location, by_key, token_to_keys)
        seen_titles += 1
        if key and key not in result:
            matched += 1
            result[key] = source_record(score, "giba", source_title=text)
    return result, {"found": seen_titles, "matched": matched}


def collect_ocioterror(by_key: dict[str, dict], token_to_keys: dict[str, set[str]]) -> tuple[dict[str, dict], dict]:
    texts = html_texts(fetch_text(OCIOTERROR_URL))
    result: dict[str, dict] = {}
    matched = 0
    found = 0
    for i, text in enumerate(texts):
        window = texts[i + 1:i + 8]
        note = parse_score(window[0] if window else "")
        fear = parse_score(window[1] if len(window) > 1 else "")
        if note is None or fear is None:
            continue
        if len(text) < 4 or text.lower().startswith(("ranking", "review")):
            continue
        location = " ".join(window[2:])
        key = match_external(text, location, by_key, token_to_keys)
        found += 1
        if key and key not in result:
            matched += 1
            result[key] = source_record(note, "ocioterror", fear_score=fear, source_title=text)
    return result, {"found": found, "matched": matched}


def merge_previous(payload: dict, generated: dict, statuses: dict) -> dict:
    previous = payload.get("ratings", {}) if isinstance(payload, dict) else {}
    for key, old_rating in previous.items():
        if key not in generated:
            continue
        old_sources = old_rating.get("sources", {}) or {}
        new_sources = generated[key].setdefault("sources", {})
        for source_id, old_source in old_sources.items():
            if source_id not in new_sources and statuses.get(source_id, {}).get("ok") is False:
                preserved = dict(old_source)
                preserved["stale"] = True
                new_sources[source_id] = preserved
    return generated


def compute_global_scores(ratings: dict[str, dict]) -> None:
    for item in ratings.values():
        sources = item.get("sources", {})
        weighted = []
        for source in sources.values():
            score = parse_score(source.get("score"))
            weight = float(source.get("weight") or 1)
            if score:
                weighted.append((score, weight))
        if not weighted:
            item["global_score"] = None
            item["source_count"] = 0
            continue
        total_weight = sum(weight for _, weight in weighted)
        item["global_score"] = round(sum(score * weight for score, weight in weighted) / total_weight, 2)
        item["source_count"] = len(weighted)


def build():
    rooms = catalog_rooms()
    all_rooms = []
    seen = set()
    for room in rooms + local_rooms():
        key = room_key(room)
        if key and key not in seen:
            all_rooms.append(room)
            seen.add(key)

    by_key, token_to_keys = build_room_index(all_rooms)
    previous_payload = load_json(RATINGS_FILE, {"ratings": {}})
    statuses = {}
    ratings: dict[str, dict] = {
        key: {
            "room": {
                "nombre": room.get("nombre", ""),
                "empresa": room.get("empresa", ""),
                "ciudad": room.get("ciudad", ""),
                "provincia": room.get("provincia", ""),
            },
            "sources": {},
        }
        for key, room in by_key.items()
    }

    collector = collect_escape_collector(rooms)
    for key, record in collector.items():
        ratings.setdefault(key, {"room": {}, "sources": {}})["sources"]["escape_collector"] = record
    statuses["escape_collector"] = {"ok": True, "matched": len(collector), "found": len(collector)}

    for source_id, collector_fn in (("giba", collect_giba), ("ocioterror", collect_ocioterror)):
        try:
            records, stat = collector_fn(by_key, token_to_keys)
            for key, record in records.items():
                ratings.setdefault(key, {"room": {}, "sources": {}})["sources"][source_id] = record
            statuses[source_id] = {"ok": True, **stat}
        except Exception as exc:
            statuses[source_id] = {"ok": False, "error": str(exc)}

    statuses["escaperoomlover"] = {
        "ok": False,
        "error": "Adaptador pendiente: no se ha localizado una puntuacion publica estable.",
    }

    ratings = merge_previous(previous_payload, ratings, statuses)
    ratings = {key: value for key, value in ratings.items() if value.get("sources")}
    compute_global_scores(ratings)

    payload = {
        "meta": {
            "generated_at": datetime.now().isoformat(timespec="seconds"),
            "sources": SOURCE_META,
            "statuses": statuses,
            "count": len(ratings),
            "with_multiple_sources": sum(1 for item in ratings.values() if item.get("source_count", 0) > 1),
        },
        "ratings": dict(sorted(ratings.items(), key=lambda item: (item[1].get("global_score") or 0), reverse=True)),
    }
    RATINGS_FILE.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(
        "external_ratings.json generado -> "
        f"{payload['meta']['count']} salas, "
        f"{payload['meta']['with_multiple_sources']} con varias fuentes"
    )
    for source_id, status in statuses.items():
        if status.get("ok"):
            print(f"OK   {source_id}: {status.get('matched', 0)} enlazadas de {status.get('found', 0)}")
        else:
            print(f"WARN {source_id}: {status.get('error')}")


if __name__ == "__main__":
    build()
