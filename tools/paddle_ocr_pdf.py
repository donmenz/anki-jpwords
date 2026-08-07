#!/usr/bin/env python3
"""Column OCR for scanned Japanese wordbooks using one local PaddleOCR model."""
from __future__ import annotations

import argparse
import json
import subprocess
import tempfile
from pathlib import Path

from paddleocr import PaddleOCR


def dimensions(path: Path) -> tuple[int, int]:
    output = subprocess.check_output(
        ["sips", "-g", "pixelWidth", "-g", "pixelHeight", str(path)], text=True
    )
    values = [int(line.split(":", 1)[1].strip()) for line in output.splitlines() if ":" in line]
    return values[-2], values[-1]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("pdf", type=Path)
    parser.add_argument("out", type=Path)
    parser.add_argument("--start", type=int)
    parser.add_argument("--end", type=int)
    parser.add_argument("--pages", help="Comma-separated PDF page numbers to process.")
    parser.add_argument("--dpi", type=int, default=120)
    parser.add_argument("--content-height", type=int, help="Source-image body height after the 40px top margin.")
    parser.add_argument("--resume", action="store_true", help="Skip pages whose JSON output already exists.")
    args = parser.parse_args()
    if args.pages:
        pages = [int(value) for value in args.pages.split(",") if value.strip()]
    elif args.start is not None and args.end is not None:
        pages = list(range(args.start, args.end + 1))
    else:
        parser.error("supply --pages or both --start and --end")
    args.out.mkdir(parents=True, exist_ok=True)
    ocr = PaddleOCR(
        lang="japan",
        use_doc_orientation_classify=False,
        use_doc_unwarping=False,
        use_textline_orientation=False,
    )
    with tempfile.TemporaryDirectory(prefix="n1-paddle-") as temp_dir:
        temp = Path(temp_dir)
        for index, page in enumerate(pages, start=1):
            output_path = args.out / f"page-{page:04d}.json"
            if args.resume and output_path.is_file():
                print(f"{index}/{len(pages)} (PDF {page}, cached)", flush=True)
                continue
            rendered = temp / f"page-{page:04d}"
            subprocess.run(
                ["pdftoppm", "-f", str(page), "-l", str(page), "-jpeg", "-r", str(args.dpi), "-singlefile", str(args.pdf), str(rendered)],
                check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            )
            source = rendered.with_suffix(".jpg")
            width, height = dimensions(source)
            content_height = min(height - 80, args.content_height or 800)
            columns = ((40, width // 2 + 4), (width // 2 - 4, width - 30))
            inputs: list[str] = []
            for side, (x0, x1) in enumerate(columns):
                cropped = temp / f"page-{page:04d}-{side}.jpg"
                subprocess.run(
                    ["ffmpeg", "-loglevel", "error", "-y", "-i", str(source), "-vf", f"crop={x1-x0}:{content_height}:{x0}:40,scale={2*(x1-x0)}:{2*content_height}", str(cropped)],
                    check=True,
                )
                inputs.append(str(cropped))
            sides = []
            for side, result in enumerate(ocr.predict(inputs)):
                x0, _ = columns[side]
                raw_boxes = result["rec_boxes"]
                boxes = raw_boxes.tolist() if hasattr(raw_boxes, "tolist") else raw_boxes
                texts = result["rec_texts"]
                raw_scores = result["rec_scores"]
                scores = raw_scores.tolist() if hasattr(raw_scores, "tolist") else raw_scores
                rows = []
                for text, score, box in zip(texts, scores, boxes):
                    left, top, right, bottom = [int(value) for value in box]
                    rows.append({
                        "text": text,
                        "score": float(score),
                        "x": x0 + left / 2,
                        "y": 40 + top / 2,
                        "w": (right - left) / 2,
                        "h": (bottom - top) / 2,
                    })
                sides.append(rows)
            document = {
                "engine": "PaddleOCR PP-OCRv6",
                "image_width": width,
                "image_height": height,
                "sides": sides,
                "ocr_result": "\n".join(row["text"] for side in sides for row in side),
            }
            output_path.write_text(
                json.dumps(document, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
            )
            print(f"{index}/{len(pages)} (PDF {page})", flush=True)


if __name__ == "__main__":
    main()
