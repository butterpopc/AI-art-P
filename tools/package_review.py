#!/usr/bin/env python3
"""Build an offline review ZIP from an explicit, credential-free allowlist."""
import hashlib
import json
from pathlib import Path
import struct
import zipfile

ROOT = Path(__file__).resolve().parents[1]
SELECTED = [
    "seorin-key-visual-v1.png",
    "seorin-turnaround-v2.png",
    "seorin-expressions-v2.png",
    "seorin-evening-v1.png",
]


def main():
    records = []
    for name in SELECTED:
        path = ROOT / "artwork" / name
        data = path.read_bytes()
        if data[:8] != b"\x89PNG\r\n\x1a\n" or data[12:16] != b"IHDR":
            raise ValueError(f"Invalid PNG: {name}")
        width, height = struct.unpack(">II", data[16:24])
        records.append({
            "file": "artwork/" + name, "width": width, "height": height,
            "sha256": hashlib.sha256(data).hexdigest(), "bytes": len(data),
            "provider": "image_gen", "client_approval": "pending",
        })
    manifest = json.dumps({"package": "seorin-client-review-v2", "images": records}, ensure_ascii=False, indent=2) + "\n"
    delivery = ROOT / "delivery"
    delivery.mkdir(exist_ok=True)
    output = delivery / "seorin-client-review-v2.zip"
    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as archive:
        for name in ["index.html", "CLIENT_REVIEW.md"]:
            archive.write(ROOT / name, name)
        for record in records:
            archive.write(ROOT / record["file"], record["file"])
        archive.writestr("manifest.json", manifest)
    with zipfile.ZipFile(output) as archive:
        if archive.testzip() is not None:
            raise ValueError("ZIP integrity check failed")
    digest = hashlib.sha256(output.read_bytes()).hexdigest()
    output.with_suffix(".sha256").write_text(digest + "  " + output.name + "\n", encoding="utf-8")
    print(json.dumps({"archive": str(output), "images": len(records), "bytes": output.stat().st_size, "sha256": digest}))


if __name__ == "__main__":
    main()
