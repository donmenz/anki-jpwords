#!/usr/bin/env python3
"""Re-OCR every advanced entry as an isolated high-resolution crop."""
from __future__ import annotations

import argparse
import json
import math
import subprocess
import tempfile
import time
from collections import defaultdict
from pathlib import Path
from urllib.request import Request, urlopen


def upload(path: Path, url: str) -> dict:
    image = path.read_bytes()
    boundary = "----CodexAdvancedCrop"
    body = (
        f'--{boundary}\r\nContent-Disposition: form-data; name="file"; filename="crop.jpg"\r\nContent-Type: image/jpeg\r\n\r\n'.encode()
        + image
        + f"\r\n--{boundary}--\r\n".encode()
    )
    request = Request(url, data=body, headers={"Content-Type": f"multipart/form-data; boundary={boundary}", "Accept": "application/json"})
    last_error = None
    for attempt in range(6):
        try:
            with urlopen(request, timeout=90) as response:
                return json.loads(response.read())
        except Exception as error:
            last_error = error
            time.sleep(min(30, 2 ** attempt))
    raise RuntimeError(f"OCR upload failed after retries: {last_error}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("pdf", type=Path)
    parser.add_argument("--input", type=Path, default=Path("data/advanced-candidates.json"))
    parser.add_argument("--out", type=Path, default=Path("data/ocr-advanced-crops-vision"))
    parser.add_argument("--url", default="http://127.0.0.1:8000/upload")
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--shard-index", type=int, default=0)
    parser.add_argument("--shard-count", type=int, default=1)
    args = parser.parse_args()
    if not 0 <= args.shard_index < args.shard_count:
        parser.error("shard-index must satisfy 0 <= index < shard-count")
    args.out.mkdir(parents=True, exist_ok=True)
    rows = json.loads(args.input.read_text(encoding="utf-8"))
    chunk = math.ceil(len(rows) / args.shard_count)
    rows = rows[args.shard_index * chunk : min(len(rows), (args.shard_index + 1) * chunk)]
    by_page: dict[int, list[dict]] = defaultdict(list)
    for row in rows:
        by_page[int(row["pdf_page"])].append(row)
    completed = 0
    with tempfile.TemporaryDirectory(prefix="n1-advanced-crops-") as temp_dir:
        temp = Path(temp_dir)
        for page, page_rows in sorted(by_page.items()):
            rendered = temp / f"page-{page:04d}"
            subprocess.run(
                ["pdftoppm", "-f", str(page), "-l", str(page), "-jpeg", "-r", "240", "-singlefile", str(args.pdf), str(rendered)],
                check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            )
            source = rendered.with_suffix(".jpg")
            for row in page_rows:
                output = args.out / f"entry-{int(row['id_number']):04d}.json"
                if args.resume and output.is_file():
                    completed += 1
                    continue
                x, y, width, height = [float(value) for value in row["source_bbox"]]
                x0 = max(0, int((x - 12) * 2))
                y0 = max(0, int((y - 7) * 2))
                crop_width = max(20, int((width + 24) * 2))
                crop_height = max(20, int((height + 14) * 2))
                crop = temp / f"entry-{int(row['id_number']):04d}.jpg"
                subprocess.run(
                    ["ffmpeg", "-loglevel", "error", "-y", "-i", str(source), "-vf", f"crop={crop_width}:{crop_height}:{x0}:{y0}", str(crop)],
                    check=True,
                )
                result = upload(crop, args.url)
                result["id_number"] = row["id_number"]
                result["pdf_page"] = page
                result["source_bbox_120dpi"] = row["source_bbox"]
                result["render_dpi"] = 240
                output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
                completed += 1
                if completed % 25 == 0:
                    print(f"shard {args.shard_index}: {completed}/{len(rows)}", flush=True)
    print(f"PASS shard {args.shard_index}: {completed}/{len(rows)} high-resolution entry crops", flush=True)


if __name__ == "__main__":
    main()
