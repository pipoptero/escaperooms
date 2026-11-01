"""Generate the season-scoped RTDB rules for public Scream Park reviews."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CATALOG = ROOT / "scream-parks" / "data-2026.json"
RULES = ROOT / "database.rules.json"
MARKERS = ('    "screamParkReviewSubmissions": {', '    "screamParkReviews": {')
CATEGORIES = ("ambientacion", "acting", "organizacion", "terror", "variedad")


def main():
    catalog = json.loads(CATALOG.read_text(encoding="utf-8"))
    historical = json.loads((ROOT / "scream-parks" / "review-seasons.json").read_text(encoding="utf-8"))
    assert historical["schemaVersion"] == 1
    entity_ids = {item["id"] for item in catalog["entries"]}
    pairs = sorted([(item["seasonId"], item["id"]) for item in catalog["entries"]]
                   + [(item["seasonId"], item["entityId"]) for item in historical["historicalSeasons"]])
    assert len(pairs) == len(set(pairs)) and all(entity in entity_ids for _, entity in pairs)
    season_expr = " || ".join(f"$seasonId === '{season}'" for season, _ in pairs)
    identity_expr = " || ".join(
        f"($seasonId === '{season}' && newData.child('entityId').val() === '{entity}')"
        for season, entity in pairs
    )
    score_rule = "newData.isNumber() && newData.val() >= 0.5 && newData.val() <= 5 && (newData.val() * 2) % 1 === 0"
    branch = {
        "screamParkReviews": {
            "$seasonId": {
                ".read": season_expr,
                "$uid": {
                    ".write": (
                        f"auth != null && ({season_expr}) && ((auth.uid === $uid && newData.exists()) || "
                        "(!newData.exists() && (auth.uid === $uid || "
                        "root.child('admins/' + auth.uid).val() === true)))"
                    ),
                    ".validate": (
                        "newData.hasChildren(['entityId','seasonId','userName','scores','text',"
                        "'createdAt','updatedAt','revision']) && "
                        f"({identity_expr}) && newData.child('seasonId').val() === $seasonId && "
                        "newData.child('createdAt').isNumber() && "
                        "(data.exists() ? newData.child('createdAt').val() === data.child('createdAt').val() : "
                        "(newData.child('createdAt').val() >= now - 300000 && "
                        "newData.child('createdAt').val() <= now + 300000)) && "
                        "newData.child('updatedAt').isNumber() && "
                        "newData.child('updatedAt').val() >= now - 300000 && "
                        "newData.child('updatedAt').val() <= now + 300000 && "
                        "newData.child('updatedAt').val() >= newData.child('createdAt').val() && "
                        "newData.child('revision').isNumber() && "
                        "newData.child('revision').val() === (data.exists() ? data.child('revision').val() + 1 : 1)"
                    ),
                    "entityId": {".validate": "newData.isString()"},
                    "seasonId": {".validate": "newData.isString()"},
                    "userName": {".validate": "newData.isString() && newData.val().length >= 2 && newData.val().length <= 40 && newData.val().matches(/^[^<>@]+$/)"},
                    "scores": {
                        ".validate": "newData.hasChildren(['ambientacion','acting','organizacion','terror','variedad'])",
                        **{category: {".validate": score_rule} for category in CATEGORIES},
                        "$other": {".validate": False},
                    },
                    "text": {".validate": "newData.isString() && newData.val().length >= 10 && newData.val().length <= 10000"},
                    "createdAt": {".validate": "newData.isNumber()"},
                    "updatedAt": {".validate": "newData.isNumber()"},
                    "revision": {".validate": "newData.isNumber()"},
                    "$other": {".validate": False},
                },
            }
        }
    }
    text = RULES.read_text(encoding="utf-8")
    marker = next((item for item in MARKERS if item in text), None)
    if marker:
        start = text.index(marker)
        end = text.index('    "profiles": {', start)
        text = text[:start] + text[end:]
    payload = "".join(f"    {json.dumps(name)}: {json.dumps(value, ensure_ascii=False, indent=2).replace(chr(10), chr(10) + '    ')},\n"
                      for name, value in branch.items())
    text = text.replace('    "profiles": {', payload + '    "profiles": {', 1)
    RULES.write_text(text, encoding="utf-8")


if __name__ == "__main__":
    main()
