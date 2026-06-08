#!/usr/bin/env python3
"""Genera terpeca_awards.json desde los resultados publicos de TERPECA."""

import html
import json
import re
import unicodedata
from pathlib import Path
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
OUT_FILE = ROOT / "terpeca_awards.json"
YEAR = 2025
SOURCE_URL = "https://www.terpeca.com/"
USER_AGENT = "scaperooms-terpeca-awards/1.0"


def slug_key(text):
    text = str(text or "").lower()
    text = unicodedata.normalize("NFD", text)
    text = "".join(ch for ch in text if unicodedata.category(ch) != "Mn")
    return re.sub(r"[^a-z0-9]+", " ", text).strip()


def clean_room_text(text):
    text = html.unescape(re.sub(r"<[^>]+>", "", text))
    text = re.sub(r"[\U0001F1E6-\U0001F1FF\U0001F300-\U0001FAFF]+", "", text)
    return re.sub(r"\s+", " ", text).strip()


def split_room_line(line):
    """Devuelve nombre/empresa desde 'Room - Company (City, Country) (n)'."""
    line = clean_room_text(line)
    line = re.sub(r"\s+\(\d+\).*$", "", line)
    line = re.sub(r"\s+\([^()]*,\s*[^()]*\)\s*$", "", line)
    if " - " not in line:
        return line, ""
    room, company = line.split(" - ", 1)
    return room.strip(), company.strip()


def fetch_html():
    req = Request(SOURCE_URL, headers={"User-Agent": USER_AGENT})
    with urlopen(req, timeout=45) as response:
        return response.read().decode("utf-8", errors="replace")


def upsert(awards, room, company, status, rank=None, nominations=None):
    key = f"{slug_key(room)}|{slug_key(company)}"
    if not key:
        return
    current = awards.setdefault(key, {
        "room": room,
        "room_key": slug_key(room),
        "company": company,
        "company_key": slug_key(company),
        "year": YEAR,
        "status": "nominee",
        "rank": "",
        "nominations": "",
        "source": SOURCE_URL,
    })
    if company and not current.get("company"):
        current["company"] = company
    if nominations and not current.get("nominations"):
        current["nominations"] = nominations
    priority = {"nominee": 1, "finalist": 2, "winner": 3}
    if priority[status] >= priority.get(current["status"], 0):
        current["status"] = status
        if rank:
            current["rank"] = rank


def parse_phase1(page, awards):
    start = page.index("START PHASE 1 ROOM RESULTS")
    end = page.index("END PHASE 1 ROOM RESULTS", start)
    section = page[start:end]
    for raw in re.split(r"<br\s*/?>", section):
        if " - " not in raw:
            continue
        finalist = "<strong>" in raw
        nominations_match = re.search(r"\((\d+)\)\s*(?:</strong>)?\s*[^()]*$", raw)
        nominations = int(nominations_match.group(1)) if nominations_match else ""
        room, company = split_room_line(raw)
        upsert(awards, room, company, "finalist" if finalist else "nominee", nominations=nominations)


def parse_phase2(page, awards):
    start = page.index("START PHASE 2 ROOM RESULTS")
    end = page.index("END PHASE 2 ROOM RESULTS", start)
    section = page[start:end]
    rows = re.findall(r"<div class='tablerow'>(.*?)</div>\s*</div>", section, flags=re.S)
    for row in rows:
        rank_match = re.search(r"data-title='Rank'.*?<strong>(\d+)</strong>", row, flags=re.S)
        room_match = re.search(r"data-title='Room'.*?<strong>(.*?)</strong>", row, flags=re.S)
        if not rank_match or not room_match:
            continue
        rank = int(rank_match.group(1))
        room, company = split_room_line(room_match.group(1))
        upsert(awards, room, company, "winner" if rank <= 100 else "finalist", rank=rank)


def build():
    page = fetch_html()
    awards = {}
    parse_phase1(page, awards)
    parse_phase2(page, awards)
    result = sorted(awards.values(), key=lambda x: (x["status"] != "winner", x.get("rank") or 9999, x["room"]))
    OUT_FILE.write_text(json.dumps({
        "meta": {
            "source": SOURCE_URL,
            "year": YEAR,
            "count": len(result),
            "winners": sum(1 for item in result if item["status"] == "winner"),
            "finalists": sum(1 for item in result if item["status"] == "finalist"),
            "nominees": sum(1 for item in result if item["status"] == "nominee"),
        },
        "awards": result,
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"terpeca_awards.json generado -> {len(result)} salas")


if __name__ == "__main__":
    build()
