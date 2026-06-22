#!/usr/bin/env python3
"""Genera extra_awards.json desde premios publicos de escape rooms."""

import html
import json
import re
import unicodedata
from concurrent.futures import ThreadPoolExecutor, as_completed
from io import BytesIO
from pathlib import Path
from urllib.request import Request, urlopen

from pypdf import PdfReader

ROOT = Path(__file__).resolve().parents[1]
OUT_FILE = ROOT / "extra_awards.json"
CATALOG_FILE = ROOT / "catalog.json"
USER_AGENT = "scaperooms-extra-awards/1.0"
GIBA_AWARDS_URL = "https://www.gibaescape.com/proyectos/escape-room-giba-awards"
HORROR_AWARDS_CATEGORY_URL = "https://ocioterror.es/category/horror-awards/"

TEN_ESCAPES_URLS = {
    2025: "https://10escapes.com/ganadores25/",
    2024: "https://10escapes.com/ganadores24/",
    2023: "https://10escapes.com/ganadores23/",
}

ERA_PDFS = [
    {
        "year": 2024,
        "kind": "winners",
        "url": "https://escaperoomawardsoficial.com/wp-content/uploads/2025/04/RESULTADOS-GANADORES-ESCAPE-ROOM-AWARDS-2024.pdf",
    },
    {
        "year": 2024,
        "kind": "nominees",
        "url": "https://escaperoomawardsoficial.com/wp-content/uploads/2025/04/RESULTADOS-NOMINACIONES-ESCAPE-ROOM-AWARDS-2024.pdf",
    },
    {
        "year": 2023,
        "kind": "winners",
        "url": "https://escaperoomawardsoficial.com/wp-content/uploads/2024/05/RESULTADOS-VOTACIONES-ESCAPE-ROOM-AWARDS-2023-2.pdf",
    },
    {
        "year": 2023,
        "kind": "nominees",
        "url": "https://escaperoomawardsoficial.com/wp-content/uploads/2024/04/RESULTADOS-NOMINACIONES-JURADO-ESCAPE-ROOM-AWARDS-2023.pdf",
    },
]

COMMUNITIES = [
    "Comunidad de Madrid", "C. de Madrid", "Comunitat Valenciana", "Com. Valenciana",
    "C. Valenciana", "Catalunya", "Cataluña", "Euskadi", "Andalucia", "Andalucía",
    "Región de Murcia", "R. de Murcia", "Murcia", "Comunidad Foral de Navarra",
    "C. F. de Navarra", "Navarra", "Castilla y León", "Castilla-La Mancha",
    "Castilla - La Mancha", "Canarias", "Cantabria", "Aragón", "Aragon",
    "Asturias", "Galicia", "La Rioja", "Extremadura", "Islas Baleares",
    "Baleares",
]

ERA_CATEGORIES = {
    "ACTING": "Mejor acting",
    "PRUEBAS": "Mejores pruebas",
    "AMBIENTACION": "Mejor ambientacion",
    "AMBIENTACIÓN": "Mejor ambientacion",
    "ORIGINAL": "Mejor sala original",
    "EXPERIENCIA": "Mejor experiencia",
    "TERROR": "Mejor experiencia de terror",
    "MARKETING": "Mejor marketing inauguracion",
    "ESCAPE ROOM": "Mejor escape room",
    "SALA ORIGINAL": "Mejor sala original",
}

GIBA_EDITION_YEAR = {
    "VIII": 2025,
    "VII": 2024,
    "VI": 2023,
    "V": 2022,
    "IV": 2021,
    "III": 2020,
    "II": 2019,
    "I": 2018,
}


def slug_key(text):
    text = str(text or "").lower()
    text = unicodedata.normalize("NFD", text)
    text = "".join(ch for ch in text if unicodedata.category(ch) != "Mn")
    return re.sub(r"[^a-z0-9]+", " ", text).strip()


def compact_key(text):
    return re.sub(r"[^a-z0-9]+", "", slug_key(text))


def fetch_bytes(url):
    req = Request(url, headers={"User-Agent": USER_AGENT})
    with urlopen(req, timeout=60) as response:
        return response.read()


def fetch_text(url):
    return fetch_bytes(url).decode("utf-8", errors="replace")


def html_to_lines(page):
    page = re.sub(r"(?is)<script[^>]*>.*?</script>", " ", page)
    page = re.sub(r"(?is)<style[^>]*>.*?</style>", " ", page)
    page = re.sub(r"(?i)<br\s*/?>", "\n", page)
    page = re.sub(r"(?i)</(?:p|div|h[1-6]|li|tr)>", "\n", page)
    page = re.sub(r"<[^>]+>", " ", page)
    page = html.unescape(page)
    return [re.sub(r"\s+", " ", line).strip() for line in page.splitlines() if line.strip()]


def clean_room(text):
    text = re.sub(r"^\s*(?:B\s*)?\d+\s+", "", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip(" -")


def strip_community(text):
    for community in sorted(COMMUNITIES, key=len, reverse=True):
        pattern = r"\s+" + re.escape(community) + r"(?:\s*\+.*)?$"
        text = re.sub(pattern, "", text, flags=re.I).strip()
    return text


def split_room_company(text):
    text = strip_community(clean_room(text))
    parts = re.split(r"\s+[–-]\s+", text, maxsplit=1)
    if len(parts) == 1:
        return parts[0].strip(), ""
    return parts[0].strip(), parts[1].strip()


def add_award(awards, source_id, source_name, source_url, year, category, status, room, company="", rank=""):
    room = re.sub(r"\s+", " ", str(room or "")).strip(" -*")
    company = re.sub(r"\s+", " ", str(company or "")).strip(" -*")
    if not room or len(room) < 3:
        return
    awards.append({
        "source_id": source_id,
        "source_name": source_name,
        "source_url": source_url,
        "year": year,
        "category": category,
        "status": status,
        "rank": rank,
        "room": room,
        "room_key": slug_key(room),
        "company": company,
        "company_key": slug_key(company),
    })


def parse_10escapes(awards):
    for year, url in TEN_ESCAPES_URLS.items():
        lines = html_to_lines(fetch_text(url))
        in_list = False
        last_rank = 0
        saw_regular_rank = False
        for line in lines:
            normalized = slug_key(line)
            if ("listado room" in normalized or "lista completa room" in normalized):
                in_list = True
                continue
            if not in_list:
                continue
            if normalized.startswith("escape comunidad") or normalized.startswith("room comunidad"):
                continue
            if normalized.startswith("top nacional") or normalized.startswith("top comunidades"):
                break
            if not re.match(r"^(?:B\s*)?\d+\s+", line):
                continue
            rank_match = re.match(r"^(B\s*)?(\d+)\s+(.+)$", line)
            if not rank_match:
                continue
            best_of_best, rank, payload = rank_match.groups()
            rank = int(rank)
            if not best_of_best and saw_regular_rank and last_rank > 20 and 0 < rank < last_rank:
                break
            if not best_of_best:
                saw_regular_rank = True
                last_rank = rank
            room, company = split_room_company(payload)
            if not room:
                continue
            category = "Best of the Best" if best_of_best else "Top Room"
            status = "best_of_best" if best_of_best else ("winner" if rank <= 10 else "ranked")
            add_award(awards, "10escapes", "10Escapes", url, year, category, status, room, company, rank)


def split_giba_room_company(text):
    text = clean_room(text)
    if "|" in text:
        company, room = [part.strip() for part in text.split("|", 1)]
        return room, company
    match = re.match(r"(.+?)\s+\(([^()]+)\)\s*$", text)
    if match:
        return match.group(1).strip(), match.group(2).strip()
    return text, ""


def discover_horror_awards_posts(max_pages=4):
    posts = {}
    urls = [
        HORROR_AWARDS_CATEGORY_URL if page_num == 1 else f"{HORROR_AWARDS_CATEGORY_URL}page/{page_num}/"
        for page_num in range(1, max_pages + 1)
    ]

    def fetch_archive(url):
        try:
            return url, fetch_text(url)
        except Exception as exc:
            print(f"[WARN] No se pudo leer el archivo Horror Awards {url}: {exc}")
            return url, ""

    with ThreadPoolExecutor(max_workers=4) as executor:
        pages = [future.result() for future in as_completed(executor.submit(fetch_archive, url) for url in urls)]

    for _, page in pages:
        for match in re.finditer(r"<a[^>]+href=[\"']([^\"']+)[\"'][^>]*>(.*?)</a>", page, flags=re.I | re.S):
            href = html.unescape(match.group(1)).split("#", 1)[0]
            title = re.sub(r"<[^>]+>", " ", match.group(2))
            title = html.unescape(re.sub(r"\s+", " ", title)).strip()
            key = slug_key(title)
            if "horror awards" not in key:
                continue
            if "ganadores" not in key and "nominados" not in key:
                continue
            if "novedades" in key or "llega" in key:
                continue
            year_match = re.search(r"(20\d{2})", title)
            if not year_match:
                continue
            posts[href] = {
                "url": href,
                "title": title,
                "year": int(year_match.group(1)),
                "kind": "winners" if "ganadores" in key else "nominees",
            }
    return list(posts.values())


def horror_category_from_line(line):
    key = slug_key(line)
    if "horror awards" in key and ("ganadores" in key or "nominados" in key):
        return ""
    if "premio horrorifico" in key:
        return "Premio Horrorifico"
    if ("best " in key or key.startswith("best ") or "mejor " in key or key.startswith("mejor ") or "nominados best" in key or "nominados mejor" in key) and not key.startswith(("ganador", "2o", "3er")):
        category = re.sub(r"(?i)^nominados\s+", "", line).strip()
        category = re.sub(r"\s*\(.*?\)\s*", " ", category)
        category = re.sub(r"\b20\d{2}\b", "", category)
        return re.sub(r"\s+", " ", category).strip(" :-")
    return ""


def split_horror_room_company(text):
    text = re.sub(r"(?i)^(ganador|2[ºo]\s*premio|3(?:er|º|o)\s*premio)\s*:\s*", "", text).strip()
    text = clean_room(text)
    parts = re.split(r"\s*[\u2013\u2014-]\s*", text, maxsplit=1)
    if len(parts) == 1:
        return parts[0].strip(), ""
    return parts[0].strip(), parts[1].strip()


def horror_winner_rank(line):
    key = slug_key(line)
    if key.startswith("ganador"):
        return 1
    if key.startswith("2o premio") or key.startswith("2 premio"):
        return 2
    if key.startswith("3er premio") or key.startswith("3o premio") or key.startswith("3 premio"):
        return 3
    return None


def parse_horror_awards(awards, catalog_rooms):
    posts = discover_horror_awards_posts()

    def fetch_post(post):
        try:
            return post, html_to_lines(fetch_text(post["url"]))
        except Exception as exc:
            print(f"[WARN] No se pudo leer Horror Awards {post['url']}: {exc}")
            return post, []

    with ThreadPoolExecutor(max_workers=4) as executor:
        fetched_posts = [future.result() for future in as_completed(executor.submit(fetch_post, post) for post in posts)]

    for post, lines in fetched_posts:
        category = ""
        ex_aequo = False
        horrorifico_pending = False
        for line in lines:
            key = slug_key(line)
            if key in {"relacionado", "descubre mas desde ocioterror"} or key.startswith("publicado por"):
                break
            maybe_category = horror_category_from_line(line)
            if maybe_category:
                category = maybe_category
                ex_aequo = False
                horrorifico_pending = "premio horrorifico" in slug_key(category)
                continue
            if not category:
                continue
            if "premio ex aequo" in key:
                ex_aequo = True
                continue
            if key.startswith(("enhorabuena", "si quieres", "entra en este enlace", "encuesta", "video del anuncio", "la encuesta")):
                continue

            rank = horror_winner_rank(line) if post["kind"] == "winners" else None
            status = "nominee"
            if post["kind"] == "winners":
                if rank is None and not ex_aequo and not horrorifico_pending:
                    continue
                rank = rank or 1
                status = "winner" if rank == 1 else "runner_up"

            room, company = split_horror_room_company(line)
            if not room or len(room) < 3:
                continue
            if any(noise in slug_key(room) for noise in ["horror awards", "suscribete", "correo electronico", "youtube", "instagram"]):
                continue

            catalog_room = match_catalog_room(f"{room} {company}", catalog_rooms) or match_catalog_room(room, catalog_rooms)
            if catalog_room:
                room = catalog_room["name"]
                if catalog_room.get("company"):
                    company = catalog_room["company"]

            add_award(
                awards,
                "horror_awards",
                "Horror Awards",
                post["url"],
                post["year"],
                category,
                status,
                room,
                company,
                rank or "",
            )
            if horrorifico_pending:
                horrorifico_pending = False


def parse_giba_awards(awards, catalog_rooms):
    lines = html_to_lines(fetch_text(GIBA_AWARDS_URL))
    year = None
    for index, line in enumerate(lines):
        explicit_year = re.match(r"^GIBA AWARDS\s+(20\d{2})\s*$", line, flags=re.I)
        if explicit_year:
            year = int(explicit_year.group(1))
            continue
        edition = re.match(r"^GIBA AWARDS\s+([IVX]+)\s+EDICI", line, flags=re.I)
        if edition:
            year = GIBA_EDITION_YEAR.get(edition.group(1).upper())
            continue
        if not year:
            continue
        category_line = re.match(r"^([123])\.\s*(.+)$", line)
        if not category_line:
            continue
        if index + 1 >= len(lines) or lines[index + 1].startswith("GIBA AWARDS"):
            continue
        rank = int(category_line.group(1))
        category = re.sub(r"\s+", " ", category_line.group(2)).strip()
        room, company = split_giba_room_company(lines[index + 1])
        catalog_room = match_catalog_room(f"{room} {company}", catalog_rooms) or match_catalog_room(room, catalog_rooms)
        if catalog_room:
            room = catalog_room["name"]
            if catalog_room.get("company"):
                company = catalog_room["company"]
        status = "winner" if rank == 1 else "runner_up"
        add_award(awards, "giba_awards", "Giba Awards", GIBA_AWARDS_URL, year, category, status, room, company, rank)


def load_catalog_rooms():
    data = json.loads(CATALOG_FILE.read_text(encoding="utf-8"))
    rooms = []
    for item in data.get("catalogo", []):
        name = item.get("nombre") or ""
        if not name:
            continue
        rooms.append({
            "name": name,
            "name_key": slug_key(name),
            "name_compact": compact_key(name),
            "company": item.get("empresa") or "",
        })
    return sorted(rooms, key=lambda item: len(item["name_key"]), reverse=True)


def extract_pdf_lines(url):
    reader = PdfReader(BytesIO(fetch_bytes(url)))
    lines = []
    for page in reader.pages:
        text = page.extract_text() or ""
        lines.extend(re.sub(r"\s+", " ", line).strip() for line in text.splitlines() if line.strip())
    return lines


def era_category_from_line(line):
    key = slug_key(line)
    for token, label in ERA_CATEGORIES.items():
        if slug_key(token) in key:
            return label
    return ""


def match_catalog_room(payload, catalog_rooms):
    key = slug_key(payload)
    compact = compact_key(payload)
    for room in catalog_rooms:
        room_key = room["name_key"]
        room_compact = room["name_compact"]
        if key.startswith(room_key + " ") or key == room_key or compact.startswith(room_compact):
            return room
    return None


def parse_era_pdf(awards, spec, catalog_rooms):
    try:
        lines = extract_pdf_lines(spec["url"])
    except Exception as exc:
        print(f"[WARN] No se pudo leer ERA {spec['year']} {spec['kind']}: {exc}")
        return
    category = ""
    for line in lines:
        maybe_category = era_category_from_line(line)
        if maybe_category and not re.match(r"^\d+\s+", line):
            category = maybe_category
            continue
        row = re.match(r"^(\d+)\s*(.+)$", line)
        if not row or not category:
            continue
        rank = int(row.group(1))
        if rank > 30:
            continue
        room = match_catalog_room(row.group(2), catalog_rooms)
        if not room:
            continue
        if spec["kind"] == "winners":
            if rank > 3:
                continue
            status = "winner" if rank == 1 else "runner_up"
        else:
            status = "nominee"
        add_award(
            awards,
            "escape_room_awards",
            "Escape Room Awards",
            spec["url"],
            spec["year"],
            category,
            status,
            room["name"],
            room["company"],
            rank,
        )


def dedupe(awards):
    priority = {"nominee": 1, "ranked": 2, "runner_up": 3, "winner": 4, "best_of_best": 5}
    unique = {}
    for award in awards:
        key = (
            award["source_id"],
            award["year"],
            award["category"],
            award["room_key"],
            award.get("company_key", ""),
        )
        current = unique.get(key)
        if not current or priority.get(award["status"], 0) >= priority.get(current["status"], 0):
            unique[key] = award
    return list(unique.values())


def build():
    awards = []
    catalog_rooms = load_catalog_rooms()
    parse_10escapes(awards)
    parse_giba_awards(awards, catalog_rooms)
    parse_horror_awards(awards, catalog_rooms)
    for spec in ERA_PDFS:
        parse_era_pdf(awards, spec, catalog_rooms)
    awards = dedupe(awards)
    awards.sort(key=lambda item: (
        item["source_id"],
        -item["year"],
        item["category"],
        item["rank"] if isinstance(item["rank"], int) else 999,
        item["room"],
    ))
    OUT_FILE.write_text(json.dumps({
        "meta": {
            "sources": [
                "https://10escapes.com/",
                "https://escaperoomawardsoficial.com/",
                GIBA_AWARDS_URL,
                HORROR_AWARDS_CATEGORY_URL,
            ],
            "count": len(awards),
            "by_source": {
                "10escapes": sum(1 for item in awards if item["source_id"] == "10escapes"),
                "escape_room_awards": sum(1 for item in awards if item["source_id"] == "escape_room_awards"),
                "giba_awards": sum(1 for item in awards if item["source_id"] == "giba_awards"),
                "horror_awards": sum(1 for item in awards if item["source_id"] == "horror_awards"),
            },
        },
        "awards": awards,
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"extra_awards.json generado -> {len(awards)} premios")


if __name__ == "__main__":
    build()
