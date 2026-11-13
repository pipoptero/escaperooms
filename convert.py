#!/usr/bin/env python3
"""
Convierte un Excel privado del grupo en el data.json público.
La entrada y la salida se indican expresamente; no busca Excels en Git.
"""

import json
import sys
import re
import unicodedata
import argparse
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

parser = argparse.ArgumentParser(description="Genera data.json desde el Excel privado del grupo")
parser.add_argument("--input", required=True, type=Path, help="Excel privado explícito")
parser.add_argument("--output", required=True, type=Path, help="JSON de salida")
args = parser.parse_args()
EXCEL_FILE = args.input.expanduser().resolve()
OUTPUT_FILE = args.output.resolve()
if EXCEL_FILE.suffix.lower() != ".xlsx" or not EXCEL_FILE.is_file():
    parser.error("--input debe ser un archivo .xlsx existente")
if EXCEL_FILE.is_relative_to(Path(__file__).resolve().parent):
    parser.error("El Excel debe permanecer fuera del repositorio público")
if OUTPUT_FILE == EXCEL_FILE:
    parser.error("Entrada y salida deben ser archivos distintos")
print("📂 Leyendo Excel privado")

import openpyxl
wb = openpyxl.load_workbook(EXCEL_FILE, data_only=True)

# ── Detectar hojas ────────────────────────────────────────────────────────────
sheet_names = wb.sheetnames
pend_name  = next((s for s in sheet_names if "pend" in s.lower()), sheet_names[0])
hecho_name = next((s for s in sheet_names if any(x in s.lower() for x in ["hech","done","complet"])), sheet_names[1] if len(sheet_names) > 1 else sheet_names[0])

print(f"   Hoja Pendientes : {pend_name}")
print(f"   Hoja Hechos     : {hecho_name}")

# ── Mapa de columnas (flexible) ───────────────────────────────────────────────
COL_ALIASES = {
    "nombre":      ["nombre del escape", "nombre", "name", "escape"],
    "empresa":     ["empresa", "company"],
    "ciudad":      ["ciudad", "city", "location"],
    "provincia":   ["provincia", "province", "region"],
    "comunidad":   ["comunidad", "comunidad autÃ³noma", "comunidad autonoma", "autonomÃ­a", "autonomia", "ccaa"],
    "tematica":    ["temática", "tematica", "theme", "tema"],
    "generos":     ["géneros", "generos", "género", "genero", "genres", "genre", "categorías", "categorias"],
    "tipo":        ["tipo", "type"],
    "publico":     ["público", "publico", "audiencia", "audience"],
    "caracteristicas": ["características", "caracteristicas", "features", "tags", "extras"],
    "duracion":    ["duración", "duracion", "duración (min)", "duration", "min"],
    "dificultad":  ["dificultad", "difficulty"],
    "rating":      ["valoración", "valoracion", "rating escapistas", "rating", "score"],
    "rating_collector": ["rating collector", "valoración collector", "valoracion collector", "collector rating"],
    "votos":       ["votos", "opiniones", "reviews", "votes"],
    "web":         ["web", "url", "link"],
    "imagen":      ["imagen", "image", "foto", "photo", "cover", "portada", "url imagen", "image url"],
    "valoracion":  ["valoración grupo", "valoracion grupo", "group rating", "puntuación", "puntuacion"],
    "descripcion":   ["descripción", "descripcion", "description", "descripción del escape", "descripcion del escape", "descripción del room", "resumen"],
    "min_personas":  ["min_personas", "min personas", "mínimo jugadores", "minimo jugadores", "min players"],
    "max_personas":  ["max_personas", "max personas", "máximo jugadores", "maximo jugadores", "jugadores", "players", "max players", "capacidad"],
    "precio_min":    ["precio_min", "precio min", "precio mÃ­nimo", "precio minimo", "min_price", "min price", "desde"],
    "precio_max":    ["precio_max", "precio max", "precio mÃ¡ximo", "precio maximo", "max_price", "max price", "hasta"],
    "precio":        ["precio", "price", "tarifa", "coste"],
    "abierto":       ["abierto", "estado", "status", "open"],
    "verificado":    ["verificado", "verified"],
    "historia":      ["historia", "history"],
    "ambientacion":  ["ambientación", "ambientacion", "atmosphere"],
    "jugabilidad":   ["jugabilidad", "gameplay"],
    "gamemaster":    ["gamemaster", "game master", "gm", "game_master"],
    "terpeca":       ["posición terpeca", "posicion terpeca", "terpeca", "pos terpeca", "posición_terpeca"],
}

def find_col(headers, key):
    aliases = COL_ALIASES.get(key, [key])
    for alias in aliases:
        for i, h in enumerate(headers):
            if h and str(h).strip().lower() == alias.lower():
                return i
    return -1

def safe_str(val):
    """Convierte un valor de celda a string limpio, ignorando fechas y valores no textuales."""
    if val is None:
        return ""
    import datetime
    if isinstance(val, (datetime.date, datetime.datetime)):
        return ""
    s = str(val).strip()
    import re
    if re.match(r'^\d{4}-\d{2}-\d{2}', s):
        return ""
    return s

# Campos numéricos: float para notas, int para conteos/duraciones
NUMERIC_FIELDS  = {"rating", "rating_collector", "duracion", "valoracion", "historia", "ambientacion", "jugabilidad", "gamemaster", "terpeca", "precio_min", "precio_max"}
INTEGER_FIELDS  = {"duracion", "min_personas", "max_personas", "votos", "terpeca", "precio_min", "precio_max"}

def safe_num(val):
    """Convierte un valor a float limpio.
    Caso especial: Excel interpreta decimales como fechas (8.9 → 8 sep → datetime(2026,9,8))
    Se recupera el valor original como float(day.month).
    """
    if val is None:
        return ""
    import datetime
    if isinstance(val, (datetime.date, datetime.datetime)):
        # Reconstruir el decimal: día=8, mes=9 → 8.9
        return float(f"{val.day}.{val.month}")
    if isinstance(val, (int, float)):
        return val
    s = str(val).strip().replace(",", ".")
    try:
        return float(s)
    except ValueError:
        return ""

def slugify(text):
    text = str(text or "").strip().lower()
    text = unicodedata.normalize("NFD", text)
    text = "".join(ch for ch in text if unicodedata.category(ch) != "Mn")
    text = re.sub(r"[^a-z0-9]+", "-", text).strip("-")
    return text or "escape-room"

def local_image_for(nombre):
    slug = slugify(nombre)
    for extension in (".webp", ".png"):
        generated_path = Path(__file__).resolve().parent / "images" / "generated-catalog" / (slug + extension)
        if generated_path.exists():
            return generated_path.relative_to(Path(__file__).resolve().parent).as_posix()
    return ""

def parse_sheet(ws, debug_fields=None):
    rows = list(ws.iter_rows(values_only=True))
    if not rows:
        return []
    headers = [str(h).strip() if h is not None else "" for h in rows[0]]
    col_map = {key: find_col(headers, key) for key in COL_ALIASES}

    # Debug: mostrar qué columnas se detectaron
    print(f"   Columnas detectadas: { {k: (headers[v] if v >= 0 else 'NO ENCONTRADA') for k, v in col_map.items() if v >= 0} }")

    result = []
    for row in rows[1:]:
        nombre_idx = col_map["nombre"]
        if nombre_idx < 0 or nombre_idx >= len(row):
            continue
        val = row[nombre_idx]
        if val is None or str(val).strip() == "":
            continue
        # Ignorar si parece una fila de cabecera repetida
        if str(val).strip().lower() in ["nombre del escape", "nombre", "name", "escape"]:
            print(f"   ⚠ Cabecera repetida ignorada en fila: {list(row)[:4]}")
            continue

        obj = {}
        for key, idx in col_map.items():
            val = ""
            if idx >= 0 and idx < len(row) and row[idx] is not None:
                raw = row[idx]
                if key in NUMERIC_FIELDS or key in INTEGER_FIELDS:
                    val = safe_num(raw)
                    if key in INTEGER_FIELDS and isinstance(val, float):
                        val = int(val)
                else:
                    val = safe_str(raw)
            obj[key] = val
        local_image = local_image_for(obj.get("nombre"))
        if local_image:
            obj["imagen"] = local_image
        result.append(obj)
    return result

# ── Parsear hojas ─────────────────────────────────────────────────────────────
print(f"\n📋 Hoja Pendientes:")
pendientes_raw = parse_sheet(wb[pend_name])
# Deduplicar por nombre (conservar primera aparición)
seen = set()
pendientes = []
for p in pendientes_raw:
    key = str(p.get("nombre","")).strip().lower()
    if key and key not in seen:
        seen.add(key)
        pendientes.append(p)
if len(pendientes_raw) != len(pendientes):
    print(f"   ⚠ Duplicados eliminados: {len(pendientes_raw) - len(pendientes)}")

print(f"\n📋 Hoja Hechos:")
hechos_raw2 = parse_sheet(wb[hecho_name])
seen2 = set()
hechos_dedup = []
for h in hechos_raw2:
    key = str(h.get("nombre","")).strip().lower()
    if key and key not in seen2:
        seen2.add(key)
        hechos_dedup.append(h)
hechos = [h for h in hechos_dedup if h["nombre"]]

# Calcular ranking por valoración grupo (robusto ante valores no numéricos)
def safe_float(val):
    try:
        return float(val)
    except (ValueError, TypeError):
        return 0

hechos_sorted = sorted(hechos, key=lambda h: safe_float(h["valoracion"]), reverse=True)
for h in hechos:
    h["ranking"] = next((i + 1 for i, x in enumerate(hechos_sorted) if x["nombre"] == h["nombre"]), 0)

# ── Escribir data.json ────────────────────────────────────────────────────────
data = {
    "pendientes": pendientes,
    "hechos": hechos,
    "meta": {
        "source": EXCEL_FILE.name,
        "pendientes_count": len(pendientes),
        "hechos_count": len(hechos),
    }
}

OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
with OUTPUT_FILE.open("w", encoding="utf-8", newline="\n") as f:
    json.dump(data, f, ensure_ascii=False, indent=2)
    f.write("\n")

print(f"✅ JSON generado → {len(pendientes)} pendientes, {len(hechos)} hechos.")
