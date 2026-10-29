"""Generate the exact season/entity guard for RTDB review rules from public Scream Parks data."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CATALOG = ROOT / "scream-parks" / "data-2026.json"
RULES = ROOT / "database.rules.json"
SERVER_IDENTITIES = ROOT / "functions" / "season-identities.json"
MARKERS = ('    "screamParkReviewSubmissions": {', '    "screamParkReviews": {')


def main():
    catalog = json.loads(CATALOG.read_text(encoding="utf-8"))
    historical = json.loads((ROOT / "scream-parks" / "review-seasons.json").read_text(encoding="utf-8"))
    assert historical["schemaVersion"] == 1
    entity_ids = {item["id"] for item in catalog["entries"]}
    pairs = sorted([(item["seasonId"], item["id"]) for item in catalog["entries"]]
                   + [(item["seasonId"], item["entityId"]) for item in historical["historicalSeasons"]])
    assert len(pairs) == len(set(pairs)) and all(entity in entity_ids for _, entity in pairs)
    SERVER_IDENTITIES.parent.mkdir(parents=True, exist_ok=True)
    SERVER_IDENTITIES.write_text(json.dumps(dict(pairs), ensure_ascii=False, sort_keys=True,
                                           indent=2) + "\n", encoding="utf-8")
    season_expr = " || ".join(f"$seasonId === '{season}'" for season, _ in pairs)
    branch = {
        "screamParkReviews": {
            "$seasonId": {
                ".write": False,
                "approved": {".read": season_expr},
                "submissions": {"$uid": {".read": "auth != null && auth.uid === $uid"}},
                "moderation": {".read": False},
                "audit": {".read": False},
            }
        },
    }
    text = RULES.read_text(encoding="utf-8")
    marker = next((item for item in MARKERS if item in text), None)
    if marker:
        start = text.index(marker)
        end = text.index('    "profiles": {', start)
        text = text[:start] + text[end:]
    payload = "".join(f"    {json.dumps(name)}: {json.dumps(value, ensure_ascii=False, indent=2)},\n"
                      for name, value in branch.items())
    # Indentation is cosmetic; JSON rules are parsed before deployment.
    text = text.replace('    "profiles": {', payload + '    "profiles": {', 1)
    RULES.write_text(text, encoding="utf-8")


if __name__ == "__main__":
    main()
