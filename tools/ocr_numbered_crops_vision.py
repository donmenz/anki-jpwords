#!/usr/bin/env python3
"""Re-OCR numbered entries as isolated 240-dpi crops, preserving every source span."""
from __future__ import annotations

import argparse
import json
import math
import subprocess
import tempfile
import time
from pathlib import Path
from urllib.request import Request, urlopen


def upload(path: Path, url: str) -> dict:
    image = path.read_bytes()
    boundary = "----CodexNumberedCrop"
    body = (
        (
            f'--{boundary}\r\nContent-Disposition: form-data; name="file"; filename="crop.jpg"\r\n'
            'Content-Type: image/jpeg\r\n\r\n'
        ).encode()
        + image
        + f"\r\n--{boundary}--\r\n".encode()
    )
    request = Request(
        url,
        data=body,
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}", "Accept": "application/json"},
    )
    last_error = None
    for attempt in range(6):
        try:
            with urlopen(request, timeout=90) as response:
                return json.loads(response.read())
        except Exception as error:
            last_error = error
            time.sleep(min(30, 2 ** attempt))
    raise RuntimeError(f"OCR upload failed after retries: {last_error}")


def render_page(pdf: Path, page: int, temp: Path, cache: dict[int, Path]) -> Path:
    if page in cache:
        return cache[page]
    target = temp / f"page-{page:04d}"
    subprocess.run(
        ["pdftoppm", "-f", str(page), "-l", str(page), "-jpeg", "-r", "240", "-singlefile", str(pdf), str(target)],
        check=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    cache[page] = target.with_suffix(".jpg")
    return cache[page]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("pdf", type=Path)
    parser.add_argument("--input", type=Path, default=Path("data/numbered-candidates.json"))
    parser.add_argument("--out", type=Path, default=Path("data/ocr-numbered-crops-vision"))
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
    selected = rows[args.shard_index * chunk : min(len(rows), (args.shard_index + 1) * chunk)]
    completed = 0
    with tempfile.TemporaryDirectory(prefix=f"n1-numbered-crops-{args.shard_index}-") as temp_dir:
        temp = Path(temp_dir)
        rendered: dict[int, Path] = {}
        for row in selected:
            card_id = int(row["id_number"])
            output = args.out / f"entry-{card_id:04d}.json"
            if args.resume and output.is_file():
                completed += 1
                continue
            reference = row["paddle"] or row["vision"]
            parts = []
            for part_index, span in enumerate(reference.get("source_spans") or [{
                "pdf_page": reference["pdf_page"],
                "book_page": reference["book_page"],
                "source_side": reference["source_side"],
                "bbox": reference["source_bbox"],
            }]):
                page = int(span["pdf_page"])
                source = render_page(args.pdf, page, temp, rendered)
                x, y, width, height = [float(value) for value in span["bbox"]]
                x0 = max(0, int((x - 10) * 2))
                y0 = max(0, int((y - 6) * 2))
                crop_width = max(30, int((width + 20) * 2))
                crop_height = max(30, int((height + 12) * 2))
                crop = temp / f"entry-{card_id:04d}-{part_index}.jpg"
                subprocess.run(
                    ["ffmpeg", "-loglevel", "error", "-y", "-i", str(source), "-vf", f"crop={crop_width}:{crop_height}:{x0}:{y0}", str(crop)],
                    check=True,
                )
                result = upload(crop, args.url)
                parts.append({"source_span": span, "ocr": result})
            document = {
                "id_number": card_id,
                "section": row["section"],
                "source_number": row["source_number"],
                "render_dpi": 240,
                "parts": parts,
                "ocr_result": "\n".join(part["ocr"].get("ocr_result", "") for part in parts),
            }
            output.write_text(json.dumps(document, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            completed += 1
            if completed % 50 == 0:
                print(f"shard {args.shard_index}: {completed}/{len(selected)}", flush=True)
    print(f"PASS shard {args.shard_index}: {completed}/{len(selected)} high-resolution entry crops", flush=True)


if __name__ == "__main__":
    main()
