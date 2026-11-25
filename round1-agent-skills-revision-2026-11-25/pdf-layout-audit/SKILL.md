---
name: pdf-layout-audit
description: 'Extract research PDFs into page-addressed reading order, sections, tables, figures and equations. Use for multicolumn layouts, scans or PDF evidence retrieval.'
---

# 文献文档解析

## Case and output contract

Read `/input/case.json`, `/input/task.md` and the actual input files before planning. Treat the case's requested outputs, field types and artifact names as authoritative. Work in `/app/work` and save editable deliverables and `/app/output/result.json` early, then revise them after verification. Preserve the exact `case_id` and all `output_contract` fields. Keep source locations, unresolved issues, changes and run status in the requested fields. For unstructured source locations use filename plus PDF frame and printed label when available, or heading and paragraph, figure, table cell or log line. Keep file paths in the result relative to its output directory when the case permits. Use `environment/resources.yaml` when the case supplies resource definitions, and verify an executable exists before depending on it. Report each actual unavailable action and save the usable portion if the result is partial.

## Prepare and finalize the case

Run the standard-library helper with `python3 run.py`. It inventories the actual inputs and writes an initial `result.json` when the output directory lacks one. In evidence, editing, translation and introduction work it also writes a literal text anchor catalog to `/app/work/source-anchors.json`. Use the workflow below to produce the requested case-specific files and a candidate JSON in `/app/work`. Finalize with `python3 run.py --draft /app/work/candidate.json`. On another machine pass `--input CASE_DIR --output OUTPUT_DIR --work WORK_DIR`. Reopen the final JSON against the real case schema. If that schema requires values unavailable from the source, represent the gap as the contract permits. A missing field affects the corresponding finding while work continues on the supported findings.

## Workflow

After ordering physical blocks, preserve a separate paragraph sequence with references to every contributing block. Join a column or page boundary only when neighboring syntax, indent and section context agree, and when neither candidate is a heading, caption, note or table cell. Preserve hyphens inside scientific compound terms unless the rendering confirms a soft wrap. Link superscript markers to footnote blocks without moving note text into the paragraph. For tables, export cell text by row and column with explicit blanks and retain header/context cells independently. Include a sample of verified transitions and table rows in your result.


1. Inventory only the requested files and pages. Record PDF frame (1-based physical page) separately from printed label. Run `pdfinfo` and, for digital text, `python3 pdf_blocks.py SOURCE.pdf /app/work/blocks.json`. Independently render the first, last and any anomalous or task-critical pages with `pdftoppm -f N -l N -r 180 -png SOURCE.pdf /app/work/page`. Use page images to adjudicate order or symbols, especially a caption spanning both columns or a section crossing a page boundary.
2. Build a page block inventory in visual order (type, text, page, bbox, extraction method). Keep repeated running heads, footers, marginalia and notes as separate blocks. Preserve source line text in evidence, while recording any repaired line wrapping separately. Correct row order by bounding boxes, never by splitting at the center of a line. Within a band, finish one column before starting the next, unless evidence shows another reading direction.
3. Keep caption and figure/table references linked by printed IDs. For tables, align by geometric column boundaries, preserve multilevel headers and merged cells, and export raw text plus row/column indices and cell bounding boxes. Join continued tables only if identifier, header structure and column alignment agree. Use null for unreadable cells with evidence of the missing area. Where the assignment needs formulas, transcribe a verified image crop to LaTeX alongside raw extraction and flag lost or ambiguous superscripts, operators and Greek letters.
4. For a page with an absent or broken text layer, render selected pages at 300 dpi and use Tesseract TSV if available. Select an installed language from `tesseract --list-langs`, group by block/paragraph/line, and map pixels to page coordinates. Visually verify any reused formula, number or low-confidence OCR token. For landscape or rotated pages compare the orientation against the rendered image. Preserve searchable text for unaffected pages if a scan, encrypted page or malformed object prevents full processing.
5. Return the requested artifacts and a page/section inventory. Attach page and block IDs to all answers. Include type totals, page coverage, extraction anomalies and unresolved blocks. Compare at least one high-risk text span, table row or equation against its rendering. For native boxes, label units as PDF points in the rendered page orientation, with top-left origin.

## Use and limits

Run `pdf_blocks.py` from this skill's folder using Python 3.9+ with Poppler installed, or invoke it by its absolute path. Its central-gutter detection is a two-column heuristic. For a three-column, rotated or nonstandard layout, verify visual order manually using page renderings. The helper does not OCR or infer tables.

## Minimal example

Synthetic call: `python3 pdf_blocks.py sample.pdf blocks.json`. A cross-column heading may be represented as `{"page":2,"id":"p2-b1","bbox":[48,52,557,76],"text":"Results"}`. This illustrates the interface.
