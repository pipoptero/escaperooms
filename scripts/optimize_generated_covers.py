"""Create lightweight WebP variants for generated covers and update public JSON."""

import json
from pathlib import Path

from PIL import Image, ImageOps


ROOT = Path(__file__).resolve().parents[1]
SOURCE_DIR = ROOT / "images" / "generated-catalog"
PUBLIC_JSON = ("catalog.json", "data.json", "published_reviews.json", "review_photos.json")


def replace_paths(value, replacements):
    if isinstance(value, dict):
        return {key: replace_paths(item, replacements) for key, item in value.items()}
    if isinstance(value, list):
        return [replace_paths(item, replacements) for item in value]
    if isinstance(value, str):
        return replacements.get(value.replace("\\", "/"), value)
    return value


def main():
    replacements = {}
    original_bytes = optimized_bytes = 0
    for source in sorted(SOURCE_DIR.glob("*.png")):
        target = source.with_suffix(".webp")
        with Image.open(source) as image:
            image = ImageOps.exif_transpose(image)
            if image.width > 1200 or image.height > 1600:
                image.thumbnail((1200, 1600), Image.Resampling.LANCZOS)
            if image.mode not in {"RGB", "RGBA"}:
                image = image.convert("RGBA" if "transparency" in image.info else "RGB")
            image.save(target, "WEBP", quality=84, method=6)
        source_ref = source.relative_to(ROOT).as_posix()
        replacements[source_ref] = target.relative_to(ROOT).as_posix()
        original_bytes += source.stat().st_size
        optimized_bytes += target.stat().st_size

    for name in PUBLIC_JSON:
        path = ROOT / name
        payload = json.loads(path.read_text(encoding="utf-8"))
        updated = replace_paths(payload, replacements)
        path.write_text(json.dumps(updated, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    saved = original_bytes - optimized_bytes
    print(
        f"{len(replacements)} portadas WebP; "
        f"{original_bytes / 1048576:.1f} MB -> {optimized_bytes / 1048576:.1f} MB "
        f"({saved / 1048576:.1f} MB menos en producción)"
    )


if __name__ == "__main__":
    main()
