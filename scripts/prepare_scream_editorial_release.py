"""Prepare one editorial Scream Park review in an isolated product checkout.

The source draft stays private. This command changes only the public registry,
one static SEO page, and the reviews sitemap. It never pushes or touches Firebase.
"""

import argparse
import hashlib
import json
from pathlib import Path
from xml.etree import ElementTree

from build_seo_pages import scream_park_review_page, site_url


ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / "scream-parks" / "editorial-reviews.json"
CATALOG = ROOT / "scream-parks" / "data-2026.json"
SITEMAP = ROOT / "sitemap-reviews.xml"


def prepare(draft_path):
    draft = json.loads(Path(draft_path).read_text(encoding="utf-8"))
    if draft.get("previewOnly") is not True or draft.get("publishable") is not False:
        raise ValueError("The private draft is not guarded")
    if draft.get("schemaVersion") != 1 or len(draft.get("reviews", [])) != 1:
        raise ValueError("Expected exactly one editorial review")
    review = dict(draft["reviews"][0])
    if (review.get("status") != "DRAFT" or review.get("entityId") != "horrorland"
            or review.get("seasonId") != "horrorland-2026"
            or review.get("id") != "horrorland-2026-the-vault"):
        raise ValueError("Review identity mismatch")
    body_hash = hashlib.sha256(review["body"].encode("utf-8")).hexdigest()
    if body_hash != review.get("sourceSha256"):
        raise ValueError("Editorial source hash mismatch")
    entries = json.loads(CATALOG.read_text(encoding="utf-8"))["entries"]
    matches = [entry for entry in entries if entry["id"] == "horrorland"
               and entry["seasonId"] == "horrorland-2026"]
    if len(matches) != 1:
        raise ValueError("Catalog identity is ambiguous")
    existing = json.loads(REGISTRY.read_text(encoding="utf-8"))
    if existing.get("schemaVersion") != 1 or any(item.get("id") != review["id"]
                                                 for item in existing.get("reviews", [])):
        raise ValueError("Registry contains another review")

    review["status"] = "PUBLISHED"  # Candidate checkout only; no deployment here.
    registry = {"schemaVersion": 1, "reviews": [review]}
    page = scream_park_review_page(review, matches[0])
    target = ROOT / "scream-parks" / "reviews" / "horrorland-2026" / "index.html"
    sitemap = SITEMAP.read_text(encoding="utf-8")
    url = site_url("/scream-parks/reviews/horrorland-2026/")
    if sitemap.count(url) > 1 or "</urlset>" not in sitemap:
        raise ValueError("Reviews sitemap is invalid")
    if url not in sitemap:
        sitemap = sitemap.replace("</urlset>", f"  <url><loc>{url}</loc></url>\n</urlset>")
    ElementTree.fromstring(sitemap)

    target.parent.mkdir(parents=True, exist_ok=True)
    REGISTRY.write_text(json.dumps(registry, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    target.write_text(page, encoding="utf-8", newline="\n")
    SITEMAP.write_text(sitemap, encoding="utf-8", newline="\n")
    return {"reviewId": review["id"], "sourceSha256": body_hash,
            "paths": [str(REGISTRY.relative_to(ROOT)), str(target.relative_to(ROOT)),
                      str(SITEMAP.relative_to(ROOT))]}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--draft", type=Path, required=True)
    print(json.dumps(prepare(parser.parse_args().draft), sort_keys=True))
