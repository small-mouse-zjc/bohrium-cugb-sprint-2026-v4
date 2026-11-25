"""Recover bounded PDF text blocks through Poppler (Python 3.9+ and pdftotext)."""

import argparse
import json
from pathlib import Path
import re
import subprocess
import xml.etree.ElementTree as ET


def coords(element):
    return [round(float(element.attrib[key]), 2) for key in ("xMin", "yMin", "xMax", "yMax")]


def get_blocks(page):
    blocks = []
    for element in page.findall(".//{*}block"):
        lines = []
        for line in element.findall("./{*}line"):
            words = ["".join(word.itertext()) for word in line.findall("./{*}word")]
            if words:
                lines.append({"text": " ".join(words), "bbox": coords(line)})
        if lines:
            blocks.append({"bbox": coords(element),
                           "text": "\n".join(line["text"] for line in lines), "lines": lines})
    return blocks


def spatial_order(blocks, width):
    """Use a supported central gutter within each band; preserve spanning blocks."""
    if not blocks:
        return [], []
    left_edge = min(block["bbox"][0] for block in blocks)
    right_edge = max(block["bbox"][2] for block in blocks)
    ink_width = right_edge - left_edge
    by_position = lambda block: (block["bbox"][1], block["bbox"][0])
    if ink_width < width * 0.3:
        return sorted(blocks, key=by_position), []
    gutter = (left_edge + right_edge) / 2
    tolerance = min(5, ink_width * 0.015)
    barriers = sorted((b for b in blocks if b["bbox"][0] < gutter - tolerance
                       and b["bbox"][2] > gutter + tolerance), key=by_position)
    candidates = [b for b in blocks if b not in barriers]
    result, two_column_bands = [], []

    def emit_band(band):
        left = [b for b in band if b["bbox"][2] <= gutter + tolerance]
        right = [b for b in band if b["bbox"][0] >= gutter - tolerance and b not in left]
        overlap = (bool(left and right) and
                   min(max(b["bbox"][3] for b in left), max(b["bbox"][3] for b in right)) >
                   max(min(b["bbox"][1] for b in left), min(b["bbox"][1] for b in right)))
        if overlap and len(left) + len(right) == len(band):
            two_column_bands.append({"gutter_x": round(gutter, 2),
                                     "block_count": len(band)})
            result.extend(sorted(left, key=by_position))
            result.extend(sorted(right, key=by_position))
        else:
            result.extend(sorted(band, key=by_position))

    for barrier in barriers:
        band = [b for b in candidates if b["bbox"][1] < barrier["bbox"][1]]
        emit_band(band)
        candidates = [b for b in candidates if b not in band]
        result.append(barrier)
    emit_band(candidates)
    return result, two_column_bands


def column_continuations(blocks, width):
    """Suggest adjacent block joins at a column boundary for visual confirmation."""
    gutter = width / 2
    suggestions = []
    for first, second in zip(blocks, blocks[1:]):
        a, b = first["bbox"], second["bbox"]
        left, right = first["text"].strip(), second["text"].strip()
        if a[2] >= gutter + 8 or b[0] <= gutter - 8 or a[1] < b[1] + 24:
            continue
        if not left or not right or left[-1] in '.!?。？！:：':
            continue
        if not right[0].islower() or re.match(r"^(?:figure|fig\.|table|section)\s", right, re.I):
            continue
        # The output keeps each contributing block intact. Layout and scope still need review.
        suggestions.append({"blocks": [first["id"], second["id"]], "status": "review",
                            "reason": "left-to-right column transition and unfinished clause"})
    return suggestions


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("pdf", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--first", type=int, default=1)
    parser.add_argument("--last", type=int)
    args = parser.parse_args()
    if args.first < 1 or (args.last is not None and args.last < args.first):
        parser.error("invalid physical page interval")
    command = ["pdftotext", "-bbox-layout", "-enc", "UTF-8", "-f", str(args.first)]
    if args.last is not None:
        command.extend(["-l", str(args.last)])
    command.extend([str(args.pdf.resolve()), "-"])
    try:
        process = subprocess.run(command, capture_output=True, timeout=120, check=True)
        root = ET.fromstring(process.stdout)
        pages = []
        for position, page in enumerate(root.findall(".//{*}page"), args.first):
            width = float(page.attrib["width"])
            ordered, bands = spatial_order(get_blocks(page), width)
            for index, block in enumerate(ordered, 1):
                block.update({"id": f"p{position}-b{index}", "page": position})
            pages.append({"page": position, "width_pt": width,
                          "height_pt": float(page.attrib["height"]), "blocks": ordered,
                          "estimated_two_column_bands": bands,
                          "paragraph_continuation_candidates": column_continuations(ordered, width),
                          "review": not ordered or any("\ufffd" in b["text"] for b in ordered)})
        if not pages:
            raise ValueError("no page records in Poppler output")
        args.output.write_text(json.dumps({"file": args.pdf.name, "method": "pdftotext -bbox-layout",
                                          "bbox_origin": "top-left", "pages": pages,
                                          "diagnostics": process.stderr.decode("utf-8", "replace")},
                                         ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    except subprocess.CalledProcessError as error:
        parser.exit(2, error.stderr.decode("utf-8", "replace"))
    except (OSError, subprocess.TimeoutExpired, ET.ParseError, KeyError, ValueError) as error:
        parser.exit(2, f"PDF extraction: {error}\n")


if __name__ == "__main__":
    main()
