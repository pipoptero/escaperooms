#!/usr/bin/env python3
"""Importa al catalogo publico salas que existen solo en la BBDD privada.

La BBDD privada puede contener candidatas localizadas en fuentes externas antes
de que existan como ficha publica. Este script las convierte en fichas minimas
marcadas como ``new`` para que despues entren en el flujo normal de fuentes y
sinopsis.

No copia sinopsis ni imagenes. Tampoco publica enlaces de agregadores como
fuente de la ficha.
"""

from __future__ import annotations

import argparse
import json
import re
import sqlite3
import unicodedata
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse

import enrich_catalog_missing_content as enrich


ROOT = Path(__file__).resolve().parents[1]
CATALOG_FILE = ROOT / "catalog.json"
PRIVATE_DB = ROOT / "private" / "synopsis_sources.sqlite"
CLOSED_ROOMS_FILE = ROOT / "private" / "closed_rooms.json"
REPORTS_DIR = ROOT / "reports"
OUT_JSON = REPORTS_DIR / "private-rooms-to-catalog.json"
OUT_MD = REPORTS_DIR / "private-rooms-to-catalog.md"

AGGREGATOR_DOMAINS = {
    "escapecollector.com",
    "www.escapecollector.com",
    "escaperoomlover.com",
    "www.escaperoomlover.com",
    "escapeup.es",
    "www.escapeup.es",
    "roomescapes.es",
    "www.roomescapes.es",
    "todoescaperooms.com",
    "www.todoescaperooms.com",
    "escaperoos.es",
    "www.escaperoos.es",
    "room-escapers.com",
    "www.room-escapers.com",
}


def load_catalog_payload() -> dict:
    payload = json.loads(CATALOG_FILE.read_text(encoding="utf-8"))
    return {"catalogo": payload} if isinstance(payload, list) else payload


def load_json(path: Path, default):
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def clean(value) -> str:
    return " ".join(str(value or "").replace("\xa0", " ").split())


def compact(value) -> str:
    value = clean(value).lower()
    value = unicodedata.normalize("NFD", value)
    value = "".join(ch for ch in value if unicodedata.category(ch) != "Mn")
    return re.sub(r"[^a-z0-9]+", " ", value).strip()


def as_number(value):
    if value in (None, ""):
        return ""
    try:
        number = float(value)
        return int(number) if number.is_integer() else number
    except Exception:
        return value


def boolish(value) -> bool:
    if value in (None, ""):
        return False
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "si", "sí", "yes", "terror"}
    return bool(value)


def safe_public_url(url: str) -> str:
    url = enrich.normalize_url(url).split("#", 1)[0].strip()
    if not url:
        return ""
    host = urlparse(url).netloc.lower()
    if host.startswith("m."):
        host = host[2:]
    if host in AGGREGATOR_DOMAINS:
        return ""
    return url


def unique_id(base: str, used: set[str]) -> str:
    candidate = enrich.slugify(base) or "sala-nueva"
    original = candidate
    index = 2
    while candidate in used:
        candidate = f"{original}-{index}"
        index += 1
    used.add(candidate)
    return candidate


def catalog_keys(rooms: list[dict]) -> dict[str, set[str]]:
    keys = {"id": set(), "name_company_city": set(), "name_company": set(), "web": set()}
    for room in rooms:
        rid = clean(room.get("id"))
        if rid:
            keys["id"].add(rid)
        name = compact(room.get("nombre"))
        company = compact(room.get("empresa"))
        city = compact(room.get("ciudad"))
        if name and company and city:
            keys["name_company_city"].add(f"{name}|{company}|{city}")
        if name and company:
            keys["name_company"].add(f"{name}|{company}")
        web = safe_public_url(room.get("web") or "").rstrip("/")
        if web:
            keys["web"].add(web)
    return keys


def closed_room_keys() -> dict[str, set[str]]:
    payload = load_json(CLOSED_ROOMS_FILE, {"rooms": []})
    keys = {"id": set(), "name_company_city": set(), "name_company": set()}
    for room in payload.get("rooms", []) or []:
        rid = clean(room.get("id"))
        name = compact(room.get("nombre") or room.get("name"))
        company = compact(room.get("empresa") or room.get("company"))
        city = compact(room.get("ciudad") or room.get("city"))
        if rid:
            keys["id"].add(rid)
        if name and company and city:
            keys["name_company_city"].add(f"{name}|{company}|{city}")
        if name and company:
            keys["name_company"].add(f"{name}|{company}")
    return keys


def private_room_known(row: sqlite3.Row, keys: dict[str, set[str]]) -> bool:
    rid = clean(row["room_id"])
    name = compact(row["nombre"])
    company = compact(row["empresa"])
    city = compact(row["ciudad"])
    web = safe_public_url(row["web"] or "").rstrip("/")
    return (
        (rid and rid in keys["id"])
        or (name and company and city and f"{name}|{company}|{city}" in keys["name_company_city"])
        or (name and company and f"{name}|{company}" in keys["name_company"])
        or (web and web in keys["web"])
    )


def private_room_closed(row: sqlite3.Row, keys: dict[str, set[str]]) -> bool:
    rid = clean(row["room_id"])
    name = compact(row["nombre"])
    company = compact(row["empresa"])
    city = compact(row["ciudad"])
    return (
        (rid and rid in keys["id"])
        or (name and company and city and f"{name}|{company}|{city}" in keys["name_company_city"])
        or (name and company and f"{name}|{company}" in keys["name_company"])
    )


def best_source(conn: sqlite3.Connection, room_id: str) -> sqlite3.Row | None:
    return conn.execute(
        """
        select *
        from source_room_data
        where room_id = ? and status in ('ok', 'no_synopsis')
        order by
          case provider when 'official' then 0 else 1 end,
          match_score desc,
          length(coalesce(sinopsis_text, '')) desc
        limit 1
        """,
        (room_id,),
    ).fetchone()


def first(*values):
    for value in values:
        if value not in (None, ""):
            return value
    return ""


def build_room(row: sqlite3.Row, source: sqlite3.Row | None, used_ids: set[str], today: str) -> dict:
    official_url = ""
    if source and source["provider"] == "official":
        official_url = safe_public_url(source["final_url"] or source["source_url"] or "")
    official_url = official_url or safe_public_url(row["web"] or "")

    name = first(source["nombre"] if source else "", row["nombre"])
    company = first(source["empresa"] if source else "", row["empresa"])
    city = first(source["ciudad"] if source else "", row["ciudad"])
    room_id = unique_id(row["room_id"] or f"{name}-{company}-{city}", used_ids)

    return {
        "id": room_id,
        "nombre": name,
        "empresa": company,
        "ciudad": city,
        "provincia": first(source["provincia"] if source else "", row["provincia"]),
        "comunidad": first(source["comunidad"] if source else "", row["comunidad"]),
        "pais": "Espana",
        "duracion": as_number(source["duracion_min"] if source else ""),
        "min_personas": as_number(source["min_personas"] if source else ""),
        "max_personas": as_number(source["max_personas"] if source else ""),
        "terror": boolish(source["terror"] if source else ""),
        "web": official_url,
        "descripcion": "Sin sinopsis",
        "imagen": "",
        "rating": None,
        "votos": None,
        "verificado": False,
        "fuente_tipo": "pendiente_consenso",
        "fuente_url": official_url,
        "fuente_revisada": today,
        "estado_verificacion": "new",
        "estado_origen": "new",
        "estado_origen_fecha": today,
        "alta_policy": "importada_desde_bbdd_privada_sin_sinopsis_ni_imagen_de_agregadores",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Importa candidatas privadas no publicadas como fichas new.")
    parser.add_argument("--limit", type=int, default=50, help="0 = todas")
    parser.add_argument("--apply", action="store_true", help="Modifica catalog.json. Sin esto solo genera informe.")
    parser.add_argument("--db", type=Path, default=PRIVATE_DB)
    args = parser.parse_args()

    if not args.db.exists():
        raise SystemExit(f"No existe la base privada: {args.db}")

    payload = load_catalog_payload()
    rooms = payload.get("catalogo", [])
    keys = catalog_keys(rooms)
    closed_keys = closed_room_keys()
    used_ids = {clean(room.get("id")) for room in rooms if clean(room.get("id"))}
    today = datetime.now().date().isoformat()

    added: list[dict] = []
    skipped_known: list[dict] = []
    skipped_closed: list[dict] = []
    candidates: list[dict] = []

    with sqlite3.connect(args.db) as conn:
        conn.row_factory = sqlite3.Row
        private_rooms = conn.execute(
            """
            select room_id, nombre, empresa, ciudad, provincia, comunidad, web
            from rooms
            order by nombre, empresa, ciudad
            """
        ).fetchall()
        for row in private_rooms:
            if private_room_closed(row, closed_keys):
                skipped_closed.append(
                    {
                        "room_id": row["room_id"],
                        "nombre": row["nombre"],
                        "empresa": row["empresa"],
                        "ciudad": row["ciudad"],
                    }
                )
                continue
            if private_room_known(row, keys):
                continue
            source = best_source(conn, row["room_id"])
            providers = [
                item[0]
                for item in conn.execute(
                    "select distinct provider from source_room_data where room_id=? order by provider",
                    (row["room_id"],),
                )
            ]
            item = {
                "room_id": row["room_id"],
                "nombre": row["nombre"],
                "empresa": row["empresa"],
                "ciudad": row["ciudad"],
                "provincia": row["provincia"],
                "web": row["web"],
                "providers": providers,
            }
            candidates.append(item)
            if args.limit > 0 and len(added) >= args.limit:
                continue
            room = build_room(row, source, used_ids, today)
            if private_room_known(row, catalog_keys([*rooms, *added])):
                skipped_known.append(item)
                continue
            added.append(room)

    if args.apply and added:
        rooms.extend(added)
        rooms.sort(key=lambda room: (room.get("provincia") or "", room.get("ciudad") or "", room.get("nombre") or ""))
        payload.setdefault("meta", {})["count"] = len(rooms)
        payload["meta"]["updated_at"] = datetime.now().isoformat(timespec="seconds")
        CATALOG_FILE.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    REPORTS_DIR.mkdir(exist_ok=True)
    report = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "apply": args.apply,
        "policy": "importa fichas minimas new desde BBDD privada; no copia sinopsis ni imagenes",
        "private_candidates_not_in_catalog": len(candidates),
        "added": added,
        "skipped_known": skipped_known,
        "skipped_closed": skipped_closed,
    }
    OUT_JSON.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    lines = [
        "# Importacion de candidatas privadas al catalogo",
        "",
        f"Fecha: {report['generated_at']}",
        f"Modo: {'aplicado' if args.apply else 'dry-run'}",
        f"Candidatas privadas no publicadas: {len(candidates)}",
        f"Fichas new creadas: {len(added)}",
        f"Omitidas por cerradas: {len(skipped_closed)}",
        "",
    ]
    for room in added:
        lines.append(f"- {room['nombre']} | {room['empresa']} | {room['ciudad']} / {room['provincia']} | {room['web'] or 'sin web oficial'}")
    OUT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(f"Candidatas privadas no publicadas: {len(candidates)}")
    print(f"Fichas new creadas: {len(added)}")
    print(f"Omitidas por cerradas: {len(skipped_closed)}")
    print(f"Informe: {OUT_MD.relative_to(ROOT)}")
    if not args.apply:
        print("Dry-run: usa --apply para modificar catalog.json.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
